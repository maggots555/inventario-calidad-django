"""
Vistas AJAX de IA para diagnóstico SIC (Fase 2 modularización).

EXPLICACIÓN PARA PRINCIPIANTES:
- pulir_diagnostico_sic_ia: mejora la redacción del diagnóstico (Ollama/Gemini).
- transcribir_audio_diagnostico: fallback servidor cuando no hay Web Speech API.

NO incluyen el chat del portal cliente (chat_seguimiento_cliente) — eso
va en la Fase 3 (views_seguimiento_cliente.py).

urls.py sigue usando views.pulir_diagnostico_sic_ia etc. porque views.py reexporta.
"""

import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


# ============================================================================
# VISTA AJAX: pulir_diagnostico_sic_ia
# Endpoint que recibe el diagnóstico escrito por el técnico, lo envía al
# proveedor de IA seleccionado (Ollama o Gemini) y devuelve la versión
# mejorada para que el técnico decida si la acepta.
#
# FLUJO:
# 1. Frontend hace POST con el diagnóstico original y datos del equipo
# 2. Esta vista llama a ollama_client.mejorar_diagnostico_dispatch()
# 3. El dispatcher detecta el proveedor según el nombre del modelo
#    - "gemini-*"  → llama a gemini_client.mejorar_diagnostico()
#    - cualquier otro → llama a ollama_client.mejorar_diagnostico()
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
    API AJAX: Mejora la redacción del diagnóstico SIC usando IA (Ollama o Gemini).

    El proveedor se selecciona automáticamente según el nombre del modelo:
        - Nombres que empiecen con "gemini" → API de Google Gemini
        - Cualquier otro nombre → Ollama (local/Tailscale)

    Recibe vía POST:
        - diagnostico_sic (str): Texto original del técnico (mínimo 20 caracteres)
        - modelo (str, opcional): Modelo a usar (override del default en settings)
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

    # Modelo seleccionado por el usuario desde el selector del modal
    # El dispatcher determinará el proveedor según el nombre del modelo
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
        f"Modelo: {modelo_override or 'default'} | "
        f"Equipo: {marca} {modelo_equipo} | Longitud diagnóstico: {len(diagnostico_sic)} chars"
    )

    # Medir el tiempo de respuesta del modelo para mostrarlo en la UI
    import time as _time
    _t_inicio = _time.monotonic()

    # Llamar al dispatcher — enruta a Gemini u Ollama según el nombre del modelo
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
# VISTA AJAX: transcribir_audio_diagnostico
# Endpoint que recibe un archivo de audio grabado por el técnico en el campo
# Diagnóstico SIC y lo transcribe usando IA (Ollama Whisper o Gemini).
#
# FLUJO:
# 1. El navegador graba audio con MediaRecorder (WebM/OGG/MP4 según soporte)
# 2. Si Web Speech API funcionó en el cliente, NO llega aquí (se maneja en JS)
# 3. Si Web Speech API no está disponible, el cliente envía el audio aquí
# 4. Esta vista detecta el proveedor disponible:
#    - OLLAMA_ENABLED=True  → usa transcribir_audio_ollama() (Whisper vía Ollama)
#    - GEMINI_ENABLED=True  → usa transcribir_audio_gemini() como fallback
# 5. Devuelve JSON con el texto transcrito
#
# Endpoint: POST /api/transcribir-audio-diagnostico/
# Recibe:  archivo 'audio' (multipart), campo 'idioma' (opcional, default 'es')
# Devuelve: {'success': True, 'texto': '...', 'proveedor': '...'}
#           {'success': False, 'error': '...mensaje...'}
# ============================================================================

