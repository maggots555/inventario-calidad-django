"""
Tareas en segundo plano (Celery) para la app servicio_tecnico.

EXPLICACIÓN PARA PRINCIPIANTES:
Un archivo tasks.py es donde defines las "tareas" que Celery ejecutará
en segundo plano. Cada función decorada con @shared_task es una tarea.

@shared_task es especial: no necesita conocer la app de Celery directamente,
funciona con cualquier instancia de Celery. Es el decorador recomendado
para tareas dentro de apps de Django.

Flujo del correo RHITSO:
    1. El usuario hace clic en "Enviar" en el navegador
    2. La VISTA de Django valida los datos (rápido, < 1 segundo)
    3. La VISTA responde al usuario de inmediato: "Enviando en segundo plano..."
    4. Esta TAREA ejecuta todo lo pesado en paralelo:
       - Generar PDF (~2-5 segundos)
       - Comprimir imágenes (~5-30 segundos según cantidad)
       - Enviar email (~3-10 segundos según conexión)
       - Registrar historial
       - Limpiar archivos temporales
"""
import os
import logging
import traceback

from celery import shared_task
from notificaciones.utils import notificar_exito, notificar_error

logger = logging.getLogger('servicio_tecnico')


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,   # Reintentar tras 60 segundos si falla
    name='servicio_tecnico.enviar_correo_rhitso'
)
def enviar_correo_rhitso_task(self, orden_id, destinatarios_principales, copia_empleados, usuario_id=None):
    """
    Tarea Celery: genera el PDF, comprime imágenes y envía el correo RHITSO.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta función es una "tarea" de Celery. Cuando la vista llama a
    enviar_correo_rhitso_task.delay(...), Celery la pone en una cola
    en Redis y el Worker la ejecuta en cuanto puede, SIN bloquear al usuario.

    Parámetros (IMPORTANTE: solo tipos simples, sin objetos Django):
        self                    : Referencia a la tarea (para reintentos), viene de bind=True
        orden_id                : ID entero de la OrdenServicio en la base de datos
        destinatarios_principales: Lista de emails principales  ej: ['a@lab.com', 'b@lab.com']
        copia_empleados         : Lista de emails en copia       ej: ['jefe@empresa.com']
        usuario_id              : ID del usuario que disparó la acción (para el historial)

    NOTA IMPORTANTE: Los parámetros deben ser tipos simples (int, str, list, dict).
    NUNCA pasar objetos de Django (como una instancia de OrdenServicio) directamente,
    porque Celery los serializa a JSON y los objetos no son serializables.
    En su lugar, pasas el ID y dentro de la tarea lo buscas en la BD.
    """
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from django.utils import timezone
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from pathlib import Path

    from .models import OrdenServicio
    from .utils.pdf_generator import PDFGeneratorRhitso
    from .utils.image_compressor import ImageCompressor

    logger.info(f"[RHITSO] Iniciando tarea de correo para Orden ID {orden_id}")

    try:
        # ===================================================================
        # PASO 1: RECUPERAR LA ORDEN DESDE LA BASE DE DATOS
        # ===================================================================
        # EXPLICACIÓN: Como Celery serializa los parámetros a JSON, no podemos
        # pasar el objeto orden directamente. Lo recuperamos aquí usando el ID.
        try:
            orden = OrdenServicio.objects.get(pk=orden_id)
        except OrdenServicio.DoesNotExist:
            logger.error(f"[RHITSO] Orden ID {orden_id} no encontrada. Tarea cancelada.")
            return {
                'success': False,
                'mensaje': f'Orden ID {orden_id} no encontrada en la base de datos.'
            }

        # ===================================================================
        # PASO 2: GENERAR PDF CON DATOS DEL EQUIPO
        # ===================================================================
        logger.info(f"[RHITSO] Generando PDF para Orden {orden.numero_orden_interno}...")

        imagenes_autorizacion = list(orden.imagenes.filter(tipo='autorizacion'))
        generator = PDFGeneratorRhitso(orden, imagenes_autorizacion)
        resultado_pdf = generator.generar_pdf()

        if not resultado_pdf.get('success'):
            error_msg = resultado_pdf.get('error', 'Error desconocido al generar PDF')
            logger.error(f"[RHITSO] Error generando PDF: {error_msg}")
            raise Exception(f"Error al generar PDF: {error_msg}")

        pdf_path = resultado_pdf['ruta']
        logger.info(f"[RHITSO] PDF generado: {pdf_path}")

        # ===================================================================
        # PASO 3: COMPRIMIR Y ANALIZAR IMÁGENES DE INGRESO
        # ===================================================================
        logger.info(f"[RHITSO] Procesando imágenes de ingreso...")

        imagenes_ingreso = list(orden.imagenes.filter(tipo='ingreso'))
        compressor = ImageCompressor()

        imagenes_para_correo = []
        for imagen in imagenes_ingreso:
            try:
                img_path = imagen.imagen.path
                if Path(img_path).exists() and Path(img_path).is_file():
                    imagenes_para_correo.append({
                        'ruta': img_path,
                        'nombre': os.path.basename(img_path)
                    })
                else:
                    logger.warning(f"[RHITSO] Imagen no encontrada: {img_path}")
            except Exception as e:
                logger.warning(f"[RHITSO] Error al procesar imagen: {e}")

        analisis = compressor.calcular_tamaño_correo(
            ruta_pdf=pdf_path,
            imagenes=imagenes_para_correo,
            contenido_html=""
        )

        if not analisis['success']:
            raise Exception(f"Error al analizar tamaño del correo: {analisis.get('error', 'Error desconocido')}")

        logger.info(
            f"[RHITSO] Tamaño total del correo: {analisis['tamaño_total_mb']} MB / 25 MB"
        )

        if analisis['excede_limite']:
            raise Exception(
                f"El correo excede el límite de Gmail ({analisis['tamaño_total_mb']} MB). "
                f"Reduce el número de imágenes."
            )

        imagenes_paths = [img['ruta_comprimida'] for img in analisis['imagenes_validas']]

        # ===================================================================
        # PASO 4: PREPARAR HTML DEL CORREO
        # ===================================================================
        ahora = timezone.now()
        context = {
            'orden': orden,
            'fecha_actual': ahora.strftime('%d/%m/%Y'),
            'hora_actual': ahora.strftime('%H:%M'),
            'agente_nombre': 'Equipo de Soporte Técnico',
            'agente_celular': '55-35-45-81-92',
            'agente_correo': settings.DEFAULT_FROM_EMAIL,
        }
        html_content = render_to_string(
            'servicio_tecnico/emails/rhitso_envio.html',
            context
        )

        # ===================================================================
        # PASO 5: CREAR Y ENVIAR EL CORREO
        # ===================================================================
        orden_para_asunto = orden.numero_orden_interno
        if orden.detalle_equipo and orden.detalle_equipo.orden_cliente:
            orden_para_asunto = orden.detalle_equipo.orden_cliente

        asunto = f'🔧ENVIO DE EQUIPO RHITSO - {orden_para_asunto}'

        from_email_base = settings.DEFAULT_FROM_EMAIL
        if '<' in from_email_base and '>' in from_email_base:
            email_address = from_email_base.split('<')[1].split('>')[0]
        else:
            email_address = from_email_base
        from_email_rhitso = f'RHITSO System <{email_address}>'

        email_msg = EmailMessage(
            subject=asunto,
            body=html_content,
            from_email=from_email_rhitso,
            to=destinatarios_principales,
            cc=copia_empleados if copia_empleados else None,
        )
        email_msg.content_subtype = 'html'

        # Adjuntar PDF
        if os.path.exists(pdf_path):
            with open(pdf_path, 'rb') as f:
                email_msg.attach(os.path.basename(pdf_path), f.read(), 'application/pdf')

        # Adjuntar imágenes comprimidas
        for imagen_path in imagenes_paths:
            if os.path.exists(imagen_path):
                with open(imagen_path, 'rb') as f:
                    email_msg.attach(os.path.basename(imagen_path), f.read(), 'image/jpeg')

        email_msg.send()
        logger.info(f"[RHITSO] Correo enviado exitosamente a {destinatarios_principales}")

        # ===================================================================
        # PASO 6: REGISTRAR EN HISTORIAL
        # ===================================================================
        # EXPLICACIÓN: Importamos registrar_historial aquí (import local) para
        # evitar importaciones circulares entre tasks.py y views.py.
        try:
            from .views import registrar_historial

            # Recuperar el usuario por ID si fue proporcionado
            usuario_empleado = None
            if usuario_id:
                User = get_user_model()
                try:
                    usuario = User.objects.get(pk=usuario_id)
                    if hasattr(usuario, 'empleado'):
                        usuario_empleado = usuario.empleado
                except User.DoesNotExist:
                    pass

            comentario = f"📧 Correo RHITSO enviado (background) a: {', '.join(destinatarios_principales[:2])}"
            if len(destinatarios_principales) > 2:
                comentario += f" y {len(destinatarios_principales) - 2} más"
            if copia_empleados:
                comentario += f" (con {len(copia_empleados)} copia(s))"

            registrar_historial(
                orden=orden,
                tipo_evento='sistema',
                usuario=usuario_empleado,
                comentario=comentario,
                es_sistema=False
            )
        except Exception as e:
            # El historial no es crítico, si falla no afecta el correo
            logger.warning(f"[RHITSO] No se pudo registrar historial: {e}")

        # ===================================================================
        # PASO 7: LIMPIAR ARCHIVOS TEMPORALES
        # ===================================================================
        archivos_a_limpiar = [pdf_path] + imagenes_paths
        for ruta in archivos_a_limpiar:
            try:
                if ruta and os.path.exists(ruta) and ('compressed' in ruta or ruta == pdf_path):
                    os.remove(ruta)
            except Exception as e:
                logger.warning(f"[RHITSO] No se pudo eliminar archivo temporal {ruta}: {e}")

        logger.info(f"[RHITSO] Tarea completada exitosamente para Orden {orden.numero_orden_interno}")

        # ── Notificar al usuario que la tarea terminó exitosamente ──
        try:
            _usuario_notif = None
            if usuario_id:
                User = get_user_model()
                try:
                    _usuario_notif = User.objects.get(pk=usuario_id)
                except User.DoesNotExist:
                    pass
            # Identificador legible: orden_cliente si existe, si no numero_orden_interno
            _oc = (
                orden.detalle_equipo.orden_cliente
                if orden.detalle_equipo and orden.detalle_equipo.orden_cliente
                else orden.numero_orden_interno
            )
            notificar_exito(
                titulo="Correo RHITSO enviado",
                mensaje=(
                    f"Orden {_oc}"
                    f" — Correo enviado a "
                    f"{len(destinatarios_principales)} destinatario(s). "
                    f"Se adjuntaron {len(imagenes_paths)} imagen(es) "
                    f"({analisis['tamaño_total_mb']} MB)."
                ),
                usuario=_usuario_notif,
                task_id=self.request.id,
                app_origen='servicio_tecnico',
            )
        except Exception as e:
            logger.warning(f"[RHITSO] No se pudo crear notificación de éxito: {e}")

        return {
            'success': True,
            'orden': orden.numero_orden_interno,
            'destinatarios': len(destinatarios_principales),
            'copias': len(copia_empleados),
            'imagenes_adjuntas': len(imagenes_paths),
            'tamaño_total_mb': analisis['tamaño_total_mb'],
        }

    except Exception as exc:
        logger.error(
            f"[RHITSO] Error en tarea de correo para Orden ID {orden_id}: {exc}\n"
            f"{traceback.format_exc()}"
        )
        # ── Notificar error al usuario ──
        try:
            _usuario_err = None
            if usuario_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    _usuario_err = User.objects.get(pk=usuario_id)
                except User.DoesNotExist:
                    pass
            notificar_error(
                titulo="Error al enviar correo RHITSO",
                mensaje=f"Orden {orden_id} — {str(exc)[:200]}",
                usuario=_usuario_err,
                task_id=self.request.id,
                app_origen='servicio_tecnico',
            )
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60)


