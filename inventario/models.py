from django.db import models
from django.utils import timezone
import uuid
import qrcode
from io import BytesIO
import base64

class Sucursal(models.Model):
    """
    Modelo para manejar las diferentes sucursales donde se puede enviar producto
    """
    # Información básica
    codigo = models.CharField(max_length=20, unique=True, help_text="Código único de la sucursal")
    nombre = models.CharField(max_length=100, help_text="Nombre de la sucursal")
    
    # Ubicación
    direccion = models.TextField(blank=True, help_text="Dirección de la sucursal")
    ciudad = models.CharField(max_length=100, blank=True, help_text="Ciudad donde se ubica")
    estado_provincia = models.CharField(max_length=100, blank=True, help_text="Estado o provincia")
    
    # Contacto
    responsable = models.CharField(max_length=100, blank=True, help_text="Persona responsable/encargado")
    telefono = models.CharField(max_length=20, blank=True, help_text="Teléfono de contacto")
    email = models.EmailField(blank=True, help_text="Correo electrónico de contacto")
    
    # Estado y observaciones
    activa = models.BooleanField(default=True, help_text="Sucursal activa")
    observaciones = models.TextField(blank=True, help_text="Observaciones adicionales")
    
    # Control de fechas
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        """
        Genera automáticamente el código único cuando se crea una sucursal nueva
        """
        if not self.codigo:
            # Generar código único: SUC + número incremental
            ultimo_numero = Sucursal.objects.filter(
                codigo__startswith='SUC'
            ).count() + 1
            self.codigo = f"SUC{ultimo_numero:03d}"  # SUC001, SUC002, etc.
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"
    
    class Meta:
        ordering = ['nombre']
        verbose_name_plural = "Sucursales"

class Producto(models.Model):
    """
    Modelo mejorado para productos con código QR único y categorización
    """
    ESTADO_CHOICES = [
        ('bueno', 'Bueno'),
        ('regular', 'Regular'),
        ('malo', 'Malo'),
    ]
    
    CATEGORIA_CHOICES = [
        ('limpieza', 'Limpieza'),
        ('seguridad', 'Seguridad'), 
        ('oficina', 'Oficina'),
        ('etiquetas', 'Etiquetas'),
        ('envases', 'Envases y Contenedores'),
        ('herramientas', 'Herramientas'),
        ('otros', 'Otros'),
    ]
    
    TIPO_CHOICES = [
        ('consumible', 'Consumible'),
        ('reutilizable', 'Reutilizable'),
    ]
    
    # Información básica del producto
    codigo_qr = models.CharField(max_length=50, unique=True, editable=False, help_text="Código QR único del producto")
    nombre = models.CharField(max_length=100, help_text="Nombre del producto")
    descripcion = models.TextField(blank=True, help_text="Descripción detallada del producto")
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, default='otros', help_text="Categoría del producto")
    tipo = models.CharField(max_length=15, choices=TIPO_CHOICES, default='consumible', help_text="Tipo de producto")
    
    # Control de inventario
    cantidad = models.PositiveIntegerField(default=0, help_text="Cantidad actual en stock")
    stock_minimo = models.PositiveIntegerField(default=5, help_text="Cantidad mínima antes de alerta")
    ubicacion = models.CharField(max_length=100, blank=True, help_text="Ubicación física en almacén")
    
    # Información adicional
    proveedor = models.CharField(max_length=100, blank=True, help_text="Proveedor del producto")
    costo_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Costo por unidad")
    estado_calidad = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='bueno', help_text="Estado de calidad del producto")
    
    # Fechas de control
    fecha_ingreso = models.DateTimeField(auto_now_add=True, help_text="Fecha de registro en el sistema")
    fecha_actualizacion = models.DateTimeField(auto_now=True, help_text="Última actualización")
    
    def save(self, *args, **kwargs):
        """
        Genera automáticamente el código QR único cuando se crea un producto nuevo
        """
        if not self.codigo_qr:
            # Generar código único: INV + timestamp + random
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            random_part = str(uuid.uuid4())[:6].upper()
            self.codigo_qr = f"INV{timestamp}{random_part}"
        super().save(*args, **kwargs)
    
    def generar_qr_image(self):
        """
        Genera la imagen QR como base64 para mostrar en templates
        """
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(self.codigo_qr)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Convertir a base64 para uso en templates
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    
    def stock_bajo(self):
        """
        Verifica si el producto tiene stock bajo
        """
        return self.cantidad <= self.stock_minimo
    
    def valor_total_stock(self):
        """
        Calcula el valor total del stock actual
        """
        return self.cantidad * self.costo_unitario
    
    def __str__(self):
        return f"{self.codigo_qr} - {self.nombre}"
    
    class Meta:
        ordering = ['-fecha_ingreso']
        verbose_name_plural = "Productos"

