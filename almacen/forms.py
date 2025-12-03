"""
Formularios para el módulo Almacén - Sistema de Inventario de Almacén Central

EXPLICACIÓN PARA PRINCIPIANTES:
-------------------------------
Este archivo define los formularios que se muestran en el navegador.
Django usa ModelForm para crear campos automáticamente basados en los modelos.

Estructura de cada formulario:
- widgets: Define cómo se ve cada campo en HTML (estilos Bootstrap)
- labels: Etiquetas que se muestran al usuario
- help_texts: Textos de ayuda debajo de cada campo
- Meta class: Configuración (modelo, campos a incluir/excluir)

Todos los formularios usan clases de Bootstrap 5 para consistencia visual.
"""

from django import forms
from django.core.exceptions import ValidationError

from .models import (
    Proveedor,
    CategoriaAlmacen,
    ProductoAlmacen,
    CompraProducto,
    MovimientoAlmacen,
    SolicitudBaja,
    Auditoria,
    DiferenciaAuditoria,
    UnidadInventario,
)
from config.constants import (
    TIPO_PRODUCTO_ALMACEN_CHOICES,
    TIPO_SOLICITUD_ALMACEN_CHOICES,
    TIPO_MOVIMIENTO_ALMACEN_CHOICES,
    TIPO_AUDITORIA_CHOICES,
    RAZON_DIFERENCIA_AUDITORIA_CHOICES,
    ESTADO_UNIDAD_CHOICES,
    DISPONIBILIDAD_UNIDAD_CHOICES,
    ORIGEN_UNIDAD_CHOICES,
    MARCAS_COMPONENTES_CHOICES,
)


# ============================================================================
# FORMULARIO: PROVEEDOR
# ============================================================================
class ProveedorForm(forms.ModelForm):
    """
    Formulario para crear y editar Proveedores.
    
    Permite registrar la información de contacto de los proveedores
    que surten productos al almacén.
    """
    
    class Meta:
        model = Proveedor
        fields = [
            'nombre',
            'contacto',
            'telefono',
            'email',
            'direccion',
            'tiempo_entrega_dias',
            'notas',
            'activo',
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre o razón social del proveedor',
                'autofocus': True,
            }),
            'contacto': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre de la persona de contacto',
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 55-1234-5678',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'correo@proveedor.com',
            }),
            'direccion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Dirección completa del proveedor',
            }),
            'tiempo_entrega_dias': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'placeholder': '7',
            }),
            'notas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Observaciones: descuentos, condiciones de pago, etc.',
            }),
            'activo': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }
        labels = {
            'nombre': 'Nombre del Proveedor',
            'contacto': 'Persona de Contacto',
            'telefono': 'Teléfono',
            'email': 'Correo Electrónico',
            'direccion': 'Dirección',
            'tiempo_entrega_dias': 'Tiempo de Entrega (días)',
            'notas': 'Notas',
            'activo': 'Proveedor Activo',
        }
        help_texts = {
            'nombre': 'Nombre único del proveedor (no se puede repetir)',
            'tiempo_entrega_dias': 'Tiempo promedio de entrega en días hábiles',
            'activo': 'Desmarcar si ya no se trabaja con este proveedor',
        }


# ============================================================================
# FORMULARIO: CATEGORÍA DE ALMACÉN
# ============================================================================
class CategoriaAlmacenForm(forms.ModelForm):
    """
    Formulario para crear y editar Categorías de Almacén.
    
    Las categorías ayudan a organizar los productos en grupos lógicos.
    """
    
    class Meta:
        model = CategoriaAlmacen
        fields = ['nombre', 'descripcion', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Repuestos, Consumibles, Herramientas',
                'autofocus': True,
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Descripción de qué productos incluye esta categoría',
            }),
            'activo': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }
        labels = {
            'nombre': 'Nombre de la Categoría',
            'descripcion': 'Descripción',
            'activo': 'Categoría Activa',
        }


