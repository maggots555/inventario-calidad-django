"""
Tarea Celery: correo de la Nota de Venta Directa (venta mostrador).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Al finalizar el wizard, si el de front marca “Enviar por correo”,
esta tarea adjunta el PDF y lo manda (hasta 3 destinatarios).

Celery no pasa por PaisMiddleware: la firma lleva db_alias.
Se reexporta al FINAL de tasks.py para que el worker la vea.
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger('servicio_tecnico')


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='servicio_tecnico.enviar_formato_venta_mostrador_email',
)
def enviar_formato_venta_mostrador_email_task(
    self,
    formato_id,
    usuario_id=None,
    db_alias='default',
):
    """
    Envía por correo el PDF de la Nota de Venta Directa.

    Args:
        formato_id: PK de FormatoServicioVentaMostrador
        usuario_id: User que disparó el envío (auditoría)
        db_alias: Alias de BD del país (Celery multi-tenant)

    Efectos secundarios:
        Envía EmailMessage con PDF adjunto; registra historial en la orden.
    """
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.contrib.staticfiles import finders
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from django.utils import timezone
    from email.mime.application import MIMEApplication
    from email.mime.image import MIMEImage
    from email.utils import formataddr, parseaddr

    from decouple import config

    from config.paises_config import fecha_local_pais, get_pais_actual
    from inventario.models import Empleado

    from .models import FormatoServicioVentaMostrador, HistorialOrden

    try:
        formato = FormatoServicioVentaMostrador.objects.select_related(
            'orden', 'orden__detalle_equipo',
        ).get(pk=formato_id)

        if not formato.pdf:
            logger.warning(
                '[FORMATO_VM] Sin PDF — formato_id=%s',
                formato_id,
            )
            return {'success': False, 'error': 'Sin PDF'}

        from .services.formato_venta_mostrador import lista_emails_envio
        destinatarios = lista_emails_envio(formato)
        if not destinatarios:
            logger.warning(
                '[FORMATO_VM] Sin email — formato_id=%s',
                formato_id,
            )
            return {'success': False, 'error': 'Sin PDF o email'}

        orden = formato.orden
        detalle = getattr(orden, 'detalle_equipo', None)
        orden_sicser = orden.numero_orden_interno
        if detalle is not None:
            orden_sicser = (
                detalle.folio_sicser
                or detalle.orden_cliente
                or orden.numero_orden_interno
            )
        asunto = f'Nota de Venta Directa — {orden_sicser}'

        _pais_email = get_pais_actual()
        ahora_local = fecha_local_pais(timezone.now(), _pais_email)
        email_empleado = ''
        nombre_empleado = ''
        whatsapp_empleado = ''
        usuario_empleado = None
        if usuario_id:
            try:
                usuario_empleado = Empleado.objects.get(user_id=usuario_id)
                email_empleado = usuario_empleado.email or ''
                nombre_empleado = usuario_empleado.nombre_completo or ''
                if usuario_empleado.numero_whatsapp:
                    codigo_tel = _pais_email.get('codigo_telefonico', '')
                    whatsapp_empleado = (
                        f"{codigo_tel}{usuario_empleado.numero_whatsapp}"
                    )
            except Empleado.DoesNotExist:
                User = get_user_model()
                try:
                    usuario = User.objects.get(pk=usuario_id)
                    email_empleado = usuario.email or ''
                    nombre_empleado = (
                        usuario.get_full_name() or usuario.username or ''
                    )
                except User.DoesNotExist:
                    pass

        context_email = {
            'orden': orden,
            'detalle': detalle,
            'orden_sicser': orden_sicser,
            'fecha_envio_texto': ahora_local.strftime('%d/%m/%Y'),
            'hora_envio_texto': ahora_local.strftime('%H:%M'),
            'empresa_nombre': _pais_email['empresa_nombre_corto'],
            'pais_nombre': _pais_email['nombre'],
            'email_empleado': email_empleado,
            'nombre_empleado': nombre_empleado,
            'whatsapp_empleado': whatsapp_empleado,
        }
        html_content = render_to_string(
            'servicio_tecnico/emails/formato_venta_mostrador_cliente.html',
            context_email,
        )

        st_from = (config('SERVICIO_TECNICO_FROM_EMAIL', default='') or '').strip()
        if st_from:
            from_email = st_from
        else:
            _nombre, _addr = parseaddr(
                getattr(settings, 'DEFAULT_FROM_EMAIL', '') or ''
            )
            from_email = (
                formataddr(('Servicio Técnico System', _addr))
                if _addr
                else getattr(settings, 'DEFAULT_FROM_EMAIL', None)
            )

        email_msg = EmailMessage(
            subject=asunto,
            body=html_content,
            from_email=from_email,
            to=destinatarios,
        )
        email_msg.content_subtype = 'html'

        try:
            logo_path = finders.find('images/logos/logo_sic.png')
            if logo_path:
                with open(logo_path, 'rb') as f:
                    logo_mime = MIMEImage(f.read(), _subtype='png')
                    logo_mime.add_header('Content-ID', '<logo_sic>')
                    logo_mime.add_header(
                        'Content-Disposition', 'inline', filename='logo_sic.png',
                    )
                    email_msg.attach(logo_mime)
        except Exception as e:
            logger.warning('[FORMATO_VM] Error al adjuntar logo: %s', e)

        try:
            iconos_sociales = {
                'icon_link': 'images/utilitys/link.png',
                'icon_instagram': 'images/utilitys/instagram.png',
                'icon_facebook': 'images/utilitys/facebook.png',
                'icon_whatsapp': 'images/utilitys/whatsapp.png',
            }
            for cid_name, icon_static_path in iconos_sociales.items():
                icon_path = finders.find(icon_static_path)
                if icon_path:
                    with open(icon_path, 'rb') as f:
                        icon_mime = MIMEImage(f.read(), _subtype='png')
                        icon_mime.add_header('Content-ID', f'<{cid_name}>')
                        icon_mime.add_header(
                            'Content-Disposition',
                            'inline',
                            filename=f'{cid_name}.png',
                        )
                        email_msg.attach(icon_mime)
        except Exception as e:
            logger.warning('[FORMATO_VM] Error al adjuntar iconos: %s', e)

        with formato.pdf.open('rb') as fh:
            pdf_bytes = fh.read()
        pdf_mime = MIMEApplication(pdf_bytes, _subtype='pdf')
        pdf_mime.add_header(
            'Content-Disposition',
            'attachment',
            filename=f'NotaVenta_{orden_sicser}.pdf',
        )
        email_msg.attach(pdf_mime)
        email_msg.send()

        destinarios_txt = ', '.join(destinatarios)
        HistorialOrden.objects.create(
            orden=orden,
            tipo_evento='email',
            comentario=(
                f'Nota de Venta Directa enviada a {destinarios_txt}'
            ),
            usuario=usuario_empleado,
            es_sistema=False,
        )
        logger.info(
            '[FORMATO_VM] Email enviado a %s orden=%s',
            destinarios_txt,
            orden.numero_orden_interno,
        )
        return {'success': True}

    except Exception as exc:
        logger.error('[FORMATO_VM] Error email: %s', exc, exc_info=True)
        raise self.retry(exc=exc, countdown=60)
