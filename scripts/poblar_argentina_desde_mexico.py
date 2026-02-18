"""
scripts/poblar_argentina_desde_mexico.py
========================================
Copia datos de catálogo desde la base de datos de México a la de Argentina.

Tablas que migra:
  - scorecard.ComponenteEquipo
  - servicio_tecnico.ReferenciaGamaEquipo

COMO EJECUTARLO:
    source ../venv/bin/activate
    python manage.py shell < scripts/poblar_argentina_desde_mexico.py

O también desde el shell de Django:
    python manage.py shell
    >>> exec(open('scripts/poblar_argentina_desde_mexico.py').read())

LÓGICA:
    - Lee TODOS los registros de la BD 'mexico'
    - Para cada registro intenta crearlo en 'argentina'
    - Si ya existe (por unique_together), lo ACTUALIZA con los datos de México
    - Nunca duplica ni borra datos existentes en Argentina
"""

import os
import sys
import django

# ---------------------------------------------------------------------------
# Setup de Django (solo necesario si ejecutas el script directamente,
# no desde manage.py shell)
# ---------------------------------------------------------------------------
if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    # Agregar el directorio raíz del proyecto al path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    django.setup()

from scorecard.models import ComponenteEquipo, CategoriaIncidencia, ServicioRealizado
from servicio_tecnico.models import ReferenciaGamaEquipo


def separador(titulo):
    print("\n" + "=" * 60)
    print(f"  {titulo}")
    print("=" * 60)


def copiar_componentes_equipo():
    """
    Copia ComponenteEquipo de México → Argentina.
    unique_together: ['nombre', 'tipo_equipo']
    """
    separador("ComponenteEquipo (scorecard)")

    registros_mx = ComponenteEquipo.objects.using('mexico').all()
    total = registros_mx.count()
    print(f"  Registros en México: {total}")

    creados = 0
    actualizados = 0
    sin_cambios = 0

    for obj in registros_mx:
        # get_or_create busca por los campos únicos
        componente_ar, creado = ComponenteEquipo.objects.using('argentina').get_or_create(
            nombre=obj.nombre,
            tipo_equipo=obj.tipo_equipo,
            defaults={
                'activo': obj.activo,
            }
        )

        if creado:
            creados += 1
            print(f"  [NUEVO]       {obj.nombre} ({obj.get_tipo_equipo_display()})")
        else:
            # Ya existía — actualizar el campo 'activo' por si cambió
            if componente_ar.activo != obj.activo:
                componente_ar.activo = obj.activo
                componente_ar.save(using='argentina')
                actualizados += 1
                print(f"  [ACTUALIZADO] {obj.nombre} ({obj.get_tipo_equipo_display()})")
            else:
                sin_cambios += 1

    print(f"\n  Resumen:")
    print(f"    Nuevos:          {creados}")
    print(f"    Actualizados:    {actualizados}")
    print(f"    Sin cambios:     {sin_cambios}")
    print(f"    Total procesado: {total}")


def copiar_referencia_gama():
    """
    Copia ReferenciaGamaEquipo de México → Argentina.
    unique_together: ['marca', 'modelo_base']
    """
    separador("ReferenciaGamaEquipo (servicio_tecnico)")

    registros_mx = ReferenciaGamaEquipo.objects.using('mexico').all()
    total = registros_mx.count()
    print(f"  Registros en México: {total}")

    creados = 0
    actualizados = 0
    sin_cambios = 0

    for obj in registros_mx:
        referencia_ar, creado = ReferenciaGamaEquipo.objects.using('argentina').get_or_create(
            marca=obj.marca,
            modelo_base=obj.modelo_base,
            defaults={
                'gama': obj.gama,
                'rango_costo_min': obj.rango_costo_min,
                'rango_costo_max': obj.rango_costo_max,
                'activo': obj.activo,
            }
        )

        if creado:
            creados += 1
            print(f"  [NUEVO]       {obj.marca} {obj.modelo_base} → {obj.get_gama_display()}")
        else:
            # Verificar si hay diferencias
            hay_cambios = (
                referencia_ar.gama != obj.gama
                or referencia_ar.rango_costo_min != obj.rango_costo_min
                or referencia_ar.rango_costo_max != obj.rango_costo_max
                or referencia_ar.activo != obj.activo
            )
            if hay_cambios:
                referencia_ar.gama = obj.gama
                referencia_ar.rango_costo_min = obj.rango_costo_min
                referencia_ar.rango_costo_max = obj.rango_costo_max
                referencia_ar.activo = obj.activo
                referencia_ar.save(using='argentina')
                actualizados += 1
                print(f"  [ACTUALIZADO] {obj.marca} {obj.modelo_base} → {obj.get_gama_display()}")
            else:
                sin_cambios += 1

    print(f"\n  Resumen:")
    print(f"    Nuevos:          {creados}")
    print(f"    Actualizados:    {actualizados}")
    print(f"    Sin cambios:     {sin_cambios}")
    print(f"    Total procesado: {total}")


