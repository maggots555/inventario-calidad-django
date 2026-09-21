"""
Importa el Excel de productos activos al catálogo local.

EXPLICACIÓN PARA PRINCIPIANTES:
-------------------------------
El archivo es el mismo que descarga la pantalla de productos. Este módulo
lo lee y deja la base de pruebas con esos productos activos: crea los que
faltan, actualiza los que cambiaron y desactiva los que ya no vienen.
No borra filas, porque un producto puede tener compras o unidades.
"""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.db import router, transaction
from openpyxl import load_workbook

from almacen.models import CategoriaAlmacen, ProductoAlmacen, Proveedor
from config.constants import TIPO_PRODUCTO_ALMACEN_CHOICES
from inventario.models import Sucursal


# El Excel escribe el texto largo del tipo. También aceptamos el código corto.
_TIPO_POR_ETIQUETA = {
    etiqueta.casefold(): codigo
    for codigo, etiqueta in TIPO_PRODUCTO_ALMACEN_CHOICES
}
_TIPO_POR_ETIQUETA.update({
    codigo.casefold(): codigo
    for codigo, _etiqueta in TIPO_PRODUCTO_ALMACEN_CHOICES
})

# «Almacén central» no es una sucursal: en el modelo el campo va vacío.
_SUCURSAL_CENTRAL = {'almacén central', 'almacen central'}

_COLUMNAS = (
    'Código',
    'Nombre',
    'Descripción',
    'Tipo',
    'Categoría',
    'Sucursal',
    'Ubicación física',
    'Stock actual',
    'Stock mínimo',
    'Stock máximo',
    'Clave SAT',
    'Costo unitario',
    'Proveedor',
    'Días de reposición',
)

# Estos campos se comparan para no guardar una fila que ya está igual.
_CAMPOS_CATALOGO = (
    'nombre',
    'descripcion',
    'tipo_producto',
    'categoria_id',
    'sucursal_id',
    'ubicacion_fisica',
    'stock_actual',
    'stock_minimo',
    'stock_maximo',
    'clave_sat',
    'costo_unitario',
    'proveedor_principal_id',
    'tiempo_reposicion_dias',
    'activo',
)


class ErrorImportacionProductos(Exception):
    """
    El Excel no se puede aplicar. La transacción no guarda nada.

    Objetivo de negocio:
        Una clave SAT mal escrita o una sucursal desconocida no debe
        dejar el catálogo a medias.

    Efectos secundarios:
        Ninguno. Solo transporta el mensaje.
    """


@dataclass
class ResultadoImportacion:
    """
    Resumen de una importación que sí se guardó.

    Objetivo de negocio:
        Quien corre el comando ve cuántos productos entraron, cambiaron
        o se ocultaron, sin abrir la base a mano.
    """

    creados: list = field(default_factory=list)
    actualizados: list = field(default_factory=list)
    iguales: list = field(default_factory=list)
    desactivados: list = field(default_factory=list)
    proveedores_creados: list = field(default_factory=list)
    categorias_creadas: list = field(default_factory=list)


def importar_productos_activos(ruta, db_alias=None):
    """
    Deja el catálogo activo igual al Excel.

    Objetivo de negocio:
        La base de pruebas muestra los mismos productos activos que
        producción descargó, sin borrar historial local.

    Args:
        ruta: camino del .xlsx (hoja con la fila de encabezados).
        db_alias: alias de Django. None usa la base de escritura del
            producto (en manage.py, sin país en el request, es default).

    Returns:
        ResultadoImportacion.

    Efectos secundarios:
        Crea o actualiza ProductoAlmacen, y si hace falta CategoriaAlmacen
        y Proveedor. Desactiva (activo=False) los activos cuyo código no
        está en el archivo. Una sola transacción: si una fila falla, no
        queda ningún cambio de esta corrida.
    """
    if db_alias is None:
        db_alias = router.db_for_write(ProductoAlmacen) or 'default'

    # Primero se lee el archivo entero. Un encabezado mal puesto no abre
    # transacción ni toca la base.
    filas = _leer_filas(ruta)
    with transaction.atomic(using=db_alias):
        return _aplicar(filas, db_alias)


