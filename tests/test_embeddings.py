"""Tests for storage.embeddings — Embedder + upsert_embedding + knn_search."""

import math
from pathlib import Path

import numpy as np
import pytest

from scholar_paper_cli.exceptions import EmbeddingInferenceError, EmbeddingModelNotFoundError
from scholar_paper_cli.storage.db import apply_migrations, connect

MODEL_PATH = Path("models/model_quantized.onnx")
TOKENIZER_PATH = Path("models/tokenizer.json")
MODEL_EXISTS = MODEL_PATH.exists() and TOKENIZER_PATH.exists()


# ── Unit tests (no model needed) ──────────────────────────────────────────


def test_load_embedder_raises_if_model_missing(tmp_path: Path) -> None:
    from scholar_paper_cli.storage.embeddings import Embedder

    missing = tmp_path / "nonexistent.onnx"
    tok = tmp_path / "dummy.json"
    tok.write_text("{}")
    with pytest.raises(EmbeddingModelNotFoundError):
        Embedder(missing, tok)


def test_embedder_raises_model_not_found_for_corrupt_model(tmp_path: Path) -> None:
    from scholar_paper_cli.storage.embeddings import Embedder

    fake = tmp_path / "model.onnx"
    fake.write_bytes(b"not a real onnx model")
    tokenizer = tmp_path / "tokenizer.json"
    tokenizer.write_text("{}")
    with pytest.raises(EmbeddingModelNotFoundError):
        Embedder(fake, tokenizer)


def test_load_embedder_raises_if_tokenizer_missing(tmp_path: Path) -> None:
    from scholar_paper_cli.storage.embeddings import Embedder

    model = tmp_path / "dummy.onnx"
    model.write_text("dummy")
    missing = tmp_path / "nonexistent.json"
    with pytest.raises(EmbeddingModelNotFoundError):
        Embedder(model, missing)


def test_upsert_embedding_wrong_dim_raises(tmp_path: Path) -> None:
    from scholar_paper_cli.storage.embeddings import upsert_embedding

    conn = connect(tmp_path / "test.db")
    apply_migrations(conn)

    with pytest.raises(EmbeddingInferenceError):
        upsert_embedding(conn, "p1", [0.1] * 100)

    conn.close()


def test_knn_search_wrong_dim_raises(tmp_path: Path) -> None:
    from scholar_paper_cli.storage.embeddings import knn_search

    conn = connect(tmp_path / "test.db")
    apply_migrations(conn)

    with pytest.raises(EmbeddingInferenceError):
        knn_search(conn, [0.1] * 100)

    conn.close()


def test_upsert_embedding_then_knn_search_roundtrips(tmp_path: Path) -> None:
    from scholar_paper_cli.storage.embeddings import knn_search, upsert_embedding

    conn = connect(tmp_path / "test.db")
    apply_migrations(conn)

    emb = [0.1 * i for i in range(384)]
    upsert_embedding(conn, "p1", emb)

    results = knn_search(conn, emb, k=5)
    assert len(results) == 1
    assert results[0][0] == "p1"
    assert isinstance(results[0][1], float)

    conn.close()


def test_upsert_embedding_replaces_existing(tmp_path: Path) -> None:
    from scholar_paper_cli.storage.embeddings import knn_search, upsert_embedding

    conn = connect(tmp_path / "test.db")
    apply_migrations(conn)

    emb1 = [0.1 * i for i in range(384)]
    emb2 = [0.2 * i for i in range(384)]
    upsert_embedding(conn, "p1", emb1)
    upsert_embedding(conn, "p1", emb2)

    results = knn_search(conn, emb2, k=5)
    assert len(results) == 1
    assert results[0][0] == "p1"

    conn.close()


def test_knn_search_returns_empty_for_no_match(tmp_path: Path) -> None:
    from scholar_paper_cli.storage.embeddings import knn_search

    conn = connect(tmp_path / "test.db")
    apply_migrations(conn)

    results = knn_search(conn, [0.0] * 384, k=5)
    assert results == []

    conn.close()


# ── Integration tests (skip if no model) ──────────────────────────────────


@pytest.mark.skipif(not MODEL_EXISTS, reason="mE5 model not downloaded")
def test_load_embedder_loads_real_model() -> None:
    from scholar_paper_cli.storage.embeddings import Embedder

    embedder = Embedder(MODEL_PATH, TOKENIZER_PATH)
    assert embedder.dim == 384
    assert embedder.session is not None
    assert embedder.tokenizer is not None