# ============================================================================
# FORMULARIO: PRODUCTO DE ALMACÉN
# ============================================================================
class ProductoAlmacenForm(forms.ModelForm):
    """
    Formulario para crear y editar Productos de Almacén.
    
    Este es el formulario principal del módulo. Permite registrar productos
    con todos sus atributos: tipo, stock, costos, proveedor, etc.
    
    TIPOS DE PRODUCTO:
    - Resurtible: Se mantiene en stock permanente, tiene mínimo/máximo
    - Único: Compra específica, no tiene alertas de reposición
    """
    
    class Meta:
        model = ProductoAlmacen
        fields = [
            # Identificación
            'codigo_producto',
            'nombre',
            'descripcion',
            # Clasificación
            'categoria',
            'tipo_producto',
            # Ubicación
            'ubicacion_fisica',
            'sucursal',
            # Stock
            'stock_actual',
            'stock_minimo',
            'stock_maximo',
            # Costos
            'costo_unitario',
            # Proveedor
            'proveedor_principal',
            'tiempo_reposicion_dias',
            # Multimedia
            'imagen',
            # Estado
            'activo',
        ]
        widgets = {
            # Identificación
            'codigo_producto': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'SKU o código interno único',
                'style': 'text-transform: uppercase;',
                'autofocus': True,
            }),
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre descriptivo del producto',
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Descripción, especificaciones técnicas...',
            }),
            # Clasificación
            'categoria': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
            'tipo_producto': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
            # Ubicación
            'ubicacion_fisica': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: A-03-2 (pasillo-estante-nivel)',
            }),
            'sucursal': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
            # Stock
            'stock_actual': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
            }),
            'stock_minimo': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
            }),
            'stock_maximo': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
            }),
            # Costos
            'costo_unitario': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'step': '0.01',
                'placeholder': '0.00',
            }),
            # Proveedor
            'proveedor_principal': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
            'tiempo_reposicion_dias': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
            }),
            # Multimedia
            'imagen': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
            }),
            # Estado
            'activo': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }
        labels = {
            'codigo_producto': 'Código / SKU',
            'nombre': 'Nombre del Producto',
            'descripcion': 'Descripción',
            'categoria': 'Categoría',
            'tipo_producto': 'Tipo de Producto',
            'ubicacion_fisica': 'Ubicación Física',
            'sucursal': 'Sucursal',
            'stock_actual': 'Stock Actual',
            'stock_minimo': 'Stock Mínimo',
            'stock_maximo': 'Stock Máximo',
            'costo_unitario': 'Costo Unitario ($)',
            'proveedor_principal': 'Proveedor Principal',
            'tiempo_reposicion_dias': 'Tiempo de Reposición (días)',
            'imagen': 'Imagen del Producto',
            'activo': 'Producto Activo',
        }
        help_texts = {
            'codigo_producto': 'Código único (SKU, código de barras, etc.)',
            'tipo_producto': 'Resurtible: stock permanente. Único: compra específica.',
            'ubicacion_fisica': 'Ubicación en almacén: pasillo-estante-nivel',
            'sucursal': 'Dejar vacío para almacén central',
            'stock_minimo': 'Nivel mínimo antes de alerta (solo resurtibles)',
            'stock_maximo': 'Nivel máximo recomendado (solo resurtibles)',
            'costo_unitario': 'Último precio de compra por unidad',
        }
    
    def clean(self):
        """
        Validaciones personalizadas del formulario.
        
        - Si es resurtible, stock_maximo debe ser >= stock_minimo
        - El código de producto se convierte a mayúsculas
        """
        cleaned_data = super().clean()
        tipo = cleaned_data.get('tipo_producto')
        stock_min = cleaned_data.get('stock_minimo', 0)
        stock_max = cleaned_data.get('stock_maximo', 0)
        
        # Validar que máximo >= mínimo para resurtibles
        if tipo == 'resurtible' and stock_max > 0 and stock_max < stock_min:
            raise ValidationError({
                'stock_maximo': 'El stock máximo debe ser mayor o igual al mínimo.'
            })
        
        # Convertir código a mayúsculas
        codigo = cleaned_data.get('codigo_producto')
        if codigo:
            cleaned_data['codigo_producto'] = codigo.upper()
        
        return cleaned_data


