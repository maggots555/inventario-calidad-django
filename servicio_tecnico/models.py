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
    MARCAS_EQUIPOS_CHOICES,  # Agregar constante de marcas
    GAMA_EQUIPO_CHOICES,
    ESTADO_ORDEN_CHOICES,
    PAQUETES_CHOICES,
    TIPO_IMAGEN_CHOICES,
    TIPO_EVENTO_CHOICES,
    MOTIVO_RECHAZO_COTIZACION,
    ESTADO_PIEZA_CHOICES,
    MOTIVO_RHITSO_CHOICES,
    obtener_precio_paquete,
    OWNER_RHITSO_CHOICES,
    COMPLEJIDAD_CHOICES,
    GRAVEDAD_INCIDENCIA_CHOICES,
    ESTADO_INCIDENCIA_CHOICES,
    IMPACTO_CLIENTE_CHOICES,
    PRIORIDAD_CHOICES,
    TIPO_CONFIG_CHOICES,
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
    
    # RHITSO - Campos adicionales del módulo de seguimiento especializado
    estado_rhitso = models.CharField(
        max_length=100,
        blank=True,
        help_text="Estado actual en el proceso RHITSO"
    )
    fecha_envio_rhitso = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha de envío del equipo a RHITSO"
    )
    fecha_recepcion_rhitso = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha de recepción del equipo desde RHITSO"
    )
    tecnico_diagnostico = models.ForeignKey(
        Empleado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='diagnosticos_realizados',
        help_text="Técnico que realizó el diagnóstico SIC"
    )
    fecha_diagnostico_sic = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha del diagnóstico realizado en SIC"
    )
    complejidad_estimada = models.CharField(
        max_length=10,
        choices=COMPLEJIDAD_CHOICES,
        default='MEDIA',
        blank=True,
        help_text="Complejidad estimada de la reparación"
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
        
        NOTA: Las validaciones de fecha se hacen con ValidationError simple
        (sin diccionario de campos) para evitar errores cuando se usan
        formularios que no incluyen esos campos.
        """
        from django.core.exceptions import ValidationError
        
        # Validación básica: Estados finales requieren fechas
        # Usamos ValidationError simple (mensaje de texto) en lugar de diccionario
        # para evitar errores "has no field named" en formularios parciales
        if self.estado == 'entregado' and not self.fecha_entrega:
            raise ValidationError(
                'Una orden con estado "entregado" debe tener fecha de entrega.'
            )
        
        if self.estado == 'finalizado' and not self.fecha_finalizacion:
            raise ValidationError(
                'Una orden con estado "finalizado" debe tener fecha de finalización.'
            )
    
    @property
    def dias_en_servicio(self):
        """Calcula los días que lleva la orden en el sistema"""
        if self.fecha_entrega:
            return (self.fecha_entrega.date() - self.fecha_ingreso.date()).days
        return (timezone.now().date() - self.fecha_ingreso.date()).days
    
    @property
    def dias_habiles_en_servicio(self):
        """
        Calcula los días HÁBILES que lleva la orden en el sistema.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        ================================
        Esta propiedad calcula solo días laborables (lunes a viernes),
        excluyendo fines de semana. Es más realista para medir tiempos
        de servicio porque los técnicos no trabajan sábados ni domingos.
        
        ¿Por qué usar días hábiles?
        - Refleja el tiempo real de trabajo
        - Métricas más precisas de rendimiento
        - Permite comparar órdenes de forma justa
        
        Reutiliza la función calcular_dias_habiles() del módulo utils_rhitso.
        
        Returns:
            int: Número de días hábiles desde ingreso hasta entrega o hasta hoy
        
        Ejemplo:
            orden.fecha_ingreso = 2025-01-01 (miércoles)
            orden.fecha_entrega = 2025-01-08 (miércoles siguiente)
            dias_naturales = 7 días
            dias_habiles = 5 días (excluye sábado 4 y domingo 5)
        """
        from .utils_rhitso import calcular_dias_habiles
        
        if self.fecha_entrega:
            # Si ya fue entregada, calcular desde ingreso hasta entrega
            return calcular_dias_habiles(self.fecha_ingreso, self.fecha_entrega)
        else:
            # Si aún está en proceso, calcular desde ingreso hasta hoy
            return calcular_dias_habiles(self.fecha_ingreso)
    
    @property
    def esta_retrasada(self):
        """Determina si la orden está retrasada (más de 15 días sin entregar)"""
        if self.estado != 'entregado' and self.dias_en_servicio > 15:
            return True
        return False
    
    @property
    def dias_en_rhitso(self):
        """
        Calcula los días que el equipo ha estado en RHITSO.
        
        Returns:
            int: Días desde fecha_envio_rhitso hasta fecha_recepcion_rhitso o hasta ahora
        """
        if not self.fecha_envio_rhitso:
            return 0
        
        if self.fecha_recepcion_rhitso:
            delta = self.fecha_recepcion_rhitso - self.fecha_envio_rhitso
        else:
            delta = timezone.now() - self.fecha_envio_rhitso
        
        return delta.days
    
    @property
    def dias_sin_actualizacion_estado(self):
        """
        Calcula los días HÁBILES que han pasado desde la última actualización del estado.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        ================================
        Esta propiedad es crucial para detectar órdenes "estancadas" que no han
        tenido avances. Usa días hábiles (lunes a viernes) porque el trabajo
        solo se realiza en días laborables.
        
        ¿Cómo funciona?
        1. Busca el último evento de cambio de estado en el historial
        2. Si lo encuentra, calcula días hábiles desde esa fecha hasta hoy
        3. Si no hay historial de cambios, usa la fecha de ingreso de la orden
        
        ¿Por qué es importante?
        - Identifica órdenes sin progreso
        - Permite alertas visuales en el dashboard
        - Ayuda a priorizar el seguimiento
        
        Returns:
            int: Número de días hábiles sin actualización de estado (0 o más)
        
        Ejemplos:
            # Orden creada hoy → 0 días
            # Orden cambiada de estado hace 3 días hábiles → 3 días
            # Orden sin cambios hace 2 semanas (10 días hábiles) → 10 días
        
        Colores sugeridos para visualización:
            0-2 días: Verde (reciente)
            3-5 días: Amarillo (requiere atención)
            6+ días: Rojo (urgente)
        """
        from .utils_rhitso import calcular_dias_en_estatus
        
        # Buscar el último cambio de estado en el historial
        ultimo_cambio = self.historial.filter(
            tipo_evento='cambio_estado'
        ).order_by('-fecha_evento').first()
        
        if ultimo_cambio:
            # Calcular días hábiles desde el último cambio de estado
            return calcular_dias_en_estatus(ultimo_cambio.fecha_evento)
        else:
            # Si no hay cambios de estado registrados, usar fecha de ingreso
            # (esto sucede con órdenes muy antiguas o recién creadas)
            return calcular_dias_en_estatus(self.fecha_ingreso)
    
    @property
    def color_dias_sin_actualizacion(self):
        """
        Retorna el color CSS de Bootstrap según los días sin actualización.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        ================================
        Esta propiedad implementa un sistema de "semáforo" visual para
        identificar rápidamente qué órdenes necesitan atención.
        
        Rangos establecidos:
            0-2 días: 'success' (verde) - Actualización reciente
            3-5 días: 'warning' (amarillo) - Requiere atención
            6+ días: 'danger' (rojo) - Urgente, sin avances
        
        Returns:
            str: Clase CSS de Bootstrap ('success', 'warning', 'danger')
        
        Uso en templates:
            <span class="badge bg-{{ orden.color_dias_sin_actualizacion }}">
                {{ orden.dias_sin_actualizacion_estado }} días
            </span>
        """
        dias = self.dias_sin_actualizacion_estado
        
        if dias <= 2:
            return 'success'    # Verde - Reciente
        elif dias <= 5:
            return 'warning'    # Amarillo - Atención
        else:
            return 'danger'     # Rojo - Urgente
    
    # ========================================================================
    # PROPERTIES ADICIONALES PARA MÓDULO RHITSO (Fase 2)
    # ========================================================================
    
    @property
    def ultimo_seguimiento_rhitso(self):
        """
        Retorna el último (más reciente) registro de seguimiento RHITSO.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        ================================
        Una @property en Python es como un atributo calculado. Puedes accederlo
        como si fuera un campo normal (orden.ultimo_seguimiento_rhitso) pero
        en realidad ejecuta código para calcularlo.
        
        ¿Qué hace?
            Busca en la tabla SeguimientoRHITSO el registro más reciente para
            esta orden (ordenando por fecha_actualizacion descendente y tomando
            el primero).
        
        Returns:
            SeguimientoRHITSO o None: El último seguimiento o None si no hay ninguno
        
        Ejemplo de uso:
            orden = OrdenServicio.objects.get(pk=1)
            ultimo = orden.ultimo_seguimiento_rhitso
            if ultimo:
                print(f"Estado actual: {ultimo.estado.estado}")
        """
        return self.seguimientos_rhitso.order_by('-fecha_actualizacion').first()
    
    @property
    def incidencias_abiertas_count(self):
        """
        Cuenta cuántas incidencias RHITSO están abiertas (no resueltas).
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        ================================
        Esta property cuenta incidencias que NO están en estado RESUELTA o CERRADA.
        
        Estados de incidencias:
            - ABIERTA: Acaba de reportarse
            - EN_REVISION: Se está investigando
            - RESUELTA: Ya se solucionó
            - CERRADA: Cerrada definitivamente
        
        ¿Por qué es útil?
            Para mostrar en el panel principal cuántos problemas activos hay,
            sin tener que hacer la consulta manualmente cada vez.
        
        Returns:
            int: Número de incidencias abiertas
        
        Ejemplo de uso:
            orden = OrdenServicio.objects.get(pk=1)
            if orden.incidencias_abiertas_count > 0:
                print(f"¡Atención! Hay {orden.incidencias_abiertas_count} problemas activos")
        """
        return self.incidencias_rhitso.exclude(
            estado__in=['RESUELTA', 'CERRADA']
        ).count()
    
    @property
    def incidencias_criticas_count(self):
        """
        Cuenta cuántas incidencias CRÍTICAS abiertas hay.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        ================================
        Esta property cuenta incidencias que cumplen DOS condiciones:
        1. Su tipo_incidencia tiene gravedad CRITICA
        2. NO están resueltas o cerradas
        
        ¿Por qué es útil?
            Las incidencias críticas requieren atención inmediata. Esta property
            te permite identificar rápidamente si hay problemas graves pendientes.
        
        La consulta:
            - exclude(): Excluye registros que cumplan la condición
            - tipo_incidencia__gravedad: Accede al campo 'gravedad' de la 
              ForeignKey tipo_incidencia (esto se llama "lookup" en Django)
        
        Returns:
            int: Número de incidencias críticas abiertas
        
        Ejemplo de uso:
            orden = OrdenServicio.objects.get(pk=1)
            if orden.incidencias_criticas_count > 0:
                print("🚨 ¡ALERTA! Hay incidencias críticas sin resolver")
        """
        return self.incidencias_rhitso.filter(
            tipo_incidencia__gravedad='CRITICA'
        ).exclude(
            estado__in=['RESUELTA', 'CERRADA']
        ).count()
    
    def puede_cambiar_estado_rhitso(self, usuario=None):
        """
        Valida si se puede cambiar el estado RHITSO de esta orden.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        ================================
        Este es un MÉTODO (no property) porque necesita recibir un parámetro
        (el usuario que quiere hacer el cambio).
        
        Métodos vs Properties:
            - Property: orden.dias_en_rhitso (sin paréntesis)
            - Método: orden.puede_cambiar_estado_rhitso(usuario) (con paréntesis)
        
        ¿Qué validaciones hace?
            1. La orden debe ser candidata a RHITSO
            2. No debe estar en estado 'entregado' o 'cancelado'
            3. (Futuro) Puede agregar validaciones de permisos del usuario
        
        Args:
            usuario (Empleado, opcional): Usuario que quiere cambiar el estado
        
        Returns:
            tuple: (puede_cambiar: bool, mensaje: str)
                   Si puede: (True, "")
                   Si no puede: (False, "Mensaje explicando por qué")
        
        Ejemplo de uso:
            orden = OrdenServicio.objects.get(pk=1)
            puede, mensaje = orden.puede_cambiar_estado_rhitso(request.user.empleado)
            if not puede:
                messages.error(request, mensaje)
                return redirect('detalle_orden', orden.id)
        """
        # Validación 1: Debe ser candidato RHITSO
        if not self.es_candidato_rhitso:
            return False, "Esta orden no está marcada como candidata a RHITSO"
        
        # Validación 2: Estado de la orden
        if self.estado in ['entregado', 'cancelado']:
            return False, f"No se puede cambiar el estado RHITSO de una orden {self.get_estado_display()}"
        
        # Validación 3: Verificar que haya al menos un estado disponible
        from servicio_tecnico.models import EstadoRHITSO
        estados_disponibles = EstadoRHITSO.objects.filter(activo=True).count()
        if estados_disponibles == 0:
            return False, "No hay estados RHITSO configurados en el sistema"
        
        # Validación 4 (opcional): Permisos del usuario
        # Aquí podrías agregar lógica como:
        # if usuario and not usuario.tiene_permiso('cambiar_estado_rhitso'):
        #     return False, "No tienes permisos para cambiar estados RHITSO"
        
        # Si pasó todas las validaciones
        return True, ""
    
    # Fin de properties RHITSO
    # ========================================================================
    
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
            
            # EXPLICACIÓN PARA PRINCIPIANTES:
            # Usamos la "orden del cliente" (número que el cliente conoce, ej: "OOW-12345")
            # en vez del número interno del sistema (ej: "42"), porque la incidencia de
            # ScoreCard debe reflejar cómo identifica el cliente su propia orden.
            # Si la orden_cliente está vacía (campo opcional), usamos numero_orden_interno
            # como fallback para que el campo nunca quede en blanco.
            numero_para_incidencia = detalle.orden_cliente or self.numero_orden_interno

            incidencia = Incidencia.objects.create(
                tipo_equipo=detalle.tipo_equipo,
                marca=detalle.marca,
                modelo=detalle.modelo,
                numero_serie=detalle.numero_serie,
                numero_orden=numero_para_incidencia,
                sucursal=self.sucursal,
                tecnico_responsable=self.tecnico_asignado_actual,
                inspector_calidad=self.responsable_seguimiento,
                area_detectora='recepcion',
                tipo_incidencia=categoria,
                categoria_fallo='funcional',
                grado_severidad='alto',
                descripcion_incidencia=f"Reingreso de orden {numero_para_incidencia}. Falla: {detalle.falla_principal}",
                es_reincidencia=True,
                orden_servicio=self,
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
        permissions = [
            ("view_dashboard_gerencial", "Puede ver dashboards gerenciales (OOW/FL, Cotizaciones)"),
            ("view_dashboard_seguimiento", "Puede ver dashboard de seguimiento de piezas"),
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
        choices=MARCAS_EQUIPOS_CHOICES,
        help_text="Marca del equipo (selecciona de la lista)"
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
    
    # ✅ NUEVO CAMPO: Email del Cliente (Noviembre 2025)
    # Agregado para facilitar el envío de fotos de ingreso y notificaciones
    email_cliente = models.EmailField(
        max_length=254,
        blank=False,  # Campo OBLIGATORIO
        default='cliente@ejemplo.com',  # Valor temporal para registros existentes
        help_text="Email del cliente para envío de fotos y notificaciones"
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
    # MIS: Mail-In Service — identifica equipos que llegaron por paquetería
    es_mis = models.BooleanField(
        default=False,
        help_text="¿El equipo llegó por paquetería (Mail-In Service / MIS)?"
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
        """
        Calcular gama y normalizar email antes de guardar.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Este método se ejecuta ANTES de guardar en la base de datos.
        - Calcula la gama del equipo si no está definida
        - Normaliza el email a minúsculas para evitar duplicados (email@example.com == EMAIL@example.com)
        - Elimina espacios en blanco del email
        """
        # Calcular gama si no está definida
        if not self.gama:
            self.calcular_gama()
        
        # Normalizar email (lowercase y sin espacios)
        if self.email_cliente:
            self.email_cliente = self.email_cliente.strip().lower()
        
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
    
    # DESCUENTOS Y BENEFICIOS (Octubre 2025)
    descontar_mano_obra = models.BooleanField(
        default=False,
        help_text="¿Se descuenta la mano de obra como beneficio por aceptar la cotización?"
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
    def costo_mano_obra_aplicado(self):
        """
        Calcula el costo de mano de obra que realmente se cobra.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        - Si descontar_mano_obra = True y el cliente aceptó → retorna 0.00 (gratis)
        - Si descontar_mano_obra = False o cliente rechazó → retorna el costo completo
        
        Esto permite ofrecer el diagnóstico gratis como incentivo al aceptar.
        """
        if self.descontar_mano_obra and self.usuario_acepto:
            return Decimal('0.00')
        return self.costo_mano_obra
    
    @property
    def monto_descuento_mano_obra(self):
        """
        Calcula el monto descontado de la mano de obra.
        
        EXPLICACIÓN:
        - Si se aplicó descuento → retorna el valor original (lo que se ahorró)
        - Si no → retorna 0.00
        
        Útil para mostrar al cliente cuánto se ahorró.
        """
        if self.descontar_mano_obra and self.usuario_acepto:
            return self.costo_mano_obra
        return Decimal('0.00')
    
    @property
    def costo_total_final(self):
        """
        Calcula el costo total FINAL que pagará el cliente.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Esta es la propiedad más importante para facturación.
        - Suma las piezas aceptadas
        - Suma la mano de obra (aplicando descuento si corresponde)
        
        Ejemplos:
        - Piezas: $500, Mano obra: $100, Sin descuento → $600
        - Piezas: $500, Mano obra: $100, CON descuento → $500 (ahorro de $100)
        - Solo mano obra: $100, CON descuento → $0 (todo gratis)
        """
        return self.costo_piezas_aceptadas + self.costo_mano_obra_aplicado
    
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
    
    # PROVEEDOR SELECCIONADO (Noviembre 2025)
    # ========================================================================
    # Campo agregado para permitir seleccionar el proveedor al momento de
    # cotizar cada pieza. Esto facilita la creación automática de seguimientos
    # cuando el cliente acepta la cotización.
    # 
    # BENEFICIOS:
    # - El técnico elige el proveedor mientras cotiza (no después)
    # - Al aceptar, se crea SeguimientoPieza automáticamente
    # - Reduce pasos manuales y errores
    # - Permite comparar precios entre proveedores en cotizaciones
    proveedor = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Proveedor con el cual se cotizó esta pieza (opcional)"
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
        """
        Representación en texto de la pieza cotizada.
        Incluye el proveedor si está especificado.
        """
        base = f"{self.componente.nombre} × {self.cantidad} - ${self.costo_total}"
        if self.proveedor:
            return f"{base} ({self.proveedor})"
        return base
    
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
    costo_paquete = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Costo del paquete de servicio (editable)"
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
    
    incluye_respaldo = models.BooleanField(
        default=False,
        help_text="¿Incluye respaldo de información del cliente?"
    )
    costo_respaldo = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Costo del servicio de respaldo de información"
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
    def total_venta(self):
        """
        Calcula el total de la venta sumando todos los conceptos:
        - Paquete (premium/oro/plata)
        - Servicios adicionales (cambio pieza, limpieza, kit, reinstalación, respaldo)
        - Piezas vendidas individualmente
        """
        total = self.costo_paquete
        total += self.costo_cambio_pieza
        total += self.costo_limpieza
        total += self.costo_kit
        total += self.costo_reinstalacion
        total += self.costo_respaldo
        
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
# FUNCIONES UPLOAD_TO PARA IMÁGENES (Estructura por Orden)
# ============================================================================

def imagen_upload_path(instance, filename):
    """
    Genera la ruta de almacenamiento para imágenes comprimidas.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta función determina dónde se guardará la imagen cuando se suba.
    En lugar de organizarlas por mes (2025/11/), las organiza por orden_cliente.
    
    Estructura resultante:
    - servicio_tecnico/imagenes/OS-001-2025/ingreso_123456.jpg
    - servicio_tecnico/imagenes/OS-002-2025/diagnostico_789012.jpg
    
    Ventajas:
    - Todas las imágenes de un equipo en una carpeta
    - Fácil localizar evidencias por orden
    - Simplifica respaldos por equipo
    
    Args:
        instance: Instancia de ImagenOrden que se está guardando
        filename: Nombre del archivo original
        
    Returns:
        str: Ruta completa donde se guardará el archivo
        
    Ejemplo:
        Para orden con orden_cliente='OS-001-2025' y filename='foto.jpg'
        Retorna: 'servicio_tecnico/imagenes/OS-001-2025/foto.jpg'
    
    NOTA IMPORTANTE:
    orden_cliente está en DetalleEquipo, no en OrdenServicio.
    La relación es: ImagenOrden.orden (OrdenServicio) → detalle_equipo → orden_cliente
    """
    # Acceder a orden_cliente a través de la relación OneToOne con DetalleEquipo
    orden_cliente = instance.orden.detalle_equipo.orden_cliente
    
    # Si orden_cliente está vacío, usar numero_orden_interno como fallback
    if not orden_cliente or orden_cliente.strip() == '':
        orden_cliente = instance.orden.numero_orden_interno
    
    return f'servicio_tecnico/imagenes/{orden_cliente}/{filename}'


def imagen_original_upload_path(instance, filename):
    """
    Genera la ruta de almacenamiento para imágenes originales (sin comprimir).
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Similar a imagen_upload_path, pero para las versiones originales de alta calidad.
    Las imágenes originales se usan para descargas y archivos de alta resolución.
    
    Estructura resultante:
    - servicio_tecnico/imagenes_originales/OS-001-2025/ingreso_123456_original.jpg
    - servicio_tecnico/imagenes_originales/OS-002-2025/diagnostico_789012_original.jpg
    
    Args:
        instance: Instancia de ImagenOrden que se está guardando
        filename: Nombre del archivo original
        
    Returns:
        str: Ruta completa donde se guardará el archivo original
        
    Ejemplo:
        Para orden con orden_cliente='OS-001-2025' y filename='foto_original.jpg'
        Retorna: 'servicio_tecnico/imagenes_originales/OS-001-2025/foto_original.jpg'
    
    NOTA IMPORTANTE:
    orden_cliente está en DetalleEquipo, no en OrdenServicio.
    La relación es: ImagenOrden.orden (OrdenServicio) → detalle_equipo → orden_cliente
    """
    # Acceder a orden_cliente a través de la relación OneToOne con DetalleEquipo
    orden_cliente = instance.orden.detalle_equipo.orden_cliente
    
    # Si orden_cliente está vacío, usar numero_orden_interno como fallback
    if not orden_cliente or orden_cliente.strip() == '':
        orden_cliente = instance.orden.numero_orden_interno
    
    return f'servicio_tecnico/imagenes_originales/{orden_cliente}/{filename}'


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
    # NOTA: Cambiado de estructura por mes (%Y/%m/) a estructura por orden_cliente
    # Imágenes nuevas se guardarán en: servicio_tecnico/imagenes/{orden_cliente}/
    # Imágenes antiguas permanecen en su ubicación original y siguen funcionando
    imagen = models.ImageField(
        upload_to=imagen_upload_path,  # ← Función que genera ruta por orden
        max_length=255,  # Límite ampliado para soportar rutas largas
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'gif'])],
        help_text="Archivo de imagen comprimida para galería (JPG, PNG, GIF)"
    )
    imagen_original = models.ImageField(
        upload_to=imagen_original_upload_path,  # ← Función que genera ruta por orden
        max_length=255,  # Límite ampliado para soportar rutas largas
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
        max_length=30,
        blank=True,
        help_text="Estado anterior (si aplica)"
    )
    estado_nuevo = models.CharField(
        max_length=30,
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


# ============================================================================
# MÓDULO RHITSO - SISTEMA DE SEGUIMIENTO ESPECIALIZADO
# ============================================================================

# ============================================================================
# MODELO 11: ESTADO RHITSO (Catálogo de Estados del Proceso)
# ============================================================================

class EstadoRHITSO(models.Model):
    """
    Catálogo de estados del proceso RHITSO con responsables asignados.
    
    Define los diferentes estados por los que puede pasar un equipo durante
    el proceso de reparación especializada RHITSO, incluyendo el responsable
    de cada estado (SIC, RHITSO, Cliente, Compras).
    
    Ejemplo:
        - "EQUIPO EN RHITSO" → Owner: RHITSO
        - "EN ESPERA DE PIEZA POR SIC" → Owner: SIC
        - "CLIENTE ACEPTA COTIZACIÓN" → Owner: CLIENTE
    """
    estado = models.CharField(
        max_length=100,
        unique=True,
        help_text="Nombre del estado (ej: 'EN DIAGNOSTICO', 'ESPERANDO PIEZAS')"
    )
    owner = models.CharField(
        max_length=20,
        choices=OWNER_RHITSO_CHOICES,
        help_text="Responsable del estado actual"
    )
    descripcion = models.TextField(
        blank=True,
        help_text="Descripción detallada del estado"
    )
    color = models.CharField(
        max_length=20,
        default='secondary',
        help_text="Color para badges Bootstrap: info, warning, success, danger, primary, secondary, dark"
    )
    orden = models.IntegerField(
        default=0,
        help_text="Orden de aparición (1-32)"
    )
    activo = models.BooleanField(
        default=True,
        help_text="¿Estado activo y disponible para usar?"
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        help_text="Fecha de creación del registro"
    )
    
    def __str__(self):
        return self.estado
    
    @classmethod
    def obtener_primer_estado(cls):
        """
        Retorna el estado con menor orden (el primero del flujo).
        
        Returns:
            EstadoRHITSO: Primer estado del flujo RHITSO o None si no hay estados
        """
        return cls.objects.filter(activo=True).order_by('orden').first()
    
    def get_badge_class(self):
        """
        Retorna la clase CSS de Bootstrap según el owner del estado.
        
        Returns:
            str: Clase CSS para badge (ej: 'badge bg-info')
        """
        badge_map = {
            'SIC': 'badge bg-info',
            'RHITSO': 'badge bg-primary',
            'CLIENTE': 'badge bg-warning text-dark',
            'COMPRAS': 'badge bg-secondary',
            'CERRADO': 'badge bg-dark',
        }
        return badge_map.get(self.owner, 'badge bg-secondary')
    
    class Meta:
        ordering = ['orden']
        verbose_name = "Estado RHITSO"
        verbose_name_plural = "Estados RHITSO"


# ============================================================================
# MODELO 12: CATEGORÍA DE DIAGNÓSTICO
# ============================================================================

class CategoriaDiagnostico(models.Model):
    """
    Categorías técnicas de problemas que típicamente requieren RHITSO.
    
    Define tipos de fallas o problemas que necesitan reparación especializada,
    con información de complejidad y tiempo estimado.
    
    Ejemplos:
        - Reballing de GPU
        - Cortocircuito en placa madre
        - Daño por líquidos con corrosión
    """
    nombre = models.CharField(
        max_length=100,
        unique=True,
        help_text="Nombre de la categoría (ej: 'Reballing', 'Soldadura SMD')"
    )
    descripcion = models.TextField(
        blank=True,
        help_text="Descripción técnica de la categoría"
    )
    requiere_rhitso = models.BooleanField(
        default=True,
        help_text="¿Requiere envío a RHITSO?"
    )
    tiempo_estimado_dias = models.IntegerField(
        default=7,
        validators=[MinValueValidator(1)],
        help_text="Tiempo estimado de reparación en días"
    )
    complejidad_tipica = models.CharField(
        max_length=10,
        choices=COMPLEJIDAD_CHOICES,
        default='MEDIA',
        help_text="Complejidad típica de esta categoría"
    )
    activo = models.BooleanField(
        default=True,
        help_text="¿Categoría activa?"
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True
    )
    
    def __str__(self):
        return self.nombre
    
    class Meta:
        ordering = ['nombre']
        verbose_name = "Categoría de Diagnóstico"
        verbose_name_plural = "Categorías de Diagnóstico"


# ============================================================================
# MODELO 13: TIPO DE INCIDENCIA RHITSO
# ============================================================================

class TipoIncidenciaRHITSO(models.Model):
    """
    Catálogo de tipos de incidencias que pueden ocurrir con RHITSO.
    
    Define los tipos de problemas o incidencias que se pueden registrar
    durante el proceso de reparación externa.
    
    Ejemplos:
        - Daño adicional al equipo
        - Retraso en la entrega
        - Falta de comunicación
        - Pieza incorrecta recibida
    """
    nombre = models.CharField(
        max_length=100,
        unique=True,
        help_text="Nombre del tipo de incidencia"
    )
    descripcion = models.TextField(
        blank=True,
        help_text="Descripción del tipo de incidencia"
    )
    gravedad = models.CharField(
        max_length=10,
        choices=GRAVEDAD_INCIDENCIA_CHOICES,
        default='MEDIA',
        help_text="Gravedad típica de este tipo de incidencia"
    )
    color = models.CharField(
        max_length=20,
        default='warning',
        help_text="Color para badges: info, warning, success, danger"
    )
    requiere_accion_inmediata = models.BooleanField(
        default=False,
        help_text="¿Requiere acción inmediata al registrarse?"
    )
    activo = models.BooleanField(
        default=True,
        help_text="¿Tipo de incidencia activo?"
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True
    )
    
    def __str__(self):
        return self.nombre
    
    class Meta:
        ordering = ['nombre']
        verbose_name = "Tipo de Incidencia RHITSO"
        verbose_name_plural = "Tipos de Incidencias RHITSO"


# ============================================================================
# MODELO 14: SEGUIMIENTO RHITSO (Historial de Estados)
# ============================================================================

class SeguimientoRHITSO(models.Model):
    """
    Historial completo de cambios de estado RHITSO de una orden.
    
    Registra cada cambio de estado por el que pasa una orden durante
    el proceso RHITSO, incluyendo observaciones, tiempo en estado anterior
    y usuario que realizó el cambio.
    
    Este modelo permite reconstruir todo el timeline del proceso RHITSO.
    """
    orden = models.ForeignKey(
        'OrdenServicio',
        on_delete=models.CASCADE,
        related_name='seguimientos_rhitso',
        help_text="Orden de servicio asociada"
    )
    estado = models.ForeignKey(
        EstadoRHITSO,
        on_delete=models.PROTECT,
        help_text="Estado RHITSO al que cambió"
    )
    estado_anterior = models.CharField(
        max_length=100,
        blank=True,
        help_text="Estado anterior (para referencia)"
    )
    observaciones = models.TextField(
        blank=True,
        help_text="Observaciones sobre el cambio de estado"
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now_add=True,
        help_text="Fecha y hora del cambio"
    )
    usuario_actualizacion = models.ForeignKey(
        Empleado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Usuario que realizó el cambio (null si es sistema)"
    )
    tiempo_en_estado_anterior = models.IntegerField(
        null=True,
        blank=True,
        help_text="Días que estuvo en el estado anterior"
    )
    notificado_cliente = models.BooleanField(
        default=False,
        help_text="¿Se notificó al cliente de este cambio?"
    )
    es_cambio_automatico = models.BooleanField(
        default=False,
        help_text="True si el cambio fue generado automáticamente por el sistema (signals), False si fue manual (usuario)"
    )
    
    def __str__(self):
        return f"{self.orden.numero_orden_interno} → {self.estado.estado}"
    
    def calcular_tiempo_en_estado(self):
        """
        Calcula los días que estuvo en este estado.
        
        Returns:
            int: Días desde esta actualización hasta la siguiente o hasta ahora
        """
        siguiente = SeguimientoRHITSO.objects.filter(
            orden=self.orden,
            fecha_actualizacion__gt=self.fecha_actualizacion
        ).order_by('fecha_actualizacion').first()
        
        if siguiente:
            delta = siguiente.fecha_actualizacion - self.fecha_actualizacion
        else:
            delta = timezone.now() - self.fecha_actualizacion
        
        return delta.days
    
    class Meta:
        ordering = ['-fecha_actualizacion']
        verbose_name = "Seguimiento RHITSO"
        verbose_name_plural = "Seguimientos RHITSO"
        indexes = [
            models.Index(fields=['orden', '-fecha_actualizacion']),
            models.Index(fields=['estado']),
            models.Index(fields=['-fecha_actualizacion']),
        ]


# ============================================================================
# MODELO 15: INCIDENCIA RHITSO
# ============================================================================

class IncidenciaRHITSO(models.Model):
    """
    Registro de problemas e incidencias durante el proceso RHITSO.
    
    Permite registrar cualquier problema, retraso o incidencia que ocurra
    durante la reparación externa, con seguimiento de su resolución.
    
    Ejemplos:
        - Daño adicional causado por RHITSO
        - Retraso en la entrega sin justificación
        - Pieza incorrecta instalada
        - Falta de comunicación sobre avances
    """
    orden = models.ForeignKey(
        'OrdenServicio',
        on_delete=models.CASCADE,
        related_name='incidencias_rhitso',
        help_text="Orden de servicio afectada"
    )
    tipo_incidencia = models.ForeignKey(
        TipoIncidenciaRHITSO,
        on_delete=models.PROTECT,
        help_text="Tipo de incidencia"
    )
    titulo = models.CharField(
        max_length=255,
        help_text="Título breve de la incidencia"
    )
    descripcion_detallada = models.TextField(
        help_text="Descripción completa del problema"
    )
    fecha_ocurrencia = models.DateTimeField(
        default=timezone.now,
        help_text="Fecha y hora en que ocurrió la incidencia"
    )
    estado = models.CharField(
        max_length=15,
        choices=ESTADO_INCIDENCIA_CHOICES,
        default='ABIERTA',
        help_text="Estado actual de la incidencia"
    )
    impacto_cliente = models.CharField(
        max_length=10,
        choices=IMPACTO_CLIENTE_CHOICES,
        default='BAJO',
        help_text="Impacto de la incidencia hacia el cliente"
    )
    accion_tomada = models.TextField(
        blank=True,
        help_text="Descripción de la acción correctiva tomada"
    )
    resuelto_por = models.ForeignKey(
        Empleado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incidencias_resueltas',
        help_text="Empleado que resolvió la incidencia"
    )
    fecha_resolucion = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha y hora de resolución"
    )
    usuario_registro = models.ForeignKey(
        Empleado,
        on_delete=models.PROTECT,
        related_name='incidencias_registradas',
        help_text="Empleado que registró la incidencia"
    )
    costo_adicional = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Costo adicional generado por la incidencia"
    )
    requiere_seguimiento = models.BooleanField(
        default=True,
        help_text="¿Requiere seguimiento continuo?"
    )
    prioridad = models.CharField(
        max_length=10,
        choices=PRIORIDAD_CHOICES,
        default='MEDIA',
        help_text="Prioridad de atención"
    )
    
    def __str__(self):
        return f"{self.orden.numero_orden_interno} - {self.titulo}"
    
    @property
    def dias_abierta(self):
        """
        Calcula los días que la incidencia ha estado abierta.
        
        Returns:
            int: Días desde la ocurrencia hasta la resolución o hasta ahora
        """
        if self.fecha_resolucion:
            delta = self.fecha_resolucion - self.fecha_ocurrencia
        else:
            delta = timezone.now() - self.fecha_ocurrencia
        return delta.days
    
    @property
    def esta_resuelta(self):
        """
        Verifica si la incidencia está resuelta.
        
        Returns:
            bool: True si el estado es RESUELTA o CERRADA
        """
        return self.estado in ['RESUELTA', 'CERRADA']
    
    def marcar_como_resuelta(self, usuario, accion_tomada):
        """
        Marca la incidencia como resuelta.
        
        Args:
            usuario (Empleado): Usuario que resuelve la incidencia
            accion_tomada (str): Descripción de la acción correctiva
        """
        self.estado = 'RESUELTA'
        self.resuelto_por = usuario
        self.fecha_resolucion = timezone.now()
        self.accion_tomada = accion_tomada
        self.save()
    
    class Meta:
        ordering = ['-fecha_ocurrencia']
        verbose_name = "Incidencia RHITSO"
        verbose_name_plural = "Incidencias RHITSO"
        indexes = [
            models.Index(fields=['orden', '-fecha_ocurrencia']),
            models.Index(fields=['tipo_incidencia']),
            models.Index(fields=['estado']),
        ]


# ============================================================================
# MODELO 16: CONFIGURACIÓN RHITSO
# ============================================================================

class ConfiguracionRHITSO(models.Model):
    """
    Configuración global del módulo RHITSO.
    
    Almacena configuraciones del sistema como:
    - Tiempo máximo sin actualización antes de alerta
    - Email de notificaciones
    - Tiempo estimado default de reparación
    - Configuraciones de notificaciones automáticas
    
    Ejemplo:
        clave='tiempo_maximo_sin_actualizacion', valor='7', tipo='INTEGER'
    """
    clave = models.CharField(
        max_length=100,
        unique=True,
        help_text="Clave de configuración (ej: 'tiempo_maximo_alerta')"
    )
    valor = models.TextField(
        blank=True,
        help_text="Valor de la configuración"
    )
    descripcion = models.TextField(
        blank=True,
        help_text="Descripción de qué controla esta configuración"
    )
    tipo = models.CharField(
        max_length=10,
        choices=TIPO_CONFIG_CHOICES,
        default='STRING',
        help_text="Tipo de dato del valor"
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        help_text="Última actualización"
    )
    
    def __str__(self):
        return f"{self.clave} = {self.valor}"
    
    @classmethod
    def obtener(cls, clave, default=None):
        """
        Obtiene el valor de una configuración.
        
        Args:
            clave (str): Clave de la configuración
            default: Valor por defecto si no existe
        
        Returns:
            str: Valor de la configuración o default
        """
        try:
            config = cls.objects.get(clave=clave)
            return config.valor
        except cls.DoesNotExist:
            return default
    
    class Meta:
        verbose_name = "Configuración RHITSO"
        verbose_name_plural = "Configuraciones RHITSO"


# ============================================================
# MODELO: FeedbackCliente
# Almacena tokens de feedback enviados a clientes.
# Soporta dos tipos:
#   - 'rechazo': Tras rechazar una cotización, se pide al cliente
#                que explique el motivo detallado. Incluye info de piezas.
#   - 'satisfaccion': Encuesta general de satisfacción al finalizar
#                     el servicio (flujo futuro).
# Seguridad:
#   - Token único firmado con django.core.signing.TimestampSigner
#   - Expiración de 7 días
#   - Uso único: una vez enviado el feedback, el token queda consumido
#   - La vista pública NO expone login ni navegación del sistema
# ============================================================

TIPO_FEEDBACK_CHOICES = [
    ('rechazo', 'Rechazo de Cotización'),
    ('satisfaccion', 'Encuesta de Satisfacción'),
]


class FeedbackCliente(models.Model):
    """
    Token de feedback para clientes.
    Permite a clientes externos dar retroalimentación mediante
    un enlace único firmado sin necesidad de autenticación.
    """

    # --- Relación ---
    cotizacion = models.ForeignKey(
        'Cotizacion',
        on_delete=models.CASCADE,
        related_name='feedbacks',
        verbose_name="Cotización",
        help_text="Cotización a la que pertenece este feedback"
    )

    # --- Token de acceso seguro ---
    token = models.CharField(
        max_length=512,
        unique=True,
        db_index=True,
        verbose_name="Token de acceso",
        help_text="Token firmado generado con TimestampSigner. Válido por 7 días."
    )

    # --- Tipo y contexto ---
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_FEEDBACK_CHOICES,
        default='rechazo',
        verbose_name="Tipo de feedback"
    )
    motivo_rechazo_snapshot = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Snapshot del motivo de rechazo",
        help_text="Copia del motivo de rechazo al momento de crear el token"
    )

    # --- Respuesta del cliente (feedback tipo 'rechazo') ---
    comentario_cliente = models.TextField(
        max_length=1000,
        blank=True,
        verbose_name="Comentario del cliente",
        help_text="Explicación libre del cliente sobre por qué rechazó (máx. 1000 chars)"
    )

    # --- Respuesta del cliente (feedback tipo 'satisfaccion') ---
    # Calificaciones estructuradas para métricas (futuro)
    calificacion_general = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Calificación general (1-5 estrellas)"
    )
    calificacion_atencion = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Calificación atención al cliente (1-5 estrellas)"
    )
    calificacion_tiempo = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Calificación tiempo de respuesta (1-5 estrellas)"
    )
    recomienda = models.BooleanField(
        null=True,
        blank=True,
        verbose_name="¿Recomendaría el servicio? (pulgar arriba/abajo)"
    )
    nps = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="NPS: ¿Del 0 al 10, qué tan probable es que nos recomiende?"
    )

    # --- Control de estado ---
    utilizado = models.BooleanField(
        default=False,
        verbose_name="Token utilizado",
        help_text="True cuando el cliente ya envió su feedback"
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación del token"
    )
    fecha_respuesta = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha en que el cliente respondió"
    )

    # --- Trazabilidad ---
    ip_respuesta = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP del cliente al responder"
    )
    enviado_por = models.ForeignKey(
        Empleado,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='feedbacks_enviados',
        verbose_name="Enviado por (empleado)"
    )
    correo_enviado = models.BooleanField(
        default=False,
        verbose_name="¿Correo enviado al cliente?",
        help_text="Se actualiza a True cuando la tarea Celery envía el correo exitosamente"
    )

    class Meta:
        verbose_name = "Feedback de Cliente"
        verbose_name_plural = "Feedbacks de Clientes"
        ordering = ['-fecha_creacion']

    def __str__(self):
        return (
            f"Feedback [{self.get_tipo_display()}] - "
            f"Orden {self.cotizacion.orden.numero_orden_interno} "
            f"({'Respondido' if self.utilizado else 'Pendiente'})"
        )

    @property
    def esta_expirado(self):
        """Token válido por 7 días desde su creación."""
        from datetime import timedelta
        return timezone.now() > self.fecha_creacion + timedelta(days=7)

    @property
    def es_valido(self):
        """True si el token no ha sido usado y no ha expirado."""
        return not self.utilizado and not self.esta_expirado

    @property
    def dias_restantes(self):
        """Días que quedan antes de que expire el token."""
        from datetime import timedelta
        expiracion = self.fecha_creacion + timedelta(days=7)
        delta = expiracion - timezone.now()
        return max(0, delta.days)


