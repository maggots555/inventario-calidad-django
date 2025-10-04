"""
Modelos para el sistema de Score Card de Calidad
Sistema para rastrear y analizar incidencias en el Centro de Servicio
"""
from django.db import models
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from inventario.models import Sucursal, Empleado
import os


class CategoriaIncidencia(models.Model):
    """
    Categorías de incidencias para clasificación
    Ejemplo: Fallo post-reparación, Defecto no registrado, etc.
    """
    nombre = models.CharField(
        max_length=100,
        unique=True,
        help_text="Nombre de la categoría (ej: Fallo post-reparación)"
    )
    descripcion = models.TextField(
        blank=True,
        help_text="Descripción detallada de esta categoría"
    )
    color = models.CharField(
        max_length=7,
        default="#6c757d",
        help_text="Color en hexadecimal para gráficos (ej: #FF5733)"
    )
    activo = models.BooleanField(
        default=True,
        help_text="Categoría activa para usar en nuevos registros"
    )
    
    # Fechas de control
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.nombre
    
    class Meta:
        ordering = ['nombre']
        verbose_name = "Categoría de Incidencia"
        verbose_name_plural = "Categorías de Incidencias"


class ComponenteEquipo(models.Model):
    """
    Componentes de equipos que pueden presentar fallas
    Ejemplo: Pantalla, Teclado, RAM, Motherboard, etc.
    """
    TIPO_EQUIPO_CHOICES = [
        ('pc', 'PC'),
        ('laptop', 'Laptop'),
        ('aio', 'AIO (All-in-One)'),
        ('todos', 'Todos los tipos'),
    ]
    
    nombre = models.CharField(
        max_length=100,
        help_text="Nombre del componente (ej: Pantalla, Teclado, RAM)"
    )
    tipo_equipo = models.CharField(
        max_length=10,
        choices=TIPO_EQUIPO_CHOICES,
        default='todos',
        help_text="Tipo de equipo donde aplica este componente"
    )
    activo = models.BooleanField(
        default=True,
        help_text="Componente activo para selección"
    )
    
    # Fechas de control
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_equipo_display()})"
    
    class Meta:
        ordering = ['nombre']
        verbose_name = "Componente de Equipo"
        verbose_name_plural = "Componentes de Equipos"
        unique_together = ['nombre', 'tipo_equipo']


class ServicioRealizado(models.Model):
    """
    Catálogo de servicios realizados en el Centro de Servicio
    Permite estandarizar los servicios y facilitar análisis
    """
    nombre = models.CharField(
        max_length=150,
        unique=True,
        help_text="Nombre del servicio (ej: Ingreso del equipo al CIS)"
    )
    descripcion = models.TextField(
        blank=True,
        help_text="Descripción detallada del servicio"
    )
    orden = models.PositiveIntegerField(
        default=0,
        help_text="Orden de aparición en listados (menor primero)"
    )
    activo = models.BooleanField(
        default=True,
        help_text="Servicio activo para selección"
    )
    
    # Fechas de control
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.nombre
    
    class Meta:
        ordering = ['orden', 'nombre']
        verbose_name = "Servicio Realizado"
        verbose_name_plural = "Servicios Realizados"


