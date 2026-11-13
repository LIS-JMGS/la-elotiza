"""Configuración leída de variables de entorno."""

import os
from dataclasses import dataclass
from decimal import Decimal
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///./la_elotiza.db"
    zona_horaria: str = "America/Mexico_City"
    cors_origins: tuple[str, ...] = ("http://localhost:3000",)
    # Encargado inicial: se crea solo si la tabla de usuarios está vacía.
    admin_nombre: str = "Encargado"
    admin_pin: str = "1234"
    sesion_horas: int = 14
    # Tras `max_intentos_pin` fallos seguidos se bloquea `bloqueo_minutos`.
    max_intentos_pin: int = 5
    bloqueo_minutos: int = 5
    # Fondo de caja si al abrir el turno no se indica otro.
    fondo_caja: Decimal = Decimal("500")
    # Texto con banco/CLABE que se agrega al mensaje de WhatsApp.
    datos_transferencia: str = ""

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.zona_horaria)

    @classmethod
    def from_env(cls) -> "Settings":
        d = cls()
        origins = os.getenv("LA_ELOTIZA_CORS_ORIGINS")
        return cls(
            database_url=os.getenv("LA_ELOTIZA_DATABASE_URL", d.database_url),
            zona_horaria=os.getenv("LA_ELOTIZA_ZONA_HORARIA", d.zona_horaria),
            cors_origins=(
                tuple(o.strip() for o in origins.split(",") if o.strip())
                if origins
                else d.cors_origins
            ),
            admin_nombre=os.getenv("LA_ELOTIZA_ADMIN_NOMBRE", d.admin_nombre),
            admin_pin=os.getenv("LA_ELOTIZA_ADMIN_PIN", d.admin_pin),
            sesion_horas=int(os.getenv("LA_ELOTIZA_SESION_HORAS", d.sesion_horas)),
            fondo_caja=Decimal(os.getenv("LA_ELOTIZA_FONDO_CAJA", str(d.fondo_caja))),
            datos_transferencia=os.getenv(
                "LA_ELOTIZA_DATOS_TRANSFERENCIA", d.datos_transferencia
            ),
        )
