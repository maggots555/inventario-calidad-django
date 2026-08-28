"""
Cascada de transcripción de audio para el Diagnóstico SIC.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El técnico dicta el diagnóstico con el micrófono. Si el navegador no tiene
Web Speech API (Firefox, algunos iPhone), el audio llega aquí.

Orden de intentos (el primero que funcione gana):
    1. Gemini 3.5 Transcribe  → modelo de Google HECHO para voz→texto
    2. Gemini Flash / Lite    → modelos generales que "oyen" el audio
    3. Ollama local           → último recurso, no gasta cuota de Google

Por qué Transcribe va primero:
    Es más preciso con acentos, muletillas y jerga. No necesita una PC
    potente. Si Google no lo tiene disponible (preview, cuota, error),
    caemos solos a los Gemini que ya teníamos y, al final, a Ollama.

Efectos secundarios:
    Llama APIs externas (Google y/o Ollama). No escribe en la base de datos.
"""

from __future__ import annotations

import base64
import json
import logging
import ssl
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

# Interactions API (Gemini 3.5 Transcribe). Distinta de generateContent.
GEMINI_INTERACTIONS_URL = (
    'https://generativelanguage.googleapis.com/v1beta/interactions'
)

# Palabras del taller que el modelo debe reconocer mejor (hasta 1000).
# EXPLICACIÓN: sin esta lista, "RHITSO" puede salir como "ritso" o similar.
VOCABULARIO_SIC: tuple[str, ...] = (
    'RHITSO',
    'SICSER',
    'SIGMA',
    'Diagnóstico SIC',
    'folio',
    'placa madre',
    'BIOS',
    'SSD',
    'no enciende',
)


def _gemini_transcribe_habilitado() -> bool:
    """
    True si debemos intentar Gemini 3.5 Transcribe.

    Args:
        Ninguno (lee settings).

    Returns:
        bool: requiere Gemini encendido y el flag de Transcribe en True.
    """
    if not getattr(settings, 'GEMINI_ENABLED', False):
        return False
    return bool(getattr(settings, 'GEMINI_TRANSCRIBE_ENABLED', True))


def _modelo_transcribe() -> str:
    """Nombre del modelo STT dedicado (configurable en .env)."""
    return (
        getattr(settings, 'GEMINI_TRANSCRIBE_MODEL', 'gemini-3.5-transcribe')
        or 'gemini-3.5-transcribe'
    ).strip()


def _es_modelo_transcribe(nombre: str) -> bool:
    """True si el ID es el STT dedicado (no debe ir en la cascada Flash)."""
    return 'transcribe' in (nombre or '').lower()


def _extraer_texto_interaccion(response_data: dict) -> str:
    """
    Saca el texto transcrito de la respuesta REST de Interactions API.

    Objetivo:
        El SDK de Google expone `output_text`, pero el JSON crudo a veces
        trae el texto en `outputs`, `steps` o `candidates`. Revisamos todos.

    Args:
        response_data: Dict JSON ya parseado de la API.

    Returns:
        str: texto limpio, o cadena vacía si no hay voz/texto.
    """
    # 1) Campo que el SDK documenta (a veces también viene en REST).
    texto = (response_data.get('output_text') or '').strip()
    if texto:
        return texto

    # 2) Lista `outputs`: cada ítem puede ser {type: text, text: "..."}.
    pedazos: list[str] = []
    for item in response_data.get('outputs') or []:
        if not isinstance(item, dict):
            continue
        pedazo = (item.get('text') or '').strip()
        if pedazo:
            pedazos.append(pedazo)
    if pedazos:
        return '\n'.join(pedazos).strip()

    # 3) `steps` con bloques de contenido (anotaciones word_info no las usamos).
    for step in response_data.get('steps') or []:
        if not isinstance(step, dict):
            continue
        for content in step.get('content') or []:
            if not isinstance(content, dict):
                continue
            pedazo = (content.get('text') or '').strip()
            if pedazo:
                pedazos.append(pedazo)
    if pedazos:
        return '\n'.join(pedazos).strip()

    # 4) Por si Google reusa la forma de generateContent.
    for candidate in response_data.get('candidates') or []:
        parts = (candidate.get('content') or {}).get('parts') or []
        for part in parts:
            if isinstance(part, dict):
                pedazo = (part.get('text') or '').strip()
                if pedazo:
                    pedazos.append(pedazo)
    return '\n'.join(pedazos).strip()