# ============================================================================
# FORMULARIO: COMPRA DE PRODUCTO
# ============================================================================
class CompraProductoForm(forms.ModelForm):
    """
    Formulario para registrar compras de productos.
    
    Registra el historial de compras: a quién se compró, cuánto costó,
    cuándo llegó, y opcionalmente a qué orden de servicio está vinculada.
    """
    
    class Meta:
        model = CompraProducto
        fields = [
            'producto',
            'proveedor',
            'cantidad',
            'costo_unitario',
            'fecha_pedido',
            'fecha_recepcion',
            'numero_factura',
            'numero_orden_compra',
            'orden_servicio',
            'observaciones',
        ]
        widgets = {
            'producto': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
            'proveedor': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': '1',
            }),
            'costo_unitario': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'step': '0.01',
                'placeholder': '0.00',
            }),
            'fecha_pedido': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'fecha_recepcion': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'numero_factura': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número de factura del proveedor',
            }),
            'numero_orden_compra': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número de orden de compra interno',
            }),
            'orden_servicio': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Notas sobre esta compra...',
            }),
        }
        labels = {
            'producto': 'Producto',
            'proveedor': 'Proveedor',
            'cantidad': 'Cantidad',
            'costo_unitario': 'Costo Unitario ($)',
            'fecha_pedido': 'Fecha de Pedido',
            'fecha_recepcion': 'Fecha de Recepción',
            'numero_factura': 'Número de Factura',
            'numero_orden_compra': 'Orden de Compra',
            'orden_servicio': 'Orden de Servicio (opcional)',
            'observaciones': 'Observaciones',
        }
        help_texts = {
            'fecha_recepcion': 'Dejar vacío si aún no se ha recibido',
            'orden_servicio': 'Vincular con orden de servicio técnico si aplica',
        }


# ============================================================================
# FORMULARIO: MOVIMIENTO DE ALMACÉN
# ============================================================================
class MovimientoAlmacenForm(forms.ModelForm):
    """
    Formulario para registrar entradas y salidas del almacén.
    
    ENTRADA: Incrementa el stock (recepción de compra, devolución)
    SALIDA: Decrementa el stock (venta, uso en servicio, etc.)
    
    NOTA: El stock se actualiza automáticamente al guardar.
    """
    
    class Meta:
        model = MovimientoAlmacen
        fields = [
            'tipo',
            'producto',
            'cantidad',
            'costo_unitario',
            'empleado',
            'orden_servicio',
            'compra',
            'observaciones',
        ]
        widgets = {
            'tipo': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
            'producto': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': '1',
            }),
            'costo_unitario': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'step': '0.01',
                'placeholder': '0.00',
            }),
            'empleado': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
            'orden_servicio': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
            'compra': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Notas sobre este movimiento...',
            }),
        }
        labels = {
            'tipo': 'Tipo de Movimiento',
            'producto': 'Producto',
            'cantidad': 'Cantidad',
            'costo_unitario': 'Costo Unitario ($)',
            'empleado': 'Registrado por',
            'orden_servicio': 'Orden de Servicio (opcional)',
            'compra': 'Compra Asociada (opcional)',
            'observaciones': 'Observaciones',
        }
        help_texts = {
            'tipo': 'Entrada: suma al stock. Salida: resta del stock.',
            'costo_unitario': 'Costo al momento del movimiento',
        }
    
    def clean(self):
        """
        Validaciones personalizadas.
        
        - No permitir salida si no hay stock suficiente
        """
        cleaned_data = super().clean()
        tipo = cleaned_data.get('tipo')
        producto = cleaned_data.get('producto')
        cantidad = cleaned_data.get('cantidad', 0)
        
        if tipo == 'salida' and producto:
            if cantidad > producto.stock_actual:
                raise ValidationError({
                    'cantidad': f'Stock insuficiente. Disponible: {producto.stock_actual}'
                })
        
        return cleaned_data


