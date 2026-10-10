"""
Vista personalizada para servir archivos media desde múltiples ubicaciones
===========================================================================

Este módulo proporciona una vista que puede servir archivos desde múltiples
directorios (disco principal y disco alterno), similar a como Django maneja
los archivos estáticos con STATICFILES_DIRS.

EXPLICACIÓN PARA PRINCIPIANTES:
-------------------------------
Cuando subes una imagen, Django necesita dos cosas:
1. GUARDAR la imagen (esto ya funciona con DynamicFileSystemStorage)
2. SERVIR/MOSTRAR la imagen cuando el navegador la solicita (esto lo resuelve este archivo)

El problema:
- Imágenes antiguas están en C:/.../media/
- Imágenes nuevas están en D:/Media_Django/.../media/
- Django solo busca en UNA ubicación por defecto

La solución:
- Esta vista busca el archivo en AMBAS ubicaciones
- Primero busca en el disco principal
- Si no lo encuentra, busca en el disco alterno
- No sigue enlaces (symlink): un nombre público no puede apuntar a una firma

IMPORTANTE:
En Docker (MEDIA_ACCEL_REDIRECT=True) esta vista solo autoriza y le
pide a Nginx que entregue el archivo (X-Accel-Redirect). En la laptop
con runserver lee el disco ella misma, en las dos carpetas de siempre.
Sin sesión (y sin token de seguimiento de esa orden) responde 404.
Los banners de publicidad siguen públicos.
"""

from pathlib import Path
import mimetypes

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse, HttpResponseNotModified
from django.utils.http import http_date
from django.views.static import was_modified_since

from config.media_acceso import clasificar_acceso_media, ruta_interna_nginx


def _archivo_si_esta_dentro_de(location, path_relativo: str):
    """
    Devuelve el archivo solo si queda DENTRO de la carpeta media.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    ``os.path.normpath('../../etc/passwd')`` SIGUE siendo ``../../etc/passwd``.
    ``Path(media) / '../../etc/passwd'`` puede salir de la carpeta. Un path
    absoluto (``/etc/passwd``) ni siquiera se une a media: Python lo deja
    como está. Por eso resolvemos ambas rutas y exigimos
    ``is_relative_to(raiz)``.

    Args:
        location: Carpeta raíz de media (disco principal o alterno).
        path_relativo: Lo que vino en la URL (ej. ``servicio_tecnico/imagenes/a.jpg``).

    Returns:
        Path del archivo si existe y está dentro de location; si no, None.

    Efectos secundarios:
        Ninguno (solo lectura de disco).
    """
    # Paso 1: barras Windows → Unix y sin slash inicial (evita path absoluto).
    limpio = str(path_relativo).replace('\\', '/').lstrip('/')
    if not limpio or limpio.startswith('/'):
        return None

    # Paso 2: un enlace (symlink) no se sigue. Si banners/apunta a una
    # firma, la URL se ve pública y Nginx entregaría el archivo privado.
    raiz = Path(location).resolve()
    cursor = raiz
    for parte in limpio.split('/'):
        if parte in ('', '.', '..'):
            return None
        cursor = cursor / parte
        if cursor.is_symlink():
            return None

    # Paso 3: resolver (sigue los .. de verdad) y comparar contra la raíz.
    candidato = cursor.resolve()
    # is_relative_to: Python 3.9+; aquí corremos 3.12.
    if not candidato.is_relative_to(raiz):
        return None
    if candidato.is_file():
        return candidato
    return None


