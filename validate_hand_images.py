#!/usr/bin/env python3
"""
Hand Image Validator and Processor

This script validates and processes hand image sets for the clock application.
It verifies that all required images exist, checks for the red pixel rotation center,
and processes images to keep only black/near-black pixels (making all other pixels transparent).

The script uses a non-destructive approach:
- Original images are kept in: <hand_set>/original/
- Processed images are saved to: <hand_set>/processed/
- The application uses processed images

Usage:
    python3 validate_hand_images.py <hand_set_name> [--tolerance N]
    
Arguments:
    hand_set_name: Name of the hand set directory
    --tolerance N: RGB tolerance for "black" pixels (default: 100)
                   Pixels with R,G,B all <= N are considered black
    
Example:
    python3 validate_hand_images.py classic
    python3 validate_hand_images.py classic --tolerance 40
"""

import sys
import os
import argparse
from PIL import Image


def find_red_pixel(image):
    """
    Find the red pixel (rotation center) in the image.
    Returns (x, y) coordinates or None if not found.
    Red pixel is defined as RGB(255, 0, 0) with full opacity.
    """
    pixels = image.load()
    width, height = image.size
    red_pixels = []
    
    for y in range(height):
        for x in range(width):
            pixel = pixels[x, y]
            
            # Handle both RGB and RGBA
            if len(pixel) == 3:
                r, g, b = pixel
                a = 255
            else:
                r, g, b, a = pixel
            
            # Check if this is a red pixel (255, 0, 0) with full opacity
            if r == 255 and g == 0 and b == 0 and a == 255:
                red_pixels.append((x, y))
    
    return red_pixels


def is_black_pixel(r, g, b, tolerance):
    """
    Check if a pixel is black or near-black within tolerance.
    
    Args:
        r, g, b: RGB values (0-255)
        tolerance: Maximum value for each channel to be considered black
    
    Returns:
        True if pixel is black/near-black, False otherwise
    """
    return r <= tolerance and g <= tolerance and b <= tolerance


def process_image(original_path, processed_path, hand_type, tolerance=100):
    """
    Process a hand image:
    1. Verify it's a PNG
    2. Find and validate the red pixel
    3. Keep only black/near-black pixels and red pixel, make everything else transparent
    4. Save to processed directory (non-destructive)
    
    Args:
        original_path: Path to original image
        processed_path: Path where processed image will be saved
        hand_type: Type of hand (hour, minute, second)
        tolerance: RGB tolerance for black pixels (default: 100)
    
    Returns:
        True if successful, False otherwise.
    """
    print(f"\nProcessing {hand_type} hand:")
    print(f"  Source: {original_path}")
    print(f"  Output: {processed_path}")
    
    # Check if file exists
    if not os.path.exists(original_path):
        print(f"  ❌ ERROR: File does not exist")
        return False
    
    # Check if it's a PNG
    if not original_path.lower().endswith('.png'):
        print(f"  ❌ ERROR: File is not a PNG")
        return False
    
    try:
        # Open image
        img = Image.open(original_path)
        
        # Verify format
        if img.format != 'PNG':
            print(f"  ❌ ERROR: File format is {img.format}, not PNG")
            return False
        
        print(f"  ✓ Format: PNG")
        print(f"  ✓ Size: {img.size[0]}x{img.size[1]} pixels")
        
        # Convert to RGBA if needed
        if img.mode != 'RGBA':
            print(f"  → Converting from {img.mode} to RGBA")
            img = img.convert('RGBA')
        
        # Find red pixel(s)
        red_pixels = find_red_pixel(img)
        
        if len(red_pixels) == 0:
            print(f"  ❌ ERROR: No red pixel found (rotation center missing)")
            return False
        elif len(red_pixels) > 1:
            print(f"  ❌ ERROR: Multiple red pixels found ({len(red_pixels)})")
            print(f"     Locations: {red_pixels}")
            return False
        else:
            pivot_x, pivot_y = red_pixels[0]
            print(f"  ✓ Red pixel found at ({pivot_x}, {pivot_y})")
            distance_to_top = pivot_y
            print(f"  ✓ Distance to top edge: {distance_to_top} pixels")
        
        # Process image: keep only black/near-black pixels and red pixel
        print(f"  → Processing: keeping black pixels (tolerance={tolerance}) and red pixel...")
        pixels = img.load()
        width, height = img.size
        black_count = 0
        red_count = 0
        transparent_count = 0
        
        for y in range(height):
            for x in range(width):
                r, g, b, a = pixels[x, y]
                
                # Always keep the red pixel
                if r == 255 and g == 0 and b == 0 and a == 255:
                    red_count += 1
                    # Keep red pixel as is
                # Replace black/near-black pixels with pure black
                elif is_black_pixel(r, g, b, tolerance):
                    black_count += 1
                    # Normalize to pure black, preserve alpha
                    pixels[x, y] = (0, 0, 0, a)
                else:
                    # Make all other pixels fully transparent
                    pixels[x, y] = (0, 0, 0, 0)
                    transparent_count += 1
        
        print(f"  ✓ Normalized {black_count} black/near-black pixels to pure black")
        print(f"  ✓ Kept {red_count} red pixel(s)")
        print(f"  ✓ Made {transparent_count} pixels transparent")
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(processed_path), exist_ok=True)
        
        # Save the processed image
        img.save(processed_path, 'PNG')
        print(f"  ✓ Saved processed image")
        
        return True
        
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        return False