class Movimiento(models.Model):
    """
    Modelo para registrar todos los movimientos de inventario (entradas/salidas)
    """
    TIPO_CHOICES = [
        ('entrada', 'Entrada'),
        ('salida', 'Salida'),
        ('ajuste', 'Ajuste de Inventario'),
        ('devolucion', 'Devolución'),
    ]
    
    MOTIVO_CHOICES = [
        ('compra', 'Compra'),
        ('entrega_empleado', 'Entrega a Empleado'),
        ('envio_sucursal', 'Envío a Sucursal'),
        ('uso_interno', 'Uso Interno'),
        ('ajuste_inventario', 'Ajuste de Inventario'),
        ('producto_dañado', 'Producto Dañado'),
        ('devolucion', 'Devolución'),
        ('otro', 'Otro'),
    ]
    
    # Información del movimiento
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, help_text="Producto involucrado")
    tipo = models.CharField(max_length=15, choices=TIPO_CHOICES, help_text="Tipo de movimiento")
    cantidad = models.PositiveIntegerField(help_text="Cantidad del movimiento")
    motivo = models.CharField(max_length=20, choices=MOTIVO_CHOICES, help_text="Motivo del movimiento")
    
    # Información del destinatario (cuando aplique)
    destinatario = models.CharField(max_length=100, blank=True, help_text="Nombre del destinatario")
    area_destino = models.CharField(max_length=100, blank=True, help_text="Área o departamento destino")
    sucursal_destino = models.ForeignKey(Sucursal, on_delete=models.SET_NULL, null=True, blank=True, help_text="Sucursal destino")
    
    # Detalles adicionales
    observaciones = models.TextField(blank=True, help_text="Observaciones del movimiento")
    numero_proyecto = models.CharField(max_length=50, blank=True, help_text="Número de proyecto (opcional)")
    
    # Control de auditoría
    fecha_movimiento = models.DateTimeField(default=timezone.now, help_text="Fecha y hora del movimiento")
    usuario_registro = models.CharField(max_length=50, help_text="Usuario que registra el movimiento")
    
    # Nuevos campos con relaciones a Empleado (manteniendo campos antiguos por compatibilidad)
    usuario_registro_empleado = models.ForeignKey(
        'Empleado', 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True,
        related_name='movimientos_registrados',
        help_text="Empleado que registra el movimiento"
    )
    empleado_destinatario = models.ForeignKey(
        'Empleado',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimientos_recibidos',
        help_text="Empleado destinatario del movimiento"
    )
    
    # Stock después del movimiento (para auditoría)
    stock_anterior = models.PositiveIntegerField(help_text="Stock antes del movimiento")
    stock_posterior = models.PositiveIntegerField(help_text="Stock después del movimiento")
    
    @property
    def area_destino_automatica(self):
        """
        Retorna el área del empleado destinatario automáticamente
        """
        if self.empleado_destinatario:
            return self.empleado_destinatario.area
        return self.area_destino  # Fallback al campo de texto antiguo
    
    def save(self, *args, **kwargs):
        """
        Actualiza automáticamente el stock del producto y registra stocks de auditoría
        """
        # Si es un movimiento nuevo, registrar stock anterior
        if not self.pk:
            self.stock_anterior = self.producto.cantidad
            
            # Calcular nuevo stock según el tipo de movimiento
            if self.tipo in ['entrada', 'devolucion']:
                nuevo_stock = self.producto.cantidad + self.cantidad
            elif self.tipo == 'salida':
                nuevo_stock = max(0, self.producto.cantidad - self.cantidad)
            else:  # ajuste
                nuevo_stock = self.cantidad
            
            self.stock_posterior = nuevo_stock
            
            # Actualizar el stock del producto
            self.producto.cantidad = nuevo_stock
            self.producto.save()
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.tipo.title()} - {self.producto.nombre} ({self.cantidad} unidades)"
    
    class Meta:
        ordering = ['-fecha_movimiento']
        verbose_name_plural = "Movimientos"


class Empleado(models.Model):
    """
    Modelo para gestionar los empleados de la empresa
    Permite tener listas consistentes para destinatarios y usuarios que registran movimientos
    """
    nombre_completo = models.CharField(max_length=100, help_text="Nombre completo del empleado")
    cargo = models.CharField(max_length=50, help_text="Cargo o puesto del empleado")
    area = models.CharField(max_length=50, help_text="Área donde trabaja (ej: Laboratorio, Oficina)")
    activo = models.BooleanField(default=True, help_text="Empleado activo en la empresa")
    
    # Fechas de control
    fecha_ingreso = models.DateTimeField(auto_now_add=True, help_text="Fecha de registro en el sistema")
    fecha_actualizacion = models.DateTimeField(auto_now=True, help_text="Última actualización del registro")
    
    def __str__(self):
        return self.nombre_completo
    
    class Meta:
        ordering = ['nombre_completo']
        verbose_name_plural = "Empleados"
