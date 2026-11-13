from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from la_elotiza_api.config import Settings
from la_elotiza_api.db import Base
from la_elotiza_api.main import create_app
from la_elotiza_api.semilla import cargar_menu_inicial

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
    with app.state.sessionmaker() as db:
        cargar_menu_inicial(db)
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


@pytest.fixture
def menu(client: TestClient, admin) -> dict[str, dict]:
    """Productos del menú (semilla) indexados por nombre."""
    categorias = client.get("/menu", headers=admin).json()
    return {p["nombre"]: p for c in categorias for p in c["productos"]}


@pytest.fixture
def item(menu) -> Callable[..., dict]:
    """Arma el cuerpo de un producto por nombres en vez de ids.

    `mods` son pares (etiqueta del grupo, opción), p. ej. ("Sabrita", "Takis").
    """

    def _item(
        producto: str,
        presentacion: str | None = None,
        mods: list[tuple[str, str]] = (),
        cantidad: int = 1,
        nota: str = "",
    ) -> dict:
        p = menu[producto]
        pres_id = next(
            (x["id"] for x in p["presentaciones"] if x["nombre"] == presentacion),
            None,
        )
        ids = []
        for etiqueta, opcion in mods:
            liga = next(
                g
                for g in p["grupos"]
                if g["etiqueta"] == etiqueta and g["presentacion_id"] in (None, pres_id)
            )
            ids.append(next(o["id"] for o in liga["opciones"] if o["nombre"] == opcion))
        cuerpo = {
            "producto_id": p["id"],
            "presentacion_id": pres_id,
            "modificadores": ids,
            "cantidad": cantidad,
        }
        if nota:  # `nota` solo existe al agregar a una orden, no al cotizar
            cuerpo["nota"] = nota
        return cuerpo

    return _item
