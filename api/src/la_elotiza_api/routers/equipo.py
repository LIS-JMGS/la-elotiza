from fastapi import APIRouter, status

from la_elotiza_api.deps import DB, Encargado
from la_elotiza_api.schemas import NuevoUsuarioIn, UsuarioOut
from la_elotiza_api.servicios import equipo

router = APIRouter(prefix="/equipo", tags=["equipo"])


@router.get("", response_model=list[UsuarioOut])
def listar(db: DB, _: Encargado):
    return equipo.listar(db)


@router.post("", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def agregar(datos: NuevoUsuarioIn, db: DB, actor: Encargado):
    """RF 28: el encargado agrega personas con nombre, PIN y rol."""
    return equipo.agregar(db, actor, datos.nombre, datos.pin, datos.rol)


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def quitar(usuario_id: int, db: DB, actor: Encargado) -> None:
    """RF 28: quita el acceso y cierra sus sesiones abiertas."""
    equipo.quitar_acceso(db, actor, usuario_id)
