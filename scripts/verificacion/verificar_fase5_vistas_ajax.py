"""
Script de Verificación - FASE 5: VISTAS AJAX RHITSO
====================================================

PROPÓSITO:
----------
Verificar que todas las vistas AJAX para el módulo RHITSO están correctamente
implementadas y funcionan según lo especificado en el plan.

FASE 5 INCLUYE:
---------------
✅ Vista actualizar_estado_rhitso - Cambiar estado RHITSO de orden
✅ Vista registrar_incidencia - Registrar nuevas incidencias
✅ Vista resolver_incidencia - Resolver incidencias existentes
✅ Vista editar_diagnostico_sic - Editar diagnóstico SIC y datos RHITSO

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Este script NO ejecuta las vistas reales (eso requeriría autenticación y datos reales).
En su lugar, verifica que:
1. Las vistas existen y están importadas
2. Los URL patterns están configurados
3. Los decoradores requeridos están presentes
4. La estructura del código es correcta
5. Los formularios necesarios existen

Ejecutar con: python verificar_fase5_vistas_ajax.py
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.urls import reverse, resolve, NoReverseMatch
from servicio_tecnico import views
from servicio_tecnico.forms import (
    ActualizarEstadoRHITSOForm,
    RegistrarIncidenciaRHITSOForm,
    ResolverIncidenciaRHITSOForm,
    EditarDiagnosticoSICForm,
)
import inspect

# ============================================================================
# COLORES PARA OUTPUT
# ============================================================================
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

def print_header(text):
    """Imprime un encabezado con formato"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(80)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}\n")

def print_test(number, description, passed, details=""):
    """Imprime resultado de un test"""
    status = f"{Colors.GREEN}✅ PASS{Colors.RESET}" if passed else f"{Colors.RED}❌ FAIL{Colors.RESET}"
    print(f"Test {number}: {description.ljust(60)} {status}")
    if details:
        color = Colors.GREEN if passed else Colors.RED
        print(f"         {color}{details}{Colors.RESET}")

def print_summary(total, passed):
    """Imprime resumen final"""
    failed = total - passed
    percentage = (passed / total * 100) if total > 0 else 0
    
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}RESUMEN DE VERIFICACIÓN - FASE 5{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
    print(f"Total de tests: {total}")
    print(f"{Colors.GREEN}Tests exitosos: {passed}{Colors.RESET}")
    print(f"{Colors.RED}Tests fallidos: {failed}{Colors.RESET}")
    print(f"Porcentaje de éxito: {percentage:.1f}%")
    
    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 ¡TODOS LOS TESTS PASARON! FASE 5 COMPLETADA AL 100%{Colors.RESET}")
    else:
        print(f"\n{Colors.YELLOW}⚠️  Algunos tests fallaron. Revisa los detalles arriba.{Colors.RESET}")
    
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}\n")

# ============================================================================
# TESTS DE VERIFICACIÓN
# ============================================================================

