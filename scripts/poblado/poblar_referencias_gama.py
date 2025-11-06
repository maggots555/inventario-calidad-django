"""
Script para poblar referencias de gama de equipos

PROPÓSITO:
Este script crea referencias iniciales en la base de datos para clasificar
automáticamente los equipos en gama alta, media o baja.

EXPLICACIÓN PARA PRINCIPIANTES:
Este script se ejecuta UNA VEZ para llenar la tabla de referencias.
Después, cada vez que crees una orden con marca y modelo, el sistema
automáticamente buscará en esta tabla para asignar la gama correcta.

CÓMO EJECUTAR:
python manage.py shell < scripts/poblado/poblar_referencias_gama.py

O desde Django shell:
python manage.py shell
>>> exec(open('scripts/poblado/poblar_referencias_gama.py').read())
"""

import os
import sys
import django

# Configurar Django
if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, BASE_DIR)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

from servicio_tecnico.models import ReferenciaGamaEquipo

# =============================================================================
# DATOS DE REFERENCIAS DE GAMA
# =============================================================================

REFERENCIAS = [
    # GAMA ALTA - Equipos premium ($25,000 - $60,000+)
    {
        'marca': 'Apple',
        'modelo_base': 'MacBook Pro',
        'gama': 'alta',
        'rango_costo_min': 35000.00,
        'rango_costo_max': 65000.00,
    },
    {
        'marca': 'Apple',
        'modelo_base': 'MacBook Air M',
        'gama': 'alta',
        'rango_costo_min': 28000.00,
        'rango_costo_max': 45000.00,
    },
    {
        'marca': 'Dell',
        'modelo_base': 'XPS',
        'gama': 'alta',
        'rango_costo_min': 30000.00,
        'rango_costo_max': 55000.00,
    },
    {
        'marca': 'Dell',
        'modelo_base': 'Alienware',
        'gama': 'alta',
        'rango_costo_min': 40000.00,
        'rango_costo_max': 70000.00,
    },
    {
        'marca': 'HP',
        'modelo_base': 'Spectre',
        'gama': 'alta',
        'rango_costo_min': 32000.00,
        'rango_costo_max': 50000.00,
    },
    {
        'marca': 'HP',
        'modelo_base': 'Omen',
        'gama': 'alta',
        'rango_costo_min': 28000.00,
        'rango_costo_max': 55000.00,
    },
    {
        'marca': 'Lenovo',
        'modelo_base': 'ThinkPad X1',
        'gama': 'alta',
        'rango_costo_min': 30000.00,
        'rango_costo_max': 50000.00,
    },
    {
        'marca': 'Lenovo',
        'modelo_base': 'Legion',
        'gama': 'alta',
        'rango_costo_min': 25000.00,
        'rango_costo_max': 50000.00,
    },
    {
        'marca': 'Asus',
        'modelo_base': 'ROG',
        'gama': 'alta',
        'rango_costo_min': 25000.00,
        'rango_costo_max': 60000.00,
    },
    {
        'marca': 'Asus',
        'modelo_base': 'ZenBook',
        'gama': 'alta',
        'rango_costo_min': 22000.00,
        'rango_costo_max': 40000.00,
    },
    {
        'marca': 'MSI',
        'modelo_base': 'Prestige',
        'gama': 'alta',
        'rango_costo_min': 28000.00,
        'rango_costo_max': 50000.00,
    },
    {
        'marca': 'MSI',
        'modelo_base': 'Creator',
        'gama': 'alta',
        'rango_costo_min': 30000.00,
        'rango_costo_max': 55000.00,
    },
    {
        'marca': 'Huawei',
        'modelo_base': 'MateBook X',
        'gama': 'alta',
        'rango_costo_min': 25000.00,
        'rango_costo_max': 40000.00,
    },
    
    # GAMA MEDIA - Equipos intermedios ($12,000 - $25,000)
    {
        'marca': 'Dell',
        'modelo_base': 'Latitude',
        'gama': 'media',
        'rango_costo_min': 15000.00,
        'rango_costo_max': 28000.00,
    },
    {
        'marca': 'Dell',
        'modelo_base': 'Vostro',
        'gama': 'media',
        'rango_costo_min': 12000.00,
        'rango_costo_max': 22000.00,
    },
    {
        'marca': 'HP',
        'modelo_base': 'ProBook',
        'gama': 'media',
        'rango_costo_min': 13000.00,
        'rango_costo_max': 25000.00,
    },
    {
        'marca': 'HP',
        'modelo_base': 'EliteBook',
        'gama': 'media',
        'rango_costo_min': 18000.00,
        'rango_costo_max': 32000.00,
    },
    {
        'marca': 'HP',
        'modelo_base': 'Pavilion',
        'gama': 'media',
        'rango_costo_min': 11000.00,
        'rango_costo_max': 20000.00,
    },
    {
        'marca': 'Lenovo',
        'modelo_base': 'ThinkPad E',
        'gama': 'media',
        'rango_costo_min': 12000.00,
        'rango_costo_max': 22000.00,
    },
    {
        'marca': 'Lenovo',
        'modelo_base': 'ThinkPad L',
        'gama': 'media',
        'rango_costo_min': 14000.00,
        'rango_costo_max': 25000.00,
    },
    {
        'marca': 'Lenovo',
        'modelo_base': 'IdeaPad',
        'gama': 'media',
        'rango_costo_min': 10000.00,
        'rango_costo_max': 18000.00,
    },
    {
        'marca': 'Acer',
        'modelo_base': 'Aspire',
        'gama': 'media',
        'rango_costo_min': 9000.00,
        'rango_costo_max': 17000.00,
    },
    {
        'marca': 'Acer',
        'modelo_base': 'Swift',
        'gama': 'media',
        'rango_costo_min': 13000.00,
        'rango_costo_max': 22000.00,
    },
    {
        'marca': 'Asus',
        'modelo_base': 'VivoBook',
        'gama': 'media',
        'rango_costo_min': 10000.00,
        'rango_costo_max': 18000.00,
    },
    {
        'marca': 'Asus',
        'modelo_base': 'TUF',
        'gama': 'media',
        'rango_costo_min': 15000.00,
        'rango_costo_max': 28000.00,
    },
    {
        'marca': 'Samsung',
        'modelo_base': 'Galaxy Book',
        'gama': 'media',
        'rango_costo_min': 14000.00,
        'rango_costo_max': 25000.00,
    },
    {
        'marca': 'Huawei',
        'modelo_base': 'MateBook D',
        'gama': 'media',
        'rango_costo_min': 12000.00,
        'rango_costo_max': 20000.00,
    },
    {
        'marca': 'MSI',
        'modelo_base': 'Modern',
        'gama': 'media',
        'rango_costo_min': 14000.00,
        'rango_costo_max': 25000.00,
    },
    
    # GAMA BAJA - Equipos básicos ($5,000 - $12,000)
    {
        'marca': 'Dell',
        'modelo_base': 'Inspiron',
        'gama': 'baja',
        'rango_costo_min': 6000.00,
        'rango_costo_max': 13000.00,
    },
    {
        'marca': 'HP',
        'modelo_base': '14',
        'gama': 'baja',
        'rango_costo_min': 5500.00,
        'rango_costo_max': 10000.00,
    },
    {
        'marca': 'HP',
        'modelo_base': '15',
        'gama': 'baja',
        'rango_costo_min': 5500.00,
        'rango_costo_max': 11000.00,
    },
    {
        'marca': 'HP',
        'modelo_base': '240',
        'gama': 'baja',
        'rango_costo_min': 5000.00,
        'rango_costo_max': 9000.00,
    },
    {
        'marca': 'Lenovo',
        'modelo_base': 'V14',
        'gama': 'baja',
        'rango_costo_min': 5500.00,
        'rango_costo_max': 10000.00,
    },
    {
        'marca': 'Lenovo',
        'modelo_base': 'V15',
        'gama': 'baja',
        'rango_costo_min': 5500.00,
        'rango_costo_max': 11000.00,
    },
    {
        'marca': 'Acer',
        'modelo_base': 'Extensa',
        'gama': 'baja',
        'rango_costo_min': 5000.00,
        'rango_costo_max': 9500.00,
    },
    {
        'marca': 'Acer',
        'modelo_base': 'TravelMate',
        'gama': 'baja',
        'rango_costo_min': 6000.00,
        'rango_costo_max': 11000.00,
    },
    {
        'marca': 'Asus',
        'modelo_base': 'X',
        'gama': 'baja',
        'rango_costo_min': 5500.00,
        'rango_costo_max': 10000.00,
    },
    {
        'marca': 'Toshiba',
        'modelo_base': 'Satellite',
        'gama': 'baja',
        'rango_costo_min': 5000.00,
        'rango_costo_max': 10000.00,
    },
    {
        'marca': 'Compaq',
        'modelo_base': 'Presario',
        'gama': 'baja',
        'rango_costo_min': 5000.00,
        'rango_costo_max': 9000.00,
    },
    {
        'marca': 'Gateway',
        'modelo_base': 'NE',
        'gama': 'baja',
        'rango_costo_min': 5000.00,
        'rango_costo_max': 9000.00,
    },
]