def _leer_filas(ruta):
    """
    Lee las filas de datos y rechaza códigos repetidos o columnas faltantes.

    Args:
        ruta: camino del .xlsx.

    Returns:
        list[dict]: cada dict trae 'fila' (número de Excel) y el texto
        de las columnas, todavía sin buscar categoría ni proveedor.

    Efectos secundarios:
        Ninguno sobre la base. Abre el archivo y lo cierra.
    """
    libro = load_workbook(ruta, read_only=True, data_only=True)
    try:
        hoja = libro.active
        filas = hoja.iter_rows(values_only=True)
        try:
            encabezados = next(filas)
        except StopIteration as exc:
            raise ErrorImportacionProductos('El archivo no tiene encabezados.') from exc

        # Paso 1: el Excel de la pantalla trae estos nombres. Si falta uno,
        # no adivinamos la columna.
        posiciones = _posiciones(encabezados)
        leidas = []
        vistos = set()
        for numero, valores in enumerate(filas, start=2):
            if _fila_vacia(valores):
                continue
            registro = {
                columna: _texto_celda(valores, posiciones[columna])
                for columna in _COLUMNAS
            }
            registro['fila'] = numero
            codigo = registro['Código']
            if not codigo:
                raise ErrorImportacionProductos(
                    f'Fila {numero}: el código está vacío.'
                )
            if len(codigo) > 50:
                raise ErrorImportacionProductos(
                    f'Fila {numero}: el código "{codigo}" pasa de 50 caracteres.'
                )
            if codigo in vistos:
                raise ErrorImportacionProductos(
                    f'Fila {numero}: el código "{codigo}" está repetido.'
                )
            vistos.add(codigo)
            leidas.append(registro)
        # Un archivo sin filas desactivaría todo el catálogo. Eso no es una
        # importación: es un error de archivo.
        if not leidas:
            raise ErrorImportacionProductos('El archivo no trae productos.')
        return leidas
    finally:
        libro.close()


def _aplicar(filas, db_alias):
    """
    Crea, actualiza y desactiva dentro de la transacción ya abierta.

    Args:
        filas: lo que devolvió _leer_filas.
        db_alias: alias de la conexión de la transacción.

    Returns:
        ResultadoImportacion.

    Efectos secundarios:
        Escribe productos, categorías y proveedores en db_alias.
    """
    resultado = ResultadoImportacion()
    categorias = {}
    proveedores = {}
    sucursales = {}
    codigos_del_archivo = []

    for registro in filas:
        codigo = registro['Código']
        codigos_del_archivo.append(codigo)
        datos = _datos_de_fila(
            registro, db_alias, categorias, proveedores, sucursales, resultado,
        )
        _guardar_producto(codigo, datos, db_alias, resultado)

    # Los activos que el archivo ya no trae se ocultan. No se borran:
    # pueden tener compras, unidades o líneas de cotización.
    sobrantes = (
        ProductoAlmacen.objects.using(db_alias)
        .filter(activo=True)
        .exclude(codigo_producto__in=codigos_del_archivo)
        .order_by('codigo_producto')
    )
    resultado.desactivados = list(sobrantes.values_list('codigo_producto', flat=True))
    sobrantes.update(activo=False)
    return resultado


def _datos_de_fila(registro, db_alias, categorias, proveedores, sucursales, resultado):
    """
    Traduce una fila del Excel a valores listos para el modelo.

    Args:
        registro: dict de _leer_filas.
        db_alias: alias de la base.
        categorias, proveedores, sucursales: cachés de esta corrida.
        resultado: acumula categorías y proveedores creados.

    Returns:
        dict con los campos de ProductoAlmacen que sí vienen en el archivo.

    Efectos secundarios:
        Puede crear una categoría o un proveedor si el nombre no existe.
    """
    fila = registro['fila']
    codigo = registro['Código']
    tipo = _TIPO_POR_ETIQUETA.get(registro['Tipo'].casefold())
    if tipo is None:
        raise ErrorImportacionProductos(
            f'Fila {fila} ({codigo}): tipo desconocido "{registro["Tipo"]}".'
        )

    # La clave vacía es válida. Si trae dígitos, el modelo pide exactamente 8.
    clave = _clave_sat(registro['Clave SAT'], fila, codigo)
    return {
        'nombre': _exigir_texto(registro['Nombre'], 'nombre', fila, codigo, 200),
        'descripcion': registro['Descripción'],
        'tipo_producto': tipo,
        'categoria': _categoria(
            registro['Categoría'], db_alias, categorias, resultado,
        ),
        'sucursal': _sucursal(
            registro['Sucursal'], db_alias, sucursales, fila, codigo,
        ),
        'ubicacion_fisica': _exigir_texto(
            registro['Ubicación física'], 'ubicación', fila, codigo, 50, obligatorio=False,
        ),
        'stock_actual': _entero(registro['Stock actual'], 'stock actual', fila, codigo),
        'stock_minimo': _entero(registro['Stock mínimo'], 'stock mínimo', fila, codigo),
        'stock_maximo': _entero(registro['Stock máximo'], 'stock máximo', fila, codigo),
        'clave_sat': clave,
        'costo_unitario': _dinero(registro['Costo unitario'], fila, codigo),
        'proveedor_principal': _proveedor(
            registro['Proveedor'], db_alias, proveedores, resultado,
        ),
        'tiempo_reposicion_dias': _entero(
            registro['Días de reposición'], 'días de reposición', fila, codigo,
        ),
        'activo': True,
    }


