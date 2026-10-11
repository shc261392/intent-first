#!/bin/sh
# Install the intent-first CLI: one Python zipapp from a GitHub release, verified against SHA256SUMS.
#
#   curl -fsSL https://raw.githubusercontent.com/shc261392/intent-first/main/install.sh | sh
#
# Environment:
#   INTENT_FIRST_VERSION  release tag to install, e.g. v3.0.0 (default: latest release)
#   INTENT_FIRST_BIN      install directory (default: ~/.local/bin)
#
# This only installs the CLI. Run `intent-first init` inside a project to set it up there.
set -eu

REPO="shc261392/intent-first"
VERSION="${INTENT_FIRST_VERSION:-latest}"
BIN_DIR="${INTENT_FIRST_BIN:-$HOME/.local/bin}"

fail() { printf 'intent-first install: %s\n' "$1" >&2; exit 1; }

PYTHON=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 &&
     "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
    PYTHON="$candidate"
    break
  fi
done
[ -n "$PYTHON" ] || fail "Python 3.9+ is required (python3 not found or too old)"

if [ "$VERSION" = "latest" ]; then
  BASE="https://github.com/$REPO/releases/latest/download"
else
  BASE="https://github.com/$REPO/releases/download/$VERSION"
fi

fetch() {
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --proto '=https' --tlsv1.2 "$1" -o "$2"
  elif command -v wget >/dev/null 2>&1; then
    wget -q --https-only "$1" -O "$2"
  else
    fail "curl or wget is required"
  fi
}

sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | cut -d' ' -f1
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | cut -d' ' -f1
  else
    "$PYTHON" -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$1"
  fi
}

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT INT TERM

fetch "$BASE/intent-first.pyz" "$TMP/intent-first.pyz" || fail "download failed: $BASE/intent-first.pyz"
fetch "$BASE/SHA256SUMS" "$TMP/SHA256SUMS" || fail "download failed: $BASE/SHA256SUMS"

expected=$(awk '$2 == "intent-first.pyz" { print $1 }' "$TMP/SHA256SUMS")
actual=$(sha256 "$TMP/intent-first.pyz")
[ -n "$expected" ] || fail "intent-first.pyz is not listed in SHA256SUMS"
[ "$expected" = "$actual" ] || fail "checksum mismatch (expected $expected, got $actual)"

mkdir -p "$BIN_DIR"
cp "$TMP/intent-first.pyz" "$BIN_DIR/intent-first"
chmod 755 "$BIN_DIR/intent-first"

printf 'Installed %s\n' "$("$PYTHON" "$BIN_DIR/intent-first" --version) → $BIN_DIR/intent-first"
# shellcheck disable=SC2016  # the literal $PATH in the hint is intended
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) printf 'Add %s to your PATH, e.g.: export PATH="%s:$PATH"\n' "$BIN_DIR" "$BIN_DIR" ;;
esac
# shellcheck disable=SC2016  # literal backticks are intended
printf 'Next: cd into a project and run `intent-first init`.\n'
