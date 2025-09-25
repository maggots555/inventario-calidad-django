from django.contrib import admin
from .models import Producto, Sucursal, Movimiento, Empleado

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('codigo_qr', 'nombre', 'categoria', 'es_objeto_unico', 'es_fraccionable', 'cantidad', 'nivel_fraccionario', 'stock_bajo', 'estado_calidad', 'fecha_ingreso')
    list_filter = ('categoria', 'tipo', 'es_objeto_unico', 'es_fraccionable', 'estado_calidad', 'fecha_ingreso')
    search_fields = ('codigo_qr', 'nombre', 'descripcion', 'proveedor', 'unidad_base')
    ordering = ['-fecha_ingreso']
    readonly_fields = ('codigo_qr', 'fecha_ingreso', 'fecha_actualizacion')
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('codigo_qr', 'nombre', 'descripcion', 'categoria', 'tipo')
        }),
        ('Control de Inventario', {
            'fields': ('cantidad', 'stock_minimo', 'ubicacion', 'es_objeto_unico')
        }),
        ('Configuración Fraccionaria', {
            'fields': ('es_fraccionable', 'unidad_base', 'cantidad_unitaria', 'cantidad_actual', 'cantidad_minima_alerta'),
            'description': 'Configure estos campos para productos que se pueden consumir en porciones (líquidos, granulados, etc.)'
        }),
        ('Información Comercial', {
            'fields': ('proveedor', 'costo_unitario', 'estado_calidad')
        }),
        ('Fechas', {
            'fields': ('fecha_ingreso', 'fecha_actualizacion'),
            'classes': ('collapse',)
        }),
    )
    
    def stock_bajo(self, obj):
        """Muestra si el producto tiene stock bajo"""
        if obj.es_fraccionable:
            return obj.stock_fraccionario_bajo()
        return obj.stock_bajo()
    stock_bajo.boolean = True
    stock_bajo.short_description = 'Stock Bajo'
    
    def nivel_fraccionario(self, obj):
        """Muestra el nivel del producto fraccionable"""
        if obj.es_fraccionable:
            porcentaje = obj.porcentaje_disponible()
            return f"{obj.cantidad_actual:.1f}/{obj.cantidad_unitaria:.0f} {obj.unidad_base} ({porcentaje:.1f}%)"
        return f"{obj.cantidad} unidades"
    nivel_fraccionario.short_description = 'Nivel Actual'

@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'responsable', 'telefono', 'activa', 'fecha_creacion')
    list_filter = ('activa', 'fecha_creacion')
    search_fields = ('nombre', 'responsable', 'direccion')
    ordering = ['nombre']

@admin.register(Movimiento)
class MovimientoAdmin(admin.ModelAdmin):
    list_display = ('fecha_movimiento', 'producto', 'tipo', 'cantidad_display_admin', 'motivo', 'destinatario', 'usuario_registro')
    list_filter = ('tipo', 'motivo', 'es_movimiento_fraccionario', 'fecha_movimiento', 'sucursal_destino')
    search_fields = ('producto__nombre', 'producto__codigo_qr', 'destinatario', 'area_destino', 'usuario_registro', 'unidad_utilizada')
    ordering = ['-fecha_movimiento']
    readonly_fields = ('stock_anterior', 'stock_posterior', 'fecha_movimiento')
    
    fieldsets = (
        ('Información del Movimiento', {
            'fields': ('producto', 'tipo', 'cantidad', 'motivo')
        }),
        ('Información Fraccionaria', {
            'fields': ('es_movimiento_fraccionario', 'cantidad_fraccionaria', 'unidad_utilizada'),
            'description': 'Para movimientos de productos fraccionables (consumo parcial)'
        }),
        ('Destinatario', {
            'fields': ('destinatario', 'area_destino', 'sucursal_destino')
        }),
        ('Detalles Adicionales', {
            'fields': ('observaciones', 'numero_proyecto', 'usuario_registro')
        }),
        ('Control de Stock', {
            'fields': ('stock_anterior', 'stock_posterior'),
            'classes': ('collapse',)
        }),
        ('Fechas', {
            'fields': ('fecha_movimiento',),
            'classes': ('collapse',)
        }),
    )
    
    def cantidad_display_admin(self, obj):
        """Muestra la cantidad correcta según el tipo de movimiento"""
        if obj.es_movimiento_fraccionario:
            return f"{obj.cantidad_fraccionaria} {obj.unidad_utilizada}"
        return f"{obj.cantidad} unidades"
    cantidad_display_admin.short_description = 'Cantidad'


@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ('nombre_completo', 'cargo', 'area', 'activo', 'fecha_ingreso')
    list_filter = ('area', 'cargo', 'activo', 'fecha_ingreso')
    search_fields = ('nombre_completo', 'cargo', 'area')
    ordering = ['nombre_completo']
    readonly_fields = ('fecha_ingreso', 'fecha_actualizacion')
    
    fieldsets = (
        ('Información Personal', {
            'fields': ('nombre_completo', 'cargo', 'area')
        }),
        ('Estado', {
            'fields': ('activo',)
        }),
        ('Fechas', {
            'fields': ('fecha_ingreso', 'fecha_actualizacion'),
            'classes': ('collapse',)
        }),
    )
