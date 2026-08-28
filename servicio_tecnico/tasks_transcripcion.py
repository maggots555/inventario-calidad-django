"""
Tarea Celery: transcribir el dictado del Diagnóstico SIC.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El técnico graba el audio y Django responde en menos de 1 segundo con un
task_id. Esta tarea (en el worker Celery) hace lo lento: llama a Gemini
Transcribe, luego Flash, luego Ollama. El navegador pregunta cada 2 s
si ya hay texto.

Por qué no va el audio en .delay():
    Celery serializa argumentos a JSON. Un archivo de 25 MB reventaría
    Redis. Guardamos el audio en el cache de Django (TTL 15 min) y aquí
    solo llega la clave.

Celery no pasa por PaisMiddleware: la firma lleva db_alias.
Se reexporta al FINAL de tasks.py para que el worker la registre.
"""

from __future__ import annotations

import base64
import logging

from celery import shared_task
from django.core.cache import cache

logger = logging.getLogger('servicio_tecnico')


@shared_task(
    bind=True,
    max_retries=0,
    name='servicio_tecnico.transcribir_audio_diagnostico',
    # EXPLICACIÓN: Transcribe puede tardar 180s; si falla, Flash y Ollama
    # suman más. 10 min (igual que CELERY_TASK_TIME_LIMIT) cubre la cascada
    # sin dejar el worker colgado para siempre.
    time_limit=600,
    soft_time_limit=540,
)
def transcribir_audio_diagnostico_task(
    self,
    cache_key: str,
    usuario_id=None,
    db_alias='default',
):
    """
    Lee el audio del cache y corre la cascada Transcribe → Flash → Ollama.

    Args:
        self: Tarea Celery (bind=True).
        cache_key: UUID de la clave transcribe_audio:{uuid} en cache.
        usuario_id: PK del técnico (auditoría en logs).
        db_alias: País activo. Obligatorio en Celery aunque hoy no escribamos BD.

    Returns:
        dict JSON-serializable:
            success, texto, proveedor, modelo_usado, error, intentos

    Efectos secundarios:
        Borra el blob de audio del cache. Llama APIs de Google/Ollama.
        No escribe en la base de datos.
    """
    from servicio_tecnico.services.transcripcion_audio import (
        clave_cache_audio,
        transcribir_audio_cascada,
    )

    clave = clave_cache_audio(cache_key)
    payload = cache.get(clave)
    cache.delete(clave)

    if not payload or not isinstance(payload, dict):
        logger.error(
            '[AudioCelery] Cache vacío | cache_key=%s | usuario=%s | db=%s',
            cache_key,
            usuario_id,
            db_alias,
        )
        return {
            'success': False,
            'error': (
                'El audio expiró o el worker no lo encontró. '
                'Vuelve a dictar el diagnóstico.'
            ),
        }

    try:
        audio_b64 = payload.get('audio_b64') or ''
        audio_bytes = base64.b64decode(audio_b64)
    except Exception:
        return {
            'success': False,
            'error': 'El audio en cache está corrupto. Vuelve a dictar.',
        }

    if not audio_bytes:
        return {
            'success': False,
            'error': 'No había bytes de audio en cache.',
        }

    logger.info(
        '[AudioCelery] Inicio | task=%s | usuario=%s | db=%s | bytes=%s',
        self.request.id,
        usuario_id,
        db_alias,
        len(audio_bytes),
    )

    try:
        resultado = transcribir_audio_cascada(
            audio_bytes=audio_bytes,
            audio_filename=payload.get('audio_filename') or 'audio.webm',
            audio_content_type=payload.get('audio_content_type') or 'audio/webm',
            idioma=payload.get('idioma') or 'es',
        )
    except Exception as exc:
        logger.exception('[AudioCelery] Cascada lanzó excepción: %s', exc)
        return {
            'success': False,
            'error': f'Error al transcribir: {str(exc)[:300]}',
        }

    logger.info(
        '[AudioCelery] Fin | task=%s | success=%s | proveedor=%s | chars=%s',
        self.request.id,
        resultado.get('success'),
        resultado.get('proveedor'),
        len(resultado.get('texto') or ''),
    )
    return resultado