# ============================================================================
# FORMULARIO: SOLICITUD DE BAJA
# ============================================================================
class SolicitudBajaForm(forms.ModelForm):
    """
    Formulario para crear solicitudes de baja de productos.
    
    Los empleados usan este formulario para solicitar productos del almacén.
    El agente de almacén posteriormente aprueba o rechaza la solicitud.
    
    FLUJO MEJORADO:
    1. Usuario selecciona un Producto (tipo genérico: "SSD 1TB")
    2. Se cargan dinámicamente las UnidadInventario disponibles de ese producto
    3. Usuario puede elegir una unidad específica (opcional) o dejar genérico
    """
    
    class Meta:
        model = SolicitudBaja
        fields = [
            'tipo_solicitud',
            'producto',
            'unidad_inventario',
            'cantidad',
            'orden_servicio',
            'observaciones',
        ]
        widgets = {
            'tipo_solicitud': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
            'producto': forms.Select(attrs={
                'class': 'form-control form-select',
                'id': 'id_producto',
            }),
            'unidad_inventario': forms.Select(attrs={
                'class': 'form-control form-select',
                'id': 'id_unidad_inventario',
            }),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': '1',
            }),
            'orden_servicio': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Motivo de la solicitud...',
            }),
        }
        labels = {
            'tipo_solicitud': 'Tipo de Solicitud',
            'producto': 'Producto',
            'unidad_inventario': 'Unidad Específica (opcional)',
            'cantidad': 'Cantidad Solicitada',
            'orden_servicio': 'Orden de Servicio (opcional)',
            'observaciones': 'Observaciones',
        }
        help_texts = {
            'tipo_solicitud': 'Propósito de la salida del producto',
            'unidad_inventario': 'Seleccione una unidad específica o deje vacío para genérico',
            'orden_servicio': 'Solo si es para servicio técnico',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Inicialmente, el campo de unidad está vacío
        # Se llenará dinámicamente con JavaScript cuando se seleccione un producto
        self.fields['unidad_inventario'].queryset = UnidadInventario.objects.none()
        self.fields['unidad_inventario'].required = False
        
        # Si hay datos del formulario (POST) o instancia existente, cargar las unidades del producto
        if 'producto' in self.data:
            try:
                producto_id = int(self.data.get('producto'))
                self.fields['unidad_inventario'].queryset = UnidadInventario.objects.filter(
                    producto_id=producto_id,
                    disponibilidad='disponible'
                ).select_related('producto')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.producto:
            self.fields['unidad_inventario'].queryset = UnidadInventario.objects.filter(
                producto=self.instance.producto,
                disponibilidad='disponible'
            ).select_related('producto')
    
    def clean_cantidad(self):
        """Validar que haya stock disponible"""
        cantidad = self.cleaned_data.get('cantidad')
        producto = self.cleaned_data.get('producto')
        
        if producto and cantidad:
            if cantidad > producto.stock_actual:
                raise ValidationError(
                    f'Stock insuficiente. Disponible: {producto.stock_actual}'
                )
        
        return cantidad


# ============================================================================
# FORMULARIO: PROCESAR SOLICITUD (para agente de almacén)
# ============================================================================
class ProcesarSolicitudForm(forms.Form):
    """
    Formulario para que el agente de almacén procese una solicitud.
    
    No es un ModelForm porque solo necesitamos la acción y observaciones.
    """
    
    ACCIONES = [
        ('aprobar', 'Aprobar Solicitud'),
        ('rechazar', 'Rechazar Solicitud'),
    ]
    
    accion = forms.ChoiceField(
        choices=ACCIONES,
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input',
        }),
        label='Acción',
    )
    
    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Observaciones (obligatorio si rechaza)...',
        }),
        label='Observaciones',
    )
    
    def clean(self):
        """Validar que si rechaza, incluya observaciones"""
        cleaned_data = super().clean()
        accion = cleaned_data.get('accion')
        observaciones = cleaned_data.get('observaciones', '').strip()
        
        if accion == 'rechazar' and not observaciones:
            raise ValidationError({
                'observaciones': 'Debe indicar el motivo del rechazo.'
            })
        
        return cleaned_data


# ============================================================================
# FORMULARIO: AUDITORÍA
# ============================================================================
class AuditoriaForm(forms.ModelForm):
    """
    Formulario para crear nuevas auditorías de inventario.
    """
    
    class Meta:
        model = Auditoria
        fields = [
            'tipo',
            'sucursal',
            'auditor',
            'observaciones_generales',
        ]
        widgets = {
            'tipo': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
            'sucursal': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
            'auditor': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
            'observaciones_generales': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Notas sobre esta auditoría...',
            }),
        }
        labels = {
            'tipo': 'Tipo de Auditoría',
            'sucursal': 'Sucursal',
            'auditor': 'Auditor Asignado',
            'observaciones_generales': 'Observaciones',
        }