# ==============================================================================
# TAREA: enviar_feedback_rechazo_task
# Envía correo al cliente con link único para que explique por qué rechazó la
# cotización. Usa token seguro firmado (TimestampSigner). Adjunta logo CID.
# ==============================================================================

@shared_task(bind=True, max_retries=3, default_retry_delay=60, name='servicio_tecnico.enviar_feedback_rechazo')
def enviar_feedback_rechazo_task(self, feedback_id, usuario_id=None):
    """
    Envía correo al cliente con link de feedback de rechazo de cotización.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta tarea recibe el ID del FeedbackCliente ya creado.
    Genera el link firmado, renderiza el HTML y envía el correo.
    Al terminar, marca correo_enviado=True en el modelo.

    Parámetros:
        feedback_id : ID del FeedbackCliente
        usuario_id  : ID del usuario Django que disparó la acción (para notificaciones)
    """
    import re
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from django.utils import timezone
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.contrib.staticfiles import finders
    from email.mime.image import MIMEImage

    from .models import FeedbackCliente, HistorialOrden

    logger.info(f"[FEEDBACK-RECHAZO] Iniciando tarea para FeedbackCliente ID {feedback_id}")

    try:
        # ── Recuperar feedback ──
        try:
            feedback = FeedbackCliente.objects.select_related(
                'cotizacion__orden__detalle_equipo',
                'enviado_por',
            ).get(pk=feedback_id)
        except FeedbackCliente.DoesNotExist:
            logger.error(f"[FEEDBACK-RECHAZO] FeedbackCliente ID {feedback_id} no encontrado.")
            return {'success': False, 'mensaje': f'FeedbackCliente ID {feedback_id} no encontrado.'}

        orden = feedback.cotizacion.orden
        detalle = orden.detalle_equipo
        email_cliente = detalle.email_cliente if detalle else None

        if not email_cliente:
            logger.error(f"[FEEDBACK-RECHAZO] Orden {orden.numero_orden_interno} sin email de cliente.")
            return {'success': False, 'mensaje': 'Sin email de cliente.'}

        # ── Construir URL pública del feedback ──
        site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        feedback_url = f"{site_url}/feedback/{feedback.token}/"

        # ── Datos del cliente y equipo ──
        # NOTA: No se registra nombre del cliente en el sistema, usamos saludo genérico
        nombre_cliente = 'Estimado usuario'
        marca_equipo = detalle.marca or ''
        modelo_equipo = detalle.modelo or ''
        tipo_equipo = detalle.tipo_equipo or ''
        folio = (
            detalle.orden_cliente if detalle and detalle.orden_cliente
            else orden.numero_orden_interno
        )

        # ── Piezas rechazadas ──
        # NOTA: 'componente__nombre' accede al nombre a través de la relación ForeignKey
        # Renombramos la clave para que el template sea más legible
        piezas_raw = feedback.cotizacion.piezas_cotizadas.filter(aceptada_por_cliente=False).values(
            'componente__nombre', 'costo_unitario', 'cantidad'
        )
        piezas = [
            {
                'nombre_pieza': p['componente__nombre'],
                'costo_unitario': p['costo_unitario'],
                'cantidad': p['cantidad']
            }
            for p in piezas_raw
        ]
        monto_total_piezas = sum(
            (p['costo_unitario'] or 0) * (p['cantidad'] or 1) for p in piezas
        )
        monto_mano_obra = feedback.cotizacion.costo_mano_obra or 0

        # ── Contexto para template email ──
        ahora_local = timezone.localtime(timezone.now())
        context_email = {
            'nombre_cliente': nombre_cliente,
            'folio': folio,
            'marca_equipo': marca_equipo,
            'modelo_equipo': modelo_equipo,
            'tipo_equipo': tipo_equipo,
            'motivo_rechazo': feedback.cotizacion.get_motivo_rechazo_display(),
            'piezas': piezas,
            'monto_total_piezas': monto_total_piezas,
            'monto_mano_obra': monto_mano_obra,
            'monto_total': monto_total_piezas + monto_mano_obra,
            'feedback_url': feedback_url,
            'dias_vigencia': 7,
            'fecha_envio': ahora_local.strftime('%d/%m/%Y'),
        }

        html_content = render_to_string(
            'servicio_tecnico/emails/feedback_rechazo.html',
            context_email
        )

        asunto = f'Tu opinión importa — Folio {folio}'
        email_match = re.search(r'<(.+?)>', settings.DEFAULT_FROM_EMAIL)
        email_solo = email_match.group(1) if email_match else settings.DEFAULT_FROM_EMAIL
        remitente = f"Servicio Técnico System <{email_solo}>"

        # ── Preparar CC (Jefe de Calidad) ──
        cc_list = []
        jefe_calidad_email = getattr(settings, 'JEFE_CALIDAD_EMAIL', None)
        if jefe_calidad_email:
            cc_list.append(jefe_calidad_email)

        email_msg = EmailMessage(
            subject=asunto,
            body=html_content,
            from_email=remitente,
            to=[email_cliente],
            cc=cc_list,
        )
        email_msg.content_subtype = 'html'

        # ── Adjuntar logo SIC ──
        try:
            logo_path = finders.find('images/logos/logo_sic.png')
            if logo_path:
                with open(logo_path, 'rb') as f:
                    logo_mime = MIMEImage(f.read(), _subtype='png')
                    logo_mime.add_header('Content-ID', '<logo_sic>')
                    logo_mime.add_header('Content-Disposition', 'inline', filename='logo_sic.png')
                    email_msg.attach(logo_mime)
        except Exception as e:
            logger.warning(f"[FEEDBACK-RECHAZO] Error al adjuntar logo: {e}")

        # ── Adjuntar iconos de redes sociales ──
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
            logger.warning(f"[FEEDBACK-RECHAZO] Error al adjuntar iconos: {e}")

        email_msg.send(fail_silently=False)
        logger.info(f"[FEEDBACK-RECHAZO] Correo enviado a {email_cliente}")

        # ── Marcar correo como enviado ──
        FeedbackCliente.objects.filter(pk=feedback_id).update(correo_enviado=True)

        # ── Registrar en historial ──
        try:
            HistorialOrden.objects.create(
                orden=orden,
                tipo_evento='email',
                comentario=(
                    f"📧 Correo de feedback de rechazo enviado al cliente ({email_cliente})\n"
                    f"🔗 Link válido por 7 días — Token ID: {feedback_id}"
                ),
                usuario=feedback.enviado_por,
                es_sistema=True
            )
        except Exception as e:
            logger.warning(f"[FEEDBACK-RECHAZO] No se pudo registrar historial: {e}")

        # ── Notificar éxito ──
        try:
            _usuario_notif = None
            if usuario_id:
                User = get_user_model()
                try:
                    _usuario_notif = User.objects.get(pk=usuario_id)
                except User.DoesNotExist:
                    pass
            notificar_exito(
                titulo="Correo de feedback enviado",
                mensaje=f"Orden {folio} — Correo de feedback de rechazo enviado a {email_cliente}.",
                usuario=_usuario_notif,
                task_id=self.request.id,
                app_origen='servicio_tecnico',
            )
        except Exception as e:
            logger.warning(f"[FEEDBACK-RECHAZO] No se pudo crear notificación: {e}")

        return {'success': True, 'feedback_id': feedback_id, 'destinatario': email_cliente}

    except Exception as exc:
        logger.error(f"[FEEDBACK-RECHAZO] Error para FeedbackCliente ID {feedback_id}: {exc}\n{traceback.format_exc()}")
        try:
            _usuario_err = None
            if usuario_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    _usuario_err = User.objects.get(pk=usuario_id)
                except User.DoesNotExist:
                    pass
            notificar_error(
                titulo="Error al enviar correo de feedback",
                mensaje=f"FeedbackCliente ID {feedback_id} — {str(exc)[:200]}",
                usuario=_usuario_err,
                task_id=self.request.id,
                app_origen='servicio_tecnico',
            )
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60)


