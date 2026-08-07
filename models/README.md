# Models

Download files for `intfloat/multilingual-e5-small` int8 ONNX.

The model is **not bundled with the repo** (removed from git LFS to avoid public bandwidth limits). Download once; the files go in `models/` (repo clone) or `~/.local/share/scholar-paper-cli/models/` (runtime lookup).

## Required files

- `model_quantized.onnx` (~118MB) — from [HuggingFace](https://huggingface.co/intfloat/multilingual-e5-small/tree/main/onnx)
- `tokenizer.json` (~5MB) — from same repo, root

## How to download

```bash
# Requires huggingface-hub CLI: uvx huggingface-cli login
uvx huggingface-cli download intfloat/multilingual-e5-small \
  onnx/model_quantized.onnx \
  --local-dir models/ \
  --local-dir-use-symlinks False
mv models/onnx/model_quantized.onnx models/
rmdir models/onnx

uvx huggingface-cli download intfloat/multilingual-e5-small tokenizer.json \
  --local-dir models/onnx \
  --local-dir-use-symlinks False
mv models/onnx/tokenizer.json models/
rmdir models/onnx
```

Or manually: download from the HF page, place in `models/`.
