"""
Script para poblar la base de datos con datos iniciales del Score Card
Ejecutar con: python poblar_scorecard.py
"""
import os
import django
import sys
from datetime import datetime, timedelta
import random

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from scorecard.models import CategoriaIncidencia, ComponenteEquipo, Incidencia, EvidenciaIncidencia
from inventario.models import Empleado, Sucursal


def crear_categorias():
    """
    Crea las categorías iniciales de incidencias
    """
    print("📋 Creando categorías de incidencias...")
    
    categorias = [
        {
            'nombre': 'Fallo Post-Reparación',
            'descripcion': 'Equipo falla después de ser reparado y entregado al área de calidad',
            'color': '#dc3545'  # Rojo
        },
        {
            'nombre': 'Defecto No Registrado',
            'descripcion': 'Defectos visibles no registrados durante la inspección inicial',
            'color': '#fd7e14'  # Naranja
        },
        {
            'nombre': 'Componente Mal Instalado',
            'descripcion': 'Componente instalado incorrectamente durante la reparación',
            'color': '#ffc107'  # Amarillo
        },
        {
            'nombre': 'Limpieza Deficiente',
            'descripcion': 'Equipo entregado sin la limpieza adecuada',
            'color': '#0dcaf0'  # Cian
        },
        {
            'nombre': 'Fallo de Diagnóstico',
            'descripcion': 'Diagnóstico inicial incorrecto que llevó a reparación inadecuada',
            'color': '#6f42c1'  # Morado
        },
        {
            'nombre': 'Daño Cosmético',
            'descripcion': 'Daño cosmético ocasionado durante el servicio',
            'color': '#d63384'  # Rosa
        },
        {
            'nombre': 'Documentación Incompleta',
            'descripcion': 'Falta de documentación del servicio realizado',
            'color': '#6c757d'  # Gris
        },
    ]
    
    for cat_data in categorias:
        categoria, created = CategoriaIncidencia.objects.get_or_create(
            nombre=cat_data['nombre'],
            defaults={
                'descripcion': cat_data['descripcion'],
                'color': cat_data['color']
            }
        )
        if created:
            print(f"  ✅ Creada: {categoria.nombre}")
        else:
            print(f"  ℹ️  Ya existe: {categoria.nombre}")
    
    print(f"✅ Total de categorías: {CategoriaIncidencia.objects.count()}\n")


def crear_componentes():
    """
    Crea los componentes de equipos
    """
    print("🔧 Creando componentes de equipos...")
    
    componentes = [
        # Componentes para todos los tipos
        {'nombre': 'Pantalla', 'tipo': 'todos'},
        {'nombre': 'Teclado', 'tipo': 'laptop'},
        {'nombre': 'Touchpad', 'tipo': 'laptop'},
        {'nombre': 'Mouse', 'tipo': 'pc'},
        {'nombre': 'Teclado USB', 'tipo': 'pc'},
        {'nombre': 'RAM', 'tipo': 'todos'},
        {'nombre': 'Disco Duro / SSD', 'tipo': 'todos'},
        {'nombre': 'Fuente de Poder', 'tipo': 'todos'},
        {'nombre': 'Motherboard', 'tipo': 'todos'},
        {'nombre': 'Procesador (CPU)', 'tipo': 'todos'},
        {'nombre': 'Tarjeta Gráfica (GPU)', 'tipo': 'todos'},
        {'nombre': 'Batería', 'tipo': 'laptop'},
        {'nombre': 'Ventilador / Cooling', 'tipo': 'todos'},
        {'nombre': 'Bisagras', 'tipo': 'laptop'},
        {'nombre': 'Carcasa / Chasis', 'tipo': 'todos'},
        {'nombre': 'Puerto USB', 'tipo': 'todos'},
        {'nombre': 'Puerto HDMI', 'tipo': 'todos'},
        {'nombre': 'Puerto de Red (Ethernet)', 'tipo': 'todos'},
        {'nombre': 'WiFi / Bluetooth', 'tipo': 'todos'},
        {'nombre': 'Webcam', 'tipo': 'todos'},
        {'nombre': 'Micrófono', 'tipo': 'todos'},
        {'nombre': 'Bocinas / Audio', 'tipo': 'todos'},
        {'nombre': 'Lector de Tarjetas', 'tipo': 'todos'},
        {'nombre': 'Sistema Operativo', 'tipo': 'todos'},
    ]
    
    for comp_data in componentes:
        componente, created = ComponenteEquipo.objects.get_or_create(
            nombre=comp_data['nombre'],
            tipo_equipo=comp_data['tipo'],
            defaults={'activo': True}
        )
        if created:
            print(f"  ✅ Creado: {componente.nombre} ({componente.get_tipo_equipo_display()})")
        else:
            print(f"  ℹ️  Ya existe: {componente.nombre}")
    
    print(f"✅ Total de componentes: {ComponenteEquipo.objects.count()}\n")


