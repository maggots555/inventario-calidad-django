"""
Formularios para la aplicación de Servicio Técnico

EXPLICACIÓN PARA PRINCIPIANTES:
- Este archivo define cómo se ven y comportan los formularios en el navegador
- ModelForm: Django crea automáticamente campos basados en tus modelos
- widgets: Define cómo se ve cada campo en HTML (como cajas de texto, checkboxes, etc.)
- Meta class: Configuración del formulario (qué modelo usa, qué campos incluir)
"""
from django import forms
from django.core.exceptions import ValidationError
from .models import (
    OrdenServicio, 
    DetalleEquipo, 
    ReferenciaGamaEquipo,
    HistorialOrden,
    ImagenOrden,
    Cotizacion,
    PiezaCotizada,
    SeguimientoPieza,
    VentaMostrador,  # ← NUEVO - FASE 3
    PiezaVentaMostrador,  # ← NUEVO - FASE 3
    # RHITSO - FASE 3 del módulo de seguimiento especializado
    EstadoRHITSO,
    TipoIncidenciaRHITSO,
    IncidenciaRHITSO,
)
from inventario.models import Sucursal, Empleado
from scorecard.models import ComponenteEquipo
from config.constants import (
    TIPO_EQUIPO_CHOICES, 
    MARCAS_EQUIPOS_CHOICES,  # Nueva constante para dropdown
    MARCAS_EQUIPOS,  # Lista simple (compatibilidad)
    TIPO_IMAGEN_CHOICES, 
    MOTIVO_RECHAZO_COTIZACION,
    ESTADO_PIEZA_CHOICES,
    # RHITSO - Constantes para módulo de seguimiento especializado
    MOTIVO_RHITSO_CHOICES,
    COMPLEJIDAD_CHOICES,
    IMPACTO_CLIENTE_CHOICES,
    PRIORIDAD_CHOICES,
    # Proveedores - Noviembre 2025
    PROVEEDORES_CHOICES,
)


class NuevaOrdenForm(forms.ModelForm):
    """
    Formulario para crear una nueva orden de servicio técnico.
    
    EXPLICACIÓN:
    Este formulario captura solo la información básica necesaria para iniciar
    una orden de servicio. Los campos más complejos se llenarán después.
    
    CAMPOS INCLUIDOS:
    - Información del equipo: tipo, marca, modelo, número de serie
    - Información de la orden: sucursal
    - Accesorios: tiene_cargador (con campo condicional para número de serie)
    - Opciones especiales: es_reingreso, es_candidato_rhitso
    """
    
    # ========================================================================
    # CAMPOS ADICIONALES DEL DETALLE DEL EQUIPO
    # ========================================================================
    # Estos campos no existen directamente en OrdenServicio, pero los necesitamos
    # para crear el DetalleEquipo relacionado
    
    tipo_equipo = forms.ChoiceField(
        choices=TIPO_EQUIPO_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control form-select',
            'required': True,
        }),
        label="Tipo de Equipo",
        help_text="Selecciona el tipo de equipo que ingresa"
    )
    
    marca = forms.ChoiceField(
        choices=MARCAS_EQUIPOS_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control form-select',
            'required': True,
        }),
        label="Marca del Equipo",
        help_text="Selecciona la marca del equipo (campo obligatorio)"
    )
    
    modelo = forms.CharField(
        max_length=100,
        required=False,  # Este campo es OPCIONAL
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: Inspiron 15, ThinkPad X1',
        }),
        label="Modelo del Equipo",
        help_text="Modelo específico del equipo (opcional)"
    )
    
    numero_serie = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: SN123456789',
            'required': True,
            'style': 'text-transform: uppercase;',  # Convertir a mayúsculas
        }),
        label="Número de Serie",
        help_text="Número de serie o Service Tag del equipo (obligatorio)"
    )
    
    orden_cliente = forms.CharField(
        max_length=50,
        initial='OOW-',  # Valor inicial con el prefijo
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'OOW-',
            'required': True,
        }),
        label="Número de Orden del Cliente",
        help_text="<strong>Campo obligatorio.</strong> El prefijo 'OOW-' aparece por defecto. Puede borrar el texto para escribir otro número de orden, pero <strong>en las órdenes que son OOW- o FL-, siempre es necesario poner el prefijo.</strong>"
    )
    
    # ✅ NUEVO: Email del Cliente (Noviembre 2025)
    email_cliente = forms.EmailField(
        required=False,  # OPCIONAL al crear, obligatorio al editar
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'cliente@ejemplo.com (opcional)',
            'type': 'email',
            'autocomplete': 'email',
        }),
        label='📧 Email del Cliente',
        help_text='Email para enviar fotos del ingreso y notificaciones (opcional, se puede agregar después)'
    )
    
    equipo_enciende = forms.BooleanField(
        required=False,  # BooleanField por defecto es False si no se marca
        initial=True,  # Por defecto marcado como True
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        label="¿El equipo enciende?",
        help_text="Marca si el equipo enciende al momento del ingreso"
    )
    
    # ========================================================================
    # CAMPOS DE ACCESORIOS (con lógica condicional)
    # ========================================================================
    
    tiene_cargador = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'id_tiene_cargador',
            'onchange': 'toggleCargadorFields()',  # JavaScript para mostrar/ocultar
        }),
        label="¿Incluye cargador?",
        help_text="Marca si el equipo trae cargador"
    )
    
    numero_serie_cargador = forms.CharField(
        max_length=100,
        required=False,  # OPCIONAL, solo si tiene cargador
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Número de serie del cargador (opcional)',
            'id': 'id_numero_serie_cargador',
        }),
        label="Número de Serie del Cargador",
        help_text="Solo si el cargador tiene número de serie identificable"
    )
    
    # ========================================================================
    # CAMPOS DE LA ORDEN DE SERVICIO
    # ========================================================================
    
    class Meta:
        """
        EXPLICACIÓN DE Meta:
        Esta clase interna le dice a Django:
        - Qué modelo usar como base (OrdenServicio)
        - Qué campos del modelo incluir en el formulario
        - Cómo debe verse cada campo (widgets con clases de Bootstrap)
        """
        model = OrdenServicio
        fields = [
            'sucursal',
            'es_reingreso',
            'es_candidato_rhitso',
        ]
        
        widgets = {
            'sucursal': forms.Select(attrs={
                'class': 'form-control form-select',
                'required': True,
            }),
            'es_reingreso': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'id_es_reingreso',
            }),
            'es_candidato_rhitso': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'id_es_candidato_rhitso',
            }),
        }
        
        labels = {
            'sucursal': 'Sucursal',
            'es_reingreso': '¿Es un reingreso?',
            'es_candidato_rhitso': '¿Candidato a RHITSO?',
        }
        
        help_texts = {
            'sucursal': 'Sucursal donde se registra la orden',
            'es_reingreso': 'Marca si este equipo ya había sido reparado anteriormente',
            'es_candidato_rhitso': 'Marca si requiere reparación especializada (soldadura, reballing)',
        }
    
    def __init__(self, *args, **kwargs):
        """
        EXPLICACIÓN DE __init__:
        Este método se ejecuta cuando se crea el formulario.
        Aquí podemos personalizar el formulario antes de mostrarlo.
        
        Por ejemplo:
        - Filtrar opciones de sucursales activas
        - Establecer valores iniciales
        - Modificar el comportamiento de campos
        """
        # Obtener el usuario actual si se pasa como argumento
        self.user = kwargs.pop('user', None)
        
        # Llamar al __init__ original (SIEMPRE necesario)
        super().__init__(*args, **kwargs)
        
        # Filtrar solo sucursales activas (el campo es 'activa' no 'activo')
        self.fields['sucursal'].queryset = Sucursal.objects.filter(activa=True)
        
        # Agregar clases CSS adicionales si es necesario
        # (ya están definidas en widgets, pero esto es un ejemplo)
    
    def clean_numero_serie(self):
        """
        EXPLICACIÓN DE clean_numero_serie:
        Este método valida y limpia el campo numero_serie.
        
        Django llama automáticamente a métodos clean_<nombre_campo>
        para validar campos individuales.
        
        Aquí convertimos el número de serie a MAYÚSCULAS para
        mantener consistencia en la base de datos.
        """
        numero_serie = self.cleaned_data.get('numero_serie')
        if numero_serie:
            # Convertir a mayúsculas y eliminar espacios en blanco
            return numero_serie.strip().upper()
        return numero_serie
    
    def clean_numero_serie_cargador(self):
        """
        EXPLICACIÓN:
        Limpia el número de serie del cargador (mayúsculas).
        """
        numero_serie_cargador = self.cleaned_data.get('numero_serie_cargador')
        if numero_serie_cargador:
            return numero_serie_cargador.strip().upper()
        return numero_serie_cargador
    
    def clean_orden_cliente(self):
        """
        EXPLICACIÓN:
        Limpia el número de orden del cliente (mayúsculas y sin espacios).
        """
        orden_cliente = self.cleaned_data.get('orden_cliente')
        if orden_cliente:
            return orden_cliente.strip().upper()
        return orden_cliente
    
    def clean_email_cliente(self):
        """
        EXPLICACIÓN PARA PRINCIPIANTES:
        Normaliza el email del cliente a minúsculas para evitar duplicados.
        
        Por ejemplo:
        - Usuario escribe: Cliente@EJEMPLO.com
        - Se guarda como: cliente@ejemplo.com
        
        Esto asegura que "cliente@ejemplo.com" y "CLIENTE@ejemplo.com" 
        se reconozcan como el mismo email.
        """
        email = self.cleaned_data.get('email_cliente')
        if email:
            return email.strip().lower()
        return email
    
    def clean(self):
        """
        EXPLICACIÓN DE clean():
        Este método valida el formulario completo (todos los campos juntos).
        
        Se ejecuta DESPUÉS de validar campos individuales.
        Aquí podemos validar lógica que involucra múltiples campos.
        
        Por ejemplo:
        - Si tiene_cargador es True pero numero_serie_cargador está vacío,
          NO es error (es opcional)
        """
        cleaned_data = super().clean()
        
        # Validación: Si es reingreso, en el futuro podríamos requerir más datos
        # Por ahora solo guardamos el flag
        
        return cleaned_data
    
    def save(self, commit=True):
        """
        EXPLICACIÓN DE save():
        Este método guarda el formulario en la base de datos.
        
        IMPORTANTE: Como creamos DOS objetos (OrdenServicio Y DetalleEquipo),
        necesitamos sobrescribir este método.
        
        Proceso:
        1. Crear OrdenServicio (con commit=False para no guardar aún)
        2. Asignar responsable y técnico (requeridos por el modelo)
        3. Guardar OrdenServicio (esto genera el número de orden automático)
        4. Crear DetalleEquipo relacionado
        5. Guardar DetalleEquipo
        6. Retornar la orden creada
        """
        # Crear la instancia de OrdenServicio pero NO guardarla aún
        orden = super().save(commit=False)
        
        # ESTABLECER TIPO DE SERVICIO COMO DIAGNÓSTICO
        # EXPLICACIÓN: Marcamos explícitamente que esta orden requiere diagnóstico técnico
        # Esto es importante para métricas, reportes y análisis del negocio
        orden.tipo_servicio = 'diagnostico'
        
        # IMPORTANTE: OrdenServicio requiere responsable_seguimiento y tecnico_asignado_actual
        # Como este es un formulario simplificado, usamos el usuario actual o el primero disponible
        
        if self.user and hasattr(self.user, 'empleado'):
            # Si el usuario tiene un empleado asociado, usarlo
            orden.responsable_seguimiento = self.user.empleado
            orden.tecnico_asignado_actual = self.user.empleado
        else:
            # Si no, usar el primer empleado activo (el campo es 'activo' para Empleado)
            primer_empleado = Empleado.objects.filter(activo=True).first()
            if primer_empleado:
                orden.responsable_seguimiento = primer_empleado
                orden.tecnico_asignado_actual = primer_empleado
            else:
                raise ValidationError("No hay empleados activos para asignar a la orden")
        
        # Ahora SÍ guardamos la orden (esto genera el numero_orden_interno automáticamente)
        if commit:
            orden.save()
            
            # AHORA crear el DetalleEquipo relacionado
            detalle = DetalleEquipo(
                orden=orden,  # Relación OneToOne con la orden
                tipo_equipo=self.cleaned_data['tipo_equipo'],
                marca=self.cleaned_data['marca'],
                modelo=self.cleaned_data.get('modelo', ''),  # Opcional
                numero_serie=self.cleaned_data['numero_serie'],
                orden_cliente=self.cleaned_data['orden_cliente'],  # Nuevo campo obligatorio
                email_cliente=self.cleaned_data.get('email_cliente', 'cliente@ejemplo.com'),  # ✅ NUEVO: Email opcional
                tiene_cargador=self.cleaned_data.get('tiene_cargador', False),
                numero_serie_cargador=self.cleaned_data.get('numero_serie_cargador', ''),
                equipo_enciende=self.cleaned_data.get('equipo_enciende', True),
                falla_principal='',  # Se llenará después en el diagnóstico
                gama='media',  # Valor por defecto, se calculará después si hay referencias
            )
            
            # Intentar calcular la gama automáticamente
            # EXPLICACIÓN: ReferenciaGamaEquipo.obtener_gama() retorna un objeto ReferenciaGamaEquipo
            # pero el campo detalle.gama espera un STRING ('alta', 'media', 'baja')
            # Por eso usamos .gama para extraer solo el valor del campo
            referencia_gama = ReferenciaGamaEquipo.obtener_gama(
                self.cleaned_data['marca'],
                self.cleaned_data.get('modelo', '')
            )
            if referencia_gama:
                # ✅ CORRECTO: Extraer el valor del campo gama del objeto
                detalle.gama = referencia_gama.gama
            
            detalle.save()
        
        return orden
    


