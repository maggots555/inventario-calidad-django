"""
Modelo de Notificaciones para tareas Celery.

EXPLICACIÓN PARA PRINCIPIANTES:
Este archivo define la tabla 'Notificacion' en la base de datos.
Cada vez que una tarea de Celery termina (con éxito o con error),
se crea un registro aquí usando las funciones helper de utils.py.

El panel de notificaciones (la campanita 🔔 en el navbar) lee esta tabla
para mostrar al usuario qué tareas terminaron.

Campos principales:
- titulo   : Texto corto que describe la notificación (ej: "Correo RHITSO enviado")
- mensaje  : Texto largo con detalles (ej: "Orden ST-001, enviado a 3 destinatarios")
- tipo     : Categoría visual (exito=verde, error=rojo, warning=amarillo, info=azul)
- leida    : Si el usuario ya la vio (True) o no (False)
- usuario  : Quién debe ver esta notificación (el que disparó la tarea)
- task_id  : ID de la tarea Celery (para rastreo técnico)
- app_origen: De qué módulo viene (ej: "servicio_tecnico")
"""

from django.db import models
from django.contrib.auth.models import User


class Notificacion(models.Model):
    """
    Notificación generada por tareas Celery (correos, PDFs, etc.).
    Se muestra en la campanita 🔔 del navbar.
    """

    # ── Tipos de notificación (determinan icono y color) ──
    TIPO_CHOICES = [
        ('exito',   'Éxito'),
        ('error',   'Error'),
        ('warning', 'Advertencia'),
        ('info',    'Información'),
    ]

    titulo = models.CharField(
        max_length=200,
        verbose_name="Título",
        help_text="Texto corto que aparece en la campanita"
    )
    mensaje = models.TextField(
        verbose_name="Mensaje detallado",
        help_text="Descripción extendida de lo que pasó"
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='info',
        verbose_name="Tipo",
        help_text="Determina el icono y color de la notificación"
    )
    leida = models.BooleanField(
        default=False,
        verbose_name="Leída",
        help_text="Se marca True cuando el usuario abre el panel de notificaciones"
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )

    # ── Destinatario ──
    # EXPLICACIÓN: ForeignKey crea una relación entre esta tabla y la tabla User.
    # null=True permite notificaciones "globales" (sin usuario específico).
    # on_delete=CASCADE significa: si se borra el usuario, se borran sus notificaciones.
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notificaciones',
        verbose_name="Usuario destinatario",
        help_text="Quién debe ver esta notificación (vacío = global)"
    )

    # ── Datos de la tarea Celery ──
    task_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="ID de tarea Celery",
        help_text="Identificador único de la tarea en Celery/Redis"
    )
    app_origen = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="App origen",
        help_text="Módulo Django que generó la notificación (ej: servicio_tecnico)"
    )

    # ── URL de destino (opcional) ──
    # EXPLICACIÓN: Si se rellena este campo, al hacer clic en la notificación
    # de la campanita el usuario navega a esa URL. Útil para llevar al técnico
    # directamente a la orden o recurso relacionado con la notificación.
    url = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="URL de destino",
        help_text="Si se especifica, al pulsar la notificación el usuario navega a esta URL"
    )

    class Meta:
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"
        ordering = ['-fecha_creacion']
        indexes = [
            # EXPLICACIÓN: Los índices aceleran las consultas más frecuentes.
            # El panel consulta notificaciones por usuario + no leídas constantemente.
            models.Index(fields=['usuario', '-fecha_creacion'], name='idx_notif_usuario_fecha'),
            models.Index(fields=['usuario', 'leida'], name='idx_notif_usuario_leida'),
        ]

    def __str__(self):
        """Representación en texto para el admin de Django y debugging."""
        return f"[{self.get_tipo_display()}] {self.titulo}"


