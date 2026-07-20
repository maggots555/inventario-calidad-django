"""
Servicio de negocio para el Formato Digital OOW.

EXPLICACIÓN PARA PRINCIPIANTES:
------------------------------------------------
Este módulo concentra la lógica que NO debe vivir en las vistas:
crear/obtener borrador, prellenar datos desde DetalleEquipo, aplicar
payloads AJAX y marcar el formato como finalizado tras generar el PDF.

Las vistas solo reciben HTTP, llaman a estas funciones y responden.
"""

from __future__ import annotations

import base64
import logging
from typing import Any

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from config.constants import (
    AVISO_PRIVACIDAD_OOW_VERSION_MX,
    COMO_ENTERASTE_OOW_CHOICES,
)
from config.paises_config import get_pais_actual
from inventario.models import Empleado
from servicio_tecnico.models import (
    DanoEsteticoVista,
    FormatoServicioOOW,
    OrdenServicio,
)

logger = logging.getLogger(__name__)

MAX_EMAILS_ENVIO_OOW = 3


def normalizar_emails_envio(raw: Any) -> list[str]:
    """
    Limpia y limita a máximo 3 correos únicos (sin vacíos).

    Args:
        raw: lista, string único, o None

    Returns:
        Lista de hasta 3 emails (strip; sin duplicados por mayúsculas/minúsculas).
    """
    candidatos: list[str] = []
    # EXPLICACIÓN PARA PRINCIPIANTES:
    # El wizard puede mandar una lista JSON o, por compatibilidad, un solo string.
    if isinstance(raw, list):
        candidatos = [str(x) for x in raw]
    elif isinstance(raw, str) and raw.strip():
        # También aceptamos "a@x.com, b@y.com" por si llega separado por comas
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
        if len(limpios) >= MAX_EMAILS_ENVIO_OOW:
            break
    return limpios


def lista_emails_envio(formato: FormatoServicioOOW) -> list[str]:
    """
    Devuelve los correos de envío del formato (hasta 3).

    Preferencia: campo JSON emails_envio; si está vacío, usa email_envio (legacy).
    """
    emails = normalizar_emails_envio(getattr(formato, 'emails_envio', None))
    if emails:
        return emails
    if formato.email_envio:
        return [formato.email_envio.strip()]
    return []


def aplicar_emails_al_formato(formato: FormatoServicioOOW, raw: Any) -> None:
    """
    Asigna emails_envio y sincroniza email_envio (primer correo) por compatibilidad.

    Efectos secundarios:
        Modifica formato en memoria (caller debe .save()).
    """
    emails = normalizar_emails_envio(raw)
    formato.emails_envio = emails
    formato.email_envio = emails[0] if emails else ''


# Claves booleanas de accesorios que llegan del front
CAMPOS_ACCESORIOS = (
    'accesorio_cargador',
    'accesorio_maletin',
    'accesorio_mouse',
    'accesorio_teclado',
    'accesorio_monitor',
    'accesorio_otros',
)

COMO_ENTERASTE_VALIDOS = {valor for valor, _ in COMO_ENTERASTE_OOW_CHOICES}


class FormatoOOWError(Exception):
    """Error de negocio al guardar o finalizar el formato OOW."""


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


def orden_es_candidata_formato_oow(orden: OrdenServicio) -> bool:
    """
    Indica si la orden puede abrir el Formato Digital OOW.

    Regla de negocio:
        - Órdenes de diagnóstico (fuera de garantía) o
        - Órdenes importadas desde SICSER OOW o
        - Órdenes cuyo orden_cliente empieza con OOW-

    Args:
        orden: OrdenServicio a evaluar

    Returns:
        bool: True si el botón/wizard aplica
    """
    if orden.tipo_servicio == 'diagnostico':
        return True
    try:
        detalle = orden.detalle_equipo
    except Exception:
        return False
    if detalle.sicser_origen == 'oow':
        return True
    orden_cliente = (detalle.orden_cliente or '').strip().upper()
    return orden_cliente.startswith('OOW-')


