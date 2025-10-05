from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import Producto, Movimiento, Sucursal, Empleado

class EmpleadoSelectWidget(forms.Select):
    """Widget personalizado para mostrar empleados con información de área"""
    
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value and hasattr(value, 'value'):
            # Si value es un ModelChoiceIteratorValue, extraer el valor real
            actual_value = value.value
        else:
            actual_value = value
            
        if actual_value:
            try:
                # Obtener el empleado y agregar el área como atributo data
                empleado = Empleado.objects.get(pk=actual_value)
                if option.get('attrs') is None:
                    option['attrs'] = {}
                option['attrs']['data-area'] = empleado.area
            except (Empleado.DoesNotExist, ValueError, TypeError):
                pass
        return option

class ProductoForm(forms.ModelForm):
    """
    Formulario para crear y editar productos con todos los campos necesarios
    """
    class Meta:
        model = Producto
        fields = [
            'nombre', 'descripcion', 'categoria', 'tipo',
            'cantidad', 'stock_minimo', 'ubicacion',
            'proveedor', 'costo_unitario', 'estado_calidad',
            # Campo para objetos únicos
            'es_objeto_unico',
            # Nuevos campos fraccionarios
            'es_fraccionable', 'unidad_base', 'cantidad_unitaria', 
            'cantidad_actual', 'cantidad_minima_alerta'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Ej: ROLLO DE ETIQUETAS CHICO'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3, 
                'placeholder': 'Descripción detallada del producto'
            }),
            'categoria': forms.Select(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control', 
                'min': 0,
                'placeholder': 'Cantidad actual en stock'
            }),
            'stock_minimo': forms.NumberInput(attrs={
                'class': 'form-control', 
                'min': 0,
                'placeholder': 'Cantidad mínima para alerta',
                'id': 'id_stock_minimo'
            }),
            'ubicacion': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Estante A-2, Almacén Principal'
            }),
            'proveedor': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del proveedor'
            }),
            'costo_unitario': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'estado_calidad': forms.Select(attrs={'class': 'form-control'}),
            # Widget para objetos únicos
            'es_objeto_unico': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'id_es_objeto_unico',
                'onchange': 'toggleStockMinimoUnico()'
            }),
            # Nuevos widgets para campos fraccionarios
            'es_fraccionable': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'id_es_fraccionable'
            }),
            'unidad_base': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: ml, litros, kg, gramos',
                'id': 'id_unidad_base'
            }),
            'cantidad_unitaria': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': 'Ej: 1000 (ml por botella)',
                'id': 'id_cantidad_unitaria'
            }),
            'cantidad_actual': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Cantidad disponible actualmente',
                'id': 'id_cantidad_actual'
            }),
            'cantidad_minima_alerta': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Alerta cuando esté por debajo de este nivel',
                'id': 'id_cantidad_minima_alerta'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Configurar campos fraccionarios como opcionales inicialmente
        self.fields['unidad_base'].required = False
        self.fields['cantidad_unitaria'].required = False
        self.fields['cantidad_actual'].required = False
        self.fields['cantidad_minima_alerta'].required = False
        
        # Agregar ayuda contextual
        self.fields['es_fraccionable'].help_text = "Marque si el producto se puede consumir en porciones (ej: líquidos, granulados)"
        self.fields['unidad_base'].help_text = "Unidad de medida base (ml, litros, gramos, kg)"
        self.fields['cantidad_unitaria'].help_text = "Cantidad que contiene cada unidad completa (ej: 1000ml por botella)"
        self.fields['cantidad_actual'].help_text = "Cantidad disponible en la unidad abierta actualmente"
        self.fields['cantidad_minima_alerta'].help_text = "Nivel mínimo antes de mostrar alerta de stock bajo"

