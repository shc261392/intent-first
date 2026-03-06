#!/usr/bin/env bash
# intent-first installer
# https://github.com/shc261392/intent-first
#
# One-liner:
#   curl -fsSL https://raw.githubusercontent.com/shc261392/intent-first/main/install.sh | bash
#
set -euo pipefail

REPO="shc261392/intent-first"
BRANCH="main"
RAW="https://raw.githubusercontent.com/$REPO/$BRANCH"

# Colors (if terminal supports it)
if [ -t 1 ]; then
  BOLD='\033[1m'
  GREEN='\033[0;32m'
  YELLOW='\033[0;33m'
  CYAN='\033[0;36m'
  RESET='\033[0m'
else
  BOLD='' GREEN='' YELLOW='' CYAN='' RESET=''
fi

info()  { echo -e "${GREEN}✓${RESET} $*"; }
warn()  { echo -e "${YELLOW}⚠${RESET} $*"; }
step()  { echo -e "${CYAN}→${RESET} $*"; }
header(){ echo -e "\n${BOLD}$*${RESET}"; }

# ── Detect OS ──────────────────────────────────────────────────
detect_os() {
  case "$(uname -s)" in
    Linux*)   OS="linux" ;;
    Darwin*)  OS="macos" ;;
    MINGW*|MSYS*|CYGWIN*) OS="windows" ;;
    *)        OS="unknown" ;;
  esac
  echo "$OS"
}

# ── Detect available download tool ─────────────────────────────
detect_downloader() {
  if command -v curl &>/dev/null; then
    echo "curl"
  elif command -v wget &>/dev/null; then
    echo "wget"
  else
    echo ""
  fi
}

download() {
  local url="$1" dest="$2"
  case "$DOWNLOADER" in
    curl) curl -fsSL --proto '=https' "$url" -o "$dest" ;;
    wget) wget --https-only -qO "$dest" "$url" ;;
    *)    echo "No download tool found (need curl or wget)"; exit 1 ;;
  esac
}

download_text() {
  local url="$1"
  case "$DOWNLOADER" in
    curl) curl -fsSL --proto '=https' "$url" ;;
    wget) wget --https-only -qO- "$url" ;;
  esac
}

# ── Detect current shell ───────────────────────────────────────
detect_shell() {
  local shell_name
  shell_name=$(basename "$SHELL")
  echo "$shell_name"
}

# ── Get shell profile path ─────────────────────────────────────
get_shell_profile() {
  local shell="$1"
  case "$shell" in
    zsh)   echo "$HOME/.zshrc" ;;
    bash)  echo "$HOME/.bashrc" ;;
    fish)  echo "$HOME/.config/fish/config.fish" ;;
    ksh)   echo "$HOME/.kshrc" ;;
    *)     echo "$HOME/.profile" ;; # fallback
  esac
}

# ── Check if PATH already contains directory ───────────────────
path_contains() {
  local dir="$1"
  echo "$PATH" | tr ':' '\n' | grep -qx "$dir"
}