def obtener_o_crear_borrador(
    orden: OrdenServicio,
    usuario=None,
) -> FormatoServicioOOW:
    """
    Obtiene el formato OOW de la orden o crea uno en estado borrador.

    Args:
        orden: OrdenServicio
        usuario: User opcional para auditar creado_por

    Returns:
        FormatoServicioOOW (existente o nuevo)

    Efectos secundarios:
        Puede INSERTAR un FormatoServicioOOW y prellenar desde DetalleEquipo.
    """
    empleado = _empleado_desde_usuario(usuario)
    formato, creado = FormatoServicioOOW.objects.get_or_create(
        orden=orden,
        defaults={
            'estado': 'borrador',
            'creado_por': empleado,
            'actualizado_por': empleado,
        },
    )
    if creado:
        # Prefill de accesorios/email/técnico desde datos ya conocidos en SIGMA
        _prefill_desde_detalle(formato)
        formato.save()
        logger.info(
            'Formato OOW borrador creado para orden %s',
            orden.numero_orden_interno,
        )
    return formato


def _prefill_desde_detalle(formato: FormatoServicioOOW) -> None:
    """
    Copia datos útiles de DetalleEquipo al borrador recién creado.

    Args:
        formato: FormatoServicioOOW sin guardar aún (o recién creado)

    Efectos secundarios:
        Modifica campos en memoria del formato (caller debe .save()).
    """
    detalle = formato.orden.detalle_equipo
    formato.accesorio_cargador = bool(detalle.tiene_cargador)
    # Prefill: un solo correo del cliente; el usuario puede agregar hasta 2 más en la UI
    aplicar_emails_al_formato(formato, detalle.email_cliente or '')
    # Tipo de diagrama según tipo de equipo
    tipo = (detalle.tipo_equipo or '').lower()
    if tipo in ('aio', 'all-in-one', 'all in one'):
        formato.tipo_diagrama = 'aio'
    elif tipo in ('desktop', 'escritorio', 'pc'):
        formato.tipo_diagrama = 'escritorio'
    else:
        formato.tipo_diagrama = 'laptop'


