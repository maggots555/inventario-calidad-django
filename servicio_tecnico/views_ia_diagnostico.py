"""
Vistas AJAX de IA para diagnóstico SIC (Fase 2 modularización).

EXPLICACIÓN PARA PRINCIPIANTES:
- pulir_diagnostico_sic_ia: mejora la redacción del diagnóstico (Ollama/Gemini).
- transcribir_audio_diagnostico: encola Celery; el worker corre la cascada
  Transcribe → Flash → Ollama. El frontend hace polling de estado.

NO incluyen el chat del portal cliente (chat_seguimiento_cliente) — eso
va en la Fase 3 (views_seguimiento_cliente.py).

urls.py sigue usando views.pulir_diagnostico_sic_ia etc. porque views.py reexporta.
"""

import logging
import uuid

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


# ============================================================================
# VISTA AJAX: pulir_diagnostico_sic_ia
# Endpoint que recibe el diagnóstico escrito por el técnico, lo envía a la
# cascada automática de IA (Gemini → … → Ollama) y devuelve la versión
# mejorada para que el técnico decida si la acepta.
#
# FLUJO:
# 1. Frontend hace POST con el diagnóstico original y datos del equipo
#    (sin selector de modelo: modo automático)
# 2. Esta vista llama a ollama_client.mejorar_diagnostico_dispatch()
# 3. El dispatcher prueba GEMINI_MODELS en orden; si fallan → Ollama
# 4. Devuelve JSON con el texto mejorado o un mensaje de error
# 5. El frontend muestra el modal de comparación (antes vs después)
#
# NOTA: El técnico siempre tiene la última palabra — puede aceptar, reintentar
# o descartar la mejora. El campo se guarda solo cuando el técnico hace clic
# en "Guardar Configuración" en el formulario principal.
# ============================================================================

@login_required
@require_http_methods(["POST"])
def pulir_diagnostico_sic_ia(request):
    """
    API AJAX: Mejora la redacción del diagnóstico SIC usando IA (cascada automática).

    Modo por defecto (sin campo modelo o vacío):
        Prueba cada modelo de GEMINI_MODELS; si ninguno responde, cae a Ollama.

    Override opcional (compatibilidad):
        - Nombres que empiecen con "gemini" → ciclo Gemini + fallback Ollama
        - Cualquier otro nombre → solo ese modelo Ollama

    Recibe vía POST:
        - diagnostico_sic (str): Texto original del técnico (mínimo 20 caracteres)
        - modelo (str, opcional): Vacío = automático. Con valor = override legado.
        - tipo_equipo (str, opcional): Tipo de equipo (Laptop, PC, AIO...)
        - marca (str, opcional): Marca del equipo
        - modelo_equipo (str, opcional): Modelo del equipo
        - gama (str, opcional): Gama del equipo (alta, media, baja)
        - equipo_enciende (str, opcional): "true" o "false"
        - falla_principal (str, opcional): Falla reportada por el cliente

    Devuelve JSON:
        {'success': True, 'diagnostico_mejorado': '...', 'modelo_usado': '...'}
        {'success': False, 'error': '...mensaje...'}
    """
    from .ollama_client import mejorar_diagnostico_dispatch

    # Verificar que al menos un proveedor de IA está habilitado en este entorno
    if not getattr(settings, 'AI_ENABLED', False):
        return JsonResponse({
            'success': False,
            'error': 'La función de IA no está habilitada en este entorno.'
        }, status=403)

    # Extraer datos del POST
    diagnostico_sic = request.POST.get('diagnostico_sic', '').strip()

    # Validación mínima de caracteres (también validado en el cliente TypeScript)
    if len(diagnostico_sic) < 20:
        return JsonResponse({
            'success': False,
            'error': 'El diagnóstico debe tener al menos 20 caracteres para poder mejorarlo.'
        }, status=400)

    # Vacío = cascada automática (flujo normal del botón sin selector).
    # Si llega un valor, el dispatcher lo trata como override (compatibilidad).
    modelo_override = request.POST.get('modelo', '').strip()

    # Datos de contexto del equipo (opcionales — mejoran la calidad del prompt)
    tipo_equipo = request.POST.get('tipo_equipo', '')
    marca = request.POST.get('marca', '')
    modelo_equipo = request.POST.get('modelo_equipo', '')
    gama = request.POST.get('gama', '')
    equipo_enciende_raw = request.POST.get('equipo_enciende', 'true').lower()
    equipo_enciende = equipo_enciende_raw not in ('false', '0', 'no')
    falla_principal = request.POST.get('falla_principal', '')

    logger.info(
        f"[IA-Diag] Solicitud de mejora SIC | Usuario: {request.user.username} | "
        f"Modelo: {modelo_override or 'automático (cascada)'} | "
        f"Equipo: {marca} {modelo_equipo} | Longitud diagnóstico: {len(diagnostico_sic)} chars"
    )

    # Medir el tiempo de respuesta del modelo para mostrarlo en la UI
    import time as _time
    _t_inicio = _time.monotonic()

    # Cascada Gemini → Ollama (o override si el POST trae modelo)
    resultado = mejorar_diagnostico_dispatch(
        diagnostico_sic=diagnostico_sic,
        tipo_equipo=tipo_equipo,
        marca=marca,
        modelo=modelo_equipo,
        gama=gama,
        equipo_enciende=equipo_enciende,
        falla_principal=falla_principal,
        modelo_override=modelo_override,
    )

    tiempo_ms = int((_time.monotonic() - _t_inicio) * 1000)

    if resultado['success']:
        # Enriquecer la respuesta con estadísticas para la UI
        resultado['tiempo_ms'] = tiempo_ms
        resultado['chars_original'] = len(diagnostico_sic)
        resultado['chars_mejorado'] = len(resultado.get('diagnostico_mejorado', ''))
        return JsonResponse(resultado)
    else:
        # Devolver el error con status 200 para que el frontend lo maneje
        # (es un error de negocio, no un error HTTP)
        return JsonResponse(resultado, status=200)



