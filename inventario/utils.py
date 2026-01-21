"""
Utilidades para gestión de acceso de empleados al sistema

EXPLICACIÓN PARA PRINCIPIANTES:
Este archivo contiene funciones "helper" (ayudantes) que realizan
tareas específicas relacionadas con la creación de usuarios y envío de emails.
Al ponerlas aquí, evitamos repetir código en las vistas.

Funciones principales:
- generar_contraseña_temporal(): Crea contraseñas aleatorias seguras
- crear_usuario_para_empleado(): Crea usuario de Django para un empleado
- enviar_credenciales_empleado(): Envía email con credenciales de acceso
"""

import secrets
import string
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.template.loader import render_to_string
from django.utils.html import strip_tags


def generar_contraseña_temporal(longitud=12):
    """
    Genera una contraseña aleatoria segura
    
    EXPLICACIÓN:
    - Usa el módulo 'secrets' (más seguro que 'random')
    - Combina letras mayúsculas, minúsculas y números
    - Evita caracteres confusos (0, O, 1, l, I) para facilitar lectura
    
    Args:
        longitud (int): Longitud de la contraseña (por defecto 12)
    
    Returns:
        str: Contraseña aleatoria segura
    
    Ejemplo:
        >>> generar_contraseña_temporal()
        'AbC9xYz3DeF8'
    """
    # Caracteres permitidos (evitamos confusión entre 0/O, 1/l/I)
    caracteres = string.ascii_uppercase + string.ascii_lowercase + string.digits
    caracteres = caracteres.replace('0', '').replace('O', '')
    caracteres = caracteres.replace('1', '').replace('l', '').replace('I', '')
    
    # Generar contraseña aleatoria segura
    contraseña = ''.join(secrets.choice(caracteres) for _ in range(longitud))
    return contraseña


def crear_usuario_para_empleado(empleado, contraseña_temporal=None):
    """
    Crea un usuario de Django para el empleado
    
    EXPLICACIÓN:
    Esta función toma un objeto Empleado y crea su usuario correspondiente
    en el sistema de autenticación de Django. El email del empleado se usa
    como username (nombre de usuario único).
    
    Args:
        empleado: Instancia del modelo Empleado
        contraseña_temporal: Contraseña a asignar (si None, se genera una automática)
    
    Returns:
        tuple: (user, contraseña_temporal) - El usuario creado y su contraseña
    
    Raises:
        ValueError: Si el empleado no tiene email o ya tiene un usuario
    
    Ejemplo de uso:
        >>> empleado = Empleado.objects.get(id=1)
        >>> user, password = crear_usuario_para_empleado(empleado)
        >>> print(f"Usuario creado: {user.username}, Contraseña: {password}")
    """
    # Validaciones de seguridad
    if not empleado.email:
        raise ValueError("El empleado debe tener un email para crear su usuario")
    
    if empleado.user:
        raise ValueError(f"El empleado {empleado.nombre_completo} ya tiene un usuario asignado")
    
    # Verificar que no exista otro usuario con ese email
    if User.objects.filter(username=empleado.email).exists():
        raise ValueError(f"Ya existe un usuario con el email {empleado.email}")
    
    # Generar contraseña si no se proporcionó
    if not contraseña_temporal:
        contraseña_temporal = generar_contraseña_temporal()
    
    # Separar nombre completo en first_name y last_name para el usuario
    # Ejemplo: "Juan Pérez López" → first_name="Juan", last_name="Pérez López"
    nombres = empleado.nombre_completo.split()
    first_name = nombres[0] if nombres else ''
    last_name = ' '.join(nombres[1:]) if len(nombres) > 1 else ''
    
    # Crear usuario de Django
    # Django automáticamente encripta la contraseña con create_user
    user = User.objects.create_user(
        username=empleado.email,  # El email es el username
        email=empleado.email,
        password=contraseña_temporal,  # Django la encripta automáticamente con hash
        first_name=first_name,
        last_name=last_name,
        is_active=True,  # Usuario activo desde el inicio
        is_staff=False,  # No tiene acceso al admin de Django
        is_superuser=False  # No es superusuario
    )
    
    # Asignar grupo según el rol del empleado
    from django.contrib.auth.models import Group
    
    # Mapeo de roles de empleado a nombres de grupos de Django
    rol_a_grupo = {
        'supervisor': 'Supervisor',
        'inspector': 'Inspector',
        'dispatcher': 'Dispatcher',
        'compras': 'Compras',
        'recepcionista': 'Recepcionista',
        'gerente_operacional': 'Gerente Operacional',
        'gerente_general': 'Gerente General',
        'tecnico': 'Técnico',
        'almacenista': 'Almacenista',
    }
    
    nombre_grupo = rol_a_grupo.get(empleado.rol)
    if nombre_grupo:
        try:
            grupo = Group.objects.get(name=nombre_grupo)
            user.groups.add(grupo)
        except Group.DoesNotExist:
            print(f"⚠️  Advertencia: No existe el grupo '{nombre_grupo}'. Ejecutar script setup_grupos_permisos.py")
    
    # Vincular el usuario al empleado y actualizar campos de control
    empleado.user = user
    empleado.tiene_acceso_sistema = True
    empleado.fecha_envio_credenciales = timezone.now()
    empleado.contraseña_configurada = False  # Debe cambiarla en primer acceso
    empleado.save()
    
    return user, contraseña_temporal


