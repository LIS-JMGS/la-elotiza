"""Menú inicial de La Elotiza (fuente: prototipo `POS La Elotiza v2`).

Solo se carga si el catálogo está vacío; después se administra desde la API.
Uso: `uv run cargar-menu`.
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from la_elotiza_api.models import (
    Categoria,
    GrupoModificadores,
    Modificador,
    Presentacion,
    Producto,
    ProductoGrupo,
)

log = logging.getLogger(__name__)

ENTERAS = [
    "Doritos Nachos",
    "Doritos Flamin'",
    "Cheetos Flamin'",
    "Takis",
    "Chips",
    "Rancheritos",
    "Ruffles",
]
TOSTITOS = ["Tostitos Morados", "Tostitos Verdes"]
TRITURADAS = [
    "Doritos Nachos",
    "Doritos Flamin'",
    "Cheetos Flamin'",
    "Cheetos Torciditos",
    "Takis",
    "Rancheritos",
    "Ruffles",
]
BOLSAS = ["Doritos Nachos", "Takis", "Chips", "Ruffles", *TOSTITOS]

# clave: (nombre, etiqueta, [(opción, precio)])
GRUPOS: dict[str, tuple[str, str, list[tuple[str, int]]]] = {
    "entera": ("Sabrita entera", "Sabrita", [(s, 0) for s in ENTERAS + TOSTITOS]),
    "topping": ("Topping", "Topping", [(s, 15) for s in TRITURADAS]),
    "ramen": (
        "Tipo de ramen",
        "Ramen",
        [
            (s, 0)
            for s in [
                "Carbonara (rosa)",
                "Carbonara cremosa (rosa-blanco)",
                "4 quesos (amarillo)",
                "Negro",
                "Morado",
                "Rojo",
            ]
        ],
    ),
    "salsa": (
        "Cantidad de salsa",
        "Salsa",
        [
            (s, 0)
            for s in [
                "Nada de salsa",
                "1/4 de salsa",
                "1/2 salsa",
                "Toda la salsa",
                "Salsa aparte",
            ]
        ],
    ),
    "bolsa": ("Bolsa de sabritas", "Bolsa", [(s, 25) for s in BOLSAS]),
    "extras": (
        "Extras",
        "Extra",
        [
            ("Queso cheddar", 15),
            ("Queso gouda", 15),
            ("Queso rallado", 15),
            ("Mayonesa", 15),
            ("Crema", 15),
            ("Mantequilla", 15),
            ("Tocino", 40),
            ("Aderezo chipotle", 15),
            ("Cubierto", 2),
        ],
    ),
    "sabor_refresco": (
        "Sabor de refresco",
        "Sabor",
        [("Coca Zero", 0), ("Mirinda", 0)],
    ),
    "sabor_lata": (
        "Sabor Kirkland lata",
        "Sabor",
        [("Toronja", 0), ("Limón amarillo", 0), ("Limón", 0)],
    ),
    "sabor_bote": (
        "Sabor Kirkland bote",
        "Sabor",
        [("Frambuesa", 0), ("Mango-naranja", 0)],
    ),
    "sabor_bolsa": ("Sabor de bolsa suelta", "Sabor", [(s, 0) for s in BOLSAS]),
}


@dataclass
class Liga:
    grupo: str
    minimo: int = 0
    maximo: int | None = None
    incluidas: int = 0
    titulo: str = ""
    solo_presentacion: str | None = None
    excluir: list[str] = field(default_factory=list)


def _una(grupo: str, **kw) -> Liga:
    return Liga(grupo, minimo=1, maximo=1, **kw)


TOPPING = Liga("topping", titulo="Topping (sabrita triturada)")
TOPPING_INCLUIDO = Liga(
    "topping", minimo=1, incluidas=1, titulo="Topping (sabrita triturada)"
)
BOLSA = Liga("bolsa")
EXTRAS_ESP = Liga("extras")
EXTRAS_SAB = Liga("extras", excluir=["Queso gouda", "Aderezo chipotle", "Cubierto"])
EXTRAS_ESQ = Liga(
    "extras", excluir=["Queso cheddar", "Queso gouda", "Aderezo chipotle"]
)
EXTRAS_ING = Liga(
    "extras",
    excluir=[
        "Queso cheddar",
        "Queso gouda",
        "Tocino",
        "Aderezo chipotle",
        "Cubierto",
    ],
)
ENTERA_SIN_TOSTITOS = _una("entera", excluir=TOSTITOS)


@dataclass
class P:
    nombre: str
    descripcion: str
    precio: int | None = None
    presentaciones: list[tuple[str, int]] = field(default_factory=list)
    ligas: list[Liga] = field(default_factory=list)


MENU: dict[str, list[P]] = {
    "Esquites": [
        P(
            "Esquite tradicional",
            "Elote desgranado con mantequilla, mayonesa, crema, queso rallado y limón",
            presentaciones=[("9 oz", 40), ("12 oz", 48), ("20 oz", 89)],
            ligas=[TOPPING, EXTRAS_ESQ],
        ),
        P(
            "Sabriesquite",
            "Elote desgranado con sabritas de tu elección, queso rallado y derretido",
            presentaciones=[("12 oz", 70), ("20 oz", 90)],
            ligas=[
                # Tostitos solo en 20 oz.
                _una("entera", solo_presentacion="12 oz", excluir=TOSTITOS),
                _una("entera", solo_presentacion="20 oz"),
                TOPPING,
                EXTRAS_SAB,
            ],
        ),
    ],
    "Elotes": [
        P(
            "Elote revolcado",
            "Elote con mantequilla, mayonesa, crema, sabritas de tu elección, "
            "queso rallado y derretido",
            precio=65,
            ligas=[ENTERA_SIN_TOSTITOS, TOPPING, EXTRAS_SAB],
        ),
        P(
            "Elote tradicional",
            "Elote con mantequilla, mayonesa, crema y queso rallado",
            precio=45,
            ligas=[TOPPING, EXTRAS_ING],
        ),
    ],
    "Especiales": [
        P(
            "Charolazo",
            "1 elote revolcado + esquite preparado + sabritas, bañado en queso líquido",
            precio=150,
            ligas=[_una("entera"), TOPPING, BOLSA, EXTRAS_ESP],
        ),
        P(
            "Charolazo Supremo",
            "2 elotes revolcados + esquite + 2 sabritas + cheddar + aderezo chipotle "
            "+ rallado",
            precio=275,
            ligas=[
                Liga(
                    "entera",
                    minimo=2,
                    maximo=2,
                    titulo="Sabritas enteras (2, distintas)",
                ),
                TOPPING,
                BOLSA,
                EXTRAS_ESP,
            ],
        ),
        P(
            "Sabriramen",
            "Ramen Buldak + esquite preparado + topping + queso cheddar y rallado",
            precio=165,
            ligas=[_una("ramen"), TOPPING_INCLUIDO, _una("salsa"), BOLSA, EXTRAS_ESP],
        ),
        P(
            "Sabriramen Especial",
            "Ramen Buldak + gouda + esquite + topping + cheddar + rallado + tocino "
            "+ aderezo chipotle",
            precio=220,
            ligas=[_una("ramen"), TOPPING_INCLUIDO, _una("salsa"), BOLSA, EXTRAS_ESP],
        ),
        P(
            "Papa Elotiza",
            "Papa preparada + esquite + sabritas + cheddar + rallado + tocino",
            precio=175,
            ligas=[ENTERA_SIN_TOSTITOS, TOPPING, BOLSA, EXTRAS_ESP],
        ),
    ],
    "Bebidas": [
        P("Coca-Cola", "600 ml", precio=30),
        P("Seven Up", "600 ml", precio=30),
        P("Agua natural", "600 ml", precio=15),
        P("Kirkland fresa-kiwi", "Bote gasificado", precio=30),
        P(
            "Otro refresco",
            "Coca Zero o Mirinda, 600 ml",
            precio=30,
            ligas=[_una("sabor_refresco")],
        ),
        P("Kirkland en lata", "Agua gasificada", precio=30, ligas=[_una("sabor_lata")]),
        P("Kirkland en bote", "Agua gasificada", precio=30, ligas=[_una("sabor_bote")]),
        P(
            "Bolsa de sabritas",
            "Se vende sola",
            precio=25,
            ligas=[_una("sabor_bolsa")],
        ),
        P("Cubierto", "Suelto", precio=2),
    ],
}


def cargar_menu_inicial(db: Session) -> bool:
    """Carga el menú si no hay categorías. Devuelve True si cargó algo."""
    if db.scalar(select(func.count()).select_from(Categoria)):
        return False

    grupos: dict[str, GrupoModificadores] = {}
    for clave, (nombre, etiqueta, opciones) in GRUPOS.items():
        grupo = GrupoModificadores(nombre=nombre, etiqueta=etiqueta)
        grupo.modificadores = [
            Modificador(nombre=n, precio=Decimal(p), orden=i)
            for i, (n, p) in enumerate(opciones)
        ]
        grupos[clave] = grupo
        db.add(grupo)

    for orden_cat, (nombre_cat, productos) in enumerate(MENU.items()):
        categoria = Categoria(nombre=nombre_cat, orden=orden_cat)
        db.add(categoria)
        for orden_prod, p in enumerate(productos):
            producto = Producto(
                categoria=categoria,
                nombre=p.nombre,
                descripcion=p.descripcion,
                precio=None if p.precio is None else Decimal(p.precio),
                orden=orden_prod,
            )
            presentaciones = {
                n: Presentacion(nombre=n, precio=Decimal(precio), orden=i)
                for i, (n, precio) in enumerate(p.presentaciones)
            }
            producto.presentaciones = list(presentaciones.values())
            for orden_liga, liga in enumerate(p.ligas):
                grupo = grupos[liga.grupo]
                producto.grupos.append(
                    ProductoGrupo(
                        grupo=grupo,
                        presentacion=(
                            presentaciones[liga.solo_presentacion]
                            if liga.solo_presentacion
                            else None
                        ),
                        titulo=liga.titulo,
                        orden=orden_liga,
                        minimo=liga.minimo,
                        maximo=liga.maximo,
                        incluidas=liga.incluidas,
                        excluidos=[
                            m for m in grupo.modificadores if m.nombre in liga.excluir
                        ],
                    )
                )
            db.add(producto)
    db.commit()
    return True


def main() -> None:
    """Punto de entrada de `uv run cargar-menu`."""
    from la_elotiza_api.config import Settings
    from la_elotiza_api.db import make_engine, make_sessionmaker

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    engine = make_engine(Settings.from_env().database_url)
    with make_sessionmaker(engine)() as db:
        if cargar_menu_inicial(db):
            log.info("Menú inicial cargado.")
        else:
            log.info("El catálogo ya tiene datos; no se cargó nada.")
    engine.dispose()
