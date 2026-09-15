# API de La Elotiza

Backend con FastAPI. Requiere Python 3.12 o superior y uv.

Desde el raíz del repositorio:

```bash
pnpm run install:api
pnpm run dev:api
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

El endpoint de salud solo verifica que la aplicación responde. Todavía no
hay base de datos, autenticación ni integración con el frontend.

Esta carpeta pertenece al repositorio Git raíz; no ejecutar `git init` aquí.