class Incidencia(models.Model):
    """
    Modelo principal para registrar incidencias de calidad
    Registra fallos detectados en equipos reparados o durante inspección
    """
    
    # Choices para los diferentes campos
    TIPO_EQUIPO_CHOICES = [
        ('pc', 'PC'),
        ('laptop', 'Laptop'),
        ('aio', 'AIO (All-in-One)'),
    ]
    
    AREA_CHOICES = [
        ('tecnico', 'Área Técnica'),
        ('calidad', 'Control de Calidad'),
        ('recepcion', 'Recepción'),
        ('cliente', 'Cliente'),
        ('otra', 'Otra'),
    ]
    
    CATEGORIA_FALLO_CHOICES = [
        ('hardware', 'Hardware'),
        ('software', 'Software'),
        ('cosmetico', 'Cosmético'),
        ('funcional', 'Funcional'),
        ('documentacion', 'Documentación'),
        ('otro', 'Otro'),
    ]
    
    GRADO_SEVERIDAD_CHOICES = [
        ('critico', 'Crítico'),
        ('alto', 'Alto'),
        ('medio', 'Medio'),
        ('bajo', 'Bajo'),
    ]
    
    ESTADO_CHOICES = [
        ('abierta', 'Abierta'),
        ('en_revision', 'En Revisión'),
        ('cerrada', 'Cerrada'),
        ('reincidente', 'Reincidente'),
    ]
    
    # IDENTIFICACIÓN Y FECHAS
    folio = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        help_text="Folio auto-generado (INC-2024-0001)"
    )
    fecha_registro = models.DateTimeField(
        auto_now_add=True,
        help_text="Fecha de registro en el sistema"
    )
    fecha_deteccion = models.DateField(
        default=timezone.now,
        help_text="Fecha en que se detectó la incidencia"
    )
    
    # INFORMACIÓN DEL EQUIPO
    tipo_equipo = models.CharField(
        max_length=10,
        choices=TIPO_EQUIPO_CHOICES,
        help_text="Tipo de equipo"
    )
    marca = models.CharField(
        max_length=50,
        help_text="Marca del equipo (HP, Dell, Lenovo, etc.)"
    )
    modelo = models.CharField(
        max_length=100,
        blank=True,
        help_text="Modelo específico del equipo"
    )
    numero_serie = models.CharField(
        max_length=100,
        help_text="Número de serie del equipo (Service Tag)"
    )
    numero_orden = models.CharField(
        max_length=50,
        blank=True,
        help_text="Número de orden interna del servicio"
    )
    servicio_realizado = models.ForeignKey(
        ServicioRealizado,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='incidencias',
        help_text="Servicio que se realizó al equipo"
    )
    
    # UBICACIÓN Y RESPONSABLES
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.PROTECT,
        related_name='incidencias',
        help_text="Sucursal donde ocurrió la incidencia"
    )
    area_detectora = models.CharField(
        max_length=20,
        choices=AREA_CHOICES,
        help_text="Área que detectó la incidencia"
    )
    tecnico_responsable = models.ForeignKey(
        Empleado,
        on_delete=models.PROTECT,
        related_name='incidencias_tecnico',
        help_text="Técnico responsable del servicio"
    )
    area_tecnico = models.CharField(
        max_length=100,
        blank=True,
        help_text="Área del técnico responsable (auto-completado)"
    )
    inspector_calidad = models.ForeignKey(
        Empleado,
        on_delete=models.PROTECT,
        related_name='incidencias_inspector',
        help_text="Inspector que detectó la incidencia"
    )
    
    # CLASIFICACIÓN DEL FALLO
    tipo_incidencia = models.ForeignKey(
        CategoriaIncidencia,
        on_delete=models.PROTECT,
        related_name='incidencias',
        help_text="Tipo de incidencia"
    )
    categoria_fallo = models.CharField(
        max_length=20,
        choices=CATEGORIA_FALLO_CHOICES,
        help_text="Categoría general del fallo"
    )
    grado_severidad = models.CharField(
        max_length=10,
        choices=GRADO_SEVERIDAD_CHOICES,
        default='medio',
        help_text="Nivel de severidad de la incidencia"
    )
    componente_afectado = models.ForeignKey(
        ComponenteEquipo,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='incidencias',
        help_text="Componente específico con fallo"
    )
    
    # DESCRIPCIÓN Y SEGUIMIENTO
    descripcion_incidencia = models.TextField(
        help_text="Descripción detallada de la incidencia"
    )
    acciones_tomadas = models.TextField(
        blank=True,
        help_text="Acciones correctivas realizadas"
    )
    causa_raiz = models.TextField(
        blank=True,
        help_text="Análisis de causa raíz (opcional)"
    )
    
    # ESTADO Y REINCIDENCIA
    estado = models.CharField(
        max_length=15,
        choices=ESTADO_CHOICES,
        default='abierta',
        help_text="Estado actual de la incidencia"
    )
    es_reincidencia = models.BooleanField(
        default=False,
        help_text="¿Es una reincidencia de una incidencia anterior?"
    )
    incidencia_relacionada = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reincidencias',
        help_text="Incidencia original si es reincidencia"
    )
    
    # ATRIBUIBILIDAD AL TÉCNICO
    es_atribuible = models.BooleanField(
        default=True,
        help_text="¿Esta incidencia es atribuible al técnico responsable?"
    )
    justificacion_no_atribuible = models.TextField(
        blank=True,
        help_text="Justificación de por qué no es atribuible al técnico"
    )
    fecha_marcado_no_atribuible = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha en que se marcó como no atribuible"
    )
    marcado_no_atribuible_por = models.ForeignKey(
        Empleado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incidencias_marcadas_no_atribuibles',
        help_text="Usuario que marcó la incidencia como no atribuible"
    )
    
    # CAMPOS AUTOMÁTICOS (calculados al guardar)
    año = models.IntegerField(
        editable=False,
        help_text="Año de la fecha de detección"
    )
    mes = models.IntegerField(
        editable=False,
        help_text="Mes de la fecha de detección (1-12)"
    )
    semana = models.IntegerField(
        editable=False,
        help_text="Semana del año (1-53)"
    )
    trimestre = models.IntegerField(
        editable=False,
        help_text="Trimestre del año (1-4)"
    )
    
    # Fechas de control
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        help_text="Última actualización del registro"
    )
    fecha_cierre = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha de cierre de la incidencia"
    )
    
    def save(self, *args, **kwargs):
        """
        Sobrescribir save para generar folio y calcular campos automáticos
        """
        # Generar folio si es nuevo registro
        if not self.folio:
            año_actual = timezone.now().year
            # Contar incidencias del año actual
            ultimo_numero = Incidencia.objects.filter(
                folio__startswith=f'INC-{año_actual}'
            ).count() + 1
            self.folio = f"INC-{año_actual}-{ultimo_numero:04d}"
        
        # Calcular campos de fecha automáticos
        fecha = self.fecha_deteccion
        self.año = fecha.year
        self.mes = fecha.month
        self.semana = fecha.isocalendar()[1]  # Número de semana ISO
        self.trimestre = (fecha.month - 1) // 3 + 1
        
        # Si cambia a cerrada, guardar fecha de cierre
        if self.estado == 'cerrada' and not self.fecha_cierre:
            self.fecha_cierre = timezone.now()
        
        super().save(*args, **kwargs)
    
    @property
    def dias_abierta(self):
        """
        Calcula los días que lleva abierta la incidencia
        """
        if self.fecha_cierre:
            return (self.fecha_cierre.date() - self.fecha_deteccion).days
        return (timezone.now().date() - self.fecha_deteccion).days
    
    @property
    def mes_nombre(self):
        """
        Retorna el nombre del mes en español
        """
        meses = [
            'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
        ]
        return meses[self.mes - 1]
    
    @property
    def trimestre_nombre(self):
        """
        Retorna el nombre del trimestre
        """
        return f"Q{self.trimestre} {self.año}"
    
    def __str__(self):
        return f"{self.folio} - {self.tipo_equipo} {self.marca} ({self.get_estado_display()})"
    
    class Meta:
        ordering = ['-fecha_registro']
        verbose_name = "Incidencia"
        verbose_name_plural = "Incidencias"
        indexes = [
            models.Index(fields=['-fecha_registro']),
            models.Index(fields=['folio']),
            models.Index(fields=['numero_serie']),
            models.Index(fields=['tecnico_responsable']),
            models.Index(fields=['año', 'mes']),
        ]


