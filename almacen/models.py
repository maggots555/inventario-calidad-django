"""
Modelos para el módulo Almacén - Sistema de Inventario de Almacén Central

Este módulo define los modelos de base de datos para:
- Proveedores de productos
- Categorías de productos de almacén
- Productos de almacén (resurtibles y únicos)
- Historial de compras
- Movimientos de entrada/salida
- Solicitudes de baja con aprobación
- Auditorías de inventario
- Diferencias de auditoría

Integración con otros módulos:
- inventario.Empleado: Para solicitantes, agentes, auditores
- inventario.Sucursal: Para ubicación de auditorías y productos
- servicio_tecnico.OrdenServicio: Para vincular piezas con reparaciones

Agregado: Diciembre 2025
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone

# Importar constantes centralizadas
from config.constants import (
    TIPO_PRODUCTO_ALMACEN_CHOICES,
    CATEGORIA_ALMACEN_CHOICES,
    TIPO_MOVIMIENTO_ALMACEN_CHOICES,
    TIPO_SOLICITUD_ALMACEN_CHOICES,
    ESTADO_SOLICITUD_BAJA_CHOICES,
    TIPO_AUDITORIA_CHOICES,
    ESTADO_AUDITORIA_CHOICES,
    RAZON_DIFERENCIA_AUDITORIA_CHOICES,
    # Constantes para UnidadInventario
    ESTADO_UNIDAD_CHOICES,
    ORIGEN_UNIDAD_CHOICES,
    DISPONIBILIDAD_UNIDAD_CHOICES,
    MARCAS_COMPONENTES_CHOICES,
    # Constantes para CompraProducto
    TIPO_COMPRA_CHOICES,
    ESTADO_COMPRA_CHOICES,
    ESTADO_UNIDAD_COMPRA_CHOICES,
    # Constantes para SolicitudCotizacion (nuevo)
    ESTADO_SOLICITUD_COTIZACION_CHOICES,
    ESTADO_LINEA_COTIZACION_CHOICES,
)


# ============================================================================
# MODELO: PROVEEDOR
# ============================================================================
class Proveedor(models.Model):
    """
    Proveedor de productos para el almacén.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Este modelo guarda información de las empresas o personas que nos venden
    productos. Es importante tener esta información para:
    - Saber a quién comprar cada producto
    - Comparar precios entre proveedores
    - Evaluar tiempos de entrega
    - Tener datos de contacto para pedidos
    
    Campos principales:
    - nombre: Nombre del proveedor (único, no se repite)
    - contacto: Nombre de la persona de contacto
    - telefono: Teléfono para llamar
    - email: Correo electrónico
    - direccion: Dirección física
    - tiempo_entrega_dias: Cuántos días tarda en entregar (promedio)
    - notas: Observaciones adicionales (descuentos, condiciones, etc.)
    - activo: Si el proveedor sigue activo o ya no se usa
    
    Uso en el sistema:
    - Se vincula con ProductoAlmacen como proveedor principal
    - Se vincula con CompraProducto para saber a quién se compró
    """
    
    # Información básica del proveedor
    nombre = models.CharField(
        max_length=200,
        unique=True,
        verbose_name='Nombre del Proveedor',
        help_text='Nombre completo o razón social del proveedor'
    )
    
    # Datos de contacto
    contacto = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Persona de Contacto',
        help_text='Nombre de la persona con quien tratar'
    )
    telefono = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Teléfono',
        help_text='Número de teléfono principal'
    )
    email = models.EmailField(
        blank=True,
        verbose_name='Correo Electrónico',
        help_text='Email para pedidos y comunicación'
    )
    direccion = models.TextField(
        blank=True,
        verbose_name='Dirección',
        help_text='Dirección física del proveedor'
    )
    
    # Métricas de servicio
    tiempo_entrega_dias = models.IntegerField(
        default=7,
        validators=[MinValueValidator(0)],
        verbose_name='Tiempo de Entrega (días)',
        help_text='Tiempo promedio de entrega en días hábiles'
    )
    
    # Información adicional
    notas = models.TextField(
        blank=True,
        verbose_name='Notas',
        help_text='Observaciones: descuentos, condiciones de pago, etc.'
    )
    
    # Estado y auditoría
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo',
        help_text='Desmarcar si ya no se trabaja con este proveedor'
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación'
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización'
    )
    
    class Meta:
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
        ordering = ['nombre']
    
    def __str__(self):
        """
        Representación en texto del proveedor.
        Se muestra en dropdowns, admin, y al imprimir el objeto.
        """
        estado = '✓' if self.activo else '✗'
        return f"{estado} {self.nombre}"
    
    def total_compras(self):
        """
        Retorna el número total de compras realizadas a este proveedor.
        Útil para reportes y evaluación de proveedores.
        """
        return self.compras_realizadas.count()
    
    def promedio_dias_entrega(self):
        """
        Calcula el promedio real de días de entrega basado en compras.
        Compara fecha_pedido vs fecha_recepcion de CompraProducto.
        """
        compras_con_recepcion = self.compras_realizadas.filter(
            fecha_recepcion__isnull=False,
            dias_entrega__isnull=False
        )
        if compras_con_recepcion.exists():
            from django.db.models import Avg
            promedio = compras_con_recepcion.aggregate(Avg('dias_entrega'))
            return promedio['dias_entrega__avg']
        return self.tiempo_entrega_dias  # Retorna el valor por defecto


# ============================================================================
# MODELO: CATEGORÍA DE ALMACÉN
# ============================================================================
class CategoriaAlmacen(models.Model):
    """
    Categorías para clasificar productos del almacén.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Las categorías ayudan a organizar los productos en grupos lógicos.
    Por ejemplo: Repuestos, Consumibles, Herramientas, Accesorios.
    
    Esto facilita:
    - Buscar productos por tipo
    - Filtrar en reportes
    - Organizar auditorías cíclicas (auditar por categoría)
    
    Campos:
    - nombre: Nombre único de la categoría
    - descripcion: Explicación de qué incluye la categoría
    - activo: Si la categoría está en uso
    """
    
    nombre = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Nombre de Categoría',
        help_text='Nombre único para la categoría (ej: Repuestos, Consumibles)'
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción',
        help_text='Explicación de qué productos incluye esta categoría'
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activa',
        help_text='Desmarcar para ocultar la categoría sin eliminarla'
    )
    
    class Meta:
        verbose_name = 'Categoría de Almacén'
        verbose_name_plural = 'Categorías de Almacén'
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre
    
    def cantidad_productos(self):
        """Retorna cuántos productos tiene esta categoría"""
        return self.productos.filter(activo=True).count()


# ============================================================================
# MODELO: PRODUCTO DE ALMACÉN
# ============================================================================
class ProductoAlmacen(models.Model):
    """
    Producto almacenado en el almacén central.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Este es el modelo principal del módulo. Representa cada artículo que
    se guarda en el almacén. Hay DOS tipos de productos:
    
    1. RESURTIBLE (Stock Permanente):
       - Se mantiene siempre en inventario
       - Tiene niveles mínimo/máximo de stock
       - Genera alertas cuando baja del mínimo
       - Ejemplo: Pasta térmica, cables HDMI, limpiadores
    
    2. ÚNICO (Compra Específica):
       - Se compra para un servicio específico
       - No tiene stock mínimo/máximo obligatorio
       - Se agota cuando se usa
       - Ejemplo: Pantalla para laptop específica, placa madre
    
    Campos importantes:
    - codigo_producto: SKU o código interno único
    - tipo_producto: 'resurtible' o 'unico'
    - stock_actual: Cantidad disponible ahora
    - stock_minimo/maximo: Solo relevantes para resurtibles
    - costo_unitario: Último precio de compra
    - sucursal: Ubicación del producto (opcional, por defecto central)
    
    Relaciones:
    - categoria: ForeignKey a CategoriaAlmacen
    - proveedor_principal: ForeignKey a Proveedor (quien normalmente lo surte)
    - creado_por: Usuario que registró el producto
    """
    
    # ========== IDENTIFICACIÓN ==========
    codigo_producto = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Código/SKU',
        help_text='Código único del producto (SKU, código de barras, etc.)'
    )
    nombre = models.CharField(
        max_length=200,
        verbose_name='Nombre del Producto',
        help_text='Nombre descriptivo del producto'
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción',
        help_text='Descripción detallada, especificaciones técnicas, etc.'
    )
    
    # ========== CLASIFICACIÓN ==========
    categoria = models.ForeignKey(
        CategoriaAlmacen,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='productos',
        verbose_name='Categoría',
        help_text='Categoría a la que pertenece el producto'
    )
    tipo_producto = models.CharField(
        max_length=20,
        choices=TIPO_PRODUCTO_ALMACEN_CHOICES,
        default='resurtible',
        verbose_name='Tipo de Producto',
        help_text='Resurtible: stock permanente. Único: compra específica.'
    )
    
    # ========== UBICACIÓN ==========
    ubicacion_fisica = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Ubicación Física',
        help_text='Ubicación en el almacén: pasillo-estante-nivel (ej: A-03-2)'
    )
    # Sucursal donde se encuentra el producto (almacén central por defecto)
    sucursal = models.ForeignKey(
        'inventario.Sucursal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='productos_almacen',
        verbose_name='Sucursal',
        help_text='Sucursal donde está el producto. Dejar vacío = almacén central.'
    )
    
    # ========== STOCK ==========
    stock_actual = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Stock Actual',
        help_text='Cantidad disponible actualmente'
    )
    stock_minimo = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Stock Mínimo',
        help_text='Nivel mínimo antes de alerta de reposición (solo resurtibles)'
    )
    stock_maximo = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Stock Máximo',
        help_text='Nivel máximo recomendado (solo resurtibles)'
    )
    
    # ========== COSTOS ==========
    costo_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Costo Unitario',
        help_text='Último costo de compra por unidad (MXN)'
    )
    
    # ========== PROVEEDOR ==========
    proveedor_principal = models.ForeignKey(
        Proveedor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='productos_principales',
        verbose_name='Proveedor Principal',
        help_text='Proveedor habitual de este producto'
    )
    tiempo_reposicion_dias = models.IntegerField(
        default=7,
        validators=[MinValueValidator(0)],
        verbose_name='Tiempo de Reposición (días)',
        help_text='Tiempo estimado para reponer stock'
    )
    
    # ========== MULTIMEDIA ==========
    imagen = models.ImageField(
        upload_to='almacen/productos/',
        blank=True,
        null=True,
        verbose_name='Imagen del Producto',
        help_text='Foto del producto para identificación visual'
    )
    qr_code = models.ImageField(
        upload_to='almacen/qr_codes/',
        blank=True,
        null=True,
        verbose_name='Código QR',
        help_text='Código QR generado automáticamente'
    )
    
    # ========== ESTADO Y AUDITORÍA ==========
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo',
        help_text='Desmarcar para ocultar sin eliminar'
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación'
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización'
    )
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='productos_almacen_creados',
        verbose_name='Creado por'
    )
    
    class Meta:
        verbose_name = 'Producto de Almacén'
        verbose_name_plural = 'Productos de Almacén'
        ordering = ['nombre']
        indexes = [
            models.Index(fields=['codigo_producto']),
            models.Index(fields=['tipo_producto']),
            models.Index(fields=['activo']),
        ]
    
    def __str__(self):
        """
        Representación del producto.
        Incluye emoji según tipo: 📦 resurtible, 🔧 único
        """
        tipo_emoji = '📦' if self.tipo_producto == 'resurtible' else '🔧'
        return f"{tipo_emoji} {self.codigo_producto} - {self.nombre}"
    
    def esta_bajo_minimo(self):
        """
        Verifica si el stock está bajo el mínimo.
        Solo aplica para productos resurtibles.
        
        Returns:
            bool: True si stock_actual <= stock_minimo (y es resurtible)
        """
        if self.tipo_producto == 'resurtible':
            return self.stock_actual <= self.stock_minimo
        return False
    
    def requiere_reposicion(self):
        """Alias de esta_bajo_minimo() para mayor claridad en el código"""
        return self.esta_bajo_minimo()
    
    def porcentaje_stock(self):
        """
        Calcula el porcentaje de stock actual respecto al máximo.
        Útil para barras de progreso en la interfaz.
        
        Returns:
            float: Porcentaje de 0 a 100 (puede ser >100 si hay exceso)
        """
        if self.tipo_producto == 'resurtible' and self.stock_maximo > 0:
            return (self.stock_actual / self.stock_maximo) * 100
        return 0
    
    def valor_total_stock(self):
        """
        Calcula el valor monetario total del stock actual.
        
        Returns:
            Decimal: stock_actual × costo_unitario
        """
        return self.stock_actual * self.costo_unitario
    
    def get_estado_stock(self):
        """
        Retorna el estado del stock para mostrar en la interfaz.
        
        Returns:
            tuple: (codigo_estado, nombre_estado, clase_css)
        """
        if self.stock_actual == 0:
            return ('agotado', 'Agotado', 'danger')
        elif self.esta_bajo_minimo():
            return ('bajo', 'Stock Bajo', 'warning')
        else:
            return ('ok', 'En Stock', 'success')
    
    # ========== MÉTODOS PARA UNIDADES INDIVIDUALES ==========
    
    def unidades_disponibles(self):
        """
        Retorna las unidades disponibles de este producto.
        
        Returns:
            QuerySet: Unidades con disponibilidad='disponible' y estado usable
        """
        return self.unidades.filter(
            disponibilidad='disponible',
            estado__in=['nuevo', 'usado_bueno', 'reparado']
        )
    
    def cantidad_unidades_disponibles(self):
        """
        Cuenta cuántas unidades están disponibles.
        
        Returns:
            int: Número de unidades disponibles
        """
        return self.unidades_disponibles().count()
    
    def unidades_por_marca(self):
        """
        Agrupa las unidades disponibles por marca.
        
        Returns:
            dict: {marca: cantidad}
        """
        from django.db.models import Count
        return dict(
            self.unidades_disponibles()
            .values('marca')
            .annotate(cantidad=Count('id'))
            .values_list('marca', 'cantidad')
        )
    
    def unidades_por_estado(self):
        """
        Agrupa todas las unidades por estado.
        
        Returns:
            dict: {estado: cantidad}
        """
        from django.db.models import Count
        return dict(
            self.unidades.filter(disponibilidad__in=['disponible', 'reservada', 'asignada'])
            .values('estado')
            .annotate(cantidad=Count('id'))
            .values_list('estado', 'cantidad')
        )
    
    def tiene_unidades_rastreadas(self):
        """
        Verifica si este producto tiene unidades individuales registradas.
        
        Returns:
            bool: True si tiene al menos una unidad registrada
        """
        return self.unidades.exists()


# ============================================================================
# MODELO: COMPRA DE PRODUCTO
# ============================================================================
class CompraProducto(models.Model):
    """
    Historial de compras y cotizaciones de productos.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Este modelo maneja TODO el flujo de adquisición de piezas:
    
    1. COTIZACIÓN: Cuando un cliente necesita una pieza, primero se cotiza.
       - Estado: pendiente_aprobacion
       - El cliente puede aprobar o rechazar
    
    2. COMPRA FORMAL: Una vez aprobada, se convierte en compra.
       - Estado: aprobada → pendiente_llegada → recibida
    
    3. PROBLEMAS: Si la pieza llega mal:
       - WPB (Wrong Part): Pieza incorrecta (mandaron otra cosa)
       - DOA (Dead On Arrival): Pieza dañada al llegar
    
    4. DEVOLUCIÓN: Si hay problema, se puede devolver al proveedor
       - Estado: devolucion_garantia → devuelta
       - Al confirmar devolución, se descuenta del stock
    
    FLUJO COMPLETO:
    ---------------
    Cotización → Aprobación → Pendiente Llegada → Recibida (OK)
                     ↓                              ↓
                 Rechazada                    WPB / DOA
                                                  ↓
                                          Devolución Garantía
                                                  ↓
                                              Devuelta
    
    Campos importantes:
    - tipo: 'cotizacion' o 'compra' (diferencia el tipo de registro)
    - estado: Estado actual en el flujo
    - orden_cliente: Número visible para el cliente (ej: "OS-2024-0001")
    - unidades_compra: Detalle de cada pieza individual con marca/modelo
    """
    
    # ========== TIPO Y ESTADO ==========
    tipo = models.CharField(
        max_length=15,
        choices=TIPO_COMPRA_CHOICES,
        default='cotizacion',
        verbose_name='Tipo de Registro',
        help_text='Cotización (pendiente aprobación) o Compra formal'
    )
    estado = models.CharField(
        max_length=25,
        choices=ESTADO_COMPRA_CHOICES,
        default='pendiente_aprobacion',
        verbose_name='Estado',
        help_text='Estado actual de la compra/cotización'
    )
    
    # ========== PRODUCTO Y PROVEEDOR ==========
    producto = models.ForeignKey(
        ProductoAlmacen,
        on_delete=models.CASCADE,
        related_name='historial_compras',
        verbose_name='Producto',
        help_text='Producto que se compró'
    )
    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.SET_NULL,
        null=True,
        related_name='compras_realizadas',
        verbose_name='Proveedor',
        help_text='Proveedor de esta compra específica'
    )
    
    # ========== CANTIDADES Y COSTOS ==========
    cantidad = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Cantidad',
        help_text='Número de unidades compradas'
    )
    costo_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Costo Unitario',
        help_text='Precio por unidad en esta compra (MXN)'
    )
    costo_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Costo Total',
        help_text='Cantidad × Costo Unitario (calculado automáticamente)'
    )
    
    # ========== FECHAS Y TIEMPOS ==========
    fecha_pedido = models.DateField(
        verbose_name='Fecha de Pedido',
        help_text='Fecha en que se realizó el pedido'
    )
    fecha_recepcion = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha de Recepción',
        help_text='Fecha en que se recibió el producto'
    )
    dias_entrega = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Días de Entrega',
        help_text='Días entre pedido y recepción (calculado automáticamente)'
    )
    
    # ========== FECHAS DE WORKFLOW ==========
    fecha_aprobacion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Aprobación',
        help_text='Cuándo el cliente aprobó la cotización'
    )
    fecha_rechazo = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Rechazo',
        help_text='Cuándo el cliente rechazó la cotización'
    )
    fecha_problema = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Problema',
        help_text='Cuándo se detectó WPB/DOA'
    )
    fecha_devolucion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Devolución',
        help_text='Cuándo se confirmó la devolución al proveedor'
    )
    
    # ========== DOCUMENTOS ==========
    numero_factura = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Número de Factura',
        help_text='Número de factura del proveedor'
    )
    numero_orden_compra = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Número de Orden de Compra',
        help_text='Número de orden de compra interno'
    )
    
    # ========== VINCULACIÓN CON SERVICIO TÉCNICO ==========
    orden_servicio = models.ForeignKey(
        'servicio_tecnico.OrdenServicio',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='compras_piezas',
        verbose_name='Orden de Servicio',
        help_text='Si esta compra es para un servicio técnico específico'
    )
    # Campo para búsqueda por orden_cliente (visible para el usuario)
    orden_cliente = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Número de Orden Cliente',
        help_text='Número de orden visible para el cliente (ej: OS-2024-0001)'
    )
    
    # ========== INFORMACIÓN DE PROBLEMA ==========
    motivo_problema = models.TextField(
        blank=True,
        verbose_name='Motivo del Problema',
        help_text='Descripción del problema (WPB/DOA)'
    )
    motivo_rechazo = models.TextField(
        blank=True,
        verbose_name='Motivo del Rechazo',
        help_text='Razón por la cual el cliente rechazó la cotización'
    )
    
    # ========== INFORMACIÓN ADICIONAL ==========
    observaciones = models.TextField(
        blank=True,
        verbose_name='Observaciones',
        help_text='Notas adicionales sobre esta compra'
    )
    
    # ========== AUDITORÍA ==========
    registrado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='compras_registradas',
        verbose_name='Registrado por'
    )
    fecha_registro = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Registro'
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización'
    )
    
    class Meta:
        verbose_name = 'Compra de Producto'
        verbose_name_plural = 'Compras de Productos'
        ordering = ['-fecha_registro']
        indexes = [
            models.Index(fields=['estado']),
            models.Index(fields=['tipo']),
            models.Index(fields=['orden_cliente']),
        ]
    
    def __str__(self):
        tipo_icon = '📋' if self.tipo == 'cotizacion' else '🛒'
        return f"{tipo_icon} {self.producto.codigo_producto} - {self.cantidad} uds @ ${self.costo_unitario} ({self.get_estado_display()})"
    
    def calcular_dias_entrega(self):
        """Calcula los días entre pedido y recepción"""
        if self.fecha_recepcion and self.fecha_pedido:
            delta = self.fecha_recepcion - self.fecha_pedido
            return delta.days
        return None
    
    def save(self, *args, **kwargs):
        """
        Override de save() para cálculos automáticos.
        
        Al guardar:
        1. Calcula costo_total = cantidad × costo_unitario
        2. Calcula dias_entrega si hay fecha de recepción
        3. Sincroniza orden_cliente desde orden_servicio si existe
        """
        # Calcular costo total
        self.costo_total = self.cantidad * self.costo_unitario
        
        # Calcular días de entrega
        self.dias_entrega = self.calcular_dias_entrega()
        
        # Sincronizar orden_cliente desde orden_servicio
        if self.orden_servicio and not self.orden_cliente:
            self.orden_cliente = self.orden_servicio.orden_cliente
        
        super().save(*args, **kwargs)
    
    # ========== MÉTODOS DE WORKFLOW ==========
    
    def puede_aprobar(self):
        """Verifica si la cotización puede ser aprobada"""
        return self.tipo == 'cotizacion' and self.estado == 'pendiente_aprobacion'
    
    def puede_rechazar(self):
        """Verifica si la cotización puede ser rechazada"""
        return self.tipo == 'cotizacion' and self.estado == 'pendiente_aprobacion'
    
    def puede_recibir(self):
        """Verifica si la compra puede marcarse como recibida"""
        return self.estado in ['aprobada', 'pendiente_llegada']
    
    def puede_marcar_problema(self):
        """Verifica si se puede marcar como WPB o DOA"""
        return self.estado == 'recibida'
    
    def puede_devolver(self):
        """Verifica si se puede iniciar devolución"""
        return self.estado in ['wpb', 'doa']
    
    def puede_confirmar_devolucion(self):
        """Verifica si se puede confirmar que fue devuelta"""
        return self.estado == 'devolucion_garantia'
    
    def aprobar(self, usuario=None):
        """
        Aprueba la cotización y la convierte en compra pendiente.
        
        Args:
            usuario: Usuario que aprueba (opcional, para auditoría)
        
        Returns:
            bool: True si se aprobó exitosamente
        """
        if not self.puede_aprobar():
            return False
        
        self.tipo = 'compra'
        self.estado = 'pendiente_llegada'
        self.fecha_aprobacion = timezone.now()
        self.save()
        return True
    
    def rechazar(self, motivo='', usuario=None):
        """
        Rechaza la cotización.
        
        Args:
            motivo: Razón del rechazo (opcional)
            usuario: Usuario que rechaza (opcional, para auditoría)
        
        Returns:
            bool: True si se rechazó exitosamente
        """
        if not self.puede_rechazar():
            return False
        
        self.estado = 'rechazada'
        self.fecha_rechazo = timezone.now()
        if motivo:
            self.motivo_rechazo = motivo
        self.save()
        return True
    
    def recibir(self, fecha_recepcion=None, crear_unidades=True):
        """
        Marca la compra como recibida y opcionalmente crea las UnidadInventario.
        
        Args:
            fecha_recepcion: Fecha de recepción (default: hoy)
            crear_unidades: Si True, crea UnidadInventario automáticamente
        
        Returns:
            bool: True si se recibió exitosamente
        
        NOTA: Este método crea MovimientoAlmacen de entrada para actualizar stock.
        """
        if not self.puede_recibir():
            return False
        
        self.estado = 'recibida'
        self.fecha_recepcion = fecha_recepcion or timezone.now().date()
        self.dias_entrega = self.calcular_dias_entrega()
        
        # Actualizar costo unitario del producto con el último costo
        if self.producto:
            self.producto.costo_unitario = self.costo_unitario
            self.producto.save(update_fields=['costo_unitario', 'fecha_actualizacion'])
        
        self.save()
        return True
    
    def marcar_wpb(self, motivo=''):
        """
        Marca la compra como WPB (Wrong Part - Pieza Incorrecta).
        
        Args:
            motivo: Descripción del problema
        
        Returns:
            bool: True si se marcó exitosamente
        """
        if not self.puede_marcar_problema():
            return False
        
        self.estado = 'wpb'
        self.fecha_problema = timezone.now()
        self.motivo_problema = motivo or 'Pieza incorrecta recibida'
        self.save()
        return True
    
    def marcar_doa(self, motivo=''):
        """
        Marca la compra como DOA (Dead On Arrival - Dañada al Llegar).
        
        Args:
            motivo: Descripción del problema
        
        Returns:
            bool: True si se marcó exitosamente
        """
        if not self.puede_marcar_problema():
            return False
        
        self.estado = 'doa'
        self.fecha_problema = timezone.now()
        self.motivo_problema = motivo or 'Pieza dañada al llegar'
        self.save()
        return True
    
    def iniciar_devolucion(self):
        """
        Inicia el proceso de devolución al proveedor.
        
        Returns:
            bool: True si se inició exitosamente
        """
        if not self.puede_devolver():
            return False
        
        self.estado = 'devolucion_garantia'
        self.save()
        return True
    
    def confirmar_devolucion(self, empleado=None, observaciones=''):
        """
        Confirma que la pieza fue devuelta al proveedor.
        
        Esto crea un MovimientoAlmacen de salida para descontar del stock
        si la pieza ya había sido ingresada al inventario.
        
        Args:
            empleado: Empleado que confirma la devolución
            observaciones: Notas adicionales
        
        Returns:
            bool: True si se confirmó exitosamente
        """
        if not self.puede_confirmar_devolucion():
            return False
        
        self.estado = 'devuelta'
        self.fecha_devolucion = timezone.now()
        
        if observaciones:
            self.observaciones = f"{self.observaciones}\n[DEVOLUCIÓN] {observaciones}".strip()
        
        self.save()
        
        # Crear movimiento de salida para descontar del stock
        # Solo si la pieza ya estaba en stock (fue recibida antes)
        if self.fecha_recepcion:
            MovimientoAlmacen.objects.create(
                tipo='salida',
                producto=self.producto,
                cantidad=self.cantidad,
                costo_unitario=self.costo_unitario,
                empleado=empleado,
                compra=self,
                observaciones=f'Devolución por {self.get_estado_display()} - {self.motivo_problema}'
            )
        
        return True
    
    def cancelar(self, motivo=''):
        """
        Cancela la compra/cotización.
        
        Args:
            motivo: Razón de la cancelación
        
        Returns:
            bool: True si se canceló exitosamente
        """
        # No se puede cancelar si ya fue recibida sin problemas
        if self.estado == 'recibida':
            return False
        
        self.estado = 'cancelada'
        if motivo:
            self.observaciones = f"{self.observaciones}\n[CANCELADA] {motivo}".strip()
        self.save()
        return True
    
    # ========== PROPIEDADES ÚTILES ==========
    
    @property
    def es_cotizacion(self):
        """Retorna True si es una cotización"""
        return self.tipo == 'cotizacion'
    
    @property
    def es_compra(self):
        """Retorna True si es una compra formal"""
        return self.tipo == 'compra'
    
    @property
    def tiene_problema(self):
        """Retorna True si tiene WPB o DOA"""
        return self.estado in ['wpb', 'doa']
    
    @property
    def esta_finalizada(self):
        """Retorna True si está en estado final"""
        return self.estado in ['recibida', 'devuelta', 'cancelada', 'rechazada']
    
    @property
    def dias_sin_respuesta(self):
        """Calcula días desde la cotización sin respuesta del cliente"""
        if self.estado == 'pendiente_aprobacion':
            delta = timezone.now() - self.fecha_registro
            return delta.days
        return 0
    
    def get_badge_estado(self):
        """Retorna la clase CSS para el badge de estado"""
        estados_css = {
            'pendiente_aprobacion': 'warning',
            'aprobada': 'info',
            'rechazada': 'secondary',
            'pendiente_llegada': 'primary',
            'recibida': 'success',
            'wpb': 'danger',
            'doa': 'danger',
            'devolucion_garantia': 'warning',
            'devuelta': 'dark',
            'cancelada': 'secondary',
        }
        return estados_css.get(self.estado, 'secondary')
    
    def get_tipo_icon(self):
        """Retorna el icono según el tipo"""
        return '📋' if self.tipo == 'cotizacion' else '🛒'


# ============================================================================
# MODELO: UNIDAD DE COMPRA (Detalle por Pieza Individual)
# ============================================================================
class UnidadCompra(models.Model):
    """
    Detalle de cada unidad individual dentro de una compra.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Cuando compras 5 tarjetas madre, cada una puede ser diferente:
    - 2 pueden ser ASUS ROG STRIX B550
    - 2 pueden ser MSI MAG B550
    - 1 puede ser Gigabyte B550 AORUS
    
    Este modelo permite registrar CADA PIEZA con sus especificaciones
    únicas, para luego convertirlas en UnidadInventario cuando lleguen.
    
    ¿Por qué necesitamos esto?
    --------------------------
    1. ESPECIFICACIONES DIFERENTES: Cada pieza puede tener marca/modelo distinto
    2. NÚMEROS DE SERIE: Cada pieza tiene su S/N único
    3. COSTOS INDIVIDUALES: A veces el precio varía por marca
    4. TRACKING POR PIEZA: Saber el estado de cada una (recibida, WPB, DOA)
    
    FLUJO:
    ------
    1. Al crear CompraProducto con cantidad=5, se pueden crear 5 UnidadCompra
    2. Cada UnidadCompra define marca, modelo, costo individual
    3. Al recibir, cada UnidadCompra se convierte en UnidadInventario
    4. Si hay problema (WPB/DOA), se marca la unidad específica
    
    Relación con otros modelos:
    - compra: ForeignKey a CompraProducto (la compra padre)
    - unidad_inventario: OneToOneField a UnidadInventario (cuando se crea)
    """
    
    # ========== RELACIÓN CON COMPRA PADRE ==========
    compra = models.ForeignKey(
        CompraProducto,
        on_delete=models.CASCADE,
        related_name='unidades_compra',
        verbose_name='Compra',
        help_text='Compra a la que pertenece esta unidad'
    )
    
    # ========== IDENTIFICACIÓN DE LA UNIDAD ==========
    numero_linea = models.PositiveIntegerField(
        default=1,
        verbose_name='Número de Línea',
        help_text='Número secuencial dentro de la compra (1, 2, 3...)'
    )
    numero_serie = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Número de Serie',
        help_text='S/N del fabricante (si se conoce al comprar)'
    )
    
    # ========== MARCA Y MODELO ESPECÍFICOS ==========
    marca = models.CharField(
        max_length=50,
        blank=True,
        choices=MARCAS_COMPONENTES_CHOICES,
        verbose_name='Marca',
        help_text='Marca del fabricante (ej: Samsung, Kingston)'
    )
    modelo = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Modelo',
        help_text='Modelo específico (ej: 870 EVO, A400)'
    )
    especificaciones = models.TextField(
        blank=True,
        verbose_name='Especificaciones',
        help_text='Detalles técnicos adicionales de esta unidad'
    )
    
    # ========== COSTO INDIVIDUAL ==========
    costo_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name='Costo Unitario',
        help_text='Costo específico de esta unidad (si difiere del general)'
    )
    
    # ========== ESTADO DE RECEPCIÓN ==========
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_UNIDAD_COMPRA_CHOICES,
        default='pendiente',
        verbose_name='Estado',
        help_text='Estado de recepción de esta unidad específica'
    )
    motivo_problema = models.TextField(
        blank=True,
        verbose_name='Motivo del Problema',
        help_text='Descripción del problema si es WPB/DOA'
    )
    
    # ========== VINCULACIÓN CON INVENTARIO ==========
    unidad_inventario = models.OneToOneField(
        'UnidadInventario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='unidad_compra_origen',
        verbose_name='Unidad de Inventario',
        help_text='UnidadInventario creada al recibir esta pieza'
    )
    
    # ========== FECHAS ==========
    fecha_recepcion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Recepción',
        help_text='Cuándo se recibió esta unidad específica'
    )
    fecha_problema = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Problema',
        help_text='Cuándo se detectó el problema'
    )
    
    # ========== AUDITORÍA ==========
    notas = models.TextField(
        blank=True,
        verbose_name='Notas',
        help_text='Observaciones adicionales'
    )
    fecha_registro = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Registro'
    )
    
    class Meta:
        verbose_name = 'Unidad de Compra'
        verbose_name_plural = 'Unidades de Compra'
        ordering = ['compra', 'numero_linea']
        unique_together = ['compra', 'numero_linea']
    
    def __str__(self):
        partes = [f"#{self.numero_linea}"]
        if self.marca:
            partes.append(self.marca)
        if self.modelo:
            partes.append(self.modelo)
        if not self.marca and not self.modelo:
            partes.append(self.compra.producto.nombre)
        partes.append(f"({self.get_estado_display()})")
        return " ".join(partes)
    
    def get_costo(self):
        """
        Retorna el costo de esta unidad.
        Si no tiene costo específico, usa el de la compra padre.
        """
        return self.costo_unitario or self.compra.costo_unitario
    
    def puede_recibir(self):
        """Verifica si esta unidad puede marcarse como recibida"""
        return self.estado == 'pendiente'
    
    def recibir(self, crear_unidad_inventario=True):
        """
        Marca esta unidad como recibida y opcionalmente crea UnidadInventario.
        
        Args:
            crear_unidad_inventario: Si True, crea la UnidadInventario
        
        Returns:
            UnidadInventario or None: La unidad creada, o None si no se creó
        """
        if not self.puede_recibir():
            return None
        
        self.estado = 'recibida'
        self.fecha_recepcion = timezone.now()
        
        unidad = None
        if crear_unidad_inventario:
            unidad = UnidadInventario.objects.create(
                producto=self.compra.producto,
                numero_serie=self.numero_serie,
                marca=self.marca,
                modelo=self.modelo,
                especificaciones=self.especificaciones,
                estado='nuevo',
                disponibilidad='disponible',
                origen='compra',
                compra=self.compra,
                costo_unitario=self.get_costo(),
                notas=f'Creada desde compra #{self.compra.id}, línea {self.numero_linea}'
            )
            self.unidad_inventario = unidad
        
        self.save()
        return unidad
    
    def marcar_wpb(self, motivo=''):
        """
        Marca esta unidad como WPB (Wrong Part).
        
        Args:
            motivo: Descripción del problema
        
        Returns:
            bool: True si se marcó exitosamente
        """
        if self.estado not in ['pendiente', 'recibida']:
            return False
        
        self.estado = 'wpb'
        self.fecha_problema = timezone.now()
        self.motivo_problema = motivo or 'Pieza incorrecta'
        self.save()
        return True
    
    def marcar_doa(self, motivo=''):
        """
        Marca esta unidad como DOA (Dead On Arrival).
        
        Args:
            motivo: Descripción del problema
        
        Returns:
            bool: True si se marcó exitosamente
        """
        if self.estado not in ['pendiente', 'recibida']:
            return False
        
        self.estado = 'doa'
        self.fecha_problema = timezone.now()
        self.motivo_problema = motivo or 'Pieza dañada'
        self.save()
        return True
    
    def iniciar_devolucion(self):
        """Inicia el proceso de devolución"""
        if self.estado not in ['wpb', 'doa']:
            return False
        
        self.estado = 'devolucion'
        self.save()
        return True
    
    def confirmar_devolucion(self):
        """Confirma que la pieza fue devuelta"""
        if self.estado != 'devolucion':
            return False
        
        self.estado = 'devuelta'
        self.save()
        
        # Si tenía UnidadInventario asociada, marcarla como descartada
        if self.unidad_inventario:
            self.unidad_inventario.marcar_descartada('Devuelta por problema')
        
        return True
    
    def get_badge_estado(self):
        """Retorna la clase CSS para el badge de estado"""
        estados_css = {
            'pendiente': 'warning',
            'recibida': 'success',
            'wpb': 'danger',
            'doa': 'danger',
            'devolucion': 'info',
            'devuelta': 'dark',
        }
        return estados_css.get(self.estado, 'secondary')


# ============================================================================
# MODELO: MOVIMIENTO DE ALMACÉN
# ============================================================================
class MovimientoAlmacen(models.Model):
    """
    Registro de entradas y salidas de productos.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Cada vez que un producto entra o sale del almacén, se registra aquí.
    Este es el modelo que REALMENTE actualiza el stock.
    
    ENTRADA: Cuando llegan productos (de una compra, devolución, etc.)
    - Se incrementa el stock_actual del producto
    - Se registra quién lo recibió y cuándo
    
    SALIDA: Cuando salen productos (venta, servicio técnico, consumo)
    - Se decrementa el stock_actual del producto
    - Se registra quién lo entregó, para qué, y a qué orden si aplica
    
    Campos importantes:
    - tipo: 'entrada' o 'salida'
    - stock_anterior / stock_posterior: Para auditoría y trazabilidad
    - orden_servicio: Si la pieza es para un servicio técnico
    - compra: Si la entrada viene de una compra registrada
    
    IMPORTANTE: El stock se actualiza automáticamente en save()
    """
    
    # ========== TIPO DE MOVIMIENTO ==========
    tipo = models.CharField(
        max_length=10,
        choices=TIPO_MOVIMIENTO_ALMACEN_CHOICES,
        verbose_name='Tipo de Movimiento',
        help_text='Entrada: suma al stock. Salida: resta del stock.'
    )
    
    # ========== PRODUCTO ==========
    producto = models.ForeignKey(
        ProductoAlmacen,
        on_delete=models.CASCADE,
        related_name='movimientos',
        verbose_name='Producto'
    )
    cantidad = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Cantidad',
        help_text='Número de unidades que entran o salen'
    )
    
    # ========== COSTO ==========
    costo_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Costo Unitario',
        help_text='Costo por unidad al momento del movimiento'
    )
    
    # ========== RESPONSABLE ==========
    empleado = models.ForeignKey(
        'inventario.Empleado',
        on_delete=models.SET_NULL,
        null=True,
        related_name='movimientos_almacen',
        verbose_name='Registrado por',
        help_text='Empleado que realizó o registró el movimiento'
    )
    
    # ========== VINCULACIONES OPCIONALES ==========
    orden_servicio = models.ForeignKey(
        'servicio_tecnico.OrdenServicio',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='piezas_almacen',
        verbose_name='Orden de Servicio',
        help_text='Si este movimiento es para un servicio técnico'
    )
    compra = models.ForeignKey(
        CompraProducto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimientos',
        verbose_name='Compra Asociada',
        help_text='Si este movimiento viene de una compra registrada'
    )
    solicitud_baja = models.ForeignKey(
        'SolicitudBaja',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimientos',
        verbose_name='Solicitud de Baja',
        help_text='Solicitud que originó este movimiento (si aplica)'
    )
    
    # ========== TRACKING DE STOCK ==========
    stock_anterior = models.IntegerField(
        verbose_name='Stock Anterior',
        help_text='Stock antes del movimiento'
    )
    stock_posterior = models.IntegerField(
        verbose_name='Stock Posterior',
        help_text='Stock después del movimiento'
    )
    
    # ========== INFORMACIÓN ADICIONAL ==========
    observaciones = models.TextField(
        blank=True,
        verbose_name='Observaciones',
        help_text='Notas sobre este movimiento'
    )
    fecha = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha y Hora'
    )
    
    class Meta:
        verbose_name = 'Movimiento de Almacén'
        verbose_name_plural = 'Movimientos de Almacén'
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['tipo']),
            models.Index(fields=['fecha']),
        ]
    
    def __str__(self):
        tipo_icon = '📥' if self.tipo == 'entrada' else '📤'
        return f"{tipo_icon} {self.producto.codigo_producto} ({self.cantidad}) - {self.fecha.strftime('%d/%m/%Y %H:%M')}"
    
    def costo_total(self):
        """Retorna el costo total del movimiento"""
        return self.cantidad * self.costo_unitario
    
    def save(self, *args, **kwargs):
        """
        Override de save() para actualizar stock automáticamente.
        
        IMPORTANTE: Solo se actualiza el stock en CREACIÓN (no en edición).
        Si necesitas corregir un movimiento, debes crear uno nuevo.
        """
        # Solo actualizar stock en creación (no tiene pk aún)
        if not self.pk:
            # Guardar stock anterior
            self.stock_anterior = self.producto.stock_actual
            
            # Calcular nuevo stock
            if self.tipo == 'entrada':
                self.producto.stock_actual += self.cantidad
            else:  # salida
                self.producto.stock_actual -= self.cantidad
            
            # Guardar stock posterior
            self.stock_posterior = self.producto.stock_actual
            
            # Guardar el producto con el nuevo stock
            self.producto.save(update_fields=['stock_actual', 'fecha_actualizacion'])
        
        super().save(*args, **kwargs)


# ============================================================================
# MODELO: SOLICITUD DE BAJA
# ============================================================================
class SolicitudBaja(models.Model):
    """
    Solicitud de baja de producto del almacén.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Cuando alguien necesita un producto del almacén, debe crear una solicitud.
    El agente de almacén revisa la solicitud y decide si aprobarla o rechazarla.
    
    FLUJO:
    1. Solicitante crea la solicitud (estado: PENDIENTE)
    2. Agente de almacén revisa
    3. Si aprueba: se crea un MovimientoAlmacen de salida
    4. Si rechaza: se registra el motivo y queda cerrada
    
    Tipos de solicitud:
    - Consumo Interno: Para uso en oficina/recepción
    - Servicio Técnico: Pieza para reparar un equipo
    - Venta Mostrador: Venta directa a cliente
    - Transferencia: Mover a otra sucursal
    
    La solicitud puede vincularse a una OrdenServicio si es para reparación.
    """
    
    # ========== TIPO Y PRODUCTO ==========
    tipo_solicitud = models.CharField(
        max_length=20,
        choices=TIPO_SOLICITUD_ALMACEN_CHOICES,
        default='consumo_interno',
        verbose_name='Tipo de Solicitud',
        help_text='Propósito de la salida del producto'
    )
    producto = models.ForeignKey(
        ProductoAlmacen,
        on_delete=models.CASCADE,
        related_name='solicitudes_baja',
        verbose_name='Producto'
    )
    # Unidad específica (opcional - si se quiere dar de baja una unidad concreta)
    unidad_inventario = models.ForeignKey(
        'UnidadInventario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='solicitudes_baja',
        verbose_name='Unidad Específica',
        help_text='Seleccionar si desea dar de baja una unidad específica (con marca/modelo/serie)'
    )
    cantidad = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Cantidad Solicitada',
        help_text='Número de unidades que se necesitan'
    )
    
    # ========== VINCULACIÓN CON SERVICIO TÉCNICO ==========
    orden_servicio = models.ForeignKey(
        'servicio_tecnico.OrdenServicio',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='solicitudes_piezas_almacen',
        verbose_name='Orden de Servicio',
        help_text='Vincular con orden de servicio técnico (si aplica)'
    )
    
    # Técnico de laboratorio asignado (solo para tipo_solicitud='servicio_tecnico')
    tecnico_asignado = models.ForeignKey(
        'inventario.Empleado',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='solicitudes_tecnico_asignado',
        verbose_name='Técnico Asignado',
        help_text='Técnico de laboratorio que utilizará el producto (obligatorio para Servicio Técnico)'
    )
    
    # ========== SOLICITANTE ==========
    solicitante = models.ForeignKey(
        'inventario.Empleado',
        on_delete=models.SET_NULL,
        null=True,
        related_name='solicitudes_almacen',
        verbose_name='Solicitante',
        help_text='Empleado que solicita el producto'
    )
    fecha_solicitud = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Solicitud'
    )
    observaciones = models.TextField(
        blank=True,
        verbose_name='Observaciones del Solicitante',
        help_text='Motivo o detalles de la solicitud'
    )
    
    # ========== ESTADO ==========
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_SOLICITUD_BAJA_CHOICES,
        default='pendiente',
        verbose_name='Estado',
        help_text='Estado actual de la solicitud'
    )
    
    # ========== PROCESAMIENTO (por agente de almacén) ==========
    agente_almacen = models.ForeignKey(
        'inventario.Empleado',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='solicitudes_procesadas',
        verbose_name='Procesado por',
        help_text='Agente que aprobó o rechazó la solicitud'
    )
    fecha_procesado = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Procesamiento'
    )
    observaciones_agente = models.TextField(
        blank=True,
        verbose_name='Observaciones del Agente',
        help_text='Motivo de rechazo o notas del agente'
    )
    
    # ========== FLAGS ==========
    requiere_reposicion = models.BooleanField(
        default=False,
        verbose_name='Requiere Reposición',
        help_text='Marcar si después de esta baja el producto quedará bajo mínimo'
    )
    
    class Meta:
        verbose_name = 'Solicitud de Baja'
        verbose_name_plural = 'Solicitudes de Baja'
        ordering = ['-fecha_solicitud']
        indexes = [
            models.Index(fields=['estado']),
            models.Index(fields=['fecha_solicitud']),
        ]
    
    def __str__(self):
        estado_icon = {
            'pendiente': '🟡',
            'aprobada': '🟢',
            'rechazada': '🔴',
            'en_espera': '⏸️'
        }
        icon = estado_icon.get(self.estado, '❓')
        return f"{icon} {self.producto.codigo_producto} ({self.cantidad}) - {self.get_estado_display()}"
    
    def aprobar(self, agente, observaciones=''):
        """
        Aprueba la solicitud y crea el movimiento de salida.
        
        Args:
            agente: Empleado que aprueba
            observaciones: Notas opcionales
        
        Returns:
            MovimientoAlmacen: El movimiento creado
        """
        self.estado = 'aprobada'
        self.agente_almacen = agente
        self.fecha_procesado = timezone.now()
        self.observaciones_agente = observaciones
        
        # Verificar si requiere reposición después de esta salida
        stock_futuro = self.producto.stock_actual - self.cantidad
        if self.producto.tipo_producto == 'resurtible':
            self.requiere_reposicion = stock_futuro <= self.producto.stock_minimo
        
        self.save()
        
        # Si hay una unidad específica seleccionada, marcarla como no disponible
        if self.unidad_inventario:
            self.unidad_inventario.disponibilidad = 'asignada'
            # Si es para una orden de servicio, registrar el destino
            if self.orden_servicio:
                self.unidad_inventario.orden_servicio_destino = self.orden_servicio
            self.unidad_inventario.save()
        
        # Crear movimiento de salida
        movimiento = MovimientoAlmacen.objects.create(
            tipo='salida',
            producto=self.producto,
            cantidad=self.cantidad,
            costo_unitario=self.producto.costo_unitario,
            empleado=agente,
            orden_servicio=self.orden_servicio,
            solicitud_baja=self,
            observaciones=f"Solicitud aprobada: {observaciones}"
        )
        
        return movimiento
    
    def rechazar(self, agente, motivo):
        """
        Rechaza la solicitud.
        
        Args:
            agente: Empleado que rechaza
            motivo: Motivo del rechazo (obligatorio)
        """
        self.estado = 'rechazada'
        self.agente_almacen = agente
        self.fecha_procesado = timezone.now()
        self.observaciones_agente = motivo
        self.save()


# ============================================================================
# MODELO: AUDITORÍA
# ============================================================================
class Auditoria(models.Model):
    """
    Auditoría de inventario del almacén.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Una auditoría es cuando se cuenta físicamente el inventario y se compara
    con lo que dice el sistema. Esto ayuda a detectar:
    - Productos faltantes (robo, merma, errores)
    - Productos sobrantes (errores de registro)
    - Problemas recurrentes con ciertos productos
    
    Tipos de auditoría:
    - COMPLETA: Se cuentan TODOS los productos
    - CÍCLICA: Se cuenta por categoría o ubicación (rotando)
    - POR DIFERENCIAS: Se verifican productos con problemas previos
    - ABC: Se priorizan productos de alto valor (Pareto)
    
    Proceso:
    1. Se crea la auditoría y se asigna auditor
    2. El auditor cuenta físicamente
    3. Se registran diferencias encontradas (DiferenciaAuditoria)
    4. Se ajusta el sistema si es necesario
    5. Se cierra la auditoría
    """
    
    # ========== TIPO Y ESTADO ==========
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_AUDITORIA_CHOICES,
        verbose_name='Tipo de Auditoría',
        help_text='Enfoque de la auditoría'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_AUDITORIA_CHOICES,
        default='en_proceso',
        verbose_name='Estado'
    )
    
    # ========== UBICACIÓN ==========
    sucursal = models.ForeignKey(
        'inventario.Sucursal',
        on_delete=models.SET_NULL,
        null=True,
        related_name='auditorias_almacen',
        verbose_name='Sucursal',
        help_text='Sucursal donde se realiza la auditoría'
    )
    
    # ========== FECHAS ==========
    fecha_inicio = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Inicio'
    )
    fecha_fin = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Fin'
    )
    
    # ========== RESPONSABLE ==========
    auditor = models.ForeignKey(
        'inventario.Empleado',
        on_delete=models.SET_NULL,
        null=True,
        related_name='auditorias_almacen_realizadas',
        verbose_name='Auditor',
        help_text='Empleado que realiza la auditoría'
    )
    
    # ========== RESULTADOS ==========
    observaciones_generales = models.TextField(
        blank=True,
        verbose_name='Observaciones Generales',
        help_text='Comentarios sobre la auditoría'
    )
    total_productos_auditados = models.IntegerField(
        default=0,
        verbose_name='Total Productos Auditados'
    )
    total_diferencias_encontradas = models.IntegerField(
        default=0,
        verbose_name='Total Diferencias Encontradas'
    )
    
    class Meta:
        verbose_name = 'Auditoría'
        verbose_name_plural = 'Auditorías'
        ordering = ['-fecha_inicio']
    
    def __str__(self):
        return f"Auditoría {self.get_tipo_display()} - {self.fecha_inicio.strftime('%d/%m/%Y')}"
    
    def actualizar_totales(self):
        """Actualiza los contadores basándose en las diferencias registradas"""
        self.total_diferencias_encontradas = self.diferencias.count()
        # Total de productos auditados = productos con diferencia + productos OK
        # Por ahora solo contamos las diferencias
        self.save(update_fields=['total_diferencias_encontradas'])
    
    def finalizar(self):
        """Marca la auditoría como finalizada"""
        self.fecha_fin = timezone.now()
        if self.total_diferencias_encontradas > 0:
            self.estado = 'con_diferencias'
        else:
            self.estado = 'completada'
        self.save()


# ============================================================================
# MODELO: DIFERENCIA DE AUDITORÍA
# ============================================================================
class DiferenciaAuditoria(models.Model):
    """
    Diferencias encontradas durante una auditoría.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Cuando el conteo físico no coincide con el sistema, se registra aquí.
    
    Por cada producto con diferencia se guarda:
    - stock_sistema: Lo que decía el sistema antes de contar
    - stock_fisico: Lo que realmente había
    - diferencia: stock_fisico - stock_sistema
      - Positivo (+): Hay más de lo esperado (sobrante)
      - Negativo (-): Hay menos de lo esperado (faltante)
    - razon: Por qué cree el auditor que hay diferencia
    - evidencia: Foto como prueba (opcional)
    
    Después de registrar, un supervisor puede aprobar el ajuste,
    lo que actualizará el stock del sistema al valor físico.
    """
    
    # ========== RELACIONES ==========
    auditoria = models.ForeignKey(
        Auditoria,
        on_delete=models.CASCADE,
        related_name='diferencias',
        verbose_name='Auditoría'
    )
    producto = models.ForeignKey(
        ProductoAlmacen,
        on_delete=models.CASCADE,
        related_name='diferencias_auditoria',
        verbose_name='Producto'
    )
    
    # ========== CANTIDADES ==========
    stock_sistema = models.IntegerField(
        verbose_name='Stock en Sistema',
        help_text='Cantidad que indicaba el sistema'
    )
    stock_fisico = models.IntegerField(
        verbose_name='Stock Físico',
        help_text='Cantidad contada físicamente'
    )
    diferencia = models.IntegerField(
        verbose_name='Diferencia',
        help_text='Stock físico - Stock sistema. Negativo = faltante.'
    )
    
    # ========== ANÁLISIS ==========
    razon = models.CharField(
        max_length=20,
        choices=RAZON_DIFERENCIA_AUDITORIA_CHOICES,
        verbose_name='Razón de Diferencia',
        help_text='Causa probable de la diferencia'
    )
    razon_detalle = models.TextField(
        blank=True,
        verbose_name='Detalle de la Razón',
        help_text='Explicación más detallada'
    )
    evidencia = models.ImageField(
        upload_to='almacen/auditorias/evidencias/',
        blank=True,
        null=True,
        verbose_name='Evidencia Fotográfica',
        help_text='Foto de la situación encontrada'
    )
    
    # ========== AJUSTE ==========
    ajuste_realizado = models.BooleanField(
        default=False,
        verbose_name='Ajuste Realizado',
        help_text='¿Se ajustó el sistema al valor físico?'
    )
    fecha_ajuste = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Ajuste'
    )
    responsable_ajuste = models.ForeignKey(
        'inventario.Empleado',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ajustes_auditoria_realizados',
        verbose_name='Responsable del Ajuste'
    )
    acciones_correctivas = models.TextField(
        blank=True,
        verbose_name='Acciones Correctivas',
        help_text='Qué se hizo para corregir o prevenir'
    )
    
    class Meta:
        verbose_name = 'Diferencia de Auditoría'
        verbose_name_plural = 'Diferencias de Auditoría'
        ordering = ['-auditoria__fecha_inicio']
    
    def __str__(self):
        signo = '+' if self.diferencia > 0 else ''
        return f"{self.producto.codigo_producto}: {signo}{self.diferencia}"
    
    def save(self, *args, **kwargs):
        """Calcula la diferencia automáticamente"""
        self.diferencia = self.stock_fisico - self.stock_sistema
        super().save(*args, **kwargs)
    
    def aplicar_ajuste(self, responsable, acciones=''):
        """
        Aplica el ajuste al sistema, actualizando el stock del producto.
        
        Args:
            responsable: Empleado que autoriza el ajuste
            acciones: Descripción de acciones correctivas
        """
        if not self.ajuste_realizado:
            # Actualizar stock del producto al valor físico
            self.producto.stock_actual = self.stock_fisico
            self.producto.save(update_fields=['stock_actual', 'fecha_actualizacion'])
            
            # Registrar el ajuste
            self.ajuste_realizado = True
            self.fecha_ajuste = timezone.now()
            self.responsable_ajuste = responsable
            self.acciones_correctivas = acciones
            self.save()
            
            # Actualizar totales de la auditoría
            self.auditoria.actualizar_totales()


# ============================================================================
# MODELO: UNIDAD DE INVENTARIO
# ============================================================================
class UnidadInventario(models.Model):
    """
    Unidad individual de un producto en el almacén.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Mientras que ProductoAlmacen representa un TIPO de producto (ej: "SSD 1TB"),
    UnidadInventario representa CADA UNIDAD FÍSICA individual.
    
    ¿Por qué necesitamos esto?
    --------------------------
    Imagina que tienes 20 SSDs de 1TB en el almacén:
    - 5 son Samsung 870 EVO (nuevos, de compra)
    - 8 son Kingston A400 (nuevos, de compra)
    - 4 son Crucial MX500 (usados, recuperados de OS-1234)
    - 3 son Western Digital Blue (nuevos, de compra)
    
    Con solo ProductoAlmacen verías: "SSD 1TB: 20 unidades"
    Con UnidadInventario puedes ver CADA UNO con su marca, modelo, origen, etc.
    
    Casos de uso principales:
    -------------------------
    1. RASTREO POR NÚMERO DE SERIE:
       - Saber exactamente qué pieza se usó en qué reparación
       - Manejar garantías de componentes individuales
    
    2. DIFERENTES MARCAS/MODELOS:
       - Un "SSD 1TB" puede ser Samsung, Kingston, Crucial, etc.
       - Diferentes precios de compra por marca
       - Diferentes niveles de calidad
    
    3. ORIGEN DE LA PIEZA:
       - ¿Se compró nueva?
       - ¿Se recuperó de un equipo en servicio técnico?
       - ¿Es devolución de cliente?
    
    4. ESTADO FÍSICO:
       - Nuevo, usado (buen estado), usado (regular), reparado, defectuoso
       - Permite ofrecer precios diferenciados (pieza nueva vs usada)
    
    Relaciones importantes:
    -----------------------
    - producto: ForeignKey a ProductoAlmacen (el tipo genérico)
    - orden_servicio_origen: De qué OS vino (si fue recuperada)
    - orden_servicio_destino: A qué OS fue asignada
    - compra: De qué compra proviene (si fue comprada)
    - movimiento_entrada/salida: Registro de movimientos
    """
    
    # ========== RELACIÓN CON PRODUCTO GENÉRICO ==========
    producto = models.ForeignKey(
        ProductoAlmacen,
        on_delete=models.CASCADE,
        related_name='unidades',
        verbose_name='Producto',
        help_text='Tipo de producto al que pertenece esta unidad'
    )
    
    # ========== IDENTIFICACIÓN DE LA UNIDAD ==========
    codigo_interno = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Código Interno',
        help_text='Código único interno para esta unidad específica (autogenerado)'
    )
    numero_serie = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Número de Serie',
        help_text='S/N del fabricante (si aplica)'
    )
    
    # ========== MARCA Y MODELO ESPECÍFICOS ==========
    marca = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Marca',
        help_text='Marca del fabricante (ej: Samsung, Kingston, Crucial)'
    )
    modelo = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Modelo',
        help_text='Modelo específico (ej: 870 EVO, A400, MX500)'
    )
    especificaciones = models.TextField(
        blank=True,
        verbose_name='Especificaciones',
        help_text='Detalles técnicos adicionales de esta unidad'
    )
    
    # ========== ESTADO Y DISPONIBILIDAD ==========
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_UNIDAD_CHOICES,
        default='nuevo',
        verbose_name='Estado',
        help_text='Condición física/funcional de la unidad'
    )
    disponibilidad = models.CharField(
        max_length=20,
        choices=DISPONIBILIDAD_UNIDAD_CHOICES,
        default='disponible',
        verbose_name='Disponibilidad',
        help_text='Estado operativo actual'
    )
    
    # ========== ORIGEN DE LA UNIDAD ==========
    origen = models.CharField(
        max_length=30,
        choices=ORIGEN_UNIDAD_CHOICES,
        default='compra',
        verbose_name='Origen',
        help_text='De dónde proviene esta unidad'
    )
    # Si vino de una orden de servicio (pieza recuperada)
    orden_servicio_origen = models.ForeignKey(
        'servicio_tecnico.OrdenServicio',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='unidades_recuperadas',
        verbose_name='Orden de Origen',
        help_text='OS de donde se recuperó esta pieza (si aplica)'
    )
    # Si fue asignada a una orden de servicio
    orden_servicio_destino = models.ForeignKey(
        'servicio_tecnico.OrdenServicio',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='unidades_asignadas',
        verbose_name='Orden de Destino',
        help_text='OS a la que se asignó esta pieza (si aplica)'
    )
    
    # ========== INFORMACIÓN DE COMPRA ==========
    compra = models.ForeignKey(
        CompraProducto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='unidades',
        verbose_name='Compra',
        help_text='Registro de compra de donde proviene'
    )
    costo_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Costo de Adquisición',
        help_text='Costo pagado por esta unidad específica'
    )
    
    # ========== UBICACIÓN ==========
    ubicacion_especifica = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Ubicación Específica',
        help_text='Ubicación exacta dentro del almacén (ej: Caja A-3)'
    )
    
    # ========== NOTAS ==========
    notas = models.TextField(
        blank=True,
        verbose_name='Notas',
        help_text='Observaciones adicionales sobre esta unidad'
    )
    
    # ========== AUDITORÍA ==========
    fecha_registro = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Registro'
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización'
    )
    registrado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='unidades_registradas',
        verbose_name='Registrado por'
    )
    
    class Meta:
        verbose_name = 'Unidad de Inventario'
        verbose_name_plural = 'Unidades de Inventario'
        ordering = ['-fecha_registro']
        indexes = [
            models.Index(fields=['producto', 'disponibilidad']),
            models.Index(fields=['marca']),
            models.Index(fields=['estado']),
            models.Index(fields=['numero_serie']),
            models.Index(fields=['codigo_interno']),
        ]
    
    def __str__(self):
        """
        Representación de la unidad.
        Formato: [CÓDIGO] MARCA MODELO (Estado)
        """
        partes = []
        if self.codigo_interno:
            partes.append(f"[{self.codigo_interno}]")
        if self.marca:
            partes.append(self.marca)
        if self.modelo:
            partes.append(self.modelo)
        if not partes:
            partes.append(self.producto.nombre)
        return f"{' '.join(partes)} ({self.get_estado_display()})"
    
    def save(self, *args, **kwargs):
        """
        Al guardar, genera código interno si no existe.
        Formato: ALM-{producto_id}-{timestamp}
        """
        if not self.codigo_interno:
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            self.codigo_interno = f"ALM-{self.producto_id or 0}-{timestamp}"
        super().save(*args, **kwargs)
    
    def esta_disponible(self):
        """
        Verifica si la unidad está disponible para asignar.
        
        Returns:
            bool: True si está disponible y en buen estado
        """
        estados_usables = ['nuevo', 'usado_bueno', 'reparado']
        return (
            self.disponibilidad == 'disponible' and
            self.estado in estados_usables
        )
    
    def reservar(self, orden_servicio=None):
        """
        Reserva la unidad para una orden de servicio.
        
        Args:
            orden_servicio: OrdenServicio que la reserva (opcional)
        """
        if self.disponibilidad == 'disponible':
            self.disponibilidad = 'reservada'
            if orden_servicio:
                self.orden_servicio_destino = orden_servicio
            self.save()
            return True
        return False
    
    def asignar(self, orden_servicio):
        """
        Asigna la unidad a una orden de servicio (salida de almacén).
        
        Args:
            orden_servicio: OrdenServicio a la que se asigna
        """
        if self.disponibilidad in ['disponible', 'reservada']:
            self.disponibilidad = 'asignada'
            self.orden_servicio_destino = orden_servicio
            self.save()
            return True
        return False
    
    def liberar(self):
        """
        Libera la unidad (cancela reserva o devolución).
        """
        if self.disponibilidad in ['reservada', 'asignada']:
            self.disponibilidad = 'disponible'
            self.orden_servicio_destino = None
            self.save()
            return True
        return False
    
    def marcar_vendida(self):
        """Marca la unidad como vendida."""
        self.disponibilidad = 'vendida'
        self.save()
    
    def marcar_descartada(self, motivo=''):
        """Marca la unidad como descartada/baja."""
        self.disponibilidad = 'descartada'
        if motivo:
            self.notas = f"{self.notas}\n[BAJA] {motivo}".strip()
        self.save()
    
    def get_info_completa(self):
        """
        Retorna información completa de la unidad en formato legible.
        
        Returns:
            str: Descripción completa
        """
        partes = [self.producto.nombre]
        if self.marca:
            partes.append(f"Marca: {self.marca}")
        if self.modelo:
            partes.append(f"Modelo: {self.modelo}")
        if self.numero_serie:
            partes.append(f"S/N: {self.numero_serie}")
        partes.append(f"Estado: {self.get_estado_display()}")
        return " | ".join(partes)
    
    def get_badge_estado(self):
        """
        Retorna la clase CSS para el badge de estado.
        
        Returns:
            str: Clase CSS de Bootstrap
        """
        estados_css = {
            'nuevo': 'success',
            'usado_bueno': 'primary',
            'usado_regular': 'info',
            'reparado': 'warning',
            'defectuoso': 'danger',
            'para_revision': 'secondary',
        }
        return estados_css.get(self.estado, 'secondary')
    
    def get_badge_disponibilidad(self):
        """
        Retorna la clase CSS para el badge de disponibilidad.
        
        Returns:
            str: Clase CSS de Bootstrap
        """
        disponibilidad_css = {
            'disponible': 'success',
            'reservada': 'warning',
            'asignada': 'info',
            'vendida': 'secondary',
            'descartada': 'dark',
        }
        return disponibilidad_css.get(self.disponibilidad, 'secondary')


# ============================================================================
# MODELO: SOLICITUD DE COTIZACIÓN (MULTI-PROVEEDOR)
# ============================================================================
class SolicitudCotizacion(models.Model):
    """
    Cabecera de cotización que agrupa múltiples líneas con diferentes proveedores.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Este modelo es la "cabecera" o "paraguas" que agrupa varias piezas cotizadas.
    
    ¿Por qué es necesario?
    ----------------------
    Antes, cada CompraProducto era independiente. Si necesitabas cotizar:
    - RAM de Amazon
    - Disco Duro de Mercado Libre
    - Fuente de poder de Steren
    
    Tenías que crear 3 cotizaciones separadas, lo cual era confuso para el cliente.
    
    Ahora con SolicitudCotizacion:
    - Creas UNA solicitud vinculada a la orden de servicio
    - Agregas múltiples líneas (cada una con su producto y proveedor)
    - El cliente ve TODO junto y puede aprobar/rechazar línea por línea
    - Al aprobar, se generan automáticamente las CompraProducto correspondientes
    
    FLUJO:
    ------
    1. Compras crea la solicitud (estado: borrador)
    2. Compras agrega las líneas con productos y proveedores
    3. Compras libera la solicitud (estado: enviada_cliente)
    4. Recepción comparte con el cliente
    5. Cliente aprueba/rechaza por línea
    6. Para líneas aprobadas, se generan CompraProducto automáticamente
    
    Campos importantes:
    - numero_solicitud: Identificador único auto-generado (SOL-2025-0001)
    - orden_servicio: Vinculación con la orden de servicio técnico
    - numero_orden_cliente: Número visible para buscar (ej: OOW-12345)
    - estado: Estado general de la solicitud
    - lineas: Relación con LineaCotizacion (cada producto/proveedor)
    """
    
    # ========== IDENTIFICACIÓN ==========
    numero_solicitud = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        verbose_name='Número de Solicitud',
        help_text='Identificador único auto-generado (SOL-2025-0001)'
    )
    
    # ========== VINCULACIÓN CON SERVICIO TÉCNICO ==========
    orden_servicio = models.ForeignKey(
        'servicio_tecnico.OrdenServicio',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='solicitudes_cotizacion',
        verbose_name='Orden de Servicio',
        help_text='Orden de servicio técnico asociada'
    )
    # Campo para búsqueda rápida (se sincroniza desde orden_servicio)
    numero_orden_cliente = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
        verbose_name='Número de Orden Cliente',
        help_text='Número visible para el cliente (ej: OOW-12345, FL-67890)'
    )
    
    # ========== ESTADO ==========
    estado = models.CharField(
        max_length=25,
        choices=ESTADO_SOLICITUD_COTIZACION_CHOICES,
        default='borrador',
        verbose_name='Estado',
        help_text='Estado actual de la solicitud de cotización'
    )
    
    # ========== FECHAS DE WORKFLOW ==========
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación'
    )
    fecha_envio_cliente = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha Envío a Cliente',
        help_text='Cuándo se liberó para compartir con el cliente'
    )
    fecha_respuesta_cliente = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha Respuesta Cliente',
        help_text='Cuándo el cliente respondió (última respuesta)'
    )
    fecha_completada = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha Completada',
        help_text='Cuándo se generaron todas las compras'
    )
    
    # ========== OBSERVACIONES ==========
    observaciones = models.TextField(
        blank=True,
        verbose_name='Observaciones',
        help_text='Notas internas sobre esta solicitud'
    )
    observaciones_cliente = models.TextField(
        blank=True,
        verbose_name='Observaciones del Cliente',
        help_text='Comentarios o feedback del cliente'
    )
    
    # ========== AUDITORÍA ==========
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='solicitudes_cotizacion_creadas',
        verbose_name='Creado por'
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización'
    )
    
    class Meta:
        verbose_name = 'Solicitud de Cotización'
        verbose_name_plural = 'Solicitudes de Cotización'
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['numero_solicitud']),
            models.Index(fields=['numero_orden_cliente']),
            models.Index(fields=['estado']),
        ]
    
    def __str__(self):
        """
        Representación en texto de la solicitud.
        Muestra: número de solicitud + orden cliente + estado
        """
        orden_info = f" | {self.numero_orden_cliente}" if self.numero_orden_cliente else ""
        return f"📋 {self.numero_solicitud}{orden_info} ({self.get_estado_display()})"
    
    def save(self, *args, **kwargs):
        """
        Override de save() para:
        1. Generar número de solicitud automáticamente
        2. Sincronizar numero_orden_cliente desde orden_servicio
        """
        # Generar número de solicitud si es nuevo
        if not self.numero_solicitud:
            self.numero_solicitud = self._generar_numero_solicitud()
        
        # Sincronizar número de orden cliente desde DetalleEquipo
        if self.orden_servicio and hasattr(self.orden_servicio, 'detalle_equipo'):
            detalle = getattr(self.orden_servicio, 'detalle_equipo', None)
            if detalle and hasattr(detalle, 'orden_cliente'):
                self.numero_orden_cliente = detalle.orden_cliente or ''
        
        super().save(*args, **kwargs)
    
    def _generar_numero_solicitud(self):
        """
        Genera un número de solicitud único con formato: SOL-YYYY-NNNN
        
        EXPLICACIÓN:
        - SOL: Prefijo para Solicitud
        - YYYY: Año actual
        - NNNN: Número secuencial con ceros a la izquierda
        
        Returns:
            str: Número generado (ej: SOL-2025-0001)
        """
        from django.db.models import Max
        import re
        
        año_actual = timezone.now().year
        prefijo = f"SOL-{año_actual}-"
        
        # Buscar el último número de este año
        ultima_solicitud = SolicitudCotizacion.objects.filter(
            numero_solicitud__startswith=prefijo
        ).aggregate(Max('numero_solicitud'))['numero_solicitud__max']
        
        if ultima_solicitud:
            # Extraer el número secuencial
            match = re.search(r'(\d{4})$', ultima_solicitud)
            if match:
                siguiente_numero = int(match.group(1)) + 1
            else:
                siguiente_numero = 1
        else:
            siguiente_numero = 1
        
        return f"{prefijo}{siguiente_numero:04d}"
    
    # ========== PROPIEDADES CALCULADAS ==========
    
    @property
    def total_lineas(self):
        """Número total de líneas en esta solicitud"""
        return self.lineas.count()
    
    @property
    def lineas_aprobadas(self):
        """Número de líneas aprobadas por el cliente"""
        return self.lineas.filter(estado_cliente='aprobada').count()
    
    @property
    def lineas_rechazadas(self):
        """Número de líneas rechazadas por el cliente"""
        return self.lineas.filter(estado_cliente='rechazada').count()
    
    @property
    def lineas_pendientes(self):
        """Número de líneas pendientes de respuesta"""
        return self.lineas.filter(estado_cliente='pendiente').count()
    
    @property
    def costo_total(self):
        """
        Suma total de todas las líneas.
        
        Returns:
            Decimal: Suma de (cantidad × costo_unitario) de todas las líneas
        """
        from django.db.models import Sum, F
        total = self.lineas.aggregate(
            total=Sum(F('cantidad') * F('costo_unitario'))
        )['total']
        return total or 0
    
    @property
    def costo_aprobado(self):
        """
        Suma de las líneas aprobadas por el cliente.
        
        Returns:
            Decimal: Suma solo de líneas con estado_cliente='aprobada'
        """
        from django.db.models import Sum, F
        total = self.lineas.filter(estado_cliente='aprobada').aggregate(
            total=Sum(F('cantidad') * F('costo_unitario'))
        )['total']
        return total or 0
    
    # ========== MÉTODOS DE WORKFLOW ==========
    
    def puede_enviar_a_cliente(self):
        """
        Verifica si la solicitud puede enviarse al cliente.
        
        Condiciones:
        - Estado debe ser 'borrador'
        - Debe tener al menos una línea
        """
        return self.estado == 'borrador' and self.total_lineas > 0
    
    def enviar_a_cliente(self, usuario=None):
        """
        Cambia el estado a 'enviada_cliente' para que Recepción pueda compartir.
        
        Args:
            usuario: Usuario que realiza la acción (opcional, para auditoría)
        
        Returns:
            bool: True si se cambió el estado exitosamente
        """
        if not self.puede_enviar_a_cliente():
            return False
        
        self.estado = 'enviada_cliente'
        self.fecha_envio_cliente = timezone.now()
        self.save()
        return True
    
    def actualizar_estado_segun_lineas(self):
        """
        Actualiza el estado de la solicitud basándose en las respuestas de las líneas.
        
        LÓGICA:
        - Si todas las líneas están aprobadas → 'totalmente_aprobada'
        - Si todas las líneas están rechazadas → 'totalmente_rechazada'
        - Si hay mezcla de aprobadas y rechazadas → 'parcialmente_aprobada'
        - Si aún hay pendientes → mantiene 'enviada_cliente'
        
        Returns:
            str: Nuevo estado de la solicitud
        """
        if self.estado not in ['enviada_cliente', 'parcialmente_aprobada']:
            return self.estado
        
        total = self.total_lineas
        aprobadas = self.lineas_aprobadas
        rechazadas = self.lineas_rechazadas
        pendientes = self.lineas_pendientes
        
        if pendientes > 0:
            # Aún hay líneas sin respuesta
            return self.estado
        
        # Todas las líneas tienen respuesta
        self.fecha_respuesta_cliente = timezone.now()
        
        if aprobadas == total:
            self.estado = 'totalmente_aprobada'
        elif rechazadas == total:
            self.estado = 'totalmente_rechazada'
        else:
            self.estado = 'parcialmente_aprobada'
        
        self.save()
        return self.estado
    
    def puede_generar_compras(self):
        """
        Verifica si se pueden generar las CompraProducto.
        
        Condiciones:
        - Estado debe ser 'totalmente_aprobada' o 'parcialmente_aprobada'
        - Debe haber al menos una línea aprobada sin compra generada
        """
        return (
            self.estado in ['totalmente_aprobada', 'parcialmente_aprobada'] and
            self.lineas.filter(estado_cliente='aprobada', compra_generada__isnull=True).exists()
        )
    
    def generar_compras(self, usuario=None):
        """
        Genera CompraProducto para cada línea aprobada.
        
        Este método:
        1. Itera sobre las líneas aprobadas sin compra
        2. Crea un CompraProducto para cada una
        3. Vincula la compra con la línea
        4. Actualiza el estado de la solicitud a 'completada' cuando termina
        
        Args:
            usuario: Usuario que genera las compras (para registrado_por)
        
        Returns:
            list: Lista de CompraProducto creados
        """
        if not self.puede_generar_compras():
            return []
        
        compras_creadas = []
        lineas_pendientes = self.lineas.filter(
            estado_cliente='aprobada',
            compra_generada__isnull=True
        )
        
        for linea in lineas_pendientes:
            compra = CompraProducto.objects.create(
                tipo='cotizacion',  # Es cotización porque viene del sistema de cotizaciones
                estado='pendiente_llegada',
                producto=linea.producto,
                proveedor=linea.proveedor,
                cantidad=linea.cantidad,
                costo_unitario=linea.costo_unitario,
                costo_total=linea.cantidad * linea.costo_unitario,
                fecha_pedido=timezone.now().date(),
                orden_servicio=self.orden_servicio,
                orden_cliente=self.numero_orden_cliente,
                observaciones=f"Generada desde solicitud {self.numero_solicitud}",
                registrado_por=usuario,
            )
            
            # Vincular la compra con la línea
            linea.compra_generada = compra
            linea.estado_cliente = 'compra_generada'
            linea.save()
            
            compras_creadas.append(compra)
        
        # Actualizar estado de la solicitud
        if not self.lineas.filter(estado_cliente='aprobada', compra_generada__isnull=True).exists():
            self.estado = 'completada'
            self.fecha_completada = timezone.now()
            self.save()
        else:
            self.estado = 'en_proceso'
            self.save()
        
        return compras_creadas
    
    def cancelar(self, motivo=''):
        """
        Cancela la solicitud.
        
        Args:
            motivo: Razón de la cancelación (se guarda en observaciones)
        
        Returns:
            bool: True si se canceló exitosamente
        """
        if self.estado in ['completada', 'cancelada']:
            return False
        
        self.estado = 'cancelada'
        if motivo:
            self.observaciones = f"{self.observaciones}\n[CANCELADA] {motivo}".strip()
        self.save()
        return True
    
    # ========== MÉTODOS DE VISUALIZACIÓN ==========
    
    def get_badge_estado(self):
        """
        Retorna la clase CSS de Bootstrap para el badge de estado.
        
        Returns:
            str: Clase CSS (success, warning, danger, etc.)
        """
        estados_css = {
            'borrador': 'secondary',
            'enviada_cliente': 'info',
            'parcialmente_aprobada': 'warning',
            'totalmente_aprobada': 'success',
            'totalmente_rechazada': 'danger',
            'en_proceso': 'primary',
            'completada': 'success',
            'cancelada': 'dark',
        }
        return estados_css.get(self.estado, 'secondary')
    
    def get_progreso_respuesta(self):
        """
        Calcula el porcentaje de respuestas recibidas.
        
        Returns:
            int: Porcentaje de 0 a 100
        """
        total = self.total_lineas
        if total == 0:
            return 0
        respondidas = self.lineas_aprobadas + self.lineas_rechazadas
        return int((respondidas / total) * 100)


# ============================================================================
# MODELO: LÍNEA DE COTIZACIÓN
# ============================================================================
class LineaCotizacion(models.Model):
    """
    Cada línea representa un producto + proveedor dentro de una SolicitudCotizacion.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Mientras SolicitudCotizacion es la "cabecera" (información general),
    LineaCotizacion son los "detalles" (cada producto específico).
    
    Piensa en una factura:
    - La factura (SolicitudCotizacion) tiene: cliente, fecha, número
    - Cada línea (LineaCotizacion) tiene: producto, cantidad, precio
    
    ¿Qué hace especial a LineaCotizacion?
    --------------------------------------
    1. Cada línea puede tener un PROVEEDOR DIFERENTE
       - Línea 1: RAM DDR4 de Amazon
       - Línea 2: SSD de Mercado Libre
       - Línea 3: Fuente de Steren
    
    2. El cliente puede aprobar/rechazar CADA LÍNEA por separado
       - "Sí quiero la RAM, pero no el SSD"
    
    3. Al aprobar una línea, se genera automáticamente una CompraProducto
       - La compra queda vinculada a esta línea para trazabilidad
    
    Campos importantes:
    - solicitud: FK a SolicitudCotizacion (la cabecera)
    - producto: FK a ProductoAlmacen (qué se cotiza)
    - descripcion_pieza: Descripción específica de la pieza (no del producto genérico)
    - proveedor: FK a Proveedor (de dónde se comprará)
    - cantidad: Cuántas unidades
    - costo_unitario: Precio por unidad
    - estado_cliente: Si el cliente aprobó/rechazó esta línea
    - compra_generada: FK a CompraProducto (cuando se genera la compra)
    """
    
    # ========== RELACIÓN CON SOLICITUD ==========
    solicitud = models.ForeignKey(
        SolicitudCotizacion,
        on_delete=models.CASCADE,
        related_name='lineas',
        verbose_name='Solicitud de Cotización'
    )
    numero_linea = models.PositiveIntegerField(
        default=0,  # 0 indica que debe auto-asignarse
        verbose_name='Número de Línea',
        help_text='Orden de la línea dentro de la solicitud (se asigna automáticamente)'
    )
    
    # ========== PRODUCTO Y DESCRIPCIÓN ==========
    producto = models.ForeignKey(
        ProductoAlmacen,
        on_delete=models.PROTECT,
        related_name='lineas_cotizacion',
        verbose_name='Producto',
        help_text='Producto del catálogo de almacén'
    )
    descripcion_pieza = models.CharField(
        max_length=255,
        verbose_name='Descripción de la Pieza',
        help_text='Descripción específica (ej: "RAM DDR4 16GB 3200MHz Kingston Fury")'
    )
    
    # ========== PROVEEDOR ==========
    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.SET_NULL,
        null=True,
        related_name='lineas_cotizacion',
        verbose_name='Proveedor',
        help_text='Proveedor donde se comprará esta pieza'
    )
    
    # ========== CANTIDADES Y COSTOS ==========
    cantidad = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name='Cantidad',
        help_text='Número de unidades a cotizar'
    )
    costo_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Costo Unitario',
        help_text='Precio por unidad (MXN)'
    )
    
    # ========== ESTADO DEL CLIENTE ==========
    estado_cliente = models.CharField(
        max_length=20,
        choices=ESTADO_LINEA_COTIZACION_CHOICES,
        default='pendiente',
        verbose_name='Estado del Cliente',
        help_text='Respuesta del cliente para esta línea'
    )
    fecha_respuesta = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Respuesta',
        help_text='Cuándo el cliente respondió'
    )
    motivo_rechazo = models.TextField(
        blank=True,
        verbose_name='Motivo de Rechazo',
        help_text='Si el cliente rechazó, por qué'
    )
    
    # ========== VINCULACIÓN CON COMPRA ==========
    compra_generada = models.OneToOneField(
        CompraProducto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='linea_cotizacion_origen',
        verbose_name='Compra Generada',
        help_text='CompraProducto creada al aprobar esta línea'
    )
    
    # ========== INFORMACIÓN ADICIONAL ==========
    notas = models.TextField(
        blank=True,
        verbose_name='Notas',
        help_text='Observaciones sobre esta línea'
    )
    tiempo_entrega_estimado = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Tiempo de Entrega (días)',
        help_text='Días estimados para recibir del proveedor'
    )
    
    # ========== AUDITORÍA ==========
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación'
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización'
    )
    
    class Meta:
        verbose_name = 'Línea de Cotización'
        verbose_name_plural = 'Líneas de Cotización'
        ordering = ['solicitud', 'numero_linea']
        unique_together = ['solicitud', 'numero_linea']
    
    def __str__(self):
        """
        Representación en texto de la línea.
        Muestra: número de línea + descripción + cantidad + proveedor
        """
        proveedor_nombre = self.proveedor.nombre if self.proveedor else 'Sin proveedor'
        return f"#{self.numero_linea}: {self.descripcion_pieza} x{self.cantidad} ({proveedor_nombre})"
    
    def save(self, *args, **kwargs):
        """
        Override de save() para:
        1. Auto-asignar número de línea si es nuevo o tiene valor 0
        2. Copiar tiempo de entrega del proveedor si no se especifica
        
        EXPLICACIÓN:
        - numero_linea=0 indica que debe auto-asignarse
        - El formset envía todas las líneas con numero_linea=0
        - Esta lógica calcula el siguiente número disponible
        """
        # Auto-asignar número de línea si es nuevo o tiene valor 0
        if not self.numero_linea or self.numero_linea == 0:
            max_linea = LineaCotizacion.objects.filter(
                solicitud=self.solicitud
            ).aggregate(models.Max('numero_linea'))['numero_linea__max']
            self.numero_linea = (max_linea or 0) + 1
        
        # Copiar tiempo de entrega del proveedor si no se especifica
        if self.tiempo_entrega_estimado is None and self.proveedor:
            self.tiempo_entrega_estimado = self.proveedor.tiempo_entrega_dias
        
        super().save(*args, **kwargs)
    
    # ========== PROPIEDADES CALCULADAS ==========
    
    @property
    def subtotal(self):
        """
        Calcula el subtotal de esta línea.
        
        Returns:
            Decimal: cantidad × costo_unitario
        """
        return self.cantidad * self.costo_unitario
    
    # ========== MÉTODOS DE WORKFLOW ==========
    
    def puede_aprobar(self):
        """Verifica si la línea puede ser aprobada"""
        return self.estado_cliente == 'pendiente'
    
    def puede_rechazar(self):
        """Verifica si la línea puede ser rechazada"""
        return self.estado_cliente == 'pendiente'
    
    def aprobar(self):
        """
        Marca la línea como aprobada por el cliente.
        
        Returns:
            bool: True si se aprobó exitosamente
        """
        if not self.puede_aprobar():
            return False
        
        self.estado_cliente = 'aprobada'
        self.fecha_respuesta = timezone.now()
        self.save()
        
        # Actualizar estado de la solicitud
        self.solicitud.actualizar_estado_segun_lineas()
        
        return True
    
    def rechazar(self, motivo=''):
        """
        Marca la línea como rechazada por el cliente.
        
        Args:
            motivo: Razón del rechazo
        
        Returns:
            bool: True si se rechazó exitosamente
        """
        if not self.puede_rechazar():
            return False
        
        self.estado_cliente = 'rechazada'
        self.fecha_respuesta = timezone.now()
        if motivo:
            self.motivo_rechazo = motivo
        self.save()
        
        # Actualizar estado de la solicitud
        self.solicitud.actualizar_estado_segun_lineas()
        
        return True
    
    # ========== MÉTODOS DE VISUALIZACIÓN ==========
    
    def get_badge_estado(self):
        """
        Retorna la clase CSS de Bootstrap para el badge de estado.
        
        Returns:
            str: Clase CSS (success, warning, danger, etc.)
        """
        estados_css = {
            'pendiente': 'secondary',
            'aprobada': 'success',
            'rechazada': 'danger',
            'compra_generada': 'primary',
        }
        return estados_css.get(self.estado_cliente, 'secondary')
    
    def get_estado_icon(self):
        """
        Retorna el icono Bootstrap Icons para el estado.
        
        Returns:
            str: Nombre del icono (ej: 'check-circle', 'x-circle')
        """
        estados_icon = {
            'pendiente': 'hourglass-split',
            'aprobada': 'check-circle-fill',
            'rechazada': 'x-circle-fill',
            'compra_generada': 'cart-check-fill',
        }
        return estados_icon.get(self.estado_cliente, 'question-circle')
