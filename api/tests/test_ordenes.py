"""Turno, captura de órdenes y comanda (RF 1-11, 19, 30-32, 35)."""

import pytest


@pytest.fixture
def sabri(item) -> dict:
    return item("Sabriesquite", "12 oz", [("Sabrita", "Takis")], nota="topping aparte")


# --- Turno ------------------------------------------------------------------


def test_sin_turno_no_se_levantan_ordenes(client, cajero):
    r = client.post("/ordenes", json={"cliente": "Karla"}, headers=cajero)
    assert r.status_code == 409
    assert "turno" in r.json()["detail"]
    assert client.get("/turnos/actual", headers=cajero).status_code == 404


def test_solo_un_turno_abierto(client, cajero, turno):
    assert client.post("/turnos", json={}, headers=cajero).status_code == 409
    actual = client.get("/turnos/actual", headers=cajero).json()
    assert actual["id"] == turno["id"]
    assert actual["fondo"] == 500
    assert actual["abierto_por"]["nombre"] == "Lupita"


def test_fondo_por_defecto_viene_de_la_configuracion(client, cajero, settings):
    r = client.post("/turnos", json={}, headers=cajero)
    assert r.json()["fondo"] == float(settings.fondo_caja)


# --- Captura ----------------------------------------------------------------


def test_agregar_producto_con_personalizacion_y_nota(client, cajero, turno, sabri):
    oid = client.post("/ordenes", json={}, headers=cajero).json()["id"]
    r = client.post(
        f"/ordenes/{oid}/items", json={**sabri, "cantidad": 2}, headers=cajero
    )
    assert r.status_code == 201
    orden = r.json()
    item = orden["items"][0]
    assert item["detalle"] == "12 oz · Sabrita: Takis"
    assert item["presentacion"] == "12 oz"
    assert [m["nombre"] for m in item["modificadores"]] == ["Takis"]
    assert item["nota"] == "topping aparte"
    assert item["precio_unitario"] == 70
    assert orden["total"] == 140
    assert orden["folio"] == f"#{oid:04d}"


def test_no_agrega_sin_opciones_obligatorias(client, cajero, turno, menu):
    oid = client.post("/ordenes", json={}, headers=cajero).json()["id"]
    cuerpo = {"producto_id": menu["Sabriesquite"]["id"]}
    r = client.post(f"/ordenes/{oid}/items", json=cuerpo, headers=cajero)
    assert r.status_code == 422
    assert r.json()["errores"] == ["Falta elegir: Presentación"]
    assert client.get(f"/ordenes/{oid}", headers=cajero).json()["items"] == []

    cuerpo["presentacion_id"] = menu["Sabriesquite"]["presentaciones"][0]["id"]
    r = client.post(f"/ordenes/{oid}/items", json=cuerpo, headers=cajero)
    assert r.json()["errores"] == ["Falta elegir: Sabrita entera"]


def test_total_se_actualiza_al_editar_y_quitar(
    client, cajero, nueva_orden, sabri, item
):
    orden = nueva_orden(items=[sabri, item("Coca-Cola")], confirmar=False)
    oid, (item_sabri, coca) = orden["id"], orden["items"]
    assert orden["total"] == 100

    nuevo = item("Sabriesquite", "20 oz", [("Sabrita", "Chips")])
    r = client.patch(
        f"/ordenes/{oid}/items/{item_sabri['id']}",
        json={
            "cantidad": 2,
            "personalizacion": {
                "presentacion_id": nuevo["presentacion_id"],
                "modificadores": nuevo["modificadores"],
            },
        },
        headers=cajero,
    )
    assert r.json()["total"] == 210  # 2 x 90 + 30
    assert r.json()["items"][0]["nota"] == "topping aparte"  # se conserva

    r = client.delete(f"/ordenes/{oid}/items/{coca['id']}", headers=cajero)
    assert r.json()["total"] == 180


def test_cambiar_nombre_del_cliente(client, cajero, nueva_orden):
    oid = nueva_orden(cliente="Karla", confirmar=False)["id"]
    r = client.patch(f"/ordenes/{oid}", json={"cliente": "  Diego "}, headers=cajero)
    assert r.json()["cliente"] == "Diego"


def test_cambiar_precio_no_afecta_ordenes_anteriores(
    client, admin, cajero, menu, nueva_orden
):
    vendida = nueva_orden()  # 2 cocas a $30
    coca = menu["Coca-Cola"]["id"]
    client.patch(f"/catalogo/productos/{coca}", json={"precio": 35}, headers=admin)
    antes = client.get(f"/ordenes/{vendida['id']}", headers=cajero).json()
    assert antes["total"] == 60
    assert nueva_orden()["total"] == 70


