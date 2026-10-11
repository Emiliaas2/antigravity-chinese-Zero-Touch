#!/usr/bin/env bash
# 一键运行 Antigravity 界面汉化注入
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$DIR/antigravity_zh.py" "$@"
