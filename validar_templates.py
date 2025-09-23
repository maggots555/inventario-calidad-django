#!/usr/bin/env python
"""
Script para validar que todos los templates usen los bloques correctos definidos en base.html
"""
import os
import re
from pathlib import Path

# Bloques válidos definidos en base.html
BLOQUES_VALIDOS = {
    'title', 'extra_css', 'sidebar', 'content_class', 'content', 'extra_js'
}

# Bloques comúnmente mal escritos
BLOQUES_INCORRECTOS = {
    'scripts': 'extra_js',
    'script': 'extra_js', 
    'javascript': 'extra_js',
    'js': 'extra_js',
    'styles': 'extra_css',
    'style': 'extra_css',
    'css': 'extra_css'
}

def validar_templates():
    """
    Valida todos los templates HTML del proyecto
    """
    print("🔍 VALIDADOR DE BLOQUES DE TEMPLATES")
    print("=" * 50)
    
    templates_dir = Path('inventario/templates')
    if not templates_dir.exists():
        print("❌ No se encontró el directorio de templates")
        return
    
    errores_encontrados = []
    templates_validados = 0
    
    # Buscar todos los archivos .html
    for template_file in templates_dir.rglob('*.html'):
        templates_validados += 1
        print(f"\n📄 Validando: {template_file}")
        
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Buscar todos los bloques {% block nombre %}
            bloques = re.findall(r'{%\s*block\s+(\w+)\s*%}', content)
            
            for bloque in bloques:
                if bloque in BLOQUES_INCORRECTOS:
                    error = {
                        'archivo': str(template_file),
                        'bloque_incorrecto': bloque,
                        'bloque_correcto': BLOQUES_INCORRECTOS[bloque],
                        'linea': obtener_numero_linea(content, bloque)
                    }
                    errores_encontrados.append(error)
                    print(f"   ❌ Bloque incorrecto: '{bloque}' → debería ser '{BLOQUES_INCORRECTOS[bloque]}'")
                elif bloque not in BLOQUES_VALIDOS:
                    print(f"   ⚠️  Bloque no reconocido: '{bloque}' (puede ser válido si es específico)")
                else:
                    print(f"   ✅ Bloque válido: '{bloque}'")
                    
        except Exception as e:
            print(f"   ❌ Error al leer archivo: {e}")
    
    # Resumen
    print("\n" + "=" * 50)
    print("📊 RESUMEN DE VALIDACIÓN")
    print("=" * 50)
    print(f"Templates validados: {templates_validados}")
    print(f"Errores encontrados: {len(errores_encontrados)}")
    
    if errores_encontrados:
        print("\n🚨 ERRORES ENCONTRADOS:")
        for error in errores_encontrados:
            print(f"  📁 {error['archivo']}")
            print(f"     Línea ~{error['linea']}: '{error['bloque_incorrecto']}' → '{error['bloque_correcto']}'")
    else:
        print("\n🎉 ¡No se encontraron errores! Todos los bloques están correctos.")
    
    return errores_encontrados

def obtener_numero_linea(content, bloque):
    """
    Obtiene el número de línea aproximado donde aparece el bloque
    """
    lines = content.split('\n')
    for i, line in enumerate(lines, 1):
        if f'block {bloque}' in line:
            return i
    return 0

if __name__ == "__main__":
    validar_templates()