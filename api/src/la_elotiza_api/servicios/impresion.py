"""Texto plano para impresora térmica de 58 mm (32 columnas).

El frontend lo manda a imprimir tal cual (RF 18); así comanda y ticket salen
iguales desde cualquier dispositivo.
"""

import textwrap
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from la_elotiza_api.models import Comanda, MetodoPago, Orden

ANCHO = 32
LINEA = "-" * ANCHO


def _dinero(n: Decimal) -> str:
    signo = "-" if n < 0 else ""
    return f"{signo}${abs(n):,.2f}"


def _fecha(dt: datetime, tz: ZoneInfo) -> str:
    return dt.astimezone(tz).strftime("%d/%m/%Y %H:%M")


def _par(izq: str, der: str) -> str:
    """Texto a la izquierda e importe a la derecha en una misma línea."""
    espacio = ANCHO - len(der) - 1
    izq = izq if len(izq) <= espacio else izq[: espacio - 1] + "…"
    return f"{izq:<{espacio}} {der}"


def _envolver(texto: str, sangria: str = "  ") -> list[str]:
    return textwrap.wrap(
        texto, ANCHO, initial_indent=sangria, subsequent_indent=sangria
    )


def _encabezado(titulo: str) -> list[str]:
    return ["LA ELOTIZA".center(ANCHO), titulo.center(ANCHO), LINEA]


def comanda(orden: Orden, c: Comanda, tz: ZoneInfo) -> str:
    titulo = "COMANDA" if c.version == 1 else f"COMANDA (CAMBIO {c.version - 1})"
    out = _encabezado(titulo)
    out += [
        _par(f"Orden {orden.folio}", _fecha(c.generada_en, tz)),
        f"Cliente: {c.cliente}",
        LINEA,
    ]
    for linea in c.lineas:
        out += textwrap.wrap(f"{linea['cantidad']}x {linea['nombre']}", ANCHO)
        out += _envolver(linea["detalle"])
        if linea["nota"]:
            out += _envolver(f"* {linea['nota']}")
    out.append(LINEA)
    return "\n".join(out) + "\n"


def ticket(orden: Orden, tz: ZoneInfo) -> str:
    pago = orden.pago
    assert pago is not None, "solo hay ticket de órdenes cobradas"
    out = _encabezado("TICKET DE VENTA")
    out += [
        _par(f"Orden {orden.folio}", _fecha(pago.registrado_en, tz)),
        f"Cliente: {orden.cliente}",
        LINEA,
    ]
    for item in orden.items:
        out.append(_par(f"{item.cantidad}x {item.nombre}", _dinero(item.importe)))
        if item.detalle != "Como viene":
            out += _envolver(item.detalle)
    out += [LINEA, _par("TOTAL", _dinero(pago.total))]
    if pago.metodo is MetodoPago.EFECTIVO:
        out += [
            _par("Efectivo", _dinero(pago.recibido or pago.total)),
            _par("Cambio", _dinero(pago.cambio or Decimal("0"))),
        ]
    else:
        out += [
            _par("Transferencia", _dinero(pago.total)),
            f"Concepto: {pago.concepto}",
        ]
    out += [LINEA, "¡Gracias por tu compra!".center(ANCHO)]
    return "\n".join(out) + "\n"
