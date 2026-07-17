"""
Vistas HTTP de descarga/eliminación de imágenes y videos (Fase 5).

EXPLICACIÓN PARA PRINCIPIANTES:
Las URLs de la galería en detalle_orden llaman a estas vistas.
La compresión al SUBIR está en services/multimedia.py (no aquí).

urls.py sigue usando views.eliminar_imagen etc. porque views.py reexporta.
"""

import os
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from .decorators import permission_required_with_message
from .models import HistorialOrden, ImagenOrden, VideoOrden

logger = logging.getLogger(__name__)


# ============================================================================
# VISTA: Descargar Imagen Original
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.view_imagenorden')
def descargar_imagen_original(request, imagen_id):
    """
    Descarga la imagen original (alta resolución) de una orden.

    Args:
        request: Objeto HttpRequest
        imagen_id: ID de la ImagenOrden
    
    Returns:
        HttpResponse con el archivo de imagen para descargar
    """
    from django.http import FileResponse, Http404, HttpResponseForbidden
    from pathlib import Path
    
    # Obtener la imagen o retornar 404
    imagen = get_object_or_404(ImagenOrden, pk=imagen_id)
    
    # Verificar que el usuario tiene permiso (empleado activo)
    try:
        empleado = request.user.empleado
        if not empleado.activo:
            return HttpResponseForbidden("No tienes permisos para descargar imágenes.")
    except:
        return HttpResponseForbidden("Debes ser un empleado activo para descargar imágenes.")
    
    # Verificar que existe la imagen original
    if not imagen.imagen_original:
        messages.warning(
            request,
            '⚠️ Esta imagen no tiene versión original guardada. '
            'Se descargará la versión comprimida.'
        )
        archivo_imagen = imagen.imagen
    else:
        archivo_imagen = imagen.imagen_original
    
    # Verificar que tenemos una ruta de archivo
    if not archivo_imagen:
        raise Http404("No hay archivo de imagen asociado.")
    
    # EXPLICACIÓN: Usar imagen.path que incluye automáticamente el prefijo del país
    # Esto funciona tanto para imágenes antiguas como nuevas (compatibilidad multi-país)
    try:
        archivo_path = Path(archivo_imagen.path)
        
        # Verificar que el archivo existe físicamente
        if not archivo_path.exists():
            print(f"[DESCARGA] ❌ Archivo no existe: {archivo_path}")
            raise Http404("El archivo de imagen no existe en el sistema de almacenamiento.")
        
        if not archivo_path.is_file():
            print(f"[DESCARGA] ❌ La ruta no es un archivo: {archivo_path}")
            raise Http404("La ruta de imagen no corresponde a un archivo válido.")
        
        print(f"[DESCARGA] ✅ Imagen encontrada: {archivo_path}")
        
    except Exception as e:
        print(f"[DESCARGA] ❌ Error al acceder a la imagen: {e}")
        raise Http404(f"Error al acceder a la imagen: {str(e)}")
    
    # Obtener el nombre del archivo original
    nombre_archivo = os.path.basename(archivo_imagen.name)
    
    # Crear nombre descriptivo para descarga
    tipo_texto = imagen.get_tipo_display()
    orden_numero = imagen.orden.numero_orden_interno
    service_tag = imagen.orden.detalle_equipo.numero_serie
    nombre_descarga = f"{orden_numero}_{service_tag}_{tipo_texto}_{nombre_archivo}"
    
    # Abrir archivo desde la ruta encontrada y crear respuesta
    # IMPORTANTE: Usamos archivo_path (Path object) en lugar de archivo_imagen.open()
    # porque archivo_path ya contiene la ubicación correcta (disco principal o alterno)
    archivo = archivo_path.open('rb')
    response = FileResponse(archivo, content_type='image/jpeg')
    response['Content-Disposition'] = f'attachment; filename="{nombre_descarga}"'
    
    return response


