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
from config.constants import FFMPEG_DRAWTEXT_FONT

logger = logging.getLogger('servicio_tecnico')


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,   # Reintentar tras 60 segundos si falla
    name='servicio_tecnico.enviar_correo_rhitso'
)
def enviar_correo_rhitso_task(self, orden_id, destinatarios_principales, copia_empleados, usuario_id=None, db_alias='default'):
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
            # Import diferido: evita ciclos al cargar tasks ↔ views
            from .services.historial import registrar_historial

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
def enviar_feedback_rechazo_task(self, feedback_id, usuario_id=None, db_alias='default'):
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
        from config.paises_config import get_pais_actual
        _pais = get_pais_actual()
        site_url = _pais.get('url_base', getattr(settings, 'SITE_URL', 'http://localhost:8000'))
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
def enviar_vigencia_vencida_task(self, orden_id, usuario_id=None, db_alias='default'):
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
    email_empleado, nombre_empleado, usuario_id=None, db_alias='default'
):
    """
    Tarea Celery: genera PDF de diagnóstico, comprime imágenes, guarda sugerencias
    de piezas, envía el correo al cliente, cambia estado y registra historial.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta tarea recibe SOLO tipos simples (int, str, list, dict).
    Dentro de la tarea recuperamos los objetos Django desde la BD usando los IDs.
    Ya NO crea Cotizacion ni PiezaCotizada en Servicio Técnico: las piezas marcadas
    se guardan como sugerencias en DetalleEquipo.piezas_sugeridas_diagnostico
    para que Almacén las vea al cotizar.

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
        db_alias              : Alias de BD del país activo (multi-tenant Celery)
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

    from .models import OrdenServicio, ImagenOrden

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
        # PASO 4: GUARDAR SUGERENCIAS DE PIEZAS (sin crear cotización ST)
        # ===================================================================
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # Antes este paso creaba Cotizacion + PiezaCotizada en Servicio Técnico.
        # Ahora Almacén cotiza las piezas, así que solo guardamos las marcadas
        # como "sugerencias" en el detalle del equipo. El PDF y el correo
        # siguen usando los mismos componentes (no cambia lo que ve el cliente).
        piezas_sugeridas = []
        componentes_seleccionados_nombres = []

        for comp in componentes_data:
            # Solo persistimos lo que el técnico dejó marcado en el modal
            if not comp.get('seleccionado', False):
                continue

            componente_nombre = (comp.get('componente_db') or '').strip()
            if not componente_nombre:
                continue

            piezas_sugeridas.append({
                'componente_db': componente_nombre,
                'dpn': (comp.get('dpn') or '').strip(),
                'es_necesaria': bool(comp.get('es_necesaria', True)),
            })
            componentes_seleccionados_nombres.append(componente_nombre)

        detalle.piezas_sugeridas_diagnostico = piezas_sugeridas
        detalle.save(update_fields=['piezas_sugeridas_diagnostico'])
        componentes_marcados = len(piezas_sugeridas)
        logger.info(
            f"[DIAGNOSTICO] Sugerencias de piezas guardadas: {componentes_marcados} "
            f"(sin crear Cotizacion/PiezaCotizada)"
        )

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

        # ── URL de seguimiento público (si existe para esta orden) ──
        seguimiento_url = None
        if orden.es_fuera_garantia:
            try:
                enlace = orden.enlace_seguimiento
                if enlace and enlace.activo:
                    site_url = _pais_email.get('url_base', getattr(settings, 'SITE_URL', 'http://localhost:8000'))
                    seguimiento_url = f"{site_url}/seguimiento/{enlace.token}/"
            except Exception:
                pass

        context_email = {
            'orden': orden,
            'detalle': detalle,
            'folio': folio,
            'mensaje_personalizado': mensaje_personalizado,
            'fecha_envio_texto': ahora_local.strftime('%d/%m/%Y'),
            'hora_envio_texto': ahora_local.strftime('%H:%M'),
            'cantidad_imagenes': len(imagenes_comprimidas),
            # Compatibilidad: el template de correo no lista piezas, pero mantenemos
            # estos nombres por si algún template los usa o se extiende después.
            'componentes_seleccionados': componentes_seleccionados_nombres,
            'piezas_creadas': componentes_marcados,
            'empresa_nombre': _pais_email['empresa_nombre_corto'],
            'pais_nombre': _pais_email['nombre'],
            'email_empleado': email_empleado,
            'nombre_empleado': nombre_empleado,
            'whatsapp_empleado': whatsapp_empleado,
            'seguimiento_url': seguimiento_url,
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
        # PASO 5b: GUARDAR PDF EN EL ENLACE PÚBLICO (para push y PWA)
        # ===================================================================
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # El PDF temporal se borra al final de la tarea. Si lo guardamos en el
        # enlace del cliente ANTES de cambiar el estado, el push automático
        # podrá incluir un link directo al diagnóstico.
        if orden.es_fuera_garantia:
            try:
                from django.core.files import File

                enlace = orden.enlace_seguimiento
                if enlace:
                    # Si ya había un PDF previo (reenvío), eliminar el archivo viejo
                    if enlace.pdf_diagnostico:
                        enlace.pdf_diagnostico.delete(save=False)

                    with open(resultado_pdf['ruta'], 'rb') as pdf_lectura:
                        enlace.pdf_diagnostico.save(
                            resultado_pdf['archivo'],
                            File(pdf_lectura),
                            save=False,
                        )
                    enlace.folio_diagnostico = folio
                    enlace.save(update_fields=['pdf_diagnostico', 'folio_diagnostico'])
                    logger.info(
                        f"[DIAGNOSTICO] PDF persistido en enlace de seguimiento "
                        f"(orden {orden.numero_orden_interno})"
                    )
            except Exception as exc:
                logger.warning(
                    f"[DIAGNOSTICO] No se pudo guardar PDF en enlace público: {exc}"
                )

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
            # Import diferido: evita ciclos al cargar tasks ↔ views
            from .services.historial import registrar_historial

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
                f"🔧 Componentes marcados (sugerencias Almacén): {componentes_marcados}\n"
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
                    f"{componentes_marcados} sugerencia(s) de pieza para Almacén, "
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
            'piezas_sugeridas': componentes_marcados,
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
    mensaje_personalizado, usuario_id=None,
    modelo_ia_inspeccion='', db_alias='default',
):
    """
    Tarea Celery: comprime imágenes de ingreso y las envía al cliente por correo.

    Parámetros:
        orden_id              : ID de la OrdenServicio
        imagenes_ids          : Lista de IDs de ImagenOrden (tipo 'ingreso')
        destinatarios_copia   : Lista de emails en CC
        mensaje_personalizado : Texto personalizado del usuario
        usuario_id            : ID del usuario que disparó la acción
        modelo_ia_inspeccion  : Modelo IA seleccionado en el modal (vacío = automático)
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
        # PASO 2.5: ANÁLISIS DE CONDICIÓN ESTÉTICA CON IA (no crítico)
        # ===================================================================
        # Se invoca ANTES de preparar el HTML del correo para poder incluir
        # el análisis en el contexto del template.
        #
        # DISEÑO FAIL-SAFE:
        #   - Si la IA responde → análisis se guarda en historial + va en el correo
        #   - Si falla por cualquier motivo → analisis_ia_texto queda None
        #     y el template simplemente omite la sección (el correo se envía igual)
        #
        # TIMEOUT: usa OLLAMA_VISION_TIMEOUT (default 600s) que cubre el tiempo
        # en cola de Ollama + el tiempo de inferencia con múltiples imágenes.
        # Celery maneja esto en background — no hay riesgo de timeout HTTP.
        analisis_ia_texto = None
        analisis_ia_modelo = None

        try:
            from .ollama_client import analizar_imagenes_ingreso_dispatch

            max_imgs = getattr(settings, 'OLLAMA_MAX_IMAGENES_IA', 8)
            # Reutilizar los bytes ya comprimidos por Pillow — sin releer disco
            imagenes_bytes_ia = [
                img_data['contenido']
                for img_data in imagenes_comprimidas[:max_imgs]
            ]

            detalle = orden.detalle_equipo
            resultado_ia = analizar_imagenes_ingreso_dispatch(
                imagenes_bytes=imagenes_bytes_ia,
                tipo_equipo=detalle.tipo_equipo if detalle else '',
                marca=detalle.marca if detalle else '',
                modelo_equipo=detalle.modelo if detalle else '',
                modelo_override=modelo_ia_inspeccion,
            )

            if resultado_ia.get('success'):
                analisis_ia_texto = resultado_ia['analisis']
                analisis_ia_modelo = resultado_ia['modelo_usado']

                logger.info(
                    f"[IMAGENES] Análisis IA completado | "
                    f"{len(analisis_ia_texto)} chars | Modelo: {analisis_ia_modelo}"
                )

                # Persistir el análisis en el historial de la orden
                HistorialOrden.objects.create(
                    orden=orden,
                    tipo_evento='inspeccion_ia',
                    comentario=(
                        f"🤖 Inspección visual automatizada — {analisis_ia_modelo}\n\n"
                        f"{analisis_ia_texto}"
                    ),
                    es_sistema=True,
                )
            else:
                logger.warning(
                    f"[IMAGENES] Análisis IA no disponible (no crítico): "
                    f"{resultado_ia.get('error', 'Sin detalles')} — "
                    f"El correo se enviará sin sección de análisis."
                )

        except Exception as e_ia:
            # Captura cualquier error inesperado del módulo de IA.
            # El flujo principal no se interrumpe bajo ninguna circunstancia.
            logger.warning(
                f"[IMAGENES] Excepción en análisis IA (no crítico, ignorando): "
                f"{type(e_ia).__name__}: {e_ia}"
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

        # ── URL de seguimiento público (si existe para esta orden) ──
        seguimiento_url = None
        if orden.es_fuera_garantia:
            try:
                enlace = orden.enlace_seguimiento
                if enlace and enlace.activo:
                    site_url = _pais_email.get('url_base', getattr(settings, 'SITE_URL', 'http://localhost:8000'))
                    seguimiento_url = f"{site_url}/seguimiento/{enlace.token}/"
            except Exception:
                pass

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
            'seguimiento_url': seguimiento_url,
            # Análisis de condición estética generado por IA.
            # Si la IA no estuvo disponible, ambos quedan en None y el
            # template omite la sección automáticamente con {% if analisis_ia_texto %}
            'analisis_ia_texto': analisis_ia_texto,
            'analisis_ia_modelo': analisis_ia_modelo,
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
    self, orden_id, destinatarios_copia, usuario_id=None, db_alias='default'
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

        # ── URL de seguimiento público (si existe para esta orden) ──
        seguimiento_url = None
        if orden.es_fuera_garantia:
            try:
                enlace = orden.enlace_seguimiento
                if enlace and enlace.activo:
                    site_url = _pais_email.get('url_base', getattr(settings, 'SITE_URL', 'http://localhost:8000'))
                    seguimiento_url = f"{site_url}/seguimiento/{enlace.token}/"
            except Exception:
                pass

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
            'seguimiento_url': seguimiento_url,
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
def enviar_feedback_satisfaccion_task(self, feedback_id, usuario_id=None, db_alias='default'):
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
                'orden__detalle_equipo',
                'enviado_por',
            ).get(pk=feedback_id)
        except FeedbackCliente.DoesNotExist:
            return {'success': False, 'mensaje': f'FeedbackCliente ID {feedback_id} no encontrado.'}

        orden   = feedback.orden
        detalle = orden.detalle_equipo
        email_cliente = detalle.email_cliente if detalle else None

        if not email_cliente:
            return {'success': False, 'mensaje': 'Sin email de cliente.'}

        # ── Construir URL pública ──
        from config.paises_config import get_pais_actual
        _pais = get_pais_actual()
        site_url     = _pais.get('url_base', getattr(settings, 'SITE_URL', 'http://localhost:8000'))
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
            'dias_vigencia': 12,
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
                f"🔗 Link válido por 12 días — Token ID: {feedback_id}"
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


# ═══════════════════════════════════════════════════════════════════════
# TAREA: Recordatorio de encuesta de satisfacción (día 10)
# ═══════════════════════════════════════════════════════════════════════
# Se dispara automáticamente para encuestas que llevan 10 días sin
# respuesta. Reutiliza el mismo template de email del envío inicial
# pero con asunto diferente para indicar que es un recordatorio.

