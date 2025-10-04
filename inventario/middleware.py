"""
Middleware para forzar cambio de contraseña en el primer login

EXPLICACIÓN PARA PRINCIPIANTES:
Un middleware es un componente que se ejecuta ANTES de cada vista (view) 
en tu aplicación Django. Es como un "filtro" que intercepta todas las 
peticiones HTTP antes de que lleguen a su destino.

¿Qué hace este middleware?
1. Se ejecuta en cada petición HTTP que recibe el servidor
2. Verifica si el usuario es un empleado con contraseña temporal
3. Si necesita cambiar su contraseña, lo redirige a la página correspondiente
4. Si no, deja que la petición continúe normalmente

¿Por qué usamos middleware y no un decorador?
- Un decorador se pone en cada vista individualmente
- Un middleware se ejecuta AUTOMÁTICAMENTE en TODAS las vistas
- Es más seguro porque no podemos olvidar ponerlo en alguna vista

Flujo de una petición en Django:
Request → [Middlewares] → View → Template → Response
          ↑ Nuestro middleware intercepta aquí
"""

from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages


class ForcePasswordChangeMiddleware:
    """
    Middleware que fuerza a los empleados a cambiar su contraseña temporal
    antes de poder acceder a otras partes del sistema.
    
    CÓMO FUNCIONA:
    1. Se inicializa cuando Django arranca (método __init__)
    2. En cada petición HTTP, se ejecuta el método __call__
    3. Verifica si el usuario necesita cambiar su contraseña
    4. Si es necesario, redirige a la página de cambio de contraseña
    5. Si no, permite que la petición continúe normalmente
    
    EXCEPCIONES (páginas que SÍ se permiten sin cambiar contraseña):
    - /logout/ → Permitir cerrar sesión
    - /cambiar-contraseña-inicial/ → La página donde cambian la contraseña
    - /admin/ → No afectar al panel de administración
    - /static/ y /media/ → Archivos estáticos (CSS, JS, imágenes)
    """
    
    def __init__(self, get_response):
        """
        Inicialización del middleware (se ejecuta UNA VEZ al iniciar Django)
        
        EXPLICACIÓN:
        Cuando Django arranca, crea una instancia de este middleware y le pasa
        una función llamada 'get_response'. Esta función es la que continúa
        procesando la petición después de que nuestro middleware termine.
        
        Args:
            get_response: Función que continúa procesando la petición
        """
        self.get_response = get_response
    
    def __call__(self, request):
        """
        Método que se ejecuta en CADA petición HTTP
        
        EXPLICACIÓN:
        Python permite que un objeto sea "llamable" como si fuera una función.
        Cuando definimos __call__, Django puede ejecutar este middleware
        pasándole el objeto 'request' de cada petición HTTP.
        
        Args:
            request: Objeto HttpRequest con información de la petición actual
                    (usuario, URL, método HTTP, etc.)
        
        Returns:
            HttpResponse: La respuesta HTTP (puede ser redirección o la respuesta normal)
        """
        
        # ===== PASO 1: Verificar si el usuario está autenticado =====
        if not request.user.is_authenticated:
            # Usuario anónimo (no ha iniciado sesión)
            # Dejar pasar la petición normalmente
            return self.get_response(request)
        
        # ===== PASO 2: Excluir usuarios staff/superuser =====
        # Los administradores no pasan por este proceso
        if request.user.is_staff or request.user.is_superuser:
            return self.get_response(request)
        
        # ===== PASO 3: Verificar si el usuario tiene perfil de Empleado =====
        try:
            empleado = request.user.empleado
        except (AttributeError, Exception):
            # El usuario no tiene el atributo 'empleado' o no existe el perfil
            # (puede ser un usuario creado manualmente sin perfil de empleado)
            # Permitir acceso normal
            return self.get_response(request)
        
        # ===== PASO 4: Verificar si ya configuró su contraseña =====
        if empleado.contraseña_configurada:
            # Ya cambió su contraseña, puede acceder normalmente
            return self.get_response(request)
        
        # ===== PASO 5: El empleado necesita cambiar su contraseña =====
        # Obtener la URL actual que el usuario está intentando acceder
        current_path = request.path
        
        # URL de la página de cambio de contraseña
        change_password_url = reverse('cambiar_contraseña_inicial')
        logout_url = reverse('logout')
        
        # ===== PASO 6: Verificar si está en la página de cambio de contraseña =====
        # IMPORTANTE: Verificar PRIMERO antes de redirigir para evitar bucle infinito
        # Normalizar URLs para comparación (manejar codificación URL)
        from urllib.parse import unquote
        current_path_normalized = unquote(current_path)
        change_password_url_normalized = unquote(change_password_url)
        
        if (current_path == change_password_url or 
            current_path_normalized == change_password_url_normalized or
            current_path == change_password_url_normalized):
            # Ya está en la página de cambio de contraseña, permitir acceso
            return self.get_response(request)
        
        # ===== PASO 7: Permitir logout =====
        if current_path == logout_url or current_path.startswith('/logout'):
            return self.get_response(request)
        
        # ===== PASO 8: Permitir archivos estáticos y admin =====
        # También permitir archivos estáticos (CSS, JS, imágenes)
        if current_path.startswith('/static/') or current_path.startswith('/media/'):
            return self.get_response(request)
        
        # Si está intentando acceder al admin, permitirlo (puede ser un caso especial)
        if current_path.startswith('/admin/'):
            return self.get_response(request)
        
        # ===== PASO 9: Redirigir a cambio de contraseña =====
        # El empleado está intentando acceder a cualquier otra página
        # pero necesita cambiar su contraseña primero
        
        # Solo mostrar el mensaje una vez (evitar spam de mensajes)
        # Verificar si ya hay un mensaje pendiente
        from django.contrib.messages import get_messages
        storage = get_messages(request)
        has_warning = any(
            'contraseña temporal' in str(message).lower() 
            for message in storage
        )
        
        if not has_warning:
            messages.warning(
                request,
                '🔐 Por seguridad, debes cambiar tu contraseña temporal '
                'antes de acceder al sistema. '
                'Este proceso es obligatorio solo en tu primer acceso.'
            )
        
        # Redirigir a la página de cambio de contraseña
        return redirect('cambiar_contraseña_inicial')


