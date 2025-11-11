"""
Script de Diagnóstico - Gráficos de Proveedores
================================================

Este script verifica si hay datos suficientes para generar los gráficos:
1. Impacto en Conversión de Ventas
2. Especialización por Componente

EXPLICACIÓN:
Los gráficos necesitan datos específicos de:
- SeguimientoPieza: Seguimiento de pedidos a proveedores
- PiezaCotizada: Piezas cotizadas con respuesta del cliente
- Cotizaciones con estado aceptado/rechazado
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from servicio_tecnico.models import (
    Cotizacion, PiezaCotizada, SeguimientoPieza, ComponenteEquipo
)
from django.db.models import Count, Q, Sum

def diagnostico_completo():
    """Realiza un diagnóstico completo de los datos necesarios."""
    
    print("\n" + "="*80)
    print("DIAGNÓSTICO DE DATOS PARA GRÁFICOS DE PROVEEDORES")
    print("="*80)
    
    # ========================================================================
    # 1. DATOS GENERALES
    # ========================================================================
    print("\n📊 1. DATOS GENERALES")
    print("-" * 80)
    
    total_cotizaciones = Cotizacion.objects.count()
    print(f"Total de cotizaciones: {total_cotizaciones}")
    
    total_piezas = PiezaCotizada.objects.count()
    print(f"Total de piezas cotizadas: {total_piezas}")
    
    total_seguimientos = SeguimientoPieza.objects.count()
    print(f"Total de seguimientos de piezas: {total_seguimientos}")
    
    total_componentes = ComponenteEquipo.objects.count()
    print(f"Total de componentes definidos: {total_componentes}")
    
    # ========================================================================
    # 2. ANÁLISIS DE COTIZACIONES CON RESPUESTA
    # ========================================================================
    print("\n📋 2. ANÁLISIS DE COTIZACIONES CON RESPUESTA")
    print("-" * 80)
    
    cotizaciones_aceptadas = Cotizacion.objects.filter(usuario_acepto=True).count()
    cotizaciones_rechazadas = Cotizacion.objects.filter(usuario_acepto=False).count()
    cotizaciones_sin_respuesta = Cotizacion.objects.filter(usuario_acepto__isnull=True).count()
    
    print(f"✅ Cotizaciones ACEPTADAS: {cotizaciones_aceptadas}")
    print(f"❌ Cotizaciones RECHAZADAS: {cotizaciones_rechazadas}")
    print(f"⏳ Cotizaciones SIN RESPUESTA: {cotizaciones_sin_respuesta}")
    
    cotizaciones_con_respuesta = cotizaciones_aceptadas + cotizaciones_rechazadas
    print(f"\n📈 Total con respuesta: {cotizaciones_con_respuesta}")
    
    if cotizaciones_con_respuesta > 0:
        tasa_aceptacion = (cotizaciones_aceptadas / cotizaciones_con_respuesta) * 100
        print(f"📊 Tasa de aceptación: {tasa_aceptacion:.1f}%")
    
    # ========================================================================
    # 3. ANÁLISIS DE SEGUIMIENTOS DE PIEZAS
    # ========================================================================
    print("\n📦 3. ANÁLISIS DE SEGUIMIENTOS DE PIEZAS")
    print("-" * 80)
    
    seguimientos_con_proveedor = SeguimientoPieza.objects.exclude(
        Q(proveedor__isnull=True) | Q(proveedor='')
    )
    print(f"Seguimientos con proveedor definido: {seguimientos_con_proveedor.count()}")
    
    # Listar proveedores únicos
    proveedores = seguimientos_con_proveedor.values_list('proveedor', flat=True).distinct()
    print(f"\n👥 Proveedores registrados ({len(proveedores)}):")
    for proveedor in proveedores:
        count = seguimientos_con_proveedor.filter(proveedor=proveedor).count()
        print(f"   - {proveedor}: {count} seguimientos")
    
    # ========================================================================
    # 4. ANÁLISIS CRÍTICO: SEGUIMIENTOS CON COTIZACIONES RESPONDIDAS
    # ========================================================================
    print("\n🔍 4. ANÁLISIS CRÍTICO: RELACIÓN SEGUIMIENTOS ↔ RESPUESTAS")
    print("-" * 80)
    
    # Seguimientos cuya cotización tiene respuesta
    seguimientos_con_respuesta = SeguimientoPieza.objects.filter(
        Q(cotizacion__usuario_acepto=True) | Q(cotizacion__usuario_acepto=False)
    ).exclude(Q(proveedor__isnull=True) | Q(proveedor=''))
    
    count_seg_respuesta = seguimientos_con_respuesta.count()
    print(f"✅ Seguimientos con cotización respondida: {count_seg_respuesta}")
    
    if count_seg_respuesta == 0:
        print("\n⚠️  PROBLEMA DETECTADO:")
        print("   No hay seguimientos de piezas vinculados a cotizaciones con respuesta.")
        print("   Esto explica por qué el gráfico 'Impacto en Conversión' no muestra datos.")
        print("\n💡 SOLUCIÓN:")
        print("   - Asegurar que cada SeguimientoPieza tenga un proveedor asignado")
        print("   - Vincular seguimientos a cotizaciones existentes")
        print("   - Marcar cotizaciones como aceptadas/rechazadas")
    else:
        print(f"\n✅ Datos suficientes para gráfico de impacto en conversión")
        
        # Detallar por proveedor
        print("\n📊 Seguimientos por proveedor con respuesta:")
        for proveedor in proveedores:
            seg_prov = seguimientos_con_respuesta.filter(proveedor=proveedor)
            aceptados = seg_prov.filter(cotizacion__usuario_acepto=True).count()
            rechazados = seg_prov.filter(cotizacion__usuario_acepto=False).count()
            total = seg_prov.count()
            
            if total > 0:
                tasa = (aceptados / total) * 100
                print(f"   {proveedor}: {total} seguimientos | {aceptados} aceptados | {rechazados} rechazados | Tasa: {tasa:.1f}%")
    
    # ========================================================================
    # 5. ANÁLISIS DE PIEZAS CON COMPONENTES
    # ========================================================================
    print("\n🔧 5. ANÁLISIS DE PIEZAS CON COMPONENTES")
    print("-" * 80)
    
    piezas_con_componente = PiezaCotizada.objects.exclude(componente__isnull=True)
    print(f"Piezas con componente asignado: {piezas_con_componente.count()}")
    
    if piezas_con_componente.count() == 0:
        print("\n⚠️  PROBLEMA DETECTADO:")
        print("   No hay piezas con componentes asignados.")
        print("   Esto explica por qué el gráfico 'Especialización por Componente' no muestra datos.")
    else:
        # Listar componentes más usados
        componentes_stats = piezas_con_componente.values('componente__nombre').annotate(
            total=Count('id')
        ).order_by('-total')[:10]
        
        print("\n📊 Top 10 componentes más cotizados:")
        for comp in componentes_stats:
            print(f"   - {comp['componente__nombre']}: {comp['total']} piezas")
    
    # ========================================================================
    # 6. ANÁLISIS CRÍTICO: RELACIÓN SEGUIMIENTOS ↔ PIEZAS ↔ COMPONENTES
    # ========================================================================
    print("\n🔗 6. ANÁLISIS DE VINCULACIÓN: SEGUIMIENTOS → PIEZAS → COMPONENTES")
    print("-" * 80)
    
    # Seguimientos con piezas vinculadas directamente
    seguimientos_con_piezas = SeguimientoPieza.objects.prefetch_related('piezas').annotate(
        num_piezas=Count('piezas')
    ).filter(num_piezas__gt=0)
    
    print(f"Seguimientos con piezas vinculadas directamente: {seguimientos_con_piezas.count()}")
    
    if seguimientos_con_piezas.count() == 0:
        print("\n⚠️  PROBLEMA DETECTADO:")
        print("   Los seguimientos no tienen piezas vinculadas directamente.")
        print("   El código intentará usar piezas de la cotización como fallback.")
        
        # Verificar si al menos tienen cotizaciones con piezas
        seguimientos_con_cot_piezas = SeguimientoPieza.objects.filter(
            cotizacion__piezas_cotizadas__isnull=False
        ).distinct()
        
        print(f"\n🔄 Seguimientos cuya cotización tiene piezas: {seguimientos_con_cot_piezas.count()}")
        
        if seguimientos_con_cot_piezas.count() == 0:
            print("\n❌ PROBLEMA CRÍTICO:")
            print("   Ni seguimientos ni cotizaciones tienen piezas asociadas.")
            print("   No es posible generar el gráfico de componentes.")
        else:
            print("\n✅ Se puede usar fallback: piezas de la cotización")
    else:
        # Analizar piezas vinculadas con componentes
        piezas_vinculadas = PiezaCotizada.objects.filter(
            seguimientos_piezas__isnull=False
        ).exclude(componente__isnull=True)
        
        print(f"Piezas vinculadas a seguimientos CON componente: {piezas_vinculadas.count()}")
        
        if piezas_vinculadas.count() > 0:
            print("\n✅ Datos suficientes para gráfico de especialización por componente")
    
    # ========================================================================
    # 7. DIAGNÓSTICO FINAL Y RECOMENDACIONES
    # ========================================================================
    print("\n" + "="*80)
    print("📋 DIAGNÓSTICO FINAL")
    print("="*80)
    
    # Verificar requisitos para Gráfico 1: Impacto en Conversión
    print("\n1️⃣  Gráfico: IMPACTO EN CONVERSIÓN DE VENTAS")
    requisitos_conversion = {
        'seguimientos_con_proveedor': seguimientos_con_proveedor.count() > 0,
        'cotizaciones_con_respuesta': cotizaciones_con_respuesta > 0,
        'seguimientos_vinculados_a_respuestas': count_seg_respuesta > 0
    }
    
    if all(requisitos_conversion.values()):
        print("   ✅ ESTADO: Datos suficientes")
        print(f"   📊 {count_seg_respuesta} seguimientos con respuesta disponibles")
    else:
        print("   ❌ ESTADO: Datos insuficientes")
        print("   📋 Requisitos faltantes:")
        for req, cumple in requisitos_conversion.items():
            status = "✅" if cumple else "❌"
            print(f"      {status} {req}")
    
    # Verificar requisitos para Gráfico 2: Especialización por Componente
    print("\n2️⃣  Gráfico: ESPECIALIZACIÓN POR COMPONENTE")
    
    # Verificar si hay datos útiles (seguimientos con proveedor y piezas con componente)
    tiene_seguimientos = seguimientos_con_proveedor.count() > 0
    tiene_piezas_componente = piezas_con_componente.count() > 0
    
    # Verificar vinculación (directa o vía cotización)
    tiene_vinculacion = (
        seguimientos_con_piezas.count() > 0 or 
        SeguimientoPieza.objects.filter(cotizacion__piezas_cotizadas__componente__isnull=False).exists()
    )
    
    requisitos_componentes = {
        'seguimientos_con_proveedor': tiene_seguimientos,
        'piezas_con_componente': tiene_piezas_componente,
        'vinculacion_seguimiento_pieza': tiene_vinculacion
    }
    
    if all(requisitos_componentes.values()):
        print("   ✅ ESTADO: Datos suficientes")
        print(f"   📊 {piezas_con_componente.count()} piezas con componente disponibles")
    else:
        print("   ❌ ESTADO: Datos insuficientes")
        print("   📋 Requisitos faltantes:")
        for req, cumple in requisitos_componentes.items():
            status = "✅" if cumple else "❌"
            print(f"      {status} {req}")
    
    # ========================================================================
    # 8. RECOMENDACIONES
    # ========================================================================
    print("\n" + "="*80)
    print("💡 RECOMENDACIONES")
    print("="*80)
    
    if not all(requisitos_conversion.values()):
        print("\n🔧 Para gráfico 'Impacto en Conversión':")
        print("   1. Asegurar que SeguimientoPieza tenga campo 'proveedor' lleno")
        print("   2. Vincular seguimientos a cotizaciones existentes")
        print("   3. Marcar cotizaciones como aceptadas (usuario_acepto=True) o rechazadas (False)")
    
    if not all(requisitos_componentes.values()):
        print("\n🔧 Para gráfico 'Especialización por Componente':")
        print("   1. Asignar componentes (ComponenteEquipo) a todas las PiezaCotizada")
        print("   2. Vincular piezas a seguimientos mediante relación ManyToMany")
        print("   3. Verificar que SeguimientoPieza.piezas tenga elementos")
    
    print("\n" + "="*80)
    print("FIN DEL DIAGNÓSTICO")
    print("="*80 + "\n")


if __name__ == '__main__':
    diagnostico_completo()
