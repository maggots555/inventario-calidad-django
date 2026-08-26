"""
Servicio de negocio para el Formato Digital de Venta Mostrador.

EXPLICACIÓN PARA PRINCIPIANTES:
------------------------------------------------
Aquí vive la lógica que NO debe estar en las vistas ni en models.py:
- ¿Esta orden es venta mostrador? (candidatura)
- Armar las líneas de lo vendido + desglose de IVA
- Guardar borrador del wizard
- Finalizar y generar PDF SIN exigir firma ni daños

Las vistas solo reciben HTTP, llaman a estas funciones y responden.
"""

from __future__ import annotations

import base64
import logging
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from config.constants import PAQUETES_CHOICES
from config.paises_config import get_pais_actual
from inventario.models import Empleado
from servicio_tecnico.models import (
    DanoEsteticoVistaVentaMostrador,
    FormatoServicioVentaMostrador,
    OrdenServicio,
)
from servicio_tecnico.services.sync_cargador_detalle import (
    db_alias_de,
    sincronizar_cargador_a_detalle,
)
from servicio_tecnico.services.vistas_dano import (
    claves_vistas_del_tipo,
    eliminar_vistas_dano_fuera_de_tipo,
)

logger = logging.getLogger(__name__)

MAX_EMAILS_ENVIO_VM = 3
# Misma tasa que pagos_orden / cotización cliente (solo México).
IVA_TASA_MX = Decimal('0.16')
FACTOR_IVA_MX = Decimal('1.16')
DOS_DECIMALES = Decimal('0.01')

# Servicios booleanos de VentaMostrador → etiqueta del PDF.
# EXPLICACIÓN PARA PRINCIPIANTES:
# La venta no guarda un renglón por servicio: cada checkbox tiene su
# costo. Esta lista dice cómo convertir esos checkboxes en líneas.
SERVICIOS_BOOLEANOS_VM = (
    ('incluye_cambio_pieza', 'costo_cambio_pieza', 'Cambio de Pieza'),
    ('incluye_limpieza', 'costo_limpieza', 'Limpieza y Mantenimiento'),
    ('incluye_kit_limpieza', 'costo_kit', 'Kit de Limpieza Profesional'),
    ('incluye_reinstalacion_so', 'costo_reinstalacion', 'Reinstalación de Sistema Operativo'),
    ('incluye_respaldo', 'costo_respaldo', 'Respaldo de Información'),
)

_PAQUETES_LABEL = dict(PAQUETES_CHOICES)


class FormatoVentaMostradorError(Exception):
    """Error de negocio al guardar o finalizar el formato de venta mostrador."""


def _dinero(valor: Decimal) -> Decimal:
    """Redondea a 2 decimales (centavos) con HALF_UP."""
    return valor.quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)


def _empleado_desde_usuario(usuario) -> Empleado | None:
    """
    Resuelve el Empleado ligado al User autenticado.

    Args:
        usuario: django.contrib.auth User

    Returns:
        Empleado o None si el usuario no tiene perfil de empleado.
    """
    if not usuario or not getattr(usuario, 'is_authenticated', False):
        return None
    try:
        return Empleado.objects.get(user=usuario)
    except Empleado.DoesNotExist:
        return None


def orden_es_candidata_formato_venta_mostrador(orden: OrdenServicio) -> bool:
    """
    Indica si la orden puede abrir la Nota de Venta Directa.

    Regla de negocio:
        Solo ``tipo_servicio == 'venta_mostrador'``.
        Las órdenes de diagnóstico (OOW / Dell) usan su propio formato,
        aunque tengan una venta mostrador de complemento.

    Args:
        orden: OrdenServicio a evaluar

    Returns:
        bool: True si el botón/wizard aplica
    """
    return orden.tipo_servicio == 'venta_mostrador'


def normalizar_emails_envio(raw: Any) -> list[str]:
    """
    Limpia y limita a máximo 3 correos únicos (sin vacíos).

    Args:
        raw: lista, string único, o None

    Returns:
        Lista de hasta 3 emails.
    """
    candidatos: list[str] = []
    if isinstance(raw, list):
        candidatos = [str(x) for x in raw]
    elif isinstance(raw, str) and raw.strip():
        candidatos = [p.strip() for p in raw.replace(';', ',').split(',')]
    elif raw is not None and raw != '':
        candidatos = [str(raw)]

    limpios: list[str] = []
    vistos: set[str] = set()
    for correo in candidatos:
        email = (correo or '').strip()
        if not email:
            continue
        clave = email.lower()
        if clave in vistos:
            continue
        vistos.add(clave)
        limpios.append(email)
        if len(limpios) >= MAX_EMAILS_ENVIO_VM:
            break
    return limpios