# ============================================================================
# FORMULARIO PARA CREAR ORDEN DE VENTA MOSTRADOR
# ============================================================================

class NuevaOrdenVentaMostradorForm(forms.ModelForm):
    """
    Formulario simplificado para crear órdenes de Venta Mostrador.
    
    EXPLICACIÓN:
    Las ventas mostrador NO requieren diagnóstico técnico previo.
    Son servicios directos como:
    - Instalación de piezas
    - Reinstalación de sistema operativo
    - Limpieza express
    - Venta de accesorios
    
    Por lo tanto, este formulario es más simple que NuevaOrdenForm.
    """
    
    # ========================================================================
    # CAMPOS ADICIONALES DEL DETALLE DEL EQUIPO
    # ========================================================================
    
    tipo_equipo = forms.ChoiceField(
        choices=TIPO_EQUIPO_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control form-select',
            'required': True,
        }),
        label="Tipo de Equipo",
        help_text="Tipo de equipo que ingresa para el servicio"
    )
    
    marca = forms.ChoiceField(
        choices=MARCAS_EQUIPOS_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control form-select',
            'required': True,
        }),
        label="Marca del Equipo",
        help_text="Selecciona la marca del equipo"
    )
    
    modelo = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: Inspiron 15 (opcional)',
        }),
        label="Modelo del Equipo",
        help_text="Modelo específico (opcional)"
    )
    
    numero_serie = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: SN123456789',
            'required': True,
            'style': 'text-transform: uppercase;',
        }),
        label="Número de Serie",
        help_text="Número de serie o Service Tag del equipo"
    )
    
    orden_cliente = forms.CharField(
        max_length=50,
        initial='FL-',  # Valor inicial con el prefijo para Venta Mostrador
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'FL-',
            'required': True,
        }),
        label="Número de Orden del Cliente",
        help_text="<strong>Campo obligatorio.</strong> El prefijo 'FL-' aparece por defecto para Venta Mostrador. Puede borrar el texto para escribir otro número de orden, pero <strong>en las órdenes que son OOW- o FL-, siempre es necesario poner el prefijo.</strong>"
    )
    
    # ✅ NUEVO: Email del Cliente (Noviembre 2025)
    email_cliente = forms.EmailField(
        required=False,  # OPCIONAL al crear, obligatorio al editar
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'cliente@ejemplo.com (opcional)',
            'type': 'email',
            'autocomplete': 'email',
        }),
        label='📧 Email del Cliente',
        help_text='Email para enviar fotos del ingreso y notificaciones (opcional, se puede agregar después)'
    )
    
    equipo_enciende = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        label="¿El equipo enciende?",
        help_text="Estado del equipo al momento del ingreso"
    )
    
    # ========================================================================
    # CAMPOS DE ACCESORIOS (igual que en diagnóstico)
    # ========================================================================
    
    tiene_cargador = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'id_tiene_cargador',
        }),
        label="¿Incluye cargador?",
        help_text="Marca si el equipo trae cargador"
    )
    
    numero_serie_cargador = forms.CharField(
        max_length=100,
        required=False,  # OPCIONAL, solo si tiene cargador
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Número de serie del cargador (opcional)',
            'id': 'id_numero_serie_cargador',
        }),
        label="Número de Serie del Cargador",
        help_text="Solo si el cargador tiene número de serie identificable"
    )
    
    # ========================================================================
    # CAMPOS OPCIONALES DE DESCRIPCIÓN DEL SERVICIO
    # ========================================================================
    
    descripcion_servicio = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Ej: Cliente solicita instalación de RAM 8GB + Limpieza general del equipo',
        }),
        label="Descripción del Servicio Solicitado",
        help_text="Breve descripción de lo que el cliente solicita (opcional)"
    )
    
    # ========================================================================
    # CAMPOS DE LA ORDEN DE SERVICIO
    # ========================================================================
    
    class Meta:
        model = OrdenServicio
        fields = [
            'sucursal',
        ]
        
        widgets = {
            'sucursal': forms.Select(attrs={
                'class': 'form-control form-select',
                'required': True,
            }),
        }
        
        labels = {
            'sucursal': 'Sucursal',
        }
        
        help_texts = {
            'sucursal': 'Sucursal donde se registra la venta mostrador',
        }
    
    def __init__(self, *args, **kwargs):
        """Inicializa el formulario con opciones filtradas"""
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filtrar solo sucursales activas
        self.fields['sucursal'].queryset = Sucursal.objects.filter(activa=True)
    
    def clean_numero_serie(self):
        """Limpia y normaliza el número de serie"""
        numero_serie = self.cleaned_data.get('numero_serie')
        if numero_serie:
            return numero_serie.strip().upper()
        return numero_serie
    
    def clean_orden_cliente(self):
        """Limpia y normaliza el número de orden del cliente"""
        orden_cliente = self.cleaned_data.get('orden_cliente')
        if orden_cliente:
            return orden_cliente.strip().upper()
        return orden_cliente
    
    def clean_email_cliente(self):
        """
        Normaliza el email del cliente a minúsculas para evitar duplicados.
        Mismo comportamiento que en NuevaOrdenForm para consistencia.
        """
        email = self.cleaned_data.get('email_cliente')
        if email:
            return email.strip().lower()
        return email
    
    def save(self, commit=True):
        """
        Guarda la orden de Venta Mostrador.
        
        IMPORTANTE: Marca automáticamente tipo_servicio='venta_mostrador'
        Esto diferencia estas órdenes de las que requieren diagnóstico técnico,
        lo cual es crítico para métricas, reportes y análisis del negocio.
        """
        orden = super().save(commit=False)
        
        # ESTABLECER TIPO DE SERVICIO COMO VENTA MOSTRADOR
        # EXPLICACIÓN: Estas órdenes NO requieren diagnóstico técnico previo
        # Son servicios directos donde el cliente puede esperar o regresar el mismo día
        orden.tipo_servicio = 'venta_mostrador'
        
        # Establecer estado inicial como 'recepcion' (pueden empezar servicio de inmediato)
        orden.estado = 'recepcion'
        
        # Asignar responsable y técnico
        if self.user and hasattr(self.user, 'empleado'):
            orden.responsable_seguimiento = self.user.empleado
            orden.tecnico_asignado_actual = self.user.empleado
        else:
            primer_empleado = Empleado.objects.filter(activo=True).first()
            if primer_empleado:
                orden.responsable_seguimiento = primer_empleado
                orden.tecnico_asignado_actual = primer_empleado
            else:
                raise ValidationError("No hay empleados activos para asignar a la orden")
        
        if commit:
            orden.save()
            
            # Crear DetalleEquipo relacionado
            detalle = DetalleEquipo(
                orden=orden,
                tipo_equipo=self.cleaned_data['tipo_equipo'],
                marca=self.cleaned_data['marca'],
                modelo=self.cleaned_data.get('modelo', ''),
                numero_serie=self.cleaned_data['numero_serie'],
                orden_cliente=self.cleaned_data['orden_cliente'],
                email_cliente=self.cleaned_data.get('email_cliente', 'cliente@ejemplo.com'),  # ✅ NUEVO: Email opcional
                equipo_enciende=self.cleaned_data.get('equipo_enciende', True),
                falla_principal=self.cleaned_data.get('descripcion_servicio', 'Venta Mostrador - Servicio Directo'),
                gama='media',  # Valor por defecto
                tiene_cargador=self.cleaned_data.get('tiene_cargador', False),
                numero_serie_cargador=self.cleaned_data.get('numero_serie_cargador', '') if self.cleaned_data.get('tiene_cargador', False) else '',
            )
            
            # Intentar calcular gama automáticamente
            # EXPLICACIÓN: Extraer el valor del campo gama del objeto ReferenciaGamaEquipo
            referencia_gama = ReferenciaGamaEquipo.obtener_gama(
                self.cleaned_data['marca'],
                self.cleaned_data.get('modelo', '')
            )
            if referencia_gama:
                # ✅ CORRECTO: Usar .gama para obtener el string ('alta', 'media', 'baja')
                detalle.gama = referencia_gama.gama
            
            detalle.save()
            
            # Registrar en historial
            # Obtener el empleado del usuario actual para el historial
            empleado_historial = None
            if self.user and hasattr(self.user, 'empleado'):
                empleado_historial = self.user.empleado
            
            HistorialOrden.objects.create(
                orden=orden,
                tipo_evento='creacion',
                comentario=f'🛒 Orden de Venta Mostrador creada: {orden.numero_orden_interno}. Servicio directo sin diagnóstico previo.',
                usuario=empleado_historial,
                es_sistema=False
            )
        
        return orden


# ============================================================================
# FORMULARIOS PARA LA VISTA DE DETALLES
# ============================================================================

