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
from .models import Notificacion


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'tipo', 'usuario', 'leida', 'app_origen', 'fecha_creacion')
    list_filter = ('tipo', 'leida', 'app_origen', 'fecha_creacion')
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
