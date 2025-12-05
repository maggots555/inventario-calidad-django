"""
Configuración del Admin para el módulo Almacén.

EXPLICACIÓN PARA PRINCIPIANTES:
-------------------------------
Este archivo configura cómo se ven y comportan los modelos en el panel
de administración de Django (/admin/).

Cada clase Admin define:
- list_display: Columnas visibles en la lista
- list_filter: Filtros en la barra lateral
- search_fields: Campos donde se puede buscar
- ordering: Orden por defecto
- fieldsets: Organización de campos en el formulario
- inlines: Modelos relacionados que se editan junto al principal

Los decoradores @admin.register(Modelo) registran cada modelo.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone

from .models import (
    Proveedor,
    CategoriaAlmacen,
    ProductoAlmacen,
    CompraProducto,
    MovimientoAlmacen,
    SolicitudBaja,
    Auditoria,
    DiferenciaAuditoria,
    UnidadInventario,
    SolicitudCotizacion,
    LineaCotizacion,
    ImagenLineaCotizacion,
)

from config.constants import (
    ESTADO_UNIDAD_CHOICES,
    DISPONIBILIDAD_UNIDAD_CHOICES,
    ORIGEN_UNIDAD_CHOICES,
)


# ============================================================================
# ADMIN: PROVEEDOR
# ============================================================================
@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    """
    Configuración del admin para Proveedores.
    Permite gestionar la lista de proveedores del almacén.
    """
    
    list_display = (
        'nombre',
        'contacto',
        'telefono',
        'email',
        'tiempo_entrega_dias',
        'activo_badge',
        'total_compras',
    )
    
    list_filter = (
        'activo',
        'tiempo_entrega_dias',
    )
    
    search_fields = (
        'nombre',
        'contacto',
        'email',
        'telefono',
    )
    
    ordering = ['nombre']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'activo')
        }),
        ('Datos de Contacto', {
            'fields': ('contacto', 'telefono', 'email', 'direccion')
        }),
        ('Métricas de Servicio', {
            'fields': ('tiempo_entrega_dias', 'notas')
        }),
    )
    
    def activo_badge(self, obj):
        """Muestra badge de color según estado activo"""
        if obj.activo:
            return format_html('<span style="color: green;">✓ Activo</span>')
        return format_html('<span style="color: red;">✗ Inactivo</span>')
    activo_badge.short_description = 'Estado'
    
    def total_compras(self, obj):
        """Muestra el número de compras realizadas a este proveedor"""
        return obj.compras_realizadas.count()
    total_compras.short_description = 'Compras'


# ============================================================================
# ADMIN: CATEGORÍA DE ALMACÉN
# ============================================================================
@admin.register(CategoriaAlmacen)
class CategoriaAlmacenAdmin(admin.ModelAdmin):
    """
    Configuración del admin para Categorías de Almacén.
    """
    
    list_display = (
        'nombre',
        'descripcion_corta',
        'cantidad_productos',
        'activo_badge',
    )
    
    list_filter = ('activo',)
    
    search_fields = ('nombre', 'descripcion')
    
    ordering = ['nombre']
    
    def descripcion_corta(self, obj):
        """Muestra descripción truncada a 50 caracteres"""
        if obj.descripcion:
            return obj.descripcion[:50] + '...' if len(obj.descripcion) > 50 else obj.descripcion
        return '-'
    descripcion_corta.short_description = 'Descripción'
    
    def cantidad_productos(self, obj):
        """Muestra cuántos productos tiene la categoría"""
        return obj.productos.filter(activo=True).count()
    cantidad_productos.short_description = 'Productos'
    
    def activo_badge(self, obj):
        if obj.activo:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    activo_badge.short_description = 'Activa'


# ============================================================================
# INLINE: UNIDADES DE INVENTARIO (para ver en ProductoAlmacen)
# ============================================================================
class UnidadInventarioInline(admin.TabularInline):
    """
    Muestra las unidades individuales dentro del admin de ProductoAlmacen.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Un "inline" permite ver y editar registros relacionados directamente
    dentro del formulario de otro modelo. Aquí, cuando editas un ProductoAlmacen,
    puedes ver todas las unidades individuales (UnidadInventario) que pertenecen
    a ese producto sin tener que ir a otra página.
    
    TabularInline: Muestra los registros en formato de tabla (más compacto)
    StackedInline: Mostraría cada registro apilado (ocupa más espacio)
    """
    
    model = UnidadInventario
    
    # Campos que se muestran en la tabla inline
    fields = (
        'codigo_interno',
        'numero_serie',
        'marca',
        'modelo',
        'estado',
        'disponibilidad',
        'origen',
        'costo_unitario',
    )
    
    # Campos que solo se pueden ver, no editar desde aquí
    readonly_fields = ('codigo_interno',)
    
    # extra = 0 significa que no mostramos filas vacías adicionales por defecto
    # (el usuario puede agregar más si quiere, pero no llenamos la pantalla)
    extra = 0
    
    # Cuántos registros mostrar antes de paginar
    max_num = 50
    
    # Mostrar enlace para ver/editar el registro completo
    show_change_link = True
    
    # Clases CSS para el inline
    classes = ['collapse']  # Colapsable para no abrumar la vista


# ============================================================================
# ADMIN: PRODUCTO DE ALMACÉN
# ============================================================================
@admin.register(ProductoAlmacen)
class ProductoAlmacenAdmin(admin.ModelAdmin):
    """
    Configuración del admin para Productos de Almacén.
    Este es el modelo principal - se configura con más detalle.
    """
    
    list_display = (
        'codigo_producto',
        'nombre',
        'tipo_producto_badge',
        'categoria',
        'stock_badge',
        'unidades_rastreadas',
        'costo_unitario',
        'proveedor_principal',
        'activo_badge',
    )
    
    list_filter = (
        'tipo_producto',
        'categoria',
        'activo',
        'proveedor_principal',
        'sucursal',
    )
    
    search_fields = (
        'codigo_producto',
        'nombre',
        'descripcion',
    )
    
    ordering = ['nombre']
    
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion', 'qr_code')
    
    fieldsets = (
        ('Identificación', {
            'fields': ('codigo_producto', 'nombre', 'descripcion', 'imagen')
        }),
        ('Clasificación', {
            'fields': ('categoria', 'tipo_producto')
        }),
        ('Ubicación', {
            'fields': ('ubicacion_fisica', 'sucursal')
        }),
        ('Stock', {
            'fields': ('stock_actual', 'stock_minimo', 'stock_maximo'),
            'description': 'Stock mínimo y máximo solo aplican para productos resurtibles.'
        }),
        ('Costos y Proveedor', {
            'fields': ('costo_unitario', 'proveedor_principal', 'tiempo_reposicion_dias')
        }),
        ('Estado', {
            'fields': ('activo', 'creado_por')
        }),
        ('Información del Sistema', {
            'fields': ('qr_code', 'fecha_creacion', 'fecha_actualizacion'),
            'classes': ('collapse',)  # Sección colapsable
        }),
    )
    
    def tipo_producto_badge(self, obj):
        """Muestra el tipo con emoji"""
        if obj.tipo_producto == 'resurtible':
            return format_html('<span title="Stock permanente">📦 Resurtible</span>')
        return format_html('<span title="Compra específica">🔧 Único</span>')
    tipo_producto_badge.short_description = 'Tipo'
    
    def stock_badge(self, obj):
        """Muestra el stock con color según nivel"""
        if obj.stock_actual == 0:
            color = 'red'
            texto = f'⚠️ {obj.stock_actual}'
        elif obj.esta_bajo_minimo():
            color = 'orange'
            texto = f'⚡ {obj.stock_actual}'
        else:
            color = 'green'
            texto = str(obj.stock_actual)
        
        if obj.tipo_producto == 'resurtible' and obj.stock_maximo > 0:
            return format_html(
                '<span style="color: {};">{} / {}</span>',
                color, texto, obj.stock_maximo
            )
        return format_html('<span style="color: {};">{}</span>', color, texto)
    stock_badge.short_description = 'Stock'
    
    def activo_badge(self, obj):
        if obj.activo:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    activo_badge.short_description = 'Activo'
    
    def unidades_rastreadas(self, obj):
        """
        Muestra cuántas unidades individuales están rastreadas vs stock total.
        
        EXPLICACIÓN:
        - Si el producto tiene unidades rastreadas, muestra: "5 / 10" (5 rastreadas de 10 en stock)
        - Si no tiene unidades rastreadas, muestra un guion
        """
        if obj.tiene_unidades_rastreadas():
            disponibles = obj.cantidad_unidades_disponibles()
            total = obj.unidades.count()
            return format_html(
                '<span title="{} disponibles de {} rastreadas">📋 {} disp / {} total</span>',
                disponibles, total, disponibles, total
            )
        return format_html('<span style="color: gray;">—</span>')
    unidades_rastreadas.short_description = 'Unidades Rastreadas'
    
    # Incluir el inline de unidades individuales
    inlines = [UnidadInventarioInline]


# ============================================================================
# ADMIN: COMPRA DE PRODUCTO
# ============================================================================
@admin.register(CompraProducto)
class CompraProductoAdmin(admin.ModelAdmin):
    """
    Configuración del admin para Compras de Productos.
    Permite ver y registrar compras realizadas.
    """
    
    list_display = (
        'producto',
        'proveedor',
        'cantidad',
        'costo_unitario',
        'costo_total',
        'fecha_pedido',
        'fecha_recepcion',
        'dias_entrega',
        'orden_servicio',
    )
    
    list_filter = (
        'proveedor',
        'fecha_pedido',
        'fecha_recepcion',
    )
    
    search_fields = (
        'producto__codigo_producto',
        'producto__nombre',
        'proveedor__nombre',
        'numero_factura',
        'numero_orden_compra',
    )
    
    ordering = ['-fecha_recepcion', '-fecha_pedido']
    
    readonly_fields = ('costo_total', 'dias_entrega', 'fecha_registro')
    
    autocomplete_fields = ['producto', 'proveedor', 'orden_servicio']
    
    fieldsets = (
        ('Producto y Proveedor', {
            'fields': ('producto', 'proveedor')
        }),
        ('Cantidades y Costos', {
            'fields': ('cantidad', 'costo_unitario', 'costo_total')
        }),
        ('Fechas', {
            'fields': ('fecha_pedido', 'fecha_recepcion', 'dias_entrega')
        }),
        ('Documentos', {
            'fields': ('numero_factura', 'numero_orden_compra')
        }),
        ('Vinculación', {
            'fields': ('orden_servicio',),
            'classes': ('collapse',)
        }),
        ('Información Adicional', {
            'fields': ('observaciones', 'registrado_por', 'fecha_registro'),
            'classes': ('collapse',)
        }),
    )


# ============================================================================
# ADMIN: MOVIMIENTO DE ALMACÉN
# ============================================================================
@admin.register(MovimientoAlmacen)
class MovimientoAlmacenAdmin(admin.ModelAdmin):
    """
    Configuración del admin para Movimientos de Almacén.
    Muestra el historial de entradas y salidas.
    """
    
    list_display = (
        'tipo_badge',
        'producto',
        'cantidad',
        'costo_unitario',
        'stock_anterior',
        'stock_posterior',
        'empleado',
        'fecha',
        'orden_servicio',
    )
    
    list_filter = (
        'tipo',
        'fecha',
        'empleado',
    )
    
    search_fields = (
        'producto__codigo_producto',
        'producto__nombre',
        'observaciones',
    )
    
    ordering = ['-fecha']
    
    readonly_fields = ('stock_anterior', 'stock_posterior', 'fecha')
    
    fieldsets = (
        ('Movimiento', {
            'fields': ('tipo', 'producto', 'cantidad', 'costo_unitario')
        }),
        ('Responsable', {
            'fields': ('empleado',)
        }),
        ('Vinculaciones', {
            'fields': ('orden_servicio', 'compra', 'solicitud_baja'),
            'classes': ('collapse',)
        }),
        ('Tracking', {
            'fields': ('stock_anterior', 'stock_posterior', 'fecha'),
        }),
        ('Observaciones', {
            'fields': ('observaciones',),
            'classes': ('collapse',)
        }),
    )
    
    def tipo_badge(self, obj):
        """Muestra el tipo con emoji y color"""
        if obj.tipo == 'entrada':
            return format_html('<span style="color: green;">📥 Entrada</span>')
        return format_html('<span style="color: red;">📤 Salida</span>')
    tipo_badge.short_description = 'Tipo'


# ============================================================================
# ADMIN: SOLICITUD DE BAJA
# ============================================================================
@admin.register(SolicitudBaja)
class SolicitudBajaAdmin(admin.ModelAdmin):
    """
    Configuración del admin para Solicitudes de Baja.
    Permite ver y gestionar solicitudes pendientes.
    """
    
    list_display = (
        'id',
        'producto',
        'cantidad',
        'tipo_solicitud',
        'estado_badge',
        'solicitante',
        'fecha_solicitud',
        'agente_almacen',
        'orden_servicio',
    )
    
    list_filter = (
        'estado',
        'tipo_solicitud',
        'fecha_solicitud',
        'requiere_reposicion',
    )
    
    search_fields = (
        'producto__codigo_producto',
        'producto__nombre',
        'solicitante__nombre_completo',
        'observaciones',
    )
    
    ordering = ['-fecha_solicitud']
    
    readonly_fields = ('fecha_solicitud', 'fecha_procesado')
    
    fieldsets = (
        ('Solicitud', {
            'fields': ('tipo_solicitud', 'producto', 'cantidad')
        }),
        ('Solicitante', {
            'fields': ('solicitante', 'fecha_solicitud', 'observaciones')
        }),
        ('Vinculación', {
            'fields': ('orden_servicio',),
            'classes': ('collapse',)
        }),
        ('Estado y Procesamiento', {
            'fields': ('estado', 'agente_almacen', 'fecha_procesado', 'observaciones_agente')
        }),
        ('Flags', {
            'fields': ('requiere_reposicion',)
        }),
    )
    
    def estado_badge(self, obj):
        """Muestra el estado con color"""
        colores = {
            'pendiente': ('orange', '🟡'),
            'aprobada': ('green', '🟢'),
            'rechazada': ('red', '🔴'),
            'en_espera': ('gray', '⏸️'),
        }
        color, emoji = colores.get(obj.estado, ('black', '❓'))
        return format_html(
            '<span style="color: {};">{} {}</span>',
            color, emoji, obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'


# ============================================================================
# INLINE: DIFERENCIAS DE AUDITORÍA
# ============================================================================
class DiferenciaAuditoriaInline(admin.TabularInline):
    """
    Inline para mostrar diferencias dentro de una Auditoría.
    Permite ver y editar diferencias directamente en el detalle de auditoría.
    """
    model = DiferenciaAuditoria
    extra = 0  # No mostrar filas vacías extra
    fields = (
        'producto',
        'stock_sistema',
        'stock_fisico',
        'diferencia',
        'razon',
        'ajuste_realizado',
    )
    readonly_fields = ('diferencia',)
    autocomplete_fields = ['producto']


# ============================================================================
# ADMIN: AUDITORÍA
# ============================================================================
@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    """
    Configuración del admin para Auditorías.
    Incluye inline de diferencias encontradas.
    """
    
    list_display = (
        'id',
        'tipo',
        'estado_badge',
        'sucursal',
        'auditor',
        'fecha_inicio',
        'fecha_fin',
        'total_productos_auditados',
        'total_diferencias_encontradas',
    )
    
    list_filter = (
        'tipo',
        'estado',
        'sucursal',
        'fecha_inicio',
    )
    
    search_fields = (
        'auditor__nombre_completo',
        'observaciones_generales',
    )
    
    ordering = ['-fecha_inicio']
    
    readonly_fields = ('fecha_inicio', 'total_diferencias_encontradas')
    
    inlines = [DiferenciaAuditoriaInline]
    
    fieldsets = (
        ('Información General', {
            'fields': ('tipo', 'estado', 'sucursal')
        }),
        ('Responsable', {
            'fields': ('auditor',)
        }),
        ('Fechas', {
            'fields': ('fecha_inicio', 'fecha_fin')
        }),
        ('Resultados', {
            'fields': ('total_productos_auditados', 'total_diferencias_encontradas', 'observaciones_generales')
        }),
    )
    
    def estado_badge(self, obj):
        """Muestra el estado con color"""
        colores = {
            'en_proceso': ('blue', '🔄'),
            'completada': ('green', '✅'),
            'con_diferencias': ('orange', '⚠️'),
        }
        color, emoji = colores.get(obj.estado, ('black', '❓'))
        return format_html(
            '<span style="color: {};">{} {}</span>',
            color, emoji, obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'


# ============================================================================
# ADMIN: DIFERENCIA DE AUDITORÍA (standalone)
# ============================================================================
@admin.register(DiferenciaAuditoria)
class DiferenciaAuditoriaAdmin(admin.ModelAdmin):
    """
    Configuración del admin para Diferencias de Auditoría.
    Permite ver todas las diferencias de forma independiente.
    """
    
    list_display = (
        'auditoria',
        'producto',
        'stock_sistema',
        'stock_fisico',
        'diferencia_badge',
        'razon',
        'ajuste_badge',
    )
    
    list_filter = (
        'razon',
        'ajuste_realizado',
        'auditoria__sucursal',
    )
    
    search_fields = (
        'producto__codigo_producto',
        'producto__nombre',
        'razon_detalle',
    )
    
    ordering = ['-auditoria__fecha_inicio']
    
    readonly_fields = ('diferencia',)
    
    fieldsets = (
        ('Identificación', {
            'fields': ('auditoria', 'producto')
        }),
        ('Cantidades', {
            'fields': ('stock_sistema', 'stock_fisico', 'diferencia')
        }),
        ('Análisis', {
            'fields': ('razon', 'razon_detalle', 'evidencia')
        }),
        ('Ajuste', {
            'fields': ('ajuste_realizado', 'fecha_ajuste', 'responsable_ajuste', 'acciones_correctivas')
        }),
    )
    
    def diferencia_badge(self, obj):
        """Muestra la diferencia con color según signo"""
        if obj.diferencia > 0:
            return format_html('<span style="color: blue;">+{}</span>', obj.diferencia)
        elif obj.diferencia < 0:
            return format_html('<span style="color: red;">{}</span>', obj.diferencia)
        return format_html('<span style="color: gray;">0</span>')
    diferencia_badge.short_description = 'Diferencia'
    
    def ajuste_badge(self, obj):
        """Muestra si el ajuste fue realizado"""
        if obj.ajuste_realizado:
            return format_html('<span style="color: green;">✓ Ajustado</span>')
        return format_html('<span style="color: orange;">Pendiente</span>')
    ajuste_badge.short_description = 'Ajuste'


# ============================================================================
# ADMIN: UNIDAD DE INVENTARIO
# ============================================================================
@admin.register(UnidadInventario)
class UnidadInventarioAdmin(admin.ModelAdmin):
    """
    Configuración del admin para Unidades Individuales de Inventario.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Este admin permite gestionar cada unidad física individual.
    
    Por ejemplo, si tienes un producto "SSD 1TB" con stock de 20 unidades,
    cada una de esas 20 unidades puede ser registrada aquí con:
    - Su marca específica (Samsung, Kingston, Crucial, etc.)
    - Su modelo específico (870 EVO, A2000, MX500)
    - Su número de serie único
    - Su origen (compra, recuperado de orden de servicio, etc.)
    - Su estado actual (nuevo, usado bueno, para revisión, etc.)
    - Su disponibilidad (disponible, reservada, asignada, vendida)
    
    Esto permite un control muy granular del inventario, especialmente útil
    para componentes de computadora donde cada unidad puede tener diferente
    marca/modelo aunque sea el "mismo producto" conceptualmente.
    """
    
    list_display = (
        'codigo_interno',
        'producto_link',
        'marca',
        'modelo',
        'numero_serie_truncado',
        'estado_badge',
        'disponibilidad_badge',
        'origen_badge',
        'costo_unitario',
        'fecha_registro',
    )
    
    list_filter = (
        'estado',
        'disponibilidad',
        'origen',
        'marca',
        'producto__categoria',
        'producto__tipo_producto',
        'fecha_registro',
    )
    
    search_fields = (
        'codigo_interno',
        'numero_serie',
        'marca',
        'modelo',
        'producto__nombre',
        'producto__codigo_producto',
        'notas',
    )
    
    ordering = ['-fecha_registro', 'producto__nombre', 'marca']
    
    date_hierarchy = 'fecha_registro'  # Navegación por fecha en la parte superior
    
    readonly_fields = (
        'codigo_interno',
        'fecha_registro',
        'fecha_actualizacion',
    )
    
    # Autocompletar para campos de relación (mejora la búsqueda)
    autocomplete_fields = ['producto', 'compra']
    
    fieldsets = (
        ('Identificación', {
            'fields': (
                'codigo_interno',
                'producto',
                'numero_serie',
            ),
            'description': 'Información básica que identifica esta unidad específica.'
        }),
        ('Especificaciones del Item', {
            'fields': (
                'marca',
                'modelo',
                'especificaciones',
            ),
            'description': 'Detalles específicos de esta unidad particular.'
        }),
        ('Estado y Disponibilidad', {
            'fields': (
                'estado',
                'disponibilidad',
            ),
            'description': 'Estado físico y disponibilidad para uso.'
        }),
        ('Origen y Trazabilidad', {
            'fields': (
                'origen',
                'compra',
                'orden_servicio_origen',
                'orden_servicio_destino',
            ),
            'description': 'De dónde vino esta unidad y a dónde fue (si aplica).'
        }),
        ('Ubicación y Costo', {
            'fields': (
                'ubicacion_especifica',
                'costo_unitario',
            ),
        }),
        ('Notas', {
            'fields': ('notas',),
            'classes': ('collapse',),  # Colapsable
        }),
        ('Información del Sistema', {
            'fields': (
                'fecha_registro',
                'fecha_actualizacion',
            ),
            'classes': ('collapse',),
        }),
    )
    
    # -------------------------------------------------------------------------
    # Métodos para personalizar la visualización en la lista
    # -------------------------------------------------------------------------
    
    def producto_link(self, obj):
        """Muestra el producto como enlace clickeable"""
        return format_html(
            '<a href="/admin/almacen/productoalmacen/{}/change/" title="Ver producto">'
            '{}</a>',
            obj.producto.id,
            obj.producto.nombre[:30] + '...' if len(obj.producto.nombre) > 30 else obj.producto.nombre
        )
    producto_link.short_description = 'Producto'
    producto_link.admin_order_field = 'producto__nombre'
    
    def numero_serie_truncado(self, obj):
        """Muestra el número de serie truncado si es muy largo"""
        if obj.numero_serie:
            if len(obj.numero_serie) > 15:
                return format_html(
                    '<span title="{}">{}</span>',
                    obj.numero_serie,
                    obj.numero_serie[:12] + '...'
                )
            return obj.numero_serie
        return format_html('<span style="color: gray;">—</span>')
    numero_serie_truncado.short_description = 'N° Serie'
    numero_serie_truncado.admin_order_field = 'numero_serie'
    
    def estado_badge(self, obj):
        """
        Muestra el estado con colores semánticos.
        
        Colores:
        - Verde: nuevo
        - Azul: usado_bueno, reparado
        - Amarillo: usado_regular, para_revision
        - Rojo: defectuoso
        """
        colores = {
            'nuevo': ('green', '🆕'),
            'usado_bueno': ('blue', '👍'),
            'usado_regular': ('orange', '👌'),
            'reparado': ('teal', '🔧'),
            'defectuoso': ('red', '❌'),
            'para_revision': ('purple', '🔍'),
        }
        color, emoji = colores.get(obj.estado, ('gray', '❓'))
        nombre = obj.get_estado_display()
        return format_html(
            '<span style="color: {};" title="{}">{} {}</span>',
            color, nombre, emoji, nombre
        )
    estado_badge.short_description = 'Estado'
    estado_badge.admin_order_field = 'estado'
    
    def disponibilidad_badge(self, obj):
        """
        Muestra la disponibilidad con colores.
        
        Colores:
        - Verde: disponible
        - Amarillo: reservada
        - Azul: asignada
        - Gris: vendida, descartada
        """
        colores = {
            'disponible': ('green', '✅'),
            'reservada': ('orange', '📌'),
            'asignada': ('blue', '🔗'),
            'vendida': ('gray', '💰'),
            'descartada': ('darkred', '🗑️'),
        }
        color, emoji = colores.get(obj.disponibilidad, ('gray', '❓'))
        nombre = obj.get_disponibilidad_display()
        return format_html(
            '<span style="color: {};" title="{}">{} {}</span>',
            color, nombre, emoji, nombre
        )
    disponibilidad_badge.short_description = 'Disponibilidad'
    disponibilidad_badge.admin_order_field = 'disponibilidad'
    
    def origen_badge(self, obj):
        """Muestra el origen con emoji identificativo"""
        emojis = {
            'compra': '🛒',
            'orden_servicio': '🔧',
            'devolucion_cliente': '↩️',
            'transferencia': '🔄',
            'inventario_inicial': '📋',
            'donacion': '🎁',
            'otro': '❓',
        }
        emoji = emojis.get(obj.origen, '❓')
        nombre = obj.get_origen_display()
        return format_html('<span title="{}">{} {}</span>', nombre, emoji, nombre)
    origen_badge.short_description = 'Origen'
    origen_badge.admin_order_field = 'origen'
    
    # -------------------------------------------------------------------------
    # Acciones personalizadas
    # -------------------------------------------------------------------------
    
    actions = ['marcar_como_disponible', 'marcar_como_defectuoso', 'marcar_para_revision']
    
    @admin.action(description='✅ Marcar seleccionados como Disponible')
    def marcar_como_disponible(self, request, queryset):
        """Marca las unidades seleccionadas como disponibles"""
        updated = queryset.update(disponibilidad='disponible')
        self.message_user(
            request,
            f'{updated} unidad(es) marcada(s) como disponible.',
        )
    
    @admin.action(description='❌ Marcar seleccionados como Defectuoso')
    def marcar_como_defectuoso(self, request, queryset):
        """Marca las unidades seleccionadas como defectuosas"""
        updated = queryset.update(estado='defectuoso', disponibilidad='descartada')
        self.message_user(
            request,
            f'{updated} unidad(es) marcada(s) como defectuosa(s).',
        )
    
    @admin.action(description='🔍 Marcar seleccionados Para Revisión')
    def marcar_para_revision(self, request, queryset):
        """Marca las unidades seleccionadas para revisión"""
        updated = queryset.update(estado='para_revision')
        self.message_user(
            request,
            f'{updated} unidad(es) marcada(s) para revisión.',
        )


# ============================================================================
# ADMIN: SOLICITUD DE COTIZACIÓN (MULTI-PROVEEDOR)
# ============================================================================

class LineaCotizacionInline(admin.TabularInline):
    """
    Inline para editar líneas de cotización dentro de SolicitudCotizacion.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Un "inline" permite editar modelos relacionados directamente dentro
    del formulario del modelo padre. Así puedes ver y editar todas las
    líneas de una solicitud sin cambiar de página.
    """
    model = LineaCotizacion
    extra = 1  # Mostrar 1 formulario vacío por defecto
    
    fields = (
        'numero_linea',
        'producto',
        'descripcion_pieza',
        'proveedor',
        'cantidad',
        'costo_unitario',
        'estado_cliente',
        'compra_generada',
    )
    
    readonly_fields = ('compra_generada',)
    
    autocomplete_fields = ['producto', 'proveedor']


@admin.register(SolicitudCotizacion)
class SolicitudCotizacionAdmin(admin.ModelAdmin):
    """
    Configuración del admin para Solicitudes de Cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Este admin permite:
    - Ver todas las solicitudes de cotización
    - Filtrar por estado, fecha, creador
    - Buscar por número de solicitud u orden cliente
    - Editar solicitudes incluyendo sus líneas (inline)
    """
    
    list_display = (
        'numero_solicitud',
        'numero_orden_cliente',
        'estado_badge',
        'total_lineas_display',
        'costo_total_display',
        'creado_por',
        'fecha_creacion',
    )
    
    list_filter = (
        'estado',
        'fecha_creacion',
        'creado_por',
    )
    
    search_fields = (
        'numero_solicitud',
        'numero_orden_cliente',
        'observaciones',
    )
    
    ordering = ['-fecha_creacion']
    
    readonly_fields = (
        'numero_solicitud',
        'fecha_creacion',
        'fecha_actualizacion',
        'fecha_envio_cliente',
        'fecha_respuesta_cliente',
        'fecha_completada',
    )
    
    autocomplete_fields = ['orden_servicio', 'creado_por']
    
    inlines = [LineaCotizacionInline]
    
    fieldsets = (
        ('Identificación', {
            'fields': ('numero_solicitud', 'estado')
        }),
        ('Vinculación', {
            'fields': ('orden_servicio', 'numero_orden_cliente')
        }),
        ('Observaciones', {
            'fields': ('observaciones', 'observaciones_cliente')
        }),
        ('Auditoría', {
            'fields': (
                'creado_por',
                'fecha_creacion',
                'fecha_envio_cliente',
                'fecha_respuesta_cliente',
                'fecha_completada',
                'fecha_actualizacion',
            ),
            'classes': ('collapse',)
        }),
    )
    
    # -------------------------------------------------------------------------
    # Métodos de visualización personalizados
    # -------------------------------------------------------------------------
    
    @admin.display(description='Estado')
    def estado_badge(self, obj):
        """Muestra el estado con un badge de color"""
        colores = {
            'borrador': '#6c757d',
            'enviada_cliente': '#17a2b8',
            'parcialmente_aprobada': '#ffc107',
            'totalmente_aprobada': '#28a745',
            'totalmente_rechazada': '#dc3545',
            'en_proceso': '#007bff',
            'completada': '#28a745',
            'cancelada': '#343a40',
        }
        color = colores.get(obj.estado, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color,
            obj.get_estado_display()
        )
    
    @admin.display(description='Líneas')
    def total_lineas_display(self, obj):
        """Muestra el número de líneas con desglose"""
        total = obj.total_lineas
        aprobadas = obj.lineas_aprobadas
        rechazadas = obj.lineas_rechazadas
        
        return format_html(
            '<span title="Total: {}, Aprobadas: {}, Rechazadas: {}">'
            '{} <small class="text-muted">(✓{} ✗{})</small></span>',
            total, aprobadas, rechazadas,
            total, aprobadas, rechazadas
        )
    
    @admin.display(description='Costo Total')
    def costo_total_display(self, obj):
        """Muestra el costo total formateado"""
        return f'${obj.costo_total:,.2f}'
    
    # -------------------------------------------------------------------------
    # Acciones personalizadas
    # -------------------------------------------------------------------------
    
    actions = ['enviar_a_cliente', 'generar_compras']
    
    @admin.action(description='📧 Enviar seleccionadas a Cliente')
    def enviar_a_cliente(self, request, queryset):
        """Cambia el estado de las solicitudes a 'enviada_cliente'"""
        enviadas = 0
        for solicitud in queryset.filter(estado='borrador'):
            if solicitud.enviar_a_cliente():
                enviadas += 1
        
        if enviadas:
            self.message_user(request, f'{enviadas} solicitud(es) enviada(s) a cliente.')
        else:
            self.message_user(request, 'No se pudo enviar ninguna solicitud (deben estar en borrador).', level='warning')
    
    @admin.action(description='🛒 Generar Compras para aprobadas')
    def generar_compras(self, request, queryset):
        """Genera CompraProducto para las líneas aprobadas"""
        compras_creadas = 0
        for solicitud in queryset:
            if solicitud.puede_generar_compras():
                compras = solicitud.generar_compras(usuario=request.user)
                compras_creadas += len(compras)
        
        if compras_creadas:
            self.message_user(request, f'{compras_creadas} compra(s) generada(s).')
        else:
            self.message_user(request, 'No se generaron compras (no hay líneas aprobadas pendientes).', level='warning')


@admin.register(LineaCotizacion)
class LineaCotizacionAdmin(admin.ModelAdmin):
    """
    Configuración del admin para Líneas de Cotización.
    
    Normalmente las líneas se editan dentro de la solicitud (inline),
    pero este admin permite verlas y filtrarlas de forma independiente.
    """
    
    list_display = (
        'solicitud',
        'numero_linea',
        'producto',
        'descripcion_pieza_corta',
        'proveedor',
        'cantidad',
        'costo_unitario',
        'subtotal_display',
        'estado_badge',
    )
    
    list_filter = (
        'estado_cliente',
        'proveedor',
        ('solicitud__fecha_creacion', admin.DateFieldListFilter),
    )
    
    search_fields = (
        'solicitud__numero_solicitud',
        'descripcion_pieza',
        'producto__nombre',
        'proveedor__nombre',
    )
    
    ordering = ['-solicitud__fecha_creacion', 'numero_linea']
    
    autocomplete_fields = ['solicitud', 'producto', 'proveedor', 'compra_generada']
    
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion', 'fecha_respuesta')
    
    # NOTA: El inline ImagenLineaCotizacionInline se agrega dinámicamente
    # después de su definición (ver más abajo en el archivo)
    inlines = []  # Se poblará después
    
    # -------------------------------------------------------------------------
    # Métodos de visualización personalizados
    # -------------------------------------------------------------------------
    
    @admin.display(description='Descripción')
    def descripcion_pieza_corta(self, obj):
        """Trunca la descripción para la lista"""
        if len(obj.descripcion_pieza) > 40:
            return obj.descripcion_pieza[:40] + '...'
        return obj.descripcion_pieza
    
    @admin.display(description='Subtotal')
    def subtotal_display(self, obj):
        """Muestra el subtotal calculado"""
        return f'${obj.subtotal:,.2f}'
    
    @admin.display(description='Estado')
    def estado_badge(self, obj):
        """Muestra el estado con un badge de color"""
        colores = {
            'pendiente': '#6c757d',
            'aprobada': '#28a745',
            'rechazada': '#dc3545',
            'compra_generada': '#007bff',
        }
        color = colores.get(obj.estado_cliente, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color,
            obj.get_estado_cliente_display()
        )


# ============================================================================
# ADMIN: IMAGEN DE LÍNEA DE COTIZACIÓN
# ============================================================================
class ImagenLineaCotizacionInline(admin.TabularInline):
    """
    Inline para mostrar y gestionar imágenes dentro del admin de LineaCotizacion.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Este inline permite ver y agregar imágenes directamente desde
    la edición de una línea de cotización en el admin.
    
    Campos mostrados:
    - Imagen (preview)
    - Descripción
    - Fecha de subida
    - Información de compresión
    """
    model = ImagenLineaCotizacion
    extra = 0
    readonly_fields = ('preview_imagen', 'fecha_subida', 'fue_comprimida', 'tamano_original_kb', 'tamano_final_kb')
    fields = ('preview_imagen', 'imagen', 'descripcion', 'fecha_subida', 'fue_comprimida')
    
    @admin.display(description='Vista Previa')
    def preview_imagen(self, obj):
        """Muestra una miniatura de la imagen"""
        if obj.imagen:
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-width: 100px; max-height: 100px; border-radius: 4px;"/>'
                '</a>',
                obj.imagen.url,
                obj.imagen.url
            )
        return '-'


@admin.register(ImagenLineaCotizacion)
class ImagenLineaCotizacionAdmin(admin.ModelAdmin):
    """
    Configuración del admin para Imágenes de Líneas de Cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Este admin permite ver todas las imágenes de cotización del sistema.
    Útil para:
    - Auditoría de imágenes subidas
    - Ver espacio utilizado
    - Buscar imágenes por solicitud o línea
    
    Normalmente las imágenes se gestionan desde el detalle de solicitud,
    pero este admin permite una vista general del sistema.
    """
    
    list_display = (
        'id',
        'preview_imagen',
        'solicitud_display',
        'linea_display',
        'descripcion_corta',
        'fecha_subida',
        'subido_por',
        'fue_comprimida',
        'tamano_display',
    )
    
    list_filter = (
        'fue_comprimida',
        ('fecha_subida', admin.DateFieldListFilter),
        'linea__solicitud',
    )
    
    search_fields = (
        'linea__solicitud__numero_solicitud',
        'linea__descripcion_pieza',
        'descripcion',
    )
    
    ordering = ['-fecha_subida']
    
    readonly_fields = (
        'preview_imagen_grande',
        'fecha_subida',
        'subido_por',
        'fue_comprimida',
        'tamano_original_kb',
        'tamano_final_kb',
    )
    
    fieldsets = (
        ('Información', {
            'fields': ('linea', 'descripcion')
        }),
        ('Imagen', {
            'fields': ('preview_imagen_grande', 'imagen')
        }),
        ('Metadatos', {
            'fields': ('fecha_subida', 'subido_por', 'fue_comprimida', 'tamano_original_kb', 'tamano_final_kb'),
            'classes': ('collapse',)
        }),
    )
    
    # -------------------------------------------------------------------------
    # Métodos de visualización personalizados
    # -------------------------------------------------------------------------
    
    @admin.display(description='Imagen')
    def preview_imagen(self, obj):
        """Muestra una miniatura de la imagen en la lista"""
        if obj.imagen:
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-width: 60px; max-height: 60px; border-radius: 4px;"/>'
                '</a>',
                obj.imagen.url,
                obj.imagen.url
            )
        return '-'
    
    @admin.display(description='Vista Previa')
    def preview_imagen_grande(self, obj):
        """Muestra una imagen más grande en el formulario de detalle"""
        if obj.imagen:
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-width: 300px; max-height: 300px; border-radius: 8px;"/>'
                '</a>',
                obj.imagen.url,
                obj.imagen.url
            )
        return '-'
    
    @admin.display(description='Solicitud')
    def solicitud_display(self, obj):
        """Muestra el número de solicitud"""
        return obj.linea.solicitud.numero_solicitud
    
    @admin.display(description='Línea')
    def linea_display(self, obj):
        """Muestra información de la línea"""
        return f'#{obj.linea.numero_linea}: {obj.linea.descripcion_pieza[:30]}...'
    
    @admin.display(description='Descripción')
    def descripcion_corta(self, obj):
        """Trunca la descripción para la lista"""
        if not obj.descripcion:
            return '-'
        if len(obj.descripcion) > 30:
            return obj.descripcion[:30] + '...'
        return obj.descripcion
    
    @admin.display(description='Tamaño')
    def tamano_display(self, obj):
        """Muestra el tamaño del archivo"""
        if obj.tamano_final_kb:
            if obj.fue_comprimida and obj.tamano_original_kb:
                ahorro = obj.tamano_original_kb - obj.tamano_final_kb
                return format_html(
                    '{} KB <span style="color: green; font-size: 10px;">(-{} KB)</span>',
                    obj.tamano_final_kb,
                    ahorro
                )
            return f'{obj.tamano_final_kb} KB'
        return '-'


# ============================================================================
# CONFIGURACIÓN POST-DEFINICIÓN: ASIGNAR INLINE A LineaCotizacionAdmin
# ============================================================================
# EXPLICACIÓN PARA PRINCIPIANTES:
# --------------------------------
# En Python, las clases se definen de arriba hacia abajo en el archivo.
# LineaCotizacionAdmin se define ANTES que ImagenLineaCotizacionInline,
# por lo que no podemos referenciar ImagenLineaCotizacionInline dentro
# de LineaCotizacionAdmin directamente.
#
# La solución es asignar el inline DESPUÉS de que ambas clases existan.
# Esto es perfectamente válido en Python y es un patrón común.
# ============================================================================
LineaCotizacionAdmin.inlines = [ImagenLineaCotizacionInline]