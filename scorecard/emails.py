"""
Lógica de envío de emails para notificaciones de Score Card
Este módulo maneja todo lo relacionado con el envío de notificaciones por correo electrónico
"""
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from .models import NotificacionIncidencia
from PIL import Image
from io import BytesIO
import json
import os


def comprimir_imagen(ruta_imagen, calidad=60, max_ancho=800):
    """
    Comprime una imagen para reducir su tamaño antes de adjuntarla al email
    
    Parámetros:
    - ruta_imagen: Ruta completa a la imagen
    - calidad: Calidad de compresión JPEG (1-100, default 60)
    - max_ancho: Ancho máximo en píxeles (default 800)
    
    Retorna:
    - BytesIO con la imagen comprimida, o None si hay error
    """
    try:
        # Abrir la imagen
        img = Image.open(ruta_imagen)
        
        # Convertir a RGB si es necesario (para JPEGs)
        if img.mode in ('RGBA', 'LA', 'P'):
            # Crear fondo blanco
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Redimensionar si es muy grande
        if img.width > max_ancho:
            ratio = max_ancho / img.width
            nuevo_alto = int(img.height * ratio)
            img = img.resize((max_ancho, nuevo_alto), Image.LANCZOS)
        
        # Guardar en BytesIO con compresión
        output = BytesIO()
        img.save(output, format='JPEG', quality=calidad, optimize=True)
        output.seek(0)
        
        return output
        
    except Exception as e:
        print(f"Error al comprimir imagen {ruta_imagen}: {e}")
        return None


