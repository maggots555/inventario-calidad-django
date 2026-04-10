"""
Cliente HTTP para la API de Google Gemini — Mejora de Diagnósticos SIC

EXPLICACIÓN PARA PRINCIPIANTES:
Este módulo se comunica con la API REST de Google Gemini usando únicamente
la librería estándar de Python (urllib), sin SDK externo ni dependencias
adicionales. La API de Gemini es una API en la nube (no local como Ollama),
por lo que requiere una API Key generada en Google AI Studio.

Flujo:
1. Django recibe el diagnóstico escrito por el técnico
2. Este módulo construye el payload con el mismo prompt que usa Ollama
3. Envía la petición a la API de Google via HTTPS
4. Gemini procesa y devuelve el texto mejorado
5. Django devuelve el texto al frontend como JSON

ENDPOINT:
  https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={API_KEY}

REGLAS DEL PROMPT (idénticas a Ollama — consistencia entre proveedores):
- Solo mejorar redacción y ortografía, NUNCA cambiar el contenido técnico
- NO inventar fallas o síntomas no mencionados por el técnico
- NO eliminar información que el técnico escribió
- Español formal, conciso, terminología técnica correcta
"""

import json
import urllib.request
import urllib.error
import ssl
import logging
from django.conf import settings

# Importamos el constructor de prompt desde ollama_client para no duplicarlo.
# El mismo prompt funciona perfectamente para ambos proveedores.
from .ollama_client import construir_prompt

logger = logging.getLogger(__name__)

# URL base de la API REST de Gemini (v1beta — soporta todos los modelos actuales)
GEMINI_API_BASE = 'https://generativelanguage.googleapis.com/v1beta/models'


