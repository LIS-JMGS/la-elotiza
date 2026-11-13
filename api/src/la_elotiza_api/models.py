"""Modelos de base de datos.

Todos heredan de `la_elotiza_api.db.Base`. Alembic importa este módulo para
detectar las tablas, así que cada modelo nuevo debe vivir aquí (o importarse
desde aquí).
"""

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Column, Enum, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from la_elotiza_api.db import Base
from la_elotiza_api.tipos import Dinero, FechaUTC, ahora_utc


def _enum(cls: type[enum.Enum], name: str) -> Enum:
    """Enum guardado como texto con los valores (no los nombres) del Enum."""
    return Enum(
        cls,
        name=name,
        native_enum=False,
        validate_strings=True,
        values_callable=lambda e: [m.value for m in e],
    )


class Rol(enum.StrEnum):
    ENCARGADO = "encargado"
    CAJERO = "cajero"


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60))
    pin_hash: Mapped[str] = mapped_column(String(200))
    rol: Mapped[Rol] = mapped_column(_enum(Rol, "rol"))
    # Baja lógica: se conserva para el historial de ventas.
    activo: Mapped[bool] = mapped_column(default=True)
    intentos_fallidos: Mapped[int] = mapped_column(default=0)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(FechaUTC())
    creado_en: Mapped[datetime] = mapped_column(FechaUTC(), default=ahora_utc)


class SesionToken(Base):
    __tablename__ = "sesiones"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    creada_en: Mapped[datetime] = mapped_column(FechaUTC(), default=ahora_utc)
    expira_en: Mapped[datetime] = mapped_column(FechaUTC())
    revocada: Mapped[bool] = mapped_column(default=False)

    usuario: Mapped[Usuario] = relationship()


# --- Catálogo -----------------------------------------------------------------
#
# Categoria → Producto → Presentacion (tamaños con precio propio).
# GrupoModificadores → Modificador (opciones con precio propio).
# ProductoGrupo liga un grupo a un producto con sus reglas: mínimo, máximo,
# cuántas opciones van incluidas sin costo, si aplica solo a una presentación
# y qué opciones del grupo no se ofrecen para ese producto.
#
# Nada se borra físicamente: se desactiva (`activo`) para no romper el
# historial de ventas. `disponible=False` marca algo como agotado.


class Categoria(Base):
    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60), unique=True)
    orden: Mapped[int] = mapped_column(default=0)
    activa: Mapped[bool] = mapped_column(default=True)

    productos: Mapped[list["Producto"]] = relationship(
        back_populates="categoria", order_by="(Producto.orden, Producto.id)"
    )


class Producto(Base):
    __tablename__ = "productos"

    id: Mapped[int] = mapped_column(primary_key=True)
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(80))
    descripcion: Mapped[str] = mapped_column(String(300), default="")
    # Precio cuando no hay presentaciones; si las hay, manda la presentación.
    precio: Mapped[Decimal | None] = mapped_column(Dinero())
    orden: Mapped[int] = mapped_column(default=0)
    activo: Mapped[bool] = mapped_column(default=True)
    disponible: Mapped[bool] = mapped_column(default=True)

    categoria: Mapped[Categoria] = relationship(back_populates="productos")
    presentaciones: Mapped[list["Presentacion"]] = relationship(
        back_populates="producto",
        order_by="(Presentacion.orden, Presentacion.id)",
    )
    grupos: Mapped[list["ProductoGrupo"]] = relationship(
        back_populates="producto",
        cascade="all, delete-orphan",
        order_by="(ProductoGrupo.orden, ProductoGrupo.id)",
    )


class Presentacion(Base):
    __tablename__ = "presentaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(40))
    precio: Mapped[Decimal] = mapped_column(Dinero())
    orden: Mapped[int] = mapped_column(default=0)
    activa: Mapped[bool] = mapped_column(default=True)

    producto: Mapped[Producto] = relationship(back_populates="presentaciones")


class GrupoModificadores(Base):
    __tablename__ = "grupos_modificadores"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Nombre para administrar (único) y etiqueta corta para comanda/ticket.
    nombre: Mapped[str] = mapped_column(String(60), unique=True)
    etiqueta: Mapped[str] = mapped_column(String(40))
    activo: Mapped[bool] = mapped_column(default=True)

    modificadores: Mapped[list["Modificador"]] = relationship(
        back_populates="grupo", order_by="(Modificador.orden, Modificador.id)"
    )


class Modificador(Base):
    __tablename__ = "modificadores"

    id: Mapped[int] = mapped_column(primary_key=True)
    grupo_id: Mapped[int] = mapped_column(
        ForeignKey("grupos_modificadores.id"), index=True
    )
    nombre: Mapped[str] = mapped_column(String(60))
    precio: Mapped[Decimal] = mapped_column(Dinero(), default=Decimal("0"))
    orden: Mapped[int] = mapped_column(default=0)
    activo: Mapped[bool] = mapped_column(default=True)
    disponible: Mapped[bool] = mapped_column(default=True)

    grupo: Mapped[GrupoModificadores] = relationship(back_populates="modificadores")


producto_grupo_excluidos = Table(
    "producto_grupo_excluidos",
    Base.metadata,
    Column(
        "producto_grupo_id",
        ForeignKey("producto_grupos.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("modificador_id", ForeignKey("modificadores.id"), primary_key=True),
)


class ProductoGrupo(Base):
    __tablename__ = "producto_grupos"

    id: Mapped[int] = mapped_column(primary_key=True)
    producto_id: Mapped[int] = mapped_column(
        ForeignKey("productos.id", ondelete="CASCADE"), index=True
    )
    grupo_id: Mapped[int] = mapped_column(ForeignKey("grupos_modificadores.id"))
    # Si se indica, el grupo solo aplica con esa presentación.
    presentacion_id: Mapped[int | None] = mapped_column(ForeignKey("presentaciones.id"))
    # Encabezado en el POS; si está vacío se usa el nombre del grupo.
    titulo: Mapped[str] = mapped_column(String(80), default="")
    orden: Mapped[int] = mapped_column(default=0)
    minimo: Mapped[int] = mapped_column(default=0)
    maximo: Mapped[int | None]
    # Cuántas opciones van sin costo (se descuentan las más baratas).
    incluidas: Mapped[int] = mapped_column(default=0)

    producto: Mapped[Producto] = relationship(back_populates="grupos")
    grupo: Mapped[GrupoModificadores] = relationship()
    presentacion: Mapped[Presentacion | None] = relationship()
    excluidos: Mapped[list[Modificador]] = relationship(
        secondary=producto_grupo_excluidos
    )

    @property
    def titulo_visible(self) -> str:
        return self.titulo or self.grupo.nombre

    def opciones(self) -> list[Modificador]:
        """Opciones activas del grupo que se ofrecen para este producto."""
        excluidos = {m.id for m in self.excluidos}
        return [
            m for m in self.grupo.modificadores if m.activo and m.id not in excluidos
        ]
