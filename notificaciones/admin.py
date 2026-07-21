"""
Configuración del admin de Django para Notificaciones.

EXPLICACIÓN PARA PRINCIPIANTES:
Este archivo configura cómo se ven las notificaciones en el panel de
administración de Django (/sic-gestion-sistema/).
- list_display: qué columnas se muestran en la tabla
- list_filter: filtros disponibles en la barra lateral
- search_fields: por qué campos se puede buscar
- readonly_fields: campos que no se pueden editar manualmente
"""

from django.contrib import admin
from .models import Notificacion, PushSubscription, PushSubscriptionCliente


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = (
        'titulo',
        'tipo',
        'categoria',
        'usuario',
        'leida',
        'app_origen',
        'fecha_creacion',
    )
    list_filter = ('tipo', 'categoria', 'leida', 'app_origen', 'fecha_creacion')
    search_fields = ('titulo', 'mensaje', 'usuario__username')
    ordering = ['-fecha_creacion']
    readonly_fields = ('fecha_creacion', 'task_id')
    list_per_page = 30

    # EXPLICACIÓN: actions permite seleccionar varias notificaciones y
    # ejecutar una acción masiva (como marcar todas como leídas).
    actions = ['marcar_como_leidas']

    @admin.action(description="Marcar seleccionadas como leídas")
    def marcar_como_leidas(self, request, queryset):
        """Acción masiva para marcar notificaciones como leídas."""
        actualizadas = queryset.update(leida=True)
        self.message_user(request, f"{actualizadas} notificación(es) marcada(s) como leída(s).")


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    """
    EXPLICACIÓN PARA PRINCIPIANTES:
    Aquí se configuran las suscripciones push en el panel admin.
    Cada registro representa un dispositivo/navegador que aceptó recibir
    notificaciones push. Son datos técnicos del navegador — no se editan
    manualmente, por eso están en readonly_fields.
    """

    list_display = ('usuario', 'endpoint_corto', 'activa', 'user_agent', 'fecha_creada')
    list_filter = ('activa', 'fecha_creada')
    search_fields = ('usuario__username', 'user_agent')
    ordering = ['-fecha_creada']
    list_per_page = 30

    # Los datos del navegador (endpoint, claves) son generados por el cliente —
    # no tiene sentido editarlos desde el admin.
    readonly_fields = ('endpoint', 'p256dh', 'auth', 'fecha_creada')

    actions = ['desactivar_suscripciones', 'activar_suscripciones']

    @admin.display(description="Endpoint")
    def endpoint_corto(self, obj):
        """Muestra solo los primeros 60 caracteres del endpoint para no romper la tabla."""
        return obj.endpoint[:60] + "..." if len(obj.endpoint) > 60 else obj.endpoint

    @admin.action(description="Desactivar suscripciones seleccionadas")
    def desactivar_suscripciones(self, request, queryset):
        """Marca las suscripciones seleccionadas como inactivas."""
        actualizadas = queryset.update(activa=False)
        self.message_user(request, f"{actualizadas} suscripción(es) desactivada(s).")

    @admin.action(description="Activar suscripciones seleccionadas")
    def activar_suscripciones(self, request, queryset):
        """Marca las suscripciones seleccionadas como activas."""
        actualizadas = queryset.update(activa=True)
        self.message_user(request, f"{actualizadas} suscripción(es) activada(s).")


@admin.register(PushSubscriptionCliente)
class PushSubscriptionClienteAdmin(admin.ModelAdmin):
    """
    EXPLICACIÓN PARA PRINCIPIANTES:
    Igual que PushSubscriptionAdmin, pero para suscripciones de clientes
    (identificados por el token de su enlace de seguimiento, no por usuario).
    """

    list_display = ('enlace', 'endpoint_corto', 'activa', 'user_agent', 'fecha_creada', 'fecha_desactivada')
    list_filter = ('activa', 'fecha_creada')
    search_fields = ('enlace__token', 'user_agent')
    ordering = ['-fecha_creada']
    list_per_page = 30

    readonly_fields = ('endpoint', 'p256dh', 'auth', 'fecha_creada')

    actions = ['desactivar_suscripciones', 'activar_suscripciones']

    @admin.display(description="Endpoint")
    def endpoint_corto(self, obj):
        """Muestra solo los primeros 60 caracteres del endpoint para no romper la tabla."""
        return obj.endpoint[:60] + "..." if len(obj.endpoint) > 60 else obj.endpoint

    @admin.action(description="Desactivar suscripciones seleccionadas")
    def desactivar_suscripciones(self, request, queryset):
        """Marca las suscripciones seleccionadas como inactivas."""
        actualizadas = queryset.update(activa=False)
        self.message_user(request, f"{actualizadas} suscripción(es) desactivada(s).")

    @admin.action(description="Activar suscripciones seleccionadas")
    def activar_suscripciones(self, request, queryset):
        """Marca las suscripciones seleccionadas como activas."""
        actualizadas = queryset.update(activa=True)
        self.message_user(request, f"{actualizadas} suscripción(es) activada(s).")
