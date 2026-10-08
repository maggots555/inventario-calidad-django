"""
Destinatarios y armado del correo del concentrado semanal.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
La página no manda el correo ella sola. Primero arma la lista de
personas (los tres contactos del .env más los Gerentes Generales).
El modal muestra esa lista ya marcada. Al confirmar, la vista solo
acepta correos de esa lista: nadie puede escribir otro a mano.

El HTML del correo vive en la plantilla. Aquí queda el texto plano
(el mismo mensaje, por si el programa de correo no muestra HTML)
y el envío con los dos archivos adjuntos.
"""

from __future__ import annotations

import logging
import re
from typing import Iterable

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger('servicio_tecnico')

# Orden fijo: primero los del .env, después los gerentes de la base.
# Cada tupla es (clave del correo, clave del nombre, etiqueta en el modal).
_CONTACTOS_ENV = (
    ('JEFE_CALIDAD_EMAIL', 'JEFE_CALIDAD_NOMBRE', 'Jefe de Calidad'),
    ('JEFE_CALIDAD_2_EMAIL', 'JEFE_CALIDAD_2_NOMBRE', 'Jefe de Calidad'),
    ('JEFE_GENERAL_EMAIL', 'JEFE_GENERAL_NOMBRE', 'Jefe General'),
)


def _correo_limpio(valor) -> str:
    """
    Quita espacios de un correo. Vacío si no hay texto.

    Args:
        valor: Lo que venga del .env o del formulario.

    Returns:
        str sin espacios a los lados, o cadena vacía.
    """
    return (valor or '').strip()


def destinatarios_concentrado() -> list[dict]:
    """
    Junta a quién se le puede enviar el concentrado.

    Objetivo de negocio:
        El modal debe abrir con los contactos de dirección ya marcados:
        Jefe de Calidad, el segundo jefe de calidad, el jefe general
        (si tienen correo en el .env) y cada empleado activo con rol
        Gerente General que tenga correo.

    Returns:
        Lista de dicts con nombre, email y origen. Sin correos vacíos
        y sin repetir el mismo correo (da igual mayúsculas).

    Efectos secundarios:
        Lee empleados activos con rol gerente_general.
    """
    from inventario.models import Empleado

    vistos: set[str] = set()
    personas: list[dict] = []

    # 1) Los tres contactos del .env. Si el correo está vacío, se omite.
    for clave_email, clave_nombre, origen in _CONTACTOS_ENV:
        email = _correo_limpio(getattr(settings, clave_email, ''))
        clave = email.casefold()
        if not email or clave in vistos:
            continue
        nombre = _correo_limpio(getattr(settings, clave_nombre, '')) or origen
        vistos.add(clave)
        personas.append({'nombre': nombre, 'email': email, 'origen': origen})

    # 2) Gerentes generales activos. Si su correo ya está arriba, no se duplica.
    gerentes = (
        Empleado.objects.filter(rol='gerente_general', activo=True)
        .exclude(email__isnull=True)
        .exclude(email='')
        .order_by('nombre_completo')
    )
    for gerente in gerentes:
        email = _correo_limpio(gerente.email)
        clave = email.casefold()
        if not email or clave in vistos:
            continue
        vistos.add(clave)
        personas.append({
            'nombre': gerente.nombre_completo or 'Gerente General',
            'email': email,
            'origen': 'Gerente General',
        })

    return personas


def filtrar_destinatarios_elegidos(elegidos: Iterable[str]) -> list[str]:
    """
    Se queda solo con los correos que el modal tenía derecho a ofrecer.

    Objetivo de negocio:
        El usuario puede quitar la marca de alguien para este envío.
        No puede agregar un correo que no esté en la lista.

    Args:
        elegidos: Valores del checkbox «destinatarios» del formulario.

    Returns:
        Correos canónicos (como están en el .env o en el empleado),
        en el mismo orden en que llegaron, sin repetidos.

    Efectos secundarios:
        Vuelve a leer la lista permitida (settings + empleados).
    """
    permitidos = {
        persona['email'].casefold(): persona['email']
        for persona in destinatarios_concentrado()
    }
    salida: list[str] = []
    vistos: set[str] = set()
    for crudo in elegidos:
        clave = _correo_limpio(crudo).casefold()
        canonico = permitidos.get(clave)
        if not canonico or clave in vistos:
            continue
        vistos.add(clave)
        salida.append(canonico)
    return salida


