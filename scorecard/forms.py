"""
Formularios para el Score Card
"""
from django import forms
from django.core.exceptions import ValidationError
from .models import Incidencia, EvidenciaIncidencia, CategoriaIncidencia, ComponenteEquipo
from inventario.models import Empleado, Sucursal


class IncidenciaForm(forms.ModelForm):
    """
    Formulario para crear y editar incidencias
    Con widgets de Bootstrap y validaciones personalizadas
    
    NOTA: El campo 'estado' se excluye del formulario ya que se maneja automáticamente:
    - Nueva incidencia: Siempre inicia como "Abierta"
    - Al enviar notificación manual: Cambia automáticamente a "En Revisión"
    - Para cambios manuales de estado, usar el formulario específico "Cambiar Estado"
    """
    
    class Meta:
        model = Incidencia
        fields = [
            'fecha_deteccion',
            'tipo_equipo',
            'marca',
            'modelo',
            'numero_serie',
            'numero_orden',
            'servicio_realizado',
            'sucursal',
            'area_detectora',
            'tecnico_responsable',
            'area_tecnico',
            'inspector_calidad',
            'tipo_incidencia',
            'categoria_fallo',
            'grado_severidad',
            'componente_afectado',
            'descripcion_incidencia',
            'acciones_tomadas',
            'causa_raiz',
            # 'estado',  # EXCLUIDO: Se maneja automáticamente
            'es_reincidencia',
            'incidencia_relacionada',
        ]
        
        widgets = {
            'fecha_deteccion': forms.DateInput(
                attrs={
                    'class': 'form-control',
                    'type': 'date',
                    'placeholder': 'Fecha de detección'
                },
                format='%Y-%m-%d'  # Formato correcto para input type="date"
            ),
            'tipo_equipo': forms.Select(
                attrs={
                    'class': 'form-select',
                    'id': 'id_tipo_equipo'
                }
            ),
            'marca': forms.Select(
                attrs={
                    'class': 'form-select',
                    'id': 'id_marca'
                }
            ),
            'modelo': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Modelo del equipo (opcional)'
                }
            ),
            'numero_serie': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Número de serie del equipo (Service Tag)',
                    'id': 'id_numero_serie',
                    'autocomplete': 'off'
                }
            ),
            'numero_orden': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Número de orden interno (opcional)',
                    'autocomplete': 'off'
                }
            ),
            'servicio_realizado': forms.Select(
                attrs={
                    'class': 'form-select',
                    'id': 'id_servicio_realizado'
                }
            ),
            'sucursal': forms.Select(
                attrs={
                    'class': 'form-select',
                    'id': 'id_sucursal'
                }
            ),
            'area_detectora': forms.Select(
                attrs={
                    'class': 'form-select',
                    'id': 'id_area_detectora'
                }
            ),
            'tecnico_responsable': forms.Select(
                attrs={
                    'class': 'form-select',
                    'id': 'id_tecnico_responsable'
                }
            ),
            'area_tecnico': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'id': 'id_area_tecnico',
                    'readonly': 'readonly',
                    'placeholder': 'Se completa automáticamente al seleccionar técnico'
                }
            ),
            'inspector_calidad': forms.Select(
                attrs={
                    'class': 'form-select',
                    'id': 'id_inspector_calidad'
                }
            ),
            'tipo_incidencia': forms.Select(
                attrs={
                    'class': 'form-select'
                }
            ),
            'categoria_fallo': forms.Select(
                attrs={
                    'class': 'form-select'
                }
            ),
            'grado_severidad': forms.Select(
                attrs={
                    'class': 'form-select'
                }
            ),
            'componente_afectado': forms.Select(
                attrs={
                    'class': 'form-select',
                    'id': 'id_componente_afectado'
                }
            ),
            'descripcion_incidencia': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 4,
                    'placeholder': 'Describe detalladamente la incidencia detectada...'
                }
            ),
            'acciones_tomadas': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 3,
                    'placeholder': 'Acciones correctivas realizadas (opcional)'
                }
            ),
            'causa_raiz': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 2,
                    'placeholder': 'Análisis de causa raíz (opcional)'
                }
            ),
            # 'estado': Campo excluido del formulario (se maneja automáticamente)
            'es_reincidencia': forms.CheckboxInput(
                attrs={
                    'class': 'form-check-input',
                    'id': 'id_es_reincidencia'
                }
            ),
            'incidencia_relacionada': forms.Select(
                attrs={
                    'class': 'form-select',
                    'id': 'id_incidencia_relacionada'
                }
            ),
        }
        
        labels = {
            'fecha_deteccion': 'Fecha de Detección',
            'tipo_equipo': 'Tipo de Equipo',
            'marca': 'Marca',
            'modelo': 'Modelo',
            'numero_serie': 'Número de Serie',
            'servicio_realizado': 'Servicio Realizado',
            'sucursal': 'Sucursal',
            'area_detectora': 'Área que Detectó',
            'tecnico_responsable': 'Técnico/Personal responsable',
            'area_tecnico': 'Área del Técnico',
            'inspector_calidad': 'Inspector de Calidad',
            'tipo_incidencia': 'Tipo de Incidencia',
            'categoria_fallo': 'Categoría del Fallo',
            'grado_severidad': 'Grado de Severidad',
            'componente_afectado': 'Componente Afectado',
            'descripcion_incidencia': 'Descripción de la Incidencia',
            'acciones_tomadas': 'Acciones Tomadas',
            'causa_raiz': 'Causa Raíz',
            # 'estado': Campo excluido del formulario
            'es_reincidencia': '¿Es una reincidencia?',
            'incidencia_relacionada': 'Incidencia Relacionada',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Configurar formato de fecha para input type="date" (yyyy-MM-dd)
        self.fields['fecha_deteccion'].input_formats = ['%Y-%m-%d']
        
        # Filtrar solo empleados activos
        self.fields['tecnico_responsable'].queryset = Empleado.objects.filter(activo=True)
        
        # Filtrar solo empleados activos del área de Calidad para inspector
        self.fields['inspector_calidad'].queryset = Empleado.objects.filter(
            activo=True,
            area__icontains='calidad'  # Solo empleados del área de Calidad
        )
        
        # Filtrar solo categorías activas
        self.fields['tipo_incidencia'].queryset = CategoriaIncidencia.objects.filter(activo=True)
        
        # Filtrar solo componentes activos
        self.fields['componente_afectado'].queryset = ComponenteEquipo.objects.filter(activo=True)
        self.fields['componente_afectado'].required = False
        
        # Filtrar solo sucursales activas
        self.fields['sucursal'].queryset = Sucursal.objects.filter(activa=True)
        
        # Filtrar incidencias para reincidencia (solo abiertas o en revisión)
        self.fields['incidencia_relacionada'].queryset = Incidencia.objects.filter(
            estado__in=['abierta', 'en_revision']
        ).order_by('-fecha_registro')[:50]  # Últimas 50
        self.fields['incidencia_relacionada'].required = False
        
        # Hacer opcional causa_raiz
        self.fields['causa_raiz'].required = False
        self.fields['acciones_tomadas'].required = False
        self.fields['modelo'].required = False
    
    def clean_numero_serie(self):
        """
        Validar que el número de serie no esté vacío
        """
        numero_serie = self.cleaned_data.get('numero_serie', '').strip()
        if not numero_serie:
            raise ValidationError('El número de serie es obligatorio.')
        return numero_serie.upper()  # Convertir a mayúsculas para consistencia
    
    def clean(self):
        """
        Validaciones adicionales del formulario
        """
        cleaned_data = super().clean()
        
        # Validar que técnico e inspector sean diferentes
        tecnico = cleaned_data.get('tecnico_responsable')
        inspector = cleaned_data.get('inspector_calidad')
        
        if tecnico and inspector and tecnico == inspector:
            raise ValidationError(
                'El técnico responsable y el inspector de calidad deben ser personas diferentes.'
            )
        
        # Validar que si es reincidencia, tenga incidencia relacionada
        es_reincidencia = cleaned_data.get('es_reincidencia')
        incidencia_relacionada = cleaned_data.get('incidencia_relacionada')
        
        if es_reincidencia and not incidencia_relacionada:
            self.add_error(
                'incidencia_relacionada',
                'Si es una reincidencia, debes seleccionar la incidencia original.'
            )
        
        return cleaned_data


class EvidenciaIncidenciaForm(forms.ModelForm):
    """
    Formulario para subir evidencias (imágenes)
    
    NOTA: Para subir múltiples archivos, se debe usar el atributo 
    'multiple' en el HTML del template directamente, no en el widget.
    La vista debe manejar request.FILES.getlist('imagenes') para 
    procesar múltiples archivos.
    """
    
    class Meta:
        model = EvidenciaIncidencia
        fields = ['imagen', 'descripcion']
        
        widgets = {
            'imagen': forms.FileInput(
                attrs={
                    'class': 'form-control',
                    'accept': 'image/*'
                    # NO incluir 'multiple': True aquí - FileInput no lo soporta
                    # Se debe agregar en el HTML del template si se necesita
                }
            ),
            'descripcion': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Descripción breve de la evidencia (opcional)'
                }
            ),
        }
    
    def clean_imagen(self):
        """
        Validar tamaño y tipo de imagen
        """
        imagen = self.cleaned_data.get('imagen')
        
        if imagen:
            # Validar tamaño (máximo 5MB)
            if imagen.size > 5 * 1024 * 1024:
                raise ValidationError('La imagen no debe superar los 5MB.')
            
            # Validar tipo de archivo
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            if hasattr(imagen, 'content_type') and imagen.content_type not in allowed_types:
                raise ValidationError('Solo se permiten imágenes JPG, PNG, GIF o WebP.')
        
        return imagen


