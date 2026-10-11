#!/usr/bin/env bash
# 等待 Antigravity 启动后自动注入汉化
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

find_port_file() {
  for pf in "$HOME/Library/Application Support/Antigravity/DevToolsActivePort" "$HOME/.config/Antigravity/DevToolsActivePort"; do
    if [ -s "$pf" ] && [ -n "$(head -1 "$pf" 2>/dev/null)" ]; then
      return 0
    fi
  done
  return 1
}

for i in $(seq 1 60); do
  if find_port_file; then
    sleep 3
    python3 "$DIR/antigravity_zh.py" && exit 0
    sleep 2
  fi
  sleep 2
done
echo "未能连接到 Antigravity 调试端口" >&2
exit 1