# ============================================================================
# VISTA: Eliminar Imagen de Orden
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.delete_imagenorden')
@require_http_methods(["POST"])
def eliminar_imagen(request, imagen_id):
    """
    Elimina una imagen de una orden de servicio.

    Args:
        request: Objeto HttpRequest
        imagen_id: ID de la ImagenOrden a eliminar
    
    Returns:
        JsonResponse con éxito o error
    """
    # Verificar que el usuario es un empleado activo
    try:
        empleado_actual = request.user.empleado
        if not empleado_actual.activo:
            return JsonResponse({
                'success': False,
                'error': 'No tienes permisos para eliminar imágenes.'
            }, status=403)
    except:
        return JsonResponse({
            'success': False,
            'error': 'Debes ser un empleado activo para eliminar imágenes.'
        }, status=403)
    
    # Obtener la imagen o retornar error 404
    try:
        imagen = ImagenOrden.objects.select_related('orden', 'subido_por').get(pk=imagen_id)
    except ImagenOrden.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'La imagen no existe.'
        }, status=404)
    
    try:
        # Guardar información para el historial antes de eliminar
        orden = imagen.orden
        tipo_imagen = imagen.get_tipo_display()
        descripcion_imagen = imagen.descripcion or imagen.nombre_archivo
        
        # Eliminar archivos físicos del sistema de archivos
        # EXPLICACIÓN: Usar imagen.path que incluye el prefijo del país automáticamente
        from pathlib import Path
        
        archivos_eliminados = []
        
        # Eliminar imagen comprimida
        if imagen.imagen:
            try:
                archivo_path = Path(imagen.imagen.path)
                
                if archivo_path.exists() and archivo_path.is_file():
                    os.remove(str(archivo_path))
                    archivos_eliminados.append('imagen comprimida')
                    print(f"[ELIMINAR] ✅ Imagen comprimida eliminada: {archivo_path.name}")
                else:
                    print(f"[ELIMINAR] ⚠️ Imagen comprimida no encontrada: {archivo_path}")
                    
            except Exception as e:
                print(f"[ELIMINAR] ⚠️ Error al eliminar archivo comprimido: {str(e)}")
        
        # Eliminar imagen original
        if imagen.imagen_original:
            try:
                archivo_path = Path(imagen.imagen_original.path)
                
                if archivo_path.exists() and archivo_path.is_file():
                    os.remove(str(archivo_path))
                    archivos_eliminados.append('imagen original')
                    print(f"[ELIMINAR] ✅ Imagen original eliminada: {archivo_path.name}")
                else:
                    print(f"[ELIMINAR] ⚠️ Imagen original no encontrada: {archivo_path}")
                    
            except Exception as e:
                print(f"[ELIMINAR] ⚠️ Error al eliminar archivo original: {str(e)}")
        
        # Eliminar registro de la base de datos
        imagen.delete()
        
        # Registrar en historial
        HistorialOrden.objects.create(
            orden=orden,
            tipo_evento='imagen',
            comentario=f'Imagen {tipo_imagen} eliminada: {descripcion_imagen} (Eliminada por: {empleado_actual.nombre_completo})',
            usuario=empleado_actual,
            es_sistema=False
        )
        
        # Mensaje de éxito
        mensaje_archivos = f" ({', '.join(archivos_eliminados)})" if archivos_eliminados else ""
        
        return JsonResponse({
            'success': True,
            'message': f'✅ Imagen {tipo_imagen} eliminada correctamente{mensaje_archivos}.',
            'imagen_id': imagen_id
        })
        
    except Exception as e:
        # Capturar cualquier error inesperado
        import traceback
        error_detallado = traceback.format_exc()
        print(f"❌ ERROR AL ELIMINAR IMAGEN: {error_detallado}")
        
        return JsonResponse({
            'success': False,
            'error': f'Error inesperado al eliminar la imagen: {str(e)}',
            'error_type': type(e).__name__
        }, status=500)


