"""
Script de Prueba para Compresión de Imágenes RHITSO
====================================================

EXPLICACIÓN PARA PRINCIPIANTES:
Este script prueba el compresor de imágenes sin necesidad de usar el navegador.
Simula el proceso completo de preparación del correo.

Uso:
    python test_compresion_imagenes.py

Funcionalidades:
    1. Comprimir una imagen individual
    2. Calcular tamaño total de un correo simulado
    3. Limpiar archivos temporales
    4. Mostrar estadísticas detalladas
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from servicio_tecnico.models import OrdenServicio, ImagenOrden
from servicio_tecnico.utils.image_compressor import ImageCompressor
from servicio_tecnico.utils.pdf_generator import PDFGeneratorRhitso


def probar_compresion_individual():
    """
    Prueba la compresión de una imagen individual.
    """
    print("=" * 70)
    print("🧪 PRUEBA 1: COMPRESIÓN DE IMAGEN INDIVIDUAL")
    print("=" * 70)
    print()
    
    # Buscar una imagen de tipo "ingreso" para probar
    print("🔍 Buscando imágenes de tipo 'ingreso'...")
    imagenes = ImagenOrden.objects.filter(tipo='ingreso').order_by('-fecha_subida')[:5]
    
    if not imagenes.exists():
        print("❌ No hay imágenes de tipo 'ingreso' para probar")
        print("💡 Sube alguna imagen de ingreso a una orden para probar")
        return
    
    print(f"✅ Se encontraron {imagenes.count()} imagen(es)")
    print()
    
    # Tomar la primera imagen
    imagen = imagenes.first()
    print(f"📸 Imagen seleccionada: {imagen.imagen.name}")
    
    from django.conf import settings
    ruta_imagen = os.path.join(settings.MEDIA_ROOT, str(imagen.imagen))
    
    if not os.path.exists(ruta_imagen):
        print(f"❌ Archivo no encontrado: {ruta_imagen}")
        return
    
    tamaño_original = os.path.getsize(ruta_imagen)
    print(f"📊 Tamaño original: {tamaño_original / 1024:.2f} KB ({tamaño_original / 1024 / 1024:.2f} MB)")
    print()
    
    # Comprimir imagen
    print("🗜️  Comprimiendo imagen...")
    compresor = ImageCompressor()
    resultado = compresor.comprimir_imagen_para_correo(ruta_imagen)
    
    if resultado['success']:
        print("=" * 70)
        print("✅ COMPRESIÓN EXITOSA")
        print("=" * 70)
        
        if resultado['fue_comprimida']:
            print(f"📄 Archivo comprimido: {os.path.basename(resultado['ruta_comprimida'])}")
            print(f"📁 Ruta: {resultado['ruta_comprimida']}")
            print()
            print(f"📊 Tamaño original: {resultado['tamaño_original'] / 1024:.2f} KB")
            print(f"📊 Tamaño comprimido: {resultado['tamaño_comprimido'] / 1024:.2f} KB")
            print(f"📉 Reducción: {resultado['reduccion_porcentaje']}%")
            print()
            print(f"📐 Dimensiones originales: {resultado['dimensiones_originales'][0]}x{resultado['dimensiones_originales'][1]} px")
            print(f"📐 Dimensiones nuevas: {resultado['dimensiones_nuevas'][0]}x{resultado['dimensiones_nuevas'][1]} px")
        else:
            print(f"ℹ️  Imagen no comprimida: {resultado.get('razon', 'Ya es pequeña')}")
        print()
        
        # Limpiar archivo temporal
        print("🧹 Limpiando archivos temporales...")
        limpieza = compresor.limpiar_archivos_temporales()
        print(f"✅ {limpieza['archivos_eliminados']} archivo(s) temporal(es) eliminado(s)")
        
    else:
        print("❌ ERROR EN COMPRESIÓN")
        print(f"Error: {resultado.get('error', 'Desconocido')}")
    
    print()


def probar_calculo_tamaño_correo():
    """
    Prueba el cálculo del tamaño total de un correo con PDF + imágenes.
    """
    print("=" * 70)
    print("🧪 PRUEBA 2: CÁLCULO DE TAMAÑO DE CORREO COMPLETO")
    print("=" * 70)
    print()
    
    # Buscar una orden RHITSO
    print("📋 Buscando orden RHITSO para probar...")
    ordenes_rhitso = OrdenServicio.objects.filter(es_candidato_rhitso=True)
    
    if not ordenes_rhitso.exists():
        print("❌ No hay órdenes candidatas RHITSO")
        return
    
    orden = ordenes_rhitso.first()
    print(f"✅ Orden encontrada: #{orden.id} - {orden.numero_orden_interno}")
    print(f"   📦 Equipo: {orden.detalle_equipo.marca} {orden.detalle_equipo.modelo}")
    print()
    
    # Generar PDF
    print("📄 Generando PDF...")
    imagenes_autorizacion = ImagenOrden.objects.filter(
        orden=orden,
        tipo='autorizacion'
    )
    
    generador_pdf = PDFGeneratorRhitso(orden, list(imagenes_autorizacion))
    resultado_pdf = generador_pdf.generar_pdf()
    
    if not resultado_pdf['success']:
        print(f"❌ Error generando PDF: {resultado_pdf.get('error')}")
        return
    
    print(f"✅ PDF generado: {resultado_pdf['archivo']}")
    print(f"   💾 Tamaño: {resultado_pdf['size'] / 1024:.2f} KB")
    print()
    
    # Obtener imágenes de ingreso
    print("🖼️  Buscando imágenes de ingreso para adjuntar...")
    imagenes_ingreso = ImagenOrden.objects.filter(
        orden=orden,
        tipo='ingreso'
    ).order_by('-fecha_subida')
    
    if not imagenes_ingreso.exists():
        print("⚠️  No hay imágenes de ingreso (se calculará solo con PDF)")
        lista_imagenes = []
    else:
        print(f"✅ Se encontraron {imagenes_ingreso.count()} imagen(es) de ingreso")
        
        from django.conf import settings
        lista_imagenes = []
        for img in imagenes_ingreso:
            ruta = os.path.join(settings.MEDIA_ROOT, str(img.imagen))
            lista_imagenes.append({
                'ruta': ruta,
                'nombre': img.imagen.name
            })
    print()
    
    # Calcular tamaño del correo
    print("📊 Calculando tamaño total del correo...")
    compresor = ImageCompressor()
    
    contenido_html = f"""
    <html>
        <body>
            <h1>Envío de Equipo RHITSO</h1>
            <p>Orden: {orden.numero_orden_interno}</p>
            <p>Equipo: {orden.detalle_equipo.marca} {orden.detalle_equipo.modelo}</p>
            <p>Serie: {orden.detalle_equipo.numero_serie}</p>
        </body>
    </html>
    """
    
    resultado = compresor.calcular_tamaño_correo(
        ruta_pdf=resultado_pdf['ruta'],
        imagenes=lista_imagenes,
        contenido_html=contenido_html
    )
    
    if resultado['success']:
        print("=" * 70)
        print("✅ CÁLCULO COMPLETADO")
        print("=" * 70)
        print()
        
        # Mostrar detalles
        print("📊 DESGLOSE DE TAMAÑOS:")
        print("-" * 70)
        
        # PDF
        pdf_info = resultado['detalles'].get('pdf', {})
        print(f"📄 PDF: {pdf_info.get('tamaño_mb', 0):.2f} MB")
        
        # HTML
        html_info = resultado['detalles'].get('html', {})
        print(f"📧 HTML: {html_info.get('tamaño_mb', 0):.3f} MB")
        
        # Imágenes
        imagenes_info = resultado['detalles'].get('imagenes', {})
        if imagenes_info.get('count', 0) > 0:
            print(f"🖼️  Imágenes ({imagenes_info['count']}):")
            print(f"   Original: {imagenes_info['tamaño_original_mb']:.2f} MB")
            print(f"   Comprimido: {imagenes_info['tamaño_comprimido_mb']:.2f} MB")
            print(f"   Reducción: {imagenes_info['reduccion_total_mb']:.2f} MB")
        
        print("-" * 70)
        print(f"📦 TOTAL: {resultado['tamaño_total_mb']:.2f} MB / {resultado['limite_gmail_mb']} MB")
        print()
        
        # Estadoexcede
        if resultado['excede_limite']:
            print("❌ ¡EXCEDE EL LÍMITE DE GMAIL!")
        else:
            porcentaje_usado = (resultado['tamaño_total_mb'] / resultado['limite_gmail_mb']) * 100
            print(f"✅ Dentro del límite ({porcentaje_usado:.1f}% usado)")
        print()
        
        # Imágenes válidas
        if resultado['imagenes_validas']:
            print(f"✅ IMÁGENES VÁLIDAS ({len(resultado['imagenes_validas'])}):")
            print("-" * 70)
            for img in resultado['imagenes_validas']:
                print(f"   📸 {img['nombre']}")
                print(f"      Original: {img['tamaño_original_mb']:.2f} MB → "
                      f"Comprimido: {img['tamaño_comprimido_mb']:.2f} MB "
                      f"({img['reduccion_porcentaje']:.1f}% reducción)")
                if img['fue_comprimida']:
                    print(f"      ✅ Comprimida automáticamente")
                else:
                    print(f"      ℹ️  No requirió compresión")
            print()
        
        # Imágenes excluidas
        if resultado['imagenes_excluidas']:
            print(f"❌ IMÁGENES EXCLUIDAS ({len(resultado['imagenes_excluidas'])}):")
            print("-" * 70)
            for img in resultado['imagenes_excluidas']:
                print(f"   📸 {img['nombre']}")
                print(f"      Tamaño: {img['tamaño_mb']:.2f} MB")
                print(f"      Razón: {img['razon']}")
            print()
        
        # Recomendaciones
        if resultado['recomendaciones']:
            print("💡 RECOMENDACIONES:")
            print("-" * 70)
            for recomendacion in resultado['recomendaciones']:
                print(f"   {recomendacion}")
            print()
        
        # Limpiar archivos temporales
        print("🧹 Limpiando archivos temporales...")
        limpieza = compresor.limpiar_archivos_temporales()
        print(f"✅ {limpieza['archivos_eliminados']} archivo(s) temporal(es) eliminado(s)")
        
        # Limpiar PDF temporal
        if os.path.exists(resultado_pdf['ruta']):
            os.unlink(resultado_pdf['ruta'])
            print(f"✅ PDF temporal eliminado")
        
    else:
        print("❌ ERROR EN CÁLCULO")
        print(f"Error: {resultado.get('error', 'Desconocido')}")
    
    print()


def probar_limpieza_directorio():
    """
    Prueba la limpieza de archivos temporales antiguos.
    """
    print("=" * 70)
    print("🧪 PRUEBA 3: LIMPIEZA DE DIRECTORIO TEMPORAL")
    print("=" * 70)
    print()
    
    print("🧹 Limpiando archivos temporales antiguos (> 1 día)...")
    resultado = ImageCompressor.limpiar_directorio_temporal(dias_antiguedad=1)
    
    print(f"✅ Archivos eliminados: {resultado['archivos_eliminados']}")
    print(f"💾 Espacio liberado: {resultado['espacio_liberado_mb']:.2f} MB")
    
    if resultado['errores']:
        print(f"⚠️  Errores encontrados:")
        for error in resultado['errores']:
            print(f"   - {error}")
    
    print()


def mostrar_estadisticas():
    """
    Muestra estadísticas generales del sistema.
    """
    print("=" * 70)
    print("📊 ESTADÍSTICAS DEL SISTEMA")
    print("=" * 70)
    print()
    
    # Contar imágenes por tipo
    from django.db.models import Count
    
    stats = ImagenOrden.objects.values('tipo').annotate(count=Count('id'))
    
    print("📸 IMÁGENES POR TIPO:")
    print("-" * 70)
    for stat in stats:
        tipo_display = dict(ImagenOrden._meta.get_field('tipo').choices).get(stat['tipo'], stat['tipo'])
        print(f"   {tipo_display}: {stat['count']}")
    print()
    
    # Órdenes RHITSO
    ordenes_rhitso = OrdenServicio.objects.filter(es_candidato_rhitso=True).count()
    print(f"🔧 Órdenes RHITSO: {ordenes_rhitso}")
    print()
    
    # Tamaño del directorio temporal
    from django.conf import settings
    directorio_temp = os.path.join(settings.MEDIA_ROOT, 'temp', 'compressed')
    
    if os.path.exists(directorio_temp):
        archivos = [f for f in os.listdir(directorio_temp) if f.startswith('compressed_')]
        tamaño_total = sum(os.path.getsize(os.path.join(directorio_temp, f)) for f in archivos)
        
        print(f"🗂️  Directorio temporal:")
        print(f"   Archivos: {len(archivos)}")
        print(f"   Tamaño total: {tamaño_total / 1024 / 1024:.2f} MB")
    else:
        print(f"🗂️  Directorio temporal: No existe (se creará al comprimir)")
    
    print()


if __name__ == '__main__':
    print()
    print("🧪 PRUEBAS DE COMPRESIÓN DE IMÁGENES RHITSO")
    print()
    
    if len(sys.argv) > 1:
        comando = sys.argv[1]
        
        if comando == 'individual':
            probar_compresion_individual()
        elif comando == 'correo':
            probar_calculo_tamaño_correo()
        elif comando == 'limpiar':
            probar_limpieza_directorio()
        elif comando == 'stats':
            mostrar_estadisticas()
        else:
            print("Comandos disponibles:")
            print("  python test_compresion_imagenes.py individual  - Prueba compresión individual")
            print("  python test_compresion_imagenes.py correo      - Prueba cálculo de correo")
            print("  python test_compresion_imagenes.py limpiar     - Limpia archivos temporales")
            print("  python test_compresion_imagenes.py stats       - Muestra estadísticas")
            print("  python test_compresion_imagenes.py             - Ejecuta todas las pruebas")
    else:
        # Ejecutar todas las pruebas
        probar_compresion_individual()
        print()
        probar_calculo_tamaño_correo()
        print()
        probar_limpieza_directorio()
        print()
        mostrar_estadisticas()
