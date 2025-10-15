"""
Script de Prueba para Generador de PDF RHITSO
==============================================

EXPLICACIÓN PARA PRINCIPIANTES:
Este script prueba el generador de PDF sin necesidad de usar el navegador.
Es útil para debugging y verificar que todo funciona correctamente.

Uso:
    python test_pdf_rhitso.py

Requisitos:
    - Tener al menos una orden con es_candidato_rhitso=True
    - Haber colocado las imágenes en static/images/
"""

import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from servicio_tecnico.models import OrdenServicio, ImagenOrden
from servicio_tecnico.utils.pdf_generator import PDFGeneratorRhitso


def probar_generacion_pdf():
    """
    Prueba la generación de PDF con la primera orden RHITSO disponible.
    """
    print("=" * 60)
    print("🧪 PRUEBA DE GENERACIÓN DE PDF RHITSO")
    print("=" * 60)
    print()
    
    # Buscar una orden candidata RHITSO
    print("📋 Buscando órdenes candidatas RHITSO...")
    ordenes_rhitso = OrdenServicio.objects.filter(es_candidato_rhitso=True)
    
    if not ordenes_rhitso.exists():
        print("❌ No hay órdenes marcadas como candidato RHITSO")
        print("💡 Crea una orden y márcala como candidato RHITSO para probar")
        return
    
    orden = ordenes_rhitso.first()
    print(f"✅ Orden encontrada: #{orden.id} - {orden.numero_orden_interno}")
    print(f"   📦 Equipo: {orden.detalle_equipo.marca} {orden.detalle_equipo.modelo}")
    print(f"   🔢 Serie: {orden.detalle_equipo.numero_serie}")
    print()
    
    # Buscar imágenes de autorización
    print("🖼️  Buscando imágenes de autorización...")
    imagenes = ImagenOrden.objects.filter(
        orden=orden,
        tipo='autorizacion'
    ).order_by('-fecha_subida')
    
    if imagenes.exists():
        print(f"✅ Se encontraron {imagenes.count()} imagen(es) de autorización")
        for img in imagenes:
            print(f"   - {img.imagen.name}")
    else:
        print("⚠️  No hay imágenes de autorización (el PDF se generará sin ellas)")
    print()
    
    # Verificar imágenes del sistema
    print("🎨 Verificando imágenes del sistema...")
    
    from django.conf import settings
    imagenes_sistema = {
        'Logo SIC': 'static/images/logos/logo_sic.png',
        'Logo RHITSO': 'static/images/logos/logo_rhitso.png',
        'Diagrama': 'static/images/rhitso/diagrama.png'
    }
    
    for nombre, ruta in imagenes_sistema.items():
        ruta_completa = os.path.join(settings.BASE_DIR, ruta)
        if os.path.exists(ruta_completa):
            print(f"   ✅ {nombre}: Encontrado")
        else:
            print(f"   ⚠️  {nombre}: No encontrado (se omitirá en el PDF)")
    print()
    
    # Generar PDF
    print("🚀 Generando PDF...")
    try:
        generador = PDFGeneratorRhitso(
            orden=orden,
            imagenes_autorizacion=list(imagenes)
        )
        
        resultado = generador.generar_pdf()
        
        if resultado['success']:
            print("=" * 60)
            print("✅ ¡PDF GENERADO EXITOSAMENTE!")
            print("=" * 60)
            print(f"📄 Archivo: {resultado['archivo']}")
            print(f"📁 Ruta: {resultado['ruta']}")
            print(f"💾 Tamaño: {resultado['size'] / 1024:.2f} KB")
            print()
            print("💡 Abre el archivo para verificar el contenido:")
            print(f"   {resultado['ruta']}")
            print()
            
            # Instrucciones adicionales
            print("🔍 Verifica que el PDF contenga:")
            print("   • Logos (si agregaste las imágenes)")
            print("   • Fecha y número de orden correctos")
            print("   • Datos del equipo completos")
            print("   • Motivo del envío")
            print("   • Información de accesorios")
            print("   • Footer con datos de contacto")
            print()
            
        else:
            print("=" * 60)
            print("❌ ERROR AL GENERAR PDF")
            print("=" * 60)
            print(f"Error: {resultado.get('error', 'Error desconocido')}")
            print()
            
    except Exception as e:
        print("=" * 60)
        print("❌ ERROR INESPERADO")
        print("=" * 60)
        print(f"Error: {str(e)}")
        print()
        
        import traceback
        print("Traceback completo:")
        traceback.print_exc()
        print()


