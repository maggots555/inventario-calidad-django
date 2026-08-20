"""
Tareas en segundo plano (Celery) para la app almacen.

EXPLICACIÓN PARA PRINCIPIANTES:
Este archivo contiene las tareas Celery específicas del módulo de almacén.
Actualmente incluye la tarea para notificar a recepción (FRONTDESK) sobre
una nueva solicitud de cotización.

Flujo de notificación a front:
    1. El usuario hace clic en "Notificar a Front" en el detalle de solicitud
    2. La VISTA valida los datos y dispara esta tarea
    3. La VISTA responde al usuario: "Notificación en proceso..."
    4. Esta TAREA ejecuta en segundo plano:
       - Comprimir imágenes de cada línea (~2-10 segundos)
       - Renderizar template HTML del correo
       - Enviar email con imágenes adjuntas
       - Registrar evento (si aplica)
"""
import os
import io
import logging
import traceback

from celery import shared_task

logger = logging.getLogger('almacen')


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='almacen.notificar_front_cotizacion'
)
def notificar_front_cotizacion_task(
    self,
    solicitud_id,
    destinatarios,
    mensaje_personalizado,
    usuario_id=None,
    tipo_plantilla='cotizacion_lista',
    db_alias='default',
):
    """
    Tarea Celery: comprime imágenes y envía correo de cotización a los destinatarios seleccionados.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta tarea se ejecuta en segundo plano para no bloquear al usuario.
    Recupera la solicitud de cotización, comprime las imágenes de cada línea
    y envía un correo HTML a los empleados seleccionados para que compartan
    la cotización con el cliente (o avisen PNC si no hay partes).

    Parámetros:
        solicitud_id            : ID de la SolicitudCotizacion
        destinatarios           : Lista de emails seleccionados por el usuario
        mensaje_personalizado   : Texto opcional del usuario
        usuario_id              : ID del usuario que disparó la acción
        tipo_plantilla          : ``cotizacion_lista`` o ``partes_no_disponibles``
        db_alias                : Alias de BD del país activo (ej: 'mexico', 'chile').
                                  La señal task_prerun de Celery usa este valor para
                                  configurar el contexto de país en el worker.
    """
    from pathlib import Path
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from django.utils import timezone
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.contrib.staticfiles import finders
    from email.mime.image import MIMEImage
    from PIL import Image

    from .models import SolicitudCotizacion

    logger.info(f"[COTIZACION] Iniciando tarea para Solicitud ID {solicitud_id}")

    try:
        # ===================================================================
        # PASO 1: RECUPERAR SOLICITUD Y VALIDAR
        # ===================================================================
        try:
            solicitud = SolicitudCotizacion.objects.select_related(
                'orden_servicio',
                'orden_servicio__detalle_equipo',
                'creado_por'
            ).prefetch_related(
                'lineas__producto',
                'lineas__imagenes',
            ).get(pk=solicitud_id)
        except SolicitudCotizacion.DoesNotExist:
            logger.error(f"[COTIZACION] Solicitud ID {solicitud_id} no encontrada.")
            return {'success': False, 'mensaje': f'Solicitud ID {solicitud_id} no encontrada.'}

        # ===================================================================
        # PASO 2: COMPRIMIR IMÁGENES DE CADA LÍNEA
        # ===================================================================
        logger.info(f"[COTIZACION] Procesando imágenes de {solicitud.lineas.count()} línea(s)...")

        lineas_con_imagenes = []
        total_imagenes = 0

        for linea in solicitud.lineas.all():
            imagenes_linea = []
            for img in linea.imagenes.all():
                try:
                    img_path = img.imagen.path
                    if not Path(img_path).exists() or not Path(img_path).is_file():
                        continue

                    # Abrir y comprimir imagen
                    pil_img = Image.open(img_path)

                    # Convertir a RGB si tiene transparencia
                    if pil_img.mode in ('RGBA', 'LA', 'P'):
                        background = Image.new('RGB', pil_img.size, (255, 255, 255))
                        if pil_img.mode == 'P':
                            pil_img = pil_img.convert('RGBA')
                        background.paste(pil_img, mask=pil_img.split()[-1] if pil_img.mode == 'RGBA' else None)
                        pil_img = background

                    # Redimensionar si es muy grande
                    max_dimension = 1200
                    if max(pil_img.size) > max_dimension:
                        ratio = max_dimension / max(pil_img.size)
                        new_size = tuple([int(dim * ratio) for dim in pil_img.size])
                        pil_img = pil_img.resize(new_size, Image.Resampling.LANCZOS)

                    # Guardar en buffer
                    output = io.BytesIO()
                    pil_img.save(output, format='JPEG', quality=85, optimize=True)
                    output.seek(0)

                    nombre_archivo = f"linea{linea.numero_linea}_img{img.id}_{os.path.basename(img.imagen.name)}"
                    if not nombre_archivo.lower().endswith('.jpg'):
                        nombre_archivo = os.path.splitext(nombre_archivo)[0] + '.jpg'

                    # Generar CID único para embeber imagen inline en el correo
                    cid = f"linea{linea.numero_linea}_img{img.id}"

                    imagenes_linea.append({
                        'id': img.id,
                        'descripcion': img.descripcion or img.nombre_archivo,
                        'contenido': output.getvalue(),
                        'nombre': nombre_archivo,
                        'cid': cid,
                    })
                    total_imagenes += 1

                except Exception as e:
                    logger.warning(f"[COTIZACION] Error procesando imagen {img.id}: {e}")

            lineas_con_imagenes.append({
                'linea': linea,
                'imagenes': imagenes_linea,
            })

        logger.info(f"[COTIZACION] Total imágenes procesadas: {total_imagenes}")

        # ===================================================================
        # PASO 3: PREPARAR CONTEXTO Y RENDERIZAR HTML
        # ===================================================================
        from config.paises_config import get_pais_actual, fecha_local_pais
        from .utils.cotizacion_email_context import url_absoluta_detalle_solicitud

        _pais_email = get_pais_actual()

        # Obtener datos del usuario que envía
        whatsapp_empleado = ''
        nombre_usuario = ''
        if usuario_id:
            User = get_user_model()
            try:
                usuario = User.objects.get(pk=usuario_id)
                nombre_usuario = usuario.get_full_name() or usuario.username
                if hasattr(usuario, 'empleado') and usuario.empleado:
                    numero_local = usuario.empleado.numero_whatsapp
                    if numero_local:
                        codigo_tel = _pais_email.get('codigo_telefonico', '')
                        whatsapp_empleado = f"{codigo_tel}{numero_local}"
            except User.DoesNotExist:
                pass

        ahora_local = fecha_local_pais(timezone.now(), _pais_email)

        # Obtener información del equipo si hay orden vinculada
        info_equipo = None
        if solicitud.orden_servicio and hasattr(solicitud.orden_servicio, 'detalle_equipo'):
            detalle = solicitud.orden_servicio.detalle_equipo
            info_equipo = {
                'tipo': detalle.tipo_equipo,
                'marca': detalle.marca,
                'modelo': detalle.modelo,
                'service_tag': detalle.numero_serie,
            }

        context = {
            'solicitud': solicitud,
            'lineas_con_imagenes': lineas_con_imagenes,
            'info_equipo': info_equipo,
            'mensaje_personalizado': mensaje_personalizado,
            'fecha_envio_texto': ahora_local.strftime('%d/%m/%Y'),
            'hora_envio_texto': ahora_local.strftime('%H:%M'),
            'total_imagenes': total_imagenes,
            'empresa_nombre': _pais_email['empresa_nombre_corto'],
            'pais_nombre': _pais_email['nombre'],
            'whatsapp_empleado': whatsapp_empleado,
            'nombre_usuario': nombre_usuario,
            'tipo_plantilla': tipo_plantilla,
            # Enlace absoluto al detalle (subdominio del país; localhost si DEBUG)
            'url_detalle': url_absoluta_detalle_solicitud(solicitud),
        }

        # EXPLICACIÓN: plantilla PNC usa otro HTML y asunto (partes no disponibles)
        es_pnc = tipo_plantilla == 'partes_no_disponibles'
        template_email = (
            'almacen/emails/cotizacion_front_pnc.html'
            if es_pnc
            else 'almacen/emails/cotizacion_front.html'
        )
        html_content = render_to_string(template_email, context)

        # ===================================================================
        # PASO 4: CREAR Y ENVIAR EL CORREO
        # ===================================================================
        # EXPLICACIÓN: con orden → orden_cliente; sin orden → S/T (helper común)
        from .utils.cotizacion_email_context import identificador_asunto_solicitud

        numero_display = identificador_asunto_solicitud(solicitud)

        if es_pnc:
            asunto = f'⚠️ PNC - Partes no disponibles - {numero_display}'
        else:
            asunto = f'📋 Nueva Cotización - {numero_display}'

        email_match = __import__('re').search(r'<(.+?)>', settings.DEFAULT_FROM_EMAIL)
        email_solo = email_match.group(1) if email_match else settings.DEFAULT_FROM_EMAIL
        # EXPLICACIÓN PARA PRINCIPIANTES: el nombre que ve el destinatario
        # en "De:" (no cambia el email real, solo la etiqueta visible).
        remitente = f"Sistema de Compras <{email_solo}>"

        email_msg = EmailMessage(
            subject=asunto,
            body=html_content,
            from_email=remitente,
            to=destinatarios,
        )
        email_msg.content_subtype = 'html'

        # Adjuntar logo SIC
        try:
            logo_path = finders.find('images/logos/logo_sic.png')
            if logo_path:
                with open(logo_path, 'rb') as f:
                    logo_mime = MIMEImage(f.read(), _subtype='png')
                    logo_mime.add_header('Content-ID', '<logo_sic>')
                    logo_mime.add_header('Content-Disposition', 'inline', filename='logo_sic.png')
                    email_msg.attach(logo_mime)
        except Exception as e:
            logger.warning(f"[COTIZACION] Error al adjuntar logo: {e}")

        # Adjuntar iconos de redes sociales
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
                        icon_mime.add_header('Content-Disposition', 'inline', filename=f'{cid_name}.png')
                        email_msg.attach(icon_mime)
        except Exception as e:
            logger.warning(f"[COTIZACION] Error al adjuntar iconos: {e}")

        # Adjuntar imágenes comprimidas de todas las líneas como inline (CID)
        for linea_data in lineas_con_imagenes:
            for img_data in linea_data['imagenes']:
                img_mime = MIMEImage(img_data['contenido'], _subtype='jpeg')
                img_mime.add_header('Content-ID', f'<{img_data["cid"]}>')
                img_mime.add_header('Content-Disposition', 'inline', filename=img_data['nombre'])
                email_msg.attach(img_mime)

        email_msg.send(fail_silently=False)
        logger.info(f"[COTIZACION] Correo enviado a {', '.join(destinatarios)}")

        # ===================================================================
        # PASO 5: RETORNAR RESULTADO EXITOSO
        # ===================================================================
        return {
            'success': True,
            'mensaje': f'Correo enviado exitosamente a {len(destinatarios)} destinatario(s)',
            'solicitud': numero_display,
            'total_imagenes': total_imagenes,
        }

    except Exception as e:
        logger.error(f"[COTIZACION] Error en tarea: {e}")
        logger.error(traceback.format_exc())
        return {'success': False, 'mensaje': f'Error: {str(e)}'}


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='almacen.notificar_compras_nueva_cotizacion'
)
def notificar_compras_nueva_cotizacion_task(
    self,
    solicitud_id,
    usuario_id=None,
    db_alias='default',
):
    """
    Tarea Celery: envía email a los empleados de Compras cuando se crea
    una solicitud de cotización "Sin Orden Activa".

    EXPLICACIÓN PARA PRINCIPIANTES:
    Cuando recepción crea una cotización sin una orden de servicio vinculada,
    el área de Compras necesita procesarla (buscar proveedores, cotizar piezas).
    Esta tarea se ejecuta en segundo plano para no bloquear al usuario que
    creó la solicitud.

    Parámetros:
        solicitud_id : ID de la SolicitudCotizacion recién creada
        usuario_id   : ID del usuario que creó la solicitud (para el contexto)
        db_alias     : Alias de BD del país activo (ej: 'mexico', 'chile').
                       La señal task_prerun de Celery usa este valor para
                       configurar el contexto de país en el worker.
    """
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from django.utils import timezone
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.contrib.staticfiles import finders
    from email.mime.image import MIMEImage

    from .models import SolicitudCotizacion
    from inventario.models import Empleado
    from config.paises_config import get_pais_actual, fecha_local_pais

    logger.info(f"[COTIZACION-COMPRAS] Iniciando notificación para Solicitud ID {solicitud_id}")

    try:
        # ===================================================================
        # PASO 1: RECUPERAR SOLICITUD Y VALIDAR
        # ===================================================================
        try:
            solicitud = SolicitudCotizacion.objects.select_related(
                'creado_por'
            ).prefetch_related(
                'lineas__producto',
                'lineas__proveedor',
            ).get(pk=solicitud_id)
        except SolicitudCotizacion.DoesNotExist:
            logger.error(f"[COTIZACION-COMPRAS] Solicitud ID {solicitud_id} no encontrada.")
            return {'success': False, 'mensaje': f'Solicitud ID {solicitud_id} no encontrada.'}

        # ===================================================================
        # PASO 2: OBTENER EMPLEADOS DE COMPRAS CON EMAIL
        # ===================================================================
        compradores = Empleado.objects.filter(
            rol='compras',
            user__is_active=True,
            email__isnull=False,
        ).exclude(email='').select_related('user')

        if not compradores.exists():
            logger.info("[COTIZACION-COMPRAS] No hay empleados de Compras con email configurado.")
            return {'success': True, 'mensaje': 'No hay empleados de Compras con email.'}

        # Recopilar emails únicos de los compradores
        destinatarios = list(set(
            emp.email for emp in compradores if emp.email
        ))

        if not destinatarios:
            logger.info("[COTIZACION-COMPRAS] Sin destinatarios de email válidos.")
            return {'success': True, 'mensaje': 'Sin destinatarios válidos.'}

        # ===================================================================
        # PASO 3: PREPARAR CONTEXTO Y RENDERIZAR HTML
        # ===================================================================
        _pais_email = get_pais_actual()

        nombre_usuario = ''
        if usuario_id:
            User = get_user_model()
            try:
                usuario = User.objects.get(pk=usuario_id)
                nombre_usuario = usuario.get_full_name() or usuario.username
            except User.DoesNotExist:
                pass

        ahora_local = fecha_local_pais(timezone.now(), _pais_email)

        from .utils.cotizacion_email_context import url_absoluta_detalle_solicitud

        context = {
            'solicitud': solicitud,
            'lineas': solicitud.lineas.select_related('producto', 'proveedor').all(),
            'fecha_envio_texto': ahora_local.strftime('%d/%m/%Y'),
            'hora_envio_texto': ahora_local.strftime('%H:%M'),
            'empresa_nombre': _pais_email['empresa_nombre_corto'],
            'pais_nombre': _pais_email['nombre'],
            'nombre_usuario': nombre_usuario,
            # Enlace absoluto al detalle (subdominio del país; localhost si DEBUG)
            'url_detalle': url_absoluta_detalle_solicitud(solicitud),
        }

        html_content = render_to_string(
            'almacen/emails/nueva_cotizacion_sin_orden.html',
            context
        )

        # ===================================================================
        # PASO 4: CREAR Y ENVIAR EL CORREO
        # ===================================================================
        # Este flujo es siempre sin orden: identificador = S/T (o N/A)
        from .utils.cotizacion_email_context import identificador_asunto_solicitud

        identificador = identificador_asunto_solicitud(solicitud)
        if identificador.startswith('S/T:'):
            etiqueta_st = identificador
        else:
            etiqueta_st = 'S/T: N/A'
        asunto = (
            f'📋 Nueva Cotización Sin Orden — '
            f'{solicitud.numero_solicitud} ({etiqueta_st})'
        )

        import re
        email_match = re.search(r'<(.+?)>', settings.DEFAULT_FROM_EMAIL)
        email_solo = email_match.group(1) if email_match else settings.DEFAULT_FROM_EMAIL
        remitente = f"Sistema de Compras <{email_solo}>"

        email_msg = EmailMessage(
            subject=asunto,
            body=html_content,
            from_email=remitente,
            to=destinatarios,
        )
        email_msg.content_subtype = 'html'

        # Adjuntar logo SIC (CID para mostrar inline en el correo)
        try:
            logo_path = finders.find('images/logos/logo_sic.png')
            if logo_path:
                with open(logo_path, 'rb') as f:
                    logo_mime = MIMEImage(f.read(), _subtype='png')
                    logo_mime.add_header('Content-ID', '<logo_sic>')
                    logo_mime.add_header('Content-Disposition', 'inline', filename='logo_sic.png')
                    email_msg.attach(logo_mime)
        except Exception as e:
            logger.warning(f"[COTIZACION-COMPRAS] Error al adjuntar logo: {e}")

        # Adjuntar iconos de redes sociales (CID para mostrar inline)
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
                        icon_mime.add_header('Content-Disposition', 'inline', filename=f'{cid_name}.png')
                        email_msg.attach(icon_mime)
        except Exception as e:
            logger.warning(f"[COTIZACION-COMPRAS] Error al adjuntar iconos: {e}")

        email_msg.send(fail_silently=False)
        logger.info(
            f"[COTIZACION-COMPRAS] Correo enviado a {len(destinatarios)} destinatario(s): "
            f"{', '.join(destinatarios)}"
        )

        # ===================================================================
        # PASO 5: RETORNAR RESULTADO EXITOSO
        # ===================================================================
        return {
            'success': True,
            'mensaje': f'Correo enviado a {len(destinatarios)} empleado(s) de Compras',
            'solicitud': solicitud.numero_solicitud,
        }

    except Exception as e:
        logger.error(f"[COTIZACION-COMPRAS] Error en tarea: {e}")
        logger.error(traceback.format_exc())
        return {'success': False, 'mensaje': f'Error: {str(e)}'}