def enviar_credenciales_empleado(empleado, contraseña_temporal, es_reenvio=False):
    """
    Envía email al empleado con sus credenciales de acceso
    
    EXPLICACIÓN:
    Usa el sistema de email ya configurado en settings.py (SMTP) para enviar
    un correo HTML profesional con las credenciales del empleado.
    
    Args:
        empleado: Instancia del modelo Empleado
        contraseña_temporal: Contraseña temporal generada
        es_reenvio: Si es True, cambia el texto del email (default: False)
    
    Returns:
        tuple: (bool, str) - (True/False si se envió, mensaje de error si falló)
    
    Ejemplo de uso:
        >>> empleado = Empleado.objects.get(id=1)
        >>> exito, error = enviar_credenciales_empleado(empleado, "AbC123XyZ", es_reenvio=False)
        >>> if exito:
        ...     print("Email enviado correctamente")
        ... else:
        ...     print(f"Error: {error}")
    """
    try:
        # VALIDACIÓN 1: Verificar que existe configuración de email
        if not settings.EMAIL_HOST_USER:
            mensaje_error = "❌ EMAIL_HOST_USER no está configurado en archivo .env"
            print(mensaje_error)
            return False, mensaje_error
        
        if not settings.EMAIL_HOST_PASSWORD:
            mensaje_error = "❌ EMAIL_HOST_PASSWORD no está configurado en archivo .env"
            print(mensaje_error)
            return False, mensaje_error
        
        # VALIDACIÓN 2: Verificar que el empleado tiene email
        if not empleado.email:
            mensaje_error = f"❌ El empleado {empleado.nombre_completo} no tiene email registrado"
            print(mensaje_error)
            return False, mensaje_error
        
        # Construir URL de login basada en ALLOWED_HOSTS configurado
        # Buscar una IP válida en ALLOWED_HOSTS que no sea '*'
        host = 'localhost'
        for allowed_host in settings.ALLOWED_HOSTS:
            if allowed_host not in ['*', 'localhost', '127.0.0.1'] and '.' in allowed_host:
                host = allowed_host
                break
        
        # Contexto para el template del email
        context = {
            'empleado': empleado,
            'contraseña_temporal': contraseña_temporal,
            'usuario': empleado.email,
            'es_reenvio': es_reenvio,
            'nombre_sistema': 'Sistema Integral de Gestión SIGMA',
            'url_login': 'https://sigmasystem.work/login/',
            'url_sistema': 'https://sigmasystem.work',
        }
        
        # Renderizar template HTML del email
        html_message = render_to_string('emails/credenciales_iniciales.html', context)
        plain_message = strip_tags(html_message)  # Versión texto plano (fallback)
        
        # Asunto del email
        asunto = '¡Bienvenido al Sistema Integral de Gestión!' if not es_reenvio else 'Credenciales de Acceso - Reenvío'
        
        # MENSAJE DE DEBUG: Mostrar información antes de enviar
        print(f"\n📧 Intentando enviar email:")
        print(f"  - Destinatario: {empleado.email}")
        print(f"  - Servidor SMTP: {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")
        print(f"  - Usuario SMTP: {settings.EMAIL_HOST_USER}")
        print(f"  - Remitente: {settings.DEFAULT_FROM_EMAIL}")
        
        # Remitente personalizado para este correo específico
        from_email_personalizado = f'SIGMA <{settings.EMAIL_HOST_USER}>'
        
        # Enviar email usando configuración SMTP de settings.py
        send_mail(
            subject=asunto,
            message=plain_message,
            from_email=from_email_personalizado,
            recipient_list=[empleado.email],
            html_message=html_message,
            fail_silently=False,  # Lanza excepción si hay error (para detectarlo)
        )
        
        print(f"✅ Email enviado correctamente a {empleado.email}")
        
        # Actualizar fecha de envío
        empleado.fecha_envio_credenciales = timezone.now()
        empleado.save()
        
        return True, None
        
    except Exception as e:
        # Capturar el error específico con información detallada
        tipo_error = type(e).__name__
        mensaje_error = str(e)
        
        # Mensajes de ayuda según el tipo de error
        error_detallado = f"{tipo_error}: {mensaje_error}"
        
        print(f"\n❌ ERROR al enviar email a {empleado.email}:")
        print(f"   {error_detallado}")
        
        # Proporcionar sugerencias según el tipo de error
        if "Authentication" in mensaje_error or "Username and Password not accepted" in mensaje_error:
            print("   💡 Sugerencia: Verifica tu EMAIL_HOST_USER y EMAIL_HOST_PASSWORD en .env")
            print("   💡 Si usas Gmail, asegúrate de usar una 'Contraseña de aplicación', no tu contraseña normal")
        elif "Connection" in mensaje_error or "timed out" in mensaje_error:
            print("   💡 Sugerencia: Problema de conexión. Verifica tu internet o firewall")
        elif "SMTPServerDisconnected" in tipo_error:
            print("   💡 Sugerencia: El servidor SMTP cerró la conexión. Verifica EMAIL_HOST y EMAIL_PORT")
        elif "SMTPRecipientsRefused" in tipo_error:
            print("   💡 Sugerencia: El email del destinatario fue rechazado. Verifica que sea válido")
        
        return False, error_detallado