def serializar_formato(formato: FormatoServicioOOW) -> dict[str, Any]:
    """
    Serializa el formato a un dict JSON-friendly para el wizard TS.

    Args:
        formato: FormatoServicioOOW

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
        'accesorio_cargador': formato.accesorio_cargador,
        'accesorio_maletin': formato.accesorio_maletin,
        'accesorio_mouse': formato.accesorio_mouse,
        'accesorio_teclado': formato.accesorio_teclado,
        'accesorio_monitor': formato.accesorio_monitor,
        'accesorio_otros': formato.accesorio_otros,
        'accesorios_otros_detalle': formato.accesorios_otros_detalle,
        'contrasena_equipo': formato.contrasena_equipo,
        'observaciones_tecnicas': formato.observaciones_tecnicas,
        'disclaimer_pc_audit': formato.disclaimer_pc_audit,
        'acepta_condiciones': formato.acepta_condiciones,
        'acepta_privacidad': formato.acepta_privacidad,
        'version_aviso_privacidad': formato.version_aviso_privacidad,
        'email_envio': formato.email_envio,
        'emails_envio': lista_emails_envio(formato),
        'como_enteraste': formato.como_enteraste,
        'firma_cliente_url': formato.firma_cliente.url if formato.firma_cliente else '',
        'pdf_url': formato.pdf.url if formato.pdf else '',
        'vistas_dano': vistas,
        'finalizado': formato.estado == 'finalizado',
    }


def datos_orden_para_wizard(orden: OrdenServicio) -> dict[str, Any]:
    """
    Datos de solo lectura (cliente/equipo) para mostrar en el wizard.

    Args:
        orden: OrdenServicio

    Returns:
        dict con folio, cliente, equipo, falla, etc.
    """
    detalle = orden.detalle_equipo
    return {
        'orden_id': orden.pk,
        'numero_orden_interno': orden.numero_orden_interno,
        'orden_cliente': detalle.orden_cliente or '',
        'folio_sicser': detalle.folio_sicser or '',
        'fecha_ingreso': orden.fecha_ingreso.strftime('%Y-%m-%d') if orden.fecha_ingreso else '',
        'nombre_cliente': detalle.nombre_cliente or '',
        'rfc_cliente': detalle.rfc_cliente or '',
        'email_cliente': detalle.email_cliente or '',
        'telefono_cliente': detalle.telefono_cliente or '',
        'marca': detalle.marca or '',
        'modelo': detalle.modelo or '',
        'numero_serie': detalle.numero_serie or '',
        'tipo_equipo': detalle.tipo_equipo or '',
        'falla_principal': detalle.falla_principal or '',
        'diagnostico_sic': detalle.diagnostico_sic or '',
        'tiene_cargador': detalle.tiene_cargador,
        'equipo_enciende': detalle.equipo_enciende,
        'sicser_cis': detalle.sicser_cis or '',
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
    # Paso 1: separar cabecera del payload base64
    if ',' in texto and texto.startswith('data:'):
        _, b64 = texto.split(',', 1)
    else:
        b64 = texto
    try:
        raw = base64.b64decode(b64)
    except Exception:
        logger.warning('No se pudo decodificar data URL de imagen OOW')
        return None
    if not raw:
        return None
    return ContentFile(raw)


def aplicar_payload_borrador(
    formato: FormatoServicioOOW,
    payload: dict[str, Any],
    usuario=None,
    permitir_finalizado: bool = False,
) -> FormatoServicioOOW:
    """
    Aplica un payload JSON del wizard al borrador (sin finalizar).

    Args:
        formato: FormatoServicioOOW
        payload: Dict con campos del formulario + firmas/vistas en base64
        usuario: User opcional
        permitir_finalizado: Si True, permite actualizar un formato ya
            finalizado (necesario para regenerar el PDF desde la UI).

    Returns:
        FormatoServicioOOW actualizado

    Raises:
        FormatoOOWError: si el formato ya está finalizado y no se permite

    Efectos secundarios:
        UPDATE FormatoServicioOOW + upsert DanoEsteticoVista + archivos ImageField
    """
    # EXPLICACIÓN PARA PRINCIPIANTES:
    # Tras finalizar, el PDF ya existe. Si el usuario quiere corregir datos,
    # el botón “Regenerar PDF” manda permitir_finalizado=True para poder
    # guardar otra vez y volver a generar el documento.
    if formato.estado == 'finalizado' and not permitir_finalizado:
        raise FormatoOOWError(
            'El formato ya está finalizado. Usa el botón “Regenerar PDF” '
            'para guardar cambios y actualizar el documento (no reenvía correo).'
        )

    empleado = _empleado_desde_usuario(usuario)

    with transaction.atomic():
        # --- Campos simples ---
        for campo in CAMPOS_ACCESORIOS:
            if campo in payload:
                setattr(formato, campo, bool(payload[campo]))

        for campo in (
            'accesorios_otros_detalle',
            'contrasena_equipo',
            'observaciones_tecnicas',
        ):
            if campo in payload and payload[campo] is not None:
                setattr(formato, campo, str(payload[campo])[:500 if campo != 'observaciones_tecnicas' else 5000])

        # Emails: preferir lista emails_envio; si no viene, aceptar email_envio único
        if 'emails_envio' in payload:
            aplicar_emails_al_formato(formato, payload.get('emails_envio'))
        elif 'email_envio' in payload and payload['email_envio'] is not None:
            aplicar_emails_al_formato(formato, payload.get('email_envio'))

        if 'tipo_diagrama' in payload and payload['tipo_diagrama'] in ('laptop', 'escritorio', 'aio'):
            formato.tipo_diagrama = payload['tipo_diagrama']

        if 'disclaimer_pc_audit' in payload:
            formato.disclaimer_pc_audit = bool(payload['disclaimer_pc_audit'])
        if 'acepta_condiciones' in payload:
            formato.acepta_condiciones = bool(payload['acepta_condiciones'])
        if 'acepta_privacidad' in payload:
            formato.acepta_privacidad = bool(payload['acepta_privacidad'])

        como = payload.get('como_enteraste', '')
        if como in COMO_ENTERASTE_VALIDOS or como == '':
            formato.como_enteraste = como

        # --- Firmas (data URLs) ---
        firma_cliente = _decode_data_url(payload.get('firma_cliente_data') or '')
        if firma_cliente is not None:
            formato.firma_cliente.save(
                'firma_cliente.png',
                firma_cliente,
                save=False,
            )

        formato.actualizado_por = empleado
        formato.save()

        # --- Vistas de daño anotadas ---
        vistas = payload.get('vistas_dano') or []
        if isinstance(vistas, list):
            for item in vistas:
                if not isinstance(item, dict):
                    continue
                clave = str(item.get('clave_vista') or '').strip()[:40]
                if not clave:
                    continue
                etiqueta = str(item.get('etiqueta_dano') or '')[:80]
                vista, _ = DanoEsteticoVista.objects.get_or_create(
                    formato=formato,
                    clave_vista=clave,
                    defaults={'etiqueta_dano': etiqueta},
                )
                vista.etiqueta_dano = etiqueta
                imagen = _decode_data_url(item.get('imagen_data') or '')
                if imagen is not None:
                    vista.imagen_anotada.save(
                        f'{clave}.png',
                        imagen,
                        save=False,
                    )
                vista.save()

    return formato


def texto_aviso_privacidad_actual() -> tuple[str, str]:
    """
    Devuelve (version, texto) del aviso según el país del request/tenant.

    Returns:
        tuple: (version, texto_completo_o_placeholder)
    """
    pais = get_pais_actual()
    codigo = (pais.get('codigo') or 'MX').upper()
    if codigo == 'MX':
        from config.constants import AVISO_PRIVACIDAD_OOW_MX
        return AVISO_PRIVACIDAD_OOW_VERSION_MX, AVISO_PRIVACIDAD_OOW_MX
    from config.constants import AVISO_PRIVACIDAD_OOW_PLACEHOLDER_OTROS
    return f'{codigo.lower()}-placeholder', AVISO_PRIVACIDAD_OOW_PLACEHOLDER_OTROS


def finalizar_formato(
    formato: FormatoServicioOOW,
    usuario=None,
    forzar_regenerar: bool = False,
) -> FormatoServicioOOW:
    """
    Valida, genera PDF estilo cotización y marca el formato como finalizado.

    Args:
        formato: FormatoServicioOOW en borrador (o finalizado si forzar_regenerar)
        usuario: User opcional
        forzar_regenerar: Si True, regenera PDF aunque ya esté finalizado

    Returns:
        FormatoServicioOOW finalizado con pdf guardado

    Raises:
        FormatoOOWError: si faltan aceptaciones o falló el PDF

    Efectos secundarios:
        Genera PDF, guarda FileField, actualiza estado y finalizado_en.
    """
    if formato.estado == 'finalizado' and not forzar_regenerar:
        if formato.pdf:
            return formato
        # Finalizado sin PDF: regenerar

    if not formato.acepta_condiciones:
        raise FormatoOOWError(
            'Debes marcar la aceptación de las condiciones de entrega del equipo.'
        )
    if not formato.acepta_privacidad:
        raise FormatoOOWError(
            'Debes aceptar el Aviso de Privacidad para finalizar el formato.'
        )
    if not formato.firma_cliente:
        raise FormatoOOWError('La firma del cliente es obligatoria.')

    version, _texto = texto_aviso_privacidad_actual()
    formato.version_aviso_privacidad = version

    # Generar PDF (import diferido para evitar ciclos)
    from servicio_tecnico.utils.pdf_formato_oow import PDFFormatoServicioOOW

    generador = PDFFormatoServicioOOW(formato)
    resultado = generador.generar_pdf()
    if not resultado.get('success') or not resultado.get('buffer'):
        raise FormatoOOWError(
            resultado.get('error') or 'No se pudo generar el PDF del formato OOW.'
        )

    empleado = _empleado_desde_usuario(usuario)
    nombre_archivo = resultado.get('nombre_archivo') or (
        f"FormatoOOW_{formato.orden.numero_orden_interno}.pdf"
    )
    pdf_bytes = resultado['buffer'].getvalue()

    with transaction.atomic():
        formato.pdf.save(nombre_archivo, ContentFile(pdf_bytes), save=False)
        formato.estado = 'finalizado'
        formato.finalizado_en = timezone.now()
        formato.actualizado_por = empleado
        formato.save()

    logger.info(
        'Formato OOW finalizado orden=%s pdf=%s',
        formato.orden.numero_orden_interno,
        nombre_archivo,
    )
    return formato
