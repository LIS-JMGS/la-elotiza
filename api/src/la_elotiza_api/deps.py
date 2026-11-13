"""Dependencias compartidas por los routers."""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from la_elotiza_api.config import Settings
from la_elotiza_api.db import get_db
from la_elotiza_api.errores import NoAutenticado
from la_elotiza_api.models import Usuario
from la_elotiza_api.servicios import auth, equipo

_bearer = HTTPBearer(auto_error=False)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_token(
    cred: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    if cred is None:
        raise NoAutenticado("Inicia sesión para continuar")
    return cred.credentials


DB = Annotated[Session, Depends(get_db)]
Config = Annotated[Settings, Depends(get_settings)]
Token = Annotated[str, Depends(get_token)]


def get_usuario(db: DB, token: Token) -> Usuario:
    return auth.usuario_por_token(db, token)


UsuarioActual = Annotated[Usuario, Depends(get_usuario)]


def get_encargado(usuario: UsuarioActual) -> Usuario:
    equipo.exigir_encargado(usuario)
    return usuario


Encargado = Annotated[Usuario, Depends(get_encargado)]