def enviar_notificacion_incidencia(incidencia, destinatarios_seleccionados, mensaje_adicional='', enviado_por='Sistema'):
    """
    Envía notificación por email sobre una incidencia
    
    Parámetros:
    - incidencia: Objeto Incidencia sobre la que se notifica
    - destinatarios_seleccionados: Lista de diccionarios con estructura:
      [{'nombre': 'Juan Pérez', 'email': 'juan@email.com', 'rol': 'Técnico Responsable'}, ...]
    - mensaje_adicional: Texto adicional opcional para incluir en el email
    - enviado_por: Nombre del usuario que envía la notificación
    
    Retorna:
    - Diccionario con 'success' (bool) y 'message' (str)
    """
    
    # Validar que hay destinatarios
    if not destinatarios_seleccionados or len(destinatarios_seleccionados) == 0:
        return {
            'success': False,
            'message': 'No se seleccionaron destinatarios'
        }
    
    # Extraer solo los emails para envío
    emails_destinatarios = [d['email'] for d in destinatarios_seleccionados if d.get('email')]
    
    if not emails_destinatarios:
        return {
            'success': False,
            'message': 'No se encontraron emails válidos'
        }
    
    # Crear asunto del email
    asunto = f"[INCIDENCIA] {incidencia.folio} - {incidencia.tipo_incidencia.nombre}"
    
    # Obtener evidencias (máximo 10 para no saturar el email)
    evidencias = incidencia.evidencias.all()[:10]
    
    # Contexto para el template del email
    context = {
        'incidencia': incidencia,
        'mensaje_adicional': mensaje_adicional,
        'destinatarios': destinatarios_seleccionados,
        'evidencias': evidencias,  # Agregar evidencias al contexto
    }
    
    # Renderizar el template HTML
    html_content = render_to_string('scorecard/emails/notificacion_incidencia.html', context)
    
    # Crear versión texto plano (fallback)
    text_content = f"""
    NOTIFICACIÓN DE INCIDENCIA - SCORE CARD SYSTEM
    
    Folio: {incidencia.folio}
    Fecha de Detección: {incidencia.fecha_deteccion.strftime('%d/%m/%Y')}
    
    EQUIPO:
    - Tipo: {incidencia.get_tipo_equipo_display()}
    - Marca: {incidencia.marca}
    - Modelo: {incidencia.modelo}
    - Número de Serie (Service Tag): {incidencia.numero_serie}
    {f'- Número de Orden: {incidencia.numero_orden}' if incidencia.numero_orden else ''}
    
    RESPONSABLES:
    - Técnico/Personal: {incidencia.tecnico_responsable.nombre_completo}
    - Inspector: {incidencia.inspector_calidad}
    - Sucursal: {incidencia.sucursal.nombre}
    
    CLASIFICACIÓN:
    - Tipo: {incidencia.tipo_incidencia.nombre}
    - Categoría: {incidencia.get_categoria_fallo_display()}
    - Severidad: {incidencia.get_grado_severidad_display()}
    - Componente: {incidencia.componente_afectado.nombre if incidencia.componente_afectado else 'N/A'}
    
    DESCRIPCIÓN:
    {incidencia.descripcion_incidencia}
    
    ACCIONES TOMADAS:
    {incidencia.acciones_tomadas}
    
    {'MENSAJE ADICIONAL: ' + mensaje_adicional if mensaje_adicional else ''}
    
    ---
    Este es un mensaje automático del Sistema Score Card de Calidad.
    """
    
    try:
        # Crear el email con versión HTML y texto
        email = EmailMultiAlternatives(
            subject=asunto,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=emails_destinatarios,
        )
        
        # Adjuntar versión HTML
        email.attach_alternative(html_content, "text/html")
        
        # Adjuntar imágenes de evidencia (comprimidas)
        imagenes_adjuntadas = 0
        for idx, evidencia in enumerate(evidencias, start=1):
            try:
                # Obtener la ruta completa de la imagen
                ruta_imagen = evidencia.imagen.path
                
                if os.path.exists(ruta_imagen):
                    # Comprimir la imagen
                    imagen_comprimida = comprimir_imagen(ruta_imagen, calidad=60, max_ancho=800)
                    
                    if imagen_comprimida:
                        # Obtener el nombre del archivo original
                        nombre_original = os.path.basename(ruta_imagen)
                        nombre_base, ext = os.path.splitext(nombre_original)
                        
                        # Crear nombre descriptivo para el adjunto
                        nombre_adjunto = f"evidencia_{idx}_{incidencia.folio}.jpg"
                        
                        # Adjuntar la imagen comprimida
                        email.attach(nombre_adjunto, imagen_comprimida.read(), 'image/jpeg')
                        imagenes_adjuntadas += 1
                        
            except Exception as img_error:
                print(f"Error al adjuntar imagen {idx}: {img_error}")
                # Continuar con las demás imágenes aunque una falle
                continue
        
        # Enviar el email
        email.send(fail_silently=False)
        
        # Mensaje de éxito con información de imágenes
        mensaje_exito = f'Notificación enviada exitosamente a {len(emails_destinatarios)} destinatario(s)'
        if imagenes_adjuntadas > 0:
            mensaje_exito += f' con {imagenes_adjuntadas} imagen(es) adjunta(s)'
        
        # Registrar la notificación en la base de datos
        NotificacionIncidencia.objects.create(
            incidencia=incidencia,
            tipo_notificacion='manual',
            destinatarios_json=json.dumps(destinatarios_seleccionados, ensure_ascii=False),
            destinatarios=json.dumps(destinatarios_seleccionados, ensure_ascii=False),  # Legacy
            asunto=asunto,
            mensaje_adicional=mensaje_adicional,
            enviado_por=enviado_por,
            exitoso=True,
            enviado_exitoso=True,
            mensaje_error=''
        )
        
        return {
            'success': True,
            'message': mensaje_exito
        }
        
    except Exception as e:
        # Registrar el error en la base de datos
        NotificacionIncidencia.objects.create(
            incidencia=incidencia,
            tipo_notificacion='manual',
            destinatarios_json=json.dumps(destinatarios_seleccionados, ensure_ascii=False),
            destinatarios=json.dumps(destinatarios_seleccionados, ensure_ascii=False),  # Legacy
            asunto=asunto,
            mensaje_adicional=mensaje_adicional,
            enviado_por=enviado_por,
            exitoso=False,
            enviado_exitoso=False,
            mensaje_error=str(e)
        )
        
        return {
            'success': False,
            'message': f'Error al enviar notificación: {str(e)}'
        }