@login_required
@require_http_methods(["POST"])
def transcribir_audio_diagnostico(request):
    """
    API AJAX: Transcribe un audio a texto usando Ollama (Whisper) o Gemini.

    Este endpoint es el fallback del lado servidor cuando el navegador no
    soporta la Web Speech API (principalmente Firefox y algunos Android).

    Recibe vía POST (multipart/form-data):
        - audio (File): Archivo de audio grabado (WebM, OGG, MP4, WAV)
        - idioma (str, opcional): Código de idioma (default: 'es')

    Devuelve JSON:
        {'success': True, 'texto': '...transcripcion...', 'proveedor': 'ollama'|'gemini'}
        {'success': False, 'error': '...mensaje de error amigable...'}
    """
    ollama_enabled = getattr(settings, 'OLLAMA_ENABLED', False)
    gemini_enabled = getattr(settings, 'GEMINI_ENABLED', False)

    # Verificar que al menos un proveedor de IA está habilitado
    if not (ollama_enabled or gemini_enabled):
        return JsonResponse({
            'success': False,
            'error': 'La transcripción de audio no está habilitada en este entorno.'
        }, status=403)

    # Validar que llegó el archivo de audio
    audio_file = request.FILES.get('audio')
    if not audio_file:
        return JsonResponse({
            'success': False,
            'error': 'No se recibió ningún archivo de audio.'
        }, status=400)

    # Límite de tamaño: 25 MB (audios de diagnóstico son cortos, < 2 minutos)
    MAX_SIZE_BYTES = 25 * 1024 * 1024
    if audio_file.size > MAX_SIZE_BYTES:
        return JsonResponse({
            'success': False,
            'error': 'El audio es demasiado grande. Máximo permitido: 25 MB.'
        }, status=400)

    idioma = request.POST.get('idioma', 'es').strip()

    # Leer el contenido binario del archivo
    audio_bytes = audio_file.read()
    audio_nombre = audio_file.name or 'audio.webm'
    audio_content_type = audio_file.content_type or 'audio/webm'

    logger.info(
        f"[AudioDiag] Solicitud de transcripción | Usuario: {request.user.username} | "
        f"Archivo: {audio_nombre} | Tamaño: {len(audio_bytes)} bytes | Idioma: {idioma}"
    )

    import time as _time

    # --- Intento 1: Ollama (Whisper local) ---
    if ollama_enabled:
        from .ollama_client import transcribir_audio_ollama
        _t = _time.monotonic()
        resultado = transcribir_audio_ollama(
            audio_bytes=audio_bytes,
            audio_filename=audio_nombre,
            audio_content_type=audio_content_type,
            idioma=idioma,
        )
        tiempo_ms = int((_time.monotonic() - _t) * 1000)

        if resultado['success']:
            logger.info(
                f"[AudioDiag] Transcripción OK (Ollama) | {tiempo_ms}ms | "
                f"Chars: {len(resultado.get('texto', ''))}"
            )
            return JsonResponse({
                'success': True,
                'texto': resultado['texto'],
                'proveedor': 'ollama',
                'tiempo_ms': tiempo_ms,
            })
        else:
            # Ollama falló — intentar con Gemini si está disponible
            logger.warning(
                f"[AudioDiag] Ollama falló, intentando Gemini | Error: {resultado.get('error')}"
            )

    # --- Intento 2: Gemini con fallback por modelos (GEMINI_MODELS) ---
    # Si el primer modelo falla (rate limit, tráfico, mantenimiento),
    # transcribir_audio_gemini_con_fallback prueba automáticamente cada modelo
    # de GEMINI_MODELS en orden hasta que uno responda con éxito.
    if gemini_enabled:
        from .gemini_client import transcribir_audio_gemini_con_fallback
        _t = _time.monotonic()
        resultado = transcribir_audio_gemini_con_fallback(
            audio_bytes=audio_bytes,
            audio_content_type=audio_content_type,
            idioma=idioma,
        )
        tiempo_ms = int((_time.monotonic() - _t) * 1000)

        if resultado['success']:
            logger.info(
                f"[AudioDiag] Transcripción OK (Gemini/{resultado.get('modelo_usado')}) | "
                f"{tiempo_ms}ms | Intentos: {resultado.get('intentos', 1)} | "
                f"Chars: {len(resultado.get('texto', ''))}"
            )
            return JsonResponse({
                'success': True,
                'texto': resultado['texto'],
                'proveedor': 'gemini',
                'tiempo_ms': tiempo_ms,
            })
        else:
            logger.error(
                f"[AudioDiag] Gemini agotó todos los modelos ({resultado.get('intentos', '?')} intentos) | "
                f"Error: {resultado.get('error')}"
            )
            return JsonResponse({
                'success': False,
                'error': resultado.get('error', 'Error al transcribir con Gemini.')
            })

     # Si Ollama fue el único proveedor y falló, devolvemos su error
    return JsonResponse({
        'success': False,
        'error': 'No se pudo transcribir el audio. Intenta de nuevo o escribe el diagnóstico manualmente.'
    })

