"""
Tarea Celery: correo de validación de pagos (cuenta de la empresa).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Al registrar o conciliar un pago, el service ya mandó push y campana.
El correo puede tardar (SMTP): se encola aquí para no bloquear la pantalla.

Celery no pasa por el middleware de país: la firma lleva db_alias.
Esta tarea se reexporta al FINAL de tasks.py para que el worker la vea.
"""

from __future__ import annotations

import logging
import traceback

from celery import shared_task

logger = logging.getLogger('servicio_tecnico')


def _remitente_sistema_facturacion() -> str:
    """
    Nombre visible del From en correos de validación de pago.

    Objetivo de negocio:
        El buzón sigue siendo el de SIGMA (DEFAULT_FROM_EMAIL), pero
        quien recibe ve «Sistema de Facturación», no «Score Card System».

    Returns:
        str tipo «Sistema de Facturación <correo@empresa>».

    Efectos secundarios:
        Ninguno (solo lee settings).
    """
    import re

    from django.conf import settings

    # Paso: DEFAULT_FROM_EMAIL suele ser «Nombre <correo>»; nos quedamos
    # solo con el correo para no cambiar el buzón que sí puede enviar.
    email_match = re.search(r'<(.+?)>', settings.DEFAULT_FROM_EMAIL)
    email_solo = (
        email_match.group(1) if email_match else settings.DEFAULT_FROM_EMAIL
    )
    return f'Sistema de Facturación <{email_solo}>'


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='servicio_tecnico.notificar_validacion_pago',
)
def notificar_validacion_pago_task(
    self,
    pago_id,
    tipo_evento,
    db_alias='default',
):
    """
    Envía el HTML de validación de pago a los destinatarios del evento.

    Args:
        pago_id: PK de PagoOrden.
        tipo_evento: 'pendiente', 'validado' o 'no_aparece'.
        db_alias: alias de BD del país (Celery multi-tenant).

    Efectos secundarios:
        Un correo HTML. No crea push ni campana (eso ya lo hizo el service).

    Returns:
        dict: success y mensaje para logs de Celery.
    """
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from django.utils import timezone

    from almacen.utils.cotizacion_email_context import (
        url_absoluta_detalle_orden,
        url_base_pais_email,
    )
    from config.paises_config import fecha_local_pais, get_pais_actual
    from servicio_tecnico.models import PagoOrden
    from servicio_tecnico.services.notificaciones_pagos import (
        TIPO_PAGO_NO_APARECE,
        TIPO_PAGO_PENDIENTE,
        TIPO_PAGO_VALIDADO,
        destinatarios_pago_no_aparece,
        destinatarios_pago_pendiente,
        destinatarios_pago_validado,
        emails_de_empleados,
        url_relativa_bandeja_pagos,
    )
    from servicio_tecnico.services.pagos_orden import referencia_visible_orden

    log_prefix = '[PAGO-VALIDACION-EMAIL]'
    logger.info(
        '%s Iniciando email pago=%s evento=%s',
        log_prefix,
        pago_id,
        tipo_evento,
    )

    try:
        try:
            pago = PagoOrden.objects.select_related(
                'orden',
                'orden__detalle_equipo',
                'orden__responsable_seguimiento',
                'orden__responsable_seguimiento__user',
                'registrado_por',
                'registrado_por__user',
                'validado_por',
            ).get(pk=pago_id)
        except PagoOrden.DoesNotExist:
            logger.error('%s PagoOrden ID %s no encontrado.', log_prefix, pago_id)
            return {
                'success': False,
                'mensaje': f'PagoOrden ID {pago_id} no encontrado.',
            }

        # Paso: folio visible = cliente → Service Tag → interno (mismo helper).
        referencia = referencia_visible_orden(pago.orden)

        # Paso: los destinatarios se vuelven a calcular aquí (el worker
        # no recibe la lista) para no mandar correos a gente que ya no aplica.
        if tipo_evento == TIPO_PAGO_PENDIENTE:
            destinatarios = destinatarios_pago_pendiente(pago)
            asunto = (
                f'Pago por validar: ${pago.monto} — {referencia.texto}'
            )
        elif tipo_evento == TIPO_PAGO_VALIDADO:
            destinatarios = destinatarios_pago_validado(pago)
            asunto = (
                f'Pago validado en cuenta: ${pago.monto} — {referencia.texto}'
            )
        elif tipo_evento == TIPO_PAGO_NO_APARECE:
            destinatarios = destinatarios_pago_no_aparece(
                pago,
                quien_marco=pago.validado_por,
            )
            asunto = (
                f'Pago no aparece en cuenta: ${pago.monto} — {referencia.texto}'
            )
        else:
            logger.error('%s tipo_evento desconocido: %s', log_prefix, tipo_evento)
            return {
                'success': False,
                'mensaje': f'tipo_evento desconocido: {tipo_evento}',
            }

        emails_to = emails_de_empleados(destinatarios)
        if not emails_to:
            logger.info('%s Sin destinatarios de email válidos.', log_prefix)
            return {'success': True, 'mensaje': 'Sin destinatarios válidos.'}

        _pais_email = get_pais_actual()
        ahora_local = fecha_local_pais(timezone.now(), _pais_email)
        url_orden = url_absoluta_detalle_orden(pago.orden)
        # Pendiente: Facturación abre la bandeja. El resto (responsable /
        # recepción) abre el detalle de esa orden, anclado a cobros.
        if tipo_evento == TIPO_PAGO_PENDIENTE:
            url_pagos = f'{url_base_pais_email()}{url_relativa_bandeja_pagos()}'
        else:
            url_pagos = f'{url_orden}#seccionPagos'

        html = render_to_string(
            'servicio_tecnico/emails/validacion_pago.html',
            {
                'pago': pago,
                'orden': pago.orden,
                'tipo_evento': tipo_evento,
                'url_pagos': url_pagos,
                'referencia_orden': referencia.texto,
                'folio_cliente': referencia.orden_cliente,
                'service_tag': referencia.service_tag,
                'folio_interno': referencia.folio_interno,
                'ahora_local': ahora_local,
                'pais': _pais_email,
            },
        )

        email_msg = EmailMessage(
            subject=asunto,
            body=html,
            from_email=_remitente_sistema_facturacion(),
            to=emails_to,
        )
        email_msg.content_subtype = 'html'
        email_msg.send(fail_silently=False)

        logger.info(
            '%s Email enviado a %s (pago=%s evento=%s)',
            log_prefix,
            ', '.join(emails_to),
            pago_id,
            tipo_evento,
        )
        return {
            'success': True,
            'mensaje': f'Email enviado a {len(emails_to)} destinatario(s).',
        }

    except Exception as exc:
        logger.error('%s Error en tarea: %s', log_prefix, exc)
        logger.error(traceback.format_exc())
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {
                'success': False,
                'mensaje': (
                    f'Error tras {self.max_retries} reintentos: {str(exc)}'
                ),
            }
