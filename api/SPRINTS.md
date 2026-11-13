# Plan de la API por sprints

Cada sprint termina con pruebas en verde (`pnpm run check:api`) y su propia
migración de Alembic, si toca tablas. Los números RF son los de
`REQUISITOS.md` del diseño.

| Sprint | Tema | RF | Estado |
| --- | --- | --- | --- |
| 1 | Cimientos | — | ✅ Hecho |
| 2 | Usuarios, login con PIN y equipo | 27-29 | ✅ Hecho |
| 3 | Catálogo administrable y menú | 3-5, 30 | ✅ Hecho |
| 4 | Turno, órdenes y comanda | 1-11, 19, 31-32, 35 | ✅ Hecho |
| 5 | Cobro, ticket y cocina | 12-18, 33-34, 36 | ✅ Hecho |
| 6 | Corte de caja y cierre de turno | 20-26, 37-38 | ✅ Hecho (pendiente de revisar) |

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

- [x] Modelos: turnos, órdenes, productos de la orden y comandas + migración
      `turnos ordenes y comandas` (con índice único: un solo turno abierto).
- [x] `POST /turnos` abre la jornada con fondo de caja (`LA_ELOTIZA_FONDO_CAJA`
      por defecto); `GET /turnos/actual`. Sin turno no se levantan órdenes.
- [x] `POST /ordenes`, `PATCH /ordenes/{id}` (cliente) y
      `POST/PATCH/DELETE /ordenes/{id}/items`; el total se recalcula solo.
- [x] Cada producto guarda copia de nombre, presentación, opciones y precio:
      cambiar el catálogo no altera órdenes anteriores.
- [x] `POST /ordenes/{id}/confirmar` → comanda con folio; exige productos y
      cliente. Un cambio posterior pide confirmar otra vez (versión 2, 3…).
- [x] `POST /ordenes/{id}/cancelar`; una orden cancelada ya no se modifica.
- [x] `GET /ordenes?filtro=en_preparacion|canceladas|todas`.
- [x] 16 pruebas en `test_ordenes.py`.

## Sprint 5 · Cobro, ticket y cocina

- [x] Modelo `pagos` y columnas `ordenes.entregada` / `orden_items.preparado`
      + migración `pagos y cocina` (probada sobre una base con órdenes).
- [x] `POST /ordenes/{id}/cobro`: efectivo (calcula el cambio; rechaza si no
      alcanza) o transferencia. Exige la comanda al día.
- [x] `GET /ordenes/{id}/transferencia?telefono=`: concepto único
      `ELO-DDMM-0001-NOMBRE` y liga de WhatsApp con el mensaje.
- [x] El cobro cierra la orden y ya no se puede modificar ni cancelar.
- [x] `servicios/impresion.py`: comanda y ticket en texto de 32 columnas para
      impresora térmica de 58 mm; `GET /ordenes/{id}/ticket` para reimprimir.
- [x] Cocina: `PUT /ordenes/{id}/items/{item_id}/preparado`,
      `PUT /ordenes/{id}/preparado` (todos) y `PUT /ordenes/{id}/entrega`
      (solo órdenes cobradas; se puede reabrir).
- [x] Filtro `entregadas`; `en_preparacion` ya no incluye las entregadas.
- [x] 15 pruebas en `test_cobro.py`.

## Sprint 6 · Corte de caja y cierre de turno

- [x] `calcular_corte`: total vendido, efectivo, transferencias, fondo,
      efectivo esperado (fondo + ventas en efectivo), contado y diferencia.
- [x] Las órdenes canceladas no cuentan en los totales (RF 20).
- [x] `GET /turnos/actual/corte?efectivo_contado=` calcula sin cerrar.
- [x] `POST /turnos/actual/cierre` registra el efectivo contado y cierra el
      turno; pide cobrar o cancelar las órdenes pendientes.
- [x] `GET /turnos/{id}/corte` para reimprimir un corte ya cerrado.
- [x] Corte en texto de 32 columnas, con la lista de transferencias para conciliar.
- [x] 12 pruebas en `test_corte.py`.
- [x] README final con estructura del proyecto.

No lleva migración: la tabla `turnos` ya tenía `cerrado_en`, `cerrado_por_id`
y `efectivo_contado` desde el sprint 4.

---

## Cobertura de requisitos

| RF | Dónde se cumple |
| --- | --- |
| 1-2 | `POST /ordenes`, `PATCH /ordenes/{id}` |
| 3-6 | `POST /ordenes/{id}/items` (cantidad, presentación, modificadores, nota) |
| 7 | `Orden.total` se calcula de sus productos en cada respuesta |
| 8-9 | `PATCH` / `DELETE /ordenes/{id}/items/{item_id}` |
| 10-11 | `POST /ordenes/{id}/confirmar` → comanda con folio |
| 12-15 | `POST /ordenes/{id}/cobro` |
| 16 | `_exigir_editable` en `servicios/ordenes.py` |
| 17-18 | `TicketOut.texto`, `GET /ordenes/{id}/ticket` |
| 19-20 | `POST /ordenes/{id}/cancelar`; `calcular_corte` las excluye |
| 21 | Tablas `ordenes` y `pagos` ligadas al turno |
| 22-26 | `GET /turnos/actual/corte`, `POST /turnos/actual/cierre` |
| 27 | `GET /auth/usuarios`, `POST /auth/login` |
| 28-29 | `/equipo` solo para encargado |
| 30 | `armar_linea` en `servicios/catalogo.py` |
| 31-32 | `confirmar` y `comanda_al_dia` |
| 33 | `Pago.cambio` |
| 34 | `GET /ordenes/{id}/transferencia` |
| 35-36 | `GET /ordenes`, `/preparado`, `/entrega` |
| 37 | `efectivo_esperado = fondo + efectivo` |
| 38 | `CorteOut.texto` al cerrar el turno |
