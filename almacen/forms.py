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
from django.forms import inlineformset_factory

from .models import (
    Proveedor,
    CategoriaAlmacen,
    ProductoAlmacen,
    CompraProducto,
    UnidadCompra,
    MovimientoAlmacen,
    SolicitudBaja,
    Auditoria,
    DiferenciaAuditoria,
    UnidadInventario,
    SolicitudCotizacion,
    LineaCotizacion,
    ImagenLineaCotizacion,
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
    TIPO_COMPRA_CHOICES,
    ESTADO_COMPRA_CHOICES,
    ESTADO_UNIDAD_COMPRA_CHOICES,
    ESTADO_SOLICITUD_COTIZACION_CHOICES,
    ESTADO_LINEA_COTIZACION_CHOICES,
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
    Formulario para registrar COMPRAS DIRECTAS de productos.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Este formulario maneja el registro de compras directas de piezas.
    
    IMPORTANTE - SISTEMA DE COTIZACIONES:
    Las cotizaciones ahora se manejan en un sistema separado (SolicitudCotizacion)
    que permite múltiples proveedores por cotización. Este formulario es 
    EXCLUSIVAMENTE para compras directas.
    
    El campo 'orden_cliente' permite buscar por el número visible al cliente
    (ej: OS-2024-0001, OOW-12345, FL-67890) en lugar del ID interno de la BD.
    
    Campos importantes:
    - producto: Qué producto se compra
    - cantidad: Número de unidades
    - costo_unitario: Precio por unidad
    - orden_cliente: Para vincular con orden de servicio por número visible
    
    NOTA: El campo 'tipo' se asigna automáticamente como 'compra' en la vista.
    """
    
    # Campo adicional para buscar orden por número de cliente
    buscar_orden_cliente = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: OS-2024-0001',
            'autocomplete': 'off',
        }),
        label='Buscar por Orden Cliente',
        help_text='Ingresa el número de orden visible para el cliente'
    )
    
    class Meta:
        model = CompraProducto
        # NOTA: 'tipo' se excluye porque se asigna automáticamente en la vista
        # Las cotizaciones ahora usan el sistema SolicitudCotizacion
        fields = [
            'producto',
            'proveedor',
            'cantidad',
            'costo_unitario',
            'fecha_pedido',
            'numero_factura',
            'numero_orden_compra',
            'orden_cliente',
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
            'numero_factura': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número de factura del proveedor',
            }),
            'numero_orden_compra': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número de orden de compra interno',
            }),
            'orden_cliente': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: OS-2024-0001 (opcional)',
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Notas sobre esta compra/cotización...',
            }),
        }
        labels = {
            'producto': 'Producto',
            'proveedor': 'Proveedor',
            'cantidad': 'Cantidad Total',
            'costo_unitario': 'Costo Unitario Promedio ($)',
            'fecha_pedido': 'Fecha de Pedido',
            'numero_factura': 'Número de Factura',
            'numero_orden_compra': 'Orden de Compra Interna',
            'orden_cliente': 'Número de Orden (Cliente)',
            'observaciones': 'Observaciones',
        }
        help_texts = {
            'cantidad': 'Cantidad total de piezas a comprar',
            'costo_unitario': 'Calculado automáticamente del promedio de las unidades',
            'orden_cliente': 'Número de orden de servicio visible para el cliente (ej: OOW-12345)',
        }
    
    def clean_orden_cliente(self):
        """
        Valida y normaliza el número de orden cliente.
        Convierte a mayúsculas para consistencia.
        """
        orden_cliente = self.cleaned_data.get('orden_cliente', '')
        if orden_cliente:
            return orden_cliente.upper().strip()
        return orden_cliente


# ============================================================================
# FORMULARIO: UNIDAD DE COMPRA (Detalle por Pieza)
# ============================================================================
class UnidadCompraForm(forms.ModelForm):
    """
    Formulario para registrar detalles de cada unidad individual en una compra.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Cuando compras varias piezas del mismo tipo (ej: 3 tarjetas madre),
    este formulario permite especificar los detalles de CADA UNA:
    
    - Marca: Samsung, Kingston, ASUS, etc.
    - Modelo: Modelo específico del fabricante
    - Número de serie: S/N único de cada pieza
    - Costo individual: Si alguna pieza cuesta diferente
    
    EJEMPLO:
    Compra de 3 Tarjetas Madre (ProductoAlmacen genérico):
    - Línea 1: ASUS ROG STRIX B550-F, S/N: ABC123, $3,500
    - Línea 2: MSI MAG B550 TOMAHAWK, S/N: DEF456, $3,200
    - Línea 3: Gigabyte B550 AORUS PRO, S/N: GHI789, $3,400
    
    Esto permite rastrear cada pieza individualmente cuando se convierta
    en UnidadInventario al recibir la compra.
    """
    
    class Meta:
        model = UnidadCompra
        fields = [
            'numero_linea',
            'cantidad',
            'marca',
            'modelo',
            'numero_serie',
            'especificaciones',
            'costo_unitario',
            'notas',
        ]
        widgets = {
            'numero_linea': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm',
                'min': 1,
                'readonly': True,  # Se asigna automáticamente
            }),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm cantidad-input',
                'min': 1,
                'placeholder': '1',
            }),
            'marca': forms.Select(attrs={
                'class': 'form-control form-select form-select-sm marca-input',
                'required': True,
            }),
            'modelo': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Ej: 870 EVO, ROG STRIX B550',
            }),
            'numero_serie': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'S/N del fabricante',
            }),
            'especificaciones': forms.Textarea(attrs={
                'class': 'form-control form-control-sm',
                'rows': 1,
                'placeholder': 'Detalles técnicos adicionales...',
            }),
            'costo_unitario': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm costo-unidad-input',
                'min': 0.01,
                'step': '0.01',
                'placeholder': 'Costo $',
                'required': True,
            }),
            'notas': forms.Textarea(attrs={
                'class': 'form-control form-control-sm',
                'rows': 1,
                'placeholder': 'Notas adicionales...',
            }),
        }
        labels = {
            'numero_linea': '#',
            'cantidad': 'Cant.',
            'marca': 'Marca *',
            'modelo': 'Modelo',
            'numero_serie': 'Número de Serie',
            'especificaciones': 'Especificaciones',
            'costo_unitario': 'Costo ($) *',
            'notas': 'Notas',
        }
        help_texts = {
            'cantidad': 'Cuántas unidades de esta marca/modelo',
            'marca': 'Obligatorio: selecciona la marca del fabricante',
            'costo_unitario': 'Obligatorio: costo unitario de esta línea',
        }
    
    def clean_marca(self):
        """Valida que la marca sea obligatoria"""
        marca = self.cleaned_data.get('marca')
        if not marca:
            raise ValidationError('La marca es obligatoria. Selecciona una opción.')
        return marca
    
    def clean_costo_unitario(self):
        """Valida que el costo unitario sea obligatorio y positivo"""
        costo = self.cleaned_data.get('costo_unitario')
        if costo is None:
            raise ValidationError('El costo unitario es obligatorio.')
        if costo <= 0:
            raise ValidationError('El costo debe ser mayor a 0.')
        return costo


# Formset para manejar múltiples UnidadCompra dentro de una CompraProducto
# EXPLICACIÓN: Un "formset" es un conjunto de formularios iguales que Django
# maneja como grupo. Esto permite crear/editar múltiples UnidadCompra a la vez.
#
# IMPORTANTE: min_num=1 y validate_min=True aseguran que siempre se especifique
# al menos una línea de detalle con marca y costo.
UnidadCompraFormSet = inlineformset_factory(
    CompraProducto,          # Modelo padre
    UnidadCompra,            # Modelo hijo
    form=UnidadCompraForm,   # Formulario a usar
    extra=1,                 # Formularios vacíos adicionales (para agregar nuevos)
    can_delete=True,         # Permitir eliminar unidades
    min_num=1,               # Mínimo 1 formulario OBLIGATORIO
    validate_min=True,       # Validar que haya al menos 1
)


# ============================================================================
# FORMULARIO: RECEPCIÓN DE COMPRA
# ============================================================================
class RecepcionCompraForm(forms.Form):
    """
    Formulario para confirmar la recepción de una compra.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Cuando llega una compra, se usa este formulario para:
    1. Registrar la fecha de recepción
    2. Agregar observaciones sobre la recepción
    3. Decidir si crear UnidadInventario automáticamente
    
    Este formulario NO es un ModelForm porque no edita directamente
    el modelo, sino que llama al método compra.recibir()
    """
    
    fecha_recepcion = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
        }),
        label='Fecha de Recepción',
        help_text='Fecha en que se recibió físicamente el producto'
    )
    
    crear_unidades = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        label='Crear Unidades de Inventario',
        help_text='Crear UnidadInventario automáticamente para cada unidad recibida'
    )
    
    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Observaciones sobre la recepción...',
        }),
        label='Observaciones'
    )


# ============================================================================
# FORMULARIO: PROBLEMA EN COMPRA (WPB/DOA)
# ============================================================================
class ProblemaCompraForm(forms.Form):
    """
    Formulario para reportar problemas en una compra (WPB o DOA).
    
    WPB = Wrong Part (Pieza Incorrecta): Enviaron otra cosa
    DOA = Dead On Arrival (Dañada al Llegar): La pieza no funciona
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Este formulario se usa cuando hay un problema con la pieza recibida.
    Permite documentar el tipo de problema y la razón para iniciar
    el proceso de devolución al proveedor.
    """
    
    TIPO_PROBLEMA_CHOICES = [
        ('wpb', 'WPB - Pieza Incorrecta (Wrong Part)'),
        ('doa', 'DOA - Dañada al Llegar (Dead On Arrival)'),
    ]
    
    tipo_problema = forms.ChoiceField(
        choices=TIPO_PROBLEMA_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control form-select',
        }),
        label='Tipo de Problema'
    )
    
    motivo = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Describe el problema detalladamente...',
        }),
        label='Descripción del Problema',
        help_text='Incluye toda la información relevante para el reclamo al proveedor'
    )


# ============================================================================
# FORMULARIO: RECHAZO DE COTIZACIÓN
# ============================================================================
class RechazoCotizacionForm(forms.Form):
    """
    Formulario para registrar el rechazo de una cotización por el cliente.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Cuando el cliente decide no aceptar una cotización, se usa este
    formulario para documentar la razón. Esto ayuda a analizar por qué
    se pierden ventas y mejorar las cotizaciones futuras.
    """
    
    motivo = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Razón del rechazo (precio, tiempo de entrega, etc.)...',
        }),
        label='Motivo del Rechazo',
        help_text='Opcional pero recomendado para análisis'
    )


# ============================================================================
# FORMULARIO: CONFIRMACIÓN DE DEVOLUCIÓN
# ============================================================================
class DevolucionCompraForm(forms.Form):
    """
    Formulario para confirmar la devolución de una pieza al proveedor.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Después de reportar un problema (WPB/DOA) y enviar la pieza de vuelta
    al proveedor, se usa este formulario para confirmar que la devolución
    fue completada. Esto descuenta la pieza del inventario.
    """
    
    numero_guia = forms.CharField(
        required=False,
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Número de guía de envío',
        }),
        label='Número de Guía',
        help_text='Número de tracking del envío de devolución'
    )
    
    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Notas sobre la devolución...',
        }),
        label='Observaciones'
    )


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
    
    FLUJO MEJORADO (Diciembre 2025):
    1. Usuario selecciona un Producto (tipo genérico: "SSD 1TB")
    2. Se cargan dinámicamente las UnidadInventario disponibles de ese producto
    3. Usuario puede elegir una unidad específica (opcional) o dejar genérico
    4. Si tipo_solicitud es 'servicio_tecnico', se muestra selector de técnico (obligatorio)
    5. Usuario puede escribir el número de orden del cliente (OOW-xxx o FL-xxx)
       - Si existe: se vincula automáticamente
       - Si no existe: se crea automáticamente con estado "Proveniente de Almacén"
    """
    
    # Campo extra para capturar el número de orden del cliente (texto libre)
    orden_cliente_input = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_orden_cliente_input',
            'placeholder': 'Ej: OOW-12345 o FL-2025-001',
            'autocomplete': 'off',
        }),
        label='Número de Orden del Cliente',
        help_text='Escriba el número de orden (OOW-xxx o FL-xxx). Si no existe, se creará automáticamente.',
    )
    
    # Campo extra para seleccionar sucursal (necesario para crear órdenes nuevas)
    sucursal_orden = forms.ModelChoiceField(
        queryset=None,  # Se configura en __init__
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control form-select',
            'id': 'id_sucursal_orden',
        }),
        label='Sucursal para la Orden',
        help_text='Sucursal donde se registrará la orden (requerido si la orden no existe)',
    )
    
    class Meta:
        model = SolicitudBaja
        fields = [
            'tipo_solicitud',
            'producto',
            'unidad_inventario',
            'cantidad',
            'orden_servicio',  # Campo oculto - se llenará automáticamente
            'tecnico_asignado',  # Técnico de laboratorio
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
            'orden_servicio': forms.HiddenInput(attrs={
                'id': 'id_orden_servicio',
            }),
            'tecnico_asignado': forms.Select(attrs={
                'class': 'form-control form-select',
                'id': 'id_tecnico_asignado',
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
            'orden_servicio': 'Orden de Servicio',
            'tecnico_asignado': 'Técnico de Laboratorio',
            'observaciones': 'Observaciones',
        }
        help_texts = {
            'tipo_solicitud': 'Propósito de la salida del producto',
            'unidad_inventario': 'Seleccione una unidad específica o deje vacío para genérico',
            'tecnico_asignado': 'Obligatorio cuando el tipo es Servicio Técnico',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Importar Empleado y Sucursal aquí para evitar importación circular
        from inventario.models import Empleado, Sucursal
        
        # ========== CONFIGURACIÓN SUCURSAL_ORDEN ==========
        # Cargar todas las sucursales activas para el campo de selección
        self.fields['sucursal_orden'].queryset = Sucursal.objects.filter(
            activa=True
        ).order_by('nombre')
        
        # ========== CONFIGURACIÓN UNIDAD_INVENTARIO ==========
        # Inicialmente, el campo de unidad está vacío
        # Se llenará dinámicamente con JavaScript cuando se seleccione un producto
        self.fields['unidad_inventario'].queryset = UnidadInventario.objects.none()
        self.fields['unidad_inventario'].required = False
        
        # ========== CONFIGURACIÓN ORDEN_SERVICIO ==========
        # El campo orden_servicio es oculto y se llenará automáticamente vía JavaScript
        # No mostramos todas las órdenes, se busca/crea por orden_cliente
        self.fields['orden_servicio'].required = False
        
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
        
        # ========== CONFIGURACIÓN TECNICO_ASIGNADO ==========
        # Cargar solo técnicos de laboratorio activos
        # El campo cargo contiene "TECNICO DE LABORATORIO" para los técnicos
        self.fields['tecnico_asignado'].queryset = Empleado.objects.filter(
            activo=True,
            cargo__icontains='TECNICO DE LABORATORIO'
        ).order_by('nombre_completo')
        
        # Inicialmente no requerido - JavaScript lo hará requerido dinámicamente
        self.fields['tecnico_asignado'].required = False
    
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
    
    def clean(self):
        """
        Validación a nivel de formulario completo.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        --------------------------------
        El método clean() se ejecuta después de validar cada campo individualmente.
        Aquí validamos reglas que dependen de múltiples campos.
        
        ACTUALIZADO (Enero 2026):
        - Valida que técnico sea obligatorio para servicio_tecnico
        - Valida que se hayan seleccionado exactamente la cantidad de unidades solicitada
        """
        cleaned_data = super().clean()
        tipo_solicitud = cleaned_data.get('tipo_solicitud')
        tecnico_asignado = cleaned_data.get('tecnico_asignado')
        cantidad = cleaned_data.get('cantidad', 0)
        
        # Tipos que requieren técnico obligatorio: servicio_tecnico y venta_mostrador
        # Ambos tipos generan una OrdenServicio que necesita técnico asignado
        tipos_requieren_tecnico = ['servicio_tecnico', 'venta_mostrador']
        
        if tipo_solicitud in tipos_requieren_tecnico and not tecnico_asignado:
            tipo_display = 'Servicio Técnico' if tipo_solicitud == 'servicio_tecnico' else 'Venta Mostrador'
            raise ValidationError({
                'tecnico_asignado': f'Debe seleccionar un técnico de laboratorio para solicitudes de {tipo_display}.'
            })
        
        # ========== VALIDACIÓN: Unidades seleccionadas (NUEVO) ==========
        # Obtener IDs de unidades seleccionadas del POST
        unidades_seleccionadas_str = self.data.get('unidades_seleccionadas', '')
        
        if unidades_seleccionadas_str:
            # Parsear IDs
            try:
                unidades_ids = [int(id_str.strip()) for id_str in unidades_seleccionadas_str.split(',') if id_str.strip()]
            except (ValueError, AttributeError):
                raise ValidationError('Error al procesar las unidades seleccionadas.')
            
            # Validar que la cantidad de unidades seleccionadas coincida con la cantidad solicitada
            if len(unidades_ids) != cantidad:
                raise ValidationError(
                    f'Debe seleccionar exactamente {cantidad} unidad(es). '
                    f'Has seleccionado {len(unidades_ids)}.'
                )
            
            # Validar que las unidades existan y estén disponibles
            from almacen.models import UnidadInventario
            unidades = UnidadInventario.objects.filter(id__in=unidades_ids, disponibilidad='disponible')
            
            if unidades.count() != len(unidades_ids):
                raise ValidationError('Algunas unidades seleccionadas no están disponibles.')
            
            # Almacenar las unidades validadas en cleaned_data para usarlas después
            cleaned_data['unidades_ids'] = unidades_ids
        else:
            # Si no hay unidades seleccionadas, validar que haya suficientes unidades disponibles
            producto = cleaned_data.get('producto')
            if producto:
                from almacen.models import UnidadInventario
                unidades_disponibles = UnidadInventario.objects.filter(
                    producto=producto,
                    disponibilidad='disponible'
                ).count()
                
                if unidades_disponibles < cantidad:
                    raise ValidationError(
                        f'No hay suficientes unidades disponibles. '
                        f'Disponibles: {unidades_disponibles}, Solicitadas: {cantidad}. '
                        f'Debes seleccionar las unidades específicas.'
                    )
        
        return cleaned_data


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
            # orden_servicio_origen se maneja con campo personalizado (buscador AJAX)
            # El widget es HiddenInput porque el template usa su propio input de búsqueda
            'orden_servicio_origen': forms.HiddenInput(attrs={
                'id': 'orden_servicio_origen_id_fallback',
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


# ============================================================================
# FORMULARIOS: SOLICITUD DE COTIZACIÓN (MULTI-PROVEEDOR)
# ============================================================================

class SolicitudCotizacionForm(forms.ModelForm):
    """
    Formulario para crear y editar Solicitudes de Cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Este formulario crea la "cabecera" de una cotización multi-proveedor.
    
    El campo más importante es 'numero_orden_cliente' que permite buscar
    la orden de servicio a la cual se vinculará esta cotización.
    
    NUEVO: Modo "Sin Orden Activa"
    ------------------------------
    Si aún no existe una orden de servicio (ej: cotización preventiva),
    se puede marcar 'sin_orden_activa' y capturar un 'folio_referencia'
    (típicamente el número de serie del equipo) como identificador temporal.
    
    Cuando posteriormente se cree la orden y se reciba la pieza, se podrá
    vincular manualmente la orden desde el formulario de Editar Unidad.
    
    La búsqueda se realiza mediante AJAX usando el endpoint existente
    'api_buscar_crear_orden' que acepta números tipo OOW-12345 o FL-67890.
    
    Campos:
    - numero_orden_cliente: Para buscar y vincular con OrdenServicio
    - sin_orden_activa: Checkbox para modo sin orden
    - folio_referencia: Identificador temporal cuando no hay orden
    - observaciones: Notas internas sobre la solicitud
    
    Los demás campos (numero_solicitud, estado, fechas) se manejan
    automáticamente por el sistema.
    """
    
    class Meta:
        model = SolicitudCotizacion
        fields = [
            'numero_orden_cliente',
            'sin_orden_activa',
            'folio_referencia',
            'observaciones',
        ]
        widgets = {
            'numero_orden_cliente': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: OOW-12345 o FL-67890',
                'id': 'numero_orden_cliente',
                'autocomplete': 'off',
            }),
            'sin_orden_activa': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'sin_orden_activa',
            }),
            'folio_referencia': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Número de serie del equipo',
                'id': 'folio_referencia',
                'style': 'text-transform: uppercase;',
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Notas internas sobre esta solicitud de cotización...',
            }),
        }
        labels = {
            'numero_orden_cliente': 'Número de Orden del Cliente',
            'sin_orden_activa': 'Sin orden activa',
            'folio_referencia': 'Folio de Referencia',
            'observaciones': 'Observaciones Internas',
        }
        help_texts = {
            'numero_orden_cliente': 'Ingresa el número de orden y presiona Tab para buscar',
            'sin_orden_activa': 'Marcar si aún no existe una orden de servicio para esta cotización',
            'folio_referencia': 'Identificador temporal (ej: número de serie) - Se convertirá a mayúsculas',
            'observaciones': 'Estas notas son internas, no se muestran al cliente',
        }
    
    def clean_folio_referencia(self):
        """
        Normaliza el folio de referencia a mayúsculas.
        """
        folio = self.cleaned_data.get('folio_referencia', '').strip()
        return folio.upper() if folio else ''
    
    def clean(self):
        """
        Validación cruzada de campos.
        
        EXPLICACIÓN:
        - Si sin_orden_activa=False: Debe haber un numero_orden_cliente válido
        - Si sin_orden_activa=True: Debe haber un folio_referencia
        """
        cleaned_data = super().clean()
        sin_orden = cleaned_data.get('sin_orden_activa', False)
        numero_orden = cleaned_data.get('numero_orden_cliente', '').strip()
        folio = cleaned_data.get('folio_referencia', '').strip()
        
        if sin_orden:
            # Modo sin orden: requiere folio_referencia
            if not folio:
                self.add_error(
                    'folio_referencia',
                    'Debes ingresar un folio de referencia cuando no hay orden activa.'
                )
            # Limpiar el número de orden si está en modo sin orden
            cleaned_data['numero_orden_cliente'] = ''
        else:
            # Modo con orden: requiere y valida numero_orden_cliente
            if not numero_orden:
                self.add_error(
                    'numero_orden_cliente',
                    'Debes ingresar un número de orden o marcar "Sin orden activa".'
                )
            else:
                # Validar que la orden exista
                numero = numero_orden.upper()
                from servicio_tecnico.models import DetalleEquipo
                
                try:
                    detalle = DetalleEquipo.objects.select_related('orden').get(
                        orden_cliente__iexact=numero
                    )
                    # Guardar la orden encontrada para usarla en el save
                    self._orden_servicio_encontrada = detalle.orden
                    cleaned_data['numero_orden_cliente'] = numero
                except DetalleEquipo.DoesNotExist:
                    self.add_error(
                        'numero_orden_cliente',
                        f'No se encontró una orden de servicio con el número "{numero}". '
                        'Verifica que el número sea correcto o marca "Sin orden activa".'
                    )
        
        return cleaned_data
    
    def save(self, commit=True):
        """
        Guarda la solicitud vinculando la orden de servicio encontrada.
        
        EXPLICACIÓN:
        - Si hay orden encontrada: la vincula
        - Si está en modo sin_orden: deja orden_servicio=None
        """
        instance = super().save(commit=False)
        
        # Vincular la orden de servicio si se encontró (modo normal)
        if hasattr(self, '_orden_servicio_encontrada') and not instance.sin_orden_activa:
            instance.orden_servicio = self._orden_servicio_encontrada
        elif instance.sin_orden_activa:
            # Modo sin orden: asegurar que no hay orden vinculada
            instance.orden_servicio = None
        
        if commit:
            instance.save()
        
        return instance


