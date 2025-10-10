"""
Modelos para el Sistema de Gestión de Órdenes de Servicio Técnico
Gestiona el ciclo completo de reparación de equipos de cómputo
"""
from django.db import models
from django.utils import timezone
from django.core.validators import FileExtensionValidator, MinValueValidator
from decimal import Decimal
from inventario.models import Sucursal, Empleado
from scorecard.models import ComponenteEquipo, Incidencia
from config.constants import (
    TIPO_EQUIPO_CHOICES,
    GAMA_EQUIPO_CHOICES,
    ESTADO_ORDEN_CHOICES,
    PAQUETES_CHOICES,
    TIPO_IMAGEN_CHOICES,
    TIPO_EVENTO_CHOICES,
    MOTIVO_RECHAZO_COTIZACION,
    ESTADO_PIEZA_CHOICES,
    MOTIVO_RHITSO_CHOICES,
    obtener_precio_paquete,
)


# ============================================================================
# MODELO 1: ORDEN DE SERVICIO (Modelo Central)
# ============================================================================

class OrdenServicio(models.Model):
    """
    Modelo central que representa una orden de servicio técnico.
    Gestiona todo el ciclo de vida de la reparación de un equipo.
    
    ACTUALIZACIÓN (Octubre 2025): Sistema refactorizado para mayor flexibilidad
    
    tipo_servicio indica el flujo PRINCIPAL:
    - 'diagnostico': Servicio con diagnóstico técnico (cotización)
    - 'venta_mostrador': Servicio directo sin diagnóstico
    
    COMPLEMENTOS OPCIONALES (pueden coexistir):
    - cotizacion: Reparación/diagnóstico (OneToOne con Cotizacion)
    - venta_mostrador: Ventas adicionales (OneToOne con VentaMostrador)
    
    Una orden puede tener:
    - Solo cotización (diagnóstico puro)
    - Solo venta_mostrador (venta directa)
    - Ambos (diagnóstico + ventas adicionales como accesorios)
    - Ninguno (orden recién creada)
    
    Relaciones:
    - Tiene UN DetalleEquipo (OneToOne)
    - Puede tener UNA Cotización (OneToOne) - OPCIONAL
    - Puede tener UNA VentaMostrador (OneToOne) - OPCIONAL
    - Puede tener MUCHAS Imágenes (ForeignKey inverso)
    - Puede tener MUCHOS Eventos de Historial (ForeignKey inverso)
    - Puede estar relacionada con UNA Incidencia de ScoreCard si es reingreso
    """
    
    # IDENTIFICACIÓN
    numero_orden_interno = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        help_text="Número de orden auto-generado (ORD-2025-0001)"
    )
    
    # FECHAS PRINCIPALES
    fecha_ingreso = models.DateTimeField(
        default=timezone.now,
        help_text="Fecha y hora de ingreso al centro de servicio"
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        help_text="Última actualización del registro"
    )
    fecha_finalizacion = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha en que se finalizó la reparación"
    )
    fecha_entrega = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha en que se entregó al cliente"
    )
    
    # UBICACIÓN Y RESPONSABLES
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.PROTECT,
        related_name='ordenes_servicio',
        help_text="Sucursal donde se registra la orden"
    )
    responsable_seguimiento = models.ForeignKey(
        Empleado,
        on_delete=models.PROTECT,
        related_name='ordenes_responsable',
        help_text="Empleado responsable del seguimiento de la orden"
    )
    tecnico_asignado_actual = models.ForeignKey(
        Empleado,
        on_delete=models.PROTECT,
        related_name='ordenes_tecnico',
        help_text="Técnico actualmente asignado a la orden"
    )
    
    # ESTADO Y WORKFLOW
    estado = models.CharField(
        max_length=30,  # Aumentado para soportar 'convertida_a_diagnostico' (24 chars)
        choices=ESTADO_ORDEN_CHOICES,
        default='espera',
        help_text="Estado actual de la orden"
    )
    
    # REINGRESO Y RELACIÓN CON SCORECARD
    es_reingreso = models.BooleanField(
        default=False,
        help_text="¿Es un reingreso de un equipo ya reparado?"
    )
    orden_original = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reingresos',
        help_text="Orden original si este es un reingreso"
    )
    incidencia_scorecard = models.ForeignKey(
        Incidencia,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ordenes_relacionadas',
        help_text="Incidencia de ScoreCard generada si es reingreso"
    )
    
    # RHITSO (Reparación Especializada)
    es_candidato_rhitso = models.BooleanField(
        default=False,
        help_text="¿Requiere reparación especializada (soldadura, reballing)?"
    )
    motivo_rhitso = models.CharField(
        max_length=30,
        choices=MOTIVO_RHITSO_CHOICES,
        blank=True,
        help_text="Motivo por el cual se considera para RHITSO"
    )
    descripcion_rhitso = models.TextField(
        blank=True,
        help_text="Descripción detallada del motivo RHITSO"
    )
    
    # FACTURACIÓN
    requiere_factura = models.BooleanField(
        default=False,
        help_text="¿El cliente requiere factura?"
    )
    factura_emitida = models.BooleanField(
        default=False,
        help_text="¿La factura ya fue emitida?"
    )
    motivo_no_factura = models.TextField(
        blank=True,
        help_text="Motivo por el cual no se ha emitido la factura"
    )
    
    # TIPO DE SERVICIO (Sistema Venta Mostrador)
    # =========================================================================
    # Indica el flujo PRINCIPAL de la orden, pero no restringe complementos
    tipo_servicio = models.CharField(
        max_length=20,
        choices=[
            ('diagnostico', 'Con Diagnóstico Técnico'),
            ('venta_mostrador', 'Venta Mostrador - Sin Diagnóstico'),
        ],
        default='diagnostico',
        help_text="Tipo de servicio: con diagnóstico técnico o venta mostrador directa"
    )
    
    control_calidad_requerido = models.BooleanField(
        default=False,
        help_text="¿Requiere pasar por control de calidad? (Opcional para ventas simples como accesorios)"
    )
    
    # CAMPOS CALCULADOS (para reportes y KPIs)
    año = models.IntegerField(
        editable=False,
        help_text="Año de ingreso"
    )
    mes = models.IntegerField(
        editable=False,
        help_text="Mes de ingreso (1-12)"
    )
    semana = models.IntegerField(
        editable=False,
        help_text="Semana del año (1-53)"
    )
    
    def save(self, *args, **kwargs):
        """
        Sobrescribir save para:
        1. Generar número de orden automático
        2. Calcular campos de fecha
        3. Registrar eventos en el historial
        """
        es_nueva = self.pk is None
        estado_anterior = None
        tecnico_anterior = None
        
        # Si es actualización, guardar estado anterior
        if not es_nueva:
            try:
                orden_anterior = OrdenServicio.objects.get(pk=self.pk)
                estado_anterior = orden_anterior.estado
                tecnico_anterior = orden_anterior.tecnico_asignado_actual
            except OrdenServicio.DoesNotExist:
                pass
        
        # Generar número de orden si es nuevo
        if not self.numero_orden_interno:
            año_actual = timezone.now().year
            
            # Obtener el último número del año
            ultima_orden = OrdenServicio.objects.filter(
                numero_orden_interno__startswith=f'ORD-{año_actual}'
            ).order_by('-numero_orden_interno').first()
            
            if ultima_orden:
                try:
                    ultimo_numero = int(ultima_orden.numero_orden_interno.split('-')[-1])
                    siguiente_numero = ultimo_numero + 1
                except (ValueError, IndexError):
                    siguiente_numero = OrdenServicio.objects.filter(
                        numero_orden_interno__startswith=f'ORD-{año_actual}'
                    ).count() + 1
            else:
                siguiente_numero = 1
            
            self.numero_orden_interno = f"ORD-{año_actual}-{siguiente_numero:04d}"
        
        # Calcular campos de fecha
        fecha = self.fecha_ingreso
        self.año = fecha.year
        self.mes = fecha.month
        self.semana = fecha.isocalendar()[1]
        
        # Guardar el objeto
        super().save(*args, **kwargs)
        
        # Registrar eventos en historial
        if es_nueva:
            HistorialOrden.objects.create(
                orden=self,
                tipo_evento='creacion',
                comentario=f"Orden creada - Estado inicial: {self.get_estado_display()}",
                es_sistema=True
            )
        else:
            # Registrar cambio de estado
            if estado_anterior and estado_anterior != self.estado:
                HistorialOrden.objects.create(
                    orden=self,
                    tipo_evento='cambio_estado',
                    estado_anterior=estado_anterior,
                    estado_nuevo=self.estado,
                    comentario=f"Estado cambiado de '{dict(ESTADO_ORDEN_CHOICES).get(estado_anterior)}' a '{self.get_estado_display()}'",
                    es_sistema=True
                )
            
            # Registrar cambio de técnico
            if tecnico_anterior and tecnico_anterior != self.tecnico_asignado_actual:
                HistorialOrden.objects.create(
                    orden=self,
                    tipo_evento='cambio_tecnico',
                    tecnico_anterior=tecnico_anterior,
                    tecnico_nuevo=self.tecnico_asignado_actual,
                    comentario=f"Técnico cambiado de '{tecnico_anterior.nombre_completo}' a '{self.tecnico_asignado_actual.nombre_completo}'",
                    es_sistema=True
                )
    
    def clean(self):
        """
        Validaciones personalizadas para mantener integridad de datos.
        
        ACTUALIZACIÓN (Octubre 2025): Sistema refactorizado
        - Venta mostrador es ahora un complemento opcional
        - Una orden puede tener cotización, venta_mostrador, o ambos
        - No hay restricciones basadas en tipo_servicio
        
        Reglas de negocio simplificadas:
        1. Si requiere factura, debe haber información fiscal
        2. Estados finales requieren fechas correspondientes
        """
        from django.core.exceptions import ValidationError
        
        # Validación básica: Estados finales requieren fechas
        if self.estado == 'entregado' and not self.fecha_entrega:
            raise ValidationError({
                'fecha_entrega': 'Una orden entregada debe tener fecha de entrega'
            })
        
        if self.estado == 'finalizado' and not self.fecha_finalizacion:
            raise ValidationError({
                'fecha_finalizacion': 'Una orden finalizada debe tener fecha de finalización'
            })
    
    @property
    def dias_en_servicio(self):
        """Calcula los días que lleva la orden en el sistema"""
        if self.fecha_entrega:
            return (self.fecha_entrega.date() - self.fecha_ingreso.date()).days
        return (timezone.now().date() - self.fecha_ingreso.date()).days
    
    @property
    def esta_retrasada(self):
        """Determina si la orden está retrasada (más de 15 días sin entregar)"""
        if self.estado != 'entregado' and self.dias_en_servicio > 15:
            return True
        return False
    
    def crear_incidencia_reingreso(self, usuario=None):
        """
        Crea automáticamente una incidencia en ScoreCard cuando es reingreso.
        
        Args:
            usuario (Empleado): Empleado que registra la incidencia
        
        Returns:
            Incidencia: La incidencia creada
        """
        if self.es_reingreso and not self.incidencia_scorecard:
            # Importar aquí para evitar importación circular
            from scorecard.models import Incidencia, CategoriaIncidencia
            
            # Obtener o crear categoría de reingreso
            categoria, _ = CategoriaIncidencia.objects.get_or_create(
                nombre="Reingreso de equipo",
                defaults={
                    'descripcion': "Equipo que regresa después de una reparación",
                    'color': "#e74c3c"
                }
            )
            
            # Obtener datos del equipo
            detalle = self.detalle_equipo
            
            incidencia = Incidencia.objects.create(
                tipo_equipo=detalle.tipo_equipo,
                marca=detalle.marca,
                modelo=detalle.modelo,
                numero_serie=detalle.numero_serie,
                numero_orden=self.numero_orden_interno,
                sucursal=self.sucursal,
                tecnico_responsable=self.tecnico_asignado_actual,
                inspector_calidad=self.responsable_seguimiento,
                area_detectora='recepcion',
                tipo_incidencia=categoria,
                categoria_fallo='funcional',
                grado_severidad='alto',
                descripcion_incidencia=f"Reingreso de orden {self.numero_orden_interno}. Falla: {detalle.falla_principal}",
                es_reincidencia=True,
            )
            
            self.incidencia_scorecard = incidencia
            self.save()
            
            # Registrar en historial
            HistorialOrden.objects.create(
                orden=self,
                tipo_evento='sistema',
                comentario=f"Incidencia de ScoreCard creada automáticamente: {incidencia.folio}",
                usuario=usuario,
                es_sistema=True
            )
            
            return incidencia
        return None
    
    # ⛔ MÉTODO ELIMINADO: convertir_a_diagnostico()
    # 
    # Este método creaba una NUEVA orden cuando una venta mostrador fallaba.
    # En el sistema refactorizado (Octubre 2025), ya no es necesario:
    # 
    # ANTES (Sistema Antiguo):
    # - Venta mostrador y diagnóstico eran excluyentes
    # - Si una venta mostrador fallaba, se convertía creando una NUEVA orden
    # - Generaba duplicación de órdenes y complejidad en el seguimiento
    # 
    # AHORA (Sistema Actual):
    # - Venta mostrador es un complemento opcional
    # - Puede coexistir con cotización en la MISMA orden
    # - No se requiere duplicar órdenes
    # - Simplemente se agregan ambos complementos a la orden según se necesiten
    # 
    # Beneficios del cambio:
    # - Menos duplicación de datos
    # - Seguimiento más simple (una sola orden)
    # - Código más limpio (~138 líneas eliminadas)
    # - Mayor flexibilidad en el flujo de trabajo
    
    def __str__(self):
        return f"{self.numero_orden_interno} - {self.sucursal.nombre} ({self.get_estado_display()})"
    
    class Meta:
        ordering = ['-fecha_ingreso']
        verbose_name = "Orden de Servicio"
        verbose_name_plural = "Órdenes de Servicio"
        indexes = [
            models.Index(fields=['-fecha_ingreso']),
            models.Index(fields=['numero_orden_interno']),
            models.Index(fields=['estado']),
            models.Index(fields=['sucursal']),
            models.Index(fields=['año', 'mes']),
        ]


