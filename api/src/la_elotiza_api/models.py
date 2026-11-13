"""Modelos de base de datos.

Todos heredan de `la_elotiza_api.db.Base`. Alembic importa este módulo para
detectar las tablas, así que cada modelo nuevo debe vivir aquí (o importarse
desde aquí).
"""

import enum
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from la_elotiza_api.db import Base
from la_elotiza_api.tipos import FechaUTC, ahora_utc


def _enum(cls: type[enum.Enum], name: str) -> Enum:
    """Enum guardado como texto con los valores (no los nombres) del Enum."""
    return Enum(
        cls,
        name=name,
        native_enum=False,
        validate_strings=True,
        values_callable=lambda e: [m.value for m in e],
    )


class Rol(enum.StrEnum):
    ENCARGADO = "encargado"
    CAJERO = "cajero"


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60))
    pin_hash: Mapped[str] = mapped_column(String(200))
    rol: Mapped[Rol] = mapped_column(_enum(Rol, "rol"))
    # Baja lógica: se conserva para el historial de ventas.
    activo: Mapped[bool] = mapped_column(default=True)
    intentos_fallidos: Mapped[int] = mapped_column(default=0)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(FechaUTC())
    creado_en: Mapped[datetime] = mapped_column(FechaUTC(), default=ahora_utc)


class SesionToken(Base):
    __tablename__ = "sesiones"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    creada_en: Mapped[datetime] = mapped_column(FechaUTC(), default=ahora_utc)
    expira_en: Mapped[datetime] = mapped_column(FechaUTC())
    revocada: Mapped[bool] = mapped_column(default=False)

    usuario: Mapped[Usuario] = relationship()
