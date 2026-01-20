#!/bin/bash
#
# Brainchain Installation Script
#
# Usage:
#   ./install.sh              # Install with uv
#   ./install.sh --uninstall  # Uninstall
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/brainchain"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Check uv installed
check_uv() {
    if ! command -v uv &> /dev/null; then
        error "uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
    fi
}

# Install with uv tool
install() {
    check_uv

    echo ""
    echo "╔═══════════════════════════════════════╗"
    echo "║     Brainchain Installation           ║"
    echo "╚═══════════════════════════════════════╝"
    echo ""

    info "Installing with uv tool (full features)..."
    cd "$SCRIPT_DIR"
    uv tool install -e ".[all]" --force
    success "Installed to ~/.local/bin/brainchain (with MCP + LSP)"

    # Initialize config
    init_config

    # Verify
    echo ""
    info "Verifying..."
    if command -v brainchain &> /dev/null; then
        success "brainchain command available"
    else
        warn "Add ~/.local/bin to PATH:"
        echo '  export PATH="$HOME/.local/bin:$PATH"'
    fi

    echo ""
    echo "╔═══════════════════════════════════════╗"
    echo "║     Installation Complete!            ║"
    echo "╚═══════════════════════════════════════╝"
    echo ""
    echo "Quick start:"
    echo "  brainchain --help           Show all options"
    echo "  brainchain --list           List agents and roles"
    echo "  brainchain --workflow       Run full workflow"
    echo ""
}

# Uninstall
uninstall() {
    check_uv

    info "Uninstalling brainchain..."
    uv tool uninstall brainchain 2>/dev/null || true
    success "Uninstalled"

    echo ""
    echo "Config preserved at: $CONFIG_DIR"
    echo "To remove config: rm -rf $CONFIG_DIR"
}

# Initialize config
init_config() {
    info "Initializing configuration..."

    mkdir -p "$CONFIG_DIR/prompts"

    # Copy config.toml
    if [ ! -f "$CONFIG_DIR/config.toml" ]; then
        if [ -f "$SCRIPT_DIR/config.toml" ]; then
            cp "$SCRIPT_DIR/config.toml" "$CONFIG_DIR/config.toml"
            success "Copied config.toml"
        fi
    else
        warn "Config exists: $CONFIG_DIR/config.toml"
    fi

    # Copy prompts
    if [ -d "$SCRIPT_DIR/prompts" ]; then
        for f in "$SCRIPT_DIR/prompts"/*.md; do
            [ -f "$f" ] || continue
            local name=$(basename "$f")
            if [ ! -f "$CONFIG_DIR/prompts/$name" ]; then
                cp "$f" "$CONFIG_DIR/prompts/"
            fi
        done
        success "Copied prompts"
    fi

    success "Config: $CONFIG_DIR"
}

# Main
case "${1:-}" in
    --uninstall|-u)
        uninstall
        ;;
    --help|-h)
        echo "Usage: $0 [--uninstall]"
        echo ""
        echo "Options:"
        echo "  --uninstall, -u    Uninstall brainchain"
        echo "  --help, -h         Show this help"
        ;;
    *)
        install
        ;;
esac
