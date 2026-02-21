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
