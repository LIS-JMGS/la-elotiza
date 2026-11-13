"""Turno de caja (jornada): agrupa las órdenes que entran en un corte."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from la_elotiza_api.errores import Conflicto
from la_elotiza_api.models import Turno, Usuario


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