# ==============================================================================
# TAREA: enviar_vigencia_vencida_task
# Para el motivo 'falta_de_respuesta': envía correo informando que la cotización
# venció por falta de respuesta del cliente. Sin link de feedback.
# ==============================================================================

@shared_task(bind=True, max_retries=3, default_retry_delay=60, name='servicio_tecnico.enviar_vigencia_vencida')
def enviar_vigencia_vencida_task(self, orden_id, usuario_id=None):
    """
    Envía correo al cliente informando que la cotización venció por falta de respuesta.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Solo envía un correo informativo. No crea FeedbackCliente ni token.
    Se usa únicamente con el motivo 'falta_de_respuesta'.

    Parámetros:
        orden_id   : ID de OrdenServicio
        usuario_id : ID del usuario Django que disparó la acción (para notificaciones)
    """
    import re
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from django.utils import timezone
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.contrib.staticfiles import finders
    from email.mime.image import MIMEImage

    from .models import OrdenServicio, HistorialOrden

    logger.info(f"[VIGENCIA-VENCIDA] Iniciando tarea para Orden ID {orden_id}")

    try:
        try:
            orden = OrdenServicio.objects.select_related(
                'detalle_equipo', 'cotizacion'
            ).get(pk=orden_id)
        except OrdenServicio.DoesNotExist:
            logger.error(f"[VIGENCIA-VENCIDA] Orden ID {orden_id} no encontrada.")
            return {'success': False, 'mensaje': f'Orden ID {orden_id} no encontrada.'}

        detalle = orden.detalle_equipo
        email_cliente = detalle.email_cliente if detalle else None

        if not email_cliente:
            logger.error(f"[VIGENCIA-VENCIDA] Orden {orden.numero_orden_interno} sin email de cliente.")
            return {'success': False, 'mensaje': 'Sin email de cliente.'}

        # NOTA: No se registra nombre del cliente en el sistema, usamos saludo genérico
        nombre_cliente = 'Estimado usuario'
        folio = (
            detalle.orden_cliente if detalle and detalle.orden_cliente
            else orden.numero_orden_interno
        )
        marca_equipo = detalle.marca or ''
        modelo_equipo = detalle.modelo or ''

        ahora_local = timezone.localtime(timezone.now())
        context_email = {
            'nombre_cliente': nombre_cliente,
            'folio': folio,
            'marca_equipo': marca_equipo,
            'modelo_equipo': modelo_equipo,
            'fecha_envio': ahora_local.strftime('%d/%m/%Y'),
        }

        html_content = render_to_string(
            'servicio_tecnico/emails/vigencia_vencida.html',
            context_email
        )

        asunto = f'Tu cotización venció — Folio {folio}'
        email_match = re.search(r'<(.+?)>', settings.DEFAULT_FROM_EMAIL)
        email_solo = email_match.group(1) if email_match else settings.DEFAULT_FROM_EMAIL
        remitente = f"Servicio Técnico System <{email_solo}>"

        # ── Preparar CC (Jefe de Calidad) ──
        cc_list = []
        jefe_calidad_email = getattr(settings, 'JEFE_CALIDAD_EMAIL', None)
        if jefe_calidad_email:
            cc_list.append(jefe_calidad_email)

        email_msg = EmailMessage(
            subject=asunto,
            body=html_content,
            from_email=remitente,
            to=[email_cliente],
            cc=cc_list,
        )
        email_msg.content_subtype = 'html'

        # ── Adjuntar logo SIC ──
        try:
            logo_path = finders.find('images/logos/logo_sic.png')
            if logo_path:
                with open(logo_path, 'rb') as f:
                    logo_mime = MIMEImage(f.read(), _subtype='png')
                    logo_mime.add_header('Content-ID', '<logo_sic>')
                    logo_mime.add_header('Content-Disposition', 'inline', filename='logo_sic.png')
                    email_msg.attach(logo_mime)
        except Exception as e:
            logger.warning(f"[VIGENCIA-VENCIDA] Error al adjuntar logo: {e}")

        # ── Adjuntar iconos de redes sociales ──
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
            logger.warning(f"[VIGENCIA-VENCIDA] Error al adjuntar iconos: {e}")

        email_msg.send(fail_silently=False)
        logger.info(f"[VIGENCIA-VENCIDA] Correo enviado a {email_cliente}")

        # ── Registrar en historial ──
        try:
            empleado_actual = None
            if usuario_id:
                User = get_user_model()
                try:
                    usuario = User.objects.get(pk=usuario_id)
                    if hasattr(usuario, 'empleado'):
                        empleado_actual = usuario.empleado
                except User.DoesNotExist:
                    pass
            HistorialOrden.objects.create(
                orden=orden,
                tipo_evento='email',
                comentario=f"📧 Correo de cotización vencida enviado al cliente ({email_cliente})",
                usuario=empleado_actual,
                es_sistema=True
            )
        except Exception as e:
            logger.warning(f"[VIGENCIA-VENCIDA] No se pudo registrar historial: {e}")

        # ── Notificar éxito ──
        try:
            _usuario_notif = None
            if usuario_id:
                User = get_user_model()
                try:
                    _usuario_notif = User.objects.get(pk=usuario_id)
                except User.DoesNotExist:
                    pass
            notificar_exito(
                titulo="Correo de vigencia vencida enviado",
                mensaje=f"Orden {folio} — Correo de cotización vencida enviado a {email_cliente}.",
                usuario=_usuario_notif,
                task_id=self.request.id,
                app_origen='servicio_tecnico',
            )
        except Exception as e:
            logger.warning(f"[VIGENCIA-VENCIDA] No se pudo crear notificación: {e}")

        return {'success': True, 'orden': orden.numero_orden_interno, 'destinatario': email_cliente}

    except Exception as exc:
        logger.error(f"[VIGENCIA-VENCIDA] Error para Orden ID {orden_id}: {exc}\n{traceback.format_exc()}")
        try:
            _usuario_err = None
            if usuario_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    _usuario_err = User.objects.get(pk=usuario_id)
                except User.DoesNotExist:
                    pass
            notificar_error(
                titulo="Error al enviar correo de vigencia vencida",
                mensaje=f"Orden {orden_id} — {str(exc)[:200]}",
                usuario=_usuario_err,
                task_id=self.request.id,
                app_origen='servicio_tecnico',
            )
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60)


