# La Elotiza

Monorepo de la aplicación: un repositorio Git para frontend y API.

```text
la-elotiza/
├── front/        # Frontend existente: Next.js + TypeScript
├── api/          # Backend: FastAPI + Python
└── package.json  # Comandos desde el raíz
```

## Frontend

Usar pnpm 11.20.0 y una versión de Node.js compatible con las dependencias.

Desde el raíz:

```bash
pnpm run install:front
pnpm run dev:front
```

Validación y compilación:

```bash
pnpm run check:front
pnpm run build:front
```

`check:front` ejecuta ESLint y TypeScript; no sustituye pruebas funcionales.
El frontend conserva su propio `pnpm-lock.yaml` y su instalación en `front/`.
Por ahora no se configura un workspace de paquetes compartidos.

## API

Requiere Python 3.12 o superior y uv. Desde el raíz:

```bash
pnpm run install:api
pnpm run dev:api
```

O directamente con uv: `uv run --directory api app --reload`.
Desde `api/`, basta con `uv run app` para iniciar el servidor.

Documentación: http://127.0.0.1:8000/docs. Ejecutar el frontend y la API
en terminales separadas. Consulta [api/README.md](api/README.md).

`pnpm run check:api` ejecuta Ruff y pytest. `pnpm run check` valida ambas
aplicaciones. Las dependencias Python se fijan en `api/uv.lock`.

## Control de versiones

Hay un único `.git/` en el raíz. No se usan submódulos ni repositorios anidados.
Un clone normal descarga las dos carpetas; las dependencias se instalan después.

Crear una rama por cambio:

```bash
git switch -c feat/pedidos
```

Se pueden guardar cambios de una sola aplicación:

```bash
git add api/
git diff --cached
git commit -m "feat(api): agregar pedidos"
```

Antes del commit, revisar `git diff --cached`: también se incluirá cualquier
archivo que ya estuviera preparado. Los cambios sin preparar de `front/`
seguirán pendientes. El push publica todos los commits pendientes de la rama.

Para cambios coordinados, incluir archivos de ambas carpetas en el mismo commit.
Frontend y API pueden tener validaciones y despliegues independientes.

## Pendiente de configurar

- Endpoints de negocio, base de datos y autenticación de la API.
- Pruebas funcionales del frontend.
- Remoto Git, CI y protección de `main` con validaciones obligatorias.

Las validaciones locales todavía no bloquean pushes ni merges automáticamente.
No subir credenciales ni archivos `.env`; usar ejemplos sin secretos para
documentar las variables necesarias.
