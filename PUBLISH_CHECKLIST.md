# Snap Store Publishing Checklist

## Remaining Tasks

### Screenshots
- [ ] Take 5 screenshots showing different features
- [ ] Minimum size: 480x480, recommended: 800x600 or 1024x768
- [ ] Crop to focus on the clock (not full desktop)
- [ ] Save to `screenshots/` directory

**Recommended shots:**
1. Hero shot - Clock on desktop showing transparency (with some background context)
2. Default theme - Tightly cropped clock
3. Different theme - Show theme variety (e.g., breguet hands)
4. With date display - Show date feature
5. Customization dialog - Show appearance settings

**How to take:**
```bash
# Create screenshots directory
mkdir -p screenshots

# Run the clock
./launch_clock.sh

# Position clock on an interesting background

# Take area screenshot (drag to select clock + minimal context)
gnome-screenshot -a -f screenshots/01-hero-transparent.png

# Change themes/settings and repeat
gnome-screenshot -a -f screenshots/02-default-theme.png
gnome-screenshot -a -f screenshots/03-breguet-theme.png
gnome-screenshot -a -f screenshots/04-with-date.png

# Open customization dialog and screenshot it
gnome-screenshot -a -f screenshots/05-customization.png

# Verify sizes (should be 800x600 or larger)
file screenshots/*.png
```

## Release Branch

### Create Release Branch
```bash
# Extract version from snapcraft.yaml
VERSION=$(grep "^version:" snapcraft.yaml | awk '{print $2}' | tr -d "'\"")

# Create and switch to release branch
git checkout -b release/v${VERSION}

# Ensure snapcraft.yaml version is correct
grep "^version:" snapcraft.yaml

# Commit any final changes
git add .
git commit -m "Prepare release v${VERSION}"

# Push release branch
git push -u origin release/v${VERSION}
```

## Build Steps

### 1. Prepare Files
```bash
# Ensure all files are in place
ls -la snapcraft.yaml snap/gui/icon.png LICENSE
```

### 2. Build and Test Locally
```bash
# Build, install, and test in one step
./rebuild_snap.sh

# Test: drag, close, reopen - verify position saved
# The snap file will be in build/dsclock_<version>_amd64.snap (version from snapcraft.yaml)
```

### 3. Publish
```bash
# Login
snapcraft login

# Register name (one-time)
snapcraft register dsclock

# Upload
snapcraft upload build/dsclock_*.snap

# Release to stable
snapcraft release dsclock 1 stable
```

## Store Listing

After publishing, fill out on https://snapcraft.io/dsclock/listing:

- [ ] Upload screenshots (3-5 images)
- [ ] Set category to Utilities
- [ ] Verify all metadata from snapcraft.yaml appears correctly

## After Publishing

Users can install with:
```bash
snap install dsclock
```

And run with:
```bash
dsclock
```

## Updates

When you make changes:

```bash
# 1. Update version in snapcraft.yaml
# Edit: version: '<new_version>'
NEW_VERSION="<new_version>"  # e.g., '1.2.0'

# 2. Create new release branch
git checkout -b release/v${NEW_VERSION}

# 3. Commit and push
git add snapcraft.yaml
git commit -m "Bump version to ${NEW_VERSION}"
git push -u origin release/v${NEW_VERSION}

# 4. Build and publish
./rebuild_snap.sh
snapcraft upload build/dsclock_*.snap
snapcraft release dsclock <revision> stable

# 5. Merge to main and tag
git checkout main
git merge release/v${NEW_VERSION}
git tag v${NEW_VERSION}
git push origin main --tags
```

Users get automatic updates!

## Help

- Snapcraft docs: https://snapcraft.io/docs
- Forum: https://forum.snapcraft.io/
- Ubuntu Store: https://dashboard.snapcraft.io/
