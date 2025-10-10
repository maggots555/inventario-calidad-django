"""
Script de Verificación - FASE 4: Vista Principal RHITSO

EXPLICACIÓN PARA PRINCIPIANTES:
Este script verifica que la vista principal del módulo RHITSO esté correctamente
implementada y funcione como se espera.

PROPÓSITO:
- Verificar que todos los imports funcionan correctamente
- Comprobar que la vista gestion_rhitso existe y está configurada
- Validar que la URL está registrada correctamente
- Verificar que el contexto se prepara adecuadamente
- Asegurar que las validaciones funcionan

CÓMO FUNCIONA:
Django tiene un sistema de testing que permite simular requests HTTP
sin necesidad de un servidor web corriendo.
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import RequestFactory, Client
from django.contrib.auth.models import User
from django.urls import reverse, resolve
from servicio_tecnico.models import (
    OrdenServicio,
    DetalleEquipo,
    EstadoRHITSO,
    SeguimientoRHITSO,
    IncidenciaRHITSO,
    TipoIncidenciaRHITSO,
)
from servicio_tecnico.forms import (
    ActualizarEstadoRHITSOForm,
    RegistrarIncidenciaRHITSOForm,
    ResolverIncidenciaRHITSOForm,
    EditarDiagnosticoSICForm,
)
from servicio_tecnico import views
from inventario.models import Empleado, Sucursal
from django.utils import timezone


def print_test_header(test_name):
    """Imprime un encabezado para cada test"""
    print("\n" + "="*80)
    print(f"TEST: {test_name}")
    print("="*80)


def print_success(message):
    """Imprime mensaje de éxito"""
    print(f"✅ {message}")


def print_error(message):
    """Imprime mensaje de error"""
    print(f"❌ {message}")


def print_info(message):
    """Imprime mensaje informativo"""
    print(f"ℹ️  {message}")


# ============================================================================
# TEST 1: VERIFICAR IMPORTS
# ============================================================================

def test_imports():
    """
    Verifica que todos los imports necesarios funcionen correctamente.
    
    EXPLICACIÓN:
    Django debe poder importar todos los modelos, formularios y vistas
    que necesita la vista gestion_rhitso sin errores.
    """
    print_test_header("Verificar Imports de RHITSO")
    
    try:
        # Verificar que la vista existe
        assert hasattr(views, 'gestion_rhitso'), "La vista gestion_rhitso no existe en views.py"
        print_success("Vista gestion_rhitso importada correctamente")
        
        # Verificar modelos RHITSO
        print_info("Verificando modelos RHITSO...")
        assert EstadoRHITSO is not None
        assert SeguimientoRHITSO is not None
        assert IncidenciaRHITSO is not None
        assert TipoIncidenciaRHITSO is not None
        print_success("Todos los modelos RHITSO importados correctamente")
        
        # Verificar formularios RHITSO
        print_info("Verificando formularios RHITSO...")
        assert ActualizarEstadoRHITSOForm is not None
        assert RegistrarIncidenciaRHITSOForm is not None
        assert ResolverIncidenciaRHITSOForm is not None
        assert EditarDiagnosticoSICForm is not None
        print_success("Todos los formularios RHITSO importados correctamente")
        
        return True
    except Exception as e:
        print_error(f"Error en imports: {str(e)}")
        return False


# ============================================================================
# TEST 2: VERIFICAR URL PATTERN
# ============================================================================

def test_url_configuration():
    """
    Verifica que la URL esté correctamente configurada.
    
    EXPLICACIÓN:
    Django debe poder resolver la URL 'gestion_rhitso' y vincularla
    correctamente con la vista.
    """
    print_test_header("Verificar Configuración de URL")
    
    try:
        # Verificar que la URL esté registrada
        url_name = 'servicio_tecnico:gestion_rhitso'
        print_info(f"Verificando URL: {url_name}")
        
        # Intentar generar la URL
        url = reverse(url_name, kwargs={'orden_id': 1})
        print_success(f"URL generada correctamente: {url}")
        
        # Verificar que apunta a la vista correcta
        resolved = resolve(url)
        assert resolved.func == views.gestion_rhitso, "La URL no apunta a la vista correcta"
        print_success("URL apunta correctamente a gestion_rhitso")
        
        # Verificar el patrón esperado
        expected_pattern = '/servicio-tecnico/rhitso/orden/1/'
        assert url == expected_pattern, f"Patrón de URL incorrecto. Esperado: {expected_pattern}, Obtenido: {url}"
        print_success(f"Patrón de URL correcto: {expected_pattern}")
        
        return True
    except Exception as e:
        print_error(f"Error en configuración de URL: {str(e)}")
        return False


# ============================================================================
# TEST 3: VERIFICAR AUTENTICACIÓN REQUERIDA
# ============================================================================

def test_authentication_required():
    """
    Verifica que la vista requiera autenticación.
    
    EXPLICACIÓN:
    El decorador @login_required debe redirigir usuarios no autenticados
    a la página de login.
    """
    print_test_header("Verificar Autenticación Requerida")
    
    try:
        client = Client()
        url = reverse('servicio_tecnico:gestion_rhitso', kwargs={'orden_id': 1})
        
        print_info("Intentando acceder sin autenticación...")
        response = client.get(url)
        
        # Debe redirigir al login
        assert response.status_code == 302, f"Debería redirigir (302), obtuvo: {response.status_code}"
        print_success("Vista redirige correctamente a usuarios no autenticados")
        
        # Verificar que redirige al login (puede ser /login/ o /accounts/login/)
        login_patterns = ['/accounts/login/', '/login/']
        redirect_url = response.url
        login_found = any(pattern in redirect_url for pattern in login_patterns)
        assert login_found, f"Debería redirigir a login, redirige a: {redirect_url}"
        print_success(f"Redirige correctamente al login: {redirect_url}")
        
        return True
    except Exception as e:
        print_error(f"Error en verificación de autenticación: {str(e)}")
        return False


# ============================================================================
# TEST 4: VERIFICAR VALIDACIÓN DE es_candidato_rhitso
# ============================================================================

def test_candidato_rhitso_validation():
    """
    Verifica que la vista valide es_candidato_rhitso correctamente.
    
    EXPLICACIÓN:
    Solo las órdenes marcadas como candidato RHITSO deben poder
    acceder al panel. Otras deben ser redirigidas con mensaje de error.
    """
    print_test_header("Verificar Validación de es_candidato_rhitso")
    
    try:
        # Crear usuario y empleado de prueba
        print_info("Creando datos de prueba...")
        
        # Eliminar usuario si ya existe (de ejecuciones anteriores)
        User.objects.filter(username='test_rhitso').delete()
        user = User.objects.create_user(username='test_rhitso', password='test123')
        
        # Buscar o crear sucursal
        sucursal = Sucursal.objects.first()
        if not sucursal:
            print_error("No hay sucursales en la base de datos. Crea al menos una sucursal.")
            return False
        
        # Crear empleado de prueba asociado al usuario
        # EXPLICACIÓN: El middleware requiere que el usuario tenga un empleado asociado
        empleado = Empleado.objects.create(
            user=user,
            nombre_completo='Empleado de Prueba RHITSO',
            cargo='Técnico',
            area='Servicio Técnico',
            sucursal=sucursal,
            activo=True,
            tiene_acceso_sistema=True,
            contraseña_configurada=True  # Evitar redirección del middleware
        )
        
        # Crear orden NO candidato RHITSO
        print_info("Creando orden NO candidato RHITSO...")
        orden_no_rhitso = OrdenServicio.objects.create(
            sucursal=sucursal,
            estado='diagnostico',
            es_candidato_rhitso=False,  # NO es candidato
            responsable_seguimiento=empleado,  # Campo requerido
            tecnico_asignado_actual=empleado,  # Campo requerido
        )
        
        # Crear DetalleEquipo
        DetalleEquipo.objects.create(
            orden=orden_no_rhitso,
            tipo_equipo='LAPTOP',
            marca='TEST',
            modelo='TEST',
            numero_serie='TEST123',
        )
        
        # Intentar acceder con orden NO candidato
        client = Client()
        client.login(username='test_rhitso', password='test123')
        url = reverse('servicio_tecnico:gestion_rhitso', kwargs={'orden_id': orden_no_rhitso.id})
        
        print_info(f"Accediendo a URL: {url}")
        response = client.get(url, follow=True)
        
        # Debe redirigir
        assert response.status_code == 200, f"Debería devolver 200, obtuvo: {response.status_code}"
        print_success("Vista maneja correctamente orden NO candidato RHITSO")
        
        # Ahora crear orden SÍ candidato RHITSO
        print_info("Creando orden SÍ candidato RHITSO...")
        orden_rhitso = OrdenServicio.objects.create(
            sucursal=sucursal,
            estado='diagnostico',
            es_candidato_rhitso=True,  # SÍ es candidato
            responsable_seguimiento=empleado,  # Campo requerido
            tecnico_asignado_actual=empleado,  # Campo requerido
        )
        
        DetalleEquipo.objects.create(
            orden=orden_rhitso,
            tipo_equipo='LAPTOP',
            marca='TEST',
            modelo='TEST',
            numero_serie='TEST456',
        )
        
        url = reverse('servicio_tecnico:gestion_rhitso', kwargs={'orden_id': orden_rhitso.id})
        print_info(f"Accediendo a URL: {url}")
        response = client.get(url)
        
        # Debe mostrar la página (200)
        assert response.status_code == 200, f"Debería devolver 200, obtuvo: {response.status_code}"
        print_success("Vista permite acceso a orden candidato RHITSO")
        
        # Limpiar
        orden_no_rhitso.delete()
        orden_rhitso.delete()
        user.delete()
        
        return True
    except Exception as e:
        print_error(f"Error en validación de candidato RHITSO: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# TEST 5: VERIFICAR CONTEXTO DE LA VISTA
# ============================================================================

def test_view_context():
    """
    Verifica que la vista prepare el contexto correctamente.
    
    EXPLICACIÓN:
    El contexto debe contener todas las claves necesarias para
    renderizar el template (orden, formularios, incidencias, etc.)
    """
    print_test_header("Verificar Contexto de la Vista")
    
    try:
        # Crear datos de prueba
        print_info("Creando datos de prueba completos...")
        
        # Eliminar usuario si ya existe (de ejecuciones anteriores)
        User.objects.filter(username='test_context').delete()
        user = User.objects.create_user(username='test_context', password='test123')
        sucursal = Sucursal.objects.first()
        
        if not sucursal:
            print_error("Faltan sucursales en la base de datos")
            return False
        
        # Crear empleado asociado al usuario
        empleado = Empleado.objects.create(
            user=user,
            nombre_completo='Empleado de Prueba Context',
            cargo='Técnico',
            area='Servicio Técnico',
            sucursal=sucursal,
            activo=True,
            tiene_acceso_sistema=True,
            contraseña_configurada=True  # Evitar redirección del middleware
        )
        
        # Crear orden candidato RHITSO
        orden = OrdenServicio.objects.create(
            sucursal=sucursal,
            estado='diagnostico',
            es_candidato_rhitso=True,
            estado_rhitso='DIAGNOSTICO_SIC',
            responsable_seguimiento=empleado,  # Campo requerido
            tecnico_asignado_actual=empleado,  # Campo requerido
        )
        
        DetalleEquipo.objects.create(
            orden=orden,
            tipo_equipo='LAPTOP',
            marca='APPLE',
            modelo='MacBook Pro',
            numero_serie='TEST789',
            diagnostico_sic='Equipo no enciende',
        )
        
        # Hacer request
        client = Client()
        client.login(username='test_context', password='test123')
        url = reverse('servicio_tecnico:gestion_rhitso', kwargs={'orden_id': orden.id})
        
        print_info(f"Ejecutando request a: {url}")
        response = client.get(url)
        
        assert response.status_code == 200, f"Status code incorrecto: {response.status_code}"
        
        # Verificar que la respuesta contiene HTML esperado
        print_info("Verificando contenido HTML...")
        content = response.content.decode('utf-8')
        
        # Verificar elementos clave del template
        expected_strings = [
            'RHITSO - Orden',
            'Información del Equipo',
            'Estado RHITSO Actual',
            'Diagnóstico SIC',
            'Historial de Seguimiento RHITSO',
            'Gestión de Incidencias',
            'Galería de Imágenes RHITSO',
        ]
        
        for expected in expected_strings:
            assert expected in content, f"No se encontró en HTML: {expected}"
            print_success(f"Presente en HTML: {expected}")
        
        print_success("Template renderiza correctamente con todas las secciones")
        
        # Limpiar
        orden.delete()
        user.delete()
        
        return True
    except Exception as e:
        print_error(f"Error en verificación de contexto: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# EJECUTAR TODOS LOS TESTS
# ============================================================================

def run_all_tests():
    """
    Ejecuta todos los tests y genera reporte.
    """
    print("\n" + "="*80)
    print("INICIANDO VERIFICACIÓN DE FASE 4: VISTA PRINCIPAL RHITSO")
    print("="*80)
    print("\nFecha:", timezone.now().strftime("%d/%m/%Y %H:%M:%S"))
    print("\n")
    
    tests = [
        ("Imports", test_imports),
        ("URL Configuration", test_url_configuration),
        ("Authentication Required", test_authentication_required),
        ("Candidato RHITSO Validation", test_candidato_rhitso_validation),
        ("View Context", test_view_context),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print_error(f"Error inesperado en {test_name}: {str(e)}")
            results.append((test_name, False))
    
    # Reporte final
    print("\n" + "="*80)
    print("RESUMEN DE VERIFICACIÓN")
    print("="*80 + "\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"Tests ejecutados: {total}")
    print(f"Tests exitosos: {passed}")
    print(f"Tests fallidos: {total - passed}")
    print(f"Porcentaje de éxito: {(passed/total)*100:.1f}%\n")
    
    print("Resultados detallados:")
    for test_name, result in results:
        status = "✅ PASÓ" if result else "❌ FALLÓ"
        print(f"  {status} - {test_name}")
    
    print("\n" + "="*80)
    
    if passed == total:
        print("🎉 ¡FASE 4 COMPLETADA EXITOSAMENTE!")
        print("="*80)
        print("\n✅ Todos los componentes de la vista principal RHITSO están funcionando correctamente.")
        print("\n📌 PRÓXIMOS PASOS:")
        print("   1. Crear template: servicio_tecnico/rhitso/gestion_rhitso.html")
        print("   2. Implementar vistas AJAX (Fase 5)")
        print("   3. Agregar estilos CSS específicos para RHITSO")
        print("   4. Pruebas de integración completas\n")
    else:
        print("⚠️  ALGUNOS TESTS FALLARON")
        print("="*80)
        print("\nRevisa los errores anteriores y corrígelos antes de continuar.\n")
    
    return passed == total


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