@shared_task(bind=True, max_retries=3, default_retry_delay=60, name='servicio_tecnico.enviar_recordatorio_encuesta')
def enviar_recordatorio_encuesta_task(self, feedback_id, db_alias='default'):
    """
    Envía un correo de recordatorio al cliente para que conteste
    la encuesta de satisfacción antes de que expire (día 10 de 12).
    """
    import re
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from django.utils import timezone
    from django.conf import settings
    from django.contrib.staticfiles import finders
    from email.mime.image import MIMEImage

    from .models import FeedbackCliente, HistorialOrden

    try:
        try:
            feedback = FeedbackCliente.objects.select_related(
                'orden__detalle_equipo',
                'enviado_por',
            ).get(pk=feedback_id)
        except FeedbackCliente.DoesNotExist:
            return {'success': False, 'mensaje': f'FeedbackCliente ID {feedback_id} no encontrado.'}

        # Doble verificación: no enviar si ya respondió o el recordatorio ya fue enviado
        if feedback.utilizado:
            return {'success': False, 'mensaje': 'El cliente ya respondió la encuesta.'}
        if feedback.recordatorio_enviado:
            return {'success': False, 'mensaje': 'Recordatorio ya enviado previamente.'}

        orden   = feedback.orden
        detalle = orden.detalle_equipo
        email_cliente = detalle.email_cliente if detalle else None

        if not email_cliente:
            return {'success': False, 'mensaje': 'Sin email de cliente.'}

        # ── Construir URL y datos del equipo ──
        from config.paises_config import get_pais_actual
        _pais = get_pais_actual()
        site_url     = _pais.get('url_base', getattr(settings, 'SITE_URL', 'http://localhost:8000'))
        feedback_url = f"{site_url}/feedback-satisfaccion/{feedback.token}/"

        marca_equipo  = detalle.marca       or ''
        modelo_equipo = detalle.modelo      or ''
        tipo_equipo   = detalle.tipo_equipo or ''
        folio = (
            detalle.orden_cliente if detalle and detalle.orden_cliente
            else orden.numero_orden_interno
        )

        fecha_entrega_str = ''
        if orden.fecha_entrega:
            fecha_entrega_str = timezone.localtime(orden.fecha_entrega).strftime('%d/%m/%Y')

        ahora_local = timezone.localtime(timezone.now())

        # ── Contexto: reutilizamos el mismo template con dias_vigencia ajustado ──
        context_email = {
            'folio':            folio,
            'marca_equipo':     marca_equipo,
            'modelo_equipo':    modelo_equipo,
            'tipo_equipo':      tipo_equipo,
            'fecha_entrega':    fecha_entrega_str,
            'feedback_url':     feedback_url,
            'dias_vigencia':    feedback.dias_restantes,  # Días que quedan realmente
            'fecha_envio':      ahora_local.strftime('%d/%m/%Y'),
            'es_recordatorio':  True,  # Flag para personalizar el template si se desea
        }

        html_content = render_to_string(
            'servicio_tecnico/emails/feedback_satisfaccion.html',
            context_email
        )

        asunto      = f'Recordatorio: ¿Cómo fue tu experiencia? — Folio {folio}'
        email_match = re.search(r'<(.+?)>', settings.DEFAULT_FROM_EMAIL)
        email_solo  = email_match.group(1) if email_match else settings.DEFAULT_FROM_EMAIL
        remitente   = f"Servicio Técnico System <{email_solo}>"

        email_msg = EmailMessage(
            subject=asunto, body=html_content,
            from_email=remitente, to=[email_cliente],
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
            logger.warning(f"[RECORDATORIO-ENCUESTA] Error al adjuntar logo: {e}")

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
                    logger.warning(f"[RECORDATORIO-ENCUESTA] Error al adjuntar icono {cid_name}: {e}")

        email_msg.send(fail_silently=False)

        # ── Marcar recordatorio como enviado ──
        FeedbackCliente.objects.filter(pk=feedback_id).update(recordatorio_enviado=True)

        # ── Registrar en historial ──
        HistorialOrden.objects.create(
            orden=orden,
            tipo_evento='email',
            comentario=(
                f"🔔 Recordatorio de encuesta de satisfacción enviado al cliente ({email_cliente})\n"
                f"⏳ Quedan {feedback.dias_restantes} día(s) — Token ID: {feedback_id}"
            ),
            usuario=feedback.enviado_por,
            es_sistema=True,
        )

        logger.info(f"[RECORDATORIO-ENCUESTA] Enviado a {email_cliente} para Orden {folio}")
        return {'success': True, 'feedback_id': feedback_id, 'destinatario': email_cliente}

    except Exception as exc:
        logger.error(f"[RECORDATORIO-ENCUESTA] Error para FeedbackCliente ID {feedback_id}: {exc}\n{traceback.format_exc()}")
        raise self.retry(exc=exc, countdown=60)


# ═══════════════════════════════════════════════════════════════════════
# TAREA PERIÓDICA: Verificar encuestas de satisfacción pendientes de recordatorio
# ═══════════════════════════════════════════════════════════════════════
# Celery Beat la ejecuta diariamente a las 8:00 AM.
# Busca encuestas que:
#   - son de tipo 'satisfaccion'
#   - el correo inicial fue enviado (correo_enviado=True)
#   - no han sido respondidas (utilizado=False)
#   - llevan ≥10 días sin respuesta
#   - aún no han expirado (≤12 días)
#   - no se les ha enviado recordatorio (recordatorio_enviado=False)

@shared_task(name='servicio_tecnico.verificar_encuestas_pendientes')
def verificar_encuestas_pendientes_task():
    """
    Tarea periódica diaria (Celery Beat) que detecta encuestas de satisfacción
    que llevan 10+ días sin respuesta y dispara el recordatorio por correo.

    MULTI-PAÍS: Itera sobre TODOS los países configurados para no omitir
    encuestas de ninguna base de datos. Pasa db_alias a cada recordatorio
    para que Celery use la BD correcta al ejecutarlo.
    """
    from datetime import timedelta
    from django.utils import timezone
    from config.paises_config import PAISES_CONFIG
    from .models import FeedbackCliente

    ahora = timezone.now()

    # Ventana: entre día 10 y día 12 desde la creación del feedback
    limite_inferior = ahora - timedelta(days=12)  # No expiradas aún
    limite_superior = ahora - timedelta(days=10)  # Al menos 10 días de antigüedad

    total_global = 0

    # Iterar sobre cada país para revisar su BD independiente
    for subdominio, pais_config in PAISES_CONFIG.items():
        db_alias = pais_config['db_alias']

        pendientes = FeedbackCliente.objects.using(db_alias).filter(
            tipo='satisfaccion',
            correo_enviado=True,
            utilizado=False,
            recordatorio_enviado=False,
            fecha_creacion__lte=limite_superior,
            fecha_creacion__gte=limite_inferior,
        )

        total = pendientes.count()
        logger.info(f"[VERIFICAR-ENCUESTAS] [{subdominio}] Encontradas {total} encuesta(s) para recordatorio.")

        for feedback in pendientes:
            try:
                # Pasar db_alias para que la señal task_prerun configure el contexto correcto
                enviar_recordatorio_encuesta_task.delay(feedback_id=feedback.pk, db_alias=db_alias)
                logger.info(
                    f"[VERIFICAR-ENCUESTAS] [{subdominio}] Recordatorio encolado para "
                    f"FeedbackCliente ID {feedback.pk} (Orden {feedback.orden.numero_orden_interno})"
                )
            except Exception as e:
                logger.error(f"[VERIFICAR-ENCUESTAS] [{subdominio}] Error al encolar feedback ID {feedback.pk}: {e}")

        total_global += total

    return {'procesadas': total_global}


# ═══════════════════════════════════════════════════════════════════════
# TAREAS: Recordatorios de imágenes faltantes (push + campanita)
# ═══════════════════════════════════════════════════════════════════════
# Disparadores:
# 1) Inmediato (señal): al pasar a 'finalizado' → técnico + egreso inspector.
# 2) Celery Beat diario 8:00: ingreso inspector (≥2 días) + pendientes que
#    siguen en finalizado (técnico / egreso inspector).


@shared_task(bind=True, max_retries=3, default_retry_delay=60, name='servicio_tecnico.enviar_recordatorio_imagen')
def enviar_recordatorio_imagen_task(self, orden_id, tipo_recordatorio, db_alias='default'):
    """
    Envía push y campanita de recordatorio por imágenes pendientes en una orden.

    Parámetros:
        orden_id: PK de OrdenServicio.
        tipo_recordatorio: 'ingreso_inspector', 'egreso_inspector' o 'tecnico_faltantes'.
        db_alias: Alias de BD del país (configurado por task_prerun).

    Efectos secundarios:
        - Notifica inspectores o técnico según el tipo.
        - Actualiza RecordatorioImagenOrden.
        - Registra evento en HistorialOrden.
    """
    from django.urls import reverse

    from inventario.models import Empleado
    from notificaciones.push_service import enviar_push_a_usuario
    from notificaciones.utils import notificar_warning

    from .models import HistorialOrden, OrdenServicio
    from .utils_recordatorio_imagenes import (
        construir_mensaje_recordatorio_egreso_inspector,
        construir_mensaje_recordatorio_ingreso_inspector,
        construir_mensaje_recordatorio_tecnico,
        obtener_etiqueta_orden,
        orden_requiere_recordatorio_egreso_inspector,
        orden_requiere_recordatorio_ingreso_inspector,
        orden_requiere_recordatorio_tecnico,
        registrar_envio_recordatorio,
        debe_recordar_hoy,
    )

    try:
        orden = OrdenServicio.objects.select_related(
            'tecnico_asignado_actual__user',
            'detalle_equipo',
            'cotizacion',
        ).get(pk=orden_id)
    except OrdenServicio.DoesNotExist:
        return {'success': False, 'mensaje': f'Orden ID {orden_id} no encontrada.'}

    if not debe_recordar_hoy(orden, tipo_recordatorio, db_alias):
        return {'success': False, 'mensaje': 'Recordatorio ya enviado hoy.'}

    url_orden = reverse('servicio_tecnico:detalle_orden', kwargs={'orden_id': orden.pk})
    etiqueta = obtener_etiqueta_orden(orden)
    destinatarios_notificados = 0

    # ── Inspectores: ingreso (≥2 días) o egreso (orden en finalizado) ──
    if tipo_recordatorio in ('ingreso_inspector', 'egreso_inspector'):
        if tipo_recordatorio == 'ingreso_inspector':
            if not orden_requiere_recordatorio_ingreso_inspector(orden):
                return {'success': False, 'mensaje': 'La orden ya no requiere recordatorio de ingreso.'}
            titulo, mensaje = construir_mensaje_recordatorio_ingreso_inspector(orden)
            tipo_foto_historial = 'ingreso'
        else:
            if not orden_requiere_recordatorio_egreso_inspector(orden):
                return {'success': False, 'mensaje': 'La orden ya no requiere recordatorio de egreso.'}
            titulo, mensaje = construir_mensaje_recordatorio_egreso_inspector(orden)
            tipo_foto_historial = 'egreso'

        # Broadcast a todos los inspectores activos (mismo patrón que ingreso)
        inspectores = Empleado.objects.filter(
            rol='inspector',
            user__is_active=True,
        ).select_related('user')

        for inspector in inspectores:
            try:
                enviar_push_a_usuario(
                    usuario=inspector.user,
                    titulo=titulo,
                    mensaje=mensaje,
                    url=url_orden,
                )
                notificar_warning(
                    titulo=titulo,
                    mensaje=mensaje,
                    usuario=inspector.user,
                    app_origen='servicio_tecnico',
                    url=url_orden,
                )
                destinatarios_notificados += 1
            except Exception as exc_push:
                logger.warning(
                    f'[RECORDATORIO-IMAGEN] Error notificando inspector '
                    f'{inspector.pk} orden {orden_id}: {exc_push}'
                )

        comentario_historial = (
            f'🔔 Recordatorio de fotos de {tipo_foto_historial} enviado a '
            f'{destinatarios_notificados} inspector(es) — Orden {etiqueta}'
        )

    elif tipo_recordatorio == 'tecnico_faltantes':
        if not orden_requiere_recordatorio_tecnico(orden):
            return {'success': False, 'mensaje': 'La orden ya no requiere recordatorio al técnico.'}

        tecnico = orden.tecnico_asignado_actual
        titulo, mensaje = construir_mensaje_recordatorio_tecnico(orden)

        try:
            enviar_push_a_usuario(
                usuario=tecnico.user,
                titulo=titulo,
                mensaje=mensaje,
                url=url_orden,
            )
            notificar_warning(
                titulo=titulo,
                mensaje=mensaje,
                usuario=tecnico.user,
                app_origen='servicio_tecnico',
                url=url_orden,
            )
            destinatarios_notificados = 1
        except Exception as exc_push:
            logger.warning(
                f'[RECORDATORIO-IMAGEN] Error notificando técnico orden {orden_id}: {exc_push}'
            )
            raise self.retry(exc=exc_push, countdown=60)

        comentario_historial = (
            f'🔔 Recordatorio de fotos pendientes enviado al técnico '
            f'{tecnico.nombre_completo} — Orden {etiqueta}'
        )

    else:
        return {'success': False, 'mensaje': f'Tipo de recordatorio inválido: {tipo_recordatorio}'}

    if destinatarios_notificados == 0:
        return {'success': False, 'mensaje': 'No se pudo notificar a ningún destinatario.'}

    registrar_envio_recordatorio(orden, tipo_recordatorio, db_alias)

    HistorialOrden.objects.create(
        orden=orden,
        tipo_evento='sistema',
        comentario=comentario_historial,
        es_sistema=True,
    )

    logger.info(
        f'[RECORDATORIO-IMAGEN] [{db_alias}] {tipo_recordatorio} orden {orden_id} '
        f'→ {destinatarios_notificados} destinatario(s)'
    )
    return {
        'success': True,
        'orden_id': orden_id,
        'tipo_recordatorio': tipo_recordatorio,
        'destinatarios': destinatarios_notificados,
    }


@shared_task(name='servicio_tecnico.verificar_recordatorios_imagenes')
def verificar_recordatorios_imagenes_task():
    """
    Tarea periódica diaria (Celery Beat) que detecta órdenes con fotos faltantes
    y encola recordatorios push/campanita para inspectores y técnicos.

    Casos:
        - Ingreso inspector: sin fotos de ingreso tras 2 días.
        - Egreso inspector: en finalizado sin fotos de egreso.
        - Técnico: en finalizado con diag/rep faltantes según cotización.

    MULTI-PAÍS: Itera PAISES_CONFIG y pasa db_alias a cada tarea hija.
    """
    from config.paises_config import PAISES_CONFIG

    from .utils_recordatorio_imagenes import (
        ordenes_pendientes_egreso_inspector,
        ordenes_pendientes_ingreso_inspector,
        ordenes_pendientes_tecnico,
    )

    total_global = 0

    for subdominio, pais_config in PAISES_CONFIG.items():
        db_alias = pais_config['db_alias']
        encoladas_pais = 0

        # 1) Ingreso faltante tras 2 días → inspectores
        for orden in ordenes_pendientes_ingreso_inspector(db_alias):
            try:
                enviar_recordatorio_imagen_task.delay(
                    orden_id=orden.pk,
                    tipo_recordatorio='ingreso_inspector',
                    db_alias=db_alias,
                )
                encoladas_pais += 1
            except Exception as exc:
                logger.error(
                    f'[VERIFICAR-RECORDATORIO-IMAGEN] [{subdominio}] '
                    f'Error al encolar ingreso inspector orden {orden.pk}: {exc}'
                )

        # 2) Egreso faltante en finalizado → inspectores (repetición diaria)
        for orden in ordenes_pendientes_egreso_inspector(db_alias):
            try:
                enviar_recordatorio_imagen_task.delay(
                    orden_id=orden.pk,
                    tipo_recordatorio='egreso_inspector',
                    db_alias=db_alias,
                )
                encoladas_pais += 1
            except Exception as exc:
                logger.error(
                    f'[VERIFICAR-RECORDATORIO-IMAGEN] [{subdominio}] '
                    f'Error al encolar egreso inspector orden {orden.pk}: {exc}'
                )

        # 3) Evidencias técnico en finalizado (según cotización / VM)
        for orden in ordenes_pendientes_tecnico(db_alias):
            try:
                enviar_recordatorio_imagen_task.delay(
                    orden_id=orden.pk,
                    tipo_recordatorio='tecnico_faltantes',
                    db_alias=db_alias,
                )
                encoladas_pais += 1
            except Exception as exc:
                logger.error(
                    f'[VERIFICAR-RECORDATORIO-IMAGEN] [{subdominio}] '
                    f'Error al encolar técnico orden {orden.pk}: {exc}'
                )

        logger.info(
            f'[VERIFICAR-RECORDATORIO-IMAGEN] [{subdominio}] '
            f'{encoladas_pais} recordatorio(s) encolado(s).'
        )
        total_global += encoladas_pais

    return {'procesadas': total_global}


# ═══════════════════════════════════════════════════════════════════════
# TAREA: Enviar enlace de seguimiento público al cliente
# ═══════════════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=3, default_retry_delay=60, name='servicio_tecnico.enviar_seguimiento_cliente')
def enviar_seguimiento_cliente_task(self, orden_id, usuario_id=None, db_alias='default'):
    """
    Envía correo al cliente con link de seguimiento público de su orden.
    Solo se dispara para órdenes fuera de garantía (es_fuera_garantia=True).
    Se invoca al crear la orden (si hay email), con fallback al enviar imágenes de ingreso.
    """
    import re
    import secrets
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from django.utils import timezone
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.contrib.staticfiles import finders
    from email.mime.image import MIMEImage

    from .models import OrdenServicio, EnlaceSeguimientoCliente, HistorialOrden

    try:
        # ── Recuperar orden ──
        try:
            orden = OrdenServicio.objects.select_related(
                'detalle_equipo',
                'responsable_seguimiento',
            ).get(pk=orden_id)
        except OrdenServicio.DoesNotExist:
            return {'success': False, 'mensaje': f'OrdenServicio ID {orden_id} no encontrada.'}

        # ── Validar que sea fuera de garantía ──
        if not orden.es_fuera_garantia:
            return {'success': False, 'mensaje': 'La orden no es fuera de garantía. No se envía seguimiento.'}

        detalle = orden.detalle_equipo
        email_cliente = detalle.email_cliente if detalle else None

        if not email_cliente:
            return {'success': False, 'mensaje': 'Sin email de cliente en los datos del equipo.'}

        # ── Obtener o crear enlace de seguimiento ──
        enlace, created = EnlaceSeguimientoCliente.objects.get_or_create(
            orden=orden,
            defaults={'token': secrets.token_urlsafe(32)},
        )

        if enlace.correo_enviado and not created:
            return {'success': False, 'mensaje': 'El correo de seguimiento ya fue enviado previamente.'}

        # ── Datos del equipo y responsable ──
        # Usar la url_base del país activo para que el enlace apunte al subdominio correcto
        # (ej: chile.sigmasystem.work en vez de siempre mexico). get_pais_actual() funciona
        # en este contexto Celery porque task_prerun ya configuró los thread-locals con db_alias.
        from config.paises_config import get_pais_actual
        _pais = get_pais_actual()
        site_url = _pais.get('url_base', getattr(settings, 'SITE_URL', 'http://localhost:8000'))
        seguimiento_url = f"{site_url}/seguimiento/{enlace.token}/"

        marca_equipo = detalle.marca or ''
        modelo_equipo = detalle.modelo or ''
        tipo_equipo = detalle.tipo_equipo or ''
        folio = detalle.orden_cliente if detalle and detalle.orden_cliente else orden.numero_orden_interno

        responsable = orden.responsable_seguimiento
        nombre_responsable = responsable.nombre_completo if responsable else None
        email_responsable = responsable.email if responsable else None

        ahora_local = timezone.localtime(timezone.now())

        # ── Contexto para el template de email ──
        context_email = {
            'folio': folio,
            'marca_equipo': marca_equipo,
            'modelo_equipo': modelo_equipo,
            'tipo_equipo': tipo_equipo,
            'seguimiento_url': seguimiento_url,
            'nombre_responsable': nombre_responsable,
            'email_responsable': email_responsable,
            'fecha_envio': ahora_local.strftime('%d/%m/%Y'),
        }

        html_content = render_to_string(
            'servicio_tecnico/emails/seguimiento_cliente.html',
            context_email,
        )

        asunto = f'Seguimiento de tu equipo — Folio {folio}'
        email_match = re.search(r'<(.+?)>', settings.DEFAULT_FROM_EMAIL)
        email_solo = email_match.group(1) if email_match else settings.DEFAULT_FROM_EMAIL
        remitente = f"Servicio Técnico System <{email_solo}>"

        email_msg = EmailMessage(
            subject=asunto,
            body=html_content,
            from_email=remitente,
            to=[email_cliente],
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
            logger.warning(f"[SEGUIMIENTO-CLIENTE] Error al adjuntar logo: {e}")

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
                    logger.warning(f"[SEGUIMIENTO-CLIENTE] Error al adjuntar icono {cid_name}: {e}")

        email_msg.send(fail_silently=False)

        # ── Marcar correo como enviado ──
        EnlaceSeguimientoCliente.objects.filter(pk=enlace.pk).update(correo_enviado=True)

        # ── Recuperar usuario y empleado ──
        usuario_obj = None
        usuario_empleado = None
        if usuario_id:
            User = get_user_model()
            try:
                usuario_obj = User.objects.get(pk=usuario_id)
                if hasattr(usuario_obj, 'empleado'):
                    usuario_empleado = usuario_obj.empleado
            except User.DoesNotExist:
                pass

        # ── Registrar en historial (usuario debe ser Empleado) ──
        HistorialOrden.objects.create(
            orden=orden,
            tipo_evento='email',
            comentario=(
                f"🔗 Enlace de seguimiento público enviado al cliente ({email_cliente})\n"
                f"📦 URL: {seguimiento_url}"
            ),
            usuario=usuario_empleado,
            es_sistema=True,
        )

        # ── Notificar éxito ──
        try:
            notificar_exito(
                titulo="Enlace de seguimiento enviado",
                mensaje=f"Orden {folio} — Enlace de seguimiento enviado a {email_cliente}.",
                usuario=usuario_obj,
                task_id=self.request.id,
                app_origen='servicio_tecnico',
            )
        except Exception as e:
            logger.warning(f"[SEGUIMIENTO-CLIENTE] No se pudo crear notificación: {e}")

        return {'success': True, 'orden_id': orden_id, 'destinatario': email_cliente}

    except Exception as exc:
        logger.error(f"[SEGUIMIENTO-CLIENTE] Error para OrdenServicio ID {orden_id}: {exc}\n{traceback.format_exc()}")
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
                titulo="Error al enviar enlace de seguimiento",
                 mensaje=f"OrdenServicio ID {orden_id} — {str(exc)[:200]}",
                 usuario=_usuario_err,
                 task_id=self.request.id,
                 app_origen='servicio_tecnico',
             )
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60)


