"""
Candado de renovación de docker/.env.

EXPLICACIÓN PARA PRINCIPIANTES:
El archivo docker/.env del servidor guarda claves (base de datos, túnel,
respaldos). Esta pieza NO borra ese archivo. Solo guarda, en una carpeta
del disco, dos cosas:

1. clave.hash — la contraseña de renovación, ya transformada (no se puede
   leer de vuelta).
2. ultima_ok — la fecha UTC de la última vez que un superusuario escribió
   la contraseña bien.

Un cron del servidor (docker/vigilar_renovacion_env.sh) lee ultima_ok.
Si pasaron más de 60 días, apaga SIGMA y borra docker/.env.
Si ultima_ok no existe, el cron no hace nada: el candado no está armado.
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timedelta, timezone as tz_std
from pathlib import Path

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone

# 60 días ≈ 2 meses. El script del cron usa el mismo número.
# Si cambias uno, cambia el otro: si no, la pantalla y el cron no coinciden.
DIAS_VIGENCIA = 60
MIN_LARGO_CLAVE = 8

_NOMBRE_HASH = 'clave.hash'
_NOMBRE_SELLO = 'ultima_ok'
# La carpeta la crea el contenedor (root). El cron corre como el usuario
# sigma, así que tiene que poder entrar y leer la fecha. La fecha no es
# un secreto. El hash de la clave sí se queda solo para el dueño.
_MODO_CARPETA = 0o755
_MODO_SELLO = 0o644
_MODO_HASH = 0o600


def carpeta_renovacion() -> Path:
    """
    Carpeta donde viven el hash y el sello.

    Returns:
        Path absoluto. En Docker es /app/renovacion (disco del servidor).
        En la laptop, docker-data/renovacion, salvo que el test la cambie.

    Efectos secundarios:
        Ninguno. No crea la carpeta.
    """
    configurada = getattr(settings, 'RENOVACION_ENV_DIR', '') or ''
    if configurada:
        return Path(configurada)
    return Path(settings.BASE_DIR) / 'docker-data' / 'renovacion'


def hay_clave() -> bool:
    """
    Dice si el candado ya tiene contraseña guardada.

    Returns:
        True si existe clave.hash con texto adentro.

    Efectos secundarios:
        Ninguno. Solo lee el disco.
    """
    ruta = carpeta_renovacion() / _NOMBRE_HASH
    if not ruta.is_file():
        return False
    return bool(ruta.read_text(encoding='utf-8').strip())


def guardar_clave_inicial(clave: str) -> None:
    """
    Arma el candado: guarda el hash y escribe el primer sello (hoy).

    Args:
        clave: Contraseña en texto plano. Mínimo 8 caracteres.
            No es la clave de inicio de sesión de SIGMA.

    Efectos secundarios:
        Crea la carpeta si no existe. Escribe clave.hash y ultima_ok.
        A partir de ese momento el cron del servidor puede borrar
        docker/.env si pasan 60 días sin renovar.

    Raises:
        ValueError: La clave es corta, o ya había una guardada.
    """
    _exigir_largo(clave)
    if hay_clave():
        raise ValueError(
            'Ya hay una clave de renovación. Para cambiarla usa el formulario de cambio.'
        )
    # El hash no se puede revertir. Ni el cron ni un respaldo de texto
    # muestran la contraseña: solo sirven para comprobarla después.
    _escribir_archivo(_NOMBRE_HASH, make_password(clave), _MODO_HASH)
    _escribir_sello(timezone.now())


def comprobar_clave(clave: str) -> bool:
    """
    Compara lo que escribió la persona contra el hash del disco.

    Args:
        clave: Texto que llegó del formulario.

    Returns:
        True si coincide. False si no hay hash o no coincide.

    Efectos secundarios:
        Ninguno. No mueve la fecha del sello.
    """
    ruta = carpeta_renovacion() / _NOMBRE_HASH
    if not ruta.is_file():
        return False
    guardado = ruta.read_text(encoding='utf-8').strip()
    if not guardado:
        return False
    return check_password(clave, guardado)


def renovar(clave: str) -> bool:
    """
    Si la clave es correcta, mueve el sello a este momento.

    Args:
        clave: Contraseña de renovación, no la de login.

    Returns:
        True si se renovó. False si la clave no coincide.

    Efectos secundarios:
        Reescribe ultima_ok con la fecha UTC de ahora.
        No toca docker/.env.
    """
    if not comprobar_clave(clave):
        return False
    _escribir_sello(timezone.now())
    return True


def cambiar_clave(anterior: str, nueva: str) -> bool:
    """
    Sustituye la clave si la anterior es correcta, y renueva el sello.

    Args:
        anterior: Clave que ya está guardada.
        nueva: Clave que va a quedar. Mínimo 8 caracteres.

    Returns:
        True si quedó cambiada. False si la anterior no coincide.

    Efectos secundarios:
        Reescribe clave.hash y ultima_ok.

    Raises:
        ValueError: La clave nueva es demasiado corta.
    """
    if not comprobar_clave(anterior):
        return False
    _exigir_largo(nueva)
    _escribir_archivo(_NOMBRE_HASH, make_password(nueva), _MODO_HASH)
    # Quien acaba de demostrar la clave anterior también "renovó":
    # el cron vuelve a contar 60 días desde ahora.
    _escribir_sello(timezone.now())
    return True


def leer_sello() -> datetime | None:
    """
    Lee la fecha de la última renovación correcta.

    Returns:
        Datetime con zona UTC, o None si no hay sello o el texto está roto.
        None significa "candado no armado" para el cron: no se borra nada.

    Efectos secundarios:
        Ninguno.
    """
    ruta = carpeta_renovacion() / _NOMBRE_SELLO
    if not ruta.is_file():
        return None
    texto = ruta.read_text(encoding='utf-8').strip()
    if not texto:
        return None
    try:
        # El archivo guarda "2026-10-07T15:44:00Z" para que bash lo lea fácil.
        momento = datetime.fromisoformat(texto.replace('Z', '+00:00'))
    except ValueError:
        return None
    if timezone.is_naive(momento):
        return timezone.make_aware(momento, tz_std.utc)
    return momento


def dias_restantes(ahora: datetime | None = None) -> int | None:
    """
    Cuántos días faltan para que el cron considere vencido el sello.

    Args:
        ahora: Momento de referencia. None = ahora mismo (útil en tests).

    Returns:
        None si no hay sello. Un entero si hay sello (puede ser negativo
        cuando ya se pasó de los 60 días).

    Efectos secundarios:
        Ninguno.
    """
    sello = leer_sello()
    if sello is None:
        return None
    momento = ahora if ahora is not None else timezone.now()
    limite = sello + timedelta(days=DIAS_VIGENCIA)
    segundos = (limite - momento).total_seconds()
    # Hacia arriba mientras quede tiempo: si acabas de renovar, la pantalla
    # dice 60, no 59. Si ya se pasó, el número es negativo (días de atraso).
    if segundos > 0:
        return math.ceil(segundos / 86400)
    return math.floor(segundos / 86400)


def esta_vencido(ahora: datetime | None = None) -> bool:
    """
    Decide si ya pasó el plazo de 60 días.

    Args:
        ahora: Momento de referencia. None = ahora mismo.

    Returns:
        False si no hay sello (no armado) o si todavía está dentro del plazo.
        True solo cuando el momento actual es posterior al sello + 60 días.
        En el instante exacto de los 60 días todavía no está vencido:
        el cron borra cuando la edad es mayor, no igual.

    Efectos secundarios:
        Ninguno. No borra archivos.
    """
    sello = leer_sello()
    if sello is None:
        return False
    momento = ahora if ahora is not None else timezone.now()
    return momento > sello + timedelta(days=DIAS_VIGENCIA)


def _exigir_largo(clave: str) -> None:
    """Rechaza una clave vacía o de menos de 8 caracteres."""
    if clave is None or len(clave) < MIN_LARGO_CLAVE:
        raise ValueError(
            f'La clave de renovación necesita al menos {MIN_LARGO_CLAVE} caracteres.'
        )


def _escribir_sello(momento: datetime) -> None:
    """
    Guarda la fecha en UTC, en una sola línea, terminada en Z.

    Efectos secundarios:
        Reescribe ultima_ok. Ese archivo es el que mira el cron.
    """
    # Pasamos a UTC para que el servidor y la laptop no peleen por el huso.
    utc = momento.astimezone(tz_std.utc)
    texto = utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    _escribir_archivo(_NOMBRE_SELLO, texto, _MODO_SELLO)


def _escribir_archivo(nombre: str, contenido: str, modo: int) -> None:
    """
    Escribe un archivo de la carpeta de renovación de forma atómica.

    Args:
        nombre: clave.hash o ultima_ok.
        contenido: Texto completo, sin salto de línea extra.
        modo: Permisos del archivo (por ejemplo 0o644 para el sello).

    Efectos secundarios:
        Crea la carpeta si falta y la deja en 755, para que el usuario
        sigma pueda entrar. Escribe un temporal y lo renombra, para no
        dejar el archivo a la mitad si el proceso se corta.
    """
    carpeta = carpeta_renovacion()
    carpeta.mkdir(parents=True, exist_ok=True)
    # El contenedor es root. Sin este chmod, la carpeta puede quedar
    # cerrada y el cron (usuario sigma) no puede ni asomarse.
    os.chmod(carpeta, _MODO_CARPETA)
    destino = carpeta / nombre
    temporal = carpeta / f'.{nombre}.tmp'
    # Paso 1: el temporal. Si falla aquí, el archivo bueno sigue intacto.
    temporal.write_text(contenido, encoding='utf-8')
    os.chmod(temporal, modo)
    # Paso 2: el renombre es el momento en que el cron ve el dato nuevo.
    temporal.replace(destino)
