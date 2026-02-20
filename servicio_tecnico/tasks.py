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
        # EXPLICACIÓN: self.retry() vuelve a intentar la tarea automáticamente.
        # countdown=60 espera 60 segundos antes de reintentar.
        # Si falla las max_retries veces (3), la tarea queda en estado FAILURE en Redis.
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
        return {
            'success': True,
            'orden': orden.numero_orden_interno,
            'destinatario': email_cliente,
            'imagenes_enviadas': len(imagenes_comprimidas),
            'tamaño_mb': round(tamaño_total_comprimido / 1024 / 1024, 2),
        }

    except Exception as exc:
        logger.error(f"[IMAGENES] Error para Orden ID {orden_id}: {exc}\n{traceback.format_exc()}")
        raise self.retry(exc=exc, countdown=60)
