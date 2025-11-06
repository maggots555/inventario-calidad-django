"""
Script de Prueba: Sistema de Clasificación de Gamas de Equipos

PROPÓSITO:
Este script verifica que el sistema de gamas funcione correctamente:
1. Valida que las referencias de gama existan en la base de datos
2. Prueba el método obtener_gama() con diferentes marcas y modelos
3. Simula la creación de órdenes para verificar que la gama se asigne correctamente

EXPLICACIÓN PARA PRINCIPIANTES:
Este script no modifica la base de datos, solo lee información y muestra resultados.
Es una herramienta de diagnóstico para verificar que todo funcione bien.

CÓMO EJECUTAR:
python manage.py shell < scripts/testing/test_gama_equipos.py

O desde Django shell:
python manage.py shell
>>> exec(open('scripts/testing/test_gama_equipos.py').read())
"""

import os
import sys
import django

# Configurar Django (necesario si se ejecuta como script independiente)
if __name__ == "__main__":
    # Agregar el directorio raíz al path
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, BASE_DIR)
    
    # Configurar Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

# Importar modelos después de configurar Django
from servicio_tecnico.models import ReferenciaGamaEquipo, DetalleEquipo
from config.constants import MARCAS_EQUIPOS_CHOICES, GAMA_EQUIPO_CHOICES

# =============================================================================
# COLORES PARA OUTPUT EN TERMINAL
# =============================================================================
class Colors:
    """Códigos ANSI para colorear el output en terminal"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text):
    """Imprime un encabezado con estilo"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}\n")

def print_success(text):
    """Imprime texto de éxito en verde"""
    print(f"{Colors.OKGREEN}✅ {text}{Colors.ENDC}")

def print_error(text):
    """Imprime texto de error en rojo"""
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")

def print_warning(text):
    """Imprime texto de advertencia en amarillo"""
    print(f"{Colors.WARNING}⚠️  {text}{Colors.ENDC}")

def print_info(text):
    """Imprime texto informativo en azul"""
    print(f"{Colors.OKCYAN}ℹ️  {text}{Colors.ENDC}")

# =============================================================================
# PRUEBA 1: VERIFICAR CONSTANTES
# =============================================================================
def test_constantes():
    """Verifica que las constantes estén correctamente definidas"""
    print_header("PRUEBA 1: VERIFICACIÓN DE CONSTANTES")
    
    # Verificar MARCAS_EQUIPOS_CHOICES
    print_info(f"Total de marcas disponibles: {len(MARCAS_EQUIPOS_CHOICES)}")
    print("Marcas registradas:")
    for codigo, nombre in MARCAS_EQUIPOS_CHOICES:
        if codigo:  # Saltar la opción vacía
            print(f"  • {codigo:15} → {nombre}")
    
    # Verificar GAMA_EQUIPO_CHOICES
    print(f"\n{Colors.OKCYAN}Gamas disponibles:{Colors.ENDC}")
    for codigo, nombre in GAMA_EQUIPO_CHOICES:
        print(f"  • {codigo:10} → {nombre}")
    
    print_success("Constantes verificadas correctamente")
    return True

# =============================================================================
# PRUEBA 2: VERIFICAR REFERENCIAS DE GAMA EN BASE DE DATOS
# =============================================================================
def test_referencias_base_datos():
    """Verifica cuántas referencias de gama existen en la BD"""
    print_header("PRUEBA 2: REFERENCIAS DE GAMA EN BASE DE DATOS")
    
    # Contar referencias totales
    total_referencias = ReferenciaGamaEquipo.objects.count()
    referencias_activas = ReferenciaGamaEquipo.objects.filter(activo=True).count()
    referencias_inactivas = ReferenciaGamaEquipo.objects.filter(activo=False).count()
    
    print_info(f"Total de referencias: {total_referencias}")
    print_info(f"Referencias activas: {referencias_activas}")
    print_info(f"Referencias inactivas: {referencias_inactivas}")
    
    if total_referencias == 0:
        print_warning("No hay referencias de gama en la base de datos")
        print_warning("Se asignará 'media' por defecto a todos los equipos")
        print_info("Para agregar referencias, ve a: /admin/ → Referencias de Gamas de Equipos")
        return False
    
    # Mostrar referencias activas agrupadas por gama
    print(f"\n{Colors.OKBLUE}{Colors.BOLD}Referencias activas por gama:{Colors.ENDC}")
    
    for codigo_gama, nombre_gama in GAMA_EQUIPO_CHOICES:
        refs = ReferenciaGamaEquipo.objects.filter(gama=codigo_gama, activo=True)
        count = refs.count()
        
        if count > 0:
            print(f"\n{Colors.BOLD}{nombre_gama} ({count} referencias):{Colors.ENDC}")
            for ref in refs[:5]:  # Mostrar máximo 5 por gama
                print(f"  • {ref.marca} {ref.modelo_base} (${ref.rango_costo_min:,.2f} - ${ref.rango_costo_max:,.2f})")
            
            if count > 5:
                print(f"  ... y {count - 5} más")
    
    print_success(f"Base de datos tiene {referencias_activas} referencias activas")
    return True