def test_orden_o_producto_inexistente(client, cajero, nueva_orden):
    assert client.get("/ordenes/999", headers=cajero).status_code == 404
    oid = nueva_orden(confirmar=False)["id"]
    r = client.patch(f"/ordenes/{oid}/items/999", json={"cantidad": 2}, headers=cajero)
    assert r.status_code == 404


# --- Comanda ----------------------------------------------------------------


def test_confirmar_exige_productos_y_cliente(client, cajero, turno):
    oid = client.post("/ordenes", json={}, headers=cajero).json()["id"]
    r = client.post(f"/ordenes/{oid}/confirmar", headers=cajero)
    assert r.status_code == 409
    assert r.json()["errores"] == [
        "Agrega al menos un producto",
        "Escribe el nombre del cliente",
    ]
    assert client.get(f"/ordenes/{oid}/comanda", headers=cajero).status_code == 409


def test_confirmar_genera_comanda_con_folio(client, cajero, nueva_orden, sabri):
    orden = nueva_orden(items=[sabri])
    comanda = orden["comanda"]
    assert orden["confirmada"] is True
    assert comanda["folio"] == orden["folio"]
    assert comanda["version"] == 1
    assert comanda["cliente"] == "Karla"
    linea = comanda["lineas"][0]
    assert linea["cantidad"] == 1
    assert linea["nombre"] == "Sabriesquite"
    assert linea["detalle"] == "12 oz · Sabrita: Takis"
    assert linea["nota"] == "topping aparte"


def test_confirmar_dos_veces_sin_cambios_no_duplica(client, cajero, nueva_orden):
    oid = nueva_orden()["id"]
    otra = client.post(f"/ordenes/{oid}/confirmar", headers=cajero).json()
    assert otra["version"] == 1


def test_cambios_despues_de_confirmar_piden_confirmar_otra_vez(
    client, cajero, nueva_orden, item
):
    orden = nueva_orden()
    oid = orden["id"]
    client.post(f"/ordenes/{oid}/items", json=item("Agua natural"), headers=cajero)

    sin_confirmar = client.get(f"/ordenes/{oid}", headers=cajero).json()
    assert sin_confirmar["comanda_al_dia"] is False
    # La comanda guardada sigue siendo la que ya está en cocina.
    assert len(sin_confirmar["comanda"]["lineas"]) == 1

    comanda = client.post(f"/ordenes/{oid}/confirmar", headers=cajero).json()
    assert comanda["version"] == 2
    assert len(comanda["lineas"]) == 2
    assert client.get(f"/ordenes/{oid}", headers=cajero).json()["comanda_al_dia"]


# --- Cancelación y listados -------------------------------------------------


def test_orden_cancelada_no_se_modifica(client, cajero, nueva_orden, item):
    orden = nueva_orden()
    oid, item_id = orden["id"], orden["items"][0]["id"]
    r = client.post(f"/ordenes/{oid}/cancelar", headers=cajero)
    assert r.json()["estado"] == "cancelada"
    assert r.json()["cancelada_en"]

    intentos = [
        client.post(f"/ordenes/{oid}/items", json=item("Agua natural"), headers=cajero),
        client.patch(
            f"/ordenes/{oid}/items/{item_id}", json={"cantidad": 5}, headers=cajero
        ),
        client.delete(f"/ordenes/{oid}/items/{item_id}", headers=cajero),
        client.patch(f"/ordenes/{oid}", json={"cliente": "Otro"}, headers=cajero),
        client.post(f"/ordenes/{oid}/confirmar", headers=cajero),
        client.post(f"/ordenes/{oid}/cancelar", headers=cajero),
    ]
    assert [r.status_code for r in intentos] == [409] * 6


def test_listado_por_filtro(client, cajero, nueva_orden):
    confirmada = nueva_orden(cliente="Karla")
    sin_confirmar = nueva_orden(cliente="Monse", confirmar=False)
    cancelada = nueva_orden(cliente="Jorge")
    client.post(f"/ordenes/{cancelada['id']}/cancelar", headers=cajero)

    def ids(filtro=None):
        params = {"filtro": filtro} if filtro else {}
        r = client.get("/ordenes", params=params, headers=cajero)
        return [o["id"] for o in r.json()]

    assert ids() == [confirmada["id"]]  # RF 35: solo confirmadas y vigentes
    assert ids("canceladas") == [cancelada["id"]]
    assert set(ids("todas")) == {
        confirmada["id"],
        sin_confirmar["id"],
        cancelada["id"],
    }


def test_ordenes_exigen_sesion(client):
    assert client.get("/ordenes").status_code == 401
    assert client.post("/turnos", json={}).status_code == 401
