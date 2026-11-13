"""Configuración leída de variables de entorno."""

import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///./la_elotiza.db"
    zona_horaria: str = "America/Mexico_City"
    cors_origins: tuple[str, ...] = ("http://localhost:3000",)

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
        )
