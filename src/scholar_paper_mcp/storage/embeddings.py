"""ONNX mE5-small embedder + sqlite-vec KNN search."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from scholar_paper_mcp.config import get_settings
from scholar_paper_mcp.exceptions import EmbeddingInferenceError, EmbeddingModelNotFoundError


class Embedder:
    """mE5-small int8 ONNX embedder. Multilingual, 384-dim, mean-pooled, L2-normalized."""

    def __init__(self, model_path: Path, tokenizer_path: Path) -> None:
        if not model_path.exists():
            raise EmbeddingModelNotFoundError(f"model not found: {model_path}")
        if not tokenizer_path.exists():
            raise EmbeddingModelNotFoundError(f"tokenizer not found: {tokenizer_path}")
        try:
            self.session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        except Exception as e:
            raise EmbeddingModelNotFoundError(f"failed to load model: {model_path}") from e
        self.tokenizer = Tokenizer.from_file(str(tokenizer_path))
        self.dim = 384

    def encode(self, texts: list[str], mode: Literal["query", "passage"]) -> list[list[float]]:
        """Encode texts to 384-dim embeddings. Prepends 'query: ' or 'passage: ' prefix."""
        if not texts:
            return []
        prefix = "query: " if mode == "query" else "passage: "
        prefixed = [prefix + t for t in texts]
        try:
            encodings = self.tokenizer.encode_batch(prefixed)
            max_len = max(len(e.ids) for e in encodings)
            ids = np.zeros((len(encodings), max_len), dtype=np.int64)
            mask = np.zeros((len(encodings), max_len), dtype=np.int64)
            token_type = np.zeros((len(encodings), max_len), dtype=np.int64)
            for i, e in enumerate(encodings):
                ids[i, : len(e.ids)] = e.ids
                mask[i, : len(e.ids)] = e.attention_mask
                if e.type_ids:
                    token_type[i, : len(e.type_ids)] = e.type_ids
            outputs = self.session.run(None, {
                "input_ids": ids,
                "attention_mask": mask,
                "token_type_ids": token_type,
            })
            last_hidden = outputs[0]
            mask_f = mask[:, :, None].astype(np.float32)
            summed = np.sum(last_hidden * mask_f, axis=1)
            counts = mask_f.sum(axis=1).clip(min=1.0)
            pooled = summed / counts
            norms = np.linalg.norm(pooled, axis=1, keepdims=True).clip(min=1e-12)
            normalized = pooled / norms
            return normalized.astype(np.float32).tolist()
        except Exception as e:
            raise EmbeddingInferenceError(f"encoding failed: {e}") from e


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    """Load and cache the embedder from SPM_EMBEDDING_MODEL path."""
    models_dir = Path(get_settings().cache_path).parent / "models"
    return Embedder(models_dir / "model_quantized.onnx", models_dir / "tokenizer.json")


def upsert_embedding(conn, paper_id: str, embedding: list[float]) -> None:
    """Store or replace embedding in embeddings_vec virtual table."""
    if len(embedding) != 384:
        raise EmbeddingInferenceError(f"expected 384-dim embedding, got {len(embedding)}")
    arr = np.array(embedding, dtype=np.float32).tobytes()
    conn.execute("DELETE FROM embeddings_vec WHERE paper_id = ?", (paper_id,))
    conn.execute(
        "INSERT INTO embeddings_vec (paper_id, embedding) VALUES (?, ?)",
        (paper_id, arr),
    )
    conn.commit()


def knn_search(conn, query_embedding: list[float], k: int = 10) -> list[tuple[str, float]]:
    """KNN search over embeddings_vec. Returns list of (paper_id, distance)."""
    if len(query_embedding) != 384:
        raise EmbeddingInferenceError(f"expected 384-dim query, got {len(query_embedding)}")
    arr = np.array(query_embedding, dtype=np.float32)
    rows = conn.execute(
        "SELECT paper_id, distance FROM embeddings_vec WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
        (arr.tobytes(), k),
    ).fetchall()
    return [(r["paper_id"], float(r["distance"])) for r in rows]
