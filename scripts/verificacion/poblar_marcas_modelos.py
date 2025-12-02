"""
Script para poblar la tabla ReferenciaGamaEquipo
Generado automáticamente desde la base de datos existente

Este script:
1. Extrae marcas y modelos únicos de las órdenes existentes
2. Clasifica automáticamente la gama (alta/media/baja)
3. Asigna rangos de costo aproximados
4. Puebla la tabla ReferenciaGamaEquipo

Uso:
    python scripts/verificacion/poblar_marcas_modelos.py
"""

import os
import sys
import django
from decimal import Decimal

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from servicio_tecnico.models import ReferenciaGamaEquipo


def poblar_referencias_gama():
    """
    Puebla la tabla ReferenciaGamaEquipo con datos extraídos.
    """
    print("=" * 80)
    print("POBLANDO ReferenciaGamaEquipo")
    print("=" * 80)
    print()
    
    creados = 0
    existentes = 0
    actualizados = 0
    
    # ========================================
    # Marca: Acer (2 modelos)
    # ========================================
    
    # Aspire A515-45 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Acer',
        modelo_base='Aspire A515-45',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Acer - Aspire A515-45 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # PREDATOR HELIOS 3000 SERIES (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Acer',
        modelo_base='PREDATOR HELIOS 3000 SERIES',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Acer - PREDATOR HELIOS 3000 SERIES ({obj.get_gama_display()})')
    else:
        existentes += 1

    # ========================================
    # Marca: Apple (1 modelos)
    # ========================================
    
    # MacBook Pro 13-inch (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Apple',
        modelo_base='MacBook Pro 13-inch',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Apple - MacBook Pro 13-inch ({obj.get_gama_display()})')
    else:
        existentes += 1

    # ========================================
    # Marca: Asus (6 modelos)
    # ========================================
    
    # G512LI (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Asus',
        modelo_base='G512LI',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Asus - G512LI ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # REPUBLIC GZ301Z (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Asus',
        modelo_base='REPUBLIC GZ301Z',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Asus - REPUBLIC GZ301Z ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # VIVOBOOK 16 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Asus',
        modelo_base='VIVOBOOK 16',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Asus - VIVOBOOK 16 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # X1404ZA-NK100W (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Asus',
        modelo_base='X1404ZA-NK100W',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Asus - X1404ZA-NK100W ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # X1502Z (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Asus',
        modelo_base='X1502Z',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Asus - X1502Z ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # X512J (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Asus',
        modelo_base='X512J',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Asus - X512J ({obj.get_gama_display()})')
    else:
        existentes += 1

    # ========================================
    # Marca: Dell (140 modelos)
    # ========================================
    
    # ALIENWARE (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='ALIENWARE',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - ALIENWARE ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # ALIENWARE 17 R4 (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='ALIENWARE 17 R4',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - ALIENWARE 17 R4 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # ALIENWARE M 16 R2 (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='ALIENWARE M 16 R2',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - ALIENWARE M 16 R2 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Alienware (usado 3 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Alienware',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Alienware ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Alienware 17 R4 (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Alienware 17 R4',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Alienware 17 R4 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Alienware 17 r5 (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Alienware 17 r5',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Alienware 17 r5 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Alienware 18 Area-51 (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Alienware 18 Area-51',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Alienware 18 Area-51 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Alienware Area-51m (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Alienware Area-51m',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Alienware Area-51m ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Alienware Aurora R16 (usado 3 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Alienware Aurora R16',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Alienware Aurora R16 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Alienware Aurora R7 (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Alienware Aurora R7',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Alienware Aurora R7 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Alienware Aurora r16 (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Alienware Aurora r16',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Alienware Aurora r16 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Alienware M15 R7 (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Alienware M15 R7',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Alienware M15 R7 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Alienware m15 R6 (usado 2 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Alienware m15 R6',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Alienware m15 R6 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Alienware m15 R7 (usado 3 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Alienware m15 R7',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Alienware m15 R7 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Alienware m15 R7 AMD (usado 2 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Alienware m15 R7 AMD',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Alienware m15 R7 AMD ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Alienware x17 R2 (usado 2 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Alienware x17 R2',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Alienware x17 R2 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # De 15 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='De 15',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - De 15 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Dell 15 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Dell 15',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Dell 15 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Dell G15 5511 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Dell G15 5511',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Dell G15 5511 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Dell G15 5530 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Dell G15 5530',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Dell G15 5530 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Dell G3 15 3590 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Dell G3 15 3590',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Dell G3 15 3590 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Dell G3 3779 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Dell G3 3779',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Dell G3 3779 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Dell G5 15 5500 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Dell G5 15 5500',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Dell G5 15 5500 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Dell Pro (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Dell Pro',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Dell Pro ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # G15 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='G15',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - G15 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # G15 5510 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='G15 5510',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - G15 5510 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # G15 5511 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='G15 5511',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - G15 5511 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # G15 5515 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='G15 5515',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - G15 5515 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # G15 5515 Ryzen Edition (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='G15 5515 Ryzen Edition',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - G15 5515 Ryzen Edition ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # G15 5520 (usado 5 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='G15 5520',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - G15 5520 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # G15 5525 (usado 4 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='G15 5525',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - G15 5525 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # G15 5530 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='G15 5530',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - G15 5530 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # G3 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='G3',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - G3 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # G3 15 3590 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='G3 15 3590',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - G3 15 3590 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # G5 15 5500 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='G5 15 5500',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - G5 15 5500 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # G5 15 5590 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='G5 15 5590',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - G5 15 5590 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # G7 15 7588 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='G7 15 7588',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - G7 15 7588 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # G7 17 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='G7 17',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - G7 17 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # G7 17 7700 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='G7 17 7700',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - G7 17 7700 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # INSPIRON 15 3520 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='INSPIRON 15 3520',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - INSPIRON 15 3520 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # INSPIRON 5348 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='INSPIRON 5348',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - INSPIRON 5348 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron (usado 22 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 13 5310 (usado 4 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 13 5310',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 13 5310 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 13 5378 2-1 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 13 5378 2-1',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 13 5378 2-1 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 13 5378 2-in-1 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 13 5378 2-in-1',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 13 5378 2-in-1 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 14 5410 2-in-1 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 14 5410 2-in-1',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 14 5410 2-in-1 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 14 5440 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 14 5440',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 14 5440 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 14 7420 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 14 7420',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 14 7420 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 14 7420 2-in-1 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 14 7420 2-in-1',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 14 7420 2-in-1 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 14 7425 2-in-1 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 14 7425 2-in-1',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 14 7425 2-in-1 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 14 7430 2-in-1 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 14 7430 2-in-1',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 14 7430 2-in-1 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 14 7460 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 14 7460',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 14 7460 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 15 3511 (usado 13 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 15 3511',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 15 3511 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 15 3515 (usado 7 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 15 3515',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 15 3515 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 15 3520 (usado 14 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 15 3520',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 15 3520 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 15 3525 (usado 3 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 15 3525',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 15 3525 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 15 3535 (usado 3 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 15 3535',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 15 3535 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 15 5510/5518 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 15 5510/5518',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 15 5510/5518 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 15 5567 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 15 5567',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 15 5567 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 15 5579 2-in-1 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 15 5579 2-in-1',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 15 5579 2-in-1 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 15 5584 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 15 5584',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 15 5584 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 15 Gaming 7566 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 15 Gaming 7566',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 15 Gaming 7566 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 16 5620 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 16 5620',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 16 5620 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 16 5640 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 16 5640',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 16 5640 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 24 5410 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 24 5410',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 24 5410 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 24 5415 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 24 5415',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 24 5415 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 24 5430 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 24 5430',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 24 5430 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 3501 (usado 6 veces) - Gama: baja
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 3501',
        defaults={
            'gama': 'baja',
            'rango_costo_min': Decimal('250'),
            'rango_costo_max': Decimal('600'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 3501 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 3505 (usado 2 veces) - Gama: baja
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 3505',
        defaults={
            'gama': 'baja',
            'rango_costo_min': Decimal('250'),
            'rango_costo_max': Decimal('600'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 3505 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 3585 (usado 1 veces) - Gama: baja
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 3585',
        defaults={
            'gama': 'baja',
            'rango_costo_min': Decimal('250'),
            'rango_costo_max': Decimal('600'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 3585 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 5400 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 5400',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 5400 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 5400 AIO (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 5400 AIO',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 5400 AIO ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 5406 2-in-1 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 5406 2-in-1',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 5406 2-in-1 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 5447 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 5447',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 5447 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 5502/5509 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 5502/5509',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 5502/5509 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 5559 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 5559',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 5559 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 5570 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 5570',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 5570 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 5593 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 5593',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 5593 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 7380 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 7380',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 7380 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 7490 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 7490',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 7490 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 7537 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 7537',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 7537 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 7568 2-1 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 7568 2-1',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 7568 2-1 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 7586 2-in-1 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 7586 2-in-1',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 7586 2-in-1 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 7700 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 7700',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 7700 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Inspiron 7706 2-in-1 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Inspiron 7706 2-in-1',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Inspiron 7706 2-in-1 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Latitude (usado 8 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Latitude',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Latitude ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Latitude 3320 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Latitude 3320',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Latitude 3320 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Latitude 3410 (usado 5 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Latitude 3410',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Latitude 3410 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Latitude 3420 (usado 7 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Latitude 3420',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Latitude 3420 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Latitude 3440 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Latitude 3440',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Latitude 3440 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Latitude 3520 (usado 9 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Latitude 3520',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Latitude 3520 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Latitude 3540 (usado 3 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Latitude 3540',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Latitude 3540 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Latitude 3550 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Latitude 3550',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Latitude 3550 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Latitude 5340 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Latitude 5340',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Latitude 5340 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Latitude 5400 (usado 3 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Latitude 5400',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Latitude 5400 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Latitude 5410 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Latitude 5410',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Latitude 5410 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Latitude 5420 (usado 4 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Latitude 5420',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Latitude 5420 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Latitude 5430 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Latitude 5430',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Latitude 5430 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Latitude 5440 (usado 4 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Latitude 5440',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Latitude 5440 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Latitude 5480/5488 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Latitude 5480/5488',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Latitude 5480/5488 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Latitude 5511 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Latitude 5511',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Latitude 5511 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Latitude 5540 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Latitude 5540',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Latitude 5540 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Latitude 7200 2-in-1 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Latitude 7200 2-in-1',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Latitude 7200 2-in-1 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Latitude 7320 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Latitude 7320',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Latitude 7320 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Latitude 7330 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Latitude 7330',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Latitude 7330 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Latitude 7430 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Latitude 7430',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Latitude 7430 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Latitude 7480 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Latitude 7480',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Latitude 7480 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Latitude 7490 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Latitude 7490',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Latitude 7490 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Latitude E7470 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Latitude E7470',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Latitude E7470 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Latitudes 7300 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Latitudes 7300',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Latitudes 7300 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # OptiPlex 3070 Small Form Factor (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='OptiPlex 3070 Small Form Factor',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - OptiPlex 3070 Small Form Factor ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # OptiPlex 3080 Micro (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='OptiPlex 3080 Micro',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - OptiPlex 3080 Micro ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # OptiPlex 7410 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='OptiPlex 7410',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - OptiPlex 7410 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # OptiPlex Small Form Factor 7020 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='OptiPlex Small Form Factor 7020',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - OptiPlex Small Form Factor 7020 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Optilplex (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Optilplex',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Optilplex ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Optiplex small form factor plus 701 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Optiplex small form factor plus 701',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Optiplex small form factor plus 701 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Precision (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Precision',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Precision ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Precision 3561 (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Precision 3561',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Precision 3561 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Precision 3571 (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Precision 3571',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Precision 3571 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Precision 5570 (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Precision 5570',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Precision 5570 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Precision 5820 Tower (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Precision 5820 Tower',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Precision 5820 Tower ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Precision 7710 (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Precision 7710',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Precision 7710 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Precision 7740 (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Precision 7740',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Precision 7740 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Precisión 7740 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Precisión 7740',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Precisión 7740 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Pro 14 PC14250 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Pro 14 PC14250',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Pro 14 PC14250 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # VOSTRO 3401 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='VOSTRO 3401',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - VOSTRO 3401 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Vostro 14 5410 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Vostro 14 5410',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Vostro 14 5410 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Vostro 15 3510 (usado 3 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Vostro 15 3510',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Vostro 15 3510 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Vostro 15 3530 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Vostro 15 3530',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Vostro 15 3530 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Vostro 3400 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Vostro 3400',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Vostro 3400 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Vostro 3405 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='Vostro 3405',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - Vostro 3405 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # XPS 12 9Q23 (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='XPS 12 9Q23',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - XPS 12 9Q23 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # XPS 13 9340 (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='XPS 13 9340',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - XPS 13 9340 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # XPS 13 9343 (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='XPS 13 9343',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - XPS 13 9343 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # XPS 13 9350 (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='XPS 13 9350',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - XPS 13 9350 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # XPS 13 9360 (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='XPS 13 9360',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - XPS 13 9360 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # XPS 13 Plus 9320 (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='XPS 13 Plus 9320',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - XPS 13 Plus 9320 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # XPS 15 9560 (usado 2 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='XPS 15 9560',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - XPS 15 9560 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # inspiron (usado 3 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='inspiron',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - inspiron ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # inspiron 5570 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Dell',
        modelo_base='inspiron 5570',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Dell - inspiron 5570 ({obj.get_gama_display()})')
    else:
        existentes += 1

    # ========================================
    # Marca: HP (13 modelos)
    # ========================================
    
    # 15-DB0004LA (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='HP',
        modelo_base='15-DB0004LA',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: HP - 15-DB0004LA ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # 15-EF2500LA (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='HP',
        modelo_base='15-EF2500LA',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: HP - 15-EF2500LA ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # 240 G8 (usado 1 veces) - Gama: baja
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='HP',
        modelo_base='240 G8',
        defaults={
            'gama': 'baja',
            'rango_costo_min': Decimal('250'),
            'rango_costo_max': Decimal('600'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: HP - 240 G8 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # ELITEDESK 800 G1 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='HP',
        modelo_base='ELITEDESK 800 G1',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: HP - ELITEDESK 800 G1 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # ENVY Recline (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='HP',
        modelo_base='ENVY Recline',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: HP - ENVY Recline ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # ENVY X360 2-IN-1 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='HP',
        modelo_base='ENVY X360 2-IN-1',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: HP - ENVY X360 2-IN-1 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # HP ELITEBOOK 840 C6 (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='HP',
        modelo_base='HP ELITEBOOK 840 C6',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: HP - HP ELITEBOOK 840 C6 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # HP PAVILON MODEL 13 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='HP',
        modelo_base='HP PAVILON MODEL 13',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: HP - HP PAVILON MODEL 13 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # HP Pavilion - 15 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='HP',
        modelo_base='HP Pavilion - 15',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: HP - HP Pavilion - 15 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Pavilion - 15-cw1012la (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='HP',
        modelo_base='Pavilion - 15-cw1012la',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: HP - Pavilion - 15-cw1012la ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Pavillion (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='HP',
        modelo_base='Pavillion',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: HP - Pavillion ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # ProBook 440 G6 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='HP',
        modelo_base='ProBook 440 G6',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: HP - ProBook 440 G6 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # ProBook 440 g6 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='HP',
        modelo_base='ProBook 440 g6',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: HP - ProBook 440 g6 ({obj.get_gama_display()})')
    else:
        existentes += 1

    # ========================================
    # Marca: Lenovo (117 modelos)
    # ========================================
    
    # 24irh9 i31315u512g 512g 8 g (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='24irh9 i31315u512g 512g 8 g',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - 24irh9 i31315u512g 512g 8 g ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # 320-15IKB (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='320-15IKB',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - 320-15IKB ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # 320-15IKB IdeaPad (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='320-15IKB IdeaPad',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - 320-15IKB IdeaPad ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # 330-15AST ideapad (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='330-15AST ideapad',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - 330-15AST ideapad ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # 330S-14IKB IdeaPad (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='330S-14IKB IdeaPad',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - 330S-14IKB IdeaPad ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # 330S-15IKB IdeaPad (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='330S-15IKB IdeaPad',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - 330S-15IKB IdeaPad ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # 500-15ACZ IdeaPad (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='500-15ACZ IdeaPad',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - 500-15ACZ IdeaPad ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # 520S-14IKB (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='520S-14IKB',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - 520S-14IKB ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # 520S-14IKB ideapad (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='520S-14IKB ideapad',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - 520S-14IKB ideapad ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # 530S-14IKB (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='530S-14IKB',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - 530S-14IKB ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # 530S-14IKB IdeaPad (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='530S-14IKB IdeaPad',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - 530S-14IKB IdeaPad ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # 530S-14IKB Laptop (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='530S-14IKB Laptop',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - 530S-14IKB Laptop ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # A540-24API ideacentre (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='A540-24API ideacentre',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - A540-24API ideacentre ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # AIO 330-20AST IdeaCenter (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='AIO 330-20AST IdeaCenter',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - AIO 330-20AST IdeaCenter ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # AIO 520-22AST IdeaCenter (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='AIO 520-22AST IdeaCenter',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - AIO 520-22AST IdeaCenter ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Aio (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Aio',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Aio ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Alienware m15 R7 (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Alienware m15 R7',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Alienware m15 R7 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # E14 Gen 2 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='E14 Gen 2',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - E14 Gen 2 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # E15 Gen 2 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='E15 Gen 2',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - E15 Gen 2 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # E15 Gen 3 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='E15 Gen 3',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - E15 Gen 3 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Flex 5-14 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Flex 5-14',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Flex 5-14 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # G480 - Type 2688 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='G480 - Type 2688',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - G480 - Type 2688 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # IDEAPAD 300-14ISK (usado 1 veces) - Gama: baja
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='IDEAPAD 300-14ISK',
        defaults={
            'gama': 'baja',
            'rango_costo_min': Decimal('250'),
            'rango_costo_max': Decimal('600'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - IDEAPAD 300-14ISK ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # INSPIRON 24 5415 ALL-IN-ONE (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='INSPIRON 24 5415 ALL-IN-ONE',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - INSPIRON 24 5415 ALL-IN-ONE ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # IP 3 14ITL6 4G 4G 1T 256G 11S (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='IP 3 14ITL6 4G 4G 1T 256G 11S',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - IP 3 14ITL6 4G 4G 1T 256G 11S ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # IP 3 15ALC6R7 8G 512G 11S (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='IP 3 15ALC6R7 8G 512G 11S',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - IP 3 15ALC6R7 8G 512G 11S ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # IP SLIM 3 15IAN8 N100 8G 256G 11S (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='IP SLIM 3 15IAN8 N100 8G 256G 11S',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - IP SLIM 3 15IAN8 N100 8G 256G 11S ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # IPFLEX 5 14ABR8 R5 512G 11S (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='IPFLEX 5 14ABR8 R5 512G 11S',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - IPFLEX 5 14ABR8 R5 512G 11S ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # IdeaCentre 3 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='IdeaCentre 3',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - IdeaCentre 3 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # IdeaCentre AIO 3 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='IdeaCentre AIO 3',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - IdeaCentre AIO 3 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # IdeaCentre AIO 3-24ITL6 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='IdeaCentre AIO 3-24ITL6',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - IdeaCentre AIO 3-24ITL6 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # IdeaPad 1 (usado 2 veces) - Gama: baja
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='IdeaPad 1',
        defaults={
            'gama': 'baja',
            'rango_costo_min': Decimal('250'),
            'rango_costo_max': Decimal('600'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - IdeaPad 1 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # IdeaPad 1 15AMN7 (usado 1 veces) - Gama: baja
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='IdeaPad 1 15AMN7',
        defaults={
            'gama': 'baja',
            'rango_costo_min': Decimal('250'),
            'rango_costo_max': Decimal('600'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - IdeaPad 1 15AMN7 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # IdeaPad 1- 15IAU7 (usado 1 veces) - Gama: baja
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='IdeaPad 1- 15IAU7',
        defaults={
            'gama': 'baja',
            'rango_costo_min': Decimal('250'),
            'rango_costo_max': Decimal('600'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - IdeaPad 1- 15IAU7 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # IdeaPad 3 (usado 8 veces) - Gama: baja
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='IdeaPad 3',
        defaults={
            'gama': 'baja',
            'rango_costo_min': Decimal('250'),
            'rango_costo_max': Decimal('600'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - IdeaPad 3 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # IdeaPad 3305 (usado 1 veces) - Gama: baja
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='IdeaPad 3305',
        defaults={
            'gama': 'baja',
            'rango_costo_min': Decimal('250'),
            'rango_costo_max': Decimal('600'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - IdeaPad 3305 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # IdeaPad 5 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='IdeaPad 5',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - IdeaPad 5 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # IdeaPad 5 Pro (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='IdeaPad 5 Pro',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - IdeaPad 5 Pro ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # IdeaPad 5-14ITL05 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='IdeaPad 5-14ITL05',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - IdeaPad 5-14ITL05 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # IdeaPad Gaming 3 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='IdeaPad Gaming 3',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - IdeaPad Gaming 3 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # IdeaPad S145 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='IdeaPad S145',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - IdeaPad S145 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # IdeaPad Slim 3 (usado 8 veces) - Gama: baja
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='IdeaPad Slim 3',
        defaults={
            'gama': 'baja',
            'rango_costo_min': Decimal('250'),
            'rango_costo_max': Decimal('600'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - IdeaPad Slim 3 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # IdeaPad Slim 5 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='IdeaPad Slim 5',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - IdeaPad Slim 5 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # IdeaPad Slim 5 14IAH8 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='IdeaPad Slim 5 14IAH8',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - IdeaPad Slim 5 14IAH8 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Ideapad (usado 7 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Ideapad',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Ideapad ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Ideapad 3 (usado 3 veces) - Gama: baja
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Ideapad 3',
        defaults={
            'gama': 'baja',
            'rango_costo_min': Decimal('250'),
            'rango_costo_max': Decimal('600'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Ideapad 3 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Ideapad 5 (usado 3 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Ideapad 5',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Ideapad 5 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Ideapad 5-15ITL05 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Ideapad 5-15ITL05',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Ideapad 5-15ITL05 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # L15 Gen 3 ThinkPad (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='L15 Gen 3 ThinkPad',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - L15 Gen 3 ThinkPad ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # L15 Gen 4 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='L15 Gen 4',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - L15 Gen 4 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # LN LEGION GO S 8ARP1Z2_GO16G 512G 11S (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='LN LEGION GO S 8ARP1Z2_GO16G 512G 11S',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - LN LEGION GO S 8ARP1Z2_GO16G 512G 11S ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # LN V14 G3 IAP 15 8G 256G 11P (usado 1 veces) - Gama: baja
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='LN V14 G3 IAP 15 8G 256G 11P',
        defaults={
            'gama': 'baja',
            'rango_costo_min': Decimal('250'),
            'rango_costo_max': Decimal('600'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - LN V14 G3 IAP 15 8G 256G 11P ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # LOQ 15IAX9 15 16G 512G 11S (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='LOQ 15IAX9 15 16G 512G 11S',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - LOQ 15IAX9 15 16G 512G 11S ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Latitude 7420 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Latitude 7420',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Latitude 7420 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Legion (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Legion',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Legion ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Legion 5 (usado 6 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Legion 5',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Legion 5 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Legion 5 Pro (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Legion 5 Pro',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Legion 5 Pro ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Legion 5 Pro 16IAH7H (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Legion 5 Pro 16IAH7H',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Legion 5 Pro 16IAH7H ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Legion 5-15IMH05H (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Legion 5-15IMH05H',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Legion 5-15IMH05H ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Legion Go (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Legion Go',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Legion Go ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Legion Pro 7 (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Legion Pro 7',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Legion Pro 7 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Legion S7 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Legion S7',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Legion S7 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Legion Y40 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Legion Y40',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Legion Y40 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Legion Y520 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Legion Y520',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Legion Y520 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Legion Y540-15IRH (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Legion Y540-15IRH',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Legion Y540-15IRH ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Legion Y740 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Legion Y740',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Legion Y740 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Legion Y740-15IRHg (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Legion Y740-15IRHg',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Legion Y740-15IRHg ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Legión go (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Legión go',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Legión go ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Lo (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Lo',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Lo ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Loq (usado 5 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Loq',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Loq ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # NB IP 3 CHROME 15 IJL6 N4500 8G 128G CRM (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='NB IP 3 CHROME 15 IJL6 N4500 8G 128G CRM',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - NB IP 3 CHROME 15 IJL6 N4500 8G 128G CRM ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # NB LOQ 15IAX9E 1T 11S (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='NB LOQ 15IAX9E 1T 11S',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - NB LOQ 15IAX9E 1T 11S ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # NB PI 3 15ALC6 R7 8G 512G 11S (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='NB PI 3 15ALC6 R7 8G 512G 11S',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - NB PI 3 15ALC6 R7 8G 512G 11S ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # NB PI 3 15IRU8 I5 8G 512G 11S (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='NB PI 3 15IRU8 I5 8G 512G 11S',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - NB PI 3 15IRU8 I5 8G 512G 11S ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # NB TP T14 AMD G2 R5_PRO 16G 512G 10P (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='NB TP T14 AMD G2 R5_PRO 16G 512G 10P',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - NB TP T14 AMD G2 R5_PRO 16G 512G 10P ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # NB YG BOOK 9 13IMU9 ULT7 16G 1T 11S (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='NB YG BOOK 9 13IMU9 ULT7 16G 1T 11S',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - NB YG BOOK 9 13IMU9 ULT7 16G 1T 11S ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # NOTE BOOK THINKPAD P16 GEN 2 21FBCTO1WW R (usado 1 veces) - Gama: alta
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='NOTE BOOK THINKPAD P16 GEN 2 21FBCTO1WW R',
        defaults={
            'gama': 'alta',
            'rango_costo_min': Decimal('1200'),
            'rango_costo_max': Decimal('4000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - NOTE BOOK THINKPAD P16 GEN 2 21FBCTO1WW R ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # NP IP 1 15IJL7 N4500 8G 256G 11S (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='NP IP 1 15IJL7 N4500 8G 256G 11S',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - NP IP 1 15IJL7 N4500 8G 256G 11S ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # NP IP 1 15iru8 I5 8G 512G11S (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='NP IP 1 15iru8 I5 8G 512G11S',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - NP IP 1 15iru8 I5 8G 512G11S ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # NP IP SLIM 3 15IAH8 I5 8G 512G11S (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='NP IP SLIM 3 15IAH8 I5 8G 512G11S',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - NP IP SLIM 3 15IAH8 I5 8G 512G11S ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Nb ip slim 3 15irub 13 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Nb ip slim 3 15irub 13',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Nb ip slim 3 15irub 13 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # P1 Gen 6 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='P1 Gen 6',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - P1 Gen 6 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # P14s Gen 3 ThinkPad (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='P14s Gen 3 ThinkPad',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - P14s Gen 3 ThinkPad ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # P15 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='P15',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - P15 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # P15s Gen 2 ThinkPad (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='P15s Gen 2 ThinkPad',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - P15s Gen 2 ThinkPad ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # P43s (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='P43s',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - P43s ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # P70 - ThinkPad (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='P70 - ThinkPad',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - P70 - ThinkPad ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # S145-14API ideapad (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='S145-14API ideapad',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - S145-14API ideapad ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # S145-15IIL IdeaPad (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='S145-15IIL IdeaPad',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - S145-15IIL IdeaPad ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # S340-14IWL (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='S340-14IWL',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - S340-14IWL ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # T14 Gen 2 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='T14 Gen 2',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - T14 Gen 2 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # T16 Gen 2 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='T16 Gen 2',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - T16 Gen 2 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # T490 ThinkPad (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='T490 ThinkPad',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - T490 ThinkPad ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Thikstation (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Thikstation',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Thikstation ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # ThinkBook 13s G2 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='ThinkBook 13s G2',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - ThinkBook 13s G2 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # ThinkBook 14 G2 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='ThinkBook 14 G2',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - ThinkBook 14 G2 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # ThinkPad 13 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='ThinkPad 13',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - ThinkPad 13 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # ThinkPad E14 Gen 2 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='ThinkPad E14 Gen 2',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - ThinkPad E14 Gen 2 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Thinkbook (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Thinkbook',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Thinkbook ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # V14 G2-ALC (usado 1 veces) - Gama: baja
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='V14 G2-ALC',
        defaults={
            'gama': 'baja',
            'rango_costo_min': Decimal('250'),
            'rango_costo_max': Decimal('600'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - V14 G2-ALC ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # V14 G2-ALC Laptop (usado 1 veces) - Gama: baja
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='V14 G2-ALC Laptop',
        defaults={
            'gama': 'baja',
            'rango_costo_min': Decimal('250'),
            'rango_costo_max': Decimal('600'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - V14 G2-ALC Laptop ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # V14 G2-ITL (usado 1 veces) - Gama: baja
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='V14 G2-ITL',
        defaults={
            'gama': 'baja',
            'rango_costo_min': Decimal('250'),
            'rango_costo_max': Decimal('600'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - V14 G2-ITL ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # V50s-07IMB - Type 11EE (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='V50s-07IMB - Type 11EE',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - V50s-07IMB - Type 11EE ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # X1 Yoga 2nd Gen (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='X1 Yoga 2nd Gen',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - X1 Yoga 2nd Gen ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # X1 Yoga 4th Gen (Type 20QF, 20QG) (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='X1 Yoga 4th Gen (Type 20QF, 20QG)',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - X1 Yoga 4th Gen (Type 20QF, 20QG) ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Y50-70 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Y50-70',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Y50-70 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Y700-17ISK (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Y700-17ISK',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Y700-17ISK ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Yoga 510 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Yoga 510',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Yoga 510 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Yoga 520 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Yoga 520',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Yoga 520 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Yoga 7 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Yoga 7',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Yoga 7 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Yoga 7 2-in-1 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Yoga 7 2-in-1',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Yoga 7 2-in-1 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Yoga 7-14ITL5 (usado 3 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Yoga 7-14ITL5',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('700'),
            'rango_costo_max': Decimal('1500'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Yoga 7-14ITL5 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Yoga S940 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Yoga S940',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Yoga S940 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # Yoga Slim 9 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='Yoga Slim 9',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - Yoga Slim 9 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # ideapad 3 (usado 3 veces) - Gama: baja
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='ideapad 3',
        defaults={
            'gama': 'baja',
            'rango_costo_min': Decimal('250'),
            'rango_costo_max': Decimal('600'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - ideapad 3 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # ideapad 3-15ITL6 (usado 1 veces) - Gama: baja
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='ideapad 3-15ITL6',
        defaults={
            'gama': 'baja',
            'rango_costo_min': Decimal('250'),
            'rango_costo_max': Decimal('600'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - ideapad 3-15ITL6 ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # ideapad 5 (usado 2 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Lenovo',
        modelo_base='ideapad 5',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('450'),
            'rango_costo_max': Decimal('900'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Lenovo - ideapad 5 ({obj.get_gama_display()})')
    else:
        existentes += 1

    # ========================================
    # Marca: MSI (4 modelos)
    # ========================================
    
    # Cyborg (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='MSI',
        modelo_base='Cyborg',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: MSI - Cyborg ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # GL65 Leopard (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='MSI',
        modelo_base='GL65 Leopard',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: MSI - GL65 Leopard ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # LEOPARD 8RE (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='MSI',
        modelo_base='LEOPARD 8RE',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: MSI - LEOPARD 8RE ({obj.get_gama_display()})')
    else:
        existentes += 1
    
    # MS-16R3 (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='MSI',
        modelo_base='MS-16R3',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: MSI - MS-16R3 ({obj.get_gama_display()})')
    else:
        existentes += 1

    # ========================================
    # Marca: Sony (1 modelos)
    # ========================================
    
    # SVF142C29U (usado 1 veces) - Gama: media
    obj, created = ReferenciaGamaEquipo.objects.get_or_create(
        marca='Sony',
        modelo_base='SVF142C29U',
        defaults={
            'gama': 'media',
            'rango_costo_min': Decimal('400'),
            'rango_costo_max': Decimal('1000'),
            'activo': True
        }
    )
    if created:
        creados += 1
        print(f'✅ Creado: Sony - SVF142C29U ({obj.get_gama_display()})')
    else:
        existentes += 1

    print()
    print('=' * 80)
    print('RESUMEN DEL POBLADO')
    print('=' * 80)
    print()
    print(f'✅ Registros creados: {creados}')
    print(f'ℹ️  Registros existentes (no modificados): {existentes}')
    print(f'📊 Total procesado: {creados + existentes}')
    print()
    
    # Mostrar estadísticas por gama
    print('Distribución por Gama:')
    for gama_code, gama_nombre in [('alta', 'Alta'), ('media', 'Media'), ('baja', 'Baja')]:
        count = ReferenciaGamaEquipo.objects.filter(gama=gama_code, activo=True).count()
        print(f'  {gama_nombre}: {count} referencias')
    print()


if __name__ == '__main__':
    try:
        poblar_referencias_gama()
        print('✅ Poblado completado exitosamente')
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)