from django.db import models
from django.contrib.auth.models import User
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
    
    # Objeto único - para productos que se prestan y regresan
    es_objeto_unico = models.BooleanField(
        default=False,
        verbose_name="Objeto Único",
        help_text="Marcar si es un producto único que se presta (permite stock mínimo 0, alerta solo cuando cantidad = 0)"
    )
    
    # Campos para manejo fraccionario (productos líquidos, granulados, etc.)
    es_fraccionable = models.BooleanField(
        default=False, 
        help_text="¿Se puede consumir en porciones? (ej: líquidos, granulados)"
    )
    unidad_base = models.CharField(
        max_length=20, 
        default='unidades', 
        help_text="Unidad de medida (ml, litros, kg, gramos, etc.)"
    )
    cantidad_unitaria = models.FloatField(
        default=1.0, 
        help_text="Cantidad por unidad completa (ej: 1000ml por botella)"
    )
    cantidad_actual = models.FloatField(
        default=0.0, 
        help_text="Cantidad real disponible en la unidad base"
    )
    cantidad_minima_alerta = models.FloatField(
        default=0.0, 
        help_text="Alerta cuando esté por debajo de este nivel"
    )
    
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
            # Generar código único: INV + timestamp + random (solo alfanumérico)
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            # Usar solo números para evitar problemas con scanners físicos
            random_part = str(uuid.uuid4().int)[:4]  # Solo números del UUID
            self.codigo_qr = f"INV{timestamp}{random_part}"
        super().save(*args, **kwargs)
    
    def clean(self):
        """
        Validaciones personalizadas para el modelo
        """
        from django.core.exceptions import ValidationError
        
        # Validación para stock_minimo basado en es_objeto_unico
        if not self.es_objeto_unico and self.stock_minimo <= 0:
            raise ValidationError({
                'stock_minimo': 'El stock mínimo debe ser mayor a 0 para productos normales.'
            })
        
        if self.es_objeto_unico and self.stock_minimo < 0:
            raise ValidationError({
                'stock_minimo': 'El stock mínimo no puede ser negativo.'
            })
    
    def generar_qr_image(self):
        """
        Genera la imagen QR como base64 para mostrar en templates
        Optimizado para compatibilidad con scanners físicos
        """
        try:
            import qrcode
            from PIL import Image
            
            # Configuración optimizada para scanners físicos
            qr = qrcode.QRCode(
                version=2,  # Versión 2 para mejor legibilidad
                error_correction=qrcode.constants.ERROR_CORRECT_M,  # Corrección media
                box_size=12,  # Cajas más grandes
                border=6,     # Borde más amplio
            )
            qr.add_data(self.codigo_qr)
            qr.make(fit=True)
            
            # Crear imagen directamente con PIL - mayor contraste
            img = qr.make_image(fill_color="black", back_color="white")
            
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            
            # Convertir a base64 para uso en templates
            img_str = base64.b64encode(buffer.getvalue()).decode()
            return f"data:image/png;base64,{img_str}"
            
        except Exception as e:
            # En caso de error, devolver un mensaje de error en lugar de fallar
            print(f"Error generando QR: {e}")
            return None
    
    def stock_bajo(self):
        """
        Verifica si el producto tiene stock bajo
        Para objetos únicos: alerta solo cuando cantidad = 0 (no disponible)
        Para productos normales: alerta cuando cantidad <= stock_minimo
        """
        if self.es_objeto_unico:
            return self.cantidad == 0  # Solo alerta cuando no hay ninguno disponible
        else:
            return self.cantidad <= self.stock_minimo  # Lógica normal
    
    def valor_total_stock(self):
        """
        Calcula el valor total del stock actual
        """
        return self.cantidad * self.costo_unitario
    
    def estado_disponibilidad(self):
        """
        Retorna el estado de disponibilidad del producto
        """
        if self.es_objeto_unico:
            return "Disponible" if self.cantidad > 0 else "No Disponible"
        else:
            if self.cantidad == 0:
                return "Agotado"
            elif self.cantidad <= self.stock_minimo:
                return "Stock Bajo"
            else:
                return "Disponible"
    
    # Métodos para manejo de productos fraccionables
    def porcentaje_disponible(self):
        """
        Calcula el porcentaje disponible del producto fraccionable
        Retorna 0-100 representando el porcentaje de la unidad actual
        """
        if not self.es_fraccionable or self.cantidad_unitaria == 0:
            return 100 if self.cantidad > 0 else 0
        
        # Asegurar que cantidad_actual no sea negativa
        cantidad_actual_segura = max(0, self.cantidad_actual)
        porcentaje = (cantidad_actual_segura / self.cantidad_unitaria) * 100
        
        # Retornar entre 0 y 100
        return max(0, min(100, porcentaje))
    
    def stock_fraccionario_bajo(self):
        """
        Verifica si el stock fraccionario está bajo el mínimo
        """
        if not self.es_fraccionable:
            return self.stock_bajo()
        
        return self.cantidad_actual <= self.cantidad_minima_alerta
    
    def cantidad_total_disponible(self):
        """
        Calcula la cantidad total disponible incluyendo unidades completas y fraccionarias
        """
        if not self.es_fraccionable:
            return self.cantidad
        
        # Unidades completas en stock (sin contar la actual) + cantidad actual
        unidades_completas = max(0, self.cantidad - 1) * self.cantidad_unitaria if self.cantidad > 0 else 0
        return unidades_completas + self.cantidad_actual
    
    def puede_consumir(self, cantidad_solicitada):
        """
        Verifica si se puede consumir la cantidad solicitada
        """
        if not self.es_fraccionable:
            return self.cantidad >= cantidad_solicitada
        
        return self.cantidad_total_disponible() >= cantidad_solicitada
    
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
    
    # Campos para movimientos fraccionarios
    es_movimiento_fraccionario = models.BooleanField(
        default=False,
        help_text="Indica si este movimiento es fraccionario (consumo parcial)"
    )
    cantidad_fraccionaria = models.FloatField(
        null=True, 
        blank=True, 
        help_text="Cantidad exacta en unidad base (ej: 600ml)"
    )
    unidad_utilizada = models.CharField(
        max_length=20, 
        blank=True, 
        help_text="Unidad de medida utilizada (ml, gramos, etc.)"
    )
    
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
    # Campos históricos para estados fraccionarios después del movimiento
    cantidad_fraccionaria_resultante = models.FloatField(
        null=True, blank=True,
        help_text="Cantidad fraccionaria restante en unidad base después del movimiento"
    )
    porcentaje_resultante = models.FloatField(
        null=True, blank=True,
        help_text="Porcentaje (0-100) restante de la unidad actual después del movimiento"
    )
    
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
        Incluye lógica para movimientos fraccionarios
        """
        # Si es un movimiento nuevo, registrar stock anterior
        if not self.pk:
            self.stock_anterior = self.producto.cantidad
            
            if self.es_movimiento_fraccionario and self.producto.es_fraccionable:
                # Manejo de movimientos fraccionarios
                self._procesar_movimiento_fraccionario()
            else:
                # Manejo de movimientos tradicionales (unidades completas)
                self._procesar_movimiento_tradicional()
            
        super().save(*args, **kwargs)
    
    def _procesar_movimiento_fraccionario(self):
        """
        Procesa movimientos fraccionarios (consumo parcial de productos)
        """
        cantidad_solicitada = self.cantidad_fraccionaria or 0
        
        if self.tipo == 'salida':
            # Verificar si hay suficiente cantidad disponible
            if self.producto.cantidad_actual >= cantidad_solicitada:
                # Consumir solo de la unidad actual
                self.producto.cantidad_actual -= cantidad_solicitada
            else:
                # Enfoque simplificado: trabajar con cantidades totales
                total_disponible_actual = self.producto.cantidad_total_disponible()
                total_despues_consumo = total_disponible_actual - cantidad_solicitada
                
                if total_despues_consumo >= 0:
                    # Calcular nuevas unidades y cantidad actual
                    nuevas_unidades_completas = int(total_despues_consumo / self.producto.cantidad_unitaria)
                    nueva_cantidad_actual = total_despues_consumo % self.producto.cantidad_unitaria
                    
                    # Si hay resto, significa que hay una unidad parcial
                    if nueva_cantidad_actual > 0:
                        self.producto.cantidad = nuevas_unidades_completas + 1
                        self.producto.cantidad_actual = nueva_cantidad_actual
                    else:
                        # No hay resto, todo son unidades completas
                        if nuevas_unidades_completas > 0:
                            self.producto.cantidad = nuevas_unidades_completas
                            self.producto.cantidad_actual = self.producto.cantidad_unitaria
                        else:
                            # No queda nada
                            self.producto.cantidad = 0
                            self.producto.cantidad_actual = 0
                else:
                    # No hay suficiente stock (no debería pasar por validación previa)
                    self.producto.cantidad_actual = 0
                    self.producto.cantidad = 0
                    
        elif self.tipo in ['entrada', 'devolucion']:
            # Para entradas fraccionarias, agregar a la cantidad actual
            self.producto.cantidad_actual += cantidad_solicitada
            
            # Si excede la cantidad unitaria, crear unidades completas
            while self.producto.cantidad_actual >= self.producto.cantidad_unitaria:
                self.producto.cantidad_actual -= self.producto.cantidad_unitaria
                self.producto.cantidad += 1
                
        # Registrar el stock posterior
        self.stock_posterior = self.producto.cantidad

        # Guardar valores resultantes fraccionarios en el movimiento (histórico)
        # cantidad_actual representa la cantidad restante en la unidad actual
        self.cantidad_fraccionaria_resultante = self.producto.cantidad_actual
        try:
            self.porcentaje_resultante = self.producto.porcentaje_disponible()
        except Exception:
            self.porcentaje_resultante = None

        # Guardar los cambios en el producto
        self.producto.save()
    
    def _procesar_movimiento_tradicional(self):
        """
        Procesa movimientos tradicionales (unidades completas)
        """
        # Calcular nuevo stock según el tipo de movimiento
        if self.tipo in ['entrada', 'devolucion']:
            nuevo_stock = self.producto.cantidad + self.cantidad
            
            # Si es un producto fraccionable y no tiene cantidad_actual, inicializar
            if self.producto.es_fraccionable and self.producto.cantidad_actual == 0:
                self.producto.cantidad_actual = self.producto.cantidad_unitaria
                
        elif self.tipo == 'salida':
            nuevo_stock = max(0, self.producto.cantidad - self.cantidad)
            
            # Si es fraccionable y se queda sin stock, resetear cantidad_actual
            if self.producto.es_fraccionable and nuevo_stock == 0:
                self.producto.cantidad_actual = 0
                
        else:  # ajuste
            nuevo_stock = self.cantidad
            
        self.stock_posterior = nuevo_stock
        
        # Actualizar el stock del producto
        self.producto.cantidad = nuevo_stock
        # Para productos fraccionables, registrar también el estado fraccionario resultante
        if self.producto.es_fraccionable:
            # Asegurar que cantidad_actual esté inicializada correctamente
            # Si no hay unidad parcial, mantener la existente
            self.cantidad_fraccionaria_resultante = self.producto.cantidad_actual
            try:
                self.porcentaje_resultante = self.producto.porcentaje_disponible()
            except Exception:
                self.porcentaje_resultante = None
        else:
            # No aplica para productos no fraccionables
            self.cantidad_fraccionaria_resultante = None
            self.porcentaje_resultante = None

        self.producto.save()
    
    def cantidad_display(self):
        """
        Retorna la representación correcta de la cantidad según el tipo de movimiento
        """
        if self.es_movimiento_fraccionario:
            return f"{self.cantidad_fraccionaria} {self.unidad_utilizada}"
        return f"{self.cantidad} unidades"
    
    def __str__(self):
        cantidad_texto = self.cantidad_display()
        return f"{self.tipo.title()} - {self.producto.nombre} ({cantidad_texto})"
    
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
    sucursal = models.ForeignKey(
        'Sucursal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='empleados',
        help_text="Sucursal a la que pertenece el empleado"
    )
    email = models.EmailField(blank=True, null=True, help_text="Correo electrónico del empleado (para notificaciones)")
    jefe_directo = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subordinados',
        verbose_name='Jefe Directo',
        help_text="Jefe directo del empleado en la jerarquía organizacional"
    )
    
    # Foto de perfil del empleado
    foto_perfil = models.ImageField(
        upload_to='empleados/fotos/',
        blank=True,
        null=True,
        verbose_name='Foto de Perfil',
        help_text='Foto del empleado para mostrar en el sistema (formatos: JPG, PNG, GIF)'
    )
    
    activo = models.BooleanField(default=True, help_text="Empleado activo en la empresa")
    
    # Fechas de control
    fecha_ingreso = models.DateTimeField(auto_now_add=True, help_text="Fecha de registro en el sistema")
    fecha_actualizacion = models.DateTimeField(auto_now=True, help_text="Última actualización del registro")
    
    # === CAMPOS PARA ACCESO AL SISTEMA ===
    # Estos campos controlan el acceso del empleado al Sistema Integral de Gestión
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='empleado',
        verbose_name='Usuario del Sistema',
        help_text='Usuario de Django asociado para acceso al sistema'
    )
    
    tiene_acceso_sistema = models.BooleanField(
        default=False,
        verbose_name='Tiene acceso al sistema',
        help_text='Indica si el empleado puede iniciar sesión en el sistema'
    )
    
    fecha_envio_credenciales = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de envío de credenciales',
        help_text='Última vez que se enviaron las credenciales por email'
    )
    
    contraseña_configurada = models.BooleanField(
        default=False,
        verbose_name='Contraseña configurada',
        help_text='Indica si el empleado ya cambió su contraseña temporal'
    )
    
    fecha_activacion_acceso = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de activación de acceso',
        help_text='Fecha en que el empleado completó su primer cambio de contraseña'
    )
    
    def __str__(self):
        return self.nombre_completo
    
    def get_foto_perfil_url(self):
        """
        Retorna la URL de la foto de perfil del empleado.
        Si no tiene foto, retorna None para usar las iniciales.
        """
        if self.foto_perfil:
            return self.foto_perfil.url
        return None
    
    def get_iniciales(self):
        """
        Retorna las iniciales del empleado para mostrar cuando no hay foto.
        Ejemplo: "Juan Pérez López" -> "JP"
        """
        nombres = self.nombre_completo.split()
        if len(nombres) >= 2:
            return f"{nombres[0][0]}{nombres[1][0]}".upper()
        elif len(nombres) == 1:
            return nombres[0][0:2].upper()
        return "US"
    
    def estado_acceso_display(self):
        """
        Retorna el estado de acceso al sistema en formato legible
        Para mostrar en templates y admin
        """
        if not self.user:
            return "Sin acceso"
        elif not self.contraseña_configurada:
            return "Pendiente de activación"
        else:
            return "Acceso activo"
    
    estado_acceso_display.short_description = 'Estado de Acceso'
    
    def obtener_estadisticas_ordenes_activas(self):
        """
        Obtiene estadísticas de las órdenes activas asignadas al técnico.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Este método cuenta cuántos equipos tiene asignados un técnico actualmente
        y cuántos de esos equipos NO encienden. Esto es útil para:
        1. Evitar sobrecargar técnicos
        2. Alertar cuando un técnico ya tiene muchos equipos complejos
        3. Distribuir mejor la carga de trabajo
        
        Returns:
            dict: Diccionario con estadísticas:
                - ordenes_activas: Total de órdenes no finalizadas/entregadas
                - equipos_no_encienden: Cantidad de equipos que NO encienden
                - tiene_sobrecarga: True si tiene 3 o más equipos que no encienden
                - porcentaje_no_encienden: % de equipos que no encienden
        """
        # Importar aquí para evitar circular imports
        from servicio_tecnico.models import OrdenServicio
        
        # Estados que se consideran "activos" (no terminados)
        estados_activos = ['espera', 'diagnostico', 'cotizacion', 'reparacion']
        
        # Obtener órdenes activas del técnico
        ordenes_activas = OrdenServicio.objects.filter(
            tecnico_asignado_actual=self,
            estado__in=estados_activos
        ).select_related('detalle_equipo')
        
        total_ordenes = ordenes_activas.count()
        
        # Contar cuántos equipos NO encienden
        equipos_no_encienden = ordenes_activas.filter(
            detalle_equipo__equipo_enciende=False
        ).count()
        
        # Calcular porcentaje
        porcentaje = 0
        if total_ordenes > 0:
            porcentaje = round((equipos_no_encienden / total_ordenes) * 100, 1)
        
        # Determinar si tiene sobrecarga (criterio: 3+ equipos que no encienden)
        tiene_sobrecarga = equipos_no_encienden >= 3
        
        return {
            'ordenes_activas': total_ordenes,
            'equipos_no_encienden': equipos_no_encienden,
            'tiene_sobrecarga': tiene_sobrecarga,
            'porcentaje_no_encienden': porcentaje,
        }
    
    class Meta:
        ordering = ['nombre_completo']
        verbose_name_plural = "Empleados"
