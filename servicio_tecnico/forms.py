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
from .models import OrdenServicio, DetalleEquipo, ReferenciaGamaEquipo
from inventario.models import Sucursal, Empleado
from config.constants import TIPO_EQUIPO_CHOICES, MARCAS_EQUIPOS


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
    
    marca = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: Dell, HP, Lenovo',
            'required': True,
            'list': 'marcas-list',  # Para autocompletar
        }),
        label="Marca del Equipo",
        help_text="Marca del equipo (campo obligatorio)"
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
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: OC-2025-001, 12345',
            'required': True,
        }),
        label="Número de Orden del Cliente",
        help_text="Número de orden interno del cliente (obligatorio)"
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
                tiene_cargador=self.cleaned_data.get('tiene_cargador', False),
                numero_serie_cargador=self.cleaned_data.get('numero_serie_cargador', ''),
                equipo_enciende=self.cleaned_data.get('equipo_enciende', True),
                falla_principal='',  # Se llenará después en el diagnóstico
                gama='media',  # Valor por defecto, se calculará después si hay referencias
            )
            
            # Intentar calcular la gama automáticamente
            gama_calculada = ReferenciaGamaEquipo.obtener_gama(
                self.cleaned_data['marca'],
                self.cleaned_data.get('modelo', '')
            )
            if gama_calculada:
                detalle.gama = gama_calculada
            
            detalle.save()
        
        return orden
    
    def get_marcas_list(self):
        """
        EXPLICACIÓN:
        Método auxiliar para obtener la lista de marcas predefinidas
        desde las constantes. Se usa en el template para el autocompletar.
        """
        return MARCAS_EQUIPOS
