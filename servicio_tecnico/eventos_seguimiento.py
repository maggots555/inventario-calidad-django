"""
eventos_seguimiento.py — Registro centralizado de eventos de producto del cliente.

EXPLICACIÓN PARA PRINCIPIANTES:
Este módulo vive aparte de views.py para no inflar un archivo ya enorme.
Aquí definimos:
  1. Qué tipos de evento existen y cuáles puede enviar el navegador (cliente)
     vs. cuáles solo registra el servidor (push, visita, chat).
  2. La función registrar_evento_seguimiento() que inserta filas en BD de
     forma segura (si falla, no rompe la visita ni el push del cliente).
  3. Helpers para el dashboard (embudo, anotaciones por enlace).
"""

from __future__ import annotations

import logging
from typing import Any

from django.db.models import Exists, OuterRef, QuerySet

logger = logging.getLogger(__name__)

# Tipos que el navegador puede reportar vía POST /seguimiento/<token>/eventos/
TIPOS_EVENTO_CLIENTE: frozenset[str] = frozenset({
    'pwa_banner_mostrado',
    'pwa_banner_cerrado',
    'pwa_prompt_aceptado',
    'pwa_prompt_rechazado',
    'pwa_instalada',
    'pwa_modo_standalone',
    'push_permiso_denegado',
    'chat_abierto',
})


def _tipos_validos() -> frozenset[str]:
    from servicio_tecnico.models import EventoSeguimientoCliente
    return frozenset(t for t, _ in EventoSeguimientoCliente.TIPO_CHOICES)


def _extraer_ip(request) -> str | None:
    """Obtiene la IP del cliente respetando proxy inverso (X-Forwarded-For)."""
    if request is None:
        return None
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def registrar_evento_seguimiento(
    enlace,
    tipo: str,
    request=None,
    session_id: str = '',
    metadata: dict[str, Any] | None = None,
) -> bool:
    """
    Inserta un EventoSeguimientoCliente de forma fail-safe.

    Args:
        enlace: instancia de EnlaceSeguimientoCliente
        tipo: código del evento (ver TIPO_CHOICES del modelo)
        request: HttpRequest opcional para IP y user_agent
        session_id: UUID de sesión del navegador (agrupa eventos de una visita)
        metadata: dict extra; nunca debe incluir texto del chat del cliente

    Returns:
        True si se guardó, False si falló o el tipo no es válido.
    """
    from servicio_tecnico.models import EventoSeguimientoCliente

    if tipo not in _tipos_validos():
        logger.warning('[EventosSeg] Tipo de evento no válido: %s', tipo)
        return False

    meta = metadata if metadata is not None else {}
    user_agent = ''
    ip = None
    if request is not None:
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:300]
        ip = _extraer_ip(request)

    try:
        EventoSeguimientoCliente.objects.create(
            enlace=enlace,
            tipo=tipo,
            session_id=(session_id or '')[:36],
            metadata=meta,
            user_agent=user_agent,
            ip=ip,
        )
        return True
    except Exception as exc:
        logger.warning(
            '[EventosSeg] No se pudo registrar evento %s para enlace %s: %s',
            tipo, getattr(enlace, 'pk', '?'), exc,
        )
        return False


def _subquery_evento(tipo: str):
    """Subconsulta Exists: ¿este enlace tiene al menos un evento del tipo dado?"""
    from servicio_tecnico.models import EventoSeguimientoCliente

    return EventoSeguimientoCliente.objects.filter(
        enlace=OuterRef('pk'),
        tipo=tipo,
    )


def anotar_eventos_enlaces(qs: QuerySet) -> QuerySet:
    """
    Anota un queryset de EnlaceSeguimientoCliente con flags de eventos clave
    para la tabla del dashboard.
    """
    from servicio_tecnico.models import EventoSeguimientoCliente

    pwa_instalada_qs = EventoSeguimientoCliente.objects.filter(
        enlace=OuterRef('pk'),
        tipo__in=['pwa_instalada', 'pwa_modo_standalone'],
    )
    return qs.annotate(
        evento_pwa_banner_visto=Exists(_subquery_evento('pwa_banner_mostrado')),
        evento_pwa_instalada=Exists(pwa_instalada_qs),
        evento_chat_usado=Exists(_subquery_evento('chat_mensaje_enviado')),
        evento_diagnostico_pdf_abierto=Exists(_subquery_evento('diagnostico_pdf_abierto')),
    )


