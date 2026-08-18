"""
Vistas del flujo de recotización (vigencia vencida)
====================================================

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Aquí vive la vista HTTP del botón "Solicitar Recotización" que aparece en el
detalle de una cotización cuando ya pasaron los 5 días hábiles de vigencia.

La vista es "delgada" a propósito: solo valida el método, pide permiso, llama
al cerebro (``almacen/utils/recotizacion.py``) y muestra un mensaje. Toda la
regla de negocio (qué se guarda, qué se limpia, a quién se avisa) vive en el
módulo de utilidades, no aquí.

``urls.py`` sigue apuntando a ``views.iniciar_recotizacion_solicitud`` porque
``views.py`` reexporta este nombre (patrón de fachada del proyecto).

Efectos secundarios:
- Crea una RondaCotizacion (snapshot) y reabre la solicitud en borrador
- Encola una tarea Celery que avisa a Compras
"""

import logging

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .decorators import permission_required_with_message
from .models import SolicitudCotizacion
from .utils.recotizacion import iniciar_nueva_ronda

logger = logging.getLogger('almacen')


@login_required
@permission_required_with_message('almacen.change_solicitudcotizacion')
@require_POST
def iniciar_recotizacion_solicitud(request, pk):
    """
    Abre una ronda nueva de cotización sobre una solicitud vencida.

    Objetivo principal (contexto de negocio):
        El cliente dejó pasar los 5 días hábiles y ahora quiere aceptar. Como
        los costos ya caducaron, esta vista devuelve la solicitud a Compras
        para que confirme disponibilidad y precio actualizado.

    Args:
        request (HttpRequest): Debe ser POST (protegido con @require_POST para
            que nadie dispare la recotización con un simple enlace).
        pk (int): ID de la SolicitudCotizacion vencida.

    Returns:
        HttpResponseRedirect: Siempre regresa al detalle de la solicitud, con
        un mensaje de éxito o de error según el resultado.

    Efectos secundarios:
        Ver ``almacen.utils.recotizacion.iniciar_nueva_ronda``: crea el
        snapshot, sube el contador de ronda, limpia precios congelados y
        encola el aviso a Compras.
    """
    solicitud = get_object_or_404(SolicitudCotizacion, pk=pk)

    # El motivo es opcional; lo captura el modal de confirmación
    observaciones = (request.POST.get('observaciones', '') or '').strip()

    try:
        # El cerebro valida internamente que sí se pueda recotizar y lanza
        # ValueError con un texto claro si no se cumple alguna condición.
        ronda = iniciar_nueva_ronda(
            solicitud,
            usuario=request.user,
            observaciones=observaciones,
        )

        messages.success(
            request,
            f'Se abrió la ronda {solicitud.ronda_cotizacion} de cotización. '
            f'Los precios de la ronda {ronda.numero_ronda} quedaron guardados '
            f'en el historial y la solicitud regresó a borrador para que '
            f'Compras confirme disponibilidad y costos actualizados.'
        )

    except ValueError as exc:
        # Caso esperado: la solicitud no cumple los requisitos (no venció o el
        # cliente ya respondió algo). Le explicamos al usuario por qué.
        messages.error(request, str(exc))

    except Exception as exc:  # pragma: no cover - error inesperado
        logger.error(
            '[RECOTIZACION] Error al recotizar %s: %s',
            solicitud.numero_solicitud,
            exc,
            exc_info=True,
        )
        messages.error(
            request,
            f'Ocurrió un error al iniciar la recotización: {exc}'
        )

    return redirect('almacen:detalle_solicitud_cotizacion', pk=solicitud.pk)