class MovimientoForm(forms.ModelForm):
    """
    Formulario para registrar envíos por mensajería con trazabilidad completa
    """
    class Meta:
        model = Movimiento
        fields = [
            'producto', 'tipo', 'cantidad', 'motivo',
            'sucursal_destino', 'observaciones', 'numero_proyecto',
            # Solo campos con empleados
            'usuario_registro_empleado', 'empleado_destinatario'
        ]
        widgets = {
            'producto': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': 'Cantidad a enviar'
            }),
            'motivo': forms.Select(attrs={'class': 'form-control'}),
            'sucursal_destino': forms.Select(attrs={
                'class': 'form-control'
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Observaciones adicionales (opcional)'
            }),
            'numero_proyecto': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: GUIA123456789 - Número de guía de mensajería'
            }),
            # Widgets para empleados
            'usuario_registro_empleado': forms.Select(attrs={
                'class': 'form-control'
            }),
            'empleado_destinatario': EmpleadoSelectWidget(attrs={
                'class': 'form-control'
            }),
        }
        
        labels = {
            'numero_proyecto': 'Número de Guía de Mensajería',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Configurar campos obligatorios para envíos por mensajería
        self.fields['sucursal_destino'].required = True
        self.fields['usuario_registro_empleado'].required = True
        self.fields['empleado_destinatario'].required = True
        self.fields['numero_proyecto'].required = True  # Número de guía obligatorio
        
        # Filtrar solo sucursales activas
        self.fields['sucursal_destino'].queryset = Sucursal.objects.filter(activa=True)
        self.fields['sucursal_destino'].empty_label = "Seleccionar sucursal de destino *"
        
        # Configurar campos de empleados con atributos de área
        empleados_activos = Empleado.objects.filter(activo=True)
        
        # Para empleado que registra
        self.fields['usuario_registro_empleado'].queryset = empleados_activos
        self.fields['usuario_registro_empleado'].empty_label = "Seleccionar empleado que registra *"
        
        # Para empleado destinatario - agregar atributos de área mediante JavaScript personalizado
        self.fields['empleado_destinatario'].queryset = empleados_activos
        self.fields['empleado_destinatario'].empty_label = "Seleccionar empleado destinatario *"
        
        # Actualizar label del número de guía
        self.fields['numero_proyecto'].label = 'Número de Guía de Mensajería'
        self.fields['numero_proyecto'].help_text = 'Número de seguimiento proporcionado por la empresa de mensajería'
        
        # Observaciones sigue siendo opcional
        self.fields['observaciones'].required = False

class SucursalForm(forms.ModelForm):
    """
    Formulario para crear y editar sucursales
    """
    class Meta:
        model = Sucursal
        fields = [
            'codigo', 'nombre', 
            'direccion', 'ciudad', 'estado_provincia',
            'responsable', 'telefono', 'email', 
            'activa', 'observaciones'
        ]
        widgets = {
            'codigo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Código único (se genera automáticamente si se deja vacío)'
            }),
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre de la sucursal'
            }),
            'direccion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Dirección completa'
            }),
            'ciudad': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ciudad'
            }),
            'estado_provincia': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Estado o provincia'
            }),
            'responsable': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del encargado/responsable'
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Teléfono de contacto'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'correo@ejemplo.com'
            }),
            'activa': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Observaciones adicionales (opcional)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hacer algunos campos opcionales
        self.fields['codigo'].required = False
        self.fields['direccion'].required = False
        self.fields['ciudad'].required = False
        self.fields['estado_provincia'].required = False
        self.fields['responsable'].required = False
        self.fields['telefono'].required = False
        self.fields['email'].required = False
        self.fields['observaciones'].required = False