# ============================================================================
# TAREA: GENERAR VIDEO RESUMEN DE GALERÍA (Ken Burns + Xfade + Música)
# ============================================================================

@shared_task(
    bind=True,
    max_retries=1,                # Solo 1 reintento (el proceso es muy pesado)
    default_retry_delay=30,
    soft_time_limit=900,          # 15 minutos — override del global de 5 min
    time_limit=1200,              # 20 minutos — override del global de 10 min
    name='servicio_tecnico.generar_video_resumen',
)
def generar_video_resumen_task(self, orden_id, usuario_id, db_alias='default'):
    """
    Tarea Celery: genera un video resumen tipo presentación con todas las fotos
    de la galería (ingreso, diagnóstico, reparación, egreso) de una orden.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta tarea usa FFmpeg para:
    1. Tomar cada foto de la galería (tipos principales: ingreso, diagnóstico,
       reparación, egreso)
    2. Aplicar efecto Ken Burns a cada foto (zoom + paneo suave cinematográfico)
    3. Añadir transiciones "fade" entre cada foto con el filtro xfade
    4. Agregar música de fondo en loop
    5. Añadir texto de cierre "Gracias por su preferencia, vuelva pronto"
    6. Guardar el resultado como VideoOrden(tipo='resumen')
    7. Notificar al usuario cuando termina

    Parámetros:
        self       : Referencia a la tarea Celery (bind=True)
        orden_id   : ID de la OrdenServicio
        usuario_id : ID del usuario que solicitó la generación

    Returns:
        dict: {'success': True, 'video_id': int, 'orden_id': int}

    Nota de rendimiento:
        El efecto zoompan de FFmpeg es computacionalmente intensivo.
        Con 10 fotos: ~2-4 minutos. Con 20 fotos: ~4-8 minutos.
        Por eso esta tarea tiene límites de tiempo extendidos (15/20 min).
    """
    import os
    import shutil
    import subprocess
    import tempfile
    import traceback
    import time
    from pathlib import Path

    from django.contrib.auth import get_user_model
    from django.contrib.staticfiles import finders
    from django.core.files import File
    from django.core.files.base import ContentFile

    from .models import OrdenServicio, VideoOrden, ImagenOrden, HistorialOrden

    logger.info(f"[VIDEO-RESUMEN] Iniciando tarea para Orden ID {orden_id}")

    # =========================================================================
    # CONSTANTES DEL VIDEO
    # =========================================================================
    # Duración de cada foto en segundos (antes del fade)
    DURACION_FOTO = 4
    # Duración de la transición xfade entre fotos (segundos)
    DURACION_FADE = 1
    # Resolución de salida del video
    RESOLUCION = '1280x720'
    # Texto de cierre que aparece al final
    TEXTO_CIERRE = "Gracias por su preferencia, vuelva pronto"
    # Duración de la pantalla de cierre con el texto (segundos)
    DURACION_CIERRE = 4
    # Tipos de foto que se incluyen en el video (en orden del flujo de trabajo)
    # NOTA: Esta lista es para diagnóstico (4 tipos). Venta mostrador usa 3 (sin diagnóstico).
    # La lista activa se calcula como TIPOS_FOTO_ACTIVOS después de cargar la orden.
    TIPOS_FOTO = ['ingreso', 'diagnostico', 'reparacion', 'egreso']
    # Duración de la pantalla de intro del rewind (logo + datos del equipo)
    DURACION_INTRO = 4
    # Duración de cada tarjeta de sección en el rewind (fondo azul + texto)
    DURACION_SECCION = 2
    # Textos para las tarjetas de sección del rewind (diagnóstico — 4 tipos)
    TEXTO_SECCIONES = {
        'ingreso':     'Así ingresó tu equipo',
        'diagnostico': 'Fue diagnosticado minuciosamente',
        'reparacion':  'Así se reparó',
        'egreso':      'Tu equipo ahora...',
    }
    # Textos para venta mostrador (3 tipos, sin diagnóstico)
    TEXTO_SECCIONES_VM = {
        'ingreso':    'Así llegó tu equipo',
        'reparacion': 'Así se realizó el servicio',
        'egreso':     'Tu equipo ahora...',
    }

    # =========================================================================
    # HELPER: ESCAPADO DE TEXTO PARA DRAWTEXT
    # =========================================================================
    def _escape_ffmpeg_text(text: str) -> str:
        """
        Escapa caracteres especiales para el filtro drawtext de FFmpeg.

        EXPLICACIÓN PARA PRINCIPIANTES:
        El filtro drawtext de FFmpeg tiene su propio lenguaje de escape.
        Si el texto contiene apóstrofes, dos puntos o barras invertidas,
        FFmpeg los interpreta como parte de la sintaxis del filtro y falla.
        Esta función los escapa para que FFmpeg los trate como texto literal.
        """
        if not text:
            return ''
        text = text.replace('\\', '\\\\')  # \ → \\ (debe ir primero)
        text = text.replace("'", "\\'")    # ' → \'
        text = text.replace(':', '\\:')    # : → \: (separa opciones en FFmpeg)
        text = text.replace('%', '%%')     # % → %% (expansión de variables drawtext)
        return text

    # =========================================================================
    # PATHS TEMPORALES Y DE TRABAJO
    # =========================================================================
    ffmpeg_bin = shutil.which('ffmpeg') or '/usr/bin/ffmpeg'
    tmp_dir = tempfile.mkdtemp(prefix='video_resumen_')
    tmp_video_out = os.path.join(tmp_dir, 'resumen_final.mp4')
    tmp_thumb = os.path.join(tmp_dir, 'resumen_thumb.jpg')
    timestamp = int(time.time() * 1000)

    try:
        # =====================================================================
        # PASO 1: OBTENER ORDEN Y USUARIO
        # =====================================================================
        try:
            orden = OrdenServicio.objects.select_related(
                'detalle_equipo'
            ).get(pk=orden_id)
        except OrdenServicio.DoesNotExist:
            raise ValueError(f"OrdenServicio ID {orden_id} no encontrada")

        User = get_user_model()
        usuario_obj = None
        empleado_obj = None
        if usuario_id:
            try:
                usuario_obj = User.objects.get(pk=usuario_id)
                if hasattr(usuario_obj, 'empleado'):
                    empleado_obj = usuario_obj.empleado
            except User.DoesNotExist:
                logger.warning(f"[VIDEO-RESUMEN] Usuario ID {usuario_id} no encontrado")

        folio = orden.numero_orden_interno

        # =====================================================================
        # PASO 1.5: DETERMINAR TIPOS ACTIVOS SEGÚN TIPO DE SERVICIO
        # Venta mostrador no pasa por diagnóstico → solo 3 tipos: ingreso, reparacion, egreso
        # Diagnóstico estándar → 4 tipos: ingreso, diagnostico, reparacion, egreso
        # =====================================================================
        _es_venta_mostrador = orden.tipo_servicio == 'venta_mostrador'
        if _es_venta_mostrador:
            TIPOS_FOTO_ACTIVOS = ['ingreso', 'reparacion', 'egreso']
            TEXTO_SECCIONES_ACTIVO = TEXTO_SECCIONES_VM
        else:
            TIPOS_FOTO_ACTIVOS = TIPOS_FOTO
            TEXTO_SECCIONES_ACTIVO = TEXTO_SECCIONES

        logger.info(
            f"[VIDEO-RESUMEN] Orden {folio} — tipo_servicio='{orden.tipo_servicio}' "
            f"→ tipos activos: {TIPOS_FOTO_ACTIVOS}"
        )

        # =====================================================================
        # PASO 2: RECOPILAR IMÁGENES EN ORDEN
        # =====================================================================
        # Tomamos solo los tipos activos (3 para venta mostrador, 4 para diagnóstico)
        imagenes_qs = ImagenOrden.objects.filter(
            orden=orden,
            tipo__in=TIPOS_FOTO_ACTIVOS,
        ).order_by('tipo', 'fecha_subida')

        # Ordenar manualmente por el orden lógico del flujo de trabajo
        # (el ORM no puede hacer esto con el orden arbitrario de TIPOS_FOTO_ACTIVOS)
        imagenes_ordenadas = []
        for tipo in TIPOS_FOTO_ACTIVOS:
            for img in imagenes_qs:
                if img.tipo == tipo:
                    imagenes_ordenadas.append(img)

        if len(imagenes_ordenadas) < 2:
            raise ValueError(
                f"Se necesitan al menos 2 fotos de los tipos principales "
                f"(ingreso/diagnóstico/reparación/egreso). "
                f"La orden {folio} tiene {len(imagenes_ordenadas)}."
            )

        logger.info(
            f"[VIDEO-RESUMEN] Orden {folio} — {len(imagenes_ordenadas)} fotos encontradas: "
            + ", ".join(i.tipo for i in imagenes_ordenadas)
        )

        # =====================================================================
        # PASO 3: PREPARAR IMÁGENES ESCALADAS (1280x720 con padding negro)
        # =====================================================================
        # Cada imagen se escala a 1280x720 con padding negro si no es 16:9.
        # Se guarda como JPG temporal numerado para el comando FFmpeg.
        # IMPORTANTE: La ruta absoluta se obtiene con .path o con el campo .imagen
        foto_paths = []
        imagenes_exitosas = []  # Imágenes que se escalaron correctamente (paralelo a foto_paths)

        for idx, imagen_obj in enumerate(imagenes_ordenadas):
            # Obtener ruta absoluta del archivo en disco
            try:
                ruta_original = imagen_obj.imagen.path
            except (ValueError, AttributeError):
                logger.warning(
                    f"[VIDEO-RESUMEN] Imagen ID {imagen_obj.pk} (tipo={imagen_obj.tipo}) "
                    f"no tiene ruta válida, se omite."
                )
                continue

            if not os.path.isfile(ruta_original):
                logger.warning(
                    f"[VIDEO-RESUMEN] Imagen ID {imagen_obj.pk} no existe en disco "
                    f"({ruta_original}), se omite."
                )
                continue

            # Escalar + pad a 1280x720 con negro, guardar en tmp_dir
            ruta_escalada = os.path.join(tmp_dir, f'foto_{idx:03d}.jpg')
            cmd_escalar = [
                ffmpeg_bin,
                '-protocol_whitelist', 'file,pipe,fd',
                '-i', ruta_original,
                '-vf', (
                    "scale=1280:720:force_original_aspect_ratio=decrease,"
                    "pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black"
                ),
                '-q:v', '2',
                '-y',
                ruta_escalada,
            ]
            resultado_escalar = subprocess.run(
                cmd_escalar,
                capture_output=True, text=True, timeout=60,
            )
            if resultado_escalar.returncode != 0 or not os.path.isfile(ruta_escalada):
                logger.warning(
                    f"[VIDEO-RESUMEN] No se pudo escalar imagen {idx}: "
                    f"{resultado_escalar.stderr[-200:]}"
                )
                continue

            foto_paths.append(ruta_escalada)
            imagenes_exitosas.append(imagen_obj)

        if len(foto_paths) < 2:
            raise ValueError(
                f"Solo se pudieron procesar {len(foto_paths)} imágenes válidas. "
                f"Se necesitan al menos 2."
            )

        logger.info(f"[VIDEO-RESUMEN] {len(foto_paths)} imágenes escaladas correctamente")

        # =====================================================================
        # PASO 3.5: DETECTAR MODO REWIND
        # =====================================================================
        # El modo rewind se activa SOLO si hay al menos 1 foto de cada uno de
        # los tipos activos (3 para venta mostrador, 4 para diagnóstico).
        # Si falta algún tipo, se usa el modo simple (comportamiento anterior).
        fotos_por_tipo_idx = {t: [] for t in TIPOS_FOTO_ACTIVOS}
        for path_idx, img in enumerate(imagenes_exitosas):
            if img.tipo in fotos_por_tipo_idx:
                fotos_por_tipo_idx[img.tipo].append(path_idx)

        es_rewind = all(len(fotos_por_tipo_idx[t]) > 0 for t in TIPOS_FOTO_ACTIVOS)

        logger.info(
            f"[VIDEO-RESUMEN] Modo {'rewind' if es_rewind else 'simple'} — "
            f"fotos por tipo: { {t: len(v) for t, v in fotos_por_tipo_idx.items()} }"
        )

        # =====================================================================
        # PASO 4: CONSTRUIR EL FILTERGRAPH DE FFMPEG
        # Ken Burns (zoompan) + xfade transiciones + pantalla de cierre con texto
        # En modo rewind: también incluye intro con logo y tarjetas de sección.
        # =====================================================================
        #
        # El filtergraph funciona así:
        # - Cada imagen de entrada se procesa con "zoompan" (Ken Burns)
        # - zoompan: hace zoom gradual del 100% al 130% durante toda la duración
        # - Todos los clips se encadenan con "xfade=transition=fade"
        # - Al final se añade una pantalla negra con el texto de cierre
        #
        # MODO REWIND (activado si hay fotos de los 4 tipos):
        # - Pantalla de intro: logo SIC + folio + tipo/marca/modelo
        # - Tarjetas de sección (fondo azul #1f6391) antes de cada grupo de fotos
        # - Secuencia: intro → [sec_ingreso → fotos ingreso] × 4 tipos → cierre
        #
        # Cálculo de offsets para xfade (generalizado):
        # offset_acumulado = suma de duraciones visibles de clips anteriores.
        # Cada xfade empieza en: offset_acumulado - DURACION_FADE.
        #
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # El "filtergraph" es la cadena de filtros que FFmpeg aplica al video.
        # Cada filtro se conecta al siguiente con ";" y los clips se unen con xfade.
        # Los identificadores entre corchetes [v0], [v1], etc. son "pads" (conexiones).

        # Total de fotos (sin contar intro, tarjetas ni cierre)
        n_fotos = len(foto_paths)

        # Duración total de cada foto en frames (25 fps)
        fps = 25
        frames_por_foto = DURACION_FOTO * fps          # 100 frames — duración visible "neta"
        frames_clip     = (DURACION_FOTO + DURACION_FADE) * fps  # 125 frames — duración real del clip
        #
        # IMPORTANTE — por qué frames_clip y NO frames_por_foto en el parámetro d de zoompan:
        #
        # Cada clip se pasa a FFmpeg con -t (DURACION_FOTO + DURACION_FADE) = 5 s = 125 frames,
        # porque xfade necesita 1 s extra de overlap entre clips adyacentes.
        #
        # El parámetro `d` de zoompan indica cuántos frames dura el ciclo del efecto. Cuando
        # zoompan llega al frame `d`, reinicia el estado de la variable `zoom` desde cero
        # y comienza un nuevo ciclo con los frames restantes del clip.
        #
        # Con d=100 (frames_por_foto):
        #   - Foto 0 (combined t=0–4 s): el reinicio ocurre en su frame 100 = combined t=4 s,
        #     exactamente cuando el fade 0→1 TERMINA → clip 0 ya está a 0% de opacidad
        #     → el reinicio es invisible para la foto 0.
        #   - Foto 1 en adelante (combined t=3–8 s): el reinicio ocurre en su frame 100
        #     = combined t=7 s, que coincide con el INICIO del siguiente fade → clip 1
        #     todavía tiene opacidad plena → el reinicio del zoom se ve como un salto brusco.
        #
        # Con d=125 (frames_clip):
        #   - El ciclo de zoom abarca los 5 s completos del clip, incluyendo el segundo
        #     de overlap. El zoom nunca se reinicia mientras el clip es visible.
        #   - El efecto Ken Burns es marginalmente más lento (0.0015 × 125 = 0.1875 unidades
        #     de zoom en lugar de 0.15), lo que es visualmente idéntico.

        # ── Construir entradas FFmpeg (fotos) ──
        # Cada foto se pasa como input con -loop 1 -t (DURACION_FOTO + DURACION_FADE)
        cmd_inputs = []
        for ruta in foto_paths:
            cmd_inputs += ['-loop', '1', '-t', str(DURACION_FOTO + DURACION_FADE), '-i', ruta]

        # ── Filtros Ken Burns para cada foto (aplica en ambos modos) ──
        filter_parts = []
        for i in range(n_fotos):
            # Ken Burns: zoom del 100% al 130%, con paneo suave al centro
            # La dirección del zoom alterna: pares hacen zoom-in, impares zoom-out
            if i % 2 == 0:
                # Zoom in: empieza en 1.0 y crece hasta ~1.19 en 125 frames
                zoom_expr = "'min(zoom+0.0015,1.3)'"
                x_expr = "'iw/2-(iw/zoom/2)'"
                y_expr = "'ih/2-(ih/zoom/2)'"
            else:
                # Zoom out: empieza en 1.3 y decrece a ~1.11 en 125 frames
                zoom_expr = "'if(eq(on,1),1.3,max(zoom-0.0015,1.0))'"
                x_expr = "'iw/2-(iw/zoom/2)'"
                y_expr = "'ih/2-(ih/zoom/2)'"

            # EXPLICACIÓN: escalar a 2560×1440 ANTES del zoompan elimina el temblor.
            # El temblor ocurre cuando zoompan tiene que *upscalear* la fuente (1280×720)
            # para hacer zoom; con una fuente 2× más grande siempre estará *downscaleando*
            # y los movimientos quedan suaves a nivel sub-píxel.
            filter_parts.append(
                f"[{i}:v]scale=2560:1440:flags=lanczos,"
                f"zoompan=z={zoom_expr}:x={x_expr}:y={y_expr}"
                f":d={frames_clip}:s=1280x720,fps={fps},"
                f"setsar=1,format=yuv420p[kbv{i}]"
            )

        # ── Pantalla negra de cierre (aplica en ambos modos) ──
        # Usamos color=black y drawtext para el mensaje final
        filter_parts.append(
            f"color=black:size=1280x720:rate={fps}:duration={DURACION_CIERRE + DURACION_FADE},"
            f"drawtext="
            f"fontfile={FFMPEG_DRAWTEXT_FONT}:"
            f"text='{TEXTO_CIERRE}':"
            f"fontcolor=white:"
            f"fontsize=36:"
            f"x=(w-text_w)/2:"
            f"y=(h-text_h)/2:"
            f"enable='gte(t,1)'"
            f"[cierre]"
        )

        # ──────────────────────────────────────────────────────────────────────
        # MODO REWIND: intro con logo + tarjetas de sección
        # ──────────────────────────────────────────────────────────────────────
        if es_rewind:
            # ── Preparar logo para la intro ──
            # Estrategia (en orden de preferencia):
            # 0. logo_sic_white.png estático → usar directamente sin conversión
            #    (generado una vez con rsvg-convert, 480×150 RGBA)
            # 1. logo_sic_white.svg → rasterizar con rsvg-convert a PNG temporal
            #    (fallback por si el PNG estático no existiera)
            # 2. logo_sic.png original → usar con filtro colorkey en FFmpeg para
            #    eliminar el fondo blanco
            # 3. Si ninguno existe → degradar a modo simple
            ruta_logo     = None   # ruta del archivo que pasará a FFmpeg
            logo_colorkey = False  # True si es el PNG original con fondo blanco

            # Paso 0: PNG estático pre-generado (ruta directa, sin dependencia externa)
            ruta_png_white = finders.find('images/logos/logo_sic_white.png')
            if not ruta_png_white:
                ruta_png_white_fb = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'static', 'images', 'logos', 'logo_sic_white.png'
                )
                if os.path.isfile(ruta_png_white_fb):
                    ruta_png_white = ruta_png_white_fb

            if ruta_png_white and os.path.isfile(ruta_png_white):
                ruta_logo = ruta_png_white
                logger.info(
                    "[VIDEO-RESUMEN] Logo: PNG estático logo_sic_white.png encontrado"
                )

            # Paso 1: fallback — SVG blanco + rsvg-convert (solo si el PNG no existe)
            if not ruta_logo:
                ruta_svg = finders.find('images/logos/logo_sic_white.svg')
                if not ruta_svg:
                    ruta_svg_fb = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'static', 'images', 'logos', 'logo_sic_white.svg'
                    )
                    if os.path.isfile(ruta_svg_fb):
                        ruta_svg = ruta_svg_fb

                if ruta_svg and os.path.isfile(ruta_svg):
                    rsvg_bin = shutil.which('rsvg-convert')
                    if rsvg_bin:
                        tmp_logo_png = os.path.join(tmp_dir, 'logo_intro.png')
                        res_svg = subprocess.run(
                            [rsvg_bin, '-w', '480', ruta_svg, '-o', tmp_logo_png],
                            capture_output=True, text=True, timeout=15,
                        )
                        if res_svg.returncode == 0 and os.path.isfile(tmp_logo_png):
                            ruta_logo = tmp_logo_png
                            logger.info(
                                "[VIDEO-RESUMEN] Logo: SVG blanco rasterizado con rsvg-convert"
                            )
                        else:
                            logger.warning(
                                f"[VIDEO-RESUMEN] rsvg-convert falló: {res_svg.stderr[:200]}"
                            )

            # Paso 2: fallback al PNG original con colorkey
            if not ruta_logo:
                ruta_png = finders.find('images/logos/logo_sic.png')
                if not ruta_png:
                    ruta_png_fb = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'static', 'images', 'logos', 'logo_sic.png'
                    )
                    if os.path.isfile(ruta_png_fb):
                        ruta_png = ruta_png_fb
                if ruta_png and os.path.isfile(ruta_png):
                    ruta_logo     = ruta_png
                    logo_colorkey = True
                    logger.info(
                        "[VIDEO-RESUMEN] Logo: usando PNG original con colorkey"
                    )

            if not ruta_logo:
                logger.warning(
                    "[VIDEO-RESUMEN] Ningún logo encontrado — "
                    "degradando a modo simple sin regresión"
                )
                es_rewind = False  # degradar silenciosamente al modo simple

        if es_rewind:
            # El logo es el input adicional al final de las fotos
            logo_idx = n_fotos
            cmd_inputs += [
                '-loop', '1',
                '-t', str(DURACION_INTRO + DURACION_FADE),
                '-i', ruta_logo,
            ]

            # Obtener datos del equipo para mostrar en la intro
            try:
                detalle       = orden.detalle_equipo
                folio_display = detalle.orden_cliente or orden.numero_orden_interno
                equipo_texto  = f"{detalle.tipo_equipo} {detalle.marca} {detalle.modelo}"
            except Exception:
                folio_display = orden.numero_orden_interno
                equipo_texto  = ''

            folio_esc  = _escape_ffmpeg_text(folio_display)
            equipo_esc = _escape_ffmpeg_text(equipo_texto)

            # ── Filtro de intro: fondo azul + logo centrado + texto ──
            # color= genera un clip de fondo sólido azul (color de marca #1f6391)
            filter_parts.append(
                f"color=0x1f6391:size=1280x720:rate={fps}"
                f":duration={DURACION_INTRO + DURACION_FADE}[bg_intro]"
            )
            # Escalar logo a 480px de ancho, mantener proporción, preparar alpha.
            # - SVG rasterizado: ya tiene alpha limpio → solo scale + format=rgba
            # - PNG original:    fondo blanco → colorkey elimina el blanco primero
            if logo_colorkey:
                filter_parts.append(
                    f"[{logo_idx}:v]scale=480:-1,"
                    f"colorkey=white:0.2:0.05,"
                    f"format=rgba[logo_sc]"
                )
            else:
                filter_parts.append(
                    f"[{logo_idx}:v]scale=480:-1,format=rgba[logo_sc]"
                )
            # Superponer logo centrado horizontalmente, desplazado hacia arriba
            filter_parts.append(
                f"[bg_intro][logo_sc]overlay=(W-w)/2:(H-h)/2-100[introlog]"
            )
            # Texto del folio (número de orden) debajo del logo
            filter_parts.append(
                f"[introlog]drawtext=fontfile={FFMPEG_DRAWTEXT_FONT}:"
                f"text='{folio_esc}':fontcolor=white:fontsize=48:"
                f"x=(w-text_w)/2:y=(h-text_h)/2+60[introtext1]"
            )
            # Texto del equipo (tipo + marca + modelo) debajo del folio
            filter_parts.append(
                f"[introtext1]drawtext=fontfile={FFMPEG_DRAWTEXT_FONT}:"
                f"text='{equipo_esc}':fontcolor=white:fontsize=28:"
                f"x=(w-text_w)/2:y=(h-text_h)/2+115[intro]"
            )

            # ── Filtros de tarjetas de sección (fondo azul + texto grande) ──
            for tipo in TIPOS_FOTO_ACTIVOS:
                texto_sec_esc = _escape_ffmpeg_text(TEXTO_SECCIONES_ACTIVO[tipo])
                filter_parts.append(
                    f"color=0x1f6391:size=1280x720:rate={fps}"
                    f":duration={DURACION_SECCION + DURACION_FADE},"
                    f"drawtext=fontfile={FFMPEG_DRAWTEXT_FONT}:"
                    f"text='{texto_sec_esc}':fontcolor=white:fontsize=40:"
                    f"x=(w-text_w)/2:y=(h-text_h)/2[sec_{tipo}]"
                )

            # ── Secuencia de clips rewind ──
            # (label, duración_visible_en_segundos)
            clips_sequence = [('[intro]', DURACION_INTRO)]
            for tipo in TIPOS_FOTO_ACTIVOS:
                clips_sequence.append((f'[sec_{tipo}]', DURACION_SECCION))
                for path_idx in fotos_por_tipo_idx[tipo]:
                    clips_sequence.append((f'[kbv{path_idx}]', DURACION_FOTO))
            clips_sequence.append(('[cierre]', DURACION_CIERRE))

        if not es_rewind:
            # ── Secuencia de clips modo simple (todas las fotos en orden) ──
            clips_sequence = [(f'[kbv{i}]', DURACION_FOTO) for i in range(n_fotos)]
            clips_sequence.append(('[cierre]', DURACION_CIERRE))

        # ── Encadenar todos los clips con xfade (generalizado para ambos modos) ──
        # offset_acumulado = suma de duraciones visibles de los clips ya procesados.
        # El xfade entre el clip N y N+1 empieza en: offset_acumulado - DURACION_FADE.
        offset_acumulado = float(clips_sequence[0][1])
        ultimo_label     = clips_sequence[0][0]

        for i in range(1, len(clips_sequence)):
            next_label, next_dur = clips_sequence[i]
            output_label = f"[xf{i}]"
            offset_str   = f"{offset_acumulado - DURACION_FADE:.3f}"
            filter_parts.append(
                f"{ultimo_label}{next_label}xfade=transition=fade"
                f":duration={DURACION_FADE}:offset={offset_str}{output_label}"
            )
            ultimo_label      = output_label
            offset_acumulado += float(next_dur)

        # El último label es el video final
        filter_parts.append(f"{ultimo_label}null[vout]")

        # Unir todo el filtergraph con ";"
        filtergraph = ";".join(filter_parts)

        # =====================================================================
        # PASO 5: ENCONTRAR RUTA DE LA MÚSICA
        # Ambos modos (normal y rewind) usan rewind_song.mp3
        # =====================================================================
        nombre_audio = 'rewind_song.mp3'
        ruta_musica = finders.find(f'audio/{nombre_audio}')
        if not ruta_musica or not os.path.isfile(ruta_musica):
            # Fallback: buscar directamente en static/
            ruta_musica_fallback = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'static', 'audio', nombre_audio
            )
            if os.path.isfile(ruta_musica_fallback):
                ruta_musica = ruta_musica_fallback
            else:
                ruta_musica = None
                logger.warning(f"[VIDEO-RESUMEN] Música {nombre_audio} no encontrada — video sin audio")

        # =====================================================================
        # PASO 6: EJECUTAR FFMPEG — GENERAR VIDEO FINAL
        # =====================================================================
        # Índice del stream de audio:
        # - Modo simple:  fotos son inputs 0..n_fotos-1, audio es n_fotos
        # - Modo rewind:  fotos son 0..n_fotos-1, logo es n_fotos, audio es n_fotos+1
        audio_stream_idx = n_fotos + (1 if es_rewind else 0)

        cmd_final = (
            [ffmpeg_bin, '-protocol_whitelist', 'file,pipe,fd']
            + cmd_inputs
            + (['-stream_loop', '-1', '-i', ruta_musica] if ruta_musica else [])
            + [
                '-filter_complex', filtergraph,
                '-map', '[vout]',
            ]
            + (['-map', f'{audio_stream_idx}:a:0'] if ruta_musica else [])
            + [
                '-c:v', 'libx264',
                '-crf', '23',
                '-preset', 'medium',
                '-pix_fmt', 'yuv420p',
                '-profile:v', 'main',
                '-level', '4.0',
                '-movflags', '+faststart',
            ]
            + (['-c:a', 'aac', '-b:a', '128k', '-shortest'] if ruta_musica else [])
            + ['-y', tmp_video_out]
        )

        logger.info(
            f"[VIDEO-RESUMEN] Ejecutando FFmpeg con {n_fotos} fotos + cierre. "
            f"Audio: {'sí' if ruta_musica else 'no'}"
        )

        resultado_video = subprocess.run(
            cmd_final,
            capture_output=True,
            text=True,
            timeout=850,  # 14 minutos máx para el proceso de FFmpeg
        )

        if resultado_video.returncode != 0:
            raise RuntimeError(
                f"FFmpeg falló (código {resultado_video.returncode}): "
                f"{resultado_video.stderr[-800:]}"
            )

        if not os.path.isfile(tmp_video_out) or os.path.getsize(tmp_video_out) < 10240:
            raise RuntimeError("FFmpeg no generó el archivo de video o está vacío")

        logger.info(
            f"[VIDEO-RESUMEN] Video generado: "
            f"{os.path.getsize(tmp_video_out) / (1024*1024):.1f} MB"
        )

        # =====================================================================
        # PASO 7: EXTRAER THUMBNAIL (frame del segundo 2)
        # =====================================================================
        cmd_thumb = [
            ffmpeg_bin,
            '-protocol_whitelist', 'file,pipe,fd',
            '-i', tmp_video_out,
            '-ss', '00:00:02',
            '-vframes', '1',
            '-q:v', '3',
            '-y',
            tmp_thumb,
        ]
        subprocess.run(cmd_thumb, capture_output=True, timeout=30)

        # =====================================================================
        # PASO 8: ELIMINAR VIDEO RESUMEN ANTERIOR SI EXISTE
        # =====================================================================
        # Solo puede existir UN video resumen por orden
        videos_anteriores = VideoOrden.objects.filter(orden=orden, tipo='resumen')
        for video_ant in videos_anteriores:
            try:
                if video_ant.video and os.path.isfile(video_ant.video.path):
                    os.remove(video_ant.video.path)
                if video_ant.thumbnail and os.path.isfile(video_ant.thumbnail.path):
                    os.remove(video_ant.thumbnail.path)
                video_ant.delete()
                logger.info(f"[VIDEO-RESUMEN] Video resumen anterior eliminado (ID {video_ant.pk})")
            except Exception as e_del:
                logger.warning(f"[VIDEO-RESUMEN] Error eliminando video anterior: {e_del}")

        # =====================================================================
        # PASO 9: CREAR REGISTRO VideoOrden EN LA BASE DE DATOS
        # =====================================================================
        tamano_final_mb = round(os.path.getsize(tmp_video_out) / (1024 * 1024), 2)
        # Duración estimada: suma de duraciones visibles menos los solapamientos de xfade
        duracion_estimada = int(
            sum(dur for _, dur in clips_sequence)
            - (len(clips_sequence) - 1) * DURACION_FADE
        )

        # Calcular duración real de imágenes procesadas en MB (usamos tamaño del archivo)
        tamano_fotos_mb = round(
            sum(
                os.path.getsize(img.imagen.path)
                for img in imagenes_ordenadas
                if hasattr(img.imagen, 'path') and os.path.isfile(img.imagen.path)
            ) / (1024 * 1024), 2
        )

        nombre_video = f"resumen_{timestamp}.mp4"
        nombre_thumb = f"resumen_{timestamp}_thumb.jpg"

        video_resumen = VideoOrden(
            orden=orden,
            tipo='resumen',
            descripcion=(
                f"Video resumen automático — {n_fotos} fotos "
                f"({', '.join(TIPOS_FOTO_ACTIVOS)}) — generado por Celery"
            ),
            subido_por=empleado_obj,
            tamano_original_mb=tamano_fotos_mb,
            tamano_final_mb=tamano_final_mb,
            duracion_segundos=duracion_estimada,
        )

        # Guardar video usando File() para no cargar todo en RAM
        with open(tmp_video_out, 'rb') as f_video:
            video_resumen.video.save(nombre_video, File(f_video), save=False)

        # Guardar thumbnail si se generó
        if os.path.isfile(tmp_thumb):
            with open(tmp_thumb, 'rb') as f_thumb:
                video_resumen.thumbnail.save(
                    nombre_thumb, ContentFile(f_thumb.read()), save=False
                )

        video_resumen.save()

        logger.info(
            f"[VIDEO-RESUMEN] VideoOrden ID {video_resumen.pk} guardado para Orden {folio}"
        )

        # =====================================================================
        # PASO 10: REGISTRAR EN HISTORIAL
        # =====================================================================
        HistorialOrden.objects.create(
            orden=orden,
            tipo_evento='comentario',
            comentario=(
                f"Video resumen {'rewind' if es_rewind else 'simple'} generado automáticamente: "
                f"{n_fotos} fotos ({DURACION_FOTO}s/foto + Ken Burns"
                + (f", intro {DURACION_INTRO}s, tarjetas {DURACION_SECCION}s" if es_rewind else "")
                + f"). Tamaño: {tamano_final_mb} MB. "
                f"Generado por: {usuario_obj.get_full_name() if usuario_obj else 'Sistema'}"
            ),
            usuario=empleado_obj,
            es_sistema=True,
        )

        # =====================================================================
        # PASO 11: NOTIFICAR AL USUARIO
        # =====================================================================
        try:
            notificar_exito(
                titulo="Video resumen generado",
                mensaje=(
                    f"Orden {folio} — Video resumen listo. "
                    f"{n_fotos} fotos procesadas, {tamano_final_mb} MB."
                ),
                usuario=usuario_obj,
                task_id=self.request.id,
                app_origen='servicio_tecnico',
            )
        except Exception as e_notif:
            logger.warning(f"[VIDEO-RESUMEN] No se pudo crear notificación: {e_notif}")

        return {
            'success': True,
            'video_id': video_resumen.pk,
            'orden_id': orden_id,
            'folio': folio,
            'n_fotos': n_fotos,
            'tamano_mb': tamano_final_mb,
        }

    except Exception as exc:
        logger.error(
            f"[VIDEO-RESUMEN] Error para Orden ID {orden_id}: {exc}\n"
            f"{traceback.format_exc()}"
        )
        # Notificar error al usuario
        try:
            _usuario_err = None
            if usuario_id:
                User = get_user_model()
                try:
                    _usuario_err = User.objects.get(pk=usuario_id)
                except User.DoesNotExist:
                    pass
            notificar_error(
                titulo="Error al generar video resumen",
                mensaje=f"Orden ID {orden_id} — {str(exc)[:300]}",
                usuario=_usuario_err,
                task_id=self.request.id,
                app_origen='servicio_tecnico',
            )
        except Exception:
            pass

        # Solo reintentamos si es un error transitorio (no de datos)
        if not isinstance(exc, ValueError):
            raise self.retry(exc=exc, countdown=30)
        raise

    finally:
        # Limpiar directorio temporal siempre, aunque haya errores
        try:
            if os.path.isdir(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)
                logger.debug(f"[VIDEO-RESUMEN] Directorio temporal eliminado: {tmp_dir}")
        except Exception:
            pass