def serve_media_from_multiple_locations(request, path):
    """
    Vista para servir archivos media desde múltiples ubicaciones.
    
    EXPLICACIÓN:
    Esta función busca un archivo en múltiples ubicaciones y lo devuelve
    cuando lo encuentra. Es similar a como Django busca archivos estáticos.
    
    Orden de búsqueda:
    1. Disco principal
    2. Disco alterno (si el archivo no estaba en el principal)
    
    Args:
        request: La petición HTTP del navegador
        path: Ruta relativa del archivo (ej: 'scorecard/evidencias/2025/11/imagen.jpg')
        
    Returns:
        FileResponse: El archivo encontrado
        Http404: Si el archivo no existe en ninguna ubicación
        
    Ejemplo de uso:
        URL: http://localhost:8000/media/scorecard/evidencias/2025/11/imagen.jpg
        path = 'scorecard/evidencias/2025/11/imagen.jpg'
        
        Busca en:
        1. D:/Media_Django/.../media/scorecard/evidencias/2025/11/imagen.jpg
        2. C:/.../media/scorecard/evidencias/2025/11/imagen.jpg
    """
    # Importar configuración de storage_utils
    from config.storage_utils import ALTERNATE_STORAGE_PATH, PRIMARY_STORAGE_PATH

    # Paso 1: sin permiso, el mismo 404 que si el archivo no existiera.
    # Así no se confirma "sí hay una firma con ese nombre".
    acceso = clasificar_acceso_media(request, path)
    if acceso == 'denegado':
        raise Http404('Archivo media no encontrado')

    # Paso 2: el archivo tiene que existir DENTRO de una carpeta media.
    # resolve() sigue los enlaces simbólicos: si apuntan fuera, no se sirve.
    hallado = None
    for location in (PRIMARY_STORAGE_PATH, ALTERNATE_STORAGE_PATH):
        hallado = _archivo_si_esta_dentro_de(location, path)
        if hallado is not None:
            break
    if hallado is None:
        raise Http404('Archivo media no encontrado')

    primaria = Path(PRIMARY_STORAGE_PATH).resolve()
    # Paso 3: en Docker, Nginx solo tiene montada la carpeta principal.
    # Le pasamos la ruta ya resuelta, no la que escribió el navegador.
    if settings.MEDIA_ACCEL_REDIRECT and hallado.is_relative_to(primaria):
        relativo = hallado.relative_to(primaria).as_posix()
        interno = ruta_interna_nginx(relativo)
        if interno is None:
            raise Http404('Archivo media no encontrado')
        tipo, _codificacion = mimetypes.guess_type(relativo)
        response = HttpResponse(content_type=tipo or 'application/octet-stream')
        response['X-Accel-Redirect'] = interno
        response['X-Content-Type-Options'] = 'nosniff'
        if acceso == 'publico':
            response['Cache-Control'] = 'public, max-age=86400'
        else:
            # private: Cloudflare no guarda la foto para el siguiente visitante.
            response['Cache-Control'] = 'private, no-store'
        return response

    # Laptop (runserver) o archivo que solo está en el disco alterno.
    statobj = hallado.stat()
    if_modified_since = request.META.get('HTTP_IF_MODIFIED_SINCE')
    if if_modified_since:
        if not was_modified_since(if_modified_since, statobj.st_mtime):
            return HttpResponseNotModified()

    response = FileResponse(hallado.open('rb'))
    response['Last-Modified'] = http_date(statobj.st_mtime)
    response['X-Content-Type-Options'] = 'nosniff'
    if acceso == 'publico':
        response['Cache-Control'] = 'public, max-age=86400'
    else:
        response['Cache-Control'] = 'private, no-store'
    return response


def get_media_locations_info():
    """
    Función auxiliar para obtener información de las ubicaciones configuradas.
    
    EXPLICACIÓN:
    Esta función es útil para debugging y monitoreo.
    Retorna información sobre dónde está buscando Django los archivos media.
    
    Returns:
        dict: Información de las ubicaciones configuradas
    """
    from config.storage_utils import ALTERNATE_STORAGE_PATH, PRIMARY_STORAGE_PATH
    
    return {
        'primary': {
            'path': str(PRIMARY_STORAGE_PATH),
            'exists': PRIMARY_STORAGE_PATH.exists(),
        },
        'alternate': {
            'path': str(ALTERNATE_STORAGE_PATH),
            'exists': ALTERNATE_STORAGE_PATH.exists(),
        }
    }