def calcular_embudo_enlaces(qs: QuerySet) -> dict:
    """
    Calcula métricas del embudo de adopción para el queryset filtrado.

    Returns:
        dict con total_enlaces, pasos (lista ordenada con totales y tasas %)
    """
    # anotar_push_enlaces vive en este mismo módulo (antes estaba en views.py).
    qs = anotar_eventos_enlaces(anotar_push_enlaces(qs))
    total = qs.count()

    def tasa(n: int) -> float:
        return round((n / total * 100) if total > 0 else 0, 1)

    correos = qs.filter(correo_enviado=True).count()
    con_visita = qs.filter(accesos_count__gt=0).count()
    pwa_banner = qs.filter(evento_pwa_banner_visto=True).count()
    pwa_inst = qs.filter(evento_pwa_instalada=True).count()
    push_act = qs.filter(push_activo=True).count()
    chat_uso = qs.filter(evento_chat_usado=True).count()
    pdf_dx = qs.filter(evento_diagnostico_pdf_abierto=True).count()
    con_pdf_dx = qs.exclude(pdf_diagnostico='').exclude(pdf_diagnostico__isnull=True).count()

    pasos = [
        {'id': 'correo_enviado', 'label': 'Correo enviado', 'total': correos, 'tasa': tasa(correos)},
        {'id': 'con_visita', 'label': 'Abrió el enlace', 'total': con_visita, 'tasa': tasa(con_visita)},
        {'id': 'pwa_banner_visto', 'label': 'Vio banner PWA', 'total': pwa_banner, 'tasa': tasa(pwa_banner)},
        {'id': 'pwa_instalada', 'label': 'PWA instalada / modo app', 'total': pwa_inst, 'tasa': tasa(pwa_inst)},
        {'id': 'push_activo', 'label': 'Push activo', 'total': push_act, 'tasa': tasa(push_act)},
        {'id': 'diagnostico_pdf_abierto', 'label': 'Abrió PDF de diagnóstico', 'total': pdf_dx, 'tasa': tasa(pdf_dx)},
        {'id': 'chat_usado', 'label': 'Usó el chat IA', 'total': chat_uso, 'tasa': tasa(chat_uso)},
    ]

    return {
        'total_enlaces': total,
        'pasos': pasos,
        'push_suscritos': push_act,
        'push_sin_suscripcion': total - push_act,
        'tasa_push': tasa(push_act),
        'con_pdf_diagnostico': con_pdf_dx,
        'pdf_diagnostico_abiertos': pdf_dx,
    }


# ---------------------------------------------------------------------------
# Helpers de queryset para el dashboard de enlaces (movidos desde views.py)
# ---------------------------------------------------------------------------

def filtrar_enlaces_seguimiento(request):
    """
    Helper: construye queryset base de EnlaceSeguimientoCliente
    aplicando los filtros GET comunes (fecha, responsable, sucursal, tipo_orden).
    """
    from .models import EnlaceSeguimientoCliente

    qs = EnlaceSeguimientoCliente.objects.select_related(
        'orden__responsable_seguimiento',
        'orden__sucursal',
        'orden__detalle_equipo',
    )

    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    responsable_id = request.GET.get('responsable_id')
    sucursal_id = request.GET.get('sucursal_id')
    tipo_orden = request.GET.get('tipo_orden')

    if fecha_desde:
        qs = qs.filter(fecha_creacion__date__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha_creacion__date__lte=fecha_hasta)
    if responsable_id:
        qs = qs.filter(orden__responsable_seguimiento_id=responsable_id)
    if sucursal_id:
        qs = qs.filter(orden__sucursal_id=sucursal_id)
    if tipo_orden and tipo_orden in ('diagnostico', 'venta_mostrador'):
        qs = qs.filter(orden__tipo_servicio=tipo_orden)

    return qs

# Alias con guion bajo: compatibilidad con código que aún use el nombre antiguo
_filtrar_enlaces_seguimiento = filtrar_enlaces_seguimiento


def anotar_push_enlaces(qs):
    """
    Anota un queryset de EnlaceSeguimientoCliente con métricas de push del cliente.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Cada enlace puede tener cero o más PushSubscriptionCliente (un dispositivo/navegador).
    Aquí calculamos en una sola consulta SQL si hay al menos una suscripción activa,
    cuántos dispositivos activos hay y la fecha más reciente de suscripción.
    """
    from django.db.models import Count, Exists, Max, OuterRef, Q
    from notificaciones.models import PushSubscriptionCliente

    subs_activas = PushSubscriptionCliente.objects.filter(
        enlace=OuterRef('pk'),
        activa=True,
    )
    return qs.annotate(
        push_activo=Exists(subs_activas),
        push_dispositivos=Count(
            'push_subscriptions',
            filter=Q(push_subscriptions__activa=True),
        ),
        push_fecha=Max(
            'push_subscriptions__fecha_creada',
            filter=Q(push_subscriptions__activa=True),
        ),
    )

_anotar_push_enlaces = anotar_push_enlaces