class CambiarEstadoIncidenciaForm(forms.Form):
    """
    Formulario para cambiar el estado de una incidencia manualmente
    
    ESTADOS PERMITIDOS:
    - 'en_revision': Para casos excepcionales donde se necesite cambiar sin enviar notificación
    - 'reincidente': Para marcar incidencias reincidentes
    
    NOTAS:
    - El estado 'abierta' se asigna automáticamente al crear la incidencia
    - El estado 'en_revision' normalmente se asigna al enviar notificación manual
    - El estado 'cerrada' se gestiona mediante el formulario de cierre específico
    """
    
    # Solo permitimos estos estados para cambio manual
    ESTADOS_PERMITIDOS = [
        ('en_revision', 'En Revisión'),
        ('reincidente', 'Reincidente'),
    ]
    
    estado = forms.ChoiceField(
        choices=ESTADOS_PERMITIDOS,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Nuevo Estado'
    )
    notas = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Notas adicionales sobre el cambio de estado (opcional)'
        }),
        label='Notas'
    )


class MarcarNoAtribuibleForm(forms.Form):
    """
    Formulario para marcar una incidencia como NO atribuible al técnico
    Requiere justificación obligatoria
    """
    justificacion = forms.CharField(
        label='Justificación',
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Explica por qué esta incidencia NO es atribuible al técnico responsable...\nEjemplo: El cliente rechazó una pieza que no fue reemplazada en el servicio.'
        }),
        help_text='Explica claramente por qué no se atribuye al técnico'
    )
    
    def clean_justificacion(self):
        """
        Validar que la justificación tenga contenido significativo
        """
        justificacion = self.cleaned_data.get('justificacion', '').strip()
        
        if len(justificacion) < 20:
            raise ValidationError('La justificación debe tener al menos 20 caracteres.')
        
        return justificacion


class CerrarIncidenciaForm(forms.Form):
    """
    Formulario para cerrar una incidencia
    Requiere información de cierre
    """
    acciones_tomadas = forms.CharField(
        label='Acciones Correctivas Tomadas',
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Describe las acciones correctivas realizadas para resolver esta incidencia...'
        })
    )
    causa_raiz = forms.CharField(
        label='Causa Raíz (Análisis)',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Análisis de la causa raíz del problema (opcional pero recomendado)'
        })
    )
    
    def clean_acciones_tomadas(self):
        """
        Validar que las acciones tomadas tengan contenido
        """
        acciones = self.cleaned_data.get('acciones_tomadas', '').strip()
        
        if len(acciones) < 20:
            raise ValidationError('Las acciones tomadas deben tener al menos 20 caracteres.')
        
        return acciones
