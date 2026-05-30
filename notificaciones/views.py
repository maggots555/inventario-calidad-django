"""
Vistas (endpoints) para el panel de notificaciones.

EXPLICACIÓN PARA PRINCIPIANTES:
Estas vistas NO devuelven HTML como las vistas normales de Django.
Devuelven JSON (datos estructurados) que TypeScript lee periódicamente.

¿Qué es JSON?
Es un formato de texto que JavaScript/TypeScript entiende nativamente.
Ejemplo: {"no_leidas": 3, "notificaciones": [{...}, {...}]}

Optimización de producción:
La vista de listar usa cache de Redis (10 segundos) para evitar consultas
a la base de datos en cada polling. Las vistas de escritura (marcar, eliminar)
invalidan el cache automáticamente para que el próximo polling refleje los cambios.

Endpoints disponibles (campanita 🔔):
    GET  /notificaciones/api/listar/           → Lista últimas 20 notificaciones
    POST /notificaciones/api/marcar/<id>/      → Marca una como leída
    POST /notificaciones/api/marcar-todas/     → Marca todas como leídas
    POST /notificaciones/api/eliminar/<id>/    → Elimina una notificación
    POST /notificaciones/api/eliminar-todas/   → Elimina todas las notificaciones

Endpoints Web Push:
    GET  /notificaciones/push/vapid-key/       → Devuelve la llave pública VAPID
    POST /notificaciones/push/suscribir/       → Guarda una suscripción push
    POST /notificaciones/push/cancelar/        → Desactiva suscripción push
"""

import json
import logging

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

from .models import Notificacion, PushSubscription

logger = logging.getLogger('notificaciones')

# ── Constantes de cache ──
# EXPLICACIÓN PARA PRINCIPIANTES:
# El "cache" guarda las notificaciones en Redis (memoria RAM) por 10 segundos.
# Si 5 usuarios tienen la pestaña abierta y hacen polling cada 15s,
# sin cache: ~20 consultas SQL por minuto (5 users × 4 polls).
# Con cache: solo 6 consultas SQL por minuto (1 cada 10s por usuario).
# En un intervalo de 60s (modo idle), la mejora es aún mayor.
CACHE_TTL_NOTIF: int = 10  # segundos


def _cache_key(user_id: int) -> str:
    """Genera la clave de cache única por usuario.

    EXPLICACIÓN: Cada usuario tiene sus propias notificaciones,
    así que el cache debe ser individual. La clave sigue el formato:
    'notif:42' donde 42 es el ID del usuario.
    """
    return f'notif:{user_id}'


def _invalidar_cache(user_id: int) -> None:
    """Borra el cache de notificaciones de un usuario.

    EXPLICACIÓN: Se llama después de marcar como leída, eliminar, etc.
    Al borrar el cache, el próximo polling consultará la BD con datos frescos.
    """
    cache.delete(_cache_key(user_id))


@login_required
@require_GET
def obtener_notificaciones(request):
    """
    Devuelve las últimas 20 notificaciones del usuario en formato JSON.

    EXPLICACIÓN PARA PRINCIPIANTES:
    TypeScript llama a esta URL periódicamente con fetch().
    La respuesta incluye:
    - no_leidas: número de notificaciones sin leer (para el badge rojo)
    - notificaciones: lista con las últimas 20 (leídas y no leídas)

    Optimización con cache:
    El resultado se guarda en Redis por 10 segundos. Si TypeScript
    hace polling cada 15s, como máximo 1 de cada 2 requests llega
    a la base de datos. En modo idle (60s), puede servir hasta 6
    requests seguidos desde cache sin tocar la BD.
    """
    user = request.user
    key = _cache_key(user.id)

    # ── Intentar leer del cache (Redis) ──
    # EXPLICACIÓN: cache.get() busca en Redis. Si encuentra datos,
    # los devuelve sin consultar la base de datos — mucho más rápido.
    data = cache.get(key)

    if data is None:
        # Cache vacío o expirado → consultar la BD
        notificaciones = Notificacion.objects.filter(
            usuario=user
        ).order_by('-fecha_creacion')[:20]

        no_leidas = Notificacion.objects.filter(
            usuario=user,
            leida=False
        ).count()

        data = {
            'no_leidas': no_leidas,
            'notificaciones': [
                {
                    'id':     n.id,
                    'titulo': n.titulo,
                    'mensaje': n.mensaje,
                    'tipo':   n.tipo,
                    'leida':  n.leida,
                    'fecha':  n.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
                    'app':    n.app_origen or '',
                    'url':    n.url or '',
                }
                for n in notificaciones
            ]
        }

        # Guardar en Redis por CACHE_TTL_NOTIF segundos
        cache.set(key, data, CACHE_TTL_NOTIF)

    return JsonResponse(data)


@login_required
@require_POST
def marcar_leida(request, notificacion_id):
    """
    Marca una notificación específica como leída.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Cuando el usuario hace clic en una notificación individual,
    TypeScript envía un POST a esta URL con el ID de la notificación.
    Solo puede marcar sus propias notificaciones (seguridad).
    """
    try:
        notif = Notificacion.objects.get(
            id=notificacion_id,
            usuario=request.user
        )
        notif.leida = True
        notif.save(update_fields=['leida'])
        _invalidar_cache(request.user.id)
        return JsonResponse({'ok': True})
    except Notificacion.DoesNotExist:
        return JsonResponse(
            {'ok': False, 'error': 'Notificación no encontrada'},
            status=404
        )


