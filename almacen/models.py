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
    # Nuevas constantes para UnidadInventario
    ESTADO_UNIDAD_CHOICES,
    ORIGEN_UNIDAD_CHOICES,
    DISPONIBILIDAD_UNIDAD_CHOICES,
    MARCAS_COMPONENTES_CHOICES,
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
    Historial de compras de productos.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Cada vez que compramos productos, se registra aquí. Esto permite:
    - Ver el historial de precios de cada producto
    - Comparar proveedores (quién da mejor precio, quién entrega más rápido)
    - Saber cuánto hemos gastado en cada producto
    - Vincular compras con órdenes de servicio técnico
    
    Campos importantes:
    - producto: Qué producto se compró
    - proveedor: A quién se compró (puede ser diferente al proveedor principal)
    - cantidad: Cuántas unidades
    - costo_unitario: Precio por unidad EN ESTA COMPRA
    - costo_total: cantidad × costo_unitario (calculado automáticamente)
    - fecha_pedido: Cuándo se hizo el pedido
    - fecha_recepcion: Cuándo llegó (para calcular días de entrega)
    - orden_servicio: Si la compra es para un servicio técnico específico
    
    NOTA: Al guardar una compra, NO se actualiza automáticamente el stock.
    El stock se actualiza a través de MovimientoAlmacen (entrada).
    """
    
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
    
    class Meta:
        verbose_name = 'Compra de Producto'
        verbose_name_plural = 'Compras de Productos'
        ordering = ['-fecha_recepcion', '-fecha_pedido']
    
    def __str__(self):
        return f"{self.producto.codigo_producto} - {self.cantidad} uds @ ${self.costo_unitario} ({self.fecha_pedido})"
    
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
        3. Actualiza el costo_unitario del producto (último costo)
        """
        # Calcular costo total
        self.costo_total = self.cantidad * self.costo_unitario
        
        # Calcular días de entrega
        self.dias_entrega = self.calcular_dias_entrega()
        
        # Actualizar costo unitario del producto con el último costo
        if self.producto:
            self.producto.costo_unitario = self.costo_unitario
            self.producto.save(update_fields=['costo_unitario', 'fecha_actualizacion'])
        
        super().save(*args, **kwargs)


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
