from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from la_elotiza_api.config import Settings
from la_elotiza_api.db import Base
from la_elotiza_api.main import create_app


@pytest.fixture
def settings() -> Settings:
    """Cada prueba usa su propia base SQLite en memoria."""
    return Settings(database_url="sqlite://")


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    return app


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c