def obtener_destinatarios_disponibles(incidencia):
    """
    Obtiene la lista de destinatarios disponibles para una incidencia
    
    Retorna lista de diccionarios con estructura:
    [
        {
            'nombre': 'Juan Pérez',
            'email': 'juan@email.com',
            'rol': 'Técnico Responsable',
            'seleccionado_default': True/False
        },
        ...
    ]
    """
    destinatarios = []
    
    # 1. Técnico responsable (seleccionado por defecto)
    if incidencia.tecnico_responsable and incidencia.tecnico_responsable.email:
        destinatarios.append({
            'nombre': incidencia.tecnico_responsable.nombre_completo,
            'email': incidencia.tecnico_responsable.email,
            'rol': 'Técnico/Personal Responsable',
            'seleccionado_default': True,
            'es_sistema': False
        })
        
        # 2. Jefe directo del técnico (opcional)
        if incidencia.tecnico_responsable.jefe_directo and incidencia.tecnico_responsable.jefe_directo.email:
            destinatarios.append({
                'nombre': incidencia.tecnico_responsable.jefe_directo.nombre_completo,
                'email': incidencia.tecnico_responsable.jefe_directo.email,
                'rol': 'Jefe Directo',
                'seleccionado_default': True,
                'es_sistema': False
            })
    
    # 3. Inspector de calidad (opcional)
    # El inspector es un CharField, no ForeignKey, así que no tiene email directo
    # Se podría buscar por nombre si existe como empleado
    
    # 4. Jefe de Calidad 1 (opcional, desde settings)
    destinatarios.append({
        'nombre': settings.JEFE_CALIDAD_NOMBRE,
        'email': settings.JEFE_CALIDAD_EMAIL,
        'rol': 'Inspector de Calidad',
        'seleccionado_default': True,
        'es_sistema': True
    })
    
    # 5. Jefe de Calidad 2 (opcional, desde settings)
    if hasattr(settings, 'JEFE_CALIDAD_2_EMAIL') and settings.JEFE_CALIDAD_2_EMAIL:
        destinatarios.append({
            'nombre': settings.JEFE_CALIDAD_2_NOMBRE,
            'email': settings.JEFE_CALIDAD_2_EMAIL,
            'rol': 'Jefe de calidad',
            'seleccionado_default': True,
            'es_sistema': True
        })
    
    # 6. Jefe General (opcional, desde settings)
    if hasattr(settings, 'JEFE_GENERAL_EMAIL') and settings.JEFE_GENERAL_EMAIL:
        destinatarios.append({
            'nombre': settings.JEFE_GENERAL_NOMBRE,
            'email': settings.JEFE_GENERAL_EMAIL,
            'rol': 'Jefe General',
            'seleccionado_default': True,
            'es_sistema': True
        })
    
    # 7. Ayudante de Compras (opcional, desde settings)
    if hasattr(settings, 'AYUDANTE_COMPRAS_EMAIL') and settings.AYUDANTE_COMPRAS_EMAIL:
        destinatarios.append({
            'nombre': settings.AYUDANTE_COMPRAS_NOMBRE,
            'email': settings.AYUDANTE_COMPRAS_EMAIL,
            'rol': 'Ayudante Compras',
            'seleccionado_default': True,
            'es_sistema': True
        })
    
    return destinatarios


def obtener_destinatarios_historicos(incidencia):
    """
    Obtiene todos los destinatarios únicos que han recibido notificaciones manuales
    exitosas previas de esta incidencia.
    
    Esta función busca en el historial de notificaciones MANUALES y extrae todos
    los destinatarios para incluirlos en notificaciones automáticas futuras.
    
    Parámetros:
    - incidencia: Objeto Incidencia del cual obtener historial
    
    Retorna:
    - Lista de diccionarios con estructura {'nombre': str, 'email': str, 'rol': str}
    - Lista vacía si no hay notificaciones previas
    """
    import json
    
    destinatarios_unicos = {}  # Usamos dict para evitar duplicados por email
    
    try:
        # Buscar notificaciones manuales exitosas de esta incidencia
        notificaciones_manuales = incidencia.notificaciones.filter(
            tipo_notificacion='manual',
            enviado_exitoso=True
        ) | incidencia.notificaciones.filter(
            tipo_notificacion='manual',
            exitoso=True  # Campo legacy
        )
        
        # Extraer destinatarios de cada notificación
        for notif in notificaciones_manuales:
            destinatarios_list = notif.get_destinatarios_list()
            
            for dest in destinatarios_list:
                email = dest.get('email', '').strip().lower()
                
                # Solo agregar si tiene email válido y no está ya en la lista
                if email and email not in destinatarios_unicos:
                    destinatarios_unicos[email] = {
                        'nombre': dest.get('nombre', 'Sin nombre'),
                        'email': email,
                        'rol': dest.get('rol', 'Previamente notificado'),
                        'es_sistema': False  # Los históricos no son del sistema
                    }
        
        # Convertir dict a lista
        return list(destinatarios_unicos.values())
        
    except Exception as e:
        # En caso de error, retornar lista vacía para no romper el flujo
        print(f"Error al obtener destinatarios históricos: {e}")
        return []


