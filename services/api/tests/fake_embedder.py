"""Faux modèle d'embeddings, déterministe et sans téléchargement.

Chaque mot (en minuscules, sans accents) est haché vers une dimension du
vecteur : deux textes qui partagent des mots ont des vecteurs proches. C'est
une recherche par mots-clés, pas par le sens, mais elle suffit pour vérifier
toute la chaîne (découpage, stockage, droits, tri) sans le vrai modèle.
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections.abc import Sequence

from internflow_api.domain.ports.search import EmbeddingUnavailableError, Vector
from internflow_api.infrastructure.persistence.orm import EMBEDDING_DIMENSION

_WORD = re.compile(r"[a-z0-9]{3,}")  # les mots de moins de 3 lettres sont ignorés


def _words(text: str) -> list[str]:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return _WORD.findall(ascii_text.lower())


class KeywordEmbedder:
    model_name = "test/keyword-hashing"

    def __init__(self, *, available: bool = True) -> None:
        self.available = available
        self.calls = 0

    def _embed(self, text: str) -> Vector:
        if not self.available:
            raise EmbeddingUnavailableError("modèle de test hors service")
        self.calls += 1
        vector = [0.0] * EMBEDDING_DIMENSION
        for word in _words(text):
            digest = hashlib.blake2b(word.encode(), digest_size=8).digest()
            vector[int.from_bytes(digest, "big") % EMBEDDING_DIMENSION] += 1.0
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        return [x / norm for x in vector]

    def embed_passages(self, texts: Sequence[str]) -> list[Vector]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> Vector:
        return self._embed(text)
