"""
Vistas (endpoints) para el panel de notificaciones.

EXPLICACIÓN PARA PRINCIPIANTES:
Estas vistas NO devuelven HTML como las vistas normales de Django.
Devuelven JSON (datos estructurados) que TypeScript lee periódicamente.

¿Qué es JSON?
Es un formato de texto que JavaScript/TypeScript entiende nativamente.
Ejemplo: {"no_leidas_accion": 3, "accion": [{...}], "avisos": [{...}]}

Optimización de producción:
La vista de listar usa cache de Redis (10 segundos) para evitar consultas
a la base de datos en cada polling. Las vistas de escritura (marcar, eliminar)
invalidan el cache automáticamente para que el próximo polling refleje los cambios.

Endpoints disponibles (campanita 🔔):
    GET  /notificaciones/api/listar/           → Dos cortes: Por hacer + Avisos
    POST /notificaciones/api/marcar/<id>/      → Marca una como leída
    POST /notificaciones/api/marcar-todas/     → Marca todas como leídas (botón ✓✓)
    POST /notificaciones/api/marcar-avisos/    → Marca solo informativas (al abrir)
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
from django.db.models import Count, Q
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET

from .models import Notificacion, PushSubscription
from .utils import clave_cache_notificaciones, invalidar_cache_notificaciones

logger = logging.getLogger('notificaciones')

# ── Constantes de cache ──
# EXPLICACIÓN PARA PRINCIPIANTES:
# El "cache" guarda las notificaciones en Redis (memoria RAM) por 10 segundos.
# Si 5 usuarios tienen la pestaña abierta y hacen polling cada 15s,
# sin cache: ~20 consultas SQL por minuto (5 users × 4 polls).
# Con cache: solo 6 consultas SQL por minuto (1 cada 10s por usuario).
# En un intervalo de 60s (modo idle), la mejora es aún mayor.
CACHE_TTL_NOTIF: int = 10  # segundos
# Tope por pestaña: 20 de «Por hacer» y 20 de «Avisos», independientes.
LIMITE_LISTA_NOTIF: int = 20


def _cache_key(user_id: int) -> str:
    """Clave Redis v2 por usuario (delegada a utils).

    Args:
        user_id: PK del usuario.

    Returns:
        str: ``notif:v2:{id}``.
    """
    return clave_cache_notificaciones(user_id)


def _invalidar_cache(user_id: int) -> None:
    """Borra el cache de notificaciones de un usuario.

    EXPLICACIÓN: Se llama después de marcar como leída, eliminar, etc.
    Al borrar el cache, el próximo polling consultará la BD con datos frescos.
    """
    invalidar_cache_notificaciones(user_id)


def _contadores_usuario(user) -> dict:
    """Cuenta no leídas reales en BD (no el tope de 20 de la lista).

    EXPLICACIÓN: El badge y los numeritos de pestaña deben reflejar TODAS
    las pendientes, aunque la lista solo muestre las 20 más recientes.
    Un solo ``aggregate`` evita tres COUNT separados.

    Args:
        user: Usuario autenticado dueño de las notificaciones.

    Returns:
        dict: no_leidas, no_leidas_accion, no_leidas_avisos, no_leidas_equipo.
    """
    agg = Notificacion.objects.filter(usuario=user).aggregate(
        no_leidas_accion=Count(
            'pk', filter=Q(requiere_accion=True, leida=False)
        ),
        no_leidas_avisos=Count(
            'pk', filter=Q(requiere_accion=False, leida=False)
        ),
        no_leidas_equipo=Count(
            'pk',
            filter=Q(
                requiere_accion=True,
                leida=False,
                categoria='equipo_disponible',
            ),
        ),
    )
    accion = int(agg['no_leidas_accion'] or 0)
    avisos = int(agg['no_leidas_avisos'] or 0)
    equipo = int(agg['no_leidas_equipo'] or 0)
    return {
        'no_leidas': accion,
        'no_leidas_accion': accion,
        'no_leidas_avisos': avisos,
        'no_leidas_equipo': equipo,
    }


def _cortar_lista(queryset, limite: int) -> tuple[list, bool]:
    """Devuelve hasta ``limite`` filas y si había más detrás.

    Pide limite+1 para no hacer un COUNT extra: si llegan 21, hay más.

    Args:
        queryset: QuerySet ya filtrado y ordenado.
        limite: Tope visible (20).

    Returns:
        tuple: (lista de modelos, hay_mas).
    """
    filas = list(queryset[: limite + 1])
    hay_mas = len(filas) > limite
    return filas[:limite], hay_mas


def _json_escritura_ok(user, extra: dict | None = None) -> JsonResponse:
    """Respuesta POST exitosa con contadores frescos (el cliente no adivina).

    Args:
        user: Usuario de la request.
        extra: Campos extra (actualizadas, eliminadas, …).

    Returns:
        JsonResponse con ok=True y contadores.
    """
    payload = {'ok': True}
    payload.update(_contadores_usuario(user))
    if extra:
        payload.update(extra)
    return JsonResponse(payload)


def _serializar_notificacion(n: Notificacion) -> dict:
    """Convierte un registro Notificacion al dict que consume TypeScript.

    Args:
        n: Instancia de Notificacion.

    Returns:
        dict: Campos del ítem de la campanita.
    """
    return {
        'id': n.id,
        'titulo': n.titulo,
        'mensaje': n.mensaje,
        'tipo': n.tipo,
        'categoria': n.categoria or 'general',
        'requiere_accion': bool(n.requiere_accion),
        'leida': n.leida,
        'fecha': n.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
        'app': n.app_origen or '',
        'url': n.url or '',
    }


@login_required
@require_GET
def obtener_notificaciones(request):
    """
    Devuelve dos cortes independientes: Por hacer y Avisos.

    EXPLICACIÓN PARA PRINCIPIANTES:
    TypeScript llama a esta URL periódicamente con fetch().
    Antes se devolvían las últimas 20 mezcladas: un correo de «video listo»
    tapaba un pago por validar. Ahora cada pestaña tiene su propio tope de 20.

    La respuesta incluye:
    - no_leidas / no_leidas_accion: pendientes de acción (badge de la campanita)
    - no_leidas_avisos: informativas sin leer
    - no_leidas_equipo: acción + categoria equipo_disponible (chip)
    - hay_mas_accion / hay_mas_avisos: True si hay más de 20 en ese corte
    - accion / avisos: listas (leídas y no leídas, más recientes primero)

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
        # Cache vacío o expirado → consultar la BD (un queryset base).
        qs = Notificacion.objects.filter(usuario=user)
        # Paso 1: dos cortes; limite+1 detecta si hay más sin un COUNT extra.
        accion, hay_mas_accion = _cortar_lista(
            qs.filter(requiere_accion=True).order_by('-fecha_creacion'),
            LIMITE_LISTA_NOTIF,
        )
        avisos, hay_mas_avisos = _cortar_lista(
            qs.filter(requiere_accion=False).order_by('-fecha_creacion'),
            LIMITE_LISTA_NOTIF,
        )

        # Paso 2: contadores sobre TODA la BD del usuario, no solo las 20.
        data = _contadores_usuario(user)
        # Paso 3: el badge usa no_leidas_accion (trabajo pendiente, no ruido).
        data.update({
            'hay_mas_accion': hay_mas_accion,
            'hay_mas_avisos': hay_mas_avisos,
            'accion': [_serializar_notificacion(n) for n in accion],
            'avisos': [_serializar_notificacion(n) for n in avisos],
        })

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
        return _json_escritura_ok(request.user)
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
    Se llama desde el botón ✓✓ del header. Las de «Por hacer» NO se
    marcan al abrir el panel (solo las informativas, ver marcar_avisos).
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

    return _json_escritura_ok(request.user, extra={'actualizadas': actualizadas})


@login_required
@require_POST
def marcar_avisos_leidos(request):
    """
    Marca como leídas solo las notificaciones informativas («Avisos»).

    EXPLICACIÓN PARA PRINCIPIANTES:
    Al abrir la campanita no queremos apagar el badge de trabajo pendiente.
    Este endpoint deja intactas las de ``requiere_accion=True`` (Por hacer)
    y solo marca las informativas: correo enviado, video listo, etc.

    Efectos secundarios:
        UPDATE en BD + invalida cache Redis del usuario.
    """
    actualizadas = Notificacion.objects.filter(
        usuario=request.user,
        leida=False,
        requiere_accion=False,
    ).update(leida=True)

    _invalidar_cache(request.user.id)

    logger.info(
        f"[NOTIF] {request.user.username} marcó {actualizadas} aviso(s) "
        f"informativo(s) como leído(s)."
    )

    return _json_escritura_ok(request.user, extra={'actualizadas': actualizadas})


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
        return _json_escritura_ok(request.user)
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

    return _json_escritura_ok(request.user, extra={'eliminadas': eliminadas})


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
