#!/bin/bash
#
# Brainchain Installation Script (Go version)
#
# Usage:
#   ./install.sh              # Build and install
#   ./install.sh --uninstall  # Uninstall
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/brainchain"
BIN_DIR="$HOME/.local/bin"

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

check_go() {
    if ! command -v go &> /dev/null; then
        error "Go not found. Install from https://go.dev/dl/"
    fi
    local version=$(go version | grep -oP 'go\d+\.\d+')
    info "Found Go $version"
}

generate_claude_md() {
    local output="$SCRIPT_DIR/CLAUDE.md"

    step "Generating CLAUDE.md..."

    cat "$SCRIPT_DIR/prompts/orchestrator.md" > "$output"

    cat >> "$output" << 'EOF'

---
## Available Role Prompts

### Role → Agent Mapping

| Role | Agent | Model | Reasoning |
|------|-------|-------|-----------|
EOF

    if [ -f "$SCRIPT_DIR/config.toml" ]; then
        grep -A3 '^\[roles\.' "$SCRIPT_DIR/config.toml" 2>/dev/null | \
        awk '
            /^\[roles\./ {
                gsub(/\[roles\./, ""); gsub(/\]/, ""); role=$0
            }
            /^agent/ { agent=$3; gsub(/"/, "", agent) }
        ' >> "$output" || true
    fi

    cat >> "$output" << 'EOF'

### Parallel Execution

```bash
echo '[{"role":"implementer","prompt":"Task 1","id":"t1"}]' | brainchain --parallel -
```

### Role Prompt Details

EOF

    for prompt_file in "$SCRIPT_DIR/prompts"/*.md; do
        [ -f "$prompt_file" ] || continue
        local name=$(basename "$prompt_file" .md)
        [ "$name" = "orchestrator" ] && continue

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

setup_claude_code() {
    step "Setting up Claude Code integration..."

    local claude_dir="$SCRIPT_DIR/.claude"
    mkdir -p "$claude_dir"

    cat > "$claude_dir/settings.local.json" << 'EOF'
{
  "permissions": {
    "allow": ["*"]
  }
}
EOF
    success "Created .claude/settings.local.json"

    generate_claude_md
}

install() {
    check_go

    echo ""
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║           Brainchain Installation (Go)                ║"
    echo "║     Multi-Agent Orchestrator for Claude Code          ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo ""

    step "Building brainchain..."
    cd "$SCRIPT_DIR/cmd/chat"
    go build -o brainchain .
    success "Built brainchain binary"

    step "Installing to $BIN_DIR..."
    mkdir -p "$BIN_DIR"
    cp brainchain "$BIN_DIR/brainchain"
    chmod +x "$BIN_DIR/brainchain"
    success "Installed to $BIN_DIR/brainchain"

    setup_claude_code
    init_config

    echo ""
    step "Verifying installation..."

    if command -v brainchain &> /dev/null; then
        success "brainchain command available"
    else
        warn "Add ~/.local/bin to PATH:"
        echo '  export PATH="$HOME/.local/bin:$PATH"'
    fi

    echo ""
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║              Installation Complete!                   ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo ""
    echo -e "${GREEN}Usage:${NC}"
    echo ""
    echo -e "  ${CYAN}# Run TUI${NC}"
    echo "  brainchain"
    echo ""
    echo -e "  ${CYAN}# CLI commands${NC}"
    echo "  brainchain --help           # Show all options"
    echo "  brainchain --list           # List agents and roles"
    echo "  brainchain --exec planner -p 'Create auth system'"
    echo "  brainchain --workflow -p 'Build REST API'"
    echo ""
    echo -e "  ${CYAN}# With Claude Code${NC}"
    echo "  cd $SCRIPT_DIR && claude"
    echo ""
}

uninstall() {
    info "Uninstalling brainchain..."
    
    if [ -f "$BIN_DIR/brainchain" ]; then
        rm "$BIN_DIR/brainchain"
        success "Removed $BIN_DIR/brainchain"
    fi

    if [ -f "$SCRIPT_DIR/CLAUDE.md" ]; then
        rm "$SCRIPT_DIR/CLAUDE.md"
        success "Removed CLAUDE.md"
    fi

    echo ""
    echo "Config preserved at: $CONFIG_DIR"
    echo "To remove config: rm -rf $CONFIG_DIR"
    echo "To remove .claude: rm -rf $SCRIPT_DIR/.claude"
}

init_config() {
    info "Initializing configuration..."

    mkdir -p "$CONFIG_DIR/prompts"

    if [ ! -f "$CONFIG_DIR/config.toml" ]; then
        if [ -f "$SCRIPT_DIR/config.toml" ]; then
            cp "$SCRIPT_DIR/config.toml" "$CONFIG_DIR/config.toml"
            success "Copied config.toml"
        fi
    else
        warn "Config exists: $CONFIG_DIR/config.toml"
    fi

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