@login_required
@require_POST
def marcar_todas_leidas(request):
    """
    Marca TODAS las notificaciones no leídas del usuario como leídas.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Se llama cuando el usuario abre el dropdown de la campanita.
    .update(leida=True) es más eficiente que recorrer una por una,
    porque hace una sola consulta SQL: UPDATE ... SET leida=True WHERE ...
    """
    actualizadas = Notificacion.objects.filter(
        usuario=request.user,
        leida=False
    ).update(leida=True)

    _invalidar_cache(request.user.id)

    logger.info(
        f"[NOTIF] {request.user.username} marcó {actualizadas} notificación(es) como leída(s)."
    )

    return JsonResponse({'ok': True, 'actualizadas': actualizadas})


@login_required
@require_POST
def eliminar_notificacion(request, notificacion_id):
    """
    Elimina una notificación específica del usuario.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Cuando el usuario hace clic en la ✕ de una notificación,
    TypeScript envía un POST a esta URL para borrarla de la BD.
    Solo puede eliminar sus propias notificaciones (seguridad).
    """
    try:
        notif = Notificacion.objects.get(
            id=notificacion_id,
            usuario=request.user
        )
        notif.delete()
        _invalidar_cache(request.user.id)
        return JsonResponse({'ok': True})
    except Notificacion.DoesNotExist:
        return JsonResponse(
            {'ok': False, 'error': 'Notificación no encontrada'},
            status=404
        )


@login_required
@require_POST
def eliminar_todas(request):
    """
    Elimina TODAS las notificaciones del usuario.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Botón "Limpiar todas" en el panel. Borra todo de una vez
    para que el usuario no tenga que eliminar una por una.
    """
    eliminadas, _ = Notificacion.objects.filter(
        usuario=request.user
    ).delete()

    _invalidar_cache(request.user.id)

    logger.info(
        f"[NOTIF] {request.user.username} eliminó {eliminadas} notificación(es)."
    )

    return JsonResponse({'ok': True, 'eliminadas': eliminadas})


# ══════════════════════════════════════════════════════════════════════════════
# WEB PUSH — Endpoints de suscripción
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_GET
def vapid_public_key(request):
    """
    Devuelve la llave pública VAPID al navegador.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Antes de suscribirse a push, el navegador necesita conocer la llave pública
    del servidor para poder cifrar los mensajes. Esta vista se la entrega.
    Es como darle la dirección de tu buzón de correo al cartero.

    La llave está en settings.py (leída desde .env) y es segura de publicar.
    """
    return JsonResponse({'vapid_public_key': settings.VAPID_PUBLIC_KEY})


@login_required
@require_POST
def suscribir_push(request):
    """
    Guarda o reactiva la suscripción push de un usuario.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Cuando el usuario acepta las notificaciones, el navegador nos da tres datos:
    - endpoint : URL del servidor push del navegador
    - p256dh   : Clave pública del navegador (para cifrar)
    - auth     : Token secreto del navegador (para autenticar)

    Guardamos esos datos en PushSubscription para poder enviar notificaciones
    después. Si ya existe una suscripción para ese endpoint (mismo dispositivo),
    la reactivamos en vez de crear una nueva.

    Body esperado (JSON):
    {
        "endpoint": "https://...",
        "keys": { "p256dh": "...", "auth": "..." }
    }
    """
    try:
        data = json.loads(request.body)
        endpoint = data.get('endpoint', '').strip()
        keys     = data.get('keys', {})
        p256dh   = keys.get('p256dh', '').strip()
        auth     = keys.get('auth', '').strip()

        if not all([endpoint, p256dh, auth]):
            return JsonResponse(
                {'ok': False, 'error': 'Datos de suscripción incompletos'},
                status=400
            )

        user_agent = request.META.get('HTTP_USER_AGENT', '')[:300]

        # update_or_create: si ya existe ese endpoint para este usuario,
        # lo reactiva; si no existe, lo crea nuevo.
        suscripcion, creada = PushSubscription.objects.update_or_create(
            usuario=request.user,
            endpoint=endpoint,
            defaults={
                'p256dh':     p256dh,
                'auth':       auth,
                'activa':     True,
                'user_agent': user_agent,
            }
        )

        accion = 'creada' if creada else 'reactivada'
        logger.info(
            f'[PUSH] Suscripción {accion} para {request.user.username} '
            f'(id={suscripcion.pk})'
        )

        return JsonResponse({'ok': True, 'accion': accion})

    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)
    except Exception as exc:
        logger.error(f'[PUSH] Error al guardar suscripción: {exc}', exc_info=True)
        return JsonResponse({'ok': False, 'error': 'Error interno'}, status=500)


@login_required
@require_POST
def cancelar_push(request):
    """
    Desactiva la suscripción push de un usuario para un endpoint específico.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Cuando el usuario desactiva las notificaciones desde su perfil,
    marcamos su suscripción como inactiva (no la borramos, por si la reactiva).

    Body esperado (JSON):
    { "endpoint": "https://..." }
    """
    try:
        data     = json.loads(request.body)
        endpoint = data.get('endpoint', '').strip()

        if not endpoint:
            # Si no viene endpoint, desactivar TODAS las suscripciones del usuario
            desactivadas = PushSubscription.objects.filter(
                usuario=request.user, activa=True
            ).update(activa=False)
        else:
            desactivadas = PushSubscription.objects.filter(
                usuario=request.user, endpoint=endpoint, activa=True
            ).update(activa=False)

        logger.info(
            f'[PUSH] {desactivadas} suscripción(es) desactivada(s) '
            f'para {request.user.username}'
        )

        return JsonResponse({'ok': True, 'desactivadas': desactivadas})

    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)
    except Exception as exc:
        logger.error(f'[PUSH] Error al cancelar suscripción: {exc}', exc_info=True)
        return JsonResponse({'ok': False, 'error': 'Error interno'}, status=500)
