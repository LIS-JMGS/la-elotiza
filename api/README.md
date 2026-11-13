# API de La Elotiza

Backend con FastAPI. Requiere Python 3.12 o superior y uv.

Desde el raíz del repositorio:

```bash
pnpm run install:api
pnpm run dev:api        # aplica migraciones y levanta con recarga
```

- API: http://127.0.0.1:8000
- Documentación interactiva: http://127.0.0.1:8000/docs
- Salud del proceso: `GET /health`, devuelve `{"status":"ok"}`.

Validar lint, formato y pruebas:

```bash
pnpm run check:api
```

También puedes trabajar sin pnpm desde `api/`:

```bash
uv sync --locked
uv run app
# Para desarrollo, con recarga automática:
uv run app --reload
uv run --locked pytest
```

Desde el raíz también puedes ejecutar `uv run --directory api app`.
El comando acepta `--host` y `--port` para configurar el servidor.

La API es un proyecto empaquetado con `uv_build`, con código en
`src/la_elotiza_api/`. El comando `app` se registra en `[project.scripts]`
de `pyproject.toml` y uv instala el paquete en el entorno automáticamente.

`uv` crea el entorno aislado en `api/.venv/`. Guardar `uv.lock` en Git
para reproducir las dependencias. Agregar dependencias con `uv add` desde
esta carpeta (o `uv add --dev` para herramientas de desarrollo).

El endpoint de salud solo verifica que la aplicación responde.

## Base de datos y configuración

SQLAlchemy 2 con migraciones de Alembic. Por defecto usa SQLite en
`api/la_elotiza.db` (ignorada por Git). Desde `api/`:

```bash
uv run alembic upgrade head                              # aplicar migraciones
uv run alembic revision --autogenerate -m "descripción"  # al cambiar modelos
uv run alembic check                                     # modelos == migraciones
```

| Variable | Por defecto | Uso |
| --- | --- | --- |
| `LA_ELOTIZA_DATABASE_URL` | `sqlite:///./la_elotiza.db` | Base de datos (SQLAlchemy) |
| `LA_ELOTIZA_ZONA_HORARIA` | `America/Mexico_City` | Fechas de ticket, comanda y corte |
| `LA_ELOTIZA_CORS_ORIGINS` | `http://localhost:3000` | Orígenes del frontend, separados por coma |

Los importes se guardan como centavos enteros (`tipos.Dinero`) y las fechas
en UTC (`tipos.FechaUTC`). Los servicios lanzan errores de `errores.py` y
`main.py` los convierte en respuestas `{"detail", "errores"}`.

El avance por sprints está en [SPRINTS.md](SPRINTS.md).

Esta carpeta pertenece al repositorio Git raíz; no ejecutar `git init` aquí.