class EvidenciaIncidencia(models.Model):
    """
    Modelo para almacenar imágenes de evidencia de las incidencias
    Permite múltiples imágenes por incidencia
    """
    incidencia = models.ForeignKey(
        Incidencia,
        on_delete=models.CASCADE,
        related_name='evidencias',
        help_text="Incidencia a la que pertenece esta evidencia"
    )
    imagen = models.ImageField(
        upload_to='scorecard/evidencias/%Y/%m/',
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'gif'])],
        help_text="Imagen de evidencia (JPG, PNG, GIF)"
    )
    descripcion = models.CharField(
        max_length=200,
        blank=True,
        help_text="Descripción breve de la evidencia"
    )
    fecha_subida = models.DateTimeField(
        auto_now_add=True,
        help_text="Fecha de subida de la imagen"
    )
    subido_por = models.ForeignKey(
        Empleado,
        on_delete=models.PROTECT,
        related_name='evidencias_subidas',
        help_text="Empleado que subió la evidencia"
    )
    
    @property
    def nombre_archivo(self):
        """
        Retorna solo el nombre del archivo sin la ruta completa
        """
        return os.path.basename(self.imagen.name)
    
    @property
    def tamaño_mb(self):
        """
        Retorna el tamaño del archivo en MB
        """
        if self.imagen:
            return round(self.imagen.size / (1024 * 1024), 2)
        return 0
    
    def __str__(self):
        return f"Evidencia {self.id} - {self.incidencia.folio}"
    
    class Meta:
        ordering = ['fecha_subida']
        verbose_name = "Evidencia"
        verbose_name_plural = "Evidencias"