# ============================================================================
# TAREA 2: ENVIAR DIAGNÓSTICO AL CLIENTE
# ============================================================================

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='servicio_tecnico.enviar_diagnostico_cliente'
)
def enviar_diagnostico_cliente_task(
    self, orden_id, folio, componentes_data, imagenes_ids,
    destinatarios_copia, mensaje_personalizado,
    email_empleado, nombre_empleado, usuario_id=None
):
    """
    Tarea Celery: genera PDF de diagnóstico, comprime imágenes, crea Cotización
    y PiezaCotizada, envía el correo al cliente, cambia estado y registra historial.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta tarea recibe SOLO tipos simples (int, str, list, dict).
    Dentro de la tarea recuperamos los objetos Django desde la BD usando los IDs.

    Parámetros:
        orden_id              : ID de la OrdenServicio
        folio                 : Folio del diagnóstico (string)
        componentes_data      : Lista de dicts con componentes seleccionados
        imagenes_ids          : Lista de IDs de ImagenOrden (tipo 'diagnostico')
        destinatarios_copia   : Lista de emails en CC
        mensaje_personalizado : Texto personalizado del usuario
        email_empleado        : Email del empleado que envía
        nombre_empleado       : Nombre del empleado que envía
        usuario_id            : ID del usuario (para historial)
    """
    import io
    import re
    from decimal import Decimal
    from pathlib import Path
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from django.utils import timezone
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.contrib.staticfiles import finders
    from email.mime.image import MIMEImage
    from PIL import Image

    from scorecard.models import ComponenteEquipo
    from .models import OrdenServicio, ImagenOrden, Cotizacion, PiezaCotizada

    logger.info(f"[DIAGNOSTICO] Iniciando tarea para Orden ID {orden_id}, Folio {folio}")

    try:
        # ===================================================================
        # PASO 1: RECUPERAR ORDEN
        # ===================================================================
        try:
            orden = OrdenServicio.objects.select_related('detalle_equipo').get(pk=orden_id)
        except OrdenServicio.DoesNotExist:
            logger.error(f"[DIAGNOSTICO] Orden ID {orden_id} no encontrada.")
            return {'success': False, 'mensaje': f'Orden ID {orden_id} no encontrada.'}

        detalle = orden.detalle_equipo
        email_cliente = detalle.email_cliente

        # ===================================================================
        # PASO 2: GENERAR PDF DE DIAGNÓSTICO
        # ===================================================================
        logger.info(f"[DIAGNOSTICO] Generando PDF...")
        from .utils.pdf_diagnostico import PDFGeneratorDiagnostico
        from config.paises_config import get_pais_actual, fecha_local_pais

        componentes_para_pdf = []
        for comp in componentes_data:
            componentes_para_pdf.append({
                'componente_db': comp.get('componente_db', ''),
                'dpn': comp.get('dpn', ''),
                'seleccionado': comp.get('seleccionado', False),
                'es_necesaria': comp.get('es_necesaria', True)
            })

        _pais_pdf = get_pais_actual()
        generador_pdf = PDFGeneratorDiagnostico(
            orden=orden,
            folio=folio,
            componentes_seleccionados=componentes_para_pdf,
            email_empleado=email_empleado,
            pais_config=_pais_pdf
        )
        resultado_pdf = generador_pdf.generar_pdf()

        if not resultado_pdf['success']:
            raise Exception(f"Error al generar PDF: {resultado_pdf.get('error', 'desconocido')}")

        logger.info(f"[DIAGNOSTICO] PDF generado: {resultado_pdf['archivo']}")

        # ===================================================================
        # PASO 3: COMPRIMIR IMÁGENES DE DIAGNÓSTICO
        # ===================================================================
        imagenes_comprimidas = []

        if imagenes_ids:
            logger.info(f"[DIAGNOSTICO] Comprimiendo {len(imagenes_ids)} imagen(es)...")
            imagenes = ImagenOrden.objects.filter(
                id__in=imagenes_ids, orden=orden, tipo='diagnostico'
            )

            for imagen in imagenes:
                try:
                    img_path = imagen.imagen.path
                    if not Path(img_path).exists() or not Path(img_path).is_file():
                        continue

                    img = Image.open(img_path)

                    if img.mode in ('RGBA', 'LA', 'P'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = background

                    max_dimension = 1920
                    if max(img.size) > max_dimension:
                        ratio = max_dimension / max(img.size)
                        new_size = tuple([int(dim * ratio) for dim in img.size])
                        img = img.resize(new_size, Image.Resampling.LANCZOS)

                    output = io.BytesIO()
                    img.save(output, format='JPEG', quality=85, optimize=True)
                    output.seek(0)

                    nombre_archivo = f"diagnostico_{imagen.id}_{os.path.basename(imagen.imagen.name)}"
                    if not nombre_archivo.lower().endswith('.jpg'):
                        nombre_archivo = os.path.splitext(nombre_archivo)[0] + '.jpg'

                    imagenes_comprimidas.append({
                        'nombre': nombre_archivo,
                        'contenido': output.getvalue(),
                    })
                except Exception as e:
                    logger.warning(f"[DIAGNOSTICO] Error procesando imagen {imagen.id}: {e}")

        # ===================================================================
        # PASO 4: CREAR/OBTENER COTIZACIÓN Y PRE-CREAR PIEZAS
        # ===================================================================
        cotizacion, cotizacion_creada = Cotizacion.objects.get_or_create(
            orden=orden,
            defaults={
                'fecha_envio': timezone.now(),
                'costo_mano_obra': Decimal('0.00'),
            }
        )

        piezas_creadas = 0
        componentes_seleccionados_nombres = []

        for comp in componentes_data:
            if comp.get('seleccionado', False):
                componente_nombre = comp.get('componente_db', '')
                dpn = comp.get('dpn', '')
                if not componente_nombre:
                    continue

                try:
                    componente_obj = ComponenteEquipo.objects.get(nombre=componente_nombre)
                except ComponenteEquipo.DoesNotExist:
                    continue

                pieza_existente = PiezaCotizada.objects.filter(
                    cotizacion=cotizacion, componente=componente_obj
                ).exists()

                if not pieza_existente:
                    PiezaCotizada.objects.create(
                        cotizacion=cotizacion,
                        componente=componente_obj,
                        descripcion_adicional=dpn,
                        costo_unitario=Decimal('0.00'),
                        proveedor='',
                        cantidad=1,
                        sugerida_por_tecnico=True,
                        es_necesaria=comp.get('es_necesaria', True),
                        orden_prioridad=piezas_creadas + 1
                    )
                    piezas_creadas += 1
                    componentes_seleccionados_nombres.append(componente_nombre)

        logger.info(f"[DIAGNOSTICO] Piezas pre-creadas: {piezas_creadas}")

        # ===================================================================
        # PASO 5: PREPARAR Y ENVIAR CORREO
        # ===================================================================
        _pais_email = get_pais_actual()

        # WhatsApp del empleado (reconstruimos el link porque no podemos serializar request)
        whatsapp_empleado = ''
        if usuario_id:
            User = get_user_model()
            try:
                usuario = User.objects.get(pk=usuario_id)
                if hasattr(usuario, 'empleado') and usuario.empleado:
                    numero_local = usuario.empleado.numero_whatsapp
                    if numero_local:
                        codigo_tel = _pais_email.get('codigo_telefonico', '')
                        whatsapp_empleado = f"{codigo_tel}{numero_local}"
            except User.DoesNotExist:
                pass

        ahora_local = fecha_local_pais(timezone.now(), _pais_email)

        context_email = {
            'orden': orden,
            'detalle': detalle,
            'folio': folio,
            'mensaje_personalizado': mensaje_personalizado,
            'fecha_envio_texto': ahora_local.strftime('%d/%m/%Y'),
            'hora_envio_texto': ahora_local.strftime('%H:%M'),
            'cantidad_imagenes': len(imagenes_comprimidas),
            'componentes_seleccionados': componentes_seleccionados_nombres,
            'piezas_creadas': piezas_creadas,
            'empresa_nombre': _pais_email['empresa_nombre_corto'],
            'pais_nombre': _pais_email['nombre'],
            'email_empleado': email_empleado,
            'nombre_empleado': nombre_empleado,
            'whatsapp_empleado': whatsapp_empleado,
        }

        html_content = render_to_string(
            'servicio_tecnico/emails/diagnostico_cliente.html',
            context_email
        )

        asunto = f'DIAGNOSTICO FOLIO {folio}'
        email_match = re.search(r'<(.+?)>', settings.DEFAULT_FROM_EMAIL)
        email_solo = email_match.group(1) if email_match else settings.DEFAULT_FROM_EMAIL
        remitente = f"Servicio Técnico System <{email_solo}>"

        email_msg = EmailMessage(
            subject=asunto,
            body=html_content,
            from_email=remitente,
            to=[email_cliente],
            cc=destinatarios_copia if destinatarios_copia else None,
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
            logger.warning(f"[DIAGNOSTICO] Error al adjuntar logo: {e}")

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
            logger.warning(f"[DIAGNOSTICO] Error al adjuntar iconos: {e}")

        # Adjuntar PDF
        with open(resultado_pdf['ruta'], 'rb') as f:
            email_msg.attach(resultado_pdf['archivo'], f.read(), 'application/pdf')

        # Adjuntar imágenes comprimidas
        for img_data in imagenes_comprimidas:
            email_msg.attach(img_data['nombre'], img_data['contenido'], 'image/jpeg')

        email_msg.send(fail_silently=False)
        logger.info(f"[DIAGNOSTICO] Correo enviado a {email_cliente}")

        # ===================================================================
        # PASO 6: CAMBIAR ESTADO DE LA ORDEN
        # ===================================================================
        estado_anterior = orden.estado
        orden.estado = 'diagnostico_enviado_cliente'
        orden.save(update_fields=['estado'])
        logger.info(f"[DIAGNOSTICO] Estado: {estado_anterior} → diagnostico_enviado_cliente")

        # ===================================================================
        # PASO 7: REGISTRAR EN HISTORIAL
        # ===================================================================
        try:
            from .views import registrar_historial

            usuario_empleado = None
            if usuario_id:
                User = get_user_model()
                try:
                    usuario = User.objects.get(pk=usuario_id)
                    if hasattr(usuario, 'empleado'):
                        usuario_empleado = usuario.empleado
                except User.DoesNotExist:
                    pass

            comentario = (
                f"📧 Diagnóstico enviado al cliente (background) ({email_cliente})\n"
                f"📋 Folio: {folio}\n"
                f"📄 PDF adjunto: {resultado_pdf['archivo']}\n"
                f"🔧 Componentes marcados: {piezas_creadas}\n"
                f"📸 Imágenes adjuntas: {len(imagenes_comprimidas)}"
            )
            if destinatarios_copia:
                comentario += f"\n👥 Copia a: {', '.join(destinatarios_copia)}"
            if componentes_seleccionados_nombres:
                comentario += f"\n🔧 Piezas: {', '.join(componentes_seleccionados_nombres)}"

            registrar_historial(
                orden=orden,
                tipo_evento='email',
                usuario=usuario_empleado,
                comentario=comentario,
                es_sistema=False
            )
        except Exception as e:
            logger.warning(f"[DIAGNOSTICO] No se pudo registrar historial: {e}")

        # ===================================================================
        # PASO 8: LIMPIAR PDF TEMPORAL
        # ===================================================================
        try:
            os.unlink(resultado_pdf['ruta'])
        except Exception:
            pass

        logger.info(f"[DIAGNOSTICO] Tarea completada para Orden {orden.numero_orden_interno}")

        # ── Notificar éxito al usuario ──
        try:
            _usuario_notif = None
            if usuario_id:
                User = get_user_model()
                try:
                    _usuario_notif = User.objects.get(pk=usuario_id)
                except User.DoesNotExist:
                    pass
            # Identificador legible: orden_cliente si existe, si no numero_orden_interno
            _oc = (
                detalle.orden_cliente
                if detalle and detalle.orden_cliente
                else orden.numero_orden_interno
            )
            notificar_exito(
                titulo="Diagnóstico enviado al cliente",
                mensaje=(
                    f"Orden {_oc}"
                    f" — Folio {folio}. "
                    f"Enviado a {email_cliente}. "
                    f"{piezas_creadas} pieza(s) pre-cotizada(s), "
                    f"{len(imagenes_comprimidas)} imagen(es) adjunta(s)."
                ),
                usuario=_usuario_notif,
                task_id=self.request.id,
                app_origen='servicio_tecnico',
            )
        except Exception as e:
            logger.warning(f"[DIAGNOSTICO] No se pudo crear notificación de éxito: {e}")

        return {
            'success': True,
            'orden': orden.numero_orden_interno,
            'destinatario': email_cliente,
            'folio': folio,
            'piezas_creadas': piezas_creadas,
            'imagenes_enviadas': len(imagenes_comprimidas),
        }

    except Exception as exc:
        logger.error(f"[DIAGNOSTICO] Error para Orden ID {orden_id}: {exc}\n{traceback.format_exc()}")
        # ── Notificar error al usuario ──
        try:
            _usuario_err = None
            if usuario_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    _usuario_err = User.objects.get(pk=usuario_id)
                except User.DoesNotExist:
                    pass
            notificar_error(
                titulo="Error al enviar diagnóstico",
                mensaje=f"Orden {orden_id}, Folio {folio} — {str(exc)[:200]}",
                usuario=_usuario_err,
                task_id=self.request.id,
                app_origen='servicio_tecnico',
            )
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60)


# ============================================================================
# TAREA 3: ENVIAR IMÁGENES AL CLIENTE
# ============================================================================

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='servicio_tecnico.enviar_imagenes_cliente'
)
def enviar_imagenes_cliente_task(
    self, orden_id, imagenes_ids, destinatarios_copia,
    mensaje_personalizado, usuario_id=None
):
    """
    Tarea Celery: comprime imágenes de ingreso y las envía al cliente por correo.

    Parámetros:
        orden_id              : ID de la OrdenServicio
        imagenes_ids          : Lista de IDs de ImagenOrden (tipo 'ingreso')
        destinatarios_copia   : Lista de emails en CC
        mensaje_personalizado : Texto personalizado del usuario
        usuario_id            : ID del usuario que disparó la acción
    """
    import io
    import re
    from pathlib import Path
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from django.utils import timezone
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.contrib.staticfiles import finders
    from email.mime.image import MIMEImage
    from PIL import Image

    from .models import OrdenServicio, ImagenOrden, HistorialOrden

    logger.info(f"[IMAGENES] Iniciando tarea para Orden ID {orden_id}")

    try:
        # ===================================================================
        # PASO 1: RECUPERAR ORDEN
        # ===================================================================
        try:
            orden = OrdenServicio.objects.select_related('detalle_equipo').get(pk=orden_id)
        except OrdenServicio.DoesNotExist:
            logger.error(f"[IMAGENES] Orden ID {orden_id} no encontrada.")
            return {'success': False, 'mensaje': f'Orden ID {orden_id} no encontrada.'}

        email_cliente = orden.detalle_equipo.email_cliente

        # ===================================================================
        # PASO 2: COMPRIMIR IMÁGENES
        # ===================================================================
        logger.info(f"[IMAGENES] Comprimiendo {len(imagenes_ids)} imagen(es)...")

        imagenes = ImagenOrden.objects.filter(
            id__in=imagenes_ids, orden=orden, tipo='ingreso'
        )

        imagenes_comprimidas = []
        tamaño_total_original = 0
        tamaño_total_comprimido = 0

        for imagen in imagenes:
            try:
                img_path = imagen.imagen.path
                if not Path(img_path).exists() or not Path(img_path).is_file():
                    continue

                img = Image.open(img_path)
                tamaño_original = os.path.getsize(img_path)
                tamaño_total_original += tamaño_original

                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background

                max_dimension = 1920
                if max(img.size) > max_dimension:
                    ratio = max_dimension / max(img.size)
                    new_size = tuple([int(dim * ratio) for dim in img.size])
                    img = img.resize(new_size, Image.Resampling.LANCZOS)

                output = io.BytesIO()
                img.save(output, format='JPEG', quality=85, optimize=True)
                output.seek(0)

                tamaño_comprimido = len(output.getvalue())
                tamaño_total_comprimido += tamaño_comprimido

                nombre_archivo = f"ingreso_{imagen.id}_{os.path.basename(imagen.imagen.name)}"
                if not nombre_archivo.lower().endswith('.jpg'):
                    nombre_archivo = os.path.splitext(nombre_archivo)[0] + '.jpg'

                imagenes_comprimidas.append({
                    'nombre': nombre_archivo,
                    'contenido': output.getvalue(),
                    'tamaño_comprimido': tamaño_comprimido,
                })
            except Exception as e:
                logger.warning(f"[IMAGENES] Error procesando imagen {imagen.id}: {e}")

        if not imagenes_comprimidas:
            raise Exception("No se pudo procesar ninguna imagen.")

        logger.info(
            f"[IMAGENES] Compresión: {tamaño_total_original/1024/1024:.2f} MB → "
            f"{tamaño_total_comprimido/1024/1024:.2f} MB"
        )

        # ===================================================================
        # PASO 3: PREPARAR HTML DEL CORREO
        # ===================================================================
        from config.paises_config import get_pais_actual, fecha_local_pais
        _pais_email = get_pais_actual()

        whatsapp_empleado = ''
        if usuario_id:
            User = get_user_model()
            try:
                usuario = User.objects.get(pk=usuario_id)
                if hasattr(usuario, 'empleado') and usuario.empleado:
                    numero_local = usuario.empleado.numero_whatsapp
                    if numero_local:
                        codigo_tel = _pais_email.get('codigo_telefonico', '')
                        whatsapp_empleado = f"{codigo_tel}{numero_local}"
            except User.DoesNotExist:
                pass

        ahora_local = fecha_local_pais(timezone.now(), _pais_email)

        context = {
            'orden': orden,
            'detalle': orden.detalle_equipo,
            'mensaje_personalizado': mensaje_personalizado,
            'fecha_envio_texto': ahora_local.strftime('%d/%m/%Y'),
            'hora_envio_texto': ahora_local.strftime('%H:%M'),
            'cantidad_imagenes': len(imagenes_comprimidas),
            'empresa_nombre': _pais_email['empresa_nombre_corto'],
            'pais_nombre': _pais_email['nombre'],
            'whatsapp_empleado': whatsapp_empleado,
        }

        html_content = render_to_string(
            'servicio_tecnico/emails/imagenes_cliente.html',
            context
        )

        # ===================================================================
        # PASO 4: CREAR Y ENVIAR EL CORREO
        # ===================================================================
        numero_orden_display = (
            orden.detalle_equipo.orden_cliente
            if orden.detalle_equipo.orden_cliente
            else orden.numero_orden_interno
        )
        asunto = f'📸 Fotografías de ingreso - Orden {numero_orden_display}'

        email_match = re.search(r'<(.+?)>', settings.DEFAULT_FROM_EMAIL)
        email_solo = email_match.group(1) if email_match else settings.DEFAULT_FROM_EMAIL
        remitente = f"Servicio Técnico System <{email_solo}>"

        email_msg = EmailMessage(
            subject=asunto,
            body=html_content,
            from_email=remitente,
            to=[email_cliente],
            cc=destinatarios_copia if destinatarios_copia else None,
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
            logger.warning(f"[IMAGENES] Error al adjuntar logo: {e}")

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
            logger.warning(f"[IMAGENES] Error al adjuntar iconos: {e}")

        # Adjuntar imágenes comprimidas
        for img_data in imagenes_comprimidas:
            email_msg.attach(img_data['nombre'], img_data['contenido'], 'image/jpeg')

        email_msg.send(fail_silently=False)
        logger.info(f"[IMAGENES] Correo enviado a {email_cliente}")

        # ===================================================================
        # PASO 5: REGISTRAR EN HISTORIAL
        # ===================================================================
        try:
            usuario_empleado = None
            if usuario_id:
                User = get_user_model()
                try:
                    usuario = User.objects.get(pk=usuario_id)
                    if hasattr(usuario, 'empleado'):
                        usuario_empleado = usuario.empleado
                except User.DoesNotExist:
                    pass

            reduccion_total = (
                ((tamaño_total_original - tamaño_total_comprimido) / tamaño_total_original) * 100
                if tamaño_total_original > 0 else 0
            )

            comentario = (
                f"📧 Imágenes de ingreso enviadas al cliente (background) ({email_cliente})\n"
                f"📸 Cantidad de imágenes: {len(imagenes_comprimidas)}\n"
                f"📦 Tamaño total: {tamaño_total_comprimido/1024/1024:.2f} MB"
            )
            if destinatarios_copia:
                comentario += f"\n👥 Copia a: {', '.join(destinatarios_copia)}"
            if mensaje_personalizado:
                comentario += f"\n💬 Mensaje: {mensaje_personalizado[:100]}..."

            HistorialOrden.objects.create(
                orden=orden,
                tipo_evento='email',
                comentario=comentario,
                usuario=usuario_empleado,
                es_sistema=False
            )
        except Exception as e:
            logger.warning(f"[IMAGENES] No se pudo registrar historial: {e}")

        logger.info(f"[IMAGENES] Tarea completada para Orden {orden.numero_orden_interno}")

        # ── Notificar éxito al usuario ──
        try:
            _usuario_notif = None
            if usuario_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    _usuario_notif = User.objects.get(pk=usuario_id)
                except User.DoesNotExist:
                    pass
            # Identificador legible: orden_cliente si existe, si no numero_orden_interno
            _oc = (
                orden.detalle_equipo.orden_cliente
                if orden.detalle_equipo and orden.detalle_equipo.orden_cliente
                else orden.numero_orden_interno
            )
            notificar_exito(
                titulo="Imágenes enviadas al cliente",
                mensaje=(
                    f"Orden {_oc}"
                    f" — "
                    f"{len(imagenes_comprimidas)} imagen(es) enviada(s) a {email_cliente}. "
                    f"Tamaño total: {tamaño_total_comprimido/1024/1024:.2f} MB."
                ),
                usuario=_usuario_notif,
                task_id=self.request.id,
                app_origen='servicio_tecnico',
            )
        except Exception as e:
            logger.warning(f"[IMAGENES] No se pudo crear notificación de éxito: {e}")

        return {
            'success': True,
            'orden': orden.numero_orden_interno,
            'destinatario': email_cliente,
            'imagenes_enviadas': len(imagenes_comprimidas),
            'tamaño_mb': round(tamaño_total_comprimido / 1024 / 1024, 2),
        }

    except Exception as exc:
        logger.error(f"[IMAGENES] Error para Orden ID {orden_id}: {exc}\n{traceback.format_exc()}")
        # ── Notificar error al usuario ──
        try:
            _usuario_err = None
            if usuario_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    _usuario_err = User.objects.get(pk=usuario_id)
                except User.DoesNotExist:
                    pass
            notificar_error(
                titulo="Error al enviar imágenes",
                mensaje=f"Orden {orden_id} — {str(exc)[:200]}",
                usuario=_usuario_err,
                task_id=self.request.id,
                app_origen='servicio_tecnico',
            )
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60)


