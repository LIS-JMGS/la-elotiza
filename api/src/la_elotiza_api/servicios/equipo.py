"""Administración del equipo (solo encargados)."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from la_elotiza_api.errores import Conflicto, NoEncontrado, SinPermiso
from la_elotiza_api.models import Rol, Usuario
from la_elotiza_api.seguridad import hash_pin
from la_elotiza_api.servicios.auth import revocar_sesiones, usuarios_activos


def exigir_encargado(usuario: Usuario) -> None:
    if usuario.rol is not Rol.ENCARGADO:
        raise SinPermiso("Solo un encargado puede administrar al equipo")


def listar(db: Session) -> list[Usuario]:
    return usuarios_activos(db)


def agregar(db: Session, actor: Usuario, nombre: str, pin: str, rol: Rol) -> Usuario:
    exigir_encargado(actor)
    nombre = " ".join(nombre.split())
    repetido = db.scalar(
        select(Usuario.id).where(
            Usuario.activo, func.lower(Usuario.nombre) == nombre.lower()
        )
    )
    if repetido:
        raise Conflicto("Ya existe alguien con ese nombre")
    usuario = Usuario(nombre=nombre, pin_hash=hash_pin(pin), rol=rol)
    db.add(usuario)
    db.commit()
    return usuario


def quitar_acceso(db: Session, actor: Usuario, usuario_id: int) -> None:
    exigir_encargado(actor)
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.activo:
        raise NoEncontrado("No existe esa persona en el equipo")
    if usuario.id == actor.id:
        raise Conflicto("No puedes quitarte el acceso a ti mismo")
    if usuario.rol is Rol.ENCARGADO:
        encargados = db.scalar(
            select(func.count())
            .select_from(Usuario)
            .where(Usuario.activo, Usuario.rol == Rol.ENCARGADO)
        )
        if encargados <= 1:
            raise Conflicto("Debe quedar al menos un encargado")
    # Baja lógica: se conserva para el historial de ventas.
    usuario.activo = False
    revocar_sesiones(db, usuario.id)
    db.commit()