def validar_email_empleado(email, empleado_actual=None):
    """
    Valida que el email no esté en uso por otro empleado
    
    Args:
        email: Email a validar
        empleado_actual: Instancia del empleado actual (para excluirlo de la búsqueda)
    
    Returns:
        tuple: (es_valido: bool, mensaje_error: str)
    
    Ejemplo:
        >>> es_valido, mensaje = validar_email_empleado('juan@empresa.com')
        >>> if not es_valido:
        ...     print(mensaje)
    """
    from .models import Empleado
    
    if not email:
        return True, ""  # Email vacío es válido (opcional)
    
    # Buscar si existe otro empleado con ese email
    empleados_con_email = Empleado.objects.filter(email=email)
    
    # Si estamos editando, excluir el empleado actual
    if empleado_actual:
        empleados_con_email = empleados_con_email.exclude(id=empleado_actual.id)
    
    if empleados_con_email.exists():
        empleado_existente = empleados_con_email.first()
        nombre = empleado_existente.nombre_completo if empleado_existente else "otro empleado"
        return False, f"Este email ya está siendo usado por {nombre}"
    
    # Verificar si hay un User con ese email (sin Empleado asociado)
    if User.objects.filter(email=email).exists():
        user_existente = User.objects.get(email=email)
        if not hasattr(user_existente, 'empleado'):
            return False, f"Este email ya está registrado en el sistema"
    
    return True, ""