# ============================================================================
# TAREA CELERY: COMPRIMIR VIDEO RESUMEN PARA DESCARGA
# ============================================================================

@shared_task(
    bind=True,
    name='servicio_tecnico.comprimir_video_resumen_descarga',
    max_retries=3,
    soft_time_limit=600,   # 10 minutos soft limit
    time_limit=720,        # 12 minutos hard limit
)
def comprimir_video_resumen_descarga_task(self, video_id: int, usuario_id: int, db_alias: str = 'default'):
    """
    Tarea Celery que comprime el video resumen de una orden para su descarga.

    Aplica los mismos parámetros que comprimir_y_guardar_video() en views.py:
    - Codec: H.264 (libx264), CRF 28, preset fast
    - Audio: AAC 96k
    - Resolución máxima: 1280×720 (sin límite de duración)
    - Resultado: VideoOrden(tipo='resumen_comprimido') ligado a la misma orden

    Si ya existe un 'resumen_comprimido' para la orden, se reemplaza.

    Args:
        self       : Referencia a la tarea Celery (bind=True)
        video_id   : ID del VideoOrden(tipo='resumen') original
        usuario_id : ID del usuario que solicitó la descarga
    """
    import os
    import shutil
    import subprocess
    import tempfile
    import time
    from pathlib import Path

    from django.contrib.auth import get_user_model
    from django.core.files import File

    from .models import VideoOrden, HistorialOrden

    logger.info(f"[VIDEO-COMPRESION] Iniciando compresión para VideoOrden ID {video_id}")

    ffmpeg_bin = shutil.which('ffmpeg') or '/usr/bin/ffmpeg'
    tmp_dir = tempfile.mkdtemp(prefix='video_compresion_')
    tmp_out = os.path.join(tmp_dir, 'resumen_comprimido.mp4')
    timestamp = int(time.time() * 1000)

    _usuario_err = None

    try:
        # =====================================================================
        # PASO 1: OBTENER VIDEO ORIGINAL Y USUARIO
        # =====================================================================
        try:
            video_original = VideoOrden.objects.select_related(
                'orden', 'orden__sucursal'
            ).get(pk=video_id, tipo='resumen')
        except VideoOrden.DoesNotExist:
            raise ValueError(
                f"VideoOrden ID {video_id} de tipo 'resumen' no encontrado."
            )

        orden = video_original.orden

        User = get_user_model()
        try:
            _usuario_err = User.objects.get(pk=usuario_id)
        except User.DoesNotExist:
            _usuario_err = None

        # =====================================================================
        # PASO 2: VERIFICAR QUE EL ARCHIVO FÍSICO EXISTE
        # =====================================================================
        if not video_original.video:
            raise ValueError("El video resumen original no tiene archivo asociado.")

        ruta_original = video_original.video.path
        if not os.path.isfile(ruta_original):
            raise FileNotFoundError(
                f"El archivo del video resumen no existe en disco: {ruta_original}"
            )

        tamano_original_mb = round(os.path.getsize(ruta_original) / (1024 * 1024), 2)
        logger.info(
            f"[VIDEO-COMPRESION] Archivo fuente: {ruta_original} "
            f"({tamano_original_mb} MB)"
        )

        # =====================================================================
        # PASO 3: COMPRIMIR CON FFMPEG
        # Mismos parámetros que comprimir_y_guardar_video() en views.py:
        # - CRF 28 (vs CRF 23 del original) — ~30-40% menos peso
        # - preset fast (vs medium del original) — más rápido
        # - Sin -t (sin límite de duración)
        # =====================================================================
        cmd_comprimir = [
            ffmpeg_bin,
            '-protocol_whitelist', 'file,pipe,fd',
            '-i', ruta_original,
            '-vf', (
                "scale='min(1280,iw)':'min(720,ih)':force_original_aspect_ratio=decrease,"
                "scale=trunc(iw/2)*2:trunc(ih/2)*2,"
                "unsharp=5:5:1.0:5:5:0.0"
            ),
            '-c:v',      'libx264',
            '-crf',      '28',
            '-preset',   'fast',
            '-pix_fmt',  'yuv420p',
            '-profile:v', 'main',
            '-level',    '4.0',
            '-c:a',      'aac',
            '-b:a',      '128k',     # Subido de 96k: evita distorsión al recodificar Opus→AAC
            '-ar',       '48000',    # Sample rate explícito — previene variación entre dispositivos
            '-map',      '0:v:0',
            '-map',      '0:a:0?',   # Audio opcional (no falla si no hay)
            '-movflags', '+faststart',
            '-map_metadata', '-1',   # Eliminar metadatos del original
            '-y',
            tmp_out,
        ]

        logger.info(f"[VIDEO-COMPRESION] Ejecutando FFmpeg para orden {orden.numero_orden_interno}")

        resultado = subprocess.run(
            cmd_comprimir,
            capture_output=True,
            text=True,
            timeout=580,
        )

        if resultado.returncode != 0:
            raise RuntimeError(
                f"FFmpeg falló al comprimir (código {resultado.returncode}): "
                f"{resultado.stderr[-800:]}"
            )

        if not os.path.isfile(tmp_out) or os.path.getsize(tmp_out) == 0:
            raise RuntimeError("FFmpeg no generó el archivo comprimido.")

        tamano_final_mb = round(os.path.getsize(tmp_out) / (1024 * 1024), 2)
        logger.info(
            f"[VIDEO-COMPRESION] Compresión completada: "
            f"{tamano_original_mb} MB → {tamano_final_mb} MB "
            f"(ahorro: {round((1 - tamano_final_mb / tamano_original_mb) * 100, 1)}%)"
        )

        # =====================================================================
        # PASO 4: ELIMINAR COMPRIMIDO ANTERIOR SI EXISTE (REEMPLAZAR)
        # =====================================================================
        video_anterior = VideoOrden.objects.filter(
            orden=orden, tipo='resumen_comprimido'
        ).first()
        if video_anterior:
            try:
                if video_anterior.video:
                    video_anterior.video.delete(save=False)
                video_anterior.delete()
                logger.info(f"[VIDEO-COMPRESION] Eliminado comprimido anterior para orden {orden.pk}")
            except Exception as e:
                logger.warning(f"[VIDEO-COMPRESION] No se pudo eliminar comprimido anterior: {e}")

        # =====================================================================
        # PASO 5: GUARDAR NUEVO VideoOrden(tipo='resumen_comprimido')
        # =====================================================================
        nombre_video = f"resumen_comprimido_{timestamp}.mp4"

        video_comprimido = VideoOrden(
            orden=orden,
            tipo='resumen_comprimido',
            descripcion=(
                f"Versión comprimida del video resumen — "
                f"{tamano_original_mb} MB → {tamano_final_mb} MB"
            ),
            subido_por=video_original.subido_por,
            tamano_original_mb=tamano_original_mb,
            tamano_final_mb=tamano_final_mb,
        )

        with open(tmp_out, 'rb') as f_video:
            video_comprimido.video.save(nombre_video, File(f_video), save=False)

        video_comprimido.save()

        # =====================================================================
        # PASO 6: HISTORIAL
        # =====================================================================
        try:
            HistorialOrden.objects.create(
                orden=orden,
                tipo_evento='video',
                comentario=(
                    f"Video resumen comprimido para descarga generado. "
                    f"Tamaño: {tamano_final_mb} MB "
                    f"(reducción del "
                    f"{round((1 - tamano_final_mb / tamano_original_mb) * 100, 1)}%)"
                ),
            )
        except Exception as e:
            logger.warning(f"[VIDEO-COMPRESION] No se pudo crear historial: {e}")

        logger.info(
            f"[VIDEO-COMPRESION] ✓ Completado — VideoOrden ID {video_comprimido.pk} "
            f"| Orden {orden.numero_orden_interno} | {tamano_final_mb} MB"
        )

        return {
            'success': True,
            'video_id': video_comprimido.pk,
            'video_url': video_comprimido.video.url,
            'tamano_original_mb': tamano_original_mb,
            'tamano_final_mb': tamano_final_mb,
        }

    except Exception as exc:
        logger.error(
            f"[VIDEO-COMPRESION] Error para VideoOrden ID {video_id}: {exc}",
            exc_info=True,
        )

        try:
            from notificaciones.utils import notificar_error
            notificar_error(
                titulo="Error al comprimir video resumen",
                mensaje=f"VideoOrden ID {video_id} — {str(exc)[:300]}",
                usuario=_usuario_err,
                task_id=self.request.id,
                app_origen='servicio_tecnico',
            )
        except Exception:
            pass

        if not isinstance(exc, ValueError):
            raise self.retry(exc=exc, countdown=30)
        raise

    finally:
        # Limpiar el directorio temporal siempre, incluso si hubo error
        try:
            if os.path.isdir(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)
                logger.debug(f"[VIDEO-COMPRESION] Directorio temporal eliminado: {tmp_dir}")
        except Exception:
            pass