def transcribir_con_gemini_transcribe(
    audio_bytes: bytes,
    audio_content_type: str = 'audio/webm',
    idioma: str = 'es',
) -> dict:
    """
    Transcribe audio con el modelo dedicado Gemini 3.5 Transcribe.

    Objetivo de negocio:
        Convertir el dictado del técnico en texto limpio (modo smart:
        quita "ehh" y autocorrecciones) para pegarlo en Diagnóstico SIC.

    Args:
        audio_bytes: Bytes del archivo grabado (WebM, OGG, WAV, MP3).
        audio_content_type: MIME type que mandó el navegador.
        idioma: Pista de idioma; es / es-MX se mandan como es-MX.

    Returns:
        dict éxito: {'success': True, 'texto': str, 'modelo_usado': str}
        dict error: {'success': False, 'error': str}

    Efectos secundarios:
        POST HTTPS a Google Interactions API. No toca la BD.
    """
    if not _gemini_transcribe_habilitado():
        return {
            'success': False,
            'error': 'Gemini 3.5 Transcribe no está habilitado.',
        }

    api_key = getattr(settings, 'GEMINI_API_KEY', '').strip()
    if not api_key:
        return {
            'success': False,
            'error': 'La API Key de Gemini no está configurada.',
        }

    if not audio_bytes:
        return {'success': False, 'error': 'No se recibieron bytes de audio.'}

    modelo = _modelo_transcribe()
    timeout = getattr(settings, 'GEMINI_TIMEOUT', 60)

    # Pista BCP-47: el taller habla español de México.
    language_tag = 'es-MX' if (idioma or 'es').lower().startswith('es') else idioma

    audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

    # EXPLICACIÓN: Interactions API usa snake_case (no generateContent).
    # El audio va inline en base64: dictados ≤60 s no necesitan Files API.
    payload = {
        'model': modelo,
        'input': [
            {
                'type': 'audio',
                'data': audio_b64,
                'mime_type': audio_content_type or 'audio/webm',
            }
        ],
        'generation_config': {
            'transcription_config': {
                # EXPLICACIÓN: Google rechaza language_hints (HTTP 400).
                # El cookbook oficial usa language_codes (BCP-47, ej. es-MX).
                'language_codes': [language_tag],
                'mode': {'type': 'smart'},
                'custom_vocabulary': list(VOCABULARIO_SIC),
            }
        },
    }

    logger.info(
        '[AudioTranscripcion][Transcribe] Iniciando | '
        f'Modelo: {modelo} | Audio: {len(audio_bytes)} bytes '
        f'({audio_content_type}) | Idioma: {language_tag}'
    )

    data = json.dumps(payload).encode('utf-8')
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'x-goog-api-key': api_key,
        'Api-Revision': '2026-05-20',
    }

    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(
            url=GEMINI_INTERACTIONS_URL,
            data=data,
            headers=headers,
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
            response_data = json.loads(response.read().decode('utf-8'))

        texto = _extraer_texto_interaccion(response_data)
        if not texto:
            logger.warning(
                f'[AudioTranscripcion][Transcribe] Respuesta sin texto | Modelo: {modelo}'
            )
            return {
                'success': False,
                'error': 'Gemini Transcribe no devolvió texto. '
                         'Se intentará con otro modelo.',
            }

        logger.info(
            f'[AudioTranscripcion][Transcribe] OK | Modelo: {modelo} | '
            f'Chars: {len(texto)}'
        )
        return {
            'success': True,
            'texto': texto,
            'modelo_usado': modelo,
        }

    except urllib.error.HTTPError as e:
        try:
            error_body = e.read().decode('utf-8')
            error_data = json.loads(error_body)
            error_msg = error_data.get('error', {}).get('message', error_body)
        except Exception:
            error_msg = str(e)
        logger.warning(
            f'[AudioTranscripcion][Transcribe] HTTP {e.code}: {error_msg} | '
            f'Modelo: {modelo}'
        )
        return {
            'success': False,
            'error': f'Gemini Transcribe HTTP {e.code}: {error_msg}',
        }

    except urllib.error.URLError as e:
        error_msg = str(e.reason) if hasattr(e, 'reason') else str(e)
        logger.warning(f'[AudioTranscripcion][Transcribe] Red: {error_msg}')
        return {
            'success': False,
            'error': f'Error de red con Gemini Transcribe: {error_msg}',
        }

    except TimeoutError:
        logger.warning(
            f'[AudioTranscripcion][Transcribe] Timeout {timeout}s | Modelo: {modelo}'
        )
        return {
            'success': False,
            'error': f'Gemini Transcribe tardó más de {timeout}s.',
        }

    except json.JSONDecodeError:
        logger.warning('[AudioTranscripcion][Transcribe] JSON inválido')
        return {
            'success': False,
            'error': 'Respuesta inválida de Gemini Transcribe.',
        }

    except Exception as e:
        logger.error(
            f'[AudioTranscripcion][Transcribe] {type(e).__name__}: {e}',
            exc_info=True,
        )
        return {
            'success': False,
            'error': f'Error inesperado en Gemini Transcribe: {str(e)}',
        }


def transcribir_audio_cascada(
    audio_bytes: bytes,
    audio_filename: str = 'audio.webm',
    audio_content_type: str = 'audio/webm',
    idioma: str = 'es',
) -> dict:
    """
    Orquesta la cascada Transcribe → Gemini general → Ollama.

    Args:
        audio_bytes: Bytes del audio grabado.
        audio_filename: Nombre original (Ollama/ffmpeg lo usan).
        audio_content_type: MIME type del navegador.
        idioma: Código de idioma (default 'es').

    Returns:
        dict éxito:
            success, texto, proveedor ('gemini-transcribe'|'gemini'|'ollama'),
            modelo_usado, intentos
        dict error:
            success=False, error, intentos

    Efectos secundarios:
        Hasta 3 familias de llamadas de red. No escribe en BD.
    """
    gemini_enabled = getattr(settings, 'GEMINI_ENABLED', False)
    ollama_enabled = getattr(settings, 'OLLAMA_ENABLED', False)
    intentos = 0
    ultimo_error = 'Ningún proveedor de transcripción está habilitado.'

    # ── Paso 1: modelo dedicado STT ──────────────────────────────────────────
    if _gemini_transcribe_habilitado():
        intentos += 1
        logger.info(
            f'[AudioCascada] Intento {intentos}: Gemini Transcribe '
            f'({_modelo_transcribe()})'
        )
        resultado = transcribir_con_gemini_transcribe(
            audio_bytes=audio_bytes,
            audio_content_type=audio_content_type,
            idioma=idioma,
        )
        if resultado.get('success'):
            resultado['proveedor'] = 'gemini-transcribe'
            resultado['intentos'] = intentos
            return resultado
        ultimo_error = resultado.get('error', ultimo_error)
        logger.warning(
            f'[AudioCascada] Transcribe falló, sigue Gemini general | {ultimo_error}'
        )

    # ── Paso 2: Gemini Flash / Lite (generateContent, como antes) ────────────
    if gemini_enabled:
        from servicio_tecnico.gemini_client import transcribir_audio_gemini_con_fallback

        # No reintentar el STT dedicado si alguien lo puso en GEMINI_MODELS.
        modelos_settings = getattr(settings, 'GEMINI_MODELS', []) or []
        modelos_generales = [m for m in modelos_settings if not _es_modelo_transcribe(m)]
        if not modelos_generales:
            default_modelo = getattr(settings, 'GEMINI_MODEL', 'gemini-3.6-flash')
            if not _es_modelo_transcribe(default_modelo):
                modelos_generales = [default_modelo]

        if modelos_generales:
            intentos += 1
            logger.info(
                f'[AudioCascada] Intento {intentos}: Gemini general '
                f'({len(modelos_generales)} modelos)'
            )
            resultado = transcribir_audio_gemini_con_fallback(
                audio_bytes=audio_bytes,
                audio_content_type=audio_content_type,
                idioma=idioma,
                modelos=modelos_generales,
            )
            # El fallback interno cuenta sub-intentos; sumamos los extras.
            sub_intentos = max(int(resultado.get('intentos') or 1), 1)
            intentos += sub_intentos - 1
            if resultado.get('success'):
                resultado['proveedor'] = 'gemini'
                resultado['intentos'] = intentos
                return resultado
            ultimo_error = resultado.get('error', ultimo_error)
            logger.warning(
                f'[AudioCascada] Gemini general falló, sigue Ollama | {ultimo_error}'
            )

    # ── Paso 3: Ollama local (último recurso) ────────────────────────────────
    if ollama_enabled:
        from servicio_tecnico.ollama_client import transcribir_audio_ollama

        intentos += 1
        logger.info(f'[AudioCascada] Intento {intentos}: Ollama local')
        resultado = transcribir_audio_ollama(
            audio_bytes=audio_bytes,
            audio_filename=audio_filename,
            audio_content_type=audio_content_type,
            idioma=idioma,
        )
        if resultado.get('success'):
            resultado['proveedor'] = 'ollama'
            resultado['intentos'] = intentos
            resultado.setdefault('modelo_usado', getattr(settings, 'OLLAMA_MODEL', ''))
            return resultado
        ultimo_error = resultado.get('error', ultimo_error)
        logger.error(f'[AudioCascada] Ollama también falló | {ultimo_error}')

    return {
        'success': False,
        'error': ultimo_error,
        'intentos': intentos,
    }
