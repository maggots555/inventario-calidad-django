"""
Utilidades para gestión de acceso de empleados al sistema

EXPLICACIÓN PARA PRINCIPIANTES:
Este archivo contiene funciones "helper" (ayudantes) que realizan
tareas específicas relacionadas con la creación de usuarios y envío de emails.
Al ponerlas aquí, evitamos repetir código en las vistas.

Funciones principales:
- ROL_A_GRUPO: diccionario único rol de empleado → nombre del Group de Django
- generar_contraseña_temporal(): Crea contraseñas aleatorias seguras
- crear_usuario_para_empleado(): Crea usuario de Django para un empleado
- enviar_credenciales_empleado(): Envía email con credenciales de acceso
- sincronizar_grupo_empleado(): Alinea el Group del User con Empleado.rol
"""

import secrets
import string
from django.contrib.auth.models import Group, User
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils import timezone
from django.template.loader import render_to_string

# EXPLICACIÓN PARA PRINCIPIANTES:
# El empleado guarda el rol en minúsculas ('tecnico', 'facturacion').
# Django Groups usa el nombre visible ('Técnico', 'Facturación').
# Este diccionario es la ÚNICA fuente: crear usuario, sincronizar y scripts
# de asignación lo leen de aquí. Si agregas un rol, agrégalo también en
# Empleado.ROL_CHOICES y en scripts/setup_grupos_permisos.py.
ROL_A_GRUPO = {
    'supervisor': 'Supervisor',
    'inspector': 'Inspector',
    'dispatcher': 'Dispatcher',
    'compras': 'Compras',
    'recepcionista': 'Recepcionista',
    'gerente_operacional': 'Gerente Operacional',
    'gerente_general': 'Gerente General',
    'tecnico': 'Técnico',
    'almacenista': 'Almacenista',
    'facturacion': 'Facturación',
}


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
    
    # Asignar grupo según el rol del empleado (fuente única: ROL_A_GRUPO).
    nombre_grupo = ROL_A_GRUPO.get(empleado.rol)
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