def crear_incidencias_ejemplo():
    """
    Crea algunas incidencias de ejemplo
    """
    print("📊 Creando incidencias de ejemplo...")
    
    # Verificar que existan empleados y sucursales
    if Empleado.objects.count() == 0:
        print("⚠️  No hay empleados en la base de datos.")
        print("   Ejecuta primero: python poblar_sistema.py")
        return
    
    if Sucursal.objects.count() == 0:
        print("⚠️  No hay sucursales en la base de datos.")
        print("   Ejecuta primero: python poblar_sistema.py")
        return
    
    if CategoriaIncidencia.objects.count() == 0:
        print("⚠️  No hay categorías creadas.")
        return
    
    # Obtener datos necesarios
    empleados = list(Empleado.objects.all())
    sucursales = list(Sucursal.objects.all())
    categorias = list(CategoriaIncidencia.objects.all())
    componentes = list(ComponenteEquipo.objects.all())
    
    # Datos de ejemplo
    marcas = ['HP', 'Dell', 'Lenovo', 'Acer', 'ASUS', 'Toshiba']
    tipos_equipo = ['pc', 'laptop', 'aio']
    severidades = ['critico', 'alto', 'medio', 'bajo']
    estados = ['abierta', 'en_revision', 'cerrada']
    categorias_fallo = ['hardware', 'software', 'cosmetico', 'funcional']
    
    descripciones_ejemplo = [
        "Equipo presenta fallo en el componente después de la reparación. Cliente reporta problema al recibir.",
        "Durante inspección de calidad se detectó defecto que no fue registrado en la recepción inicial.",
        "Componente instalado presenta holgura o no está correctamente conectado.",
        "Se detectaron residuos de pasta térmica y polvo en el equipo entregado.",
        "El diagnóstico inicial no identificó correctamente el problema, requiriendo re-trabajo.",
        "Se observan rayones o marcas en la carcasa que no estaban previos al servicio.",
        "Falta documentación completa del trabajo realizado en el equipo.",
        "Puerto USB quedó suelto después del servicio de mantenimiento.",
        "Pantalla presenta manchas después de la limpieza.",
        "Sistema operativo no arranca correctamente después de la instalación.",
    ]
    
    acciones_ejemplo = [
        "Se realizó nueva reparación del componente afectado. Equipo probado durante 2 horas.",
        "Se registró el defecto en sistema y se notificó al área de recepción para reforzar inspección.",
        "Se reinstalaron correctamente todos los componentes y se verificó estabilidad.",
        "Se realizó limpieza profunda adicional según protocolo de calidad.",
        "Se actualizó proceso de diagnóstico y se capacitó al técnico responsable.",
        "Se realizó pulido superficial y se documentó para prevenir futuros incidentes.",
        "Se completó documentación faltante y se actualizó checklist de entrega.",
        "Se reemplazó puerto USB y se reforzó fijación interna.",
        "Se limpió pantalla con productos especializados y se verificó ausencia de marcas.",
        "Se reinstaló sistema operativo desde cero y se verificó funcionamiento completo.",
    ]
    
    # Crear 15 incidencias de ejemplo
    num_incidencias = 15
    
    for i in range(num_incidencias):
        # Fecha aleatoria en los últimos 3 meses
        dias_atras = random.randint(0, 90)
        fecha_deteccion = datetime.now().date() - timedelta(days=dias_atras)
        
        # Seleccionar datos aleatorios
        tipo_equipo = random.choice(tipos_equipo)
        marca = random.choice(marcas)
        numero_serie = f"SN{random.randint(10000000, 99999999)}"
        sucursal = random.choice(sucursales)
        tecnico = random.choice(empleados)
        inspector = random.choice([e for e in empleados if e != tecnico])  # Diferente al técnico
        categoria = random.choice(categorias)
        componente = random.choice([c for c in componentes if c.tipo_equipo in [tipo_equipo, 'todos']])
        severidad = random.choice(severidades)
        estado = random.choice(estados)
        
        try:
            incidencia = Incidencia.objects.create(
                fecha_deteccion=fecha_deteccion,
                tipo_equipo=tipo_equipo,
                marca=marca,
                modelo=f"Modelo-{random.randint(100, 999)}",
                numero_serie=numero_serie,
                servicio_realizado=f"Reparación de {componente.nombre}",
                sucursal=sucursal,
                area_detectora=random.choice(['tecnico', 'calidad', 'recepcion']),
                tecnico_responsable=tecnico,
                inspector_calidad=inspector,
                tipo_incidencia=categoria,
                categoria_fallo=random.choice(categorias_fallo),
                grado_severidad=severidad,
                componente_afectado=componente,
                descripcion_incidencia=random.choice(descripciones_ejemplo),
                acciones_tomadas=random.choice(acciones_ejemplo),
                estado=estado,
                es_reincidencia=False
            )
            
            print(f"  ✅ Creada: {incidencia.folio} - {marca} {tipo_equipo} ({severidad})")
            
        except Exception as e:
            print(f"  ❌ Error creando incidencia: {e}")
    
    print(f"✅ Total de incidencias: {Incidencia.objects.count()}\n")


def main():
    """
    Función principal
    """
    print("=" * 70)
    print("🎯 SCRIPT DE POBLACIÓN - SCORE CARD")
    print("=" * 70)
    print()
    
    try:
        crear_categorias()
        crear_componentes()
        crear_incidencias_ejemplo()
        
        print("=" * 70)
        print("✅ PROCESO COMPLETADO EXITOSAMENTE")
        print("=" * 70)
        print()
        print("📊 Resumen:")
        print(f"   - Categorías: {CategoriaIncidencia.objects.count()}")
        print(f"   - Componentes: {ComponenteEquipo.objects.count()}")
        print(f"   - Incidencias: {Incidencia.objects.count()}")
        print(f"   - Empleados disponibles: {Empleado.objects.count()}")
        print(f"   - Sucursales disponibles: {Sucursal.objects.count()}")
        print()
        print("🌐 Accede al Score Card en:")
        print("   http://localhost:8000/scorecard/")
        print()
        print("👉 Accede al admin en:")
        print("   http://localhost:8000/admin/")
        print()
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
