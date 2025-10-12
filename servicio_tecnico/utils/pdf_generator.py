"""
Generador de PDF para Formato RHITSO
=====================================

EXPLICACIÓN PARA PRINCIPIANTES:
Este módulo crea documentos PDF profesionales usando ReportLab.
ReportLab es una librería de Python que funciona similar a TCPDF de PHP.

¿Qué hace este archivo?
- Genera un PDF con formato profesional para envíos a RHITSO
- Incluye logos, tablas, información del equipo e imágenes
- Convierte imágenes PNG con transparencia a JPG para compatibilidad
- Maneja el diseño y posicionamiento de todos los elementos

Estructura del PDF generado:
1. Header con logos (SIC y RHITSO)
2. Información de fecha y orden
3. Datos del equipo (modelo, serie, etc.)
4. Motivo del envío
5. Accesorios incluidos
6. Diagrama de revisión de daños
7. Imágenes de autorización/contraseñas
8. Footer con información de contacto
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

# ReportLab - Librería para generar PDFs (similar a TCPDF en PHP)
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch, mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

# Pillow - Librería para manipular imágenes (convertir PNG a JPG, etc.)
from PIL import Image as PILImage

# Django
from django.conf import settings


class PDFGeneratorRhitso:
    """
    Generador de PDF para el formato RHITSO.
    
    EXPLICACIÓN:
    Esta clase se encarga de crear un PDF completo con toda la información
    del equipo que se envía a RHITSO para reparación especializada.
    
    Uso básico:
    ```python
    generator = PDFGeneratorRhitso(orden_servicio, imagenes_autorizacion)
    pdf_path = generator.generar_pdf()
    ```
    
    Parámetros:
    - orden: Objeto OrdenServicio con los datos del equipo
    - imagenes_autorizacion: Lista de imágenes de tipo "Autorización/Pass"
    """
    
    # Constantes de diseño (medidas en puntos - 1 punto = 1/72 de pulgada)
    MARGEN_IZQUIERDO = 15 * mm  # Márgen izquierdo
    MARGEN_DERECHO = 15 * mm    # Márgen derecho
    MARGEN_SUPERIOR = 20 * mm   # Márgen superior
    MARGEN_INFERIOR = 10 * mm   # Márgen inferior
    
    # Ancho útil para contenido (ancho de página menos márgenes)
    ANCHO_UTIL = letter[0] - (MARGEN_IZQUIERDO + MARGEN_DERECHO)
    
    # Colores corporativos
    COLOR_GRIS_HEADER = colors.HexColor('#DCDCDC')  # Gris claro para encabezados de tabla
    COLOR_NEGRO = colors.black
    COLOR_AMARILLO_CARGADOR = colors.HexColor('#FFFFC8')  # Amarillo claro para destacar cargador
    
    def __init__(self, orden, imagenes_autorizacion: List = None):
        """
        Inicializa el generador de PDF.
        
        EXPLICACIÓN:
        Este método se ejecuta cuando creas una instancia de la clase.
        Prepara todos los datos necesarios para generar el PDF.
        
        Args:
            orden: Objeto OrdenServicio con los datos del equipo
            imagenes_autorizacion: Lista de objetos ImagenOrden de tipo "AUTORIZACION_PASS"
        """
        self.orden = orden
        self.detalle_equipo = orden.detalle_equipo  # Acceso directo al detalle del equipo
        self.imagenes_autorizacion = imagenes_autorizacion or []
        
        # Rutas de imágenes del sistema
        self.ruta_logo_sic = self._obtener_ruta_imagen('logos/logo_sic.png')
        self.ruta_logo_rhitso = self._obtener_ruta_imagen('logos/logo_rhitso.png')
        self.ruta_diagrama = self._obtener_ruta_imagen('rhitso/diagrama.png')
        
        # Estilos de párrafo predefinidos
        self.estilos = getSampleStyleSheet()
        self._crear_estilos_personalizados()
    
    def _obtener_ruta_imagen(self, nombre_archivo: str) -> Optional[str]:
        """
        Obtiene la ruta completa de una imagen del sistema.
        
        EXPLICACIÓN:
        Busca la imagen en las carpetas static de Django.
        Primero intenta en STATIC_ROOT (producción), luego en STATICFILES_DIRS (desarrollo).
        
        Args:
            nombre_archivo: Nombre del archivo relativo a static/images/
            
        Returns:
            Ruta completa del archivo o None si no existe
        """
        # Intentar en STATIC_ROOT (producción)
        if hasattr(settings, 'STATIC_ROOT') and settings.STATIC_ROOT:
            ruta = os.path.join(settings.STATIC_ROOT, 'images', nombre_archivo)
            if os.path.exists(ruta):
                return ruta
        
        # Intentar en STATICFILES_DIRS (desarrollo)
        if hasattr(settings, 'STATICFILES_DIRS'):
            for directorio in settings.STATICFILES_DIRS:
                ruta = os.path.join(directorio, 'images', nombre_archivo)
                if os.path.exists(ruta):
                    return ruta
        
        return None
    
    def _crear_estilos_personalizados(self):
        """
        Crea estilos de párrafo personalizados para el PDF.
        
        EXPLICACIÓN:
        Los estilos definen cómo se ve el texto (tamaño, fuente, color, alineación).
        Es como usar clases CSS en HTML.
        """
        # Estilo para títulos grandes
        self.estilos.add(ParagraphStyle(
            name='TituloGrande',
            parent=self.estilos['Heading1'],
            fontSize=16,
            textColor=self.COLOR_NEGRO,
            alignment=1,  # 1 = centrado
            spaceAfter=6,
            fontName='Helvetica-Bold'
        ))
        
        # Estilo para subtítulos
        self.estilos.add(ParagraphStyle(
            name='Subtitulo',
            parent=self.estilos['Normal'],
            fontSize=12,
            textColor=self.COLOR_NEGRO,
            alignment=1,  # centrado
            fontName='Helvetica-Bold'
        ))
        
        # Estilo para texto pequeño
        self.estilos.add(ParagraphStyle(
            name='TextoPequeño',
            parent=self.estilos['Normal'],
            fontSize=9,
            textColor=self.COLOR_NEGRO,
            alignment=1,  # centrado
            fontName='Helvetica'
        ))
    
    def _convertir_png_a_jpg(self, ruta_png: str) -> str:
        """
        Convierte una imagen PNG con transparencia a JPG con fondo blanco.
        
        EXPLICACIÓN:
        ReportLab (como TCPDF en PHP) a veces tiene problemas con PNG transparentes.
        Esta función convierte el PNG a JPG con fondo blanco para asegurar compatibilidad.
        
        ¿Cómo funciona?
        1. Abre la imagen PNG con Pillow
        2. Crea una nueva imagen con fondo blanco del mismo tamaño
        3. Pega la imagen PNG encima del fondo blanco
        4. Guarda como JPG en un archivo temporal
        5. Retorna la ruta del archivo temporal
        
        Args:
            ruta_png: Ruta del archivo PNG original
            
        Returns:
            Ruta del archivo JPG temporal creado
        """
        try:
            # Verificar que el archivo existe
            if not os.path.exists(ruta_png):
                return ruta_png
            
            # Abrir la imagen original con Pillow
            imagen_original = PILImage.open(ruta_png)
            
            # Solo procesar si es PNG (verificar por el formato)
            if imagen_original.format != 'PNG':
                return ruta_png  # Si no es PNG, devolver la ruta original
            
            # Obtener dimensiones de la imagen
            ancho, alto = imagen_original.size
            
            # Crear nueva imagen con fondo blanco
            imagen_nueva = PILImage.new('RGB', (ancho, alto), (255, 255, 255))
            
            # Si la imagen tiene transparencia (modo RGBA), convertir primero
            if imagen_original.mode == 'RGBA':
                # Pegar la imagen original sobre el fondo blanco
                # La transparencia se rellena con blanco automáticamente
                imagen_nueva.paste(imagen_original, (0, 0), imagen_original)
            else:
                # Si no tiene transparencia, simplemente convertir
                imagen_nueva.paste(imagen_original, (0, 0))
            
            # Crear archivo temporal para el JPG
            archivo_temporal = tempfile.NamedTemporaryFile(
                suffix='.jpg',
                delete=False,  # No eliminar automáticamente
                prefix='rhitso_'
            )
            
            # Guardar como JPG con calidad del 90%
            imagen_nueva.save(archivo_temporal.name, 'JPEG', quality=90)
            
            # Cerrar imágenes para liberar memoria
            imagen_original.close()
            imagen_nueva.close()
            
            return archivo_temporal.name
            
        except Exception as e:
            print(f"Error convirtiendo imagen {ruta_png}: {str(e)}")
            return ruta_png  # En caso de error, devolver la ruta original
    
    def _agregar_imagen_al_pdf(self, canvas_obj, ruta_imagen: str, x: float, y: float, 
                               ancho_max: float, alto_max: float) -> bool:
        """
        Agrega una imagen al PDF en la posición especificada.
        
        EXPLICACIÓN:
        Esta función agrega una imagen al PDF, escalándola automáticamente
        para que quepa en el espacio disponible manteniendo sus proporciones.
        
        ¿Cómo funciona?
        1. Verifica que la imagen existe
        2. Convierte PNG a JPG si es necesario
        3. Obtiene las dimensiones de la imagen
        4. Calcula la escala para que quepa en el espacio disponible
        5. Dibuja la imagen centrada en el espacio
        6. Limpia archivos temporales
        
        Args:
            canvas_obj: Objeto canvas de ReportLab donde dibujar
            ruta_imagen: Ruta de la imagen a agregar
            x: Posición X (desde la izquierda)
            y: Posición Y (desde abajo - ReportLab usa coordenadas desde abajo)
            ancho_max: Ancho máximo disponible
            alto_max: Alto máximo disponible
            
        Returns:
            True si se agregó correctamente, False si hubo error
        """
        if not ruta_imagen or not os.path.exists(ruta_imagen):
            return False
        
        try:
            # Convertir PNG a JPG si es necesario
            ruta_procesada = self._convertir_png_a_jpg(ruta_imagen)
            
            # Obtener dimensiones de la imagen usando PIL
            with PILImage.open(ruta_procesada) as img:
                ancho_original, alto_original = img.size
            
            # Calcular escala para que quepa manteniendo proporciones
            escala_ancho = ancho_max / ancho_original
            escala_alto = alto_max / alto_original
            escala = min(escala_ancho, escala_alto)  # Usar la menor para que quepa completo
            
            # Calcular dimensiones finales
            ancho_final = ancho_original * escala
            alto_final = alto_original * escala
            
            # Centrar la imagen en el espacio disponible
            x_centrado = x + (ancho_max - ancho_final) / 2
            y_centrado = y + (alto_max - alto_final) / 2
            
            # Dibujar la imagen en el PDF
            canvas_obj.drawImage(
                ruta_procesada,
                x_centrado,
                y_centrado,
                width=ancho_final,
                height=alto_final,
                preserveAspectRatio=True
            )
            
            # Si se creó un archivo temporal, eliminarlo
            if ruta_procesada != ruta_imagen and os.path.exists(ruta_procesada):
                try:
                    os.unlink(ruta_procesada)
                except:
                    pass  # No importa si no se puede eliminar
            
            return True
            
        except Exception as e:
            print(f"Error agregando imagen al PDF: {str(e)}")
            
            # Limpiar archivo temporal en caso de error
            if 'ruta_procesada' in locals() and ruta_procesada != ruta_imagen:
                try:
                    if os.path.exists(ruta_procesada):
                        os.unlink(ruta_procesada)
                except:
                    pass
            
            return False
    
    def generar_pdf(self) -> Dict[str, Any]:
        """
        Genera el PDF completo del formato RHITSO.
        
        EXPLICACIÓN:
        Este es el método principal que coordina la generación del PDF.
        Crea el archivo, agrega todos los elementos y retorna la información del archivo.
        
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
            serie = self.detalle_equipo.numero_serie.replace(' ', '_').replace('/', '_')
            nombre_archivo = f"RHITSO_{fecha}_{serie}.pdf"
            
            # Crear directorio temporal si no existe
            directorio_temp = os.path.join(settings.MEDIA_ROOT, 'temp', 'rhitso')
            os.makedirs(directorio_temp, exist_ok=True)
            
            # Ruta completa del archivo
            ruta_archivo = os.path.join(directorio_temp, nombre_archivo)
            
            # Crear el PDF usando canvas (bajo nivel, más control)
            pdf_canvas = canvas.Canvas(ruta_archivo, pagesize=letter)
            
            # Configurar metadatos del PDF
            pdf_canvas.setTitle(f"Formato RHITSO - Equipo {self.detalle_equipo.numero_serie}")
            pdf_canvas.setAuthor("SIC Comercialización y Servicios México SC")
            pdf_canvas.setSubject("Envío de equipo a RHITSO para revisión especializada")
            pdf_canvas.setCreator("SIC México - Sistema RHITSO")
            
            # Generar contenido del PDF
            self._generar_contenido_pdf(pdf_canvas)
            
            # Guardar y cerrar el PDF
            pdf_canvas.save()
            
            # Obtener tamaño del archivo
            tamaño_archivo = os.path.getsize(ruta_archivo)
            
            return {
                'success': True,
                'archivo': nombre_archivo,
                'ruta': ruta_archivo,
                'size': tamaño_archivo
            }
            
        except Exception as e:
            print(f"Error generando PDF RHITSO: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return {
                'success': False,
                'error': f'Error generando PDF: {str(e)}'
            }
    
    def _generar_contenido_pdf(self, c: canvas.Canvas):
        """
        Genera todo el contenido del PDF.
        
        EXPLICACIÓN:
        Este método coordina la creación de todas las secciones del PDF.
        Llama a métodos específicos para cada sección.
        
        Args:
            c: Canvas de ReportLab donde se dibuja el PDF
        """
        # Variables de posición (ReportLab usa coordenadas desde ABAJO hacia ARRIBA)
        page_width, page_height = letter
        y_actual = page_height - self.MARGEN_SUPERIOR
        
        # 1. Header con logos
        y_actual = self._dibujar_header(c, y_actual)
        y_actual -= 15  # Espacio después del header
        
        # 2. Información de fecha y orden
        y_actual = self._dibujar_fecha_orden(c, y_actual)
        y_actual -= 10  # Espacio
        
        # 3. Información del equipo
        y_actual = self._dibujar_info_equipo(c, y_actual)
        y_actual -= 15  # Espacio
        
        # 4. Motivo
        y_actual = self._dibujar_motivo(c, y_actual)
        y_actual -= 15  # Espacio
        
        # 5. Accesorios enviados
        y_actual = self._dibujar_accesorios(c, y_actual)
        y_actual -= 20  # Espacio
        
        # 6. Revisión de daños externos (diagrama)
        y_actual = self._dibujar_revision_danos(c, y_actual)
        y_actual -= 15  # Espacio
        
        # 7. Imágenes de autorización (si hay)
        if self.imagenes_autorizacion:
            y_actual = self._dibujar_imagenes_autorizacion(c, y_actual)
        
        # 8. Footer (siempre en la parte inferior)
        self._dibujar_footer(c)
    
    def _dibujar_header(self, c: canvas.Canvas, y_inicial: float) -> float:
        """
        Dibuja el encabezado del PDF con logos y título.
        
        EXPLICACIÓN:
        Crea la parte superior del PDF con:
        - Logo SIC a la izquierda
        - Título central "Formato SIC COMERCIALIZACION..."
        - Logo RHITSO a la derecha
        
        Returns:
            Nueva posición Y después del header
        """
        page_width = letter[0]
        
        # Altura del header
        alto_header = 70
        
        # Logo SIC (izquierda)
        if self.ruta_logo_sic:
            self._agregar_imagen_al_pdf(
                c,
                self.ruta_logo_sic,
                x=self.MARGEN_IZQUIERDO + 5,
                y=y_inicial - alto_header + 30,
                ancho_max=100,
                alto_max=50
            )
        
        # Título central
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(page_width / 2, y_inicial - 15, "Formato RHITSO")
        
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(page_width / 2, y_inicial - 30, "SIC COMERCIALIZACION Y SERVICIOS")
        
        c.setFont("Helvetica", 9)
        c.drawCentredString(page_width / 2, y_inicial - 43, "MEXICO")
        
        # Logo RHITSO (derecha)
        if self.ruta_logo_rhitso:
            self._agregar_imagen_al_pdf(
                c,
                self.ruta_logo_rhitso,
                x=page_width - self.MARGEN_DERECHO - 105,
                y=y_inicial - alto_header + 30,
                ancho_max=100,
                alto_max=50
            )
        
        return y_inicial - alto_header
    
    def _dibujar_fecha_orden(self, c: canvas.Canvas, y_inicial: float) -> float:
        """
        Dibuja la tabla de fecha y número de orden.
        
        Returns:
            Nueva posición Y después de la tabla
        """
        # IMPORTANTE: orden_cliente es el número de orden interna del cliente
        orden_interna = self.detalle_equipo.orden_cliente or f"ORD-{self.orden.id}"
        fecha_actual = datetime.now().strftime('%d/%m/%Y')
        
        # Posiciones y medidas
        alto_celda = 20
        x_inicio = self.MARGEN_IZQUIERDO
        ancho_total = self.ANCHO_UTIL
        
        # Configurar tabla: FECHA | fecha_actual | espacio | ORDEN DE SERVICIO | orden_interna
        ancho_fecha_label = 70
        ancho_fecha_valor = 100
        ancho_espacio = ancho_total - ancho_fecha_label - ancho_fecha_valor - 130 - 130
        ancho_orden_label = 130
        ancho_orden_valor = 130
        
        # Dibujar celdas
        y_celda = y_inicial - alto_celda
        
        # FECHA (label con fondo gris)
        c.setFillColor(self.COLOR_GRIS_HEADER)
        c.rect(x_inicio, y_celda, ancho_fecha_label, alto_celda, fill=1, stroke=1)
        c.setFillColor(self.COLOR_NEGRO)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(
            x_inicio + ancho_fecha_label / 2,
            y_celda + alto_celda / 2 - 3,
            "FECHA"
        )
        
        # Fecha valor
        c.rect(x_inicio + ancho_fecha_label, y_celda, ancho_fecha_valor, alto_celda, fill=0, stroke=1)
        c.setFont("Helvetica", 9)
        c.drawCentredString(
            x_inicio + ancho_fecha_label + ancho_fecha_valor / 2,
            y_celda + alto_celda / 2 - 3,
            fecha_actual
        )
        
        # Espacio central (sin dibujar)
        x_orden_label = x_inicio + ancho_fecha_label + ancho_fecha_valor + ancho_espacio
        
        # ORDEN DE SERVICIO (label con fondo gris)
        c.setFillColor(self.COLOR_GRIS_HEADER)
        c.rect(x_orden_label, y_celda, ancho_orden_label, alto_celda, fill=1, stroke=1)
        c.setFillColor(self.COLOR_NEGRO)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(
            x_orden_label + ancho_orden_label / 2,
            y_celda + alto_celda / 2 - 3,
            "ORDEN DE SERVICIO"
        )
        
        # Orden valor
        c.rect(x_orden_label + ancho_orden_label, y_celda, ancho_orden_valor, alto_celda, fill=0, stroke=1)
        c.setFont("Helvetica", 8)
        c.drawCentredString(
            x_orden_label + ancho_orden_label + ancho_orden_valor / 2,
            y_celda + alto_celda / 2 - 3,
            str(orden_interna)
        )
        
        return y_celda - 5
    
    def _dibujar_info_equipo(self, c: canvas.Canvas, y_inicial: float) -> float:
        """
        Dibuja la sección de información del equipo.
        
        Returns:
            Nueva posición Y después de la sección
        """
        alto_header = 25
        alto_fila = 25
        x_inicio = self.MARGEN_IZQUIERDO
        ancho_total = self.ANCHO_UTIL
        
        # Header
        y_header = y_inicial - alto_header
        c.setFillColor(self.COLOR_GRIS_HEADER)
        c.rect(x_inicio, y_header, ancho_total, alto_header, fill=1, stroke=1)
        c.setFillColor(self.COLOR_NEGRO)
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(
            x_inicio + ancho_total / 2,
            y_header + alto_header / 2 - 4,
            "INFORMACION DEL EQUIPO"
        )
        
        # Fila con MODELO y NUMERO DE SERIE
        y_fila = y_header - alto_fila
        
        # Anchos
        ancho_modelo_label = 70
        ancho_modelo_valor = (ancho_total / 2) - ancho_modelo_label
        ancho_serie_label = 100
        ancho_serie_valor = (ancho_total / 2) - ancho_serie_label
        
        # MODELO label
        c.setFillColor(self.COLOR_GRIS_HEADER)
        c.rect(x_inicio, y_fila, ancho_modelo_label, alto_fila, fill=1, stroke=1)
        c.setFillColor(self.COLOR_NEGRO)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(
            x_inicio + ancho_modelo_label / 2,
            y_fila + alto_fila / 2 - 3,
            "MODELO"
        )
        
        # Modelo valor
        c.rect(x_inicio + ancho_modelo_label, y_fila, ancho_modelo_valor, alto_fila, fill=0, stroke=1)
        c.setFont("Helvetica", 9)
        modelo_texto = self.detalle_equipo.modelo or 'N/A'
        c.drawCentredString(
            x_inicio + ancho_modelo_label + ancho_modelo_valor / 2,
            y_fila + alto_fila / 2 - 3,
            modelo_texto
        )
        
        # NUMERO DE SERIE label
        x_serie_label = x_inicio + ancho_modelo_label + ancho_modelo_valor
        c.setFillColor(self.COLOR_GRIS_HEADER)
        c.rect(x_serie_label, y_fila, ancho_serie_label, alto_fila, fill=1, stroke=1)
        c.setFillColor(self.COLOR_NEGRO)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(
            x_serie_label + ancho_serie_label / 2,
            y_fila + alto_fila / 2 - 3,
            "NUMERO DE SERIE"
        )
        
        # Numero de serie valor
        c.rect(
            x_serie_label + ancho_serie_label,
            y_fila,
            ancho_serie_valor,
            alto_fila,
            fill=0,
            stroke=1
        )
        c.setFont("Helvetica", 8)
        c.drawCentredString(
            x_serie_label + ancho_serie_label + ancho_serie_valor / 2,
            y_fila + alto_fila / 2 - 3,
            self.detalle_equipo.numero_serie
        )
        
        return y_fila - 5
    
    def _dibujar_motivo(self, c: canvas.Canvas, y_inicial: float) -> float:
        """
        Dibuja la sección de motivo del envío.
        
        Returns:
            Nueva posición Y después de la sección
        """
        alto_header = 25
        alto_minimo_contenido = 70
        x_inicio = self.MARGEN_IZQUIERDO
        ancho_total = self.ANCHO_UTIL
        
        # Header
        y_header = y_inicial - alto_header
        c.setFillColor(self.COLOR_GRIS_HEADER)
        c.rect(x_inicio, y_header, ancho_total, alto_header, fill=1, stroke=1)
        c.setFillColor(self.COLOR_NEGRO)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(
            x_inicio + ancho_total / 2,
            y_header + alto_header / 2 - 4,
            "MOTIVO"
        )
        
        # Contenido
        motivo_texto = self.orden.descripcion_rhitso or 'No especificado'
        
        # Dibujar rectángulo del contenido
        y_contenido = y_header - alto_minimo_contenido
        c.rect(x_inicio, y_contenido, ancho_total, alto_minimo_contenido, fill=0, stroke=1)
        
        # Dibujar texto del motivo (con margen interno)
        c.setFont("Helvetica", 9)
        margen_texto = 10
        ancho_texto = ancho_total - (2 * margen_texto)
        
        # Crear objeto de texto para texto multilínea
        texto_obj = c.beginText(x_inicio + margen_texto, y_header - 15)
        texto_obj.setFont("Helvetica", 9)
        
        # Dividir texto en líneas que quepan en el ancho disponible
        palabras = motivo_texto.split()
        linea_actual = ""
        
        for palabra in palabras:
            linea_prueba = linea_actual + palabra + " "
            ancho_linea = c.stringWidth(linea_prueba, "Helvetica", 9)
            
            if ancho_linea <= ancho_texto:
                linea_actual = linea_prueba
            else:
                texto_obj.textLine(linea_actual.strip())
                linea_actual = palabra + " "
        
        if linea_actual:
            texto_obj.textLine(linea_actual.strip())
        
        c.drawText(texto_obj)
        
        return y_contenido - 5
    
    def _dibujar_accesorios(self, c: canvas.Canvas, y_inicial: float) -> float:
        """
        Dibuja la sección de accesorios enviados.
        
        Returns:
            Nueva posición Y después de la sección
        """
        alto_header = 25
        alto_fila_checkboxes = 25
        x_inicio = self.MARGEN_IZQUIERDO
        ancho_total = self.ANCHO_UTIL
        
        # Header
        y_header = y_inicial - alto_header
        c.setFillColor(self.COLOR_GRIS_HEADER)
        c.rect(x_inicio, y_header, ancho_total, alto_header, fill=1, stroke=1)
        c.setFillColor(self.COLOR_NEGRO)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(
            x_inicio + ancho_total / 2,
            y_header + alto_header / 2 - 4,
            "ACCESORIOS ENVIADOS"
        )
        
        # Checkboxes
        tiene_cargador = self.detalle_equipo.tiene_cargador
        check_adaptador = '[X]' if tiene_cargador else '[ ]'
        check_sin_cargador = '[X]' if not tiene_cargador else '[ ]'
        
        y_fila = y_header - alto_fila_checkboxes
        ancho_columna = ancho_total / 3
        
        # ADAPTADOR
        c.rect(x_inicio, y_fila, ancho_columna, alto_fila_checkboxes, fill=0, stroke=1)
        c.setFont("Helvetica", 9)
        c.drawString(
            x_inicio + 10,
            y_fila + alto_fila_checkboxes / 2 - 3,
            f"{check_adaptador} ADAPTADOR"
        )
        
        # SIN CARGADOR (en negritas si está marcado)
        c.rect(x_inicio + ancho_columna, y_fila, ancho_columna, alto_fila_checkboxes, fill=0, stroke=1)
        font_cargador = "Helvetica-Bold" if not tiene_cargador else "Helvetica"
        c.setFont(font_cargador, 9)
        c.drawString(
            x_inicio + ancho_columna + 10,
            y_fila + alto_fila_checkboxes / 2 - 3,
            f"{check_sin_cargador} SIN CARGADOR"
        )
        
        # OTROS
        c.rect(x_inicio + 2 * ancho_columna, y_fila, ancho_columna, alto_fila_checkboxes, fill=0, stroke=1)
        c.setFont("Helvetica", 9)
        c.drawString(
            x_inicio + 2 * ancho_columna + 10,
            y_fila + alto_fila_checkboxes / 2 - 3,
            "[ ] OTROS"
        )
        
        y_final = y_fila
        
        # Si tiene cargador, agregar información destacada
        if tiene_cargador and self.detalle_equipo.numero_serie_cargador:
            y_cargador = y_fila - 25
            c.setFillColor(self.COLOR_AMARILLO_CARGADOR)
            c.rect(x_inicio, y_cargador, ancho_total, 25, fill=1, stroke=1)
            c.setFillColor(self.COLOR_NEGRO)
            c.setFont("Helvetica-Bold", 9)
            c.drawString(
                x_inicio + 10,
                y_cargador + 25 / 2 - 3,
                f"CARGADOR Y CABLE: {self.detalle_equipo.numero_serie_cargador}"
            )
            y_final = y_cargador
        
        return y_final - 5
    
    def _dibujar_revision_danos(self, c: canvas.Canvas, y_inicial: float) -> float:
        """
        Dibuja la sección de revisión de daños con el diagrama.
        
        Returns:
            Nueva posición Y después de la sección
        """
        alto_header = 25
        alto_diagrama = 250
        x_inicio = self.MARGEN_IZQUIERDO
        ancho_total = self.ANCHO_UTIL
        
        # Header
        y_header = y_inicial - alto_header
        c.setFillColor(self.COLOR_GRIS_HEADER)
        c.rect(x_inicio, y_header, ancho_total, alto_header, fill=1, stroke=1)
        c.setFillColor(self.COLOR_NEGRO)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(
            x_inicio + ancho_total / 2,
            y_header + alto_header / 2 - 4,
            "REVISION DE DAÑOS EXTERNOS"
        )
        
        # Diagrama
        y_diagrama = y_header - alto_diagrama
        
        if self.ruta_diagrama:
            exito = self._agregar_imagen_al_pdf(
                c,
                self.ruta_diagrama,
                x=x_inicio,
                y=y_diagrama,
                ancho_max=ancho_total,
                alto_max=alto_diagrama
            )
            
            if not exito:
                # Si no se pudo agregar, dibujar rectángulo con texto
                c.rect(x_inicio, y_diagrama, ancho_total, alto_diagrama, fill=0, stroke=1)
                c.setFont("Helvetica", 10)
                c.drawCentredString(
                    x_inicio + ancho_total / 2,
                    y_diagrama + alto_diagrama / 2,
                    "Diagrama de revision fisica del equipo"
                )
        else:
            # Si no hay diagrama, dibujar rectángulo con texto
            c.rect(x_inicio, y_diagrama, ancho_total, alto_diagrama, fill=0, stroke=1)
            c.setFont("Helvetica", 10)
            c.drawCentredString(
                x_inicio + ancho_total / 2,
                y_diagrama + alto_diagrama / 2,
                "Diagrama de revision fisica del equipo"
            )
        
        return y_diagrama - 5
    
    def _dibujar_imagenes_autorizacion(self, c: canvas.Canvas, y_inicial: float) -> float:
        """
        Dibuja la sección de imágenes de autorización/contraseñas.
        
        Returns:
            Nueva posición Y después de la sección
        """
        # Verificar si hay espacio suficiente en la página
        espacio_necesario = 150
        if y_inicial < espacio_necesario:
            # No hay espacio, agregar nueva página
            c.showPage()
            y_inicial = letter[1] - self.MARGEN_SUPERIOR
        
        alto_header = 25
        alto_imagen = 280
        x_inicio = self.MARGEN_IZQUIERDO
        ancho_total = self.ANCHO_UTIL
        
        # Header
        y_header = y_inicial - alto_header
        c.setFillColor(self.COLOR_GRIS_HEADER)
        c.rect(x_inicio, y_header, ancho_total, alto_header, fill=1, stroke=1)
        c.setFillColor(self.COLOR_NEGRO)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(
            x_inicio + ancho_total / 2,
            y_header + alto_header / 2 - 4,
            "IMAGENES DE AUTORIZACION/CONTRASEÑAS"
        )
        
        # Tomar solo la primera imagen (más reciente)
        if self.imagenes_autorizacion:
            imagen = self.imagenes_autorizacion[0]
            
            # Obtener ruta de la imagen
            ruta_imagen = None
            if hasattr(imagen, 'imagen') and imagen.imagen:
                ruta_imagen = os.path.join(settings.MEDIA_ROOT, str(imagen.imagen))
            
            y_imagen = y_header - alto_imagen
            
            if ruta_imagen and os.path.exists(ruta_imagen):
                exito = self._agregar_imagen_al_pdf(
                    c,
                    ruta_imagen,
                    x=x_inicio,
                    y=y_imagen,
                    ancho_max=ancho_total,
                    alto_max=alto_imagen
                )
                
                if not exito:
                    # Si no se pudo agregar, dibujar rectángulo con texto
                    c.rect(x_inicio, y_imagen, ancho_total, alto_imagen, fill=0, stroke=1)
                    c.setFont("Helvetica", 10)
                    c.drawCentredString(
                        x_inicio + ancho_total / 2,
                        y_imagen + alto_imagen / 2,
                        "Error cargando imagen de autorizacion"
                    )
            else:
                # Si no existe el archivo, mostrar mensaje
                c.rect(x_inicio, y_imagen, ancho_total, alto_imagen, fill=0, stroke=1)
                c.setFont("Helvetica", 10)
                c.drawCentredString(
                    x_inicio + ancho_total / 2,
                    y_imagen + alto_imagen / 2,
                    "Imagen de autorizacion no encontrada"
                )
            
            return y_imagen - 5
        
        return y_header - 5
    
    def _dibujar_footer(self, c: canvas.Canvas):
        """
        Dibuja el pie de página con información de contacto.
        """
        page_width = letter[0]
        y_footer = self.MARGEN_INFERIOR + 40
        
        # Información de contacto
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(page_width / 2, y_footer, "SIC Comercializacion y Servicios Mexico SC")
        
        c.setFont("Helvetica", 7)
        c.drawCentredString(page_width / 2, y_footer - 12, "Domicilio")
        c.drawCentredString(
            page_width / 2,
            y_footer - 24,
            "Circuito Economistas 15-A, Col. Satelite, Naucalpan de Juarez, Edo de Mexico CP 53100"
        )
        
        c.setFont("Helvetica", 8)
        c.drawCentredString(
            page_width / 2,
            y_footer - 40,
            "Seguimiento con: Alejandro Garcia Tel: 55-35-45-81-92 / Correo: cis_mex@sic.com.mx"
        )
