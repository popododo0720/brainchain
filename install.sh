#!/bin/bash
set -e

INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing brainchain..."

# Copy executable
cp "$SCRIPT_DIR/brainchain.py" "$INSTALL_DIR/brainchain"
chmod +x "$INSTALL_DIR/brainchain"
echo "Installed: $INSTALL_DIR/brainchain"

# Initialize config if not exists
if [ ! -d "$HOME/.config/brainchain" ]; then
    "$INSTALL_DIR/brainchain" --init
fi

echo ""
echo "Done! Run: brainchain --help"
