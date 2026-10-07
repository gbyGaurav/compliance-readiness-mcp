"""
Local embedding generator using TF-IDF sublinear n-gram vectorization with L2 normalization.
Provides deterministic, zero-cost, fully offline local vector representations.
"""

from typing import List
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


class LocalEmbeddingEngine:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            sublinear_tf=True,
            stop_words="english",
            norm="l2",
        )
        self._is_fitted = False

    def fit_and_embed(self, documents: List[str]) -> np.ndarray:
        if not documents:
            return np.empty((0, 0))
        sparse_mat = self.vectorizer.fit_transform(documents)
        self._is_fitted = True
        return sparse_mat.toarray()

    def embed_queries(self, queries: List[str]) -> np.ndarray:
        if not self._is_fitted:
            raise RuntimeError("Embedding engine must be fitted on corpus before embedding queries.")
        sparse_mat = self.vectorizer.transform(queries)
        return sparse_mat.toarray()

    def embed_query(self, query: str) -> np.ndarray:
        return self.embed_queries([query])[0]