# ============================================================================
# MODELO 2: DETALLE DEL EQUIPO
# ============================================================================

class DetalleEquipo(models.Model):
    """
    Información detallada del equipo en servicio.
    Relación OneToOne con OrdenServicio.
    """
    
    # RELACIÓN CON ORDEN
    orden = models.OneToOneField(
        OrdenServicio,
        on_delete=models.CASCADE,
        related_name='detalle_equipo',
        primary_key=True,
        help_text="Orden de servicio a la que pertenece este detalle"
    )
    
    # INFORMACIÓN BÁSICA DEL EQUIPO
    tipo_equipo = models.CharField(
        max_length=10,
        choices=TIPO_EQUIPO_CHOICES,
        help_text="Tipo de equipo (PC, Laptop, AIO)"
    )
    marca = models.CharField(
        max_length=50,
        help_text="Marca del equipo"
    )
    modelo = models.CharField(
        max_length=100,
        help_text="Modelo específico del equipo"
    )
    numero_serie = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Número de serie del equipo (Service Tag)"
    )
    orden_cliente = models.CharField(
        max_length=50,
        db_index=True,
        blank=True,
        help_text="Número de orden del cliente (identificador interno del cliente)"
    )
    
    # GAMA DEL EQUIPO
    gama = models.CharField(
        max_length=10,
        choices=GAMA_EQUIPO_CHOICES,
        help_text="Gama del equipo (calculada automáticamente)"
    )
    
    # ACCESORIOS
    tiene_cargador = models.BooleanField(
        default=False,
        help_text="¿El equipo incluye cargador?"
    )
    numero_serie_cargador = models.CharField(
        max_length=100,
        blank=True,
        help_text="Número de serie del cargador (si aplica)"
    )
    
    # ESTADO AL INGRESO
    equipo_enciende = models.BooleanField(
        default=True,
        help_text="¿El equipo enciende al momento del ingreso?"
    )
    falla_principal = models.TextField(
        help_text="Descripción de la falla principal reportada por el cliente"
    )
    
    # DIAGNÓSTICO
    diagnostico_sic = models.TextField(
        blank=True,
        help_text="Diagnóstico técnico del equipo (SIC - Sistema de Información del Cliente)"
    )
    fecha_inicio_diagnostico = models.DateField(
        null=True,
        blank=True,
        help_text="Fecha en que inició el diagnóstico"
    )
    fecha_fin_diagnostico = models.DateField(
        null=True,
        blank=True,
        help_text="Fecha en que finalizó el diagnóstico"
    )
    
    # REPARACIÓN
    fecha_inicio_reparacion = models.DateField(
        null=True,
        blank=True,
        help_text="Fecha en que inició la reparación"
    )
    fecha_fin_reparacion = models.DateField(
        null=True,
        blank=True,
        help_text="Fecha en que finalizó la reparación"
    )
    
    @property
    def dias_diagnostico(self):
        """Calcula los días que tomó el diagnóstico"""
        if self.fecha_inicio_diagnostico and self.fecha_fin_diagnostico:
            return (self.fecha_fin_diagnostico - self.fecha_inicio_diagnostico).days
        return None
    
    @property
    def dias_reparacion(self):
        """Calcula los días que tomó la reparación"""
        if self.fecha_inicio_reparacion and self.fecha_fin_reparacion:
            return (self.fecha_fin_reparacion - self.fecha_inicio_reparacion).days
        return None
    
    @property
    def duracion_diagnostico(self):
        """
        Devuelve texto descriptivo de la duración del diagnóstico.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        - Esta property calcula cuánto tiempo tomó el diagnóstico
        - Devuelve un texto legible como "2 días" o "1 día"
        - Si no hay fechas, devuelve None
        - Se usa en templates para mostrar información al usuario
        """
        dias = self.dias_diagnostico
        if dias is not None:
            if dias == 0:
                return "Mismo día"
            elif dias == 1:
                return "1 día"
            else:
                return f"{dias} días"
        return None
    
    @property
    def duracion_reparacion(self):
        """
        Devuelve texto descriptivo de la duración de la reparación.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        - Esta property calcula cuánto tiempo tomó la reparación
        - Devuelve un texto legible como "3 días" o "1 día"
        - Si no hay fechas, devuelve None
        - Se usa en templates para mostrar información al usuario
        """
        dias = self.dias_reparacion
        if dias is not None:
            if dias == 0:
                return "Mismo día"
            elif dias == 1:
                return "1 día"
            else:
                return f"{dias} días"
        return None
    
    def calcular_gama(self):
        """
        Calcula la gama del equipo basándose en la tabla de referencia.
        Si no encuentra coincidencia, asigna 'media' por defecto.
        """
        try:
            referencia = ReferenciaGamaEquipo.obtener_gama(self.marca, self.modelo)
            if referencia:
                self.gama = referencia.gama
            else:
                self.gama = 'media'  # Por defecto
        except:
            self.gama = 'media'
    
    def save(self, *args, **kwargs):
        """Calcular gama antes de guardar"""
        if not self.gama:
            self.calcular_gama()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.tipo_equipo.upper()} {self.marca} {self.modelo} - S/N: {self.numero_serie}"
    
    class Meta:
        verbose_name = "Detalle de Equipo"
        verbose_name_plural = "Detalles de Equipos"