def construir_texto_plano_credenciales(context: dict) -> str:
    """
    Arma el cuerpo text/plain del correo de credenciales iniciales.

    Objetivo de negocio:
        Si la bandeja no muestra el HTML, el empleado igual lee su
        usuario, la contraseña temporal y la misma URL para entrar.

    Args:
        context: El mismo diccionario que credenciales_iniciales.html.
            Claves: empleado, contraseña_temporal, usuario, es_reenvio,
            nombre_sistema, url_login, url_sistema.

    Returns:
        str: Cuerpo en texto plano, con las mismas frases del HTML.

    Efectos secundarios:
        Ninguno. No envía correo ni toca la base de datos.
    """
    empleado = context['empleado']
    nombre_sistema = context.get('nombre_sistema') or ''
    es_reenvio = bool(context.get('es_reenvio'))

    # El saludo cambia según sea el alta o un reenvío pedido a mano.
    if es_reenvio:
        titulo = 'Reenvío de Credenciales de Acceso'
        cuerpo = (
            'Como solicitaste, te reenviamos tus credenciales de acceso '
            'al Sistema Integral de Gestión.'
        )
    else:
        titulo = '¡Bienvenido al Sistema!'
        cuerpo = (
            '¡Nos complace informarte que se te ha otorgado acceso al '
            'Sistema Integral de Gestión!\n'
            'A partir de ahora podrás acceder a todas las funcionalidades '
            'del sistema usando tus credenciales personales.'
        )

    # Sucursal es opcional: el HTML también la omite si no hay.
    sucursal = getattr(empleado, 'sucursal', None)
    nombre_sucursal = getattr(sucursal, 'nombre', '') if sucursal else ''

    lineas = [
        nombre_sistema,
        titulo,
        '',
        f'Hola {empleado.nombre_completo},',
        cuerpo,
        '',
        'TUS CREDENCIALES DE ACCESO',
        f"Usuario: {context.get('usuario') or ''}",
        f"Contraseña Temporal: {context.get('contraseña_temporal') or ''}",
        '',
        'IMPORTANTE - CAMBIO DE CONTRASEÑA OBLIGATORIO:',
        'Esta contraseña es TEMPORAL y de un solo uso',
        'Al iniciar sesión por primera vez, el sistema te obligará a cambiarla por una contraseña personal segura',
        'No podrás acceder a ninguna función del sistema hasta que cambies tu contraseña',
        'Este proceso es obligatorio por seguridad y solo ocurre una vez',
        'Después de cambiarla, tendrás acceso completo al sistema',
        'Por seguridad, no compartas estas credenciales con nadie',
        '',
        '¿Qué pasará en tu primer inicio de sesión?',
        '1. Ingresarás con tu usuario y contraseña temporal',
        '2. El sistema te redirigirá automáticamente a la página de cambio de contraseña',
        '3. Ingresarás tu contraseña temporal nuevamente (verificación)',
        '4. Crearás tu nueva contraseña personal (mínimo 8 caracteres)',
        '5. ¡Listo! Tendrás acceso completo al sistema',
        '',
        'Acceder al Sistema Ahora:',
        context.get('url_login') or '',
        'Dirección del sistema:',
        context.get('url_sistema') or '',
        '',
        'Información de tu cuenta:',
        f'Email: {empleado.email}',
        f'Cargo: {empleado.cargo}',
        f'Área: {empleado.area}',
    ]
    if nombre_sucursal:
        lineas.append(f'Sucursal: {nombre_sucursal}')

    lineas.extend([
        '',
        '¿Problemas para acceder?',
        'Si tienes dificultades para iniciar sesión o cambiar tu contraseña, contacta al administrador del sistema.',
        '',
        'Recomendaciones de seguridad:',
        'Elige una contraseña fuerte (mínimo 8 caracteres)',
        'Combina letras, números y símbolos',
        'No uses información personal obvia',
        'Cierra sesión cuando termines de trabajar',
        '',
        nombre_sistema,
        'Este es un email automático, por favor no responder.',
    ])
    return '\n'.join(lineas)


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
        
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # Usamos get_pais_actual() para obtener la URL correcta del país activo.
        # Antes estaba hardcodeado 'https://sigmasystem.work' para todos.
        # Ahora cada país tiene su propia url_base (ej: mexico.sigmasystem.work).
        from config.paises_config import get_pais_actual
        _pais = get_pais_actual()
        
        # Contexto para el template del email
        context = {
            'empleado': empleado,
            'contraseña_temporal': contraseña_temporal,
            'usuario': empleado.email,
            'es_reenvio': es_reenvio,
            'nombre_sistema': 'Sistema Integral de Gestión SIGMA',
            'url_login': f"{_pais['url_base']}/login/",
            'url_sistema': _pais['url_base'],
        }
        
        # Renderizar template HTML del email
        html_message = render_to_string('emails/credenciales_iniciales.html', context)
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # El texto plano es el mismo aviso, sin diseño. Si la bandeja
        # bloquea el HTML, el empleado igual ve usuario, contraseña y el enlace.
        plain_message = construir_texto_plano_credenciales(context)
        
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
        
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # send_mail no puede pegar imágenes. EmailMultiAlternatives manda
        # el texto plano Y el HTML, y deja adjuntar el logo de la barra
        # (el HTML dice src="cid:logo_sic_white").
        email_msg = EmailMultiAlternatives(
            subject=asunto,
            body=plain_message,
            from_email=from_email_personalizado,
            to=[empleado.email],
        )
        email_msg.attach_alternative(html_message, 'text/html')
        from servicio_tecnico.services.email_cid_assets import adjuntar_logo_blanco_email
        adjuntar_logo_blanco_email(email_msg, '[CREDENCIALES]')
        email_msg.send(fail_silently=False)
        
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


def sincronizar_grupo_empleado(empleado):
    """
    Sincroniza el grupo del usuario de Django con el rol del empleado

    Args:
        empleado (Empleado): Instancia del empleado a sincronizar

    Efectos secundarios:
        Limpia los grupos actuales del User y deja solo el de ROL_A_GRUPO.

    Proceso:
        1. Valida que el empleado tenga usuario asignado
        2. Obtiene el nombre del grupo según el rol (ROL_A_GRUPO)
        3. Limpia todos los grupos actuales del usuario
        4. Asigna el nuevo grupo correspondiente al rol
    """
    import logging

    logger = logging.getLogger(__name__)

    if not empleado.user:
        return

    nombre_grupo = ROL_A_GRUPO.get(empleado.rol)
    
    if nombre_grupo:
        try:
            grupo = Group.objects.get(name=nombre_grupo)
            empleado.user.groups.clear()
            empleado.user.groups.add(grupo)
            logger.info(f"✅ Grupo sincronizado: {empleado.nombre_completo} → {nombre_grupo}")
        except Group.DoesNotExist:
            logger.warning(f"⚠️ No existe el grupo '{nombre_grupo}'. Ejecutar: python scripts/setup_grupos_permisos.py")
    else:
        empleado.user.groups.clear()
        logger.warning(f"⚠️ Rol '{empleado.rol}' sin grupo mapeado para {empleado.nombre_completo}")