# ============================================================================
# TAREA 4: ENVIAR IMÁGENES DE EGRESO AL CLIENTE
# ============================================================================

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='servicio_tecnico.enviar_imagenes_egreso_cliente'
)
def enviar_imagenes_egreso_cliente_task(
    self, orden_id, destinatarios_copia, usuario_id=None
):
    """
    Tarea Celery: comprime imágenes de egreso y las envía al cliente por correo.

    A diferencia de la tarea de ingreso, esta tarea:
    - Envía TODAS las imágenes de tipo 'egreso' de la orden (sin selección manual).
    - Usa el template imagenes_egreso_cliente.html con la nota aclaratoria de
      que el equipo aún NO está listo para ser recolectado.
    - Los destinatarios provienen del parseo del historial del envío de ingreso.

    Parámetros:
        orden_id             : ID de la OrdenServicio
        destinatarios_copia  : Lista de emails en CC (extraídos del historial de ingreso)
        usuario_id           : ID del usuario que disparó la acción
    """
    import io
    import re
    from pathlib import Path
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from django.utils import timezone
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.contrib.staticfiles import finders
    from email.mime.image import MIMEImage
    from PIL import Image

    from .models import OrdenServicio, ImagenOrden, HistorialOrden

    logger.info(f"[IMAGENES-EGRESO] Iniciando tarea para Orden ID {orden_id}")

    try:
        # ===================================================================
        # PASO 1: RECUPERAR ORDEN
        # ===================================================================
        try:
            orden = OrdenServicio.objects.select_related('detalle_equipo').get(pk=orden_id)
        except OrdenServicio.DoesNotExist:
            logger.error(f"[IMAGENES-EGRESO] Orden ID {orden_id} no encontrada.")
            return {'success': False, 'mensaje': f'Orden ID {orden_id} no encontrada.'}

        email_cliente = orden.detalle_equipo.email_cliente

        # ===================================================================
        # PASO 2: OBTENER Y COMPRIMIR IMÁGENES DE EGRESO
        # ===================================================================
        imagenes = ImagenOrden.objects.filter(orden=orden, tipo='egreso')
        logger.info(f"[IMAGENES-EGRESO] Encontradas {imagenes.count()} imágenes de egreso.")

        imagenes_comprimidas = []
        tamaño_total_original = 0
        tamaño_total_comprimido = 0

        for imagen in imagenes:
            try:
                img_path = imagen.imagen.path
                if not Path(img_path).exists() or not Path(img_path).is_file():
                    continue

                img = Image.open(img_path)
                tamaño_original = os.path.getsize(img_path)
                tamaño_total_original += tamaño_original

                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background

                max_dimension = 1920
                if max(img.size) > max_dimension:
                    ratio = max_dimension / max(img.size)
                    new_size = tuple([int(dim * ratio) for dim in img.size])
                    img = img.resize(new_size, Image.Resampling.LANCZOS)

                output = io.BytesIO()
                img.save(output, format='JPEG', quality=85, optimize=True)
                output.seek(0)

                tamaño_comprimido = len(output.getvalue())
                tamaño_total_comprimido += tamaño_comprimido

                nombre_archivo = f"egreso_{imagen.id}_{os.path.basename(imagen.imagen.name)}"
                if not nombre_archivo.lower().endswith('.jpg'):
                    nombre_archivo = os.path.splitext(nombre_archivo)[0] + '.jpg'

                imagenes_comprimidas.append({
                    'nombre': nombre_archivo,
                    'contenido': output.getvalue(),
                    'tamaño_comprimido': tamaño_comprimido,
                })
            except Exception as e:
                logger.warning(f"[IMAGENES-EGRESO] Error procesando imagen {imagen.id}: {e}")

        if not imagenes_comprimidas:
            raise Exception("No se pudo procesar ninguna imagen de egreso.")

        logger.info(
            f"[IMAGENES-EGRESO] Compresión: {tamaño_total_original/1024/1024:.2f} MB → "
            f"{tamaño_total_comprimido/1024/1024:.2f} MB"
        )

        # ===================================================================
        # PASO 3: PREPARAR HTML DEL CORREO
        # ===================================================================
        from config.paises_config import get_pais_actual, fecha_local_pais
        _pais_email = get_pais_actual()

        whatsapp_empleado = ''
        if usuario_id:
            User = get_user_model()
            try:
                usuario = User.objects.get(pk=usuario_id)
                if hasattr(usuario, 'empleado') and usuario.empleado:
                    numero_local = usuario.empleado.numero_whatsapp
                    if numero_local:
                        codigo_tel = _pais_email.get('codigo_telefonico', '')
                        whatsapp_empleado = f"{codigo_tel}{numero_local}"
            except User.DoesNotExist:
                pass

        ahora_local = fecha_local_pais(timezone.now(), _pais_email)

        context = {
            'orden': orden,
            'detalle': orden.detalle_equipo,
            'mensaje_personalizado': '',
            'fecha_envio_texto': ahora_local.strftime('%d/%m/%Y'),
            'hora_envio_texto': ahora_local.strftime('%H:%M'),
            'cantidad_imagenes': len(imagenes_comprimidas),
            'empresa_nombre': _pais_email['empresa_nombre_corto'],
            'pais_nombre': _pais_email['nombre'],
            'whatsapp_empleado': whatsapp_empleado,
        }

        html_content = render_to_string(
            'servicio_tecnico/emails/imagenes_egreso_cliente.html',
            context
        )

        # ===================================================================
        # PASO 4: CREAR Y ENVIAR EL CORREO
        # ===================================================================
        numero_orden_display = (
            orden.detalle_equipo.orden_cliente
            if orden.detalle_equipo.orden_cliente
            else orden.numero_orden_interno
        )
        asunto = f'📦 Fotografías de egreso - Orden {numero_orden_display}'

        email_match = re.search(r'<(.+?)>', settings.DEFAULT_FROM_EMAIL)
        email_solo = email_match.group(1) if email_match else settings.DEFAULT_FROM_EMAIL
        remitente = f"Servicio Técnico System <{email_solo}>"

        email_msg = EmailMessage(
            subject=asunto,
            body=html_content,
            from_email=remitente,
            to=[email_cliente],
            cc=destinatarios_copia if destinatarios_copia else None,
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
            logger.warning(f"[IMAGENES-EGRESO] Error al adjuntar logo: {e}")

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
            logger.warning(f"[IMAGENES-EGRESO] Error al adjuntar iconos: {e}")

        # Adjuntar imágenes de egreso comprimidas
        for img_data in imagenes_comprimidas:
            email_msg.attach(img_data['nombre'], img_data['contenido'], 'image/jpeg')

        email_msg.send(fail_silently=False)
        logger.info(f"[IMAGENES-EGRESO] Correo enviado a {email_cliente}")

        # ===================================================================
        # PASO 5: REGISTRAR EN HISTORIAL
        # ===================================================================
        try:
            usuario_empleado = None
            if usuario_id:
                User = get_user_model()
                try:
                    usuario = User.objects.get(pk=usuario_id)
                    if hasattr(usuario, 'empleado'):
                        usuario_empleado = usuario.empleado
                except User.DoesNotExist:
                    pass

            comentario = (
                f"📧 Imágenes de egreso enviadas al cliente (background) ({email_cliente})\n"
                f"📸 Cantidad de imágenes: {len(imagenes_comprimidas)}\n"
                f"📦 Tamaño total: {tamaño_total_comprimido/1024/1024:.2f} MB"
            )
            if destinatarios_copia:
                comentario += f"\n👥 Copia a: {', '.join(destinatarios_copia)}"

            HistorialOrden.objects.create(
                orden=orden,
                tipo_evento='email',
                comentario=comentario,
                usuario=usuario_empleado,
                es_sistema=False
            )
        except Exception as e:
            logger.warning(f"[IMAGENES-EGRESO] No se pudo registrar historial: {e}")

        logger.info(f"[IMAGENES-EGRESO] Tarea completada para Orden {orden.numero_orden_interno}")

        # ── Notificar éxito al usuario ──
        try:
            _usuario_notif = None
            if usuario_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    _usuario_notif = User.objects.get(pk=usuario_id)
                except User.DoesNotExist:
                    pass
            _oc = (
                orden.detalle_equipo.orden_cliente
                if orden.detalle_equipo and orden.detalle_equipo.orden_cliente
                else orden.numero_orden_interno
            )
            notificar_exito(
                titulo="Imágenes de egreso enviadas al cliente",
                mensaje=(
                    f"Orden {_oc}"
                    f" — "
                    f"{len(imagenes_comprimidas)} imagen(es) de egreso enviada(s) a {email_cliente}. "
                    f"Tamaño total: {tamaño_total_comprimido/1024/1024:.2f} MB."
                ),
                usuario=_usuario_notif,
                task_id=self.request.id,
                app_origen='servicio_tecnico',
            )
        except Exception as e:
            logger.warning(f"[IMAGENES-EGRESO] No se pudo crear notificación de éxito: {e}")

        return {
            'success': True,
            'orden': orden.numero_orden_interno,
            'destinatario': email_cliente,
            'imagenes_enviadas': len(imagenes_comprimidas),
            'tamaño_mb': round(tamaño_total_comprimido / 1024 / 1024, 2),
        }

    except Exception as exc:
        logger.error(f"[IMAGENES-EGRESO] Error para Orden ID {orden_id}: {exc}\n{traceback.format_exc()}")
        # ── Notificar error al usuario ──
        try:
            _usuario_err = None
            if usuario_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    _usuario_err = User.objects.get(pk=usuario_id)
                except User.DoesNotExist:
                    pass
            notificar_error(
                titulo="Error al enviar imágenes de egreso",
                mensaje=f"Orden {orden_id} — {str(exc)[:200]}",
                usuario=_usuario_err,
                task_id=self.request.id,
                app_origen='servicio_tecnico',
            )
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60)


