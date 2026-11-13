from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from la_elotiza_api.config import Settings
from la_elotiza_api.deps import DB, Config, UsuarioActual
from la_elotiza_api.errores import Conflicto
from la_elotiza_api.models import Comanda, Orden
from la_elotiza_api.schemas import (
    ClienteIn,
    CobroIn,
    ComandaOut,
    EntregaIn,
    ItemCambiosIn,
    ItemIn,
    ItemOut,
    LineaComandaOut,
    OrdenIn,
    OrdenOut,
    PagoOut,
    PreparadoIn,
    TicketOut,
    TransferenciaOut,
)
from la_elotiza_api.servicios import impresion, ordenes, turnos

router = APIRouter(prefix="/ordenes", tags=["órdenes"])


def _comanda_out(orden: Orden, comanda: Comanda, settings: Settings) -> ComandaOut:
    preparados = {i.id: i.preparado for i in orden.items}
    return ComandaOut(
        folio=orden.folio,
        version=comanda.version,
        cliente=comanda.cliente,
        generada_en=comanda.generada_en,
        lineas=[
            LineaComandaOut(**linea, preparado=preparados.get(linea["item_id"], False))
            for linea in comanda.lineas
        ],
        texto=impresion.comanda(orden, comanda, settings.tz),
    )


def _orden_out(orden: Orden, settings: Settings) -> OrdenOut:
    return OrdenOut(
        id=orden.id,
        folio=orden.folio,
        cliente=orden.cliente,
        estado=orden.estado,
        comanda_al_dia=orden.comanda_al_dia,
        confirmada=orden.comanda is not None,
        entregada=orden.entregada,
        creada_en=orden.creada_en,
        cancelada_en=orden.cancelada_en,
        total=orden.total,
        items=[ItemOut.model_validate(i) for i in orden.items],
        comanda=_comanda_out(orden, orden.comanda, settings) if orden.comanda else None,
        pago=PagoOut.model_validate(orden.pago) if orden.pago else None,
    )


def _orden(orden_id: int, db: DB, _: UsuarioActual) -> Orden:
    """Carga la orden de la ruta y exige sesión; 404 si no existe."""
    return ordenes.obtener(db, orden_id)


OrdenRuta = Annotated[Orden, Depends(_orden)]


@router.get("", response_model=list[OrdenOut])
def listar(
    db: DB,
    settings: Config,
    _: UsuarioActual,
    filtro: Annotated[ordenes.Filtro, Query()] = ordenes.Filtro.EN_PREPARACION,
):
    """Órdenes del turno abierto. Por defecto, las que están en preparación."""
    turno = turnos.exigir_turno_abierto(db)
    return [_orden_out(o, settings) for o in ordenes.listar(db, turno, filtro)]


@router.post("", response_model=OrdenOut, status_code=status.HTTP_201_CREATED)
def crear(datos: OrdenIn, db: DB, settings: Config, usuario: UsuarioActual):
    """RF 1-2: nueva orden con el nombre del cliente (puede ir después)."""
    return _orden_out(ordenes.crear(db, usuario, datos.cliente), settings)


@router.get("/{orden_id}", response_model=OrdenOut)
def detalle(orden: OrdenRuta, settings: Config):
    return _orden_out(orden, settings)


@router.patch("/{orden_id}", response_model=OrdenOut)
def cambiar_cliente(datos: ClienteIn, orden: OrdenRuta, db: DB, settings: Config):
    return _orden_out(ordenes.cambiar_cliente(db, orden, datos.cliente), settings)


@router.post(
    "/{orden_id}/items", response_model=OrdenOut, status_code=status.HTTP_201_CREATED
)
def agregar_item(datos: ItemIn, orden: OrdenRuta, db: DB, settings: Config):
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
    return _orden_out(orden, settings)


@router.patch("/{orden_id}/items/{item_id}", response_model=OrdenOut)
def editar_item(
    item_id: int, datos: ItemCambiosIn, orden: OrdenRuta, db: DB, settings: Config
):
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
    return _orden_out(orden, settings)


