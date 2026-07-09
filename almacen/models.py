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
from django.core.validators import MinValueValidator, FileExtensionValidator
from config.validators import FileSizeValidator
from django.utils import timezone
from PIL import Image
import io
import os

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
    OPCION_PAGO_REAC_CHOICES,
    # Constantes para datos del cliente en cotizaciones
    MARCAS_EQUIPOS_CHOICES,
    TIPO_EQUIPO_CHOICES,
    # Constantes para servicios adicionales (Venta Mostrador en cotizaciones)
    TIPO_SERVICIO_ADICIONAL_CHOICES,
    PRECIOS_SERVICIOS_ADICIONALES,
    MAPEO_SERVICIO_A_VENTA_MOSTRADOR,
)

import logging
logger = logging.getLogger('almacen')


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

    def get_bg_class(self):
        """
        Retorna la clase CSS para el fondo de la categoría basado en su nombre.
        Se usa en los templates para asignar colores específicos.
        """
        nombre_lower = self.nombre.lower()
        
        if 'accesorios' in nombre_lower:
            return 'bg-accesorios'
        elif 'audio' in nombre_lower or 'video' in nombre_lower:
            return 'bg-audio-video'
        elif 'bater' in nombre_lower:
            return 'bg-baterias'
        elif 'cable' in nombre_lower or 'conector' in nombre_lower:
            return 'bg-cables-conectores'
        elif 'carcasa' in nombre_lower or 'estructura' in nombre_lower:
            return 'bg-carcasas-estructuras'
        elif 'cargador' in nombre_lower or 'adaptador' in nombre_lower:
            return 'bg-cargadores-adaptadores'
        elif 'input' in nombre_lower:
            return 'bg-componentes-input'
        elif 'disco' in nombre_lower or 'almacenamiento' in nombre_lower:
            return 'bg-discos-almacenamiento'
        elif 'equipo' in nombre_lower or 'completo' in nombre_lower:
            return 'bg-equipos-completos'
        elif 'general' in nombre_lower:
            return 'bg-general'
        elif 'herramienta' in nombre_lower or 'consumible' in nombre_lower:
            return 'bg-herramientas-consumibles'
        elif 'memoria' in nombre_lower or 'ram' in nombre_lower:
            return 'bg-memoria-ram'
        elif 'pantalla' in nombre_lower or 'display' in nombre_lower:
            return 'bg-pantallas-displays'
        elif 'placa' in nombre_lower or 'tarjeta' in nombre_lower:
            return 'bg-placas-tarjetas'
        elif 'refrigera' in nombre_lower or 'enfri' in nombre_lower:
            return 'bg-refrigeracion'
        elif 'servicio' in nombre_lower or 'solucion' in nombre_lower:
            return 'bg-servicios-soluciones'
        else:
            return 'bg-default'

    def get_icon_name(self):
        """
        Retorna el nombre del archivo SVG (sin ruta, solo nombre base) para la categoría.
        """
        nombre_lower = self.nombre.lower()
        
        if 'accesorios' in nombre_lower:
            return 'accesorios.svg'
        elif 'audio' in nombre_lower or 'video' in nombre_lower:
            return 'audio_video.svg'
        elif 'bater' in nombre_lower:
            return 'baterias.svg'
        elif 'cable' in nombre_lower or 'conector' in nombre_lower:
            return 'cables_conectores.svg'
        elif 'carcasa' in nombre_lower or 'estructura' in nombre_lower:
            return 'carcasas_estructuras.svg'
        elif 'cargador' in nombre_lower or 'adaptador' in nombre_lower:
            return 'cargadores_adaptadores.svg'
        elif 'input' in nombre_lower:
            return 'componentes_input.svg'
        elif 'disco' in nombre_lower or 'almacenamiento' in nombre_lower:
            return 'discos_almacenamiento.svg'
        elif 'equipo' in nombre_lower or 'completo' in nombre_lower:
            return 'equipos_completos.svg'
        elif 'general' in nombre_lower:
            return 'general.svg'
        elif 'herramienta' in nombre_lower or 'consumible' in nombre_lower:
            return 'herramientas_consumibles.svg'
        elif 'memoria' in nombre_lower or 'ram' in nombre_lower:
            return 'memoria_ram.svg'
        elif 'pantalla' in nombre_lower or 'display' in nombre_lower:
            return 'pantallas_displays.svg'
        elif 'placa' in nombre_lower or 'tarjeta' in nombre_lower:
            return 'placas_tarjetas.svg'
        elif 'refrigera' in nombre_lower or 'enfri' in nombre_lower:
            return 'refrigeracion.svg'
        elif 'servicio' in nombre_lower or 'solucion' in nombre_lower:
            return 'servicios_soluciones.svg'
        else:
            return 'general.svg'


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
        help_text='Último costo de compra por unidad'
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
        max_length=255,  # Límite ampliado para soportar rutas largas
        blank=True,
        null=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'gif', 'webp']), FileSizeValidator(10)],
        verbose_name='Imagen del Producto',
        help_text='Foto del producto para identificación visual (JPG, PNG, GIF, WebP). Máx 10 MB.'
    )
    qr_code = models.ImageField(
        upload_to='almacen/qr_codes/',
        max_length=255,  # Límite ampliado para soportar rutas largas
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
    
    def unidades_asignadas(self):
        """
        Retorna las unidades asignadas a órdenes de servicio.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        --------------------------------
        Estas son piezas que ya están comprometidas con un servicio
        (provienen de cotizaciones aprobadas) pero aún no han sido
        físicamente entregadas/usadas en la reparación.
        
        Returns:
            QuerySet: Unidades con disponibilidad='asignada'
        """
        return self.unidades.filter(disponibilidad='asignada')
    
    def cantidad_unidades_asignadas(self):
        """
        Cuenta cuántas unidades están asignadas a servicios.
        
        Returns:
            int: Número de unidades comprometidas con órdenes de servicio
        """
        return self.unidades_asignadas().count()
    
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
        help_text='Precio por unidad en esta compra'
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
    
    def calcular_costo_promedio(self):
        """
        Calcula el costo promedio ponderado según las UnidadCompra.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        --------------------------------
        Cuando compras piezas de diferentes marcas con diferentes precios,
        este método calcula el costo promedio considerando las cantidades.
        
        Ejemplo:
        - 5 Kingston @ $100 = $500
        - 5 Samsung @ $120 = $600
        - Total: 10 piezas, $1100
        - Costo promedio: $1100 / 10 = $110
        
        Returns:
            Decimal: Costo promedio ponderado, o 0 si no hay unidades
        """
        from decimal import Decimal
        
        unidades = self.unidades_compra.all()
        
        if not unidades.exists():
            return Decimal('0')
        
        # Calcular suma ponderada: (cantidad × costo) para cada línea
        suma_total = Decimal('0')
        total_cantidad = 0
        
        for unidad in unidades:
            if unidad.costo_unitario is not None:
                suma_total += unidad.cantidad * unidad.costo_unitario
                total_cantidad += unidad.cantidad
        
        # Promedio ponderado
        if total_cantidad > 0:
            return suma_total / total_cantidad
        
        return Decimal('0')
    
    def actualizar_costo_desde_unidades(self):
        """
        Actualiza el costo_unitario de la compra basándose en las UnidadCompra.
        
        Este método se llama después de guardar las UnidadCompra para
        recalcular el costo promedio ponderado.
        
        Returns:
            bool: True si se actualizó el costo
        """
        costo_promedio = self.calcular_costo_promedio()
        
        if costo_promedio > 0:
            self.costo_unitario = costo_promedio
            self.costo_total = self.cantidad * self.costo_unitario
            self.save(update_fields=['costo_unitario', 'costo_total'])
            return True
        
        return False
    
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
        
        IMPORTANTE: También actualiza las UnidadInventario asociadas,
        marcándolas como 'descartada' para reflejar que ya no están
        disponibles en el inventario físico.
        
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
        
        # ============================================================
        # ACTUALIZAR UnidadInventario ASOCIADAS
        # ============================================================
        # Las UnidadInventario tienen una relación directa con CompraProducto
        # a través del campo 'compra'. Al devolver la compra, debemos marcar
        # todas las unidades como 'descartada' ya que físicamente fueron
        # devueltas al proveedor.
        # 
        # NOTA: Usamos self.unidades (related_name de UnidadInventario.compra)
        # ============================================================
        
        motivo_descarte = f'Devuelta al proveedor - Compra #{self.pk} ({self.get_estado_display()})'
        if self.motivo_problema:
            motivo_descarte += f' - {self.motivo_problema}'
        
        # Actualizar UnidadInventario vinculadas directamente a esta compra
        for unidad_inventario in self.unidades.all():
            # Solo actualizar si no está ya descartada
            if unidad_inventario.disponibilidad != 'descartada':
                unidad_inventario.marcar_descartada(motivo_descarte)
        
        # También actualizar UnidadCompra si existen (para compras con detalle)
        for unidad_compra in self.unidades_compra.all():
            if unidad_compra.estado != 'devuelta':
                unidad_compra.estado = 'devuelta'
                unidad_compra.save()
            
            # Marcar la UnidadInventario asociada a UnidadCompra
            if unidad_compra.unidad_inventario:
                if unidad_compra.unidad_inventario.disponibilidad != 'descartada':
                    unidad_compra.unidad_inventario.marcar_descartada(motivo_descarte)
        
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
    cantidad = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name='Cantidad',
        help_text='Cuántas piezas son de esta marca/modelo (ej: 5 Kingston, 3 Samsung)'
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
    
    def recibir(self, crear_unidad_inventario=True, orden_servicio_destino=None, registrado_por=None):
        """
        Marca esta unidad como recibida y crea N UnidadInventario según self.cantidad.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        --------------------------------
        Cuando una línea de compra tiene cantidad=5, este método crea
        5 UnidadInventario individuales, todas con la misma marca/modelo
        pero cada una es una pieza física separada.
        
        Args:
            crear_unidad_inventario: Si True, crea las UnidadInventario
            orden_servicio_destino: OrdenServicio a la que asignar las unidades (opcional)
            registrado_por: Usuario que registra la recepción (opcional)
        
        Returns:
            list[UnidadInventario]: Lista de unidades creadas, o lista vacía si no se crearon
        """
        if not self.puede_recibir():
            return []
        
        self.estado = 'recibida'
        self.fecha_recepcion = timezone.now()
        
        unidades_creadas = []
        
        if crear_unidad_inventario:
            # Crear N UnidadInventario según self.cantidad
            for i in range(self.cantidad):
                # Determinar disponibilidad
                disponibilidad = 'asignada' if orden_servicio_destino else 'disponible'
                
                # Crear cada unidad individual
                unidad = UnidadInventario.objects.create(
                    producto=self.compra.producto,
                    numero_serie=self.numero_serie if i == 0 else '',  # Solo la primera tiene S/N
                    marca=self.marca,
                    modelo=self.modelo,
                    especificaciones=self.especificaciones,
                    estado='nuevo',
                    disponibilidad=disponibilidad,
                    origen='compra',
                    compra=self.compra,
                    costo_unitario=self.costo_unitario,  # Costo específico de esta línea
                    orden_servicio_destino=orden_servicio_destino,
                    registrado_por=registrado_por,
                    notas=f'Creada desde compra #{self.compra.id}, línea {self.numero_linea} ({i+1}/{self.cantidad})'
                )
                unidades_creadas.append(unidad)
            
            # Vincular la primera unidad creada (para referencia)
            if unidades_creadas:
                self.unidad_inventario = unidades_creadas[0]
        
        self.save()
        return unidades_creadas
    
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
        max_length=15,  # Incrementado para 'transferencia' (13 chars)
        choices=TIPO_MOVIMIENTO_ALMACEN_CHOICES,
        verbose_name='Tipo de Movimiento',
        help_text='Entrada: suma al stock. Salida: resta del stock. Transferencia: no afecta stock.'
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
        tipo_icons = {
            'entrada': '📥',
            'salida': '📤',
            'transferencia': '🔄'
        }
        tipo_icon = tipo_icons.get(self.tipo, '📦')
        return f"{tipo_icon} {self.producto.codigo_producto} ({self.cantidad}) - {self.fecha.strftime('%d/%m/%Y %H:%M')}"
    
    def costo_total(self):
        """Retorna el costo total del movimiento"""
        return self.cantidad * self.costo_unitario
    
    def save(self, *args, **kwargs):
        """
        Override de save() para actualizar stock automáticamente.
        
        IMPORTANTE: Solo se actualiza el stock en CREACIÓN (no en edición).
        Si necesitas corregir un movimiento, debes crear uno nuevo.
        
        ACTUALIZADO (Enero 2026):
        - Las transferencias NO afectan el stock total (solo cambian ubicación)
        """
        # Solo actualizar stock en creación (no tiene pk aún)
        if not self.pk:
            # Guardar stock anterior
            self.stock_anterior = self.producto.stock_actual
            
            # Calcular nuevo stock (SOLO si NO es transferencia)
            if self.tipo == 'transferencia':
                # Transferencia: stock se mantiene igual (solo cambia ubicación)
                self.stock_posterior = self.producto.stock_actual
            elif self.tipo == 'entrada':
                self.producto.stock_actual += self.cantidad
                self.stock_posterior = self.producto.stock_actual
                self.producto.save(update_fields=['stock_actual', 'fecha_actualizacion'])
            else:  # salida
                self.producto.stock_actual -= self.cantidad
                self.stock_posterior = self.producto.stock_actual
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
    # DEPRECADO: Mantener por compatibilidad, usar unidades_seleccionadas para nuevas solicitudes
    unidad_inventario = models.ForeignKey(
        'UnidadInventario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='solicitudes_baja',
        verbose_name='Unidad Específica',
        help_text='Seleccionar si desea dar de baja una unidad específica (con marca/modelo/serie)'
    )
    # NUEVO (Enero 2026): Múltiples unidades seleccionadas para trazabilidad completa
    unidades_seleccionadas = models.ManyToManyField(
        'UnidadInventario',
        blank=True,
        related_name='solicitudes_baja_multiples',
        verbose_name='Unidades Seleccionadas',
        help_text='Unidades específicas seleccionadas para esta solicitud (obligatorio para trazabilidad)'
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
    
    # ========== TRANSFERENCIA ENTRE SUCURSALES ==========
    sucursal_destino = models.ForeignKey(
        'inventario.Sucursal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transferencias_entrantes',
        verbose_name='Sucursal Destino',
        help_text='Solo para transferencias: sucursal a donde se enviará el producto'
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
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        --------------------------------
        Este método hace 3 cosas importantes:
        1. Cambia el estado de la solicitud a 'aprobada'
        2. Marca las UnidadInventario como 'asignadas' (usa unidades_seleccionadas)
        3. Crea un MovimientoAlmacen que descuenta el stock automáticamente
        
        ACTUALIZADO (Enero 2026):
        - Prioriza unidades_seleccionadas (ManyToMany) para trazabilidad 100%
        - Fallback a lógica antigua si no hay unidades seleccionadas
        - Transferencias: NO descuentan stock, mantienen disponibilidad
        """
        self.estado = 'aprobada'
        self.agente_almacen = agente
        self.fecha_procesado = timezone.now()
        self.observaciones_agente = observaciones
        
        # ========== LÓGICA DIFERENCIADA: TRANSFERENCIA vs SALIDA NORMAL ==========
        es_transferencia = (self.tipo_solicitud == 'transferencia')
        
        # Verificar si requiere reposición (SOLO para salidas normales)
        if not es_transferencia:
            stock_futuro = self.producto.stock_actual - self.cantidad
            if self.producto.tipo_producto == 'resurtible':
                self.requiere_reposicion = stock_futuro <= self.producto.stock_minimo
        
        self.save()
        
        # ========== MARCAR UNIDADES ==========
        # PRIORIDAD: Usar unidades_seleccionadas (ManyToMany) - NUEVA LÓGICA
        unidades_a_marcar = list(self.unidades_seleccionadas.all())
        
        if unidades_a_marcar:
            # ✅ Hay unidades seleccionadas específicamente (nuevo flujo)
            for unidad in unidades_a_marcar:
                # TRANSFERENCIA: Mantener disponible y cambiar sucursal
                # SALIDA NORMAL: Marcar como asignada
                if es_transferencia:
                    unidad.disponibilidad = 'disponible'  # Se mantiene disponible
                    unidad.sucursal_actual = self.sucursal_destino
                else:
                    unidad.disponibilidad = 'asignada'
                    if self.orden_servicio:
                        unidad.orden_servicio_destino = self.orden_servicio
                
                unidad.save()
        else:
            # ⚠️ FALLBACK: Lógica antigua para compatibilidad con solicitudes viejas
            if self.unidad_inventario:
                # Caso 1: Se seleccionó una unidad específica (campo ForeignKey antiguo)
                unidades_a_marcar = [self.unidad_inventario]
                
                # Si se pidieron más de 1, buscar unidades adicionales
                if self.cantidad > 1:
                    unidades_adicionales = UnidadInventario.objects.filter(
                        producto=self.producto,
                        disponibilidad='disponible'
                    ).exclude(
                        pk=self.unidad_inventario.pk
                    )[:(self.cantidad - 1)]
                    
                    unidades_a_marcar.extend(unidades_adicionales)
            else:
                # Caso 2: Solicitud genérica (sin unidad específica)
                unidades_a_marcar = list(UnidadInventario.objects.filter(
                    producto=self.producto,
                    disponibilidad='disponible'
                )[:self.cantidad])
            
            # Marcar todas las unidades seleccionadas como asignadas
            for unidad in unidades_a_marcar:
                # TRANSFERENCIA: Mantener disponible y cambiar sucursal
                # SALIDA NORMAL: Marcar como asignada
                if es_transferencia:
                    unidad.disponibilidad = 'disponible'  # Se mantiene disponible
                    unidad.sucursal_actual = self.sucursal_destino
                else:
                    unidad.disponibilidad = 'asignada'
                    if self.orden_servicio:
                        unidad.orden_servicio_destino = self.orden_servicio
                
                unidad.save()
        
        # ========== CREAR MOVIMIENTO ==========
        # TRANSFERENCIA: tipo='transferencia' (no afecta stock)
        # SALIDA NORMAL: tipo='salida' (descuenta stock)
        tipo_movimiento = 'transferencia' if es_transferencia else 'salida'
        
        # Construir observaciones del movimiento
        obs_movimiento = observaciones if observaciones else ''
        if es_transferencia and self.sucursal_destino:
            obs_movimiento = f"Transferencia a {self.sucursal_destino.nombre}. {obs_movimiento}"
        else:
            obs_movimiento = f"Solicitud aprobada: {obs_movimiento}"
        
        movimiento = MovimientoAlmacen.objects.create(
            tipo=tipo_movimiento,
            producto=self.producto,
            cantidad=self.cantidad,
            costo_unitario=self.producto.costo_unitario,
            empleado=agente,
            orden_servicio=self.orden_servicio,
            solicitud_baja=self,
            observaciones=obs_movimiento
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
        max_length=255,  # Límite ampliado para soportar rutas largas
        blank=True,
        null=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'gif', 'webp']), FileSizeValidator(10)],
        verbose_name='Evidencia Fotográfica',
        help_text='Foto de la situación encontrada (JPG, PNG, GIF, WebP). Máx 10 MB.'
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
    sucursal_actual = models.ForeignKey(
        'inventario.Sucursal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='unidades_almacenadas',
        verbose_name='Sucursal Actual',
        help_text='Sucursal donde está esta unidad. Vacío = Almacén Central'
    )
    ubicacion_especifica = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Ubicación Específica',
        help_text='Ubicación exacta dentro del almacén (ej: Caja A-3, Estante 5)'
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
        Formato nuevo: {MARCA}-{MODELO}-{FECHA}
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        --------------------------------
        El código interno ahora incluye información más descriptiva:
        - MARCA: Nombre del fabricante (ej: SAMSUNG, KINGSTON)
        - MODELO: Modelo específico (ej: 870EVO, A400)
        - FECHA: Fecha de registro en formato YYYYMMDD
        
        Ejemplos:
        - SAMSUNG-870EVO-20260116
        - KINGSTON-A400-20260116
        - SINMARCA-SINMODELO-20260116 (si no tiene marca/modelo)
        
        Formato anterior: ALM-{producto_id}-{timestamp}
        Formato nuevo: {MARCA}-{MODELO}-{FECHA}
        """
        if not self.codigo_interno:
            # Obtener marca (limpiar espacios y convertir a mayúsculas)
            marca = (self.marca or 'SINMARCA').replace(' ', '').upper()
            
            # Obtener modelo (limpiar espacios y convertir a mayúsculas)
            modelo = (self.modelo or 'SINMODELO').replace(' ', '').upper()
            
            # Fecha en formato corto YYYYMMDD
            fecha = timezone.now().strftime('%Y%m%d')
            
            # Generar código: MARCA-MODELO-FECHA
            self.codigo_interno = f"{marca}-{modelo}-{fecha}"
            
            # Si ya existe este código, agregar sufijo incremental
            # Esto maneja el caso de múltiples unidades iguales en el mismo día
            contador = 1
            codigo_base = self.codigo_interno
            while UnidadInventario.objects.filter(codigo_interno=self.codigo_interno).exists():
                contador += 1
                self.codigo_interno = f"{codigo_base}-{contador:02d}"
        
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
    3. Compras libera la solicitud (estado: enviada_front)
    4. Recepción comparte con el cliente (estado: enviada_cliente)
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
    
    # ========== MODO SIN ORDEN ACTIVA ==========
    sin_orden_activa = models.BooleanField(
        default=False,
        verbose_name='Sin Orden Activa',
        help_text='Marcar si aún no existe una orden de servicio para esta cotización'
    )
    service_tag = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Service Tag',
        help_text='Número de serie o identificador del equipo cuando no hay orden activa'
    )
    
    # ========== DATOS DEL CLIENTE (cuando recepción solicita cotización) ==========
    nombre_cliente = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Nombre del Cliente',
        help_text='Nombre completo del cliente que solicita la cotización'
    )
    telefono_cliente = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Teléfono del Cliente',
        help_text='Número de contacto del cliente'
    )
    # ✅ NUEVO CAMPO: RFC del Cliente (Junio 2026)
    # Campo opcional para datos fiscales del cliente cuando no hay orden activa
    rfc_cliente = models.CharField(
        max_length=13,
        blank=True,
        verbose_name='RFC del Cliente',
        help_text='RFC del cliente (opcional, 13 caracteres persona física, 12 persona moral)'
    )
    email_cliente = models.EmailField(
        blank=True,
        verbose_name='Correo del Cliente',
        help_text='Correo electrónico del cliente para enviar la cotización'
    )
    marca = models.CharField(
        max_length=50,
        blank=True,
        choices=MARCAS_EQUIPOS_CHOICES,
        verbose_name='Marca del Equipo',
        help_text='Marca del equipo del cliente'
    )
    # ✅ NUEVO CAMPO: Tipo de Equipo (Junio 2026)
    # Permite clasificar el equipo cuando no hay orden activa vinculada
    tipo_equipo = models.CharField(
        max_length=10,
        blank=True,
        choices=TIPO_EQUIPO_CHOICES,
        verbose_name='Tipo de Equipo',
        help_text='Tipo de equipo del cliente (PC, Laptop, AIO)'
    )
    modelo = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Modelo del Equipo',
        help_text='Modelo del equipo del cliente (texto libre)'
    )

    # ========== PRECIOS AL CLIENTE (snapshot envío + totales al aprobar) ==========
    TIPO_SERVICIO_CLIENTE_CHOICES = [
        ('mostrador', 'Mostrador'),
        ('estandar', 'Estándar'),
        ('express', 'Express'),
        ('alta_gama', 'Alta Gama'),
        ('server', 'Server'),
        ('rep_nivel_componente', 'Reparación a nivel componente'),
    ]
    tipo_servicio_cliente = models.CharField(
        max_length=20,
        blank=True,
        default='',
        choices=TIPO_SERVICIO_CLIENTE_CHOICES,
        verbose_name='Perfil de profit enviado al cliente',
        help_text='Perfil de servicio usado al enviar la cotización por correo/PDF'
    )
    incluir_descuento_diagnostico_cliente = models.BooleanField(
        default=True,
        verbose_name='Descontar diagnóstico (envío al cliente)',
        help_text='Si el PDF enviado al cliente incluía descuento de diagnóstico'
    )
    fecha_precios_cliente = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha precios cliente',
        help_text='Cuándo se calcularon y guardaron los precios al cliente (al aprobar)'
    )
    precio_total_sin_iva_cliente = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Total cliente sin IVA',
        help_text='Total cotizado al cliente sin IVA (todas las líneas con costo)'
    )
    precio_total_con_iva_cliente = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Total cliente con IVA',
        help_text='Total cotizado al cliente con IVA incluido'
    )
    precio_total_menos_diagnostico_cliente = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Total cliente menos diagnóstico',
        help_text='Total con IVA restando diagnóstico ya pagado (si aplica)'
    )

    # ========== COTIZACIÓN EQUIPO REACONDICIONADO ==========
    MODO_COTIZACION_CLIENTE_CHOICES = [
        ('reparacion', 'Reparación'),
        ('reacondicionado', 'Equipo reacondicionado'),
    ]
    modo_cotizacion_cliente = models.CharField(
        max_length=20,
        choices=MODO_COTIZACION_CLIENTE_CHOICES,
        blank=True,
        default='reparacion',
        verbose_name='Modo de cotización enviada',
        help_text='Reparación por piezas o propuesta de equipo reacondicionado'
    )
    costo_proveedor_reac = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Costo proveedor (reacondicionado)',
        help_text='Costo de adquisición del equipo sin IVA'
    )
    dias_front_desk_reac = models.PositiveSmallIntegerField(
        default=1,
        verbose_name='Días front desk (reacondicionado)',
        help_text='Días proporcionales de recurso front desk para el costeo'
    )
    reac_marca = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Marca equipo ofertado',
    )
    reac_modelo = models.CharField(
        max_length=150,
        blank=True,
        verbose_name='Modelo equipo ofertado',
    )
    reac_procesador = models.CharField(
        max_length=150,
        blank=True,
        verbose_name='Procesador equipo ofertado',
    )
    reac_ram = models.CharField(
        max_length=80,
        blank=True,
        verbose_name='RAM equipo ofertado',
    )
    reac_sistema_operativo = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Sistema operativo equipo ofertado',
    )
    reac_incluye_cargador = models.BooleanField(
        default=False,
        verbose_name='Incluye cargador',
        help_text='Si el equipo reacondicionado incluye cargador original o compatible'
    )
    reac_especificaciones = models.TextField(
        blank=True,
        verbose_name='Especificaciones adicionales',
        help_text='Detalles extra del equipo (almacenamiento, pantalla, etc.)'
    )
    resultado_costeo_reac = models.JSONField(
        null=True,
        blank=True,
        verbose_name='Snapshot costeo reacondicionado',
        help_text='Resultado JSON de calcular_costeo al enviar la propuesta'
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
        3. Manejar modo sin_orden_activa con service_tag
        4. Crear Cotizacion en Servicio Técnico si tiene orden_servicio
        """
        # Generar número de solicitud si es nuevo
        if not self.numero_solicitud:
            self.numero_solicitud = self._generar_numero_solicitud()
        
        # Si tiene orden de servicio, sincronizar numero_orden_cliente
        if self.orden_servicio and hasattr(self.orden_servicio, 'detalle_equipo'):
            detalle = getattr(self.orden_servicio, 'detalle_equipo', None)
            if detalle and hasattr(detalle, 'orden_cliente'):
                self.numero_orden_cliente = detalle.orden_cliente or ''
            # Si se vincula una orden, desactivar modo sin_orden
            self.sin_orden_activa = False
        elif self.sin_orden_activa:
            # Si está en modo sin orden, usar service_tag como numero_orden_cliente
            self.service_tag = self.service_tag.upper().strip()
            self.numero_orden_cliente = self.service_tag
            self.orden_servicio = None
        
        super().save(*args, **kwargs)
        
        # Crear Cotizacion en Servicio Técnico si tiene orden_servicio
        if self.orden_servicio:
            self._sincronizar_cotizacion_st()
    
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
    
    def _sincronizar_cotizacion_st(self):
        """
        Crea o reutiliza la Cotizacion en Servicio Técnico para esta orden.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        --------------------------------
        Cuando una SolicitudCotizacion tiene orden_servicio vinculada,
        este método asegura que exista una Cotizacion correspondiente
        en el módulo de Servicio Técnico.
        
        Si ya existe (creada manualmente o desde diagnóstico), la reutiliza.
        Si no existe, la crea con costo_mano_obra = 0.
        
        Las piezas (PiezaCotizada) se sincronizan desde LineaCotizacion.save()
        
        IMPORTANTE — Órdenes FL- (Venta Mostrador):
        Para órdenes con tipo_servicio='venta_mostrador', NO se crea Cotizacion en ST.
        La lógica de cotización surge del diagnóstico técnico (flujo OOW-). En una
        venta mostrador directa (FL-) no hay diagnóstico previo, por lo que el objeto
        Cotizacion no tiene sentido. Las piezas van directamente a PiezaVentaMostrador
        y los servicios a VentaMostrador.
        """
        from servicio_tecnico.models import Cotizacion
        
        if not self.orden_servicio:
            return

        # Para órdenes de Venta Mostrador (FL-), no se crea Cotizacion en ST.
        # La cotización es un concepto del flujo de diagnóstico (OOW-) únicamente.
        if self.orden_servicio.tipo_servicio == 'venta_mostrador':
            return
        
        # Buscar o crear Cotizacion en ST
        cotizacion, creada = Cotizacion.objects.get_or_create(
            orden=self.orden_servicio,
            defaults={
                'fecha_envio': timezone.now(),
                'costo_mano_obra': 0,
            }
        )
        
        if creada:
            logger.info(
                f"Cotizacion creada en ST para orden {self.orden_servicio.numero_orden_interno} "
                f"desde SolicitudCotizacion {self.numero_solicitud}"
            )
    
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
        total = self.lineas.filter(
            estado_cliente__in=['aprobada', 'compra_generada']
        ).aggregate(
            total=Sum(F('cantidad') * F('costo_unitario'))
        )['total']
        return total or 0

    @property
    def precio_cliente_aprobado_sin_iva(self):
        """
        Suma del precio al cliente (sin IVA) de líneas aprobadas o con compra generada.

        Returns:
            Decimal: Total precio cliente de piezas aceptadas
        """
        from django.db.models import Sum
        total = self.lineas.filter(
            estado_cliente__in=['aprobada', 'compra_generada']
        ).aggregate(total=Sum('subtotal_cliente_sin_iva'))['total']
        return total or 0

    @property
    def margen_aprobado_estimado(self):
        """Diferencia entre precio cliente y costo proveedor en líneas aprobadas (sin IVA)."""
        from decimal import Decimal
        costo = self.costo_aprobado or Decimal('0')
        precio = self.precio_cliente_aprobado_sin_iva or Decimal('0')
        if precio <= 0:
            return Decimal('0')
        return precio - costo

    @property
    def cotizacion_precios_persistidos(self):
        """
        Indica si ya se calcularon y guardaron los precios al cliente.

        Returns:
            bool: True cuando existe fecha_precios_cliente y total sin IVA.
        """
        return bool(
            self.fecha_precios_cliente
            and self.precio_total_sin_iva_cliente
        )

    @property
    def servicios_aprobados_con_iva(self):
        """
        Suma de servicios adicionales aceptados por el cliente (precio con IVA).

        Los servicios se cotizan con IVA incluido; este monto es lo que paga el cliente.
        """
        from decimal import Decimal
        from django.db.models import Sum
        from config.constants import ESTADOS_LINEA_COTIZACION_ACEPTADA

        total = self.servicios_adicionales.filter(
            estado_cliente__in=ESTADOS_LINEA_COTIZACION_ACEPTADA
        ).aggregate(total=Sum('costo'))['total']
        return total or Decimal('0')

    @property
    def servicios_aprobados_sin_iva(self):
        """Servicios aceptados expresados sin IVA (costo con IVA ÷ 1.16)."""
        from decimal import Decimal, ROUND_HALF_UP

        con_iva = self.servicios_aprobados_con_iva or Decimal('0')
        if con_iva <= 0:
            return Decimal('0')
        return (con_iva / Decimal('1.16')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @property
    def piezas_aprobadas_con_iva(self):
        """Precio al cliente de piezas aceptadas, con IVA (16%)."""
        from decimal import Decimal, ROUND_HALF_UP

        sin_iva = self.precio_cliente_aprobado_sin_iva or Decimal('0')
        if sin_iva <= 0:
            return Decimal('0')
        return (sin_iva * Decimal('1.16')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @property
    def total_aprobado_sin_iva(self):
        """
        Total aceptado sin IVA: piezas (con profit) + servicios (sin IVA).

        Returns:
            Decimal: Monto neto de todo lo que el cliente aprobó.
        """
        from decimal import Decimal

        piezas = self.precio_cliente_aprobado_sin_iva or Decimal('0')
        servicios = self.servicios_aprobados_sin_iva or Decimal('0')
        return piezas + servicios

    @property
    def total_aprobado_con_iva(self):
        """
        Total real a cobrar al cliente por ítems aceptados (con IVA).

        Piezas: subtotal persistido × 1.16. Servicios: costo ya incluye IVA.
        """
        from decimal import Decimal

        return self.piezas_aprobadas_con_iva + (self.servicios_aprobados_con_iva or Decimal('0'))

    @property
    def tiene_items_aprobados_cliente(self):
        """True si hay al menos una pieza o servicio aceptado por el cliente."""
        from decimal import Decimal

        return (
            (self.costo_aprobado or Decimal('0')) > 0
            or (self.precio_cliente_aprobado_sin_iva or Decimal('0')) > 0
            or (self.servicios_aprobados_con_iva or Decimal('0')) > 0
        )

    def persistir_precios_cliente(self):
        """
        Calcula y guarda los precios al cliente en líneas y cabecera.

        Se invoca al aprobar la primera línea. Delega en el módulo de utilidades
        que replica la fórmula del PDF de cotización.
        """
        from almacen.utils.cotizacion_precios_cliente import persistir_precios_cliente_solicitud
        return persistir_precios_cliente_solicitud(self)
    
    # ========== PROPIEDADES DE SERVICIOS ADICIONALES ==========
    
    @property
    def total_servicios_adicionales(self):
        """Número total de servicios adicionales en esta solicitud."""
        return self.servicios_adicionales.count()
    
    @property
    def servicios_aprobados(self):
        """Número de servicios adicionales aprobados por el cliente."""
        return self.servicios_adicionales.filter(estado_cliente='aprobada').count()
    
    @property
    def servicios_rechazados(self):
        """Número de servicios adicionales rechazados por el cliente."""
        return self.servicios_adicionales.filter(estado_cliente='rechazada').count()
    
    @property
    def servicios_pendientes(self):
        """Número de servicios adicionales pendientes de respuesta."""
        return self.servicios_adicionales.filter(estado_cliente='pendiente').count()
    
    @property
    def costo_servicios_adicionales(self):
        """
        Suma total de todos los servicios adicionales.
        
        Returns:
            Decimal: Suma de costos de todos los servicios adicionales
        """
        from django.db.models import Sum
        total = self.servicios_adicionales.aggregate(
            total=Sum('costo')
        )['total']
        return total or 0
    
    @property
    def costo_servicios_aprobados(self):
        """
        Suma de los servicios adicionales aceptados (con IVA).

        Alias de servicios_aprobados_con_iva para compatibilidad con código existente.
        """
        return self.servicios_aprobados_con_iva
    
    @property
    def costo_total_con_servicios(self):
        """
        Suma total incluyendo piezas Y servicios adicionales.
        
        Returns:
            Decimal: costo_total + costo_servicios_adicionales
        """
        return self.costo_total + self.costo_servicios_adicionales
    
    @property
    def costo_aprobado_con_servicios(self):
        """
        Suma aprobada incluyendo piezas Y servicios adicionales.
        
        Returns:
            Decimal: costo_aprobado + costo_servicios_aprobados
        """
        return self.costo_aprobado + self.costo_servicios_aprobados
    
    @property
    def total_estimado(self):
        """
        Alias de costo_total para compatibilidad con templates.
        
        Returns:
            Decimal: Suma de (cantidad × costo_unitario) de todas las líneas
        """
        return self.costo_total
    
    @property
    def dias_sin_respuesta(self):
        """
        Calcula los días desde que se envió al cliente sin respuesta.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        --------------------------------
        Esta propiedad calcula cuántos días han pasado desde que la
        cotización fue enviada al cliente y aún no tiene respuesta completa.
        
        Útil para identificar cotizaciones "estancadas" que necesitan
        seguimiento con el cliente.
        
        Returns:
            int: Número de días sin respuesta (0 si ya fue respondida o no enviada)
        """
        # Calcular días tanto en enviada_front como en enviada_cliente
        if self.estado in ['enviada_front', 'enviada_cliente'] and self.fecha_envio_cliente:
            delta = timezone.now() - self.fecha_envio_cliente
            return delta.days
        elif self.estado in ['enviada_front', 'enviada_cliente'] and not self.fecha_envio_cliente:
            # Fallback: usar fecha de creación si no hay fecha de envío
            delta = timezone.now() - self.fecha_creacion
            return delta.days
        return 0
    
    # ========== MÉTODOS DE WORKFLOW ==========
    
    def puede_enviar_a_front(self):
        """
        Verifica si la solicitud puede enviarse a Front (recepción).
        
        Condiciones:
        - Estado debe ser 'borrador'
        - Debe tener al menos una línea
        """
        return self.estado == 'borrador' and self.total_lineas > 0
    
    def enviar_a_front(self, usuario=None):
        """
        Cambia el estado a 'enviada_front' para que Recepción pueda verla.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        --------------------------------
        Este método se llama cuando Compras termina de preparar la cotización
        y la libera para que Recepción la revise. En este estado, Recepción
        puede reenviar notificaciones y editar líneas, pero NO puede aprobar
        ni rechazar piezas (eso solo ocurre cuando se envía al cliente).
        
        Args:
            usuario: Usuario que realiza la acción (opcional, para auditoría)
        
        Returns:
            bool: True si se cambió el estado exitosamente
        """
        if not self.puede_enviar_a_front():
            return False
        
        self.estado = 'enviada_front'
        self.fecha_envio_cliente = timezone.now()
        self.save()
        return True
    
    def puede_enviar_a_cliente(self):
        """
        Verifica si la solicitud puede enviarse al cliente final.
        
        Condiciones:
        - Estado debe ser 'enviada_front' (ya fue revisada por recepción)
        - Debe tener al menos una línea
        """
        return self.estado == 'enviada_front' and self.total_lineas > 0
    
    def enviar_a_cliente(self, usuario=None):
        """
        Cambia el estado a 'enviada_cliente' para que el cliente pueda aprobar/rechazar.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        --------------------------------
        Este método se llama cuando Recepción comparte la cotización con el
        cliente final. A partir de este momento, el cliente puede aprobar o
        rechazar cada línea individualmente. Ya no se pueden editar líneas
        ni reenviar notificaciones (eso era en el estado enviada_front).
        
        Args:
            usuario: Usuario que realiza la acción (opcional, para auditoría)
        
        Returns:
            bool: True si se cambió el estado exitosamente
        """
        if not self.puede_enviar_a_cliente():
            return False
        
        self.estado = 'enviada_cliente'
        self.save()
        return True
    
    def actualizar_estado_segun_lineas(self):
        """
        Actualiza el estado de la solicitud basándose en las respuestas de líneas Y servicios.
        
        LÓGICA:
        - Cuenta tanto líneas de cotización (piezas) como servicios adicionales
        - Si TODOS están aprobados → 'totalmente_aprobada'
        - Si TODOS están rechazados → 'totalmente_rechazada'
        - Si hay mezcla de aprobados y rechazados → 'parcialmente_aprobada'
        - Si aún hay pendientes (piezas o servicios) → mantiene 'enviada_cliente'
        
        IMPORTANTE:
        - Los servicios adicionales también cuentan para determinar el estado
        - No se marca como "totalmente_aprobada" hasta que servicios también respondan
        
        Returns:
            str: Nuevo estado de la solicitud
        """
        if self.estado not in ['enviada_front', 'enviada_cliente', 'parcialmente_aprobada']:
            return self.estado
        
        # Contar líneas de cotización (piezas)
        total_lineas = self.total_lineas
        lineas_aprobadas = self.lineas_aprobadas
        lineas_rechazadas = self.lineas_rechazadas
        lineas_pendientes = self.lineas_pendientes
        
        # Contar servicios adicionales
        total_servicios = self.total_servicios_adicionales
        servicios_aprobados = self.servicios_aprobados
        servicios_rechazados = self.servicios_rechazados
        servicios_pendientes = self.servicios_pendientes
        
        # Totales combinados
        total = total_lineas + total_servicios
        aprobadas = lineas_aprobadas + servicios_aprobados
        rechazadas = lineas_rechazadas + servicios_rechazados
        pendientes = lineas_pendientes + servicios_pendientes
        
        # Si no hay nada que evaluar, no cambiar estado
        if total == 0:
            return self.estado
        
        if pendientes > 0:
            # Aún hay líneas o servicios sin respuesta
            return self.estado
        
        # Todas las líneas y servicios tienen respuesta
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
            
            # CREAR UnidadCompra para que al recibir se generen las UnidadInventario
            # Esto permite tracking individual de cada pieza
            # marca: Nombre del producto genérico (ej: "Memoria RAM DDR4")
            # modelo: Descripción específica de la pieza (ej: "RAM DDR4 16GB 3200MHz Kingston Fury")
            UnidadCompra.objects.create(
                compra=compra,
                numero_linea=1,
                marca=linea.producto.nombre,  # Nombre del producto genérico
                modelo=linea.descripcion_pieza,  # Descripción específica de la pieza
                cantidad=linea.cantidad,
                costo_unitario=linea.costo_unitario,
                estado='pendiente'
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
    
    def puede_generar_venta_mostrador(self):
        """
        Verifica si se puede crear/actualizar VentaMostrador.
        
        Condiciones:
        - Debe tener orden_servicio vinculada
        - Debe haber al menos un servicio adicional aprobado sin procesar
        """
        if not self.orden_servicio:
            return False
        
        return self.servicios_adicionales.filter(
            estado_cliente='aprobada'
        ).exclude(
            estado_cliente='compra_generada'
        ).exists()
    
    def generar_venta_mostrador(self):
        """
        Crea o actualiza el VentaMostrador en la orden de servicio vinculada.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        --------------------------------
        Este método toma los servicios adicionales aprobados y los "traslada"
        al modelo VentaMostrador de servicio_tecnico.
        
        Por ejemplo, si el cliente aprobó:
        - paquete_premium ($5,500)
        - limpieza ($450)
        
        Este método creará/actualizará el VentaMostrador con:
        - paquete = 'premium'
        - costo_paquete = 5500
        - incluye_limpieza = True
        - costo_limpieza = 450
        
        IMPORTANTE:
        - Solo funciona si la solicitud tiene orden_servicio vinculada
        - Si ya existe VentaMostrador, actualiza los campos correspondientes
        - Marca los servicios como 'compra_generada' para no procesarlos dos veces
        
        Returns:
            VentaMostrador: Instancia creada/actualizada, o None si no aplica
        """
        # Validar que haya orden de servicio
        if not self.orden_servicio:
            return None
        
        # Obtener servicios aprobados que no hayan sido procesados
        servicios_aprobados = self.servicios_adicionales.filter(
            estado_cliente='aprobada'
        )
        
        if not servicios_aprobados.exists():
            return None
        
        # Importar modelos de servicio_tecnico (evitar import circular)
        from servicio_tecnico.models import VentaMostrador
        
        # Buscar o crear VentaMostrador para esta orden
        venta, creada = VentaMostrador.objects.get_or_create(
            orden=self.orden_servicio,
            defaults={'fecha_venta': timezone.now()}
        )
        
        # Procesar cada servicio aprobado
        for servicio in servicios_aprobados:
            mapeo = MAPEO_SERVICIO_A_VENTA_MOSTRADOR.get(servicio.tipo_servicio)
            
            if not mapeo:
                continue
            
            # Si es un paquete (premium/oro/plata)
            if servicio.es_paquete:
                venta.paquete = servicio.valor_paquete
                venta.costo_paquete = servicio.costo
            
            # Si es un servicio individual (limpieza, reinstalación, etc.)
            elif 'campo_incluye' in mapeo:
                setattr(venta, mapeo['campo_incluye'], True)
                setattr(venta, mapeo['campo_costo'], servicio.costo)
            
            # Marcar servicio como procesado
            servicio.estado_cliente = 'compra_generada'
            servicio.save()
        
        # Guardar VentaMostrador con todos los cambios
        venta.save()
        
        return venta
    
    def generar_piezas_venta_mostrador(self):
        """
        Crea registros PiezaVentaMostrador en ST a partir de LineaCotizacion aprobadas.

        EXPLICACIÓN PARA PRINCIPIANTES:
        --------------------------------
        Hay dos escenarios que convergen en PiezaVentaMostrador:

        1. Órdenes FL- (venta_mostrador): TODAS las líneas aprobadas van aquí.
        2. Órdenes OOW (diagnóstico): SOLO las líneas con es_linea_reacondicionado=True
           (equipo P0125 ofertado como alternativa a reparación por piezas).

        Las piezas de reparación en OOW siguen yendo a PiezaCotizada vía _sincronizar_pieza_st.

        Diseño anti-duplicados:
        - Solo procesa líneas con estado_cliente='aprobada'.
        - generar_compras() las marca 'compra_generada' después; este método debe
          llamarse ANTES de generar_compras() en la vista.

        Returns:
            int: Número de PiezaVentaMostrador creadas (0 si no aplica o no hay líneas)
        """
        if not self.orden_servicio:
            return 0

        from decimal import Decimal
        from servicio_tecnico.models import VentaMostrador, PiezaVentaMostrador

        es_orden_fl = self.orden_servicio.tipo_servicio == 'venta_mostrador'

        # Líneas aprobadas pendientes de procesar como compra
        lineas_pendientes = self.lineas.filter(estado_cliente='aprobada')

        if es_orden_fl:
            # FL-: todas las líneas aprobadas van a Venta Mostrador
            lineas_a_procesar = lineas_pendientes
        else:
            # OOW: solo equipos reacondicionados (no piezas de reparación)
            lineas_a_procesar = lineas_pendientes.filter(es_linea_reacondicionado=True)
            if not lineas_a_procesar.exists():
                return 0

        vm, _ = VentaMostrador.objects.get_or_create(
            orden=self.orden_servicio,
            defaults={'fecha_venta': timezone.now()}
        )

        piezas_creadas = 0
        IVA_FACTOR = Decimal('1.16')

        for linea in lineas_a_procesar:
            nombre_producto = linea.producto.nombre if linea.producto else 'Pieza sin nombre'
            descripcion_extra = linea.descripcion_pieza or ''
            if descripcion_extra:
                descripcion_completa = f"{nombre_producto} — {descripcion_extra}"
            else:
                descripcion_completa = nombre_producto
            descripcion_completa = descripcion_completa[:200]

            # Equipos reac: precio con IVA según forma de pago elegida al aprobar
            if linea.es_linea_reacondicionado:
                from almacen.utils.costeo_reacondicionado import (
                    obtener_etiqueta_opcion_pago_reac,
                    obtener_precio_reac_con_iva,
                )
                costeo = self.resultado_costeo_reac or {}
                opcion = linea.opcion_pago_reac or 'contado'
                precio_venta = obtener_precio_reac_con_iva(costeo, opcion)
                if precio_venta <= 0 and linea.precio_unitario_cliente is not None:
                    precio_venta = linea.precio_unitario_cliente * IVA_FACTOR
                elif precio_venta <= 0:
                    precio_venta = (linea.costo_unitario or Decimal('0.00')) * IVA_FACTOR
                etiqueta_pago = obtener_etiqueta_opcion_pago_reac(opcion)
                notas_pieza = (
                    f"Equipo reacondicionado — cotización {self.numero_solicitud}. "
                    f"Forma de pago: {etiqueta_pago}. "
                    f"{linea.notas[:400] if linea.notas else ''}"
                ).strip()
            else:
                # FL- piezas normales: precio cotizado al cliente (fallback costo proveedor)
                precio_venta = (
                    linea.precio_unitario_cliente
                    if linea.precio_unitario_cliente is not None
                    else (linea.costo_unitario or Decimal('0.00'))
                )
                notas_pieza = (
                    f"Generada desde cotización {self.numero_solicitud}. "
                    f"Proveedor: {linea.proveedor.nombre if linea.proveedor else 'N/A'}."
                )

            PiezaVentaMostrador.objects.create(
                venta_mostrador=vm,
                descripcion_pieza=descripcion_completa,
                cantidad=linea.cantidad,
                precio_unitario=precio_venta,
                notas=notas_pieza,
            )
            piezas_creadas += 1

        if piezas_creadas:
            logger.info(
                f"SolicitudCotizacion {self.numero_solicitud}: "
                f"{piezas_creadas} PiezaVentaMostrador creada(s) en orden "
                f"{self.orden_servicio.numero_orden_interno}"
            )

        return piezas_creadas

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
    
    def puede_vincular_orden(self):
        """
        Verifica si se puede vincular una orden de servicio.
        
        Condiciones:
        - Debe estar en modo sin_orden_activa
        - No debe estar completada ni cancelada
        """
        return (
            self.sin_orden_activa
            and self.estado not in ['completada', 'cancelada']
        )
    
    def vincular_orden(self, orden_servicio):
        """
        Vincula esta solicitud con una orden de servicio existente.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        --------------------------------
        Cuando una cotización se crea sin orden activa (el equipo aún no ingresa),
        este método permite vincularla después cuando el equipo ya ingresó
        formalmente y se creó la orden de servicio.
        
        Al vincular:
        - Se asigna el FK orden_servicio
        - Se desactiva el modo sin_orden_activa
        - Se sincroniza el numero_orden_cliente desde DetalleEquipo
        - Se conservan los datos del cliente de la cotización (no se sobreescriben)
        
        Args:
            orden_servicio: Instancia de OrdenServicio a vincular
        
        Returns:
            bool: True si se vinculó exitosamente
        
        Raises:
            ValueError: Si no se puede vincular la orden
        """
        if not self.puede_vincular_orden():
            raise ValueError(
                'No se puede vincular la orden. La solicitud ya tiene orden activa '
                'o está en un estado que no lo permite.'
            )
        
        if not orden_servicio:
            raise ValueError('Debe proporcionar una orden de servicio válida.')
        
        # Verificar que la orden no tenga ya otra solicitud vinculada en estados activos
        solicitudes_existentes = SolicitudCotizacion.objects.filter(
            orden_servicio=orden_servicio,
            estado__in=['borrador', 'enviada_front', 'enviada_cliente', 'parcialmente_aprobada', 'totalmente_aprobada']
        ).exclude(pk=self.pk)
        
        if solicitudes_existentes.exists():
            raise ValueError(
                f'La orden {orden_servicio.numero_orden_interno} ya tiene '
                f'{solicitudes_existentes.count()} solicitud(es) activa(s) vinculada(s).'
            )
        
        # Vincular la orden
        self.orden_servicio = orden_servicio
        self.sin_orden_activa = False
        
        # Sincronizar numero_orden_cliente desde DetalleEquipo
        if hasattr(orden_servicio, 'detalle_equipo'):
            detalle = orden_servicio.detalle_equipo
            if detalle and hasattr(detalle, 'orden_cliente'):
                self.numero_orden_cliente = detalle.orden_cliente or ''
        
        # Agregar nota en observaciones
        nota = f"[VINCULADA] Orden {orden_servicio.numero_orden_interno} vinculada el {timezone.now().strftime('%d/%m/%Y %H:%M')}"
        if self.observaciones:
            self.observaciones = f"{self.observaciones}\n{nota}"
        else:
            self.observaciones = nota
        
        self.save()
        
        logger.info(
            f"SolicitudCotizacion {self.numero_solicitud} vinculada a "
            f"OrdenServicio {orden_servicio.numero_orden_interno}"
        )
        
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
            'enviada_front': 'info',
            'enviada_cliente': 'primary',
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
        null=True,
        blank=True,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Costo Unitario',
        help_text='Precio por unidad (opcional, puede dejarse en 0 si aún no se conoce)'
    )
    precio_unitario_cliente = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Precio unitario al cliente (sin IVA)',
        help_text='Precio cotizado al cliente por unidad, calculado al aprobar la línea'
    )
    subtotal_cliente_sin_iva = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Subtotal cliente sin IVA',
        help_text='cantidad × precio_unitario_cliente, guardado al aprobar'
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
    
    # ========== VINCULACIÓN CON PIEZA COTIZADA (Servicio Técnico) ==========
    pieza_cotizada_origen = models.OneToOneField(
        'servicio_tecnico.PiezaCotizada',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='linea_cotizacion_almacen',
        verbose_name='Pieza Cotizada Origen',
        help_text='PiezaCotizada de servicio técnico que originó esta línea (sincronización automática)'
    )
    
    # ========== CLASIFICACIÓN DE LA PIEZA (espejo de PiezaCotizada en ST) ==========
    # Estos campos son equivalentes a los de PiezaCotizada en servicio_tecnico/models.py.
    # Permiten que el personal de almacén indique si una pieza es necesaria para
    # la reparación o solo una mejora opcional, manteniendo ambos módulos sincronizados.
    es_necesaria = models.BooleanField(
        default=True,
        verbose_name='¿Es necesaria?',
        help_text='¿Es necesaria para el funcionamiento? Desmarcar si es mejora estética o de rendimiento'
    )
    sugerida_por_tecnico = models.BooleanField(
        default=False,
        verbose_name='¿Sugerida por técnico?',
        help_text='¿Fue sugerida por el técnico en su diagnóstico? (normalmente False para líneas de Almacén)'
    )
    es_linea_reacondicionado = models.BooleanField(
        default=False,
        verbose_name='¿Es equipo reacondicionado?',
        help_text=(
            'True si esta línea representa una propuesta de equipo reacondicionado (P0125). '
            'No se sincroniza a PiezaCotizada; al aprobar va a PiezaVentaMostrador en ST.'
        ),
    )
    opcion_pago_reac = models.CharField(
        max_length=20,
        choices=OPCION_PAGO_REAC_CHOICES,
        blank=True,
        default='',
        verbose_name='Forma de pago reacondicionado',
        help_text='Opción de pago elegida por el cliente al aprobar la línea reac (contado o meses)',
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
        3. Sincronizar con PiezaCotizada en Servicio Técnico
        
        EXPLICACIÓN:
        - numero_linea=0 indica que debe auto-asignarse
        - El formset envía todas las líneas con numero_linea=0
        - Esta lógica calcula el siguiente número disponible
        - Si la solicitud tiene orden_servicio, crea/actualiza PiezaCotizada en ST
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
        
        # Sincronizar con PiezaCotizada en Servicio Técnico
        if self.solicitud.orden_servicio:
            self._sincronizar_pieza_st()
    
    # ========== PROPIEDADES CALCULADAS ==========
    
    @property
    def subtotal(self):
        """
        Calcula el subtotal de esta línea.
        
        Returns:
            Decimal: cantidad × costo_unitario (0 si costo es None)
        """
        costo = self.costo_unitario or 0
        return self.cantidad * costo

    @property
    def subtotal_cliente(self):
        """
        Subtotal al cliente sin IVA para esta línea.

        Returns:
            Decimal o None si aún no se ha calculado el precio al cliente
        """
        if self.subtotal_cliente_sin_iva is not None:
            return self.subtotal_cliente_sin_iva
        if self.precio_unitario_cliente is not None:
            return self.cantidad * self.precio_unitario_cliente
        return None

    @property
    def precio_reac_aceptado_con_iva(self):
        """
        Monto con IVA de la forma de pago elegida al aprobar equipo reacondicionado.

        Returns:
            Decimal o None si no aplica o no hay opción guardada.
        """
        if not self.es_linea_reacondicionado or not self.opcion_pago_reac:
            return None
        from almacen.utils.costeo_reacondicionado import obtener_precio_reac_con_iva
        costeo = getattr(self.solicitud, 'resultado_costeo_reac', None) or {}
        precio = obtener_precio_reac_con_iva(costeo, self.opcion_pago_reac)
        return precio if precio > 0 else None
    
    def _sincronizar_pieza_st(self):
        """
        Crea o actualiza la PiezaCotizada correspondiente en Servicio Técnico.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        --------------------------------
        Cada LineaCotizacion en almacén tiene una PiezaCotizada correspondiente
        en el módulo de Servicio Técnico. Este método asegura que estén sincronizadas.
        
        MAPEO DE CAMPOS:
        - LineaCotizacion.producto.nombre → busca ComponenteEquipo por nombre
        - LineaCotizacion.descripcion_pieza → PiezaCotizada.descripcion_adicional
        - LineaCotizacion.cantidad → PiezaCotizada.cantidad
        - LineaCotizacion.costo_unitario → PiezaCotizada.costo_unitario
        - LineaCotizacion.precio_unitario_cliente → PiezaCotizada.precio_unitario_cliente
        - LineaCotizacion.proveedor.nombre → PiezaCotizada.proveedor (CharField)
        
        Si ya existe PiezaCotizada vinculada (pieza_cotizada_origen), la actualiza.
        Si no existe, busca una que coincida o crea una nueva.
        
        IMPORTANTE — Órdenes FL- (Venta Mostrador):
        Para órdenes con tipo_servicio='venta_mostrador', las piezas NO van a
        PiezaCotizada sino a PiezaVentaMostrador. Este método sale inmediatamente
        para ese tipo de órdenes, evitando duplicados en la sección de cotización.
        El destino correcto (PiezaVentaMostrador) es gestionado por
        SolicitudCotizacion.generar_piezas_venta_mostrador().
        """
        from servicio_tecnico.models import Cotizacion, PiezaCotizada
        from scorecard.models import ComponenteEquipo
        from decimal import Decimal
        
        if not self.solicitud.orden_servicio:
            return

        # Equipos reacondicionados van a PiezaVentaMostrador, no a PiezaCotizada
        if self.es_linea_reacondicionado:
            return

        # Para órdenes de Venta Mostrador (FL-), las piezas van a PiezaVentaMostrador,
        # NO a PiezaCotizada. Salir sin hacer nada para evitar duplicados.
        if self.solicitud.orden_servicio.tipo_servicio == 'venta_mostrador':
            return
        
        # Obtener o crear Cotizacion en ST
        try:
            cotizacion = Cotizacion.objects.get(orden=self.solicitud.orden_servicio)
        except Cotizacion.DoesNotExist:
            # No debería pasar porque SolicitudCotizacion.save() ya la crea
            logger.warning(
                f"No existe Cotizacion en ST para orden {self.solicitud.orden_servicio.numero_orden_interno}"
            )
            return
        
        # Buscar ComponenteEquipo que coincida con el producto
        componente = ComponenteEquipo.objects.filter(
            nombre__icontains=self.producto.nombre,
            activo=True
        ).first()
        
        if not componente:
            # Intentar búsqueda más amplia
            componente = ComponenteEquipo.objects.filter(activo=True).first()
        
        if not componente:
            logger.warning(
                f"No se encontró ComponenteEquipo para producto '{self.producto.nombre}'"
            )
            return
        
        # Buscar PiezaCotizada existente (por vínculo o por coincidencia)
        pieza = None
        
        # 1. Buscar por vínculo directo
        if self.pieza_cotizada_origen:
            pieza = self.pieza_cotizada_origen
        
        # 2. Buscar por coincidencia en la misma cotización
        if not pieza:
            pieza = PiezaCotizada.objects.filter(
                cotizacion=cotizacion,
                componente=componente,
                descripcion_adicional__icontains=self.descripcion_pieza[:50]
            ).first()
        
        # 3. Crear nueva si no existe
        if not pieza:
            pieza = PiezaCotizada(
                cotizacion=cotizacion,
                componente=componente,
            )
        
        # Actualizar campos — sincronización completa con LineaCotizacion de Almacén.
        # Los campos es_necesaria y sugerida_por_tecnico se toman del campo real
        # en lugar de hardcodear valores (antes era False/True fijo).
        pieza.descripcion_adicional = self.descripcion_pieza
        pieza.cantidad = self.cantidad
        pieza.costo_unitario = self.costo_unitario or Decimal('0.00')
        pieza.precio_unitario_cliente = self.precio_unitario_cliente
        pieza.proveedor = self.proveedor.nombre if self.proveedor else ''
        # Usar el valor real del campo (ya no hardcodeado)
        pieza.sugerida_por_tecnico = self.sugerida_por_tecnico
        pieza.es_necesaria = self.es_necesaria
        pieza.orden_prioridad = self.numero_linea
        
        # Sincronizar estado de aceptación
        if self.estado_cliente == 'aprobada':
            pieza.aceptada_por_cliente = True
        elif self.estado_cliente == 'rechazada':
            pieza.aceptada_por_cliente = False
            pieza.motivo_rechazo_pieza = self.motivo_rechazo
        # Si está pendiente, no tocar aceptada_por_cliente (dejar None)
        
        pieza.save()
        
        # Vincular bidireccionalmente
        if not self.pieza_cotizada_origen:
            self.pieza_cotizada_origen = pieza
            # Guardar sin disparar sincronización recursiva
            super(LineaCotizacion, self).save(update_fields=['pieza_cotizada_origen'])
        
        logger.debug(
            f"PiezaCotizada #{pieza.pk} sincronizada desde LineaCotizacion #{self.pk}"
        )
    
    def _actualizar_cotizacion_st_estado(self):
        """
        Actualiza el estado general de la Cotizacion en ST según las piezas.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        --------------------------------
        Cuando el cliente aprueba/rechaza piezas en almacén, este método
        actualiza el campo usuario_acepto de la Cotizacion en ST:
        
        - Si TODAS las piezas tienen respuesta → establece usuario_acepto
        - Si al menos una fue aceptada → usuario_acepto = True
        - Si todas fueron rechazadas → usuario_acepto = False
        - Si aún hay pendientes → usuario_acepto = None
        """
        from servicio_tecnico.models import Cotizacion
        
        if not self.solicitud.orden_servicio:
            return
        
        try:
            cotizacion = Cotizacion.objects.get(orden=self.solicitud.orden_servicio)
        except Cotizacion.DoesNotExist:
            return
        
        # Contar piezas con respuesta
        total_piezas = self.solicitud.lineas.count()
        aprobadas = self.solicitud.lineas.filter(estado_cliente='aprobada').count()
        rechazadas = self.solicitud.lineas.filter(estado_cliente='rechazada').count()
        pendientes = total_piezas - aprobadas - rechazadas
        
        # Solo actualizar si todas las piezas tienen respuesta
        if pendientes == 0 and total_piezas > 0:
            # Si al menos una fue aceptada, la cotización se considera aceptada
            if aprobadas > 0:
                cotizacion.usuario_acepto = True
            else:
                cotizacion.usuario_acepto = False
            
            if not cotizacion.fecha_respuesta:
                cotizacion.fecha_respuesta = timezone.now()
            
            cotizacion.save()
            
            logger.info(
                f"Cotizacion ST actualizada: usuario_acepto={cotizacion.usuario_acepto} "
                f"para orden {self.solicitud.orden_servicio.numero_orden_interno}"
            )
    
    # ========== MÉTODOS DE WORKFLOW ==========
    
    def puede_aprobar(self):
        """Verifica si la línea puede ser aprobada"""
        return self.estado_cliente == 'pendiente'
    
    def puede_rechazar(self):
        """Verifica si la línea puede ser rechazada"""
        return self.estado_cliente == 'pendiente'
    
    def aprobar(self, opcion_pago_reac=None):
        """
        Marca la línea como aprobada por el cliente.
        
        Efectos:
        - Cambia estado_cliente a 'aprobada'
        - En líneas reacondicionadas, aplica forma de pago y precio acordado
        - Calcula y persiste precios al cliente (primera aprobación de la solicitud)
        - Sincroniza con PiezaCotizada en ST (aceptada_por_cliente=True)
        - Actualiza estado general de Cotizacion en ST si todas tienen respuesta
        
        Args:
            opcion_pago_reac: Forma de pago elegida (solo líneas es_linea_reacondicionado).
        
        Returns:
            bool: True si se aprobó exitosamente
        """
        if not self.puede_aprobar():
            return False

        # Equipo reacondicionado: precio según contado o financiamiento elegido
        if self.es_linea_reacondicionado:
            from almacen.utils.costeo_reacondicionado import obtener_precio_reac_sin_iva
            opcion = opcion_pago_reac or self.opcion_pago_reac
            if not opcion:
                return False
            costeo = getattr(self.solicitud, 'resultado_costeo_reac', None) or {}
            precio_sin_iva = obtener_precio_reac_sin_iva(costeo, opcion)
            if precio_sin_iva <= 0:
                return False
            self.opcion_pago_reac = opcion
            self.precio_unitario_cliente = precio_sin_iva
            self.subtotal_cliente_sin_iva = precio_sin_iva
        
        self.estado_cliente = 'aprobada'
        self.fecha_respuesta = timezone.now()

        # EXPLICACIÓN PARA PRINCIPIANTES:
        # Primera aprobación de la solicitud: bloquear precios de TODAS las líneas de reparación.
        # Hay que guardar estado 'aprobada' en BD ANTES de persistir_precios_cliente(), porque
        # después hacemos refresh_from_db() y si el estado aún era 'pendiente' en BD, se revertía
        # y el usuario tenía que aprobar dos veces.
        if not self.solicitud.fecha_precios_cliente:
            self.save()
            self.solicitud.persistir_precios_cliente()
            self.refresh_from_db()

        self.save()
        
        # Actualizar estado de la solicitud
        self.solicitud.actualizar_estado_segun_lineas()
        
        # Actualizar estado general de Cotizacion en ST
        self._actualizar_cotizacion_st_estado()
        
        return True
    
    def rechazar(self, motivo=''):
        """
        Marca la línea como rechazada por el cliente.
        
        Efectos:
        - Cambia estado_cliente a 'rechazada'
        - Sincroniza con PiezaCotizada en ST (aceptada_por_cliente=False)
        - Actualiza estado general de Cotizacion en ST si todas tienen respuesta
        
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
        
        # Actualizar estado general de Cotizacion en ST
        self._actualizar_cotizacion_st_estado()
        
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


# ============================================================================
# FUNCIONES DE RUTA DE ALMACENAMIENTO PARA IMÁGENES DE COTIZACIÓN
# ============================================================================

def imagen_linea_cotizacion_upload_path(instance, filename):
    """
    Genera la ruta de almacenamiento para imágenes de líneas de cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta función le dice a Django DÓNDE guardar cada imagen que se sube.
    En lugar de guardar todo en una sola carpeta (que sería un desastre),
    organizamos las imágenes por:
    1. Carpeta del módulo: almacen/cotizaciones/
    2. Subcarpeta por solicitud: SOL-2025-0001/
    3. Archivo con prefijo de línea: linea_1_imagen_original.jpg
    
    Ejemplo de ruta generada:
    - almacen/cotizaciones/SOL-2025-0001/linea_1_foto_pieza.jpg
    - almacen/cotizaciones/SOL-2025-0015/linea_3_referencia.png
    
    Args:
        instance: Instancia de ImagenLineaCotizacion que se está guardando
        filename: Nombre del archivo original (ej: 'foto_pieza.jpg')
        
    Returns:
        str: Ruta completa donde se guardará el archivo
        
    NOTA TÉCNICA:
    - numero_solicitud es único para cada SolicitudCotizacion (formato SOL-YYYY-NNNN)
    - Usamos el número porque es más legible que un ID numérico
    - El prefijo linea_N ayuda a identificar a qué línea pertenece la imagen
    """
    # Obtener el número de solicitud a través de la relación
    numero_solicitud = instance.linea.solicitud.numero_solicitud
    numero_linea = instance.linea.numero_linea
    
    # Sanitizar el nombre del archivo (remover caracteres problemáticos)
    # Mantenemos solo el nombre limpio del archivo original
    nombre_archivo = os.path.basename(filename)
    
    # Generar nombre único con prefijo de línea
    nombre_final = f"linea_{numero_linea}_{nombre_archivo}"
    
    return f'almacen/cotizaciones/{numero_solicitud}/{nombre_final}'


# ============================================================================
# MODELO: IMAGEN DE LÍNEA DE COTIZACIÓN
# ============================================================================
class ImagenLineaCotizacion(models.Model):
    """
    Imágenes de referencia asociadas a cada línea de cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Este modelo permite subir fotos de las piezas que se están cotizando.
    Por ejemplo, si cotizas una RAM específica, puedes subir fotos de:
    - El modelo exacto que necesitas
    - La etiqueta con especificaciones
    - El equipo donde se instalará
    
    ¿Por qué es útil?
    -----------------
    1. El proveedor ve exactamente qué pieza necesitas (evita confusiones)
    2. El cliente puede revisar las especificaciones antes de aprobar
    3. Cuando llega la pieza, puedes verificar que sea la correcta
    4. Queda evidencia visual en el historial de la unidad de almacén
    
    Características técnicas:
    -------------------------
    - Máximo 5 imágenes por línea (para no sobrecargar el sistema)
    - Compresión automática si el archivo supera 2MB
    - Se organizan en carpetas por folio de solicitud
    - Se muestran en el detalle de UnidadInventario (trazabilidad completa)
    
    Relación con otros modelos:
    ---------------------------
    ImagenLineaCotizacion → LineaCotizacion → SolicitudCotizacion
                                            ↓
                        CompraProducto → UnidadInventario (aquí se muestran las imágenes)
    """
    
    # Límite máximo de imágenes por línea
    MAX_IMAGENES_POR_LINEA = 5
    
    # Tamaño máximo en bytes antes de comprimir (2MB)
    TAMANO_MAXIMO_SIN_COMPRIMIR = 2 * 1024 * 1024  # 2MB
    
    # ========== RELACIÓN CON LÍNEA DE COTIZACIÓN ==========
    linea = models.ForeignKey(
        LineaCotizacion,
        on_delete=models.CASCADE,
        related_name='imagenes',
        verbose_name='Línea de Cotización',
        help_text='Línea de cotización a la que pertenece esta imagen'
    )
    
    # ========== IMAGEN ==========
    imagen = models.ImageField(
        upload_to=imagen_linea_cotizacion_upload_path,
        max_length=255,  # Límite ampliado para soportar rutas largas
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'gif', 'webp'])],
        verbose_name='Imagen',
        help_text='Imagen de referencia de la pieza (JPG, PNG, GIF, WebP). Máx 10MB.'
    )
    
    # ========== DESCRIPCIÓN ==========
    descripcion = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Descripción',
        help_text='Descripción breve de la imagen (ej: "Etiqueta con modelo", "Vista frontal")'
    )
    
    # ========== METADATOS ==========
    fecha_subida = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Subida',
        help_text='Fecha y hora en que se subió la imagen'
    )
    subido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='imagenes_cotizacion_subidas',
        verbose_name='Subido Por',
        help_text='Usuario que subió la imagen'
    )
    
    # ========== INFORMACIÓN DE COMPRESIÓN ==========
    fue_comprimida = models.BooleanField(
        default=False,
        verbose_name='¿Fue Comprimida?',
        help_text='Indica si la imagen fue comprimida automáticamente'
    )
    tamano_original_kb = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Tamaño Original (KB)',
        help_text='Tamaño original del archivo antes de compresión'
    )
    tamano_final_kb = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Tamaño Final (KB)',
        help_text='Tamaño final del archivo después de procesamiento'
    )
    
    class Meta:
        verbose_name = 'Imagen de Línea de Cotización'
        verbose_name_plural = 'Imágenes de Líneas de Cotización'
        ordering = ['linea', 'fecha_subida']
    
    def __str__(self):
        """
        Representación en texto de la imagen.
        Ejemplo: "Imagen Línea #1 - SOL-2025-0001"
        """
        return f"Imagen Línea #{self.linea.numero_linea} - {self.linea.solicitud.numero_solicitud}"
    
    @property
    def nombre_archivo(self):
        """
        Retorna solo el nombre del archivo sin la ruta completa.
        
        Útil para mostrar en la interfaz de usuario.
        
        Returns:
            str: Nombre del archivo (ej: 'linea_1_foto_pieza.jpg')
        """
        return os.path.basename(self.imagen.name) if self.imagen else ''
    
    @classmethod
    def puede_agregar_imagen(cls, linea):
        """
        Verifica si se puede agregar otra imagen a una línea.
        
        EXPLICACIÓN:
        Limitamos a 5 imágenes por línea para:
        - Evitar sobrecargar el servidor de almacenamiento
        - Mantener las cotizaciones enfocadas
        - Facilitar la revisión visual
        
        Args:
            linea: Instancia de LineaCotizacion a verificar
            
        Returns:
            bool: True si se puede agregar, False si ya tiene el máximo
        """
        imagenes_actuales = cls.objects.filter(linea=linea).count()
        return imagenes_actuales < cls.MAX_IMAGENES_POR_LINEA
    
    @classmethod
    def imagenes_restantes(cls, linea):
        """
        Calcula cuántas imágenes más se pueden subir a una línea.
        
        Args:
            linea: Instancia de LineaCotizacion
            
        Returns:
            int: Número de imágenes que aún se pueden subir (0-5)
        """
        imagenes_actuales = cls.objects.filter(linea=linea).count()
        return max(0, cls.MAX_IMAGENES_POR_LINEA - imagenes_actuales)
    
    def save(self, *args, **kwargs):
        """
        Override del método save() para:
        1. Validar el límite de imágenes por línea
        2. Comprimir la imagen si supera 2MB
        3. Guardar información de compresión
        
        EXPLICACIÓN DETALLADA:
        ----------------------
        Este método se ejecuta cada vez que guardamos una imagen.
        
        Paso 1 - Validación:
        Si ya hay 5 imágenes para esta línea, lanzamos un error.
        Esto previene que se suban más imágenes del límite permitido.
        
        Paso 2 - Compresión:
        Si la imagen pesa más de 2MB, la comprimimos automáticamente.
        Esto ahorra espacio en disco y hace más rápida la carga de páginas.
        
        Paso 3 - Metadatos:
        Guardamos el tamaño original y final para poder mostrar al usuario
        cuánto espacio se ahorró con la compresión.
        
        Raises:
            ValueError: Si ya se alcanzó el límite de 5 imágenes
        """
        es_nueva = self.pk is None
        
        # ========== VALIDAR LÍMITE DE IMÁGENES ==========
        if es_nueva and not self.puede_agregar_imagen(self.linea):
            raise ValueError(
                f"No se pueden agregar más imágenes. Límite máximo: "
                f"{self.MAX_IMAGENES_POR_LINEA} imágenes por línea."
            )
        
        # ========== PROCESAR Y COMPRIMIR IMAGEN ==========
        if self.imagen and es_nueva:
            # Obtener el archivo de imagen
            imagen_file = self.imagen
            
            # Calcular tamaño original
            imagen_file.seek(0, 2)  # Ir al final del archivo
            tamano_original = imagen_file.tell()  # Obtener posición (= tamaño)
            imagen_file.seek(0)  # Volver al inicio
            
            self.tamano_original_kb = tamano_original // 1024
            
            # Comprimir solo si supera el límite de 2MB
            if tamano_original > self.TAMANO_MAXIMO_SIN_COMPRIMIR:
                imagen_comprimida = self._comprimir_imagen(imagen_file)
                if imagen_comprimida:
                    self.imagen = imagen_comprimida
                    self.fue_comprimida = True
                    
                    # Calcular nuevo tamaño
                    imagen_comprimida.seek(0, 2)
                    tamano_final = imagen_comprimida.tell()
                    imagen_comprimida.seek(0)
                    self.tamano_final_kb = tamano_final // 1024
                else:
                    # Si falla la compresión, guardar tamaño original
                    self.tamano_final_kb = self.tamano_original_kb
            else:
                # No necesita compresión
                self.tamano_final_kb = self.tamano_original_kb
        
        super().save(*args, **kwargs)
    
    def _comprimir_imagen(self, imagen_file):
        """
        Comprime una imagen para reducir su tamaño.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        --------------------------------
        Este método usa la librería Pillow (PIL) para:
        1. Abrir la imagen original
        2. Convertirla a formato RGB si es necesario (algunas imágenes PNG tienen transparencia)
        3. Guardarla con menor calidad (85%) para reducir tamaño
        4. Si aún es muy grande, reduce también las dimensiones
        
        La calidad 85% es un buen balance entre:
        - Tamaño de archivo reducido
        - Calidad visual aceptable para referencia
        
        Args:
            imagen_file: Archivo de imagen (InMemoryUploadedFile o similar)
            
        Returns:
            ContentFile: Imagen comprimida lista para guardar, o None si falla
        """
        from django.core.files.base import ContentFile
        
        try:
            # Abrir la imagen con Pillow
            img = Image.open(imagen_file)
            
            # Convertir a RGB si tiene transparencia (PNG con alpha)
            if img.mode in ('RGBA', 'LA', 'P'):
                # Crear fondo blanco para reemplazar transparencia
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Si la imagen es muy grande, redimensionar
            max_dimension = 1920  # Full HD como máximo
            if img.width > max_dimension or img.height > max_dimension:
                # Calcular nuevo tamaño manteniendo proporción
                ratio = min(max_dimension / img.width, max_dimension / img.height)
                nuevo_ancho = int(img.width * ratio)
                nuevo_alto = int(img.height * ratio)
                img = img.resize((nuevo_ancho, nuevo_alto), Image.Resampling.LANCZOS)
            
            # Guardar con compresión JPEG
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=85, optimize=True)
            output.seek(0)
            
            # Generar nombre de archivo con extensión .jpg
            nombre_original = os.path.basename(imagen_file.name)
            nombre_sin_ext = os.path.splitext(nombre_original)[0]
            nuevo_nombre = f"{nombre_sin_ext}.jpg"
            
            return ContentFile(output.read(), name=nuevo_nombre)
            
        except Exception as e:
            # Si falla la compresión, registrar error y retornar None
            # La imagen se guardará sin comprimir
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error al comprimir imagen: {e}")
            return None
    
    def delete(self, *args, **kwargs):
        """
        Override del método delete() para eliminar el archivo físico.
        
        EXPLICACIÓN:
        Cuando eliminamos un registro de ImagenLineaCotizacion,
        también debemos eliminar el archivo físico del disco.
        De lo contrario, quedarían archivos huérfanos ocupando espacio.
        """
        # Guardar referencia al archivo antes de eliminar el registro
        imagen_path = self.imagen.path if self.imagen else None
        
        # Eliminar el registro de la base de datos
        super().delete(*args, **kwargs)
        
        # Eliminar el archivo físico si existe
        if imagen_path and os.path.exists(imagen_path):
            try:
                os.remove(imagen_path)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error al eliminar archivo de imagen: {e}")


