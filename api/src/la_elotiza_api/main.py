from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from la_elotiza_api.config import Settings
from la_elotiza_api.db import make_engine, make_sessionmaker
from la_elotiza_api.errores import ErrorDominio
from la_elotiza_api.routers import auth, equipo
from la_elotiza_api.servicios.auth import crear_encargado_inicial


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Crea la aplicación. Las pruebas pasan su propia configuración."""
    settings = settings or Settings.from_env()
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Al arrancar: garantiza que exista alguien que pueda entrar.
        with app.state.sessionmaker() as db:
            crear_encargado_inicial(db, settings)
        yield
        engine.dispose()

    app = FastAPI(title="La Elotiza API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = make_sessionmaker(engine)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ErrorDominio)
    async def _error_dominio(_: Request, exc: ErrorDominio) -> JSONResponse:
        contenido: dict = {"detail": exc.mensaje}
        if exc.detalles:
            contenido["errores"] = exc.detalles
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(contenido, status_code=exc.status_code, headers=headers)

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    def health() -> HealthResponse:
        """Indica que el proceso responde; no comprueba servicios externos."""
        return HealthResponse()

    for r in (auth, equipo):
        app.include_router(r.router)

    return app


app = create_app()
