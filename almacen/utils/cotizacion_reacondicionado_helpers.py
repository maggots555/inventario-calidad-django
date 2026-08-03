"""
Helpers compartidos del flujo de cotización (profit + reacondicionado).

EXPLICACIÓN PARA PRINCIPIANTES:
-------------------------------
Antes vivían en el medio de views.py entre editar_lineas y detalle.
Los sacamos aquí (Fase 4a) para que views_solicitudes_cotizacion y
views_cotizacion_cliente puedan usarlos sin importarse entre sí
(evita imports circulares).

Efectos secundarios:
- Lectura de parámetros profit/REAC (BD + .env)
- Persistencia de snapshot REAC en SolicitudCotizacion
- Crear/actualizar LineaCotizacion P0125 (equipo reacondicionado)
- Sync de estado ST al enviar cotización al cliente (delega en util)
"""

from __future__ import annotations

import json as _json
import logging

logger = logging.getLogger('almacen')


def _serializar_profit_config() -> str:
    """
    Lee la configuración de profit vigente (panel BD + fallback .env)
    y la convierte a una cadena JSON lista para inyectar en el template.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    El template necesita pasar estos valores al JavaScript del navegador.
    Al usar |safe en el template, Django inserta el JSON sin escapar las
    comillas, de modo que el navegador lo interpreta como objeto JS válido.

    Importamos dentro de la función (importación diferida) para evitar
    importaciones circulares y para mantener el módulo ligero.

    Returns:
        str: Cadena JSON con la configuración de profit por perfil.
    """
    # Importación diferida: usa BD (panel) con respaldo .env
    from almacen.utils.parametros_cotizador import obtener_profit_config

    profit_cfg = obtener_profit_config()
    # Construir un diccionario serializable (las listas de costos_fijos ya lo son)
    datos = {
        perfil: {
            'profit_target':  cfg['profit_target'],
            'costos_fijos':   cfg['costos_fijos'],
            'diagnostico':    cfg['diagnostico'],
        }
        for perfil, cfg in profit_cfg.items()
    }
    # Convertir a JSON compacto — se incrustará dentro de un <script>
    return _json.dumps(datos, separators=(',', ':'))


def _serializar_costeo_reacondicionado_config() -> str:
    """
    Serializa la configuración del costeo de reacondicionados para el modal TypeScript.

    Returns:
        str: JSON compacto con porcentajes y montos del .env.
    """
    from almacen.utils.costeo_reacondicionado import serializar_config_costeo
    return _json.dumps(serializar_config_costeo(), separators=(',', ':'))


def _actualizar_estado_st_esperando_aprobacion_cliente(solicitud, usuario=None):
    """
    Compatibilidad: delega en el util de sync (no retrocede estados posteriores).

    EXPLICACIÓN PARA PRINCIPIANTES:
    La lógica real vive en sincronizar_estado_st.py. Esta función solo existe
    para que las vistas de envío de cotización sigan llamando el mismo nombre.
    """
    from almacen.utils.sincronizar_estado_st import (
        sincronizar_estado_st_al_enviar_cotizacion_cliente,
    )
    return sincronizar_estado_st_al_enviar_cotizacion_cliente(
        solicitud,
        usuario=usuario,
    )


def _extraer_datos_reacondicionado_post(post) -> dict:
    """
    Lee del POST los campos del equipo reacondicionado capturados en el modal.

    Args:
        post: request.POST de Django.

    Returns:
        dict: Datos del equipo y parámetros de costeo.
    """
    return {
        'costo_proveedor': post.get('reac_costo_proveedor', '').strip(),
        'dias_front_desk': post.get('reac_dias_front_desk', '1').strip(),
        'marca': post.get('reac_marca', '').strip(),
        'modelo': post.get('reac_modelo', '').strip(),
        'procesador': post.get('reac_procesador', '').strip(),
        'ram': post.get('reac_ram', '').strip(),
        'sistema_operativo': post.get('reac_sistema_operativo', '').strip(),
        'incluye_cargador': post.get('reac_incluye_cargador') == '1',
        'especificaciones': post.get('reac_especificaciones', '').strip(),
    }