# ============================================================================
# FORMULARIO: DIFERENCIA DE AUDITORÍA
# ============================================================================
class DiferenciaAuditoriaForm(forms.ModelForm):
    """
    Formulario para registrar diferencias encontradas en auditorías.
    """
    
    class Meta:
        model = DiferenciaAuditoria
        fields = [
            'producto',
            'stock_sistema',
            'stock_fisico',
            'razon',
            'razon_detalle',
            'evidencia',
        ]
        widgets = {
            'producto': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
            'stock_sistema': forms.NumberInput(attrs={
                'class': 'form-control',
                'readonly': True,  # Se autocompleta con el stock actual
            }),
            'stock_fisico': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'placeholder': 'Cantidad contada físicamente',
            }),
            'razon': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
            'razon_detalle': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Explicación detallada de la diferencia...',
            }),
            'evidencia': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
            }),
        }
        labels = {
            'producto': 'Producto',
            'stock_sistema': 'Stock en Sistema',
            'stock_fisico': 'Stock Físico (Contado)',
            'razon': 'Razón de la Diferencia',
            'razon_detalle': 'Detalle',
            'evidencia': 'Evidencia Fotográfica',
        }


# ============================================================================
# FORMULARIO: BÚSQUEDA DE PRODUCTOS
# ============================================================================
class BusquedaProductoForm(forms.Form):
    """
    Formulario de búsqueda y filtros para la lista de productos.
    """
    
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar por código, nombre...',
        }),
        label='',
    )
    
    tipo = forms.ChoiceField(
        required=False,
        choices=[('', 'Todos los tipos')] + list(TIPO_PRODUCTO_ALMACEN_CHOICES),
        widget=forms.Select(attrs={
            'class': 'form-control form-select',
        }),
        label='Tipo',
    )
    
    categoria = forms.ModelChoiceField(
        required=False,
        queryset=CategoriaAlmacen.objects.filter(activo=True),
        empty_label='Todas las categorías',
        widget=forms.Select(attrs={
            'class': 'form-control form-select',
        }),
        label='Categoría',
    )
    
    stock = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'Todo el stock'),
            ('bajo', 'Stock Bajo'),
            ('agotado', 'Agotados'),
            ('disponible', 'Disponibles'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-control form-select',
        }),
        label='Stock',
    )


# ============================================================================
# FORMULARIO: ENTRADA RÁPIDA (Recepción de Compra)
# ============================================================================
class EntradaRapidaForm(forms.Form):
    """
    Formulario simplificado para dar entrada rápida a productos.
    
    Combina la creación de CompraProducto y MovimientoAlmacen en un solo paso.
    Útil para recepción de mercancía.
    """
    
    producto = forms.ModelChoiceField(
        queryset=ProductoAlmacen.objects.filter(activo=True),
        widget=forms.Select(attrs={
            'class': 'form-control form-select',
        }),
        label='Producto',
    )
    
    cantidad = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '1',
        }),
        label='Cantidad',
    )
    
    costo_unitario = forms.DecimalField(
        min_value=0,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': '0.00',
        }),
        label='Costo Unitario ($)',
    )
    
    proveedor = forms.ModelChoiceField(
        queryset=Proveedor.objects.filter(activo=True),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control form-select',
        }),
        label='Proveedor',
    )
    
    numero_factura = forms.CharField(
        required=False,
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Número de factura (opcional)',
        }),
        label='Factura',
    )
    
    vincular_orden = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        label='¿Es para un Servicio Técnico?',
    )
    
    # Este campo se muestra condicionalmente con JavaScript
    orden_servicio = forms.CharField(
        required=False,
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar orden de servicio...',
        }),
        label='Orden de Servicio',
    )
    
    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Observaciones...',
        }),
        label='Observaciones',
    )


