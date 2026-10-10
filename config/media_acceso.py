"""
Quién puede ver un archivo de /media/.

EXPLICACIÓN PARA PRINCIPIANTES:
Antes Nginx entregaba cualquier foto si alguien adivinaba la carpeta
(el folio de la orden + firma_cliente.png). Ahora la petición pasa por
aquí primero.

Tres puertas:
1. Los banners de publicidad (carpeta banners/) siguen públicos.
2. El personal con sesión puede ver el resto.
3. El cliente, sin sesión, solo si trae el token vigente de SU orden
   (?t=...) y el archivo está en la carpeta de esa orden.
"""

from urllib.parse import quote


PAISES_MEDIA = ('mexico', 'argentina', 'chile', 'colombia')


def ruta_relativa_segura(path: str) -> str | None:
    """
    Limpia la ruta de la URL y rechaza la que intenta salir de media.

    Objetivo de negocio:
        Un ``../`` o un path absoluto no debe leer archivos del sistema
        (por ejemplo /etc/passwd) ni de otra carpeta del disco.

    Args:
        path: Lo que vino después de /media/ en la URL.

    Returns:
        str con segmentos unidos por /, o None si la ruta no es segura.

    Efectos secundarios:
        Ninguno.
    """
    # Paso 1: barras de Windows y sin slash inicial (un /etc/passwd
    # absoluto no se sirve).
    limpio = str(path or '').replace('\\', '/').lstrip('/')
    if not limpio or '\x00' in limpio:
        return None

    # Paso 2: cada carpeta. ".." se rechaza entero, no se "sube" un nivel.
    partes: list[str] = []
    for parte in limpio.split('/'):
        if parte in ('', '.'):
            continue
        if parte == '..':
            return None
        partes.append(parte)
    if not partes:
        return None
    return '/'.join(partes)


# Carpetas donde el nombre que sigue es el folio de UNA orden.
# El folio tiene que ir ahí, no en cualquier pedazo de la ruta:
# si el folio fuera "imagenes", no debe abrir toda la carpeta imagenes.
_PREFIJOS_DE_ORDEN = (
    'servicio_tecnico/imagenes/',
    'servicio_tecnico/imagenes_originales/',
    'servicio_tecnico/videos/',
    'servicio_tecnico/videos_thumbs/',
    'servicio_tecnico/comprobantes/',
    'servicio_tecnico/formato_oow/',
    'servicio_tecnico/formato_garantia/',
    'servicio_tecnico/formato_venta_mostrador/',
)


def _pais_de_esta_peticion() -> str:
    """
    Subcarpeta de media del país que está atendiendo esta visita.

    Args:
        Ninguno. Lee el país que dejó el middleware (mexico, argentina, ...).

    Returns:
        str: ``mexico`` si no hay visita HTTP (tests, comandos).

    Efectos secundarios:
        Ninguno.
    """
    from config.middleware_pais import get_current_pais_config
    from config.paises_config import PAIS_DEFAULT, PAISES_CONFIG

    # Paso 1: la visita ya trae país (mexico.sigmasystem.work, etc.).
    cfg = get_current_pais_config()
    if cfg and cfg.get('media_subdir'):
        return cfg['media_subdir']
    # Paso 2: sin middleware (tests). El default del proyecto es México.
    return PAISES_CONFIG.get(PAIS_DEFAULT, {}).get('media_subdir', PAIS_DEFAULT)


def _pais_y_resto(path: str) -> tuple[str | None, str] | None:
    """
    Separa la carpeta de país del resto de la ruta.

    Args:
        path: Ruta relativa bajo media.

    Returns:
        ``(pais, resto)``. ``pais`` es None en archivos viejos que no
        tienen carpeta de país. None si la ruta no es segura o se queda
        vacía después de quitar el país.

    Efectos secundarios:
        Ninguno.
    """
    limpio = ruta_relativa_segura(path)
    if limpio is None:
        return None
    partes = limpio.split('/')
    if partes[0] in PAISES_MEDIA:
        if len(partes) < 2:
            return None
        return partes[0], '/'.join(partes[1:])
    return None, limpio


def ruta_es_de_este_pais(path: str) -> bool:
    """
    True si el archivo es de este país, o es viejo y no trae carpeta de país.

    Objetivo de negocio:
        México y Argentina comparten el disco, en carpetas distintas.
        Una sesión de México no abre ``argentina/...``. El número de
        orden ``ORD-2026-0001`` existe en los dos países: sin esta
        regla, el token de uno abriría las fotos del otro.

    Args:
        path: Ruta relativa bajo media.

    Returns:
        bool.

    Efectos secundarios:
        Lee el país de la visita (memoria del hilo, no la base).
    """
    separado = _pais_y_resto(path)
    if separado is None:
        return False
    pais, _resto = separado
    if pais is None:
        return True
    return pais == _pais_de_esta_peticion()


def es_banner_publico(path: str) -> bool:
    """
    True si el archivo es un banner de publicidad de ESTE país.

    Args:
        path: Ruta relativa bajo media.

    Returns:
        bool: True solo para la carpeta banners/ del país de la visita.

    Efectos secundarios:
        Lee el país de la visita.
    """
    if not ruta_es_de_este_pais(path):
        return False
    separado = _pais_y_resto(path)
    if separado is None:
        return False
    _pais, resto = separado
    return resto.split('/', 1)[0] == 'banners'


