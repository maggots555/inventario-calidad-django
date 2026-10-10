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
   (?t=...) y la ruta es una foto o un video guardados en esa orden.
   No basta con que la carpeta se llame como el folio: ese folio se
   puede repetir y el número interno también sale en los correos.
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


def _normalizar_ruta(nombre: str) -> str:
    """
    Deja la ruta con barras / y sin slash al inicio.

    Args:
        nombre: Ruta de la URL o del FileField. Puede venir vacía.

    Returns:
        str: Ruta limpia, o '' si no había nada.

    Efectos secundarios:
        Ninguno.
    """
    return str(nombre or '').replace('\\', '/').lstrip('/')


def _ruta_pedida_es_la_guardada(pedida: str, guardada: str) -> bool:
    """
    True si el navegador pide el mismo archivo que está en la base.

    Objetivo de negocio:
        La galería guarda ``servicio_tecnico/imagenes/OOW/a.jpg`` y el
        navegador pide ``mexico/servicio_tecnico/imagenes/OOW/a.jpg``.
        Eso sí es el mismo archivo. Al revés no: si la base ya trae
        ``mexico/...`` y piden la ruta sin país, el disco abriría
        ``media/servicio_tecnico/...``, que puede ser otra foto vieja.

    Args:
        pedida: Ruta que vino en la URL, ya limpia.
        guardada: ``name`` del FileField de esta orden.

    Returns:
        bool.

    Efectos secundarios:
        Lee el país de la visita para armar el prefijo. No escribe.
    """
    pedido = _normalizar_ruta(pedida)
    guardado = _normalizar_ruta(guardada)
    if not pedido or not guardado:
        return False
    if pedido == guardado:
        return True
    # El nombre guardado ya trae país: no le pegamos otro ni se lo quitamos.
    primer_tramo, _sep, _cola = guardado.partition('/')
    if primer_tramo in PAISES_MEDIA:
        return False
    pais_visita = _pais_de_esta_peticion()
    return pedido == f'{pais_visita}/{guardado}'


def _algun_nombre_coincide(pedida: str, nombres) -> bool:
    """
    True si alguna ruta guardada es la que pidió el navegador.

    Args:
        pedida: Ruta de la URL.
        nombres: Iterable de ``name`` de FileField (pueden venir vacíos).

    Returns:
        bool.

    Efectos secundarios:
        Ninguno. Quien llama ya leyó la base.
    """
    for nombre in nombres:
        if _ruta_pedida_es_la_guardada(pedida, nombre):
            return True
    return False


def _es_archivo_registrado_en_la_orden(pedida: str, orden) -> bool:
    """
    True si esa ruta es un archivo que esta orden tiene guardado.

    Objetivo de negocio:
        El token abre la foto de la galería, el video del correo, el
        PDF de diagnóstico y la factura (pdf y xml) de ESA orden.
        No abre otro nombre en la misma carpeta, aunque el folio o el
        id coincidan.

    Args:
        pedida: Ruta relativa ya limpia.
        orden: OrdenServicio.

    Returns:
        bool.

    Efectos secundarios:
        Lee fotos, videos, el PDF de diagnóstico y los CFDI. No escribe.
    """
    from servicio_tecnico.models import EnlaceSeguimientoCliente, ImagenOrden, VideoOrden
    from servicio_tecnico.models_facturacion import DocumentoFiscalOrden

    if getattr(orden, 'pk', None) is None or not _normalizar_ruta(pedida):
        return False

    # Paso 1: galería del seguimiento (ImagenOrden.imagen).
    fotos = (
        ImagenOrden.objects.filter(orden=orden)
        .exclude(imagen='')
        .values_list('imagen', flat=True)
    )
    if _algun_nombre_coincide(pedida, fotos):
        return True

    # Paso 2: el mp4 del correo. La miniatura y la firma no van aquí.
    videos = (
        VideoOrden.objects.filter(orden=orden)
        .exclude(video='')
        .values_list('video', flat=True)
    )
    if _algun_nombre_coincide(pedida, videos):
        return True

    # Paso 3: el PDF que el botón de seguimiento abre por su propia vista.
    # Si alguien pide el archivo por /media/, tiene que ser ese nombre.
    diagnosticos = (
        EnlaceSeguimientoCliente.objects.filter(orden=orden)
        .exclude(pdf_diagnostico='')
        .exclude(pdf_diagnostico__isnull=True)
        .values_list('pdf_diagnostico', flat=True)
    )
    if _algun_nombre_coincide(pedida, diagnosticos):
        return True

    # Paso 4: factura. Solo el pdf y el xml guardados, no la carpeta entera.
    documentos = DocumentoFiscalOrden.objects.filter(orden=orden).values_list(
        'pdf', 'cfdi_xml'
    )
    for pdf, xml in documentos:
        if _ruta_pedida_es_la_guardada(pedida, pdf):
            return True
        if _ruta_pedida_es_la_guardada(pedida, xml):
            return True
    return False


def archivo_pertenece_a_orden(path: str, orden) -> bool:
    """
    True si el cliente con el token de esta orden puede ver esa ruta.

    Objetivo de negocio:
        Solo se entrega el archivo que esta orden tiene en la base:
        foto, video, PDF de diagnóstico o factura. Una firma, un
        comprobante o un nombre suelto en la carpeta no.

    Args:
        path: Ruta relativa bajo media.
        orden: OrdenServicio.

    Returns:
        bool.

    Efectos secundarios:
        Si la ruta es de este país, lee los archivos de la orden.
        No escribe.
    """
    separado = _pais_y_resto(path)
    if separado is None:
        return False
    pais, resto = separado
    # La carpeta argentina/ no se abre con un token que vive en la base de México.
    if pais is not None and pais != _pais_de_esta_peticion():
        return False

    limpio = ruta_relativa_segura(path) or resto
    return _es_archivo_registrado_en_la_orden(limpio, orden)


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
        Si hay token, lee el enlace y, para una foto o un video,
        comprueba que esa ruta esté guardada en la orden.
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