class ConfiguracionAdicionalForm(forms.ModelForm):
    """
    Formulario para configurar información adicional del equipo después de crear la orden.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Este formulario permite al técnico agregar más información detallada sobre el equipo
    después de que la orden fue creada. Incluye:
    - Diagnóstico técnico (SIC - Sistema de Información del Cliente)
    - Fechas de inicio y fin del diagnóstico
    - Fechas de inicio y fin de la reparación
    - Si requiere factura
    """
    
    class Meta:
        model = DetalleEquipo
        fields = [
            'falla_principal',
            'diagnostico_sic',
            'fecha_inicio_diagnostico',
            'fecha_fin_diagnostico',
            'fecha_inicio_reparacion',
            'fecha_fin_reparacion',
        ]
        
        widgets = {
            'falla_principal': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe la falla principal reportada por el cliente...',
            }),
            'diagnostico_sic': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Diagnóstico técnico detallado del equipo...',
            }),
            'fecha_inicio_diagnostico': forms.DateInput(
                format='%Y-%m-%d',
                attrs={
                    'class': 'form-control',
                    'type': 'date',
                }
            ),
            'fecha_fin_diagnostico': forms.DateInput(
                format='%Y-%m-%d',
                attrs={
                    'class': 'form-control',
                    'type': 'date',
                }
            ),
            'fecha_inicio_reparacion': forms.DateInput(
                format='%Y-%m-%d',
                attrs={
                    'class': 'form-control',
                    'type': 'date',
                }
            ),
            'fecha_fin_reparacion': forms.DateInput(
                format='%Y-%m-%d',
                attrs={
                    'class': 'form-control',
                    'type': 'date',
                }
            ),
        }
        
        labels = {
            'falla_principal': 'Falla Principal',
            'diagnostico_sic': 'Diagnóstico SIC',
            'fecha_inicio_diagnostico': 'Inicio Diagnóstico',
            'fecha_fin_diagnostico': 'Fin Diagnóstico',
            'fecha_inicio_reparacion': 'Inicio Reparación',
            'fecha_fin_reparacion': 'Fin Reparación',
        }
        
        help_texts = {
            'falla_principal': 'Descripción de la falla reportada por el cliente',
            'diagnostico_sic': 'Diagnóstico técnico completo',
        }
    
    def save(self, commit=True):
        """
        Sobrescribe el método save para preservar fechas existentes.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        - Problema: Cuando envías el formulario, los campos de fecha vacíos
          se guardan como None, borrando valores anteriores
        - Solución: Si un campo de fecha viene vacío en el formulario PERO
          ya tenía un valor guardado, lo preservamos
        - Esto permite modificar fechas individualmente sin perder las demás
        
        Ejemplo:
        - Tienes guardado: inicio=01/10, fin=05/10
        - Solo cambias inicio a 02/10, dejando fin vacío en el form
        - Sin esta función: inicio=02/10, fin=None (se borra)
        - Con esta función: inicio=02/10, fin=05/10 (se preserva)
        """
        instance = super().save(commit=False)
        
        # Lista de campos de fecha a preservar
        campos_fecha = [
            'fecha_inicio_diagnostico',
            'fecha_fin_diagnostico',
            'fecha_inicio_reparacion',
            'fecha_fin_reparacion',
        ]
        
        # Para cada campo de fecha
        for campo in campos_fecha:
            # Obtener el valor del formulario
            valor_nuevo = self.cleaned_data.get(campo)
            
            # Si el formulario trae None (campo vacío)
            if valor_nuevo is None:
                # Verificar si la instancia original tenía un valor
                if self.instance.pk:  # Solo si ya existe en la BD
                    # Obtener el valor actual de la base de datos
                    try:
                        instancia_original = DetalleEquipo.objects.get(pk=self.instance.pk)
                        valor_existente = getattr(instancia_original, campo)
                        
                        # Si había un valor guardado, preservarlo
                        if valor_existente is not None:
                            setattr(instance, campo, valor_existente)
                    except DetalleEquipo.DoesNotExist:
                        pass
        
        if commit:
            instance.save()
        
        return instance


class ReingresoRHITSOForm(forms.ModelForm):
    """
    Formulario para marcar una orden como reingreso o candidato a RHITSO.
    
    EXPLICACIÓN:
    - Reingreso: Equipo que regresa después de una reparación previa
    - RHITSO: Reparación especializada (soldadura, reballing, etc.)
    
    Este formulario permite marcar estas condiciones después de crear la orden.
    """
    
    class Meta:
        model = OrdenServicio
        fields = [
            'es_reingreso',
            'orden_original',
            'es_candidato_rhitso',
            'motivo_rhitso',
            'descripcion_rhitso',
        ]
        
        widgets = {
            'es_reingreso': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'id_es_reingreso_detalle',
            }),
            'orden_original': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
            'es_candidato_rhitso': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'id_es_candidato_rhitso_detalle',
            }),
            'motivo_rhitso': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
            'descripcion_rhitso': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe por qué requiere reparación especializada...',
            }),
        }
        
        labels = {
            'es_reingreso': '¿Es un reingreso?',
            'orden_original': 'Orden Original',
            'es_candidato_rhitso': '¿Candidato a RHITSO?',
            'motivo_rhitso': 'Motivo RHITSO',
            'descripcion_rhitso': 'Descripción Detallada',
        }
        
        help_texts = {
            'es_reingreso': 'Marca si este equipo ya fue reparado anteriormente',
            'orden_original': 'Selecciona la orden original si es reingreso',
            'es_candidato_rhitso': 'Marca si requiere reparación especializada',
            'motivo_rhitso': 'Motivo por el cual requiere RHITSO',
        }
    
    def __init__(self, *args, **kwargs):
        """
        Personalizar el formulario al crearlo.
        Filtra las órdenes disponibles para seleccionar como orden original.
        """
        super().__init__(*args, **kwargs)
        
        # Solo mostrar órdenes entregadas como posibles órdenes originales
        if self.instance and self.instance.pk:
            # Excluir la orden actual de la lista
            self.fields['orden_original'].queryset = OrdenServicio.objects.filter(
                estado='entregado'
            ).exclude(pk=self.instance.pk)
        else:
            self.fields['orden_original'].queryset = OrdenServicio.objects.filter(
                estado='entregado'
            )


class CambioEstadoForm(forms.ModelForm):
    """
    Formulario para cambiar el estado de una orden.
    
    EXPLICACIÓN:
    Cuando cambias el estado de una orden, el sistema automáticamente:
    1. Registra el cambio en el historial
    2. Actualiza las fechas correspondientes
    3. Cambia el estado de la orden
    
    Los estados posibles están definidos en config/constants.py
    
    NOTA: Este formulario SOLO cambia el estado. Para asignar responsables
    usa el formulario AsignarResponsablesForm.
    """
    
    comentario_cambio = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Comentario opcional sobre el cambio de estado...',
        }),
        label='Comentario (Opcional)',
        help_text='Agrega un comentario sobre por qué cambió el estado'
    )
    
    class Meta:
        model = OrdenServicio
        fields = ['estado']  # Solo el estado, no los responsables
        
        widgets = {
            'estado': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
        }
        
        labels = {
            'estado': 'Nuevo Estado',
        }
        
        help_texts = {
            'estado': 'Selecciona el nuevo estado de la orden',
        }
    
    def clean(self):
        """
        Validación personalizada que asigna fechas ANTES de la validación del modelo.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        ================================
        Este método se ejecuta durante form.is_valid(), ANTES de que Django
        valide el modelo completo con instance.clean().
        
        ¿Por qué es importante?
        El modelo OrdenServicio tiene una validación que requiere que:
        - Si estado = 'finalizado', debe existir fecha_finalizacion
        - Si estado = 'entregado', debe existir fecha_entrega
        
        Si no asignamos estas fechas AQUÍ, la validación del modelo fallará
        y el usuario verá un error.
        
        Flujo:
        1. Usuario envía formulario
        2. is_valid() llama a form.clean() ← ESTAMOS AQUÍ
        3. Asignamos las fechas necesarias
        4. is_valid() llama a instance.clean() ← Ya tenemos las fechas
        5. ✅ Validación exitosa
        
        Returns:
            dict: Los datos limpios del formulario
        """
        from django.utils import timezone
        
        # Llamar al clean() de la clase padre primero
        cleaned_data = super().clean()
        
        # Obtener el nuevo estado del formulario
        nuevo_estado = cleaned_data.get('estado')
        
        # Obtener el estado anterior de la instancia
        estado_anterior = self.instance.estado if self.instance.pk else None
        
        # Asignar fechas ANTES de la validación del modelo si es necesario
        if nuevo_estado == 'finalizado' and estado_anterior != 'finalizado':
            if not self.instance.fecha_finalizacion:
                self.instance.fecha_finalizacion = timezone.now()
        
        if nuevo_estado == 'entregado' and estado_anterior != 'entregado':
            if not self.instance.fecha_entrega:
                self.instance.fecha_entrega = timezone.now()
        
        return cleaned_data
    
    def save(self, commit=True):
        """
        Guarda la orden con las fechas ya asignadas en clean().
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        ================================
        Este método simplemente guarda la orden. Las fechas ya fueron
        asignadas en el método clean() que se ejecuta durante is_valid().
        
        No necesitamos lógica compleja aquí porque clean() ya hizo el trabajo.
        
        Parámetros:
            commit (bool): Si True, guarda en la base de datos. Si False, solo prepara.
        
        Returns:
            OrdenServicio: El objeto guardado o preparado
        """
        # Las fechas ya fueron asignadas en clean(), solo guardamos
        return super().save(commit=commit)


class AsignarResponsablesForm(forms.ModelForm):
    """
    Formulario para asignar responsables de la orden (técnico y seguimiento).
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Este formulario permite cambiar quién es responsable de la orden:
    
    - tecnico_asignado_actual: El técnico que repara el equipo (SOLO TECNICOS DE LABORATORIO)
    - responsable_seguimiento: La persona que da seguimiento al caso
    
    FILTROS APLICADOS:
    - Técnicos: Solo empleados con cargo "TECNICO DE LABORATORIO" y activos
    - Responsables: Todos los empleados activos
    
    Cuando cambias estos responsables:
    1. Se actualiza la orden
    2. Se registra el cambio en el historial
    3. Se guarda quién era el técnico anterior (si aplica)
    """
    
    class Meta:
        model = OrdenServicio
        fields = ['tecnico_asignado_actual', 'responsable_seguimiento']
        
        widgets = {
            'tecnico_asignado_actual': forms.Select(attrs={
                'class': 'form-control form-select',
                'id': 'id_tecnico_select',  # ID específico para JavaScript
            }),
            'responsable_seguimiento': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
        }
        
        labels = {
            'tecnico_asignado_actual': 'Técnico Asignado',
            'responsable_seguimiento': 'Responsable de Seguimiento',
        }
        
        help_texts = {
            'tecnico_asignado_actual': 'Técnico de laboratorio que reparará el equipo',
            'responsable_seguimiento': 'Persona encargada del seguimiento',
        }
    
    def __init__(self, *args, **kwargs):
        """
        EXPLICACIÓN PARA PRINCIPIANTES:
        Este método se ejecuta cuando se crea el formulario.
        Aquí aplicamos filtros especiales:
        
        1. Para TÉCNICOS: Solo mostramos empleados con cargo "TECNICO DE LABORATORIO"
        2. Para RESPONSABLES: Mostramos todos los empleados activos
        
        El filtro usa __icontains que es case-insensitive (no importa mayúsculas/minúsculas)
        """
        super().__init__(*args, **kwargs)
        
        # FILTRO ESPECIAL: Solo técnicos de laboratorio activos
        # __icontains = búsqueda case-insensitive (ignora mayúsculas/minúsculas)
        tecnicos_laboratorio = Empleado.objects.filter(
            activo=True,
            cargo__icontains='TECNICO DE LABORATORIO'
        ).order_by('nombre_completo')
        
        self.fields['tecnico_asignado_actual'].queryset = tecnicos_laboratorio
        
        # Para responsables: todos los empleados activos
        self.fields['responsable_seguimiento'].queryset = Empleado.objects.filter(
            activo=True
        ).order_by('nombre_completo')


