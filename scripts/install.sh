#!/usr/bin/env bash
# install.sh — install the space-ocr skill into Claude Code or Cursor.
#
# Usage:
#   bash install.sh                # interactive, asks which target
#   bash install.sh claude         # install for Claude Code only
#   bash install.sh cursor         # install for Cursor only
#   bash install.sh both           # install for both
#
# Curl-piped usage:
#   curl -fsSL <raw-url>/scripts/install.sh | bash -s -- cursor

set -euo pipefail

REPO="oisidonut/claude-space-ocr-skill"
TARBALL="https://github.com/${REPO}/archive/refs/heads/main.tar.gz"

target="${1:-}"

if [[ -z "$target" ]]; then
    echo "Install space-ocr skill — pick a target:"
    echo "  1) Claude Code  (~/.claude/skills/)"
    echo "  2) Cursor       (~/.cursor/skills/)"
    echo "  3) Both"
    read -rp "Choice [1/2/3]: " choice
    case "$choice" in
        1) target="claude" ;;
        2) target="cursor" ;;
        3) target="both" ;;
        *) echo "Cancelled." >&2; exit 1 ;;
    esac
fi

case "$target" in
    claude|cursor|both) ;;
    *) echo "Unknown target: $target (expected claude|cursor|both)" >&2; exit 2 ;;
esac

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

echo "Downloading skill from ${REPO}..."
curl -fsSL "$TARBALL" | tar -xz -C "$tmp_dir"
src_skill="$(find "$tmp_dir" -maxdepth 2 -type d -name 'space-ocr' -path '*/skills/*' | head -n1)"

if [[ -z "$src_skill" || ! -d "$src_skill" ]]; then
    echo "Could not locate skills/space-ocr in the downloaded archive." >&2
    exit 3
fi

install_to() {
    local dest_root="$1"
    local label="$2"
    local dest="${dest_root}/space-ocr"
    mkdir -p "$dest_root"
    if [[ -e "$dest" ]]; then
        local backup="${dest}.bak.$(date +%s)"
        echo "Existing install found — backing up to: $backup"
        mv "$dest" "$backup"
    fi
    cp -r "$src_skill" "$dest"
    echo "Installed for $label: $dest"
}

[[ "$target" == "claude" || "$target" == "both" ]] && install_to "$HOME/.claude/skills" "Claude Code"
[[ "$target" == "cursor" || "$target" == "both" ]] && install_to "$HOME/.cursor/skills" "Cursor"

echo
echo "Done. Set your API key next:"
echo "  export SPACE_OCR_API_KEY=spocr_..."
echo "Get one at https://space-ocr.com (100 free scans, no card)."
