"""Modelos de base de datos.

Todos heredan de `la_elotiza_api.db.Base`. Alembic importa este módulo para
detectar las tablas, así que cada modelo nuevo debe vivir aquí (o importarse
desde aquí). Las tablas llegan a partir del sprint 2.
"""

from la_elotiza_api.db import Base

__all__ = ["Base"]
