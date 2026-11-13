from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from la_elotiza_api.deps import DB, UsuarioActual
from la_elotiza_api.errores import Conflicto
from la_elotiza_api.models import Comanda, Orden
from la_elotiza_api.schemas import (
    ClienteIn,
    ComandaOut,
    ItemCambiosIn,
    ItemIn,
    ItemOut,
    LineaComandaOut,
    OrdenIn,
    OrdenOut,
)
from la_elotiza_api.servicios import ordenes, turnos

router = APIRouter(prefix="/ordenes", tags=["órdenes"])


def _comanda_out(orden: Orden, comanda: Comanda) -> ComandaOut:
    return ComandaOut(
        folio=orden.folio,
        version=comanda.version,
        cliente=comanda.cliente,
        generada_en=comanda.generada_en,
        lineas=[LineaComandaOut(**linea) for linea in comanda.lineas],
    )


def _orden_out(orden: Orden) -> OrdenOut:
    return OrdenOut(
        id=orden.id,
        folio=orden.folio,
        cliente=orden.cliente,
        estado=orden.estado,
        comanda_al_dia=orden.comanda_al_dia,
        confirmada=orden.comanda is not None,
        creada_en=orden.creada_en,
        cancelada_en=orden.cancelada_en,
        total=orden.total,
        items=[ItemOut.model_validate(i) for i in orden.items],
        comanda=_comanda_out(orden, orden.comanda) if orden.comanda else None,
    )


def _orden(orden_id: int, db: DB, _: UsuarioActual) -> Orden:
    """Carga la orden de la ruta y exige sesión; 404 si no existe."""
    return ordenes.obtener(db, orden_id)


OrdenRuta = Annotated[Orden, Depends(_orden)]


@router.get("", response_model=list[OrdenOut])
def listar(
    db: DB,
    _: UsuarioActual,
    filtro: Annotated[ordenes.Filtro, Query()] = ordenes.Filtro.EN_PREPARACION,
):
    """Órdenes del turno abierto. Por defecto, las confirmadas (RF 35)."""
    turno = turnos.exigir_turno_abierto(db)
    return [_orden_out(o) for o in ordenes.listar(db, turno, filtro)]


@router.post("", response_model=OrdenOut, status_code=status.HTTP_201_CREATED)
def crear(datos: OrdenIn, db: DB, usuario: UsuarioActual):
    """RF 1-2: nueva orden con el nombre del cliente (puede ir después)."""
    return _orden_out(ordenes.crear(db, usuario, datos.cliente))


@router.get("/{orden_id}", response_model=OrdenOut)
def detalle(orden: OrdenRuta):
    return _orden_out(orden)


@router.patch("/{orden_id}", response_model=OrdenOut)
def cambiar_cliente(datos: ClienteIn, orden: OrdenRuta, db: DB):
    return _orden_out(ordenes.cambiar_cliente(db, orden, datos.cliente))


@router.post(
    "/{orden_id}/items", response_model=OrdenOut, status_code=status.HTTP_201_CREATED
)
def agregar_item(datos: ItemIn, orden: OrdenRuta, db: DB):
    """RF 3-7, 30: agrega un producto validando opciones obligatorias."""
    orden = ordenes.agregar_item(
        db,
        orden,
        datos.producto_id,
        datos.cantidad,
        datos.nota,
        datos.presentacion_id,
        datos.modificadores,
    )
    return _orden_out(orden)


@router.patch("/{orden_id}/items/{item_id}", response_model=OrdenOut)
def editar_item(item_id: int, datos: ItemCambiosIn, orden: OrdenRuta, db: DB):
    """RF 8: cambia cantidad, personalización o nota mientras no se cobre."""
    p = datos.personalizacion
    orden = ordenes.editar_item(
        db,
        orden,
        item_id,
        cantidad=datos.cantidad,
        nota=datos.nota,
        personalizacion=(p.presentacion_id, p.modificadores) if p else None,
    )
    return _orden_out(orden)


@router.delete("/{orden_id}/items/{item_id}", response_model=OrdenOut)
def quitar_item(item_id: int, orden: OrdenRuta, db: DB):
    """RF 9: quita un producto mientras no se cobre."""
    return _orden_out(ordenes.quitar_item(db, orden, item_id))


@router.post("/{orden_id}/confirmar", response_model=ComandaOut)
def confirmar(orden: OrdenRuta, db: DB):
    """RF 10-11, 31-32: genera la comanda (o una nueva versión si hubo cambios)."""
    return _comanda_out(orden, ordenes.confirmar(db, orden))


@router.get("/{orden_id}/comanda", response_model=ComandaOut)
def comanda(orden: OrdenRuta):
    if orden.comanda is None:
        raise Conflicto("La orden aún no se confirma")
    return _comanda_out(orden, orden.comanda)


@router.post("/{orden_id}/cancelar", response_model=OrdenOut)
def cancelar(orden: OrdenRuta, db: DB):
    """RF 19: cancela una orden que no se ha cobrado."""
    return _orden_out(ordenes.cancelar(db, orden))
