"""Ciclo de vida de una orden: captura, comanda, cobro, cocina y entrega.

Estados:
    ABIERTA   → se puede editar, confirmar (comanda), cancelar o cobrar.
    CERRADA   → cobrada; ya no se modifica (RF 16).
    CANCELADA → no se cobró; no cuenta en ventas ni corte (RF 19-20).
"""

import re
import unicodedata
from collections.abc import Iterable
from decimal import Decimal
from enum import StrEnum
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from la_elotiza_api.config import Settings
from la_elotiza_api.errores import Conflicto, DatosInvalidos, NoEncontrado
from la_elotiza_api.models import (
    Comanda,
    EstadoOrden,
    MetodoPago,
    Orden,
    OrdenItem,
    Pago,
    Turno,
    Usuario,
)
from la_elotiza_api.servicios import catalogo
from la_elotiza_api.servicios.turnos import exigir_turno_abierto
from la_elotiza_api.tipos import ahora_utc


class Filtro(StrEnum):
    EN_PREPARACION = "en_preparacion"
    ENTREGADAS = "entregadas"
    CANCELADAS = "canceladas"
    TODAS = "todas"


def _cargar():
    return (
        selectinload(Orden.items),
        selectinload(Orden.comandas),
        selectinload(Orden.pago),
    )


def obtener(db: Session, orden_id: int) -> Orden:
    orden = db.scalar(select(Orden).where(Orden.id == orden_id).options(*_cargar()))
    if orden is None:
        raise NoEncontrado("No existe esa orden")
    return orden


def listar(db: Session, turno: Turno, filtro: Filtro) -> list[Orden]:
    q = select(Orden).where(Orden.turno_id == turno.id).options(*_cargar())
    if filtro is Filtro.EN_PREPARACION:
        # RF 35: confirmadas (con comanda), sin entregar y no canceladas.
        q = q.where(
            Orden.comandas.any(),
            Orden.estado != EstadoOrden.CANCELADA,
            ~Orden.entregada,
        ).order_by(Orden.id)
    elif filtro is Filtro.ENTREGADAS:
        q = q.where(Orden.entregada, Orden.estado != EstadoOrden.CANCELADA).order_by(
            Orden.id.desc()
        )
    elif filtro is Filtro.CANCELADAS:
        q = q.where(Orden.estado == EstadoOrden.CANCELADA).order_by(Orden.id.desc())
    else:
        q = q.order_by(Orden.id.desc())
    return list(db.scalars(q))


def _exigir_editable(orden: Orden) -> None:
    if orden.estado is EstadoOrden.CERRADA:
        raise Conflicto("La orden ya se cobró y no se puede modificar")
    if orden.estado is EstadoOrden.CANCELADA:
        raise Conflicto("La orden está cancelada")


def _marcar_cambio(orden: Orden) -> None:
    # RF 32: si ya había comanda, hay que confirmar de nuevo.
    orden.comanda_al_dia = False


def crear(db: Session, cajero: Usuario, cliente: str = "") -> Orden:
    turno = exigir_turno_abierto(db)
    orden = Orden(turno=turno, cajero=cajero, cliente=cliente.strip())
    db.add(orden)
    db.commit()
    return obtener(db, orden.id)


def cambiar_cliente(db: Session, orden: Orden, cliente: str) -> Orden:
    _exigir_editable(orden)
    cliente = cliente.strip()
    if cliente != orden.cliente:
        orden.cliente = cliente
        _marcar_cambio(orden)
        db.commit()
    return orden


def _aplicar_linea(item: OrdenItem, linea: catalogo.Linea) -> None:
    """Copia al item lo validado y cotizado por el catálogo."""
    item.producto_id = linea.producto.id
    item.nombre = linea.producto.nombre
    item.presentacion_id = linea.presentacion.id if linea.presentacion else None
    item.presentacion = linea.presentacion.nombre if linea.presentacion else ""
    item.modificadores = linea.modificadores_snapshot()
    item.detalle = linea.detalle
    item.precio_unitario = linea.precio_unitario


def agregar_item(
    db: Session,
    orden: Orden,
    producto_id: int,
    cantidad: int,
    nota: str,
    presentacion_id: int | None = None,
    modificadores: Iterable[int] = (),
) -> Orden:
    _exigir_editable(orden)
    # RF 30: armar_linea rechaza si faltan opciones obligatorias.
    linea = catalogo.armar_linea(db, producto_id, presentacion_id, modificadores)
    item = OrdenItem(cantidad=cantidad, nota=nota.strip())
    _aplicar_linea(item, linea)
    orden.items.append(item)
    _marcar_cambio(orden)
    db.commit()
    return orden


def _item(orden: Orden, item_id: int) -> OrdenItem:
    for item in orden.items:
        if item.id == item_id:
            return item
    raise NoEncontrado("Ese producto no está en la orden")


def editar_item(
    db: Session,
    orden: Orden,
    item_id: int,
    cantidad: int | None = None,
    nota: str | None = None,
    personalizacion: tuple[int | None, Iterable[int]] | None = None,
) -> Orden:
    """`personalizacion` = (presentacion_id, modificadores) y reemplaza la
    anterior completa; si es None se conserva."""
    _exigir_editable(orden)
    item = _item(orden, item_id)
    if personalizacion is not None:
        presentacion_id, modificadores = personalizacion
        linea = catalogo.armar_linea(
            db, item.producto_id, presentacion_id, modificadores
        )
        _aplicar_linea(item, linea)
    if cantidad is not None:
        item.cantidad = cantidad
    if nota is not None:
        item.nota = nota.strip()
    item.preparado = False  # cambió: cocina debe volver a revisarlo
    _marcar_cambio(orden)
    db.commit()
    return orden