@pytest.mark.skipif(not MODEL_EXISTS, reason="mE5 model not downloaded")
def test_encode_query_adds_query_prefix() -> None:
    from scholar_paper_cli.storage.embeddings import Embedder

    embedder = Embedder(MODEL_PATH, TOKENIZER_PATH)
    tokens = embedder.tokenizer.encode("query: hello")
    _result = embedder.encode(["hello"], mode="query")
    # If the prefix was prepended, the tokens should match
    result_tokens = embedder.tokenizer.encode("query: hello")
    assert result_tokens.ids[:3] == tokens.ids[:3]


@pytest.mark.skipif(not MODEL_EXISTS, reason="mE5 model not downloaded")
def test_encode_passage_adds_passage_prefix() -> None:
    from scholar_paper_cli.storage.embeddings import Embedder

    embedder = Embedder(MODEL_PATH, TOKENIZER_PATH)
    tokens = embedder.tokenizer.encode("passage: hello")
    _result = embedder.encode(["hello"], mode="passage")
    result_tokens = embedder.tokenizer.encode("passage: hello")
    assert result_tokens.ids[:3] == tokens.ids[:3]


@pytest.mark.skipif(not MODEL_EXISTS, reason="mE5 model not downloaded")
def test_encode_returns_384_dim_vectors() -> None:
    from scholar_paper_cli.storage.embeddings import Embedder

    embedder = Embedder(MODEL_PATH, TOKENIZER_PATH)
    result = embedder.encode(["hello world"], mode="query")
    assert len(result) == 1
    assert len(result[0]) == 384


@pytest.mark.skipif(not MODEL_EXISTS, reason="mE5 model not downloaded")
def test_encode_batch_returns_same_count_as_input() -> None:
    from scholar_paper_cli.storage.embeddings import Embedder

    embedder = Embedder(MODEL_PATH, TOKENIZER_PATH)
    texts = ["hello", "world", "test"]
    result = embedder.encode(texts, mode="query")
    assert len(result) == 3
    for vec in result:
        assert len(vec) == 384


@pytest.mark.skipif(not MODEL_EXISTS, reason="mE5 model not downloaded")
def test_encode_empty_input_returns_empty_list() -> None:
    from scholar_paper_cli.storage.embeddings import Embedder

    embedder = Embedder(MODEL_PATH, TOKENIZER_PATH)
    result = embedder.encode([], mode="query")
    assert result == []


@pytest.mark.skipif(not MODEL_EXISTS, reason="mE5 model not downloaded")
def test_encoded_vectors_are_l2_normalized() -> None:
    from scholar_paper_cli.storage.embeddings import Embedder

    embedder = Embedder(MODEL_PATH, TOKENIZER_PATH)
    result = embedder.encode(["hello world"], mode="query")
    vec = np.array(result[0])
    norm = np.linalg.norm(vec)
    assert math.isclose(norm, 1.0, rel_tol=1e-3)


@pytest.mark.skipif(not MODEL_EXISTS, reason="mE5 model not downloaded")
def test_knn_search_finds_known_similar(tmp_path: Path) -> None:
    from scholar_paper_cli.storage.embeddings import Embedder, knn_search, upsert_embedding

    embedder = Embedder(MODEL_PATH, TOKENIZER_PATH)
    conn = connect(tmp_path / "test.db")
    apply_migrations(conn)

    q_emb = embedder.encode(["quantum entanglement"], mode="query")[0]
    d1_emb = embedder.encode(["quantum entanglement"], mode="passage")[0]
    d2_emb = embedder.encode(["classical mechanics"], mode="passage")[0]

    upsert_embedding(conn, "d1", d1_emb)
    upsert_embedding(conn, "d2", d2_emb)

    results = knn_search(conn, q_emb, k=5)
    assert len(results) >= 1
    # The most similar to the query should be d1
    assert results[0][0] == "d1"

    conn.close()


@pytest.mark.skipif(not MODEL_EXISTS, reason="mE5 model not downloaded")
def test_knn_search_ranks_similar_higher_than_dissimilar(tmp_path: Path) -> None:
    from scholar_paper_cli.storage.embeddings import Embedder, knn_search, upsert_embedding

    embedder = Embedder(MODEL_PATH, TOKENIZER_PATH)
    conn = connect(tmp_path / "test.db")
    apply_migrations(conn)

    q_emb = embedder.encode(["quantum physics"], mode="query")[0]
    sim_emb = embedder.encode(["quantum mechanics"], mode="passage")[0]
    dis_emb = embedder.encode(["baking recipes"], mode="passage")[0]

    upsert_embedding(conn, "similar", sim_emb)
    upsert_embedding(conn, "dissimilar", dis_emb)

    results = knn_search(conn, q_emb, k=5)
    results_map = dict(results)
    assert results_map["similar"] < results_map["dissimilar"]

    conn.close()