class ComentarioForm(forms.ModelForm):
    """
    Formulario para agregar comentarios al historial de la orden.
    
    EXPLICACIÓN:
    Los comentarios se guardan en el modelo HistorialOrden con tipo_evento='comentario'.
    Este formulario es simple pero importante para la trazabilidad del proceso.
    """
    
    class Meta:
        model = HistorialOrden
        fields = ['comentario']
        
        widgets = {
            'comentario': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Escribe un comentario sobre la orden...',
                'required': True,
            }),
        }
        
        labels = {
            'comentario': 'Comentario',
        }
        
        help_texts = {
            'comentario': 'Agrega notas, observaciones o actualizaciones sobre la orden',
        }
    
    def save(self, commit=True, orden=None, usuario=None):
        """
        Guardar el comentario con información adicional.
        
        EXPLICACIÓN:
        Necesitamos sobrescribir save() porque el comentario requiere:
        - La orden a la que pertenece
        - El usuario que lo creó
        - Tipo de evento = 'comentario'
        """
        comentario = super().save(commit=False)
        
        if orden:
            comentario.orden = orden
        
        if usuario:
            comentario.usuario = usuario
        
        comentario.tipo_evento = 'comentario'
        comentario.es_sistema = False
        
        if commit:
            comentario.save()
        
        return comentario


class SubirImagenesForm(forms.Form):
    """
    Formulario para subir múltiples imágenes de una orden.
    
    EXPLICACIÓN:
    Este formulario maneja la subida de imágenes con las siguientes características:
    - Permite subir múltiples archivos a la vez
    - Valida que sean imágenes (JPG, PNG, GIF)
    - Limita el tamaño a 6MB por imagen
    - Comprime automáticamente las imágenes
    - Organiza las imágenes por service_tag y tipo
    
    IMPORTANTE:
    La compresión y organización se maneja en la vista, no en el formulario.
    Usamos forms.Form (no ModelForm) porque necesitamos manejar múltiples archivos.
    El atributo 'multiple' se agrega directamente en el HTML del template.
    """
    
    tipo = forms.ChoiceField(
        choices=TIPO_IMAGEN_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control form-select',
        }),
        label='Tipo de Imagen',
        help_text='Selecciona el tipo de imagen (ingreso, egreso, diagnóstico, etc.)',
    )
    
    imagenes = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/jpeg,image/jpg,image/png,image/gif',
        }),
        label='Seleccionar Imágenes',
        help_text='Puedes seleccionar múltiples imágenes (máximo 30, 50MB cada una)',
        required=False,
    )
    
    descripcion = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Descripción opcional de las imágenes...',
        }),
        label='Descripción',
        help_text='Descripción breve opcional',
    )


# ============================================================================
# FORMULARIO 7: Editar Información Principal del Equipo
# ============================================================================

class EditarInformacionEquipoForm(forms.ModelForm):
    """
    Formulario para editar la información principal del equipo.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Este formulario permite modificar datos importantes del equipo que pueden
    haber sido omitidos o necesitan corrección, como:
    - Modelo del equipo (si no se especificó al inicio)
    - Si el equipo enciende o no
    - Número de serie del cargador
    - Otros datos básicos del equipo
    
    Se usa en un modal para permitir ediciones rápidas sin salir de la vista
    de detalle de la orden.
    """
    
    class Meta:
        model = DetalleEquipo
        fields = [
            'tipo_equipo',
            'marca',
            'modelo',
            'numero_serie',
            'orden_cliente',
            'email_cliente',  # ✅ NUEVO CAMPO (Noviembre 2025)
            'equipo_enciende',
            'tiene_cargador',
            'numero_serie_cargador',
            'gama',
        ]
        
        widgets = {
            'tipo_equipo': forms.Select(attrs={
                'class': 'form-control form-select',
                'required': True,
            }),
            'marca': forms.Select(attrs={
                'class': 'form-control form-select',
                'required': True,
            }),
            'modelo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Inspiron 15, ThinkPad X1 (opcional)',
                'data-api-url': '/servicio-tecnico/api/buscar-modelos-por-marca/',
                'data-enable-select2': 'true',  # Flag para habilitar Select2 via JS
            }),
            'numero_serie': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número de serie o Service Tag',
                'required': True,
                'style': 'text-transform: uppercase;',
            }),
            'orden_cliente': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número de orden del cliente',
                'required': True,
            }),
            # ✅ NUEVO WIDGET: Email del Cliente
            'email_cliente': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'cliente@ejemplo.com',
                'required': True,
                'type': 'email',  # HTML5 email validation
                'autocomplete': 'email',
            }),
            'equipo_enciende': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'tiene_cargador': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'id_tiene_cargador_modal',
                'onchange': 'toggleCargadorFieldsModal()',
            }),
            'numero_serie_cargador': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número de serie del cargador (opcional)',
                'id': 'id_numero_serie_cargador_modal',
            }),
            'gama': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
        }
        
        labels = {
            'tipo_equipo': 'Tipo de Equipo',
            'marca': 'Marca',
            'modelo': 'Modelo',
            'numero_serie': 'Número de Serie',
            'orden_cliente': 'Orden del Cliente',
            'email_cliente': '📧 Email del Cliente',  # ✅ NUEVO
            'equipo_enciende': '¿El equipo enciende?',
            'tiene_cargador': '¿Incluye cargador?',
            'numero_serie_cargador': 'Número de Serie del Cargador',
            'gama': 'Gama del Equipo',
        }
        
        help_texts = {
            'tipo_equipo': 'Tipo de equipo (Laptop, Desktop, etc.)',
            'marca': 'Marca del fabricante',
            'modelo': 'Modelo específico (opcional)',
            'numero_serie': 'Número de serie o Service Tag del equipo',
            'orden_cliente': 'Número de orden del cliente',
            'email_cliente': 'Email para enviar fotos del ingreso y notificaciones (obligatorio)',  # ✅ NUEVO
            'equipo_enciende': 'Marca si el equipo enciende al momento del ingreso',
            'tiene_cargador': 'Marca si el equipo incluye cargador',
            'numero_serie_cargador': 'Solo si el cargador tiene número de serie identificable',
            'gama': 'Clasificación de gama del equipo',
        }


# ============================================================================
# FORMULARIO PARA REFERENCIAS DE GAMA
# ============================================================================

class ReferenciaGamaEquipoForm(forms.ModelForm):
    """
    Formulario para crear y editar referencias de gama de equipos.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Este formulario permite agregar/editar referencias que el sistema usa
    para clasificar automáticamente los equipos en gama alta, media o baja.
    
    Por ejemplo:
    - Marca: Lenovo
    - Modelo Base: ThinkPad X1
    - Gama: Alta
    - Rango de costo: $25,000 - $45,000
    
    Cuando alguien cree una orden con marca "Lenovo" y modelo "ThinkPad X1 Carbon",
    el sistema automáticamente lo clasificará como gama alta.
    """
    
    class Meta:
        model = ReferenciaGamaEquipo
        fields = [
            'marca',
            'modelo_base',
            'gama',
            'rango_costo_min',
            'rango_costo_max',
            'activo',
        ]
        
        # Widgets: Definir cómo se ven los campos en el HTML
        widgets = {
            'marca': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Lenovo, HP, Dell, Apple',
                'maxlength': 50,
            }),
            'modelo_base': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: ThinkPad, Inspiron, Pavilion, MacBook Pro',
                'maxlength': 100,
            }),
            'gama': forms.Select(attrs={
                'class': 'form-select',
            }),
            'rango_costo_min': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 5000.00',
                'step': '0.01',
                'min': '0',
            }),
            'rango_costo_max': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 15000.00',
                'step': '0.01',
                'min': '0',
            }),
            'activo': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }
        
        labels = {
            'marca': 'Marca del Equipo',
            'modelo_base': 'Modelo Base o Familia',
            'gama': 'Clasificación de Gama',
            'rango_costo_min': 'Costo Mínimo Aproximado ($)',
            'rango_costo_max': 'Costo Máximo Aproximado ($)',
            'activo': 'Referencia Activa',
        }
        
        help_texts = {
            'marca': 'Nombre del fabricante del equipo',
            'modelo_base': 'Modelo o familia de productos (se buscan coincidencias parciales). Ej: "ThinkPad" coincidirá con "ThinkPad X1 Carbon"',
            'gama': 'Clasificación que se asignará automáticamente a equipos que coincidan',
            'rango_costo_min': 'Costo aproximado mínimo del equipo (solo referencia)',
            'rango_costo_max': 'Costo aproximado máximo del equipo (solo referencia)',
            'activo': 'Si está activa, se usará para clasificación automática. Si está inactiva, se ignorará',
        }
    
    def clean(self):
        """
        Validaciones personalizadas del formulario.
        
        EXPLICACIÓN:
        Esta función se ejecuta cuando Django valida el formulario.
        Verificamos que los datos sean consistentes antes de guardar.
        """
        cleaned_data = super().clean()
        
        marca = cleaned_data.get('marca')
        modelo_base = cleaned_data.get('modelo_base')
        rango_min = cleaned_data.get('rango_costo_min')
        rango_max = cleaned_data.get('rango_costo_max')
        
        # Validación 1: El costo máximo debe ser mayor al mínimo
        if rango_min and rango_max:
            if rango_max <= rango_min:
                raise ValidationError(
                    '❌ El costo máximo debe ser mayor que el costo mínimo'
                )
        
        # Validación 2: Verificar duplicados (marca + modelo_base únicos)
        # Solo si estamos creando (no editando)
        if self.instance.pk is None:  # Es un nuevo registro
            if marca and modelo_base:
                existe = ReferenciaGamaEquipo.objects.filter(
                    marca__iexact=marca,
                    modelo_base__iexact=modelo_base
                ).exists()
                
                if existe:
                    raise ValidationError(
                        f'❌ Ya existe una referencia para {marca} {modelo_base}. '
                        f'Edita la existente o usa un modelo diferente.'
                    )
        
        return cleaned_data


# ============================================================================
# FORMULARIO: CREAR COTIZACIÓN
# ============================================================================

