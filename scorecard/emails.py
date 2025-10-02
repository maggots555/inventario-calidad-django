"""
Lógica de envío de emails para notificaciones de Score Card
Este módulo maneja todo lo relacionado con el envío de notificaciones por correo electrónico
"""
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
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
    
    # Obtener evidencias (máximo 3 para no saturar el email)
    evidencias = incidencia.evidencias.all()[:3]
    
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
    - Técnico: {incidencia.tecnico_responsable.nombre_completo}
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
            destinatarios=json.dumps(destinatarios_seleccionados, ensure_ascii=False),
            asunto=asunto,
            mensaje_adicional=mensaje_adicional,
            enviado_por=enviado_por,
            exitoso=True,
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
            destinatarios=json.dumps(destinatarios_seleccionados, ensure_ascii=False),
            asunto=asunto,
            mensaje_adicional=mensaje_adicional,
            enviado_por=enviado_por,
            exitoso=False,
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
            'seleccionado_default': True
        })
        
        # 2. Jefe directo del técnico (opcional)
        if incidencia.tecnico_responsable.jefe_directo and incidencia.tecnico_responsable.jefe_directo.email:
            destinatarios.append({
                'nombre': incidencia.tecnico_responsable.jefe_directo.nombre_completo,
                'email': incidencia.tecnico_responsable.jefe_directo.email,
                'rol': 'Jefe Directo',
                'seleccionado_default': True
            })
    
    # 3. Inspector de calidad (opcional)
    # El inspector es un CharField, no ForeignKey, así que no tiene email directo
    # Se podría buscar por nombre si existe como empleado
    
    # 4. Jefe de Calidad (opcional, desde settings)
    destinatarios.append({
        'nombre': settings.JEFE_CALIDAD_NOMBRE,
        'email': settings.JEFE_CALIDAD_EMAIL,
        'rol': 'Inspector de Calidad',
        'seleccionado_default': True
    })
    
    return destinatarios