def _adjuntar_logo_e_iconos_email(email_msg, log_prefix: str) -> None:
    """
    Adjunta logo SIC e iconos sociales como CID (inline) a un EmailMessage.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Los correos HTML no pueden usar {% static %}; las imágenes van embebidas
    con Content-ID (cid:logo_sic) para que el cliente de correo las muestre.

    Args:
        email_msg: EmailMessage ya creado.
        log_prefix: Prefijo para mensajes de log (ej. '[COTIZ-ACEPTADA]').
    """
    from django.contrib.staticfiles import finders
    from email.mime.image import MIMEImage

    try:
        logo_path = finders.find('images/logos/logo_sic.png')
        if logo_path:
            with open(logo_path, 'rb') as f:
                logo_mime = MIMEImage(f.read(), _subtype='png')
                logo_mime.add_header('Content-ID', '<logo_sic>')
                logo_mime.add_header(
                    'Content-Disposition', 'inline', filename='logo_sic.png'
                )
                email_msg.attach(logo_mime)
    except Exception as e:
        logger.warning(f'{log_prefix} Error al adjuntar logo: {e}')

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
        logger.warning(f'{log_prefix} Error al adjuntar iconos: {e}')


def _remitente_sistema_compras() -> str:
    """Remitente visible «Sistema de Compras <email>» desde DEFAULT_FROM_EMAIL."""
    import re
    from django.conf import settings

    email_match = re.search(r'<(.+?)>', settings.DEFAULT_FROM_EMAIL)
    email_solo = email_match.group(1) if email_match else settings.DEFAULT_FROM_EMAIL
    return f'Sistema de Compras <{email_solo}>'


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='almacen.notificar_compras_cotizacion_aceptada'
)
def notificar_compras_cotizacion_aceptada_task(
    self,
    solicitud_id,
    db_alias='default',
):
    """
    Email a Compras cuando el cliente acepta la cotización (total o parcial).

    Objetivo de negocio:
        Que Compras vea las piezas/servicios aceptados y pueda pedirlos al
        proveedor antes de usar «Generar compras».

    Args:
        solicitud_id: PK de SolicitudCotizacion.
        db_alias: Alias de BD del país (Celery multi-tenant).

    Efectos secundarios:
        Envía un correo HTML a empleados rol=compras con email configurado.
    """
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from django.utils import timezone

    from .models import SolicitudCotizacion
    from inventario.models import Empleado
    from config.paises_config import get_pais_actual, fecha_local_pais
    from .utils.cotizacion_email_context import (
        identificador_asunto_solicitud,
        url_absoluta_detalle_solicitud,
    )

    log_prefix = '[COTIZ-ACEPTADA]'
    logger.info(f'{log_prefix} Iniciando email aceptación Solicitud ID {solicitud_id}')

    try:
        try:
            solicitud = SolicitudCotizacion.objects.select_related(
                'orden_servicio',
                'creado_por',
            ).prefetch_related(
                'lineas__producto',
                'lineas__proveedor',
                'servicios_adicionales',
            ).get(pk=solicitud_id)
        except SolicitudCotizacion.DoesNotExist:
            logger.error(f'{log_prefix} Solicitud ID {solicitud_id} no encontrada.')
            return {'success': False, 'mensaje': f'Solicitud ID {solicitud_id} no encontrada.'}

        # Solo empleados Compras con correo válido
        compradores = Empleado.objects.filter(
            rol='compras',
            user__is_active=True,
            email__isnull=False,
        ).exclude(email='').select_related('user')

        destinatarios = list({emp.email for emp in compradores if emp.email})
        if not destinatarios:
            logger.info(f'{log_prefix} Sin destinatarios de email de Compras.')
            return {'success': True, 'mensaje': 'Sin destinatarios válidos.'}

        lineas_aprobadas = [
            linea
            for linea in solicitud.lineas.all()
            if linea.estado_cliente in ('aprobada', 'compra_generada')
        ]
        servicios_aprobados = [
            srv
            for srv in solicitud.servicios_adicionales.all()
            if srv.estado_cliente in ('aprobada', 'compra_generada')
        ]

        _pais_email = get_pais_actual()
        ahora_local = fecha_local_pais(timezone.now(), _pais_email)
        # EXPLICACIÓN: URL del país (o localhost si DEBUG), no SITE_URL fijo
        url_detalle = url_absoluta_detalle_solicitud(solicitud)

        context = {
            'solicitud': solicitud,
            'lineas_aprobadas': lineas_aprobadas,
            'servicios_aprobados': servicios_aprobados,
            'es_parcial': solicitud.estado == 'parcialmente_aprobada',
            'fecha_envio_texto': ahora_local.strftime('%d/%m/%Y'),
            'hora_envio_texto': ahora_local.strftime('%H:%M'),
            'empresa_nombre': _pais_email['empresa_nombre_corto'],
            'pais_nombre': _pais_email['nombre'],
            'url_detalle': url_detalle,
        }

        html_content = render_to_string(
            'almacen/emails/cotizacion_aceptada_compras.html',
            context,
        )

        identificador = identificador_asunto_solicitud(solicitud)
        tipo = 'parcial' if context['es_parcial'] else 'total'
        # EXPLICACIÓN: emoji + identificador (orden_cliente / S/T / SOL), estilo Front/PNC
        asunto = f'✅ Cotización aceptada ({tipo}) — {identificador}'

        email_msg = EmailMessage(
            subject=asunto,
            body=html_content,
            from_email=_remitente_sistema_compras(),
            to=destinatarios,
        )
        email_msg.content_subtype = 'html'
        _adjuntar_logo_e_iconos_email(email_msg, log_prefix)
        email_msg.send(fail_silently=False)

        logger.info(
            f'{log_prefix} Correo enviado a {len(destinatarios)}: '
            f'{", ".join(destinatarios)}'
        )
        return {
            'success': True,
            'mensaje': f'Correo aceptación enviado a {len(destinatarios)}',
            'solicitud': solicitud.numero_solicitud,
        }

    except Exception as e:
        logger.error(f'{log_prefix} Error en tarea: {e}')
        logger.error(traceback.format_exc())
        return {'success': False, 'mensaje': f'Error: {str(e)}'}


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='almacen.notificar_respuesta_cotizacion_rechazada'
)
def notificar_respuesta_cotizacion_rechazada_task(
    self,
    solicitud_id,
    db_alias='default',
):
    """
    Email a Compras + técnico + responsable cuando la cotización se rechaza.

    Objetivo de negocio:
        Informar que no deben generar compras y que el cliente rechazó todo.

    Args:
        solicitud_id: PK de SolicitudCotizacion.
        db_alias: Alias de BD del país (Celery multi-tenant).

    Efectos secundarios:
        Envía un correo HTML a destinatarios con email (deduplicados).
    """
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from django.utils import timezone

    from .models import SolicitudCotizacion
    from config.paises_config import get_pais_actual, fecha_local_pais
    from .utils.cotizacion_email_context import (
        identificador_asunto_solicitud,
        url_absoluta_detalle_orden,
        url_absoluta_detalle_solicitud,
    )
    from .utils.notificar_respuesta_cotizacion import obtener_destinatarios_rechazo
    from .utils.sincronizar_rechazo_cotizacion_st import (
        armar_detalle_rechazo_desde_items,
        label_motivo_rechazo,
    )

    log_prefix = '[COTIZ-RECHAZADA]'
    logger.info(f'{log_prefix} Iniciando email rechazo Solicitud ID {solicitud_id}')

    try:
        try:
            solicitud = SolicitudCotizacion.objects.select_related(
                'orden_servicio',
                'orden_servicio__tecnico_asignado_actual',
                'orden_servicio__tecnico_asignado_actual__user',
                'orden_servicio__responsable_seguimiento',
                'orden_servicio__responsable_seguimiento__user',
                'creado_por',
            ).prefetch_related(
                'lineas__producto',
                'lineas__proveedor',
                'servicios_adicionales',
            ).get(pk=solicitud_id)
        except SolicitudCotizacion.DoesNotExist:
            logger.error(f'{log_prefix} Solicitud ID {solicitud_id} no encontrada.')
            return {'success': False, 'mensaje': f'Solicitud ID {solicitud_id} no encontrada.'}

        destinatarios_emp = obtener_destinatarios_rechazo(solicitud)
        emails = list({
            (emp.email or '').strip()
            for emp in destinatarios_emp
            if (emp.email or '').strip()
        })
        if not emails:
            logger.info(f'{log_prefix} Sin destinatarios de email válidos.')
            return {'success': True, 'mensaje': 'Sin destinatarios válidos.'}

        lineas_rechazadas = [
            linea
            for linea in solicitud.lineas.all()
            if linea.estado_cliente == 'rechazada'
        ]
        servicios_rechazados = [
            srv
            for srv in solicitud.servicios_adicionales.all()
            if srv.estado_cliente == 'rechazada'
        ]

        motivo_catalogo = ''
        if solicitud.motivo_rechazo:
            motivo_catalogo = label_motivo_rechazo(solicitud.motivo_rechazo)
        detalle_items = armar_detalle_rechazo_desde_items(solicitud)

        _pais_email = get_pais_actual()
        ahora_local = fecha_local_pais(timezone.now(), _pais_email)
        # EXPLICACIÓN: misma base de país para solicitud y orden ST
        url_detalle = url_absoluta_detalle_solicitud(solicitud)

        url_orden = ''
        orden = solicitud.orden_servicio
        if orden is not None:
            try:
                url_orden = url_absoluta_detalle_orden(orden)
            except Exception:
                url_orden = ''

        context = {
            'solicitud': solicitud,
            'lineas_rechazadas': lineas_rechazadas,
            'servicios_rechazados': servicios_rechazados,
            'motivo_catalogo': motivo_catalogo,
            'detalle_items': detalle_items,
            'detalle_rechazo': (solicitud.detalle_rechazo or '').strip(),
            'fecha_envio_texto': ahora_local.strftime('%d/%m/%Y'),
            'hora_envio_texto': ahora_local.strftime('%H:%M'),
            'empresa_nombre': _pais_email['empresa_nombre_corto'],
            'pais_nombre': _pais_email['nombre'],
            'url_detalle': url_detalle,
            'url_orden': url_orden,
            'orden': orden,
        }

        html_content = render_to_string(
            'almacen/emails/cotizacion_rechazada_interna.html',
            context,
        )

        identificador = identificador_asunto_solicitud(solicitud)
        # EXPLICACIÓN: emoji + identificador (orden_cliente / S/T / SOL), estilo Front/PNC
        asunto = f'❌ Cotización rechazada — {identificador}'

        email_msg = EmailMessage(
            subject=asunto,
            body=html_content,
            from_email=_remitente_sistema_compras(),
            to=emails,
        )
        email_msg.content_subtype = 'html'
        _adjuntar_logo_e_iconos_email(email_msg, log_prefix)
        email_msg.send(fail_silently=False)

        logger.info(
            f'{log_prefix} Correo enviado a {len(emails)}: {", ".join(emails)}'
        )
        return {
            'success': True,
            'mensaje': f'Correo rechazo enviado a {len(emails)}',
            'solicitud': solicitud.numero_solicitud,
        }

    except Exception as e:
        logger.error(f'{log_prefix} Error en tarea: {e}')
        logger.error(traceback.format_exc())
        return {'success': False, 'mensaje': f'Error: {str(e)}'}


