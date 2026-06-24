"""
Generador de PDF para Cotización al Cliente — Almacén SIC
==========================================================

EXPLICACIÓN PARA PRINCIPIANTES:
Este módulo genera el PDF profesional de cotización que se envía directamente
al cliente final. Sigue el mismo estilo visual que el PDF de diagnóstico SIC:
headers navy azul, filas verdes para piezas necesarias, amarillas para opcionales.

Estructura del PDF generado:
1. Header: Logo SIC + nombre empresa + fecha + folio
2. Título del tipo de servicio (ej: "Diagnóstico + Reparación Estándar")
3. Datos del cliente (nombre, RFC, email, teléfono, centro de servicio)
4. Datos del equipo (marca, modelo, tipo, service tag)
5. Tabla de productos/servicios (con precios ya con margen aplicado, sin IVA)
6. Sección Cotización (totales: sin IVA, con IVA, descuento diagnóstico si aplica)

Uso básico:
    from almacen.utils.pdf_cotizacion_cliente import PDFCotizacionCliente
    gen = PDFCotizacionCliente(solicitud=sol, tipo_servicio='estandar', items=lista_items, ...)
    resultado = gen.generar_pdf()
    if resultado['success']:
        buffer = resultado['buffer']   # BytesIO — listo para adjuntar en email
"""

import io
import logging
from decimal import Decimal
from datetime import date
from pathlib import Path
from typing import Optional, List, Dict, Any

# ReportLab — generación de PDFs
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable, Image as RLImage
)
from reportlab.platypus.flowables import Flowable

# Pillow — manejo de imágenes (logo PNG → compatible con ReportLab)
try:
    from PIL import Image as PILImage
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

# Django
from django.conf import settings
from django.contrib.staticfiles import finders

# python-decouple — lectura de variables de entorno
from decouple import config as env_config

logger = logging.getLogger('almacen')


# =============================================================================
# CONSTANTES Y CONFIGURACIÓN
# =============================================================================

# Colores corporativos SIC (idénticos al PDF de diagnóstico)
COLOR_NAVY          = colors.HexColor('#003366')   # Header de sección — azul marino
COLOR_NAVY_LIGHT    = colors.HexColor('#1d4e8f')   # Subheader de tabla
COLOR_VERDE_BG      = colors.HexColor('#C6EFCE')   # Fila "Necesaria" — verde claro
COLOR_VERDE_TEXTO   = colors.HexColor('#375623')   # Texto sobre fondo verde
COLOR_AMARILLO_BG   = colors.HexColor('#FFF2CC')   # Fila "Opcional" — amarillo claro
COLOR_AMARILLO_TEXTO = colors.HexColor('#7D6608')  # Texto sobre fondo amarillo
COLOR_GRIS_ALT      = colors.HexColor('#F2F2F2')   # Fila alternada en tabla totales
COLOR_GRIS_BORDE    = colors.HexColor('#CCCCCC')   # Bordes de tabla
COLOR_BLANCO        = colors.white
COLOR_NEGRO         = colors.black
COLOR_AZUL_TOTAL    = colors.HexColor('#003366')   # Filas de totales importantes

# Márgenes del documento
MARGEN = 15 * mm

# Nombres públicos por tipo de servicio
TIPO_SERVICIO_NOMBRES: Dict[str, str] = {
    'mostrador': 'Venta Mostrador y Cotización de Partes',
    'estandar':  'Diagnóstico + Reparación Estándar',
    'express':   'Diagnóstico + Reparación Express',
    'alta_gama': 'Diagnóstico + Reparación Alta Gama',
    'server':    'Cotización de Partes + Reparación de Servidor',
}

def _fijos(val: str) -> List[float]:
    """Convierte una cadena 'a,b,c' del .env en lista de floats."""
    return [float(x.strip()) for x in val.split(',') if x.strip()]


def _cargar_profit_config() -> Dict[str, Dict]:
    """
    Construye PROFIT_CONFIG leyendo los valores desde variables de entorno.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    En lugar de dejar los márgenes de ganancia visibles en el código fuente
    (donde cualquier desarrollador con acceso al repositorio podría verlos),
    se leen del archivo .env que NO se sube a git.

    Si una variable no existe en .env se usa el valor por defecto indicado,
    garantizando que el sistema funcione aunque el .env esté incompleto.
    """
    return {
        'mostrador': {
            'profit_target': env_config('PROFIT_MOSTRADOR',    cast=float, default=0.42),
            'costos_fijos':  _fijos(env_config('COSTOS_FIJOS_MOSTRADOR',  default='50,40')),
            'diagnostico':   env_config('DIAGNOSTICO_MOSTRADOR', cast=float, default=0),
        },
        'estandar': {
            'profit_target': env_config('PROFIT_ESTANDAR',     cast=float, default=0.36),
            'costos_fijos':  _fijos(env_config('COSTOS_FIJOS_ESTANDAR',   default='25,160')),
            'diagnostico':   env_config('DIAGNOSTICO_ESTANDAR',  cast=float, default=570),
        },
        'express': {
            'profit_target': env_config('PROFIT_EXPRESS',      cast=float, default=0.44),
            'costos_fijos':  _fijos(env_config('COSTOS_FIJOS_EXPRESS',    default='25,160')),
            'diagnostico':   env_config('DIAGNOSTICO_EXPRESS',   cast=float, default=774),
        },
        'alta_gama': {
            'profit_target': env_config('PROFIT_ALTA_GAMA',    cast=float, default=0.44),
            'costos_fijos':  _fijos(env_config('COSTOS_FIJOS_ALTA_GAMA',  default='25,160')),
            'diagnostico':   env_config('DIAGNOSTICO_ALTA_GAMA', cast=float, default=864),
        },
        'server': {
            'profit_target': env_config('PROFIT_SERVER',       cast=float, default=0.59),
            'costos_fijos':  _fijos(env_config('COSTOS_FIJOS_SERVER',     default='72,49,20,350')),
            'diagnostico':   env_config('DIAGNOSTICO_SERVER',   cast=float, default=1000),
        },
    }


# Se construye una sola vez al importar el módulo (igual que antes,
# pero ahora los valores vienen del .env en lugar del código fuente).
PROFIT_CONFIG: Dict[str, Dict] = _cargar_profit_config()