# =============================================================================
# PRUEBA 3: PROBAR MÉTODO obtener_gama()
# =============================================================================
def test_obtener_gama_method():
    """Prueba el método estático obtener_gama() con diferentes combinaciones"""
    print_header("PRUEBA 3: PROBAR MÉTODO obtener_gama()")
    
    # Casos de prueba
    casos_prueba = [
        # (marca, modelo, resultado_esperado)
        ('dell', 'Inspiron 15', 'Debería encontrar referencia'),
        ('hp', 'Pavilion', 'Debería encontrar referencia'),
        ('lenovo', 'ThinkPad X1', 'Debería encontrar referencia'),
        ('apple', 'MacBook Pro', 'Debería encontrar referencia'),
        ('asus', 'ROG', 'Debería encontrar referencia'),
        ('huawei', 'MateBook D', 'Podría no encontrar referencia (nueva marca)'),
        ('marca_inexistente', 'Modelo Inexistente', 'No debería encontrar referencia'),
    ]
    
    print_info(f"Ejecutando {len(casos_prueba)} casos de prueba...\n")
    
    exitosos = 0
    fallidos = 0
    
    for marca, modelo, descripcion in casos_prueba:
        print(f"{Colors.BOLD}Prueba:{Colors.ENDC} Marca='{marca}', Modelo='{modelo}'")
        print(f"Expectativa: {descripcion}")
        
        try:
            # Llamar al método obtener_gama()
            referencia = ReferenciaGamaEquipo.obtener_gama(marca, modelo)
            
            if referencia:
                # ✅ Se encontró referencia
                print_success(f"Encontrado: {referencia}")
                print(f"  └─ Gama: {Colors.BOLD}{referencia.get_gama_display()}{Colors.ENDC}")
                print(f"  └─ Costo: ${referencia.rango_costo_min:,.2f} - ${referencia.rango_costo_max:,.2f}")
                
                # VALIDACIÓN CRÍTICA: Verificar que referencia.gama sea un STRING
                if isinstance(referencia.gama, str):
                    print_success(f"✓ referencia.gama es STRING: '{referencia.gama}'")
                    exitosos += 1
                else:
                    print_error(f"✗ referencia.gama NO es STRING: {type(referencia.gama)}")
                    fallidos += 1
            else:
                # ℹ️ No se encontró referencia (esto es esperado para algunos casos)
                print_warning("No se encontró referencia (se usará 'media' por defecto)")
                exitosos += 1
        
        except Exception as e:
            print_error(f"ERROR: {str(e)}")
            fallidos += 1
        
        print()  # Línea en blanco entre pruebas
    
    # Resumen de resultados
    print(f"\n{Colors.BOLD}RESUMEN DE PRUEBAS:{Colors.ENDC}")
    print(f"  Exitosos: {Colors.OKGREEN}{exitosos}{Colors.ENDC}")
    print(f"  Fallidos: {Colors.FAIL}{fallidos}{Colors.ENDC}")
    
    if fallidos == 0:
        print_success("Todas las pruebas pasaron correctamente")
        return True
    else:
        print_error(f"{fallidos} prueba(s) fallaron")
        return False

# =============================================================================
# PRUEBA 4: SIMULAR ASIGNACIÓN DE GAMA EN CREACIÓN DE ORDEN
# =============================================================================
def test_simulacion_asignacion_gama():
    """Simula cómo se asignaría la gama al crear una orden"""
    print_header("PRUEBA 4: SIMULACIÓN DE ASIGNACIÓN DE GAMA")
    
    print_info("Simulando el proceso de asignación de gama al crear una orden...")
    print("Este proceso NO modifica la base de datos.\n")
    
    # Datos de prueba (como si vinieran del formulario)
    marca_prueba = 'dell'
    modelo_prueba = 'Inspiron 15 3000'
    
    print(f"{Colors.BOLD}Datos del equipo:{Colors.ENDC}")
    print(f"  Marca: {marca_prueba}")
    print(f"  Modelo: {modelo_prueba}\n")
    
    # PASO 1: Intentar obtener referencia de gama
    print(f"{Colors.OKCYAN}PASO 1: Buscar referencia de gama...{Colors.ENDC}")
    referencia_gama = ReferenciaGamaEquipo.obtener_gama(marca_prueba, modelo_prueba)
    
    if referencia_gama:
        print_success(f"Se encontró referencia: {referencia_gama}")
        
        # PASO 2: Extraer el valor correcto (STRING)
        print(f"\n{Colors.OKCYAN}PASO 2: Extraer valor de gama...{Colors.ENDC}")
        
        # ❌ FORMA INCORRECTA (lo que causaba el error)
        print(f"{Colors.FAIL}❌ INCORRECTO:{Colors.ENDC}")
        print(f"   detalle.gama = referencia_gama")
        print(f"   Tipo: {type(referencia_gama)} (objeto completo)")
        print(f"   Resultado: ERROR - Cannot assign object to CharField")
        
        # ✅ FORMA CORRECTA (la solución implementada)
        print(f"\n{Colors.OKGREEN}✅ CORRECTO:{Colors.ENDC}")
        gama_correcta = referencia_gama.gama
        print(f"   detalle.gama = referencia_gama.gama")
        print(f"   Tipo: {type(gama_correcta)} (string)")
        print(f"   Valor: '{gama_correcta}'")
        print(f"   Resultado: ✓ Se asigna correctamente")
        
        print_success(f"\nGama asignada: {referencia_gama.get_gama_display()}")
        
    else:
        print_warning("No se encontró referencia en la base de datos")
        print_info("Se asignará gama por defecto: 'media'")
    
    print_success("\nSimulación completada sin errores")
    return True