class CrearCotizacionForm(forms.ModelForm):
    """
    Formulario para crear una nueva cotización para una orden.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Este formulario permite iniciar el proceso de cotización. Captura solo
    el costo de mano de obra inicialmente. Las piezas se agregan después
    desde el admin de Django.
    
    FLUJO:
    1. Usuario crea cotización con costo de mano de obra
    2. Se va al admin para agregar las piezas necesarias (PiezaCotizada)
    3. Se envía cotización al cliente
    4. Cliente responde (acepta/rechaza) usando GestionarCotizacionForm
    """
    
    class Meta:
        model = Cotizacion
        fields = ['costo_mano_obra']
        
        widgets = {
            'costo_mano_obra': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
                'required': True,
            }),
        }
        
        labels = {
            'costo_mano_obra': 'Costo de Mano de Obra',
        }
        
        help_texts = {
            'costo_mano_obra': 'Costo del servicio técnico (diagnóstico + reparación)',
        }
    
    def __init__(self, *args, **kwargs):
        """
        EXPLICACIÓN:
        Configuración inicial del formulario. Aquí podemos personalizar
        cómo se ve o comporta el formulario antes de mostrarlo.
        """
        super().__init__(*args, **kwargs)
        
        # Agregar clase de validación de Bootstrap
        for field_name, field in self.fields.items():
            if 'class' in field.widget.attrs:
                field.widget.attrs['class'] += ' '
            else:
                field.widget.attrs['class'] = ''
            field.widget.attrs['class'] += 'is-validatable'


# ============================================================================
# FORMULARIO: GESTIONAR COTIZACIÓN (Aceptar/Rechazar)
# ============================================================================

class GestionarCotizacionForm(forms.ModelForm):
    """
    Formulario para que el cliente acepte o rechace la cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Este formulario captura la decisión del cliente sobre la cotización.
    - Si acepta: usuario_acepto = True, solo las piezas seleccionadas se aceptan
    - Si rechaza: usuario_acepto = False, TODAS las piezas se rechazan automáticamente
    
    NOTA IMPORTANTE:
    Las piezas seleccionadas NO se manejan en el formulario, sino directamente
    en la vista desde request.POST.getlist('piezas_seleccionadas'). Esto es porque
    los checkboxes están fuera del formulario en el template.
    """
    
    # Campo adicional para decidir la acción (no se guarda en la BD)
    accion = forms.ChoiceField(
        choices=[
            ('aceptar', 'Aceptar Cotización'),
            ('rechazar', 'Rechazar Cotización'),
        ],
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input',
        }),
        label='Decisión del Cliente',
        help_text='Selecciona la decisión del cliente sobre la cotización',
        required=True,
    )
    
    # Campo para aplicar descuento de mano de obra (Octubre 2025)
    descontar_mano_obra = forms.BooleanField(
        required=False,
        label='🎁 Descontar mano de obra como beneficio',
        help_text='Al aceptar la cotización, el diagnóstico será gratuito como incentivo',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'id_descontar_mano_obra',
        }),
    )
    
    class Meta:
        model = Cotizacion
        fields = ['motivo_rechazo', 'detalle_rechazo', 'descontar_mano_obra']
        
        widgets = {
            'motivo_rechazo': forms.Select(attrs={
                'class': 'form-control form-select',
                'id': 'id_motivo_rechazo',
            }),
            'detalle_rechazo': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'id': 'id_detalle_rechazo',
                'placeholder': 'Selecciona un motivo de rechazo y se cargará automáticamente una plantilla. Edita los campos entre [ ] con los datos específicos del caso.',
            }),
        }
        
        labels = {
            'motivo_rechazo': 'Motivo del Rechazo',
            'detalle_rechazo': 'Detalle Adicional del Rechazo',
        }
        
        help_texts = {
            'motivo_rechazo': 'Selecciona la razón principal por la que rechaza',
            'detalle_rechazo': 'Información adicional sobre el rechazo (opcional)',
        }
    
    def __init__(self, *args, **kwargs):
        """
        EXPLICACIÓN:
        Configuración inicial del formulario.
        Los campos de rechazo solo son obligatorios si se rechaza la cotización.
        """
        super().__init__(*args, **kwargs)
        
        # Por defecto, los campos de rechazo no son obligatorios
        # Se harán obligatorios con JavaScript si selecciona "rechazar"
        self.fields['motivo_rechazo'].required = False
        self.fields['detalle_rechazo'].required = False
    
    def clean(self):
        """
        EXPLICACIÓN:
        Validación personalizada del formulario.
        Si rechaza, debe indicar al menos el motivo.
        El descuento solo es válido si acepta la cotización.
        
        NOTA: La validación de piezas seleccionadas se hace en la vista,
        no aquí, porque los checkboxes están fuera del formulario.
        """
        cleaned_data = super().clean()
        accion = cleaned_data.get('accion')
        motivo_rechazo = cleaned_data.get('motivo_rechazo')
        descontar_mano_obra = cleaned_data.get('descontar_mano_obra', False)
        
        # Si rechaza, el motivo es obligatorio
        if accion == 'rechazar' and not motivo_rechazo:
            raise ValidationError({
                'motivo_rechazo': '❌ Debes seleccionar un motivo si rechazas la cotización'
            })
        
        # Si acepta, limpiar campos de rechazo
        if accion == 'aceptar':
            cleaned_data['motivo_rechazo'] = ''
            cleaned_data['detalle_rechazo'] = ''
        
        # Si rechaza, NO puede aplicar descuento (lógica de negocio)
        if accion == 'rechazar' and descontar_mano_obra:
            cleaned_data['descontar_mano_obra'] = False
        
        return cleaned_data
    
    def save(self, commit=True):
        """
        EXPLICACIÓN:
        Guardar el formulario con la decisión del cliente.
        Actualiza usuario_acepto según la acción seleccionada.
        
        NOTA IMPORTANTE: Este método NO actualiza las piezas individuales.
        Eso se hace en la vista para tener más control y registro en el historial.
        """
        instance = super().save(commit=False)
        
        # Obtener la acción del cleaned_data
        accion = self.cleaned_data.get('accion')
        
        # Actualizar usuario_acepto según la acción
        if accion == 'aceptar':
            instance.usuario_acepto = True
            # Limpiar campos de rechazo si existían
            instance.motivo_rechazo = ''
            instance.detalle_rechazo = ''
        elif accion == 'rechazar':
            instance.usuario_acepto = False
        
        # Actualizar fecha de respuesta
        from django.utils import timezone
        if instance.fecha_respuesta is None:
            instance.fecha_respuesta = timezone.now()
        
        if commit:
            instance.save()
        
        return instance


# ============================================================================
# FORMULARIO: GESTIONAR PIEZA COTIZADA
# ============================================================================

class PiezaCotizadaForm(forms.ModelForm):
    """
    Formulario para agregar o editar piezas en una cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Este formulario permite gestionar las piezas individuales que forman parte
    de una cotización. El usuario selecciona un componente del catálogo de
    ScoreCard, define cantidad y costo, y marca su prioridad.
    
    IMPORTANTE:
    - No se puede eliminar una pieza si la cotización ya fue aceptada
    - Sí se puede modificar después de aceptada (para ajustar costos reales)
    - El componente viene del catálogo de ScoreCard (reutilización)
    """
    
    class Meta:
        model = PiezaCotizada
        fields = [
            'componente',
            'descripcion_adicional',
            'proveedor',  # ← NUEVO CAMPO (Noviembre 2025)
            'cantidad',
            'costo_unitario',
            'orden_prioridad',
            'es_necesaria',
            'sugerida_por_tecnico',
        ]
        
        widgets = {
            'componente': forms.Select(attrs={
                'class': 'form-control form-select',
                'id': 'componente',  # ID explícito para JavaScript
                'required': True,
            }),
            'descripcion_adicional': forms.Textarea(attrs={
                'class': 'form-control',
                'id': 'descripcion_adicional',
                'rows': 2,
                'placeholder': 'Descripción específica de la pieza (opcional)',
            }),
            'proveedor': forms.Select(attrs={
                'class': 'form-control form-select',
                'id': 'proveedor',
            }),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control',
                'id': 'cantidad',
                'min': '1',
                'value': '1',
                'required': True,
            }),
            'costo_unitario': forms.NumberInput(attrs={
                'class': 'form-control',
                'id': 'costo_unitario',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00',
                'required': True,
            }),
            'orden_prioridad': forms.NumberInput(attrs={
                'class': 'form-control',
                'id': 'orden_prioridad',
                'min': '1',
                'value': '1',
                'required': True,
            }),
            'es_necesaria': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'es_necesaria',
            }),
            'sugerida_por_tecnico': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'sugerida_por_tecnico',
            }),
        }
        
        labels = {
            'componente': 'Componente',
            'descripcion_adicional': 'Descripción Adicional',
            'proveedor': '🏪 Proveedor',  # ← NUEVO CAMPO
            'cantidad': 'Cantidad',
            'costo_unitario': 'Costo Unitario ($)',
            'orden_prioridad': 'Prioridad',
            'es_necesaria': '¿Es necesaria para el funcionamiento?',
            'sugerida_por_tecnico': '¿Sugerida por el técnico?',
        }
        
        help_texts = {
            'componente': 'Selecciona el componente del catálogo',
            'proveedor': 'Selecciona con qué proveedor se cotizó esta pieza (opcional)',  # ← NUEVO
            'cantidad': 'Número de unidades a cambiar',
            'costo_unitario': 'Precio por unidad',
            'orden_prioridad': '1 = más importante',
            'es_necesaria': 'Marca si es necesaria para el funcionamiento (vs mejora estética/rendimiento)',
        }
    
    def __init__(self, *args, **kwargs):
        """
        EXPLICACIÓN:
        Personalización del formulario al inicializarse.
        Filtramos solo componentes activos del catálogo.
        
        NOVIEMBRE 2025: Agregado configuración de proveedores predefinidos.
        """
        super().__init__(*args, **kwargs)
        
        # Filtrar solo componentes activos
        self.fields['componente'].queryset = ComponenteEquipo.objects.filter(
            activo=True
        ).order_by('nombre')
        
        # Agregar opción vacía al dropdown
        self.fields['componente'].empty_label = "-- Selecciona un componente --"
        
        # ✨ NUEVO: Configurar campo proveedor con lista predefinida
        # El campo proveedor usa las constantes de config/constants.py
        # esto permite mantener la lista centralizada y fácil de actualizar
        self.fields['proveedor'].widget = forms.Select(
            choices=PROVEEDORES_CHOICES,
            attrs={
                'class': 'form-control form-select',
                'id': 'proveedor',
            }
        )
    
    def clean(self):
        """
        EXPLICACIÓN:
        Validaciones personalizadas del formulario.
        """
        cleaned_data = super().clean()
        cantidad = cleaned_data.get('cantidad')
        costo_unitario = cleaned_data.get('costo_unitario')
        
        # Validar que cantidad sea positiva
        if cantidad and cantidad < 1:
            raise ValidationError({
                'cantidad': '❌ La cantidad debe ser al menos 1'
            })
        
        # Validar que costo sea positivo
        if costo_unitario and costo_unitario < 0:
            raise ValidationError({
                'costo_unitario': '❌ El costo no puede ser negativo'
            })
        
        return cleaned_data


# ============================================================================
# FORMULARIO: GESTIONAR SEGUIMIENTO DE PIEZA
# ============================================================================

