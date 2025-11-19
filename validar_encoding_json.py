# validar_utf8.py
"""
Script para validar que los archivos JSON exportados tienen encoding UTF-8 correcto
"""
import json
import sys
from pathlib import Path

def validar_archivo(ruta_archivo):
    """Valida un archivo JSON para encoding UTF-8 correcto"""
    print(f"\n{'='*60}")
    print(f"Archivo: {ruta_archivo.name}")
    print('='*60)
    
    # Leer bytes crudos
    with open(ruta_archivo, 'rb') as f:
        bytes_contenido = f.read()
    
    # Verificar BOM
    if bytes_contenido[:3] == b'\xef\xbb\xbf':
        print("✓ Encoding: UTF-8 con BOM")
        tiene_bom = True
    else:
        print("✓ Encoding: UTF-8 sin BOM (correcto)")
        tiene_bom = False
    
    # Tamaño
    tamaño_kb = len(bytes_contenido) / 1024
    print(f"✓ Tamaño: {tamaño_kb:.2f} KB")
    
    # Intentar decodificar como UTF-8
    try:
        contenido = bytes_contenido.decode('utf-8')
        print("✓ Decodificación UTF-8: Exitosa")
    except UnicodeDecodeError as e:
        print(f"✗ ERROR: No se puede decodificar como UTF-8: {e}")
        return False
    
    # Buscar caracteres corruptos (double encoding)
    caracteres_corruptos = ['Ã¡', 'Ã©', 'Ã­', 'Ã³', 'Ãº', 'Ã±', 'Â¿', 'Â¡', 'â€']
    corrupcion_encontrada = []
    
    for corrupto in caracteres_corruptos:
        if corrupto in contenido:
            corrupcion_encontrada.append(corrupto)
    
    if corrupcion_encontrada:
        print(f"✗ ADVERTENCIA: Caracteres corruptos detectados: {', '.join(corrupcion_encontrada)}")
        return False
    else:
        print("✓ Sin caracteres corruptos detectados")
    
    # Contar caracteres especiales del español
    caracteres_español = 'áéíóúñÁÉÍÓÚÑ¿¡'
    contador_especiales = sum(1 for c in contenido if c in caracteres_español)
    print(f"✓ Caracteres especiales españoles: {contador_especiales}")
    
    # Validar JSON
    try:
        datos = json.loads(contenido)
        print(f"✓ JSON válido: SÍ")
        if isinstance(datos, list):
            print(f"✓ Número de registros: {len(datos)}")
            
            # Mostrar ejemplos con acentos
            ejemplos_con_acentos = []
            for item in datos[:10]:  # Revisar primeros 10 registros
                if isinstance(item, dict) and 'fields' in item:
                    for key, value in item['fields'].items():
                        if isinstance(value, str) and any(c in value for c in caracteres_español):
                            ejemplos_con_acentos.append(f"{key}: {value[:50]}")
                            if len(ejemplos_con_acentos) >= 3:
                                break
                if len(ejemplos_con_acentos) >= 3:
                    break
            
            if ejemplos_con_acentos:
                print("\n📝 Ejemplos de texto con acentos:")
                for ejemplo in ejemplos_con_acentos:
                    print(f"   {ejemplo}")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"✗ JSON inválido: {e}")
        return False

def main():
    import sys
    
    backup_dir = "backup_sqlite_utf8"
    if len(sys.argv) > 1:
        backup_dir = sys.argv[1]
    
    backup_path = Path(backup_dir)
    
    if not backup_path.exists():
        print(f"❌ ERROR: No existe el directorio '{backup_dir}'")
        sys.exit(1)
    
    print("\n" + "="*60)
    print("  VALIDACIÓN DE ENCODING UTF-8 - ARCHIVOS JSON")
    print("="*60)
    print(f"\n📂 Directorio: {backup_dir}\n")
    
    archivos_json = list(backup_path.glob("*.json"))
    
    if not archivos_json:
        print(f"❌ No se encontraron archivos JSON en {backup_dir}")
        sys.exit(1)
    
    print(f"Total de archivos: {len(archivos_json)}\n")
    
    resultados = {}
    for archivo in sorted(archivos_json):
        resultado = validar_archivo(archivo)
        resultados[archivo.name] = resultado
    
    # Resumen final
    print("\n" + "="*60)
    print("  RESUMEN DE VALIDACIÓN")
    print("="*60)
    
    archivos_validos = sum(1 for v in resultados.values() if v)
    archivos_totales = len(resultados)
    
    print(f"\n📊 Archivos procesados: {archivos_totales}")
    print(f"✓ Archivos válidos: {archivos_validos}")
    
    if archivos_validos == archivos_totales:
        print("\n" + "="*60)
        print("🎉 ¡TODOS LOS ARCHIVOS SON VÁLIDOS!")
        print("="*60)
        print("\n✅ Los archivos están listos para importar en PostgreSQL (Linux)")
        print("✅ Los acentos y caracteres especiales se verán correctamente")
        print("\n📝 Próximos pasos:")
        print(f"   1. Copiar '{backup_dir}' a tu servidor Linux")
        print("   2. Ejecutar: python manage.py migrate")
        print(f"   3. Ejecutar: python manage.py loaddata {backup_dir}/*.json")
    else:
        archivos_problemas = archivos_totales - archivos_validos
        print(f"\n⚠️  ADVERTENCIA: {archivos_problemas} archivo(s) con problemas")
        print("\nArchivos con problemas:")
        for nombre, resultado in resultados.items():
            if not resultado:
                print(f"   ✗ {nombre}")
        print("\n💡 Considera re-exportar los archivos con el script export_data_utf8.ps1")
    
    print()

if __name__ == '__main__':
    main()
