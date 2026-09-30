"""Local text embeddings with intfloat/multilingual-e5-base (768 numbers per text).

An embedding is a list of numbers representing a passage's meaning: passages with similar
meaning get similar numbers even when they share no words ("melting" vs "ablation").
The e5 model requires the prefixes "query: " and "passage: ".
"""
from functools import lru_cache

from app.core.config import get_settings


@lru_cache
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(get_settings().embedding_model, device="cpu")


def embed_passages(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    vectors = _model().encode(
        [f"passage: {t}" for t in texts], batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False
    )
    return [v.tolist() for v in vectors]


def embed_query(text: str) -> list[float]:
    return _model().encode(f"query: {text}", normalize_embeddings=True).tolist()