class LineaCotizacionForm(forms.ModelForm):
    """
    Formulario para cada línea de la cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Este formulario representa UNA línea dentro de la solicitud:
    - Qué producto se cotiza (del catálogo de almacén)
    - Descripción específica de la pieza
    - De qué proveedor se comprará
    - Cantidad y precio
    
    Se usa como parte de un FORMSET (conjunto de formularios) que permite
    agregar múltiples líneas dinámicamente desde JavaScript.
    
    Campos principales:
    - producto: Selector del catálogo de almacén
    - descripcion_pieza: Descripción específica (ej: "RAM DDR4 16GB Kingston")
    - proveedor: De dónde se comprará
    - cantidad: Cuántas unidades
    - costo_unitario: Precio por unidad
    - notas: Observaciones adicionales
    """
    
    class Meta:
        model = LineaCotizacion
        fields = [
            'producto',
            'descripcion_pieza',
            'proveedor',
            'cantidad',
            'costo_unitario',
            'tiempo_entrega_estimado',
            'notas',
        ]
        widgets = {
            'producto': forms.Select(attrs={
                'class': 'form-select form-select-sm producto-select',
            }),
            'descripcion_pieza': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Ej: RAM DDR4 16GB 3200MHz Kingston Fury',
            }),
            'proveedor': forms.Select(attrs={
                'class': 'form-select form-select-sm proveedor-select',
            }),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm',
                'min': 1,
                'value': 1,
            }),
            'costo_unitario': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm',
                'min': 0,
                'step': '0.01',
                'placeholder': '0.00',
            }),
            'tiempo_entrega_estimado': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm',
                'min': 0,
                'placeholder': 'días',
            }),
            'notas': forms.Textarea(attrs={
                'class': 'form-control form-control-sm',
                'rows': 1,
                'placeholder': 'Notas adicionales...',
            }),
        }
        labels = {
            'producto': 'Producto',
            'descripcion_pieza': 'Descripción de la Pieza',
            'proveedor': 'Proveedor',
            'cantidad': 'Cant.',
            'costo_unitario': 'Costo Unit.',
            'tiempo_entrega_estimado': 'Entrega (días)',
            'notas': 'Notas',
        }
    
    def __init__(self, *args, **kwargs):
        """
        Personaliza los querysets de los campos relacionales.
        
        EXPLICACIÓN:
        - Solo muestra productos activos
        - Solo muestra proveedores activos
        - Ordena alfabéticamente para facilitar búsqueda
        """
        super().__init__(*args, **kwargs)
        
        # Filtrar productos activos y ordenar por nombre
        self.fields['producto'].queryset = ProductoAlmacen.objects.filter(
            activo=True
        ).order_by('nombre')
        self.fields['producto'].empty_label = '-- Seleccionar Producto --'
        
        # Filtrar proveedores activos y ordenar por nombre
        self.fields['proveedor'].queryset = Proveedor.objects.filter(
            activo=True
        ).order_by('nombre')
        self.fields['proveedor'].empty_label = '-- Seleccionar Proveedor --'
    
    def clean(self):
        """
        Validaciones que involucran múltiples campos.
        """
        cleaned_data = super().clean()
        producto = cleaned_data.get('producto')
        descripcion = cleaned_data.get('descripcion_pieza')
        costo = cleaned_data.get('costo_unitario')
        
        # La descripción es obligatoria
        if not descripcion:
            self.add_error(
                'descripcion_pieza',
                'La descripción de la pieza es obligatoria.'
            )
        
        # El costo debe ser mayor a 0
        if costo is not None and costo <= 0:
            self.add_error(
                'costo_unitario',
                'El costo debe ser mayor a 0.'
            )
        
        return cleaned_data


