"""
Configuración del Admin de Django para Servicio Técnico
Administración completa de órdenes, cotizaciones, imágenes y más
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    OrdenServicio,
    DetalleEquipo,
    ReferenciaGamaEquipo,
    Cotizacion,
    PiezaCotizada,
    SeguimientoPieza,
    VentaMostrador,
    PiezaVentaMostrador,  # NUEVO - FASE 2
    ImagenOrden,
    HistorialOrden,
)


# ============================================================================
# INLINES (Modelos relacionados que se muestran en el mismo formulario)
# ============================================================================

class DetalleEquipoInline(admin.StackedInline):
    """Inline para mostrar detalle del equipo en la orden"""
    model = DetalleEquipo
    can_delete = False
    fields = (
        ('tipo_equipo', 'marca', 'modelo'),
        ('numero_serie', 'gama'),
        ('tiene_cargador', 'numero_serie_cargador'),
        'equipo_enciende',
        'falla_principal',
        'diagnostico_sic',
        ('fecha_inicio_diagnostico', 'fecha_fin_diagnostico'),
        ('fecha_inicio_reparacion', 'fecha_fin_reparacion'),
    )


class PiezaCotizadaInline(admin.TabularInline):
    """Inline para mostrar piezas en la cotización"""
    model = PiezaCotizada
    extra = 1
    fields = (
        'componente',
        'descripcion_adicional',
        'cantidad',
        'costo_unitario',
        'sugerida_por_tecnico',
        'es_necesaria',
        'aceptada_por_cliente',
        'orden_prioridad',
    )
    ordering = ['orden_prioridad']


class SeguimientoPiezaInline(admin.TabularInline):
    """Inline para mostrar seguimientos de piezas en la cotización"""
    model = SeguimientoPieza
    extra = 1
    fields = (
        'proveedor',
        'fecha_pedido',
        'fecha_entrega_estimada',
        'fecha_entrega_real',
        'estado',
        'numero_pedido',
    )


class ImagenOrdenInline(admin.TabularInline):
    """Inline para mostrar imágenes en la orden"""
    model = ImagenOrden
    extra = 1
    fields = ('tipo', 'imagen', 'descripcion', 'subido_por')
    readonly_fields = ('fecha_subida',)


class HistorialOrdenInline(admin.TabularInline):
    """Inline para mostrar historial en la orden (solo lectura)"""
    model = HistorialOrden
    extra = 0
    can_delete = False
    fields = ('fecha_evento', 'tipo_evento', 'comentario', 'usuario')
    readonly_fields = ('fecha_evento', 'tipo_evento', 'comentario', 'usuario')
    ordering = ['-fecha_evento']
    
    def has_add_permission(self, request, obj=None):
        return False


class PiezaVentaMostradorInline(admin.TabularInline):
    """
    Inline para mostrar piezas vendidas en venta mostrador.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    - TabularInline: Muestra las piezas en forma de tabla dentro del formulario de VentaMostrador
    - extra = 1: Muestra 1 fila vacía adicional para agregar nuevas piezas
    - fields: Campos que se mostrarán en cada fila de la tabla
    - readonly_fields: Campo 'subtotal' es calculado automáticamente, no se puede editar
    - autocomplete_fields: Campo 'componente' se busca con autocompletado para facilidad
    
    Esto permite agregar múltiples piezas a una venta mostrador directamente desde el admin.
    """
    model = PiezaVentaMostrador
    extra = 1
    fields = (
        'componente',
        'descripcion_pieza',
        'cantidad',
        'precio_unitario',
        'subtotal_display',
        'notas',
    )
    readonly_fields = ('subtotal_display',)
    autocomplete_fields = ['componente']
    
    def subtotal_display(self, obj):
        """
        Muestra el subtotal calculado (cantidad × precio_unitario) con formato de moneda.
        
        EXPLICACIÓN:
        - obj.subtotal: Es una property del modelo que calcula cantidad * precio_unitario
        - format_html: Django función que permite crear HTML seguro
        - ${:,.2f}: Formato de moneda con comas y 2 decimales
        """
        if obj.pk:  # Si el objeto ya existe (no es nuevo)
            return format_html('<strong>${:,.2f}</strong>', float(obj.subtotal))
        return '-'
    subtotal_display.short_description = 'Subtotal'


# ============================================================================
# ADMIN: ORDEN DE SERVICIO
# ============================================================================

@admin.register(OrdenServicio)
class OrdenServicioAdmin(admin.ModelAdmin):
    list_display = (
        'numero_orden_interno',
        'sucursal',
        'tipo_servicio_badge',  # NUEVO - FASE 2: Muestra el tipo de servicio con badge
        'estado_badge',
        'tecnico_asignado_actual',
        'fecha_ingreso',
        'dias_en_servicio_display',
        'es_reingreso',
        'es_candidato_rhitso',
        'requiere_factura',
    )
    list_filter = (
        'tipo_servicio',  # NUEVO - FASE 2: Permite filtrar por tipo de servicio
        'estado',
        'sucursal',
        'es_reingreso',
        'es_candidato_rhitso',
        'requiere_factura',
        'año',
        'mes',
    )
    search_fields = (
        'numero_orden_interno',
        'detalle_equipo__numero_serie',
        'detalle_equipo__marca',
        'detalle_equipo__modelo',
        'tecnico_asignado_actual__nombre',
        'tecnico_asignado_actual__apellido',
    )
    date_hierarchy = 'fecha_ingreso'
    
    fieldsets = (
        ('Identificación', {
            'fields': ('numero_orden_interno',)
        }),
        ('Tipo de Servicio', {
            'fields': (
                'tipo_servicio',
                'control_calidad_requerido',
            ),
            'description': 'Define si esta orden es una venta mostrador (sin diagnóstico) o requiere diagnóstico técnico completo.'
        }),
        ('Ubicación y Responsables', {
            'fields': (
                'sucursal',
                'responsable_seguimiento',
                'tecnico_asignado_actual',
            )
        }),
        ('Estado y Fechas', {
            'fields': (
                'estado',
                'fecha_ingreso',
                'fecha_finalizacion',
                'fecha_entrega',
            )
        }),
        ('Conversión desde Venta Mostrador', {
            'fields': (
                'orden_venta_mostrador_previa',
                'monto_abono_previo',
                'notas_conversion',
            ),
            'classes': ('collapse',),
            'description': 'Información sobre conversión de una venta mostrador que requirió diagnóstico completo.'
        }),
        ('Reingreso y ScoreCard', {
            'fields': (
                'es_reingreso',
                'orden_original',
                'incidencia_scorecard',
            ),
            'classes': ('collapse',)
        }),
        ('RHITSO', {
            'fields': (
                'es_candidato_rhitso',
                'motivo_rhitso',
                'descripcion_rhitso',
            ),
            'classes': ('collapse',)
        }),
        ('Facturación', {
            'fields': (
                'requiere_factura',
                'factura_emitida',
                'motivo_no_factura',
            ),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('numero_orden_interno', 'año', 'mes', 'semana')
    
    inlines = [
        DetalleEquipoInline,
        ImagenOrdenInline,
        HistorialOrdenInline,
    ]
    
    def tipo_servicio_badge(self, obj):
        """
        Muestra el tipo de servicio con un badge de color + indicadores de complementos.
        
        ACTUALIZACIÓN (Octubre 2025): Ahora muestra iconos adicionales
        para cotización y venta_mostrador si existen, ya que pueden coexistir.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        - Este método crea un "badge" (etiqueta con color) que muestra visualmente el tipo de servicio
        - 'diagnostico': Azul (#007bff) - Servicio completo con diagnóstico técnico
        - 'venta_mostrador': Verde (#28a745) - Servicio directo sin diagnóstico
        - Además muestra iconos: 📋 si tiene cotización, 💰 si tiene venta_mostrador
        - format_html: Función de Django que crea HTML de forma segura
        - get_tipo_servicio_display(): Método automático de Django que devuelve el texto legible del choice
        
        Este badge ayuda a identificar rápidamente qué tipo de orden es y qué complementos tiene.
        """
        colores = {
            'diagnostico': '#007bff',      # Azul para órdenes con diagnóstico
            'venta_mostrador': '#28a745',  # Verde para ventas mostrador
        }
        color = colores.get(obj.tipo_servicio, '#6c757d')  # Gris por defecto
        
        # Badge principal de tipo
        badge = f'<span style="background-color: {color}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{obj.get_tipo_servicio_display()}</span>'
        
        # NUEVO: Indicadores de complementos
        indicadores = []
        
        if hasattr(obj, 'cotizacion') and obj.cotizacion:
            indicadores.append('<span style="background-color: #0d6efd; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; margin-left: 4px;" title="Tiene cotización">📋</span>')
        
        if hasattr(obj, 'venta_mostrador') and obj.venta_mostrador:
            indicadores.append('<span style="background-color: #28a745; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; margin-left: 4px;" title="Tiene venta mostrador">💰</span>')
        
        # Combinar badge + indicadores
        resultado = badge
        if indicadores:
            resultado += ''.join(indicadores)
        
        return format_html(resultado)
    
    tipo_servicio_badge.short_description = 'Tipo / Complementos'
    
    def estado_badge(self, obj):
        """
        Muestra el estado con un badge de color.
        """
        colores = {
            'espera': '#6c757d',
            'recepcion': '#17a2b8',
            'diagnostico': '#ffc107',
            'cotizacion': '#fd7e14',
            'rechazada': '#dc3545',
            'esperando_piezas': '#e83e8c',
            'reparacion': '#007bff',
            'control_calidad': '#20c997',
            'finalizado': '#28a745',
            'entregado': '#28a745',
            'cancelado': '#6c757d',
        }
        color = colores.get(obj.estado, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'
    
    def dias_en_servicio_display(self, obj):
        """Muestra los días en servicio con color si está retrasada"""
        dias = obj.dias_en_servicio
        if obj.esta_retrasada:
            return format_html(
                '<span style="color: red; font-weight: bold;">{} días ⚠️</span>',
                dias
            )
        return f"{dias} días"
    dias_en_servicio_display.short_description = 'Días en Servicio'


# ============================================================================
# ADMIN: DETALLE DE EQUIPO
# ============================================================================

@admin.register(DetalleEquipo)
class DetalleEquipoAdmin(admin.ModelAdmin):
    list_display = (
        'numero_serie',
        'orden',
        'tipo_equipo',
        'marca',
        'modelo',
        'gama',
        'equipo_enciende',
        'tiene_cargador',
    )
    list_filter = ('tipo_equipo', 'gama', 'marca', 'equipo_enciende')
    search_fields = ('numero_serie', 'marca', 'modelo', 'orden__numero_orden_interno')
    
    fieldsets = (
        ('Información Básica', {
            'fields': (
                'orden',
                ('tipo_equipo', 'marca'),
                ('modelo', 'gama'),
                'numero_serie',
            )
        }),
        ('Accesorios', {
            'fields': (
                'tiene_cargador',
                'numero_serie_cargador',
            )
        }),
        ('Estado al Ingreso', {
            'fields': (
                'equipo_enciende',
                'falla_principal',
            )
        }),
        ('Diagnóstico', {
            'fields': (
                'diagnostico_sic',
                ('fecha_inicio_diagnostico', 'fecha_fin_diagnostico'),
            )
        }),
        ('Reparación', {
            'fields': (
                ('fecha_inicio_reparacion', 'fecha_fin_reparacion'),
            )
        }),
    )


# ============================================================================
# ADMIN: REFERENCIA GAMA EQUIPO
# ============================================================================

@admin.register(ReferenciaGamaEquipo)
class ReferenciaGamaEquipoAdmin(admin.ModelAdmin):
    list_display = (
        'marca',
        'modelo_base',
        'gama_badge',
        'rango_costo_min',
        'rango_costo_max',
        'activo',
    )
    list_filter = ('gama', 'marca', 'activo')
    search_fields = ('marca', 'modelo_base')
    
    fields = (
        ('marca', 'modelo_base'),
        'gama',
        ('rango_costo_min', 'rango_costo_max'),
        'activo',
    )
    
    def gama_badge(self, obj):
        """Muestra la gama con color"""
        colores = {
            'alta': '#28a745',
            'media': '#ffc107',
            'baja': '#dc3545',
        }
        color = colores.get(obj.gama, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_gama_display()
        )
    gama_badge.short_description = 'Gama'


# ============================================================================
# ADMIN: COTIZACIÓN
# ============================================================================

@admin.register(Cotizacion)
class CotizacionAdmin(admin.ModelAdmin):
    list_display = (
        'orden',
        'fecha_envio',
        'estado_respuesta',
        'costo_total_piezas_display',
        'costo_mano_obra',
        'costo_total_display',
        'dias_sin_respuesta',
    )
    list_filter = ('usuario_acepto', 'motivo_rechazo')
    search_fields = ('orden__numero_orden_interno',)
    
    fieldsets = (
        ('Orden Relacionada', {
            'fields': ('orden',)
        }),
        ('Fechas', {
            'fields': (
                'fecha_envio',
                'fecha_respuesta',
            )
        }),
        ('Respuesta del Cliente', {
            'fields': (
                'usuario_acepto',
                'motivo_rechazo',
                'detalle_rechazo',
            )
        }),
        ('Costos', {
            'fields': ('costo_mano_obra',)
        }),
    )
    
    inlines = [PiezaCotizadaInline, SeguimientoPiezaInline]
    
    def estado_respuesta(self, obj):
        """Muestra el estado de la respuesta con color"""
        if obj.usuario_acepto is True:
            return format_html('<span style="color: green;">✓ Aceptada</span>')
        elif obj.usuario_acepto is False:
            return format_html('<span style="color: red;">✗ Rechazada</span>')
        return format_html('<span style="color: orange;">⏳ Sin Respuesta</span>')
    estado_respuesta.short_description = 'Estado'
    
    def costo_total_piezas_display(self, obj):
        """Muestra el costo total de piezas formateado"""
        try:
            costo = float(obj.costo_total_piezas)
            return f"${costo:,.2f}"
        except (ValueError, TypeError):
            return '$0.00'
    costo_total_piezas_display.short_description = 'Total Piezas'
    
    def costo_total_display(self, obj):
        """Muestra el costo total con formato de moneda"""
        try:
            costo = float(obj.costo_total)
            return format_html('<strong>${:,.2f}</strong>', costo)
        except (ValueError, TypeError):
            return '<strong>$0.00</strong>'
    costo_total_display.short_description = 'Total'


# ============================================================================
# ADMIN: PIEZA COTIZADA
# ============================================================================

@admin.register(PiezaCotizada)
class PiezaCotizadaAdmin(admin.ModelAdmin):
    list_display = (
        'componente',
        'cotizacion',
        'cantidad',
        'costo_unitario',
        'costo_total_display',
        'sugerida_por_tecnico',
        'aceptada_por_cliente',
        'orden_prioridad',
    )
    list_filter = ('sugerida_por_tecnico', 'es_necesaria', 'aceptada_por_cliente')
    search_fields = (
        'componente__nombre',
        'cotizacion__orden__numero_orden_interno',
        'descripcion_adicional',
    )
    
    def costo_total_display(self, obj):
        """Muestra el costo total formateado"""
        try:
            costo = float(obj.costo_total)
            return f"${costo:,.2f}"
        except (ValueError, TypeError):
            return '$0.00'
    costo_total_display.short_description = 'Costo Total'


# ============================================================================
# ADMIN: SEGUIMIENTO DE PIEZA
# ============================================================================

@admin.register(SeguimientoPieza)
class SeguimientoPiezaAdmin(admin.ModelAdmin):
    list_display = (
        'proveedor',
        'cotizacion',
        'fecha_pedido',
        'fecha_entrega_estimada',
        'estado_badge',
        'esta_retrasado_display',
        'dias_desde_pedido',
    )
    list_filter = ('estado', 'proveedor')
    search_fields = (
        'proveedor',
        'numero_pedido',
        'cotizacion__orden__numero_orden_interno',
        'descripcion_piezas',
    )
    date_hierarchy = 'fecha_pedido'
    
    def estado_badge(self, obj):
        """Muestra el estado con color"""
        colores = {
            'pedido': '#6c757d',
            'confirmado': '#17a2b8',
            'transito': '#ffc107',
            'retrasado': '#dc3545',
            'recibido': '#28a745',
        }
        color = colores.get(obj.estado, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'
    
    def esta_retrasado_display(self, obj):
        if obj.esta_retrasado:
            return format_html(
                '<span style="color: red; font-weight: bold;">⚠️ {} días</span>',
                obj.dias_retraso
            )
        return '✓ A tiempo'
    esta_retrasado_display.short_description = 'Retraso'


# ============================================================================
# ADMIN: VENTA MOSTRADOR
# ============================================================================

@admin.register(VentaMostrador)
class VentaMostradorAdmin(admin.ModelAdmin):
    list_display = (
        'folio_venta',
        'orden',
        'fecha_venta',
        'paquete_badge',
        'servicios_incluidos',
        'genera_comision',  # NUEVO - FASE 2: Muestra si genera comisión
        'total_venta_display',
    )
    list_filter = (
        'paquete',
        'genera_comision',  # NUEVO - FASE 2: Permite filtrar por comisión
        'incluye_cambio_pieza',
        'incluye_limpieza',
        'incluye_reinstalacion_so',
    )
    search_fields = ('folio_venta', 'orden__numero_orden_interno')
    date_hierarchy = 'fecha_venta'
    
    readonly_fields = ('folio_venta',)
    
    fieldsets = (
        ('Identificación', {
            'fields': ('folio_venta', 'orden', 'fecha_venta')
        }),
        ('Paquete', {
            'fields': ('paquete',)
        }),
        ('Comisiones', {
            'fields': ('genera_comision',),
            'description': 'Las ventas de paquetes Premium, Oro y Plata generan comisión automáticamente.'
        }),
        ('Servicios Adicionales', {
            'fields': (
                ('incluye_cambio_pieza', 'costo_cambio_pieza'),
                ('incluye_limpieza', 'costo_limpieza'),
                ('incluye_kit_limpieza', 'costo_kit'),
                ('incluye_reinstalacion_so', 'costo_reinstalacion'),
            )
        }),
        ('Notas', {
            'fields': ('notas_adicionales',)
        }),
    )
    
    # NUEVO - FASE 2: Agregar inline de piezas vendidas
    inlines = [PiezaVentaMostradorInline]
    
    def paquete_badge(self, obj):
        """
        Muestra el paquete con color.
        
        ACTUALIZADO FASE 2: Se actualizaron los colores para los nuevos paquetes:
        - premium: Morado (#9b59b6) - Paquete más completo
        - oro: Dorado (#FFD700) - Paquete intermedio alto
        - plata: Plateado (#C0C0C0) - Paquete intermedio básico
        - ninguno: Gris (#6c757d) - Sin paquete
        
        Los colores ayudan a identificar visualmente el nivel de cada paquete.
        """
        colores = {
            'premium': '#9b59b6',   # ACTUALIZADO - Morado para Premium
            'oro': '#FFD700',       # Dorado (mantiene el dorado original)
            'plata': '#C0C0C0',     # Plateado (mantiene el plateado original)
            'ninguno': '#6c757d',   # Gris para sin paquete
        }
        color = colores.get(obj.paquete, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_paquete_display()
        )
    paquete_badge.short_description = 'Paquete'
    
    def servicios_incluidos(self, obj):
        """Muestra lista de servicios incluidos"""
        servicios = []
        if obj.incluye_cambio_pieza:
            servicios.append('Cambio Pieza')
        if obj.incluye_limpieza:
            servicios.append('Limpieza')
        if obj.incluye_kit_limpieza:
            servicios.append('Kit Limpieza')
        if obj.incluye_reinstalacion_so:
            servicios.append('Reinstalación SO')
        return ', '.join(servicios) if servicios else '-'
    servicios_incluidos.short_description = 'Servicios'
    
    def total_venta_display(self, obj):
        """Muestra el total de venta formateado en verde"""
        return format_html(
            '<strong style="color: green;">${:,.2f}</strong>',
            float(obj.total_venta)  # Convertir explícitamente a float
        )
    total_venta_display.short_description = 'Total'


# ============================================================================
# ADMIN: PIEZA VENTA MOSTRADOR (NUEVO - FASE 2)
# ============================================================================

@admin.register(PiezaVentaMostrador)
class PiezaVentaMostradorAdmin(admin.ModelAdmin):
    """
    Admin para gestionar piezas vendidas en mostrador.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    - Este admin permite ver y gestionar todas las piezas que se han vendido en mostrador
    - list_display: Columnas que se muestran en la lista principal
    - list_filter: Filtros laterales para buscar piezas específicas
    - search_fields: Campos en los que se puede buscar texto
    - date_hierarchy: Navegación por fechas en la parte superior
    - readonly_fields: Campos que no se pueden editar (calculados automáticamente)
    
    Es útil para reportes, auditorías y seguimiento de inventario.
    """
    list_display = (
        'venta_mostrador',
        'descripcion_pieza',
        'componente',
        'cantidad',
        'precio_unitario_display',
        'subtotal_display',
        'fecha_venta',
    )
    list_filter = (
        'fecha_venta',
        'componente',
    )
    search_fields = (
        'descripcion_pieza',
        'venta_mostrador__folio_venta',
        'venta_mostrador__orden__numero_orden_interno',
        'componente__nombre',
    )
    date_hierarchy = 'fecha_venta'
    
    readonly_fields = ('subtotal_display', 'fecha_venta')
    
    autocomplete_fields = ['componente', 'venta_mostrador']
    
    fieldsets = (
        ('Venta Relacionada', {
            'fields': ('venta_mostrador', 'fecha_venta')
        }),
        ('Información de la Pieza', {
            'fields': (
                'componente',
                'descripcion_pieza',
                ('cantidad', 'precio_unitario'),
                'subtotal_display',
            )
        }),
        ('Notas', {
            'fields': ('notas',),
            'classes': ('collapse',)
        }),
    )
    
    def precio_unitario_display(self, obj):
        """Muestra el precio unitario con formato de moneda"""
        return f"${obj.precio_unitario:,.2f}"
    precio_unitario_display.short_description = 'Precio Unitario'
    
    def subtotal_display(self, obj):
        """Muestra el subtotal con formato de moneda y negrita"""
        return format_html(
            '<strong style="color: green;">${:,.2f}</strong>',
            float(obj.subtotal)
        )
    subtotal_display.short_description = 'Subtotal'


# ============================================================================
# ADMIN: IMAGEN DE ORDEN
# ============================================================================

@admin.register(ImagenOrden)
class ImagenOrdenAdmin(admin.ModelAdmin):
    list_display = (
        'orden',
        'tipo',
        'miniatura',
        'descripcion',
        'subido_por',
        'fecha_subida',
    )
    list_filter = ('tipo', 'fecha_subida')
    search_fields = ('orden__numero_orden_interno', 'descripcion')
    date_hierarchy = 'fecha_subida'
    
    readonly_fields = ('fecha_subida', 'preview_imagen')
    
    fields = (
        'orden',
        'tipo',
        'imagen',
        'preview_imagen',
        'descripcion',
        'subido_por',
    )
    
    def miniatura(self, obj):
        """Muestra una miniatura de la imagen"""
        if obj.imagen:
            return format_html(
                '<img src="{}" style="width: 50px; height: 50px; object-fit: cover;" />',
                obj.imagen.url
            )
        return '-'
    miniatura.short_description = 'Miniatura'
    
    def preview_imagen(self, obj):
        """Muestra un preview más grande de la imagen"""
        if obj.imagen:
            return format_html(
                '<img src="{}" style="max-width: 400px; max-height: 400px;" />',
                obj.imagen.url
            )
        return 'No hay imagen'
    preview_imagen.short_description = 'Preview'


# ============================================================================
# ADMIN: HISTORIAL DE ORDEN
# ============================================================================

@admin.register(HistorialOrden)
class HistorialOrdenAdmin(admin.ModelAdmin):
    list_display = (
        'orden',
        'fecha_evento',
        'tipo_evento_badge',
        'comentario_corto',
        'usuario',
        'es_sistema',
    )
    list_filter = ('tipo_evento', 'es_sistema', 'fecha_evento')
    search_fields = ('orden__numero_orden_interno', 'comentario')
    date_hierarchy = 'fecha_evento'
    
    readonly_fields = ('fecha_evento',)
    
    def tipo_evento_badge(self, obj):
        """Muestra el tipo de evento con color"""
        colores = {
            'creacion': '#28a745',
            'cambio_estado': '#17a2b8',
            'cambio_tecnico': '#ffc107',
            'comentario': '#6c757d',
            'sistema': '#007bff',
            'imagen': '#e83e8c',
            'cotizacion': '#fd7e14',
            'pieza': '#20c997',
        }
        color = colores.get(obj.tipo_evento, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_tipo_evento_display()
        )
    tipo_evento_badge.short_description = 'Tipo'
    
    def comentario_corto(self, obj):
        """Muestra el comentario truncado"""
        if len(obj.comentario) > 60:
            return obj.comentario[:60] + '...'
        return obj.comentario
    comentario_corto.short_description = 'Comentario'
    
    def has_add_permission(self, request):
        """El historial solo se crea automáticamente"""
        return False


# Configuración del sitio admin
admin.site.site_header = "Administración - Servicio Técnico"
admin.site.site_title = "Servicio Técnico Admin"
admin.site.index_title = "Panel de Administración"