# ============================================================================
# MODELO 3: REFERENCIA DE GAMA DE EQUIPOS (Catálogo)
# ============================================================================

class ReferenciaGamaEquipo(models.Model):
    """
    Catálogo de referencia para determinar automáticamente la gama de un equipo.
    Permite clasificar equipos en alta, media o baja gama según marca y modelo.
    """
    
    marca = models.CharField(
        max_length=50,
        help_text="Marca del equipo"
    )
    modelo_base = models.CharField(
        max_length=100,
        help_text="Modelo base o familia (ej: ThinkPad, Inspiron, Pavilion)"
    )
    gama = models.CharField(
        max_length=10,
        choices=GAMA_EQUIPO_CHOICES,
        help_text="Gama del equipo"
    )
    rango_costo_min = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Costo mínimo aproximado (para referencia)"
    )
    rango_costo_max = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Costo máximo aproximado (para referencia)"
    )
    activo = models.BooleanField(
        default=True,
        help_text="Referencia activa para cálculo automático"
    )
    
    # Fechas de control
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    @classmethod
    def obtener_gama(cls, marca, modelo):
        """
        Busca la gama de un equipo según su marca y modelo.
        
        Args:
            marca (str): Marca del equipo
            modelo (str): Modelo del equipo
        
        Returns:
            ReferenciaGamaEquipo o None: Referencia encontrada o None
        """
        # Buscar coincidencia exacta primero
        referencia = cls.objects.filter(
            marca__iexact=marca,
            modelo_base__iexact=modelo,
            activo=True
        ).first()
        
        if referencia:
            return referencia
        
        # Buscar coincidencia parcial (el modelo contiene el modelo_base)
        referencias = cls.objects.filter(
            marca__iexact=marca,
            activo=True
        )
        
        for ref in referencias:
            if ref.modelo_base.lower() in modelo.lower():
                return ref
        
        return None
    
    def __str__(self):
        return f"{self.marca} {self.modelo_base} - {self.get_gama_display()}"
    
    class Meta:
        ordering = ['marca', 'modelo_base']
        verbose_name = "Referencia de Gama"
        verbose_name_plural = "Referencias de Gamas de Equipos"
        unique_together = ['marca', 'modelo_base']