# ============================================================================
# FORMULARIO: UNIDAD DE INVENTARIO
# ============================================================================
class UnidadInventarioForm(forms.ModelForm):
    """
    Formulario para crear y editar Unidades Individuales de Inventario.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Este formulario permite registrar cada unidad física de un producto.
    
    Por ejemplo, si el producto es "SSD 1TB", cada SSD físico se registra
    aquí con su marca específica (Samsung, Kingston), modelo (870 EVO, A2000),
    y número de serie único.
    
    Campos principales:
    - producto: El producto consolidado al que pertenece (ej: "SSD 1TB")
    - marca: La marca específica de esta unidad (ej: "Samsung")
    - modelo: El modelo específico (ej: "870 EVO 1TB")
    - numero_serie: Identificador único del fabricante
    - estado: Condición física (nuevo, usado bueno, defectuoso, etc.)
    - disponibilidad: Si está disponible, reservada, asignada, etc.
    - origen: Cómo llegó al inventario (compra, orden de servicio, etc.)
    """
    
    class Meta:
        model = UnidadInventario
        fields = [
            'producto',
            'numero_serie',
            'marca',
            'modelo',
            'especificaciones',
            'estado',
            'disponibilidad',
            'origen',
            'compra',
            'orden_servicio_origen',
            'ubicacion_especifica',
            'costo_unitario',
            'notas',
        ]
        widgets = {
            'producto': forms.Select(attrs={
                'class': 'form-select',
                'required': True,
            }),
            'numero_serie': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número de serie del fabricante (si aplica)',
            }),
            'marca': forms.Select(
                choices=[('', '-- Seleccionar Marca --')] + list(MARCAS_COMPONENTES_CHOICES),
                attrs={
                    'class': 'form-select',
                }
            ),
            'modelo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Modelo específico (ej: 870 EVO, A2000)',
            }),
            'especificaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Especificaciones adicionales: capacidad, velocidad, etc.',
            }),
            'estado': forms.Select(
                choices=ESTADO_UNIDAD_CHOICES,
                attrs={
                    'class': 'form-select',
                }
            ),
            'disponibilidad': forms.Select(
                choices=DISPONIBILIDAD_UNIDAD_CHOICES,
                attrs={
                    'class': 'form-select',
                }
            ),
            'origen': forms.Select(
                choices=ORIGEN_UNIDAD_CHOICES,
                attrs={
                    'class': 'form-select',
                }
            ),
            'compra': forms.Select(attrs={
                'class': 'form-select',
            }),
            'orden_servicio_origen': forms.Select(attrs={
                'class': 'form-select',
            }),
            'ubicacion_especifica': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ubicación específica (ej: Estante A, Caja 3)',
            }),
            'costo_unitario': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0.01',
                'placeholder': '0.00',
            }),
            'notas': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Observaciones adicionales sobre esta unidad...',
            }),
        }
        labels = {
            'producto': 'Producto',
            'numero_serie': 'Número de Serie',
            'marca': 'Marca',
            'modelo': 'Modelo',
            'especificaciones': 'Especificaciones Técnicas',
            'estado': 'Estado Físico',
            'disponibilidad': 'Disponibilidad',
            'origen': 'Origen',
            'compra': 'Compra Asociada',
            'orden_servicio_origen': 'Orden de Servicio (Origen)',
            'ubicacion_especifica': 'Ubicación Específica',
            'costo_unitario': 'Costo Unitario',
            'notas': 'Notas',
        }
        help_texts = {
            'producto': 'Producto consolidado al que pertenece esta unidad.',
            'numero_serie': 'S/N único del fabricante. Puede estar vacío para productos genéricos.',
            'marca': 'Marca del fabricante de esta unidad específica.',
            'modelo': 'Modelo específico según el fabricante.',
            'especificaciones': 'Detalles adicionales: capacidad, velocidad, etc.',
            'estado': 'Condición física actual de la unidad.',
            'disponibilidad': 'Estado de disponibilidad para uso o venta.',
            'origen': '¿Cómo llegó esta unidad al inventario?',
            'compra': 'Si vino de una compra, selecciona cuál.',
            'orden_servicio_origen': 'Si se recuperó de un servicio, indica la orden.',
            'ubicacion_especifica': 'Dónde está físicamente esta unidad.',
            'costo_unitario': 'Costo de adquisición o valor estimado.',
            'notas': 'Cualquier observación relevante sobre esta unidad.',
        }
    
    def __init__(self, *args, **kwargs):
        """
        Personaliza el formulario al inicializarse.
        
        Filtra las opciones de producto para mostrar solo los activos,
        y las compras/órdenes relevantes.
        """
        super().__init__(*args, **kwargs)
        
        # Filtrar solo productos activos
        self.fields['producto'].queryset = ProductoAlmacen.objects.filter(
            activo=True
        ).order_by('nombre')
        
        # Filtrar compras para mostrar solo las recientes (últimos 6 meses) o todas si estamos editando
        from django.utils import timezone
        from datetime import timedelta
        
        if self.instance and self.instance.pk:
            # Si estamos editando, mostrar la compra actual más las recientes
            self.fields['compra'].queryset = CompraProducto.objects.filter(
                fecha_pedido__gte=timezone.now() - timedelta(days=180)
            ).order_by('-fecha_pedido')
        else:
            # Si es nuevo, solo mostrar compras recientes
            self.fields['compra'].queryset = CompraProducto.objects.filter(
                fecha_pedido__gte=timezone.now() - timedelta(days=180)
            ).order_by('-fecha_pedido')
        
        # El campo orden_servicio_origen se configura dinámicamente
        # (Se puede implementar con AJAX si es necesario)
    
    def clean_numero_serie(self):
        """
        Valida que el número de serie sea único si se proporciona.
        """
        numero_serie = self.cleaned_data.get('numero_serie')
        
        if numero_serie:
            # Verificar que no exista otra unidad con el mismo número de serie
            qs = UnidadInventario.objects.filter(numero_serie__iexact=numero_serie)
            
            # Si estamos editando, excluir la instancia actual
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            
            if qs.exists():
                raise ValidationError(
                    f'Ya existe una unidad con el número de serie "{numero_serie}".'
                )
        
        return numero_serie
    
    def clean(self):
        """
        Validaciones que involucran múltiples campos.
        """
        cleaned_data = super().clean()
        origen = cleaned_data.get('origen')
        compra = cleaned_data.get('compra')
        orden_servicio_origen = cleaned_data.get('orden_servicio_origen')
        
        # Si el origen es 'compra', debería tener una compra asociada
        if origen == 'compra' and not compra:
            self.add_error(
                'compra',
                'Si el origen es "Compra", debe seleccionar la compra asociada.'
            )
        
        # Si el origen es 'orden_servicio', debería tener una orden asociada
        if origen == 'orden_servicio' and not orden_servicio_origen:
            self.add_error(
                'orden_servicio_origen',
                'Si el origen es "Orden de Servicio", debe seleccionar la orden.'
            )
        
        return cleaned_data


