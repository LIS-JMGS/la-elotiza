# Plan de la API por sprints

Cada sprint termina con pruebas en verde (`pnpm run check:api`) y su propia
migración de Alembic, si toca tablas. Los números RF son los de
`REQUISITOS.md` del diseño.

| Sprint | Tema | RF | Estado |
| --- | --- | --- | --- |
| 1 | Cimientos | — | ✅ Hecho |
| 2 | Usuarios, login con PIN y equipo | 27-29 | ✅ Hecho |
| 3 | Catálogo administrable y menú | 3-5, 30 | ✅ Hecho (pendiente de revisar) |
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

- [x] Modelos `usuarios` y `sesiones` + migración `usuarios y sesiones`.
- [x] `seguridad.py`: PIN con hash PBKDF2 y sal; del token de sesión solo se
      guarda su hash.
- [x] Sesiones con expiración (`LA_ELOTIZA_SESION_HORAS`, 14 h por defecto).
- [x] Bloqueo de 5 minutos tras 5 PIN incorrectos.
- [x] `GET /auth/usuarios`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/yo`.
- [x] Encargado inicial si no hay usuarios (`LA_ELOTIZA_ADMIN_NOMBRE` / `_PIN`).
- [x] `GET/POST /equipo`, `DELETE /equipo/{id}` solo para encargado; no se
      puede quitar a uno mismo ni al último encargado; quitar cierra sesiones.
- [x] `deps.py`: `UsuarioActual` y `Encargado` como dependencias reutilizables.
- [x] 14 pruebas en `test_auth_equipo.py`.

## Sprint 3 · Catálogo administrable y menú

- [x] Modelos: categorías, productos, presentaciones, grupos de modificadores,
      modificadores y ligas producto-grupo (mínimo, máximo, incluidas,
      solo para una presentación, opciones excluidas) + migración `catalogo`.
- [x] `servicios/catalogo.py`: `armar_linea` valida la personalización y
      calcula el precio (presentación u producto + opciones − incluidas).
- [x] `GET /menu` (por categoría, con las reglas de cada grupo) y
      `POST /menu/cotizar` para el precio en vivo.
- [x] Marcar agotados: `PUT /menu/productos/{id}/disponible` y
      `PUT /menu/modificadores/{id}/disponible` (cualquier usuario).
- [x] Administración `/catalogo/*` solo para encargado; nada se borra, se
      desactiva.
- [x] `semilla.py`: menú del prototipo (`uv run cargar-menu`, `pnpm run seed:api`);
      solo carga si el catálogo está vacío.
- [x] 21 pruebas en `test_catalogo.py`.

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