"""
CÓMO ACTIVAR ESTE MIDDLEWARE:

1. En settings.py, agregar a la lista MIDDLEWARE:

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'inventario.middleware.ForcePasswordChangeMiddleware',  # ← AGREGAR AQUÍ
]

2. Asegurarse de que esté DESPUÉS de AuthenticationMiddleware
   (porque necesitamos que request.user ya esté disponible)

3. Reiniciar el servidor de Django para que tome efecto


DIAGRAMA DE FLUJO:
┌─────────────────────────────────────┐
│ Usuario intenta acceder a una URL  │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│ Middleware intercepta la petición   │
└────────────┬────────────────────────┘
             │
             ▼
        ¿Autenticado?
             │
    ┌────────┴────────┐
    │ No              │ Sí
    ▼                 ▼
┌───────┐      ¿Es staff/superuser?
│ Pasar │             │
└───────┘      ┌──────┴──────┐
               │ Sí          │ No
               ▼             ▼
           ┌───────┐   ¿Tiene empleado?
           │ Pasar │         │
           └───────┘   ┌─────┴─────┐
                       │ No        │ Sí
                       ▼           ▼
                   ┌───────┐  ¿Contraseña
                   │ Pasar │  configurada?
                   └───────┘      │
                            ┌─────┴─────┐
                            │ Sí        │ No
                            ▼           ▼
                        ┌───────┐  ¿URL permitida?
                        │ Pasar │      │
                        └───────┘ ┌────┴────┐
                                  │ Sí      │ No
                                  ▼         ▼
                              ┌───────┐ ┌──────────┐
                              │ Pasar │ │ Redirigir│
                              └───────┘ └──────────┘
"""
