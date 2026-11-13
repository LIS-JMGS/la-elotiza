"""Tipos de columna propios: dinero en centavos y fechas en UTC."""

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import DateTime, Integer
from sqlalchemy.types import TypeDecorator

CENTAVO = Decimal("0.01")


def redondear(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def ahora_utc() -> datetime:
    return datetime.now(UTC)


class Dinero(TypeDecorator[Decimal]):
    """Guarda importes como centavos enteros para evitar errores de redondeo."""

    impl = Integer
    cache_ok = True

    def process_bind_param(self, value: Decimal | None, dialect) -> int | None:
        if value is None:
            return None
        return int(redondear(Decimal(value)) * 100)

    def process_result_value(self, value: int | None, dialect) -> Decimal | None:
        if value is None:
            return None
        return redondear(Decimal(value) / 100)


class FechaUTC(TypeDecorator[datetime]):
    """Guarda fechas en UTC y siempre las devuelve con zona horaria."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Las fechas deben llevar zona horaria")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC)
