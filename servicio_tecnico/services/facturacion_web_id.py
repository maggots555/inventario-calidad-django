"""
Generación y lectura del `webId` del autofacturador.

Objetivo de negocio:
    El cliente entra al portal de facturación y teclea un identificador corto.
    Ese identificador se llama `webId` y lo produce SIGMA con esta forma:

        SAT9596-1
        └┬┘ └┬─┘ └┬
         │   │    └── tipo de documento: 1 = PUE, 2 = PPD
         │   └─────── dígitos del folio del cliente (OOW-9596 → 9596)
         └─────────── prefijo de la sucursal (Sucursal.prefijo_facturacion)

EXPLICACIÓN PARA PRINCIPIANTES — ¿por qué tres partes?
    * El prefijo evita choques: puede existir OOW-1234 en Satélite y FL-1234
      en Drop Off. Con SAT1234 y DROP1234 ya no hay duda de cuál es cuál.
    * El sufijo permite que una misma orden tenga dos facturas distintas:
      el diagnóstico pagado al 100% (PUE) y el anticipo de la reparación (PPD).

Somos tolerantes al leer: si el portal manda `SAT9596` (sin sufijo) o incluso
`9596` (como en las primeras pruebas), igual resolvemos siempre que no haya
ambigüedad. Somos estrictos al generar: siempre con prefijo y sufijo.

Efectos secundarios:
    Ninguno. Este módulo solo arma y descompone texto, y busca en BD para
    resolver. Quien crea documentos es facturacion_documentos.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from django.core.exceptions import ObjectDoesNotExist

from servicio_tecnico.models_facturacion import DocumentoFiscalOrden

# Un webId válido: letras opcionales + dígitos + sufijo opcional.
# Ejemplos que acepta: SAT9596-1, SAT9596, 9596, sat9596-2.
PATRON_WEB_ID = re.compile(r'^([A-Z]*)(\d+)(?:-(\d+))?$')

# Traducción inversa del sufijo numérico al tipo del modelo.
TIPO_POR_SUFIJO = {
    codigo: tipo for tipo, codigo in DocumentoFiscalOrden.CODIGO_TIPO.items()
}


@dataclass(frozen=True)
class PartesWebId:
    """
    Las tres piezas de un webId ya separadas.

    Args/campos:
        prefijo: sucursal ('SAT'). Cadena vacía si el portal no lo mandó.
        digitos: folio del cliente sin ceros a la izquierda ('9596').
        tipo: 'pue' / 'ppd'. None si el portal no mandó sufijo.
    """

    prefijo: str
    digitos: str
    tipo: Optional[str]

    @property
    def numero(self) -> int:
        """Los dígitos como entero, para comparar folios (0123 == 123)."""
        return int(self.digitos)


def extraer_digitos(texto: str) -> str:
    """
    Deja solo los números de un folio de cliente.

    Args:
        texto: ej. 'OOW-11902' o 'FL-2026-0001'.

    Returns:
        str: '11902' o '20260001'. Cadena vacía si no hay dígitos.
    """
    return ''.join(caracter for caracter in (texto or '') if caracter.isdigit())


def prefijo_de_orden(orden) -> str:
    """
    Prefijo de facturación de la sucursal de la orden.

    Args:
        orden: OrdenServicio.

    Returns:
        str: 'SAT', 'DROP'… o '' si la sucursal no factura (sucursal de prueba
        o sin prefijo capturado en el admin).
    """
    sucursal = getattr(orden, 'sucursal', None)
    if sucursal is None:
        return ''
    return (sucursal.prefijo_facturacion or '').strip().upper()


def digitos_de_orden(orden) -> str:
    """
    Dígitos del folio que ve el cliente (`DetalleEquipo.orden_cliente`).

    Args:
        orden: OrdenServicio.

    Returns:
        str: '9596' o cadena vacía si la orden no tiene folio de cliente.

    Efectos secundarios:
        Lee DetalleEquipo (una consulta si no viene en select_related).
    """
    try:
        folio = (orden.detalle_equipo.orden_cliente or '').strip()
    except ObjectDoesNotExist:
        return ''
    digitos = extraer_digitos(folio)
    # Paso: quitamos ceros a la izquierda para que 0123 y 123 sean el mismo
    # webId y no existan dos documentos para el mismo folio.
    return str(int(digitos)) if digitos else ''


def construir_web_id(orden, tipo: str) -> str:
    """
    Arma el webId definitivo de un documento fiscal.

    Args:
        orden: OrdenServicio dueña del documento.
        tipo: DocumentoFiscalOrden.TIPO_PUE o TIPO_PPD.

    Returns:
        str: 'SAT9596-1'. Cadena vacía si falta prefijo o folio, que es la
        forma de decir "esta orden todavía no se puede autofacturar".
    """
    prefijo = prefijo_de_orden(orden)
    digitos = digitos_de_orden(orden)
    sufijo = DocumentoFiscalOrden.SUFIJO_TIPO.get(tipo)
    # Paso: si falta cualquiera de las tres piezas no inventamos nada.
    if not prefijo or not digitos or not sufijo:
        return ''
    return f'{prefijo}{digitos}-{sufijo}'


def desglosar_web_id(web_id: str) -> Optional[PartesWebId]:
    """
    Separa un webId recibido del portal en sus tres piezas.

    Args:
        web_id: texto crudo del path del API ('SAT9596-1', 'sat9596', '9596').

    Returns:
        PartesWebId o None si el texto no tiene forma de webId (por ejemplo
        viene vacío, con símbolos raros o sin un solo dígito).
    """
    bruto = str(web_id or '').strip().upper()
    # Paso 1: toleramos separadores que un humano teclea de más.
    bruto = bruto.replace(' ', '').replace('_', '-')
    coincidencia = PATRON_WEB_ID.match(bruto)
    if not coincidencia:
        return None

    prefijo, digitos, sufijo = coincidencia.groups()
    # Paso 2: el sufijo solo vale si es un tipo que conocemos (1 o 2).
    tipo = None
    if sufijo is not None:
        tipo = TIPO_POR_SUFIJO.get(int(sufijo))
        if tipo is None:
            return None

    # Paso 3: normalizamos los dígitos igual que al generar (sin ceros).
    return PartesWebId(prefijo=prefijo, digitos=str(int(digitos)), tipo=tipo)


def filtrar_ordenes_por_prefijo(ordenes: list, prefijo: str) -> list:
    """
    Reduce una lista de órdenes a las de una sucursal concreta.

    Objetivo: cuando dos folios distintos comparten los mismos dígitos, el
    prefijo del webId nos dice cuál quiso el cliente.

    Args:
        ordenes: candidatas que ya coinciden en dígitos.
        prefijo: 'SAT', 'DROP'… Si viene vacío no filtramos nada.

    Returns:
        list: las órdenes cuya sucursal tiene ese prefijo.
    """
    if not prefijo:
        return ordenes
    coincidentes = [
        orden for orden in ordenes if prefijo_de_orden(orden) == prefijo
    ]
    # Paso: si el prefijo no descarta a nadie (o descarta a todos), devolvemos
    # la lista original para que el llamador decida el error correcto.
    return coincidentes or ordenes