# ============================================================================
# VISTA AJAX: guardar_diagnostico_sic_ia
# Guarda SOLO el campo diagnostico_sic cuando el técnico acepta la mejora
# del modal de IA, sin enviar todo el formulario "Guardar configuración".
#
# FLUJO:
# 1. Frontend pone el texto mejorado en el textarea
# 2. POST a este endpoint con orden_id + diagnostico_sic
# 3. Actualizamos DetalleEquipo.diagnostico_sic y registramos historial
# 4. JSON de éxito → el modal se cierra; el texto ya quedó persistido
# ============================================================================

@login_required
@require_http_methods(["POST"])
def guardar_diagnostico_sic_ia(request):
    """
    API AJAX: Persiste el diagnóstico SIC aceptado desde el modal de mejora IA.

    Objetivo de negocio:
        Evitar el doble clic (Aceptar + Guardar configuración). Al aceptar la
        sugerencia de redacción, el texto queda guardado en BD de inmediato.
        Si aplica, también cierra el diagnóstico (fecha_fin + Equipo Diagnosticado).

    Recibe vía POST:
        - orden_id (int): PK de la OrdenServicio
        - diagnostico_sic (str): Texto a guardar (mínimo 20 caracteres)

    Devuelve JSON:
        {'success': True, 'mensaje': '...', 'diagnostico_sic': '...'}
        {'success': False, 'error': '...'}

    Efectos secundarios:
        Actualiza DetalleEquipo.diagnostico_sic; puede setear
        fecha_fin_diagnostico y estado equipo_diagnosticado; crea HistorialOrden.
    """
    from django.shortcuts import get_object_or_404

    from .models import OrdenServicio
    from .services.historial import registrar_historial

    # EXPLICACIÓN PARA PRINCIPIANTES: leemos y validamos antes de tocar la BD.
    orden_id_raw = request.POST.get('orden_id', '').strip()
    diagnostico_sic = request.POST.get('diagnostico_sic', '').strip()

    if not orden_id_raw.isdigit():
        return JsonResponse({
            'success': False,
            'error': 'Falta el identificador de la orden o es inválido.',
        }, status=400)

    if len(diagnostico_sic) < 20:
        return JsonResponse({
            'success': False,
            'error': 'El diagnóstico debe tener al menos 20 caracteres para guardarlo.',
        }, status=400)

    orden = get_object_or_404(OrdenServicio, pk=int(orden_id_raw))
    detalle_equipo = getattr(orden, 'detalle_equipo', None)

    if detalle_equipo is None:
        return JsonResponse({
            'success': False,
            'error': 'Esta orden no tiene detalle de equipo.',
        }, status=400)

    # Valor ANTES de guardar: el helper detecta "primera vez" de fecha_fin y SIC.
    fecha_fin_anterior = detalle_equipo.fecha_fin_diagnostico
    diagnostico_sic_anterior = detalle_equipo.diagnostico_sic or ''

    # Guardar el diagnóstico; el cierre (fecha_fin / estado) lo hace el helper.
    detalle_equipo.diagnostico_sic = diagnostico_sic
    detalle_equipo.save(update_fields=['diagnostico_sic'])

    empleado_actual = None
    if hasattr(request.user, 'empleado'):
        empleado_actual = request.user.empleado

    # EXPLICACIÓN PARA PRINCIPIANTES:
    # Aceptar la mejora IA también "guarda" el SIC; debe cerrar el diagnóstico
    # igual que el botón Guardar configuración.
    from servicio_tecnico.services.cierre_diagnostico import (
        aplicar_fecha_fin_al_guardar_diagnostico_sic,
    )
    aplicar_fecha_fin_al_guardar_diagnostico_sic(
        detalle_equipo,
        orden,
        empleado_actual,
        fecha_fin_anterior=fecha_fin_anterior,
        diagnostico_sic_anterior=diagnostico_sic_anterior,
    )

    # Historial breve: queda rastro de que se aceptó una mejora IA
    registrar_historial(
        orden=orden,
        tipo_evento='actualizacion',
        usuario=empleado_actual,
        comentario=(
            'Diagnóstico SIC actualizado al aceptar mejora de redacción con IA '
            f'({len(diagnostico_sic)} caracteres).'
        ),
        es_sistema=False,
    )

    logger.info(
        f"[IA-Diag] Diagnóstico SIC guardado tras aceptar mejora | "
        f"Usuario: {request.user.username} | Orden: {orden.pk} | "
        f"Chars: {len(diagnostico_sic)}"
    )

    return JsonResponse({
        'success': True,
        'mensaje': 'Diagnóstico guardado correctamente.',
        'diagnostico_sic': diagnostico_sic,
    })