def _guardar_producto(codigo, datos, db_alias, resultado):
    """
    Crea el producto o lo actualiza solo si algún campo cambió.

    Args:
        codigo: codigo_producto.
        datos: dict de _datos_de_fila.
        db_alias: alias de la base.
        resultado: listas de creados, actualizados e iguales.

    Efectos secundarios:
        Inserta o actualiza un ProductoAlmacen.
    """
    producto = (
        ProductoAlmacen.objects.using(db_alias)
        .filter(codigo_producto=codigo)
        .first()
    )
    if producto is None:
        ProductoAlmacen.objects.using(db_alias).create(
            codigo_producto=codigo,
            **datos,
        )
        resultado.creados.append(codigo)
        return

    # Paso: armar el estado deseado y compararlo con lo que ya está guardado.
    # Si es igual, no se llama save() y la fecha de actualización no se mueve.
    deseado = {
        'categoria_id': datos['categoria'].pk if datos['categoria'] else None,
        'sucursal_id': datos['sucursal'].pk if datos['sucursal'] else None,
        'proveedor_principal_id': (
            datos['proveedor_principal'].pk if datos['proveedor_principal'] else None
        ),
    }
    for campo in _CAMPOS_CATALOGO:
        if campo in ('categoria_id', 'sucursal_id', 'proveedor_principal_id'):
            continue
        deseado[campo] = datos[campo]

    cambio = False
    for campo, valor in deseado.items():
        if getattr(producto, campo) != valor:
            setattr(producto, campo, valor)
            cambio = True
    if not cambio:
        resultado.iguales.append(codigo)
        return

    producto.save(using=db_alias, update_fields=list(deseado))
    resultado.actualizados.append(codigo)


def _posiciones(encabezados):
    """
    Ubica cada columna requerida en la fila 1.

    Args:
        encabezados: tupla de la primera fila.

    Returns:
        dict columna → índice.

    Efectos secundarios:
        Ninguno. Lanza ErrorImportacionProductos si falta una columna.
    """
    nombres = [_texto(valor) for valor in (encabezados or ())]
    posiciones = {}
    faltan = []
    for columna in _COLUMNAS:
        if columna not in nombres:
            faltan.append(columna)
        else:
            posiciones[columna] = nombres.index(columna)
    if faltan:
        raise ErrorImportacionProductos(
            'Faltan columnas: ' + ', '.join(faltan)
        )
    return posiciones


def _categoria(nombre, db_alias, cache, resultado):
    """
    Busca la categoría por nombre y la crea si el Excel trae una nueva.

    Args:
        nombre: texto de la celda. Vacío = sin categoría.
        db_alias: alias de la base.
        cache: nombre → CategoriaAlmacen de esta corrida.
        resultado: recibe el nombre si se crea.

    Returns:
        CategoriaAlmacen o None.

    Efectos secundarios:
        Puede insertar una categoría.
    """
    if not nombre:
        return None
    if nombre in cache:
        return cache[nombre]
    categoria, creada = CategoriaAlmacen.objects.using(db_alias).get_or_create(
        nombre=nombre,
    )
    cache[nombre] = categoria
    if creada:
        resultado.categorias_creadas.append(nombre)
    return categoria


def _proveedor(nombre, db_alias, cache, resultado):
    """
    Busca el proveedor por nombre. Si no existe, lo crea solo con el nombre.

    Args:
        nombre: texto de la celda. Vacío = sin proveedor.
        db_alias: alias de la base.
        cache: nombre → Proveedor de esta corrida.
        resultado: recibe el nombre si se crea.

    Returns:
        Proveedor o None.

    Efectos secundarios:
        Puede insertar un proveedor sin teléfono ni correo.
    """
    if not nombre:
        return None
    if nombre in cache:
        return cache[nombre]
    proveedor, creado = Proveedor.objects.using(db_alias).get_or_create(
        nombre=nombre,
    )
    cache[nombre] = proveedor
    if creado:
        resultado.proveedores_creados.append(nombre)
    return proveedor


def _sucursal(nombre, db_alias, cache, fila, codigo):
    """
    Resuelve la sucursal. «Almacén central» y vacío significan sin sucursal.

    Args:
        nombre: texto de la celda.
        db_alias: alias de la base.
        cache: nombre → Sucursal o None.
        fila: número de fila del Excel, para el mensaje de error.
        codigo: código del producto.

    Returns:
        Sucursal o None.

    Efectos secundarios:
        Ninguno. Si el nombre no existe, detiene toda la importación.
    """
    if not nombre or nombre.casefold() in _SUCURSAL_CENTRAL:
        return None
    if nombre in cache:
        return cache[nombre]
    sucursal = (
        Sucursal.objects.using(db_alias)
        .filter(nombre__iexact=nombre)
        .first()
    )
    if sucursal is None:
        raise ErrorImportacionProductos(
            f'Fila {fila} ({codigo}): no existe la sucursal "{nombre}".'
        )
    cache[nombre] = sucursal
    return sucursal


