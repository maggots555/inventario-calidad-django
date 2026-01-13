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
- Imágenes antiguas están en C:\...\media\
- Imágenes nuevas están en D:\Media_Django\...\media\
- Django solo busca en UNA ubicación por defecto

La solución:
- Esta vista busca el archivo en AMBAS ubicaciones
- Primero busca en el disco alterno (D:)
- Si no lo encuentra, busca en el disco principal (C:)
- Retorna el primero que encuentre

IMPORTANTE: Solo se usa en desarrollo (DEBUG=True)
En producción, configura tu servidor web (nginx/apache) para servir ambas rutas.
"""

import os
from pathlib import Path
from django.http import FileResponse, Http404, HttpResponseNotModified
from django.views.static import was_modified_since
from django.utils.http import http_date
from django.conf import settings


def serve_media_from_multiple_locations(request, path):
    """
    Vista para servir archivos media desde múltiples ubicaciones.
    
    EXPLICACIÓN:
    Esta función busca un archivo en múltiples ubicaciones y lo devuelve
    cuando lo encuentra. Es similar a como Django busca archivos estáticos.
    
    Orden de búsqueda:
    1. Disco alterno (D:\Media_Django\...) - Archivos nuevos
    2. Disco principal (C:\...\media\) - Archivos antiguos
    
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
        1. D:\Media_Django\...\media\scorecard\evidencias\2025\11\imagen.jpg
        2. C:\...\media\scorecard\evidencias\2025\11\imagen.jpg
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
    
    # Normalizar la ruta (eliminar .. y barras dobles para seguridad)
    path = os.path.normpath(path).replace('\\', '/')
    
    # Buscar el archivo en cada ubicación
    for location in search_locations:
        # Construir ruta completa
        full_path = Path(location) / path
        
        # Verificar si el archivo existe
        if full_path.exists() and full_path.is_file():
            # Archivo encontrado!
            
            # Obtener información del archivo
            statobj = full_path.stat()
            
            # Verificar si el archivo fue modificado (para caché del navegador)
            # Esto mejora el rendimiento evitando transferir archivos sin cambios
            # En Django 5.x, was_modified_since() solo toma el header y la fecha
            if_modified_since = request.META.get('HTTP_IF_MODIFIED_SINCE')
            if if_modified_since:
                if not was_modified_since(if_modified_since, statobj.st_mtime):
                    # Archivo no modificado, devolver respuesta 304
                    return HttpResponseNotModified()
            
            # Abrir y devolver el archivo
            response = FileResponse(full_path.open('rb'))
            
            # Agregar encabezado Last-Modified para caché
            response['Last-Modified'] = http_date(statobj.st_mtime)
            
            # Log para debugging (visible en consola del servidor)
            print(f"[MEDIA SERVE] ✅ Archivo encontrado: {full_path}")
            
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