# =============================================================================
# FUNCIÓN AUXILIAR DE CÁLCULO DE PROFIT
# =============================================================================

def calcular_precio_cliente(
    costo_piezas: float,
    tipo_servicio: str = 'estandar',
    incluir_descuento_diagnostico: bool = True
) -> Dict[str, Any]:
    """
    Calcula los precios al cliente según la matriz de profit de SIC.

    EXPLICACIÓN:
    Esta función implementa exactamente la misma lógica de la función Python
    definida en el diseño del módulo. Aplica el profit_target para calcular
    el precio al público (sin margen visible).

    Args:
        costo_piezas   : Costo interno total de piezas (puede ser lista o número).
        tipo_servicio  : Clave del tipo ('mostrador', 'estandar', 'express', etc.)
        incluir_descuento_diagnostico: Si True, calcula el precio con deducción.

    Returns:
        Dict con los resultados del cálculo (precios sin IVA y con IVA).
    """
    # Validar que el tipo de servicio exista en la configuración
    if tipo_servicio not in PROFIT_CONFIG:
        tipo_servicio = 'estandar'

    perfil = PROFIT_CONFIG[tipo_servicio]
    target = perfil['profit_target']
    factor_ganancia = 1 - target  # Divisor para aplicar el margen

    # Convertir a float para operaciones numéricas
    if isinstance(costo_piezas, (list, tuple)):
        costo_total = float(sum(costo_piezas))
    else:
        costo_total = float(costo_piezas)

    # Precio de piezas al cliente (con margen aplicado)
    precio_piezas_cliente = costo_total / factor_ganancia

    # Precio de costos fijos al cliente (con mismo margen)
    precio_fijos_cliente = sum(c / factor_ganancia for c in perfil['costos_fijos'])

    # Total de costos internos (solo para auditoría, no se muestra al cliente)
    total_costos_internos = costo_total + sum(perfil['costos_fijos'])

    # Precio sin IVA = piezas con margen + fijos con margen + diagnóstico (sin margen)
    precio_sin_iva = precio_piezas_cliente + precio_fijos_cliente + perfil['diagnostico']

    # Total con IVA (16%)
    precio_con_iva = precio_sin_iva * 1.16

    # Deducción de diagnóstico (se aplica con su IVA incluido)
    precio_menos_diagnostico_iva = None
    if incluir_descuento_diagnostico and perfil['diagnostico'] > 0:
        diagnostico_con_iva = perfil['diagnostico'] * 1.16
        precio_menos_diagnostico_iva = precio_con_iva - diagnostico_con_iva

    return {
        'servicio_nombre':           TIPO_SERVICIO_NOMBRES.get(tipo_servicio, 'Cotización'),
        'total_costos_internos':     round(total_costos_internos, 2),
        'precio_piezas_sin_iva':     round(precio_piezas_cliente, 2),
        'precio_fijos_sin_iva':      round(precio_fijos_cliente, 2),
        'diagnostico':               perfil['diagnostico'],
        'precio_sin_iva':            round(precio_sin_iva, 2),
        'precio_con_iva':            round(precio_con_iva, 2),
        'precio_menos_diagnostico':  round(precio_menos_diagnostico_iva, 2) if precio_menos_diagnostico_iva is not None else None,
        'factor_ganancia':           factor_ganancia,
        'profit_target':             target,
    }


def calcular_precio_unitario_cliente(costo_unitario: float, tipo_servicio: str) -> float:
    """
    Calcula el precio unitario al cliente para UN solo ítem.

    EXPLICACIÓN:
    Usa el mismo factor de ganancia que calcular_precio_cliente() pero
    aplicado a un costo individual (para mostrar precios por pieza en la tabla).

    Args:
        costo_unitario  : Costo interno de la pieza/servicio.
        tipo_servicio   : Clave del tipo de servicio.

    Returns:
        float: Precio al cliente sin IVA.
    """
    if tipo_servicio not in PROFIT_CONFIG:
        tipo_servicio = 'estandar'
    factor = 1 - PROFIT_CONFIG[tipo_servicio]['profit_target']
    return float(costo_unitario) / factor


# =============================================================================
# CLASE PRINCIPAL DEL GENERADOR PDF
# =============================================================================