# ============================================================================
# TAREA: Comprimir Video de Evidencia (reemplazo asíncrono de comprimir_y_guardar_video)
# ============================================================================

@shared_task(
    bind=True,
    max_retries=1,
    default_retry_delay=30,
    soft_time_limit=1260,  # 21 minutos — margen amplio para videos WebM pesados
    time_limit=1320,       # 22 minutos hard-limit (el worker se mata si supera esto)
    name='servicio_tecnico.comprimir_video_evidencia',
)
def comprimir_video_evidencia_task(
    self,
    archivo_tmp_path: str,
    nombre_original: str,
    tamano_bytes: int,
    orden_id: int,
    tipo: str,
    descripcion: str,
    empleado_id: int,
    usuario_id: int,
    orientacion_video: int = 0,
    db_alias: str = 'default',
):
    """
    Tarea Celery: comprime un video de evidencia con FFmpeg y guarda el VideoOrden.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta tarea es el reemplazo asíncrono de comprimir_y_guardar_video() en views.py.
    Antes, esa función bloqueaba el request HTTP hasta que FFmpeg terminaba de
    comprimir — lo que causaba que Cloudflare cortara la conexión en videos largos.

    Nuevo flujo:
      1. La VISTA guarda el video crudo en /tmp y despacha esta tarea de inmediato.
      2. Esta TAREA corre en el worker de Celery (proceso separado, sin límite HTTP):
         - Comprime con FFmpeg (H.264/AAC, máx 1080p, CRF 23)
         - Extrae thumbnail del segundo 1
         - Guarda VideoOrden en la base de datos
         - Notifica al usuario por campanita (siempre) y por push (si está suscrito)

    Parámetros (IMPORTANTE: solo tipos simples — NUNCA objetos Django):
        self              : Referencia a la tarea (para reintentos), viene de bind=True
        archivo_tmp_path  : Ruta absoluta del archivo crudo guardado en /tmp
        nombre_original   : Nombre original del archivo (para detectar extensión)
        tamano_bytes      : Tamaño original sin comprimir en bytes (para el registro)
        orden_id          : ID de la OrdenServicio en la base de datos
        tipo              : Tipo de video (ingreso, diagnostico, reparacion, egreso, packing)
        descripcion       : Descripción opcional del técnico
        empleado_id       : ID del Empleado que sube el video (para VideoOrden.subido_por)
        usuario_id        : ID del User Django (para la notificación campanita y push)
    """
    import subprocess
    import shutil
    import time
    from pathlib import Path as PPath
    from django.core.files import File
    from django.core.files.base import ContentFile
    from django.contrib.auth import get_user_model
    from django.urls import reverse
    from servicio_tecnico.models import OrdenServicio, VideoOrden
    from inventario.models import Empleado
    from notificaciones.push_service import enviar_push_a_usuario

    logger.info(
        f"[VIDEO-EVIDENCIA] Iniciando compresión — Orden ID {orden_id}, tipo={tipo}"
    )

    # ── Resolver usuario para notificaciones ─────────────────────────────────
    # Se hace aquí, fuera del try principal, para poder usarlo también en except
    User = get_user_model()
    try:
        usuario = User.objects.get(pk=usuario_id)
    except User.DoesNotExist:
        usuario = None
        logger.warning(f"[VIDEO-EVIDENCIA] Usuario ID {usuario_id} no encontrado en BD")

    # Variables de rutas intermedias — declaradas aquí para el bloque finally
    tmp_out_path   = None
    tmp_thumb_path = None

    try:
        # =====================================================================
        # PASO 1: VERIFICAR QUE EL ARCHIVO TEMPORAL EXISTE EN DISCO
        # =====================================================================
        # La vista guardó el video crudo en /tmp antes de despachar esta tarea.
        # Si el archivo ya no existe (limpieza del SO, crash, etc.) lanzamos
        # FileNotFoundError que no se reintenta (ver bloque except abajo).
        if not PPath(archivo_tmp_path).exists():
            raise FileNotFoundError(
                f"Archivo temporal no encontrado: {archivo_tmp_path}. "
                f"Puede haberse limpiado antes de que Celery procesara la tarea."
            )

        # =====================================================================
        # PASO 2: OBTENER OBJETOS DJANGO DESDE LA BD
        # =====================================================================
        try:
            orden = OrdenServicio.objects.select_related(
                'detalle_equipo', 'sucursal'
            ).get(pk=orden_id)
        except OrdenServicio.DoesNotExist:
            raise ValueError(f"OrdenServicio ID {orden_id} no encontrada en BD")

        try:
            empleado = Empleado.objects.get(pk=empleado_id)
        except Empleado.DoesNotExist:
            raise ValueError(f"Empleado ID {empleado_id} no encontrado en BD")

        # =====================================================================
        # PASO 3: PREPARAR RUTAS TEMPORALES DE SALIDA
        # =====================================================================
        timestamp      = int(time.time() * 1000)
        nombre_video   = f"{tipo}_{timestamp}.mp4"
        nombre_thumb   = f"{tipo}_{timestamp}_thumb.jpg"
        tmp_out_path   = archivo_tmp_path + '_out.mp4'
        tmp_thumb_path = archivo_tmp_path + '_thumb.jpg'

        # Mismo patrón de detección de ffmpeg que comprimir_y_guardar_video():
        # shutil.which() busca en el PATH del worker; fallback a ruta absoluta.
        ffmpeg_bin = shutil.which('ffmpeg') or '/usr/bin/ffmpeg'

        # =====================================================================
        # PASO 4: CONSTRUIR FILTRO DE ORIENTACIÓN
        # El cliente captura la orientación del dispositivo al iniciar la grabación
        # (screen.orientation + giroscopio) y la envía como 'orientacion_video' (0/90/180/270).
        #
        # Muchos teléfonos graban los píxeles en orientación portrait (sensor nativo)
        # independientemente de cómo se sostenga el celular, y embeben un tag de rotación
        # en el contenedor. FFmpeg con -map_metadata -1 elimina ese tag sin rotar los píxeles,
        # dejando el video "de lado". Este filtro corrige los píxeles directamente.
        #
        # Mapa de transposes:
        #   orientacion=0   → portrait normal       → sin transpose
        #   orientacion=90  → landscape hacia derecha → transpose=1 (rota 90° CW)
        #   orientacion=270 → landscape hacia izquierda → transpose=2 (rota 90° CCW)
        #   orientacion=180 → portrait invertido     → hflip + vflip (180°)
        # =====================================================================
        if orientacion_video == 90:
            transpose_prefijo = 'transpose=1,'
        elif orientacion_video == 270:
            transpose_prefijo = 'transpose=2,'
        elif orientacion_video == 180:
            transpose_prefijo = 'hflip,vflip,'
        else:
            transpose_prefijo = ''

        # =====================================================================
        # PASO 5: COMPRIMIR CON FFMPEG
        # Parámetros idénticos a comprimir_y_guardar_video() en views.py:
        # H.264 + AAC, máx 1080p, CRF 23, preset fast, safety-limit 10 min.
        # =====================================================================
        cmd_compress = [
            ffmpeg_bin,
            '-protocol_whitelist', 'file,pipe,fd',
             '-i', archivo_tmp_path,
             '-vf', (
                 f"{transpose_prefijo}"
                 "scale='min(1280,iw)':'min(720,ih)':force_original_aspect_ratio=decrease,"
                 "scale=trunc(iw/2)*2:trunc(ih/2)*2"
             ),
            '-c:v', 'libx264',
            '-crf', '25',
            '-preset', 'veryfast',
            '-pix_fmt', 'yuv420p',
            '-profile:v', 'main',
            '-level', '4.0',
            '-c:a', 'aac',
            '-b:a', '128k',    # Subido de 96k: evita distorsión al recodificar Opus→AAC
            '-ar', '48000',    # Sample rate explícito — previene variación entre dispositivos
            '-map', '0:v:0',
            '-map', '0:a:0?',      # Audio opcional — no falla si el video no tiene audio
            '-movflags', '+faststart',
            '-t', '600',           # Safety-limit: 10 min máx
            '-map_metadata', '-1',
            '-y',
            tmp_out_path,
        ]
        logger.info(
            f"[VIDEO-EVIDENCIA] FFmpeg iniciando — Orden {orden.numero_orden_interno} "
            f"| orientacion={orientacion_video}° "
            f"| transpose={'sí (' + transpose_prefijo.rstrip(',') + ')' if transpose_prefijo else 'no'}"
        )
        resultado = subprocess.run(
            cmd_compress,
            capture_output=True,
            text=True,
            timeout=1200,  # 20 minutos máximo para el proceso FFmpeg
        )
        if resultado.returncode != 0:
            raise RuntimeError(
                f'FFmpeg falló (código {resultado.returncode}): {resultado.stderr[-500:]}'
            )

        logger.info(
            f"[VIDEO-EVIDENCIA] FFmpeg completado — Orden {orden.numero_orden_interno}"
        )

        # =====================================================================
        # PASO 5: EXTRAER THUMBNAIL DEL SEGUNDO 1
        # Si falla no es crítico — VideoOrden.thumbnail puede quedar vacío
        # =====================================================================
        cmd_thumb = [
            ffmpeg_bin,
            '-protocol_whitelist', 'file,pipe,fd',
            '-i', tmp_out_path,
            '-ss', '00:00:01',
            '-vframes', '1',
            '-q:v', '3',
            '-y',
            tmp_thumb_path,
        ]
        subprocess.run(cmd_thumb, capture_output=True, timeout=30)

        # =====================================================================
        # PASO 6: MEDIR DURACIÓN CON FFPROBE
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # ffprobe lee los metadatos del video comprimido para obtener su duración
        # exacta en segundos. Si falla por cualquier motivo, simplemente guarda
        # None — no es un error crítico.
        # =====================================================================
        duracion_segundos = None
        try:
            cmd_probe = [
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                tmp_out_path,
            ]
            resultado_probe = subprocess.run(
                cmd_probe, capture_output=True, text=True, timeout=10
            )
            if resultado_probe.returncode == 0:
                duracion_segundos = int(float(resultado_probe.stdout.strip()))
        except Exception:
            pass  # No crítico — el video se guarda igualmente sin duración

        # =====================================================================
        # PASO 7: CREAR REGISTRO VideoOrden EN LA BASE DE DATOS
        # video_orden.save() llama al override del modelo que registra el historial
        # =====================================================================
        tamano_original_mb = round(tamano_bytes / (1024 * 1024), 2)
        tamano_final_mb    = round(os.path.getsize(tmp_out_path) / (1024 * 1024), 2)

        video_orden = VideoOrden(
            orden=orden,
            tipo=tipo,
            descripcion=descripcion,
            subido_por=empleado,
            tamano_original_mb=tamano_original_mb,
            tamano_final_mb=tamano_final_mb,
            duracion_segundos=duracion_segundos,
        )

        with open(tmp_out_path, 'rb') as f_video:
            video_orden.video.save(nombre_video, File(f_video), save=False)

        if PPath(tmp_thumb_path).exists():
            with open(tmp_thumb_path, 'rb') as f_thumb:
                video_orden.thumbnail.save(nombre_thumb, ContentFile(f_thumb.read()), save=False)

        video_orden.save()

        logger.info(
            f"[VIDEO-EVIDENCIA] VideoOrden ID {video_orden.pk} guardado — "
            f"{tamano_original_mb} MB → {tamano_final_mb} MB"
        )

        # =====================================================================
        # PASO 7: NOTIFICAR AL USUARIO — campanita (garantizada) + push (opcional)
        # =====================================================================
        try:
            orden_ref = (
                orden.detalle_equipo.orden_cliente
                if orden.detalle_equipo and orden.detalle_equipo.orden_cliente
                else orden.numero_orden_interno
            )
        except Exception:
            orden_ref = orden.numero_orden_interno

        try:
            tipo_display = dict(
                VideoOrden._meta.get_field('tipo').choices
            ).get(tipo, tipo)
        except Exception:
            tipo_display = tipo

        porcentaje    = video_orden.porcentaje_compresion
        titulo_notif  = f"Video listo — {orden_ref}"
        mensaje_notif = (
            f"Video de {tipo_display} procesado. Compresión: −{porcentaje}%."
            if porcentaje
            else f"Video de {tipo_display} guardado correctamente."
        )

        # URL para el botón de la notificación push — abre la orden directamente
        try:
            url_orden = reverse(
                'servicio_tecnico:detalle_orden', kwargs={'orden_id': orden_id}
            )
        except Exception:
            url_orden = f"/servicio_tecnico/ordenes/{orden_id}/"

        # Campanita: polling de 15s la muestra rápido, y es la notificación garantizada
        notificar_exito(
            titulo=titulo_notif,
            mensaje=mensaje_notif,
            usuario=usuario,
            task_id=self.request.id,
            app_origen='servicio_tecnico',
            url=url_orden,
        )

        # Push: solo si el usuario tiene suscripciones activas
        if usuario:
            try:
                enviados = enviar_push_a_usuario(
                    usuario=usuario,
                    titulo=titulo_notif,
                    mensaje=mensaje_notif,
                    url=url_orden,
                )
                if enviados:
                    logger.info(
                        f"[VIDEO-EVIDENCIA] Push enviado a {enviados} dispositivo(s) "
                        f"del usuario {usuario.username}"
                    )
            except Exception as e_push:
                # El push falla en silencio — la campanita ya notificó al usuario
                logger.warning(
                    f"[VIDEO-EVIDENCIA] No se pudo enviar push a {usuario.username}: {e_push}"
                )

        return {
            'success': True,
            'video_id': video_orden.pk,
            'orden_id': orden_id,
            'tipo': tipo,
        }

    except Exception as exc:
        logger.error(
            f"[VIDEO-EVIDENCIA] Error para Orden ID {orden_id}: {exc}",
            exc_info=True,
        )

        # Notificar el error al usuario por campanita y push
        try:
            if usuario:
                _url_err = locals().get(
                    'url_orden',
                    f"/servicio_tecnico/ordenes/{orden_id}/"
                )
                notificar_error(
                    titulo=f"Error al procesar video — Orden ID {orden_id}",
                    mensaje=(
                        f"No se pudo comprimir el video de {tipo}. "
                        f"Detalle: {str(exc)[:300]}"
                    ),
                    usuario=usuario,
                    task_id=self.request.id,
                    app_origen='servicio_tecnico',
                    url=_url_err,
                )
                try:
                    enviar_push_a_usuario(
                        usuario=usuario,
                        titulo="Error al procesar video",
                        mensaje=(
                            f"No se pudo comprimir el video de {tipo}. "
                            f"Intenta subirlo de nuevo."
                        ),
                        url=_url_err,
                    )
                except Exception:
                    pass
        except Exception as e_notif:
            logger.warning(
                f"[VIDEO-EVIDENCIA] No se pudo crear notificación de error: {e_notif}"
            )

        # Solo reintentar en errores de sistema — no en errores de lógica ni timeouts
        # (FileNotFoundError, ValueError y TimeoutExpired no se resuelven con un reintento:
        #  el archivo temporal ya se eliminó en el finally antes del retry)
        if not isinstance(exc, (ValueError, FileNotFoundError, subprocess.TimeoutExpired)):
            raise self.retry(exc=exc, countdown=30)
        raise

    finally:
        # Limpiar TODOS los archivos temporales: original crudo + intermedios de FFmpeg
        # Se ejecuta siempre, aunque la tarea haya fallado — evita llenar el disco
        for tmp_path in filter(None, [archivo_tmp_path, tmp_out_path, tmp_thumb_path]):
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
        logger.info(
            f"[VIDEO-EVIDENCIA] Archivos temporales limpiados — Orden ID {orden_id}"
        )