# =============================================================================
# FUNCIÓN PRINCIPAL
# =============================================================================

def poblar_referencias():
    """Crea todas las referencias de gama en la base de datos"""
    print("\n" + "="*80)
    print(" POBLANDO REFERENCIAS DE GAMA DE EQUIPOS ".center(80, "="))
    print("="*80 + "\n")
    
    creadas = 0
    actualizadas = 0
    errores = 0
    
    for datos in REFERENCIAS:
        try:
            # Usar get_or_create para evitar duplicados
            referencia, creado = ReferenciaGamaEquipo.objects.get_or_create(
                marca=datos['marca'],
                modelo_base=datos['modelo_base'],
                defaults={
                    'gama': datos['gama'],
                    'rango_costo_min': datos['rango_costo_min'],
                    'rango_costo_max': datos['rango_costo_max'],
                    'activo': True,
                }
            )
            
            if creado:
                creadas += 1
                print(f"✅ Creada: {referencia.marca:15} {referencia.modelo_base:20} → {referencia.get_gama_display()}")
            else:
                # Si ya existe, actualizar los valores
                referencia.gama = datos['gama']
                referencia.rango_costo_min = datos['rango_costo_min']
                referencia.rango_costo_max = datos['rango_costo_max']
                referencia.activo = True
                referencia.save()
                actualizadas += 1
                print(f"🔄 Actualizada: {referencia.marca:15} {referencia.modelo_base:20} → {referencia.get_gama_display()}")
        
        except Exception as e:
            errores += 1
            print(f"❌ Error: {datos['marca']} {datos['modelo_base']} - {str(e)}")
    
    # Resumen
    print("\n" + "="*80)
    print(" RESUMEN ".center(80, "="))
    print("="*80)
    print(f"  Referencias creadas:      {creadas}")
    print(f"  Referencias actualizadas: {actualizadas}")
    print(f"  Errores:                  {errores}")
    print(f"  Total procesadas:         {len(REFERENCIAS)}")
    print("="*80 + "\n")
    
    if errores == 0:
        print("✅ ¡Todas las referencias fueron procesadas correctamente!")
    else:
        print(f"⚠️  Se encontraron {errores} errores durante el proceso")
    
    # Mostrar estadísticas por gama
    print("\n📊 ESTADÍSTICAS POR GAMA:")
    for gama_codigo, gama_nombre in [('alta', 'Gama Alta'), ('media', 'Gama Media'), ('baja', 'Gama Baja')]:
        count = ReferenciaGamaEquipo.objects.filter(gama=gama_codigo, activo=True).count()
        print(f"  {gama_nombre:12}: {count:3} referencias")
    
    total = ReferenciaGamaEquipo.objects.filter(activo=True).count()
    print(f"  {'Total':12}: {total:3} referencias activas\n")

# =============================================================================
# EJECUTAR
# =============================================================================

if __name__ == "__main__":
    try:
        poblar_referencias()
        print("✅ Script completado exitosamente\n")
    except Exception as e:
        print(f"\n❌ Error crítico: {str(e)}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