class NotificacionIncidencia(models.Model):
    """
    Modelo para registrar el historial de notificaciones enviadas por email
    Permite rastrear qué notificaciones se han enviado, a quién y cuándo
    """
    TIPO_NOTIFICACION_CHOICES = [
        ('manual', 'Notificación Manual'),
        ('no_atribuible', 'Marcada como No Atribuible'),
        ('cierre', 'Cierre de Incidencia'),
        ('cierre_no_atribuible', 'Cierre de Incidencia No Atribuible'),
    ]
    
    incidencia = models.ForeignKey(
        Incidencia,
        on_delete=models.CASCADE,
        related_name='notificaciones',
        help_text="Incidencia sobre la que se envió la notificación"
    )
    tipo_notificacion = models.CharField(
        max_length=30,
        choices=TIPO_NOTIFICACION_CHOICES,
        default='manual',
        help_text="Tipo de notificación enviada"
    )
    destinatarios_json = models.TextField(
        default='[]',
        help_text="Lista de destinatarios (JSON con nombres y emails)"
    )
    # Campo legacy para compatibilidad
    destinatarios = models.TextField(
        blank=True,
        default='',
        help_text="Lista de destinatarios (JSON con nombres y emails) - legacy"
    )
    asunto = models.CharField(
        max_length=255,
        help_text="Asunto del email enviado"
    )
    mensaje_adicional = models.TextField(
        blank=True,
        help_text="Mensaje adicional incluido en el email (opcional)"
    )
    fecha_envio = models.DateTimeField(
        auto_now_add=True,
        help_text="Fecha y hora en que se envió la notificación"
    )
    enviado_por = models.CharField(
        max_length=100,
        default='Sistema',
        help_text="Usuario que envió la notificación"
    )
    exitoso = models.BooleanField(
        default=True,
        help_text="Si el envío fue exitoso"
    )
    # Campo renombrado para mayor claridad
    enviado_exitoso = models.BooleanField(
        default=True,
        help_text="Si el envío fue exitoso"
    )
    mensaje_error = models.TextField(
        blank=True,
        help_text="Mensaje de error si el envío falló"
    )
    
    def get_destinatarios_list(self):
        """
        Parsea el JSON de destinatarios y retorna una lista de diccionarios
        """
        import json
        try:
            # Intentar con nuevo campo primero
            if self.destinatarios_json:
                return json.loads(self.destinatarios_json)
            # Fallback a campo legacy
            elif self.destinatarios:
                return json.loads(self.destinatarios)
            return []
        except:
            return []
    
    def __str__(self):
        return f"Notificación {self.incidencia.folio} - {self.get_tipo_notificacion_display()} - {self.fecha_envio.strftime('%d/%m/%Y %H:%M')}"
    
    class Meta:
        ordering = ['-fecha_envio']
        verbose_name = "Notificación de Incidencia"
        verbose_name_plural = "Notificaciones de Incidencias"