def mostrar_info_orden(orden_id: int):
    """
    Muestra información detallada de una orden específica.
    
    Args:
        orden_id: ID de la orden a consultar
    """
    try:
        orden = OrdenServicio.objects.get(id=orden_id)
        
        print("=" * 60)
        print(f"📋 INFORMACIÓN DE LA ORDEN #{orden_id}")
        print("=" * 60)
        print()
        
        print(f"Número Orden: {orden.numero_orden_interno}")
        print(f"Candidato RHITSO: {'✅ Sí' if orden.es_candidato_rhitso else '❌ No'}")
        print()
        
        print("DETALLE DEL EQUIPO:")
        print(f"  Tipo: {orden.detalle_equipo.tipo_equipo}")
        print(f"  Marca: {orden.detalle_equipo.marca}")
        print(f"  Modelo: {orden.detalle_equipo.modelo}")
        print(f"  Número de Serie: {orden.detalle_equipo.numero_serie}")
        print(f"  Orden Cliente: {orden.detalle_equipo.orden_cliente or 'No especificada'}")
        print(f"  Tiene Cargador: {'✅ Sí' if orden.detalle_equipo.tiene_cargador else '❌ No'}")
        
        if orden.detalle_equipo.tiene_cargador:
            print(f"  Serie Cargador: {orden.detalle_equipo.numero_serie_cargador or 'No especificado'}")
        print()
        
        print("INFORMACIÓN RHITSO:")
        print(f"  Motivo: {orden.motivo_rhitso or 'No especificado'}")
        print(f"  Descripción: {orden.descripcion_rhitso or 'No especificada'}")
        print()
        
        imagenes = ImagenOrden.objects.filter(orden=orden)
        print(f"IMÁGENES: {imagenes.count()} total")
        for img in imagenes:
            print(f"  - {img.tipo_imagen}: {img.imagen.name}")
        print()
        
    except OrdenServicio.DoesNotExist:
        print(f"❌ No existe una orden con ID {orden_id}")


def listar_ordenes_rhitso():
    """
    Lista todas las órdenes candidatas RHITSO disponibles.
    """
    ordenes = OrdenServicio.objects.filter(es_candidato_rhitso=True).order_by('-id')
    
    print("=" * 60)
    print("📋 ÓRDENES CANDIDATAS RHITSO")
    print("=" * 60)
    print()
    
    if not ordenes.exists():
        print("❌ No hay órdenes candidatas RHITSO")
        return
    
    print(f"Total: {ordenes.count()} orden(es)")
    print()
    
    for orden in ordenes:
        print(f"ID: {orden.id} | {orden.numero_orden_interno}")
        print(f"   {orden.detalle_equipo.marca} {orden.detalle_equipo.modelo}")
        print(f"   Serie: {orden.detalle_equipo.numero_serie}")
        print(f"   Estado: {orden.get_estado_display()}")
        print()


if __name__ == '__main__':
    import sys
    
    print()
    
    if len(sys.argv) > 1:
        comando = sys.argv[1]
        
        if comando == 'listar':
            listar_ordenes_rhitso()
        elif comando == 'info' and len(sys.argv) > 2:
            orden_id = int(sys.argv[2])
            mostrar_info_orden(orden_id)
        elif comando == 'generar' and len(sys.argv) > 2:
            # Probar con una orden específica
            orden_id = int(sys.argv[2])
            try:
                orden = OrdenServicio.objects.get(id=orden_id)
                imagenes = ImagenOrden.objects.filter(
                    orden=orden,
                    tipo='autorizacion'
                )
                
                generador = PDFGeneratorRhitso(orden, list(imagenes))
                resultado = generador.generar_pdf()
                
                if resultado['success']:
                    print(f"✅ PDF generado: {resultado['ruta']}")
                else:
                    print(f"❌ Error: {resultado['error']}")
                    
            except OrdenServicio.DoesNotExist:
                print(f"❌ No existe orden con ID {orden_id}")
        else:
            print("Comandos disponibles:")
            print("  python test_pdf_rhitso.py              - Prueba automática")
            print("  python test_pdf_rhitso.py listar       - Lista órdenes RHITSO")
            print("  python test_pdf_rhitso.py info <id>    - Info de una orden")
            print("  python test_pdf_rhitso.py generar <id> - Genera PDF de una orden")
    else:
        # Prueba automática
        probar_generacion_pdf()
