"""Catálogo: consulta del menú, reglas de personalización/precio y
administración (categorías, productos, presentaciones y modificadores)."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from la_elotiza_api.errores import Conflicto, DatosInvalidos, NoEncontrado
from la_elotiza_api.models import (
    Categoria,
    GrupoModificadores,
    Modificador,
    Presentacion,
    Producto,
    ProductoGrupo,
)

CERO = Decimal("0")


def _opciones_producto():
    return (
        selectinload(Producto.presentaciones),
        selectinload(Producto.grupos).selectinload(ProductoGrupo.excluidos),
        selectinload(Producto.grupos)
        .selectinload(ProductoGrupo.grupo)
        .selectinload(GrupoModificadores.modificadores),
    )


# --- Consulta -----------------------------------------------------------------


def categorias(db: Session, solo_activos: bool) -> list[Categoria]:
    """Árbol completo del catálogo. Para el POS se filtran los inactivos."""
    q = select(Categoria).options(
        selectinload(Categoria.productos).options(*_opciones_producto())
    )
    if solo_activos:
        q = q.where(Categoria.activa)
    return list(db.scalars(q.order_by(Categoria.orden, Categoria.id)))


def grupos(db: Session) -> list[GrupoModificadores]:
    return list(
        db.scalars(
            select(GrupoModificadores)
            .options(selectinload(GrupoModificadores.modificadores))
            .order_by(GrupoModificadores.nombre)
        )
    )


def obtener_producto(db: Session, producto_id: int) -> Producto:
    producto = db.scalar(
        select(Producto)
        .where(Producto.id == producto_id)
        .options(*_opciones_producto())
    )
    if producto is None:
        raise NoEncontrado("No existe ese producto")
    return producto


def ligas_aplicables(
    producto: Producto, presentacion: Presentacion | None
) -> list[ProductoGrupo]:
    return [
        liga
        for liga in producto.grupos
        if liga.grupo.activo
        and (
            liga.presentacion_id is None
            or (presentacion is not None and liga.presentacion_id == presentacion.id)
        )
    ]


def precio_desde(producto: Producto) -> Decimal | None:
    activas = [p.precio for p in producto.presentaciones if p.activa]
    return min(activas) if activas else producto.precio


# --- Reglas de personalización y precio ---------------------------------------


@dataclass(frozen=True)
class Linea:
    """Producto ya validado y cotizado, listo para guardarse en una orden."""

    producto: Producto
    presentacion: Presentacion | None
    elegidos: list[tuple[ProductoGrupo, list[Modificador]]]
    precio_unitario: Decimal
    detalle: str

    def modificadores_snapshot(self) -> list[dict[str, Any]]:
        return [
            {
                "id": m.id,
                "grupo": liga.grupo.etiqueta,
                "nombre": m.nombre,
                "precio": str(m.precio),
            }
            for liga, mods in self.elegidos
            for m in mods
        ]


def armar_linea(
    db: Session,
    producto_id: int,
    presentacion_id: int | None,
    modificador_ids: Iterable[int],
) -> Linea:
    """Valida la personalización (RF 4-5, 30) y calcula el precio unitario."""
    producto = db.scalar(
        select(Producto)
        .where(Producto.id == producto_id, Producto.activo)
        .options(*_opciones_producto())
    )
    if producto is None:
        raise DatosInvalidos("No existe ese producto en el menú")
    if not producto.disponible:
        raise Conflicto(f"{producto.nombre} está agotado")

    errores: list[str] = []
    ids = list(modificador_ids)
    if len(set(ids)) != len(ids):
        errores.append("No repitas opciones")

    presentacion: Presentacion | None = None
    activas = {p.id: p for p in producto.presentaciones if p.activa}
    if activas:
        if presentacion_id is None:
            errores.append("Falta elegir: Presentación")
        elif presentacion_id not in activas:
            errores.append("La presentación no es válida para este producto")
        else:
            presentacion = activas[presentacion_id]
        base = presentacion.precio if presentacion else CERO
    else:
        if presentacion_id is not None:
            errores.append(f"{producto.nombre} no tiene presentaciones")
        if producto.precio is None:
            errores.append(f"{producto.nombre} no tiene precio configurado")
        base = producto.precio or CERO

    ligas = ligas_aplicables(producto, presentacion)
    por_liga: dict[int, list[Modificador]] = {liga.id: [] for liga in ligas}
    for mid in dict.fromkeys(ids):
        liga = next((x for x in ligas if any(m.id == mid for m in x.opciones())), None)
        if liga is None:
            errores.append(f"La opción {mid} no aplica para {producto.nombre}")
            continue
        mod = next(m for m in liga.opciones() if m.id == mid)
        if not mod.disponible:
            errores.append(f"{mod.nombre} está agotado")
        por_liga[liga.id].append(mod)

    total = base
    elegidos: list[tuple[ProductoGrupo, list[Modificador]]] = []
    for liga in ligas:
        mods = sorted(por_liga[liga.id], key=lambda m: (m.orden, m.id))
        n, titulo = len(mods), liga.titulo_visible
        if n < liga.minimo:
            if n == 0:
                errores.append(f"Falta elegir: {titulo}")
            elif liga.maximo == liga.minimo:
                errores.append(f"{titulo}: elige exactamente {liga.minimo}")
            else:
                errores.append(f"{titulo}: elige al menos {liga.minimo}")
        elif liga.maximo is not None and n > liga.maximo:
            errores.append(f"{titulo}: elige máximo {liga.maximo}")
        if not mods:
            continue
        precios = sorted(m.precio for m in mods)
        total += sum(precios[liga.incluidas :], CERO)
        elegidos.append((liga, mods))

    if errores:
        raise DatosInvalidos("La personalización no es válida", errores)

    partes = [presentacion.nombre] if presentacion else []
    partes += [
        f"{liga.grupo.etiqueta}: " + " + ".join(m.nombre for m in mods)
        for liga, mods in elegidos
    ]
    return Linea(
        producto=producto,
        presentacion=presentacion,
        elegidos=elegidos,
        precio_unitario=total,
        detalle=" · ".join(partes) or "Como viene",
    )


# --- Disponibilidad (cualquier usuario) ---------------------------------------


def cambiar_disponible_producto(db: Session, producto_id: int, disponible: bool):
    producto = obtener_producto(db, producto_id)
    producto.disponible = disponible
    db.commit()
    return producto


def cambiar_disponible_modificador(db: Session, modificador_id: int, disponible: bool):
    mod = _get(db, Modificador, modificador_id, "No existe esa opción")
    mod.disponible = disponible
    db.commit()
    return mod


# --- Administración (encargado) -----------------------------------------------


def _get[T](db: Session, modelo: type[T], id_: int, mensaje: str) -> T:
    obj = db.get(modelo, id_)
    if obj is None:
        raise NoEncontrado(mensaje)
    return obj


def _aplicar(obj: object, cambios: Mapping[str, Any]) -> None:
    for campo, valor in cambios.items():
        setattr(obj, campo, valor)


def _nombre_libre(db: Session, modelo, nombre: str, excepto: int | None = None) -> None:
    q = select(modelo.id).where(func.lower(modelo.nombre) == nombre.lower())
    if excepto is not None:
        q = q.where(modelo.id != excepto)
    if db.scalar(q) is not None:
        raise Conflicto(f"Ya existe '{nombre}'")


def crear_categoria(db: Session, datos: Mapping[str, Any]) -> Categoria:
    _nombre_libre(db, Categoria, datos["nombre"])
    categoria = Categoria(**datos)
    db.add(categoria)
    db.commit()
    return categoria


def editar_categoria(
    db: Session, categoria_id: int, cambios: Mapping[str, Any]
) -> Categoria:
    categoria = _get(db, Categoria, categoria_id, "No existe esa categoría")
    if "nombre" in cambios:
        _nombre_libre(db, Categoria, cambios["nombre"], excepto=categoria_id)
    _aplicar(categoria, cambios)
    db.commit()
    return categoria


def crear_producto(db: Session, datos: Mapping[str, Any]) -> Producto:
    _get(db, Categoria, datos["categoria_id"], "No existe esa categoría")
    producto = Producto(**datos)
    db.add(producto)
    db.commit()
    return obtener_producto(db, producto.id)


def editar_producto(
    db: Session, producto_id: int, cambios: Mapping[str, Any]
) -> Producto:
    producto = obtener_producto(db, producto_id)
    if "categoria_id" in cambios:
        _get(db, Categoria, cambios["categoria_id"], "No existe esa categoría")
    _aplicar(producto, cambios)
    db.commit()
    return producto


def crear_presentacion(
    db: Session, producto_id: int, datos: Mapping[str, Any]
) -> Presentacion:
    producto = obtener_producto(db, producto_id)
    presentacion = Presentacion(producto=producto, **datos)
    db.add(presentacion)
    db.commit()
    return presentacion


def editar_presentacion(
    db: Session, presentacion_id: int, cambios: Mapping[str, Any]
) -> Presentacion:
    presentacion = _get(db, Presentacion, presentacion_id, "No existe esa presentación")
    _aplicar(presentacion, cambios)
    db.commit()
    return presentacion


def crear_grupo(db: Session, datos: Mapping[str, Any]) -> GrupoModificadores:
    _nombre_libre(db, GrupoModificadores, datos["nombre"])
    grupo = GrupoModificadores(**datos)
    db.add(grupo)
    db.commit()
    return grupo


def editar_grupo(
    db: Session, grupo_id: int, cambios: Mapping[str, Any]
) -> GrupoModificadores:
    grupo = _get(db, GrupoModificadores, grupo_id, "No existe ese grupo")
    if "nombre" in cambios:
        _nombre_libre(db, GrupoModificadores, cambios["nombre"], excepto=grupo_id)
    _aplicar(grupo, cambios)
    db.commit()
    return grupo


def crear_modificador(
    db: Session, grupo_id: int, datos: Mapping[str, Any]
) -> Modificador:
    grupo = _get(db, GrupoModificadores, grupo_id, "No existe ese grupo")
    mod = Modificador(grupo=grupo, **datos)
    db.add(mod)
    db.commit()
    return mod


def editar_modificador(
    db: Session, modificador_id: int, cambios: Mapping[str, Any]
) -> Modificador:
    mod = _get(db, Modificador, modificador_id, "No existe esa opción")
    _aplicar(mod, cambios)
    db.commit()
    return mod


def _validar_liga(db: Session, liga: ProductoGrupo, excluidos: list[int] | None):
    if liga.maximo is not None and liga.maximo < liga.minimo:
        raise DatosInvalidos("El máximo no puede ser menor que el mínimo")
    if liga.maximo is not None and liga.incluidas > liga.maximo:
        raise DatosInvalidos("No puede haber más incluidas que el máximo")
    if liga.presentacion_id is not None:
        pres = db.get(Presentacion, liga.presentacion_id)
        if pres is None or pres.producto_id != liga.producto_id:
            raise DatosInvalidos("La presentación no es de este producto")
    repetida = db.scalar(
        select(ProductoGrupo.id).where(
            ProductoGrupo.producto_id == liga.producto_id,
            ProductoGrupo.grupo_id == liga.grupo_id,
            ProductoGrupo.presentacion_id.is_(None)
            if liga.presentacion_id is None
            else ProductoGrupo.presentacion_id == liga.presentacion_id,
            ProductoGrupo.id != (liga.id or 0),
        )
    )
    if repetida is not None:
        raise Conflicto("Ese grupo ya está ligado al producto")
    if excluidos is not None:
        grupo = _get(db, GrupoModificadores, liga.grupo_id, "No existe ese grupo")
        validos = {m.id: m for m in grupo.modificadores}
        ajenos = [i for i in excluidos if i not in validos]
        if ajenos:
            raise DatosInvalidos(
                "Hay opciones excluidas que no son del grupo",
                [str(i) for i in ajenos],
            )
        liga.excluidos = [validos[i] for i in dict.fromkeys(excluidos)]


def ligar_grupo(
    db: Session, producto_id: int, datos: Mapping[str, Any]
) -> ProductoGrupo:
    producto = obtener_producto(db, producto_id)
    datos = dict(datos)
    excluidos = datos.pop("excluidos", [])
    _get(db, GrupoModificadores, datos["grupo_id"], "No existe ese grupo")
    liga = ProductoGrupo(producto_id=producto.id, **datos)
    with db.no_autoflush:
        _validar_liga(db, liga, excluidos)
    producto.grupos.append(liga)
    db.commit()
    return liga


def editar_liga(db: Session, liga_id: int, cambios: Mapping[str, Any]) -> ProductoGrupo:
    liga = _get(db, ProductoGrupo, liga_id, "No existe esa liga")
    cambios = dict(cambios)
    excluidos = cambios.pop("excluidos", None)
    if "grupo_id" in cambios:
        _get(db, GrupoModificadores, cambios["grupo_id"], "No existe ese grupo")
        if excluidos is None:
            excluidos = []  # las exclusiones del grupo anterior ya no aplican
    with db.no_autoflush:
        _aplicar(liga, cambios)
        _validar_liga(db, liga, excluidos)
    db.commit()
    return liga


def quitar_liga(db: Session, liga_id: int) -> None:
    liga = _get(db, ProductoGrupo, liga_id, "No existe esa liga")
    db.delete(liga)
    db.commit()
