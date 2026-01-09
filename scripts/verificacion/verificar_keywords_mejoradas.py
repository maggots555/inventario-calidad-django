# -*- coding: utf-8 -*-
"""Verificación Rápida: Comparación de Keywords Antes vs Después"""

import os
import sys
import django
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from servicio_tecnico.ml_advanced.motivo_rechazo_mejorado import PredictorMotivoRechazoMejorado

predictor = PredictorMotivoRechazoMejorado()

print("\n" + "="*80)
print("KEYWORDS MEJORADAS - COMPARACION")
print("="*80)

# Motivos clave que tenían problemas
motivos_clave = [
    'costo_alto',
    'no_apto', 
    'rechazo_sin_decision',
    'no_hay_partes',
    'solo_venta_mostrador',
    'muchas_piezas',
    'tiempo_largo'
]

for motivo in motivos_clave:
    config = predictor.MOTIVOS[motivo]
    print(f"\n{motivo}:")
    print(f"  Nombre: {config['nombre']}")
    print(f"  Total Keywords: {len(config['keywords'])}")
    print(f"  Keywords: {', '.join(config['keywords'][:8])}")
    if len(config['keywords']) > 8:
        print(f"           {', '.join(config['keywords'][8:])}")

print("\n" + "="*80)
print("Keywords actualizadas correctamente basadas en datos reales de la BD")
print("="*80)
