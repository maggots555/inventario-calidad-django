"""
Script para extraer marcas y modelos únicos de la base de datos
Este script genera un reporte de todas las marcas y modelos que existen
en las órdenes de servicio para poblar la base de datos de referencia.

Uso:
    python scripts/verificacion/extraer_marcas_modelos.py

Salida:
    - Reporte en consola con marcas y modelos
    - Archivo JSON con la estructura de datos
    - Estadísticas de frecuencia de uso
"""

import os
import sys
import django
import json
from collections import defaultdict, Counter

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from servicio_tecnico.models import DetalleEquipo
from django.db.models import Count


def extraer_marcas_modelos():
    """
    Extrae todas las marcas y modelos únicos de la base de datos.
    Retorna un diccionario organizado por marca con sus modelos y frecuencia.
    
    FILTROS APLICADOS:
    - Excluye modelos vacíos o genéricos (SIN MODELO, NO IDENTIFICADO, NO VISIBLE)
    - Excluye modelos que son iguales a la marca
    - Solo incluye datos útiles para la base de referencia
    """
    print("=" * 80)
    print("EXTRAYENDO MARCAS Y MODELOS DE LA BASE DE DATOS (DATOS ÚTILES)")
    print("=" * 80)
    print()
    
    # Obtener todos los registros con marca y modelo
    detalles = DetalleEquipo.objects.all().values('marca', 'modelo')
    total_registros = detalles.count()
    
    print(f"📊 Total de equipos en base de datos: {total_registros}")
    print()
    
    if total_registros == 0:
        print("⚠️  No hay registros en la base de datos.")
        return {}
    
    # Modelos a excluir (normalizado a minúsculas para comparación)
    MODELOS_EXCLUIDOS = {
        'sin modelo',
        'no identificado',
        'no visible',
        'no visibles',
    }
    
    # Organizar por marca
    marcas_modelos = defaultdict(list)
    combinaciones = []
    registros_excluidos = 0
    
    for detalle in detalles:
        marca = detalle['marca'].strip() if detalle['marca'] else ''
        modelo = detalle['modelo'].strip() if detalle['modelo'] else ''
        
        # Saltar si no hay marca
        if not marca:
            registros_excluidos += 1
            continue
        
        # Normalizar para comparación
        modelo_lower = modelo.lower()
        marca_lower = marca.lower()
        
        # Excluir modelos vacíos o en lista de excluidos
        if not modelo or modelo_lower in MODELOS_EXCLUIDOS:
            registros_excluidos += 1
            continue
        
        # Excluir si el modelo es igual a la marca
        if modelo_lower == marca_lower:
            registros_excluidos += 1
            continue
        
        # Registro válido
        combinaciones.append((marca, modelo))
        if modelo not in marcas_modelos[marca]:
            marcas_modelos[marca].append(modelo)
    
    # Contar frecuencias
    frecuencias = Counter(combinaciones)
    
    print(f"✅ Registros útiles: {len(combinaciones)}")
    print(f"❌ Registros excluidos: {registros_excluidos}")
    print()
    
    # Ordenar marcas alfabéticamente
    marcas_ordenadas = sorted(marcas_modelos.keys())
    
    print("=" * 80)
    print("MARCAS Y MODELOS ENCONTRADOS (SOLO DATOS ÚTILES)")
    print("=" * 80)
    print()
    
    # Estructura de datos para exportar
    datos_exportacion = {
        'metadata': {
            'total_registros_bd': total_registros,
            'registros_utiles': len(combinaciones),
            'registros_excluidos': registros_excluidos,
            'total_marcas': len(marcas_ordenadas),
            'fecha_extraccion': None  # Se llenará más adelante
        },
        'marcas': {}
    }
    
    # Mostrar resultados por marca
    total_modelos = 0
    for marca in marcas_ordenadas:
        modelos = sorted(marcas_modelos[marca])
        total_modelos += len(modelos)
        
        print(f"🏷️  {marca}")
        print(f"   Modelos únicos: {len(modelos)}")
        print()
        
        # Preparar datos para exportación
        modelos_con_frecuencia = []
        
        for modelo in modelos:
            frecuencia = frecuencias[(marca, modelo)]
            modelos_con_frecuencia.append({
                'modelo': modelo,
                'frecuencia': frecuencia
            })
            print(f"      • {modelo} ({frecuencia} vez/veces)")
        
        print()
        
        # Agregar a estructura de exportación
        datos_exportacion['marcas'][marca] = {
            'total_modelos': len(modelos),
            'modelos': modelos_con_frecuencia
        }
    
    # Actualizar metadata
    datos_exportacion['metadata']['total_modelos'] = total_modelos
    
    print("=" * 80)
    print("RESUMEN ESTADÍSTICO")
    print("=" * 80)
    print()
    print(f"📊 Registros totales en BD: {total_registros}")
    print(f"✅ Registros útiles extraídos: {len(combinaciones)}")
    print(f"❌ Registros excluidos: {registros_excluidos}")
    print(f"📊 Tasa de aprovechamiento: {len(combinaciones) / total_registros * 100:.1f}%")
    print()
    print(f"🏷️  Total de marcas únicas: {len(marcas_ordenadas)}")
    print(f"📦 Total de modelos únicos: {total_modelos}")
    print(f"📊 Promedio de modelos por marca: {total_modelos / len(marcas_ordenadas):.2f}")
    print()
    
    # Top 10 combinaciones más frecuentes
    print("=" * 80)
    print("TOP 10 COMBINACIONES MÁS FRECUENTES")
    print("=" * 80)
    print()
    
    for i, ((marca, modelo), frecuencia) in enumerate(frecuencias.most_common(10), 1):
        print(f"{i:2d}. {marca} - {modelo}: {frecuencia} veces")
    
    print()
    
    return datos_exportacion