def lista_emails_envio(formato: FormatoServicioVentaMostrador) -> list[str]:
    """
    Devuelve los correos de envío del formato (hasta 3).

    Preferencia: JSON emails_envio; si está vacío, usa email_envio.
    """
    emails = normalizar_emails_envio(getattr(formato, 'emails_envio', None))
    if emails:
        return emails
    if formato.email_envio:
        return [formato.email_envio.strip()]
    return []


def aplicar_emails_al_formato(
    formato: FormatoServicioVentaMostrador,
    raw: Any,
) -> None:
    """
    Asigna emails_envio y sincroniza email_envio (primer correo).

    Efectos secundarios:
        Modifica formato en memoria (caller debe .save()).
    """
    emails = normalizar_emails_envio(raw)
    formato.emails_envio = emails
    formato.email_envio = emails[0] if emails else ''


def _pais_aplica_iva() -> bool:
    """True si el tenant actual desglosa IVA 16% (México)."""
    codigo = (get_pais_actual().get('codigo') or 'MX').upper()
    return codigo == 'MX'


def _sin_iva_desde_con_iva(monto_con_iva: Decimal, aplica_iva: bool) -> Decimal:
    """
    Convierte un precio con IVA incluido al subtotal sin IVA.

    Args:
        monto_con_iva: Precio que ya incluye IVA (así se guarda VM).
        aplica_iva: Si False, el monto se deja igual.

    Returns:
        Decimal a 2 decimales.
    """
    monto = _dinero(Decimal(monto_con_iva or 0))
    if not aplica_iva or monto <= 0:
        return monto
    return _dinero(monto / FACTOR_IVA_MX)


def armar_conceptos_venta(orden: OrdenServicio) -> dict[str, Any]:
    """
    Arma las líneas de la nota (servicios + piezas) y el desglose IVA.

    Objetivo de negocio:
        El PDF muestra CANTIDAD / CONCEPTO / PRECIO / IMPORTE como el
        formato papel. Los montos de VM ya vienen CON IVA; aquí se
        desglosan para México.

    Args:
        orden: OrdenServicio (puede no tener VentaMostrador aún)

    Returns:
        dict con lineas, subtotal, iva, total, aplica_iva.
        Cada línea: cantidad, descripcion, precio_unitario, importe
        (precio/importe SIN IVA en MX).
    """
    aplica_iva = _pais_aplica_iva()
    lineas: list[dict[str, Any]] = []
    total_con_iva = Decimal('0.00')

    venta = getattr(orden, 'venta_mostrador', None)
    if venta is None:
        return {
            'lineas': [],
            'subtotal': Decimal('0.00'),
            'iva': Decimal('0.00'),
            'total': Decimal('0.00'),
            'aplica_iva': aplica_iva,
            'tasa_iva': IVA_TASA_MX if aplica_iva else Decimal('0.00'),
        }

    # Paso 1: paquete (premium / oro / plata)
    if venta.paquete and venta.paquete != 'ninguno':
        costo = _dinero(Decimal(venta.costo_paquete or 0))
        if costo > 0:
            label = _PAQUETES_LABEL.get(venta.paquete, venta.paquete)
            precio_pdf = _sin_iva_desde_con_iva(costo, aplica_iva)
            lineas.append({
                'cantidad': 1,
                'descripcion': label,
                'precio_unitario': precio_pdf,
                'importe': precio_pdf,
                'monto_con_iva': costo,
            })
            total_con_iva += costo

    # Paso 2: checkboxes de servicio (limpieza, respaldo, …)
    for flag, campo_costo, etiqueta in SERVICIOS_BOOLEANOS_VM:
        if not getattr(venta, flag, False):
            continue
        costo = _dinero(Decimal(getattr(venta, campo_costo) or 0))
        if costo <= 0:
            continue
        precio_pdf = _sin_iva_desde_con_iva(costo, aplica_iva)
        lineas.append({
            'cantidad': 1,
            'descripcion': etiqueta,
            'precio_unitario': precio_pdf,
            'importe': precio_pdf,
            'monto_con_iva': costo,
        })
        total_con_iva += costo

    # Paso 3: piezas vendidas (precio_unitario ya con IVA)
    piezas = []
    if hasattr(venta, 'piezas_vendidas'):
        piezas = list(venta.piezas_vendidas.all())
    for pieza in piezas:
        cantidad = int(pieza.cantidad or 1)
        unitario_con_iva = _dinero(Decimal(pieza.precio_unitario or 0))
        subtotal_con_iva = _dinero(Decimal(pieza.subtotal or 0))
        unitario_pdf = _sin_iva_desde_con_iva(unitario_con_iva, aplica_iva)
        importe_pdf = _dinero(unitario_pdf * Decimal(cantidad))
        lineas.append({
            'cantidad': cantidad,
            'descripcion': pieza.descripcion_pieza or 'Pieza',
            'precio_unitario': unitario_pdf,
            'importe': importe_pdf,
            'monto_con_iva': subtotal_con_iva,
        })
        total_con_iva += subtotal_con_iva

    total_con_iva = _dinero(total_con_iva)
    if aplica_iva:
        subtotal = _dinero(sum((linea['importe'] for linea in lineas), Decimal('0.00')))
        iva = _dinero(total_con_iva - subtotal)
        if iva < 0:
            iva = Decimal('0.00')
    else:
        subtotal = total_con_iva
        iva = Decimal('0.00')

    return {
        'lineas': lineas,
        'subtotal': subtotal,
        'iva': iva,
        'total': total_con_iva,
        'aplica_iva': aplica_iva,
        'tasa_iva': IVA_TASA_MX if aplica_iva else Decimal('0.00'),
    }


