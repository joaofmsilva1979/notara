def test_lifespan_loads_btc_model(monkeypatch):
    """Lifespan warm-loads BTC. SynthTab is no longer used in jobs (D-17)."""
    from unittest.mock import MagicMock
    import asyncio

    btc_loaded = []

    monkeypatch.setattr("pipeline.chord_detection_btc._load_model",
                        lambda: btc_loaded.append(True))

    from api.main import lifespan
    from fastapi import FastAPI
    app = FastAPI()

    async def _run():
        async with lifespan(app):
            pass

    asyncio.run(_run())
    assert btc_loaded, "BTC model was not warm-loaded at startup"