class UnidadInventarioFiltroForm(forms.Form):
    """
    Formulario de filtros para la lista de unidades de inventario.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Este formulario NO guarda datos en la base de datos.
    Su único propósito es proporcionar campos para filtrar la lista
    de unidades en la vista de lista.
    
    Por ejemplo, permite filtrar por:
    - Producto específico
    - Marca
    - Estado (nuevo, usado, defectuoso)
    - Disponibilidad (disponible, reservada, asignada)
    - Origen (compra, orden de servicio, etc.)
    """
    
    producto = forms.ModelChoiceField(
        queryset=ProductoAlmacen.objects.filter(activo=True).order_by('nombre'),
        required=False,
        empty_label='Todos los productos',
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm',
        }),
        label='Producto',
    )
    
    marca = forms.ChoiceField(
        choices=[('', 'Todas las marcas')] + list(MARCAS_COMPONENTES_CHOICES),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm',
        }),
        label='Marca',
    )
    
    estado = forms.ChoiceField(
        choices=[('', 'Todos los estados')] + list(ESTADO_UNIDAD_CHOICES),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm',
        }),
        label='Estado',
    )
    
    disponibilidad = forms.ChoiceField(
        choices=[('', 'Todas')] + list(DISPONIBILIDAD_UNIDAD_CHOICES),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm',
        }),
        label='Disponibilidad',
    )
    
    origen = forms.ChoiceField(
        choices=[('', 'Todos los orígenes')] + list(ORIGEN_UNIDAD_CHOICES),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm',
        }),
        label='Origen',
    )
    
    buscar = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Buscar por código, serie, modelo...',
        }),
        label='Buscar',
    )
