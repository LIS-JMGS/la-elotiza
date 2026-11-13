"""Corte de caja y cierre de turno (RF 20-26, 37-38)."""

import pytest


def _cobrar(client, headers, oid, metodo="efectivo", **extra):
    r = client.post(
        f"/ordenes/{oid}/cobro", json={"metodo": metodo, **extra}, headers=headers
    )
    assert r.status_code == 200, r.text


def _corte(client, headers, contado=None):
    params = {} if contado is None else {"efectivo_contado": contado}
    r = client.get("/turnos/actual/corte", params=params, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _cerrar(client, headers, contado):
    return client.post(
        "/turnos/actual/cierre", json={"efectivo_contado": contado}, headers=headers
    )


@pytest.fixture
def jornada(client, cajero, nueva_orden, item) -> dict:
    """Una venta en efectivo ($60), una por transferencia ($15) y una cancelada."""
    efectivo = nueva_orden(cliente="Diego")
    _cobrar(client, cajero, efectivo["id"], recibido=100)
    transfer = nueva_orden(cliente="Karla", items=[item("Agua natural")])
    _cobrar(client, cajero, transfer["id"], "transferencia", whatsapp_enviado=True)
    cancelada = nueva_orden(cliente="Jorge")
    client.post(f"/ordenes/{cancelada['id']}/cancelar", headers=cajero)
    return {"efectivo": efectivo, "transfer": transfer, "cancelada": cancelada}


def test_corte_de_turno_sin_ventas(client, cajero, turno):
    corte = _corte(client, cajero)
    assert corte["total_ventas"] == 0
    assert corte["efectivo_esperado"] == 500  # solo el fondo
    assert corte["efectivo_contado"] is None
    assert corte["diferencia"] is None
    assert corte["transferencias"] == []


def test_corte_separa_efectivo_y_transferencia(client, cajero, jornada):
    corte = _corte(client, cajero)
    assert corte["ordenes_cobradas"] == 2
    assert corte["total_ventas"] == 75
    assert corte["total_efectivo"] == 60
    assert corte["total_transferencia"] == 15
    transferencia = corte["transferencias"][0]
    assert transferencia["cliente"] == "Karla"
    assert transferencia["monto"] == 15
    assert transferencia["whatsapp_enviado"] is True
    assert transferencia["concepto"].endswith("-KARLA")


def test_las_canceladas_no_cuentan(client, cajero, jornada):
    corte = _corte(client, cajero)
    assert corte["ordenes_canceladas"] == 1
    assert corte["total_ventas"] == 75  # la de Jorge ($60) quedó fuera


def test_efectivo_esperado_incluye_el_fondo(client, cajero, jornada):
    corte = _corte(client, cajero)
    assert corte["fondo"] == 500
    # El cambio que se dio ($40) ya no está en caja: cuenta la venta, no lo recibido.
    assert corte["efectivo_esperado"] == 560


@pytest.mark.parametrize(
    ("contado", "diferencia", "texto"),
    [(560, 0, "$0.00"), (550, -10, "-$10.00"), (580, 20, "$20.00")],
)
def test_diferencia_contra_el_efectivo_contado(
    client, cajero, jornada, contado, diferencia, texto
):
    corte = _corte(client, cajero, contado)
    assert corte["efectivo_contado"] == contado
    assert corte["diferencia"] == diferencia
    assert texto in corte["texto"]


def test_cierre_exige_cobrar_o_cancelar_pendientes(client, cajero, nueva_orden):
    pendiente = nueva_orden()
    assert _corte(client, cajero)["ordenes_pendientes"] == 1
    r = _cerrar(client, cajero, 500)
    assert r.status_code == 409
    assert r.json()["errores"] == [pendiente["folio"]]
    assert client.get("/turnos/actual", headers=cajero).status_code == 200


def test_cerrar_turno_guarda_el_corte(client, cajero, jornada):
    r = _cerrar(client, cajero, 560)
    assert r.status_code == 200
    corte = r.json()
    assert corte["diferencia"] == 0
    assert corte["turno"]["cerrado_en"]
    assert corte["turno"]["efectivo_contado"] == 560

    # Ya no hay turno: no se levantan órdenes ni se cierra dos veces.
    assert client.get("/turnos/actual", headers=cajero).status_code == 404
    assert client.post("/ordenes", json={}, headers=cajero).status_code == 409
    assert _cerrar(client, cajero, 560).status_code == 409

    # El corte queda guardado para reimprimir.
    reimpresion = client.get(f"/turnos/{corte['turno']['id']}/corte", headers=cajero)
    assert reimpresion.json() == corte


def test_un_turno_nuevo_empieza_en_cero(client, cajero, jornada):
    _cerrar(client, cajero, 560)
    r = client.post("/turnos", json={"fondo": 300}, headers=cajero)
    assert r.status_code == 201
    nuevo = _corte(client, cajero)
    assert nuevo["total_ventas"] == 0
    assert nuevo["ordenes_cobradas"] == 0
    assert nuevo["efectivo_esperado"] == 300
    assert (
        client.get("/ordenes", params={"filtro": "todas"}, headers=cajero).json() == []
    )


def test_corte_imprimible(client, cajero, jornada):
    texto = _cerrar(client, cajero, 550).json()["texto"]
    for esperado in (
        "CORTE DE CAJA",
        "Total vendido",
        "$75.00",
        "Fondo de caja",
        "Efectivo esperado",
        "$560.00",
        "Efectivo contado",
        "Diferencia",
        "-$10.00",
        "Transferencias:",
    ):
        assert esperado in texto
    assert all(len(linea) <= 32 for linea in texto.splitlines())


def test_corte_exige_sesion_y_turno(client, cajero):
    assert client.get("/turnos/actual/corte").status_code == 401
    assert client.get("/turnos/actual/corte", headers=cajero).status_code == 409
    assert client.get("/turnos/999/corte", headers=cajero).status_code == 404
    assert _cerrar(client, cajero, 0).status_code == 409