def enviar_notificacion_no_atribuible(incidencia, justificacion, marcado_por='Sistema'):
    """
    Envía notificación al técnico cuando una incidencia se marca como NO atribuible
    
    Esta notificación explica al técnico que la incidencia NO afectará su scorecard
    y proporciona la justificación de por qué no se le atribuye.
    
    IMPORTANTE: También incluye automáticamente a todos los destinatarios que
    recibieron notificaciones manuales previas de esta incidencia.
    
    Parámetros:
    - incidencia: Objeto Incidencia que se marcó como no atribuible
    - justificacion: Texto explicando por qué no es atribuible
    - marcado_por: Nombre del usuario que marcó como no atribuible
    
    Retorna:
    - Diccionario con 'success' (bool) y 'message' (str)
    """
    
    # Verificar que el técnico tiene email
    if not incidencia.tecnico_responsable.email:
        return {
            'success': False,
            'message': f'El técnico {incidencia.tecnico_responsable.nombre_completo} no tiene email registrado'
        }
    
    # Lista de destinatarios
    destinatarios = []
    emails_destinatarios = []
    
    # 1. Destinatario principal: el técnico responsable
    email_tecnico = incidencia.tecnico_responsable.email.strip().lower()
    destinatarios.append({
        'nombre': incidencia.tecnico_responsable.nombre_completo,
        'email': email_tecnico,
        'rol': 'Técnico Responsable'
    })
    emails_destinatarios.append(email_tecnico)
    
    # 2. Obtener destinatarios del historial de notificaciones manuales
    destinatarios_historicos = obtener_destinatarios_historicos(incidencia)
    
    for dest_hist in destinatarios_historicos:
        email_hist = dest_hist['email'].strip().lower()
        
        # Solo agregar si no está ya en la lista (evitar duplicados)
        if email_hist not in emails_destinatarios:
            destinatarios.append(dest_hist)
            emails_destinatarios.append(email_hist)
    
    # Asunto del email
    asunto = f"[INFO] {incidencia.folio} - Incidencia NO Atribuible"
    
    # Contexto para el template
    context = {
        'incidencia': incidencia,
        'tecnico': incidencia.tecnico_responsable,
        'justificacion': justificacion,
        'marcado_por': marcado_por,
        'fecha_actual': timezone.now(),
        'destinatarios_adicionales': len(destinatarios) - 1  # Todos menos el técnico
    }
    
    try:
        # Renderizar template HTML
        html_content = render_to_string('scorecard/emails/no_atribuible.html', context)
        
        # Crear email con todos los destinatarios
        email = EmailMultiAlternatives(
            subject=asunto,
            body=f"Incidencia {incidencia.folio} - Marcada como NO Atribuible",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=emails_destinatarios  # Lista completa de emails
        )
        
        # Adjuntar versión HTML
        email.attach_alternative(html_content, "text/html")
        
        # Enviar
        email.send(fail_silently=False)
        
        # Mensaje de éxito
        mensaje_exito = f'Notificación enviada a {len(emails_destinatarios)} destinatario(s)'
        if len(destinatarios) > 1:
            mensaje_exito += f' (incluye {len(destinatarios) - 1} del historial)'
        
        # Registrar en base de datos
        from .models import NotificacionIncidencia
        NotificacionIncidencia.objects.create(
            incidencia=incidencia,
            tipo_notificacion='no_atribuible',
            destinatarios_json=json.dumps(destinatarios, ensure_ascii=False),
            asunto=asunto,
            enviado_exitoso=True
        )
        
        return {
            'success': True,
            'message': mensaje_exito
        }
        
    except Exception as e:
        # Registrar error en base de datos
        from .models import NotificacionIncidencia
        NotificacionIncidencia.objects.create(
            incidencia=incidencia,
            tipo_notificacion='no_atribuible',
            destinatarios_json=json.dumps(destinatarios, ensure_ascii=False),
            asunto=asunto,
            enviado_exitoso=False,
            mensaje_error=str(e)
        )
        
        return {
            'success': False,
            'message': f'Error al enviar notificación: {str(e)}'
        }


