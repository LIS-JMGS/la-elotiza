from fastapi import APIRouter, status

from la_elotiza_api.deps import DB, Config, Token, UsuarioActual
from la_elotiza_api.schemas import LoginIn, LoginOut, UsuarioLogin, UsuarioOut
from la_elotiza_api.servicios import auth

router = APIRouter(prefix="/auth", tags=["sesión"])


@router.get("/usuarios", response_model=list[UsuarioLogin])
def usuarios_para_login(db: DB):
    """Nombres para la pantalla de inicio (RF 27). No requiere sesión."""
    return auth.usuarios_activos(db)


@router.post("/login", response_model=LoginOut)
def login(datos: LoginIn, db: DB, settings: Config):
    token, sesion = auth.iniciar_sesion(db, settings, datos.usuario_id, datos.pin)
    return LoginOut(token=token, expira_en=sesion.expira_en, usuario=sesion.usuario)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(db: DB, token: Token) -> None:
    auth.cerrar_sesion(db, token)


@router.get("/yo", response_model=UsuarioOut)
def yo(usuario: UsuarioActual):
    return usuario
