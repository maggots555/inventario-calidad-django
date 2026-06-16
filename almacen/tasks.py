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
):
    """
    Tarea Celery: comprime imágenes y envía correo de cotización a los destinatarios seleccionados.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta tarea se ejecuta en segundo plano para no bloquear al usuario.
    Recupera la solicitud de cotización, comprime las imágenes de cada línea
    y envía un correo HTML a los empleados seleccionados para que compartan
    la cotización con el cliente.

    Parámetros:
        solicitud_id            : ID de la SolicitudCotizacion
        destinatarios           : Lista de emails seleccionados por el usuario
        mensaje_personalizado   : Texto opcional del usuario
        usuario_id              : ID del usuario que disparó la acción
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
        }

        html_content = render_to_string(
            'almacen/emails/cotizacion_front.html',
            context
        )

        # ===================================================================
        # PASO 4: CREAR Y ENVIAR EL CORREO
        # ===================================================================
        # Usar Service Tag si está disponible, sino el número de solicitud
        if solicitud.orden_servicio and hasattr(solicitud.orden_servicio, 'detalle_equipo'):
            service_tag = solicitud.orden_servicio.detalle_equipo.numero_serie
            numero_display = f"S/T: {service_tag}" if service_tag else solicitud.numero_solicitud
        elif solicitud.service_tag:
            numero_display = f"S/T: {solicitud.service_tag}"
        else:
            numero_display = solicitud.numero_solicitud
        
        asunto = f'📋 Nueva Cotización - {numero_display}'

        email_match = __import__('re').search(r'<(.+?)>', settings.DEFAULT_FROM_EMAIL)
        email_solo = email_match.group(1) if email_match else settings.DEFAULT_FROM_EMAIL
        remitente = f"Sistema de Almacén <{email_solo}>"

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

        context = {
            'solicitud': solicitud,
            'lineas': solicitud.lineas.select_related('producto', 'proveedor').all(),
            'fecha_envio_texto': ahora_local.strftime('%d/%m/%Y'),
            'hora_envio_texto': ahora_local.strftime('%H:%M'),
            'empresa_nombre': _pais_email['empresa_nombre_corto'],
            'pais_nombre': _pais_email['nombre'],
            'nombre_usuario': nombre_usuario,
        }

        html_content = render_to_string(
            'almacen/emails/nueva_cotizacion_sin_orden.html',
            context
        )

        # ===================================================================
        # PASO 4: CREAR Y ENVIAR EL CORREO
        # ===================================================================
        service_tag_display = solicitud.service_tag or 'N/A'
        asunto = f'📋 Nueva Cotización Sin Orden — {solicitud.numero_solicitud} (S/T: {service_tag_display})'

        import re
        email_match = re.search(r'<(.+?)>', settings.DEFAULT_FROM_EMAIL)
        email_solo = email_match.group(1) if email_match else settings.DEFAULT_FROM_EMAIL
        remitente = f"Sistema de Almacén <{email_solo}>"

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