# ============================================================================
# MODELO 4: COTIZACIÓN
# ============================================================================

class Cotizacion(models.Model):
    """
    Cotización enviada al cliente con las piezas y servicios necesarios.
    Relación OneToOne con OrdenServicio.
    """
    
    # RELACIÓN CON ORDEN
    orden = models.OneToOneField(
        OrdenServicio,
        on_delete=models.CASCADE,
        related_name='cotizacion',
        primary_key=True,
        help_text="Orden de servicio a la que pertenece esta cotización"
    )
    
    # FECHAS DE COTIZACIÓN
    fecha_envio = models.DateTimeField(
        default=timezone.now,
        help_text="Fecha en que se envió la cotización al cliente"
    )
    fecha_respuesta = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha en que el cliente respondió"
    )
    
    # RESPUESTA DEL CLIENTE
    usuario_acepto = models.BooleanField(
        null=True,
        blank=True,
        help_text="¿El usuario aceptó la cotización? (Null = Sin respuesta)"
    )
    motivo_rechazo = models.CharField(
        max_length=30,
        choices=MOTIVO_RECHAZO_COTIZACION,
        blank=True,
        help_text="Motivo por el cual rechazó la cotización"
    )
    detalle_rechazo = models.TextField(
        blank=True,
        help_text="Detalle adicional del motivo de rechazo"
    )
    
    # COSTOS
    costo_mano_obra = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Costo de mano de obra"
    )
    
    @property
    def costo_total_piezas(self):
        """Calcula el costo total de todas las piezas cotizadas"""
        return sum(
            pieza.costo_total 
            for pieza in self.piezas_cotizadas.all()
        )
    
    @property
    def costo_piezas_aceptadas(self):
        """Calcula el costo total de las piezas aceptadas por el cliente"""
        return sum(
            pieza.costo_total 
            for pieza in self.piezas_cotizadas.filter(aceptada_por_cliente=True)
        )
    
    @property
    def costo_piezas_rechazadas(self):
        """Calcula el costo total de las piezas rechazadas por el cliente"""
        return sum(
            pieza.costo_total 
            for pieza in self.piezas_cotizadas.filter(aceptada_por_cliente=False)
        )
    
    @property
    def costo_total(self):
        """Calcula el costo total (piezas + mano de obra)"""
        return self.costo_total_piezas + self.costo_mano_obra
    
    @property
    def dias_sin_respuesta(self):
        """Calcula los días que lleva sin respuesta"""
        if self.fecha_respuesta:
            return (self.fecha_respuesta.date() - self.fecha_envio.date()).days
        return (timezone.now().date() - self.fecha_envio.date()).days
    
    def __str__(self):
        estado = "Aceptada" if self.usuario_acepto else ("Rechazada" if self.usuario_acepto == False else "Sin Respuesta")
        return f"Cotización {self.orden.numero_orden_interno} - {estado}"
    
    class Meta:
        verbose_name = "Cotización"
        verbose_name_plural = "Cotizaciones"