# ============================================================================
# FUNCIÓN DE RUTA DE ALMACENAMIENTO PARA IMÁGENES DE REFERENCIA DE SOLICITUD
# ============================================================================

def imagen_solicitud_cotizacion_upload_path(instance, filename):
    """
    Genera la ruta de almacenamiento para imágenes de referencia de solicitud.
    
    Ruta: almacen/cotizaciones/{numero_solicitud}/referencia/{nombre_archivo}
    
    Args:
        instance: Instancia de ImagenSolicitudCotizacion
        filename: Nombre original del archivo
        
    Returns:
        str: Ruta relativa donde se guardará la imagen
    """
    numero_solicitud = instance.solicitud.numero_solicitud or 'temp'
    nombre_archivo = filename.replace(' ', '_')
    return f'almacen/cotizaciones/{numero_solicitud}/referencia/{nombre_archivo}'


# ============================================================================
# MODELO: IMAGEN DE REFERENCIA DE SOLICITUD DE COTIZACIÓN
# ============================================================================
class ImagenSolicitudCotizacion(models.Model):
    """
    Imágenes de referencia asociadas a la solicitud de cotización completa.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    A diferencia de ImagenLineaCotizacion (que se vincula a una línea específica),
    este modelo almacena imágenes generales de la solicitud.
    
    Caso de uso principal:
    Cuando recepción solicita una cotización sin llevar el equipo al centro de
    servicio, el cliente puede compartir fotos de las piezas que necesita cotizar.
    Estas imágenes ayudan a compras a identificar exactamente qué piezas buscar.
    
    Características:
    - Máximo 6 imágenes por solicitud
    - Compresión automática si supera 2MB
    - Se organizan en carpeta /referencia/ dentro de la solicitud
    """
    
    MAX_IMAGENES_POR_SOLICITUD = 6
    TAMANO_MAXIMO_SIN_COMPRIMIR = 2 * 1024 * 1024  # 2MB
    
    # ========== RELACIÓN CON SOLICITUD ==========
    solicitud = models.ForeignKey(
        SolicitudCotizacion,
        on_delete=models.CASCADE,
        related_name='imagenes_referencia',
        verbose_name='Solicitud de Cotización',
        help_text='Solicitud a la que pertenece esta imagen de referencia'
    )
    
    # ========== IMAGEN ==========
    imagen = models.ImageField(
        upload_to=imagen_solicitud_cotizacion_upload_path,
        max_length=255,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'gif', 'webp'])],
        verbose_name='Imagen',
        help_text='Imagen de referencia (JPG, PNG, GIF, WebP). Máx 10MB.'
    )
    
    # ========== DESCRIPCIÓN ==========
    descripcion = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Descripción',
        help_text='Descripción breve de la imagen'
    )
    
    # ========== METADATOS ==========
    fecha_subida = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Subida'
    )
    subido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='imagenes_solicitud_cotizacion_subidas',
        verbose_name='Subido Por'
    )
    
    # ========== INFORMACIÓN DE COMPRESIÓN ==========
    fue_comprimida = models.BooleanField(
        default=False,
        verbose_name='¿Fue Comprimida?'
    )
    tamano_original_kb = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Tamaño Original (KB)'
    )
    tamano_final_kb = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Tamaño Final (KB)'
    )
    
    class Meta:
        verbose_name = 'Imagen de Referencia de Solicitud'
        verbose_name_plural = 'Imágenes de Referencia de Solicitud'
        ordering = ['solicitud', 'fecha_subida']
    
    def __str__(self):
        """Representación en texto de la imagen."""
        return f"Imagen Ref. {self.solicitud.numero_solicitud} - {self.descripcion or 'Sin descripción'}"
    
    @property
    def nombre_archivo(self):
        """Retorna solo el nombre del archivo sin la ruta completa."""
        return os.path.basename(self.imagen.name) if self.imagen else ''
    
    @classmethod
    def puede_agregar_imagen(cls, solicitud):
        """
        Verifica si se puede agregar otra imagen a la solicitud.
        
        Args:
            solicitud: Instancia de SolicitudCotizacion
            
        Returns:
            bool: True si se puede agregar, False si ya tiene el máximo
        """
        imagenes_actuales = cls.objects.filter(solicitud=solicitud).count()
        return imagenes_actuales < cls.MAX_IMAGENES_POR_SOLICITUD
    
    @classmethod
    def imagenes_restantes(cls, solicitud):
        """
        Calcula cuántas imágenes más se pueden subir.
        
        Args:
            solicitud: Instancia de SolicitudCotizacion
            
        Returns:
            int: Número de imágenes que aún se pueden subir (0-6)
        """
        imagenes_actuales = cls.objects.filter(solicitud=solicitud).count()
        return max(0, cls.MAX_IMAGENES_POR_SOLICITUD - imagenes_actuales)
    
    def save(self, *args, **kwargs):
        """
        Override del método save() para:
        1. Validar el límite de imágenes por solicitud
        2. Comprimir la imagen si supera 2MB
        3. Guardar información de compresión
        """
        es_nueva = self.pk is None
        
        # ========== VALIDAR LÍMITE DE IMÁGENES ==========
        if es_nueva and not self.puede_agregar_imagen(self.solicitud):
            raise ValueError(
                f"No se pueden agregar más imágenes. Límite máximo: "
                f"{self.MAX_IMAGENES_POR_SOLICITUD} imágenes por solicitud."
            )
        
        # ========== PROCESAR Y COMPRIMIR IMAGEN ==========
        if self.imagen and es_nueva:
            imagen_file = self.imagen
            
            # Calcular tamaño original
            imagen_file.seek(0, 2)
            tamano_original = imagen_file.tell()
            imagen_file.seek(0)
            
            self.tamano_original_kb = tamano_original // 1024
            
            # Comprimir solo si supera el límite de 2MB
            if tamano_original > self.TAMANO_MAXIMO_SIN_COMPRIMIR:
                imagen_comprimida = self._comprimir_imagen(imagen_file)
                if imagen_comprimida:
                    self.imagen = imagen_comprimida
                    self.fue_comprimida = True
                    
                    imagen_comprimida.seek(0, 2)
                    tamano_final = imagen_comprimida.tell()
                    imagen_comprimida.seek(0)
                    self.tamano_final_kb = tamano_final // 1024
                else:
                    self.tamano_final_kb = self.tamano_original_kb
            else:
                self.tamano_final_kb = self.tamano_original_kb
        
        super().save(*args, **kwargs)
    
    def _comprimir_imagen(self, imagen_file):
        """
        Comprime una imagen para reducir su tamaño.
        Usa Pillow para redimensionar y comprimir a JPEG quality=85.
        
        Args:
            imagen_file: Archivo de imagen
            
        Returns:
            ContentFile: Imagen comprimida, o None si falla
        """
        from django.core.files.base import ContentFile
        
        try:
            img = Image.open(imagen_file)
            
            # Convertir a RGB si tiene transparencia
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Redimensionar si es muy grande
            max_dimension = 1920
            if img.width > max_dimension or img.height > max_dimension:
                ratio = min(max_dimension / img.width, max_dimension / img.height)
                nuevo_ancho = int(img.width * ratio)
                nuevo_alto = int(img.height * ratio)
                img = img.resize((nuevo_ancho, nuevo_alto), Image.Resampling.LANCZOS)
            
            # Guardar con compresión JPEG
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=85, optimize=True)
            output.seek(0)
            
            nombre_original = os.path.basename(imagen_file.name)
            nombre_sin_ext = os.path.splitext(nombre_original)[0]
            nuevo_nombre = f"{nombre_sin_ext}.jpg"
            
            return ContentFile(output.read(), name=nuevo_nombre)
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error al comprimir imagen de solicitud: {e}")
            return None
    
    def delete(self, *args, **kwargs):
        """Override del método delete() para eliminar el archivo físico."""
        imagen_path = self.imagen.path if self.imagen else None
        super().delete(*args, **kwargs)
        
        if imagen_path and os.path.exists(imagen_path):
            try:
                os.remove(imagen_path)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error al eliminar archivo de imagen de solicitud: {e}")


