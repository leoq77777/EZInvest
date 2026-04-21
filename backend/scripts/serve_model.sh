#!/usr/bin/env bash
#
# Start a local LLM server with the fine-tuned model.
# Supports three backends: vLLM (recommended), llama.cpp, or Ollama.
#
# Usage:
#   ./scripts/serve_model.sh vllm   [model_path]
#   ./scripts/serve_model.sh llamacpp [gguf_path]
#   ./scripts/serve_model.sh ollama  [model_name]
#
# The server exposes an OpenAI-compatible API at http://localhost:8000/v1
# which the EZInvest backend connects to via LLM_BASE_URL.

set -euo pipefail

BACKEND="${1:-vllm}"
MODEL="${2:-models/finetuned/qwen2.5-7b-qlora}"
PORT=8000

case "$BACKEND" in

  # ─────────────────────────────────────────────
  # Option 1: vLLM (recommended for GPU servers)
  # pip install vllm
  # ─────────────────────────────────────────────
  vllm)
    echo "Starting vLLM server..."
    echo "  Model:  $MODEL"
    echo "  Port:   $PORT"
    echo "  URL:    http://localhost:$PORT/v1"
    echo ""
    python -m vllm.entrypoints.openai.api_server \
      --model "$MODEL" \
      --port "$PORT" \
      --max-model-len 4096 \
      --dtype auto \
      --quantization awq \
      --gpu-memory-utilization 0.90 \
      --trust-remote-code
    ;;

  # ─────────────────────────────────────────────
  # Option 2: llama.cpp (CPU or low-VRAM GPU)
  # pip install llama-cpp-python[server]
  # ─────────────────────────────────────────────
  llamacpp)
    echo "Starting llama.cpp server..."
    echo "  Model:  $MODEL"
    echo "  Port:   $PORT"
    echo ""
    python -m llama_cpp.server \
      --model "$MODEL" \
      --host 0.0.0.0 \
      --port "$PORT" \
      --n_ctx 4096 \
      --n_gpu_layers -1 \
      --chat_format chatml
    ;;

  # ─────────────────────────────────────────────
  # Option 3: Ollama (easiest setup)
  # Install from https://ollama.ai
  # ─────────────────────────────────────────────
  ollama)
    MODEL_NAME="${MODEL:-qwen2.5:7b}"
    echo "Starting Ollama with model: $MODEL_NAME"
    echo "  Ollama API: http://localhost:11434"
    echo ""
    echo "Note: Set these in .env:"
    echo "  LLM_BASE_URL=http://localhost:11434/v1"
    echo "  LLM_MODEL_PATH=$MODEL_NAME"
    echo ""
    ollama pull "$MODEL_NAME"
    ollama serve &
    sleep 2
    echo "Ollama ready. Run 'ollama run $MODEL_NAME' to test interactively."
    wait
    ;;

  *)
    echo "Unknown backend: $BACKEND"
    echo "Usage: $0 {vllm|llamacpp|ollama} [model_path]"
    exit 1
    ;;
esac
