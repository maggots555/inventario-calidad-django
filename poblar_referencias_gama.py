"""
Script para poblar automáticamente la tabla ReferenciaGamaEquipo
basándose en los equipos registrados en el sistema.

REGLAS DE CLASIFICACIÓN POR MARCA:

DELL:
- Inspiron 3000 series → BAJA
- Inspiron 5000 series → MEDIA
- Inspiron 7000/Plus → ALTA
- XPS (13/14/16) → ALTA
- G3/G5 → ALTA
- G15/G16 → ALTA
- Latitude (todas) → MEDIA
- Alienware (todas) → ALTA
- Precision → ALTA
- Vostro → BAJA

LENOVO:
- IdeaPad 1 → BAJA
- IdeaPad 3 → MEDIA
- IdeaPad 5 → MEDIA
- IdeaPad Pro 5 → ALTA
- IdeaPad Gaming → ALTA
- IdeaPad Slim → BAJA
- Yoga → ALTA
- Legion → ALTA
- LOQ → ALTA
- ThinkPad E → MEDIA
- ThinkPad L → MEDIA
- ThinkPad T → MEDIA
- ThinkPad X → ALTA
- ThinkPad P → ALTA
- ThinkBook → MEDIA

HP:
- Pavilion → BAJA
- Envy → MEDIA
- Spectre → ALTA
- EliteBook → MEDIA
- ProBook → BAJA
- Omen → ALTA
- ZBook → ALTA
"""
import os
import django
import re
from decimal import Decimal

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from servicio_tecnico.models import DetalleEquipo, ReferenciaGamaEquipo
from django.db import transaction
from django.db.models import Count, Q
from collections import Counter


def clasificar_gama_dell(modelo):
    """
    Clasifica la gama de un equipo Dell según el modelo.
    
    Args:
        modelo (str): Modelo del equipo Dell
    
    Returns:
        str: 'alta', 'media', o 'baja'
    """
    modelo_upper = modelo.upper()
    
    # Alienware → ALTA
    if 'ALIENWARE' in modelo_upper:
        return 'alta'
    
    # XPS → ALTA
    if 'XPS' in modelo_upper:
        return 'alta'
    
    # Precision → ALTA
    if 'PRECISION' in modelo_upper:
        return 'alta'
    
    # Serie G (Gaming) → ALTA
    if re.search(r'\bG\s*(?:3|5|15|16)\b', modelo_upper):
        return 'alta'
    
    # Vostro → BAJA
    if 'VOSTRO' in modelo_upper:
        return 'baja'
    
    # Latitude → MEDIA (todas)
    if 'LATITUDE' in modelo_upper:
        return 'media'
    
    # Inspiron → depende del número de serie
    if 'INSPIRON' in modelo_upper:
        # Buscar el número de modelo (3000, 5000, 7000)
        match = re.search(r'(\d)(\d{3})', modelo)
        if match:
            serie = match.group(1)  # Primer dígito (3, 5, 7)
            
            if serie == '3':
                return 'baja'  # Inspiron 3000 series
            elif serie == '5':
                return 'media'  # Inspiron 5000 series
            elif serie == '7':
                return 'alta'  # Inspiron 7000 series
        
        # Si dice "Plus" → ALTA
        if 'PLUS' in modelo_upper:
            return 'alta'
        
        # Si no se puede determinar el número, asumir MEDIA
        return 'media'
    
    # Por defecto → MEDIA
    return 'media'


def clasificar_gama_lenovo(modelo):
    """
    Clasifica la gama de un equipo Lenovo según el modelo.
    
    Args:
        modelo (str): Modelo del equipo Lenovo
    
    Returns:
        str: 'alta', 'media', o 'baja'
    """
    modelo_upper = modelo.upper()
    
    # Legion → ALTA
    if 'LEGION' in modelo_upper:
        return 'alta'
    
    # LOQ → ALTA
    if 'LOQ' in modelo_upper:
        return 'alta'
    
    # Yoga → ALTA
    if 'YOGA' in modelo_upper:
        return 'alta'
    
    # ThinkPad X → ALTA
    if re.search(r'THINKPAD\s+X', modelo_upper):
        return 'alta'
    
    # ThinkPad P → ALTA (workstation)
    if re.search(r'THINKPAD\s+P', modelo_upper):
        return 'alta'
    
    # ThinkPad E, L, T → MEDIA
    if re.search(r'THINKPAD\s+[ELT]', modelo_upper):
        return 'media'
    
    # ThinkBook → MEDIA
    if 'THINKBOOK' in modelo_upper:
        return 'media'
    
    # IdeaPad Gaming → ALTA
    if 'IDEAPAD' in modelo_upper and 'GAMING' in modelo_upper:
        return 'alta'
    
    # IdeaPad Pro 5 → ALTA
    if 'IDEAPAD' in modelo_upper and 'PRO' in modelo_upper:
        return 'alta'
    
    # IdeaPad 1 → BAJA
    if re.search(r'IDEAPAD\s+1', modelo_upper):
        return 'baja'
    
    # IdeaPad Slim → BAJA
    if 'IDEAPAD' in modelo_upper and 'SLIM' in modelo_upper:
        return 'baja'
    
    # IdeaPad 3 → MEDIA
    if re.search(r'IDEAPAD\s+3', modelo_upper):
        return 'media'
    
    # IdeaPad 5 → MEDIA
    if re.search(r'IDEAPAD\s+5', modelo_upper):
        return 'media'
    
    # IdeaPad genérico → MEDIA (por defecto)
    if 'IDEAPAD' in modelo_upper:
        return 'media'
    
    # Por defecto → MEDIA
    return 'media'


