"""Modelos de entrada y salida de la API (Pydantic)."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from la_elotiza_api.models import Rol

Pin = Annotated[str, StringConstraints(pattern=r"^\d{4}$")]
Nombre = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)
]


class Esquema(BaseModel):
    # from_attributes: se construyen directo desde los modelos de SQLAlchemy.
    # extra="forbid": un campo desconocido es error, no se ignora en silencio.
    model_config = ConfigDict(from_attributes=True, extra="forbid")


# --- Sesión y equipo --------------------------------------------------------


class UsuarioLogin(Esquema):
    """Lo mínimo para la pantalla de inicio: no expone rol ni PIN."""

    id: int
    nombre: str


class UsuarioOut(Esquema):
    id: int
    nombre: str
    rol: Rol


class LoginIn(Esquema):
    usuario_id: int
    pin: Pin


class LoginOut(Esquema):
    token: str
    expira_en: datetime
    usuario: UsuarioOut


class NuevoUsuarioIn(Esquema):
    nombre: Nombre
    pin: Pin
    rol: Rol = Rol.CAJERO
