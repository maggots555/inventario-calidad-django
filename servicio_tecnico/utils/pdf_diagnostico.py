"""
Generador de PDF para Formato de Diagnóstico SIC
=================================================

EXPLICACIÓN PARA PRINCIPIANTES:
Este módulo crea documentos PDF profesionales con el formato oficial de
diagnóstico de SIC para enviar al cliente. Usa ReportLab (similar a TCPDF en PHP).

¿Qué hace este archivo?
- Genera un PDF con el formato de diagnóstico que se envía al cliente
- Incluye: logo SIC, folio, datos del equipo, reporte de usuario,
  diagnóstico técnico, tabla de observaciones de componentes

Estructura del PDF generado:
1. Header con logo SIC + Folio y Fecha
2. Datos del equipo (marca, modelo, tipo, serie)
3. Reporte de usuario (falla reportada)
4. Diagnóstico SIC (análisis técnico detallado)
5. Piezas a cotizar (tabla de 18 componentes con checkboxes y DPN)
6. Footer con contacto del empleado
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

# ReportLab - Librería para generar PDFs
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch, mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

# Pillow - Para manipular imágenes (convertir PNG a JPG, etc.)
from PIL import Image as PILImage

# Django
from django.conf import settings

# Constantes del proyecto
from config.constants import COMPONENTES_DIAGNOSTICO_ORDEN


class PDFGeneratorDiagnostico:
    """
    Generador de PDF para el formato de Diagnóstico SIC.
    
    EXPLICACIÓN:
    Esta clase crea un PDF con el formato oficial de diagnóstico que se envía
    al cliente por correo electrónico. Replica el formato de la hoja de
    diagnóstico que usa SIC México internamente.
    
    Uso básico:
    ```python
    generator = PDFGeneratorDiagnostico(
        orden=orden_servicio,
        folio='MX_CIS_MX_MONTERREY1_02690',
        componentes_seleccionados=[
            {'componente_db': 'Pantalla', 'dpn': 'DPN: 0XPJWG', 'seleccionado': True},
            ...
        ],
        email_empleado='tecnico@sic.com.mx'
    )
    resultado = generator.generar_pdf()
    ```
    """
    
    # Constantes de diseño (medidas en puntos - 1 punto = 1/72 de pulgada)
    MARGEN_IZQUIERDO = 15 * mm
    MARGEN_DERECHO = 15 * mm
    MARGEN_SUPERIOR = 20 * mm
    MARGEN_INFERIOR = 10 * mm
    
    # Ancho útil para contenido (ancho de página menos márgenes)
    ANCHO_UTIL = letter[0] - (15 * mm + 15 * mm)
    
    # Colores corporativos
    COLOR_AZUL_HEADER = colors.HexColor('#003366')    # Azul oscuro para headers
    COLOR_AZUL_CLARO = colors.HexColor('#4472C4')     # Azul claro para subheaders
    COLOR_GRIS_HEADER = colors.HexColor('#DCDCDC')    # Gris claro para celdas
    COLOR_ROJO_CHECK = colors.HexColor('#FF0000')     # Rojo para las X de componentes
    COLOR_NEGRO = colors.black
    COLOR_BLANCO = colors.white
    
    def __init__(self, orden, folio: str, componentes_seleccionados: List[Dict] = None,
                 email_empleado: str = '', pais_config: Dict = None):
        """
        Inicializa el generador de PDF.
        
        EXPLICACIÓN:
        Prepara todos los datos necesarios para generar el PDF de diagnóstico.
        
        Args:
            orden: Objeto OrdenServicio con los datos del equipo
            folio: Folio personalizado (ej: 'MX_CIS_MX_MONTERREY1_02690')
            componentes_seleccionados: Lista de dicts con componentes marcados
                Cada dict: {'componente_db': str, 'dpn': str, 'seleccionado': bool}
            email_empleado: Email del empleado que envía el diagnóstico
            pais_config: Diccionario con la configuración del país actual
                (de config.paises_config.get_pais_actual()). Se usa para
                mostrar el nombre correcto de la empresa en el PDF.
        """
        self.orden = orden
        self.detalle_equipo = orden.detalle_equipo
        self.folio = folio
        self.componentes_seleccionados = componentes_seleccionados or []
        self.email_empleado = email_empleado
        
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # pais_config contiene datos como 'empresa_nombre', 'empresa_nombre_corto', etc.
        # Si no se pasa, usamos valores por defecto de México para compatibilidad.
        self.pais_config = pais_config or {}
        self.empresa_nombre = self.pais_config.get('empresa_nombre', 'SIC Comercialización y Servicios México SC')
        self.empresa_nombre_corto = self.pais_config.get('empresa_nombre_corto', 'SIC México')
        
        # Ruta del logo SIC
        self.ruta_logo_sic = self._obtener_ruta_imagen('logos/logo_sic.png')
        
        # Estilos de párrafo predefinidos
        self.estilos = getSampleStyleSheet()
    
    def _obtener_ruta_imagen(self, nombre_archivo: str) -> Optional[str]:
        """
        Obtiene la ruta completa de una imagen estática.
        
        Busca primero en STATIC_ROOT (producción) y luego en STATICFILES_DIRS (desarrollo).
        """
        if hasattr(settings, 'STATIC_ROOT') and settings.STATIC_ROOT:
            ruta = os.path.join(settings.STATIC_ROOT, 'images', nombre_archivo)
            if os.path.exists(ruta):
                return ruta
        
        if hasattr(settings, 'STATICFILES_DIRS'):
            for directorio in settings.STATICFILES_DIRS:
                ruta = os.path.join(directorio, 'images', nombre_archivo)
                if os.path.exists(ruta):
                    return ruta
        
        return None
    
    def _convertir_png_a_jpg(self, ruta_png: str) -> str:
        """
        Convierte una imagen PNG con transparencia a JPG con fondo blanco.
        Necesario porque ReportLab a veces tiene problemas con PNG transparentes.
        """
        try:
            if not os.path.exists(ruta_png):
                return ruta_png
            
            imagen_original = PILImage.open(ruta_png)
            
            if imagen_original.format != 'PNG':
                return ruta_png
            
            ancho, alto = imagen_original.size
            imagen_nueva = PILImage.new('RGB', (ancho, alto), (255, 255, 255))
            
            if imagen_original.mode == 'RGBA':
                imagen_nueva.paste(imagen_original, (0, 0), imagen_original)
            else:
                imagen_nueva.paste(imagen_original, (0, 0))
            
            archivo_temporal = tempfile.NamedTemporaryFile(
                suffix='.jpg', delete=False, prefix='diag_'
            )
            imagen_nueva.save(archivo_temporal.name, 'JPEG', quality=90)
            
            imagen_original.close()
            imagen_nueva.close()
            
            return archivo_temporal.name
            
        except Exception as e:
            print(f"Error convirtiendo imagen {ruta_png}: {str(e)}")
            return ruta_png
    
    def _agregar_imagen_al_pdf(self, canvas_obj, ruta_imagen: str, x: float, y: float,
                               ancho_max: float, alto_max: float) -> bool:
        """
        Agrega una imagen al PDF escalándola para que quepa en el espacio disponible.
        """
        if not ruta_imagen or not os.path.exists(ruta_imagen):
            return False
        
        try:
            ruta_procesada = self._convertir_png_a_jpg(ruta_imagen)
            
            with PILImage.open(ruta_procesada) as img:
                ancho_original, alto_original = img.size
            
            escala_ancho = ancho_max / ancho_original
            escala_alto = alto_max / alto_original
            escala = min(escala_ancho, escala_alto)
            
            ancho_final = ancho_original * escala
            alto_final = alto_original * escala
            
            x_centrado = x + (ancho_max - ancho_final) / 2
            y_centrado = y + (alto_max - alto_final) / 2
            
            canvas_obj.drawImage(
                ruta_procesada, x_centrado, y_centrado,
                width=ancho_final, height=alto_final,
                preserveAspectRatio=True
            )
            
            if ruta_procesada != ruta_imagen and os.path.exists(ruta_procesada):
                try:
                    os.unlink(ruta_procesada)
                except:
                    pass
            
            return True
            
        except Exception as e:
            print(f"Error agregando imagen al PDF: {str(e)}")
            return False
    
    def _dibujar_texto_multilinea(self, c, texto: str, x: float, y: float,
                                   ancho_max: float, font: str = 'Helvetica',
                                   font_size: int = 9) -> float:
        """
        Dibuja texto multilínea respetando el ancho máximo.
        Retorna la posición Y final después del texto.
        
        EXPLICACIÓN:
        ReportLab no tiene "word-wrap" automático como HTML.
        Esta función divide el texto en líneas que quepan en el ancho disponible.
        """
        texto_obj = c.beginText(x, y)
        texto_obj.setFont(font, font_size)
        texto_obj.setFillColor(self.COLOR_NEGRO)  # CRÍTICO: Forzar color negro para texto legible
        
        linea_altura = font_size + 3  # Espacio entre líneas
        
        # Dividir por líneas existentes primero (respetar saltos de línea del usuario)
        parrafos = texto.split('\n')
        lineas_totales = 0
        
        for parrafo in parrafos:
            if not parrafo.strip():
                texto_obj.textLine('')
                lineas_totales += 1
                continue
            
            palabras = parrafo.split()
            linea_actual = ""
            
            for palabra in palabras:
                linea_prueba = linea_actual + palabra + " "
                ancho_linea = c.stringWidth(linea_prueba, font, font_size)
                
                if ancho_linea <= ancho_max:
                    linea_actual = linea_prueba
                else:
                    texto_obj.textLine(linea_actual.strip())
                    lineas_totales += 1
                    linea_actual = palabra + " "
            
            if linea_actual:
                texto_obj.textLine(linea_actual.strip())
                lineas_totales += 1
        
        c.drawText(texto_obj)
        
        return y - (lineas_totales * linea_altura)
    
    def generar_pdf(self) -> Dict[str, Any]:
        """
        Genera el PDF completo del formato de diagnóstico.
        
        Returns:
            Diccionario con:
            - success: True/False
            - archivo: Nombre del archivo generado
            - ruta: Ruta completa del archivo
            - size: Tamaño en bytes
            - error: Mensaje de error (si success=False)
        """
        try:
            # Generar nombre del archivo
            fecha = datetime.now().strftime('%Y%m%d')
            folio_limpio = self.folio.replace(' ', '_').replace('/', '_')
            nombre_archivo = f"DIAGNOSTICO_{fecha}_{folio_limpio}.pdf"
            
            # Crear directorio temporal
            directorio_temp = os.path.join(settings.MEDIA_ROOT, 'temp', 'diagnostico')
            os.makedirs(directorio_temp, exist_ok=True)
            
            ruta_archivo = os.path.join(directorio_temp, nombre_archivo)
            
            # Crear el PDF usando canvas
            pdf_canvas = canvas.Canvas(ruta_archivo, pagesize=letter)
            
            # Metadatos del PDF (dinámicos según el país configurado)
            pdf_canvas.setTitle(f"Diagnóstico - {self.folio}")
            pdf_canvas.setAuthor(self.empresa_nombre_corto)
            pdf_canvas.setSubject(f"Diagnóstico de equipo {self.detalle_equipo.numero_serie}")
            pdf_canvas.setCreator(f"{self.empresa_nombre_corto} - Sistema de Servicio Técnico")
            
            # Generar contenido
            self._generar_contenido_pdf(pdf_canvas)
            
            # Guardar y cerrar
            pdf_canvas.save()
            
            tamaño_archivo = os.path.getsize(ruta_archivo)
            
            return {
                'success': True,
                'archivo': nombre_archivo,
                'ruta': ruta_archivo,
                'size': tamaño_archivo
            }
            
        except Exception as e:
            print(f"Error generando PDF de diagnóstico: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return {
                'success': False,
                'error': f'Error generando PDF: {str(e)}'
            }
    
    def _generar_contenido_pdf(self, c: canvas.Canvas):
        """
        Genera todo el contenido del PDF coordinando las secciones.
        """
        page_width, page_height = letter
        y_actual = page_height - self.MARGEN_SUPERIOR
        
        # 1. Header con logo + folio/fecha
        y_actual = self._dibujar_header(c, y_actual)
        y_actual -= 10
        
        # 2. Datos del equipo
        y_actual = self._dibujar_datos_equipo(c, y_actual)
        y_actual -= 10
        
        # 3. Reporte de usuario (falla principal)
        y_actual = self._dibujar_reporte_usuario(c, y_actual)
        y_actual -= 5
        
        # 4. Diagnóstico SIC (texto largo)
        y_actual = self._dibujar_diagnostico(c, y_actual)
        y_actual -= 10
        
        # 5. Observaciones adicionales (tabla de componentes)
        y_actual = self._dibujar_observaciones(c, y_actual)
        
        # 6. Footer
        self._dibujar_footer(c)
    
    def _dibujar_header(self, c: canvas.Canvas, y_inicial: float) -> float:
        """
        Dibuja el header del PDF con logo SIC y campo de folio/fecha.
        
        Estructura (según formato de referencia):
        | [Logo SIC]  |        | FOLIO Y FECHA | {folio}    |
        |             |        |               | {fecha}    |
        """
        page_width = letter[0]
        alto_header = 60
        
        # === COLUMNA A-C: Logo SIC (izquierda) ===
        if self.ruta_logo_sic:
            self._agregar_imagen_al_pdf(
                c, self.ruta_logo_sic,
                x=self.MARGEN_IZQUIERDO + 5,
                y=y_inicial - alto_header + 10,
                ancho_max=140,
                alto_max=50
            )
        
        # === COLUMNA D-E: Folio y Fecha (derecha) ===
        # Ancho de cada celda
        ancho_label = 90
        ancho_valor = 170
        x_label = page_width - self.MARGEN_DERECHO - ancho_label - ancho_valor
        x_valor = x_label + ancho_label
        alto_celda = 22
        
        # Fila 1: "FOLIO Y FECHA" | folio
        y_fila1 = y_inicial - alto_celda
        
        c.setFillColor(self.COLOR_AZUL_HEADER)
        c.rect(x_label, y_fila1, ancho_label, alto_celda, fill=1, stroke=1)
        c.setFillColor(self.COLOR_BLANCO)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(x_label + ancho_label / 2, y_fila1 + alto_celda / 2 - 3, "FOLIO Y FECHA")
        
        c.setFillColor(self.COLOR_BLANCO)
        c.rect(x_valor, y_fila1, ancho_valor, alto_celda, fill=1, stroke=1)
        c.setFillColor(self.COLOR_NEGRO)
        c.setFont("Helvetica", 8)
        c.drawCentredString(x_valor + ancho_valor / 2, y_fila1 + alto_celda / 2 - 3, str(self.folio))
        
        # Fila 2: vacío | fecha
        y_fila2 = y_fila1 - alto_celda
        
        c.setFillColor(self.COLOR_BLANCO)
        c.rect(x_label, y_fila2, ancho_label, alto_celda, fill=1, stroke=1)
        c.rect(x_valor, y_fila2, ancho_valor, alto_celda, fill=1, stroke=1)
        c.setFillColor(self.COLOR_NEGRO)
        c.setFont("Helvetica", 9)
        fecha_actual = datetime.now().strftime('%d/%m/%Y')
        c.drawCentredString(x_valor + ancho_valor / 2, y_fila2 + alto_celda / 2 - 3, fecha_actual)
        
        return y_inicial - alto_header - 5
    
    def _dibujar_datos_equipo(self, c: canvas.Canvas, y_inicial: float) -> float:
        """
        Dibuja la sección DATOS DEL EQUIPO.
        
        Estructura (tabla horizontal de 4 columnas):
        |              DATOS DEL EQUIPO                          |
        |  MARCA  |      MODELO       |   TIPO   |    SERIE     |
        | {marca} | {modelo}          | {tipo}   | {serie}      |
        """
        x_inicio = self.MARGEN_IZQUIERDO
        ancho_total = self.ANCHO_UTIL
        alto_header = 22
        alto_fila = 22
        
        # Header azul: "DATOS DEL EQUIPO"
        y_header = y_inicial - alto_header
        c.setFillColor(self.COLOR_AZUL_HEADER)
        c.rect(x_inicio, y_header, ancho_total, alto_header, fill=1, stroke=1)
        c.setFillColor(self.COLOR_BLANCO)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(x_inicio + ancho_total / 2, y_header + alto_header / 2 - 3, "DATOS DEL EQUIPO")
        
        # Anchos de columnas (4 columnas proporcionadas)
        ancho_col_marca = ancho_total * 0.15
        ancho_col_modelo = ancho_total * 0.40
        ancho_col_tipo = ancho_total * 0.15
        ancho_col_serie = ancho_total * 0.30
        
        x_modelo = x_inicio + ancho_col_marca
        x_tipo = x_modelo + ancho_col_modelo
        x_serie = x_tipo + ancho_col_tipo
        
        # Fila de LABELS: MARCA | MODELO | TIPO | SERIE
        y_labels = y_header - alto_fila
        
        columnas = [
            (x_inicio, ancho_col_marca, "MARCA"),
            (x_modelo, ancho_col_modelo, "MODELO"),
            (x_tipo, ancho_col_tipo, "TIPO"),
            (x_serie, ancho_col_serie, "SERIE"),
        ]
        
        for x_col, ancho_col, label in columnas:
            c.setFillColor(self.COLOR_GRIS_HEADER)
            c.rect(x_col, y_labels, ancho_col, alto_fila, fill=1, stroke=1)
            c.setFillColor(self.COLOR_NEGRO)
            c.setFont("Helvetica-Bold", 8)
            c.drawCentredString(x_col + ancho_col / 2, y_labels + alto_fila / 2 - 3, label)
        
        # Fila de VALORES: {marca} | {modelo} | {tipo} | {serie}
        y_valores = y_labels - alto_fila
        
        tipo_display = str(
            self.detalle_equipo.get_tipo_equipo_display()
            if hasattr(self.detalle_equipo, 'get_tipo_equipo_display')
            else self.detalle_equipo.tipo_equipo or 'N/A'
        )
        
        valores = [
            (x_inicio, ancho_col_marca, str(self.detalle_equipo.marca or 'N/A')),
            (x_modelo, ancho_col_modelo, str(self.detalle_equipo.modelo or 'N/A')),
            (x_tipo, ancho_col_tipo, tipo_display),
            (x_serie, ancho_col_serie, str(self.detalle_equipo.numero_serie or 'N/A')),
        ]
        
        for x_col, ancho_col, valor in valores:
            c.setFillColor(self.COLOR_BLANCO)
            c.rect(x_col, y_valores, ancho_col, alto_fila, fill=1, stroke=1)
            c.setFillColor(self.COLOR_NEGRO)
            c.setFont("Helvetica", 8)
            # Truncar si es muy largo para la columna
            max_chars = int(ancho_col / 4.2)
            texto = valor[:max_chars] if len(valor) > max_chars else valor
            c.drawCentredString(x_col + ancho_col / 2, y_valores + alto_fila / 2 - 3, texto)
        
        return y_valores - 5
    
    def _dibujar_reporte_usuario(self, c: canvas.Canvas, y_inicial: float) -> float:
        """
        Dibuja la sección REPORTE DE USUARIO con la falla principal.
        """
        x_inicio = self.MARGEN_IZQUIERDO
        ancho_total = self.ANCHO_UTIL
        alto_header = 22
        
        # Header azul
        y_header = y_inicial - alto_header
        c.setFillColor(self.COLOR_AZUL_CLARO)
        c.rect(x_inicio, y_header, ancho_total, alto_header, fill=1, stroke=1)
        c.setFillColor(self.COLOR_BLANCO)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(x_inicio + ancho_total / 2, y_header + alto_header / 2 - 3, "REPORTE DE USUARIO:")
        
        # Contenido: texto de falla principal
        falla_texto = self.detalle_equipo.falla_principal or 'Sin reporte de usuario'
        
        # Calcular alto necesario para el texto
        margen_texto = 10
        ancho_texto = ancho_total - (2 * margen_texto)
        
        # Estimar líneas necesarias
        lineas = self._calcular_lineas_texto(c, falla_texto, ancho_texto, 'Helvetica', 9)
        alto_contenido = max(50, (lineas + 1) * 12 + 10)
        
        # Dibujar rectángulo de contenido
        y_contenido = y_header - alto_contenido
        c.setFillColor(self.COLOR_BLANCO)
        c.rect(x_inicio, y_contenido, ancho_total, alto_contenido, fill=1, stroke=1)
        
        # Dibujar texto (forzar color negro después del rect blanco)
        c.setFillColor(self.COLOR_NEGRO)
        self._dibujar_texto_multilinea(
            c, falla_texto,
            x=x_inicio + margen_texto,
            y=y_header - 15,
            ancho_max=ancho_texto,
            font='Helvetica',
            font_size=9
        )
        
        return y_contenido - 5
    
    def _dibujar_diagnostico(self, c: canvas.Canvas, y_inicial: float) -> float:
        """
        Dibuja la sección de DIAGNÓSTICO TÉCNICO con el análisis técnico detallado.
        Incluye su propio header azul igual que REPORTE DE USUARIO.
        """
        x_inicio = self.MARGEN_IZQUIERDO
        ancho_total = self.ANCHO_UTIL
        alto_header = 22
        
        diagnostico_texto = self.detalle_equipo.diagnostico_sic or 'Sin diagnóstico registrado'
        
        margen_texto = 10
        ancho_texto = ancho_total - (2 * margen_texto)
        
        # Calcular alto necesario para el texto
        lineas = self._calcular_lineas_texto(c, diagnostico_texto, ancho_texto, 'Helvetica', 9)
        alto_contenido = max(80, (lineas + 1) * 12 + 15)
        
        # Verificar si cabe en la página actual (header + contenido)
        espacio_total = alto_header + alto_contenido + 10
        if y_inicial - espacio_total < self.MARGEN_INFERIOR + 50:
            c.showPage()
            y_inicial = letter[1] - self.MARGEN_SUPERIOR
        
        # Header azul: "DIAGNÓSTICO TÉCNICO"
        y_header = y_inicial - alto_header
        c.setFillColor(self.COLOR_AZUL_CLARO)
        c.rect(x_inicio, y_header, ancho_total, alto_header, fill=1, stroke=1)
        c.setFillColor(self.COLOR_BLANCO)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(x_inicio + ancho_total / 2, y_header + alto_header / 2 - 3, "DIAGNÓSTICO TÉCNICO:")
        
        # Rectángulo de contenido
        y_contenido = y_header - alto_contenido
        c.setFillColor(self.COLOR_BLANCO)
        c.rect(x_inicio, y_contenido, ancho_total, alto_contenido, fill=1, stroke=1)
        
        # Dibujar texto del diagnóstico (forzar color negro después del rect blanco)
        c.setFillColor(self.COLOR_NEGRO)
        self._dibujar_texto_multilinea(
            c, diagnostico_texto,
            x=x_inicio + margen_texto,
            y=y_header - 15,
            ancho_max=ancho_texto,
            font='Helvetica',
            font_size=9
        )
        
        return y_contenido - 5
    
    def _dibujar_observaciones(self, c: canvas.Canvas, y_inicial: float) -> float:
        """
        Dibuja la tabla OBSERVACIONES ADICIONALES con los 18 componentes.
        
        Estructura por fila:
        | Nombre componente  | [X] | DPN/notas                    |
        
        Cada componente tiene:
        - Checkbox (X roja si está seleccionado, vacío si no)
        - Campo de notas/DPN (si fue llenado)
        """
        x_inicio = self.MARGEN_IZQUIERDO
        ancho_total = self.ANCHO_UTIL
        alto_header = 22
        alto_fila = 18
        
        # Verificar espacio suficiente (predefinidos + adicionales)
        componentes_adicionales_count = len([
            c for c in self.componentes_seleccionados
            if c.get('componente_db', '') not in {comp['componente_db'] for comp in COMPONENTES_DIAGNOSTICO_ORDEN}
        ])
        total_filas_estimadas = len(COMPONENTES_DIAGNOSTICO_ORDEN) + componentes_adicionales_count
        espacio_necesario = alto_header + (total_filas_estimadas * alto_fila) + 20
        if y_inicial - espacio_necesario < self.MARGEN_INFERIOR:
            c.showPage()
            y_inicial = letter[1] - self.MARGEN_SUPERIOR
        
        # Header azul: "OBSERVACIONES ADICIONALES"
        y_header = y_inicial - alto_header
        c.setFillColor(self.COLOR_AZUL_CLARO)
        c.rect(x_inicio, y_header, ancho_total, alto_header, fill=1, stroke=1)
        c.setFillColor(self.COLOR_BLANCO)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(x_inicio + ancho_total / 2, y_header + alto_header / 2 - 3, "PIEZAS A COTIZAR")
        
        # Columnas de la tabla
        ancho_nombre = 140    # Nombre del componente
        ancho_check = 25      # Checkbox
        ancho_dpn = ancho_total - ancho_nombre - ancho_check  # DPN/notas
        
        # Crear un mapeo rápido de componentes seleccionados
        componentes_map = {}
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # Guardamos los componentes adicionales (los que NO están en COMPONENTES_DIAGNOSTICO_ORDEN)
        # en una lista separada para dibujarlos después de los predefinidos.
        nombres_predefinidos = {comp['componente_db'] for comp in COMPONENTES_DIAGNOSTICO_ORDEN}
        componentes_adicionales = []
        
        for comp in self.componentes_seleccionados:
            nombre_db = comp.get('componente_db', '')
            componentes_map[nombre_db] = {
                'seleccionado': comp.get('seleccionado', False),
                'dpn': comp.get('dpn', '')
            }
            # Si NO está en los predefinidos, es un componente adicional dinámico
            if nombre_db and nombre_db not in nombres_predefinidos:
                componentes_adicionales.append(comp)
        
        # Dibujar filas de componentes
        y_fila = y_header
        
        for comp_config in COMPONENTES_DIAGNOSTICO_ORDEN:
            y_fila -= alto_fila
            
            nombre_db = comp_config['componente_db']
            label_pdf = comp_config['label_pdf']
            
            # Obtener datos de selección
            comp_data = componentes_map.get(nombre_db, {'seleccionado': False, 'dpn': ''})
            esta_seleccionado = comp_data.get('seleccionado', False)
            dpn_texto = comp_data.get('dpn', '')
            
            # Celda: Nombre del componente
            c.setFillColor(self.COLOR_GRIS_HEADER)
            c.rect(x_inicio, y_fila, ancho_nombre, alto_fila, fill=1, stroke=1)
            c.setFillColor(self.COLOR_NEGRO)
            c.setFont("Helvetica", 8)
            c.drawString(x_inicio + 5, y_fila + alto_fila / 2 - 3, label_pdf)
            
            # Celda: Checkbox
            x_check = x_inicio + ancho_nombre
            c.setFillColor(self.COLOR_BLANCO)
            c.rect(x_check, y_fila, ancho_check, alto_fila, fill=1, stroke=1)
            
            if esta_seleccionado:
                # Dibujar X roja
                c.setFillColor(self.COLOR_ROJO_CHECK)
                c.setFont("Helvetica-Bold", 10)
                c.drawCentredString(x_check + ancho_check / 2, y_fila + alto_fila / 2 - 4, "X")
            
            # Celda: DPN/notas
            x_dpn = x_check + ancho_check
            c.setFillColor(self.COLOR_BLANCO)
            c.rect(x_dpn, y_fila, ancho_dpn, alto_fila, fill=1, stroke=1)
            
            if dpn_texto:
                c.setFillColor(self.COLOR_NEGRO)
                c.setFont("Helvetica", 8)
                # Truncar si es muy largo
                max_chars = int(ancho_dpn / 4.5)
                texto_truncado = dpn_texto[:max_chars] if len(dpn_texto) > max_chars else dpn_texto
                c.drawString(x_dpn + 5, y_fila + alto_fila / 2 - 3, texto_truncado)
        
        # ── Dibujar filas de componentes ADICIONALES (agregados dinámicamente) ──
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # Estos son los componentes que el usuario agregó con el botón "+"
        # y que NO están en la lista predefinida COMPONENTES_DIAGNOSTICO_ORDEN.
        # Se dibujan exactamente igual que los predefinidos, con un estilo
        # ligeramente diferente (fondo verde claro) para distinguirlos.
        for comp_adicional in componentes_adicionales:
            nombre_db = comp_adicional.get('componente_db', '')
            esta_seleccionado = comp_adicional.get('seleccionado', False)
            dpn_texto = comp_adicional.get('dpn', '')
            # Usar el nombre del componente como etiqueta (en mayúsculas)
            label_pdf = nombre_db.upper() if nombre_db else 'COMPONENTE ADICIONAL'

            # Verificar salto de página si no cabe
            if y_fila - alto_fila < self.MARGEN_INFERIOR + 40:
                c.showPage()
                y_fila = letter[1] - self.MARGEN_SUPERIOR - 20

            y_fila -= alto_fila

            # Celda: Nombre – mismo estilo que los predefinidos
            c.setFillColor(self.COLOR_GRIS_HEADER)
            c.rect(x_inicio, y_fila, ancho_nombre, alto_fila, fill=1, stroke=1)
            c.setFillColor(self.COLOR_NEGRO)
            c.setFont("Helvetica", 8)
            c.drawString(x_inicio + 5, y_fila + alto_fila / 2 - 3, label_pdf)

            # Celda: Checkbox
            x_check = x_inicio + ancho_nombre
            c.setFillColor(self.COLOR_BLANCO)
            c.rect(x_check, y_fila, ancho_check, alto_fila, fill=1, stroke=1)

            if esta_seleccionado:
                c.setFillColor(self.COLOR_ROJO_CHECK)
                c.setFont("Helvetica-Bold", 10)
                c.drawCentredString(x_check + ancho_check / 2, y_fila + alto_fila / 2 - 4, "X")

            # Celda: DPN/notas
            x_dpn = x_check + ancho_check
            c.setFillColor(self.COLOR_BLANCO)
            c.rect(x_dpn, y_fila, ancho_dpn, alto_fila, fill=1, stroke=1)

            if dpn_texto:
                c.setFillColor(self.COLOR_NEGRO)
                c.setFont("Helvetica", 8)
                max_chars = int(ancho_dpn / 4.5)
                texto_truncado = dpn_texto[:max_chars] if len(dpn_texto) > max_chars else dpn_texto
                c.drawString(x_dpn + 5, y_fila + alto_fila / 2 - 3, texto_truncado)
        
        return y_fila - 5
    
    def _dibujar_footer(self, c: canvas.Canvas):
        """
        Dibuja el pie de página con el email del empleado que envía.
        """
        page_width = letter[0]
        y_footer = self.MARGEN_INFERIOR + 30
        
        # Línea separadora
        c.setStrokeColor(self.COLOR_AZUL_HEADER)
        c.setLineWidth(1)
        c.line(self.MARGEN_IZQUIERDO, y_footer + 15, page_width - self.MARGEN_DERECHO, y_footer + 15)
        
        # Empresa (nombre corto dinámico según país: "SIC México" o "SIC Argentina")
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(self.COLOR_AZUL_HEADER)
        c.drawCentredString(page_width / 2, y_footer, self.empresa_nombre_corto)
        
        # Email del empleado
        if self.email_empleado:
            c.setFont("Helvetica", 7)
            c.setFillColor(self.COLOR_NEGRO)
            c.drawCentredString(page_width / 2, y_footer - 12,
                                f"Contacto: {self.email_empleado}")
    
    def _calcular_lineas_texto(self, c, texto: str, ancho_max: float,
                                font: str, font_size: int) -> int:
        """
        Calcula cuántas líneas ocupará un texto en el espacio disponible.
        """
        lineas = 0
        parrafos = texto.split('\n')
        
        for parrafo in parrafos:
            if not parrafo.strip():
                lineas += 1
                continue
            
            palabras = parrafo.split()
            linea_actual = ""
            
            for palabra in palabras:
                linea_prueba = linea_actual + palabra + " "
                ancho_linea = c.stringWidth(linea_prueba, font, font_size)
                
                if ancho_linea <= ancho_max:
                    linea_actual = linea_prueba
                else:
                    lineas += 1
                    linea_actual = palabra + " "
            
            if linea_actual:
                lineas += 1
        
        return lineas