def _validar_y_calcular_reacondicionado(datos: dict):
    """
    Valida campos obligatorios y ejecuta calcular_costeo().

    Returns:
        tuple: (ok: bool, resultado_o_error: dict|str)
    """
    from almacen.utils.costeo_reacondicionado import calcular_costeo

    if not datos.get('marca'):
        return False, 'La marca del equipo es obligatoria.'
    if not datos.get('modelo'):
        return False, 'El modelo del equipo es obligatorio.'

    try:
        costo = float(datos.get('costo_proveedor') or 0)
        if costo <= 0:
            return False, 'El costo de proveedor debe ser mayor a cero.'
    except ValueError:
        return False, 'El costo de proveedor no es un número válido.'

    try:
        dias = int(datos.get('dias_front_desk') or 1)
        if dias < 1:
            dias = 1
    except ValueError:
        return False, 'Los días de front desk deben ser un número entero válido.'

    # Si los % variables en BD suman ≥ 100%, calcular_costeo lanza ValueError
    try:
        costeo = calcular_costeo(costo_proveedor=costo, dias_front_desk=dias)
    except ValueError as exc:
        return False, str(exc)

    datos_equipo = {
        'marca': datos['marca'],
        'modelo': datos['modelo'],
        'procesador': datos.get('procesador', ''),
        'ram': datos.get('ram', ''),
        'sistema_operativo': datos.get('sistema_operativo', ''),
        'incluye_cargador': datos.get('incluye_cargador', False),
        'especificaciones': datos.get('especificaciones', ''),
    }
    return True, {'costeo': costeo, 'datos_equipo': datos_equipo, 'dias_front_desk': dias, 'costo_proveedor': costo}


def _guardar_snapshot_reacondicionado(solicitud, datos_equipo, costeo, dias, costo):
    """Persiste en la solicitud el snapshot de la propuesta reacondicionada."""
    from decimal import Decimal
    solicitud.modo_cotizacion_cliente = 'reacondicionado'
    solicitud.costo_proveedor_reac = Decimal(str(costo))
    solicitud.dias_front_desk_reac = dias
    solicitud.reac_marca = datos_equipo.get('marca', '')
    solicitud.reac_modelo = datos_equipo.get('modelo', '')
    solicitud.reac_procesador = datos_equipo.get('procesador', '')
    solicitud.reac_ram = datos_equipo.get('ram', '')
    solicitud.reac_sistema_operativo = datos_equipo.get('sistema_operativo', '')
    solicitud.reac_incluye_cargador = bool(datos_equipo.get('incluye_cargador'))
    solicitud.reac_especificaciones = datos_equipo.get('especificaciones', '')
    solicitud.resultado_costeo_reac = costeo
    solicitud.save(update_fields=[
        'modo_cotizacion_cliente',
        'costo_proveedor_reac',
        'dias_front_desk_reac',
        'reac_marca',
        'reac_modelo',
        'reac_procesador',
        'reac_ram',
        'reac_sistema_operativo',
        'reac_incluye_cargador',
        'reac_especificaciones',
        'resultado_costeo_reac',
    ])


# SKU del catálogo para equipos reacondicionados ofertados al cliente
CODIGO_PRODUCTO_REACONDICIONADO = 'P0125'


def _construir_descripcion_linea_reac(datos_equipo: dict) -> str:
    """
    Arma una descripción compacta del equipo para LineaCotizacion.descripcion_pieza.

    Args:
        datos_equipo: dict con marca, modelo, procesador, ram, sistema_operativo, incluye_cargador.

    Returns:
        str: Texto truncado a 255 caracteres (límite del campo).
    """
    partes = []
    marca = (datos_equipo.get('marca') or '').strip()
    modelo = (datos_equipo.get('modelo') or '').strip()
    if marca or modelo:
        partes.append(f'{marca} {modelo}'.strip())
    if datos_equipo.get('procesador'):
        partes.append(str(datos_equipo['procesador']).strip())
    if datos_equipo.get('ram'):
        partes.append(str(datos_equipo['ram']).strip())
    if datos_equipo.get('sistema_operativo'):
        partes.append(str(datos_equipo['sistema_operativo']).strip())
    if datos_equipo.get('incluye_cargador'):
        partes.append('Con cargador')
    return ' | '.join(partes)[:255]