class PDFCotizacionCliente:
    """
    Generador de PDF de cotización para enviar al cliente.

    EXPLICACIÓN:
    Esta clase construye el PDF usando ReportLab Platypus (SimpleDocTemplate +
    Flowables). El estilo visual sigue fielmente el PDF de diagnóstico SIC:
    - Headers de sección con fondo navy (#003366) y texto blanco
    - Filas verdes para piezas NECESARIAS
    - Filas amarillas para ítems OPCIONALES
    - Totales destacados con fondo navy

    Uso:
        items = [
            {'descripcion': 'Memoria RAM 8GB', 'cantidad': 1, 'costo_unitario': 1500,
             'es_necesaria': True, 'dias_entrega': 15, 'es_servicio': False},
        ]
        gen = PDFCotizacionCliente(solicitud, tipo_servicio='estandar', items=items)
        resultado = gen.generar_pdf()
        buffer_bytes = resultado['buffer'].getvalue()   # Para adjuntar en email
    """

    def __init__(
        self,
        solicitud,
        tipo_servicio: str,
        items: List[Dict],
        titulo_propuesta: str = '',
        incluir_descuento_diagnostico: bool = True,
        mano_de_obra_override: Optional[float] = None,
        pais_config: Optional[Dict] = None,
    ):
        """
        Inicializa el generador con todos los parámetros de la propuesta.

        Args:
            solicitud                   : Instancia de SolicitudCotizacion.
            tipo_servicio               : 'mostrador', 'estandar', 'express', 'alta_gama', 'server'.
            items                       : Lista de dicts con los ítems a incluir en el PDF.
            titulo_propuesta            : Título personalizado (usa nombre del perfil si está vacío).
            incluir_descuento_diagnostico: Si True y hay diagnóstico, muestra precio con deducción.
            mano_de_obra_override       : Si el usuario editó la mano de obra en el modal (float).
            pais_config                 : Dict con info del país activo (empresa, ciudad, etc.).
        """
        self.solicitud = solicitud
        self.tipo_servicio = tipo_servicio if tipo_servicio in PROFIT_CONFIG else 'estandar'
        self.items = items
        self.incluir_descuento_diagnostico = incluir_descuento_diagnostico
        self.mano_de_obra_override = mano_de_obra_override
        self.pais_config = pais_config or {}

        # Título del PDF: personalizado o nombre del perfil
        self.titulo = (
            titulo_propuesta
            or TIPO_SERVICIO_NOMBRES.get(self.tipo_servicio, 'Cotización de Servicio')
        )

        # Estilos de texto para Platypus
        self._estilos = getSampleStyleSheet()
        self._configurar_estilos()

    # -------------------------------------------------------------------------
    # ESTILOS DE TEXTO
    # -------------------------------------------------------------------------

    def _configurar_estilos(self) -> None:
        """
        Define los estilos de párrafo usados en el PDF.

        EXPLICACIÓN:
        Cada ParagraphStyle define fuente, tamaño, color y alineación.
        Los usamos para garantizar consistencia visual en todo el documento.
        """
        # Estilo para el nombre de la empresa en el header
        self._estilos.add(ParagraphStyle(
            'EmpresaHeader',
            fontName='Helvetica-Bold',
            fontSize=12,
            textColor=COLOR_NEGRO,
            alignment=TA_RIGHT,
            spaceAfter=2,
        ))
        # Estilo para fecha y folio debajo del header
        self._estilos.add(ParagraphStyle(
            'FechaFolio',
            fontName='Helvetica',
            fontSize=9,
            textColor=COLOR_NEGRO,
            alignment=TA_LEFT,
            spaceBefore=2,
        ))
        # Estilo para el título principal (tipo de servicio)
        self._estilos.add(ParagraphStyle(
            'TituloPrincipal',
            fontName='Helvetica-Bold',
            fontSize=13,
            textColor=COLOR_NAVY,
            alignment=TA_CENTER,
            spaceBefore=4,
            spaceAfter=4,
        ))
        # Estilo para los encabezados de sección (texto en celda navy)
        self._estilos.add(ParagraphStyle(
            'HeaderSeccion',
            fontName='Helvetica-Bold',
            fontSize=10,
            textColor=COLOR_BLANCO,
            alignment=TA_CENTER,
        ))
        # Estilo para etiquetas en el cuerpo (campo: valor)
        self._estilos.add(ParagraphStyle(
            'Etiqueta',
            fontName='Helvetica-Bold',
            fontSize=8,
            textColor=COLOR_NEGRO,
            alignment=TA_LEFT,
        ))
        # Estilo para valores en el cuerpo
        self._estilos.add(ParagraphStyle(
            'Valor',
            fontName='Helvetica',
            fontSize=8,
            textColor=COLOR_NEGRO,
            alignment=TA_LEFT,
        ))
        # Estilo para cabeceras de tabla (texto blanco en fondo navy)
        self._estilos.add(ParagraphStyle(
            'CabeceraTablaNegra',
            fontName='Helvetica-Bold',
            fontSize=8,
            textColor=COLOR_BLANCO,
            alignment=TA_CENTER,
        ))
        # Estilo para las notas del pie de tabla (leyenda Necesaria/Opcional)
        self._estilos.add(ParagraphStyle(
            'NotaTabla',
            fontName='Helvetica',
            fontSize=7,
            textColor=COLOR_NEGRO,
            alignment=TA_LEFT,
        ))
        # Estilo para totales (negrita)
        self._estilos.add(ParagraphStyle(
            'TotalBold',
            fontName='Helvetica-Bold',
            fontSize=9,
            textColor=COLOR_NEGRO,
            alignment=TA_RIGHT,
        ))

    # -------------------------------------------------------------------------
    # MÉTODO PRINCIPAL
    # -------------------------------------------------------------------------

    def generar_pdf(self) -> Dict[str, Any]:
        """
        Genera el PDF completo y lo retorna en un buffer BytesIO.

        EXPLICACIÓN:
        Construye el documento ReportLab en memoria. El buffer puede usarse
        directamente para adjuntar en un email (sin guardar en disco).

        Returns:
            Dict con {'success': bool, 'buffer': BytesIO, 'nombre_archivo': str}
        """
        try:
            buffer = io.BytesIO()

            # Crear el documento ReportLab en memoria (no en disco)
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                leftMargin=MARGEN,
                rightMargin=MARGEN,
                topMargin=MARGEN,
                bottomMargin=MARGEN,
            )

            # Calcular totales para las secciones del PDF
            calculo = self._calcular_totales()

            # Construir la lista de elementos (flowables) del PDF
            elementos = []
            elementos += self._construir_header()
            elementos.append(Spacer(1, 3 * mm))
            elementos += self._construir_titulo()
            elementos.append(Spacer(1, 3 * mm))
            elementos += self._construir_datos_cliente()
            elementos.append(Spacer(1, 3 * mm))
            elementos += self._construir_datos_equipo()
            elementos.append(Spacer(1, 3 * mm))
            elementos += self._construir_tabla_productos(calculo)
            elementos.append(Spacer(1, 3 * mm))
            elementos += self._construir_seccion_cotizacion(calculo)

            # Construir el documento final
            doc.build(elementos)
            buffer.seek(0)

            # Nombre del archivo para el adjunto del email
            numero = self.solicitud.numero_solicitud
            nombre_archivo = f"Cotizacion_{numero}_{self.tipo_servicio}.pdf"

            return {'success': True, 'buffer': buffer, 'nombre_archivo': nombre_archivo}

        except Exception as e:
            logger.error(f"[PDF_COTIZACION] Error al generar PDF: {e}", exc_info=True)
            return {'success': False, 'error': str(e), 'buffer': None}

    # -------------------------------------------------------------------------
    # CÁLCULO DE TOTALES
    # -------------------------------------------------------------------------

    def _calcular_totales(self) -> Dict[str, Any]:
        """
        Aplica la lógica de profit y calcula los totales para el PDF.

        EXPLICACIÓN:
        ─────────────────────────────────────────────────────────────────
        ESTRATEGIA DE PRECIOS REDISTRIBUIDOS
        ─────────────────────────────────────────────────────────────────
        El problema de mostrar `precio_unit = costo / factor` pieza por
        pieza es que la suma de subtotales NO coincide con el TOTAL CON IVA,
        porque la mano de obra y los costos fijos del perfil no aparecen
        como filas en la tabla del cliente.

        Solución: calcular primero el total completo que debe pagar el cliente
        (sin diagnóstico) y luego redistribuirlo proporcionalmente entre los
        ítems de la tabla según el peso relativo de cada uno.

        Fórmula:
            total_distribuible   = Σcostos_brutos + mano_obra + costos_fijos
            total_cliente_sin_iva = total_distribuible / (1 - profit%)

            Para cada ítem:
                peso             = costo_unitario / total_distribuible
                precio_cliente   = peso × total_cliente_sin_iva

        Verificación:
            Σ(precio_cliente_i × cantidad_i) = total_cliente_sin_iva  ✅
            × 1.16                           = TOTAL CON IVA          ✅

        Caso sin ítems (solo mano de obra):
            Se agrega una línea genérica "Servicio de reparación" que
            absorbe todo el total a cobrar, para que el PDF no quede vacío.

        Returns:
            Dict con todos los valores calculados para mostrar en el PDF.
        """
        perfil = PROFIT_CONFIG[self.tipo_servicio]
        factor = 1 - perfil['profit_target']
        mano_obra = float(self.mano_de_obra_override or 0)

        # ── Paso 1: calcular los costos brutos de cada ítem ──────────────────
        # "Bruto" = costo proveedor, sin profit. Solo se usa para calcular pesos.
        items_brutos: List[Dict] = []
        suma_costos_brutos = 0.0

        for item in self.items:
            costo_unit = float(item.get('costo_unitario', 0) or 0)
            cantidad   = int(item.get('cantidad', 1) or 1)
            subtotal_bruto = costo_unit * cantidad

            # Acumular la base total distribuible (costos de ítems)
            suma_costos_brutos += subtotal_bruto

            items_brutos.append({
                **item,
                '_costo_unit_bruto': costo_unit,
                '_subtotal_bruto':   subtotal_bruto,
                '_cantidad':         cantidad,
            })

        # ── Paso 2: calcular el total a cobrar al cliente (sin diagnóstico) ──
        # Todo lo que lleva profit: piezas + mano de obra + costos fijos del perfil.
        # El diagnóstico se maneja aparte como descuento, no va en este total.
        suma_costos_fijos  = sum(perfil['costos_fijos'])
        total_distribuible = suma_costos_brutos + mano_obra + suma_costos_fijos

        # Aplicar el factor de profit sobre toda la base de una sola vez
        total_cliente_sin_iva_sin_diag = total_distribuible / factor if factor > 0 else total_distribuible

        # Precio sin IVA final = total con profit + diagnóstico (cargo fijo sin profit)
        # Se calcula ANTES de la redistribución porque es el número que los ítems
        # deben sumar: Σ(subtotal_item) = precio_sin_iva → Σ × 1.16 = TOTAL CON IVA
        precio_sin_iva = total_cliente_sin_iva_sin_diag + perfil['diagnostico']

        # ── Paso 3: redistribuir el total proporcionalmente entre los ítems ──
        items_calculados: List[Dict] = []

        if suma_costos_brutos > 0:
            # Factor de redistribución:
            #   precio_sin_iva / suma_costos_brutos
            #
            # Se usa precio_sin_iva (CON diagnóstico incluido) para que el diagnóstico
            # quede absorbido proporcionalmente en cada ítem. Así:
            #
            #   Σ(costo_unit_i × factor_redistrib × cantidad_i)
            #   = factor_redistrib × Σ(costo_unit_i × cantidad_i)
            #   = (precio_sin_iva / suma_costos_brutos) × suma_costos_brutos
            #   = precio_sin_iva                                              ✅
            #   × 1.16 = TOTAL CON IVA                                       ✅
            #   - diagnostico × 1.16 = TOTAL A PAGAR                         ✅
            factor_redistrib = precio_sin_iva / suma_costos_brutos

            for item in items_brutos:
                costo_unit = item['_costo_unit_bruto']
                cantidad   = item['_cantidad']

                # Precio unitario redistribuido: absorbe proporcionalmente
                # mano de obra, costos fijos y diagnóstico del perfil.
                precio_unit_cliente = costo_unit * factor_redistrib
                subtotal_cliente    = precio_unit_cliente * cantidad

                # Limpiar campos internos temporales antes de incluir en el resultado
                item_limpio = {k: v for k, v in item.items() if not k.startswith('_')}
                items_calculados.append({
                    **item_limpio,
                    'precio_unitario_cliente': round(precio_unit_cliente, 2),
                    'subtotal_cliente':        round(subtotal_cliente, 2),
                })

        # ── Paso 4: caso sin ítems (solo mano de obra) ───────────────────────
        # Si no hay piezas ni servicios pero sí hay mano de obra o costos fijos,
        # se agrega una línea genérica "Servicio de reparación" para que la tabla
        # del PDF no quede vacía y los totales sigan cuadrando.
        if not items_calculados and precio_sin_iva > 0:
            items_calculados.append({
                'descripcion':             'Servicio de reparación',
                'cantidad':                1,
                'precio_unitario_cliente': round(precio_sin_iva, 2),
                'subtotal_cliente':        round(precio_sin_iva, 2),
                'tiempo_entrega_estimado': None,
                'es_necesaria':            True,
            })

        # ── Paso 5: totales finales ───────────────────────────────────────────
        iva            = precio_sin_iva * 0.16
        precio_con_iva = precio_sin_iva * 1.16

        # Si el cliente ya pagó el diagnóstico al ingresar, se descuenta del total
        precio_menos_diagnostico = None
        if self.incluir_descuento_diagnostico and perfil['diagnostico'] > 0:
            diagnostico_con_iva      = perfil['diagnostico'] * 1.16
            precio_menos_diagnostico = precio_con_iva - diagnostico_con_iva

        return {
            'items_calculados':         items_calculados,
            'mano_obra':                round(mano_obra, 2),
            'precio_piezas_sin_iva':    round(total_cliente_sin_iva_sin_diag, 2),
            'precio_fijos_sin_iva':     round(suma_costos_fijos / factor if factor > 0 else 0, 2),
            'diagnostico':              perfil['diagnostico'],
            'precio_sin_iva':           round(precio_sin_iva, 2),
            'iva':                      round(iva, 2),
            'precio_con_iva':           round(precio_con_iva, 2),
            'precio_menos_diagnostico': round(precio_menos_diagnostico, 2) if precio_menos_diagnostico else None,
        }

    # -------------------------------------------------------------------------
    # SECCIÓN 1: HEADER (Logo + Empresa + Fecha + Folio)
    # -------------------------------------------------------------------------

    def _construir_header(self) -> List:
        """
        Construye el encabezado del documento con logo SIC y datos de la empresa.

        EXPLICACIÓN:
        El header tiene dos columnas: logo a la izquierda, nombre de empresa
        a la derecha. La fecha y el folio aparecen en la segunda fila.
        Si el logo no se encuentra en archivos estáticos, se omite silenciosamente.
        """
        elementos = []

        # Intentar cargar el logo SIC desde archivos estáticos
        logo_flowable = self._obtener_logo()

        # Nombre de la empresa (desde config del país o fallback)
        empresa = self.pais_config.get('empresa_nombre', 'SIC Comercialización y Servicios de México SC')

        # Fila 1: Logo | Nombre empresa
        if logo_flowable:
            fila_header = [[logo_flowable, Paragraph(empresa, self._estilos['EmpresaHeader'])]]
        else:
            fila_header = [['', Paragraph(empresa, self._estilos['EmpresaHeader'])]]

        tabla_header = Table(fila_header, colWidths=[70 * mm, None])
        tabla_header.setStyle(TableStyle([
            ('VALIGN',  (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING',  (0, 0), (0, 0), 0),
            ('RIGHTPADDING', (1, 0), (1, 0), 0),
        ]))
        elementos.append(tabla_header)

        # Separador delgado debajo del header
        elementos.append(Spacer(1, 2 * mm))
        elementos.append(HRFlowable(width='100%', thickness=1, color=COLOR_GRIS_BORDE))
        elementos.append(Spacer(1, 3 * mm))

        # Fila 2: Fecha | Folio
        hoy = date.today()
        dias_semana_es = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        meses_es = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
        fecha_texto = f"{dias_semana_es[hoy.weekday()]} {hoy.day} de {meses_es[hoy.month - 1]} de {hoy.year}"

        folio_texto = self.solicitud.numero_solicitud

        # Si hay orden vinculada con service tag, usar ese como parte del folio
        if self.solicitud.orden_servicio:
            try:
                st = self.solicitud.orden_servicio.detalle_equipo.numero_serie
                if st:
                    folio_texto = f"{folio_texto} / S/T: {st}"
            except Exception:
                pass

        estilo_fecha = ParagraphStyle(
            'FechaFooter',
            fontName='Helvetica',
            fontSize=9,
            textColor=COLOR_NEGRO,
        )
        estilo_folio = ParagraphStyle(
            'FolioFooter',
            fontName='Helvetica',
            fontSize=9,
            textColor=COLOR_NEGRO,
            alignment=TA_RIGHT,
        )

        fila_fecha = [[
            Paragraph(f"Fecha: {fecha_texto}", estilo_fecha),
            Paragraph(f"Folio: {folio_texto}", estilo_folio),
        ]]
        tabla_fecha = Table(fila_fecha, colWidths=[None, None])
        tabla_fecha.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elementos.append(tabla_fecha)

        return elementos

    def _obtener_logo(self) -> Optional[RLImage]:
        """
        Busca el logo SIC en archivos estáticos y lo convierte a RLImage.

        Returns:
            RLImage listo para insertar en la tabla, o None si no se encuentra.
        """
        try:
            # Intentar encontrar el logo PNG principal (con fondo blanco)
            ruta_logo = finders.find('images/logos/logo_sic.png')
            if not ruta_logo:
                ruta_logo = finders.find('images/logos/logo_sic.svg')
            if ruta_logo and ruta_logo.endswith('.png'):
                return RLImage(ruta_logo, width=45 * mm, height=15 * mm, kind='proportional')
        except Exception as e:
            logger.warning(f"[PDF_COTIZACION] No se encontró el logo SIC: {e}")
        return None

    # -------------------------------------------------------------------------
    # SECCIÓN 2: TÍTULO DEL TIPO DE SERVICIO
    # -------------------------------------------------------------------------

    def _construir_titulo(self) -> List:
        """
        Construye la línea de título con el nombre del tipo de servicio.

        EXPLICACIÓN:
        El título aparece centrado en azul marino, mostrando el tipo de
        cotización (ej: "Diagnóstico + Reparación Estándar"). Refleja
        fielmente el diseño del PDF de diagnóstico de referencia.
        """
        return [Paragraph(self.titulo, self._estilos['TituloPrincipal'])]

    # -------------------------------------------------------------------------
    # SECCIÓN 3: DATOS DEL CLIENTE
    # -------------------------------------------------------------------------

    def _construir_datos_cliente(self) -> List:
        """
        Construye la sección "Datos del cliente" con header navy y tabla de datos.

        EXPLICACIÓN:
        Obtiene los datos del cliente de dos fuentes posibles:
        1. Si hay orden de servicio vinculada → usa DetalleEquipo de ST
        2. Si es "sin orden activa" → usa los campos directos de SolicitudCotizacion

        El "Centro de servicio" proviene de la sucursal:
        - Con orden vinculada → orden_servicio.sucursal
        - Sin orden activa → creado_por.empleado.sucursal
        """
        # --- Extracción de datos del cliente ---
        nombre_cliente = ''
        email_cliente  = ''
        telefono       = ''
        rfc            = ''
        centro_servicio = ''

        solicitud = self.solicitud

        # Sucursal según el tipo de solicitud (misma lógica que detalle_solicitud.html)
        if solicitud.orden_servicio:
            try:
                sucursal = solicitud.orden_servicio.sucursal
                if sucursal:
                    centro_servicio = sucursal.nombre
            except Exception:
                pass
        else:
            try:
                sucursal = solicitud.creado_por.empleado.sucursal
                if sucursal:
                    centro_servicio = sucursal.nombre
            except Exception:
                pass

        if solicitud.orden_servicio:
            # Fuente: DetalleEquipo de la orden en servicio técnico
            try:
                det = solicitud.orden_servicio.detalle_equipo
                nombre_cliente = getattr(det, 'nombre_cliente', '') or ''
                email_cliente  = getattr(det, 'email_cliente', '') or ''
                telefono       = getattr(det, 'telefono_cliente', '') or ''
                rfc            = getattr(det, 'rfc_cliente', '') or ''
            except Exception:
                pass
        else:
            # Fuente: campos directos de SolicitudCotizacion (modo sin orden activa)
            nombre_cliente = solicitud.nombre_cliente or ''
            email_cliente  = solicitud.email_cliente or ''
            telefono       = solicitud.telefono_cliente or ''
            rfc            = solicitud.rfc_cliente or ''

        # --- Header de sección (navy + texto blanco) ---
        elementos = [self._crear_header_seccion('Datos del cliente')]

        # --- Tabla de datos del cliente (3 columnas) ---
        # Fila 1: Centro de servicio | Cliente | RFC
        # Fila 2: Atención a | Correo | Teléfono
        st_valor = ''
        if solicitud.orden_servicio:
            try:
                st_valor = solicitud.orden_servicio.detalle_equipo.numero_serie or ''
            except Exception:
                pass
        elif solicitud.service_tag:
            st_valor = solicitud.service_tag

        filas = [
            # Fila 1
            [
                self._celda_etiqueta_valor('Centro de servicio:', centro_servicio or '—'),
                self._celda_etiqueta_valor('Cliente:', nombre_cliente or '—'),
                self._celda_etiqueta_valor('RFC:', rfc or '—'),
            ],
            # Fila 2
            [
                self._celda_etiqueta_valor('Service Tag:', st_valor or '—'),
                self._celda_etiqueta_valor('Correo:', email_cliente or '—'),
                self._celda_etiqueta_valor('Teléfono:', telefono or '—'),
            ],
        ]

        tabla = Table(filas, colWidths=[None, None, None])
        tabla.setStyle(TableStyle([
            ('GRID',        (0, 0), (-1, -1), 0.5, COLOR_GRIS_BORDE),
            ('BACKGROUND',  (0, 0), (-1, -1), COLOR_BLANCO),
            ('VALIGN',      (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING',  (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elementos.append(tabla)
        return elementos

    # -------------------------------------------------------------------------
    # SECCIÓN 4: DATOS DEL EQUIPO
    # -------------------------------------------------------------------------

    def _construir_datos_equipo(self) -> List:
        """
        Construye la sección "Datos del equipo" con marca, modelo, tipo y service tag.

        EXPLICACIÓN:
        Si la solicitud tiene una orden vinculada en servicio técnico, obtiene
        los datos del equipo de DetalleEquipo. Si es "sin orden activa", usa
        los campos de SolicitudCotizacion.
        """
        solicitud = self.solicitud
        marca = modelo = tipo_equipo = service_tag = ''

        if solicitud.orden_servicio:
            try:
                det = solicitud.orden_servicio.detalle_equipo
                marca       = getattr(det, 'marca', '') or ''
                modelo      = getattr(det, 'modelo', '') or ''
                tipo_equipo = getattr(det, 'get_tipo_equipo_display', lambda: '')() or ''
                service_tag = getattr(det, 'numero_serie', '') or ''
            except Exception:
                pass
        else:
            # Usar campos del modo sin orden activa
            marca       = solicitud.get_marca_display() if solicitud.marca else ''
            modelo      = solicitud.modelo or ''
            tipo_equipo = solicitud.get_tipo_equipo_display() if solicitud.tipo_equipo else ''
            service_tag = solicitud.service_tag or ''

        elementos = [self._crear_header_seccion('Datos del equipo')]

        filas = [[
            self._celda_etiqueta_valor('Marca:', marca or '—'),
            self._celda_etiqueta_valor('Modelo:', modelo or '—'),
            self._celda_etiqueta_valor('Tipo:', tipo_equipo or '—'),
            self._celda_etiqueta_valor('Service Tag:', service_tag or '—'),
        ]]

        tabla = Table(filas, colWidths=[None, None, None, None])
        tabla.setStyle(TableStyle([
            ('GRID',         (0, 0), (-1, -1), 0.5, COLOR_GRIS_BORDE),
            ('BACKGROUND',   (0, 0), (-1, -1), COLOR_BLANCO),
            ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING',   (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 4),
            ('LEFTPADDING',  (0, 0), (-1, -1), 6),
        ]))
        elementos.append(tabla)
        return elementos

    # -------------------------------------------------------------------------
    # SECCIÓN 5: TABLA DE PRODUCTOS/SERVICIOS
    # -------------------------------------------------------------------------

    def _construir_tabla_productos(self, calculo: Dict) -> List:
        """
        Construye la tabla de ítems cotizados con precios al cliente (sin IVA).

        EXPLICACIÓN:
        Esta es la sección más visual del PDF. Cada fila tiene un color según
        si la pieza es NECESARIA (verde) u OPCIONAL (amarillo).
        Los precios mostrados ya incluyen el margen de ganancia aplicado.
        Al final hay una leyenda con la referencia de colores.

        Args:
            calculo: Dict resultado de _calcular_totales() con items_calculados.
        """
        elementos = [self._crear_header_seccion('Datos del/los producto/s')]

        # Cabeceras de la tabla (fondo navy, texto blanco)
        cabeceras = [
            Paragraph('Descripción', self._estilos['CabeceraTablaNegra']),
            Paragraph('Cantidad', self._estilos['CabeceraTablaNegra']),
            Paragraph('Precio unitario\nsin iva', self._estilos['CabeceraTablaNegra']),
            Paragraph('Total sin iva', self._estilos['CabeceraTablaNegra']),
            Paragraph('Días de entrega', self._estilos['CabeceraTablaNegra']),
        ]

        # Anchos de columna proporcionales al ancho útil
        ancho_util = letter[0] - 2 * MARGEN
        col_widths = [
            ancho_util * 0.38,  # Descripción — más amplia
            ancho_util * 0.10,  # Cantidad
            ancho_util * 0.17,  # Precio unit.
            ancho_util * 0.17,  # Total sin IVA
            ancho_util * 0.18,  # Días de entrega
        ]

        # Construir filas de datos
        filas_datos = [cabeceras]
        estilos_filas = [
            # Cabecera navy
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_NAVY),
            ('TEXTCOLOR',  (0, 0), (-1, 0), COLOR_BLANCO),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, 0), 8),
            ('ALIGN',      (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ]

        for idx, item in enumerate(calculo['items_calculados'], start=1):
            # Preparar texto de días de entrega
            dias = item.get('dias_entrega')
            if dias:
                try:
                    dias_int = int(dias)
                    if dias_int <= 5:
                        dias_texto = f"3 A 5 DÍAS\nHÁBILES"
                    elif dias_int <= 10:
                        dias_texto = f"5 A 10 DÍAS\nHÁBILES"
                    elif dias_int <= 15:
                        dias_texto = f"10 A 15 DÍAS\nHÁBILES"
                    else:
                        dias_texto = f"15 A 20 DÍAS\nHÁBILES"
                except (ValueError, TypeError):
                    dias_texto = str(dias)
            else:
                dias_texto = "POR CONFIRMAR"

            # Preparar estilos del párrafo según si es necesaria u opcional
            es_necesaria = item.get('es_necesaria', True)
            color_bg = COLOR_VERDE_BG if es_necesaria else COLOR_AMARILLO_BG
            color_texto = COLOR_VERDE_TEXTO if es_necesaria else COLOR_AMARILLO_TEXTO

            estilo_desc = ParagraphStyle(
                f'Desc_{idx}',
                fontName='Helvetica-Bold',
                fontSize=8,
                textColor=color_texto,
            )
            estilo_val = ParagraphStyle(
                f'Val_{idx}',
                fontName='Helvetica',
                fontSize=8,
                textColor=color_texto,
                alignment=TA_CENTER,
            )
            estilo_monto = ParagraphStyle(
                f'Monto_{idx}',
                fontName='Helvetica',
                fontSize=8,
                textColor=color_texto,
                alignment=TA_RIGHT,
            )

            precio_unit = item['precio_unitario_cliente']
            subtotal    = item['subtotal_cliente']

            fila = [
                Paragraph(item.get('descripcion', ''), estilo_desc),
                Paragraph(str(item.get('cantidad', 1)), estilo_val),
                Paragraph(f"${precio_unit:,.2f}", estilo_monto),
                Paragraph(f"${subtotal:,.2f}", estilo_monto),
                Paragraph(dias_texto, estilo_val),
            ]
            filas_datos.append(fila)

            # Color de fondo de la fila (verde o amarillo)
            estilos_filas.append(('BACKGROUND', (0, idx), (-1, idx), color_bg))

        # Construir la tabla
        tabla_productos = Table(filas_datos, colWidths=col_widths, repeatRows=1)

        # Aplicar estilos + bordes
        # NOTA: NO se usa ROWBACKGROUNDS porque los colores de cada fila
        # (verde/amarillo) ya se aplican explícitamente arriba con ('BACKGROUND', ...).
        # Pasar None a ROWBACKGROUNDS causaría TypeError en ReportLab.
        tabla_productos.setStyle(TableStyle(
            estilos_filas + [
                ('GRID',         (0, 0), (-1, -1), 0.5, COLOR_GRIS_BORDE),
                ('TOPPADDING',   (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING',(0, 0), (-1, -1), 5),
                ('LEFTPADDING',  (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ]
        ))

        elementos.append(tabla_productos)

        # Nota de precios antes de IVA
        elementos.append(Spacer(1, 2 * mm))
        elementos.append(Paragraph(
            "<i>*Precios antes de iva</i>",
            self._estilos['NotaTabla']
        ))

        # Leyenda de colores: Necesaria / Opcional
        leyenda = self._construir_leyenda()
        elementos.append(leyenda)

        return elementos

    def _construir_leyenda(self) -> Table:
        """
        Crea la leyenda de colores que indica qué es Necesaria y qué es Opcional.

        EXPLICACIÓN:
        Pequeña tabla horizontal debajo de la tabla de productos con muestras
        de color verde y amarillo junto con las etiquetas "Necesari@" y "Opcional".
        Es la misma leyenda que aparece en el PDF de referencia.
        """
        # Rectángulos de color representados como celdas de 1 carácter con fondo
        estilo_leyenda = ParagraphStyle(
            'Leyenda',
            fontName='Helvetica',
            fontSize=8,
            textColor=COLOR_NEGRO,
        )

        filas = [[
            Paragraph('  ', estilo_leyenda),   # Espacio verde (simulado con fondo)
            Paragraph('Necesari@', estilo_leyenda),
            Paragraph('  |  ', estilo_leyenda),
            Paragraph('  ', estilo_leyenda),   # Espacio amarillo
            Paragraph('Opcional', estilo_leyenda),
        ]]

        tabla_leyenda = Table(filas, colWidths=[8 * mm, 25 * mm, 10 * mm, 8 * mm, 25 * mm])
        tabla_leyenda.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), COLOR_VERDE_BG),
            ('BACKGROUND', (3, 0), (3, 0), COLOR_AMARILLO_BG),
            ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('GRID',       (0, 0), (0, 0), 0.3, COLOR_VERDE_TEXTO),
            ('GRID',       (3, 0), (3, 0), 0.3, COLOR_AMARILLO_TEXTO),
        ]))
        return tabla_leyenda

    # -------------------------------------------------------------------------
    # SECCIÓN 6: COTIZACIÓN (TOTALES)
    # -------------------------------------------------------------------------

    def _construir_seccion_cotizacion(self, calculo: Dict) -> List:
        """
        Construye la sección "Cotización" con el desglose de totales.

        EXPLICACIÓN:
        Esta sección muestra solo los valores que el cliente necesita ver:
        - Total con IVA (siempre visible)
        - Total con IVA menos diagnóstico (solo si aplica y el usuario eligió mostrarlo)
        
        Los costos internos (margen, overhead) NO se muestran al cliente.
        Los valores están calculados en _calcular_totales().

        Args:
            calculo: Dict con todos los valores calculados.
        """
        elementos = [self._crear_header_seccion('Cotización')]

        # Estilo para la columna de etiqueta
        estilo_etiqueta = ParagraphStyle(
            'TotalEtiqueta',
            fontName='Helvetica',
            fontSize=9,
            textColor=COLOR_NEGRO,
            alignment=TA_LEFT,
        )
        # Estilo para la columna de monto
        estilo_monto = ParagraphStyle(
            'TotalMonto',
            fontName='Helvetica',
            fontSize=9,
            textColor=COLOR_NEGRO,
            alignment=TA_RIGHT,
        )
        # Estilo para las filas destacadas (Total con IVA y Total a pagar)
        estilo_destacado = ParagraphStyle(
            'TotalDestacado',
            fontName='Helvetica-Bold',
            fontSize=10,
            textColor=COLOR_BLANCO,
            alignment=TA_RIGHT,
        )
        estilo_destacado_etq = ParagraphStyle(
            'TotalDestacadoEtq',
            fontName='Helvetica-Bold',
            fontSize=10,
            textColor=COLOR_BLANCO,
            alignment=TA_LEFT,
        )

        # Ancho de las columnas de la tabla de totales
        ancho_util = letter[0] - 2 * MARGEN
        col_widths_totales = [ancho_util * 0.60, ancho_util * 0.40]

        # Construir filas de totales
        filas_totales = []
        estilos_totales = [
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING',    (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING',   (0, 0), (-1, -1), 8),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, COLOR_GRIS_BORDE),
        ]

        fila_idx = 0

        # Fila destacada: Total con IVA (SIEMPRE visible, fondo navy)
        filas_totales.append([
            Paragraph('TOTAL CON IVA:', estilo_destacado_etq),
            Paragraph(f"${calculo['precio_con_iva']:,.2f}", estilo_destacado),
        ])
        idx_total_iva = fila_idx
        fila_idx += 1
        estilos_totales.append(('BACKGROUND', (0, idx_total_iva), (-1, idx_total_iva), COLOR_NAVY))

        # Fila opcional: descuento diagnóstico
        if calculo.get('precio_menos_diagnostico') is not None:
            # Calcular el descuento como la diferencia exacta entre los dos totales.
            # Esto evita cualquier discrepancia por redondeo vs. diagnostico * 1.16.
            descuento_display = calculo['precio_con_iva'] - calculo['precio_menos_diagnostico']
            filas_totales.append([
                Paragraph(
                    'Descuento diagnóstico incluido (diagnóstico ya pagado):',
                    ParagraphStyle('DescDiag', fontName='Helvetica', fontSize=8,
                                   textColor=colors.HexColor('#555555'), alignment=TA_LEFT)
                ),
                Paragraph(
                    f"- ${descuento_display:,.2f}",
                    ParagraphStyle('DescDiagMonto', fontName='Helvetica', fontSize=8,
                                   textColor=colors.HexColor('#555555'), alignment=TA_RIGHT)
                ),
            ])
            estilos_totales.append(('BACKGROUND', (0, fila_idx), (-1, fila_idx), COLOR_GRIS_ALT))
            fila_idx += 1

            # Fila final: Total a pagar (con descuento), fondo navy
            filas_totales.append([
                Paragraph('TOTAL A PAGAR (aplicando descuento diagnóstico):', estilo_destacado_etq),
                Paragraph(f"${calculo['precio_menos_diagnostico']:,.2f}", estilo_destacado),
            ])
            estilos_totales.append(('BACKGROUND', (0, fila_idx), (-1, fila_idx), COLOR_NAVY))
            fila_idx += 1

        tabla_totales = Table(filas_totales, colWidths=col_widths_totales)
        tabla_totales.setStyle(TableStyle(estilos_totales))
        elementos.append(tabla_totales)

        # Nota final: vigencia de cotización
        elementos.append(Spacer(1, 4 * mm))
        elementos.append(Paragraph(
            "<i>Esta cotización tiene una vigencia de 15 días hábiles a partir de la fecha de emisión. "
            "Los precios están sujetos a disponibilidad de las piezas.</i>",
            ParagraphStyle(
                'NotaFinal',
                fontName='Helvetica-Oblique',
                fontSize=7,
                textColor=colors.HexColor('#666666'),
                alignment=TA_CENTER,
            )
        ))

        return elementos

    # -------------------------------------------------------------------------
    # HELPERS DE DISEÑO
    # -------------------------------------------------------------------------

    def _crear_header_seccion(self, titulo: str) -> Table:
        """
        Crea un encabezado de sección con fondo navy azul y texto blanco centrado.

        EXPLICACIÓN:
        Este es el mismo estilo de header que aparece en el PDF de referencia
        (ej: "Datos del cliente", "Datos del equipo", etc.). Se implementa como
        una tabla de una sola celda con fondo de color.

        Args:
            titulo: Texto a mostrar en el header.

        Returns:
            Table de una fila con el header de sección.
        """
        ancho_util = letter[0] - 2 * MARGEN
        tabla = Table(
            [[Paragraph(titulo, self._estilos['HeaderSeccion'])]],
            colWidths=[ancho_util],
        )
        tabla.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), COLOR_NAVY),
            ('TEXTCOLOR',     (0, 0), (-1, -1), COLOR_BLANCO),
            ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING',    (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        return tabla

    def _celda_etiqueta_valor(self, etiqueta: str, valor: str) -> Table:
        """
        Crea una mini-tabla con etiqueta en negrita y valor debajo.

        EXPLICACIÓN:
        Se usa para mostrar campos como "Marca: LENOVO" en el PDF. La etiqueta
        va en negrita y el valor en texto normal, apilados verticalmente.

        Args:
            etiqueta : Texto del campo (ej: "Marca:").
            valor    : Valor del campo (ej: "LENOVO").
        """
        contenido = [
            [Paragraph(f"<b>{etiqueta}</b>", self._estilos['Etiqueta'])],
            [Paragraph(valor, self._estilos['Valor'])],
        ]
        tabla = Table(contenido)
        tabla.setStyle(TableStyle([
            ('TOPPADDING',    (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ]))
        return tabla
