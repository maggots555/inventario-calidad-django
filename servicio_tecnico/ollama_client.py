"""
Cliente HTTP para Ollama — Mejora de Diagnósticos SIC

EXPLICACIÓN PARA PRINCIPIANTES:
Este módulo se comunica con la API local de Ollama usando únicamente
la librería estándar de Python (urllib), sin dependencias externas.

Flujo:
1. Django recibe el diagnóstico escrito por el técnico
2. Este módulo construye un prompt con contexto del equipo + el texto del técnico
3. Envía el prompt a Ollama vía HTTP POST a localhost (o IP remota via Tailscale)
4. Ollama procesa con el modelo configurado y devuelve el texto mejorado
5. Django devuelve el texto mejorado al frontend como JSON

REGLAS DEL PROMPT:
- Solo mejorar redacción y ortografía, NUNCA cambiar el contenido técnico
- NO inventar fallas o síntomas no mencionados por el técnico
- NO eliminar información que el técnico escribió
- Español formal, conciso, terminología técnica correcta
"""

import json
import urllib.request
import urllib.error
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


# ============================================================================
# PROMPT SYSTEM — Instrucciones estrictas para el modelo
# ============================================================================

PROMPT_SYSTEM = """Eres un corrector técnico especializado en diagnósticos de equipos electrónicos para un centro de servicio técnico profesional.

Tu única función es MEJORAR LA REDACCIÓN del diagnóstico que te proporciona el técnico. NO eres un diagnosticador.

REGLAS ESTRICTAS — NUNCA las violes:
1. SOLO corrige ortografía, gramática y redacción. NUNCA cambies el contenido técnico.
2. NUNCA agregues fallas, síntomas, componentes o causas que el técnico NO mencionó.
3. NUNCA elimines información que el técnico escribió, aunque parezca redundante.
4. NUNCA supongas causas adicionales ni hagas suposiciones técnicas propias.
5. Si el técnico menciona un componente específico (ej: "VRM", "slot RAM"), mantenlo exactamente.
6. Escribe en español formal y profesional.
7. Usa terminología técnica estándar donde el técnico usó términos coloquiales (ej: "placa" → "tarjeta madre", "cargador" → "adaptador de corriente").
8. Mantén el diagnóstico conciso — no lo hagas más largo de lo necesario.
9. Si el diagnóstico ya está bien redactado, devuélvelo con cambios mínimos.
10. Devuelve ÚNICAMENTE el texto mejorado, sin explicaciones, sin comillas, sin encabezados, sin "Diagnóstico mejorado:", solo el texto.

Contexto del equipo (solo para entender el contexto, NO para agregar información):
- Tipo de equipo: {tipo_equipo}
- Marca: {marca}
- Modelo: {modelo}
- Gama: {gama}
- El equipo enciende: {equipo_enciende}
- Falla reportada por el cliente: {falla_principal}

Diagnóstico escrito por el técnico (SOLO mejora este texto):
{diagnostico_sic}"""