# ============================================================================
# TAREA CELERY: ENVIAR CORREO REWIND AL CLIENTE (segunda etapa del chain)
# ============================================================================

@shared_task(
    bind=True,
    name='servicio_tecnico.enviar_rewind_egreso_email',
    max_retries=2,
    default_retry_delay=30,
    soft_time_limit=120,
    time_limit=180,
)
def enviar_rewind_egreso_email_task(self, prev_result, orden_id, usuario_id, destinatarios_copia, db_alias='default'):
    """
    Segunda etapa del chain rewind de egreso.

    Recibe el resultado de generar_video_resumen_task (que incluye video_id y
    el thumbnail ya guardado en VideoOrden), construye el correo HTML con el
    thumbnail embebido como imagen inline (cid:thumbnail_video) y un botón CTA
    que apunta al seguimiento público del cliente.

    EXPLICACIÓN PARA PRINCIPIANTES:
    En un chain de Celery, el valor de retorno de la primera tarea se pasa
    automáticamente como primer argumento de la segunda (prev_result).
    Si la generación del video falló, prev_result['success'] será False y
    abortamos el envío sin lanzar error.

    Parámetros:
        prev_result         : Dict retornado por generar_video_resumen_task
                              {'success': bool, 'video_id': int, ...}
        orden_id            : ID de la OrdenServicio
        usuario_id          : ID del usuario que disparó la acción
        destinatarios_copia : Lista de emails en CC
    """
    import io
    from pathlib import Path
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from django.utils import timezone
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.contrib.staticfiles import finders
    from email.mime.image import MIMEImage

    from .models import OrdenServicio, VideoOrden, HistorialOrden

    logger.info(f"[REWIND-EMAIL] Iniciando para Orden ID {orden_id}")

    # =========================================================================
    # PASO 1: VERIFICAR QUE EL PASO ANTERIOR (GENERACIÓN DE VIDEO) TUVO ÉXITO
    # =========================================================================
    if not prev_result or not prev_result.get('success'):
        motivo = (prev_result or {}).get('error', 'Desconocido')
        logger.error(
            f"[REWIND-EMAIL] generar_video_resumen_task falló para Orden {orden_id}. "
            f"Motivo: {motivo} — abortando envío de correo rewind."
        )
        # Notificar al usuario del fallo
        try:
            if usuario_id:
                User = get_user_model()
                try:
                    _u = User.objects.get(pk=usuario_id)
                except User.DoesNotExist:
                    _u = None
                from notificaciones.utils import notificar_error
                notificar_error(
                    titulo="Error en video rewind — correo no enviado",
                    mensaje=(
                        f"Orden ID {orden_id} — La generación del video falló antes del envío. "
                        f"Motivo: {str(motivo)[:200]}"
                    ),
                    usuario=_u,
                    task_id=self.request.id,
                    app_origen='servicio_tecnico',
                )
        except Exception:
            pass
        return {'success': False, 'motivo': 'video_fallido', 'orden_id': orden_id}

    video_id = prev_result.get('video_id')

    try:
        # =====================================================================
        # PASO 2: CARGAR ORDEN Y VIDEO
        # =====================================================================
        try:
            orden = OrdenServicio.objects.select_related('detalle_equipo').get(pk=orden_id)
        except OrdenServicio.DoesNotExist:
            logger.error(f"[REWIND-EMAIL] Orden ID {orden_id} no encontrada.")
            return {'success': False, 'motivo': 'orden_no_encontrada'}

        email_cliente = orden.detalle_equipo.email_cliente

        # Intentar cargar el VideoOrden para obtener el thumbnail y la URL del video
        video_obj = None
        thumbnail_path = None
        video_url = None
        if video_id:
            try:
                video_obj = VideoOrden.objects.get(pk=video_id)
                if video_obj.thumbnail and hasattr(video_obj.thumbnail, 'path'):
                    _thumb_path = video_obj.thumbnail.path
                    if Path(_thumb_path).is_file():
                        thumbnail_path = _thumb_path
                # URL directa al archivo de video para el enlace del correo
                if video_obj.video:
                    try:
                        from config.paises_config import get_pais_actual as _get_pais_vid
                        site_url_vid = _get_pais_vid().get('url_base', getattr(settings, 'SITE_URL', 'http://localhost:8000'))
                        video_url = f"{site_url_vid}{video_obj.video.url}"
                    except Exception:
                        pass
            except VideoOrden.DoesNotExist:
                logger.warning(f"[REWIND-EMAIL] VideoOrden ID {video_id} no encontrado.")

        # =====================================================================
        # PASO 3: PREPARAR CONTEXTO DEL TEMPLATE
        # =====================================================================
        from config.paises_config import get_pais_actual, fecha_local_pais
        _pais = get_pais_actual()

        whatsapp_empleado = ''
        if usuario_id:
            User = get_user_model()
            try:
                usuario = User.objects.get(pk=usuario_id)
                if hasattr(usuario, 'empleado') and usuario.empleado:
                    numero_local = usuario.empleado.numero_whatsapp
                    if numero_local:
                        codigo_tel = _pais.get('codigo_telefonico', '')
                        whatsapp_empleado = f"{codigo_tel}{numero_local}"
            except User.DoesNotExist:
                pass

        ahora_local = fecha_local_pais(timezone.now(), _pais)

        # URL de seguimiento público (igual que en enviar_imagenes_egreso_cliente_task)
        seguimiento_url = None
        if orden.es_fuera_garantia:
            try:
                enlace = orden.enlace_seguimiento
                if enlace and enlace.activo:
                    site_url = _pais.get('url_base', getattr(settings, 'SITE_URL', 'http://localhost:8000'))
                    seguimiento_url = f"{site_url}/seguimiento/{enlace.token}/"
            except Exception:
                pass

        context = {
            'orden': orden,
            'detalle': orden.detalle_equipo,
            'fecha_envio_texto': ahora_local.strftime('%d/%m/%Y'),
            'hora_envio_texto': ahora_local.strftime('%H:%M'),
            'empresa_nombre': _pais['empresa_nombre_corto'],
            'pais_nombre': _pais['nombre'],
            'whatsapp_empleado': whatsapp_empleado,
            'seguimiento_url': seguimiento_url,
            'thumbnail_disponible': thumbnail_path is not None,
            'video_url': video_url,
            # Si es venta mostrador, el template omite menciones a diagnóstico
            'es_venta_mostrador': orden.tipo_servicio == 'venta_mostrador',
        }

        html_content = render_to_string(
            'servicio_tecnico/emails/rewind_egreso_cliente.html',
            context
        )

        # =====================================================================
        # PASO 4: CONSTRUIR Y ENVIAR EL CORREO
        # =====================================================================
        numero_orden_display = (
            orden.detalle_equipo.orden_cliente
            if orden.detalle_equipo.orden_cliente
            else orden.numero_orden_interno
        )
        asunto = f'🎬 Resumen del servicio de tu equipo - Orden {numero_orden_display}'

        import re as _re
        email_match = _re.search(r'<(.+?)>', settings.DEFAULT_FROM_EMAIL)
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

        # ── Thumbnail del video (embebido como cid:thumbnail_video) ──────────
        if thumbnail_path:
            try:
                with open(thumbnail_path, 'rb') as f_thumb:
                    thumb_mime = MIMEImage(f_thumb.read(), _subtype='jpeg')
                    thumb_mime.add_header('Content-ID', '<thumbnail_video>')
                    thumb_mime.add_header('Content-Disposition', 'inline', filename='thumbnail_video.jpg')
                    email_msg.attach(thumb_mime)
                logger.info(f"[REWIND-EMAIL] Thumbnail adjunto desde {thumbnail_path}")
            except Exception as e:
                logger.warning(f"[REWIND-EMAIL] No se pudo adjuntar thumbnail: {e}")

        # ── Logo SIC ─────────────────────────────────────────────────────────
        try:
            logo_path = finders.find('images/logos/logo_sic.png')
            if logo_path:
                with open(logo_path, 'rb') as f:
                    logo_mime = MIMEImage(f.read(), _subtype='png')
                    logo_mime.add_header('Content-ID', '<logo_sic>')
                    logo_mime.add_header('Content-Disposition', 'inline', filename='logo_sic.png')
                    email_msg.attach(logo_mime)
        except Exception as e:
            logger.warning(f"[REWIND-EMAIL] Error al adjuntar logo: {e}")

        # ── Iconos de redes sociales ──────────────────────────────────────────
        try:
            iconos_sociales = {
                'icon_link':      'images/utilitys/link.png',
                'icon_instagram': 'images/utilitys/instagram.png',
                'icon_facebook':  'images/utilitys/facebook.png',
                'icon_whatsapp':  'images/utilitys/whatsapp.png',
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
            logger.warning(f"[REWIND-EMAIL] Error al adjuntar iconos: {e}")

        email_msg.send(fail_silently=False)
        logger.info(f"[REWIND-EMAIL] Correo rewind enviado a {email_cliente}")

        # =====================================================================
        # PASO 5: REGISTRAR EN HISTORIAL
        # El comentario incluye "video rewind" Y "imágenes de egreso" para que
        # ambos filtros de egreso_correo_ya_enviado y rewind_ya_enviado lo detecten.
        # =====================================================================
        try:
            usuario_empleado = None
            if usuario_id:
                User = get_user_model()
                try:
                    _u2 = User.objects.get(pk=usuario_id)
                    if hasattr(_u2, 'empleado'):
                        usuario_empleado = _u2.empleado
                except User.DoesNotExist:
                    pass

            comentario_hist = (
                f"📧 Video rewind — imágenes de egreso enviadas al cliente ({email_cliente})\n"
                f"🎬 Modo: Video resumen rewind del servicio completo\n"
                f"📹 VideoOrden ID: {video_id}"
            )
            if destinatarios_copia:
                comentario_hist += f"\n👥 Copia a: {', '.join(destinatarios_copia)}"

            HistorialOrden.objects.create(
                orden=orden,
                tipo_evento='email',
                comentario=comentario_hist,
                usuario=usuario_empleado,
                es_sistema=False,
            )
        except Exception as e:
            logger.warning(f"[REWIND-EMAIL] No se pudo registrar historial: {e}")

        # =====================================================================
        # PASO 6: NOTIFICAR ÉXITO AL USUARIO
        # =====================================================================
        try:
            _usuario_notif = None
            if usuario_id:
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
                titulo="Video rewind enviado al cliente",
                mensaje=(
                    f"Orden {_oc} — Correo rewind enviado exitosamente a {email_cliente}."
                ),
                usuario=_usuario_notif,
                task_id=self.request.id,
                app_origen='servicio_tecnico',
            )
        except Exception as e:
            logger.warning(f"[REWIND-EMAIL] No se pudo crear notificación de éxito: {e}")

        logger.info(f"[REWIND-EMAIL] Tarea completada para Orden {orden.numero_orden_interno}")

        return {
            'success': True,
            'orden': orden.numero_orden_interno,
            'destinatario': email_cliente,
            'video_id': video_id,
        }

    except Exception as exc:
        logger.error(
            f"[REWIND-EMAIL] Error para Orden ID {orden_id}: {exc}",
            exc_info=True,
        )
        try:
            if usuario_id:
                User = get_user_model()
                try:
                    _u_err = User.objects.get(pk=usuario_id)
                except User.DoesNotExist:
                    _u_err = None
                from notificaciones.utils import notificar_error
                notificar_error(
                    titulo="Error al enviar correo rewind",
                    mensaje=f"Orden ID {orden_id} — {str(exc)[:300]}",
                    usuario=_u_err,
                    task_id=self.request.id,
                    app_origen='servicio_tecnico',
                )
        except Exception:
            pass

        if not isinstance(exc, ValueError):
            raise self.retry(exc=exc, countdown=30)
        raise


