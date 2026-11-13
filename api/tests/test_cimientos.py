"""Configuración, tipos de columna y errores de dominio (sprint 1)."""

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Column, Integer, MetaData, Table, insert, select

from la_elotiza_api.config import Settings
from la_elotiza_api.db import make_engine
from la_elotiza_api.errores import Conflicto, DatosInvalidos, NoAutenticado
from la_elotiza_api.main import create_app
from la_elotiza_api.tipos import Dinero, FechaUTC


def test_settings_lee_variables_de_entorno(monkeypatch):
    monkeypatch.setenv("LA_ELOTIZA_DATABASE_URL", "sqlite:///otra.db")
    monkeypatch.setenv("LA_ELOTIZA_CORS_ORIGINS", "http://a.test, http://b.test")
    s = Settings.from_env()
    assert s.database_url == "sqlite:///otra.db"
    assert s.cors_origins == ("http://a.test", "http://b.test")
    assert s.tz.key == "America/Mexico_City"


@pytest.fixture
def tabla():
    """Tabla temporal para probar los tipos propios contra SQLite."""
    engine = make_engine("sqlite://")
    meta = MetaData()
    t = Table(
        "prueba",
        meta,
        Column("id", Integer, primary_key=True),
        Column("monto", Dinero()),
        Column("fecha", FechaUTC()),
    )
    meta.create_all(engine)
    with engine.begin() as conn:
        yield t, conn


def test_dinero_se_guarda_en_centavos(tabla):
    t, conn = tabla
    conn.execute(insert(t).values(id=1, monto=Decimal("89.905")))
    crudo = conn.exec_driver_sql("SELECT monto FROM prueba").scalar()
    assert crudo == 8991  # redondeo comercial a centavos
    assert conn.execute(select(t.c.monto)).scalar() == Decimal("89.91")


def test_fecha_se_guarda_en_utc_y_regresa_con_zona(tabla):
    t, conn = tabla
    cdmx = timezone(timedelta(hours=-6))
    conn.execute(
        insert(t).values(id=1, fecha=datetime(2026, 9, 14, 20, 14, tzinfo=cdmx))
    )
    leida = conn.execute(select(t.c.fecha)).scalar()
    assert leida == datetime(2026, 9, 15, 2, 14, tzinfo=UTC)


def test_fecha_sin_zona_se_rechaza(tabla):
    t, conn = tabla
    with pytest.raises(Exception, match="zona horaria"):
        conn.execute(insert(t).values(id=1, fecha=datetime(2026, 9, 14)))


@pytest.mark.parametrize(
    ("error", "codigo"),
    [(NoAutenticado, 401), (Conflicto, 409), (DatosInvalidos, 422)],
)
def test_errores_de_dominio_se_traducen_a_http(settings, error, codigo):
    app = create_app(settings)

    @app.get("/falla")
    def falla():
        raise error("Algo salió mal", ["detalle 1"])

    with TestClient(app) as c:
        r = c.get("/falla")
    assert r.status_code == codigo
    assert r.json() == {"detail": "Algo salió mal", "errores": ["detalle 1"]}
    if codigo == 401:
        assert r.headers["www-authenticate"] == "Bearer"