def clasificar_gama_hp(modelo):
    """
    Clasifica la gama de un equipo HP según el modelo.
    
    Args:
        modelo (str): Modelo del equipo HP
    
    Returns:
        str: 'alta', 'media', o 'baja'
    """
    modelo_upper = modelo.upper()
    
    # Omen → ALTA (gaming)
    if 'OMEN' in modelo_upper:
        return 'alta'
    
    # ZBook → ALTA (workstation)
    if 'ZBOOK' in modelo_upper:
        return 'alta'
    
    # Spectre → ALTA (premium)
    if 'SPECTRE' in modelo_upper:
        return 'alta'
    
    # EliteBook → MEDIA (empresarial)
    if 'ELITEBOOK' in modelo_upper or 'ELITE BOOK' in modelo_upper:
        return 'media'
    
    # Envy → MEDIA
    if 'ENVY' in modelo_upper:
        return 'media'
    
    # ProBook → BAJA
    if 'PROBOOK' in modelo_upper or 'PRO BOOK' in modelo_upper:
        return 'baja'
    
    # Pavilion → BAJA
    if 'PAVILION' in modelo_upper or 'PAVILON' in modelo_upper:
        return 'baja'
    
    # Por defecto → MEDIA
    return 'media'


def clasificar_gama_automatica(marca, modelo):
    """
    Clasifica automáticamente la gama según marca y modelo.
    
    Args:
        marca (str): Marca del equipo
        modelo (str): Modelo del equipo
    
    Returns:
        str: 'alta', 'media', o 'baja'
    """
    if marca == 'Dell':
        return clasificar_gama_dell(modelo)
    elif marca == 'Lenovo':
        return clasificar_gama_lenovo(modelo)
    elif marca == 'HP':
        return clasificar_gama_hp(modelo)
    elif marca in ['Asus', 'MSI']:
        # Gaming brands → por defecto ALTA
        if any(keyword in modelo.upper() for keyword in ['ROG', 'TUF', 'GAMING', 'ZEPHYRUS', 'STRIX']):
            return 'alta'
        return 'media'
    else:
        # Marcas desconocidas → MEDIA por defecto
        return 'media'


def extraer_modelo_base(modelo):
    """
    Extrae el modelo base del modelo completo.
    
    Ejemplo:
        "Inspiron 15 3520" → "Inspiron 15 3520"
        "IdeaPad 3 15ITL6" → "IdeaPad 3"
        "Latitude 3520" → "Latitude 3520"
    
    Args:
        modelo (str): Modelo completo
    
    Returns:
        str: Modelo base simplificado
    """
    # Si está vacío o es genérico, retornar vacío
    if not modelo or modelo.strip() == '':
        return ''
    
    modelo_upper = modelo.upper()
    
    # Casos especiales que no queremos como referencias
    if modelo_upper in ['NO IDENTIFICADO', 'NO VISIBLE', 'LENOVO', 'DELL', 'HP']:
        return ''
    
    # Para modelos con código complejo al final, limpiar
    # Ejemplo: "IdeaPad 3 15ITL6" → "IdeaPad 3"
    modelo_limpio = re.sub(r'\s+\d{2}[A-Z]{3,}\d+$', '', modelo)
    
    return modelo_limpio.strip()


