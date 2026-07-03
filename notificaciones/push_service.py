"""
Servicio de notificaciones Web Push para SIGMA.

EXPLICACIÓN PARA PRINCIPIANTES:
Este módulo se encarga de enviar notificaciones push a los técnicos.
Una notificación push es el mensaje que aparece en el teléfono o computadora
aunque el usuario no tenga el navegador abierto.

Flujo de una notificación:
  1. Django llama a `enviar_push_a_usuario(usuario, titulo, mensaje, url)`
  2. Esa función busca todas las suscripciones activas de ese usuario
  3. Por cada suscripción llama a `_enviar_una_suscripcion()`
  4. pywebpush cifra el mensaje y lo envía al servidor push del navegador
     (Google FCM, Mozilla Push Service, Apple APNS, etc.)
  5. El servidor push lo entrega al dispositivo
  6. El Service Worker lo recibe con el evento 'push' y muestra la notificación

Si el navegador ya no acepta la suscripción (expiró o fue revocada),
se desactiva automáticamente en la base de datos.
"""

import json
import logging

from django.conf import settings
from django.contrib.auth.models import User

from pywebpush import webpush, WebPushException

logger = logging.getLogger('notificaciones')


def _vapid_ok() -> bool:
    """Verifica que las llaves VAPID estén configuradas antes de intentar enviar."""
    return bool(settings.VAPID_PRIVATE_KEY and settings.VAPID_PUBLIC_KEY)


def _enviar_una_suscripcion(suscripcion, payload: dict) -> bool:
    """
    Envía una notificación a una suscripción específica.

    EXPLICACIÓN:
    pywebpush toma los datos de la suscripción (endpoint, p256dh, auth),
    cifra el payload con la llave pública del navegador y lo envía a
    través del servidor push del navegador.

    Retorna True si el envío fue exitoso, False si falló.
    """
    # Lazy import del modelo para evitar import circular al inicio del módulo
    from notificaciones.models import PushSubscription  # noqa

    subscription_info = {
        "endpoint": suscripcion.endpoint,
        "keys": {
            "p256dh": suscripcion.p256dh,
            "auth": suscripcion.auth,
        },
    }

    vapid_claims = {
        "sub": f"mailto:{settings.VAPID_CLAIMS_EMAIL}",
    }

    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims=vapid_claims,
            content_encoding="aes128gcm",
            ttl=86400,  # 24 horas: el servidor push reintenta la entrega si el dispositivo
                        # no está conectado en el momento del envío. Sin este parámetro
                        # (TTL=0 por defecto) el mensaje se descarta inmediatamente si
                        # el dispositivo está offline, lo que causa entregas intermitentes.
        )
        return True

    except WebPushException as exc:
        codigo = exc.response.status_code if exc.response is not None else None

        # 404 o 410 → la suscripción expiró o fue revocada por el navegador
        if codigo in (404, 410):
            logger.info(
                f"[PUSH] Suscripción expirada/revocada (HTTP {codigo}), "
                f"desactivando id={suscripcion.pk}"
            )
            PushSubscription.objects.filter(pk=suscripcion.pk).update(activa=False)
        else:
            logger.error(
                f"[PUSH] Error al enviar a suscripción id={suscripcion.pk}: "
                f"HTTP {codigo} — {exc}"
            )
        return False

    except Exception as exc:
        logger.error(
            f"[PUSH] Error inesperado al enviar a suscripción id={suscripcion.pk}: {exc}",
            exc_info=True,
        )
        return False


def enviar_push_a_usuario(usuario: User, titulo: str, mensaje: str, url: str = '/') -> int:
    """
    Envía una notificación push a todas las suscripciones activas de un usuario.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Un usuario puede tener el sitio instalado en su teléfono Y en su computadora.
    Esta función envía la notificación a TODOS sus dispositivos suscritos.

    Args:
        usuario : El usuario de Django que debe recibir la notificación
        titulo  : Título corto (aparece en negrita en la notificación)
        mensaje : Texto del cuerpo de la notificación
        url     : URL a abrir cuando el usuario toca la notificación

    Returns:
        Número de suscripciones a las que se envió exitosamente.
    """
    if not _vapid_ok():
        logger.warning('[PUSH] VAPID keys no configuradas — notificación omitida.')
        return 0

    from notificaciones.models import PushSubscription  # noqa

    suscripciones = PushSubscription.objects.filter(usuario=usuario, activa=True)

    if not suscripciones.exists():
        return 0

    payload = {
        'titulo':  titulo,
        'mensaje': mensaje,
        'url':     url,
    }

    enviados = 0
    for suscripcion in suscripciones:
        if _enviar_una_suscripcion(suscripcion, payload):
            enviados += 1

    if enviados:
        logger.info(
            f'[PUSH] Enviado a {usuario.username}: "{titulo}" '
            f'— {enviados}/{suscripciones.count()} dispositivos'
        )

    return enviados