# Formset para las líneas de cotización
# EXPLICACIÓN PARA PRINCIPIANTES:
# --------------------------------
# Un "formset" es un conjunto de formularios del mismo tipo.
# Permite manejar múltiples instancias del mismo modelo en una sola vista.
# 
# Parámetros importantes:
# - model: El modelo padre (SolicitudCotizacion)
# - model: El modelo hijo (LineaCotizacion)
# - form: El formulario a usar para cada línea
# - extra: Cuántos formularios vacíos mostrar inicialmente
# - can_delete: Si se permite eliminar líneas existentes
# - min_num: Mínimo de formularios (1 = al menos una línea)
# - validate_min: Si validar el mínimo

LineaCotizacionFormSet = inlineformset_factory(
    SolicitudCotizacion,  # Modelo padre
    LineaCotizacion,      # Modelo hijo
    form=LineaCotizacionForm,
    extra=1,              # 1 formulario vacío inicial
    can_delete=True,      # Permite eliminar líneas
    min_num=1,            # Al menos 1 línea
    validate_min=True,    # Validar que haya al menos 1
)


class SolicitudCotizacionFiltroForm(forms.Form):
    """
    Formulario de filtros para la lista de solicitudes de cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Este formulario NO guarda datos en la base de datos.
    Su único propósito es proporcionar campos para filtrar la lista
    de solicitudes en la vista de lista.
    """
    
    estado = forms.ChoiceField(
        choices=[('', 'Todos los estados')] + list(ESTADO_SOLICITUD_COTIZACION_CHOICES),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm',
        }),
        label='Estado',
    )
    
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control form-control-sm',
            'type': 'date',
        }),
        label='Desde',
    )
    
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control form-control-sm',
            'type': 'date',
        }),
        label='Hasta',
    )
    
    buscar = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Buscar por número de solicitud u orden...',
        }),
        label='Buscar',
    )