def construir_prompt(
    diagnostico_sic: str,
    tipo_equipo: str = "",
    marca: str = "",
    modelo: str = "",
    gama: str = "",
    equipo_enciende: bool = True,
    falla_principal: str = "",
) -> str:
    """
    Construye el prompt completo insertando los datos del equipo y el diagnóstico.

    Args:
        diagnostico_sic: Texto del diagnóstico escrito por el técnico (requerido)
        tipo_equipo: Laptop, PC, AIO, etc.
        marca: Dell, HP, Lenovo, etc.
        modelo: Modelo específico del equipo
        gama: alta, media, baja
        equipo_enciende: Si el equipo enciende al ingreso
        falla_principal: Falla reportada por el cliente

    Returns:
        str: Prompt completo listo para enviar a Ollama
    """
    return PROMPT_SYSTEM.format(
        tipo_equipo=tipo_equipo or "No especificado",
        marca=marca or "No especificada",
        modelo=modelo or "No especificado",
        gama=gama or "No especificada",
        equipo_enciende="Sí" if equipo_enciende else "No",
        falla_principal=falla_principal or "No especificada",
        diagnostico_sic=diagnostico_sic.strip(),
    )


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
    Llama a la API de Ollama para mejorar la redacción del diagnóstico SIC.

    Usa urllib.request (stdlib) — sin dependencias externas.
    Compatible con Ollama local (localhost) y remoto via Tailscale (100.x.x.x).

    Args:
        diagnostico_sic: Texto original del técnico (mínimo 20 caracteres)
        tipo_equipo, marca, modelo, gama, equipo_enciende, falla_principal:
            Datos del equipo para dar contexto al modelo
        modelo_override: Si se especifica, usa este modelo en lugar de OLLAMA_MODEL.
            Permite seleccionar el modelo desde la UI sin cambiar la configuración.

    Returns:
        dict con estructura:
            {'success': True, 'diagnostico_mejorado': '...texto...', 'modelo_usado': '...'}
            {'success': False, 'error': '...mensaje de error...'}
    """
    # Validación básica
    diagnostico_limpio = diagnostico_sic.strip()
    if len(diagnostico_limpio) < 20:
        return {
            'success': False,
            'error': 'El diagnóstico debe tener al menos 20 caracteres para poder mejorarlo.'
        }

    # Verificar configuración de Ollama
    if not getattr(settings, 'OLLAMA_ENABLED', False):
        return {
            'success': False,
            'error': 'La función de IA no está habilitada en este entorno.'
        }

    base_url = getattr(settings, 'OLLAMA_BASE_URL', 'http://localhost:11434')
    # Usar modelo_override si viene del frontend, si no el default del settings
    model = modelo_override.strip() if modelo_override.strip() else getattr(settings, 'OLLAMA_MODEL', 'gemma3:12b')
    timeout = getattr(settings, 'OLLAMA_TIMEOUT', 120)

    # Construir el prompt con todos los datos del equipo
    prompt = construir_prompt(
        diagnostico_sic=diagnostico_limpio,
        tipo_equipo=tipo_equipo,
        marca=marca,
        modelo=modelo,
        gama=gama,
        equipo_enciende=equipo_enciende,
        falla_principal=falla_principal,
    )

    # Estructura del payload para la API /api/chat de Ollama
    # Compatible con Ollama >= 0.1.x y la API de OpenAI-compatible
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "stream": False,
        "options": {
            # Temperatura baja = respuestas más conservadoras y predecibles
            # Ideal para corrección de texto (no queremos creatividad excesiva)
            "temperature": 0.3,
            "top_p": 0.9,
        }
    }

    url = f"{base_url.rstrip('/')}/api/chat"
    data = json.dumps(payload).encode('utf-8')

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
            f"[Ollama] Solicitando mejora de diagnóstico SIC | "
            f"Modelo: {model} | URL: {url} | "
            f"Equipo: {marca} {modelo} | "
            f"Longitud diagnóstico: {len(diagnostico_limpio)} chars"
        )

        with urllib.request.urlopen(req, timeout=timeout) as response:
            response_data = json.loads(response.read().decode('utf-8'))

        # Extraer el texto de la respuesta
        # Estructura de /api/chat: response_data['message']['content']
        diagnostico_mejorado = (
            response_data
            .get('message', {})
            .get('content', '')
            .strip()
        )

        if not diagnostico_mejorado:
            logger.warning("[Ollama] Respuesta vacía del modelo")
            return {
                'success': False,
                'error': 'El modelo devolvió una respuesta vacía. Intenta de nuevo.'
            }

        logger.info(
            f"[Ollama] Mejora completada | "
            f"Original: {len(diagnostico_limpio)} chars → "
            f"Mejorado: {len(diagnostico_mejorado)} chars"
        )

        return {
            'success': True,
            'diagnostico_mejorado': diagnostico_mejorado,
            'modelo_usado': model,
        }

    except urllib.error.URLError as e:
        # Error de conexión — Ollama no está corriendo o la IP/puerto es incorrecto
        error_msg = str(e.reason) if hasattr(e, 'reason') else str(e)
        logger.error(f"[Ollama] Error de conexión: {error_msg} | URL: {url}")

        if 'Connection refused' in error_msg or 'refused' in error_msg.lower():
            return {
                'success': False,
                'error': (
                    'No se pudo conectar con Ollama. '
                    'Verifica que el servicio esté corriendo en la dirección configurada.'
                )
            }
        elif 'timed out' in error_msg.lower() or 'timeout' in error_msg.lower():
            return {
                'success': False,
                'error': (
                    f'El modelo tardó más de {timeout} segundos en responder. '
                    'Intenta de nuevo o usa un modelo más rápido.'
                )
            }
        else:
            return {
                'success': False,
                'error': f'Error de red al conectar con Ollama: {error_msg}'
            }

    except TimeoutError:
        logger.error(f"[Ollama] Timeout después de {timeout}s | URL: {url}")
        return {
            'success': False,
            'error': (
                f'El modelo tardó más de {timeout} segundos en responder. '
                'Intenta de nuevo o usa un modelo más rápido.'
            )
        }

    except json.JSONDecodeError as e:
        logger.error(f"[Ollama] Error al parsear respuesta JSON: {e}")
        return {
            'success': False,
            'error': 'Respuesta inválida de Ollama. Verifica la versión del servicio.'
        }

    except Exception as e:
        logger.error(f"[Ollama] Error inesperado: {type(e).__name__}: {e}", exc_info=True)
        return {
            'success': False,
            'error': f'Error inesperado: {str(e)}'
        }
