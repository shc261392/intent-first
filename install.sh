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
INTENT_FIRST_HOME="${INTENT_FIRST_HOME:-$HOME/.intent-first}"

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
    curl) curl -fsSL --proto '=https' "$url" -o "$dest" || return 1 ;;
    wget) wget --https-only -qO "$dest" "$url" || return 1 ;;
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

# ── Ask user which tool they use (interactive fallback) ───────────
ask_tool_interactive() {
  echo ""
  echo "  No AI tool configuration detected."
  echo "  Which AI coding tool do you use? (enter number(s), comma-separated)"
  echo ""
  echo "    1) GitHub Copilot (VS Code)"
  echo "    2) Cursor"
  echo "    3) Claude Code"
  echo "    4) Windsurf"
  echo "    5) Aider"
  echo "    6) Cline / Roo"
  echo "    7) None / skip"
  echo ""
  printf "  Choice(s) [1]: "
  local reply
  if [ -t 0 ]; then
    read -r reply
  else
    read -r reply < /dev/tty
  fi
  reply="${reply:-1}"
  local tools=()
  IFS=',' read -ra choices <<< "$reply"
  for c in "${choices[@]}"; do
    c="${c// /}"  # trim spaces
    case "$c" in
      1) tools+=("copilot") ;;
      2) tools+=("cursor") ;;
      3) tools+=("claude") ;;
      4) tools+=("windsurf") ;;
      5) tools+=("aider") ;;
      6) tools+=("cline") ;;
      7) ;; # skip
      *) warn "Unknown choice: $c (skipped)" ;;
    esac
  done
  echo "${tools[@]}"
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

  # Return empty if nothing detected — caller will ask interactively
  # (Do not silently install files for tools the user doesn't use)

  echo "${tools[@]}"
}

# ── File installation per tool ─────────────────────────────────