# ============================================================================
# MODELO 5: PIEZA COTIZADA
# ============================================================================

class PiezaCotizada(models.Model):
    """
    Cada pieza incluida en una cotización.
    Permite registrar múltiples piezas por cotización.
    """
    
    # RELACIÓN CON COTIZACIÓN
    cotizacion = models.ForeignKey(
        Cotizacion,
        on_delete=models.CASCADE,
        related_name='piezas_cotizadas',
        help_text="Cotización a la que pertenece esta pieza"
    )
    
    # INFORMACIÓN DE LA PIEZA
    componente = models.ForeignKey(
        ComponenteEquipo,
        on_delete=models.PROTECT,
        related_name='piezas_cotizadas',
        help_text="Componente del catálogo (reutiliza de ScoreCard)"
    )
    descripcion_adicional = models.TextField(
        blank=True,
        help_text="Descripción adicional o específica de la pieza"
    )
    
    # ORIGEN DE LA SUGERENCIA
    sugerida_por_tecnico = models.BooleanField(
        default=True,
        help_text="¿Fue sugerida por el técnico en el diagnóstico?"
    )
    es_necesaria = models.BooleanField(
        default=True,
        help_text="¿Es necesaria para el funcionamiento? (False = Mejora estética/rendimiento)"
    )
    
    # CANTIDAD Y COSTOS
    cantidad = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Cantidad de piezas"
    )
    costo_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Costo unitario de la pieza"
    )
    
    # RESPUESTA DEL CLIENTE
    aceptada_por_cliente = models.BooleanField(
        null=True,
        blank=True,
        help_text="¿El cliente aceptó cambiar esta pieza? (Null = Sin respuesta)"
    )
    motivo_rechazo_pieza = models.TextField(
        blank=True,
        help_text="Motivo por el cual rechazó esta pieza específica"
    )
    
    # ORDEN DE PRIORIDAD
    orden_prioridad = models.PositiveIntegerField(
        default=1,
        help_text="Orden de prioridad (1 = más importante)"
    )
    
    # Fechas de control
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    @property
    def costo_total(self):
        """Calcula el costo total de esta pieza (cantidad × costo unitario)"""
        return self.cantidad * self.costo_unitario
    
    def __str__(self):
        return f"{self.componente.nombre} × {self.cantidad} - ${self.costo_total}"
    
    class Meta:
        ordering = ['orden_prioridad', 'fecha_creacion']
        verbose_name = "Pieza Cotizada"
        verbose_name_plural = "Piezas Cotizadas"


