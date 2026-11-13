"""Cobro, ticket, impresión y cocina (RF 12-18, 33-34, 36)."""

import pytest


@pytest.fixture
def sabri(item) -> dict:
    return item("Sabriesquite", "12 oz", [("Sabrita", "Takis")], nota="topping aparte")


def _cobrar(client, headers, oid, **cuerpo):
    cuerpo.setdefault("metodo", "efectivo")
    return client.post(f"/ordenes/{oid}/cobro", json=cuerpo, headers=headers)


# --- Cobro ------------------------------------------------------------------


def test_cobro_en_efectivo_calcula_cambio_y_cierra(client, cajero, nueva_orden):
    orden = nueva_orden(cliente="Diego")  # 2 cocas = 60
    oid = orden["id"]
    r = _cobrar(client, cajero, oid, recibido=100)
    assert r.status_code == 200
    ticket = r.json()
    assert ticket["total"] == 60
    assert ticket["pago"]["metodo"] == "efectivo"
    assert ticket["pago"]["recibido"] == 100
    assert ticket["pago"]["cambio"] == 40
    assert ticket["pago"]["registrado_en"]
    for texto in ("Diego", "2x Coca-Cola", "$60.00", "Efectivo", "Cambio"):
        assert texto in ticket["texto"]

    cerrada = client.get(f"/ordenes/{oid}", headers=cajero).json()
    assert cerrada["estado"] == "cerrada"
    assert cerrada["pago"]["total"] == 60
    assert client.get(f"/ordenes/{oid}/ticket", headers=cajero).json() == ticket


def test_efectivo_exacto_si_no_se_indica_recibido(client, cajero, nueva_orden):
    pago = _cobrar(client, cajero, nueva_orden()["id"]).json()["pago"]
    assert pago["recibido"] == 60
    assert pago["cambio"] == 0


def test_efectivo_insuficiente(client, cajero, nueva_orden):
    oid = nueva_orden()["id"]
    assert _cobrar(client, cajero, oid, recibido=50).status_code == 422
    assert client.get(f"/ordenes/{oid}", headers=cajero).json()["estado"] == "abierta"


def test_no_se_cobra_sin_confirmar(client, cajero, nueva_orden, item):
    sin_confirmar = nueva_orden(confirmar=False)
    assert _cobrar(client, cajero, sin_confirmar["id"]).status_code == 409

    # Confirmada, pero con cambios pendientes de mandar a cocina (RF 32).
    oid = nueva_orden()["id"]
    client.post(f"/ordenes/{oid}/items", json=item("Agua natural"), headers=cajero)
    assert _cobrar(client, cajero, oid).status_code == 409
    client.post(f"/ordenes/{oid}/confirmar", headers=cajero)
    assert _cobrar(client, cajero, oid).status_code == 200


def test_orden_cobrada_no_se_modifica(client, cajero, nueva_orden, item):
    orden = nueva_orden()
    oid, item_id = orden["id"], orden["items"][0]["id"]
    _cobrar(client, cajero, oid)

    intentos = [
        client.post(f"/ordenes/{oid}/items", json=item("Agua natural"), headers=cajero),
        client.patch(
            f"/ordenes/{oid}/items/{item_id}", json={"cantidad": 5}, headers=cajero
        ),
        client.delete(f"/ordenes/{oid}/items/{item_id}", headers=cajero),
        client.patch(f"/ordenes/{oid}", json={"cliente": "Otro"}, headers=cajero),
        client.post(f"/ordenes/{oid}/confirmar", headers=cajero),
        client.post(f"/ordenes/{oid}/cancelar", headers=cajero),
        _cobrar(client, cajero, oid),
    ]
    assert [r.status_code for r in intentos] == [409] * 7


def test_orden_cancelada_no_se_cobra(client, cajero, nueva_orden):
    oid = nueva_orden()["id"]
    client.post(f"/ordenes/{oid}/cancelar", headers=cajero)
    assert _cobrar(client, cajero, oid).status_code == 409
    assert client.get(f"/ordenes/{oid}/ticket", headers=cajero).status_code == 409


# --- Transferencia ----------------------------------------------------------


def test_transferencia_con_concepto_unico_y_whatsapp(client, cajero, nueva_orden):
    orden = nueva_orden(cliente="José Luis")
    oid = orden["id"]
    r = client.get(
        f"/ordenes/{oid}/transferencia",
        params={"telefono": "55 1234 5678"},
        headers=cajero,
    )
    datos = r.json()
    assert datos["concepto"].startswith("ELO-")
    assert datos["concepto"].endswith(f"-{oid:04d}-JOSE")  # sin acentos
    assert datos["total"] == 60
    assert datos["whatsapp_url"].startswith("https://wa.me/525512345678?text=")
    assert datos["concepto"] in datos["mensaje"]

    ticket = _cobrar(
        client, cajero, oid, metodo="transferencia", whatsapp_enviado=True
    ).json()
    assert ticket["pago"]["concepto"] == datos["concepto"]
    assert ticket["pago"]["whatsapp_enviado"] is True
    assert ticket["pago"]["recibido"] is None
    assert datos["concepto"] in ticket["texto"]