def _crear_o_actualizar_linea_reacondicionado(solicitud, datos_equipo, costeo, costo_proveedor):
    """
    Crea o actualiza la LineaCotizacion P0125 al enviar propuesta de equipo reacondicionado.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta línea permite a Front aprobar/rechazar la oferta de equipo igual que las piezas
    de reparación. Al aprobar y generar compras, el equipo va a PiezaVentaMostrador en ST.

    Args:
        solicitud: SolicitudCotizacion vinculada.
        datos_equipo: Especificaciones capturadas en el modal.
        costeo: Resultado de calcular_costeo().
        costo_proveedor: float, costo de adquisición sin IVA.

    Returns:
        tuple: (ok: bool, error: str|None)
    """
    from decimal import Decimal
    from almacen.models import LineaCotizacion, ProductoAlmacen

    try:
        producto = ProductoAlmacen.objects.get(codigo_producto=CODIGO_PRODUCTO_REACONDICIONADO)
    except ProductoAlmacen.DoesNotExist:
        logger.error(
            f'[REAC] Producto {CODIGO_PRODUCTO_REACONDICIONADO} no existe en ProductoAlmacen. '
            f'Solicitud {solicitud.numero_solicitud}'
        )
        return False, (
            f'El producto {CODIGO_PRODUCTO_REACONDICIONADO} (equipo reacondicionado) '
            'no está en el catálogo de almacén. Contacte al administrador.'
        )

    subtotal_sin_iva = Decimal(str(costeo.get('subtotal_sin_iva', 0)))
    descripcion = _construir_descripcion_linea_reac(datos_equipo)

    notas_partes = []
    especificaciones = (datos_equipo.get('especificaciones') or '').strip()
    if especificaciones:
        notas_partes.append(especificaciones)
    total_contado = costeo.get('total_precio_contado_mxn')
    if total_contado is not None:
        notas_partes.append(f'Precio contado (IVA incl.): ${total_contado}')

    defaults = {
        'descripcion_pieza': descripcion,
        'cantidad': 1,
        'costo_unitario': Decimal(str(costo_proveedor)),
        'precio_unitario_cliente': subtotal_sin_iva,
        'subtotal_cliente_sin_iva': subtotal_sin_iva,
        'es_linea_reacondicionado': True,
        'es_necesaria': False,
        'estado_cliente': 'pendiente',
        'opcion_pago_reac': '',
        'notas': '\n'.join(notas_partes),
    }

    linea = solicitud.lineas.filter(
        producto=producto,
        es_linea_reacondicionado=True,
    ).first()

    if linea:
        for campo, valor in defaults.items():
            setattr(linea, campo, valor)
        linea.save()
        logger.info(
            f'[REAC] Línea reacondicionado actualizada en solicitud {solicitud.numero_solicitud}'
        )
    else:
        LineaCotizacion.objects.create(
            solicitud=solicitud,
            producto=producto,
            **defaults,
        )
        logger.info(
            f'[REAC] Línea reacondicionado creada en solicitud {solicitud.numero_solicitud}'
        )

    return True, None


def _opciones_servicios_adicionales():
    """
    Construye la lista de servicios adicionales para el dropdown del modal.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Los nombres vienen de TIPO_SERVICIO_ADICIONAL_CHOICES y los precios de
    PRECIOS_SERVICIOS_ADICIONALES (constants.py). Así el template no repite
    valores hardcodeados que pueden quedar desactualizados.

    Returns:
        list[dict]: Opciones con codigo, nombre y precio (IVA incluido).
    """
    from config.constants import (
        TIPO_SERVICIO_ADICIONAL_CHOICES,
        PRECIOS_SERVICIOS_ADICIONALES,
    )

    return [
        {
            'codigo': codigo,
            'nombre': nombre,
            'precio': PRECIOS_SERVICIOS_ADICIONALES.get(codigo, 0),
        }
        for codigo, nombre in TIPO_SERVICIO_ADICIONAL_CHOICES
    ]