# ============================================================================
# VISTA AJAX: transcribir_audio_diagnostico
# El técnico envía el WebM grabado. Esta vista NO llama a Gemini: guarda el
# audio en cache y encola una tarea Celery. El navegador pregunta el estado
# en GET .../estado/<task_id>/ cada 2 s (así Cloudflare no corta a los ~100 s).
#
# Endpoint POST: /api/transcribir-audio-diagnostico/
# Endpoint GET:  /api/transcribir-audio-diagnostico/estado/<task_id>/
# ============================================================================

@login_required
@require_http_methods(["POST"])
def transcribir_audio_diagnostico(request):
    """
    API AJAX: encola la transcripción en Celery y devuelve task_id.

    Recibe vía POST (multipart/form-data):
        - audio (File): Archivo de audio grabado (WebM, OGG, MP4, WAV)
        - idioma (str, opcional): Código de idioma (default: 'es')

    Devuelve JSON:
        {'success': True, 'task_id': '...'}
        {'success': False, 'error': '...'}

    Efectos secundarios:
        Escribe el audio en cache Django (TTL 15 min) y encola Celery.
        No llama a Google ni a Ollama en este request.
    """
    import base64

    from django.core.cache import cache

    from config.paises_config import get_pais_actual
    from servicio_tecnico.services.transcripcion_audio import (
        CACHE_TTL_TRANSCRIPCION,
        clave_cache_audio,
        clave_cache_owner,
    )
    from servicio_tecnico.tasks_transcripcion import transcribir_audio_diagnostico_task

    ollama_enabled = getattr(settings, 'OLLAMA_ENABLED', False)
    gemini_enabled = getattr(settings, 'GEMINI_ENABLED', False)

    if not (ollama_enabled or gemini_enabled):
        return JsonResponse({
            'success': False,
            'error': 'La transcripción de audio no está habilitada en este entorno.'
        }, status=403)

    audio_file = request.FILES.get('audio')
    if not audio_file:
        return JsonResponse({
            'success': False,
            'error': 'No se recibió ningún archivo de audio.'
        }, status=400)

    MAX_SIZE_BYTES = 25 * 1024 * 1024
    if audio_file.size > MAX_SIZE_BYTES:
        return JsonResponse({
            'success': False,
            'error': 'El audio es demasiado grande. Máximo permitido: 25 MB.'
        }, status=400)

    idioma = request.POST.get('idioma', 'es').strip()
    audio_bytes = audio_file.read()
    audio_nombre = audio_file.name or 'audio.webm'
    audio_content_type = audio_file.content_type or 'audio/webm'

    logger.info(
        f"[AudioDiag] Encolando transcripción | Usuario: {request.user.username} | "
        f"Archivo: {audio_nombre} | Tamaño: {len(audio_bytes)} bytes | Idioma: {idioma}"
    )

    # EXPLICACIÓN: base64 en cache es JSON-safe (Redis pickle o JSON).
    cache_key = uuid.uuid4().hex
    cache.set(
        clave_cache_audio(cache_key),
        {
            'audio_b64': base64.b64encode(audio_bytes).decode('ascii'),
            'audio_filename': audio_nombre,
            'audio_content_type': audio_content_type,
            'idioma': idioma,
        },
        CACHE_TTL_TRANSCRIPCION,
    )

    tarea = transcribir_audio_diagnostico_task.delay(
        cache_key=cache_key,
        usuario_id=request.user.pk,
        db_alias=get_pais_actual()['db_alias'],
    )
    cache.set(
        clave_cache_owner(tarea.id),
        request.user.pk,
        CACHE_TTL_TRANSCRIPCION,
    )

    logger.info(
        f"[AudioDiag] Tarea encolada | task_id={tarea.id} | cache_key={cache_key}"
    )
    return JsonResponse({
        'success': True,
        'task_id': tarea.id,
        'mensaje': 'Transcribiendo en segundo plano. No cierres la página.',
    })


