"""
Vista: notificar al cliente que no hay piezas disponibles (PNC).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Cuando Compras/Front confirma que no hay refacciones en el mercado, pueden
avisar al cliente final (sin PDF de precios). Eso pasa la solicitud a
``enviada_cliente`` para desbloquear rechazo por línea y tipificación.

Con orden ST vinculada, el estado de la orden pasa a PNC (única fuente de
PNC en ST). El primer aviso exige que Front haya recibido plantilla PNC
(``plantilla_pnc_front_enviada``). También permite reenviar el aviso si
ya se marcó ``aviso_pnc_cliente_enviado``.
"""

from __future__ import annotations

import logging
import re

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from .decorators import permission_required_with_message
from .models import SolicitudCotizacion

logger = logging.getLogger('almacen')

# Validación simple de email (mismo criterio que api_enviar_cotizacion_cliente)
_RE_EMAIL = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')


@login_required
@permission_required_with_message('almacen.change_solicitudcotizacion')
@require_http_methods(['POST'])
def notificar_cliente_pnc(request, pk):
    """
    Avisa (o reenvía el aviso) al cliente: no hay piezas en el mercado.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Primer aviso (``enviada_front`` + ``plantilla_pnc_front_enviada``):
      1. Valida email y líneas.
      2. Pasa a ``enviada_cliente`` + marca ``aviso_pnc_cliente_enviado``.
      3. Si hay orden ST → PNC.
      4. Encola correo Celery.

    Reenvío (``enviada_cliente`` + flag PNC):
      - No vuelve a cambiar el estado de la solicitud.
      - Si ST ya está en PNC, solo deja comentario en historial.
      - Encola de nuevo el correo.

    Args:
        request: HttpRequest POST (email_cliente, mensaje_personalizado, CC).
        pk: ID de SolicitudCotizacion.

    Returns:
        JsonResponse con success / error.
    """
    from config.paises_config import get_pais_actual

    from almacen.tasks import notificar_cliente_pnc_task
    from almacen.utils.sincronizar_estado_st import (
        sincronizar_estado_st_al_notificar_cliente_pnc,
    )

    try:
        solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)

        # Primer aviso / reenvío: misma regla que la UI (métodos del modelo)
        es_primer_aviso = solicitud.puede_notificar_cliente_pnc()
        es_reenvio = solicitud.puede_reenviar_aviso_pnc()
        if not es_primer_aviso and not es_reenvio:
            # Mensaje distinto si está en Front pero sin plantilla PNC
            if (
                solicitud.estado == 'enviada_front'
                and not solicitud.plantilla_pnc_front_enviada
            ):
                error_msg = (
                    'Solo puedes avisar PNC al cliente si Front recibió la '
                    'plantilla «Partes no disponibles (PNC)». '
                    'Reenvía la notificación a Front con esa plantilla, '
                    'o usa «Enviar Cotización al Cliente».'
                )
            else:
                error_msg = (
                    'Solo se puede notificar PNC al cliente desde «Enviada a Front» '
                    'con plantilla PNC, o reenviar el aviso si esa solicitud ya '
                    'fue notificada con PNC.'
                )
            return JsonResponse({
                'success': False,
                'error': error_msg,
            }, status=400)

        if not solicitud.lineas.exists():
            return JsonResponse({
                'success': False,
                'error': 'La solicitud debe tener al menos una línea.',
            }, status=400)

        email_cliente = (request.POST.get('email_cliente') or '').strip()
        if not email_cliente:
            return JsonResponse({
                'success': False,
                'error': 'El email del cliente es requerido.',
            }, status=400)
        if not _RE_EMAIL.match(email_cliente):
            return JsonResponse({
                'success': False,
                'error': f'El email "{email_cliente}" no tiene formato válido.',
            }, status=400)

        mensaje_personalizado = (
            request.POST.get('mensaje_personalizado') or ''
        ).strip()
        # EXPLICACIÓN: CC opcionales (empleados seleccionados en el modal)
        copia_empleados = request.POST.getlist('copia_empleados', [])

        # Guardar email en la solicitud si estaba vacío (útil en sin_orden)
        if not (solicitud.email_cliente or '').strip():
            solicitud.email_cliente = email_cliente
            solicitud.save(update_fields=['email_cliente'])

        if es_primer_aviso:
            # Pasar a enviada_cliente para desbloquear respuestas / tipificación
            if not solicitud.enviar_a_cliente(usuario=request.user):
                return JsonResponse({
                    'success': False,
                    'error': 'No se pudo cambiar el estado a «Enviada al Cliente».',
                }, status=400)

            # EXPLICACIÓN: el flag habilita reenvío y bloquea aprobar hasta cotización/REAC
            solicitud.aviso_pnc_cliente_enviado = True
            solicitud.save(update_fields=['aviso_pnc_cliente_enviado'])

        # Con orden: ST → PNC (o comentario de reaviso si ya estaba en PNC)
        sincronizar_estado_st_al_notificar_cliente_pnc(
            solicitud,
            usuario=request.user,
        )

        usuario_id = request.user.pk if request.user.is_authenticated else None
        tarea = notificar_cliente_pnc_task.delay(
            solicitud_id=pk,
            email_cliente=email_cliente,
            mensaje_personalizado=mensaje_personalizado,
            copia_empleados=copia_empleados,
            usuario_id=usuario_id,
            db_alias=get_pais_actual()['db_alias'],
        )

        if es_reenvio:
            mensaje_ok = (
                f'Reenvío del aviso PNC en proceso hacia {email_cliente}.'
            )
        else:
            mensaje_ok = (
                f'Aviso PNC en proceso de envío a {email_cliente}. '
                f'Ya puedes registrar el rechazo de las líneas.'
            )

        return JsonResponse({
            'success': True,
            'message': mensaje_ok,
            'data': {
                'task_id': tarea.id,
                'email_cliente': email_cliente,
                'solicitud': solicitud.numero_solicitud,
                'estado': solicitud.estado,
                'es_reenvio': es_reenvio,
            },
        })

    except Exception as e:
        logger.exception('[PNC-CLIENTE] Error en notificar_cliente_pnc: %s', e)
        return JsonResponse({
            'success': False,
            'error': f'Error al procesar la solicitud: {str(e)}',
        }, status=500)
