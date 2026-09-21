"""
Carga la clave SAT del Excel de partes en los productos de almacén que ya existen.

Objetivo de negocio:
    Contabilidad entregó la ClaveProdServ de cada parte. Hay que escribirla
    en ProductoAlmacen.clave_sat para que el PUE de contado la use. No se
    crean productos nuevos y no se toca la columna "activa" del archivo.

Uso:
    python scripts/mantenimiento/cargar_claves_sat_productos.py RUTA.xlsx
    python scripts/mantenimiento/cargar_claves_sat_productos.py RUTA.xlsx --aplicar
    python scripts/mantenimiento/cargar_claves_sat_productos.py RUTA.xlsx --aplicar --forzar

Sin --aplicar solo imprime el contraste. --forzar pisa una clave distinta
que el producto ya tuviera.

Efectos secundarios:
    Con --aplicar hace UPDATE de clave_sat en la base del país por defecto
    (México / default). No borra productos ni claves.
"""

import argparse
import os
import re
import sys
import unicodedata
from pathlib import Path

import django

# El script vive en scripts/mantenimiento/; config está en la raíz del proyecto.
RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ_PROYECTO))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from almacen.models import ProductoAlmacen  # noqa: E402


def normalizar_nombre(texto: str) -> str:
    """
    Deja dos nombres comparables: mayúsculas, sin acentos, slash uniforme.

    Args:
        texto: nombre del Excel o del producto.

    Returns:
        str listo para comparar.
    """
    plano = unicodedata.normalize('NFD', str(texto or ''))
    sin_acentos = ''.join(
        caracter for caracter in plano
        if unicodedata.category(caracter) != 'Mn'
    )
    nombre = sin_acentos.upper().strip()
    nombre = nombre.replace('"', '').replace("'", '')
    # "LCD O DISPLAY" en el Excel es "LCD / DISPLAY" en el catálogo.
    nombre = nombre.replace(' O ', ' / ')
    nombre = re.sub(r'\s*/\s*', '/', nombre)
    return re.sub(r'\s+', ' ', nombre)


def nombre_compacto(texto: str) -> str:
    """
    Solo letras y números, para casos como 'USB 32 GB' y 'USB 32GB'.

    Args:
        texto: nombre ya leído del Excel o del producto.

    Returns:
        str sin espacios ni signos.
    """
    return re.sub(r'[^A-Z0-9]', '', normalizar_nombre(texto))


def clave_de_ocho_digitos(valor) -> str:
    """
    Convierte la celda del Excel en 8 dígitos, o '' si no es una clave válida.

    Args:
        valor: int, float o texto de la columna codigo_sat.

    Returns:
        str de 8 dígitos, o cadena vacía si hay letras o el largo no cuadra.
    """
    if valor is None:
        return ''
    if isinstance(valor, float) and valor.is_integer():
        texto = str(int(valor))
    elif isinstance(valor, int):
        texto = str(valor)
    else:
        texto = str(valor).strip()
    # 43211600 llega como número y hay que rellenar a 8. 432116OO no es clave.
    if texto.isdigit():
        texto = texto.zfill(8)
    if re.fullmatch(r'\d{8}', texto):
        return texto
    return ''


def leer_filas(ruta: Path) -> list[tuple[str, str, str]]:
    """
    Lee codigo_sat y descripcion. Ignora la columna activa.

    Args:
        ruta: archivo .xlsx.

    Returns:
        Lista de (clave, nombre_normalizado, descripcion_original).
        La clave va vacía cuando la celda no tiene 8 dígitos.

    Efectos secundarios:
        Abre el archivo. No toca la base.
    """
    import openpyxl

    libro = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    hoja = libro.active
    filas = []
    for numero, fila in enumerate(hoja.iter_rows(values_only=True), start=1):
        if numero == 1:
            continue
        if not fila or fila[1] in (None, ''):
            continue
        descripcion = str(fila[1])
        filas.append((
            clave_de_ocho_digitos(fila[0]),
            normalizar_nombre(descripcion),
            descripcion.strip(),
        ))
    libro.close()
    return filas


def indice_productos(productos) -> tuple[dict, dict]:
    """
    Arma dos diccionarios: nombre normalizado y nombre compacto.

    Args:
        productos: queryset o lista de ProductoAlmacen.

    Returns:
        (por_nombre, por_compacto). El valor es la lista de productos
        que comparten esa llave. Más de uno es ambigüedad.
    """
    por_nombre: dict[str, list] = {}
    por_compacto: dict[str, list] = {}
    for producto in productos:
        por_nombre.setdefault(normalizar_nombre(producto.nombre), []).append(producto)
        por_compacto.setdefault(nombre_compacto(producto.nombre), []).append(producto)
    return por_nombre, por_compacto


def producto_unico(candidatos: list):
    """
    Devuelve el producto si hay exactamente uno.

    Args:
        candidatos: productos que empataron con la fila.

    Returns:
        ProductoAlmacen o None.
    """
    if len(candidatos) == 1:
        return candidatos[0]
    return None


