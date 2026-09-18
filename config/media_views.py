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
- Primero busca en el disco alterno (D:)
- Si no lo encuentra, busca en el disco principal (C:)
- Retorna el primero que encuentre

IMPORTANTE: Solo se usa en desarrollo (DEBUG=True)
En producción, configura tu servidor web (nginx/apache) para servir ambas rutas.
"""

from pathlib import Path

from django.http import FileResponse, Http404, HttpResponseNotModified
from django.utils.http import http_date
from django.views.static import was_modified_since


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

    # Paso 2: resolver (sigue los .. de verdad) y comparar contra la raíz.
    raiz = Path(location).resolve()
    candidato = (raiz / limpio).resolve()
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
    1. Disco alterno (D:/Media_Django/...) - Archivos nuevos
    2. Disco principal (C:/.../media/) - Archivos antiguos
    
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
    
    # Lista de ubicaciones donde buscar (en orden de prioridad)
    # IMPORTANTE: Buscar primero en PRIMARY (donde se guardan nuevos archivos)
    # luego en ALTERNATE (donde están archivos antiguos)
    search_locations = [
        PRIMARY_STORAGE_PATH,    # Disco principal - Archivos nuevos (1TB)
        ALTERNATE_STORAGE_PATH,  # Disco alterno - Archivos antiguos (fallback)
    ]

    # Buscar el archivo en cada ubicación, sin salir de esa carpeta.
    for location in search_locations:
        full_path = _archivo_si_esta_dentro_de(location, path)
        if full_path is None:
            continue

        # Obtener información del archivo
        statobj = full_path.stat()

        # Verificar si el archivo fue modificado (para caché del navegador)
        if_modified_since = request.META.get('HTTP_IF_MODIFIED_SINCE')
        if if_modified_since:
            if not was_modified_since(if_modified_since, statobj.st_mtime):
                return HttpResponseNotModified()

        response = FileResponse(full_path.open('rb'))
        response['Last-Modified'] = http_date(statobj.st_mtime)
        print(f"[MEDIA SERVE] Archivo encontrado: {full_path}")
        return response
    
    # Si llegamos aquí, el archivo no existe en ninguna ubicación
    print(f"[MEDIA SERVE] ❌ Archivo no encontrado: {path}")
    print(f"[MEDIA SERVE]    Buscado en:")
    for location in search_locations:
        print(f"[MEDIA SERVE]      - {Path(location) / path}")
    
    # Lanzar error 404
    raise Http404(f"Archivo media no encontrado: {path}")


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
