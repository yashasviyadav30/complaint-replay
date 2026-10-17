from replay.grouping import cosine, scores, settings


def test_cosine() -> None:
    assert cosine([1, 0], [1, 0]) == 1.0
    assert cosine([1, 0], [0, 1]) == 0.0


def test_scores_count_merges_against_labels() -> None:
    pairs = [(1.0, True), (1.0, False), (0.0, True), (0.0, False)]  # (merged?, really the same bug?)
    assert scores(pairs, 0.5) == {"precision": 0.5, "recall": 0.5, "f1": 0.5, "pairs": 4}


def test_settings_have_safe_defaults(tmp_path, monkeypatch) -> None:
    import replay.grouping as g
    monkeypatch.setattr(g, "SETTINGS", tmp_path / "missing.json")
    assert settings() == {"embed_text": "raw", "top_k": 3}


def test_embedding_model_comes_from_the_providers_catalog(monkeypatch) -> None:
    import asyncio
    from types import SimpleNamespace

    from replay import grouping

    monkeypatch.delenv("EMBED_MODEL", raising=False)

    class Models:
        async def list(self):
            return SimpleNamespace(data=[SimpleNamespace(id="nvidia/nemotron-3-super-120b-a12b"),
                                         SimpleNamespace(id="nvidia/Nemotron-Embed-1B-v2")])

    client = SimpleNamespace(models=Models())
    assert asyncio.run(grouping.embed_model(client)) == "nvidia/Nemotron-Embed-1B-v2"
    monkeypatch.setenv("EMBED_MODEL", "mine")
    assert asyncio.run(grouping.embed_model(client)) == "mine"
