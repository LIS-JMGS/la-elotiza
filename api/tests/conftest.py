from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from la_elotiza_api.config import Settings
from la_elotiza_api.db import Base
from la_elotiza_api.main import create_app

ADMIN = {"nombre": "Rafa", "pin": "1234"}


@pytest.fixture
def settings() -> Settings:
    """Cada prueba usa su propia base SQLite en memoria."""
    return Settings(
        database_url="sqlite://",
        admin_nombre=ADMIN["nombre"],
        admin_pin=ADMIN["pin"],
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    return app


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def id_de(client: TestClient, nombre: str) -> int:
    usuarios = client.get("/auth/usuarios").json()
    return next(u["id"] for u in usuarios if u["nombre"] == nombre)


@pytest.fixture
def login(client: TestClient) -> Callable[[str, str], dict[str, str]]:
    """Inicia sesión y devuelve los headers de autorización."""

    def _login(nombre: str, pin: str) -> dict[str, str]:
        r = client.post(
            "/auth/login", json={"usuario_id": id_de(client, nombre), "pin": pin}
        )
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['token']}"}

    return _login


@pytest.fixture
def admin(login) -> dict[str, str]:
    """Headers del encargado inicial."""
    return login(ADMIN["nombre"], ADMIN["pin"])


@pytest.fixture
def cajero(client: TestClient, admin, login) -> dict[str, str]:
    """Headers de un cajero dado de alta por el encargado."""
    r = client.post(
        "/equipo",
        json={"nombre": "Lupita", "pin": "1111", "rol": "cajero"},
        headers=admin,
    )
    assert r.status_code == 201, r.text
    return login("Lupita", "1111")
