"""
Consulta de productos activos del catálogo de almacén.

EXPLICACIÓN PARA PRINCIPIANTES:
-------------------------------
La pantalla de productos y el botón de Excel tienen que mostrar la misma
lista. Si cada uno arma su propio filtro, un día el Excel trae filas que
la pantalla ya no enseña (o al revés). Este módulo es el único lugar
donde se decide qué producto activo entra.
"""

from django.db.models import F, Q

from almacen.forms import BusquedaProductoForm
from almacen.models import ProductoAlmacen


def queryset_productos_activos(parametros_get, *, aplicar_clave_sat=True):
    """
    Arma la lista de productos activos según los filtros de la pantalla.

    Objetivo de negocio:
        La tabla y la descarga Excel parten del mismo conjunto: solo
        productos activos, y solo los que cumplen búsqueda, tipo,
        categoría, stock y clave SAT.

    Args:
        parametros_get: request.GET (o un dict con las mismas claves).
            Claves usadas: q, tipo, categoria, stock, clave_sat.
            `page` se ignora: la paginación no recorta esta consulta.
        aplicar_clave_sat: si es False, deja fuera el filtro de clave SAT.
            La pantalla lo usa así para contar los badges «con clave» y
            «sin clave» antes de recortar la tabla.

    Returns:
        QuerySet de ProductoAlmacen, con categoría, proveedor y sucursal
        ya cargados. Si el formulario trae un valor imposible, regresa
        todos los activos (igual que la lista cuando el form no valida).

    Efectos secundarios:
        Ninguno. Solo lee la base de datos cuando alguien evalúa el QuerySet.
    """
    # Paso 1: el catálogo público del almacén son los productos activos.
    productos = ProductoAlmacen.objects.filter(activo=True).select_related(
        'categoria', 'proveedor_principal', 'sucursal',
    )

    # Paso 2: las mismas reglas del formulario de la lista. Un valor
    # inválido (categoría que no existe, stock desconocido) no filtra nada.
    formulario = BusquedaProductoForm(parametros_get)
    if not formulario.is_valid():
        return productos

    productos = _filtrar_texto_tipo_categoria_stock(productos, formulario)
    if not aplicar_clave_sat:
        return productos

    # Paso 3: la clave SAT se aplica al final. Así quien cuenta badges
    # puede pedir el mismo queryset un paso antes.
    return _filtrar_clave_sat(productos, formulario.cleaned_data.get('clave_sat'))


def _filtrar_texto_tipo_categoria_stock(productos, formulario):
    """
    Aplica búsqueda, tipo, categoría y stock. No toca la clave SAT.

    Args:
        productos: QuerySet de productos activos.
        formulario: BusquedaProductoForm ya validado.

    Returns:
        QuerySet recortado. Puede ser el mismo si ningún filtro trae valor.

    Efectos secundarios:
        Ninguno.
    """
    datos = formulario.cleaned_data

    # Texto libre: código, nombre, descripción o la propia clave SAT.
    texto = datos.get('q')
    if texto:
        productos = productos.filter(
            Q(codigo_producto__icontains=texto)
            | Q(nombre__icontains=texto)
            | Q(descripcion__icontains=texto)
            | Q(clave_sat__icontains=texto)
        )

    tipo = datos.get('tipo')
    if tipo:
        productos = productos.filter(tipo_producto=tipo)

    categoria = datos.get('categoria')
    if categoria:
        productos = productos.filter(categoria=categoria)

    # Stock bajo solo aplica a resurtibles: un único no tiene mínimo.
    stock = datos.get('stock')
    if stock == 'bajo':
        productos = productos.filter(
            tipo_producto='resurtible',
            stock_actual__lte=F('stock_minimo'),
        )
    elif stock == 'agotado':
        productos = productos.filter(stock_actual=0)
    elif stock == 'disponible':
        productos = productos.filter(stock_actual__gt=0)

    return productos


def _filtrar_clave_sat(productos, clave_sat):
    """
    Deja solo productos con clave SAT, solo los vacíos, o todos.

    Args:
        productos: QuerySet ya filtrado por el resto de la pantalla.
        clave_sat: 'con', 'sin' o vacío (todas).

    Returns:
        QuerySet. Vacío o cualquier otro valor no recorta.

    Efectos secundarios:
        Ninguno.
    """
    if clave_sat == 'con':
        return productos.exclude(clave_sat='')
    if clave_sat == 'sin':
        return productos.filter(clave_sat='')
    return productos