def analizar_combinaciones_confiables(min_registros=3):
    """
    Analiza combinaciones marca-modelo con suficientes registros.
    
    Args:
        min_registros (int): Número mínimo de registros para considerar confiable
    
    Returns:
        list: Lista de diccionarios con información de cada combinación
    """
    equipos = DetalleEquipo.objects.exclude(
        Q(modelo='') | 
        Q(modelo__iexact='NO IDENTIFICADO') | 
        Q(modelo__iexact='NO VISIBLE') |
        Q(modelo__iexact='Lenovo') |
        Q(modelo__iexact='Dell') |
        Q(modelo__iexact='HP')
    )
    
    combinaciones = equipos.values('marca', 'modelo').annotate(
        total=Count('orden')
    ).filter(total__gte=min_registros).order_by('-total')
    
    resultados = []
    
    for combo in combinaciones:
        marca = combo['marca']
        modelo = combo['modelo']
        modelo_base = extraer_modelo_base(modelo)
        
        if not modelo_base:
            continue
        
        # Obtener todas las gamas registradas para esta combinación
        gamas_registradas = equipos.filter(
            marca=marca,
            modelo=modelo
        ).values_list('gama', flat=True)
        
        gama_counter = Counter(gamas_registradas)
        gama_predominante = gama_counter.most_common(1)[0][0]
        
        # Clasificar según reglas inteligentes
        gama_inteligente = clasificar_gama_automatica(marca, modelo)
        
        # Calcular rangos de costo (si están disponibles en el futuro)
        rango_costo_min = Decimal('100.00')
        rango_costo_max = Decimal('500.00')
        
        # Ajustar rangos según gama
        if gama_inteligente == 'alta':
            rango_costo_min = Decimal('800.00')
            rango_costo_max = Decimal('2000.00')
        elif gama_inteligente == 'media':
            rango_costo_min = Decimal('400.00')
            rango_costo_max = Decimal('800.00')
        else:  # baja
            rango_costo_min = Decimal('200.00')
            rango_costo_max = Decimal('400.00')
        
        resultados.append({
            'marca': marca,
            'modelo_original': modelo,
            'modelo_base': modelo_base,
            'gama_predominante': gama_predominante,
            'gama_inteligente': gama_inteligente,
            'total_registros': combo['total'],
            'rango_costo_min': rango_costo_min,
            'rango_costo_max': rango_costo_max,
            'coincide_gama': gama_predominante == gama_inteligente
        })
    
    return resultados


def poblar_referencias(combinaciones, dry_run=True):
    """
    Crea referencias en la base de datos.
    
    Args:
        combinaciones (list): Lista de combinaciones a crear
        dry_run (bool): Si es True, solo simula sin guardar
    
    Returns:
        dict: Resumen de la operación
    """
    referencias_creadas = 0
    referencias_actualizadas = 0
    referencias_ignoradas = 0
    errores = []
    
    if not dry_run:
        with transaction.atomic():
            for combo in combinaciones:
                try:
                    # Verificar si ya existe
                    existe = ReferenciaGamaEquipo.objects.filter(
                        marca=combo['marca'],
                        modelo_base=combo['modelo_base']
                    ).first()
                    
                    if existe:
                        # Actualizar si la gama cambió
                        if existe.gama != combo['gama_inteligente']:
                            existe.gama = combo['gama_inteligente']
                            existe.rango_costo_min = combo['rango_costo_min']
                            existe.rango_costo_max = combo['rango_costo_max']
                            existe.save()
                            referencias_actualizadas += 1
                        else:
                            referencias_ignoradas += 1
                    else:
                        # Crear nueva referencia
                        ReferenciaGamaEquipo.objects.create(
                            marca=combo['marca'],
                            modelo_base=combo['modelo_base'],
                            gama=combo['gama_inteligente'],
                            rango_costo_min=combo['rango_costo_min'],
                            rango_costo_max=combo['rango_costo_max'],
                            activo=True
                        )
                        referencias_creadas += 1
                
                except Exception as e:
                    errores.append({
                        'marca': combo['marca'],
                        'modelo': combo['modelo_base'],
                        'error': str(e)
                    })
    else:
        # Solo contar lo que se haría
        for combo in combinaciones:
            existe = ReferenciaGamaEquipo.objects.filter(
                marca=combo['marca'],
                modelo_base=combo['modelo_base']
            ).first()
            
            if existe:
                if existe.gama != combo['gama_inteligente']:
                    referencias_actualizadas += 1
                else:
                    referencias_ignoradas += 1
            else:
                referencias_creadas += 1
    
    return {
        'creadas': referencias_creadas,
        'actualizadas': referencias_actualizadas,
        'ignoradas': referencias_ignoradas,
        'errores': errores
    }


