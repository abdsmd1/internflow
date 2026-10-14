"""Port du modèle d'embeddings (texte → vecteur).

Le domaine ignore quel modèle est utilisé : l'adaptateur de production fait
tourner un modèle local (ONNX, sur CPU), les tests un faux déterministe.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

Vector = list[float]


class EmbeddingUnavailableError(Exception):
    """Le modèle d'embeddings ne peut pas être chargé ou n'a pas répondu."""


class TextEmbedder(Protocol):
    @property
    def model_name(self) -> str: ...

    def embed_passages(self, texts: Sequence[str]) -> list[Vector]:
        """Vecteurs des textes à indexer, dans le même ordre.

        Lève `EmbeddingUnavailableError` si le modèle n'est pas disponible.
        """
        ...

    def embed_query(self, text: str) -> Vector:
        """Vecteur d'une question de recherche."""
        ...