def obtener_o_crear_borrador(
    orden: OrdenServicio,
    usuario=None,
) -> FormatoServicioVentaMostrador:
    """
    Obtiene el formato VM de la orden o crea uno en estado borrador.

    Args:
        orden: OrdenServicio
        usuario: User opcional para auditar creado_por

    Returns:
        FormatoServicioVentaMostrador (existente o nuevo)

    Efectos secundarios:
        Puede INSERTAR un FormatoServicioVentaMostrador y prellenar.
    """
    empleado = _empleado_desde_usuario(usuario)
    formato, creado = FormatoServicioVentaMostrador.objects.get_or_create(
        orden=orden,
        defaults={
            'estado': 'borrador',
            'creado_por': empleado,
            'actualizado_por': empleado,
        },
    )
    if creado:
        _prefill_desde_detalle(formato)
        formato.save()
        logger.info(
            'Formato VM borrador creado para orden %s',
            orden.numero_orden_interno,
        )
    return formato


def _prefill_desde_detalle(formato: FormatoServicioVentaMostrador) -> None:
    """
    Copia datos útiles de DetalleEquipo al borrador recién creado.

    Efectos secundarios:
        Modifica campos en memoria (caller debe .save()).
    """
    detalle = getattr(formato.orden, 'detalle_equipo', None)
    if detalle is None:
        return
    # Empresa / contacto: el modelo no los separa; el wizard puede editarlos
    formato.empresa_cliente = (detalle.nombre_cliente or '')[:200]
    aplicar_emails_al_formato(formato, detalle.email_cliente or '')
    serie = (getattr(detalle, 'numero_serie_cargador', None) or '').strip()
    if serie:
        formato.numero_cargador = serie[:100]
    tipo = (detalle.tipo_equipo or '').lower()
    if tipo in ('aio', 'all-in-one', 'all in one'):
        formato.tipo_diagrama = 'aio'
    elif tipo in ('desktop', 'escritorio', 'pc'):
        formato.tipo_diagrama = 'escritorio'
    else:
        formato.tipo_diagrama = 'laptop'


def serializar_formato(formato: FormatoServicioVentaMostrador) -> dict[str, Any]:
    """
    Serializa el formato a un dict JSON-friendly para el wizard TS.

    Args:
        formato: FormatoServicioVentaMostrador

    Returns:
        dict con campos del formulario + URLs de firmas/vistas
    """
    vistas = []
    for vista in formato.vistas_dano.all():
        vistas.append({
            'clave_vista': vista.clave_vista,
            'etiqueta_dano': vista.etiqueta_dano,
            'imagen_url': vista.imagen_anotada.url if vista.imagen_anotada else '',
        })

    return {
        'id': formato.pk,
        'estado': formato.estado,
        'tipo_diagrama': formato.tipo_diagrama,
        'empresa_cliente': formato.empresa_cliente,
        'persona_contacto': formato.persona_contacto,
        'numero_cargador': formato.numero_cargador,
        'email_envio': formato.email_envio,
        'emails_envio': lista_emails_envio(formato),
        'firma_entrega_cis_url': (
            formato.firma_entrega_cis.url if formato.firma_entrega_cis else ''
        ),
        'firma_entrega_cliente_url': (
            formato.firma_entrega_cliente.url if formato.firma_entrega_cliente else ''
        ),
        'pdf_url': formato.pdf.url if formato.pdf else '',
        'vistas_dano': vistas,
        'finalizado': formato.estado == 'finalizado',
    }