def enviar_notificacion_cierre_incidencia(incidencia, mensaje_adicional='', enviado_por='Sistema'):
    """
    Envía notificación cuando se cierra una incidencia (atribuible o no)
    
    - Si es ATRIBUIBLE: Notifica que la incidencia fue cerrada (estándar)
    - Si es NO ATRIBUIBLE: Notifica con conclusión final para conocimiento del técnico
    
    IMPORTANTE: También incluye automáticamente a todos los destinatarios que
    recibieron notificaciones manuales previas de esta incidencia.
    
    Parámetros:
    - incidencia: Objeto Incidencia que se está cerrando
    - mensaje_adicional: Texto adicional con conclusiones o notas finales
    - enviado_por: Nombre del usuario que cierra la incidencia
    
    Retorna:
    - Diccionario con 'success' (bool) y 'message' (str)
    """
    
    # Verificar que el técnico tiene email
    if not incidencia.tecnico_responsable.email:
        return {
            'success': False,
            'message': f'El técnico {incidencia.tecnico_responsable.nombre_completo} no tiene email registrado'
        }
    
    # Lista de destinatarios
    destinatarios = []
    emails_destinatarios = []
    
    # 1. Destinatario principal: el técnico responsable
    email_tecnico = incidencia.tecnico_responsable.email.strip().lower()
    destinatarios.append({
        'nombre': incidencia.tecnico_responsable.nombre_completo,
        'email': email_tecnico,
        'rol': 'Técnico Responsable'
    })
    emails_destinatarios.append(email_tecnico)
    
    # 2. Obtener destinatarios del historial de notificaciones manuales
    destinatarios_historicos = obtener_destinatarios_historicos(incidencia)
    
    for dest_hist in destinatarios_historicos:
        email_hist = dest_hist['email'].strip().lower()
        
        # Solo agregar si no está ya en la lista (evitar duplicados)
        if email_hist not in emails_destinatarios:
            destinatarios.append(dest_hist)
            emails_destinatarios.append(email_hist)
    
    # Asunto según si es atribuible o no
    if incidencia.es_atribuible:
        asunto = f"[CERRADA] {incidencia.folio} - Incidencia Cerrada"
        tipo_notif = 'cierre'
        template = 'scorecard/emails/cierre_incidencia.html'
    else:
        asunto = f"[INFO] {incidencia.folio} - Conclusión Final (No Atribuible)"
        tipo_notif = 'cierre_no_atribuible'
        template = 'scorecard/emails/cierre_no_atribuible.html'
    
    # Contexto para el template
    context = {
        'incidencia': incidencia,
        'tecnico': incidencia.tecnico_responsable,
        'mensaje_adicional': mensaje_adicional,
        'enviado_por': enviado_por,
        'fecha_cierre': incidencia.fecha_cierre or timezone.now(),
        'es_atribuible': incidencia.es_atribuible,
        'destinatarios_adicionales': len(destinatarios) - 1  # Todos menos el técnico
    }
    
    try:
        # Renderizar template HTML
        html_content = render_to_string(template, context)
        
        # Crear email con todos los destinatarios
        email = EmailMultiAlternatives(
            subject=asunto,
            body=f"Incidencia {incidencia.folio} - Cerrada",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=emails_destinatarios  # Lista completa de emails
        )
        
        # Adjuntar versión HTML
        email.attach_alternative(html_content, "text/html")
        
        # Enviar
        email.send(fail_silently=False)
        
        # Mensaje de éxito
        mensaje_exito = f'Notificación enviada a {len(emails_destinatarios)} destinatario(s)'
        if len(destinatarios) > 1:
            mensaje_exito += f' (incluye {len(destinatarios) - 1} del historial)'
        
        # Registrar en base de datos
        from .models import NotificacionIncidencia
        NotificacionIncidencia.objects.create(
            incidencia=incidencia,
            tipo_notificacion=tipo_notif,
            destinatarios_json=json.dumps(destinatarios, ensure_ascii=False),
            asunto=asunto,
            enviado_exitoso=True
        )
        
        return {
            'success': True,
            'message': mensaje_exito
        }
        
    except Exception as e:
        # Registrar error en base de datos
        from .models import NotificacionIncidencia
        NotificacionIncidencia.objects.create(
            incidencia=incidencia,
            tipo_notificacion=tipo_notif,
            destinatarios_json=json.dumps(destinatarios, ensure_ascii=False),
            asunto=asunto,
            enviado_exitoso=False,
            mensaje_error=str(e)
        )
        
        return {
            'success': False,
            'message': f'Error al enviar notificación: {str(e)}'
        }
