# Clock Hand Images

This directory contains hand image sets for the clock.

## Structure

Each hand set should be in its own subdirectory with the following structure:

```
<hand_set_name>/
├── original/       # Original source images (preserved)
│   ├── hour.png
│   ├── minute.png
│   └── second.png
└── processed/      # Processed images (used by app, auto-generated)
    ├── hour.png
    ├── minute.png
    └── second.png
```

**Important:**
- Place your original hand images in the `original/` subdirectory
- Run `validate_hand_images.py` to generate processed versions
- The application uses images from `processed/` directory
- Original images are never modified

All hand images should be:
- In 12 o'clock position (pointing straight up)
- PNG format with transparency
- **Must contain exactly one red pixel RGB(255, 0, 0) marking the rotation center**
- The red pixel defines where the hand rotates around the clock center

## Example Structure

```
assets/hands/
├── classic/
│   ├── original/
│   │   ├── hour.png
│   │   ├── minute.png
│   │   └── second.png
│   └── processed/
│       ├── hour.png
│       ├── minute.png
│       └── second.png
├── modern/
│   ├── original/
│   │   ├── hour.png
│   │   ├── minute.png
│   │   └── second.png
│   └── processed/
│       ├── hour.png
│       ├── minute.png
│       └── second.png
└── ornate/
    ├── original/
    │   ├── hour.png
    │   ├── minute.png
    │   └── second.png
    └── processed/
        ├── hour.png
        ├── minute.png
        └── second.png
```

## Image Guidelines

- **Hour hand**: Should be shorter and thicker
- **Minute hand**: Should be longer and thinner
- **Second hand**: Should be the longest and thinnest
- **Red pixel**: Place exactly one red pixel RGB(255, 0, 0) at the point where the hand should rotate
  - This is typically at the base of the hand where it connects to the clock center
  - The red pixel will not be visible in the final render
- Use transparency for the background
- Recommended size: 200-400px height for best quality

## Red Pixel and Scaling

The red pixel serves two purposes:
1. **Rotation center**: The hand rotates around this point
2. **Length reference**: The distance from the red pixel to the top edge (y=0) defines the hand's length

**Scaling behavior:**
- **Length**: Distance from red pixel to top of image is scaled to match the theme's `hand_length` property
- **Width**: Image width is scaled to match the theme's `hand_width` property

**Example:**
For a hand pointing upward (12 o'clock position):
- If the hand is 200px tall and the rotation point is 20px from the bottom
- Place the red pixel at coordinates (center_x, 180) where center_x is the horizontal center
- The distance from red pixel to top (180 pixels) will be scaled to match the configured hand length
- The image width will be scaled independently based on the configured hand width

## Processing Hand Images

Use the `validate_hand_images.py` script to process your hand images:

```bash
# Basic usage (default tolerance: 30)
python3 validate_hand_images.py <hand_set_name>

# With custom tolerance for near-black pixels
python3 validate_hand_images.py <hand_set_name> --tolerance 40
```

**What the script does:**
1. Validates that all three hand images exist in `original/` directory
2. Verifies each image is PNG format
3. Checks for exactly one red pixel (rotation center) in each image
4. Processes images to keep only black/near-black pixels and the red pixel
5. Makes all other pixels fully transparent
6. Saves processed images to `processed/` directory

**Tolerance parameter:**
- Default: 30
- Pixels with R, G, B all ≤ tolerance are considered "black" and kept
- Higher tolerance = more pixels kept (useful for anti-aliased edges)
- Lower tolerance = only very dark pixels kept

**Example:**
```bash
# Process the "classic" hand set with default tolerance
python3 validate_hand_images.py classic

# Process with higher tolerance to keep more near-black pixels
python3 validate_hand_images.py classic --tolerance 50
```
