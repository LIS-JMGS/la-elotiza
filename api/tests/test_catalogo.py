"""Reglas de personalización/precio del menú semilla y administración del
catálogo (RF 3-5, 30)."""

import pytest


@pytest.fixture
def cotizar(client, admin, item):
    def _cotizar(*args, **kwargs):
        return client.post("/menu/cotizar", json=item(*args, **kwargs), headers=admin)

    return _cotizar


def _ok(r) -> float:
    assert r.status_code == 200, r.text
    return r.json()["precio_unitario"]


def _errores(r) -> list[str]:
    assert r.status_code == 422, r.text
    return r.json()["errores"]


def test_menu_por_categorias(client, admin):
    menu = client.get("/menu", headers=admin).json()
    assert [c["nombre"] for c in menu] == [
        "Esquites",
        "Elotes",
        "Especiales",
        "Bebidas",
    ]
    esquite = menu[0]["productos"][0]
    assert esquite["nombre"] == "Esquite tradicional"
    assert esquite["precio"] is None
    assert esquite["precio_desde"] == 40
    assert [p["nombre"] for p in esquite["presentaciones"]] == [
        "9 oz",
        "12 oz",
        "20 oz",
    ]


@pytest.mark.parametrize(
    ("tamano", "esperado"), [("9 oz", 40), ("12 oz", 48), ("20 oz", 89)]
)
def test_la_presentacion_define_el_precio_base(cotizar, tamano, esperado):
    assert _ok(cotizar("Esquite tradicional", tamano)) == esperado


def test_presentacion_es_obligatoria(cotizar):
    assert _errores(cotizar("Esquite tradicional")) == ["Falta elegir: Presentación"]


def test_extras_y_toppings_suman_al_precio(cotizar):
    mods = [("Extra", "Tocino"), ("Extra", "Crema"), ("Topping", "Takis")]
    # 48 + tocino 40 + crema 15 + topping 15
    assert _ok(cotizar("Esquite tradicional", "12 oz", mods)) == 118


def test_ramen_incluye_un_topping_y_cobra_los_adicionales(cotizar):
    base = [("Ramen", "Negro"), ("Salsa", "1/2 salsa")]
    assert _ok(cotizar("Sabriramen", mods=[*base, ("Topping", "Takis")])) == 165
    dos = [*base, ("Topping", "Takis"), ("Topping", "Ruffles")]
    assert _ok(cotizar("Sabriramen", mods=dos)) == 180


def test_ramen_exige_tipo_topping_y_salsa(cotizar):
    assert _errores(cotizar("Sabriramen")) == [
        "Falta elegir: Tipo de ramen",
        "Falta elegir: Topping (sabrita triturada)",
        "Falta elegir: Cantidad de salsa",
    ]


def test_bolsas_cuestan_25_cada_una(cotizar):
    mods = [("Sabrita", "Takis"), ("Bolsa", "Chips"), ("Bolsa", "Ruffles")]
    assert _ok(cotizar("Charolazo", mods=mods)) == 200


def test_supremo_exige_dos_sabritas(cotizar):
    r = cotizar("Charolazo Supremo", mods=[("Sabrita", "Takis")])
    assert _errores(r) == ["Sabritas enteras (2, distintas): elige exactamente 2"]
    dos = [("Sabrita", "Takis"), ("Sabrita", "Tostitos Verdes")]
    assert _ok(cotizar("Charolazo Supremo", mods=dos)) == 275


def test_tostitos_en_sabriesquite_solo_en_20_oz(client, admin, cotizar, item, menu):
    assert _ok(cotizar("Sabriesquite", "20 oz", [("Sabrita", "Tostitos Verdes")])) == 90
    # En 12 oz la opción ni siquiera se ofrece.
    tostitos_20 = item("Sabriesquite", "20 oz", [("Sabrita", "Tostitos Verdes")])
    en_12 = {
        **item("Sabriesquite", "12 oz"),
        "modificadores": tostitos_20["modificadores"],
    }
    r = client.post("/menu/cotizar", json=en_12, headers=admin)
    assert _errores(r)[0].endswith("no aplica para Sabriesquite")


def test_no_se_repiten_opciones(client, admin, item):
    cuerpo = item("Charolazo Supremo", mods=[("Sabrita", "Takis")])
    cuerpo["modificadores"] *= 2
    r = client.post("/menu/cotizar", json=cuerpo, headers=admin)
    assert "No repitas opciones" in _errores(r)


def test_detalle_para_comanda(client, admin, item):
    cuerpo = item(
        "Sabriesquite", "12 oz", [("Sabrita", "Cheetos Flamin'"), ("Extra", "Tocino")]
    )
    r = client.post("/menu/cotizar", json=cuerpo, headers=admin)
    assert r.json()["detalle"] == "12 oz · Sabrita: Cheetos Flamin' · Extra: Tocino"
    coca = client.post("/menu/cotizar", json=item("Coca-Cola"), headers=admin)
    assert coca.json()["detalle"] == "Como viene"


# --- Disponibilidad ---------------------------------------------------------


def test_producto_agotado_no_se_vende(client, cajero, menu, item):
    coca = menu["Coca-Cola"]["id"]
    r = client.put(
        f"/menu/productos/{coca}/disponible", json={"disponible": False}, headers=cajero
    )
    assert r.json()["disponible"] is False
    r = client.post("/menu/cotizar", json=item("Coca-Cola"), headers=cajero)
    assert r.status_code == 409
    assert r.json()["detail"] == "Coca-Cola está agotado"