def enviar_push_a_cliente(enlace, titulo: str, mensaje: str, url: str = '/') -> int:
    """
    Envía una notificación push a todas las suscripciones activas de un CLIENTE.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Es el equivalente de 'enviar_push_a_usuario', pero para clientes finales
    que no tienen cuenta en el sistema. En vez de buscar por 'usuario',
    buscamos por 'enlace' (el EnlaceSeguimientoCliente / token único que el
    cliente abrió desde su correo).

    Args:
        enlace  : Instancia de EnlaceSeguimientoCliente dueña de las suscripciones
        titulo  : Título corto (aparece en negrita en la notificación)
        mensaje : Texto del cuerpo de la notificación
        url     : URL a abrir al tocar la notificación (normalmente su propia
                  página de seguimiento: /seguimiento/<token>/)

    Returns:
        Número de suscripciones a las que se envió exitosamente.
    """
    if not _vapid_ok():
        logger.warning('[PUSH] VAPID keys no configuradas — notificación a cliente omitida.')
        return 0

    # Import perezoso: PushSubscriptionCliente vive en este mismo módulo de
    # notificaciones, pero se importa aquí (no arriba) por consistencia con
    # el resto del archivo y para evitar problemas de import circular si en
    # el futuro el modelo depende de algo de servicio_tecnico.
    from notificaciones.models import PushSubscriptionCliente  # noqa

    suscripciones = PushSubscriptionCliente.objects.filter(enlace=enlace, activa=True)

    if not suscripciones.exists():
        return 0

    payload = {
        'titulo':  titulo,
        'mensaje': mensaje,
        'url':     url,
    }

    enviados = 0
    for suscripcion in suscripciones:
        if _enviar_una_suscripcion_cliente(suscripcion, payload):
            enviados += 1

    if enviados:
        logger.info(
            f'[PUSH] Enviado a cliente (token={enlace.token[:8]}...): "{titulo}" '
            f'— {enviados}/{suscripciones.count()} dispositivos'
        )

    return enviados


def _enviar_una_suscripcion_cliente(suscripcion, payload: dict) -> bool:
    """
    Igual que '_enviar_una_suscripcion', pero para PushSubscriptionCliente.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Se duplica esta función (en vez de reutilizar '_enviar_una_suscripcion')
    únicamente porque, al desactivar una suscripción expirada (HTTP 404/410),
    cada una debe actualizar su propio modelo — PushSubscription o
    PushSubscriptionCliente. El envío en sí (pywebpush) es idéntico.
    """
    from notificaciones.models import PushSubscriptionCliente  # noqa

    subscription_info = {
        "endpoint": suscripcion.endpoint,
        "keys": {
            "p256dh": suscripcion.p256dh,
            "auth": suscripcion.auth,
        },
    }

    vapid_claims = {
        "sub": f"mailto:{settings.VAPID_CLAIMS_EMAIL}",
    }

    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims=vapid_claims,
            content_encoding="aes128gcm",
            ttl=86400,
        )
        return True

    except WebPushException as exc:
        codigo = exc.response.status_code if exc.response is not None else None

        if codigo in (404, 410):
            logger.info(
                f"[PUSH] Suscripción de cliente expirada/revocada (HTTP {codigo}), "
                f"desactivando id={suscripcion.pk}"
            )
            PushSubscriptionCliente.objects.filter(pk=suscripcion.pk).update(activa=False)
        else:
            logger.error(
                f"[PUSH] Error al enviar a suscripción de cliente id={suscripcion.pk}: "
                f"HTTP {codigo} — {exc}"
            )
        return False

    except Exception as exc:
        logger.error(
            f"[PUSH] Error inesperado al enviar a suscripción de cliente id={suscripcion.pk}: {exc}",
            exc_info=True,
        )
        return False
