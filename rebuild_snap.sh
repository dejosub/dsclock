#!/bin/bash
# Rebuild and reinstall the snap locally

set -e  # Exit on error

# Create build output directory
mkdir -p build

echo "Removing old snap..."
sudo snap remove dsclock 2>/dev/null || true

echo "Cleaning build artifacts..."
snapcraft clean
sudo rm -rf parts/ stage/ prime/

echo "Building snap..."
sudo snapcraft pack --destructive-mode

# Move snap file to build directory
echo "Moving snap to build directory..."
mv *.snap build/

echo "Installing snap..."
VERSION=$(grep "^version:" snapcraft.yaml | awk '{print $2}' | tr -d "'\"")
sudo snap install build/dsclock_${VERSION}_amd64.snap --dangerous

echo "Done! Starting the clock..."
nohup dsclock >/dev/null 2>&1 &