def describir_alcance(filtros: dict) -> str:
    """
    Texto corto de qué sucursales cubre este envío.

    Args:
        filtros: El dict de resolver_filtros_concentrado.

    Returns:
        «Todas las sucursales», el nombre del grupo o el de la sucursal.
    """
    parametro = filtros.get('sucursal_param')
    if parametro == 'grupo_cis':
        return 'CIS (Drop Off + Satélite)'
    if parametro == 'grupo_foranea':
        return 'Foráneas'
    sucursal_id = filtros.get('sucursal_id')
    if sucursal_id:
        for sucursal in filtros.get('sucursales') or []:
            if sucursal.id == sucursal_id:
                return sucursal.nombre
        return 'Sucursal seleccionada'
    return 'Todas las sucursales'


def signo_variacion(valor: int) -> str:
    """
    Pone el signo + cuando la semana subió respecto a la anterior.

    Args:
        valor: Diferencia (esta semana menos la anterior).

    Returns:
        str como «+3», «0» o «-2».
    """
    if valor > 0:
        return f'+{valor}'
    return str(valor)


def remitente_sistema() -> str:
    """
    Nombre visible del From en este aviso interno.

    Returns:
        str tipo «Sistema SIGMA — Servicio Técnico <correo@empresa>».
    """
    bruto = settings.DEFAULT_FROM_EMAIL
    encontrado = re.search(r'<(.+?)>', bruto)
    correo = encontrado.group(1) if encontrado else bruto
    return f'Sistema SIGMA — Servicio Técnico <{correo}>'


def texto_plano_concentrado(contexto: dict) -> str:
    """
    El mismo aviso, en texto plano, para quien no ve el HTML.

    Args:
        contexto: Semana, alcance y las cuatro cifras del resumen.

    Returns:
        Cuerpo text/plain. Menciona que el Excel y el PDF van adjuntos.
    """
    return (
        f"Concentrado semanal — Semana {contexto['numero_semana']} "
        f"de {contexto['año']}\n"
        f"{contexto['lunes']} al {contexto['viernes']}\n"
        f"Alcance: {contexto['alcance']}\n"
        "\n"
        f"Ingresaron: {contexto['ingresaron']} "
        f"(vs sem. ant. {contexto['variacion_ingresaron']})\n"
        f"Salieron: {contexto['salieron']} "
        f"(vs sem. ant. {contexto['variacion_salieron']})\n"
        f"Balance: {contexto['balance']} "
        f"(vs sem. ant. {contexto['variacion_balance']})\n"
        f"Candidatos RHITSO: {contexto['candidatos_rhitso']} "
        f"(vs sem. ant. {contexto['variacion_rhitso']})\n"
        "\n"
        "Los candidatos RHITSO ya están contados con su técnico. "
        "No son un ingreso extra.\n"
        "\n"
        "El Excel y el PDF de esta semana van adjuntos a este correo.\n"
    )


def enviar_correo_concentrado(
    *,
    destinatarios: list[str],
    contexto: dict,
    excel_bytes: bytes,
    pdf_bytes: bytes,
    nombre_excel: str,
    nombre_pdf: str,
) -> int:
    """
    Manda un solo correo con el resumen y los dos archivos.

    Objetivo de negocio:
        Dirección recibe el concentrado de la semana que estaba en
        pantalla, sin tener que descargarlo y reenviarlo a mano.

    Args:
        destinatarios: Correos ya filtrados. Todos van en Para.
        contexto: Datos que rellena la plantilla HTML y el texto plano.
        excel_bytes: Archivo .xlsx ya generado.
        pdf_bytes: Archivo .pdf ya generado.
        nombre_excel: Nombre del adjunto Excel.
        nombre_pdf: Nombre del adjunto PDF.

    Returns:
        1 si se envió, 0 si no había destinatarios.

    Efectos secundarios:
        Envía por el backend de correo de Django (SMTP en producción).
        Adjunta el logo blanco por CID para la barra de marca.
    """
    if not destinatarios:
        return 0

    html = render_to_string(
        'servicio_tecnico/emails/concentrado_semanal_staff.html',
        contexto,
    )
    texto = texto_plano_concentrado(contexto)
    asunto = (
        f"Concentrado semanal — Semana {contexto['numero_semana']} "
        f"de {contexto['año']}"
    )

    # Un solo mensaje para todos: así no se manda una copia por persona.
    mensaje = EmailMultiAlternatives(
        subject=asunto,
        body=texto,
        from_email=remitente_sistema(),
        to=destinatarios,
    )
    mensaje.attach_alternative(html, 'text/html')
    mensaje.attach(
        nombre_excel,
        excel_bytes,
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    mensaje.attach(nombre_pdf, pdf_bytes, 'application/pdf')

    from servicio_tecnico.services.email_cid_assets import adjuntar_logo_blanco_email
    adjuntar_logo_blanco_email(mensaje, '[CONCENTRADO]')

    mensaje.send(fail_silently=False)
    logger.info(
        '[CONCENTRADO] Correo semana %s enviado a %s',
        contexto.get('numero_semana'),
        ', '.join(destinatarios),
    )
    return 1