def validate_hand_set(hand_set_name, tolerance=100):
    """
    Validate and process a complete hand image set.
    
    Args:
        hand_set_name: Name of the hand set directory
        tolerance: RGB tolerance for black pixels
    
    Returns:
        True if all validations and processing succeeded, False otherwise.
    """
    print(f"=" * 70)
    print(f"Validating and processing hand set: {hand_set_name}")
    print(f"Black pixel tolerance: {tolerance}")
    print(f"=" * 70)
    
    # Determine the hand set directory
    # Check in assets/hands first (builtin)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    hand_dir = os.path.join(script_dir, 'assets', 'hands', hand_set_name)
    
    if not os.path.exists(hand_dir):
        # Check in user directory
        user_hands_dir = os.path.expanduser('~/.config/dsclock/hands')
        hand_dir = os.path.join(user_hands_dir, hand_set_name)
        
        if not os.path.exists(hand_dir):
            print(f"\n❌ ERROR: Hand set directory not found")
            print(f"   Checked: {os.path.join(script_dir, 'assets', 'hands', hand_set_name)}")
            print(f"   Checked: {hand_dir}")
            return False
    
    print(f"\nHand set directory: {hand_dir}")
    
    # Set up directory structure
    original_dir = os.path.join(hand_dir, 'original')
    processed_dir = os.path.join(hand_dir, 'processed')
    
    # Check for all three required images in original directory
    required_hands = ['hour', 'minute', 'second']
    original_paths = {}
    processed_paths = {}
    all_exist = True
    
    print(f"\nChecking for required images in original/:")
    for hand_type in required_hands:
        original_path = os.path.join(original_dir, f'{hand_type}.png')
        processed_path = os.path.join(processed_dir, f'{hand_type}.png')
        
        exists = os.path.exists(original_path)
        status = "✓" if exists else "❌"
        print(f"  {status} {hand_type}.png")
        
        if exists:
            original_paths[hand_type] = original_path
            processed_paths[hand_type] = processed_path
        else:
            all_exist = False
    
    if not all_exist:
        print(f"\n❌ FAILED: Not all required images exist in original/ directory")
        print(f"\nExpected structure:")
        print(f"  {hand_dir}/")
        print(f"    original/")
        print(f"      hour.png")
        print(f"      minute.png")
        print(f"      second.png")
        return False
    
    # Process each image
    print(f"\n" + "=" * 70)
    print(f"Processing images...")
    print(f"=" * 70)
    
    success = True
    for hand_type in required_hands:
        if not process_image(original_paths[hand_type], processed_paths[hand_type], 
                           hand_type, tolerance):
            success = False
    
    # Summary
    print(f"\n" + "=" * 70)
    if success:
        print(f"✓ SUCCESS: All images validated and processed")
        print(f"\nProcessed images saved to: {processed_dir}")
    else:
        print(f"❌ FAILED: Some images had errors")
    print(f"=" * 70)
    
    return success


def main():
    parser = argparse.ArgumentParser(
        description='Validate and process hand image sets for the clock application.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 validate_hand_images.py classic
  python3 validate_hand_images.py classic --tolerance 40

Directory structure:
  <hand_set>/
    original/       # Original images (preserved)
      hour.png
      minute.png
      second.png
    processed/      # Processed images (used by app)
      hour.png
      minute.png
      second.png
        """
    )
    
    parser.add_argument('hand_set_name', help='Name of the hand set directory')
    parser.add_argument('--tolerance', type=int, default=100,
                       help='RGB tolerance for black pixels (default: 100)')
    
    args = parser.parse_args()
    
    if args.tolerance < 0 or args.tolerance > 255:
        print("Error: Tolerance must be between 0 and 255")
        sys.exit(1)
    
    success = validate_hand_set(args.hand_set_name, args.tolerance)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