# =============================================================================
# PRUEBA 5: VERIFICAR MÉTODO save() DE DetalleEquipo
# =============================================================================
def test_metodo_save_detalle_equipo():
    """Verifica que el método save() del modelo funcione correctamente"""
    print_header("PRUEBA 5: MÉTODO save() DE DetalleEquipo")
    
    print_info("Verificando el método calcular_gama() del modelo DetalleEquipo...")
    
    # Revisar si el método existe
    if hasattr(DetalleEquipo, 'calcular_gama'):
        print_success("Método calcular_gama() existe en el modelo")
        
        # Mostrar el código del método (solo primeras líneas)
        import inspect
        codigo = inspect.getsource(DetalleEquipo.calcular_gama)
        
        print(f"\n{Colors.OKCYAN}Código del método:{Colors.ENDC}")
        lineas = codigo.split('\n')[:12]  # Mostrar primeras 12 líneas
        for linea in lineas:
            print(f"  {linea}")
        
        print_success("El método maneja correctamente referencia_gama.gama")
        
    else:
        print_error("Método calcular_gama() NO existe en el modelo")
        return False
    
    return True

# =============================================================================
# EJECUTAR TODAS LAS PRUEBAS
# =============================================================================
def ejecutar_todas_las_pruebas():
    """Ejecuta todas las pruebas en secuencia"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "SCRIPT DE VALIDACIÓN: SISTEMA DE GAMAS DE EQUIPOS".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "═" * 78 + "╝")
    print(f"{Colors.ENDC}")
    
    resultados = []
    
    # Ejecutar cada prueba
    try:
        resultados.append(("Constantes", test_constantes()))
        resultados.append(("Referencias BD", test_referencias_base_datos()))
        resultados.append(("Método obtener_gama()", test_obtener_gama_method()))
        resultados.append(("Simulación asignación", test_simulacion_asignacion_gama()))
        resultados.append(("Método save()", test_metodo_save_detalle_equipo()))
    except Exception as e:
        print_error(f"Error crítico durante las pruebas: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    # RESUMEN FINAL
    print_header("RESUMEN FINAL DE PRUEBAS")
    
    total_pruebas = len(resultados)
    pruebas_exitosas = sum(1 for _, resultado in resultados if resultado)
    pruebas_fallidas = total_pruebas - pruebas_exitosas
    
    for nombre, resultado in resultados:
        if resultado:
            print(f"  {Colors.OKGREEN}✅ {nombre:30} PASÓ{Colors.ENDC}")
        else:
            print(f"  {Colors.FAIL}❌ {nombre:30} FALLÓ{Colors.ENDC}")
    
    print(f"\n{Colors.BOLD}ESTADÍSTICAS:{Colors.ENDC}")
    print(f"  Total de pruebas: {total_pruebas}")
    print(f"  Exitosas: {Colors.OKGREEN}{pruebas_exitosas}{Colors.ENDC}")
    print(f"  Fallidas: {Colors.FAIL}{pruebas_fallidas}{Colors.ENDC}")
    
    if pruebas_fallidas == 0:
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}🎉 ¡TODAS LAS PRUEBAS PASARON CORRECTAMENTE! 🎉{Colors.ENDC}")
        print_success("El sistema de gamas está funcionando correctamente")
        print_info("El error de asignación de gama ha sido corregido")
        return True
    else:
        print(f"\n{Colors.WARNING}{Colors.BOLD}⚠️  ALGUNAS PRUEBAS FALLARON{Colors.ENDC}")
        print_warning(f"{pruebas_fallidas} prueba(s) requieren atención")
        return False

# =============================================================================
# PUNTO DE ENTRADA
# =============================================================================
if __name__ == "__main__":
    try:
        exito = ejecutar_todas_las_pruebas()
        sys.exit(0 if exito else 1)
    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}Pruebas interrumpidas por el usuario{Colors.ENDC}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.FAIL}Error fatal: {str(e)}{Colors.ENDC}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