@router.delete("/{orden_id}/items/{item_id}", response_model=OrdenOut)
def quitar_item(item_id: int, orden: OrdenRuta, db: DB, settings: Config):
    """RF 9: quita un producto mientras no se cobre."""
    return _orden_out(ordenes.quitar_item(db, orden, item_id), settings)


@router.post("/{orden_id}/confirmar", response_model=ComandaOut)
def confirmar(orden: OrdenRuta, db: DB, settings: Config):
    """RF 10-11, 31-32: genera la comanda (o una nueva versión si hubo cambios)."""
    comanda = ordenes.confirmar(db, orden)
    return _comanda_out(orden, comanda, settings)


@router.get("/{orden_id}/comanda", response_model=ComandaOut)
def comanda(orden: OrdenRuta, settings: Config):
    if orden.comanda is None:
        raise Conflicto("La orden aún no se confirma")
    return _comanda_out(orden, orden.comanda, settings)


@router.post("/{orden_id}/cancelar", response_model=OrdenOut)
def cancelar(orden: OrdenRuta, db: DB, settings: Config):
    """RF 19: cancela una orden que no se ha cobrado."""
    return _orden_out(ordenes.cancelar(db, orden), settings)


@router.get("/{orden_id}/transferencia", response_model=TransferenciaOut)
def transferencia(
    orden: OrdenRuta,
    settings: Config,
    telefono: Annotated[str | None, Query(max_length=20)] = None,
):
    """RF 34: concepto único y liga de WhatsApp para mandárselo al cliente."""
    concepto, mensaje, url = ordenes.mensaje_transferencia(orden, settings, telefono)
    return TransferenciaOut(
        folio=orden.folio,
        total=orden.total,
        concepto=concepto,
        mensaje=mensaje,
        whatsapp_url=url,
    )


@router.post("/{orden_id}/cobro", response_model=TicketOut)
def cobrar(
    datos: CobroIn, orden: OrdenRuta, db: DB, settings: Config, usuario: UsuarioActual
):
    """RF 12-17, 33: registra el pago, cierra la orden y devuelve el ticket."""
    ordenes.cobrar(
        db,
        orden,
        usuario,
        settings,
        datos.metodo,
        datos.recibido,
        datos.whatsapp_enviado,
    )
    return _ticket_out(orden, settings)


def _ticket_out(orden: Orden, settings: Settings) -> TicketOut:
    assert orden.pago is not None
    return TicketOut(
        folio=orden.folio,
        cliente=orden.cliente,
        items=[ItemOut.model_validate(i) for i in orden.items],
        total=orden.pago.total,
        pago=PagoOut.model_validate(orden.pago),
        texto=impresion.ticket(orden, settings.tz),
    )


@router.get("/{orden_id}/ticket", response_model=TicketOut)
def ticket(orden: OrdenRuta, settings: Config):
    """RF 18: ticket para (re)imprimir."""
    if orden.pago is None:
        raise Conflicto("La orden aún no se cobra")
    return _ticket_out(orden, settings)


@router.put("/{orden_id}/preparado", response_model=OrdenOut)
def marcar_todo(datos: PreparadoIn, orden: OrdenRuta, db: DB, settings: Config):
    """RF 36: marca (o desmarca) todos los productos como preparados."""
    return _orden_out(ordenes.marcar_preparado(db, orden, datos.preparado), settings)


@router.put("/{orden_id}/items/{item_id}/preparado", response_model=OrdenOut)
def marcar_item(
    item_id: int, datos: PreparadoIn, orden: OrdenRuta, db: DB, settings: Config
):
    """RF 36: marca (o desmarca) un producto como preparado."""
    orden = ordenes.marcar_preparado(db, orden, datos.preparado, item_id)
    return _orden_out(orden, settings)


@router.put("/{orden_id}/entrega", response_model=OrdenOut)
def entregar(datos: EntregaIn, orden: OrdenRuta, db: DB, settings: Config):
    """RF 36: marca la orden como entregada (o la reabre)."""
    return _orden_out(ordenes.marcar_entregada(db, orden, datos.entregada), settings)
