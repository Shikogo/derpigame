"""uvicorn entrypoint: ``uvicorn app.main:app``."""

from app.transport.app import create_app

app = create_app()