def main():
    """
    Función principal del script.
    """
    print("\n" + "="*70)
    print("SCRIPT DE POBLACIÓN AUTOMÁTICA DE REFERENCIAS DE GAMA")
    print("="*70)
    
    print("\n📊 ANALIZANDO EQUIPOS REGISTRADOS...")
    
    combinaciones = analizar_combinaciones_confiables(min_registros=3)
    
    print(f"\n✅ Se encontraron {len(combinaciones)} combinaciones confiables (3+ registros)")
    
    if not combinaciones:
        print("\n⚠️  No hay suficientes datos para crear referencias.")
        print("   Necesitas más órdenes de servicio registradas.")
        return
    
    # Mostrar preview
    print("\n" + "="*70)
    print("🔍 PREVIEW DE REFERENCIAS A CREAR/ACTUALIZAR")
    print("="*70)
    
    print(f"\n{'#':<4} {'Marca':<10} {'Modelo':<35} {'Gama':<6} {'Registros':<10} {'Match':<6}")
    print("-" * 78)
    
    for i, combo in enumerate(combinaciones[:30], 1):
        match_icon = "✅" if combo['coincide_gama'] else "⚠️"
        print(f"{i:<4} {combo['marca']:<10} {combo['modelo_base'][:35]:<35} "
              f"{combo['gama_inteligente'].upper():<6} {combo['total_registros']:<10} {match_icon:<6}")
    
    if len(combinaciones) > 30:
        print(f"\n... y {len(combinaciones) - 30} más")
    
    # Resumen por gama
    print("\n📈 DISTRIBUCIÓN POR GAMA (clasificación inteligente):")
    gamas_counter = Counter(c['gama_inteligente'] for c in combinaciones)
    for gama, count in gamas_counter.most_common():
        porcentaje = (count / len(combinaciones)) * 100
        print(f"   {gama.upper():<6} → {count:2} referencias ({porcentaje:.1f}%)")
    
    # Resumen de coincidencias
    coincidencias = sum(1 for c in combinaciones if c['coincide_gama'])
    no_coincidencias = len(combinaciones) - coincidencias
    
    print(f"\n📊 ANÁLISIS DE CLASIFICACIÓN:")
    print(f"   ✅ Coinciden con gama registrada: {coincidencias} ({(coincidencias/len(combinaciones)*100):.1f}%)")
    print(f"   ⚠️  Difieren de gama registrada: {no_coincidencias} ({(no_coincidencias/len(combinaciones)*100):.1f}%)")
    
    if no_coincidencias > 0:
        print(f"\n⚠️  NOTA: Hay {no_coincidencias} referencias donde la clasificación inteligente")
        print(f"   difiere de la gama registrada manualmente. Esto puede indicar:")
        print(f"   - Errores en clasificación manual previa")
        print(f"   - Casos especiales que requieren revisión")
    
    # Preview del resultado
    print("\n" + "="*70)
    print("📋 RESUMEN DE OPERACIÓN")
    print("="*70)
    
    resumen = poblar_referencias(combinaciones, dry_run=True)
    
    print(f"\n   🆕 Referencias NUEVAS a crear: {resumen['creadas']}")
    print(f"   🔄 Referencias a ACTUALIZAR: {resumen['actualizadas']}")
    print(f"   ⏭️  Referencias IGNORADAS (ya existen y están correctas): {resumen['ignoradas']}")
    
    # Confirmación
    print("\n" + "="*70)
    print("⚠️  CONFIRMACIÓN REQUERIDA")
    print("="*70)
    
    respuesta = input("\n¿Deseas ejecutar la población de referencias? (si/no): ").lower().strip()
    
    if respuesta in ['si', 'sí', 's', 'yes', 'y']:
        print("\n🔄 EJECUTANDO POBLACIÓN DE REFERENCIAS...")
        
        resumen_final = poblar_referencias(combinaciones, dry_run=False)
        
        print(f"\n✅ ¡POBLACIÓN COMPLETADA!")
        print(f"   🆕 Referencias creadas: {resumen_final['creadas']}")
        print(f"   🔄 Referencias actualizadas: {resumen_final['actualizadas']}")
        print(f"   ⏭️  Referencias sin cambios: {resumen_final['ignoradas']}")
        
        if resumen_final['errores']:
            print(f"\n⚠️  Se encontraron {len(resumen_final['errores'])} errores:")
            for error in resumen_final['errores'][:5]:
                print(f"   - {error['marca']} {error['modelo']}: {error['error']}")
        
        # Verificar total de referencias
        total_referencias = ReferenciaGamaEquipo.objects.filter(activo=True).count()
        print(f"\n📚 Total de referencias activas en el sistema: {total_referencias}")
        
        print("\n💡 SIGUIENTE PASO:")
        print("   Prueba crear una orden de servicio y verifica que la gama")
        print("   se asigne automáticamente según estas nuevas referencias.")
    else:
        print("\n❌ Población cancelada por el usuario.")
        print("   No se realizaron cambios en la base de datos.")
    
    print("\n" + "="*70)
    print("FIN DEL SCRIPT")
    print("="*70 + "\n")


if __name__ == '__main__':
    main()
