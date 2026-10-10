"""
Nombres de archivo que no se pueden adivinar.

EXPLICACIÓN PARA PRINCIPIANTES:
firma_cliente.png siempre se llamaba igual. Quien conocía el folio
podía pedir esa URL. Los archivos NUEVOS llevan un sufijo aleatorio.
Los viejos siguen en disco con el nombre fijo, pero solo se entregan
si Django autorizó la petición.
"""

import secrets


def nombre_archivo_privado(prefijo: str, extension: str = '.png') -> str:
    """
    Arma un nombre de archivo con un sufijo que no se puede adivinar.

    Objetivo de negocio:
        Firmas y capturas dejan de tener un nombre fijo
        (firma_cliente.png). Aunque alguien conozca la carpeta de la
        orden, no adivina el archivo. La autorización de /media/
        sigue siendo la barrera principal.

    Args:
        prefijo: Texto corto sin carpetas, por ejemplo ``firma_cliente``.
        extension: Incluye el punto, por ejemplo ``.png``.

    Returns:
        str: ``firma_cliente_<16 hex>.png``.

    Efectos secundarios:
        Ninguno. No toca el disco; solo inventa el nombre.
    """
    limpio = (prefijo or 'archivo').strip().replace('/', '').replace('\\', '')
    if not extension.startswith('.'):
        extension = f'.{extension}'
    return f'{limpio}_{secrets.token_hex(8)}{extension}'
