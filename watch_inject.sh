#!/usr/bin/env bash
# Antigravity 汉化守护进程（持续侦测与保活）
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 -u "$DIR/antigravity_zh.py" --watch