# ============================================================================
# MODELO: LÍNEA DE SERVICIO ADICIONAL (Venta Mostrador en Cotizaciones)
# ============================================================================

class LineaServicioAdicional(models.Model):
    """
    Servicios adicionales de Venta Mostrador dentro de una SolicitudCotizacion.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Este modelo permite agregar servicios adicionales (como limpieza, reinstalación
    de SO, paquetes de mejora, etc.) dentro de una cotización de almacén.
    
    ¿Por qué es útil?
    -----------------
    Cuando un cliente trae su equipo a servicio técnico, además de las piezas que
    necesita (RAM, disco duro, etc.), también puede querer servicios adicionales:
    - Limpieza profunda del equipo
    - Reinstalación del sistema operativo
    - Respaldo de su información
    - Un paquete completo de mejora (Premium/Oro/Plata)
    
    Antes, estos servicios se tenían que crear manualmente en "Ventas Mostrador"
    después de que el cliente aceptaba. Ahora se pueden cotizar juntos con las
    piezas, y cuando el cliente aprueba, se crea automáticamente el VentaMostrador.
    
    FLUJO:
    ------
    1. Almacén agrega servicios adicionales a la cotización (junto con las piezas)
    2. El cliente ve TODO junto: piezas + servicios
    3. El cliente aprueba/rechaza cada línea por separado
    4. Al generar compras, los servicios aprobados crean/actualizan VentaMostrador
    
    RELACIÓN CON VentaMostrador:
    ----------------------------
    Cada tipo de servicio mapea a un campo específico en VentaMostrador:
    - paquete_premium → VentaMostrador.paquete = 'premium'
    - limpieza → VentaMostrador.incluye_limpieza = True
    - reinstalacion_so → VentaMostrador.incluye_reinstalacion_so = True
    - etc.
    
    Campos importantes:
    - solicitud: FK a SolicitudCotizacion (la cabecera)
    - tipo_servicio: Tipo de servicio (paquete, limpieza, etc.)
    - costo: Precio del servicio
    - es_necesaria: Clasificación para PDF (verde/amarillo); no va a VentaMostrador
    - estado_cliente: Si el cliente aprobó/rechazó este servicio
    """
    
    # ========== RELACIÓN CON SOLICITUD ==========
    solicitud = models.ForeignKey(
        SolicitudCotizacion,
        on_delete=models.CASCADE,
        related_name='servicios_adicionales',
        verbose_name='Solicitud de Cotización'
    )
    numero_linea = models.PositiveIntegerField(
        default=0,
        verbose_name='Número de Línea',
        help_text='Orden de la línea dentro de la solicitud (se asigna automáticamente)'
    )
    
    # ========== TIPO DE SERVICIO ==========
    tipo_servicio = models.CharField(
        max_length=25,
        choices=TIPO_SERVICIO_ADICIONAL_CHOICES,
        verbose_name='Tipo de Servicio',
        help_text='Tipo de servicio adicional (paquete, limpieza, reinstalación, etc.)'
    )
    
    # ========== COSTO ==========
    costo = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Costo del Servicio',
        help_text='Precio del servicio (IVA incluido)'
    )

    # ========== CLASIFICACIÓN PARA PDF DE COTIZACIÓN ==========
    # Solo afecta el color/fila en el PDF al cliente (verde=necesaria, amarillo=opcional).
    # NO se sincroniza con VentaMostrador en Servicio Técnico.
    es_necesaria = models.BooleanField(
        default=False,
        verbose_name='¿Es necesaria?',
        help_text='Marcar si el servicio es indispensable. Desmarcado = opcional (ej. limpieza)'
    )

    # ========== ESTADO DEL CLIENTE ==========
    estado_cliente = models.CharField(
        max_length=20,
        choices=ESTADO_LINEA_COTIZACION_CHOICES,
        default='pendiente',
        verbose_name='Estado del Cliente',
        help_text='Respuesta del cliente para este servicio'
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
    
    # ========== NOTAS ==========
    notas = models.TextField(
        blank=True,
        verbose_name='Notas',
        help_text='Observaciones sobre este servicio'
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
        verbose_name = 'Servicio Adicional'
        verbose_name_plural = 'Servicios Adicionales'
        ordering = ['solicitud', 'numero_linea']
        unique_together = ['solicitud', 'numero_linea']
    
    def __str__(self):
        """Representación en texto del servicio adicional."""
        return f"#{self.numero_linea}: {self.get_tipo_servicio_display()} (${self.costo})"
    
    def save(self, *args, **kwargs):
        """
        Override de save() para auto-asignar número de línea.
        
        Los números de línea de servicios adicionales empiezan en 1000
        para no chocar con las líneas de cotización (que empiezan en 1).
        """
        if not self.numero_linea or self.numero_linea == 0:
            max_linea = LineaServicioAdicional.objects.filter(
                solicitud=self.solicitud
            ).aggregate(models.Max('numero_linea'))['numero_linea__max']
            # Empezar en 1000 para diferenciar de líneas de cotización
            self.numero_linea = (max_linea or 999) + 1
        
        # Asignar costo por defecto si es 0 o None
        if not self.costo or self.costo == 0:
            from decimal import Decimal
            costo_default = PRECIOS_SERVICIOS_ADICIONALES.get(self.tipo_servicio, 0)
            self.costo = Decimal(str(costo_default))
        
        super().save(*args, **kwargs)
    
    # ========== PROPIEDADES CALCULADAS ==========
    
    @property
    def subtotal(self):
        """
        Calcula el subtotal de este servicio.
        
        Los servicios adicionales siempre tienen cantidad = 1,
        por lo que el subtotal es igual al costo.
        
        Returns:
            Decimal: El costo del servicio
        """
        return self.costo or 0
    
    @property
    def es_paquete(self):
        """Verifica si este servicio es un paquete (premium/oro/plata)."""
        return self.tipo_servicio.startswith('paquete_')
    
    @property
    def valor_paquete(self):
        """
        Si es un paquete, retorna el valor del paquete ('premium', 'oro', 'plata').
        Si no es paquete, retorna None.
        """
        if self.es_paquete:
            return self.tipo_servicio.replace('paquete_', '')
        return None
    
    # ========== MÉTODOS DE WORKFLOW ==========
    
    def puede_aprobar(self):
        """Verifica si el servicio puede ser aprobado."""
        return self.estado_cliente == 'pendiente'
    
    def puede_rechazar(self):
        """Verifica si el servicio puede ser rechazado."""
        return self.estado_cliente == 'pendiente'
    
    def aprobar(self):
        """
        Marca el servicio como aprobado por el cliente.
        
        Efectos:
        - Cambia estado_cliente a 'aprobada'
        - Actualiza estado general de la solicitud (piezas + servicios)
        
        Returns:
            bool: True si se aprobó exitosamente
        """
        if not self.puede_aprobar():
            return False
        
        self.estado_cliente = 'aprobada'
        self.fecha_respuesta = timezone.now()
        self.save()
        
        # Actualizar estado general de la solicitud
        self.solicitud.actualizar_estado_segun_lineas()
        
        return True
    
    def rechazar(self, motivo=''):
        """
        Marca el servicio como rechazado por el cliente.
        
        Efectos:
        - Cambia estado_cliente a 'rechazada'
        - Actualiza estado general de la solicitud (piezas + servicios)
        
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
        
        # Actualizar estado general de la solicitud
        self.solicitud.actualizar_estado_segun_lineas()
        
        return True
    
    # ========== MÉTODOS DE VISUALIZACIÓN ==========
    
    def get_badge_estado(self):
        """Retorna la clase CSS de Bootstrap para el badge de estado."""
        estados_css = {
            'pendiente': 'secondary',
            'aprobada': 'success',
            'rechazada': 'danger',
            'compra_generada': 'primary',
        }
        return estados_css.get(self.estado_cliente, 'secondary')
    
    def get_estado_icon(self):
        """Retorna el icono Bootstrap Icons para el estado."""
        estados_icon = {
            'pendiente': 'hourglass-split',
            'aprobada': 'check-circle-fill',
            'rechazada': 'x-circle-fill',
            'compra_generada': 'wrench-adjustable',
        }
        return estados_icon.get(self.estado_cliente, 'question-circle')
    
    def get_icono_servicio(self):
        """Retorna el icono Bootstrap Icons según el tipo de servicio."""
        iconos = {
            'paquete_premium': 'trophy-fill',
            'paquete_oro': 'award-fill',
            'paquete_plata': 'shield-fill-check',
            'cambio_pieza': 'tools',
            'limpieza': 'droplet-fill',
            'kit_limpieza': 'box-seam-fill',
            'reinstalacion_so': 'windows',
            'respaldo': 'cloud-arrow-up-fill',
        }
        return iconos.get(self.tipo_servicio, 'gear-fill')