# ============================================================================
# VISTA: Eliminar Video de Orden
# ============================================================================

@login_required
@permission_required_with_message('servicio_tecnico.delete_videoorden')
@require_http_methods(["POST"])
def eliminar_video(request, video_id):
    """
    Elimina un video de una orden de servicio.

    EXPLICACIÓN PARA PRINCIPIANTES:
    - Solo acepta POST (nunca GET, para evitar borrados accidentales con links)
    - Borra el archivo de video Y el thumbnail del sistema de archivos
    - Registra el evento en el historial de la orden
    - Devuelve JSON para que el frontend pueda actualizar la UI sin recargar

    Args:
        request: Objeto HttpRequest
        video_id: ID del VideoOrden a eliminar
    
    Returns:
        JsonResponse con éxito o error
    """
    # Verificar que el usuario es un empleado activo
    try:
        empleado_actual = request.user.empleado
        if not empleado_actual.activo:
            return JsonResponse({
                'success': False,
                'error': 'No tienes permisos para eliminar videos.'
            }, status=403)
    except Exception:
        return JsonResponse({
            'success': False,
            'error': 'Debes ser un empleado activo para eliminar videos.'
        }, status=403)

    # Obtener el video o retornar error 404
    try:
        video = VideoOrden.objects.select_related('orden', 'subido_por').get(pk=video_id)
    except VideoOrden.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'El video no existe.'
        }, status=404)

    try:
        from pathlib import Path

        orden = video.orden
        tipo_video = video.get_tipo_display()
        descripcion_video = video.descripcion or video.nombre_archivo
        archivos_eliminados = []

        # Eliminar archivo de video comprimido
        if video.video:
            try:
                archivo_path = Path(video.video.path)
                if archivo_path.exists() and archivo_path.is_file():
                    os.remove(str(archivo_path))
                    archivos_eliminados.append('video')
                    print(f"[ELIMINAR VIDEO] ✅ Video eliminado: {archivo_path.name}")
                else:
                    print(f"[ELIMINAR VIDEO] ⚠️ Video no encontrado: {archivo_path}")
            except Exception as e:
                print(f"[ELIMINAR VIDEO] ⚠️ Error al eliminar archivo de video: {str(e)}")

        # Eliminar thumbnail
        if video.thumbnail:
            try:
                thumb_path = Path(video.thumbnail.path)
                if thumb_path.exists() and thumb_path.is_file():
                    os.remove(str(thumb_path))
                    archivos_eliminados.append('thumbnail')
                    print(f"[ELIMINAR VIDEO] ✅ Thumbnail eliminado: {thumb_path.name}")
                else:
                    print(f"[ELIMINAR VIDEO] ⚠️ Thumbnail no encontrado: {thumb_path}")
            except Exception as e:
                print(f"[ELIMINAR VIDEO] ⚠️ Error al eliminar thumbnail: {str(e)}")

        # Eliminar registro de base de datos
        video.delete()

        # Registrar en historial
        HistorialOrden.objects.create(
            orden=orden,
            tipo_evento='video',
            comentario=f'Video {tipo_video} eliminado: {descripcion_video} (Eliminado por: {empleado_actual.nombre_completo})',
            usuario=empleado_actual,
            es_sistema=False,
        )

        mensaje_archivos = f" ({', '.join(archivos_eliminados)})" if archivos_eliminados else ""
        return JsonResponse({
            'success': True,
            'message': f'✅ Video {tipo_video} eliminado correctamente{mensaje_archivos}.',
            'video_id': video_id,
        })

    except Exception as e:
        import traceback
        print(f"❌ ERROR AL ELIMINAR VIDEO: {traceback.format_exc()}")
        return JsonResponse({
            'success': False,
            'error': f'Error inesperado al eliminar el video: {str(e)}',
            'error_type': type(e).__name__,
        }, status=500)