class SeguimientoPiezaForm(forms.ModelForm):
    """
    Formulario para agregar o actualizar seguimiento de pedidos a proveedores.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Este formulario gestiona el tracking de pedidos de piezas a proveedores.
    Permite registrar: quién provee, cuándo se pidió, cuándo llega, estado actual.
    
    NUEVA FUNCIONALIDAD:
    Ahora permite seleccionar las piezas específicas que se están rastreando.
    Solo muestra piezas que fueron aceptadas por el cliente.
    
    CAMPOS OBLIGATORIOS:
    - Proveedor (siempre)
    - Descripción de piezas (siempre)
    - Fecha de pedido (siempre)
    - Fecha estimada de entrega (siempre)
    
    NOTIFICACIÓN AUTOMÁTICA:
    Cuando el estado cambia a "recibido", se envía un email al técnico asignado.
    """
    
    class Meta:
        model = SeguimientoPieza
        fields = [
            'piezas',  # NUEVO: Selección de piezas específicas
            'proveedor',
            'descripcion_piezas',
            'numero_pedido',
            'fecha_pedido',
            'fecha_entrega_estimada',
            'fecha_entrega_real',
            'estado',
            'notas_seguimiento',
        ]
        
        widgets = {
            'piezas': forms.CheckboxSelectMultiple(attrs={
                'class': 'form-check-input',
            }),
            'proveedor': forms.Select(attrs={
                'class': 'form-control form-select',
                'required': True,
            }),
            'descripcion_piezas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Describe las piezas incluidas en este pedido',
                'required': True,
            }),
            'numero_pedido': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número de pedido o tracking',
            }),
            'fecha_pedido': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'required': True,
            }),
            'fecha_entrega_estimada': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'required': True,
            }),
            'fecha_entrega_real': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'estado': forms.Select(attrs={
                'class': 'form-control form-select',
                'required': True,
            }),
            'notas_seguimiento': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Notas adicionales sobre el seguimiento (opcional)',
            }),
        }
        
        labels = {
            'piezas': 'Piezas a Rastrear',
            'proveedor': 'Proveedor',
            'descripcion_piezas': 'Descripción de Piezas',
            'numero_pedido': 'Número de Pedido / Tracking',
            'fecha_pedido': 'Fecha de Pedido',
            'fecha_entrega_estimada': 'Fecha Estimada de Entrega',
            'fecha_entrega_real': 'Fecha Real de Entrega',
            'estado': 'Estado del Pedido',
            'notas_seguimiento': 'Notas de Seguimiento',
        }
        
        help_texts = {
            'piezas': 'Selecciona las piezas específicas que se están pidiendo a este proveedor',
            'proveedor': 'Nombre del proveedor donde se pidió',
            'descripcion_piezas': 'Lista de piezas incluidas en este pedido',
            'numero_pedido': 'Número de orden o tracking del proveedor (opcional)',
            'fecha_entrega_estimada': 'Fecha comprometida por el proveedor',
            'fecha_entrega_real': 'Fecha en que realmente llegó (dejar vacío si aún no llega)',
            'estado': 'Estado actual del pedido',
        }
    
    def __init__(self, *args, **kwargs):
        """
        EXPLICACIÓN:
        Personalización del formulario.
        Filtra las piezas para mostrar SOLO las que fueron aceptadas por el cliente.
        
        ACTUALIZACIÓN NOVIEMBRE 2025:
        Configurar dropdown de proveedores predefinidos con lista de PROVEEDORES_CHOICES.
        """
        cotizacion = kwargs.pop('cotizacion', None)
        super().__init__(*args, **kwargs)
        
        # ✨ NUEVO: Configurar campo proveedor con lista predefinida (Noviembre 2025)
        self.fields['proveedor'].widget = forms.Select(
            choices=PROVEEDORES_CHOICES,
            attrs={
                'class': 'form-control form-select',
                'required': True,
            }
        )
        
        # NUEVO: Filtrar solo piezas aceptadas por el cliente
        if cotizacion:
            piezas_aceptadas = cotizacion.piezas_cotizadas.filter(aceptada_por_cliente=True)
            self.fields['piezas'].queryset = piezas_aceptadas
            self.fields['piezas'].label_from_instance = lambda obj: f"{obj.componente.nombre} × {obj.cantidad} (${obj.costo_total})"
        else:
            # Si no hay cotización, no mostrar ninguna pieza
            self.fields['piezas'].queryset = PiezaCotizada.objects.none()
        
        # Configurar fechas mínimas
        from datetime import date
        self.fields['fecha_pedido'].widget.attrs['max'] = date.today().isoformat()
        self.fields['fecha_entrega_estimada'].widget.attrs['min'] = date.today().isoformat()
        
        # Si es edición y el estado es "recibido" (incluye recibido, incorrecto, danado),
        # hacer obligatoria la fecha real ya que la pieza llegó físicamente
        from config.constants import ESTADOS_PIEZA_RECIBIDOS
        if self.instance and self.instance.pk and self.instance.estado in ESTADOS_PIEZA_RECIBIDOS:
            self.fields['fecha_entrega_real'].required = True
    
    def clean(self):
        """
        EXPLICACIÓN:
        Validaciones personalizadas.
        """
        cleaned_data = super().clean()
        fecha_pedido = cleaned_data.get('fecha_pedido')
        fecha_estimada = cleaned_data.get('fecha_entrega_estimada')
        fecha_real = cleaned_data.get('fecha_entrega_real')
        estado = cleaned_data.get('estado')
        
        # Validar que fecha estimada sea posterior a fecha de pedido
        if fecha_pedido and fecha_estimada:
            if fecha_estimada < fecha_pedido:
                raise ValidationError({
                    'fecha_entrega_estimada': '❌ La fecha estimada no puede ser anterior a la fecha de pedido'
                })
        
        # Si el estado es "recibido" (incluye recibido, incorrecto, danado), la fecha real es obligatoria
        from config.constants import ESTADOS_PIEZA_RECIBIDOS
        if estado in ESTADOS_PIEZA_RECIBIDOS and not fecha_real:
            raise ValidationError({
                'fecha_entrega_real': '❌ Debes indicar la fecha real de entrega si la pieza fue recibida (correcta, incorrecta o dañada)'
            })
        
        # Si hay fecha real, validar que sea posterior al pedido
        if fecha_pedido and fecha_real:
            if fecha_real < fecha_pedido:
                raise ValidationError({
                    'fecha_entrega_real': '❌ La fecha real de entrega no puede ser anterior a la fecha de pedido'
                })
        
        return cleaned_data


# ============================================================================
# FORMULARIOS PARA VENTA MOSTRADOR - FASE 3
# ============================================================================

class VentaMostradorForm(forms.ModelForm):
    """
    Formulario para crear/editar una Venta Mostrador asociada a una orden.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Este formulario permite registrar ventas directas sin diagnóstico previo:
    - Seleccionar paquete (premium/oro/plata/ninguno)
    - Agregar servicios adicionales (cambio pieza, limpieza, kit, reinstalación)
    - Cada servicio adicional tiene un campo de costo asociado
    
    CAMPOS INCLUIDOS:
    - paquete: Select con opciones de paquetes
    - incluye_cambio_pieza + costo_cambio_pieza: Checkbox + campo numérico
    - incluye_limpieza + costo_limpieza: Checkbox + campo numérico
    - incluye_kit_limpieza + costo_kit: Checkbox + campo numérico
    - incluye_reinstalacion_so + costo_reinstalacion: Checkbox + campo numérico
    - notas_adicionales: Textarea para observaciones
    """
    
    class Meta:
        model = VentaMostrador
        fields = [
            'paquete',
            'incluye_cambio_pieza',
            'costo_cambio_pieza',
            'incluye_limpieza',
            'costo_limpieza',
            'incluye_kit_limpieza',
            'costo_kit',
            'incluye_reinstalacion_so',
            'costo_reinstalacion',
            'incluye_respaldo',
            'costo_respaldo',
            'notas_adicionales',
        ]
        
        widgets = {
            'paquete': forms.Select(attrs={
                'class': 'form-control form-select',
                'id': 'id_paquete_venta',
            }),
            'incluye_cambio_pieza': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'onchange': 'toggleCambioPiezaCosto()',
            }),
            'costo_cambio_pieza': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
            }),
            'incluye_limpieza': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'onchange': 'toggleLimpiezaCosto()',
            }),
            'costo_limpieza': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
            }),
            'incluye_kit_limpieza': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'onchange': 'toggleKitCosto()',
            }),
            'costo_kit': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
            }),
            'incluye_reinstalacion_so': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'onchange': 'toggleReinstalacionCosto()',
            }),
            'costo_reinstalacion': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
            }),
            'incluye_respaldo': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'onchange': 'toggleRespaldoCosto()',
            }),
            'costo_respaldo': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
            }),
            'notas_adicionales': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Notas u observaciones adicionales sobre la venta...',
            }),
        }
        
        labels = {
            'paquete': 'Paquete de Servicio',
            'incluye_cambio_pieza': 'Incluye cambio de pieza',
            'costo_cambio_pieza': 'Costo de instalación',
            'incluye_limpieza': 'Incluye limpieza y mantenimiento',
            'costo_limpieza': 'Costo de limpieza',
            'incluye_kit_limpieza': 'Venta de kit de limpieza',
            'costo_kit': 'Costo del kit',
            'incluye_reinstalacion_so': 'Reinstalación de sistema operativo',
            'costo_reinstalacion': 'Costo de reinstalación',
            'incluye_respaldo': 'Respaldo de información',
            'costo_respaldo': 'Costo del respaldo',
            'notas_adicionales': 'Notas adicionales',
        }
        
        help_texts = {
            'paquete': 'Selecciona el paquete que desea el cliente',
            'incluye_cambio_pieza': 'Marca si incluye instalación de pieza comprada',
            'costo_cambio_pieza': 'Costo del servicio de instalación',
            'incluye_limpieza': 'Limpieza interna y externa del equipo',
            'costo_limpieza': 'Costo del servicio de limpieza',
            'incluye_kit_limpieza': 'Venta de kit de limpieza para el cliente',
            'costo_kit': 'Precio de venta del kit',
            'incluye_reinstalacion_so': 'Reinstalación de Windows u otro SO',
            'costo_reinstalacion': 'Costo del servicio de reinstalación',
            'incluye_respaldo': 'Respaldo de archivos, fotos, documentos del cliente',
            'costo_respaldo': 'Costo del servicio de respaldo',
            'notas_adicionales': 'Cualquier observación o detalle importante',
        }
    
    def clean(self):
        """
        Validaciones personalizadas del formulario.
        
        EXPLICACIÓN:
        Verifica que si un checkbox está marcado, su costo asociado sea mayor a 0.
        Por ejemplo: Si "incluye_cambio_pieza" = True, entonces "costo_cambio_pieza" > 0
        """
        cleaned_data = super().clean()
        
        # Validar cambio de pieza
        if cleaned_data.get('incluye_cambio_pieza'):
            if not cleaned_data.get('costo_cambio_pieza') or cleaned_data.get('costo_cambio_pieza') <= 0:
                raise ValidationError({
                    'costo_cambio_pieza': '❌ Si incluye cambio de pieza, el costo debe ser mayor a 0'
                })
        
        # Validar limpieza
        if cleaned_data.get('incluye_limpieza'):
            if not cleaned_data.get('costo_limpieza') or cleaned_data.get('costo_limpieza') <= 0:
                raise ValidationError({
                    'costo_limpieza': '❌ Si incluye limpieza, el costo debe ser mayor a 0'
                })
        
        # Validar kit de limpieza
        if cleaned_data.get('incluye_kit_limpieza'):
            if not cleaned_data.get('costo_kit') or cleaned_data.get('costo_kit') <= 0:
                raise ValidationError({
                    'costo_kit': '❌ Si incluye kit de limpieza, el costo debe ser mayor a 0'
                })
        
        # Validar reinstalación SO
        if cleaned_data.get('incluye_reinstalacion_so'):
            if not cleaned_data.get('costo_reinstalacion') or cleaned_data.get('costo_reinstalacion') <= 0:
                raise ValidationError({
                    'costo_reinstalacion': '❌ Si incluye reinstalación, el costo debe ser mayor a 0'
                })
        
        # Validar respaldo de información
        if cleaned_data.get('incluye_respaldo'):
            if not cleaned_data.get('costo_respaldo') or cleaned_data.get('costo_respaldo') <= 0:
                raise ValidationError({
                    'costo_respaldo': '❌ Si incluye respaldo de información, el costo debe ser mayor a 0'
                })
        
        return cleaned_data