class RespuestaLineaCotizacionForm(forms.Form):
    """
    Formulario para registrar la respuesta del cliente a una línea.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Este formulario se usa cuando Recepción registra si el cliente
    aprobó o rechazó una línea específica de la cotización.
    
    Es un Form simple (no ModelForm) porque solo necesitamos capturar
    la decisión y opcionalmente el motivo del rechazo.
    """
    
    decision = forms.ChoiceField(
        choices=[
            ('aprobar', 'Aprobar'),
            ('rechazar', 'Rechazar'),
        ],
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input',
        }),
        label='Decisión del Cliente',
    )
    
    motivo_rechazo = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Motivo del rechazo (obligatorio si rechaza)...',
        }),
        label='Motivo del Rechazo',
    )
    
    def clean(self):
        """
        Valida que si la decisión es rechazar, haya un motivo.
        """
        cleaned_data = super().clean()
        decision = cleaned_data.get('decision')
        motivo = cleaned_data.get('motivo_rechazo')
        
        if decision == 'rechazar' and not motivo:
            self.add_error(
                'motivo_rechazo',
                'Debes indicar el motivo del rechazo.'
            )
        
        return cleaned_data


# ============================================================================
# FORMULARIO: IMAGEN DE LÍNEA DE COTIZACIÓN
# ============================================================================
class ImagenLineaCotizacionForm(forms.ModelForm):
    """
    Formulario para subir imágenes de referencia a una línea de cotización.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Este formulario permite al usuario subir una imagen junto con una
    descripción opcional. La imagen se asocia a una línea específica
    de la cotización para servir como referencia visual.
    
    Características:
    - Acepta archivos de imagen (JPG, PNG, GIF, WebP)
    - Tamaño máximo: 10MB (después se comprime si supera 2MB)
    - La descripción es opcional pero recomendada
    
    Validaciones automáticas:
    - El modelo valida el límite de 5 imágenes por línea
    - El modelo comprime automáticamente si supera 2MB
    - Se valida la extensión del archivo
    """
    
    class Meta:
        model = ImagenLineaCotizacion
        fields = ['imagen', 'descripcion']
        widgets = {
            'imagen': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/jpeg,image/png,image/gif,image/webp',
            }),
            'descripcion': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Vista frontal del componente, Etiqueta con modelo...',
                'maxlength': 200,
            }),
        }
        labels = {
            'imagen': 'Imagen de Referencia',
            'descripcion': 'Descripción (opcional)',
        }
        help_texts = {
            'imagen': 'Formatos: JPG, PNG, GIF, WebP. Máximo 10MB. Se comprime automáticamente si supera 2MB.',
            'descripcion': 'Breve descripción de qué muestra la imagen.',
        }
    
    def __init__(self, *args, linea=None, **kwargs):
        """
        Inicializa el formulario con la línea de cotización.
        
        EXPLICACIÓN:
        Recibimos la línea como parámetro para:
        1. Validar el límite de imágenes
        2. Mostrar cuántas imágenes quedan disponibles
        
        Args:
            linea: Instancia de LineaCotizacion (opcional en __init__, requerida en clean)
        """
        super().__init__(*args, **kwargs)
        self.linea = linea
        
        # Si tenemos la línea, mostrar cuántas imágenes quedan
        if linea:
            restantes = ImagenLineaCotizacion.imagenes_restantes(linea)
            if restantes == 0:
                self.fields['imagen'].widget.attrs['disabled'] = True
                self.fields['imagen'].help_text = (
                    '⚠️ Se alcanzó el límite de 5 imágenes para esta línea.'
                )
            else:
                self.fields['imagen'].help_text = (
                    f'Puedes subir hasta {restantes} imagen(es) más. '
                    f'Formatos: JPG, PNG, GIF, WebP. Máximo 10MB.'
                )
    
    def clean_imagen(self):
        """
        Valida el archivo de imagen.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        --------------------------------
        Este método se ejecuta automáticamente cuando Django procesa
        el formulario. Aquí validamos:
        
        1. Que se haya seleccionado un archivo
        2. Que el archivo no sea demasiado grande (10MB máximo)
        3. Que la extensión sea válida
        
        Si algo está mal, lanzamos un ValidationError que Django
        mostrará al usuario junto al campo correspondiente.
        
        Returns:
            El archivo de imagen validado
            
        Raises:
            ValidationError: Si la validación falla
        """
        imagen = self.cleaned_data.get('imagen')
        
        if not imagen:
            raise ValidationError('Debes seleccionar una imagen.')
        
        # Validar tamaño máximo (10MB)
        max_size = 10 * 1024 * 1024  # 10MB en bytes
        if imagen.size > max_size:
            raise ValidationError(
                f'El archivo es demasiado grande ({imagen.size // (1024*1024)}MB). '
                f'El tamaño máximo es 10MB.'
            )
        
        # Validar extensión
        extensiones_validas = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        import os
        ext = os.path.splitext(imagen.name)[1].lower()
        if ext not in extensiones_validas:
            raise ValidationError(
                f'Extensión "{ext}" no válida. '
                f'Usa: {", ".join(extensiones_validas)}'
            )
        
        return imagen
    
    def clean(self):
        """
        Validaciones que involucran múltiples campos y el límite de imágenes.
        
        EXPLICACIÓN:
        Aquí validamos que la línea no haya alcanzado el límite de 5 imágenes.
        Esta validación es importante porque previene que se suban más
        imágenes de las permitidas, incluso si el usuario intenta hacerlo
        manipulando el formulario.
        """
        cleaned_data = super().clean()
        
        # Validar límite de imágenes si tenemos la línea
        if self.linea and cleaned_data.get('imagen'):
            if not ImagenLineaCotizacion.puede_agregar_imagen(self.linea):
                raise ValidationError(
                    f'Esta línea ya tiene el máximo de '
                    f'{ImagenLineaCotizacion.MAX_IMAGENES_POR_LINEA} imágenes.'
                )
        
        return cleaned_data
    
    def save(self, commit=True, user=None):
        """
        Guarda la imagen asociándola a la línea y al usuario.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        --------------------------------
        Este método extiende el save() normal para:
        1. Asociar la imagen a la línea de cotización
        2. Registrar qué usuario subió la imagen
        
        Args:
            commit: Si guardar inmediatamente en la BD (default: True)
            user: Usuario que está subiendo la imagen
            
        Returns:
            Instancia de ImagenLineaCotizacion guardada
        """
        instance = super().save(commit=False)
        
        # Asociar la línea si se proporcionó
        if self.linea:
            instance.linea = self.linea
        
        # Asociar el usuario si se proporcionó
        if user:
            instance.subido_por = user
        
        if commit:
            instance.save()
        
        return instance