def quitar_item(db: Session, orden: Orden, item_id: int) -> Orden:
    _exigir_editable(orden)
    orden.items.remove(_item(orden, item_id))
    _marcar_cambio(orden)
    db.commit()
    return orden


def confirmar(db: Session, orden: Orden) -> Comanda:
    """Genera (o actualiza) la comanda para cocina. RF 10, 11, 31, 32."""
    _exigir_editable(orden)
    faltantes = []
    if not orden.items:
        faltantes.append("Agrega al menos un producto")
    if not orden.cliente:
        faltantes.append("Escribe el nombre del cliente")
    if faltantes:
        raise Conflicto("La orden no se puede confirmar", faltantes)
    if orden.comanda_al_dia and orden.comanda:
        return orden.comanda  # sin cambios: no se duplica la comanda

    comanda = Comanda(
        version=(orden.comanda.version + 1) if orden.comanda else 1,
        cliente=orden.cliente,
        # Copia: la comanda no cambia aunque después se edite la orden.
        lineas=[
            {
                "item_id": i.id,
                "cantidad": i.cantidad,
                "nombre": i.nombre,
                "detalle": i.detalle,
                "nota": i.nota,
            }
            for i in orden.items
        ],
    )
    orden.comandas.append(comanda)
    orden.comanda_al_dia = True
    db.commit()
    return comanda


def cancelar(db: Session, orden: Orden) -> Orden:
    if orden.estado is EstadoOrden.CERRADA:
        raise Conflicto("La orden ya se cobró; no se puede cancelar")
    if orden.estado is EstadoOrden.CANCELADA:
        raise Conflicto("La orden ya estaba cancelada")
    orden.estado = EstadoOrden.CANCELADA
    orden.cancelada_en = ahora_utc()
    db.commit()
    return orden


def concepto_transferencia(orden: Orden, settings: Settings) -> str:
    """Concepto único para conciliar la transferencia (RF 34).

    Formato `ELO-DDMM-0001-NOMBRE`: es único por el folio y solo usa
    caracteres ASCII porque algunos bancos rechazan acentos.
    """
    fecha = orden.creada_en.astimezone(settings.tz)
    primero = (orden.cliente.split() or ["CLIENTE"])[0]
    ascii_ = unicodedata.normalize("NFKD", primero).encode("ascii", "ignore").decode()
    nombre = re.sub(r"[^A-Z]", "", ascii_.upper())[:12] or "CLIENTE"
    return f"ELO-{fecha:%d%m}-{orden.id:04d}-{nombre}"


def _exigir_cobrable(orden: Orden) -> None:
    _exigir_editable(orden)
    if not orden.items:
        raise Conflicto("La orden no tiene productos")
    if not orden.comanda_al_dia:
        raise Conflicto("Confirma la orden (o sus cambios) antes de cobrar")


def mensaje_transferencia(
    orden: Orden,
    settings: Settings,
    telefono: str | None = None,
) -> tuple[str, str, str]:
    """Devuelve (concepto, mensaje, url de WhatsApp) para mandar al cliente."""
    _exigir_cobrable(orden)
    concepto = concepto_transferencia(orden, settings)
    lineas = [
        f"¡Hola {orden.cliente}! Tu orden {orden.folio} en La Elotiza "
        f"es de ${orden.total:,.2f}.",
        f"Al transferir, usa este concepto: {concepto}",
    ]
    if settings.datos_transferencia:
        lineas.append(settings.datos_transferencia)
    mensaje = "\n".join(lineas)
    destino = ""
    if telefono:
        digitos = re.sub(r"\D", "", telefono)
        if len(digitos) == 10:  # número mexicano sin lada de país
            digitos = "52" + digitos
        if not 11 <= len(digitos) <= 15:
            raise DatosInvalidos("El teléfono no es válido")
        destino = digitos
    url = f"https://wa.me/{destino}?text={quote(mensaje)}"
    return concepto, mensaje, url


def cobrar(
    db: Session,
    orden: Orden,
    usuario: Usuario,
    settings: Settings,
    metodo: MetodoPago,
    recibido: Decimal | None = None,
    whatsapp_enviado: bool = False,
) -> Pago:
    """Registra el pago y cierra la orden. RF 12-15, 33-34."""
    _exigir_cobrable(orden)
    total = orden.total
    pago = Pago(metodo=metodo, total=total, usuario=usuario)
    if metodo is MetodoPago.EFECTIVO:
        recibido = total if recibido is None else recibido
        if recibido < total:
            raise DatosInvalidos(f"El efectivo recibido no cubre el total (${total})")
        pago.recibido = recibido
        pago.cambio = recibido - total
    else:
        pago.concepto = concepto_transferencia(orden, settings)
        pago.whatsapp_enviado = whatsapp_enviado
    orden.pago = pago
    orden.estado = EstadoOrden.CERRADA
    db.commit()
    return pago


def marcar_preparado(
    db: Session, orden: Orden, preparado: bool, item_id: int | None = None
) -> Orden:
    """Marca uno o todos los productos como preparados (RF 36)."""
    if orden.estado is EstadoOrden.CANCELADA:
        raise Conflicto("La orden está cancelada")
    if orden.comanda is None:
        raise Conflicto("La orden aún no se manda a cocina")
    items = [_item(orden, item_id)] if item_id is not None else orden.items
    for item in items:
        item.preparado = preparado
    db.commit()
    return orden


def marcar_entregada(db: Session, orden: Orden, entregada: bool) -> Orden:
    if orden.estado is not EstadoOrden.CERRADA:
        raise Conflicto("Solo se entregan órdenes cobradas")
    orden.entregada = entregada
    if entregada:
        for item in orden.items:
            item.preparado = True
    db.commit()
    return orden
