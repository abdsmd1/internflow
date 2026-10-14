"""Modèle d'embeddings local, exécuté sur CPU avec ONNX Runtime (FastEmbed).

Pourquoi local plutôt qu'une API : les rapports des stagiaires ne quittent pas
le serveur, il n'y a ni clé ni quota, et un petit modèle répond en quelques
millisecondes sur CPU (contrairement à un LLM de génération).

Le modèle est chargé au premier usage (ou au démarrage, voir `warm_up`) puis
gardé en mémoire. Dans l'image Docker, il est téléchargé au build et lu hors
ligne (`HF_HUB_OFFLINE=1`).
"""

from __future__ import annotations

import threading
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Any

import structlog

from internflow_api.domain.ports.search import EmbeddingUnavailableError, Vector

if TYPE_CHECKING:
    from fastembed import TextEmbedding

logger = structlog.get_logger(__name__)

DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class FastEmbedEmbedder:
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        *,
        dimension: int,
        cache_dir: str | None = None,
    ) -> None:
        self._model_name = model_name
        self._dimension = dimension
        self._cache_dir = cache_dir
        self._model: TextEmbedding | None = None
        self._lock = threading.Lock()

    @property
    def model_name(self) -> str:
        return self._model_name

    def _load(self) -> TextEmbedding:
        with self._lock:  # un seul chargement, même si plusieurs requêtes arrivent
            if self._model is None:
                try:
                    from fastembed import TextEmbedding  # noqa: PLC0415 (dépendance optionnelle)

                    self._model = TextEmbedding(self._model_name, cache_dir=self._cache_dir)
                except ImportError as error:
                    raise EmbeddingUnavailableError(
                        "FastEmbed n'est pas installé (extra « search » de internflow-api)."
                    ) from error
                except Exception as error:
                    raise EmbeddingUnavailableError(
                        f"Modèle d'embeddings « {self._model_name} » indisponible : {error}"
                    ) from error
            return self._model

    def _vectors(self, raw: Iterable[Iterable[Any]]) -> list[Vector]:
        vectors = [[float(x) for x in vector] for vector in raw]
        for vector in vectors:
            if len(vector) != self._dimension:
                raise EmbeddingUnavailableError(
                    f"Le modèle produit des vecteurs de taille {len(vector)}, "
                    f"la base attend {self._dimension}."
                )
        return vectors

    def embed_passages(self, texts: Sequence[str]) -> list[Vector]:
        if not texts:
            return []
        model = self._load()
        try:
            return self._vectors(model.passage_embed(list(texts)))
        except EmbeddingUnavailableError:
            raise
        except Exception as error:
            raise EmbeddingUnavailableError(
                f"Calcul des embeddings impossible : {error}"
            ) from error

    def embed_query(self, text: str) -> Vector:
        model = self._load()
        try:
            return self._vectors(model.query_embed(text))[0]
        except EmbeddingUnavailableError:
            raise
        except Exception as error:
            raise EmbeddingUnavailableError(
                f"Calcul des embeddings impossible : {error}"
            ) from error

    def warm_up(self) -> None:
        """Charge le modèle en arrière-plan pour que la première recherche soit rapide."""
        try:
            self.embed_query("initialisation")
        except EmbeddingUnavailableError as error:
            logger.warning("embedding_warmup_failed", model=self._model_name, detail=str(error))
        else:
            logger.info("embedding_model_ready", model=self._model_name)
