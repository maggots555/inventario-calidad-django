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
    list_display = (
        'fecha_movimiento', 'producto', 'tipo', 'cantidad_display_admin', 'motivo', 'destinatario',
        'stock_posterior', 'cantidad_fraccionaria_resultante_display', 'porcentaje_resultante_display',
        'usuario_registro'
    )
    list_filter = ('tipo', 'motivo', 'es_movimiento_fraccionario', 'fecha_movimiento', 'sucursal_destino')
    search_fields = ('producto__nombre', 'producto__codigo_qr', 'destinatario', 'area_destino', 'usuario_registro', 'unidad_utilizada')
    ordering = ['-fecha_movimiento']
    readonly_fields = ('stock_anterior', 'stock_posterior', 'fecha_movimiento', 'cantidad_fraccionaria_resultante', 'porcentaje_resultante')
    
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
            'fields': ('stock_anterior', 'stock_posterior', 'cantidad_fraccionaria_resultante', 'porcentaje_resultante'),
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

    def cantidad_fraccionaria_resultante_display(self, obj):
        """Muestra la cantidad fraccionaria resultante (histórica) de forma amigable"""
        if obj.cantidad_fraccionaria_resultante is None:
            return '-'
        try:
            return f"{obj.cantidad_fraccionaria_resultante:.1f} {obj.producto.unidad_base}"
        except Exception:
            return str(obj.cantidad_fraccionaria_resultante)
    cantidad_fraccionaria_resultante_display.short_description = 'Restante (post)'

    def porcentaje_resultante_display(self, obj):
        if obj.porcentaje_resultante is None:
            return '-'
        try:
            return f"{obj.porcentaje_resultante:.0f}%"
        except Exception:
            return str(obj.porcentaje_resultante)
    porcentaje_resultante_display.short_description = 'Porcentaje (post)'


@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ('nombre_completo', 'cargo', 'area', 'rol', 'sucursal', 'jefe_directo', 'email', 'tiene_foto', 'estado_acceso_display', 'activo', 'fecha_ingreso')
    list_filter = ('area', 'cargo', 'rol', 'sucursal', 'activo', 'tiene_acceso_sistema', 'contraseña_configurada', 'fecha_ingreso')
    search_fields = ('nombre_completo', 'cargo', 'area', 'email')
    ordering = ['nombre_completo']
    readonly_fields = ('fecha_ingreso', 'fecha_actualizacion', 'user', 'tiene_acceso_sistema', 'fecha_envio_credenciales', 'contraseña_configurada', 'fecha_activacion_acceso', 'preview_foto')
    
    fieldsets = (
        ('Información Personal', {
            'fields': ('nombre_completo', 'cargo', 'area', 'email', 'numero_whatsapp', 'foto_perfil', 'preview_foto')
        }),
        ('Ubicación y Jerarquía', {
            'fields': ('sucursal', 'jefe_directo', 'rol'),
            'description': 'Sucursal donde trabaja el empleado, su jefe directo y rol en el sistema'
        }),
        ('Acceso al Sistema', {
            'fields': ('user', 'tiene_acceso_sistema', 'contraseña_configurada', 'fecha_envio_credenciales', 'fecha_activacion_acceso'),
            'description': 'Información sobre el acceso del empleado al Sistema Integral de Gestión. Estos campos se gestionan automáticamente desde la interfaz de empleados.',
            'classes': ('collapse',)
        }),
        ('Estado', {
            'fields': ('activo',)
        }),
        ('Fechas', {
            'fields': ('fecha_ingreso', 'fecha_actualizacion'),
            'classes': ('collapse',)
        }),
    )
    
    def tiene_foto(self, obj):
        """
        Muestra un ícono indicando si el empleado tiene foto de perfil
        """
        if obj.foto_perfil:
            return '✅ Sí'
        return '❌ No'
    tiene_foto.short_description = 'Foto'
    
    def preview_foto(self, obj):
        """
        Muestra una vista previa de la foto de perfil en el admin
        """
        if obj.foto_perfil:
            from django.utils.html import format_html
            return format_html(
                '<img src="{}" style="max-width: 150px; max-height: 150px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);" />',
                obj.foto_perfil.url
            )
        return "Sin foto de perfil"
    preview_foto.short_description = 'Vista previa de foto'
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        Personaliza el campo jefe_directo para mostrar solo empleados activos
        y evitar que un empleado sea su propio jefe
        """
        if db_field.name == "jefe_directo":
            kwargs["queryset"] = Empleado.objects.filter(activo=True).order_by('nombre_completo')
        if db_field.name == "sucursal":
            kwargs["queryset"] = Sucursal.objects.filter(activa=True).order_by('nombre')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
