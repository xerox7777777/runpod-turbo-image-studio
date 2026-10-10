#!/usr/bin/env bash
set -euo pipefail
/start.sh &
mkdir -p /workspace/outputs /workspace/comfyui-user/default/workflows /workspace/inputs
cp -n /app/workflows/*.json /workspace/comfyui-user/default/workflows/
case "${UI_MODE:-comfyui}" in
  comfyui)
    if [[ -n "${UI_USERNAME:-}" || -n "${UI_PASSWORD:-}" ]]; then
      echo "UI_USERNAME/PASSWORD only protect Gradio. ComfyUI requires SSH tunneling; see README." >&2
      exit 1
    fi
    exec python -u /opt/ComfyUI/main.py --listen "${COMFY_LISTEN:-0.0.0.0}" --port 8188 --user-directory /workspace/comfyui-user --input-directory /workspace/inputs --output-directory /workspace/outputs --disable-auto-launch
    ;;
  gradio) exec python -u /app/app.py ;;
  *) echo "UI_MODE must be comfyui or gradio" >&2; exit 1 ;;
esac
