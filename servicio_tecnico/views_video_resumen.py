"""
Vistas HTTP del video resumen (encolar Celery + polling de estado).

EXPLICACIÓN PARA PRINCIPIANTES:
Estas vistas NO generan ni comprimen video con FFmpeg. Solo:
1) Validan la orden / el VideoOrden
2) Encolan tareas Celery (con db_alias multi-país)
3) Consultan AsyncResult para que el frontend haga polling

El trabajo pesado sigue en tasks.py (generar_video_resumen_task, etc.).
urls.py usa views.generar_video_resumen porque views.py reexporta estos nombres.
"""

import logging

from celery.result import AsyncResult
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from .models import ImagenOrden, OrdenServicio, VideoOrden

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["POST"])
def generar_video_resumen(request, orden_id):
    """
    Encola la tarea Celery para generar el video resumen de galería.

    Args:
        orden_id (int): PK de OrdenServicio.

    Returns:
        JsonResponse con task_id o error de validación (mínimo 2 fotos).

    Efectos secundarios:
        Encola generar_video_resumen_task en Celery (no escribe el video aquí).
    """
    from config.paises_config import get_pais_actual
    from .tasks import generar_video_resumen_task

    orden = get_object_or_404(OrdenServicio, pk=orden_id)

    # Verificar que hay suficientes fotos para generar el video
    TIPOS_PRINCIPALES = ['ingreso', 'diagnostico', 'reparacion', 'egreso']
    n_fotos = ImagenOrden.objects.filter(
        orden=orden,
        tipo__in=TIPOS_PRINCIPALES,
    ).count()

    if n_fotos < 2:
        return JsonResponse({
            'success': False,
            'error': (
                f'Se necesitan al menos 2 fotos de los tipos principales '
                f'(ingreso, diagnóstico, reparación, egreso). '
                f'Esta orden tiene {n_fotos}.'
            ),
        }, status=400)

    # Encolar la tarea Celery (responde inmediatamente al usuario)
    tarea = generar_video_resumen_task.delay(
        orden_id=orden.pk,
        usuario_id=request.user.pk,
        db_alias=get_pais_actual()['db_alias'],
    )

    logger.info(
        f"[VIDEO-RESUMEN] Tarea encolada — Orden {orden.numero_orden_interno} "
        f"| task_id={tarea.id} | usuario={request.user.username}"
    )

    return JsonResponse({
        'success': True,
        'task_id': tarea.id,
        'mensaje': (
            f'Generando video resumen para {n_fotos} fotos. '
            f'Te avisaremos cuando esté listo.'
        ),
        'n_fotos': n_fotos,
    })


@login_required
@require_http_methods(["GET"])
def estado_video_resumen(request, task_id):
    """
    Polling del estado de la tarea Celery de generación de video resumen.

    Args:
        task_id (str): ID de tarea Celery devuelto por generar_video_resumen.

    Returns:
        JsonResponse con estado, listo, y URLs si SUCCESS.

    Efectos secundarios:
        Solo lectura (Redis AsyncResult + opcional VideoOrden).
    """
    resultado = AsyncResult(task_id)
    estado = resultado.state

    respuesta = {
        'estado': estado,
        'listo': estado in ('SUCCESS', 'FAILURE'),
    }

    if estado == 'SUCCESS':
        # La tarea terminó bien — obtener datos del video generado
        data = resultado.result or {}
        video_id = data.get('video_id')
        if video_id:
            try:
                video = VideoOrden.objects.get(pk=video_id)
                respuesta['video_url'] = video.video.url if video.video else None
                respuesta['thumbnail_url'] = (
                    video.thumbnail.url if video.thumbnail else None
                )
                respuesta['video_id'] = video_id
                respuesta['n_fotos'] = data.get('n_fotos', 0)
                respuesta['tamano_mb'] = data.get('tamano_mb', 0)
            except VideoOrden.DoesNotExist:
                respuesta['error'] = (
                    'El video fue generado pero no se encontró en la base de datos.'
                )

    elif estado == 'FAILURE':
        error = resultado.result
        if isinstance(error, Exception):
            respuesta['error'] = str(error)[:300]
        else:
            respuesta['error'] = 'Error desconocido al generar el video.'

    return JsonResponse(respuesta)


@login_required
@require_http_methods(["POST"])
def comprimir_video_resumen(request, video_id):
    """
    Encola la compresión del video resumen para descarga.

    Args:
        video_id (int): PK de VideoOrden con tipo='resumen'.

    Efectos secundarios:
        Encola comprimir_video_resumen_descarga_task (Celery + db_alias).
    """
    from config.paises_config import get_pais_actual
    from .tasks import comprimir_video_resumen_descarga_task

    # Verificar que el video original existe y es de tipo 'resumen'
    video_original = get_object_or_404(VideoOrden, pk=video_id, tipo='resumen')

    if not video_original.video:
        return JsonResponse({
            'success': False,
            'error': 'El video resumen no tiene archivo asociado.',
        }, status=400)

    tarea = comprimir_video_resumen_descarga_task.delay(
        video_id=video_original.pk,
        usuario_id=request.user.pk,
        db_alias=get_pais_actual()['db_alias'],
    )

    logger.info(
        f"[VIDEO-COMPRESION] Tarea encolada — VideoOrden {video_original.pk} "
        f"| Orden {video_original.orden.numero_orden_interno} "
        f"| task_id={tarea.id} | usuario={request.user.username}"
    )

    return JsonResponse({
        'success': True,
        'task_id': tarea.id,
        'tamano_original_mb': video_original.tamano_final_mb,
    })


@login_required
@require_http_methods(["GET"])
def estado_compresion_resumen(request, task_id):
    """
    Polling del estado de la tarea Celery de compresión para descarga.

    Args:
        task_id (str): ID de tarea Celery de compresión.

    Returns:
        JsonResponse con URL del MP4 comprimido cuando SUCCESS.
    """
    resultado = AsyncResult(task_id)
    estado = resultado.state

    respuesta = {
        'estado': estado,
        'listo': estado in ('SUCCESS', 'FAILURE'),
    }

    if estado == 'SUCCESS':
        data = resultado.result or {}
        video_id = data.get('video_id')
        if video_id:
            try:
                video = VideoOrden.objects.get(pk=video_id, tipo='resumen_comprimido')
                respuesta['video_url'] = video.video.url if video.video else None
                respuesta['tamano_final_mb'] = data.get('tamano_final_mb', 0)
                respuesta['tamano_original_mb'] = data.get('tamano_original_mb', 0)
            except VideoOrden.DoesNotExist:
                respuesta['error'] = (
                    'El video comprimido no se encontró en la base de datos.'
                )

    elif estado == 'FAILURE':
        error = resultado.result
        if isinstance(error, Exception):
            respuesta['error'] = str(error)[:300]
        else:
            respuesta['error'] = 'Error desconocido al comprimir el video.'

    return JsonResponse(respuesta)
