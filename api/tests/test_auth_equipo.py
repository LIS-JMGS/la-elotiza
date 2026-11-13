"""Inicio de sesión con PIN (RF 27) y administración del equipo (RF 28-29)."""

from datetime import timedelta

from conftest import ADMIN, id_de

from la_elotiza_api.models import SesionToken, Usuario
from la_elotiza_api.seguridad import hash_pin, verificar_pin
from la_elotiza_api.tipos import ahora_utc


def _login(client, nombre, pin):
    return client.post(
        "/auth/login", json={"usuario_id": id_de(client, nombre), "pin": pin}
    )


def test_el_pin_se_guarda_con_hash_y_sal(app, client):
    with app.state.sessionmaker() as db:
        guardado = db.query(Usuario).one().pin_hash
    assert ADMIN["pin"] not in guardado
    assert verificar_pin(ADMIN["pin"], guardado)
    assert not verificar_pin("0000", guardado)
    assert hash_pin("1234") != hash_pin("1234")  # sal distinta cada vez


def test_crea_encargado_inicial_y_lista_nombres_sin_sesion(client):
    usuarios = client.get("/auth/usuarios").json()
    assert [u["nombre"] for u in usuarios] == [ADMIN["nombre"]]
    assert set(usuarios[0]) == {"id", "nombre"}  # no expone PIN ni rol


def test_login_correcto_devuelve_usuario_y_token(client):
    r = _login(client, "Rafa", ADMIN["pin"])
    assert r.status_code == 200
    datos = r.json()
    assert datos["usuario"]["rol"] == "encargado"
    yo = client.get("/auth/yo", headers={"Authorization": f"Bearer {datos['token']}"})
    assert yo.json()["nombre"] == "Rafa"


def test_pin_incorrecto_o_mal_formado(client):
    assert _login(client, "Rafa", "9999").status_code == 401
    assert _login(client, "Rafa", "12").status_code == 422
    r = client.post("/auth/login", json={"usuario_id": 999, "pin": "1234"})
    assert r.status_code == 401


def test_bloquea_tras_varios_intentos_fallidos(client, settings):
    for _ in range(settings.max_intentos_pin):
        _login(client, "Rafa", "0000")
    assert _login(client, "Rafa", ADMIN["pin"]).status_code == 429


def test_el_bloqueo_expira(app, client, settings):
    for _ in range(settings.max_intentos_pin):
        _login(client, "Rafa", "0000")
    with app.state.sessionmaker() as db:
        usuario = db.query(Usuario).one()
        usuario.bloqueado_hasta = ahora_utc() - timedelta(seconds=1)
        db.commit()
    assert _login(client, "Rafa", ADMIN["pin"]).status_code == 200


def test_rutas_protegidas_exigen_sesion(client):
    assert client.get("/auth/yo").status_code == 401
    malo = {"Authorization": "Bearer inventado"}
    assert client.get("/auth/yo", headers=malo).status_code == 401


def test_sesion_expirada_no_sirve(app, client, admin):
    with app.state.sessionmaker() as db:
        sesion = db.query(SesionToken).one()
        sesion.expira_en = ahora_utc() - timedelta(seconds=1)
        db.commit()
    assert client.get("/auth/yo", headers=admin).status_code == 401


def test_logout_invalida_el_token(client, admin):
    assert client.post("/auth/logout", headers=admin).status_code == 204
    assert client.get("/auth/yo", headers=admin).status_code == 401


def test_encargado_agrega_personas(client, admin, login):
    r = client.post(
        "/equipo",
        json={"nombre": "  Toño ", "pin": "2222", "rol": "cajero"},
        headers=admin,
    )
    assert r.status_code == 201
    assert r.json()["nombre"] == "Toño"
    assert login("Toño", "2222")
    nombres = [u["nombre"] for u in client.get("/equipo", headers=admin).json()]
    assert sorted(nombres) == ["Rafa", "Toño"]


def test_no_permite_nombres_repetidos_ni_pin_invalido(client, admin):
    dup = client.post("/equipo", json={"nombre": "rafa", "pin": "2222"}, headers=admin)
    assert dup.status_code == 409
    pin = client.post("/equipo", json={"nombre": "Ana", "pin": "12a4"}, headers=admin)
    assert pin.status_code == 422


def test_cajero_no_administra_al_equipo(client, cajero):
    assert client.get("/equipo", headers=cajero).status_code == 403
    r = client.post("/equipo", json={"nombre": "Ana", "pin": "3333"}, headers=cajero)
    assert r.status_code == 403
    r = client.delete(f"/equipo/{id_de(client, 'Rafa')}", headers=cajero)
    assert r.status_code == 403


def test_quitar_acceso_cierra_sus_sesiones(client, admin, cajero):
    uid = id_de(client, "Lupita")
    assert client.delete(f"/equipo/{uid}", headers=admin).status_code == 204
    assert client.get("/auth/yo", headers=cajero).status_code == 401
    assert "Lupita" not in [u["nombre"] for u in client.get("/auth/usuarios").json()]


def test_no_se_puede_quitar_a_si_mismo_ni_al_ultimo_encargado(client, admin, login):
    rafa = id_de(client, "Rafa")
    assert client.delete(f"/equipo/{rafa}", headers=admin).status_code == 409

    client.post(
        "/equipo",
        json={"nombre": "Ana", "pin": "4444", "rol": "encargado"},
        headers=admin,
    )
    ana = login("Ana", "4444")
    assert client.delete(f"/equipo/{rafa}", headers=ana).status_code == 204
