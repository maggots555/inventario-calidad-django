"""
Script para configurar grupos y permisos del sistema

Este script crea los grupos de Django según los roles definidos
y asigna los permisos correspondientes a cada grupo.

FORMA RECOMENDADA DE EJECUTAR:
    python scripts/manage_grupos.py

O directamente:
    python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); exec(open('scripts/setup_grupos_permisos.py').read())"

IMPORTANTE: Ejecutar desde el directorio raíz del proyecto
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


def crear_grupo(nombre, descripcion):
    """Crea o retorna un grupo existente"""
    grupo, created = Group.objects.get_or_create(name=nombre)
    if created:
        print(f"✅ Grupo creado: {nombre}")
    else:
        print(f"♻️  Grupo existente: {nombre}")
    return grupo


def obtener_permisos_modelo(modelo, acciones=['view', 'add', 'change', 'delete']):
    """Obtiene permisos de un modelo específico"""
    content_type = ContentType.objects.get_for_model(modelo)
    permisos = []
    for accion in acciones:
        codename = f"{accion}_{modelo._meta.model_name}"
        try:
            permiso = Permission.objects.get(
                codename=codename,
                content_type=content_type
            )
            permisos.append(permiso)
        except Permission.DoesNotExist:
            print(f"⚠️  Permiso no encontrado: {codename}")
    return permisos


def setup_grupos_y_permisos():
    """Configuración completa de grupos y permisos"""
    
    print("\n" + "="*70)
    print("CONFIGURACIÓN DE GRUPOS Y PERMISOS DEL SISTEMA")
    print("="*70 + "\n")
    
    # ========== PERMISOS PERSONALIZADOS ==========
    # Obtener permisos personalizados de dashboards
    from django.contrib.contenttypes.models import ContentType
    ct_ordenservicio = ContentType.objects.get_for_model(OrdenServicio)
    
    try:
        permiso_dashboard_gerencial = Permission.objects.get(
            codename='view_dashboard_gerencial',
            content_type=ct_ordenservicio
        )
        permiso_dashboard_seguimiento = Permission.objects.get(
            codename='view_dashboard_seguimiento',
            content_type=ct_ordenservicio
        )
        print("✅ Permisos personalizados encontrados")
    except Permission.DoesNotExist:
        print("⚠️  Permisos personalizados no encontrados. Ejecuta las migraciones primero.")
        permiso_dashboard_gerencial = None
        permiso_dashboard_seguimiento = None
    
    # ========== SUPERVISOR ==========
    print("📋 Configurando grupo: SUPERVISOR")
    grupo_supervisor = crear_grupo("Supervisor", "Acceso general al sistema excepto configuraciones")
    permisos_supervisor = []
    
    # Inventario - Acceso completo
    permisos_supervisor.extend(obtener_permisos_modelo(Producto))
    permisos_supervisor.extend(obtener_permisos_modelo(Movimiento))
    permisos_supervisor.extend(obtener_permisos_modelo(Empleado, ['view', 'add', 'change']))  # Sin delete
    permisos_supervisor.extend(obtener_permisos_modelo(Sucursal))
    
    # Servicio Técnico - Acceso completo
    permisos_supervisor.extend(obtener_permisos_modelo(OrdenServicio))
    permisos_supervisor.extend(obtener_permisos_modelo(DetalleEquipo))
    permisos_supervisor.extend(obtener_permisos_modelo(Cotizacion))
    permisos_supervisor.extend(obtener_permisos_modelo(HistorialOrden, ['view', 'add']))
    permisos_supervisor.extend(obtener_permisos_modelo(ImagenOrden))
    permisos_supervisor.extend(obtener_permisos_modelo(SeguimientoPieza))
    permisos_supervisor.extend(obtener_permisos_modelo(EstadoRHITSO))
    permisos_supervisor.extend(obtener_permisos_modelo(SeguimientoRHITSO))
    permisos_supervisor.extend(obtener_permisos_modelo(IncidenciaRHITSO))
    permisos_supervisor.extend(obtener_permisos_modelo(VentaMostrador))
    permisos_supervisor.extend(obtener_permisos_modelo(ReferenciaGamaEquipo))
    permisos_supervisor.extend(obtener_permisos_modelo(PiezaCotizada))
    permisos_supervisor.extend(obtener_permisos_modelo(PiezaVentaMostrador))
    
    # Permisos personalizados de dashboards (solo gerenciales)
    if permiso_dashboard_gerencial:
        permisos_supervisor.append(permiso_dashboard_gerencial)
    if permiso_dashboard_seguimiento:
        permisos_supervisor.append(permiso_dashboard_seguimiento)
    
    # Scorecard - Acceso completo
    permisos_supervisor.extend(obtener_permisos_modelo(Incidencia))
    permisos_supervisor.extend(obtener_permisos_modelo(ComponenteEquipo))
    permisos_supervisor.extend(obtener_permisos_modelo(CategoriaIncidencia))
    permisos_supervisor.extend(obtener_permisos_modelo(ServicioRealizado))
    
    # Almacén - Acceso completo
    permisos_supervisor.extend(obtener_permisos_modelo(Proveedor))
    permisos_supervisor.extend(obtener_permisos_modelo(CategoriaAlmacen))
    permisos_supervisor.extend(obtener_permisos_modelo(ProductoAlmacen))
    permisos_supervisor.extend(obtener_permisos_modelo(CompraProducto))
    permisos_supervisor.extend(obtener_permisos_modelo(UnidadCompra))
    permisos_supervisor.extend(obtener_permisos_modelo(MovimientoAlmacen))
    permisos_supervisor.extend(obtener_permisos_modelo(SolicitudBaja))
    permisos_supervisor.extend(obtener_permisos_modelo(Auditoria))
    permisos_supervisor.extend(obtener_permisos_modelo(DiferenciaAuditoria))
    permisos_supervisor.extend(obtener_permisos_modelo(UnidadInventario))
    permisos_supervisor.extend(obtener_permisos_modelo(SolicitudCotizacion))
    permisos_supervisor.extend(obtener_permisos_modelo(LineaCotizacion))
    permisos_supervisor.extend(obtener_permisos_modelo(ImagenLineaCotizacion))
    
    grupo_supervisor.permissions.set(permisos_supervisor)
    print(f"   ✅ {len(permisos_supervisor)} permisos asignados\n")
    
    # ========== INSPECTOR ==========
    print("📋 Configurando grupo: INSPECTOR")
    grupo_inspector = crear_grupo("Inspector", "Acceso general al sistema excepto configuraciones")
    # Inspector tiene los mismos permisos que Supervisor
    grupo_inspector.permissions.set(permisos_supervisor)
    print(f"   ✅ {len(permisos_supervisor)} permisos asignados\n")
    
    # ========== DISPATCHER ==========
    print("📋 Configurando grupo: DISPATCHER")
    grupo_dispatcher = crear_grupo("Dispatcher", "Solo consulta en servicio técnico")
    permisos_dispatcher = []
    
    # Servicio Técnico - Solo lectura
    permisos_dispatcher.extend(obtener_permisos_modelo(OrdenServicio, ['view']))
    permisos_dispatcher.extend(obtener_permisos_modelo(DetalleEquipo, ['view']))
    permisos_dispatcher.extend(obtener_permisos_modelo(Cotizacion, ['view']))
    permisos_dispatcher.extend(obtener_permisos_modelo(HistorialOrden, ['view']))
    permisos_dispatcher.extend(obtener_permisos_modelo(ImagenOrden, ['view']))
    permisos_dispatcher.extend(obtener_permisos_modelo(SeguimientoPieza, ['view']))
    permisos_dispatcher.extend(obtener_permisos_modelo(EstadoRHITSO, ['view']))
    permisos_dispatcher.extend(obtener_permisos_modelo(SeguimientoRHITSO, ['view']))
    permisos_dispatcher.extend(obtener_permisos_modelo(IncidenciaRHITSO, ['view']))
    permisos_dispatcher.extend(obtener_permisos_modelo(VentaMostrador, ['view']))
    permisos_dispatcher.extend(obtener_permisos_modelo(ReferenciaGamaEquipo, ['view']))
    permisos_dispatcher.extend(obtener_permisos_modelo(PiezaCotizada, ['view']))
    permisos_dispatcher.extend(obtener_permisos_modelo(PiezaVentaMostrador, ['view']))
    
    # Almacén - SIN ACCESO (Dispatcher no necesita ver módulo de almacén)
    # El Dispatcher solo gestiona órdenes de servicio, no inventario
    
    grupo_dispatcher.permissions.set(permisos_dispatcher)
    print(f"   ✅ {len(permisos_dispatcher)} permisos asignados\n")
    
    # ========== COMPRAS ==========
    print("📋 Configurando grupo: COMPRAS")
    grupo_compras = crear_grupo("Compras", "Acceso a servicio técnico y almacén")
    permisos_compras = []
    
    # Servicio Técnico - Acceso completo
    permisos_compras.extend(obtener_permisos_modelo(OrdenServicio))
    permisos_compras.extend(obtener_permisos_modelo(DetalleEquipo))
    permisos_compras.extend(obtener_permisos_modelo(Cotizacion))
    permisos_compras.extend(obtener_permisos_modelo(HistorialOrden, ['view', 'add']))
    permisos_compras.extend(obtener_permisos_modelo(ImagenOrden))
    permisos_compras.extend(obtener_permisos_modelo(SeguimientoPieza))
    permisos_compras.extend(obtener_permisos_modelo(EstadoRHITSO))
    permisos_compras.extend(obtener_permisos_modelo(SeguimientoRHITSO))
    permisos_compras.extend(obtener_permisos_modelo(IncidenciaRHITSO))
    permisos_compras.extend(obtener_permisos_modelo(VentaMostrador))
    permisos_compras.extend(obtener_permisos_modelo(ReferenciaGamaEquipo))
    permisos_compras.extend(obtener_permisos_modelo(PiezaCotizada))
    permisos_compras.extend(obtener_permisos_modelo(PiezaVentaMostrador))
    
    # Almacén - Acceso completo
    permisos_compras.extend(obtener_permisos_modelo(Proveedor))
    permisos_compras.extend(obtener_permisos_modelo(CategoriaAlmacen))
    permisos_compras.extend(obtener_permisos_modelo(ProductoAlmacen))
    permisos_compras.extend(obtener_permisos_modelo(CompraProducto))
    permisos_compras.extend(obtener_permisos_modelo(UnidadCompra))
    permisos_compras.extend(obtener_permisos_modelo(MovimientoAlmacen))
    permisos_compras.extend(obtener_permisos_modelo(SolicitudBaja))
    permisos_compras.extend(obtener_permisos_modelo(Auditoria))
    permisos_compras.extend(obtener_permisos_modelo(DiferenciaAuditoria))
    permisos_compras.extend(obtener_permisos_modelo(UnidadInventario))
    permisos_compras.extend(obtener_permisos_modelo(SolicitudCotizacion))
    permisos_compras.extend(obtener_permisos_modelo(LineaCotizacion))
    permisos_compras.extend(obtener_permisos_modelo(ImagenLineaCotizacion))
    
    grupo_compras.permissions.set(permisos_compras)
    print(f"   ✅ {len(permisos_compras)} permisos asignados\n")
    
    # ========== RECEPCIONISTA ==========
    print("📋 Configurando grupo: RECEPCIONISTA")
    grupo_recepcionista = crear_grupo("Recepcionista", "Acceso a servicio técnico y almacén")
    permisos_recepcionista = []
    
    # Servicio Técnico - Acceso completo
    permisos_recepcionista.extend(obtener_permisos_modelo(OrdenServicio))
    permisos_recepcionista.extend(obtener_permisos_modelo(DetalleEquipo))
    permisos_recepcionista.extend(obtener_permisos_modelo(Cotizacion, ['view']))  # Solo vista
    permisos_recepcionista.extend(obtener_permisos_modelo(HistorialOrden, ['view', 'add']))
    permisos_recepcionista.extend(obtener_permisos_modelo(ImagenOrden))
    permisos_recepcionista.extend(obtener_permisos_modelo(SeguimientoPieza, ['view', 'add']))
    permisos_recepcionista.extend(obtener_permisos_modelo(EstadoRHITSO, ['view', 'add']))
    permisos_recepcionista.extend(obtener_permisos_modelo(SeguimientoRHITSO, ['view', 'add']))
    permisos_recepcionista.extend(obtener_permisos_modelo(IncidenciaRHITSO, ['view', 'add']))
    permisos_recepcionista.extend(obtener_permisos_modelo(VentaMostrador))
    permisos_recepcionista.extend(obtener_permisos_modelo(ReferenciaGamaEquipo, ['view']))  # CRÍTICO: Para autocompletado de modelos
    permisos_recepcionista.extend(obtener_permisos_modelo(PiezaCotizada, ['view']))  # Solo vista de piezas cotizadas
    permisos_recepcionista.extend(obtener_permisos_modelo(PiezaVentaMostrador))  # Acceso completo a piezas venta mostrador
    
    # Almacén - Acceso limitado
    permisos_recepcionista.extend(obtener_permisos_modelo(ProductoAlmacen, ['view', 'add', 'change']))  # Casi completo
    permisos_recepcionista.extend(obtener_permisos_modelo(Proveedor, ['view']))  # Solo consulta
    permisos_recepcionista.extend(obtener_permisos_modelo(CategoriaAlmacen, ['view']))  # Solo consulta
    permisos_recepcionista.extend(obtener_permisos_modelo(CompraProducto, ['view']))  # Solo consulta
    permisos_recepcionista.extend(obtener_permisos_modelo(UnidadCompra, ['view']))  # Solo consulta
    permisos_recepcionista.extend(obtener_permisos_modelo(MovimientoAlmacen, ['view', 'add']))  # Puede registrar movimientos
    permisos_recepcionista.extend(obtener_permisos_modelo(SolicitudBaja, ['view', 'add', 'change']))  # Gestiona solicitudes
    permisos_recepcionista.extend(obtener_permisos_modelo(Auditoria, ['view']))  # Solo consulta
    permisos_recepcionista.extend(obtener_permisos_modelo(DiferenciaAuditoria, ['view']))  # Solo consulta
    permisos_recepcionista.extend(obtener_permisos_modelo(UnidadInventario, ['view', 'add', 'change']))  # Gestiona unidades
    permisos_recepcionista.extend(obtener_permisos_modelo(SolicitudCotizacion, ['view', 'add', 'change']))  # Gestiona cotizaciones
    permisos_recepcionista.extend(obtener_permisos_modelo(LineaCotizacion, ['view', 'add', 'change']))  # Gestiona líneas
    permisos_recepcionista.extend(obtener_permisos_modelo(ImagenLineaCotizacion, ['view', 'add']))  # Sube imágenes
    
    grupo_recepcionista.permissions.set(permisos_recepcionista)
    print(f"   ✅ {len(permisos_recepcionista)} permisos asignados\n")
    
    # ========== GERENTE OPERACIONAL ==========
    print("📋 Configurando grupo: GERENTE OPERACIONAL")
    grupo_gerente_op = crear_grupo("Gerente Operacional", "Acceso general al sistema")
    # Gerente Operacional tiene los mismos permisos que Supervisor
    grupo_gerente_op.permissions.set(permisos_supervisor)
    print(f"   ✅ {len(permisos_supervisor)} permisos asignados\n")
    
    # ========== GERENTE GENERAL ==========
    print("📋 Configurando grupo: GERENTE GENERAL")
    grupo_gerente_gral = crear_grupo("Gerente General", "Acceso general al sistema")
    # Gerente General tiene los mismos permisos que Supervisor
    grupo_gerente_gral.permissions.set(permisos_supervisor)
    print(f"   ✅ {len(permisos_supervisor)} permisos asignados\n")
    
    # ========== TÉCNICO ==========
    print("📋 Configurando grupo: TÉCNICO")
    grupo_tecnico = crear_grupo("Técnico", "Acceso a servicio técnico y almacén")
    permisos_tecnico = []
    
    # Servicio Técnico - Acceso completo excepto eliminar órdenes
    permisos_tecnico.extend(obtener_permisos_modelo(OrdenServicio, ['view', 'add', 'change']))
    permisos_tecnico.extend(obtener_permisos_modelo(DetalleEquipo, ['view', 'add', 'change']))
    permisos_tecnico.extend(obtener_permisos_modelo(Cotizacion, ['view', 'add', 'change']))
    permisos_tecnico.extend(obtener_permisos_modelo(HistorialOrden, ['view', 'add']))
    permisos_tecnico.extend(obtener_permisos_modelo(ImagenOrden))
    permisos_tecnico.extend(obtener_permisos_modelo(SeguimientoPieza, ['view', 'add', 'change']))
    permisos_tecnico.extend(obtener_permisos_modelo(EstadoRHITSO, ['view', 'add', 'change']))
    permisos_tecnico.extend(obtener_permisos_modelo(SeguimientoRHITSO, ['view', 'add', 'change']))
    permisos_tecnico.extend(obtener_permisos_modelo(IncidenciaRHITSO, ['view', 'add', 'change']))
    permisos_tecnico.extend(obtener_permisos_modelo(VentaMostrador))
    permisos_tecnico.extend(obtener_permisos_modelo(ReferenciaGamaEquipo, ['view']))  # Para consultar referencias
    permisos_tecnico.extend(obtener_permisos_modelo(PiezaCotizada, ['view', 'add', 'change']))  # Para cotizaciones
    permisos_tecnico.extend(obtener_permisos_modelo(PiezaVentaMostrador, ['view', 'add', 'change']))  # Para ventas
    
    # Almacén - Solo consulta y solicitudes
    permisos_tecnico.extend(obtener_permisos_modelo(ProductoAlmacen, ['view']))  # Consultar productos
    permisos_tecnico.extend(obtener_permisos_modelo(CategoriaAlmacen, ['view']))  # Consultar categorías
    permisos_tecnico.extend(obtener_permisos_modelo(UnidadInventario, ['view']))  # Consultar unidades disponibles
    permisos_tecnico.extend(obtener_permisos_modelo(MovimientoAlmacen, ['view', 'add']))  # Registrar movimientos
    permisos_tecnico.extend(obtener_permisos_modelo(SolicitudBaja, ['view', 'add', 'change']))  # Crear solicitudes
    permisos_tecnico.extend(obtener_permisos_modelo(SolicitudCotizacion, ['view']))  # Consultar cotizaciones
    
    grupo_tecnico.permissions.set(permisos_tecnico)
    print(f"   ✅ {len(permisos_tecnico)} permisos asignados\n")
    
    # ========== ALMACENISTA ==========
    print("📋 Configurando grupo: ALMACENISTA")
    grupo_almacenista = crear_grupo("Almacenista", "Acceso a almacén y servicio técnico")
    permisos_almacenista = []
    
    # Almacén - Acceso completo a TODOS los modelos
    permisos_almacenista.extend(obtener_permisos_modelo(Proveedor))
    permisos_almacenista.extend(obtener_permisos_modelo(CategoriaAlmacen))
    permisos_almacenista.extend(obtener_permisos_modelo(ProductoAlmacen))
    permisos_almacenista.extend(obtener_permisos_modelo(CompraProducto))
    permisos_almacenista.extend(obtener_permisos_modelo(UnidadCompra))
    permisos_almacenista.extend(obtener_permisos_modelo(MovimientoAlmacen))
    permisos_almacenista.extend(obtener_permisos_modelo(SolicitudBaja))
    permisos_almacenista.extend(obtener_permisos_modelo(Auditoria))
    permisos_almacenista.extend(obtener_permisos_modelo(DiferenciaAuditoria))
    permisos_almacenista.extend(obtener_permisos_modelo(UnidadInventario))
    permisos_almacenista.extend(obtener_permisos_modelo(SolicitudCotizacion))
    permisos_almacenista.extend(obtener_permisos_modelo(LineaCotizacion))
    permisos_almacenista.extend(obtener_permisos_modelo(ImagenLineaCotizacion))
    
    # Servicio Técnico - Solo consulta
    permisos_almacenista.extend(obtener_permisos_modelo(OrdenServicio, ['view']))
    permisos_almacenista.extend(obtener_permisos_modelo(DetalleEquipo, ['view']))
    permisos_almacenista.extend(obtener_permisos_modelo(Cotizacion, ['view']))
    permisos_almacenista.extend(obtener_permisos_modelo(VentaMostrador, ['view']))
    permisos_almacenista.extend(obtener_permisos_modelo(ReferenciaGamaEquipo, ['view']))
    permisos_almacenista.extend(obtener_permisos_modelo(PiezaCotizada, ['view']))
    permisos_almacenista.extend(obtener_permisos_modelo(PiezaVentaMostrador, ['view']))
    
    grupo_almacenista.permissions.set(permisos_almacenista)
    print(f"   ✅ {len(permisos_almacenista)} permisos asignados\n")
    
    # ========== RESUMEN ==========
    print("="*70)
    print("RESUMEN DE GRUPOS CREADOS")
    print("="*70)
    grupos = Group.objects.all().order_by('name')
    for grupo in grupos:
        print(f"✅ {grupo.name}: {grupo.permissions.count()} permisos")
    print("\n" + "="*70)
    print("✅ CONFIGURACIÓN COMPLETADA EXITOSAMENTE")
    print("="*70 + "\n")


if __name__ == '__main__':
    setup_grupos_y_permisos()
