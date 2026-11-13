"""Modelos de entrada y salida de la API (Pydantic)."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, ClassVar, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
    model_validator,
)

from la_elotiza_api.models import EstadoOrden, Rol

# Los importes se exponen como número JSON con 2 decimales; por dentro son
# Decimal para no acumular errores de redondeo.
Dinero = Annotated[
    Decimal,
    PlainSerializer(lambda v: float(v), return_type=float, when_used="json"),
]
DineroEntrada = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]
Pin = Annotated[str, StringConstraints(pattern=r"^\d{4}$")]
Nombre = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)
]
Cliente = Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)]
Nota = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Texto = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]
Posicion = Annotated[int, Field(ge=0)]
Ids = Annotated[list[int], Field(max_length=50)]


def _ids(valor: object) -> object:
    """Convierte una lista de objetos ORM en sus ids."""
    if isinstance(valor, list):
        return [getattr(v, "id", v) for v in valor]
    return valor


class Esquema(BaseModel):
    # from_attributes: se construyen directo desde los modelos de SQLAlchemy.
    # extra="forbid": un campo desconocido es error, no se ignora en silencio.
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class Cambios(Esquema):
    """Base para PATCH: solo se aplican los campos enviados y `null` solo se
    acepta en los campos listados en `anulables`."""

    anulables: ClassVar[set[str]] = set()

    @model_validator(mode="after")
    def _sin_nulos(self) -> Self:
        for campo in self.model_fields_set:
            if getattr(self, campo) is None and campo not in self.anulables:
                raise ValueError(f"'{campo}' no puede ser null")
        return self

    def cambios(self) -> dict:
        return self.model_dump(exclude_unset=True)


# --- Sesión y equipo --------------------------------------------------------


class UsuarioLogin(Esquema):
    """Lo mínimo para la pantalla de inicio: no expone rol ni PIN."""

    id: int
    nombre: str


class UsuarioOut(Esquema):
    id: int
    nombre: str
    rol: Rol


class LoginIn(Esquema):
    usuario_id: int
    pin: Pin


class LoginOut(Esquema):
    token: str
    expira_en: datetime
    usuario: UsuarioOut


class NuevoUsuarioIn(Esquema):
    nombre: Nombre
    pin: Pin
    rol: Rol = Rol.CAJERO


# --- Menú para el POS -------------------------------------------------------


class MenuOpcionOut(Esquema):
    id: int
    nombre: str
    precio: Dinero
    disponible: bool


class MenuGrupoOut(Esquema):
    id: int = Field(description="Id de la liga producto-grupo")
    grupo_id: int
    titulo: str
    etiqueta: str
    minimo: int
    maximo: int | None
    incluidas: int
    presentacion_id: int | None = Field(
        description="Si no es null, el grupo solo aplica con esa presentación"
    )
    opciones: list[MenuOpcionOut]


class MenuPresentacionOut(Esquema):
    id: int
    nombre: str
    precio: Dinero


class MenuProductoOut(Esquema):
    id: int
    nombre: str
    descripcion: str
    precio: Dinero | None
    precio_desde: Dinero | None
    disponible: bool
    presentaciones: list[MenuPresentacionOut]
    grupos: list[MenuGrupoOut]


class MenuCategoriaOut(Esquema):
    id: int
    nombre: str
    productos: list[MenuProductoOut]


class Personalizacion(Esquema):
    presentacion_id: int | None = None
    modificadores: Ids = Field(default_factory=list)


class CotizacionIn(Personalizacion):
    producto_id: int
    cantidad: int = Field(1, ge=1, le=99)


class CotizacionOut(Esquema):
    precio_unitario: Dinero
    importe: Dinero
    detalle: str


class DisponibleIn(Esquema):
    disponible: bool


# --- Administración del catálogo (encargado) --------------------------------


class CategoriaIn(Esquema):
    nombre: Nombre
    orden: Posicion = 0
    activa: bool = True


class CategoriaCambios(Cambios):
    nombre: Nombre | None = None
    orden: Posicion | None = None
    activa: bool | None = None


class CategoriaOut(Esquema):
    id: int
    nombre: str
    orden: int
    activa: bool


class ProductoIn(Esquema):
    categoria_id: int
    nombre: Nombre
    descripcion: Texto = ""
    precio: DineroEntrada | None = Field(
        None, description="Null si el precio lo dan las presentaciones"
    )
    orden: Posicion = 0
    activo: bool = True
    disponible: bool = True


class ProductoCambios(Cambios):
    anulables: ClassVar[set[str]] = {"precio"}
    categoria_id: int | None = None
    nombre: Nombre | None = None
    descripcion: Texto | None = None
    precio: DineroEntrada | None = None
    orden: Posicion | None = None
    activo: bool | None = None
    disponible: bool | None = None


class PresentacionIn(Esquema):
    nombre: Nombre
    precio: DineroEntrada
    orden: Posicion = 0
    activa: bool = True


class PresentacionCambios(Cambios):
    nombre: Nombre | None = None
    precio: DineroEntrada | None = None
    orden: Posicion | None = None
    activa: bool | None = None


class PresentacionOut(Esquema):
    id: int
    nombre: str
    precio: Dinero
    orden: int
    activa: bool


class GrupoIn(Esquema):
    nombre: Nombre
    etiqueta: Nombre
    activo: bool = True


class GrupoCambios(Cambios):
    nombre: Nombre | None = None
    etiqueta: Nombre | None = None
    activo: bool | None = None


class ModificadorIn(Esquema):
    nombre: Nombre
    precio: DineroEntrada = Decimal("0")
    orden: Posicion = 0
    activo: bool = True
    disponible: bool = True


class ModificadorCambios(Cambios):
    nombre: Nombre | None = None
    precio: DineroEntrada | None = None
    orden: Posicion | None = None
    activo: bool | None = None
    disponible: bool | None = None


class ModificadorOut(Esquema):
    id: int
    grupo_id: int
    nombre: str
    precio: Dinero
    orden: int
    activo: bool
    disponible: bool


class GrupoOut(Esquema):
    id: int
    nombre: str
    etiqueta: str
    activo: bool
    modificadores: list[ModificadorOut]


class LigaIn(Esquema):
    grupo_id: int
    presentacion_id: int | None = None
    titulo: Texto = ""
    orden: Posicion = 0
    minimo: int = Field(0, ge=0)
    maximo: int | None = Field(None, ge=1)
    incluidas: int = Field(0, ge=0)
    excluidos: Ids = Field(
        default_factory=list, description="Ids de opciones del grupo que no aplican"
    )


class LigaCambios(Cambios):
    anulables: ClassVar[set[str]] = {"presentacion_id", "maximo"}
    grupo_id: int | None = None
    presentacion_id: int | None = None
    titulo: Texto | None = None
    orden: Posicion | None = None
    minimo: int | None = Field(None, ge=0)
    maximo: int | None = Field(None, ge=1)
    incluidas: int | None = Field(None, ge=0)
    excluidos: Ids | None = None


class LigaOut(Esquema):
    id: int
    grupo_id: int
    presentacion_id: int | None
    titulo: str
    orden: int
    minimo: int
    maximo: int | None
    incluidas: int
    excluidos: Annotated[list[int], BeforeValidator(_ids)]


class ProductoOut(Esquema):
    id: int
    categoria_id: int
    nombre: str
    descripcion: str
    precio: Dinero | None
    orden: int
    activo: bool
    disponible: bool
    presentaciones: list[PresentacionOut]
    grupos: list[LigaOut]


class CatalogoCategoriaOut(CategoriaOut):
    productos: list[ProductoOut]


# --- Turno ------------------------------------------------------------------


class AbrirTurnoIn(Esquema):
    fondo: DineroEntrada | None = Field(
        None, description="Si se omite, se usa el fondo configurado."
    )


class TurnoOut(Esquema):
    id: int
    fondo: Dinero
    abierto_en: datetime
    abierto_por: UsuarioOut
    cerrado_en: datetime | None


# --- Órdenes ----------------------------------------------------------------


class OrdenIn(Esquema):
    cliente: Cliente = ""


class ClienteIn(Esquema):
    cliente: Cliente


class ItemIn(Personalizacion):
    producto_id: int
    cantidad: int = Field(1, ge=1, le=99)
    nota: Nota = ""


class ItemCambiosIn(Cambios):
    cantidad: int | None = Field(None, ge=1, le=99)
    nota: Nota | None = None
    personalizacion: Personalizacion | None = Field(
        None, description="Reemplaza presentación y modificadores completos"
    )


class ModificadorElegidoOut(Esquema):
    id: int
    grupo: str
    nombre: str
    precio: Dinero


class ItemOut(Esquema):
    id: int
    producto_id: int
    presentacion_id: int | None
    nombre: str
    presentacion: str
    modificadores: list[ModificadorElegidoOut]
    cantidad: int
    detalle: str
    nota: str
    precio_unitario: Dinero
    importe: Dinero


class LineaComandaOut(Esquema):
    item_id: int
    cantidad: int
    nombre: str
    detalle: str
    nota: str


class ComandaOut(Esquema):
    folio: str
    version: int
    cliente: str
    generada_en: datetime
    lineas: list[LineaComandaOut]


class OrdenOut(Esquema):
    id: int
    folio: str
    cliente: str
    estado: EstadoOrden
    comanda_al_dia: bool
    confirmada: bool
    creada_en: datetime
    cancelada_en: datetime | None
    total: Dinero
    items: list[ItemOut]
    comanda: ComandaOut | None