# ============================================================================
# TAREA: enviar_feedback_satisfaccion_task
# Envía correo al cliente con link de encuesta de satisfacción después de
# que su equipo fue entregado y la cotización fue aceptada.
# ============================================================================

@shared_task(bind=True, max_retries=3, default_retry_delay=60, name='servicio_tecnico.enviar_feedback_satisfaccion')
def enviar_feedback_satisfaccion_task(self, feedback_id, usuario_id=None):
    """
    Envía correo al cliente con link de encuesta de satisfacción.
    Se dispara cuando una orden cambia a estado 'entregado' con cotización aceptada.
    """
    import re
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from django.utils import timezone
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.contrib.staticfiles import finders
    from email.mime.image import MIMEImage

    from .models import FeedbackCliente, HistorialOrden

    try:
        # ── Recuperar feedback ──
        try:
            feedback = FeedbackCliente.objects.select_related(
                'cotizacion__orden__detalle_equipo',
                'enviado_por',
            ).get(pk=feedback_id)
        except FeedbackCliente.DoesNotExist:
            return {'success': False, 'mensaje': f'FeedbackCliente ID {feedback_id} no encontrado.'}

        orden   = feedback.cotizacion.orden
        detalle = orden.detalle_equipo
        email_cliente = detalle.email_cliente if detalle else None

        if not email_cliente:
            return {'success': False, 'mensaje': 'Sin email de cliente.'}

        # ── Construir URL pública ──
        site_url     = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        feedback_url = f"{site_url}/feedback-satisfaccion/{feedback.token}/"

        # ── Datos del equipo ──
        marca_equipo  = detalle.marca         or ''
        modelo_equipo = detalle.modelo        or ''
        tipo_equipo   = detalle.tipo_equipo   or ''
        folio = (
            detalle.orden_cliente if detalle and detalle.orden_cliente
            else orden.numero_orden_interno
        )

        fecha_entrega_str = ''
        if orden.fecha_entrega:
            fecha_entrega_str = timezone.localtime(orden.fecha_entrega).strftime('%d/%m/%Y')

        # ── Contexto para el template de email ──
        ahora_local   = timezone.localtime(timezone.now())
        context_email = {
            'folio':         folio,
            'marca_equipo':  marca_equipo,
            'modelo_equipo': modelo_equipo,
            'tipo_equipo':   tipo_equipo,
            'fecha_entrega': fecha_entrega_str,
            'feedback_url':  feedback_url,
            'dias_vigencia': 7,
            'fecha_envio':   ahora_local.strftime('%d/%m/%Y'),
        }

        html_content = render_to_string(
            'servicio_tecnico/emails/feedback_satisfaccion.html',
            context_email
        )

        asunto      = f'¿Cómo fue tu experiencia? — Folio {folio}'
        email_match = re.search(r'<(.+?)>', settings.DEFAULT_FROM_EMAIL)
        email_solo  = email_match.group(1) if email_match else settings.DEFAULT_FROM_EMAIL
        remitente   = f"Servicio Técnico System <{email_solo}>"

        # ── CC a Jefe(s) de Calidad ──
        cc_list = []
        jefe_calidad_email   = getattr(settings, 'JEFE_CALIDAD_EMAIL',   None)
        jefe_calidad_2_email = getattr(settings, 'JEFE_CALIDAD_2_EMAIL', None)
        if jefe_calidad_email:
            cc_list.append(jefe_calidad_email)
        if jefe_calidad_2_email:
            cc_list.append(jefe_calidad_2_email)

        email_msg = EmailMessage(
            subject=asunto, body=html_content,
            from_email=remitente, to=[email_cliente], cc=cc_list,
        )
        email_msg.content_subtype = 'html'

        # ── Logo SIC (CID inline) ──
        try:
            logo_path = finders.find('images/logos/logo_sic.png')
            if logo_path:
                with open(logo_path, 'rb') as f:
                    logo_mime = MIMEImage(f.read(), _subtype='png')
                    logo_mime.add_header('Content-ID', '<logo_sic>')
                    logo_mime.add_header('Content-Disposition', 'inline', filename='logo_sic.png')
                    email_msg.attach(logo_mime)
        except Exception as e:
            logger.warning(f"[FEEDBACK-SATISFACCION] Error al adjuntar logo: {e}")

        # ── Iconos de redes sociales ──
        iconos_sociales = {
            'icon_link':      'images/utilitys/link.png',
            'icon_instagram': 'images/utilitys/instagram.png',
            'icon_facebook':  'images/utilitys/facebook.png',
            'icon_whatsapp':  'images/utilitys/whatsapp.png',
        }
        for cid_name, icon_static_path in iconos_sociales.items():
            icon_path = finders.find(icon_static_path)
            if icon_path:
                try:
                    with open(icon_path, 'rb') as f:
                        icon_mime = MIMEImage(f.read(), _subtype='png')
                        icon_mime.add_header('Content-ID', f'<{cid_name}>')
                        icon_mime.add_header('Content-Disposition', 'inline', filename=f'{cid_name}.png')
                        email_msg.attach(icon_mime)
                except Exception as e:
                    logger.warning(f"[FEEDBACK-SATISFACCION] Error al adjuntar icono {cid_name}: {e}")

        email_msg.send(fail_silently=False)

        # ── Marcar correo como enviado ──
        FeedbackCliente.objects.filter(pk=feedback_id).update(correo_enviado=True)

        # ── Registrar en historial ──
        HistorialOrden.objects.create(
            orden=orden,
            tipo_evento='email',
            comentario=(
                f"⭐ Encuesta de satisfacción enviada al cliente ({email_cliente})\n"
                f"🔗 Link válido por 7 días — Token ID: {feedback_id}"
            ),
            usuario=feedback.enviado_por,
            es_sistema=True
        )

        # ── Notificar éxito ──
        try:
            _usuario_notif = None
            if usuario_id:
                User = get_user_model()
                try:
                    _usuario_notif = User.objects.get(pk=usuario_id)
                except User.DoesNotExist:
                    pass
            notificar_exito(
                titulo="Encuesta de satisfacción enviada",
                mensaje=f"Orden {folio} — Encuesta de satisfacción enviada a {email_cliente}.",
                usuario=_usuario_notif,
                task_id=self.request.id,
                app_origen='servicio_tecnico',
            )
        except Exception as e:
            logger.warning(f"[FEEDBACK-SATISFACCION] No se pudo crear notificación: {e}")

        return {'success': True, 'feedback_id': feedback_id, 'destinatario': email_cliente}

    except Exception as exc:
        logger.error(f"[FEEDBACK-SATISFACCION] Error para FeedbackCliente ID {feedback_id}: {exc}\n{traceback.format_exc()}")
        try:
            _usuario_err = None
            if usuario_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    _usuario_err = User.objects.get(pk=usuario_id)
                except User.DoesNotExist:
                    pass
            notificar_error(
                titulo="Error al enviar encuesta de satisfacción",
                mensaje=f"FeedbackCliente ID {feedback_id} — {str(exc)[:200]}",
                usuario=_usuario_err,
                task_id=self.request.id,
                app_origen='servicio_tecnico',
            )
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60)