install_rules_to() {
  local dest="$1"
  local one_liner="For the Intent-First Agentic Workflow, see \`.intent-first/rules.md\`."
  mkdir -p "$(dirname "$dest")"
  if [ -f "$dest" ]; then
    if ! grep -qi "intent-first" "$dest" 2>/dev/null; then
      printf '\n%s\n' "$one_liner" >> "$dest"
      info "Added Intent-First reference → $dest"
    else
      warn "$dest already references Intent-First (skipped)"
    fi
  else
    printf '%s\n' "$one_liner" > "$dest"
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

install_agents_to() {
  local dest_dir="$1"
  mkdir -p "$dest_dir"
  for agent in wf-auditor.agents.md; do
    download "$RAW/agents/$agent" "$dest_dir/$agent"
  done
  info "Installed 1 agent file → $dest_dir/"
}

install_copilot() {
  step "Installing for GitHub Copilot (VS Code / CLI)..."
  mkdir -p .github/prompts .github/agents
  install_rules_to ".github/copilot-instructions.md"
  install_prompts_to ".github/prompts"
  install_agents_to ".github/agents"
}

install_cursor() {
  step "Installing for Cursor..."
  mkdir -p .cursor/prompts .cursor/agents
  install_rules_to ".cursor/rules/intent-first.md"
  install_prompts_to ".cursor/prompts"
  install_agents_to ".cursor/agents"
}

install_claude() {
  step "Installing for Claude Code..."
  install_rules_to "CLAUDE.md"
  mkdir -p .claude/prompts .claude/agents
  install_prompts_to ".claude/prompts"
  install_agents_to ".claude/agents"
}

install_windsurf() {
  step "Installing for Windsurf..."
  install_rules_to ".windsurfrules"
  mkdir -p .windsurf/prompts .windsurf/agents
  install_prompts_to ".windsurf/prompts"
  install_agents_to ".windsurf/agents"
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
  mkdir -p .antigravity/prompts .antigravity/agents
  install_prompts_to ".antigravity/prompts"
  install_agents_to ".antigravity/agents"
}

# ── Install global rules ───────────────────────────────────────
install_global_rules() {
  local dest="$INTENT_FIRST_HOME/rules.md"
  mkdir -p "$(dirname "$dest")"
  download "$RAW/rules/RULES.md" "$dest"
  info "Installed rules → $dest"
}

# ── Install templates (global) ─────────────────────────────────
install_templates() {
  local dest="$INTENT_FIRST_HOME/templates"
  if [ -d "$dest" ]; then
    local bk="${dest}.bk"
    [ -d "$bk" ] && rm -rf "$bk"
    cp -r "$dest" "$bk"; info "Backed up templates → $(basename "$bk")"
  fi
  mkdir -p "$dest"
  for tmpl in s1_intent.md s2_spec.md s3_plan.md s4_execution.md s5_artifacts.md status.yml; do
    download "$RAW/templates/$tmpl" "$dest/$tmpl"
  done
  info "Installed 6 templates → $dest/"
}

# ── Install CLI (global) ──────────────────────────────────────
install_cli() {
  local global_dir="$INTENT_FIRST_HOME/bin"
  local dest="$global_dir/intent-first"
  local shell_name profile_path export_line

  if ! command -v python3 &>/dev/null; then
    echo "Error: python3 is required but not found."
    echo "  Install Python 3.8+ and re-run this installer."
    exit 1
  fi

  mkdir -p "$global_dir"

  # Always download and install the CLI
  step "Downloading intent-first CLI..."
  if download "$RAW/cli/intent-first" "$dest"; then
    chmod +x "$dest"
    info "Installed CLI → $dest"
  else
    echo "❌ Failed to download intent-first CLI"
    echo "   Check your internet connection and try again."
    exit 1
  fi
  echo ""

  shell_name=$(detect_shell)
  profile_path=$(get_shell_profile "$shell_name")
  export_line="export PATH=\"\$HOME/.intent-first/bin:\$PATH\""

  if path_contains "$global_dir"; then
    info "$global_dir already in PATH"
    return
  fi

  # Check if profile already has the line (covers already-set-but-not-active sessions)
  if [ -f "$profile_path" ] && grep -qF '.intent-first/bin' "$profile_path" 2>/dev/null; then
    warn "PATH entry already in $profile_path — open a new terminal or run: source $profile_path"
    return
  fi

  echo ""
  echo "  ${BOLD}Add $global_dir to PATH?${RESET}"
  echo "  This appends one line to: ${GREEN}${profile_path}${RESET}"
  echo ""
  printf "  Append to %s? [Y/n] " "$profile_path"

  # Read from /dev/tty so it works even when script is piped through curl | bash
  if [ -t 0 ]; then
    read -r reply
  else
    read -r reply < /dev/tty
  fi

  case "${reply:-Y}" in
    [Yy]|"")
      printf '\n# Intent-First CLI\n%s\n' "$export_line" >> "$profile_path"
      info "Appended PATH entry → $profile_path"
      echo "  Run: ${CYAN}source $profile_path${RESET}"
      ;;
    *)
      warn "Skipped. Add manually:"
      echo "    echo '$export_line' >> $profile_path"
      ;;
  esac
}

# ── Main ───────────────────────────────────────────────────────

header "🎯 Intent-First Workflow Installer"
echo "   https://github.com/$REPO"
echo "   Primary support: VSCode GitHub Copilot extension & Copilot CLI"
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
if [ ${#TOOLS[@]} -gt 0 ]; then
  info "Detected tools: ${TOOLS[*]}"
else
  TOOLS=($(ask_tool_interactive))
  [ ${#TOOLS[@]} -gt 0 ] && info "Installing for tools: ${TOOLS[*]}"
fi

header "⚡ Installing CLI..."
install_cli

header "📦 Installing global templates & rules..."
install_templates
install_global_rules

header "📐 Adding tool references..."
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

header "✅ Intent-First installed!"
echo ""
echo "  Next: initialize each project that will use Intent-First:"
echo ""
echo "    cd your-project"
echo "    intent-first init"
echo ""
echo "  This copies rules.md into the project and adds the workflow folder to .gitignore."
echo ""
echo "  Then start a workflow:"
echo "    1. Run:  intent-first new"
echo "    2. Edit: .intent-first/workflows/1/s1_intent.md"
echo "    3. Ask your AI agent: /wf-spec 1"
echo ""
echo "  Docs: https://github.com/$REPO"