def datos_orden_para_wizard(orden: OrdenServicio) -> dict[str, Any]:
    """
    Datos de solo lectura (cliente/equipo/venta) para mostrar en el wizard.

    Args:
        orden: OrdenServicio

    Returns:
        dict con folio, cliente, equipo, conceptos de venta
    """
    detalle = getattr(orden, 'detalle_equipo', None)
    sucursal_nombre = ''
    if getattr(orden, 'sucursal', None) is not None:
        sucursal_nombre = orden.sucursal.nombre or ''

    conceptos = armar_conceptos_venta(orden)
    lineas_json = []
    for linea in conceptos['lineas']:
        lineas_json.append({
            'cantidad': linea['cantidad'],
            'descripcion': linea['descripcion'],
            'precio_unitario': str(linea['precio_unitario']),
            'importe': str(linea['importe']),
        })

    return {
        'orden_id': orden.pk,
        'numero_orden_interno': orden.numero_orden_interno,
        'orden_cliente': (detalle.orden_cliente if detalle else '') or '',
        'folio_sicser': (detalle.folio_sicser if detalle else '') or '',
        'fecha_ingreso': (
            orden.fecha_ingreso.strftime('%Y-%m-%d') if orden.fecha_ingreso else ''
        ),
        'nombre_cliente': (detalle.nombre_cliente if detalle else '') or '',
        'rfc_cliente': (detalle.rfc_cliente if detalle else '') or '',
        'email_cliente': (detalle.email_cliente if detalle else '') or '',
        'telefono_cliente': (detalle.telefono_cliente if detalle else '') or '',
        'marca': (detalle.marca if detalle else '') or '',
        'modelo': (detalle.modelo if detalle else '') or '',
        'numero_serie': (detalle.numero_serie if detalle else '') or '',
        'tipo_equipo': (detalle.tipo_equipo if detalle else '') or '',
        'sucursal': sucursal_nombre,
        'conceptos': lineas_json,
        'subtotal': str(conceptos['subtotal']),
        'iva': str(conceptos['iva']),
        'total': str(conceptos['total']),
        'aplica_iva': conceptos['aplica_iva'],
    }


def _decode_data_url(data_url: str) -> ContentFile | None:
    """
    Convierte un data URL base64 (canvas.toDataURL) en ContentFile PNG.

    Args:
        data_url: Cadena tipo 'data:image/png;base64,....'

    Returns:
        ContentFile o None si el string está vacío/inválido
    """
    if not data_url or not isinstance(data_url, str):
        return None
    texto = data_url.strip()
    if not texto:
        return None
    if ',' in texto and texto.startswith('data:'):
        _, b64 = texto.split(',', 1)
    else:
        b64 = texto
    try:
        raw = base64.b64decode(b64)
    except Exception:
        logger.warning('No se pudo decodificar data URL de imagen VM')
        return None
    if not raw:
        return None
    return ContentFile(raw)


