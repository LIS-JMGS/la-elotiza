# API de La Elotiza

Backend con FastAPI. Requiere Python 3.12 o superior y uv.

Desde el raíz del repositorio:

```bash
pnpm run install:api
pnpm run dev:api        # migraciones + menú inicial + servidor con recarga
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
| `LA_ELOTIZA_ADMIN_NOMBRE` / `LA_ELOTIZA_ADMIN_PIN` | `Encargado` / `1234` | Encargado inicial |
| `LA_ELOTIZA_SESION_HORAS` | `14` | Duración del token de sesión |
| `LA_ELOTIZA_FONDO_CAJA` | `500` | Fondo si al abrir turno no se indica |

Los importes se guardan como centavos enteros (`tipos.Dinero`) y las fechas
en UTC (`tipos.FechaUTC`). Los servicios lanzan errores de `errores.py` y
`main.py` los convierte en respuestas `{"detail", "errores"}`.

## Sesión y equipo

En el primer arranque, si no hay usuarios, se crea un **encargado inicial**
con `LA_ELOTIZA_ADMIN_NOMBRE` / `LA_ELOTIZA_ADMIN_PIN`. Cambia esos valores
antes de usar la API en el local.

- `GET /auth/usuarios` — nombres para la pantalla de inicio (sin sesión).
- `POST /auth/login` `{usuario_id, pin}` → `{token, expira_en, usuario}`.
  Tras 5 PIN incorrectos el usuario se bloquea 5 minutos (429).
- `POST /auth/logout`, `GET /auth/yo`.
- `GET/POST /equipo`, `DELETE /equipo/{id}` — solo encargado. Quitar a
  alguien es una baja lógica y cierra sus sesiones.

Las rutas protegidas piden `Authorization: Bearer <token>`. Los PIN se
guardan con hash PBKDF2 y de los tokens solo se guarda su hash.

## Catálogo y menú

```text
Categoría → Producto → Presentación (tamaño con precio)
                     ↘ Liga → Grupo de modificadores → Modificador (opción con precio)
```

Una **liga** pega un grupo a un producto con sus reglas:

| Campo | Para qué | Ejemplo del menú |
| --- | --- | --- |
| `minimo` / `maximo` | Cuántas opciones se eligen | Supremo: 2 y 2 sabritas |
| `incluidas` | Cuántas van sin costo (las más baratas) | Sabriramen: 1 topping incluido |
| `presentacion_id` | El grupo solo aplica con ese tamaño | Sabriesquite 20 oz admite Tostitos |
| `excluidos` | Opciones del grupo que no se ofrecen | Elote tradicional sin tocino |

El precio de una pieza es el de la presentación (o el del producto) más la
suma de las opciones elegidas, menos las incluidas.

- `GET /menu` — categorías → productos activos con presentaciones y grupos.
- `POST /menu/cotizar` `{producto_id, presentacion_id?, modificadores: [ids], cantidad}`
  → precio y texto de detalle; 422 con `errores` si falta algo obligatorio.
- `PUT /menu/productos/{id}/disponible`, `PUT /menu/modificadores/{id}/disponible`
  — marcar agotados (cualquier usuario).
- `/catalogo/*` — altas y cambios de categorías, productos, presentaciones,
  grupos, opciones y ligas (solo encargado). Nada se borra: se desactiva con
  `activo=false`.

El menú inicial sale de `semilla.py` y solo se carga si el catálogo está
vacío: `uv run cargar-menu` (o `pnpm run seed:api` desde el raíz).

## Turno, órdenes y comanda

Una orden vive dentro de un **turno** (la jornada de caja). Solo puede haber
un turno abierto y sin él no se levantan órdenes.

- `POST /turnos` `{fondo?}` — abre el turno; `GET /turnos/actual`.
- `POST /ordenes` `{cliente?}` — nueva orden; `PATCH /ordenes/{id}` cambia el cliente.
- `POST /ordenes/{id}/items` `{producto_id, presentacion_id?, modificadores: [ids], cantidad, nota}`.
- `PATCH /ordenes/{id}/items/{item_id}` `{cantidad?, nota?, personalizacion?}` —
  `personalizacion` reemplaza presentación y modificadores completos.
- `DELETE /ordenes/{id}/items/{item_id}`.
- `POST /ordenes/{id}/confirmar` — genera la comanda con el folio de la orden.
  Exige productos y nombre del cliente. Si después cambia algo, la orden queda
  con `comanda_al_dia=false` y al confirmar de nuevo sale la versión siguiente.
- `GET /ordenes/{id}/comanda`, `POST /ordenes/{id}/cancelar`.
- `GET /ordenes?filtro=en_preparacion|canceladas|todas` — órdenes del turno abierto.

Estados de una orden: `abierta` (editable) → `cerrada` (cobrada) o `cancelada`.
Cada producto de la orden guarda copia de su nombre, presentación, opciones y
precio, así que cambiar el catálogo no altera órdenes ya levantadas.

El avance por sprints está en [SPRINTS.md](SPRINTS.md).

Esta carpeta pertenece al repositorio Git raíz; no ejecutar `git init` aquí.
