"""
Script para configurar grupos y permisos del sistema

Este script crea los grupos de Django segun los roles definidos
y asigna los permisos correspondientes a cada grupo.

SOPORTE MULTI-PAIS (v2.0):
    Ahora soporta un parametro db_alias para crear grupos en la
    base de datos de cualquier pais.

FORMA RECOMENDADA DE EJECUTAR:
    python scripts/manage_grupos.py                      # Mexico (default)
    python scripts/manage_grupos.py --database=argentina  # Argentina
    python scripts/manage_grupos.py --todos               # Todos los paises

O directamente:
    python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); exec(open('scripts/setup_grupos_permisos.py').read())"

IMPORTANTE: Ejecutar desde el directorio raiz del proyecto
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

# Importar modelos para obtener permisos
from inventario.models import Producto, Movimiento, Empleado, Sucursal
from servicio_tecnico.models import (
    OrdenServicio, DetalleEquipo, Cotizacion, HistorialOrden,
    ImagenOrden, VentaMostrador, SeguimientoPieza, EstadoRHITSO,
    SeguimientoRHITSO, IncidenciaRHITSO, ReferenciaGamaEquipo,
    PiezaCotizada, PiezaVentaMostrador
)
from scorecard.models import Incidencia, ComponenteEquipo, CategoriaIncidencia, ServicioRealizado
from almacen.models import (
    Proveedor, CategoriaAlmacen, ProductoAlmacen, CompraProducto, UnidadCompra,
    MovimientoAlmacen, SolicitudBaja, Auditoria, DiferenciaAuditoria,
    UnidadInventario, SolicitudCotizacion, LineaCotizacion, ImagenLineaCotizacion
)


# ============================================================================
# EXPLICACION PARA PRINCIPIANTES — .using() en Django
# ============================================================================
#
# Normalmente cuando haces Group.objects.get_or_create(name="Supervisor"),
# Django busca en la base de datos 'default' (Mexico).
#
# Para buscar en otra base de datos, usamos .using():
#     Group.objects.using('argentina').get_or_create(name="Supervisor")
#
# Esto le dice a Django: "Busca en la BD de Argentina, no en la de Mexico".
#
# IMPORTANTE: .using() solo afecta la lectura/escritura del objeto principal.
# Para relaciones ManyToMany (como grupo.permissions), tambien hay que
# especificar la BD. Por eso usamos grupo.permissions.set(...) que Django
# resuelve correctamente si el grupo fue creado con .using().
# ============================================================================


def crear_grupo(nombre, descripcion, db_alias='default'):
    """
    Crea o retorna un grupo existente en la BD especificada.

    EXPLICACION PARA PRINCIPIANTES:
    Antes esta funcion siempre creaba el grupo en la BD de Mexico.
    Ahora recibe db_alias para poder crear grupos en cualquier BD.

    Args:
        nombre: Nombre del grupo (ej: "Supervisor")
        descripcion: Descripcion del grupo (informativa, no se guarda)
        db_alias: Alias de la BD donde crear el grupo (ej: 'default', 'argentina')

    Returns:
        Group: Instancia del grupo creado o existente
    """
    grupo, created = Group.objects.using(db_alias).get_or_create(name=nombre)
    if created:
        print(f"  Grupo creado: {nombre}")
    else:
        print(f"  Grupo existente: {nombre}")
    return grupo


def obtener_permisos_modelo(modelo, acciones=['view', 'add', 'change', 'delete'], db_alias='default'):
    """
    Obtiene permisos de un modelo especifico desde la BD indicada.

    EXPLICACION PARA PRINCIPIANTES:
    Los permisos (Permission) y tipos de contenido (ContentType) son
    tablas que Django crea automaticamente cuando ejecutas migrate.
    Cada BD tiene su propia copia de estas tablas.

    Cuando buscamos permisos para Argentina, debemos buscarlos en
    la BD de Argentina, no en la de Mexico.

    Args:
        modelo: Clase del modelo (ej: OrdenServicio, Producto)
        acciones: Lista de acciones (ej: ['view', 'add', 'change', 'delete'])
        db_alias: Alias de la BD donde buscar los permisos

    Returns:
        list[Permission]: Lista de objetos Permission encontrados
    """
    # EXPLICACION: ContentType es la tabla que registra todos los modelos
    # de Django. Cada modelo tiene un ContentType unico. Necesitamos
    # buscar el ContentType en la MISMA BD donde vamos a asignar permisos.
    #
    # EXPLICACION PARA PRINCIPIANTES:
    # Usamos db_manager(db_alias) en lugar de using(db_alias) porque
    # get_for_model() es un metodo especial del Manager de ContentType,
    # no esta disponible en un QuerySet normal. db_manager() nos da
    # acceso al Manager completo pero apuntando a la BD correcta.
    content_type = ContentType.objects.db_manager(db_alias).get_for_model(modelo)
    permisos = []
    for accion in acciones:
        codename = f"{accion}_{modelo._meta.model_name}"
        try:
            permiso = Permission.objects.using(db_alias).get(
                codename=codename,
                content_type=content_type
            )
            permisos.append(permiso)
        except Permission.DoesNotExist:
            print(f"  Permiso no encontrado: {codename}")
    return permisos


def setup_grupos_y_permisos(db_alias='default'):
    """
    Configuracion completa de grupos y permisos para una BD especifica.

    EXPLICACION PARA PRINCIPIANTES:
    Esta funcion crea los 9 grupos del sistema y asigna los permisos
    correspondientes a cada uno. Ahora recibe db_alias para poder
    ejecutarse contra la BD de cualquier pais.

    Uso:
        setup_grupos_y_permisos()                 # Mexico (default)
        setup_grupos_y_permisos('argentina')      # Argentina

    Args:
        db_alias: Alias de la BD ('default', 'mexico', 'argentina', etc.)
    """

    # Obtener nombre legible del pais para los mensajes
    nombres_bd = {
        'default': 'Mexico (default)',
        'mexico': 'Mexico',
        'argentina': 'Argentina',
    }
    nombre_bd = nombres_bd.get(db_alias, db_alias)

    print("\n" + "="*70)
    print(f"CONFIGURACION DE GRUPOS Y PERMISOS — {nombre_bd}")
    print(f"Base de datos: {db_alias}")
    print("="*70 + "\n")

    # ========== PERMISOS PERSONALIZADOS ==========
    # Obtener permisos personalizados de dashboards
    ct_ordenservicio = ContentType.objects.db_manager(db_alias).get_for_model(OrdenServicio)

    try:
        permiso_dashboard_gerencial = Permission.objects.using(db_alias).get(
            codename='view_dashboard_gerencial',
            content_type=ct_ordenservicio
        )
        permiso_dashboard_seguimiento = Permission.objects.using(db_alias).get(
            codename='view_dashboard_seguimiento',
            content_type=ct_ordenservicio
        )
        print("  Permisos personalizados encontrados")
    except Permission.DoesNotExist:
        print("  Permisos personalizados no encontrados. Ejecuta las migraciones primero.")
        permiso_dashboard_gerencial = None
        permiso_dashboard_seguimiento = None

    # ========== SUPERVISOR ==========
    print("  Configurando grupo: SUPERVISOR")
    grupo_supervisor = crear_grupo("Supervisor", "Acceso general al sistema excepto configuraciones", db_alias)
    permisos_supervisor = []

    # Inventario - Acceso completo
    permisos_supervisor.extend(obtener_permisos_modelo(Producto, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(Movimiento, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(Empleado, ['view', 'add', 'change'], db_alias))  # Sin delete
    permisos_supervisor.extend(obtener_permisos_modelo(Sucursal, db_alias=db_alias))

    # Servicio Tecnico - Acceso completo
    permisos_supervisor.extend(obtener_permisos_modelo(OrdenServicio, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(DetalleEquipo, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(Cotizacion, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(HistorialOrden, ['view', 'add'], db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(ImagenOrden, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(SeguimientoPieza, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(EstadoRHITSO, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(SeguimientoRHITSO, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(IncidenciaRHITSO, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(VentaMostrador, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(ReferenciaGamaEquipo, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(PiezaCotizada, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(PiezaVentaMostrador, db_alias=db_alias))

    # Permisos personalizados de dashboards (solo gerenciales)
    if permiso_dashboard_gerencial:
        permisos_supervisor.append(permiso_dashboard_gerencial)
    if permiso_dashboard_seguimiento:
        permisos_supervisor.append(permiso_dashboard_seguimiento)

    # Scorecard - Acceso completo
    permisos_supervisor.extend(obtener_permisos_modelo(Incidencia, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(ComponenteEquipo, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(CategoriaIncidencia, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(ServicioRealizado, db_alias=db_alias))

    # Almacen - Acceso completo
    permisos_supervisor.extend(obtener_permisos_modelo(Proveedor, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(CategoriaAlmacen, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(ProductoAlmacen, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(CompraProducto, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(UnidadCompra, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(MovimientoAlmacen, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(SolicitudBaja, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(Auditoria, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(DiferenciaAuditoria, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(UnidadInventario, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(SolicitudCotizacion, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(LineaCotizacion, db_alias=db_alias))
    permisos_supervisor.extend(obtener_permisos_modelo(ImagenLineaCotizacion, db_alias=db_alias))

    grupo_supervisor.permissions.set(permisos_supervisor)
    print(f"     {len(permisos_supervisor)} permisos asignados\n")

    # ========== INSPECTOR ==========
    print("  Configurando grupo: INSPECTOR")
    grupo_inspector = crear_grupo("Inspector", "Acceso general al sistema excepto configuraciones", db_alias)
    # Inspector tiene los mismos permisos que Supervisor
    grupo_inspector.permissions.set(permisos_supervisor)
    print(f"     {len(permisos_supervisor)} permisos asignados\n")

    # ========== DISPATCHER ==========
    print("  Configurando grupo: DISPATCHER")
    grupo_dispatcher = crear_grupo("Dispatcher", "Solo consulta en servicio tecnico", db_alias)
    permisos_dispatcher = []

    # Servicio Tecnico - Solo lectura
    permisos_dispatcher.extend(obtener_permisos_modelo(OrdenServicio, ['view'], db_alias))
    permisos_dispatcher.extend(obtener_permisos_modelo(DetalleEquipo, ['view'], db_alias))
    permisos_dispatcher.extend(obtener_permisos_modelo(Cotizacion, ['view'], db_alias))
    permisos_dispatcher.extend(obtener_permisos_modelo(HistorialOrden, ['view'], db_alias))
    permisos_dispatcher.extend(obtener_permisos_modelo(ImagenOrden, ['view'], db_alias))
    permisos_dispatcher.extend(obtener_permisos_modelo(SeguimientoPieza, ['view'], db_alias))
    permisos_dispatcher.extend(obtener_permisos_modelo(EstadoRHITSO, ['view'], db_alias))
    permisos_dispatcher.extend(obtener_permisos_modelo(SeguimientoRHITSO, ['view'], db_alias))
    permisos_dispatcher.extend(obtener_permisos_modelo(IncidenciaRHITSO, ['view'], db_alias))
    permisos_dispatcher.extend(obtener_permisos_modelo(VentaMostrador, ['view'], db_alias))
    permisos_dispatcher.extend(obtener_permisos_modelo(ReferenciaGamaEquipo, ['view'], db_alias))
    permisos_dispatcher.extend(obtener_permisos_modelo(PiezaCotizada, ['view'], db_alias))
    permisos_dispatcher.extend(obtener_permisos_modelo(PiezaVentaMostrador, ['view'], db_alias))

    # Almacen - SIN ACCESO (Dispatcher no necesita ver modulo de almacen)
    # El Dispatcher solo gestiona ordenes de servicio, no inventario

    grupo_dispatcher.permissions.set(permisos_dispatcher)
    print(f"     {len(permisos_dispatcher)} permisos asignados\n")

    # ========== COMPRAS ==========
    print("  Configurando grupo: COMPRAS")
    grupo_compras = crear_grupo("Compras", "Acceso a servicio tecnico y almacen", db_alias)
    permisos_compras = []

    # Servicio Tecnico - Acceso completo
    permisos_compras.extend(obtener_permisos_modelo(OrdenServicio, db_alias=db_alias))
    permisos_compras.extend(obtener_permisos_modelo(DetalleEquipo, db_alias=db_alias))
    permisos_compras.extend(obtener_permisos_modelo(Cotizacion, db_alias=db_alias))
    permisos_compras.extend(obtener_permisos_modelo(HistorialOrden, ['view', 'add'], db_alias))
    permisos_compras.extend(obtener_permisos_modelo(ImagenOrden, db_alias=db_alias))
    permisos_compras.extend(obtener_permisos_modelo(SeguimientoPieza, db_alias=db_alias))
    permisos_compras.extend(obtener_permisos_modelo(EstadoRHITSO, db_alias=db_alias))
    permisos_compras.extend(obtener_permisos_modelo(SeguimientoRHITSO, db_alias=db_alias))
    permisos_compras.extend(obtener_permisos_modelo(IncidenciaRHITSO, db_alias=db_alias))
    permisos_compras.extend(obtener_permisos_modelo(VentaMostrador, db_alias=db_alias))
    permisos_compras.extend(obtener_permisos_modelo(ReferenciaGamaEquipo, db_alias=db_alias))
    permisos_compras.extend(obtener_permisos_modelo(PiezaCotizada, db_alias=db_alias))
    permisos_compras.extend(obtener_permisos_modelo(PiezaVentaMostrador, db_alias=db_alias))

    # Almacen - Acceso completo
    permisos_compras.extend(obtener_permisos_modelo(Proveedor, db_alias=db_alias))
    permisos_compras.extend(obtener_permisos_modelo(CategoriaAlmacen, db_alias=db_alias))
    permisos_compras.extend(obtener_permisos_modelo(ProductoAlmacen, db_alias=db_alias))
    permisos_compras.extend(obtener_permisos_modelo(CompraProducto, db_alias=db_alias))
    permisos_compras.extend(obtener_permisos_modelo(UnidadCompra, db_alias=db_alias))
    permisos_compras.extend(obtener_permisos_modelo(MovimientoAlmacen, db_alias=db_alias))
    permisos_compras.extend(obtener_permisos_modelo(SolicitudBaja, db_alias=db_alias))
    permisos_compras.extend(obtener_permisos_modelo(Auditoria, db_alias=db_alias))
    permisos_compras.extend(obtener_permisos_modelo(DiferenciaAuditoria, db_alias=db_alias))
    permisos_compras.extend(obtener_permisos_modelo(UnidadInventario, db_alias=db_alias))
    permisos_compras.extend(obtener_permisos_modelo(SolicitudCotizacion, db_alias=db_alias))
    permisos_compras.extend(obtener_permisos_modelo(LineaCotizacion, db_alias=db_alias))
    permisos_compras.extend(obtener_permisos_modelo(ImagenLineaCotizacion, db_alias=db_alias))

    grupo_compras.permissions.set(permisos_compras)
    print(f"     {len(permisos_compras)} permisos asignados\n")

    # ========== RECEPCIONISTA ==========
    print("  Configurando grupo: RECEPCIONISTA")
    grupo_recepcionista = crear_grupo("Recepcionista", "Acceso a servicio tecnico y almacen", db_alias)
    permisos_recepcionista = []

    # Servicio Tecnico - Acceso completo
    permisos_recepcionista.extend(obtener_permisos_modelo(OrdenServicio, db_alias=db_alias))
    permisos_recepcionista.extend(obtener_permisos_modelo(DetalleEquipo, db_alias=db_alias))
    permisos_recepcionista.extend(obtener_permisos_modelo(Cotizacion, ['view'], db_alias))  # Solo vista
    permisos_recepcionista.extend(obtener_permisos_modelo(HistorialOrden, ['view', 'add'], db_alias))
    permisos_recepcionista.extend(obtener_permisos_modelo(ImagenOrden, db_alias=db_alias))
    permisos_recepcionista.extend(obtener_permisos_modelo(SeguimientoPieza, ['view', 'add'], db_alias))
    permisos_recepcionista.extend(obtener_permisos_modelo(EstadoRHITSO, ['view', 'add'], db_alias))
    permisos_recepcionista.extend(obtener_permisos_modelo(SeguimientoRHITSO, ['view', 'add'], db_alias))
    permisos_recepcionista.extend(obtener_permisos_modelo(IncidenciaRHITSO, ['view', 'add'], db_alias))
    permisos_recepcionista.extend(obtener_permisos_modelo(VentaMostrador, db_alias=db_alias))
    permisos_recepcionista.extend(obtener_permisos_modelo(ReferenciaGamaEquipo, ['view'], db_alias))  # Para autocompletado
    permisos_recepcionista.extend(obtener_permisos_modelo(PiezaCotizada, ['view'], db_alias))  # Solo vista
    permisos_recepcionista.extend(obtener_permisos_modelo(PiezaVentaMostrador, db_alias=db_alias))  # Acceso completo

    # Almacen - Acceso limitado
    permisos_recepcionista.extend(obtener_permisos_modelo(ProductoAlmacen, ['view', 'add', 'change'], db_alias))
    permisos_recepcionista.extend(obtener_permisos_modelo(Proveedor, ['view'], db_alias))
    permisos_recepcionista.extend(obtener_permisos_modelo(CategoriaAlmacen, ['view'], db_alias))
    permisos_recepcionista.extend(obtener_permisos_modelo(CompraProducto, ['view'], db_alias))
    permisos_recepcionista.extend(obtener_permisos_modelo(UnidadCompra, ['view'], db_alias))
    permisos_recepcionista.extend(obtener_permisos_modelo(MovimientoAlmacen, ['view', 'add'], db_alias))
    permisos_recepcionista.extend(obtener_permisos_modelo(SolicitudBaja, ['view', 'add', 'change'], db_alias))
    permisos_recepcionista.extend(obtener_permisos_modelo(Auditoria, ['view'], db_alias))
    permisos_recepcionista.extend(obtener_permisos_modelo(DiferenciaAuditoria, ['view'], db_alias))
    permisos_recepcionista.extend(obtener_permisos_modelo(UnidadInventario, ['view', 'add', 'change'], db_alias))
    permisos_recepcionista.extend(obtener_permisos_modelo(SolicitudCotizacion, ['view', 'add', 'change'], db_alias))
    permisos_recepcionista.extend(obtener_permisos_modelo(LineaCotizacion, ['view', 'add', 'change'], db_alias))
    permisos_recepcionista.extend(obtener_permisos_modelo(ImagenLineaCotizacion, ['view', 'add'], db_alias))

    grupo_recepcionista.permissions.set(permisos_recepcionista)
    print(f"     {len(permisos_recepcionista)} permisos asignados\n")

    # ========== GERENTE OPERACIONAL ==========
    print("  Configurando grupo: GERENTE OPERACIONAL")
    grupo_gerente_op = crear_grupo("Gerente Operacional", "Acceso general al sistema", db_alias)
    # Gerente Operacional tiene los mismos permisos que Supervisor
    grupo_gerente_op.permissions.set(permisos_supervisor)
    print(f"     {len(permisos_supervisor)} permisos asignados\n")

    # ========== GERENTE GENERAL ==========
    print("  Configurando grupo: GERENTE GENERAL")
    grupo_gerente_gral = crear_grupo("Gerente General", "Acceso general al sistema", db_alias)
    # Gerente General tiene los mismos permisos que Supervisor
    grupo_gerente_gral.permissions.set(permisos_supervisor)
    print(f"     {len(permisos_supervisor)} permisos asignados\n")

    # ========== TÉCNICO ==========
    print("  Configurando grupo: TÉCNICO")
    grupo_tecnico = crear_grupo("Técnico", "Acceso a servicio técnico y almacén", db_alias)
    permisos_tecnico = []

    # Servicio Tecnico - Acceso completo excepto eliminar ordenes
    permisos_tecnico.extend(obtener_permisos_modelo(OrdenServicio, ['view', 'add', 'change'], db_alias))
    permisos_tecnico.extend(obtener_permisos_modelo(DetalleEquipo, ['view', 'add', 'change'], db_alias))
    permisos_tecnico.extend(obtener_permisos_modelo(Cotizacion, ['view', 'add', 'change'], db_alias))
    permisos_tecnico.extend(obtener_permisos_modelo(HistorialOrden, ['view', 'add'], db_alias))
    permisos_tecnico.extend(obtener_permisos_modelo(ImagenOrden, db_alias=db_alias))
    permisos_tecnico.extend(obtener_permisos_modelo(SeguimientoPieza, ['view', 'add', 'change'], db_alias))
    permisos_tecnico.extend(obtener_permisos_modelo(EstadoRHITSO, ['view', 'add', 'change'], db_alias))
    permisos_tecnico.extend(obtener_permisos_modelo(SeguimientoRHITSO, ['view', 'add', 'change'], db_alias))
    permisos_tecnico.extend(obtener_permisos_modelo(IncidenciaRHITSO, ['view', 'add', 'change'], db_alias))
    permisos_tecnico.extend(obtener_permisos_modelo(VentaMostrador, db_alias=db_alias))
    permisos_tecnico.extend(obtener_permisos_modelo(ReferenciaGamaEquipo, ['view'], db_alias))
    permisos_tecnico.extend(obtener_permisos_modelo(PiezaCotizada, ['view', 'add', 'change'], db_alias))
    permisos_tecnico.extend(obtener_permisos_modelo(PiezaVentaMostrador, ['view', 'add', 'change'], db_alias))

    # Almacen - Solo consulta y solicitudes
    permisos_tecnico.extend(obtener_permisos_modelo(ProductoAlmacen, ['view'], db_alias))
    permisos_tecnico.extend(obtener_permisos_modelo(CategoriaAlmacen, ['view'], db_alias))
    permisos_tecnico.extend(obtener_permisos_modelo(UnidadInventario, ['view'], db_alias))
    permisos_tecnico.extend(obtener_permisos_modelo(MovimientoAlmacen, ['view', 'add'], db_alias))
    permisos_tecnico.extend(obtener_permisos_modelo(SolicitudBaja, ['view', 'add', 'change'], db_alias))
    permisos_tecnico.extend(obtener_permisos_modelo(SolicitudCotizacion, ['view'], db_alias))

    grupo_tecnico.permissions.set(permisos_tecnico)
    print(f"     {len(permisos_tecnico)} permisos asignados\n")

    # ========== ALMACENISTA ==========
    print("  Configurando grupo: ALMACENISTA")
    grupo_almacenista = crear_grupo("Almacenista", "Acceso a almacen y servicio tecnico", db_alias)
    permisos_almacenista = []

    # Almacen - Acceso completo a TODOS los modelos
    permisos_almacenista.extend(obtener_permisos_modelo(Proveedor, db_alias=db_alias))
    permisos_almacenista.extend(obtener_permisos_modelo(CategoriaAlmacen, db_alias=db_alias))
    permisos_almacenista.extend(obtener_permisos_modelo(ProductoAlmacen, db_alias=db_alias))
    permisos_almacenista.extend(obtener_permisos_modelo(CompraProducto, db_alias=db_alias))
    permisos_almacenista.extend(obtener_permisos_modelo(UnidadCompra, db_alias=db_alias))
    permisos_almacenista.extend(obtener_permisos_modelo(MovimientoAlmacen, db_alias=db_alias))
    permisos_almacenista.extend(obtener_permisos_modelo(SolicitudBaja, db_alias=db_alias))
    permisos_almacenista.extend(obtener_permisos_modelo(Auditoria, db_alias=db_alias))
    permisos_almacenista.extend(obtener_permisos_modelo(DiferenciaAuditoria, db_alias=db_alias))
    permisos_almacenista.extend(obtener_permisos_modelo(UnidadInventario, db_alias=db_alias))
    permisos_almacenista.extend(obtener_permisos_modelo(SolicitudCotizacion, db_alias=db_alias))
    permisos_almacenista.extend(obtener_permisos_modelo(LineaCotizacion, db_alias=db_alias))
    permisos_almacenista.extend(obtener_permisos_modelo(ImagenLineaCotizacion, db_alias=db_alias))

    # Servicio Tecnico - Solo consulta
    permisos_almacenista.extend(obtener_permisos_modelo(OrdenServicio, ['view'], db_alias))
    permisos_almacenista.extend(obtener_permisos_modelo(DetalleEquipo, ['view'], db_alias))
    permisos_almacenista.extend(obtener_permisos_modelo(Cotizacion, ['view'], db_alias))
    permisos_almacenista.extend(obtener_permisos_modelo(VentaMostrador, ['view'], db_alias))
    permisos_almacenista.extend(obtener_permisos_modelo(ReferenciaGamaEquipo, ['view'], db_alias))
    permisos_almacenista.extend(obtener_permisos_modelo(PiezaCotizada, ['view'], db_alias))
    permisos_almacenista.extend(obtener_permisos_modelo(PiezaVentaMostrador, ['view'], db_alias))

    grupo_almacenista.permissions.set(permisos_almacenista)
    print(f"     {len(permisos_almacenista)} permisos asignados\n")

    # ========== RESUMEN ==========
    print("="*70)
    print(f"RESUMEN DE GRUPOS — {nombre_bd}")
    print("="*70)
    grupos = Group.objects.using(db_alias).all().order_by('name')
    for grupo in grupos:
        print(f"  {grupo.name}: {grupo.permissions.count()} permisos")
    print("\n" + "="*70)
    print(f"  CONFIGURACION COMPLETADA — {nombre_bd}")
    print("="*70 + "\n")


if __name__ == '__main__':
    setup_grupos_y_permisos()
