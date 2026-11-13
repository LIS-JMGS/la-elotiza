from fastapi import APIRouter, status

from la_elotiza_api.deps import DB, Config, UsuarioActual
from la_elotiza_api.errores import NoEncontrado
from la_elotiza_api.schemas import AbrirTurnoIn, TurnoOut
from la_elotiza_api.servicios import turnos

router = APIRouter(prefix="/turnos", tags=["turno"])


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