def mejorar_diagnostico(
    diagnostico_sic: str,
    tipo_equipo: str = "",
    marca: str = "",
    modelo: str = "",
    gama: str = "",
    equipo_enciende: bool = True,
    falla_principal: str = "",
    modelo_override: str = "",
) -> dict:
    """
    Llama a la API REST de Google Gemini para mejorar la redacción del diagnóstico SIC.

    Usa urllib.request (stdlib) — sin dependencias externas ni SDK de Google.
    Requiere GEMINI_API_KEY configurada en .env y GEMINI_ENABLED=True.

    Args:
        diagnostico_sic: Texto original del técnico (mínimo 20 caracteres)
        tipo_equipo, marca, modelo, gama, equipo_enciende, falla_principal:
            Datos del equipo para dar contexto al modelo
        modelo_override: Si se especifica, usa este modelo en lugar de GEMINI_MODEL.
            Permite seleccionar el modelo desde la UI sin cambiar la configuración.

    Returns:
        dict con estructura:
            {'success': True, 'diagnostico_mejorado': '...texto...', 'modelo_usado': '...'}
            {'success': False, 'error': '...mensaje de error...'}
    """
    # ── Validación básica del texto ──
    diagnostico_limpio = diagnostico_sic.strip()
    if len(diagnostico_limpio) < 20:
        return {
            'success': False,
            'error': 'El diagnóstico debe tener al menos 20 caracteres para poder mejorarlo.'
        }

    # ── Verificar que Gemini está habilitado y tiene API key ──
    if not getattr(settings, 'GEMINI_ENABLED', False):
        return {
            'success': False,
            'error': 'La integración con Gemini no está habilitada en este entorno.'
        }

    api_key = getattr(settings, 'GEMINI_API_KEY', '').strip()
    if not api_key:
        logger.error("[Gemini] GEMINI_API_KEY no está configurada en .env")
        return {
            'success': False,
            'error': 'La API Key de Gemini no está configurada. Contacta al administrador.'
        }

    # ── Selección del modelo ──
    # Prioridad: modelo_override (selector UI) → GEMINI_MODEL (settings) → default
    model = (
        modelo_override.strip()
        if modelo_override.strip()
        else getattr(settings, 'GEMINI_MODEL', 'gemini-2.0-flash')
    )

    # Si el modelo viene con prefijo "[Gemini] ", lo removemos para la API
    # (el prefijo es solo visual en la UI, la API necesita el nombre limpio)
    if model.startswith('[Gemini] '):
        model = model[len('[Gemini] '):]

    timeout = getattr(settings, 'GEMINI_TIMEOUT', 60)

    # ── Construir el prompt (reutiliza construir_prompt de ollama_client) ──
    prompt = construir_prompt(
        diagnostico_sic=diagnostico_limpio,
        tipo_equipo=tipo_equipo,
        marca=marca,
        modelo=modelo,
        gama=gama,
        equipo_enciende=equipo_enciende,
        falla_principal=falla_principal,
    )

    # ── Construir la URL con la API key como query param ──
    url = f"{GEMINI_API_BASE}/{model}:generateContent?key={api_key}"

    # ── Payload para la API de Gemini ──
    # Estructura: contents[].parts[].text
    # Temperatura baja (0.3) = respuestas conservadoras y predecibles (igual que Ollama)
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.3,
            "topP": 0.9,
            # maxOutputTokens: 8192 es más que suficiente para cualquier diagnóstico técnico.
            # (gemini-2.5-flash soporta hasta 65536 tokens de salida)
            # Un diagnóstico detallado en español raramente supera 500 tokens.
            "maxOutputTokens": 8192,
            # thinkingConfig: desactiva el razonamiento interno (thinking budget = 0).
            # Para corrección de texto no se necesita razonamiento profundo.
            # Sin esto, gemini-2.5-flash consume ~1000 tokens internos antes de responder,
            # dejando muy poco espacio para la respuesta real con límites bajos.
            # En modelos 2.0 y anteriores este campo se ignora silenciosamente.
            "thinkingConfig": {
                "thinkingBudget": 0
            }
        }
    }

    data = json.dumps(payload).encode('utf-8')

    # ── URL para logs (sin API key por seguridad) ──
    url_log = f"{GEMINI_API_BASE}/{model}:generateContent"

    try:
        req = urllib.request.Request(
            url=url,
            data=data,
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            method='POST',
        )

        logger.info(
            f"[Gemini] Solicitando mejora de diagnóstico SIC | "
            f"Modelo: {model} | URL: {url_log} | "
            f"Equipo: {marca} {modelo} | "
            f"Longitud diagnóstico: {len(diagnostico_limpio)} chars"
        )

        # Contexto SSL por defecto (verifica certificados de Google — correcto)
        ctx = ssl.create_default_context()

        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
            response_data = json.loads(response.read().decode('utf-8'))

        # ── Extraer el texto de la respuesta de Gemini ──
        # Estructura: candidates[0].content.parts[0].text
        candidates = response_data.get('candidates', [])
        if not candidates:
            # La API puede bloquear la respuesta por safety filters
            # Verificar si hay promptFeedback con blockReason
            feedback = response_data.get('promptFeedback', {})
            block_reason = feedback.get('blockReason', '')
            if block_reason:
                logger.warning(f"[Gemini] Respuesta bloqueada por safety filter: {block_reason}")
                return {
                    'success': False,
                    'error': (
                        'Gemini bloqueó la respuesta por filtros de seguridad. '
                        'Intenta reformular el diagnóstico o usa otro modelo.'
                    )
                }
            logger.warning("[Gemini] Respuesta vacía — sin candidatos")
            return {
                'success': False,
                'error': 'Gemini devolvió una respuesta vacía. Intenta de nuevo.'
            }

        diagnostico_mejorado = (
            candidates[0]
            .get('content', {})
            .get('parts', [{}])[0]
            .get('text', '')
            .strip()
        )

        # ── Verificar que la respuesta no fue cortada por el límite de tokens ──
        # finishReason='STOP'      → respuesta completa (correcto)
        # finishReason='MAX_TOKENS'→ respuesta truncada — aunque subimos maxOutputTokens
        #                            a 8192, lo detectamos y avisamos al técnico
        # finishReason='SAFETY'   → bloqueada por filtros de contenido
        finish_reason = candidates[0].get('finishReason', 'STOP')

        if finish_reason == 'MAX_TOKENS':
            logger.warning(
                f"[Gemini] Respuesta TRUNCADA por límite de tokens | "
                f"Modelo: {model} | Original: {len(diagnostico_limpio)} chars | "
                f"Mejorado parcial: {len(diagnostico_mejorado)} chars"
            )
            return {
                'success': False,
                'error': (
                    'La respuesta de Gemini fue cortada porque el diagnóstico es demasiado largo. '
                    'Intenta dividirlo en secciones más cortas.'
                )
            }

        if finish_reason == 'SAFETY':
            logger.warning(f"[Gemini] Respuesta bloqueada por SAFETY | Modelo: {model}")
            return {
                'success': False,
                'error': (
                    'Gemini bloqueó la respuesta por filtros de seguridad. '
                    'Intenta reformular el diagnóstico.'
                )
            }

        if not diagnostico_mejorado:
            logger.warning("[Gemini] Texto extraído vacío después de parsear la respuesta")
            return {
                'success': False,
                'error': 'Gemini devolvió una respuesta vacía. Intenta de nuevo.'
            }

        logger.info(
            f"[Gemini] Mejora completada | "
            f"Original: {len(diagnostico_limpio)} chars → "
            f"Mejorado: {len(diagnostico_mejorado)} chars | "
            f"finishReason: {finish_reason}"
        )

        return {
            'success': True,
            'diagnostico_mejorado': diagnostico_mejorado,
            'modelo_usado': model,
        }

    except urllib.error.HTTPError as e:
        # Error HTTP de la API de Google (4xx, 5xx)
        error_body = ''
        try:
            error_body = e.read().decode('utf-8')
            error_json = json.loads(error_body)
            # La API de Gemini devuelve errores en formato {"error": {"message": "..."}}
            error_msg = error_json.get('error', {}).get('message', str(e))
        except Exception:
            error_msg = error_body or str(e)

        logger.error(f"[Gemini] HTTP {e.code}: {error_msg} | Modelo: {model}")

        if e.code == 400:
            return {
                'success': False,
                'error': f'Solicitud inválida a Gemini: {error_msg}'
            }
        elif e.code == 401 or e.code == 403:
            return {
                'success': False,
                'error': (
                    'API Key de Gemini inválida o sin permisos. '
                    'Verifica la configuración en Google AI Studio.'
                )
            }
        elif e.code == 404:
            return {
                'success': False,
                'error': (
                    f'Modelo "{model}" no encontrado en Gemini. '
                    'Verifica el nombre del modelo en la configuración.'
                )
            }
        elif e.code == 429:
            return {
                'success': False,
                'error': (
                    'Se superó el límite de peticiones a Gemini (rate limit). '
                    'Espera unos segundos y vuelve a intentarlo.'
                )
            }
        elif e.code >= 500:
            return {
                'success': False,
                'error': 'Error interno en los servidores de Google. Intenta de nuevo en unos minutos.'
            }
        else:
            return {
                'success': False,
                'error': f'Error de la API de Gemini (HTTP {e.code}): {error_msg}'
            }

    except urllib.error.URLError as e:
        error_msg = str(e.reason) if hasattr(e, 'reason') else str(e)
        logger.error(f"[Gemini] Error de red: {error_msg}")

        if 'timed out' in error_msg.lower() or 'timeout' in error_msg.lower():
            return {
                'success': False,
                'error': (
                    f'Gemini tardó más de {timeout} segundos en responder. '
                    'Intenta de nuevo.'
                )
            }
        return {
            'success': False,
            'error': f'Error de red al conectar con Gemini: {error_msg}'
        }

    except TimeoutError:
        logger.error(f"[Gemini] Timeout después de {timeout}s | Modelo: {model}")
        return {
            'success': False,
            'error': (
                f'Gemini tardó más de {timeout} segundos en responder. '
                'Intenta de nuevo.'
            )
        }

    except json.JSONDecodeError as e:
        logger.error(f"[Gemini] Error al parsear respuesta JSON: {e}")
        return {
            'success': False,
            'error': 'Respuesta inválida de la API de Gemini. Intenta de nuevo.'
        }

    except Exception as e:
        logger.error(f"[Gemini] Error inesperado: {type(e).__name__}: {e}", exc_info=True)
        return {
            'success': False,
            'error': f'Error inesperado al conectar con Gemini: {str(e)}'
        }