def run_tests():
    """Ejecuta todos los tests de verificación"""
    total_tests = 0
    passed_tests = 0
    
    print_header("VERIFICACIÓN FASE 5: VISTAS AJAX RHITSO")
    
    # ========================================================================
    # SECCIÓN 1: VERIFICAR EXISTENCIA DE VISTAS
    # ========================================================================
    print_header("SECCIÓN 1: VERIFICACIÓN DE VISTAS")
    
    # Test 1: Vista actualizar_estado_rhitso existe
    total_tests += 1
    try:
        vista_actualizar = getattr(views, 'actualizar_estado_rhitso', None)
        exists = vista_actualizar is not None and callable(vista_actualizar)
        passed_tests += 1 if exists else 0
        print_test(1, "Vista actualizar_estado_rhitso existe", exists,
                  "Vista encontrada en servicio_tecnico.views" if exists else "Vista NO encontrada")
    except Exception as e:
        print_test(1, "Vista actualizar_estado_rhitso existe", False, str(e))
    
    # Test 2: Vista registrar_incidencia existe
    total_tests += 1
    try:
        vista_registrar = getattr(views, 'registrar_incidencia', None)
        exists = vista_registrar is not None and callable(vista_registrar)
        passed_tests += 1 if exists else 0
        print_test(2, "Vista registrar_incidencia existe", exists,
                  "Vista encontrada en servicio_tecnico.views" if exists else "Vista NO encontrada")
    except Exception as e:
        print_test(2, "Vista registrar_incidencia existe", False, str(e))
    
    # Test 3: Vista resolver_incidencia existe
    total_tests += 1
    try:
        vista_resolver = getattr(views, 'resolver_incidencia', None)
        exists = vista_resolver is not None and callable(vista_resolver)
        passed_tests += 1 if exists else 0
        print_test(3, "Vista resolver_incidencia existe", exists,
                  "Vista encontrada en servicio_tecnico.views" if exists else "Vista NO encontrada")
    except Exception as e:
        print_test(3, "Vista resolver_incidencia existe", False, str(e))
    
    # Test 4: Vista editar_diagnostico_sic existe
    total_tests += 1
    try:
        vista_editar = getattr(views, 'editar_diagnostico_sic', None)
        exists = vista_editar is not None and callable(vista_editar)
        passed_tests += 1 if exists else 0
        print_test(4, "Vista editar_diagnostico_sic existe", exists,
                  "Vista encontrada en servicio_tecnico.views" if exists else "Vista NO encontrada")
    except Exception as e:
        print_test(4, "Vista editar_diagnostico_sic existe", False, str(e))
    
    # ========================================================================
    # SECCIÓN 2: VERIFICAR DECORADORES
    # ========================================================================
    print_header("SECCIÓN 2: VERIFICACIÓN DE DECORADORES")
    
    # Test 5: actualizar_estado_rhitso tiene @login_required
    total_tests += 1
    try:
        vista = views.actualizar_estado_rhitso
        source = inspect.getsource(vista)
        has_login = '@login_required' in source or 'login_required' in str(vista)
        passed_tests += 1 if has_login else 0
        print_test(5, "actualizar_estado_rhitso tiene @login_required", has_login,
                  "Decorador encontrado" if has_login else "Decorador NO encontrado")
    except Exception as e:
        print_test(5, "actualizar_estado_rhitso tiene @login_required", False, str(e))
    
    # Test 6: actualizar_estado_rhitso tiene @require_POST
    total_tests += 1
    try:
        vista = views.actualizar_estado_rhitso
        source = inspect.getsource(vista)
        has_post = '@require_http_methods' in source or 'require_POST' in source
        passed_tests += 1 if has_post else 0
        print_test(6, "actualizar_estado_rhitso tiene @require_POST", has_post,
                  "Decorador encontrado" if has_post else "Decorador NO encontrado")
    except Exception as e:
        print_test(6, "actualizar_estado_rhitso tiene @require_POST", False, str(e))
    
    # Test 7: registrar_incidencia tiene @login_required
    total_tests += 1
    try:
        vista = views.registrar_incidencia
        source = inspect.getsource(vista)
        has_login = '@login_required' in source or 'login_required' in str(vista)
        passed_tests += 1 if has_login else 0
        print_test(7, "registrar_incidencia tiene @login_required", has_login,
                  "Decorador encontrado" if has_login else "Decorador NO encontrado")
    except Exception as e:
        print_test(7, "registrar_incidencia tiene @login_required", False, str(e))
    
    # Test 8: resolver_incidencia tiene @login_required
    total_tests += 1
    try:
        vista = views.resolver_incidencia
        source = inspect.getsource(vista)
        has_login = '@login_required' in source or 'login_required' in str(vista)
        passed_tests += 1 if has_login else 0
        print_test(8, "resolver_incidencia tiene @login_required", has_login,
                  "Decorador encontrado" if has_login else "Decorador NO encontrado")
    except Exception as e:
        print_test(8, "resolver_incidencia tiene @login_required", False, str(e))
    
    # Test 9: editar_diagnostico_sic tiene @login_required
    total_tests += 1
    try:
        vista = views.editar_diagnostico_sic
        source = inspect.getsource(vista)
        has_login = '@login_required' in source or 'login_required' in str(vista)
        passed_tests += 1 if has_login else 0
        print_test(9, "editar_diagnostico_sic tiene @login_required", has_login,
                  "Decorador encontrado" if has_login else "Decorador NO encontrado")
    except Exception as e:
        print_test(9, "editar_diagnostico_sic tiene @login_required", False, str(e))
    
    # ========================================================================
    # SECCIÓN 3: VERIFICAR URLs
    # ========================================================================
    print_header("SECCIÓN 3: VERIFICACIÓN DE URL PATTERNS")
    
    # Test 10: URL actualizar_estado_rhitso está configurada
    total_tests += 1
    try:
        url = reverse('servicio_tecnico:actualizar_estado_rhitso', kwargs={'orden_id': 1})
        resolved = resolve(url)
        is_correct = resolved.func == views.actualizar_estado_rhitso
        passed_tests += 1 if is_correct else 0
        print_test(10, "URL actualizar_estado_rhitso configurada", is_correct,
                  f"URL: {url}" if is_correct else "URL no resuelve correctamente")
    except NoReverseMatch:
        print_test(10, "URL actualizar_estado_rhitso configurada", False, "URL pattern NO encontrado")
    except Exception as e:
        print_test(10, "URL actualizar_estado_rhitso configurada", False, str(e))
    
    # Test 11: URL registrar_incidencia está configurada
    total_tests += 1
    try:
        url = reverse('servicio_tecnico:registrar_incidencia', kwargs={'orden_id': 1})
        resolved = resolve(url)
        is_correct = resolved.func == views.registrar_incidencia
        passed_tests += 1 if is_correct else 0
        print_test(11, "URL registrar_incidencia configurada", is_correct,
                  f"URL: {url}" if is_correct else "URL no resuelve correctamente")
    except NoReverseMatch:
        print_test(11, "URL registrar_incidencia configurada", False, "URL pattern NO encontrado")
    except Exception as e:
        print_test(11, "URL registrar_incidencia configurada", False, str(e))
    
    # Test 12: URL resolver_incidencia está configurada
    total_tests += 1
    try:
        url = reverse('servicio_tecnico:resolver_incidencia', kwargs={'incidencia_id': 1})
        resolved = resolve(url)
        is_correct = resolved.func == views.resolver_incidencia
        passed_tests += 1 if is_correct else 0
        print_test(12, "URL resolver_incidencia configurada", is_correct,
                  f"URL: {url}" if is_correct else "URL no resuelve correctamente")
    except NoReverseMatch:
        print_test(12, "URL resolver_incidencia configurada", False, "URL pattern NO encontrado")
    except Exception as e:
        print_test(12, "URL resolver_incidencia configurada", False, str(e))
    
    # Test 13: URL editar_diagnostico_sic está configurada
    total_tests += 1
    try:
        url = reverse('servicio_tecnico:editar_diagnostico_sic', kwargs={'orden_id': 1})
        resolved = resolve(url)
        is_correct = resolved.func == views.editar_diagnostico_sic
        passed_tests += 1 if is_correct else 0
        print_test(13, "URL editar_diagnostico_sic configurada", is_correct,
                  f"URL: {url}" if is_correct else "URL no resuelve correctamente")
    except NoReverseMatch:
        print_test(13, "URL editar_diagnostico_sic configurada", False, "URL pattern NO encontrado")
    except Exception as e:
        print_test(13, "URL editar_diagnostico_sic configurada", False, str(e))
    
    # ========================================================================
    # SECCIÓN 4: VERIFICAR FORMULARIOS
    # ========================================================================
    print_header("SECCIÓN 4: VERIFICACIÓN DE FORMULARIOS")
    
    # Test 14: Formulario ActualizarEstadoRHITSOForm existe
    total_tests += 1
    try:
        form = ActualizarEstadoRHITSOForm()
        has_fields = all(field in form.fields for field in ['estado_rhitso', 'observaciones', 'notificar_cliente'])
        passed_tests += 1 if has_fields else 0
        print_test(14, "ActualizarEstadoRHITSOForm tiene campos requeridos", has_fields,
                  "Campos: estado_rhitso, observaciones, notificar_cliente" if has_fields else "Faltan campos")
    except Exception as e:
        print_test(14, "ActualizarEstadoRHITSOForm tiene campos requeridos", False, str(e))
    
    # Test 15: Formulario RegistrarIncidenciaRHITSOForm existe
    total_tests += 1
    try:
        form = RegistrarIncidenciaRHITSOForm()
        has_fields = all(field in form.fields for field in ['tipo_incidencia', 'titulo', 'descripcion_detallada'])
        passed_tests += 1 if has_fields else 0
        print_test(15, "RegistrarIncidenciaRHITSOForm tiene campos requeridos", has_fields,
                  "Campos: tipo_incidencia, titulo, descripcion_detallada..." if has_fields else "Faltan campos")
    except Exception as e:
        print_test(15, "RegistrarIncidenciaRHITSOForm tiene campos requeridos", False, str(e))
    
    # Test 16: Formulario ResolverIncidenciaRHITSOForm existe
    total_tests += 1
    try:
        form = ResolverIncidenciaRHITSOForm()
        has_fields = 'accion_tomada' in form.fields
        passed_tests += 1 if has_fields else 0
        print_test(16, "ResolverIncidenciaRHITSOForm tiene campos requeridos", has_fields,
                  "Campo: accion_tomada" if has_fields else "Falta campo accion_tomada")
    except Exception as e:
        print_test(16, "ResolverIncidenciaRHITSOForm tiene campos requeridos", False, str(e))
    
    # Test 17: Formulario EditarDiagnosticoSICForm existe
    total_tests += 1
    try:
        form = EditarDiagnosticoSICForm()
        has_fields = all(field in form.fields for field in ['diagnostico_sic', 'motivo_rhitso', 'complejidad_estimada'])
        passed_tests += 1 if has_fields else 0
        print_test(17, "EditarDiagnosticoSICForm tiene campos requeridos", has_fields,
                  "Campos: diagnostico_sic, motivo_rhitso, complejidad_estimada..." if has_fields else "Faltan campos")
    except Exception as e:
        print_test(17, "EditarDiagnosticoSICForm tiene campos requeridos", False, str(e))
    
    # ========================================================================
    # SECCIÓN 5: VERIFICAR ESTRUCTURA DE CÓDIGO
    # ========================================================================
    print_header("SECCIÓN 5: VERIFICACIÓN DE ESTRUCTURA DE CÓDIGO")
    
    # Test 18: actualizar_estado_rhitso retorna JsonResponse
    total_tests += 1
    try:
        vista = views.actualizar_estado_rhitso
        source = inspect.getsource(vista)
        returns_json = 'JsonResponse' in source
        passed_tests += 1 if returns_json else 0
        print_test(18, "actualizar_estado_rhitso retorna JsonResponse", returns_json,
                  "Vista usa JsonResponse para AJAX" if returns_json else "No usa JsonResponse")
    except Exception as e:
        print_test(18, "actualizar_estado_rhitso retorna JsonResponse", False, str(e))
    
    # Test 19: registrar_incidencia crea IncidenciaRHITSO
    total_tests += 1
    try:
        vista = views.registrar_incidencia
        source = inspect.getsource(vista)
        creates_incidencia = 'IncidenciaRHITSO' in source or 'form.save' in source
        passed_tests += 1 if creates_incidencia else 0
        print_test(19, "registrar_incidencia crea IncidenciaRHITSO", creates_incidencia,
                  "Vista maneja creación de incidencias" if creates_incidencia else "No crea incidencias")
    except Exception as e:
        print_test(19, "registrar_incidencia crea IncidenciaRHITSO", False, str(e))
    
    # Test 20: resolver_incidencia usa marcar_como_resuelta
    total_tests += 1
    try:
        vista = views.resolver_incidencia
        source = inspect.getsource(vista)
        uses_method = 'marcar_como_resuelta' in source
        passed_tests += 1 if uses_method else 0
        print_test(20, "resolver_incidencia usa marcar_como_resuelta()", uses_method,
                  "Vista usa método del modelo" if uses_method else "No usa método del modelo")
    except Exception as e:
        print_test(20, "resolver_incidencia usa marcar_como_resuelta()", False, str(e))
    
    # Test 21: editar_diagnostico_sic actualiza DetalleEquipo y OrdenServicio
    total_tests += 1
    try:
        vista = views.editar_diagnostico_sic
        source = inspect.getsource(vista)
        updates_both = 'detalle_equipo' in source and 'orden.motivo_rhitso' in source
        passed_tests += 1 if updates_both else 0
        print_test(21, "editar_diagnostico_sic actualiza ambos modelos", updates_both,
                  "Vista actualiza DetalleEquipo y OrdenServicio" if updates_both else "No actualiza ambos modelos")
    except Exception as e:
        print_test(21, "editar_diagnostico_sic actualiza ambos modelos", False, str(e))
    
    # Test 22: Todas las vistas manejan excepciones
    total_tests += 1
    try:
        vista1 = inspect.getsource(views.actualizar_estado_rhitso)
        vista2 = inspect.getsource(views.registrar_incidencia)
        vista3 = inspect.getsource(views.resolver_incidencia)
        vista4 = inspect.getsource(views.editar_diagnostico_sic)
        
        has_exception_handling = all([
            'try:' in vista and 'except' in vista
            for vista in [vista1, vista2, vista3, vista4]
        ])
        passed_tests += 1 if has_exception_handling else 0
        print_test(22, "Todas las vistas manejan excepciones", has_exception_handling,
                  "Todas usan try/except" if has_exception_handling else "Algunas no manejan excepciones")
    except Exception as e:
        print_test(22, "Todas las vistas manejan excepciones", False, str(e))
    
    # ========================================================================
    # RESUMEN FINAL
    # ========================================================================
    print_summary(total_tests, passed_tests)
    
    return passed_tests == total_tests

# ============================================================================
# EJECUCIÓN PRINCIPAL
# ============================================================================
if __name__ == '__main__':
    try:
        success = run_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Verificación interrumpida por el usuario.{Colors.RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Error fatal durante la verificación: {e}{Colors.RESET}")
        sys.exit(1)
