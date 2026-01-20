#!/bin/bash
#
# Brainchain Installation Script
#
# Usage:
#   ./install.sh              # Install with uv (full features + Claude Code integration)
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
CYAN='\033[0;36m'
NC='\033[0m'

info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
step() { echo -e "${CYAN}[STEP]${NC} $1"; }

# Check uv installed
check_uv() {
    if ! command -v uv &> /dev/null; then
        error "uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
    fi
}

# Generate CLAUDE.md from prompts
generate_claude_md() {
    local output="$SCRIPT_DIR/CLAUDE.md"

    step "Generating CLAUDE.md..."

    # Start with orchestrator prompt
    cat "$SCRIPT_DIR/prompts/orchestrator.md" > "$output"

    # Add separator
    cat >> "$output" << 'EOF'

---
## Available Role Prompts

EOF

    # Extract role mappings from config.toml
    cat >> "$output" << 'EOF'
### Role → Agent Mapping

| Role | Agent | Model | Reasoning |
|------|-------|-------|-----------|
EOF

    # Parse config.toml for roles (simplified grep approach)
    if [ -f "$SCRIPT_DIR/config.toml" ]; then
        grep -A3 '^\[roles\.' "$SCRIPT_DIR/config.toml" 2>/dev/null | \
        awk '
            /^\[roles\./ {
                gsub(/\[roles\./, ""); gsub(/\]/, ""); role=$0
            }
            /^agent/ { agent=$3; gsub(/"/, "", agent) }
            /^model/ { model=$3; gsub(/"/, "", model) }
            /^effort/ {
                effort=$3; gsub(/"/, "", effort)
                printf "| %s | %s | %s | %s |\n", role, agent, model, effort
            }
        ' >> "$output"
    fi

    # Add parallel execution hint
    cat >> "$output" << 'EOF'

### Parallel Execution

```bash
echo '[{"role":"implementer","prompt":"Task 1","id":"t1"}]' | brainchain --parallel -
```

EOF

    # Add each role prompt
    cat >> "$output" << 'EOF'
### Role Prompt Details

EOF

    for prompt_file in "$SCRIPT_DIR/prompts"/*.md; do
        [ -f "$prompt_file" ] || continue
        local name=$(basename "$prompt_file" .md)

        # Skip orchestrator (already included)
        [ "$name" = "orchestrator" ] && continue

        # Get agent name from config
        local agent=$(grep -A1 "^\[roles\.$name\]" "$SCRIPT_DIR/config.toml" 2>/dev/null | grep "agent" | cut -d'"' -f2)
        [ -z "$agent" ] && agent="unknown"

        cat >> "$output" << EOF

#### $name (uses $agent)

\`\`\`
$(cat "$prompt_file")
\`\`\`

EOF
    done

    success "Generated CLAUDE.md"
}

# Setup Claude Code integration
setup_claude_code() {
    step "Setting up Claude Code integration..."

    local claude_dir="$SCRIPT_DIR/.claude"
    mkdir -p "$claude_dir"

    # Create settings.local.json with permissions
    cat > "$claude_dir/settings.local.json" << 'EOF'
{
  "permissions": {
    "allow": [
      "Bash(uv run brainchain:*)",
      "Bash(uv run python -m brainchain:*)",
      "Bash(brainchain:*)",
      "Bash(uv sync:*)",
      "Bash(uv run pytest:*)",
      "Bash(git:*)",
      "WebSearch",
      "WebFetch"
    ]
  }
}
EOF
    success "Created .claude/settings.local.json"

    # Generate CLAUDE.md
    generate_claude_md
}

# Install with uv tool
install() {
    check_uv

    echo ""
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║           Brainchain Installation                     ║"
    echo "║     Multi-Agent Orchestrator for Claude Code          ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo ""

    # Step 1: Install Python package
    step "Installing brainchain with all features..."
    cd "$SCRIPT_DIR"
    uv sync --extra all
    success "Installed dependencies (MCP + LSP + TUI)"

    # Step 2: Install as global tool
    step "Installing as global tool..."
    uv tool install -e ".[all]" --force 2>/dev/null || true
    success "Installed to ~/.local/bin/brainchain"

    # Step 3: Setup Claude Code
    setup_claude_code

    # Step 4: Initialize user config
    init_config

    # Verify
    echo ""
    step "Verifying installation..."

    if command -v brainchain &> /dev/null; then
        success "brainchain command available"
    else
        warn "Add ~/.local/bin to PATH:"
        echo '  export PATH="$HOME/.local/bin:$PATH"'
    fi

    # Check TUI
    if uv run python -c "import textual" 2>/dev/null; then
        success "TUI (textual) available"
    else
        warn "TUI not available"
    fi

    echo ""
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║              Installation Complete!                   ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo ""
    echo -e "${GREEN}Usage:${NC}"
    echo ""
    echo -e "  ${CYAN}# Run in this directory with Claude Code${NC}"
    echo "  cd $SCRIPT_DIR && claude"
    echo ""
    echo -e "  ${CYAN}# Or use brainchain CLI directly${NC}"
    echo "  brainchain --help           # Show all options"
    echo "  brainchain --tui            # Launch TUI dashboard"
    echo "  brainchain --list           # List agents and roles"
    echo ""
}

# Uninstall
uninstall() {
    check_uv

    info "Uninstalling brainchain..."
    uv tool uninstall brainchain 2>/dev/null || true
    success "Uninstalled global tool"

    # Remove CLAUDE.md
    if [ -f "$SCRIPT_DIR/CLAUDE.md" ]; then
        rm "$SCRIPT_DIR/CLAUDE.md"
        success "Removed CLAUDE.md"
    fi

    echo ""
    echo "Config preserved at: $CONFIG_DIR"
    echo "To remove config: rm -rf $CONFIG_DIR"
    echo "To remove .claude: rm -rf $SCRIPT_DIR/.claude"
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