class MovimientoRapidoForm(forms.ModelForm):
    """
    Formulario simplificado para movimientos rápidos usando scanner QR
    """
    codigo_qr = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'INV202509231914... (scanner o manual)',
            'id': 'codigo_qr_input',
            'autocomplete': 'off',
            'style': 'text-transform: uppercase;'  # Auto-convertir a mayúsculas mientras escribe
        }),
        help_text="Use el scanner de cámara o escriba el código manualmente. No importa si usa mayúsculas o minúsculas.",
        label="Código de Barras/QR del Producto"
    )
    
    class Meta:
        model = Movimiento
        fields = [
            'tipo', 'cantidad', 'motivo', 'sucursal_destino',
            'empleado_destinatario', 'usuario_registro_empleado', 'observaciones'
        ]
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': 'Cantidad'
            }),
            'motivo': forms.Select(attrs={'class': 'form-control'}),
            'sucursal_destino': forms.Select(attrs={
                'class': 'form-control'
            }),
            'empleado_destinatario': EmpleadoSelectWidget(attrs={
                'class': 'form-control'
            }),
            'usuario_registro_empleado': forms.Select(attrs={
                'class': 'form-control'
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Observaciones adicionales (opcional)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Configurar campos de empleados con empleados activos
        empleados_activos = Empleado.objects.filter(activo=True)
        sucursales_activas = Sucursal.objects.all()
        
        # Configurar campos obligatorios
        self.fields['tipo'].required = True
        self.fields['cantidad'].required = True
        self.fields['motivo'].required = True
        self.fields['sucursal_destino'].required = True
        self.fields['usuario_registro_empleado'].required = True
        
        # Para sucursal destino
        self.fields['sucursal_destino'].queryset = sucursales_activas
        self.fields['sucursal_destino'].empty_label = "Seleccionar sucursal destino *"
        
        # Para empleado destinatario con widget personalizado para área
        self.fields['empleado_destinatario'].queryset = empleados_activos
        self.fields['empleado_destinatario'].empty_label = "Seleccionar empleado destinatario *"
        self.fields['empleado_destinatario'].required = True
        
        # Para empleado que registra
        self.fields['usuario_registro_empleado'].queryset = empleados_activos
        self.fields['usuario_registro_empleado'].empty_label = "Seleccionar empleado que registra *"
        
        # Observaciones no requeridas
        self.fields['observaciones'].required = False
    
    def clean_codigo_qr(self):
        """
        Validar que el código QR existe con limpieza de caracteres invisibles
        """
        import re
        codigo_raw = self.cleaned_data['codigo_qr']
        
        # Limpiar código de caracteres invisibles y problemáticos del scanner
        codigo = re.sub(r'[\r\n\t\x00-\x1f\x7f-\x9f]', '', codigo_raw)  # Remover caracteres de control
        codigo = codigo.strip()  # Remover espacios al inicio y final
        codigo = re.sub(r'\s+', '', codigo)  # Remover espacios internos
        
        if not codigo:
            raise forms.ValidationError(f"Código QR inválido (solo contenía caracteres invisibles)")
        
        # Búsqueda insensible a mayúsculas/minúsculas
        try:
            producto = Producto.objects.get(codigo_qr__iexact=codigo)
            return codigo  # Devolver el código limpio
        except Producto.DoesNotExist:
            raise forms.ValidationError("Código QR no encontrado en el inventario")
    
    def save(self, commit=True):
        """
        Asignar automáticamente el producto basado en el código QR
        """
        movimiento = super().save(commit=False)
        codigo_qr = self.cleaned_data['codigo_qr']
        movimiento.producto = Producto.objects.get(codigo_qr=codigo_qr)
        
        if commit:
            movimiento.save()
        return movimiento


class EmpleadoForm(forms.ModelForm):
    """
    Formulario para crear y editar empleados
    Incluye correo electrónico, asignación de sucursal y jefe directo
    """
    class Meta:
        model = Empleado
        fields = ['nombre_completo', 'cargo', 'area', 'email', 'foto_perfil', 'sucursal', 'jefe_directo', 'activo']
        widgets = {
            'nombre_completo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Juan Pérez López'
            }),
            'cargo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Técnico de Laboratorio'
            }),
            'area': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Laboratorio, Oficina, Almacén'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: juan.perez@empresa.com'
            }),
            'foto_perfil': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
                'id': 'id_foto_perfil'
            }),
            'sucursal': forms.Select(attrs={
                'class': 'form-control'
            }),
            'jefe_directo': forms.Select(attrs={
                'class': 'form-control'
            }),
            'activo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        """
        Inicialización del formulario con filtros personalizados
        """
        super().__init__(*args, **kwargs)
        
        # Filtrar solo sucursales activas
        self.fields['sucursal'].queryset = Sucursal.objects.filter(activa=True)
        
        # Filtrar solo empleados activos para jefe directo
        # Excluir al empleado actual para que no pueda ser su propio jefe
        jefe_queryset = Empleado.objects.filter(activo=True).order_by('nombre_completo')
        if self.instance and self.instance.pk:
            jefe_queryset = jefe_queryset.exclude(pk=self.instance.pk)
        self.fields['jefe_directo'].queryset = jefe_queryset
        
        # Hacer campos opcionales
        self.fields['sucursal'].required = False
        self.fields['email'].required = False
        self.fields['jefe_directo'].required = False
        
        # Agregar texto de ayuda
        self.fields['jefe_directo'].help_text = 'Selecciona el jefe directo de este empleado en la jerarquía organizacional'
    
    def clean_email(self):
        """
        Validar que el email sea único si se proporciona
        """
        email = self.cleaned_data.get('email')
        
        if email:
            # Verificar si ya existe otro empleado con ese email
            empleados_con_email = Empleado.objects.filter(email=email)
            
            # Si estamos editando, excluir el empleado actual
            if self.instance.pk:
                empleados_con_email = empleados_con_email.exclude(pk=self.instance.pk)
            
            if empleados_con_email.exists():
                raise forms.ValidationError(
                    'Ya existe un empleado registrado con este correo electrónico.'
                )
        
        return email


class MovimientoFraccionarioForm(forms.ModelForm):
    """
    Formulario especializado para movimientos fraccionarios (consumo parcial)
    """
    codigo_qr = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'INV202509231914... (scanner o manual)',
            'id': 'codigo_qr_fraccionario',
            'autocomplete': 'off',
            'style': 'text-transform: uppercase;'
        }),
        help_text="Escanee o escriba el código del producto fraccionable",
        label="Código de Barras/QR del Producto"
    )
    
    class Meta:
        model = Movimiento
        fields = [
            'tipo', 'motivo', 'cantidad_fraccionaria', 'unidad_utilizada',
            'sucursal_destino', 'empleado_destinatario', 'usuario_registro_empleado', 
            'observaciones'
        ]
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'motivo': forms.Select(attrs={'class': 'form-control'}),
            'cantidad_fraccionaria': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': 'Ej: 600 (ml)',
                'id': 'cantidad_fraccionaria'
            }),
            'unidad_utilizada': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: ml, gramos',
                'id': 'unidad_utilizada'
            }),
            'sucursal_destino': forms.Select(attrs={
                'class': 'form-control'
            }),
            'empleado_destinatario': EmpleadoSelectWidget(attrs={
                'class': 'form-control'
            }),
            'usuario_registro_empleado': forms.Select(attrs={
                'class': 'form-control'
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Observaciones adicionales (opcional)'
            }),
        }
        
        labels = {
            'cantidad_fraccionaria': 'Cantidad Exacta',
            'unidad_utilizada': 'Unidad de Medida',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Configurar campos obligatorios
        self.fields['tipo'].required = True
        self.fields['motivo'].required = True
        self.fields['cantidad_fraccionaria'].required = True
        self.fields['unidad_utilizada'].required = True
        self.fields['sucursal_destino'].required = True
        self.fields['empleado_destinatario'].required = True
        self.fields['usuario_registro_empleado'].required = True
        
        # Configurar empleados y sucursales activos
        empleados_activos = Empleado.objects.filter(activo=True)
        sucursales_activas = Sucursal.objects.filter(activa=True)
        
        self.fields['sucursal_destino'].queryset = sucursales_activas
        self.fields['sucursal_destino'].empty_label = "Seleccionar sucursal destino *"
        
        self.fields['empleado_destinatario'].queryset = empleados_activos
        self.fields['empleado_destinatario'].empty_label = "Seleccionar empleado destinatario *"
        
        self.fields['usuario_registro_empleado'].queryset = empleados_activos
        self.fields['usuario_registro_empleado'].empty_label = "Seleccionar empleado que registra *"
        
        # Observaciones opcional
        self.fields['observaciones'].required = False
        
        # Ayuda contextual
        self.fields['cantidad_fraccionaria'].help_text = "Cantidad exacta a consumir del producto"
        self.fields['unidad_utilizada'].help_text = "Debe coincidir con la unidad base del producto"
    
    def clean_codigo_qr(self):
        """
        Validar que el código QR corresponde a un producto fraccionable
        """
        import re
        codigo_raw = self.cleaned_data['codigo_qr']
        
        # Limpiar código
        codigo = re.sub(r'[\r\n\t\x00-\x1f\x7f-\x9f]', '', codigo_raw)
        codigo = codigo.strip()
        codigo = re.sub(r'\s+', '', codigo)
        
        if not codigo:
            raise forms.ValidationError("Código QR inválido")
        
        try:
            producto = Producto.objects.get(codigo_qr__iexact=codigo)
            if not producto.es_fraccionable:
                raise forms.ValidationError("Este producto no es fraccionable. Use el formulario de movimientos normales.")
            return codigo
        except Producto.DoesNotExist:
            raise forms.ValidationError("Código QR no encontrado en el inventario")
    
    def clean(self):
        """
        Validaciones adicionales para movimientos fraccionarios
        """
        cleaned_data = super().clean()
        codigo_qr = cleaned_data.get('codigo_qr')
        cantidad_fraccionaria = cleaned_data.get('cantidad_fraccionaria')
        unidad_utilizada = cleaned_data.get('unidad_utilizada')
        tipo = cleaned_data.get('tipo')
        
        if codigo_qr and cantidad_fraccionaria and tipo:
            try:
                producto = Producto.objects.get(codigo_qr__iexact=codigo_qr)
                
                # Solo validar disponibilidad para SALIDAS
                if tipo == 'salida':
                    if not producto.puede_consumir(cantidad_fraccionaria):
                        raise forms.ValidationError(
                            f"No hay suficiente cantidad disponible. "
                            f"Disponible: {producto.cantidad_total_disponible():.2f} {producto.unidad_base}, "
                            f"Solicitado: {cantidad_fraccionaria}"
                        )
                
                # Para ENTRADAS, no validamos disponibilidad (podemos agregar todo lo que queramos)
                # Solo verificamos que sea una cantidad positiva (ya se valida en el campo)
                
                # Verificar que la unidad coincida
                if unidad_utilizada and unidad_utilizada.lower() != producto.unidad_base.lower():
                    raise forms.ValidationError(
                        f"La unidad debe ser '{producto.unidad_base}' para este producto"
                    )
                    
            except Producto.DoesNotExist:
                pass  # Ya se maneja en clean_codigo_qr
        
        return cleaned_data
    
    def save(self, commit=True):
        """
        Guardar movimiento fraccionario con campos específicos
        """
        movimiento = super().save(commit=False)
        codigo_qr = self.cleaned_data['codigo_qr']
        movimiento.producto = Producto.objects.get(codigo_qr__iexact=codigo_qr)
        
        # Marcar como movimiento fraccionario
        movimiento.es_movimiento_fraccionario = True
        
        # Establecer cantidad en 1 para compatibilidad con el sistema existente
        movimiento.cantidad = 1
        
        if commit:
            movimiento.save()
        return movimiento


class CambioContraseñaInicialForm(forms.Form):
    """
    Formulario para cambio de contraseña inicial (primer login)
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Este formulario se usa cuando un empleado inicia sesión por primera vez
    con su contraseña temporal. Le obliga a cambiarla por una segura.
    
    Campos:
    - contraseña_temporal: La contraseña que recibió por email
    - nueva_contraseña: La nueva contraseña que quiere usar
    - confirmar_contraseña: Debe repetir la nueva contraseña (para evitar errores)
    
    Validaciones:
    - Verifica que la contraseña temporal sea correcta
    - Valida que la nueva contraseña cumpla requisitos de seguridad de Django
    - Verifica que ambas contraseñas nuevas coincidan
    """
    
    contraseña_temporal = forms.CharField(
        label='Contraseña Temporal',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Contraseña que recibiste por email',
            'autocomplete': 'current-password'
        }),
        help_text='Ingresa la contraseña temporal que recibiste por correo electrónico'
    )
    
    nueva_contraseña = forms.CharField(
        label='Nueva Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Tu nueva contraseña segura',
            'autocomplete': 'new-password'
        }),
        help_text='Mínimo 8 caracteres. Debe incluir letras y números.'
    )
    
    confirmar_contraseña = forms.CharField(
        label='Confirmar Nueva Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Repite tu nueva contraseña',
            'autocomplete': 'new-password'
        }),
        help_text='Vuelve a escribir tu nueva contraseña para confirmar'
    )
    
    def __init__(self, user, *args, **kwargs):
        """
        Inicializar el formulario con el usuario actual
        
        EXPLICACIÓN:
        Necesitamos el objeto 'user' para poder verificar que la contraseña
        temporal ingresada sea correcta. Lo guardamos como atributo del form.
        
        Args:
            user: El objeto User de Django del empleado actual
        """
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_contraseña_temporal(self):
        """
        Valida que la contraseña temporal ingresada sea correcta
        
        EXPLICACIÓN:
        Django almacena las contraseñas encriptadas (hasheadas), nunca en texto plano.
        Usamos check_password() para verificar si la contraseña ingresada coincide
        con el hash almacenado en la base de datos.
        
        Returns:
            str: La contraseña temporal si es válida
        
        Raises:
            ValidationError: Si la contraseña temporal es incorrecta
        """
        contraseña_temporal = self.cleaned_data.get('contraseña_temporal')
        
        # Verificar que la contraseña temporal sea correcta
        # check_password compara el texto plano con el hash almacenado
        if not self.user.check_password(contraseña_temporal):
            raise ValidationError(
                'La contraseña temporal es incorrecta. '
                'Por favor verifica tu email y vuelve a intentarlo.'
            )
        
        return contraseña_temporal
    
    def clean(self):
        """
        Validación completa del formulario (todos los campos juntos)
        
        EXPLICACIÓN:
        Este método se ejecuta después de validar cada campo individual.
        Aquí verificamos que:
        1. La nueva contraseña cumpla con los requisitos de seguridad de Django
        2. Ambas contraseñas nuevas coincidan
        
        Returns:
            dict: Los datos limpiados y validados
        
        Raises:
            ValidationError: Si hay problemas con la nueva contraseña
        """
        cleaned_data = super().clean()
        nueva_contraseña = cleaned_data.get('nueva_contraseña')
        confirmar_contraseña = cleaned_data.get('confirmar_contraseña')
        
        # Validar que ambas contraseñas nuevas coincidan
        if nueva_contraseña and confirmar_contraseña:
            if nueva_contraseña != confirmar_contraseña:
                raise ValidationError({
                    'confirmar_contraseña': 'Las contraseñas no coinciden. Por favor verifica.'
                })
        
        # Validar que la nueva contraseña cumpla requisitos de seguridad
        # Django incluye validadores como:
        # - Mínimo 8 caracteres
        # - No puede ser muy común (como "password123")
        # - No puede ser muy similar al username
        # - No puede ser completamente numérica
        if nueva_contraseña:
            try:
                validate_password(nueva_contraseña, self.user)
            except ValidationError as e:
                # Agregar el error al campo nueva_contraseña
                self.add_error('nueva_contraseña', e)
        
        return cleaned_data
    
    def save(self, commit=True):
        """
        Guarda la nueva contraseña del usuario
        
        EXPLICACIÓN:
        Cuando el formulario es válido, este método:
        1. Toma la nueva contraseña
        2. La encripta usando set_password() (NUNCA guardar contraseñas en texto plano)
        3. Guarda el usuario en la base de datos
        
        Args:
            commit: Si True, guarda inmediatamente en la base de datos
        
        Returns:
            User: El objeto usuario con la contraseña actualizada
        """
        nueva_contraseña = self.cleaned_data['nueva_contraseña']
        
        # set_password() encripta automáticamente la contraseña
        # Usa un algoritmo hash seguro (PBKDF2 por defecto en Django)
        self.user.set_password(nueva_contraseña)
        
        if commit:
            self.user.save()
        
        return self.user