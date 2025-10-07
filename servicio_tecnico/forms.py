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
)
from inventario.models import Sucursal, Empleado
from config.constants import TIPO_EQUIPO_CHOICES, MARCAS_EQUIPOS, TIPO_IMAGEN_CHOICES


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
            'fecha_inicio_diagnostico': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'fecha_fin_diagnostico': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'fecha_inicio_reparacion': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'fecha_fin_reparacion': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
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
        fields = ['estado', 'tecnico_asignado_actual']
        
        widgets = {
            'estado': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
            'tecnico_asignado_actual': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
        }
        
        labels = {
            'estado': 'Nuevo Estado',
            'tecnico_asignado_actual': 'Técnico Asignado',
        }
        
        help_texts = {
            'estado': 'Selecciona el nuevo estado de la orden',
            'tecnico_asignado_actual': 'Técnico responsable de la orden',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrar solo empleados activos
        self.fields['tecnico_asignado_actual'].queryset = Empleado.objects.filter(activo=True)


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
        help_text='Puedes seleccionar múltiples imágenes (máximo 30, 6MB cada una)',
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
