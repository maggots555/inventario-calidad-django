"""
Configuración del Django Admin para Score Card
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    CategoriaIncidencia, 
    ComponenteEquipo, 
    ServicioRealizado,
    Incidencia, 
    EvidenciaIncidencia, 
    NotificacionIncidencia
)


@admin.register(CategoriaIncidencia)
class CategoriaIncidenciaAdmin(admin.ModelAdmin):
    """
    Administración de Categorías de Incidencias
    """
    list_display = ['nombre', 'color_preview', 'activo', 'fecha_creacion']
    list_filter = ['activo']
    search_fields = ['nombre', 'descripcion']
    ordering = ['nombre']
    
    def color_preview(self, obj):
        """
        Muestra una vista previa del color
        """
        return format_html(
            '<span style="background-color: {}; padding: 5px 15px; border-radius: 3px; color: white;">{}</span>',
            obj.color,
            obj.color
        )
    color_preview.short_description = 'Color'


@admin.register(ComponenteEquipo)
class ComponenteEquipoAdmin(admin.ModelAdmin):
    """
    Administración de Componentes de Equipos
    """
    list_display = ['nombre', 'tipo_equipo', 'activo', 'fecha_creacion']
    list_filter = ['tipo_equipo', 'activo']
    search_fields = ['nombre']
    ordering = ['nombre']


@admin.register(ServicioRealizado)
class ServicioRealizadoAdmin(admin.ModelAdmin):
    """
    Administración de Servicios Realizados
    """
    list_display = ['nombre', 'orden', 'activo', 'fecha_creacion', 'total_incidencias']
    list_filter = ['activo']
    search_fields = ['nombre', 'descripcion']
    ordering = ['orden', 'nombre']
    list_editable = ['orden', 'activo']
    
    def total_incidencias(self, obj):
        """
        Muestra el total de incidencias asociadas a este servicio
        """
        total = obj.incidencias.count()
        return format_html(
            '<span style="background-color: {}; padding: 3px 10px; border-radius: 3px; color: white; font-weight: bold;">{}</span>',
            '#28a745' if total > 0 else '#6c757d',
            total
        )
    total_incidencias.short_description = 'Incidencias'


class EvidenciaIncidenciaInline(admin.TabularInline):
    """
    Inline para gestionar evidencias dentro de la incidencia
    """
    model = EvidenciaIncidencia
    extra = 1
    fields = ['imagen', 'descripcion', 'subido_por']
    readonly_fields = ['fecha_subida']


@admin.register(Incidencia)
class IncidenciaAdmin(admin.ModelAdmin):
    """
    Administración de Incidencias
    """
    list_display = [
        'folio',
        'fecha_deteccion',
        'tipo_equipo',
        'marca',
        'numero_serie',
        'tecnico_responsable',
        'area_tecnico',
        'grado_severidad_badge',
        'estado_badge',
        'dias_abierta'
    ]
    list_filter = [
        'estado',
        'grado_severidad',
        'tipo_equipo',
        'categoria_fallo',
        'sucursal',
        'año',
        'trimestre',
        'es_reincidencia'
    ]
    search_fields = [
        'folio',
        'numero_serie',
        'numero_orden',
        'marca',
        'modelo',
        'descripcion_incidencia',
        'tecnico_responsable__nombre_completo'
    ]
    readonly_fields = [
        'folio',
        'fecha_registro',
        'area_tecnico',
        'año',
        'mes',
        'semana',
        'trimestre',
        'fecha_cierre',
        'dias_abierta'
    ]
    
    fieldsets = (
        ('Identificación', {
            'fields': ('folio', 'fecha_registro', 'fecha_deteccion')
        }),
        ('Información del Equipo', {
            'fields': (
                'tipo_equipo',
                'marca',
                'modelo',
                'numero_serie',
                'numero_orden',
                'servicio_realizado'
            )
        }),
        ('Ubicación y Responsables', {
            'fields': (
                'sucursal',
                'area_detectora',
                'tecnico_responsable',
                'area_tecnico',
                'inspector_calidad'
            )
        }),
        ('Clasificación del Fallo', {
            'fields': (
                'tipo_incidencia',
                'categoria_fallo',
                'grado_severidad',
                'componente_afectado'
            )
        }),
        ('Descripción y Seguimiento', {
            'fields': (
                'descripcion_incidencia',
                'acciones_tomadas',
                'causa_raiz'
            )
        }),
        ('Estado y Reincidencia', {
            'fields': (
                'estado',
                'es_reincidencia',
                'incidencia_relacionada',
                'fecha_cierre'
            )
        }),
        ('Información Calculada (Solo Lectura)', {
            'fields': ('año', 'mes', 'semana', 'trimestre', 'dias_abierta'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [EvidenciaIncidenciaInline]
    
    def save_model(self, request, obj, form, change):
        """
        Sobrescribir save_model para auto-completar el área del técnico
        """
        # Auto-completar área del técnico si existe
        if obj.tecnico_responsable and obj.tecnico_responsable.area:
            obj.area_tecnico = obj.tecnico_responsable.area
        
        super().save_model(request, obj, form, change)
    
    ordering = ['-fecha_registro']
    date_hierarchy = 'fecha_deteccion'
    
    def grado_severidad_badge(self, obj):
        """
        Muestra el grado de severidad con colores
        """
        colors = {
            'critico': '#dc3545',
            'alto': '#fd7e14',
            'medio': '#ffc107',
            'bajo': '#28a745'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            colors.get(obj.grado_severidad, '#6c757d'),
            obj.get_grado_severidad_display()
        )
    grado_severidad_badge.short_description = 'Severidad'
    
    def estado_badge(self, obj):
        """
        Muestra el estado con colores
        """
        colors = {
            'abierta': '#0d6efd',
            'en_revision': '#ffc107',
            'cerrada': '#28a745',
            'reincidente': '#dc3545'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.estado, '#6c757d'),
            obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'


@admin.register(EvidenciaIncidencia)
class EvidenciaIncidenciaAdmin(admin.ModelAdmin):
    """
    Administración de Evidencias
    """
    list_display = [
        'id',
        'incidencia',
        'imagen_preview',
        'descripcion',
        'subido_por',
        'fecha_subida',
        'tamaño_mb'
    ]
    list_filter = ['fecha_subida', 'subido_por']
    search_fields = ['incidencia__folio', 'descripcion']
    readonly_fields = ['fecha_subida', 'imagen_preview_large']
    
    def imagen_preview(self, obj):
        """
        Muestra una miniatura de la imagen
        """
        if obj.imagen:
            return format_html(
                '<img src="{}" style="max-width: 50px; max-height: 50px;" />',
                obj.imagen.url
            )
        return '-'
    imagen_preview.short_description = 'Vista Previa'
    
    def imagen_preview_large(self, obj):
        """
        Muestra una vista previa más grande en el detalle
        """
        if obj.imagen:
            return format_html(
                '<img src="{}" style="max-width: 400px; max-height: 400px;" />',
                obj.imagen.url
            )
        return '-'
    imagen_preview_large.short_description = 'Imagen'


@admin.register(NotificacionIncidencia)
class NotificacionIncidenciaAdmin(admin.ModelAdmin):
    """
    Administración de Notificaciones enviadas
    """
    list_display = [
        'incidencia',
        'asunto',
        'fecha_envio',
        'enviado_por',
        'exitoso_badge',
        'num_destinatarios'
    ]
    list_filter = ['exitoso', 'fecha_envio']
    search_fields = ['incidencia__folio', 'asunto', 'destinatarios']
    readonly_fields = ['fecha_envio']
    ordering = ['-fecha_envio']
    date_hierarchy = 'fecha_envio'
    
    fieldsets = (
        ('Información General', {
            'fields': ('incidencia', 'asunto', 'fecha_envio', 'enviado_por')
        }),
        ('Destinatarios', {
            'fields': ('destinatarios',)
        }),
        ('Contenido', {
            'fields': ('mensaje_adicional',)
        }),
        ('Estado del Envío', {
            'fields': ('exitoso', 'mensaje_error')
        }),
    )
    
    def exitoso_badge(self, obj):
        """
        Muestra el estado del envío con badge de color
        """
        if obj.exitoso:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px;">✓ Exitoso</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 3px 10px; border-radius: 3px;">✗ Fallido</span>'
            )
    exitoso_badge.short_description = 'Estado'
    
    def num_destinatarios(self, obj):
        """
        Cuenta el número de destinatarios en el JSON
        """
        import json
        try:
            destinatarios = json.loads(obj.destinatarios)
            return len(destinatarios)
        except:
            return '-'
    num_destinatarios.short_description = 'Destinatarios'


# Personalización del sitio admin
admin.site.site_header = "Score Card - Control de Calidad"
admin.site.site_title = "Score Card Admin"
admin.site.index_title = "Gestión de Incidencias de Calidad"
