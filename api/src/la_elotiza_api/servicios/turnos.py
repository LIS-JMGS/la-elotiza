"""Turno de caja (jornada): agrupa las órdenes que entran en un corte."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from la_elotiza_api.errores import Conflicto, NoEncontrado
from la_elotiza_api.models import EstadoOrden, MetodoPago, Orden, Turno, Usuario
from la_elotiza_api.tipos import ahora_utc

CERO = Decimal("0.00")


def turno_abierto(db: Session) -> Turno | None:
    return db.scalar(select(Turno).where(Turno.cerrado_en.is_(None)))


def exigir_turno_abierto(db: Session) -> Turno:
    turno = turno_abierto(db)
    if turno is None:
        raise Conflicto("No hay turno abierto. Abre el turno con el fondo de caja.")
    return turno


def abrir(db: Session, usuario: Usuario, fondo: Decimal) -> Turno:
    if turno_abierto(db) is not None:
        raise Conflicto("Ya hay un turno abierto")
    turno = Turno(fondo=fondo, abierto_por=usuario)
    db.add(turno)
    try:
        db.commit()
    except IntegrityError as e:
        # Otro cajero lo abrió al mismo tiempo: lo frena el índice único.
        db.rollback()
        raise Conflicto("Ya hay un turno abierto") from e
    return turno


def obtener(db: Session, turno_id: int) -> Turno:
    turno = db.get(Turno, turno_id)
    if turno is None:
        raise NoEncontrado("No existe ese turno")
    return turno


@dataclass(frozen=True)
class Transferencia:
    folio: str
    concepto: str
    cliente: str
    monto: Decimal
    whatsapp_enviado: bool


@dataclass(frozen=True)
class Corte:
    turno: Turno
    ordenes_cobradas: int
    ordenes_canceladas: int
    ordenes_pendientes: int
    total_ventas: Decimal
    total_efectivo: Decimal
    total_transferencia: Decimal
    fondo: Decimal
    efectivo_esperado: Decimal
    efectivo_contado: Decimal | None
    diferencia: Decimal | None
    transferencias: list[Transferencia]
    calculado_en: datetime


def calcular_corte(
    db: Session, turno: Turno, efectivo_contado: Decimal | None = None
) -> Corte:
    """Totales del turno. Las órdenes canceladas no cuentan (RF 20)."""
    ordenes = db.scalars(
        select(Orden)
        .where(Orden.turno_id == turno.id)
        .options(selectinload(Orden.pago))
        .order_by(Orden.id)
    ).all()

    cobradas = [o for o in ordenes if o.estado is EstadoOrden.CERRADA and o.pago]
    efectivo = sum(
        (o.pago.total for o in cobradas if o.pago.metodo is MetodoPago.EFECTIVO), CERO
    )
    transfer = [o for o in cobradas if o.pago.metodo is MetodoPago.TRANSFERENCIA]
    total_transfer = sum((o.pago.total for o in transfer), CERO)

    if efectivo_contado is None:
        efectivo_contado = turno.efectivo_contado
    esperado = turno.fondo + efectivo  # RF 37: incluye el fondo de caja
    return Corte(
        turno=turno,
        ordenes_cobradas=len(cobradas),
        ordenes_canceladas=sum(o.estado is EstadoOrden.CANCELADA for o in ordenes),
        ordenes_pendientes=sum(o.estado is EstadoOrden.ABIERTA for o in ordenes),
        total_ventas=efectivo + total_transfer,
        total_efectivo=efectivo,
        total_transferencia=total_transfer,
        fondo=turno.fondo,
        efectivo_esperado=esperado,
        efectivo_contado=efectivo_contado,
        diferencia=None if efectivo_contado is None else efectivo_contado - esperado,
        transferencias=[
            Transferencia(
                folio=o.folio,
                concepto=o.pago.concepto or "",
                cliente=o.cliente,
                monto=o.pago.total,
                whatsapp_enviado=o.pago.whatsapp_enviado,
            )
            for o in transfer
        ],
        calculado_en=turno.cerrado_en or ahora_utc(),
    )


def cerrar(
    db: Session, turno: Turno, usuario: Usuario, efectivo_contado: Decimal
) -> Corte:
    if turno.cerrado_en is not None:
        raise Conflicto("El turno ya está cerrado")
    pendientes = db.scalars(
        select(Orden).where(
            Orden.turno_id == turno.id, Orden.estado == EstadoOrden.ABIERTA
        )
    ).all()
    if pendientes:
        raise Conflicto(
            "Hay órdenes sin cobrar. Cóbralas o cancélalas antes del corte.",
            [o.folio for o in pendientes],
        )
    turno.efectivo_contado = efectivo_contado
    turno.cerrado_en = ahora_utc()
    turno.cerrado_por = usuario
    db.commit()
    return calcular_corte(db, turno)