def test_opcion_agotada_no_se_vende(client, cajero, item):
    cuerpo = item("Elote revolcado", mods=[("Sabrita", "Takis")])
    takis = cuerpo["modificadores"][0]
    client.put(
        f"/menu/modificadores/{takis}/disponible",
        json={"disponible": False},
        headers=cajero,
    )
    r = client.post("/menu/cotizar", json=cuerpo, headers=cajero)
    assert _errores(r) == ["Takis está agotado"]


# --- Administración (encargado) ---------------------------------------------


def test_cajero_no_administra_el_catalogo(client, cajero):
    assert client.get("/catalogo", headers=cajero).status_code == 403
    r = client.post("/catalogo/categorias", json={"nombre": "Postres"}, headers=cajero)
    assert r.status_code == 403


def test_cambiar_precios_desde_el_catalogo(client, admin, cajero, menu, item):
    coca = menu["Coca-Cola"]["id"]
    r = client.patch(f"/catalogo/productos/{coca}", json={"precio": 35}, headers=admin)
    assert r.json()["precio"] == 35
    assert (
        _ok(client.post("/menu/cotizar", json=item("Coca-Cola"), headers=cajero)) == 35
    )

    chico = menu["Esquite tradicional"]["presentaciones"][0]["id"]
    client.patch(
        f"/catalogo/presentaciones/{chico}", json={"precio": 42}, headers=admin
    )
    r = client.post(
        "/menu/cotizar", json=item("Esquite tradicional", "9 oz"), headers=cajero
    )
    assert _ok(r) == 42


def test_alta_de_producto_con_presentaciones_y_grupo(client, admin, cajero):
    cat = client.post(
        "/catalogo/categorias", json={"nombre": "Postres", "orden": 9}, headers=admin
    )
    assert cat.status_code == 201
    prod = client.post(
        "/catalogo/productos",
        json={"categoria_id": cat.json()["id"], "nombre": "Fresas con crema"},
        headers=admin,
    ).json()
    chico = client.post(
        f"/catalogo/productos/{prod['id']}/presentaciones",
        json={"nombre": "Chico", "precio": 50},
        headers=admin,
    ).json()
    grupo = client.post(
        "/catalogo/grupos",
        json={"nombre": "Toppings de fresa", "etiqueta": "Topping"},
        headers=admin,
    ).json()
    granola = client.post(
        f"/catalogo/grupos/{grupo['id']}/modificadores",
        json={"nombre": "Granola", "precio": 10},
        headers=admin,
    ).json()
    liga = client.post(
        f"/catalogo/productos/{prod['id']}/grupos",
        json={"grupo_id": grupo["id"], "maximo": 2},
        headers=admin,
    )
    assert liga.status_code == 201

    postres = next(
        c
        for c in client.get("/menu", headers=cajero).json()
        if c["nombre"] == "Postres"
    )
    assert postres["productos"][0]["grupos"][0]["opciones"][0]["nombre"] == "Granola"
    r = client.post(
        "/menu/cotizar",
        json={
            "producto_id": prod["id"],
            "presentacion_id": chico["id"],
            "modificadores": [granola["id"]],
        },
        headers=cajero,
    )
    assert r.json()["precio_unitario"] == 60


def test_desactivar_producto_lo_quita_del_menu(client, admin, menu):
    coca = menu["Coca-Cola"]["id"]
    client.patch(f"/catalogo/productos/{coca}", json={"activo": False}, headers=admin)
    nombres = [
        p["nombre"]
        for c in client.get("/menu", headers=admin).json()
        for p in c["productos"]
    ]
    assert "Coca-Cola" not in nombres
    completo = client.get("/catalogo", headers=admin).json()
    assert "Coca-Cola" in [p["nombre"] for c in completo for p in c["productos"]]


def test_validaciones_de_administracion(client, admin, menu):
    dup = client.post("/catalogo/categorias", json={"nombre": "bebidas"}, headers=admin)
    assert dup.status_code == 409
    coca = menu["Coca-Cola"]["id"]
    nulo = client.patch(
        f"/catalogo/productos/{coca}", json={"nombre": None}, headers=admin
    )
    assert nulo.status_code == 422
    sin_cat = client.post(
        "/catalogo/productos", json={"categoria_id": 999, "nombre": "X"}, headers=admin
    )
    assert sin_cat.status_code == 404

    grupo_id = menu["Charolazo"]["grupos"][0]["grupo_id"]
    repetida = client.post(
        f"/catalogo/productos/{menu['Charolazo']['id']}/grupos",
        json={"grupo_id": grupo_id},
        headers=admin,
    )
    assert repetida.status_code == 409
    al_reves = client.post(
        f"/catalogo/productos/{coca}/grupos",
        json={"grupo_id": grupo_id, "minimo": 3, "maximo": 1},
        headers=admin,
    )
    assert al_reves.status_code == 422


def test_editar_y_quitar_liga(client, admin, menu, item):
    liga = menu["Elote revolcado"]["grupos"][0]  # Sabrita entera 1/1
    r = client.patch(f"/catalogo/ligas/{liga['id']}", json={"minimo": 0}, headers=admin)
    assert r.json()["minimo"] == 0
    assert (
        client.post(
            "/menu/cotizar", json=item("Elote revolcado"), headers=admin
        ).status_code
        == 200
    )

    assert (
        client.delete(f"/catalogo/ligas/{liga['id']}", headers=admin).status_code == 204
    )
    revolcado = next(
        p
        for c in client.get("/menu", headers=admin).json()
        for p in c["productos"]
        if p["nombre"] == "Elote revolcado"
    )
    assert [g["etiqueta"] for g in revolcado["grupos"]] == ["Topping", "Extra"]