# ============================================================================
# MODELO 6: SEGUIMIENTO DE PIEZA
# ============================================================================

class SeguimientoPieza(models.Model):
    """
    Seguimiento de pedidos de piezas a proveedores.
    Permite rastrear múltiples pedidos por cotización.
    
    NUEVA FUNCIONALIDAD:
    Ahora puede vincularse a piezas específicas que fueron aceptadas por el cliente.
    Esto permite un seguimiento más preciso de qué piezas se están esperando.
    """
    
    # RELACIÓN CON COTIZACIÓN
    cotizacion = models.ForeignKey(
        Cotizacion,
        on_delete=models.CASCADE,
        related_name='seguimientos_piezas',
        help_text="Cotización a la que pertenece este seguimiento"
    )
    
    # NUEVO: RELACIÓN CON PIEZAS ESPECÍFICAS
    piezas = models.ManyToManyField(
        'PiezaCotizada',
        blank=True,
        related_name='seguimientos',
        help_text="Piezas específicas que se están rastreando en este pedido"
    )
    
    # INFORMACIÓN DEL PEDIDO
    proveedor = models.CharField(
        max_length=100,
        help_text="Nombre del proveedor"
    )
    descripcion_piezas = models.TextField(
        help_text="Descripción de las piezas pedidas en este seguimiento"
    )
    numero_pedido = models.CharField(
        max_length=100,
        blank=True,
        help_text="Número de pedido o tracking del proveedor"
    )
    
    # FECHAS DE SEGUIMIENTO
    fecha_pedido = models.DateField(
        default=timezone.now,
        help_text="Fecha en que se realizó el pedido"
    )
    fecha_entrega_estimada = models.DateField(
        help_text="Fecha estimada de llegada"
    )
    fecha_entrega_real = models.DateField(
        null=True,
        blank=True,
        help_text="Fecha real en que llegó la pieza"
    )
    
    # ESTADO DEL PEDIDO
    estado = models.CharField(
        max_length=15,
        choices=ESTADO_PIEZA_CHOICES,
        default='pedido',
        help_text="Estado actual del pedido"
    )
    
    # NOTAS Y SEGUIMIENTO
    notas_seguimiento = models.TextField(
        blank=True,
        help_text="Notas y actualizaciones del seguimiento"
    )
    
    # Fechas de control
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    @property
    def dias_desde_pedido(self):
        """Calcula los días desde que se hizo el pedido"""
        if self.fecha_entrega_real:
            return (self.fecha_entrega_real - self.fecha_pedido).days
        return (timezone.now().date() - self.fecha_pedido).days
    
    @property
    def esta_retrasado(self):
        """Determina si el pedido está retrasado"""
        if not self.fecha_entrega_real and timezone.now().date() > self.fecha_entrega_estimada:
            return True
        return False
    
    @property
    def dias_retraso(self):
        """Calcula los días de retraso"""
        if self.esta_retrasado:
            return (timezone.now().date() - self.fecha_entrega_estimada).days
        return 0
    
    def __str__(self):
        return f"{self.proveedor} - {self.get_estado_display()} ({self.cotizacion.orden.numero_orden_interno})"
    
    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = "Seguimiento de Pieza"
        verbose_name_plural = "Seguimientos de Piezas"


# ============================================================================
# MODELO 7: VENTA MOSTRADOR
# ============================================================================

