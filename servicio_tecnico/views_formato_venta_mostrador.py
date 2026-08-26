"""
Vistas del Formato Digital de Venta Mostrador (Nota de Venta Directa).

EXPLICACIÓN PARA PRINCIPIANTES:
------------------------------------------------
Módulo hermano (no monolito): wizard, guardado AJAX, finalización,
preview PDF y reenvío de correo.

urls.py usa views.* gracias a los reexports en views.py.
A diferencia de OOW, finalizar NUNCA exige firma ni daños.
"""

from __future__ import annotations

import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .decorators import permission_required_with_message
from .models import OrdenServicio

logger = logging.getLogger(__name__)


def _json_error(mensaje: str, status: int = 400) -> JsonResponse:
    return JsonResponse({'success': False, 'error': mensaje}, status=status)


@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
def formato_venta_mostrador_wizard(request, orden_id: int):
    """
    Pantalla wizard de la Nota de Venta Directa (iPad/PWA).

    Args:
        request: HttpRequest autenticado
        orden_id: PK de OrdenServicio

    Efectos secundarios:
        Puede crear un borrador FormatoServicioVentaMostrador si no existe.
    """
    from config.constants import (
        VISTAS_DANO_ESTETICO_AIO,
        VISTAS_DANO_ESTETICO_ESCRITORIO,
        VISTAS_DANO_ESTETICO_LAPTOP,
    )
    from .services.formato_venta_mostrador import (
        datos_orden_para_wizard,
        obtener_o_crear_borrador,
        orden_es_candidata_formato_venta_mostrador,
        serializar_formato,
    )

    orden = get_object_or_404(
        OrdenServicio.objects.select_related(
            'detalle_equipo',
            'sucursal',
            'venta_mostrador',
        ),
        pk=orden_id,
    )
    if not orden_es_candidata_formato_venta_mostrador(orden):
        messages.warning(
            request,
            'Esta orden no es de venta mostrador; usa el formato OOW o Garantía Dell.',
        )
        return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

    try:
        formato = obtener_o_crear_borrador(orden, usuario=request.user)
    except Exception as exc:
        logger.exception('Error creando borrador formato VM: %s', exc)
        messages.error(request, f'No se pudo abrir el formato de venta mostrador: {exc}')
        return redirect('servicio_tecnico:detalle_orden', orden_id=orden.pk)

    context = {
        'page_title': f'Nota de Venta — {orden.numero_orden_interno}',
        'orden': orden,
        'formato': formato,
        'formato_json': serializar_formato(formato),
        'orden_json': datos_orden_para_wizard(orden),
        'vistas_laptop': VISTAS_DANO_ESTETICO_LAPTOP,
        'vistas_escritorio': VISTAS_DANO_ESTETICO_ESCRITORIO,
        'vistas_aio': VISTAS_DANO_ESTETICO_AIO,
        'url_guardar': reverse(
            'servicio_tecnico:formato_venta_mostrador_guardar',
            args=[orden.pk],
        ),
        'url_finalizar': reverse(
            'servicio_tecnico:formato_venta_mostrador_finalizar',
            args=[orden.pk],
        ),
        'url_reenviar': reverse(
            'servicio_tecnico:formato_venta_mostrador_reenviar_email',
            args=[orden.pk],
        ),
        'url_pdf': reverse(
            'servicio_tecnico:formato_venta_mostrador_pdf',
            args=[orden.pk],
        ),
        'url_detalle': reverse('servicio_tecnico:detalle_orden', args=[orden.pk]),
    }
    return render(request, 'servicio_tecnico/formato_venta_mostrador.html', context)


@login_required
@permission_required_with_message('servicio_tecnico.change_ordenservicio')
@require_http_methods(['POST'])
def formato_venta_mostrador_guardar(request, orden_id: int):
    """
    Guarda borrador del formato VM vía AJAX (JSON).

    Body JSON: campos del formulario + firmas/vistas en data URL base64.

    Returns:
        JsonResponse con formato serializado
    """
    from .services.formato_venta_mostrador import (
        FormatoVentaMostradorError,
        aplicar_payload_borrador,
        obtener_o_crear_borrador,
        serializar_formato,
    )

    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return _json_error('JSON inválido')

    try:
        formato = obtener_o_crear_borrador(orden, usuario=request.user)
        formato = aplicar_payload_borrador(
            formato,
            payload,
            usuario=request.user,
            permitir_finalizado=(formato.estado == 'finalizado'),
        )
    except FormatoVentaMostradorError as exc:
        return _json_error(str(exc))
    except Exception as exc:
        logger.exception('Error guardando formato VM: %s', exc)
        return _json_error(f'Error al guardar: {exc}', status=500)

    return JsonResponse({
        'success': True,
        'mensaje': (
            'Datos guardados. Usa “Regenerar PDF” para actualizar el documento.'
            if formato.estado == 'finalizado'
            else 'Borrador guardado'
        ),
        'formato': serializar_formato(formato),
    })


