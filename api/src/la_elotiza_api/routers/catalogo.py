"""Administración del catálogo (solo encargado).

Nada se borra: productos, presentaciones y opciones se desactivan con
`activo=false` para conservar el historial de ventas. Las ligas
producto-grupo sí se pueden quitar.
"""

from fastapi import APIRouter, status

from la_elotiza_api.deps import DB, Encargado
from la_elotiza_api.schemas import (
    CatalogoCategoriaOut,
    CategoriaCambios,
    CategoriaIn,
    CategoriaOut,
    GrupoCambios,
    GrupoIn,
    GrupoOut,
    LigaCambios,
    LigaIn,
    LigaOut,
    ModificadorCambios,
    ModificadorIn,
    ModificadorOut,
    PresentacionCambios,
    PresentacionIn,
    PresentacionOut,
    ProductoCambios,
    ProductoIn,
    ProductoOut,
)
from la_elotiza_api.servicios import catalogo

router = APIRouter(prefix="/catalogo", tags=["catálogo"])
CREADO = status.HTTP_201_CREATED


@router.get("", response_model=list[CatalogoCategoriaOut])
def catalogo_completo(db: DB, _: Encargado):
    """Todo el catálogo, incluidos los elementos inactivos."""
    return catalogo.categorias(db, solo_activos=False)


@router.post("/categorias", response_model=CategoriaOut, status_code=CREADO)
def crear_categoria(datos: CategoriaIn, db: DB, _: Encargado):
    return catalogo.crear_categoria(db, datos.model_dump())


@router.patch("/categorias/{categoria_id}", response_model=CategoriaOut)
def editar_categoria(categoria_id: int, datos: CategoriaCambios, db: DB, _: Encargado):
    return catalogo.editar_categoria(db, categoria_id, datos.cambios())


@router.post("/productos", response_model=ProductoOut, status_code=CREADO)
def crear_producto(datos: ProductoIn, db: DB, _: Encargado):
    return catalogo.crear_producto(db, datos.model_dump())


@router.get("/productos/{producto_id}", response_model=ProductoOut)
def producto(producto_id: int, db: DB, _: Encargado):
    return catalogo.obtener_producto(db, producto_id)


@router.patch("/productos/{producto_id}", response_model=ProductoOut)
def editar_producto(producto_id: int, datos: ProductoCambios, db: DB, _: Encargado):
    return catalogo.editar_producto(db, producto_id, datos.cambios())


@router.post(
    "/productos/{producto_id}/presentaciones",
    response_model=PresentacionOut,
    status_code=CREADO,
)
def crear_presentacion(producto_id: int, datos: PresentacionIn, db: DB, _: Encargado):
    return catalogo.crear_presentacion(db, producto_id, datos.model_dump())


@router.patch("/presentaciones/{presentacion_id}", response_model=PresentacionOut)
def editar_presentacion(
    presentacion_id: int, datos: PresentacionCambios, db: DB, _: Encargado
):
    return catalogo.editar_presentacion(db, presentacion_id, datos.cambios())


@router.post(
    "/productos/{producto_id}/grupos", response_model=LigaOut, status_code=CREADO
)
def ligar_grupo(producto_id: int, datos: LigaIn, db: DB, _: Encargado):
    """Agrega un grupo de opciones a un producto con sus reglas."""
    return catalogo.ligar_grupo(db, producto_id, datos.model_dump())


@router.patch("/ligas/{liga_id}", response_model=LigaOut)
def editar_liga(liga_id: int, datos: LigaCambios, db: DB, _: Encargado):
    return catalogo.editar_liga(db, liga_id, datos.cambios())


@router.delete("/ligas/{liga_id}", status_code=status.HTTP_204_NO_CONTENT)
def quitar_liga(liga_id: int, db: DB, _: Encargado) -> None:
    catalogo.quitar_liga(db, liga_id)


@router.get("/grupos", response_model=list[GrupoOut])
def grupos(db: DB, _: Encargado):
    return catalogo.grupos(db)


@router.post("/grupos", response_model=GrupoOut, status_code=CREADO)
def crear_grupo(datos: GrupoIn, db: DB, _: Encargado):
    return catalogo.crear_grupo(db, datos.model_dump())


@router.patch("/grupos/{grupo_id}", response_model=GrupoOut)
def editar_grupo(grupo_id: int, datos: GrupoCambios, db: DB, _: Encargado):
    return catalogo.editar_grupo(db, grupo_id, datos.cambios())


@router.post(
    "/grupos/{grupo_id}/modificadores",
    response_model=ModificadorOut,
    status_code=CREADO,
)
def crear_modificador(grupo_id: int, datos: ModificadorIn, db: DB, _: Encargado):
    return catalogo.crear_modificador(db, grupo_id, datos.model_dump())


@router.patch("/modificadores/{modificador_id}", response_model=ModificadorOut)
def editar_modificador(
    modificador_id: int, datos: ModificadorCambios, db: DB, _: Encargado
):
    return catalogo.editar_modificador(db, modificador_id, datos.cambios())
