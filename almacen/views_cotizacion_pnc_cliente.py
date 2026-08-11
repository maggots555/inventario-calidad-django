"""
Vista: notificar al cliente que no hay piezas disponibles (PNC).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Cuando Compras/Front confirma que no hay refacciones en el mercado, pueden
avisar al cliente final (sin PDF de precios). Eso pasa la solicitud a
``enviada_cliente`` para desbloquear rechazo por línea y tipificación.

Con orden ST vinculada, el estado de la orden pasa a PNC.
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
    Avisa al cliente que no hay piezas en el mercado y abre el flujo de rechazo.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    1. Valida que la solicitud esté en ``enviada_front`` y tenga líneas.
    2. Exige un email de cliente válido.
    3. Cambia la solicitud a ``enviada_cliente`` (desbloquea aprobar/rechazar).
    4. Si hay orden ST, la sincroniza a PNC.
    5. Encola el correo Celery (plantilla PNC al cliente).

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

        # Solo desde «Enviada a Front» (mismo momento que enviar cotización)
        if solicitud.estado != 'enviada_front':
            return JsonResponse({
                'success': False,
                'error': (
                    'Solo se puede notificar PNC al cliente cuando la solicitud '
                    'está en «Enviada a Front».'
                ),
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

        # Pasar a enviada_cliente para desbloquear respuestas / tipificación
        if not solicitud.enviar_a_cliente(usuario=request.user):
            return JsonResponse({
                'success': False,
                'error': 'No se pudo cambiar el estado a «Enviada al Cliente».',
            }, status=400)

        # Con orden: ST → PNC (si aplica)
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

        return JsonResponse({
            'success': True,
            'message': (
                f'Aviso PNC en proceso de envío a {email_cliente}. '
                f'Ya puedes registrar el rechazo de las líneas.'
            ),
            'data': {
                'task_id': tarea.id,
                'email_cliente': email_cliente,
                'solicitud': solicitud.numero_solicitud,
                'estado': solicitud.estado,
            },
        })

    except Exception as e:
        logger.exception('[PNC-CLIENTE] Error en notificar_cliente_pnc: %s', e)
        return JsonResponse({
            'success': False,
            'error': f'Error al procesar la solicitud: {str(e)}',
        }, status=500)