def contrastar(filas, productos) -> dict:
    """
    Cruza cada fila del Excel con el catálogo, sin escribir.

    Args:
        filas: lo que devolvió leer_filas.
        productos: productos actuales.

    Returns:
        dict con listas: actualizar, iguales, conflicto, invalidas,
        sin_producto, ambiguas, productos_sin_fila.
    """
    por_nombre, por_compacto = indice_productos(productos)
    actualizar = []
    iguales = []
    conflicto = []
    invalidas = []
    sin_producto = []
    ambiguas = []
    usados = set()
    # Una misma pieza puede venir dos veces. La segunda no debe contradecir.
    clave_por_producto: dict[int, str] = {}

    for clave, nombre, original in filas:
        if not clave:
            invalidas.append(original)
            continue
        candidatos = por_nombre.get(nombre, [])
        # Paso: si el slash y los espacios impiden el exacto, probamos
        # la forma compacta, pero solo cuando apunta a un solo producto.
        if not candidatos:
            candidatos = por_compacto.get(nombre_compacto(original), [])
        if len(candidatos) > 1:
            ambiguas.append((original, [item.nombre for item in candidatos]))
            continue
        producto = producto_unico(candidatos)
        if producto is None:
            sin_producto.append(original)
            continue
        previa = clave_por_producto.get(producto.pk)
        if previa and previa != clave:
            # La misma pieza vino dos veces con claves distintas: no se escribe.
            conflicto.append((producto, clave, previa))
            actualizar[:] = [
                par for par in actualizar if par[0].pk != producto.pk
            ]
            continue
        if previa == clave:
            continue
        clave_por_producto[producto.pk] = clave
        usados.add(producto.pk)
        actual = (producto.clave_sat or '').strip()
        if actual == clave:
            iguales.append(producto)
        elif actual and actual != clave:
            conflicto.append((producto, clave, actual))
        else:
            actualizar.append((producto, clave))

    sin_fila = [item for item in productos if item.pk not in usados]
    return {
        'actualizar': actualizar,
        'iguales': iguales,
        'conflicto': conflicto,
        'invalidas': invalidas,
        'sin_producto': sin_producto,
        'ambiguas': ambiguas,
        'productos_sin_fila': sin_fila,
    }


def imprimir_reporte(reporte: dict, aplicar: bool) -> None:
    """
    Muestra el contraste en cuatro bloques, más los casos que no se escriben.

    Args:
        reporte: resultado de contrastar.
        aplicar: True si esta corrida va a guardar.

    Efectos secundarios:
        Solo imprime.
    """
    modo = 'APLICAR' if aplicar else 'SOLO INFORME'
    print(f'=== {modo} ===')
    print(f"Se van a cargar: {len(reporte['actualizar'])}")
    for producto, clave in reporte['actualizar']:
        print(f"  {clave}  {producto.codigo_producto}  {producto.nombre}")
    print(f"Ya tenían esa clave: {len(reporte['iguales'])}")
    print(f"Excel sin producto en la base: {len(reporte['sin_producto'])}")
    for nombre in reporte['sin_producto']:
        print(f"  - {nombre}")
    print(f"Productos sin fila segura en el Excel: {len(reporte['productos_sin_fila'])}")
    for producto in reporte['productos_sin_fila']:
        print(f"  - {producto.codigo_producto}  {producto.nombre}")
    if reporte['invalidas']:
        print(f"Claves inválidas (no se guardan): {len(reporte['invalidas'])}")
        for nombre in reporte['invalidas']:
            print(f"  - {nombre}")
    if reporte['conflicto']:
        print(f"No se pisan claves distintas: {len(reporte['conflicto'])}")
        for producto, nueva, actual in reporte['conflicto']:
            print(f"  {producto.nombre}: tiene {actual}, el Excel dice {nueva}")
    if reporte['ambiguas']:
        print(f"Nombres que empatan con más de un producto: {len(reporte['ambiguas'])}")


def aplicar_claves(pares: list[tuple], forzar: bool) -> int:
    """
    Escribe clave_sat en los productos emparejados.

    Args:
        pares: lista de (producto, clave).
        forzar: si True, también reemplaza una clave distinta.
            Hoy contrastar ya dejó fuera esos casos cuando forzar es False.

    Returns:
        Cuántos productos se actualizaron.

    Efectos secundarios:
        UPDATE de clave_sat. No crea filas.
    """
    cambiados = 0
    for producto, clave in pares:
        actual = (producto.clave_sat or '').strip()
        if actual == clave:
            continue
        if actual and not forzar:
            continue
        producto.clave_sat = clave
        producto.save(update_fields=['clave_sat'])
        cambiados += 1
    return cambiados


def main() -> None:
    """
    Lee el Excel, contrasta y, si se pidió, guarda las claves.

    Efectos secundarios:
        Con --aplicar, UPDATE en la base default.
    """
    parser = argparse.ArgumentParser(
        description='Carga claves SAT del Excel en productos de almacén existentes.',
    )
    parser.add_argument('excel', help='Ruta al .xlsx (columnas codigo_sat, descripcion)')
    parser.add_argument(
        '--aplicar',
        action='store_true',
        help='Escribe las claves. Sin esta bandera solo informa.',
    )
    parser.add_argument(
        '--forzar',
        action='store_true',
        help='Reemplaza una clave distinta que el producto ya tenga.',
    )
    args = parser.parse_args()
    ruta = Path(args.excel)
    if not ruta.is_file():
        print(f'No existe el archivo: {ruta}')
        sys.exit(1)

    filas = leer_filas(ruta)
    productos = list(ProductoAlmacen.objects.all())
    reporte = contrastar(filas, productos)
    # --forzar vuelve a meter en "actualizar" los que tenían otra clave.
    if args.forzar:
        for producto, nueva, _actual in list(reporte['conflicto']):
            reporte['actualizar'].append((producto, nueva))
        reporte['conflicto'] = []
    imprimir_reporte(reporte, args.aplicar)
    if not args.aplicar:
        print('Nada se escribió. Vuelve a correr con --aplicar para guardar.')
        return
    cambiados = aplicar_claves(reporte['actualizar'], forzar=True)
    print(f'Productos actualizados: {cambiados}')


if __name__ == '__main__':
    main()