# =============================================================================
# TAREA: ENVIAR COTIZACIÓN DIRECTAMENTE AL CLIENTE FINAL CON PDF ADJUNTO
# =============================================================================

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='almacen.enviar_cotizacion_cliente'
)
def enviar_cotizacion_cliente_task(
    self,
    solicitud_id,
    email_cliente,
    copia_empleados,
    tipo_servicio,
    items,
    titulo_propuesta='',
    incluir_descuento_diagnostico=False,
    mano_de_obra_override=None,
    mensaje_personalizado='',
    asunto_correo='',
    usuario_id=None,
    db_alias='default',
    modo_cotizacion='reparacion',
    datos_equipo_reac=None,
    costeo_reac=None,
):
    """
    Genera el PDF de cotización y lo envía directamente al cliente por correo.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta tarea es la encargada de la parte pesada del envío al cliente:
    1. Recupera la SolicitudCotizacion de la base de datos.
    2. Instancia PDFCotizacionCliente con los parámetros del modal.
    3. Genera el PDF en memoria (BytesIO) con el estilo SIC.
    4. Compone el correo HTML con el resumen de la cotización.
    5. Adjunta el PDF al correo y lo envía al cliente.

    Parámetros:
        solicitud_id                 : ID de la SolicitudCotizacion.
        email_cliente                : Correo del destinatario principal (el cliente).
        copia_empleados              : Lista de emails para CC (empleados internos).
        tipo_servicio                : Clave del perfil ('estandar', 'express', etc.)
        items                        : Lista de dicts con los ítems del PDF (ya serializada).
        titulo_propuesta             : Título de la propuesta (vacío = usar nombre del perfil).
        incluir_descuento_diagnostico: Legacy; siempre se fuerza a False (sin descuento).
        mano_de_obra_override        : Costo de mano de obra (informativo, se ignora en cálculo).
        mensaje_personalizado        : Texto adicional para el cuerpo del email.
        asunto_correo                : Asunto personalizado. Si está vacío se genera automáticamente.
        usuario_id                   : ID del usuario que disparó la acción.
        db_alias                     : Alias de BD del país activo (CRÍTICO para multi-tenant).

    Efectos secundarios:
        - Envía un correo con PDF adjunto al email_cliente.
        - Loguea el resultado en el logger 'almacen'.
    """
    import io as _io
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from django.utils import timezone
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.contrib.staticfiles import finders
    from email.mime.image import MIMEImage
    from email.mime.application import MIMEApplication

    from .models import SolicitudCotizacion
    from .utils.pdf_cotizacion_cliente import PDFCotizacionCliente

    logger.info(
        f"[COTIZACION-CLIENTE] Iniciando envío al cliente para Solicitud ID {solicitud_id} "
        f"| tipo_servicio={tipo_servicio} | email={email_cliente}"
    )

    try:
        # --- PASO 1: RECUPERAR LA SOLICITUD ---
        # Incluimos select_related para minimizar queries al generar el PDF
        try:
            solicitud = SolicitudCotizacion.objects.select_related(
                'orden_servicio',
                'orden_servicio__detalle_equipo',
                'orden_servicio__sucursal',
                'creado_por',
                'creado_por__empleado__sucursal',
            ).prefetch_related(
                'lineas__producto',
                'servicios_adicionales',
            ).get(pk=solicitud_id)
        except SolicitudCotizacion.DoesNotExist:
            logger.error(f"[COTIZACION-CLIENTE] Solicitud ID {solicitud_id} no encontrada.")
            return {'success': False, 'mensaje': f'Solicitud ID {solicitud_id} no encontrada.'}

        # --- PASO 2: OBTENER CONFIGURACIÓN DEL PAÍS ACTIVO ---
        # La señal task_prerun ya configuró el contexto de país en el worker
        from config.paises_config import get_pais_actual, fecha_local_pais
        _pais = get_pais_actual()

        # --- PASO 3: GENERAR EL PDF EN MEMORIA ---
        es_reacondicionado = modo_cotizacion == 'reacondicionado'

        if es_reacondicionado:
            from .utils.pdf_cotizacion_reacondicionado import PDFCotizacionReacondicionado

            logger.info('[COTIZACION-CLIENTE] Generando PDF de equipo reacondicionado...')
            generador_reac = PDFCotizacionReacondicionado(
                solicitud=solicitud,
                datos_equipo=datos_equipo_reac or {},
                costeo=costeo_reac or {},
                pais_config=_pais,
            )
            resultado_pdf = generador_reac.generar_pdf()
        else:
            logger.info(f"[COTIZACION-CLIENTE] Generando PDF con {len(items)} ítem(s)...")
            generador = PDFCotizacionCliente(
                solicitud=solicitud,
                tipo_servicio=tipo_servicio,
                items=items,
                titulo_propuesta=titulo_propuesta,
                incluir_descuento_diagnostico=False,
                mano_de_obra_override=mano_de_obra_override,
                pais_config=_pais,
            )
            resultado_pdf = generador.generar_pdf()

        if not resultado_pdf['success']:
            logger.error(f"[COTIZACION-CLIENTE] Error al generar PDF: {resultado_pdf.get('error')}")
            return {'success': False, 'mensaje': f"Error al generar PDF: {resultado_pdf.get('error')}"}

        pdf_bytes   = resultado_pdf['buffer'].getvalue()
        nombre_pdf  = resultado_pdf['nombre_archivo']
        logger.info(f"[COTIZACION-CLIENTE] PDF generado exitosamente ({len(pdf_bytes)} bytes): {nombre_pdf}")

        # --- PASO 4: PREPARAR CONTEXTO PARA EL TEMPLATE DE EMAIL ---
        # Obtener nombre del usuario que envió la cotización
        nombre_usuario = ''
        whatsapp_empleado = ''
        if usuario_id:
            User = get_user_model()
            try:
                usuario = User.objects.get(pk=usuario_id)
                nombre_usuario = usuario.get_full_name() or usuario.username
                if hasattr(usuario, 'empleado') and usuario.empleado:
                    numero_local = usuario.empleado.numero_whatsapp
                    if numero_local:
                        codigo_tel = _pais.get('codigo_telefonico', '')
                        whatsapp_empleado = f"{codigo_tel}{numero_local}"
            except Exception:
                pass

        # Calcular la fecha local del país
        ahora_local = fecha_local_pais(timezone.now(), _pais)

        # Datos del equipo para el email (si hay orden vinculada)
        info_equipo = None
        if solicitud.orden_servicio:
            try:
                det = solicitud.orden_servicio.detalle_equipo
                info_equipo = {
                    'tipo': det.tipo_equipo,
                    'marca': det.marca,
                    'modelo': det.modelo,
                    'service_tag': det.numero_serie,
                }
            except Exception:
                pass

        # Nombre del cliente para personalizar el saludo
        nombre_cliente = ''
        if info_equipo and solicitud.orden_servicio:
            try:
                nombre_cliente = solicitud.orden_servicio.detalle_equipo.nombre_cliente or ''
            except Exception:
                pass
        if not nombre_cliente and solicitud.nombre_cliente:
            nombre_cliente = solicitud.nombre_cliente

        # Calcular total con IVA para mostrar en el email (sin abrir el PDF)
        if es_reacondicionado:
            calculo_resumen = {
                'servicio_nombre': titulo_propuesta or 'Propuesta de Equipo Reacondicionado',
                'precio_con_iva': (costeo_reac or {}).get('total_precio_contado_mxn', 0),
                'precio_menos_diagnostico': None,
                'diagnostico': 0,
            }
            info_equipo_reac = datos_equipo_reac or {}
        else:
            # EXPLICACIÓN PARA PRINCIPIANTES:
            # El resumen del email DEBE usar el mismo motor que el PDF/modal:
            # profit por pieza (profit_override / profit_aplicado), NO un solo %
            # del perfil sobre la suma de costos (eso descuadraba el total).
            from .utils.pdf_cotizacion_cliente import (
                TIPO_SERVICIO_NOMBRES,
                calcular_precios_items_cotizacion,
            )
            calculo_items = calcular_precios_items_cotizacion(
                items=items or [],
                tipo_servicio=tipo_servicio,
                incluir_descuento_diagnostico=False,
                mano_de_obra_override=mano_de_obra_override,
            )
            calculo_resumen = {
                'servicio_nombre': TIPO_SERVICIO_NOMBRES.get(
                    tipo_servicio, 'Cotización'
                ),
                'precio_sin_iva': calculo_items.get('precio_sin_iva', 0),
                'iva': calculo_items.get('iva', 0),
                'precio_con_iva': calculo_items.get('precio_con_iva', 0),
                'precio_menos_diagnostico': None,
                'diagnostico': 0,
                'profit_target': None,
            }
            info_equipo_reac = None

        # Construir el nombre del título de la propuesta para el asunto del email
        titulo_display = titulo_propuesta or calculo_resumen['servicio_nombre']

        # EXPLICACIÓN: con orden → orden_cliente; sin orden → S/T (helper común)
        from .utils.cotizacion_email_context import (
            construir_contexto_email_cotizacion,
            identificador_asunto_solicitud,
        )

        numero_display = identificador_asunto_solicitud(solicitud)

        if asunto_correo and asunto_correo.strip():
            asunto_base = asunto_correo.strip()
        else:
            asunto_base = f'Cotización SIC — {titulo_display} | {numero_display}'

        # Variables adicionales según país (referencia de pago, textos México, etc.)
        contexto_pais = construir_contexto_email_cotizacion(
            solicitud=solicitud,
            pais_config=_pais,
            fecha_local=ahora_local,
            asunto_fallback=asunto_base,
        )

        # México: si hay Solución Plata, el correo avisa que el detalle va en el PDF
        pais_codigo_email = _pais.get('codigo', '')
        incluye_paquete_plata = (
            pais_codigo_email == 'MX'
            and any(item.get('tipo_servicio') == 'paquete_plata' for item in (items or []))
        )

        context_email = {
            'solicitud':             solicitud,
            'titulo_propuesta':      titulo_display,
            'info_equipo':           info_equipo,
            'nombre_cliente':        nombre_cliente,
            'calculo':               calculo_resumen,
            'mensaje_personalizado': mensaje_personalizado,
            'fecha_envio_texto':     ahora_local.strftime('%d/%m/%Y'),
            'hora_envio_texto':      ahora_local.strftime('%H:%M'),
            'empresa_nombre':        _pais.get('empresa_nombre_corto', 'SIC'),
            'pais_nombre':           _pais.get('nombre', ''),
            'whatsapp_empleado':     whatsapp_empleado,
            'nombre_usuario':        nombre_usuario,
            'incluir_descuento':     False,
            'es_reacondicionado':    es_reacondicionado,
            'costeo_reac':           costeo_reac or {},
            'info_equipo_reac':      info_equipo_reac or {},
            'incluye_paquete_plata': incluye_paquete_plata,
            **contexto_pais,
        }

        # Renderizar el template HTML del email
        html_content = render_to_string(
            'almacen/emails/cotizacion_cliente_final.html',
            context_email
        )

        # --- PASO 5: COMPONER Y ENVIAR EL CORREO ---
        # Asunto final: agregar referencia si no venía en asunto personalizado
        referencia_pago = contexto_pais.get('referencia_pago', '')
        if asunto_correo and asunto_correo.strip():
            asunto = asunto_correo.strip()
            # Si el asunto personalizado no incluye la referencia, agregarla al final
            if referencia_pago and referencia_pago.upper() not in asunto.upper():
                asunto = f'{asunto} - {referencia_pago}'
        else:
            asunto = asunto_base
            if referencia_pago:
                asunto = f'{asunto} - {referencia_pago}'

        # Correo remitente extraído desde DEFAULT_FROM_EMAIL
        import re as _re
        email_match = _re.search(r'<(.+?)>', settings.DEFAULT_FROM_EMAIL)
        email_solo  = email_match.group(1) if email_match else settings.DEFAULT_FROM_EMAIL
        remitente   = f"SIC Cotizaciones <{email_solo}>"

        # Crear el objeto EmailMessage con el cliente como destinatario principal
        email_msg = EmailMessage(
            subject=asunto,
            body=html_content,
            from_email=remitente,
            to=[email_cliente],
            cc=copia_empleados or [],
        )
        email_msg.content_subtype = 'html'

        # Adjuntar el logo SIC como imagen inline (CID)
        try:
            logo_path = finders.find('images/logos/logo_sic.png')
            if logo_path:
                with open(logo_path, 'rb') as f:
                    logo_mime = MIMEImage(f.read(), _subtype='png')
                    logo_mime.add_header('Content-ID', '<logo_sic>')
                    logo_mime.add_header('Content-Disposition', 'inline', filename='logo_sic.png')
                    email_msg.attach(logo_mime)
        except Exception as e:
            logger.warning(f"[COTIZACION-CLIENTE] Error al adjuntar logo: {e}")

        # Adjuntar iconos de redes sociales (CID inline)
        try:
            iconos = {
                'icon_link':      'images/utilitys/link.png',
                'icon_instagram': 'images/utilitys/instagram.png',
                'icon_facebook':  'images/utilitys/facebook.png',
                'icon_whatsapp':  'images/utilitys/whatsapp.png',
            }
            for cid_name, static_path in iconos.items():
                icon_path = finders.find(static_path)
                if icon_path:
                    with open(icon_path, 'rb') as f:
                        icon_mime = MIMEImage(f.read(), _subtype='png')
                        icon_mime.add_header('Content-ID', f'<{cid_name}>')
                        icon_mime.add_header('Content-Disposition', 'inline', filename=f'{cid_name}.png')
                        email_msg.attach(icon_mime)
        except Exception as e:
            logger.warning(f"[COTIZACION-CLIENTE] Error al adjuntar iconos: {e}")

        # Adjuntar el PDF generado como archivo descargable
        pdf_mime = MIMEApplication(pdf_bytes, _subtype='pdf')
        pdf_mime.add_header('Content-Disposition', 'attachment', filename=nombre_pdf)
        email_msg.attach(pdf_mime)

        # Enviar el correo
        email_msg.send(fail_silently=False)
        logger.info(
            f"[COTIZACION-CLIENTE] Correo enviado a {email_cliente} "
            f"(CC: {', '.join(copia_empleados) if copia_empleados else 'ninguno'}) "
            f"| PDF: {nombre_pdf}"
        )

        return {
            'success': True,
            'mensaje': f'Correo enviado a {email_cliente}',
            'solicitud': numero_display,
            'pdf': nombre_pdf,
            'items': len(items),
        }

    except Exception as e:
        logger.error(f"[COTIZACION-CLIENTE] Error en tarea: {e}")
        logger.error(traceback.format_exc())
        # Reintentar la tarea hasta max_retries veces si es un error de red
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            return {'success': False, 'mensaje': f'Error tras {self.max_retries} reintentos: {str(e)}'}


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='almacen.notificar_cliente_pnc',
)
def notificar_cliente_pnc_task(
    self,
    solicitud_id,
    email_cliente,
    mensaje_personalizado='',
    copia_empleados=None,
    usuario_id=None,
    db_alias='default',
):
    """
    Tarea Celery: envía al cliente el aviso de partes no disponibles (PNC).

    EXPLICACIÓN PARA PRINCIPIANTES:
    No genera PDF de cotización. Solo informa que las refacciones no están
    disponibles en el mercado y que el centro de servicio dará seguimiento
    si hay alternativas.

    Args:
        solicitud_id: ID de SolicitudCotizacion.
        email_cliente: Destinatario principal (cliente).
        mensaje_personalizado: Nota opcional de Front/Compras.
        copia_empleados: Lista de emails en CC (opcional).
        usuario_id: Quién disparó la acción.
        db_alias: Alias de BD del país (multi-tenant Celery).

    Returns:
        dict con success / mensaje.
    """
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.contrib.staticfiles import finders
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from django.utils import timezone
    from email.mime.image import MIMEImage

    from config.paises_config import fecha_local_pais, get_pais_actual

    from .models import SolicitudCotizacion

    if copia_empleados is None:
        copia_empleados = []

    logger.info(
        f'[PNC-CLIENTE] Iniciando tarea solicitud={solicitud_id} '
        f'→ {email_cliente}'
    )

    try:
        try:
            solicitud = SolicitudCotizacion.objects.select_related(
                'orden_servicio',
                'orden_servicio__detalle_equipo',
            ).prefetch_related(
                'lineas__producto',
            ).get(pk=solicitud_id)
        except SolicitudCotizacion.DoesNotExist:
            logger.error(f'[PNC-CLIENTE] Solicitud {solicitud_id} no encontrada.')
            return {
                'success': False,
                'mensaje': f'Solicitud ID {solicitud_id} no encontrada.',
            }

        _pais_email = get_pais_actual()
        ahora_local = fecha_local_pais(timezone.now(), _pais_email)

        nombre_usuario = ''
        whatsapp_empleado = ''
        if usuario_id:
            User = get_user_model()
            try:
                usuario = User.objects.get(pk=usuario_id)
                nombre_usuario = usuario.get_full_name() or usuario.username
                if hasattr(usuario, 'empleado') and usuario.empleado:
                    numero_local = usuario.empleado.numero_whatsapp
                    if numero_local:
                        codigo_tel = _pais_email.get('codigo_telefonico', '')
                        whatsapp_empleado = f'{codigo_tel}{numero_local}'
            except User.DoesNotExist:
                pass

        # Datos de equipo / cliente para el correo
        info_equipo = None
        nombre_cliente = (solicitud.nombre_cliente or '').strip()
        if solicitud.orden_servicio and hasattr(
            solicitud.orden_servicio, 'detalle_equipo'
        ):
            detalle = solicitud.orden_servicio.detalle_equipo
            info_equipo = {
                'tipo': detalle.tipo_equipo,
                'marca': detalle.marca,
                'modelo': detalle.modelo,
                'service_tag': detalle.numero_serie,
            }
            if not nombre_cliente:
                nombre_cliente = (detalle.nombre_cliente or '').strip()

        lineas_listado = []
        for linea in solicitud.lineas.order_by('numero_linea'):
            lineas_listado.append({
                'numero': linea.numero_linea,
                'producto': (
                    linea.producto.nombre if linea.producto_id else ''
                ),
                'descripcion': linea.descripcion_pieza or '',
                'cantidad': linea.cantidad,
            })

        context = {
            'solicitud': solicitud,
            'lineas_listado': lineas_listado,
            'info_equipo': info_equipo,
            'nombre_cliente': nombre_cliente or 'Cliente',
            'mensaje_personalizado': mensaje_personalizado,
            'tiene_orden_vinculada': bool(solicitud.orden_servicio_id),
            'fecha_envio_texto': ahora_local.strftime('%d/%m/%Y'),
            'hora_envio_texto': ahora_local.strftime('%H:%M'),
            'empresa_nombre': _pais_email['empresa_nombre_corto'],
            'pais_nombre': _pais_email['nombre'],
            'whatsapp_empleado': whatsapp_empleado,
            'nombre_usuario': nombre_usuario,
        }

        html_content = render_to_string(
            'almacen/emails/cotizacion_cliente_pnc.html',
            context,
        )

        # EXPLICACIÓN: con orden → orden_cliente; sin orden → S/T (helper común)
        from .utils.cotizacion_email_context import identificador_asunto_solicitud

        numero_display = identificador_asunto_solicitud(solicitud)

        # EXPLICACIÓN PARA PRINCIPIANTES: el emoji ⚠️ va en el asunto (no en el HTML)
        # para que destaque en la bandeja del cliente, igual que el PNC a recepción.
        asunto = f'⚠️ Aviso: componentes no disponibles - {numero_display}'

        email_match = __import__('re').search(
            r'<(.+?)>', settings.DEFAULT_FROM_EMAIL
        )
        email_solo = (
            email_match.group(1) if email_match else settings.DEFAULT_FROM_EMAIL
        )
        remitente = f'Sistema de Compras <{email_solo}>'

        email_msg = EmailMessage(
            subject=asunto,
            body=html_content,
            from_email=remitente,
            to=[email_cliente],
            cc=[e for e in copia_empleados if e and e != email_cliente],
        )
        email_msg.content_subtype = 'html'

        try:
            logo_path = finders.find('images/logos/logo_sic.png')
            if logo_path:
                with open(logo_path, 'rb') as f:
                    logo_mime = MIMEImage(f.read(), _subtype='png')
                    logo_mime.add_header('Content-ID', '<logo_sic>')
                    logo_mime.add_header(
                        'Content-Disposition', 'inline', filename='logo_sic.png'
                    )
                    email_msg.attach(logo_mime)
        except Exception as e:
            logger.warning(f'[PNC-CLIENTE] Error al adjuntar logo: {e}')

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
            logger.warning(f'[PNC-CLIENTE] Error al adjuntar iconos: {e}')

        email_msg.send(fail_silently=False)
        logger.info(f'[PNC-CLIENTE] Correo enviado a {email_cliente}')

        return {
            'success': True,
            'mensaje': f'Correo PNC enviado a {email_cliente}',
            'solicitud': numero_display,
        }

    except Exception as e:
        logger.error(f'[PNC-CLIENTE] Error en tarea: {e}')
        logger.error(traceback.format_exc())
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            return {
                'success': False,
                'mensaje': f'Error tras {self.max_retries} reintentos: {str(e)}',
            }


# EXPLICACIÓN: Celery solo autodescubre almacen/tasks.py. Importar aquí
# registra la tarea de solicitud de baja sin hinchar este archivo.
from almacen.tasks_solicitud_baja import (  # noqa: E402, F401
    notificar_almacenista_solicitud_baja_task,
    notificar_solicitud_baja_procesada_task,
)

# Mismo motivo: las tareas de vigencia y recotización viven en su propio
# archivo, pero el worker solo las ve si se importan aquí al final.
from almacen.tasks_vigencia_cotizacion import (  # noqa: E402, F401
    notificar_recotizacion_solicitada_task,
    procesar_vigencias_pais_task,
    verificar_vigencia_cotizaciones,
)