class PushSubscription(models.Model):
    """
    Suscripción Web Push de un usuario.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Cuando el usuario acepta recibir notificaciones push en su navegador,
    el navegador nos da tres datos únicos de ese dispositivo+navegador:
    - endpoint : URL del servidor de push (Google, Mozilla, Apple...)
    - p256dh   : Clave pública de cifrado del navegador
    - auth     : Token secreto de autenticación

    Con esos tres datos podemos enviar notificaciones incluso cuando
    el usuario no tiene el sitio abierto, siempre que el dispositivo
    tenga internet.

    Un usuario puede tener varias suscripciones activas a la vez
    (teléfono + computadora + tablet).
    """

    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='push_subscriptions',
        verbose_name="Usuario",
        help_text="Usuario dueño de esta suscripción",
    )
    endpoint = models.TextField(
        verbose_name="Endpoint",
        help_text="URL del servidor push del navegador (Google/Mozilla/Apple)",
    )
    p256dh = models.TextField(
        verbose_name="Clave pública (p256dh)",
        help_text="Clave pública de cifrado del navegador",
    )
    auth = models.TextField(
        verbose_name="Auth secret",
        help_text="Token secreto de autenticación del navegador",
    )
    activa = models.BooleanField(
        default=True,
        verbose_name="Activa",
        help_text="False si el usuario desactivó las notificaciones o la suscripción expiró",
    )
    fecha_creada = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de suscripción",
    )
    user_agent = models.CharField(
        max_length=300,
        blank=True,
        verbose_name="User Agent",
        help_text="Navegador y dispositivo del usuario (informativo)",
    )

    class Meta:
        verbose_name = "Suscripción Push"
        verbose_name_plural = "Suscripciones Push"
        ordering = ['-fecha_creada']
        # Un endpoint es único por usuario — evita duplicados si se suscribe dos veces
        # desde el mismo navegador
        unique_together = [('usuario', 'endpoint')]
        indexes = [
            models.Index(fields=['usuario', 'activa'], name='idx_push_usuario_activa'),
        ]

    def __str__(self):
        return f"Push [{self.usuario.username}] — {'activa' if self.activa else 'inactiva'}"


class PushSubscriptionCliente(models.Model):
    """
    Suscripción Web Push de un CLIENTE FINAL (sin cuenta de usuario Django).

    EXPLICACIÓN PARA PRINCIPIANTES:
    Este modelo es el "hermano" de PushSubscription, pero para clientes.
    La diferencia clave: un empleado se identifica con su cuenta (usuario),
    pero un cliente que consulta '/seguimiento/<token>/' NO tiene cuenta en
    el sistema — solo existe el 'token' único de su enlace de seguimiento.

    Por eso, en vez de una ForeignKey a User, usamos una ForeignKey a
    'EnlaceSeguimientoCliente' (de la app servicio_tecnico). Así sabemos
    exactamente a qué orden pertenece cada suscripción, sin necesidad de
    inventar un sistema de cuentas para clientes.

    Se usa un modelo SEPARADO de PushSubscription (y no se le agrega un
    campo nullable a ese modelo) para no tocar la lógica de push existente
    de empleados, que es sensible y ya está en producción.
    """

    enlace = models.ForeignKey(
        'servicio_tecnico.EnlaceSeguimientoCliente',
        on_delete=models.CASCADE,
        related_name='push_subscriptions',
        verbose_name="Enlace de seguimiento",
        help_text="Enlace (token) del cliente dueño de esta suscripción",
    )
    endpoint = models.TextField(
        verbose_name="Endpoint",
        help_text="URL del servidor push del navegador (Google/Mozilla/Apple)",
    )
    p256dh = models.TextField(
        verbose_name="Clave pública (p256dh)",
        help_text="Clave pública de cifrado del navegador",
    )
    auth = models.TextField(
        verbose_name="Auth secret",
        help_text="Token secreto de autenticación del navegador",
    )
    activa = models.BooleanField(
        default=True,
        verbose_name="Activa",
        help_text="False si el cliente desactivó las notificaciones o la suscripción expiró",
    )
    fecha_creada = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de suscripción",
    )
    user_agent = models.CharField(
        max_length=300,
        blank=True,
        verbose_name="User Agent",
        help_text="Navegador y dispositivo del cliente (informativo)",
    )

    class Meta:
        verbose_name = "Suscripción Push de Cliente"
        verbose_name_plural = "Suscripciones Push de Clientes"
        ordering = ['-fecha_creada']
        # Un mismo endpoint no puede repetirse para el mismo enlace — evita
        # duplicados si el cliente se suscribe dos veces desde el mismo navegador.
        unique_together = [('enlace', 'endpoint')]
        indexes = [
            models.Index(fields=['enlace', 'activa'], name='idx_push_cli_enlace_activa'),
        ]

    def __str__(self):
        return f"Push cliente [{self.enlace.token[:8]}...] — {'activa' if self.activa else 'inactiva'}"