class PiezaVentaMostradorForm(forms.ModelForm):
    """
    Formulario para agregar/editar piezas vendidas en mostrador.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Este formulario permite registrar piezas individuales vendidas además
    de los paquetes. Por ejemplo: RAM adicional, cables, accesorios, etc.
    
    CAMPOS INCLUIDOS:
    - componente: Select con autocompletado (opcional, del catálogo ScoreCard)
    - descripcion_pieza: Texto libre para describir la pieza
    - cantidad: Número de unidades vendidas
    - precio_unitario: Precio por unidad
    - notas: Observaciones adicionales
    
    NOTA: El subtotal se calcula automáticamente (cantidad × precio_unitario)
    """
    
    class Meta:
        model = PiezaVentaMostrador
        fields = [
            'componente',
            'descripcion_pieza',
            'cantidad',
            'precio_unitario',
            'notas',
        ]
        
        widgets = {
            'componente': forms.Select(attrs={
                'class': 'form-control form-select',
                'id': 'id_componente_pieza',
            }),
            'descripcion_pieza': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: RAM 8GB DDR4 Kingston, Cable HDMI 2m',
                'required': True,
            }),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'value': '1',
                'required': True,
                'onchange': 'calcularSubtotalPieza()',
            }),
            'precio_unitario': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '0.00',
                'required': True,
                'onchange': 'calcularSubtotalPieza()',
            }),
            'notas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Observaciones sobre la pieza vendida (opcional)',
            }),
        }
        
        labels = {
            'componente': 'Componente del catálogo (opcional)',
            'descripcion_pieza': 'Descripción de la pieza',
            'cantidad': 'Cantidad',
            'precio_unitario': 'Precio unitario',
            'notas': 'Notas',
        }
        
        help_texts = {
            'componente': 'Selecciona del catálogo si está disponible',
            'descripcion_pieza': 'Describe claramente qué pieza se vendió',
            'cantidad': 'Número de unidades vendidas',
            'precio_unitario': 'Precio por unidad (IVA incluido)',
            'notas': 'Cualquier observación adicional',
        }
    
    def clean_descripcion_pieza(self):
        """
        Validación del campo descripcion_pieza.
        
        EXPLICACIÓN:
        Asegura que la descripción no esté vacía y tenga al menos 3 caracteres.
        """
        descripcion = self.cleaned_data.get('descripcion_pieza', '').strip()
        
        if not descripcion:
            raise ValidationError('❌ La descripción de la pieza es obligatoria')
        
        if len(descripcion) < 3:
            raise ValidationError('❌ La descripción debe tener al menos 3 caracteres')
        
        return descripcion
    
    def clean_cantidad(self):
        """
        Validación del campo cantidad.
        
        EXPLICACIÓN:
        Asegura que la cantidad sea un número positivo mayor a 0.
        """
        cantidad = self.cleaned_data.get('cantidad')
        
        if cantidad is None or cantidad < 1:
            raise ValidationError('❌ La cantidad debe ser al menos 1')
        
        return cantidad
    
    def clean_precio_unitario(self):
        """
        Validación del campo precio_unitario.
        
        EXPLICACIÓN:
        Asegura que el precio sea un número positivo mayor a 0.
        """
        precio = self.cleaned_data.get('precio_unitario')
        
        if precio is None or precio <= 0:
            raise ValidationError('❌ El precio unitario debe ser mayor a 0')
        
        return precio


# ============================================================================
# FORMULARIOS RHITSO - FASE 3 (Módulo de Seguimiento Especializado)
# ============================================================================

"""
EXPLICACIÓN PARA PRINCIPIANTES - MÓDULO RHITSO:
===============================================
RHITSO es el módulo de seguimiento especializado para reparaciones de alta complejidad
(soldadura, reballing, etc.) que requieren ser enviadas a un centro externo.

Los siguientes formularios permiten:
1. Cambiar el estado RHITSO de una orden
2. Registrar incidencias/problemas durante el proceso
3. Resolver incidencias existentes
4. Editar el diagnóstico SIC y datos RHITSO

Estos formularios trabajan en conjunto con los signals de la Fase 2 para
mantener un historial automático de todos los cambios.
"""


class ActualizarEstadoRHITSOForm(forms.Form):
    """
    Formulario para cambiar el estado RHITSO de una orden.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Este formulario permite cambiar el estado de una orden que está en proceso
    RHITSO. Por ejemplo: de "DIAGNOSTICO_SIC" a "ENVIADO_A_RHITSO".
    
    ¿Qué hace especial este formulario?
    - Los estados disponibles son DINÁMICOS: se cargan desde la base de datos
    - Requiere observaciones obligatorias: para documentar por qué cambió
    - Opción de notificar al cliente: checkbox opcional
    
    ¿Cómo funciona con los signals?
    Cuando guardas un cambio de estado_rhitso en la orden, el signal
    automáticamente crea un registro en SeguimientoRHITSO. Este formulario
    solo captura la información necesaria para hacer el cambio.
    
    CAMPOS:
    - estado_rhitso: Seleccionar el nuevo estado (dropdown dinámico)
    - observaciones: Explicar por qué se hace el cambio (textarea obligatorio)
    - notificar_cliente: Checkbox opcional para enviar notificación
    """
    
    estado_rhitso = forms.ChoiceField(
        label="Nuevo Estado RHITSO",
        help_text="Selecciona el nuevo estado para la orden",
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True,
        })
    )
    
    observaciones = forms.CharField(
        label="Observaciones",
        help_text="Explica el motivo del cambio de estado (mínimo 10 caracteres)",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Ej: Equipo enviado a RHITSO para soldadura de componente X...',
            'required': True,
        })
    )
    
    fecha_envio_rhitso = forms.DateTimeField(
        label="Fecha de Envío a RHITSO (Manual)",
        help_text="⚠️ Ingresa manualmente la fecha y hora exacta cuando el equipo sea enviado físicamente a RHITSO. NO se registra automáticamente.",
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local',
            'placeholder': 'YYYY-MM-DD HH:MM',
        })
    )
    
    fecha_recepcion_rhitso = forms.DateTimeField(
        label="Fecha de Retorno a SIC (Manual)",
        help_text="⚠️ Ingresa manualmente la fecha y hora exacta cuando el equipo regrese de RHITSO a SIC. NO se registra automáticamente.",
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local',
            'placeholder': 'YYYY-MM-DD HH:MM',
        })
    )
    
    notificar_cliente = forms.BooleanField(
        label="¿Notificar al cliente?",
        help_text="Marca esta casilla si deseas que se notifique al cliente sobre este cambio",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        })
    )
    
    def __init__(self, *args, **kwargs):
        """
        EXPLICACIÓN DE __init__:
        ========================
        Este método se ejecuta cuando se crea el formulario.
        
        Aquí cargamos los estados ACTIVOS desde la base de datos para
        poblar el dropdown dinámicamente AGRUPADOS POR RESPONSABLE (OWNER).
        
        ¿Por qué agrupado?
        Facilita la selección visual al usuario. Los estados se muestran
        organizados por bloques según el responsable: SIC, RHITSO, CLIENTE, etc.
        
        ¿Por qué dinámico?
        Porque los estados pueden cambiar en el admin sin tocar código.
        Si agregas un nuevo estado, automáticamente aparecerá en el formulario.
        """
        super().__init__(*args, **kwargs)
        
        # Cargar estados activos desde la base de datos ordenados por owner y orden
        estados_activos = EstadoRHITSO.objects.filter(activo=True).order_by('owner', 'orden')
        
        # Agrupar estados por OWNER para crear optgroups
        # EXPLICACIÓN: Organizamos los estados en un diccionario donde:
        # - La clave es el OWNER (SIC, RHITSO, CLIENTE, etc.)
        # - El valor es una lista de tuplas (estado, etiqueta)
        from collections import defaultdict
        estados_por_owner = defaultdict(list)
        
        for estado in estados_activos:
            # Crear etiqueta con número de orden para mejor visualización
            etiqueta = f"{estado.orden}. {estado.estado}"
            estados_por_owner[estado.owner].append((estado.estado, etiqueta))
        
        # Definir orden de los bloques y sus etiquetas visuales
        # EXPLICACIÓN: Este orden determina cómo aparecen los bloques en el dropdown
        ORDEN_BLOQUES = [
            ('SIC', '🏢 BLOQUE SIC - Estados bajo responsabilidad de SIC'),
            ('RHITSO', '🔧 BLOQUE RHITSO - Estados de RHITSO'),
            ('CLIENTE', '👤 BLOQUE CLIENTE - Pendiente de Cliente'),
            ('COMPRAS', '🛒 BLOQUE COMPRAS - Esperando Compras'),
            ('CERRADO', '✅ CERRADO - Proceso Finalizado'),
        ]
        
        # Construir choices con optgroups
        # EXPLICACIÓN: choices es una lista que puede contener:
        # - Tuplas simples: (valor, etiqueta)
        # - Tuplas con sublista: (nombre_grupo, [(valor1, etiqueta1), (valor2, etiqueta2)])
        choices = [('', '--- Selecciona un estado ---')]
        
        for owner_code, owner_label in ORDEN_BLOQUES:
            if owner_code in estados_por_owner:
                # Agregar el grupo con sus estados
                choices.append((owner_label, estados_por_owner[owner_code]))
        
        self.fields['estado_rhitso'].choices = choices
    
    def clean_estado_rhitso(self):
        """
        Validación del campo estado_rhitso.
        
        EXPLICACIÓN:
        ============
        Verifica que el estado seleccionado realmente exista en la base de datos.
        
        ¿Por qué es necesario?
        Aunque el dropdown solo muestra estados válidos, alguien podría
        manipular el HTML y enviar un valor inválido. Esta validación
        lo previene.
        """
        estado_seleccionado = self.cleaned_data.get('estado_rhitso')
        
        if not estado_seleccionado:
            raise ValidationError('❌ Debes seleccionar un estado RHITSO válido')
        
        # Verificar que el estado existe en la BD
        try:
            EstadoRHITSO.objects.get(estado=estado_seleccionado, activo=True)
        except EstadoRHITSO.DoesNotExist:
            raise ValidationError(
                f'❌ El estado "{estado_seleccionado}" no existe o está inactivo'
            )
        
        return estado_seleccionado
    
    def clean_observaciones(self):
        """
        Validación del campo observaciones.
        
        EXPLICACIÓN:
        ============
        Asegura que el usuario escriba al menos 10 caracteres.
        
        ¿Por qué?
        Para tener un historial útil. "Ok" o "Cambio" no es información
        suficiente. Necesitamos contexto real sobre por qué cambió el estado.
        """
        observaciones = self.cleaned_data.get('observaciones', '').strip()
        
        if len(observaciones) < 10:
            raise ValidationError(
                '❌ Las observaciones deben tener al menos 10 caracteres. '
                'Proporciona más detalles sobre el cambio.'
            )
        
        return observaciones