def exportar_json(datos, nombre_archivo='marcas_modelos_extraidos.json'):
    """
    Exporta los datos a un archivo JSON.
    """
    from datetime import datetime
    
    # Agregar fecha de extracción
    datos['metadata']['fecha_extraccion'] = datetime.now().isoformat()
    
    ruta_salida = os.path.join(
        os.path.dirname(__file__),
        nombre_archivo
    )
    
    with open(ruta_salida, 'w', encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    
    print("=" * 80)
    print("EXPORTACIÓN COMPLETADA")
    print("=" * 80)
    print()
    print(f"✅ Archivo generado: {ruta_salida}")
    print()
    print("💡 Puedes usar este archivo para:")
    print("   1. Poblar la base de datos de referencia (MarcaEquipo, ModeloEquipo)")
    print("   2. Actualizar el autocompletado del frontend")
    print("   3. Generar reportes de equipos más comunes")
    print()


def clasificar_gama(marca, modelo):
    """
    Clasifica la gama de un equipo basándose en la marca y modelo.
    
    Returns:
        tuple: (gama, costo_min, costo_max)
            gama: 'alta', 'media', 'baja'
            costo_min, costo_max: rangos de precio en dólares
    """
    modelo_lower = modelo.lower()
    marca_lower = marca.lower()
    
    # ============================================================================
    # GAMA ALTA - Equipos de alto rendimiento y profesionales
    # ============================================================================
    if any(keyword in modelo_lower for keyword in [
        'alienware', 'xps', 'precision', 'thinkpad p', 'legion pro', 'legion 7',
        'thinkpad x1', 'elitebook', 'zbook', 'macbook pro', 'studio', 'pro art',
        'rog', 'republic', 'predator', 'razer', 'surface pro', 'surface laptop studio'
    ]):
        return ('alta', 1200, 4000)
    
    # ============================================================================
    # GAMA MEDIA-ALTA - Gaming y profesionales de entrada
    # ============================================================================
    if any(keyword in modelo_lower for keyword in [
        'legion 5', 'legion y', 'loq', 'omen', 'victus', 'pavilion gaming',
        'g15', 'g5', 'g7', 'latitude 5', 'latitude 7', 'thinkpad t', 'thinkpad e',
        'thinkbook', 'inspiron 7', 'inspiron 16', 'ideapad gaming', 'vivobook pro',
        'zenbook', 'yoga 9', 'yoga 7', 'envy', 'spectre', 'vostro 5'
    ]):
        return ('media', 700, 1500)
    
    # ============================================================================
    # GAMA MEDIA - Uso general y oficina
    # ============================================================================
    if any(keyword in modelo_lower for keyword in [
        'inspiron 5', 'inspiron 15', 'inspiron 14', 'inspiron 13',
        'latitude 3', 'ideapad 5', 'ideapad slim 5', 'thinkpad l',
        'pavilion', 'probook', 'elitedesk', 'optiplex', 'vostro 3',
        'yoga 5', 'flex', 'vivobook', 'aspire 5', 'aspire 7'
    ]):
        return ('media', 450, 900)
    
    # ============================================================================
    # GAMA BAJA - Equipos básicos y de entrada
    # ============================================================================
    if any(keyword in modelo_lower for keyword in [
        'inspiron 3', 'ideapad 1', 'ideapad 3', 'ideapad slim 3',
        'v14', 'v15', 'chromebook', 'aspire 3', 'aspire 1',
        '240 g', '245 g', '250 g', 'essential', 'stream'
    ]):
        return ('baja', 250, 600)
    
    # ============================================================================
    # Por defecto: GAMA MEDIA (si no se puede clasificar)
    # ============================================================================
    return ('media', 400, 1000)


def generar_script_poblado(datos):
    """
    Genera un script Python para poblar ReferenciaGamaEquipo.
    Incluye clasificación automática de gamas y rangos de costo.
    """
    print("=" * 80)
    print("GENERANDO SCRIPT DE POBLADO PARA ReferenciaGamaEquipo")
    print("=" * 80)
    print()
    
    script_lineas = [
        '"""',
        'Script para poblar la tabla ReferenciaGamaEquipo',
        'Generado automáticamente desde la base de datos existente',
        '',
        'Este script:',
        '1. Extrae marcas y modelos únicos de las órdenes existentes',
        '2. Clasifica automáticamente la gama (alta/media/baja)',
        '3. Asigna rangos de costo aproximados',
        '4. Puebla la tabla ReferenciaGamaEquipo',
        '',
        'Uso:',
        '    python scripts/verificacion/poblar_marcas_modelos.py',
        '"""',
        '',
        'import os',
        'import sys',
        'import django',
        'from decimal import Decimal',
        '',
        '# Configurar Django',
        "sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))",
        "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')",
        'django.setup()',
        '',
        'from servicio_tecnico.models import ReferenciaGamaEquipo',
        '',
        '',
        'def poblar_referencias_gama():',
        '    """',
        '    Puebla la tabla ReferenciaGamaEquipo con datos extraídos.',
        '    """',
        '    print("=" * 80)',
        '    print("POBLANDO ReferenciaGamaEquipo")',
        '    print("=" * 80)',
        '    print()',
        '    ',
        '    creados = 0',
        '    existentes = 0',
        '    actualizados = 0',
        '    ',
    ]
    
    for marca, info in datos['marcas'].items():
        script_lineas.append(f"    # ========================================")
        script_lineas.append(f"    # Marca: {marca} ({info['total_modelos']} modelos)")
        script_lineas.append(f"    # ========================================")
        
        for modelo_data in info['modelos']:
            modelo = modelo_data['modelo'].replace("'", "\\'")  # Escapar comillas
            frecuencia = modelo_data['frecuencia']
            
            # Clasificar gama
            gama, costo_min, costo_max = clasificar_gama(marca, modelo)
            
            script_lineas.append(f"    ")
            script_lineas.append(f"    # {modelo} (usado {frecuencia} veces) - Gama: {gama}")
            script_lineas.append(f"    obj, created = ReferenciaGamaEquipo.objects.get_or_create(")
            script_lineas.append(f"        marca='{marca}',")
            script_lineas.append(f"        modelo_base='{modelo}',")
            script_lineas.append(f"        defaults={{")
            script_lineas.append(f"            'gama': '{gama}',")
            script_lineas.append(f"            'rango_costo_min': Decimal('{costo_min}'),")
            script_lineas.append(f"            'rango_costo_max': Decimal('{costo_max}'),")
            script_lineas.append(f"            'activo': True")
            script_lineas.append(f"        }}")
            script_lineas.append(f"    )")
            script_lineas.append(f"    if created:")
            script_lineas.append(f"        creados += 1")
            script_lineas.append(f"        print(f'✅ Creado: {marca} - {modelo} ({{obj.get_gama_display()}})')")
            script_lineas.append(f"    else:")
            script_lineas.append(f"        existentes += 1")
        
        script_lineas.append("")
    
    script_lineas.extend([
        "    print()",
        "    print('=' * 80)",
        "    print('RESUMEN DEL POBLADO')",
        "    print('=' * 80)",
        "    print()",
        "    print(f'✅ Registros creados: {creados}')",
        "    print(f'ℹ️  Registros existentes (no modificados): {existentes}')",
        "    print(f'📊 Total procesado: {creados + existentes}')",
        "    print()",
        "    ",
        "    # Mostrar estadísticas por gama",
        "    print('Distribución por Gama:')",
        "    for gama_code, gama_nombre in [('alta', 'Alta'), ('media', 'Media'), ('baja', 'Baja')]:",
        "        count = ReferenciaGamaEquipo.objects.filter(gama=gama_code, activo=True).count()",
        "        print(f'  {gama_nombre}: {count} referencias')",
        "    print()",
        "",
        "",
        "if __name__ == '__main__':",
        "    try:",
        "        poblar_referencias_gama()",
        "        print('✅ Poblado completado exitosamente')",
        "    except Exception as e:",
        "        print(f'❌ Error: {e}')",
        "        import traceback",
        "        traceback.print_exc()",
        "        sys.exit(1)",
    ])
    
    
    ruta_script = os.path.join(
        os.path.dirname(__file__),
        'poblar_marcas_modelos.py'
    )
    
    with open(ruta_script, 'w', encoding='utf-8') as f:
        f.write('\n'.join(script_lineas))
    
    print(f"✅ Script de poblado generado: {ruta_script}")
    print()
    print("💡 Para ejecutar el script de poblado:")
    print(f"   python {ruta_script}")
    print()


if __name__ == '__main__':
    try:
        # Extraer datos
        datos = extraer_marcas_modelos()
        
        if datos and datos['marcas']:
            # Exportar a JSON
            exportar_json(datos)
            
            # Generar script de poblado
            generar_script_poblado(datos)
            
            print("=" * 80)
            print("✅ PROCESO COMPLETADO EXITOSAMENTE")
            print("=" * 80)
        else:
            print("⚠️  No se encontraron datos para exportar.")
    
    except Exception as e:
        print(f"❌ Error durante la extracción: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
