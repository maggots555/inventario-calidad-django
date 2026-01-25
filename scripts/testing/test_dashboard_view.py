#!/usr/bin/env python
"""
Script de prueba para la vista del Dashboard de Distribución Multi-Sucursal
Simula una petición HTTP y verifica el contexto de la respuesta
"""
import os
import sys
import django

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import RequestFactory, Client
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from almacen.views import dashboard_distribucion_sucursales

User = get_user_model()

def test_dashboard_view():
    """Prueba la vista del dashboard con una petición simulada"""
    
    print("=" * 70)
    print("PRUEBA: Vista Dashboard de Distribución Multi-Sucursal")
    print("=" * 70)
    
    # Crear un usuario de prueba con permisos
    try:
        user = User.objects.get(username='admin')
        print(f"\n✓ Usuario encontrado: {user.username}")
    except User.DoesNotExist:
        # Intentar crear un superusuario temporal
        print("\n⚠ No se encontró usuario 'admin', usando cliente anónimo")
        user = None
    
    # Usar Django Test Client
    client = Client()
    
    if user:
        client.force_login(user)
        print(f"✓ Usuario autenticado: {user.username}")
    
    # Hacer petición GET a la vista
    print("\n--- Petición GET ---")
    url = '/almacen/dashboard/distribucion-sucursales/'
    
    try:
        response = client.get(url)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Vista responde correctamente (200 OK)")
            
            # Verificar el contexto
            context = response.context
            
            print("\n--- Contexto de la Vista ---")
            print(f"✓ Productos: {len(context['productos_paginados'])} en la página actual")
            print(f"✓ Total productos: {context['page_obj'].paginator.count if 'page_obj' in context else 'N/A'}")
            print(f"✓ Sucursales: {len(context['sucursales'])}")
            print(f"✓ KPIs:")
            print(f"  - Productos con stock: {context['productos_con_stock']}")
            print(f"  - Total unidades: {context['total_unidades']}")
            print(f"  - Productos sin stock: {context['productos_sin_stock']}")
            print(f"  - Sucursales activas: {context['sucursales_activas']}")
            
            # Mostrar algunos productos de ejemplo
            print("\n--- Productos de Ejemplo ---")
            for i, producto in enumerate(context['productos_paginados'][:3], 1):
                print(f"\n{i}. {producto.codigo_producto} - {producto.nombre}")
                print(f"   Inventario: {producto.inventario}")
                print(f"   Total general: {producto.total_general}")
            
            # Verificar template usado
            print(f"\n--- Template ---")
            print(f"✓ Template usado: {response.templates[0].name if response.templates else 'N/A'}")
            
        elif response.status_code == 302:
            print(f"⚠ Redirección (302): {response.url}")
            print("  (Probablemente requiere autenticación)")
            
        elif response.status_code == 403:
            print("❌ Acceso denegado (403)")
            print("  El usuario no tiene los permisos necesarios")
            
        else:
            print(f"⚠ Código de estado inesperado: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error al hacer la petición: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Probar filtros
    print("\n" + "=" * 70)
    print("PRUEBA: Filtros")
    print("=" * 70)
    
    # Filtro de búsqueda
    response_search = client.get(url, {'q': 'RAM'})
    if response_search.status_code == 200:
        count = len(response_search.context['productos_paginados'])
        print(f"✓ Filtro de búsqueda 'RAM': {count} productos encontrados")
    
    # Filtro por categoría
    from almacen.models import CategoriaAlmacen
    categorias = CategoriaAlmacen.objects.all()[:1]
    if categorias:
        response_cat = client.get(url, {'categoria': categorias[0].id})
        if response_cat.status_code == 200:
            count = len(response_cat.context['productos_paginados'])
            print(f"✓ Filtro por categoría '{categorias[0].nombre}': {count} productos")
    
    print("\n" + "=" * 70)
    print("✅ PRUEBA DE VISTA COMPLETADA")
    print("=" * 70)
    
    return True

if __name__ == '__main__':
    try:
        success = test_dashboard_view()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR CRÍTICO: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
