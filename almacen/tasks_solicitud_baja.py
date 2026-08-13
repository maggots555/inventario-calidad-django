"""
Tarea Celery: correo de nueva SolicitudBaja a almacenistas (To) y CC.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
La vista NO espera a que salga el correo (SMTP puede tardar). Encola esta
tarea y el usuario ve de inmediato «Solicitud creada».

El worker Celery no pasa por el middleware de país: por eso la firma
lleva db_alias='default'. task_prerun lo aplica al hilo del worker.

To = almacenistas. CC = Compras + quien pidió el producto.
Si no hay To pero sí CC, el correo sale igual (CC pasa a To) para
que quede constancia.
"""

from __future__ import annotations

import logging
import traceback

from celery import shared_task

logger = logging.getLogger('almacen')


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='almacen.notificar_almacenista_solicitud_baja',
)
def notificar_almacenista_solicitud_baja_task(
    self,
    solicitud_id,
    db_alias='default',
):
    """
    Envía el HTML de nueva solicitud de baja (To almacenistas, CC Compras).

    Args:
        solicitud_id: PK de SolicitudBaja.
        db_alias: Alias de BD del país (Celery multi-tenant).

    Efectos secundarios:
        Un correo HTML a To/CC. No crea push ni campanita (eso ya lo
        hizo el util en la petición HTTP).

    Returns:
        dict: success y mensaje para logs de Celery.
    """
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from django.utils import timezone

    from almacen.models import SolicitudBaja
    from almacen.tasks import (
        _adjuntar_logo_e_iconos_email,
        _remitente_sistema_compras,
    )
    from almacen.utils.notificar_solicitud_baja import (
        armar_destinatarios_email,
        url_absoluta_procesar_solicitud,
    )
    from config.paises_config import fecha_local_pais, get_pais_actual

    log_prefix = '[NOTIF-BAJA-EMAIL]'
    logger.info(
        '%s Iniciando email SolicitudBaja ID %s',
        log_prefix,
        solicitud_id,
    )

    try:
        try:
            solicitud = SolicitudBaja.objects.select_related(
                'producto',
                'solicitante',
                'tecnico_asignado',
                'orden_servicio',
                'orden_servicio__detalle_equipo',
                'sucursal_destino',
            ).get(pk=solicitud_id)
        except SolicitudBaja.DoesNotExist:
            logger.error(
                '%s SolicitudBaja ID %s no encontrada.',
                log_prefix,
                solicitud_id,
            )
            return {
                'success': False,
                'mensaje': f'SolicitudBaja ID {solicitud_id} no encontrada.',
            }

        emails_to, emails_cc = armar_destinatarios_email(solicitud)
        # EXPLICACIÓN: SMTP suele rechazar un correo sin To. Si no hay
        # almacenista con email, mandamos a CC como destinatario principal.
        if not emails_to and emails_cc:
            logger.info(
                '%s Sin To de almacenistas; CC pasa a To para que salga el correo',
                log_prefix,
            )
            emails_to = emails_cc
            emails_cc = []

        if not emails_to:
            logger.info('%s Sin destinatarios de email válidos.', log_prefix)
            return {'success': True, 'mensaje': 'Sin destinatarios válidos.'}

        _pais_email = get_pais_actual()
        ahora_local = fecha_local_pais(timezone.now(), _pais_email)
        url_procesar = url_absoluta_procesar_solicitud(solicitud)

        orden = getattr(solicitud, 'orden_servicio', None)
        folio_interno = ''
        folio_cliente = ''
        if orden is not None:
            folio_interno = orden.numero_orden_interno or f'#{orden.pk}'
            detalle = getattr(orden, 'detalle_equipo', None)
            if detalle is not None:
                folio_cliente = (detalle.orden_cliente or '').strip()

        solicitante = getattr(solicitud, 'solicitante', None)
        nombre_solicitante = (
            getattr(solicitante, 'nombre_completo', None) or 'No indicado'
        )

        context = {
            'solicitud': solicitud,
            'nombre_solicitante': nombre_solicitante,
            'folio_interno': folio_interno,
            'folio_cliente': folio_cliente,
            'tiene_orden': orden is not None,
            'fecha_envio_texto': ahora_local.strftime('%d/%m/%Y'),
            'hora_envio_texto': ahora_local.strftime('%H:%M'),
            'empresa_nombre': _pais_email['empresa_nombre_corto'],
            'pais_nombre': _pais_email['nombre'],
            'url_procesar': url_procesar,
        }

        html_content = render_to_string(
            'almacen/emails/nueva_solicitud_baja.html',
            context,
        )

        identificador = folio_cliente or folio_interno or f'#{solicitud.pk}'
        # EXPLICACIÓN: el emoji al inicio del asunto es el mismo patrón
        # que cotizaciones (📋 / ⚠️ / ✅) para reconocerlo en la bandeja.
        asunto = (
            f'📦 Nueva solicitud de baja #{solicitud.pk} — {identificador}'
        )

        email_msg = EmailMessage(
            subject=asunto,
            body=html_content,
            from_email=_remitente_sistema_compras(),
            to=emails_to,
            cc=emails_cc,
        )
        email_msg.content_subtype = 'html'
        _adjuntar_logo_e_iconos_email(email_msg, log_prefix)
        email_msg.send(fail_silently=False)

        logger.info(
            '%s Correo enviado To=%s CC=%s solicitud #%s',
            log_prefix,
            len(emails_to),
            len(emails_cc),
            solicitud.pk,
        )
        return {
            'success': True,
            'mensaje': (
                f'Correo enviado To={len(emails_to)} CC={len(emails_cc)}'
            ),
            'solicitud_id': solicitud.pk,
        }

    except Exception as e:
        logger.error('%s Error en tarea: %s', log_prefix, e)
        logger.error(traceback.format_exc())
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            return {
                'success': False,
                'mensaje': (
                    f'Error tras {self.max_retries} reintentos: {str(e)}'
                ),
            }
