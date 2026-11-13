"""Menú para tomar órdenes (cualquier usuario con sesión)."""

from fastapi import APIRouter

from la_elotiza_api.deps import DB, UsuarioActual
from la_elotiza_api.models import Producto
from la_elotiza_api.schemas import (
    CotizacionIn,
    CotizacionOut,
    DisponibleIn,
    MenuCategoriaOut,
    MenuGrupoOut,
    MenuOpcionOut,
    MenuPresentacionOut,
    MenuProductoOut,
    ModificadorOut,
    ProductoOut,
)
from la_elotiza_api.servicios import catalogo

router = APIRouter(prefix="/menu", tags=["menú"])


def _producto_pos(p: Producto) -> MenuProductoOut:
    return MenuProductoOut(
        id=p.id,
        nombre=p.nombre,
        descripcion=p.descripcion,
        precio=p.precio,
        precio_desde=catalogo.precio_desde(p),
        disponible=p.disponible,
        presentaciones=[
            MenuPresentacionOut.model_validate(x) for x in p.presentaciones if x.activa
        ],
        grupos=[
            MenuGrupoOut(
                id=liga.id,
                grupo_id=liga.grupo_id,
                titulo=liga.titulo_visible,
                etiqueta=liga.grupo.etiqueta,
                minimo=liga.minimo,
                maximo=liga.maximo,
                incluidas=liga.incluidas,
                presentacion_id=liga.presentacion_id,
                opciones=[MenuOpcionOut.model_validate(m) for m in liga.opciones()],
            )
            for liga in p.grupos
            if liga.grupo.activo
        ],
    )


@router.get("", response_model=list[MenuCategoriaOut])
def menu(db: DB, _: UsuarioActual):
    """Categorías y productos activos con sus presentaciones y grupos de
    opciones. Los agotados vienen con `disponible=false`."""
    return [
        MenuCategoriaOut(
            id=c.id,
            nombre=c.nombre,
            productos=[_producto_pos(p) for p in c.productos if p.activo],
        )
        for c in catalogo.categorias(db, solo_activos=True)
    ]


@router.post("/cotizar", response_model=CotizacionOut)
def cotizar(datos: CotizacionIn, db: DB, _: UsuarioActual):
    """Precio de un producto personalizado antes de agregarlo a la orden.

    Sirve para mostrar el precio en vivo sin duplicar reglas en el frontend.
    """
    linea = catalogo.armar_linea(
        db, datos.producto_id, datos.presentacion_id, datos.modificadores
    )
    return CotizacionOut(
        precio_unitario=linea.precio_unitario,
        importe=linea.precio_unitario * datos.cantidad,
        detalle=linea.detalle,
    )


@router.put("/productos/{producto_id}/disponible", response_model=ProductoOut)
def disponibilidad_producto(
    producto_id: int, datos: DisponibleIn, db: DB, _: UsuarioActual
):
    """Marca un producto como agotado o disponible."""
    return catalogo.cambiar_disponible_producto(db, producto_id, datos.disponible)


@router.put("/modificadores/{modificador_id}/disponible", response_model=ModificadorOut)
def disponibilidad_modificador(
    modificador_id: int, datos: DisponibleIn, db: DB, _: UsuarioActual
):
    """Marca una opción (p. ej. una sabrita) como agotada o disponible."""
    return catalogo.cambiar_disponible_modificador(db, modificador_id, datos.disponible)
