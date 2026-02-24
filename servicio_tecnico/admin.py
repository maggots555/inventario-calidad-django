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
    # MODELOS RHITSO - Módulo de Reparación Especializada
    EstadoRHITSO,
    CategoriaDiagnostico,
    TipoIncidenciaRHITSO,
    SeguimientoRHITSO,
    IncidenciaRHITSO,
    ConfiguracionRHITSO,
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
        'es_mis',
        'falla_principal',
        'diagnostico_sic',
        ('fecha_inicio_diagnostico', 'fecha_fin_diagnostico'),
        ('fecha_inicio_reparacion', 'fecha_fin_reparacion'),
    )


class PiezaCotizadaInline(admin.TabularInline):
    """
    Inline para mostrar piezas en la cotización.
    
    ACTUALIZACIÓN NOVIEMBRE 2025:
    - Agregado campo 'proveedor' para especificar con quién se cotiza cada pieza
    - Al aceptar la cotización, se usa este proveedor para crear el seguimiento automático
    """
    model = PiezaCotizada
    extra = 1
    fields = (
        'componente',
        'descripcion_adicional',
        'proveedor',  # ← NUEVO CAMPO (Noviembre 2025)
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
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        - obj.subtotal: Es una property del modelo que calcula cantidad * precio_unitario
        - obj.pk: Es el ID del objeto en la base de datos (None si es nuevo)
        - format_html: Django función que permite crear HTML seguro
        - ${:,.2f}: Formato de moneda con comas y 2 decimales
        - try-except: Maneja errores si el subtotal no se puede calcular
        
        Esta función solo muestra el subtotal si el objeto ya existe en la BD,
        evitando errores al crear nuevas piezas.
        """
        if obj.pk:  # Si el objeto ya existe (no es nuevo)
            try:
                # Convertir explícitamente a float para evitar errores con SafeString
                subtotal = float(obj.subtotal)
                return format_html('<strong>${:,.2f}</strong>', subtotal)
            except (ValueError, TypeError, AttributeError):
                return format_html('<strong>$0.00</strong>')
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
        'estado_rhitso_display',  # NUEVO - Muestra estado RHITSO con indicadores de fechas
        'requiere_factura',
    )
    list_filter = (
        'tipo_servicio',  # NUEVO - FASE 2: Permite filtrar por tipo de servicio
        'estado',
        'sucursal',
        'es_reingreso',
        'es_candidato_rhitso',
        'estado_rhitso',  # NUEVO - Filtrar por estado RHITSO
        'fecha_envio_rhitso',  # NUEVO - Filtrar por fecha de envío a RHITSO
        'fecha_recepcion_rhitso',  # NUEVO - Filtrar por fecha de recepción desde RHITSO
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
        ('Reingreso y ScoreCard', {
            'fields': (
                'es_reingreso',
                'orden_original',
                'incidencia_scorecard',
            ),
            'classes': ('collapse',)
        }),
        ('RHITSO - Seguimiento Especializado', {
            'fields': (
                'es_candidato_rhitso',
                'motivo_rhitso',
                'descripcion_rhitso',
                'estado_rhitso',
                'fecha_envio_rhitso',
                'fecha_recepcion_rhitso',
                'tecnico_diagnostico',
                'fecha_diagnostico_sic',
                'complejidad_estimada',
            ),
            'classes': ('collapse',),
            'description': '🔧 Gestión completa del proceso RHITSO. Las fechas de envío y recepción son MANUALES (no automáticas).'
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
    
    def estado_rhitso_display(self, obj):
        """
        Muestra el estado RHITSO actual con indicadores visuales de fechas.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Este método crea una visualización del estado RHITSO con:
        - Badge con el estado actual (si existe)
        - Iconos que indican si las fechas están registradas:
          📤 = Tiene fecha de envío
          📥 = Tiene fecha de recepción
        - Color distintivo para identificar rápidamente el estado
        """
        if not obj.es_candidato_rhitso:
            return format_html('<span style="color: #999;">No aplica</span>')
        
        if not obj.estado_rhitso:
            return format_html('<span style="color: #ffc107; font-weight: bold;">⚠️ Sin estado</span>')
        
        # Badge del estado
        badge = f'<span style="background-color: #0d6efd; color: white; padding: 3px 8px; border-radius: 3px; font-size: 0.85em;">{obj.estado_rhitso[:30]}</span>'
        
        # Indicadores de fechas
        indicadores = []
        if obj.fecha_envio_rhitso:
            indicadores.append('<span title="Fecha de envío registrada: {}">📤</span>'.format(
                obj.fecha_envio_rhitso.strftime('%d/%m/%Y %H:%M')
            ))
        if obj.fecha_recepcion_rhitso:
            indicadores.append('<span title="Fecha de recepción registrada: {}">📥</span>'.format(
                obj.fecha_recepcion_rhitso.strftime('%d/%m/%Y %H:%M')
            ))
        
        resultado = badge
        if indicadores:
            resultado += ' ' + ' '.join(indicadores)
        
        return format_html(resultado)
    
    estado_rhitso_display.short_description = 'Estado RHITSO'


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
        'es_mis',
        'tiene_cargador',
    )
    list_filter = ('tipo_equipo', 'gama', 'marca', 'equipo_enciende', 'es_mis')
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
                'es_mis',
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
        """
        Muestra el costo total de piezas formateado.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        - obj.costo_total_piezas suma el costo de todas las piezas en la cotización
        - try-except maneja errores si el valor es None o inválido
        - f-string con {:,.2f} formatea como moneda con 2 decimales
        - Si hay error, muestra $0.00
        """
        try:
            costo = float(obj.costo_total_piezas)
            return f"${costo:,.2f}"
        except (ValueError, TypeError, AttributeError):
            return '$0.00'
    costo_total_piezas_display.short_description = 'Total Piezas'
    
    def costo_total_display(self, obj):
        """
        Muestra el costo total con formato de moneda.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        - obj.costo_total suma piezas + mano de obra
        - float() convierte el Decimal a número antes de formatear
        - format_html crea HTML seguro con negrita
        - Si hay error, también usa format_html para mantener consistencia
        """
        try:
            costo = float(obj.costo_total)
            return format_html('<strong>${:,.2f}</strong>', costo)
        except (ValueError, TypeError, AttributeError):
            return format_html('<strong>$0.00</strong>')
    costo_total_display.short_description = 'Total'


# ============================================================================
# ADMIN: PIEZA COTIZADA
# ============================================================================

@admin.register(PiezaCotizada)
class PiezaCotizadaAdmin(admin.ModelAdmin):
    """
    Admin para PiezaCotizada.
    
    ACTUALIZACIÓN NOVIEMBRE 2025:
    - Agregado 'proveedor' en list_display para ver con quién se cotizó
    - Agregado 'proveedor' en list_filter para filtrar por proveedor
    - Agregado 'proveedor' en search_fields para buscar por nombre de proveedor
    """
    list_display = (
        'componente',
        'cotizacion',
        'proveedor',  # ← NUEVO (Noviembre 2025)
        'cantidad',
        'costo_unitario',
        'costo_total_display',
        'sugerida_por_tecnico',
        'aceptada_por_cliente',
        'orden_prioridad',
    )
    list_filter = (
        'sugerida_por_tecnico', 
        'es_necesaria', 
        'aceptada_por_cliente',
        'proveedor',  # ← NUEVO FILTRO (Noviembre 2025)
    )
    search_fields = (
        'componente__nombre',
        'cotizacion__orden__numero_orden_interno',
        'descripcion_adicional',
        'proveedor',  # ← NUEVO CAMPO DE BÚSQUEDA (Noviembre 2025)
    )
    
    def costo_total_display(self, obj):
        """
        Muestra el costo total formateado.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        - obj.costo_total es una property que multiplica cantidad × costo_unitario
        - try-except maneja errores si el valor es None o inválido
        - f-string con {:,.2f} formatea como moneda con 2 decimales
        - Esta función NO usa format_html porque devuelve texto plano, no HTML
        """
        try:
            costo = float(obj.costo_total)
            return f"${costo:,.2f}"
        except (ValueError, TypeError, AttributeError):
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
        """Muestra el estado con color (Actualizado Nov 2025)"""
        colores = {
            'pedido': '#6c757d',
            'confirmado': '#17a2b8',
            'transito': '#ffc107',
            'retrasado': '#dc3545',
            'recibido': '#28a745',
            'incorrecto': '#dc3545',  # NUEVO: Pieza incorrecta (WPB) - Rojo
            'danado': '#ffc107',      # NUEVO: Pieza dañada (DOA) - Amarillo
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
        'incluye_respaldo',
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
                ('incluye_respaldo', 'costo_respaldo'),
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
        if obj.incluye_respaldo:
            servicios.append('Respaldo Info')
        return ', '.join(servicios) if servicios else '-'
    servicios_incluidos.short_description = 'Servicios'
    
    def total_venta_display(self, obj):
        """
        Muestra el total de venta formateado en verde.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        - obj.total_venta es una property que calcula el total de la venta
        - Usamos try-except para manejar casos donde el valor podría ser None o inválido
        - float() convierte el Decimal a número flotante ANTES de usar format_html
        - format_html crea HTML seguro para mostrar el valor con formato de moneda
        - Si hay un error, mostramos $0.00 como valor por defecto
        """
        try:
            # Convertir explícitamente a float para evitar errores con SafeString
            total = float(obj.total_venta)
            return format_html(
                '<strong style="color: green;">${:,.2f}</strong>',
                total
            )
        except (ValueError, TypeError, AttributeError):
            return format_html('<strong style="color: green;">$0.00</strong>')
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
        """
        Muestra el precio unitario con formato de moneda.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        - f-string (f"...") permite insertar variables directamente en el texto
        - obj.precio_unitario es el precio de una pieza individual
        - {:,.2f} formatea el número con comas como separador de miles y 2 decimales
        - Ejemplo: 1234.5 se muestra como $1,234.50
        """
        return f"${obj.precio_unitario:,.2f}"
    precio_unitario_display.short_description = 'Precio Unitario'
    
    def subtotal_display(self, obj):
        """
        Muestra el subtotal con formato de moneda y negrita.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        - obj.subtotal es una property que multiplica cantidad × precio_unitario
        - try-except maneja errores si el subtotal no se puede calcular
        - float() convierte el Decimal a número flotante antes de formatear
        - format_html crea HTML seguro con color verde y negrita
        - Si hay error, muestra $0.00 como valor por defecto
        """
        try:
            # Convertir explícitamente a float para evitar errores con SafeString
            subtotal = float(obj.subtotal)
            return format_html(
                '<strong style="color: green;">${:,.2f}</strong>',
                subtotal
            )
        except (ValueError, TypeError, AttributeError):
            return format_html('<strong style="color: green;">$0.00</strong>')
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


# ============================================================================
# ADMIN: MODELOS RHITSO - REPARACIÓN ESPECIALIZADA
# ============================================================================

@admin.register(EstadoRHITSO)
class EstadoRHITSOAdmin(admin.ModelAdmin):
    """
    Administración de Estados RHITSO.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    - Este admin permite crear y gestionar los estados del proceso RHITSO
    - Cada estado tiene un responsable (owner): SIC, RHITSO, CLIENTE, o COMPRAS
    - Los estados se muestran en orden secuencial según el campo 'orden'
    - El badge de color ayuda a identificar visualmente cada estado
    """
    list_display = (
        'orden',
        'estado',
        'owner_badge',
        'color_preview',
        'activo',
        'fecha_creacion',
    )
    list_filter = ('owner', 'activo', 'color')
    search_fields = ('estado', 'descripcion')
    ordering = ['orden']
    
    fieldsets = (
        ('Información del Estado', {
            'fields': ('estado', 'owner', 'descripcion')
        }),
        ('Visualización', {
            'fields': ('color', 'orden')
        }),
        ('Estado', {
            'fields': ('activo',)
        }),
    )
    
    readonly_fields = ('fecha_creacion',)
    
    def owner_badge(self, obj):
        """
        Muestra el responsable con un badge de color según el owner.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        - format_html: Función de Django que crea HTML seguro
        - obj.get_badge_class(): Método del modelo que retorna la clase CSS apropiada
        - Este método hace que en la lista se vea un badge colorido en lugar de texto plano
        """
        return format_html(
            '<span class="{}">{}</span>',
            obj.get_badge_class(),
            obj.owner
        )
    owner_badge.short_description = 'Responsable'
    
    def color_preview(self, obj):
        """
        Muestra un preview visual del color del badge.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        - Crea un pequeño cuadrado con el color del badge
        - Ayuda a visualizar cómo se verá el estado en la interfaz
        - Los colores de Bootstrap: primary (azul), success (verde), warning (amarillo), danger (rojo), etc.
        """
        colores_bootstrap = {
            'primary': '#0d6efd',
            'secondary': '#6c757d',
            'success': '#198754',
            'danger': '#dc3545',
            'warning': '#ffc107',
            'info': '#0dcaf0',
            'dark': '#212529',
        }
        color_hex = colores_bootstrap.get(obj.color, '#6c757d')
        return format_html(
            '<div style="width: 20px; height: 20px; background-color: {}; border: 1px solid #ccc; border-radius: 3px;"></div>',
            color_hex
        )
    color_preview.short_description = 'Color'


@admin.register(CategoriaDiagnostico)
class CategoriaDiagnosticoAdmin(admin.ModelAdmin):
    """
    Administración de Categorías de Diagnóstico.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    - Define tipos de problemas técnicos que requieren RHITSO
    - Cada categoría tiene un tiempo estimado de reparación
    - La complejidad indica qué tan difícil es la reparación
    - Ejemplos: Reballing de GPU, Soldadura SMD, Daño por líquidos
    """
    list_display = (
        'nombre',
        'complejidad_badge',
        'tiempo_estimado_dias',
        'requiere_rhitso',
        'activo',
    )
    list_filter = ('complejidad_tipica', 'requiere_rhitso', 'activo')
    search_fields = ('nombre', 'descripcion')
    ordering = ['nombre']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'descripcion')
        }),
        ('Configuración Técnica', {
            'fields': (
                'requiere_rhitso',
                'complejidad_tipica',
                'tiempo_estimado_dias',
            )
        }),
        ('Estado', {
            'fields': ('activo',)
        }),
    )
    
    readonly_fields = ('fecha_creacion',)
    
    def complejidad_badge(self, obj):
        """Muestra la complejidad con un badge de color"""
        colores = {
            'BAJA': 'success',
            'MEDIA': 'info',
            'ALTA': 'warning',
            'CRITICA': 'danger',
        }
        color = colores.get(obj.complejidad_tipica, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_complejidad_tipica_display()
        )
    complejidad_badge.short_description = 'Complejidad'


@admin.register(TipoIncidenciaRHITSO)
class TipoIncidenciaRHITSOAdmin(admin.ModelAdmin):
    """
    Administración de Tipos de Incidencias RHITSO.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    - Define los tipos de problemas que pueden ocurrir con RHITSO
    - Gravedad indica qué tan serio es el problema (BAJA, MEDIA, ALTA, CRITICA)
    - requiere_accion_inmediata marca si necesita atención urgente
    - Ejemplos: Daño adicional, Retraso en entrega, Pieza incorrecta
    """
    list_display = (
        'nombre',
        'gravedad_badge',
        'requiere_accion_inmediata',
        'color_preview',
        'activo',
    )
    list_filter = ('gravedad', 'requiere_accion_inmediata', 'activo')
    search_fields = ('nombre', 'descripcion')
    ordering = ['nombre']
    
    fieldsets = (
        ('Información del Tipo', {
            'fields': ('nombre', 'descripcion')
        }),
        ('Configuración', {
            'fields': (
                'gravedad',
                'color',
                'requiere_accion_inmediata',
            )
        }),
        ('Estado', {
            'fields': ('activo',)
        }),
    )
    
    readonly_fields = ('fecha_creacion',)
    
    def gravedad_badge(self, obj):
        """Muestra la gravedad con un badge de color"""
        colores = {
            'BAJA': 'success',
            'MEDIA': 'info',
            'ALTA': 'warning',
            'CRITICA': 'danger',
        }
        color = colores.get(obj.gravedad, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.gravedad
        )
    gravedad_badge.short_description = 'Gravedad'
    
    def color_preview(self, obj):
        """Muestra un preview del color del tipo de incidencia"""
        colores_bootstrap = {
            'primary': '#0d6efd',
            'secondary': '#6c757d',
            'success': '#198754',
            'danger': '#dc3545',
            'warning': '#ffc107',
            'info': '#0dcaf0',
        }
        color_hex = colores_bootstrap.get(obj.color, '#6c757d')
        return format_html(
            '<div style="width: 20px; height: 20px; background-color: {}; border: 1px solid #ccc; border-radius: 3px;"></div>',
            color_hex
        )
    color_preview.short_description = 'Color'


@admin.register(SeguimientoRHITSO)
class SeguimientoRHITSOAdmin(admin.ModelAdmin):
    """
    Administración de Seguimientos RHITSO (Historial de Estados).
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    - Registra cada cambio de estado en el proceso RHITSO
    - Es como un timeline o historial completo de la orden
    - Muestra quién hizo el cambio, cuándo, y observaciones
    - tiempo_en_estado_anterior: Días que estuvo en el estado previo
    - Este modelo es principalmente de solo lectura (creado por el sistema)
    """
    list_display = (
        'orden_link',
        'estado',
        'estado_anterior',
        'fecha_actualizacion',
        'usuario_actualizacion',
        'tiempo_en_estado_anterior',
        'notificado_cliente',
    )
    list_filter = ('estado', 'notificado_cliente', 'fecha_actualizacion')
    search_fields = (
        'orden__numero_orden_interno',
        'estado__estado',
        'observaciones',
    )
    date_hierarchy = 'fecha_actualizacion'
    ordering = ['-fecha_actualizacion']
    
    readonly_fields = ('fecha_actualizacion',)
    
    fieldsets = (
        ('Orden y Estado', {
            'fields': ('orden', 'estado', 'estado_anterior')
        }),
        ('Detalles del Cambio', {
            'fields': (
                'observaciones',
                'tiempo_en_estado_anterior',
                'usuario_actualizacion',
            )
        }),
        ('Notificaciones', {
            'fields': ('notificado_cliente',)
        }),
    )
    
    def orden_link(self, obj):
        """
        Crea un link clicable a la orden de servicio.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        - reverse: Genera la URL del admin de OrdenServicio
        - format_html: Crea un link HTML seguro
        - Permite ir directamente a la orden desde el seguimiento
        """
        url = reverse('admin:servicio_tecnico_ordenservicio_change', args=[obj.orden.id])
        return format_html('<a href="{}">{}</a>', url, obj.orden.numero_orden_interno)
    orden_link.short_description = 'Orden'
    
    def has_add_permission(self, request):
        """
        Los seguimientos se crean automáticamente por el sistema.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        - has_add_permission = False: No permite crear seguimientos manualmente
        - Se crean automáticamente cuando se cambia el estado RHITSO de una orden
        - Esto mantiene la integridad del historial
        """
        return False


@admin.register(IncidenciaRHITSO)
class IncidenciaRHITSOAdmin(admin.ModelAdmin):
    """
    Administración de Incidencias RHITSO.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    - Registra problemas que ocurren durante el proceso RHITSO
    - Ejemplos: Daño adicional, retrasos, piezas incorrectas
    - Permite hacer seguimiento hasta su resolución
    - Incluye impacto al cliente, prioridad, y costos adicionales
    """
    list_display = (
        'orden_link',
        'tipo_incidencia',
        'titulo_corto',
        'estado_badge',
        'gravedad_badge',
        'prioridad_badge',
        'impacto_cliente_badge',
        'fecha_ocurrencia',
        'dias_abierta_display',
    )
    list_filter = (
        'estado',
        'tipo_incidencia__gravedad',
        'prioridad',
        'impacto_cliente',
        'requiere_seguimiento',
        'fecha_ocurrencia',
    )
    search_fields = (
        'orden__numero_orden_interno',
        'titulo',
        'descripcion_detallada',
        'accion_tomada',
    )
    date_hierarchy = 'fecha_ocurrencia'
    ordering = ['-fecha_ocurrencia']
    
    fieldsets = (
        ('Información de la Incidencia', {
            'fields': (
                'orden',
                'tipo_incidencia',
                'titulo',
                'descripcion_detallada',
            )
        }),
        ('Clasificación', {
            'fields': (
                'estado',
                'prioridad',
                'impacto_cliente',
                'requiere_seguimiento',
            )
        }),
        ('Fechas', {
            'fields': (
                'fecha_ocurrencia',
                'fecha_resolucion',
            )
        }),
        ('Resolución', {
            'fields': (
                'accion_tomada',
                'resuelto_por',
            )
        }),
        ('Información Adicional', {
            'fields': (
                'usuario_registro',
                'costo_adicional',
            )
        }),
    )
    
    readonly_fields = ('fecha_ocurrencia',)
    
    def orden_link(self, obj):
        """Crea un link clicable a la orden"""
        url = reverse('admin:servicio_tecnico_ordenservicio_change', args=[obj.orden.id])
        return format_html('<a href="{}">{}</a>', url, obj.orden.numero_orden_interno)
    orden_link.short_description = 'Orden'
    
    def titulo_corto(self, obj):
        """Muestra el título truncado si es muy largo"""
        if len(obj.titulo) > 50:
            return obj.titulo[:50] + '...'
        return obj.titulo
    titulo_corto.short_description = 'Título'
    
    def estado_badge(self, obj):
        """Muestra el estado con un badge de color"""
        colores = {
            'ABIERTA': 'danger',
            'EN_PROCESO': 'warning',
            'RESUELTA': 'success',
            'CERRADA': 'secondary',
        }
        color = colores.get(obj.estado, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'
    
    def gravedad_badge(self, obj):
        """Muestra la gravedad del tipo de incidencia"""
        colores = {
            'BAJA': 'success',
            'MEDIA': 'info',
            'ALTA': 'warning',
            'CRITICA': 'danger',
        }
        color = colores.get(obj.tipo_incidencia.gravedad, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.tipo_incidencia.gravedad
        )
    gravedad_badge.short_description = 'Gravedad'
    
    def prioridad_badge(self, obj):
        """Muestra la prioridad con un badge de color"""
        colores = {
            'BAJA': 'success',
            'MEDIA': 'info',
            'ALTA': 'warning',
            'CRITICA': 'danger',
        }
        color = colores.get(obj.prioridad, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_prioridad_display()
        )
    prioridad_badge.short_description = 'Prioridad'
    
    def impacto_cliente_badge(self, obj):
        """Muestra el impacto al cliente con un badge de color"""
        colores = {
            'BAJO': 'success',
            'MEDIO': 'info',
            'ALTO': 'warning',
            'CRITICO': 'danger',
        }
        color = colores.get(obj.impacto_cliente, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_impacto_cliente_display()
        )
    impacto_cliente_badge.short_description = 'Impacto Cliente'
    
    def dias_abierta_display(self, obj):
        """
        Muestra los días que la incidencia ha estado abierta.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        - obj.dias_abierta: Es una property del modelo que calcula automáticamente los días
        - Si está resuelta: días desde ocurrencia hasta resolución
        - Si está abierta: días desde ocurrencia hasta hoy
        - Color rojo si lleva más de 7 días abierta
        """
        dias = obj.dias_abierta
        if obj.esta_resuelta:
            return format_html(
                '<span style="color: green;">{} días</span>',
                dias
            )
        elif dias > 7:
            return format_html(
                '<span style="color: red; font-weight: bold;">{} días ⚠️</span>',
                dias
            )
        else:
            return f'{dias} días'
    dias_abierta_display.short_description = 'Días Abierta'


@admin.register(ConfiguracionRHITSO)
class ConfiguracionRHITSOAdmin(admin.ModelAdmin):
    """
    Administración de Configuraciones RHITSO.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    - Almacena configuraciones globales del módulo RHITSO
    - Ejemplos: tiempo máximo sin actualización, email de notificaciones
    - tipo: Define si el valor es STRING, INTEGER, BOOLEAN, EMAIL, o URL
    - Se usa para ajustar el comportamiento del sistema sin cambiar código
    """
    list_display = (
        'clave',
        'valor_preview',
        'tipo_badge',
        'fecha_actualizacion',
    )
    list_filter = ('tipo',)
    search_fields = ('clave', 'descripcion', 'valor')
    ordering = ['clave']
    
    fieldsets = (
        ('Identificación', {
            'fields': ('clave', 'tipo')
        }),
        ('Valor', {
            'fields': ('valor',)
        }),
        ('Descripción', {
            'fields': ('descripcion',)
        }),
    )
    
    readonly_fields = ('fecha_actualizacion',)
    
    def valor_preview(self, obj):
        """
        Muestra el valor truncado si es muy largo.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        - Si el valor tiene más de 50 caracteres, lo corta y agrega "..."
        - Hace más legible la lista cuando hay valores largos
        - El valor completo se puede ver al editar la configuración
        """
        if len(obj.valor) > 50:
            return obj.valor[:50] + '...'
        return obj.valor
    valor_preview.short_description = 'Valor'
    
    def tipo_badge(self, obj):
        """Muestra el tipo de dato con un badge de color"""
        colores = {
            'STRING': 'primary',
            'INTEGER': 'success',
            'BOOLEAN': 'info',
            'EMAIL': 'warning',
            'URL': 'secondary',
        }
        color = colores.get(obj.tipo, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_tipo_display()
        )
    tipo_badge.short_description = 'Tipo'


# Configuración del sitio admin
admin.site.site_header = "Administración - Servicio Técnico"
admin.site.site_title = "Servicio Técnico Admin"
admin.site.index_title = "Panel de Administración"

