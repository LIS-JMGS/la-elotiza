# Plan de la API por sprints

Cada sprint termina con pruebas en verde (`pnpm run check:api`) y su propia
migración de Alembic, si toca tablas. Los números RF son los de
`REQUISITOS.md` del diseño.

| Sprint | Tema | RF | Estado |
| --- | --- | --- | --- |
| 1 | Cimientos | — | ✅ Hecho (pendiente de revisar) |
| 2 | Usuarios, login con PIN y equipo | 27-29 | ⬜ Pendiente |
| 3 | Catálogo administrable y menú | 3-5, 30 | ⬜ Pendiente |
| 4 | Turno, órdenes y comanda | 1-11, 19, 31-32, 35 | ⬜ Pendiente |
| 5 | Cobro, ticket y cocina | 12-18, 33-34, 36 | ⬜ Pendiente |
| 6 | Corte de caja y cierre de turno | 20-26, 37-38 | ⬜ Pendiente |

---

## Sprint 1 · Cimientos

Base técnica sobre la que se construye todo lo demás. No tiene endpoints de
negocio todavía.

- [x] Dependencias: SQLAlchemy 2, Alembic y tzdata.
- [x] `config.py`: `Settings` leída de variables de entorno (`LA_ELOTIZA_*`).
- [x] `db.py`: motor, `Base` declarativa, sesión por petición (`get_db`) y
      llaves foráneas activas en SQLite.
- [x] `tipos.py`: `Dinero` (se guarda en centavos enteros) y `FechaUTC`
      (siempre con zona horaria).
- [x] `errores.py`: errores de dominio que `main` traduce a 401/403/404/409/422/429.
- [x] `main.py`: `create_app(settings)`, CORS para el front y manejador de errores.
- [x] Alembic configurado con la misma URL y modelos que la API.
- [x] Pruebas: `conftest.py` con SQLite en memoria, salud, tipos y errores.
- [x] Scripts: `pnpm run migrate:api`; `dev:api` migra antes de arrancar.

## Sprint 2 · Usuarios, login con PIN y equipo

- [ ] Modelos `usuarios` y `sesiones` + migración.
- [ ] PIN con hash PBKDF2; token de sesión (solo se guarda su hash) con expiración.
- [ ] Bloqueo de 5 minutos tras 5 PIN incorrectos.
- [ ] `GET /auth/usuarios`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/yo`.
- [ ] Encargado inicial si no hay usuarios.
- [ ] `GET/POST /equipo`, `DELETE /equipo/{id}` solo para encargado.
- [ ] Pruebas.

## Sprint 3 · Catálogo administrable y menú

- [ ] Modelos: categorías, productos, presentaciones, grupos de modificadores,
      modificadores y ligas producto-grupo (mínimo, máximo, incluidas,
      solo para una presentación, opciones excluidas) + migración.
- [ ] Reglas: validar personalización y calcular precio.
- [ ] `GET /menu`, `POST /menu/cotizar`, marcar agotados.
- [ ] Administración `/catalogo/*` para encargado.
- [ ] Semilla con el menú del prototipo (`uv run cargar-menu`).
- [ ] Pruebas.

## Sprint 4 · Turno, órdenes y comanda

- [ ] Modelos: turnos (uno abierto a la vez), órdenes, productos de la orden,
      comandas + migración.
- [ ] Abrir turno con fondo de caja.
- [ ] Crear orden, cliente, agregar/editar/quitar productos con total al día.
- [ ] Confirmar → comanda con folio; cambios piden confirmar de nuevo.
- [ ] Cancelar antes de cobrar.
- [ ] Pruebas.

## Sprint 5 · Cobro, ticket y cocina

- [ ] Modelo `pagos` + migración.
- [ ] Cobro en efectivo (cambio) o transferencia (concepto único + liga de WhatsApp).
- [ ] La orden cobrada se cierra y ya no se modifica.
- [ ] Ticket y comanda en texto para impresora térmica de 58 mm.
- [ ] Cocina: lista en preparación, marcar preparados, entregar.
- [ ] Pruebas.

## Sprint 6 · Corte de caja y cierre de turno

- [ ] Corte: total, efectivo, transferencias, fondo, esperado, contado y diferencia.
- [ ] Las canceladas no cuentan.
- [ ] Cerrar turno (pide cobrar o cancelar pendientes) e imprimir el corte.
- [ ] Pruebas y README final.