def archivo_pertenece_a_orden(path: str, orden) -> bool:
    """
    True si alguna carpeta de la ruta es el folio de esa orden.

    Objetivo de negocio:
        El token del cliente abre las fotos de SU equipo, no el disco
        completo. El folio (orden_cliente o el número interno) es el
        nombre de la carpeta. Los CFDI viven en facturacion/<id>/.

    Args:
        path: Ruta relativa bajo media.
        orden: OrdenServicio (con detalle_equipo si ya se cargó).

    Returns:
        bool.

    Efectos secundarios:
        Ninguno. No consulta la base; usa el objeto que ya tienes.
    """
    separado = _pais_y_resto(path)
    if separado is None:
        return False
    pais, resto = separado
    # La carpeta argentina/ no se abre con un token que vive en la base de México.
    if pais is not None and pais != _pais_de_esta_peticion():
        return False

    refs = set()
    detalle = getattr(orden, 'detalle_equipo', None)
    if detalle is not None:
        folio = (getattr(detalle, 'orden_cliente', None) or '').strip()
        if folio:
            refs.add(folio)
    interno = (getattr(orden, 'numero_orden_interno', None) or '').strip()
    if interno:
        refs.add(interno)

    # Paso: el folio es la carpeta que sigue a imagenes/, videos/, firmas/, etc.
    # Tiene que haber un archivo después. No basta con que el folio aparezca
    # en el nombre del jpg.
    for prefijo in _PREFIJOS_DE_ORDEN:
        if not resto.startswith(prefijo):
            continue
        cola = resto[len(prefijo):]
        carpeta, _sep, archivo = cola.partition('/')
        if archivo and carpeta in refs:
            return True

    # CFDIs y el PDF de diagnóstico usan el id de la orden, no el folio.
    orden_id = str(getattr(orden, 'pk', '') or '')
    if not orden_id:
        return False
    if resto.startswith(f'facturacion/{orden_id}/'):
        return True
    if resto.startswith(f'seguimiento/{orden_id}/'):
        return True
    return False


def _enlace_vigente(token: str):
    """
    Busca el enlace de seguimiento si el token sigue sirviendo.

    Args:
        token: Query ?t= de la URL de la foto.

    Returns:
        EnlaceSeguimientoCliente o None.

    Efectos secundarios:
        Lee la base (una fila). No anota la visita: la página de
        seguimiento ya cuenta los accesos.
    """
    if not token:
        return None
    from servicio_tecnico.models import EnlaceSeguimientoCliente
    try:
        enlace = (
            EnlaceSeguimientoCliente.objects
            .select_related('orden__detalle_equipo')
            .get(token=token)
        )
    except EnlaceSeguimientoCliente.DoesNotExist:
        return None
    if not enlace.esta_disponible:
        return None
    return enlace


def clasificar_acceso_media(request, path: str) -> str:
    """
    Decide si esta petición puede ver el archivo.

    Objetivo de negocio:
        Evidencias, firmas y comprobantes no se descargan con solo
        conocer la URL. Los banners del portal sí, porque son publicidad.

    Args:
        request: Petición HTTP. Puede traer usuario de sesión y ?t=.
        path: Ruta relativa bajo media.

    Returns:
        ``publico`` (banner), ``privado`` (staff o token de esa orden)
        o ``denegado``.

    Efectos secundarios:
        Si hay token, lee el enlace en la base.
    """
    # Primero el país. Un banner de Argentina no es público en México.
    if not ruta_es_de_este_pais(path):
        return 'denegado'
    if es_banner_publico(path):
        return 'publico'

    usuario = getattr(request, 'user', None)
    if usuario is not None and getattr(usuario, 'is_authenticated', False):
        return 'privado'

    token = ''
    if request is not None:
        token = (request.GET.get('t') or '').strip()
    enlace = _enlace_vigente(token)
    if enlace is not None and archivo_pertenece_a_orden(path, enlace.orden):
        return 'privado'
    return 'denegado'


def anexar_token_seguimiento(url: str, token: str) -> str:
    """
    Pega ?t=token a la URL de un archivo para que el cliente pueda verlo.

    Args:
        url: URL del archivo (relativa o absoluta).
        token: Token del enlace de seguimiento. Vacío = no se modifica.

    Returns:
        str: La misma URL con el query t, o la original si no hay token.

    Efectos secundarios:
        Ninguno.
    """
    if not url or not token:
        return url
    separador = '&' if '?' in url else '?'
    return f'{url}{separador}t={quote(token, safe="")}'


def token_seguimiento_vigente(orden) -> str:
    """
    Token del enlace activo de esa orden, o cadena vacía.

    Objetivo de negocio:
        Los correos que mandan un video al cliente tienen que llevar
        el mismo permiso que la página de seguimiento. Si el enlace
        ya no sirve, el correo no incluye un token muerto.

    Args:
        orden: OrdenServicio.

    Returns:
        str: Token, o '' si no hay enlace vigente.

    Efectos secundarios:
        Lee una fila de EnlaceSeguimientoCliente.
    """
    from servicio_tecnico.models import EnlaceSeguimientoCliente
    enlace = (
        EnlaceSeguimientoCliente.objects
        .filter(orden=orden, activo=True)
        .order_by('-pk')
        .first()
    )
    if enlace is None or not enlace.esta_disponible:
        return ''
    return enlace.token


def ruta_interna_nginx(path: str) -> str | None:
    """
    Arma el valor de X-Accel-Redirect para que Nginx entregue el archivo.

    Args:
        path: Ruta relativa ya validada, o la cruda de la URL.

    Returns:
        str tipo ``/media-interno/mexico/fotos/a.jpg``, o None si no es segura.

    Efectos secundarios:
        Ninguno.
    """
    limpio = ruta_relativa_segura(path)
    if limpio is None:
        return None
    # safe='/' deja las carpetas. El resto (espacios, ?) se escapa.
    return '/media-interno/' + quote(limpio, safe='/')