class RegistrarIncidenciaRHITSOForm(forms.ModelForm):
    """
    Formulario para registrar una nueva incidencia con RHITSO.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Las "incidencias" son problemas que ocurren durante el proceso RHITSO.
    Por ejemplo:
    - RHITSO dañó un componente adicional
    - Retraso injustificado en la entrega
    - Pieza incorrecta instalada
    - Falta de comunicación
    
    Este formulario captura toda la información necesaria para documentar
    el problema y su impacto.
    
    ¿Qué pasa cuando se registra una incidencia crítica?
    El signal de la Fase 2 automáticamente registra un evento en el
    HistorialOrden con una alerta ⚠️ visible para todos.
    
    CAMPOS:
    - tipo_incidencia: Tipo de problema (desde catálogo)
    - titulo: Título breve del problema
    - descripcion_detallada: Descripción completa
    - impacto_cliente: Qué tan grave es para el cliente
    - prioridad: Qué tan urgente es resolverlo
    - costo_adicional: Costo extra generado (opcional)
    """
    
    class Meta:
        model = IncidenciaRHITSO
        fields = [
            'tipo_incidencia',
            'titulo',
            'descripcion_detallada',
            'impacto_cliente',
            'prioridad',
            'costo_adicional',
        ]
        
        widgets = {
            'tipo_incidencia': forms.Select(attrs={
                'class': 'form-select',
                'required': True,
            }),
            'titulo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Daño en placa madre durante desmontaje',
                'maxlength': 255,
                'required': True,
            }),
            'descripcion_detallada': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Describe detalladamente qué ocurrió, cuándo, y las consecuencias...',
                'required': True,
            }),
            'impacto_cliente': forms.Select(attrs={
                'class': 'form-select',
                'required': True,
            }),
            'prioridad': forms.Select(attrs={
                'class': 'form-select',
                'required': True,
            }),
            'costo_adicional': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0.01',
                'placeholder': '0.00',
            }),
        }
        
        labels = {
            'tipo_incidencia': 'Tipo de Incidencia',
            'titulo': 'Título de la Incidencia',
            'descripcion_detallada': 'Descripción Detallada',
            'impacto_cliente': 'Impacto al Cliente',
            'prioridad': 'Prioridad',
            'costo_adicional': 'Costo Adicional (MXN)',
        }
        
        help_texts = {
            'tipo_incidencia': 'Selecciona el tipo de problema que ocurrió',
            'titulo': 'Un título breve que describa el problema (máximo 255 caracteres)',
            'descripcion_detallada': 'Descripción completa del problema con todos los detalles',
            'impacto_cliente': '¿Qué tan grave es este problema para el cliente?',
            'prioridad': '¿Qué tan urgente es resolver este problema?',
            'costo_adicional': 'Costo extra generado por esta incidencia (dejar en 0 si no aplica)',
        }
    
    def __init__(self, *args, **kwargs):
        """
        EXPLICACIÓN DE __init__:
        ========================
        Personaliza el formulario al crearlo:
        - Solo muestra tipos de incidencia activos
        - Configura valores iniciales apropiados
        """
        super().__init__(*args, **kwargs)
        
        # Filtrar solo tipos de incidencia activos
        self.fields['tipo_incidencia'].queryset = TipoIncidenciaRHITSO.objects.filter(
            activo=True
        ).order_by('nombre')
        
        # Configurar choices para campos que usan constantes
        self.fields['impacto_cliente'].choices = IMPACTO_CLIENTE_CHOICES
        self.fields['prioridad'].choices = PRIORIDAD_CHOICES
        
        # Valor inicial para costo_adicional
        if not self.instance.pk:  # Si es un nuevo registro
            self.fields['costo_adicional'].initial = 0.00
    
    def clean_titulo(self):
        """
        Validación del campo titulo.
        
        EXPLICACIÓN:
        ============
        Asegura que el título tenga al menos 5 caracteres.
        
        ¿Por qué?
        Un título debe ser descriptivo. "Error" o "Mal" no es suficiente.
        Necesitamos títulos que identifiquen rápidamente el problema.
        """
        titulo = self.cleaned_data.get('titulo', '').strip()
        
        if len(titulo) < 5:
            raise ValidationError(
                '❌ El título debe tener al menos 5 caracteres. '
                'Sé más descriptivo sobre el problema.'
            )
        
        return titulo
    
    def clean_costo_adicional(self):
        """
        Validación del campo costo_adicional.
        
        EXPLICACIÓN:
        ============
        Asegura que el costo sea un número positivo (>= 0).
        No puede ser negativo.
        """
        costo = self.cleaned_data.get('costo_adicional')
        
        if costo is None:
            costo = 0.00
        
        if costo < 0:
            raise ValidationError(
                '❌ El costo adicional no puede ser negativo. '
                'Debe ser 0 o un número positivo.'
            )
        
        return costo


class ResolverIncidenciaRHITSOForm(forms.Form):
    """
    Formulario para resolver/cerrar una incidencia existente.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Cuando una incidencia se resuelve, necesitamos documentar:
    1. Qué acción se tomó para resolverla
    2. Si hubo algún costo adicional final
    
    Este formulario es simple pero importante para cerrar el ciclo de
    seguimiento de problemas.
    
    ¿Qué pasa al resolver una incidencia?
    El modelo tiene un método marcar_como_resuelta() que actualiza:
    - Estado → 'RESUELTA'
    - fecha_resolucion → ahora
    - resuelto_por → usuario actual
    - accion_tomada → lo que escribiste aquí
    
    CAMPOS:
    - accion_tomada: Descripción de cómo se resolvió (mínimo 20 caracteres)
    - costo_adicional_final: Costo final si cambió (opcional)
    """
    
    accion_tomada = forms.CharField(
        label="Acción Correctiva Tomada",
        help_text="Describe detalladamente cómo se resolvió la incidencia (mínimo 20 caracteres)",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Ej: Se reemplazó el componente dañado sin costo para el cliente. '
                          'RHITSO asumió la responsabilidad y entregó pieza nueva...',
            'required': True,
        })
    )
    
    costo_adicional_final = forms.DecimalField(
        label="Costo Adicional Final (MXN)",
        help_text="Costo final si cambió desde el registro inicial (opcional)",
        required=False,
        min_value=0,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0',
            'step': '0.01',
            'placeholder': '0.00',
        })
    )
    
    def clean_accion_tomada(self):
        """
        Validación del campo accion_tomada.
        
        EXPLICACIÓN:
        ============
        Asegura que se proporcione una descripción completa (mínimo 20 caracteres).
        
        ¿Por qué 20 caracteres?
        Para documentar adecuadamente la resolución. Necesitamos saber:
        - Qué se hizo exactamente
        - Quién fue responsable
        - Si hubo algún costo o compensación
        
        "Se arregló" no es suficiente información.
        """
        accion = self.cleaned_data.get('accion_tomada', '').strip()
        
        if len(accion) < 20:
            raise ValidationError(
                '❌ La descripción de la acción tomada debe tener al menos 20 caracteres. '
                'Proporciona detalles completos sobre cómo se resolvió la incidencia.'
            )
        
        return accion


class EditarDiagnosticoSICForm(forms.Form):
    """
    Formulario para editar el diagnóstico SIC y datos relacionados con RHITSO.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Este formulario es especial porque maneja campos de DOS modelos diferentes:
    1. DetalleEquipo (diagnostico_sic)
    2. OrdenServicio (motivo_rhitso, descripcion_rhitso, etc.)
    
    ¿Por qué no usar ModelForm?
    Porque ModelForm trabaja con UN solo modelo. Aquí necesitamos editar
    campos de dos modelos al mismo tiempo. Por eso usamos Form (sin Model).
    
    ¿Cuándo se usa este formulario?
    Cuando el técnico de SIC hace el diagnóstico inicial y determina que
    el equipo necesita ir a RHITSO. Aquí documenta:
    - El diagnóstico técnico completo
    - Por qué necesita RHITSO (reballing, soldadura, etc.)
    - Qué tan complejo es
    - Quién hizo el diagnóstico
    
    CAMPOS:
    - diagnostico_sic: Diagnóstico técnico del equipo (DetalleEquipo)
    - motivo_rhitso: Por qué necesita RHITSO (OrdenServicio)
    - descripcion_rhitso: Descripción detallada del problema (OrdenServicio)
    - complejidad_estimada: Qué tan complejo es (OrdenServicio)
    - tecnico_diagnostico: Quién hizo el diagnóstico (OrdenServicio)
    """
    
    diagnostico_sic = forms.CharField(
        label="Diagnóstico SIC",
        help_text="Diagnóstico técnico completo realizado por SIC",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Ej: Equipo no enciende. Se detectó problema en chip gráfico. '
                          'Requiere reballing para reparación...',
            'required': True,
        })
    )
    
    motivo_rhitso = forms.ChoiceField(
        label="Motivo RHITSO",
        help_text="Razón por la cual se envía a RHITSO",
        choices=MOTIVO_RHITSO_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True,
        })
    )
    
    descripcion_rhitso = forms.CharField(
        label="Descripción Detallada RHITSO",
        help_text="Descripción completa del trabajo a realizar en RHITSO",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Ej: Se requiere reballing del chip gráfico GTX 1650. '
                          'Cliente autorizado presupuesto de $1500...',
            'required': True,
        })
    )
    
    complejidad_estimada = forms.ChoiceField(
        label="Complejidad Estimada",
        help_text="Nivel de complejidad del trabajo",
        choices=COMPLEJIDAD_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True,
        })
    )
    
    tecnico_diagnostico = forms.ModelChoiceField(
        label="Técnico que Realizó el Diagnóstico",
        help_text="Técnico responsable del diagnóstico SIC",
        queryset=Empleado.objects.filter(activo=True).order_by('nombre_completo'),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True,
        })
    )
    
    def clean_diagnostico_sic(self):
        """
        Validación del campo diagnostico_sic.
        
        EXPLICACIÓN:
        ============
        Asegura que el diagnóstico tenga contenido sustancial (mínimo 20 caracteres).
        
        ¿Por qué?
        El diagnóstico es crítico para que RHITSO entienda qué hacer.
        Necesita información técnica detallada, no solo "Está malo".
        """
        diagnostico = self.cleaned_data.get('diagnostico_sic', '').strip()
        
        if len(diagnostico) < 20:
            raise ValidationError(
                '❌ El diagnóstico debe tener al menos 20 caracteres. '
                'Proporciona un análisis técnico detallado del problema.'
            )
        
        return diagnostico
    
    def clean_descripcion_rhitso(self):
        """
        Validación del campo descripcion_rhitso.
        
        EXPLICACIÓN:
        ============
        Asegura que la descripción para RHITSO sea completa (mínimo 15 caracteres).
        
        ¿Por qué?
        RHITSO necesita instrucciones claras sobre qué trabajo realizar.
        "Reballing" no es suficiente. Necesitan saber QUÉ componente,
        si está autorizado, presupuesto, etc.
        """
        descripcion = self.cleaned_data.get('descripcion_rhitso', '').strip()
        
        if len(descripcion) < 15:
            raise ValidationError(
                '❌ La descripción RHITSO debe tener al menos 15 caracteres. '
                'Proporciona detalles completos del trabajo a realizar.'
            )
        
        return descripcion
