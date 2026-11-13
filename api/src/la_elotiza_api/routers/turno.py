from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query, status

from la_elotiza_api.config import Settings
from la_elotiza_api.deps import DB, Config, UsuarioActual
from la_elotiza_api.errores import NoEncontrado
from la_elotiza_api.schemas import (
    AbrirTurnoIn,
    CerrarTurnoIn,
    CorteOut,
    TransferenciaCorteOut,
    TurnoOut,
)
from la_elotiza_api.servicios import impresion, turnos

router = APIRouter(prefix="/turnos", tags=["turno y corte"])


def _corte_out(corte: turnos.Corte, settings: Settings) -> CorteOut:
    return CorteOut(
        turno=TurnoOut.model_validate(corte.turno),
        ordenes_cobradas=corte.ordenes_cobradas,
        ordenes_canceladas=corte.ordenes_canceladas,
        ordenes_pendientes=corte.ordenes_pendientes,
        total_ventas=corte.total_ventas,
        total_efectivo=corte.total_efectivo,
        total_transferencia=corte.total_transferencia,
        fondo=corte.fondo,
        efectivo_esperado=corte.efectivo_esperado,
        efectivo_contado=corte.efectivo_contado,
        diferencia=corte.diferencia,
        transferencias=[
            TransferenciaCorteOut.model_validate(t) for t in corte.transferencias
        ],
        texto=impresion.corte(corte, settings.tz),
    )


@router.post("", response_model=TurnoOut, status_code=status.HTTP_201_CREATED)
def abrir(datos: AbrirTurnoIn, db: DB, settings: Config, usuario: UsuarioActual):
    """Abre la jornada con el fondo de caja (RF 37)."""
    fondo = datos.fondo if datos.fondo is not None else settings.fondo_caja
    return turnos.abrir(db, usuario, fondo)


@router.get("/actual", response_model=TurnoOut)
def actual(db: DB, _: UsuarioActual):
    turno = turnos.turno_abierto(db)
    if turno is None:
        raise NoEncontrado("No hay turno abierto")
    return turno


@router.get("/actual/corte", response_model=CorteOut)
def corte_previo(
    db: DB,
    settings: Config,
    _: UsuarioActual,
    efectivo_contado: Annotated[
        Decimal | None, Query(ge=0, max_digits=10, decimal_places=2)
    ] = None,
):
    """RF 22-26: calcula el corte sin cerrar el turno."""
    turno = turnos.exigir_turno_abierto(db)
    return _corte_out(turnos.calcular_corte(db, turno, efectivo_contado), settings)


@router.post("/actual/cierre", response_model=CorteOut)
def cerrar(datos: CerrarTurnoIn, db: DB, settings: Config, usuario: UsuarioActual):
    """RF 24-26, 38: registra el efectivo contado, cierra el turno y devuelve
    el corte listo para imprimir."""
    turno = turnos.exigir_turno_abierto(db)
    corte = turnos.cerrar(db, turno, usuario, datos.efectivo_contado)
    return _corte_out(corte, settings)


@router.get("/{turno_id}/corte", response_model=CorteOut)
def corte(turno_id: int, db: DB, settings: Config, _: UsuarioActual):
    """Corte de un turno ya cerrado, para reimprimir."""
    turno = turnos.obtener(db, turno_id)
    return _corte_out(turnos.calcular_corte(db, turno), settings)
