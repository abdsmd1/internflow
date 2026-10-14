"""Adaptateur FastEmbed, testé avec un faux module (aucun modèle téléchargé)."""

from __future__ import annotations

import sys
import threading
import types
from collections.abc import Iterable, Iterator

import pytest

from internflow_api.domain.ports.search import EmbeddingUnavailableError
from internflow_api.infrastructure.search.fastembed_embedder import (
    DEFAULT_MODEL,
    FastEmbedEmbedder,
)


class FakeTextEmbedding:
    instances = 0
    fail_on_load: Exception | None = None
    fail_on_embed: Exception | None = None
    dimension = 3

    def __init__(self, model_name: str, cache_dir: str | None = None) -> None:
        if FakeTextEmbedding.fail_on_load is not None:
            raise FakeTextEmbedding.fail_on_load
        FakeTextEmbedding.instances += 1
        self.model_name = model_name
        self.cache_dir = cache_dir

    def _vectors(self, texts: Iterable[str]) -> Iterator[list[float]]:
        if FakeTextEmbedding.fail_on_embed is not None:
            raise FakeTextEmbedding.fail_on_embed
        for text in texts:
            yield [float(len(text))] * FakeTextEmbedding.dimension

    def passage_embed(self, texts: list[str]) -> Iterator[list[float]]:
        return self._vectors(texts)

    def query_embed(self, text: str) -> Iterator[list[float]]:
        return self._vectors([text])


@pytest.fixture(autouse=True)
def fake_fastembed(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.ModuleType("fastembed")
    module.TextEmbedding = FakeTextEmbedding  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fastembed", module)
    monkeypatch.setattr(FakeTextEmbedding, "instances", 0)
    monkeypatch.setattr(FakeTextEmbedding, "fail_on_load", None)
    monkeypatch.setattr(FakeTextEmbedding, "fail_on_embed", None)
    monkeypatch.setattr(FakeTextEmbedding, "dimension", 3)


def embedder() -> FastEmbedEmbedder:
    return FastEmbedEmbedder(DEFAULT_MODEL, dimension=3, cache_dir="/models")


def embed(model: FastEmbedEmbedder, method: str) -> object:
    return model.embed_passages(["x"]) if method == "passages" else model.embed_query("x")


def test_vectors_are_plain_float_lists_in_the_same_order() -> None:
    assert embedder().embed_passages(["ab", "abcd"]) == [[2.0] * 3, [4.0] * 3]
    assert embedder().embed_query("abc") == [3.0] * 3


def test_the_model_is_loaded_lazily_and_only_once() -> None:
    model = embedder()
    assert FakeTextEmbedding.instances == 0  # rien au démarrage de l'API
    threads = [threading.Thread(target=model.embed_query, args=("x",)) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert FakeTextEmbedding.instances == 1
    assert model.model_name == DEFAULT_MODEL


def test_nothing_to_embed_does_not_load_the_model() -> None:
    assert embedder().embed_passages([]) == []
    assert FakeTextEmbedding.instances == 0


def test_a_loading_failure_becomes_unavailable() -> None:
    FakeTextEmbedding.fail_on_load = OSError("pas de réseau")
    with pytest.raises(EmbeddingUnavailableError, match="pas de réseau"):
        embedder().embed_query("x")


def test_a_missing_optional_dependency_is_explained(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "fastembed", None)  # l'import lèvera ImportError
    with pytest.raises(EmbeddingUnavailableError, match="extra « search »"):
        embedder().embed_query("x")


@pytest.mark.parametrize("method", ["passages", "query"])
def test_an_inference_failure_becomes_unavailable(method: str) -> None:
    FakeTextEmbedding.fail_on_embed = RuntimeError("ONNX en panne")
    model = embedder()
    with pytest.raises(EmbeddingUnavailableError, match="ONNX en panne"):
        embed(model, method)


@pytest.mark.parametrize("method", ["passages", "query"])
def test_a_wrong_vector_size_is_refused(method: str) -> None:
    FakeTextEmbedding.dimension = 4  # modèle changé sans migrer la base
    model = embedder()
    with pytest.raises(EmbeddingUnavailableError, match="taille 4"):
        embed(model, method)


def test_warm_up_loads_the_model() -> None:
    model = embedder()
    model.warm_up()
    assert FakeTextEmbedding.instances == 1


def test_warm_up_never_raises() -> None:
    FakeTextEmbedding.fail_on_load = OSError("pas de réseau")
    embedder().warm_up()  # journalisé, mais l'API démarre quand même
