# -*- coding: utf-8 -*-
"""
Script: Análisis de Text Mining para Motivos de Rechazo
========================================================

PROPÓSITO:
Analiza los datos reales de la BD para verificar si las keywords
definidas en el modelo coinciden con los textos reales de los rechazos.

EXPLICACIÓN PARA PRINCIPIANTES:
Este script revisa todos los rechazos en la base de datos y compara
el texto que escriben los usuarios con las palabras clave que el modelo
busca. Así podemos mejorar las keywords.
"""

import os
import sys
import django
from pathlib import Path
from collections import Counter, defaultdict
import re

# Configurar Django
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from servicio_tecnico.models import Cotizacion
from servicio_tecnico.ml_advanced.motivo_rechazo_mejorado import PredictorMotivoRechazoMejorado


def normalizar_texto(texto):
    """Normaliza texto igual que el modelo."""
    if not texto:
        return ""
    texto = str(texto).lower()
    texto = re.sub(r'[^a-záéíóúñ0-9\s]', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto


def analizar_keywords_por_motivo():
    """
    Analiza si las keywords definidas coinciden con los textos reales.
    """
    
    print("\n" + "="*80)
    print("ANÁLISIS DE TEXT MINING - MOTIVOS DE RECHAZO")
    print("="*80)
    
    # Obtener cotizaciones rechazadas CON detalle
    cotizaciones = Cotizacion.objects.filter(
        usuario_acepto=False,
        motivo_rechazo__isnull=False
    ).exclude(
        motivo_rechazo=''
    ).values('orden_id', 'motivo_rechazo', 'detalle_rechazo')
    
    print(f"\n📊 Total cotizaciones rechazadas: {len(cotizaciones)}")
    
    # Cargar keywords del modelo
    predictor = PredictorMotivoRechazoMejorado()
    motivos_config = predictor.MOTIVOS
    
    # Análisis por motivo
    resultados = {}
    
    for motivo, config in motivos_config.items():
        print(f"\n{'='*80}")
        print(f"🎯 MOTIVO: {config['nombre']} ({motivo})")
        print(f"   Icono: {config['icono']}")
        print(f"   Descripción: {config['descripcion']}")
        print(f"{'='*80}")
        
        # Keywords definidas
        keywords_definidas = config['keywords']
        print(f"\n📝 Keywords Definidas ({len(keywords_definidas)}):")
        for kw in keywords_definidas:
            print(f"   - '{kw}'")
        
        # Filtrar cotizaciones de este motivo
        cots_motivo = [c for c in cotizaciones if c['motivo_rechazo'] == motivo]
        
        print(f"\n📊 Cotizaciones con este motivo: {len(cots_motivo)}")
        
        if len(cots_motivo) == 0:
            print("   ⚠️ No hay datos para este motivo")
            continue
        
        # Analizar textos reales
        textos_encontrados = []
        keywords_encontradas = Counter()
        keywords_no_encontradas = Counter(keywords_definidas)
        
        for cot in cots_motivo:
            # Usar solo detalle_rechazo (observaciones está en otro modelo)
            texto_completo = ""
            if cot['detalle_rechazo']:
                texto_completo = str(cot['detalle_rechazo'])
            
            texto_normalizado = normalizar_texto(texto_completo)
            
            if texto_normalizado:
                textos_encontrados.append(texto_normalizado)
                
                # Verificar qué keywords aparecen
                for keyword in keywords_definidas:
                    keyword_norm = normalizar_texto(keyword)
                    if keyword_norm in texto_normalizado:
                        keywords_encontradas[keyword] += 1
                        if keyword in keywords_no_encontradas:
                            del keywords_no_encontradas[keyword]
        
        # Estadísticas de coincidencia
        total_con_texto = len([t for t in textos_encontrados if t])
        tasa_keywords = (
            len(keywords_encontradas) / len(keywords_definidas) * 100
            if keywords_definidas else 0
        )
        
        print(f"\n📈 Análisis de Coincidencias:")
        print(f"   Cotizaciones con texto: {total_con_texto}/{len(cots_motivo)}")
        print(f"   Keywords que SÍ aparecen: {len(keywords_encontradas)}/{len(keywords_definidas)} ({tasa_keywords:.1f}%)")
        
        if keywords_encontradas:
            print(f"\n   ✅ Keywords ENCONTRADAS en textos reales:")
            for kw, count in keywords_encontradas.most_common():
                porcentaje = (count / total_con_texto * 100) if total_con_texto > 0 else 0
                print(f"      - '{kw}': {count} veces ({porcentaje:.1f}% de textos)")
        
        if keywords_no_encontradas:
            print(f"\n   ❌ Keywords NO encontradas (posiblemente innecesarias):")
            for kw in keywords_no_encontradas:
                print(f"      - '{kw}'")
        
        # Mostrar ejemplos de textos reales
        print(f"\n📝 Ejemplos de Textos Reales (primeros 5):")
        for i, texto in enumerate(textos_encontrados[:5], 1):
            texto_preview = texto[:100] + "..." if len(texto) > 100 else texto
            print(f"   {i}. {texto_preview}")
        
        # Análisis de palabras frecuentes en textos reales
        todas_palabras = []
        for texto in textos_encontrados:
            palabras = texto.split()
            todas_palabras.extend([p for p in palabras if len(p) > 3])  # Solo palabras > 3 letras
        
        if todas_palabras:
            palabras_frecuentes = Counter(todas_palabras).most_common(10)
            print(f"\n🔤 Top 10 Palabras Más Frecuentes en Textos Reales:")
            for palabra, freq in palabras_frecuentes:
                print(f"   - '{palabra}': {freq} veces")
            
            # Sugerir nuevas keywords
            keywords_actuales_norm = {normalizar_texto(kw) for kw in keywords_definidas}
            palabras_candidatas = [
                (palabra, freq) 
                for palabra, freq in palabras_frecuentes 
                if palabra not in keywords_actuales_norm 
                and len(palabra) > 4  # Palabras más significativas
                and freq >= 3  # Aparece al menos 3 veces
            ]
            
            if palabras_candidatas:
                print(f"\n💡 Sugerencias de Nuevas Keywords (aparecen frecuentemente pero NO están en lista):")
                for palabra, freq in palabras_candidatas[:5]:
                    print(f"   - '{palabra}' (aparece {freq} veces)")
        
        # Guardar resultados
        resultados[motivo] = {
            'total_cotizaciones': len(cots_motivo),
            'con_texto': total_con_texto,
            'keywords_definidas': len(keywords_definidas),
            'keywords_encontradas': len(keywords_encontradas),
            'tasa_coincidencia': tasa_keywords,
            'ejemplos': textos_encontrados[:3]
        }
    
    # Resumen global
    print("\n\n" + "="*80)
    print("📊 RESUMEN GLOBAL")
    print("="*80)
    
    print(f"\n{'Motivo':<30} {'Cots':>6} {'KW Def':>8} {'KW OK':>8} {'Tasa %':>8}")
    print("-" * 80)
    
    for motivo, datos in sorted(resultados.items(), key=lambda x: x[1]['total_cotizaciones'], reverse=True):
        nombre_corto = motivos_config[motivo]['nombre'][:28]
        print(
            f"{nombre_corto:<30} "
            f"{datos['total_cotizaciones']:>6} "
            f"{datos['keywords_definidas']:>8} "
            f"{datos['keywords_encontradas']:>8} "
            f"{datos['tasa_coincidencia']:>7.1f}%"
        )
    
    print("\n" + "="*80)
    print("✅ Análisis completado")
    print("="*80)


if __name__ == '__main__':
    analizar_keywords_por_motivo()
