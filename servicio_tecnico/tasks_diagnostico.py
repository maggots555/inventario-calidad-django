"""
Tarea Celery: correo de Diagnóstico SIC listo (responsable + Compras).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Al guardar el SIC por primera vez, el service ya mandó push y campana.
El correo puede tardar (SMTP): se encola aquí para no bloquear al técnico.

Celery no pasa por el middleware de país: la firma lleva db_alias.
Esta tarea se reexporta al FINAL de tasks.py para que el worker la vea.
"""

from __future__ import annotations

import logging
import traceback

from celery import shared_task

logger = logging.getLogger('servicio_tecnico')


def _remitente_sistema_servicio_tecnico() -> str:
    """
    Nombre visible del From en correos internos de ST.

    Returns:
        str tipo «Sistema SIGMA — Servicio Técnico <correo@empresa>».
    """
    import re

    from django.conf import settings

    email_match = re.search(r'<(.+?)>', settings.DEFAULT_FROM_EMAIL)
    email_solo = (
        email_match.group(1) if email_match else settings.DEFAULT_FROM_EMAIL
    )
    return f'Sistema SIGMA — Servicio Técnico <{email_solo}>'


def _enviar_lote_email(
    *,
    audiencia: str,
    asunto: str,
    destinatarios,
    contexto_base: dict,
    log_prefix: str,
) -> int:
    """
    Renderiza y envía un correo HTML a un lote de empleados.

    Args:
        audiencia: 'responsable' o 'compras' (texto distinto en plantilla).
        asunto: línea Subject del correo.
        destinatarios: iterable de Empleado.
        contexto_base: dict compartido (orden, url, extracto SIC, etc.).
        log_prefix: etiqueta para logs.

    Returns:
        Cantidad de correos enviados (0 si no hay emails válidos).
    """
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string

    from servicio_tecnico.services.notificaciones_diagnostico import (
        emails_de_empleados,
    )

    emails_to = emails_de_empleados(destinatarios)
    if not emails_to:
        return 0

    contexto = {**contexto_base, 'audiencia': audiencia}
    html = render_to_string(
        'servicio_tecnico/emails/diagnostico_sic_listo_staff.html',
        contexto,
    )

    email_msg = EmailMessage(
        subject=asunto,
        body=html,
        from_email=_remitente_sistema_servicio_tecnico(),
        to=emails_to,
    )
    email_msg.content_subtype = 'html'
    email_msg.send(fail_silently=False)

    logger.info(
        '%s Email %s enviado a %s',
        log_prefix,
        audiencia,
        ', '.join(emails_to),
    )
    return len(emails_to)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='servicio_tecnico.notificar_diagnostico_sic_listo',
)
def notificar_diagnostico_sic_listo_task(
    self,
    orden_id,
    db_alias='default',
):
    """
    Envía correos HTML a responsable de seguimiento y Compras.

    Args:
        orden_id: PK de OrdenServicio.
        db_alias: alias de BD del país (Celery multi-tenant).

    Efectos secundarios:
        Hasta dos correos HTML (audiencias distintas). No crea push/campana.

    Returns:
        dict: success y mensaje para logs de Celery.
    """
    from django.utils import timezone

    from almacen.utils.cotizacion_email_context import url_absoluta_detalle_orden
    from config.paises_config import fecha_local_pais, get_pais_actual
    from servicio_tecnico.models import OrdenServicio
    from servicio_tecnico.services.notificaciones_diagnostico import (
        AUDIENCIA_COMPRAS,
        AUDIENCIA_RESPONSABLE,
        destinatarios_compras,
        destinatarios_responsable_seguimiento,
        extracto_diagnostico_sic,
    )
    from servicio_tecnico.services.pagos_orden import referencia_visible_orden

    log_prefix = '[DIAG-SIC-EMAIL]'
    logger.info('%s Iniciando email orden=%s', log_prefix, orden_id)

    try:
        try:
            orden = OrdenServicio.objects.select_related(
                'detalle_equipo',
                'responsable_seguimiento',
                'responsable_seguimiento__user',
            ).get(pk=orden_id)
        except OrdenServicio.DoesNotExist:
            logger.error('%s OrdenServicio ID %s no encontrada.', log_prefix, orden_id)
            return {
                'success': False,
                'mensaje': f'OrdenServicio ID {orden_id} no encontrada.',
            }

        # Paso: VM o SIC vacío → nada que enviar (tarea encolada antes del guardado).
        if orden.tipo_servicio == 'venta_mostrador':
            return {'success': True, 'mensaje': 'Venta Mostrador: sin correo.'}

        detalle = orden.detalle_equipo
        sic_texto = (getattr(detalle, 'diagnostico_sic', None) or '').strip()
        if not sic_texto:
            return {'success': True, 'mensaje': 'SIC vacío: sin correo.'}

        referencia = referencia_visible_orden(orden)
        _pais_email = get_pais_actual()
        ahora_local = fecha_local_pais(timezone.now(), _pais_email)
        url_detalle = url_absoluta_detalle_orden(orden)

        contexto_base = {
            'orden': orden,
            'detalle': detalle,
            'referencia_orden': referencia.texto,
            'folio_cliente': referencia.orden_cliente,
            'service_tag': referencia.service_tag,
            'folio_interno': referencia.folio_interno,
            'nombre_cliente': getattr(detalle, 'nombre_cliente', '') or '',
            'extracto_sic': extracto_diagnostico_sic(sic_texto),
            'url_detalle': url_detalle,
            'ahora_local': ahora_local,
            'pais': _pais_email,
        }

        total_enviados = 0

        # Lote 1: responsable de seguimiento.
        dest_resp = destinatarios_responsable_seguimiento(orden)
        if dest_resp:
            total_enviados += _enviar_lote_email(
                audiencia=AUDIENCIA_RESPONSABLE,
                asunto=(
                    f'Diagnóstico listo para compartir — {referencia.texto}'
                ),
                destinatarios=dest_resp,
                contexto_base=contexto_base,
                log_prefix=log_prefix,
            )

        # Lote 2: Compras.
        dest_compras = destinatarios_compras()
        if dest_compras:
            total_enviados += _enviar_lote_email(
                audiencia=AUDIENCIA_COMPRAS,
                asunto=(
                    f'Diagnóstico SIC disponible — cotizar piezas — '
                    f'{referencia.texto}'
                ),
                destinatarios=dest_compras,
                contexto_base=contexto_base,
                log_prefix=log_prefix,
            )

        if total_enviados == 0:
            logger.info('%s Sin destinatarios de email válidos.', log_prefix)
            return {'success': True, 'mensaje': 'Sin destinatarios válidos.'}

        return {
            'success': True,
            'mensaje': f'Email enviado en {total_enviados} lote(s).',
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
