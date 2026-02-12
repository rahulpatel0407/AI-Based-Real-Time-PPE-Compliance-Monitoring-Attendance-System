#!/bin/bash
set -e

MODEL_DIR="YOLO-Weights"
MODEL_FILE="$MODEL_DIR/ppe.pt"
MODEL_URL="https://example.com/path/to/ppe.pt"

mkdir -p "$MODEL_DIR"

echo "Downloading model from $MODEL_URL"

if command -v curl >/dev/null 2>&1; then
  curl -L "$MODEL_URL" -o "$MODEL_FILE"
elif command -v wget >/dev/null 2>&1; then
  wget -O "$MODEL_FILE" "$MODEL_URL"
else
  echo "Error: curl or wget is required to download models."
  exit 1
fi

echo "Model saved to $MODEL_FILE"
