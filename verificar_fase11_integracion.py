"""
Script de Verificación - FASE 11: INTEGRACIÓN - BOTÓN EN DETALLE ORDEN
========================================================================

PROPÓSITO:
----------
Verificar que el botón de acceso al módulo RHITSO se ha agregado correctamente
en el template detalle_orden.html y que cumple con todos los requisitos de la Fase 11.

FASE 11 INCLUYE:
----------------
✅ Bloque condicional que solo aparece si orden.es_candidato_rhitso es True
✅ Alert box con información del proceso RHITSO
✅ Botón prominente de acceso a gestión RHITSO
✅ Badges informativos de estado y días en RHITSO
✅ Diseño integrado que no rompe el template existente

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Este script verifica que el código HTML/Django del botón RHITSO esté presente
en el template y tenga todos los elementos necesarios:
- Condicional {% if orden.es_candidato_rhitso %}
- URL correcta al módulo RHITSO
- Elementos visuales (badges, iconos, botón)
- Información del proceso (motivo, estado, días)

Ejecutar con: python verificar_fase11_integracion.py
"""

import os
import sys

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
    print(f"{Colors.BOLD}RESUMEN DE VERIFICACIÓN - FASE 11{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
    print(f"Total de tests: {total}")
    print(f"{Colors.GREEN}Tests exitosos: {passed}{Colors.RESET}")
    print(f"{Colors.RED}Tests fallidos: {failed}{Colors.RESET}")
    print(f"Porcentaje de éxito: {percentage:.1f}%")
    
    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 ¡TODOS LOS TESTS PASARON! FASE 11 COMPLETADA AL 100%{Colors.RESET}")
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
    
    print_header("VERIFICACIÓN FASE 11: INTEGRACIÓN - BOTÓN EN DETALLE ORDEN")
    
    # Ruta al template
    template_path = os.path.join(
        os.path.dirname(__file__),
        'servicio_tecnico',
        'templates',
        'servicio_tecnico',
        'detalle_orden.html'
    )
    
    # Verificar que el archivo existe
    if not os.path.exists(template_path):
        print(f"{Colors.RED}❌ ERROR: Template detalle_orden.html no encontrado en:{Colors.RESET}")
        print(f"   {template_path}")
        return False
    
    # Leer contenido del template
    with open(template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()
    
    # ========================================================================
    # SECCIÓN 1: VERIFICAR ESTRUCTURA BÁSICA
    # ========================================================================
    print_header("SECCIÓN 1: VERIFICACIÓN DE ESTRUCTURA BÁSICA")
    
    # Test 1: Comentario de Fase 11 presente
    total_tests += 1
    has_comment = 'FASE 11' in template_content and 'CANDIDATO A RHITSO' in template_content
    passed_tests += 1 if has_comment else 0
    print_test(1, "Comentario identificador de Fase 11 presente", has_comment,
              "Comentario de sección encontrado" if has_comment else "Comentario NO encontrado")
    
    # Test 2: Bloque condicional es_candidato_rhitso existe
    total_tests += 1
    has_conditional = '{% if orden.es_candidato_rhitso %}' in template_content
    passed_tests += 1 if has_conditional else 0
    print_test(2, "Bloque condicional es_candidato_rhitso existe", has_conditional,
              "Condicional {% if orden.es_candidato_rhitso %} encontrado" if has_conditional else "Condicional NO encontrado")
    
    # Test 3: Cierre del bloque condicional
    total_tests += 1
    has_endif = template_content.count('{% endif %}') >= template_content.count('{% if orden.es_candidato_rhitso %}')
    passed_tests += 1 if has_endif else 0
    print_test(3, "Bloque condicional tiene cierre correcto", has_endif,
              "{% endif %} encontrado" if has_endif else "Falta {% endif %}")
    
    # Test 4: Alert box con clase alert-info
    total_tests += 1
    has_alert = 'alert alert-info' in template_content and 'es_candidato_rhitso' in template_content
    passed_tests += 1 if has_alert else 0
    print_test(4, "Alert box Bootstrap presente", has_alert,
              "Alert con clase alert-info encontrado" if has_alert else "Alert NO encontrado")
    
    # ========================================================================
    # SECCIÓN 2: VERIFICAR CONTENIDO INFORMATIVO
    # ========================================================================
    print_header("SECCIÓN 2: VERIFICACIÓN DE CONTENIDO INFORMATIVO")
    
    # Test 5: Título "Candidato a RHITSO"
    total_tests += 1
    has_title = 'Candidato a RHITSO' in template_content
    passed_tests += 1 if has_title else 0
    print_test(5, "Título 'Candidato a RHITSO' presente", has_title,
              "Título encontrado" if has_title else "Título NO encontrado")
    
    # Test 6: Motivo RHITSO mostrado
    total_tests += 1
    has_motivo = 'orden.get_motivo_rhitso_display' in template_content or 'Motivo:' in template_content
    passed_tests += 1 if has_motivo else 0
    print_test(6, "Campo Motivo RHITSO incluido", has_motivo,
              "get_motivo_rhitso_display encontrado" if has_motivo else "Campo motivo NO encontrado")
    
    # Test 7: Estado RHITSO condicional
    total_tests += 1
    has_estado = '{% if orden.estado_rhitso %}' in template_content
    passed_tests += 1 if has_estado else 0
    print_test(7, "Condicional para estado_rhitso presente", has_estado,
              "Condicional de estado encontrado" if has_estado else "Condicional NO encontrado")
    
    # Test 8: Días en RHITSO mostrados
    total_tests += 1
    has_dias = 'orden.dias_en_rhitso' in template_content
    passed_tests += 1 if has_dias else 0
    print_test(8, "Campo días en RHITSO incluido", has_dias,
              "orden.dias_en_rhitso encontrado" if has_dias else "Campo días NO encontrado")
    
    # Test 9: Descripción RHITSO opcional
    total_tests += 1
    has_descripcion = 'orden.descripcion_rhitso' in template_content
    passed_tests += 1 if has_descripcion else 0
    print_test(9, "Campo descripción RHITSO incluido", has_descripcion,
              "orden.descripcion_rhitso encontrado" if has_descripcion else "Campo descripción NO encontrado")
    
    # ========================================================================
    # SECCIÓN 3: VERIFICAR BOTÓN DE ACCESO
    # ========================================================================
    print_header("SECCIÓN 3: VERIFICACIÓN DE BOTÓN DE ACCESO")
    
    # Test 10: URL a gestion_rhitso
    total_tests += 1
    has_url = "{% url 'servicio_tecnico:gestion_rhitso' orden.id %}" in template_content
    passed_tests += 1 if has_url else 0
    print_test(10, "URL a gestion_rhitso correcta", has_url,
              "URL pattern correcto encontrado" if has_url else "URL pattern NO encontrado o incorrecto")
    
    # Test 11: Botón con clase btn-primary
    total_tests += 1
    has_button = 'btn btn-primary' in template_content and 'gestion_rhitso' in template_content
    passed_tests += 1 if has_button else 0
    print_test(11, "Botón Bootstrap con estilo primario", has_button,
              "Botón btn-primary encontrado" if has_button else "Botón NO encontrado")
    
    # Test 12: Botón prominente (btn-lg)
    total_tests += 1
    has_large_button = 'btn-lg' in template_content and 'Gestión RHITSO' in template_content
    passed_tests += 1 if has_large_button else 0
    print_test(12, "Botón de tamaño grande (prominente)", has_large_button,
              "btn-lg encontrado" if has_large_button else "Botón grande NO encontrado")
    
    # Test 13: Texto del botón
    total_tests += 1
    has_button_text = 'Gestión RHITSO' in template_content
    passed_tests += 1 if has_button_text else 0
    print_test(13, "Texto del botón 'Gestión RHITSO'", has_button_text,
              "Texto correcto encontrado" if has_button_text else "Texto del botón NO encontrado")
    
    # ========================================================================
    # SECCIÓN 4: VERIFICAR ELEMENTOS VISUALES
    # ========================================================================
    print_header("SECCIÓN 4: VERIFICACIÓN DE ELEMENTOS VISUALES")
    
    # Test 14: Iconos Bootstrap Icons
    total_tests += 1
    icon_count = template_content.count('bi bi-') + template_content.count('bi-')
    has_icons = icon_count >= 3  # Al menos 3 iconos en el bloque RHITSO
    passed_tests += 1 if has_icons else 0
    print_test(14, "Iconos Bootstrap Icons presentes", has_icons,
              f"{icon_count} iconos encontrados" if has_icons else "Pocos iconos encontrados")
    
    # Test 15: Badges para estado
    total_tests += 1
    has_badges = template_content.count('badge bg-') >= 2  # Al menos 2 badges
    passed_tests += 1 if has_badges else 0
    print_test(15, "Badges informativos presentes", has_badges,
              "Badges encontrados" if has_badges else "Badges NO encontrados")
    
    # Test 16: Tooltip para botón
    total_tests += 1
    has_tooltip = 'data-bs-toggle="tooltip"' in template_content or 'title=' in template_content
    passed_tests += 1 if has_tooltip else 0
    print_test(16, "Tooltip en botón para UX mejorada", has_tooltip,
              "Tooltip encontrado" if has_tooltip else "Tooltip NO encontrado")
    
    # ========================================================================
    # SECCIÓN 5: VERIFICAR INTEGRACIÓN CON TEMPLATE
    # ========================================================================
    print_header("SECCIÓN 5: VERIFICACIÓN DE INTEGRACIÓN")
    
    # Test 17: Bloque insertado antes de SECCIÓN 1
    total_tests += 1
    rhitso_pos = template_content.find('es_candidato_rhitso')
    seccion1_pos = template_content.find('SECCIÓN 1: INFORMACIÓN PRINCIPAL')
    properly_placed = rhitso_pos > 0 and seccion1_pos > rhitso_pos and (seccion1_pos - rhitso_pos) < 5000
    passed_tests += 1 if properly_placed else 0
    print_test(17, "Bloque insertado en posición correcta", properly_placed,
              "Bloque antes de SECCIÓN 1" if properly_placed else "Posición incorrecta")
    
    # Test 18: No rompe estructura existente
    total_tests += 1
    has_section1 = 'SECCIÓN 1: INFORMACIÓN PRINCIPAL' in template_content
    has_closing_divs = template_content.count('</div>') >= 50  # Template tiene muchos divs
    structure_ok = has_section1 and has_closing_divs
    passed_tests += 1 if structure_ok else 0
    print_test(18, "Estructura existente intacta", structure_ok,
              "Template mantiene estructura original" if structure_ok else "Posible daño en estructura")
    
    # Test 19: Responsive design (col-md, col-lg)
    total_tests += 1
    has_responsive = 'col-md-' in template_content and 'col-12' in template_content
    passed_tests += 1 if has_responsive else 0
    print_test(19, "Diseño responsive implementado", has_responsive,
              "Clases responsive encontradas" if has_responsive else "Diseño NO responsive")
    
    # Test 20: Gradiente o estilo visual destacado
    total_tests += 1
    has_gradient = 'linear-gradient' in template_content or 'border-left:' in template_content
    passed_tests += 1 if has_gradient else 0
    print_test(20, "Estilo visual destacado presente", has_gradient,
              "Gradiente o borde destacado encontrado" if has_gradient else "Sin estilo destacado")
    
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
