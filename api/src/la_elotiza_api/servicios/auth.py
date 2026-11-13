"""Inicio de sesión con nombre + PIN y manejo de tokens."""

import logging
from datetime import timedelta

from sqlalchemy import func, inspect, select, update
from sqlalchemy.orm import Session

from la_elotiza_api.config import Settings
from la_elotiza_api.errores import Bloqueado, NoAutenticado
from la_elotiza_api.models import Rol, SesionToken, Usuario
from la_elotiza_api.seguridad import hash_pin, hash_token, nuevo_token, verificar_pin
from la_elotiza_api.tipos import ahora_utc

log = logging.getLogger(__name__)


def usuarios_activos(db: Session) -> list[Usuario]:
    return list(
        db.scalars(select(Usuario).where(Usuario.activo).order_by(Usuario.nombre))
    )


def iniciar_sesion(
    db: Session, settings: Settings, usuario_id: int, pin: str
) -> tuple[str, SesionToken]:
    usuario = db.get(Usuario, usuario_id)
    # Mismo mensaje si no existe o si el PIN es incorrecto.
    if usuario is None or not usuario.activo:
        raise NoAutenticado("Usuario o PIN incorrecto")

    ahora = ahora_utc()
    if usuario.bloqueado_hasta and usuario.bloqueado_hasta > ahora:
        raise Bloqueado("Demasiados intentos. Espera unos minutos e intenta de nuevo.")

    if not verificar_pin(pin, usuario.pin_hash):
        usuario.intentos_fallidos += 1
        if usuario.intentos_fallidos >= settings.max_intentos_pin:
            usuario.intentos_fallidos = 0
            usuario.bloqueado_hasta = ahora + timedelta(
                minutes=settings.bloqueo_minutos
            )
        db.commit()
        raise NoAutenticado("Usuario o PIN incorrecto")

    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    token = nuevo_token()
    sesion = SesionToken(
        token_hash=hash_token(token),
        usuario=usuario,
        creada_en=ahora,
        expira_en=ahora + timedelta(hours=settings.sesion_horas),
    )
    db.add(sesion)
    db.commit()
    return token, sesion


def usuario_por_token(db: Session, token: str) -> Usuario:
    sesion = db.scalar(
        select(SesionToken).where(SesionToken.token_hash == hash_token(token))
    )
    if (
        sesion is None
        or sesion.revocada
        or sesion.expira_en <= ahora_utc()
        or not sesion.usuario.activo
    ):
        raise NoAutenticado("Sesión no válida o expirada")
    return sesion.usuario


def cerrar_sesion(db: Session, token: str) -> None:
    db.execute(
        update(SesionToken)
        .where(SesionToken.token_hash == hash_token(token))
        .values(revocada=True)
    )
    db.commit()


def revocar_sesiones(db: Session, usuario_id: int) -> None:
    db.execute(
        update(SesionToken)
        .where(SesionToken.usuario_id == usuario_id, ~SesionToken.revocada)
        .values(revocada=True)
    )


def crear_encargado_inicial(db: Session, settings: Settings) -> None:
    """Crea el primer encargado si no hay nadie registrado."""
    if not inspect(db.get_bind()).has_table(Usuario.__tablename__):
        log.warning("No existen las tablas; ejecuta `alembic upgrade head`.")
        return
    if db.scalar(select(func.count()).select_from(Usuario)):
        return
    db.add(
        Usuario(
            nombre=settings.admin_nombre,
            pin_hash=hash_pin(settings.admin_pin),
            rol=Rol.ENCARGADO,
        )
    )
    db.commit()
    log.warning(
        "Se creó el encargado inicial '%s' con el PIN de LA_ELOTIZA_ADMIN_PIN.",
        settings.admin_nombre,
    )