# ── Detect AI tools in use ─────────────────────────────────────
detect_tools() {
  local tools=()

  # GitHub Copilot (VS Code / CLI)
  if [ -d ".github" ] || [ -f ".github/copilot-instructions.md" ]; then
    tools+=("copilot")
  fi

  # Cursor
  if [ -d ".cursor" ] || [ -f ".cursorrules" ]; then
    tools+=("cursor")
  fi

  # Claude Code
  if [ -f "CLAUDE.md" ]; then
    tools+=("claude")
  fi

  # Windsurf / Codeium
  if [ -f ".windsurfrules" ]; then
    tools+=("windsurf")
  fi

  # Aider
  if [ -f ".aider.conf.yml" ] || [ -f ".aiderignore" ]; then
    tools+=("aider")
  fi

  # Cline / Roo
  if [ -f ".clinerules" ] || [ -d ".cline" ]; then
    tools+=("cline")
  fi

  # Antigravity
  if [ -f ".antigravity" ] || [ -d ".antigravity" ]; then
    tools+=("antigravity")
  fi

  # If nothing detected, default to all common tools
  if [ ${#tools[@]} -eq 0 ]; then
    tools=("copilot" "cursor" "claude")
  fi

  echo "${tools[@]}"
}

# ── File installation per tool ─────────────────────────────────

install_rules_to() {
  local dest="$1"
  mkdir -p "$(dirname "$dest")"
  if [ -f "$dest" ]; then
    # Append if file exists and doesn't already have intent-first
    if ! grep -q "Intent-First" "$dest" 2>/dev/null; then
      echo "" >> "$dest"
      echo "<!-- intent-first workflow rules -->" >> "$dest"
      download_text "$RAW/rules/RULES.md" >> "$dest"
      info "Appended rules to $dest"
    else
      warn "$dest already contains Intent-First rules (skipped)"
    fi
  else
    download "$RAW/rules/RULES.md" "$dest"
    info "Created $dest"
  fi
}

install_prompts_to() {
  local dest_dir="$1"
  mkdir -p "$dest_dir"
  for prompt in wf-spec.prompt.md wf-plan.prompt.md wf-execution.prompt.md wf-artifacts.prompt.md wf-yolo.prompt.md; do
    download "$RAW/prompts/$prompt" "$dest_dir/$prompt"
  done
  info "Installed 5 prompt files → $dest_dir/"
}

install_copilot() {
  step "Installing for GitHub Copilot (VS Code / CLI)..."
  mkdir -p .github/prompts
  install_rules_to ".github/copilot-instructions.md"
  install_prompts_to ".github/prompts"
}

install_cursor() {
  step "Installing for Cursor..."
  mkdir -p .cursor/prompts
  install_rules_to ".cursor/rules/intent-first.md"
  install_prompts_to ".cursor/prompts"
}

install_claude() {
  step "Installing for Claude Code..."
  install_rules_to "CLAUDE.md"
  mkdir -p .claude/prompts
  install_prompts_to ".claude/prompts"
}

install_windsurf() {
  step "Installing for Windsurf..."
  install_rules_to ".windsurfrules"
  mkdir -p .windsurf/prompts
  install_prompts_to ".windsurf/prompts"
}

install_aider() {
  step "Installing for Aider..."
  install_rules_to ".aider.rules.md"
}

install_cline() {
  step "Installing for Cline / Roo..."
  install_rules_to ".clinerules"
}

install_antigravity() {
  step "Installing for Antigravity..."
  install_rules_to ".antigravity/rules/intent-first.md"
  mkdir -p .antigravity/prompts
  install_prompts_to ".antigravity/prompts"
}

# ── Install templates ──────────────────────────────────────────
install_templates() {
  local dest=".intent-first/templates"
  mkdir -p "$dest"
  for tmpl in s1_intent.md s2_spec.md s3_plan.md s4_execution.md s5_artifacts.md; do
    download "$RAW/templates/$tmpl" "$dest/$tmpl"
  done
  info "Installed 5 templates → $dest/"
}

# ── Install CLI (global) ──────────────────────────────────────
install_cli() {
  local global_dir="$HOME/.intent_first/bin"
  local dest="$global_dir/intent-first"
  local shell_name profile_path export_line
  
  mkdir -p "$global_dir"
  download "$RAW/cli/intent-first" "$dest"
  chmod +x "$dest"
  info "Installed CLI → $dest"
  echo ""

  shell_name=$(detect_shell)
  profile_path=$(get_shell_profile "$shell_name")
  export_line="export PATH=\"\$HOME/.intent_first/bin:\$PATH\""
  
  echo "  ${BOLD}Add to PATH:${RESET}"
  echo "    ${GREEN}${profile_path}${RESET}"
  echo ""
  echo "  ${CYAN}Copy & paste:${RESET}"
  echo "    echo '$export_line' >> $profile_path"
  echo "    source $profile_path"
  echo ""
  echo "  ${BOLD}Quick start:${RESET}"
  echo "    intent-first new"
}

# ── Ensure .gitignore covers workflow data ─────────────────────
install_gitignore() {
  local gitignore=".gitignore"
  local marker=".intent-first/"

  if [ -f "$gitignore" ]; then
    if ! grep -qF "$marker" "$gitignore" 2>/dev/null; then
      echo "" >> "$gitignore"
      echo "# Intent-First workflow (ephemeral)" >> "$gitignore"
      echo ".intent-first/" >> "$gitignore"
      echo "workflow/" >> "$gitignore"
      info "Appended .intent-first/ and workflow/ to .gitignore"
    else
      info ".gitignore already covers .intent-first/ (skipped)"
    fi
  else
    cat > "$gitignore" <<'GITIGNORE'
# Intent-First workflow (ephemeral)
.intent-first/
workflow/
GITIGNORE
    info "Created .gitignore with .intent-first/ and workflow/"
  fi
}

# ── Main ───────────────────────────────────────────────────────

header "🎯 Intent-First Workflow Installer"
echo "   https://github.com/$REPO"
echo ""

OS=$(detect_os)
DOWNLOADER=$(detect_downloader)

if [ -z "$DOWNLOADER" ]; then
  echo "Error: curl or wget required. Install one and retry."
  exit 1
fi

info "Detected OS: $OS"
info "Using: $DOWNLOADER"

# Detect tools
TOOLS=($(detect_tools))
info "Detected tools: ${TOOLS[*]}"

header "📄 Installing templates..."
install_templates

header "📐 Installing rules & prompts..."
for tool in "${TOOLS[@]}"; do
  case "$tool" in
    copilot)     install_copilot ;;
    cursor)      install_cursor ;;
    claude)      install_claude ;;
    windsurf)    install_windsurf ;;
    aider)       install_aider ;;
    cline)       install_cline ;;
    antigravity) install_antigravity ;;
  esac
done

header "⚡ Installing CLI..."
install_cli

header "📝 Configuring .gitignore..."
install_gitignore

header "✅ Intent-First installed!"
echo ""
echo "  Get started:"
echo "    1. Run:  intent-first new"
echo "    2. Edit: workflow/1/s1_intent.md"
echo "    3. Ask your AI agent: /wf-spec 1"
echo ""
echo "  Workflow data is ephemeral and gitignored."
echo "  Docs: https://github.com/$REPO"