def copiar_categorias_incidencia():
    """
    Copia CategoriaIncidencia de México → Argentina.
    Campo único: nombre
    """
    separador("CategoriaIncidencia (scorecard)")

    registros_mx = CategoriaIncidencia.objects.using('mexico').all()
    total = registros_mx.count()
    print(f"  Registros en México: {total}")

    creados = 0
    actualizados = 0
    sin_cambios = 0

    for obj in registros_mx:
        categoria_ar, creado = CategoriaIncidencia.objects.using('argentina').get_or_create(
            nombre=obj.nombre,
            defaults={
                'descripcion': obj.descripcion,
                'color': obj.color,
                'activo': obj.activo,
            }
        )

        if creado:
            creados += 1
            print(f"  [NUEVO]       {obj.nombre}")
        else:
            hay_cambios = (
                categoria_ar.descripcion != obj.descripcion
                or categoria_ar.color != obj.color
                or categoria_ar.activo != obj.activo
            )
            if hay_cambios:
                categoria_ar.descripcion = obj.descripcion
                categoria_ar.color = obj.color
                categoria_ar.activo = obj.activo
                categoria_ar.save(using='argentina')
                actualizados += 1
                print(f"  [ACTUALIZADO] {obj.nombre}")
            else:
                sin_cambios += 1

    print(f"\n  Resumen:")
    print(f"    Nuevos:          {creados}")
    print(f"    Actualizados:    {actualizados}")
    print(f"    Sin cambios:     {sin_cambios}")
    print(f"    Total procesado: {total}")


def copiar_servicios_realizados():
    """
    Copia ServicioRealizado de México → Argentina.
    Campo único: nombre
    """
    separador("ServicioRealizado (scorecard)")

    registros_mx = ServicioRealizado.objects.using('mexico').all()
    total = registros_mx.count()
    print(f"  Registros en México: {total}")

    creados = 0
    actualizados = 0
    sin_cambios = 0

    for obj in registros_mx:
        servicio_ar, creado = ServicioRealizado.objects.using('argentina').get_or_create(
            nombre=obj.nombre,
            defaults={
                'descripcion': obj.descripcion,
                'orden': obj.orden,
                'activo': obj.activo,
            }
        )

        if creado:
            creados += 1
            print(f"  [NUEVO]       {obj.nombre}")
        else:
            hay_cambios = (
                servicio_ar.descripcion != obj.descripcion
                or servicio_ar.orden != obj.orden
                or servicio_ar.activo != obj.activo
            )
            if hay_cambios:
                servicio_ar.descripcion = obj.descripcion
                servicio_ar.orden = obj.orden
                servicio_ar.activo = obj.activo
                servicio_ar.save(using='argentina')
                actualizados += 1
                print(f"  [ACTUALIZADO] {obj.nombre}")
            else:
                sin_cambios += 1

    print(f"\n  Resumen:")
    print(f"    Nuevos:          {creados}")
    print(f"    Actualizados:    {actualizados}")
    print(f"    Sin cambios:     {sin_cambios}")
    print(f"    Total procesado: {total}")


# ---------------------------------------------------------------------------
# EJECUCIÓN PRINCIPAL
# ---------------------------------------------------------------------------

separador("INICIO — Poblar Argentina desde México")
print("  Este script copia datos de catálogo de México → Argentina.")
print("  No borra datos existentes en Argentina.")

copiar_componentes_equipo()
copiar_referencia_gama()
copiar_categorias_incidencia()
copiar_servicios_realizados()

separador("FIN — Proceso completado")
