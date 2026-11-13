"""Errores de dominio.

Los servicios los lanzan sin saber nada de HTTP y `main` los traduce a una
respuesta JSON `{"detail": ..., "errores": [...]}` con el código indicado.
"""


class ErrorDominio(Exception):
    status_code = 400

    def __init__(self, mensaje: str, detalles: list[str] | None = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalles = detalles or []


class NoAutenticado(ErrorDominio):
    status_code = 401


class SinPermiso(ErrorDominio):
    status_code = 403


class NoEncontrado(ErrorDominio):
    status_code = 404


class Conflicto(ErrorDominio):
    """La operación no es válida en el estado actual (orden cerrada, etc.)."""

    status_code = 409


class DatosInvalidos(ErrorDominio):
    status_code = 422


class Bloqueado(ErrorDominio):
    status_code = 429