# ============================================================================
# TAREA: ENVIAR EVIDENCIA EN VIDEO AL CLIENTE
# ============================================================================
# Flujo:
#   1. Cargar orden + videos seleccionados
#   2. Extraer frames de cada video con FFmpeg (en memoria)
#   3. Análisis IA con frames (fail-safe: si falla, se omite la sección)
#   4. Renderizar plantilla HTML con thumbnails embebidos CID
#   5. Enviar correo al cliente
#   6. Registrar en historial + notificar al usuario
# ============================================================================

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='servicio_tecnico.enviar_evidencia_video',
    soft_time_limit=600,
    time_limit=660,
)
def enviar_evidencia_video_task(
    self, orden_id, video_ids, destinatarios_copia,
    modelo_ia_analisis='', usuario_id=None,
    mensaje_personalizado='', db_alias='default',
):
    """
    Tarea Celery: extrae frames de videos de evidencia, genera análisis IA
    opcional y envía correo al cliente con la evidencia en video.

    Parámetros:
        orden_id              : ID de la OrdenServicio
        video_ids             : Lista de IDs de VideoOrden seleccionados
        destinatarios_copia   : Lista de emails en CC
        modelo_ia_analisis    : Modelo IA seleccionado (vacío = sin análisis)
        usuario_id            : ID del usuario que disparó la acción
        mensaje_personalizado : Texto opcional que el usuario agrega al correo
    """
    from pathlib import Path
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from django.utils import timezone
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.contrib.staticfiles import finders
    from email.mime.image import MIMEImage

    from .models import OrdenServicio, VideoOrden, HistorialOrden

    logger.info(f"[EVIDENCIA-VIDEO] Iniciando tarea para Orden ID {orden_id}")

    try:
        # ===================================================================
        # PASO 1: RECUPERAR ORDEN Y VIDEOS
        # ===================================================================
        try:
            orden = OrdenServicio.objects.select_related('detalle_equipo').get(pk=orden_id)
        except OrdenServicio.DoesNotExist:
            logger.error(f"[EVIDENCIA-VIDEO] Orden ID {orden_id} no encontrada.")
            return {'success': False, 'mensaje': f'Orden ID {orden_id} no encontrada.'}

        email_cliente = orden.detalle_equipo.email_cliente

        videos = VideoOrden.objects.filter(
            id__in=video_ids, orden=orden
        ).exclude(tipo__in=['resumen', 'resumen_comprimido'])

        if not videos.exists():
            raise Exception("No se encontraron videos válidos para enviar.")

        # ===================================================================
        # PASO 2: EXTRAER FRAMES DE CADA VIDEO (para IA y thumbnails)
        # ===================================================================
        from .ollama_client import extraer_frames_video

        todos_los_frames = []
        videos_data = []
        from config.paises_config import get_pais_actual as _get_pais_ev
        site_url = _get_pais_ev().get('url_base', getattr(settings, 'SITE_URL', 'http://localhost:8000'))

        for video in videos:
            video_path = video.video.path if video.video else None
            if not video_path or not Path(video_path).exists():
                logger.warning(f"[EVIDENCIA-VIDEO] Video {video.id} no encontrado en disco.")
                continue

            frames = extraer_frames_video(video_path, max_frames=8)
            todos_los_frames.extend(frames)

            duracion_str = ''
            if video.duracion_segundos:
                mins = video.duracion_segundos // 60
                segs = video.duracion_segundos % 60
                duracion_str = f"{mins}:{segs:02d}"

            thumbnail_bytes = None
            if video.thumbnail and Path(video.thumbnail.path).exists():
                try:
                    from PIL import Image
                    import io
                    img = Image.open(video.thumbnail.path)
                    if img.mode in ('RGBA', 'LA', 'P'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = background
                    max_dim = 480
                    if max(img.size) > max_dim:
                        ratio = max_dim / max(img.size)
                        new_size = tuple([int(d * ratio) for d in img.size])
                        img = img.resize(new_size, Image.Resampling.LANCZOS)
                    output = io.BytesIO()
                    img.save(output, format='JPEG', quality=80, optimize=True)
                    thumbnail_bytes = output.getvalue()
                except Exception as e_thumb:
                    logger.warning(f"[EVIDENCIA-VIDEO] Error procesando thumbnail {video.id}: {e_thumb}")

            videos_data.append({
                'id': video.id,
                'tipo_display': video.get_tipo_display(),
                'descripcion': video.descripcion or '',
                'duracion': duracion_str,
                'tamano': str(video.tamano_final_mb) if video.tamano_final_mb else '',
                'tiene_thumbnail': thumbnail_bytes is not None,
                'thumbnail_bytes': thumbnail_bytes,
                'video_url': f"{site_url}{video.video.url}" if video.video else '',
            })

        if not videos_data:
            raise Exception("No se pudo procesar ningún video.")

        # ===================================================================
        # PASO 2.5: ANÁLISIS IA DE EVIDENCIA EN VIDEO (no crítico)
        # ===================================================================
        analisis_ia_texto = None
        analisis_ia_modelo = None

        if modelo_ia_analisis and todos_los_frames:
            try:
                from .ollama_client import analizar_video_evidencia_dispatch

                max_frames_ia = getattr(settings, 'OLLAMA_MAX_IMAGENES_IA', 8)
                frames_para_ia = todos_los_frames[:max_frames_ia]

                detalle = orden.detalle_equipo
                resultado_ia = analizar_video_evidencia_dispatch(
                    frames_bytes=frames_para_ia,
                    tipo_equipo=detalle.tipo_equipo if detalle else '',
                    marca=detalle.marca if detalle else '',
                    modelo_equipo=detalle.modelo if detalle else '',
                    n_videos=len(videos_data),
                    modelo_override=modelo_ia_analisis,
                    contexto_adicional=mensaje_personalizado,
                )

                if resultado_ia.get('success'):
                    analisis_ia_texto = resultado_ia['analisis']
                    analisis_ia_modelo = resultado_ia['modelo_usado']

                    logger.info(
                        f"[EVIDENCIA-VIDEO] Análisis IA completado | "
                        f"{len(analisis_ia_texto)} chars | Modelo: {analisis_ia_modelo}"
                    )

                    HistorialOrden.objects.create(
                        orden=orden,
                        tipo_evento='inspeccion_ia',
                        comentario=(
                            f"🤖 Análisis de evidencia en video — {analisis_ia_modelo}\n\n"
                            f"{analisis_ia_texto}"
                        ),
                        es_sistema=True,
                    )
                else:
                    logger.warning(
                        f"[EVIDENCIA-VIDEO] Análisis IA no disponible: "
                        f"{resultado_ia.get('error', 'Sin detalles')}"
                    )

            except Exception as e_ia:
                logger.warning(
                    f"[EVIDENCIA-VIDEO] Excepción en análisis IA (no crítico): "
                    f"{type(e_ia).__name__}: {e_ia}"
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

        seguimiento_url = None
        if orden.es_fuera_garantia:
            try:
                enlace = orden.enlace_seguimiento
                if enlace and enlace.activo:
                    site_url = _pais_email.get('url_base', getattr(settings, 'SITE_URL', 'http://localhost:8000'))
                    seguimiento_url = f"{site_url}/seguimiento/{enlace.token}/"
            except Exception:
                pass

        context = {
            'orden': orden,
            'detalle': orden.detalle_equipo,
            'fecha_envio_texto': ahora_local.strftime('%d/%m/%Y'),
            'hora_envio_texto': ahora_local.strftime('%H:%M'),
            'cantidad_videos': len(videos_data),
            'videos_data': videos_data,
            'empresa_nombre': _pais_email['empresa_nombre_corto'],
            'pais_nombre': _pais_email['nombre'],
            'whatsapp_empleado': whatsapp_empleado,
            'seguimiento_url': seguimiento_url,
            'analisis_ia_texto': analisis_ia_texto,
            'analisis_ia_modelo': analisis_ia_modelo,
            'mensaje_personalizado': mensaje_personalizado,
        }

        html_content = render_to_string(
            'servicio_tecnico/emails/evidencia_video_cliente.html',
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
        asunto = f'🎬 Evidencia en video del servicio - Orden {numero_orden_display}'

        import re
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

        try:
            logo_path = finders.find('images/logos/logo_sic.png')
            if logo_path:
                with open(logo_path, 'rb') as f:
                    logo_mime = MIMEImage(f.read(), _subtype='png')
                    logo_mime.add_header('Content-ID', '<logo_sic>')
                    logo_mime.add_header('Content-Disposition', 'inline', filename='logo_sic.png')
                    email_msg.attach(logo_mime)
        except Exception as e:
            logger.warning(f"[EVIDENCIA-VIDEO] Error al adjuntar logo: {e}")

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
            logger.warning(f"[EVIDENCIA-VIDEO] Error al adjuntar iconos: {e}")

        for v_data in videos_data:
            if v_data['tiene_thumbnail'] and v_data['thumbnail_bytes']:
                try:
                    thumb_mime = MIMEImage(v_data['thumbnail_bytes'], _subtype='jpeg')
                    thumb_mime.add_header('Content-ID', f'<thumb_video_{v_data["id"]}>')
                    thumb_mime.add_header('Content-Disposition', 'inline', filename=f'thumb_{v_data["id"]}.jpg')
                    email_msg.attach(thumb_mime)
                except Exception as e_thumb:
                    logger.warning(f"[EVIDENCIA-VIDEO] Error adjuntando thumbnail {v_data['id']}: {e_thumb}")

        email_msg.send(fail_silently=False)
        logger.info(f"[EVIDENCIA-VIDEO] Correo enviado a {email_cliente}")

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

            tipos_enviados = [v['tipo_display'] for v in videos_data]
            comentario = (
                f"🎬 Evidencia en video enviada al cliente ({email_cliente})\n"
                f"📹 Cantidad de videos: {len(videos_data)}\n"
                f"🏷️ Tipos: {', '.join(tipos_enviados)}"
            )
            if destinatarios_copia:
                comentario += f"\n👥 Copia a: {', '.join(destinatarios_copia)}"
            if analisis_ia_texto:
                comentario += f"\n🤖 Análisis IA: {analisis_ia_modelo}"

            HistorialOrden.objects.create(
                orden=orden,
                tipo_evento='email',
                comentario=comentario,
                usuario=usuario_empleado,
                es_sistema=False,
            )
        except Exception as e:
            logger.warning(f"[EVIDENCIA-VIDEO] No se pudo registrar historial: {e}")

        logger.info(f"[EVIDENCIA-VIDEO] Tarea completada para Orden {orden.numero_orden_interno}")

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
                titulo="Evidencia en video enviada",
                mensaje=(
                    f"Orden {_oc} — "
                    f"{len(videos_data)} video(s) enviado(s) a {email_cliente}."
                ),
                usuario=_usuario_notif,
                task_id=self.request.id,
                app_origen='servicio_tecnico',
            )
        except Exception as e:
            logger.warning(f"[EVIDENCIA-VIDEO] No se pudo crear notificación de éxito: {e}")

        return {
            'success': True,
            'orden': orden.numero_orden_interno,
            'destinatario': email_cliente,
            'videos_enviados': len(videos_data),
        }

    except Exception as exc:
        logger.error(
            f"[EVIDENCIA-VIDEO] Error para Orden ID {orden_id}: {exc}\n{traceback.format_exc()}"
        )
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
                titulo="Error al enviar evidencia en video",
                mensaje=f"Orden {orden_id} — {str(exc)[:200]}",
                usuario=_usuario_err,
                task_id=self.request.id,
                app_origen='servicio_tecnico',
            )
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='servicio_tecnico.enviar_formato_oow_email',
)
def enviar_formato_oow_email_task(
    self,
    formato_id,
    usuario_id=None,
    db_alias='default',
):
    """
    Envía por correo el PDF del Formato Digital OOW al cliente.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Celery no pasa por PaisMiddleware; db_alias encola el tenant correcto
    (México=default, argentina, chile, colombia).

    Args:
        formato_id: PK de FormatoServicioOOW
        usuario_id: User que disparó el envío (auditoría)
        db_alias: Alias de BD del país

    Efectos secundarios:
        Envía EmailMessage con PDF adjunto; registra historial en la orden.
    """
    from django.conf import settings
    from django.core.mail import EmailMessage
    from email.mime.application import MIMEApplication

    from .models import FormatoServicioOOW, HistorialOrden
    from inventario.models import Empleado

    try:
        formato = FormatoServicioOOW.objects.select_related(
            'orden', 'orden__detalle_equipo',
        ).get(pk=formato_id)

        if not formato.pdf:
            logger.warning(
                '[FORMATO_OOW] Sin PDF — formato_id=%s',
                formato_id,
            )
            return {'success': False, 'error': 'Sin PDF'}

        from .services.formato_oow import lista_emails_envio
        destinatarios = lista_emails_envio(formato)
        if not destinatarios:
            logger.warning(
                '[FORMATO_OOW] Sin email — formato_id=%s',
                formato_id,
            )
            return {'success': False, 'error': 'Sin PDF o email'}

        orden = formato.orden
        detalle = orden.detalle_equipo
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # En el correo mostramos la orden SICSER (folio / orden cliente),
        # no el número interno ORD-… de SIGMA.
        orden_sicser = (
            detalle.folio_sicser
            or detalle.orden_cliente
            or orden.numero_orden_interno
        )
        asunto = f'Formato de Servicio OOW — {orden_sicser}'
        cuerpo = (
            f'<p>Estimado(a) cliente,</p>'
            f'<p>Adjuntamos el <strong>Formato de Servicio Fuera de Garantía</strong> '
            f'correspondiente a su equipo.</p>'
            f'<p>Orden: <b>{orden_sicser}</b><br>'
            f'Service Tag: <b>{detalle.numero_serie or "—"}</b></p>'
            f'<p>SIC Comercialización y Servicios</p>'
        )

        # Remitente de Servicio Técnico (no el de Score Card).
        # Si SERVICIO_TECNICO_FROM_EMAIL no está en .env, reutilizamos la
        # dirección de DEFAULT_FROM_EMAIL pero con el nombre correcto.
        from email.utils import formataddr, parseaddr
        from decouple import config

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

        # EXPLICACIÓN PARA PRINCIPIANTES:
        # EmailMessage.to acepta una lista: se envía el mismo PDF a todos (máx. 3).
        email_msg = EmailMessage(
            subject=asunto,
            body=cuerpo,
            from_email=from_email,
            to=destinatarios,
        )
        email_msg.content_subtype = 'html'

        with formato.pdf.open('rb') as fh:
            pdf_bytes = fh.read()
        pdf_mime = MIMEApplication(pdf_bytes, _subtype='pdf')
        pdf_mime.add_header(
            'Content-Disposition',
            'attachment',
            filename=f'FormatoOOW_{orden_sicser}.pdf',
        )
        email_msg.attach(pdf_mime)
        email_msg.send()

        usuario_empleado = None
        if usuario_id:
            try:
                usuario_empleado = Empleado.objects.get(user_id=usuario_id)
            except Empleado.DoesNotExist:
                usuario_empleado = None

        destinarios_txt = ', '.join(destinatarios)
        HistorialOrden.objects.create(
            orden=orden,
            tipo_evento='email',
            comentario=(
                f'Formato Digital OOW enviado a {destinarios_txt}'
            ),
            usuario=usuario_empleado,
            es_sistema=False,
        )
        logger.info(
            '[FORMATO_OOW] Email enviado a %s orden=%s',
            destinarios_txt,
            orden.numero_orden_interno,
        )
        return {'success': True}

    except Exception as exc:
        logger.error('[FORMATO_OOW] Error email: %s', exc, exc_info=True)
        raise self.retry(exc=exc, countdown=60)