def aplicar_payload_borrador(
    formato: FormatoServicioVentaMostrador,
    payload: dict[str, Any],
    usuario=None,
    permitir_finalizado: bool = False,
) -> FormatoServicioVentaMostrador:
    """
    Aplica un payload JSON del wizard al borrador (sin finalizar).

    Args:
        formato: FormatoServicioVentaMostrador
        payload: Dict con campos + firmas/vistas en base64
        usuario: User opcional
        permitir_finalizado: Si True, permite actualizar uno ya finalizado

    Returns:
        FormatoServicioVentaMostrador actualizado

    Raises:
        FormatoVentaMostradorError: si ya está finalizado y no se permite

    Efectos secundarios:
        UPDATE formato + upsert vistas de daño + sync cargador
    """
    if formato.estado == 'finalizado' and not permitir_finalizado:
        raise FormatoVentaMostradorError(
            'El formato ya está finalizado. Usa el botón “Regenerar PDF” '
            'para guardar cambios y actualizar el documento (no reenvía correo).'
        )

    empleado = _empleado_desde_usuario(usuario)
    db_alias = db_alias_de(formato)

    with transaction.atomic(using=db_alias):
        for campo, limite in (
            ('empresa_cliente', 200),
            ('persona_contacto', 200),
            ('numero_cargador', 100),
        ):
            if campo in payload and payload[campo] is not None:
                setattr(formato, campo, str(payload[campo])[:limite])

        if 'emails_envio' in payload:
            aplicar_emails_al_formato(formato, payload.get('emails_envio'))
        elif 'email_envio' in payload and payload['email_envio'] is not None:
            aplicar_emails_al_formato(formato, payload.get('email_envio'))

        if 'tipo_diagrama' in payload and payload['tipo_diagrama'] in (
            'laptop',
            'escritorio',
            'aio',
        ):
            formato.tipo_diagrama = payload['tipo_diagrama']

        # Firmas opcionales (entrega CIS / entrega a cliente)
        firma_cis = _decode_data_url(payload.get('firma_entrega_cis_data') or '')
        if firma_cis is not None:
            formato.firma_entrega_cis.save('firma_cis.png', firma_cis, save=False)

        firma_cli = _decode_data_url(payload.get('firma_entrega_cliente_data') or '')
        if firma_cli is not None:
            formato.firma_entrega_cliente.save(
                'firma_cliente.png',
                firma_cli,
                save=False,
            )

        formato.actualizado_por = empleado
        formato.save()

        # Si capturaron cargador, lo copiamos a la ficha del equipo
        sincronizar_cargador_a_detalle(
            formato.orden,
            numero_cargador=formato.numero_cargador,
            accesorio_cargador=bool(formato.numero_cargador),
        )

        vistas = payload.get('vistas_dano') or []
        claves_tipo = claves_vistas_del_tipo(formato.tipo_diagrama)
        if isinstance(vistas, list):
            for item in vistas:
                if not isinstance(item, dict):
                    continue
                clave = str(item.get('clave_vista') or '').strip()[:40]
                if not clave or clave not in claves_tipo:
                    continue
                etiqueta = str(item.get('etiqueta_dano') or '')[:80]
                vista, _ = DanoEsteticoVistaVentaMostrador.objects.get_or_create(
                    formato=formato,
                    clave_vista=clave,
                    defaults={'etiqueta_dano': etiqueta},
                )
                vista.etiqueta_dano = etiqueta
                imagen = _decode_data_url(item.get('imagen_data') or '')
                if imagen is not None:
                    vista.imagen_anotada.save(f'{clave}.png', imagen, save=False)
                vista.save()
        eliminar_vistas_dano_fuera_de_tipo(formato)

    return formato


def finalizar_formato(
    formato: FormatoServicioVentaMostrador,
    usuario=None,
    forzar_regenerar: bool = False,
) -> FormatoServicioVentaMostrador:
    """
    Genera el PDF de Nota de Venta y marca el formato como finalizado.

    EXPLICACIÓN PARA PRINCIPIANTES:
    A diferencia de OOW, aquí NO se exige firma, daños ni casillas.
    El de front puede enviar la nota solo con lo vendido.

    Args:
        formato: FormatoServicioVentaMostrador
        usuario: User opcional
        forzar_regenerar: Si True, regenera PDF aunque ya esté finalizado

    Returns:
        FormatoServicioVentaMostrador finalizado con pdf guardado

    Raises:
        FormatoVentaMostradorError: si falló el PDF

    Efectos secundarios:
        Genera PDF, guarda FileField, actualiza estado y finalizado_en.
    """
    if formato.estado == 'finalizado' and not forzar_regenerar:
        if formato.pdf:
            return formato

    ahora = timezone.now()
    if not formato.finalizado_en:
        formato.finalizado_en = ahora

    from servicio_tecnico.utils.pdf_formato_venta_mostrador import (
        PDFFormatoVentaMostrador,
    )

    generador = PDFFormatoVentaMostrador(formato)
    resultado = generador.generar_pdf()
    if not resultado.get('success') or not resultado.get('buffer'):
        raise FormatoVentaMostradorError(
            resultado.get('error')
            or 'No se pudo generar el PDF de la nota de venta.'
        )

    empleado = _empleado_desde_usuario(usuario)
    nombre_archivo = resultado.get('nombre_archivo') or (
        f"NotaVenta_{formato.orden.numero_orden_interno}.pdf"
    )
    pdf_bytes = resultado['buffer'].getvalue()
    db_alias = db_alias_de(formato)

    with transaction.atomic(using=db_alias):
        formato.pdf.save(nombre_archivo, ContentFile(pdf_bytes), save=False)
        formato.estado = 'finalizado'
        if not formato.finalizado_en:
            formato.finalizado_en = ahora
        formato.actualizado_por = empleado
        formato.save()

    logger.info(
        'Formato VM finalizado orden=%s pdf=%s',
        formato.orden.numero_orden_interno,
        nombre_archivo,
    )
    return formato