@login_required
@require_http_methods(["GET"])
def estado_transcripcion_audio(request, task_id):
    """
    Polling del estado de transcribir_audio_diagnostico_task.

    Args:
        task_id: UUID de Celery devuelto por el POST.

    Returns:
        JsonResponse con estado, listo, y texto si SUCCESS.

    Efectos secundarios:
        Solo lectura (Redis AsyncResult + cache de dueño).
    """
    from celery.result import AsyncResult
    from django.core.cache import cache

    from servicio_tecnico.services.transcripcion_audio import clave_cache_owner

    dueno_id = cache.get(clave_cache_owner(task_id))
    if dueno_id is None or int(dueno_id) != int(request.user.pk):
        return JsonResponse({
            'success': False,
            'error': 'No tienes permiso para consultar esta transcripción.',
        }, status=403)

    resultado = AsyncResult(task_id)
    estado = resultado.state
    respuesta = {
        'estado': estado,
        'listo': estado in ('SUCCESS', 'FAILURE'),
    }

    if estado == 'SUCCESS':
        data = resultado.result or {}
        if not isinstance(data, dict):
            data = {}
        respuesta['success'] = bool(data.get('success'))
        respuesta['texto'] = data.get('texto') or ''
        respuesta['proveedor'] = data.get('proveedor') or ''
        respuesta['modelo_usado'] = data.get('modelo_usado') or ''
        if not data.get('success'):
            respuesta['error'] = data.get(
                'error',
                'No se pudo transcribir el audio.',
            )

    elif estado == 'FAILURE':
        respuesta['success'] = False
        error = resultado.result
        if isinstance(error, Exception):
            respuesta['error'] = str(error)[:300]
        else:
            respuesta['error'] = 'Error desconocido al transcribir el audio.'

    return JsonResponse(respuesta)