class VentaMostrador(models.Model):
    """
    Servicios adicionales de venta mostrador asociados a una orden.
    Relación OneToOne con OrdenServicio.
    """
    
    # RELACIÓN CON ORDEN
    orden = models.OneToOneField(
        OrdenServicio,
        on_delete=models.CASCADE,
        related_name='venta_mostrador',
        primary_key=True,
        help_text="Orden de servicio a la que pertenece esta venta"
    )
    
    # IDENTIFICACIÓN
    folio_venta = models.CharField(
        max_length=20,
        unique=True,
        help_text="Folio de venta mostrador (VM-2025-0001)"
    )
    fecha_venta = models.DateTimeField(
        default=timezone.now,
        help_text="Fecha de la venta"
    )
    
    # PAQUETES
    paquete = models.CharField(
        max_length=10,
        choices=PAQUETES_CHOICES,
        default='ninguno',
        help_text="Paquete de servicio adicional"
    )
    
    # SERVICIOS ADICIONALES
    incluye_cambio_pieza = models.BooleanField(
        default=False,
        help_text="¿Incluye cambio de pieza sin diagnóstico?"
    )
    costo_cambio_pieza = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Costo del servicio de cambio de pieza"
    )
    
    incluye_limpieza = models.BooleanField(
        default=False,
        help_text="¿Incluye servicio de limpieza y mantenimiento?"
    )
    costo_limpieza = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Costo del servicio de limpieza"
    )
    
    incluye_kit_limpieza = models.BooleanField(
        default=False,
        help_text="¿Se vendió kit de limpieza?"
    )
    costo_kit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Costo del kit de limpieza"
    )
    
    incluye_reinstalacion_so = models.BooleanField(
        default=False,
        help_text="¿Incluye reinstalación de sistema operativo?"
    )
    costo_reinstalacion = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Costo de reinstalación de SO"
    )
    
    # NOTAS
    notas_adicionales = models.TextField(
        blank=True,
        help_text="Notas adicionales sobre la venta"
    )
    
    # COMISIONES (Sistema de comisiones futuro)
    genera_comision = models.BooleanField(
        default=False,
        help_text="¿Esta venta genera comisión para el responsable? (Paquetes siempre generan)"
    )
    
    # Fechas de control
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    @property
    def costo_paquete(self):
        """Obtiene el costo del paquete desde constants.py"""
        return Decimal(str(obtener_precio_paquete(self.paquete)))
    
    @property
    def total_venta(self):
        """
        Calcula el total de la venta sumando todos los conceptos:
        - Paquete (premium/oro/plata)
        - Servicios adicionales (cambio pieza, limpieza, kit, reinstalación)
        - Piezas vendidas individualmente
        """
        total = self.costo_paquete
        total += self.costo_cambio_pieza
        total += self.costo_limpieza
        total += self.costo_kit
        total += self.costo_reinstalacion
        
        # NUEVO: Sumar todas las piezas vendidas individualmente
        if hasattr(self, 'piezas_vendidas'):
            total += sum(pieza.subtotal for pieza in self.piezas_vendidas.all())
        
        return total
    
    @property
    def total_piezas_vendidas(self):
        """
        Calcula el total solo de piezas vendidas individualmente.
        No incluye paquetes ni servicios.
        """
        if hasattr(self, 'piezas_vendidas'):
            return sum(pieza.subtotal for pieza in self.piezas_vendidas.all())
        return Decimal('0.00')
    
    def save(self, *args, **kwargs):
        """
        Generar folio VM-YYYY-XXXX si es nuevo.
        Activar genera_comision automáticamente si es un paquete premium/oro/plata.
        """
        # Generar folio si es nuevo
        if not self.folio_venta:
            año_actual = timezone.now().year
            
            ultima_venta = VentaMostrador.objects.filter(
                folio_venta__startswith=f'VM-{año_actual}'
            ).order_by('-folio_venta').first()
            
            if ultima_venta:
                try:
                    ultimo_numero = int(ultima_venta.folio_venta.split('-')[-1])
                    siguiente_numero = ultimo_numero + 1
                except (ValueError, IndexError):
                    siguiente_numero = VentaMostrador.objects.filter(
                        folio_venta__startswith=f'VM-{año_actual}'
                    ).count() + 1
            else:
                siguiente_numero = 1
            
            self.folio_venta = f"VM-{año_actual}-{siguiente_numero:04d}"
        
        # Activar comisión automáticamente si es paquete premium/oro/plata
        if self.paquete in ['premium', 'oro', 'plata']:
            self.genera_comision = True
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.folio_venta} - {self.orden.numero_orden_interno} (${self.total_venta})"
    
    class Meta:
        verbose_name = "Venta Mostrador"
        verbose_name_plural = "Ventas Mostrador"


# ============================================================================
# MODELO 7.5: PIEZA VENTA MOSTRADOR (Simplificado)
# ============================================================================

class PiezaVentaMostrador(models.Model):
    """
    Piezas vendidas directamente en mostrador sin diagnóstico previo.
    Versión simplificada sin tracking de instalación.
    
    Este modelo registra piezas individuales vendidas además de los paquetes,
    como memorias RAM, discos duros, cables, accesorios, etc.
    
    Nota: Los paquetes (premium/oro/plata) NO se desglosan aquí, se manejan
    como un concepto único en VentaMostrador.paquete
    """
    
    # RELACIÓN CON VENTA MOSTRADOR
    venta_mostrador = models.ForeignKey(
        VentaMostrador,
        on_delete=models.CASCADE,
        related_name='piezas_vendidas',
        help_text="Venta mostrador a la que pertenece esta pieza"
    )
    
    # IDENTIFICACIÓN DE LA PIEZA
    # Puede ser del catálogo ScoreCard o descripción libre
    componente = models.ForeignKey(
        ComponenteEquipo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Componente del catálogo ScoreCard (opcional)"
    )
    descripcion_pieza = models.CharField(
        max_length=200,
        help_text="Descripción de la pieza (ej: RAM 8GB DDR4 Kingston, Cable HDMI 2m)"
    )
    
    # CANTIDADES Y PRECIOS
    cantidad = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Cantidad vendida"
    )
    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Precio unitario de venta (IVA incluido)"
    )
    
    # CONTROL Y NOTAS
    fecha_venta = models.DateTimeField(
        default=timezone.now,
        help_text="Fecha de venta de la pieza"
    )
    notas = models.TextField(
        blank=True,
        help_text="Notas u observaciones sobre la pieza vendida"
    )
    
    @property
    def subtotal(self):
        """Calcula el subtotal de esta pieza (cantidad × precio unitario)"""
        return self.cantidad * self.precio_unitario
    
    def __str__(self):
        return f"{self.descripcion_pieza} x{self.cantidad} - ${self.subtotal}"
    
    class Meta:
        verbose_name = "Pieza Venta Mostrador"
        verbose_name_plural = "Piezas Venta Mostrador"
        ordering = ['-fecha_venta']
        indexes = [
            models.Index(fields=['-fecha_venta']),
            models.Index(fields=['venta_mostrador']),
        ]