def _clave_sat(valor, fila, codigo):
    """
    Normaliza la clave SAT a 8 dígitos o a vacío.

    Args:
        valor: texto ya leído de la celda. Un número de Excel llega como
            texto sin decimales (43211600, no 43211600.0).
        fila: número de fila.
        codigo: código del producto.

    Returns:
        str de 8 dígitos, o '' si la celda está vacía.

    Efectos secundarios:
        Ninguno. Lanza ErrorImportacionProductos si no son dígitos.
    """
    if not valor:
        return ''
    digitos = valor
    if digitos.endswith('.0') and digitos[:-2].isdigit():
        digitos = digitos[:-2]
    if not digitos.isdigit() or len(digitos) > 8:
        raise ErrorImportacionProductos(
            f'Fila {fila} ({codigo}): la clave SAT "{valor}" no tiene 8 dígitos.'
        )
    return digitos.zfill(8)


def _entero(valor, campo, fila, codigo):
    """
    Convierte una celda numérica a entero mayor o igual a cero.

    Args:
        valor: texto de la celda. Vacío cuenta como 0.
        campo: nombre en español para el mensaje.
        fila: número de fila.
        codigo: código del producto.

    Returns:
        int.

    Efectos secundarios:
        Ninguno.
    """
    if valor == '':
        return 0
    try:
        numero = Decimal(valor)
    except InvalidOperation as exc:
        raise ErrorImportacionProductos(
            f'Fila {fila} ({codigo}): {campo} no es un número ({valor}).'
        ) from exc
    if numero != numero.to_integral_value() or numero < 0:
        raise ErrorImportacionProductos(
            f'Fila {fila} ({codigo}): {campo} debe ser un entero de 0 para arriba.'
        )
    return int(numero)


def _dinero(valor, fila, codigo):
    """
    Convierte el costo a Decimal de dos decimales.

    Args:
        valor: texto de la celda. Vacío cuenta como 0.
        fila: número de fila.
        codigo: código del producto.

    Returns:
        Decimal.

    Efectos secundarios:
        Ninguno.
    """
    if valor == '':
        return Decimal('0.00')
    try:
        numero = Decimal(valor)
    except InvalidOperation as exc:
        raise ErrorImportacionProductos(
            f'Fila {fila} ({codigo}): el costo no es un número ({valor}).'
        ) from exc
    if numero < 0:
        raise ErrorImportacionProductos(
            f'Fila {fila} ({codigo}): el costo no puede ser negativo.'
        )
    return numero.quantize(Decimal('0.01'))


def _exigir_texto(valor, campo, fila, codigo, maximo, obligatorio=True):
    """
    Recorta espacios y rechaza un texto más largo de lo que cabe en el campo.

    Args:
        valor: texto de la celda.
        campo: nombre en español para el mensaje.
        fila: número de fila.
        codigo: código del producto.
        maximo: largo máximo del campo.
        obligatorio: si es True, el vacío también es error.

    Returns:
        str.

    Efectos secundarios:
        Ninguno.
    """
    if obligatorio and not valor:
        raise ErrorImportacionProductos(
            f'Fila {fila} ({codigo}): el {campo} está vacío.'
        )
    if len(valor) > maximo:
        raise ErrorImportacionProductos(
            f'Fila {fila} ({codigo}): el {campo} pasa de {maximo} caracteres.'
        )
    return valor


def _texto_celda(valores, indice):
    """
    Lee una celda y la deja como texto sin espacios de más.

    Args:
        valores: tupla de la fila.
        indice: posición de la columna.

    Returns:
        str. Vacío si la celda no existe o está en blanco.

    Efectos secundarios:
        Ninguno.
    """
    if indice >= len(valores):
        return ''
    return _texto(valores[indice])


def _texto(valor):
    """
    Convierte una celda de Excel a texto.

    Un número entero que Excel guardó como 43211600.0 vuelve como
    '43211600', para no perder ceros ni colar el decimal.

    Args:
        valor: cualquier valor de openpyxl, o None.

    Returns:
        str sin espacios alrededor.

    Efectos secundarios:
        Ninguno.
    """
    if valor is None:
        return ''
    if isinstance(valor, bool):
        return str(valor)
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    if isinstance(valor, int):
        return str(valor)
    return str(valor).strip()


def _fila_vacia(valores):
    """
    Dice si la fila no trae ningún dato.

    Args:
        valores: tupla de openpyxl.

    Returns:
        bool.

    Efectos secundarios:
        Ninguno.
    """
    return all(_texto(valor) == '' for valor in valores)