def test_conceptos_distintos_por_orden(client, cajero, nueva_orden):
    conceptos = set()
    for _ in range(2):
        oid = nueva_orden(cliente="Karla")["id"]
        ticket = _cobrar(client, cajero, oid, metodo="transferencia").json()
        conceptos.add(ticket["pago"]["concepto"])
    assert len(conceptos) == 2


def test_whatsapp_sin_telefono_y_telefono_invalido(client, cajero, nueva_orden):
    oid = nueva_orden()["id"]
    r = client.get(f"/ordenes/{oid}/transferencia", headers=cajero)
    assert r.json()["whatsapp_url"].startswith("https://wa.me/?text=")
    r = client.get(
        f"/ordenes/{oid}/transferencia", params={"telefono": "123"}, headers=cajero
    )
    assert r.status_code == 422


# --- Impresión --------------------------------------------------------------


def test_comanda_imprimible(client, cajero, nueva_orden, sabri, item):
    orden = nueva_orden(items=[sabri])
    texto = orden["comanda"]["texto"]
    assert "COMANDA" in texto
    assert orden["folio"] in texto
    assert "1x Sabriesquite" in texto
    assert "* topping aparte" in texto
    assert all(len(linea) <= 32 for linea in texto.splitlines())

    oid = orden["id"]
    client.post(f"/ordenes/{oid}/items", json=item("Agua natural"), headers=cajero)
    cambio = client.post(f"/ordenes/{oid}/confirmar", headers=cajero).json()
    assert "COMANDA (CAMBIO 1)" in cambio["texto"]


def test_ticket_cabe_en_32_columnas(client, cajero, nueva_orden, item):
    largo = item(
        "Charolazo Supremo",
        mods=[("Sabrita", "Doritos Nachos"), ("Sabrita", "Tostitos Verdes")],
    )
    oid = nueva_orden(cliente="María Fernanda", items=[largo])["id"]
    texto = _cobrar(client, cajero, oid, recibido=500).json()["texto"]
    assert all(len(linea) <= 32 for linea in texto.splitlines())
    assert "$275.00" in texto and "$225.00" in texto


# --- Cocina -----------------------------------------------------------------


def test_cocina_marca_preparados_y_entrega(client, cajero, nueva_orden, sabri, item):
    orden = nueva_orden(items=[sabri, item("Coca-Cola")])
    oid, item_id = orden["id"], orden["items"][0]["id"]

    r = client.put(f"/ordenes/{oid}/items/{item_id}/preparado", json={}, headers=cajero)
    lineas = r.json()["comanda"]["lineas"]
    assert [linea["preparado"] for linea in lineas] == [True, False]

    # No se entrega sin cobrar.
    r = client.put(f"/ordenes/{oid}/entrega", json={}, headers=cajero)
    assert r.status_code == 409

    _cobrar(client, cajero, oid)
    entregada = client.put(f"/ordenes/{oid}/entrega", json={}, headers=cajero).json()
    assert entregada["entregada"] is True
    assert all(i["preparado"] for i in entregada["items"])

    assert client.get("/ordenes", headers=cajero).json() == []
    r = client.get("/ordenes", params={"filtro": "entregadas"}, headers=cajero)
    assert [o["id"] for o in r.json()] == [oid]

    # Reabrir: vuelve a la lista de preparación.
    r = client.put(f"/ordenes/{oid}/entrega", json={"entregada": False}, headers=cajero)
    assert r.json()["entregada"] is False
    assert [o["id"] for o in client.get("/ordenes", headers=cajero).json()] == [oid]


def test_marcar_y_desmarcar_todo(client, cajero, nueva_orden, sabri, item):
    oid = nueva_orden(items=[sabri, item("Coca-Cola")])["id"]
    r = client.put(f"/ordenes/{oid}/preparado", json={}, headers=cajero)
    assert all(i["preparado"] for i in r.json()["items"])
    r = client.put(
        f"/ordenes/{oid}/preparado", json={"preparado": False}, headers=cajero
    )
    assert not any(i["preparado"] for i in r.json()["items"])


def test_editar_un_producto_lo_regresa_a_pendiente(client, cajero, nueva_orden):
    orden = nueva_orden()
    oid, item_id = orden["id"], orden["items"][0]["id"]
    client.put(f"/ordenes/{oid}/items/{item_id}/preparado", json={}, headers=cajero)
    r = client.patch(
        f"/ordenes/{oid}/items/{item_id}", json={"cantidad": 3}, headers=cajero
    )
    assert r.json()["items"][0]["preparado"] is False


def test_no_se_prepara_lo_que_no_esta_en_cocina(client, cajero, nueva_orden):
    sin_confirmar = nueva_orden(confirmar=False)["id"]
    r = client.put(f"/ordenes/{sin_confirmar}/preparado", json={}, headers=cajero)
    assert r.status_code == 409

    cancelada = nueva_orden()["id"]
    client.post(f"/ordenes/{cancelada}/cancelar", headers=cajero)
    r = client.put(f"/ordenes/{cancelada}/preparado", json={}, headers=cajero)
    assert r.status_code == 409
