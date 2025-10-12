"""
Compresor de Imágenes para Correos RHITSO
==========================================

EXPLICACIÓN PARA PRINCIPIANTES:
Este módulo se encarga de comprimir imágenes para que puedan ser enviadas por correo
sin exceder los límites de Gmail (25MB).

¿Qué hace?
- Comprime imágenes grandes a un tamaño manejable
- Redimensiona imágenes muy grandes (máximo 1920x1080)
- Convierte a JPG con calidad optimizada (75%)
- Calcula el tamaño total del correo antes de enviarlo
- Limpia archivos temporales después del envío
- Genera recomendaciones si el correo es muy pesado

¿Cuándo se usa?
- Antes de enviar correos con adjuntos pesados
- Para optimizar imágenes de tipo "ingreso" (evidencia del equipo)
- Para verificar que no se exceda el límite de Gmail

Basado en: Sistema PHP con GD (imagecreatefromjpeg, imagecopyresampled)
Implementado con: Pillow (PIL) - equivalente Python de GD
"""

import os
import tempfile
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from datetime import datetime

# Pillow - Librería para manipular imágenes (equivalente a GD en PHP)
from PIL import Image as PILImage

# Django
from django.conf import settings


class ImageCompressor:
    """
    Compresor de imágenes para optimizar el envío por correo.
    
    EXPLICACIÓN:
    Esta clase replica exactamente la funcionalidad del sistema PHP.
    Comprime imágenes grandes para que quepan en el límite de Gmail (25MB).
    
    Parámetros de compresión (iguales a PHP):
    - Calidad JPG: 75% (balance entre calidad y tamaño)
    - Dimensiones máximas: 1920x1080 píxeles
    - Umbral de compresión: 500KB (imágenes menores no se comprimen)
    - Límite individual: 25MB (imágenes mayores se rechazan)
    - Límite total correo: 25MB (Gmail)
    """
    
    # Constantes de compresión (iguales a PHP)
    CALIDAD_JPG = 75              # Calidad de compresión JPG (0-100)
    MAX_ANCHO = 1920              # Ancho máximo en píxeles
    MAX_ALTO = 1080               # Alto máximo en píxeles
    UMBRAL_COMPRESION = 500 * 1024  # 500KB - no comprimir si es menor
    LIMITE_INDIVIDUAL = 25 * 1024 * 1024  # 25MB por imagen
    LIMITE_GMAIL = 25 * 1024 * 1024       # 25MB total del correo
    
    def __init__(self, directorio_temp: Optional[str] = None):
        """
        Inicializa el compresor de imágenes.
        
        Args:
            directorio_temp: Directorio para archivos temporales.
                           Si no se especifica, usa media/temp/compressed/
        """
        if directorio_temp:
            self.directorio_temp = directorio_temp
        else:
            self.directorio_temp = os.path.join(
                settings.MEDIA_ROOT,
                'temp',
                'compressed'
            )
        
        # Crear directorio si no existe
        os.makedirs(self.directorio_temp, exist_ok=True)
        
        # Lista de archivos temporales creados (para limpieza posterior)
        self.archivos_temporales = []
    
    def comprimir_imagen_para_correo(
        self,
        ruta_original: str,
        calidad: int = None,
        max_ancho: int = None,
        max_alto: int = None
    ) -> Dict[str, Any]:
        """
        Comprime una imagen para optimizar el envío por correo.
        
        EXPLICACIÓN:
        Replica la función comprimirImagenParaCorreo() de PHP.
        
        ¿Qué hace?
        1. Verifica que la imagen existe
        2. Si es < 500KB, NO comprime (ya es pequeña)
        3. Redimensiona si es muy grande (máx 1920x1080)
        4. Convierte a JPG con calidad 75%
        5. Guarda en archivo temporal
        6. Retorna información de la compresión
        
        Args:
            ruta_original: Ruta del archivo de imagen original
            calidad: Calidad JPG (0-100), default 75
            max_ancho: Ancho máximo en píxeles, default 1920
            max_alto: Alto máximo en píxeles, default 1080
            
        Returns:
            Diccionario con:
            - success: True/False
            - ruta_comprimida: Ruta del archivo comprimido
            - fue_comprimida: Si se comprimió o se usó la original
            - tamaño_original: Tamaño en bytes del original
            - tamaño_comprimido: Tamaño en bytes después de comprimir
            - reduccion_porcentaje: % de reducción del tamaño
            - dimensiones_originales: (ancho, alto) original
            - dimensiones_nuevas: (ancho, alto) después de redimensionar
            - error: Mensaje de error (si success=False)
        """
        try:
            # Usar valores por defecto si no se especifican
            calidad = calidad or self.CALIDAD_JPG
            max_ancho = max_ancho or self.MAX_ANCHO
            max_alto = max_alto or self.MAX_ALTO
            
            # Verificar que el archivo existe
            if not os.path.exists(ruta_original):
                return {
                    'success': False,
                    'error': f'Archivo no encontrado: {ruta_original}'
                }
            
            # Obtener tamaño original
            tamaño_original = os.path.getsize(ruta_original)
            
            # Si la imagen es pequeña (< 500KB), no comprimir
            if tamaño_original < self.UMBRAL_COMPRESION:
                return {
                    'success': True,
                    'ruta_comprimida': ruta_original,
                    'fue_comprimida': False,
                    'tamaño_original': tamaño_original,
                    'tamaño_comprimido': tamaño_original,
                    'reduccion_porcentaje': 0,
                    'razon': 'Imagen ya es pequeña (< 500KB)'
                }
            
            # Abrir imagen con Pillow
            try:
                imagen_original = PILImage.open(ruta_original)
            except Exception as e:
                return {
                    'success': False,
                    'error': f'No se pudo abrir la imagen: {str(e)}'
                }
            
            # Obtener dimensiones originales
            ancho_original, alto_original = imagen_original.size
            
            # Calcular nuevas dimensiones manteniendo proporción
            # (igual que en PHP)
            factor_escala = min(
                max_ancho / ancho_original,
                max_alto / alto_original,
                1  # No agrandar si es más pequeña
            )
            
            nuevo_ancho = int(ancho_original * factor_escala)
            nuevo_alto = int(alto_original * factor_escala)
            
            # Redimensionar imagen si es necesario
            if factor_escala < 1:
                # Usar LANCZOS para mejor calidad (equivalente a imagecopyresampled en PHP)
                imagen_redimensionada = imagen_original.resize(
                    (nuevo_ancho, nuevo_alto),
                    PILImage.Resampling.LANCZOS
                )
            else:
                imagen_redimensionada = imagen_original
            
            # Convertir a RGB si es necesario (para guardar como JPG)
            # PNG con transparencia, RGBA, etc. → RGB
            if imagen_redimensionada.mode in ('RGBA', 'LA', 'P'):
                # Crear fondo blanco
                fondo = PILImage.new('RGB', imagen_redimensionada.size, (255, 255, 255))
                # Si tiene canal alpha, usarlo
                if imagen_redimensionada.mode == 'RGBA':
                    fondo.paste(imagen_redimensionada, mask=imagen_redimensionada.split()[3])
                else:
                    fondo.paste(imagen_redimensionada)
                imagen_redimensionada = fondo
            elif imagen_redimensionada.mode != 'RGB':
                imagen_redimensionada = imagen_redimensionada.convert('RGB')
            
            # Generar nombre de archivo temporal
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            nombre_base = Path(ruta_original).stem
            nombre_comprimido = f"compressed_{timestamp}_{nombre_base}.jpg"
            ruta_comprimida = os.path.join(self.directorio_temp, nombre_comprimido)
            
            # Guardar como JPG con la calidad especificada
            imagen_redimensionada.save(
                ruta_comprimida,
                'JPEG',
                quality=calidad,
                optimize=True  # Optimización adicional
            )
            
            # Cerrar imágenes para liberar memoria
            imagen_original.close()
            imagen_redimensionada.close()
            
            # Obtener tamaño del archivo comprimido
            tamaño_comprimido = os.path.getsize(ruta_comprimida)
            
            # Calcular reducción porcentual
            reduccion_porcentaje = round(
                ((tamaño_original - tamaño_comprimido) / tamaño_original) * 100,
                1
            )
            
            # Agregar a lista de archivos temporales para limpieza posterior
            self.archivos_temporales.append(ruta_comprimida)
            
            return {
                'success': True,
                'ruta_comprimida': ruta_comprimida,
                'fue_comprimida': True,
                'tamaño_original': tamaño_original,
                'tamaño_comprimido': tamaño_comprimido,
                'reduccion_porcentaje': reduccion_porcentaje,
                'dimensiones_originales': (ancho_original, alto_original),
                'dimensiones_nuevas': (nuevo_ancho, nuevo_alto)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Error comprimiendo imagen: {str(e)}'
            }
    
    def calcular_tamaño_correo(
        self,
        ruta_pdf: str,
        imagenes: List[Dict[str, str]],
        contenido_html: str = ""
    ) -> Dict[str, Any]:
        """
        Calcula el tamaño total del correo antes de enviarlo.
        
        EXPLICACIÓN:
        Replica la función calcularTamañoCorreo() de PHP.
        
        ¿Qué hace?
        1. Suma el tamaño del PDF
        2. Suma el tamaño del contenido HTML
        3. Para cada imagen:
           - Verifica que existe
           - Rechaza si > 25MB individual
           - Comprime la imagen
           - Suma el tamaño comprimido
        4. Verifica si excede el límite de Gmail (25MB)
        5. Genera recomendaciones
        
        Args:
            ruta_pdf: Ruta del archivo PDF generado
            imagenes: Lista de diccionarios con información de imágenes
                     Cada diccionario debe tener:
                     - 'ruta': Ruta del archivo de imagen
                     - 'nombre': Nombre para mostrar
            contenido_html: Contenido HTML del correo (opcional)
            
        Returns:
            Diccionario con:
            - success: True/False
            - tamaño_total: Tamaño total en bytes
            - tamaño_total_mb: Tamaño total en MB
            - excede_limite: True si excede 25MB
            - detalles: Desglose de tamaños (pdf, html, imágenes)
            - imagenes_validas: Lista de imágenes que se incluirán
            - imagenes_excluidas: Lista de imágenes excluidas (muy grandes)
            - recomendaciones: Lista de mensajes de recomendación
        """
        try:
            resultado = {
                'success': True,
                'tamaño_total': 0,
                'detalles': {},
                'imagenes_validas': [],
                'imagenes_excluidas': [],
            }
            
            # 1. Tamaño del PDF
            if os.path.exists(ruta_pdf):
                tamaño_pdf = os.path.getsize(ruta_pdf)
                resultado['tamaño_total'] += tamaño_pdf
                resultado['detalles']['pdf'] = {
                    'nombre': os.path.basename(ruta_pdf),
                    'tamaño': tamaño_pdf,
                    'tamaño_mb': round(tamaño_pdf / 1024 / 1024, 2)
                }
            else:
                resultado['detalles']['pdf'] = {
                    'nombre': 'PDF no encontrado',
                    'tamaño': 0,
                    'tamaño_mb': 0
                }
            
            # 2. Tamaño del HTML
            tamaño_html = len(contenido_html.encode('utf-8'))
            resultado['tamaño_total'] += tamaño_html
            resultado['detalles']['html'] = {
                'tamaño': tamaño_html,
                'tamaño_mb': round(tamaño_html / 1024 / 1024, 2)
            }
            
            # 3. Procesar imágenes
            tamaño_imagenes_original = 0
            tamaño_imagenes_comprimido = 0
            
            for imagen in imagenes:
                ruta_imagen = imagen.get('ruta')
                nombre_imagen = imagen.get('nombre', os.path.basename(ruta_imagen))
                
                if not os.path.exists(ruta_imagen):
                    resultado['imagenes_excluidas'].append({
                        'nombre': nombre_imagen,
                        'tamaño': 0,
                        'tamaño_mb': 0,
                        'razon': 'Archivo no encontrado'
                    })
                    continue
                
                tamaño_original = os.path.getsize(ruta_imagen)
                
                # Verificar límite individual (25MB)
                if tamaño_original > self.LIMITE_INDIVIDUAL:
                    resultado['imagenes_excluidas'].append({
                        'nombre': nombre_imagen,
                        'tamaño': tamaño_original,
                        'tamaño_mb': round(tamaño_original / 1024 / 1024, 2),
                        'razon': 'Excede límite individual de 25MB'
                    })
                    continue
                
                # Comprimir imagen
                resultado_compresion = self.comprimir_imagen_para_correo(ruta_imagen)
                
                if resultado_compresion['success']:
                    tamaño_comprimido = resultado_compresion['tamaño_comprimido']
                    
                    tamaño_imagenes_original += tamaño_original
                    tamaño_imagenes_comprimido += tamaño_comprimido
                    
                    resultado['imagenes_validas'].append({
                        'nombre': nombre_imagen,
                        'ruta_original': ruta_imagen,
                        'ruta_comprimida': resultado_compresion['ruta_comprimida'],
                        'tamaño_original': tamaño_original,
                        'tamaño_original_mb': round(tamaño_original / 1024 / 1024, 2),
                        'tamaño_comprimido': tamaño_comprimido,
                        'tamaño_comprimido_mb': round(tamaño_comprimido / 1024 / 1024, 2),
                        'reduccion_porcentaje': resultado_compresion.get('reduccion_porcentaje', 0),
                        'fue_comprimida': resultado_compresion.get('fue_comprimida', False)
                    })
                else:
                    resultado['imagenes_excluidas'].append({
                        'nombre': nombre_imagen,
                        'tamaño': tamaño_original,
                        'tamaño_mb': round(tamaño_original / 1024 / 1024, 2),
                        'razon': f"Error al comprimir: {resultado_compresion.get('error', 'Desconocido')}"
                    })
            
            # Sumar imágenes comprimidas al total
            resultado['tamaño_total'] += tamaño_imagenes_comprimido
            
            resultado['detalles']['imagenes'] = {
                'tamaño_original': tamaño_imagenes_original,
                'tamaño_original_mb': round(tamaño_imagenes_original / 1024 / 1024, 2),
                'tamaño_comprimido': tamaño_imagenes_comprimido,
                'tamaño_comprimido_mb': round(tamaño_imagenes_comprimido / 1024 / 1024, 2),
                'reduccion_total_mb': round((tamaño_imagenes_original - tamaño_imagenes_comprimido) / 1024 / 1024, 2),
                'count': len(resultado['imagenes_validas'])
            }
            
            # Calcular tamaño total en MB
            resultado['tamaño_total_mb'] = round(resultado['tamaño_total'] / 1024 / 1024, 2)
            
            # Verificar si excede límite
            resultado['excede_limite'] = resultado['tamaño_total'] > self.LIMITE_GMAIL
            resultado['limite_gmail_mb'] = 25
            
            # Generar recomendaciones
            resultado['recomendaciones'] = self._generar_recomendaciones(
                resultado['tamaño_total'],
                len(resultado['imagenes_validas']),
                len(resultado['imagenes_excluidas'])
            )
            
            resultado['imagenes_validas_count'] = len(resultado['imagenes_validas'])
            resultado['imagenes_excluidas_count'] = len(resultado['imagenes_excluidas'])
            
            return resultado
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Error calculando tamaño del correo: {str(e)}'
            }
    
    def _generar_recomendaciones(
        self,
        tamaño_total: int,
        imagenes_validas: int,
        imagenes_excluidas: int
    ) -> List[str]:
        """
        Genera recomendaciones basadas en el tamaño del correo.
        
        EXPLICACIÓN:
        Replica la función generarRecomendaciones() de PHP.
        Genera mensajes útiles dependiendo del tamaño del correo.
        
        Args:
            tamaño_total: Tamaño total en bytes
            imagenes_validas: Cantidad de imágenes válidas
            imagenes_excluidas: Cantidad de imágenes excluidas
            
        Returns:
            Lista de strings con recomendaciones
        """
        recomendaciones = []
        tamaño_mb = round(tamaño_total / 1024 / 1024, 2)
        
        # Recomendaciones según tamaño
        if tamaño_mb > 25:
            recomendaciones.append("⚠️ El correo excede el límite de Gmail aún con compresión automática.")
            recomendaciones.append("📉 Reduce el número de imágenes adjuntas.")
            recomendaciones.append("🗜️ Las imágenes ya fueron comprimidas automáticamente, pero aún es demasiado.")
            recomendaciones.append("☁️ Considera usar un servicio de transferencia de archivos como WeTransfer.")
        elif tamaño_mb > 20:
            recomendaciones.append("⚠️ El correo está muy cerca del límite. Ten precaución.")
            recomendaciones.append("🎯 La compresión automática ayudó, pero considera reducir algunas imágenes.")
        elif tamaño_mb > 15:
            recomendaciones.append("✅ El correo es grande pero dentro del límite.")
            recomendaciones.append("🗜️ La compresión automática optimizó el tamaño para el envío.")
        else:
            recomendaciones.append("✅ El tamaño del correo es excelente para el envío.")
            recomendaciones.append("🎯 Las imágenes han sido optimizadas automáticamente.")
        
        # Recomendaciones por imágenes excluidas
        if imagenes_excluidas > 0:
            recomendaciones.append(f"⚠️ Hay {imagenes_excluidas} imagen(es) excluidas por ser demasiado grandes.")
            recomendaciones.append("💡 Comprime las imágenes excluidas si deseas incluirlas.")
        
        # Recomendaciones por cantidad de imágenes
        if imagenes_validas > 8:
            recomendaciones.append("📸 Muchas imágenes adjuntas. Considera si todas son necesarias.")
        
        return recomendaciones
    
    def limpiar_archivos_temporales(self):
        """
        Elimina todos los archivos temporales creados durante la compresión.
        
        EXPLICACIÓN:
        Esta función se debe llamar DESPUÉS de enviar el correo exitosamente.
        Elimina todos los archivos temporales comprimidos para no llenar el disco.
        
        ¿Cuándo usar?
        - Después de enviar el correo con éxito
        - Si se cancela el envío (para limpiar)
        - Periódicamente como mantenimiento
        
        Returns:
            Diccionario con:
            - archivos_eliminados: Cantidad de archivos eliminados
            - errores: Lista de errores al eliminar (si los hay)
        """
        archivos_eliminados = 0
        errores = []
        
        for archivo in self.archivos_temporales:
            try:
                if os.path.exists(archivo):
                    os.unlink(archivo)
                    archivos_eliminados += 1
            except Exception as e:
                errores.append(f"Error eliminando {archivo}: {str(e)}")
        
        # Limpiar la lista
        self.archivos_temporales = []
        
        return {
            'archivos_eliminados': archivos_eliminados,
            'errores': errores
        }
    
    @staticmethod
    def limpiar_directorio_temporal(directorio: Optional[str] = None, dias_antiguedad: int = 1):
        """
        Limpia archivos temporales antiguos del directorio.
        
        EXPLICACIÓN:
        Función estática para limpieza de mantenimiento.
        Elimina archivos temporales de compresión que tengan más de X días.
        
        ¿Cuándo usar?
        - Como tarea programada (cron job)
        - Al iniciar la aplicación
        - Periódicamente para mantenimiento
        
        Args:
            directorio: Directorio a limpiar. Si es None, usa el default
            dias_antiguedad: Eliminar archivos con más de X días (default: 1)
            
        Returns:
            Diccionario con:
            - archivos_eliminados: Cantidad de archivos eliminados
            - espacio_liberado_mb: MB liberados
            - errores: Lista de errores (si los hay)
        """
        if directorio is None:
            directorio = os.path.join(settings.MEDIA_ROOT, 'temp', 'compressed')
        
        if not os.path.exists(directorio):
            return {
                'archivos_eliminados': 0,
                'espacio_liberado_mb': 0,
                'errores': []
            }
        
        import time
        
        archivos_eliminados = 0
        espacio_liberado = 0
        errores = []
        tiempo_limite = time.time() - (dias_antiguedad * 24 * 60 * 60)
        
        try:
            for archivo in os.listdir(directorio):
                ruta_completa = os.path.join(directorio, archivo)
                
                if not os.path.isfile(ruta_completa):
                    continue
                
                # Verificar si es un archivo de compresión (empieza con "compressed_")
                if not archivo.startswith('compressed_'):
                    continue
                
                # Verificar antigüedad
                tiempo_modificacion = os.path.getmtime(ruta_completa)
                if tiempo_modificacion < tiempo_limite:
                    try:
                        tamaño = os.path.getsize(ruta_completa)
                        os.unlink(ruta_completa)
                        archivos_eliminados += 1
                        espacio_liberado += tamaño
                    except Exception as e:
                        errores.append(f"Error eliminando {archivo}: {str(e)}")
        
        except Exception as e:
            errores.append(f"Error accediendo al directorio: {str(e)}")
        
        return {
            'archivos_eliminados': archivos_eliminados,
            'espacio_liberado_mb': round(espacio_liberado / 1024 / 1024, 2),
            'errores': errores
        }