# ============================================================================
# MODELO 8: IMAGEN DE ORDEN
# ============================================================================

class ImagenOrden(models.Model):
    """
    Imágenes asociadas a una orden (ingreso, egreso, diagnóstico, etc.).
    Permite múltiples imágenes por orden.
    """
    
    # RELACIÓN CON ORDEN
    orden = models.ForeignKey(
        OrdenServicio,
        on_delete=models.CASCADE,
        related_name='imagenes',
        help_text="Orden a la que pertenece esta imagen"
    )
    
    # TIPO DE IMAGEN
    tipo = models.CharField(
        max_length=15,
        choices=TIPO_IMAGEN_CHOICES,
        help_text="Tipo de imagen (ingreso, egreso, diagnóstico, etc.)"
    )
    
    # IMAGEN Y DESCRIPCIÓN
    imagen = models.ImageField(
        upload_to='servicio_tecnico/imagenes/%Y/%m/',
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'gif'])],
        help_text="Archivo de imagen comprimida para galería (JPG, PNG, GIF)"
    )
    imagen_original = models.ImageField(
        upload_to='servicio_tecnico/imagenes_originales/%Y/%m/',
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'gif'])],
        null=True,
        blank=True,
        help_text="Archivo de imagen original sin comprimir (alta resolución)"
    )
    descripcion = models.CharField(
        max_length=200,
        blank=True,
        help_text="Descripción breve de la imagen"
    )
    
    # METADATOS
    fecha_subida = models.DateTimeField(
        auto_now_add=True,
        help_text="Fecha en que se subió la imagen"
    )
    subido_por = models.ForeignKey(
        Empleado,
        on_delete=models.PROTECT,
        related_name='imagenes_subidas_servicio',
        help_text="Empleado que subió la imagen"
    )
    
    @property
    def nombre_archivo(self):
        """Retorna solo el nombre del archivo"""
        import os
        return os.path.basename(self.imagen.name)
    
    def save(self, *args, **kwargs):
        """Registrar en historial al subir imagen"""
        es_nueva = self.pk is None
        super().save(*args, **kwargs)
        
        if es_nueva:
            HistorialOrden.objects.create(
                orden=self.orden,
                tipo_evento='imagen',
                comentario=f"Imagen {self.get_tipo_display()} subida: {self.descripcion or self.nombre_archivo}",
                usuario=self.subido_por,
                es_sistema=True
            )
    
    def __str__(self):
        return f"{self.get_tipo_display()} - {self.orden.numero_orden_interno}"
    
    class Meta:
        ordering = ['fecha_subida']
        verbose_name = "Imagen de Orden"
        verbose_name_plural = "Imágenes de Órdenes"


# ============================================================================
# MODELO 9: HISTORIAL DE ORDEN
# ============================================================================

class HistorialOrden(models.Model):
    """
    Historial completo de eventos y cambios en una orden.
    Permite trazabilidad total del proceso.
    """
    
    # RELACIÓN CON ORDEN
    orden = models.ForeignKey(
        OrdenServicio,
        on_delete=models.CASCADE,
        related_name='historial',
        help_text="Orden a la que pertenece este evento"
    )
    
    # INFORMACIÓN DEL EVENTO
    fecha_evento = models.DateTimeField(
        default=timezone.now,
        help_text="Fecha y hora del evento"
    )
    tipo_evento = models.CharField(
        max_length=20,
        choices=TIPO_EVENTO_CHOICES,
        help_text="Tipo de evento registrado"
    )
    
    # CAMBIOS DE ESTADO
    estado_anterior = models.CharField(
        max_length=20,
        blank=True,
        help_text="Estado anterior (si aplica)"
    )
    estado_nuevo = models.CharField(
        max_length=20,
        blank=True,
        help_text="Estado nuevo (si aplica)"
    )
    
    # CAMBIOS DE TÉCNICO
    tecnico_anterior = models.ForeignKey(
        Empleado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='historial_tecnico_anterior',
        help_text="Técnico anterior (si aplica)"
    )
    tecnico_nuevo = models.ForeignKey(
        Empleado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='historial_tecnico_nuevo',
        help_text="Técnico nuevo (si aplica)"
    )
    
    # DESCRIPCIÓN Y USUARIO
    comentario = models.TextField(
        help_text="Descripción detallada del evento o comentario"
    )
    usuario = models.ForeignKey(
        Empleado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='historial_creado',
        help_text="Usuario que realizó la acción (null si es del sistema)"
    )
    es_sistema = models.BooleanField(
        default=False,
        help_text="¿Es un evento generado automáticamente por el sistema?"
    )
    
    def __str__(self):
        return f"{self.orden.numero_orden_interno} - {self.get_tipo_evento_display()} - {self.fecha_evento.strftime('%d/%m/%Y %H:%M')}"
    
    class Meta:
        ordering = ['-fecha_evento']
        verbose_name = "Evento de Historial"
        verbose_name_plural = "Historial de Órdenes"
        indexes = [
            models.Index(fields=['-fecha_evento']),
            models.Index(fields=['orden', '-fecha_evento']),
        ]


