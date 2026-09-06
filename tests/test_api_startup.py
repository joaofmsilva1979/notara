def test_lifespan_loads_btc_and_synthtab_models(monkeypatch):
    """Lifespan calls _load_model and _load on startup."""
    from unittest.mock import MagicMock
    import asyncio

    btc_loaded = []
    synthtab_loaded = []

    monkeypatch.setattr("pipeline.chord_detection_btc._load_model",
                        lambda: btc_loaded.append(True))
    monkeypatch.setattr("pipeline.transcription_synthtab._load",
                        lambda: synthtab_loaded.append(True))

    from api.main import lifespan
    from fastapi import FastAPI
    app = FastAPI()

    async def _run():
        async with lifespan(app):
            pass

    asyncio.run(_run())
    assert btc_loaded, "BTC model was not warm-loaded at startup"
    assert synthtab_loaded, "SynthTab model was not warm-loaded at startup"