@login_required
@permission_required_with_message('servicio_tecnico.change_ordenservicio')
@require_http_methods(['POST'])
def formato_venta_mostrador_finalizar(request, orden_id: int):
    """
    Guarda (si viene payload), genera PDF y marca finalizado.

    Body JSON opcional: mismos campos que guardar + enviar_email (bool).

    Efectos secundarios:
        PDF en media; opcionalmente encola task de correo con db_alias.
    """
    from config.paises_config import get_pais_actual
    from .services.formato_venta_mostrador import (
        FormatoVentaMostradorError,
        aplicar_payload_borrador,
        finalizar_formato,
        lista_emails_envio,
        obtener_o_crear_borrador,
        serializar_formato,
    )

    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return _json_error('JSON inválido')

    try:
        formato = obtener_o_crear_borrador(orden, usuario=request.user)
        solo_regenerar = bool(payload.get('solo_regenerar'))
        forzar = bool(payload.get('forzar_regenerar')) or solo_regenerar or (
            formato.estado == 'finalizado'
        )
        if payload:
            formato = aplicar_payload_borrador(
                formato,
                payload,
                usuario=request.user,
                permitir_finalizado=True,
            )
        formato = finalizar_formato(
            formato,
            usuario=request.user,
            forzar_regenerar=forzar,
        )
    except FormatoVentaMostradorError as exc:
        return _json_error(str(exc))
    except Exception as exc:
        logger.exception('Error finalizando formato VM: %s', exc)
        return _json_error(f'Error al finalizar: {exc}', status=500)

    emails = lista_emails_envio(formato)
    enviar = bool(payload.get('enviar_email')) and not solo_regenerar
    if enviar and emails and formato.pdf:
        try:
            from .tasks import enviar_formato_venta_mostrador_email_task
            enviar_formato_venta_mostrador_email_task.delay(
                formato_id=formato.pk,
                usuario_id=request.user.pk,
                db_alias=get_pais_actual()['db_alias'],
            )
        except Exception as exc:
            logger.warning('No se pudo encolar email formato VM: %s', exc)

    return JsonResponse({
        'success': True,
        'mensaje': (
            'PDF regenerado (sin reenviar correo)'
            if solo_regenerar
            else 'Nota de venta generada'
        ),
        'formato': serializar_formato(formato),
        'pdf_url': reverse(
            'servicio_tecnico:formato_venta_mostrador_pdf',
            args=[orden.pk],
        ),
    })


@login_required
@permission_required_with_message('servicio_tecnico.change_ordenservicio')
@require_http_methods(['POST'])
def formato_venta_mostrador_reenviar_email(request, orden_id: int):
    """
    Reenvía el PDF por correo (sin regenerar).

    Body JSON opcional: emails_envio (lista) o email_envio (string).

    Efectos secundarios:
        Puede actualizar emails_envio; encola Celery con db_alias.
    """
    from config.paises_config import get_pais_actual
    from .models import FormatoServicioVentaMostrador
    from .services.formato_venta_mostrador import (
        aplicar_emails_al_formato,
        lista_emails_envio,
        serializar_formato,
    )

    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    try:
        formato = FormatoServicioVentaMostrador.objects.get(orden=orden)
    except FormatoServicioVentaMostrador.DoesNotExist:
        return _json_error('No hay formato de venta mostrador para esta orden.')

    if formato.estado != 'finalizado' or not formato.pdf:
        return _json_error(
            'Primero debes generar el PDF antes de reenviar el correo.'
        )

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return _json_error('JSON inválido')

    if 'emails_envio' in payload or 'email_envio' in payload:
        raw = payload.get('emails_envio', payload.get('email_envio'))
        aplicar_emails_al_formato(formato, raw)
        formato.save(
            update_fields=['emails_envio', 'email_envio', 'fecha_actualizacion'],
        )

    emails = lista_emails_envio(formato)
    if not emails:
        return _json_error(
            'Captura al menos un correo en “Email(s) para recibir el formato”.'
        )

    try:
        from .tasks import enviar_formato_venta_mostrador_email_task
        enviar_formato_venta_mostrador_email_task.delay(
            formato_id=formato.pk,
            usuario_id=request.user.pk,
            db_alias=get_pais_actual()['db_alias'],
        )
    except Exception as exc:
        logger.exception('No se pudo encolar reenvío formato VM: %s', exc)
        return _json_error(f'No se pudo encolar el correo: {exc}', status=500)

    destinarios_txt = ', '.join(emails)
    return JsonResponse({
        'success': True,
        'mensaje': f'Correo encolado para: {destinarios_txt}',
        'emails': emails,
        'formato': serializar_formato(formato),
    })


@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
def formato_venta_mostrador_pdf(request, orden_id: int):
    """
    Descarga o previsualiza el PDF de la nota de venta.

    Query:
        inline=1 → Content-Disposition inline (visor del navegador)
    """
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    formato = getattr(orden, 'formato_venta_mostrador', None)
    if not formato or not formato.pdf:
        messages.warning(request, 'Aún no hay PDF generado para esta nota de venta.')
        return redirect(
            'servicio_tecnico:formato_venta_mostrador_wizard',
            orden_id=orden.pk,
        )

    inline = request.GET.get('inline') == '1'
    disposition = 'inline' if inline else 'attachment'
    response = FileResponse(
        formato.pdf.open('rb'),
        content_type='application/pdf',
    )
    response['Content-Disposition'] = (
        f'{disposition}; filename="NotaVenta_{orden.numero_orden_interno}.pdf"'
    )
    return response
