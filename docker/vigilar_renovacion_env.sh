#!/bin/bash
# Cron de sic-sigma: apaga SIGMA y borra docker/.env si nadie renovó en 60 días.
#
# EXPLICACIÓN PARA PRINCIPIANTES:
# 1. Lee la fecha que guardó la pantalla de SIGMA
#    (archivo ultima_ok, en el disco de datos).
# 2. Si ese archivo no existe, no hace nada. El candado no está armado.
# 3. Si la fecha tiene más de 60 días, PRIMERO apaga los contenedores
#    (todavía con el .env presente) y DESPUÉS borra docker/.env.
# 4. No toca Postgres, fotos ni respaldos.
#
# Este script NO se instala solo. En el servidor, después de armar la
# clave en la pantalla, agrega esta línea al crontab (04:00, hora del
# reloj de sic-sigma; el respaldo sigue a las 03:00):
#
#   0 4 * * * /srv/sic/apps/sigma/docker/vigilar_renovacion_env.sh
#
# 60 tiene que coincidir con DIAS_VIGENCIA en inventario/renovacion_env.py.
# Quien tenga SSH puede apagar este cron: no está escondido.

set -euo pipefail

# Misma cifra que inventario/renovacion_env.py (DIAS_VIGENCIA).
DIAS_VIGENCIA=60

APP_DIR="/srv/sic/apps/sigma"
DATA_DIR="/srv/sic/data/sigma"
SELLO="${DATA_DIR}/renovacion/ultima_ok"
LOG_DIR="${DATA_DIR}/logs"
LOG_FILE="${LOG_DIR}/renovacion_env.log"

# En la laptop esa ruta no existe. Salir aquí evita borrar un .env de pruebas.
if [ ! -d "$APP_DIR" ]; then
    echo "Este cron solo corre en sic-sigma. No existe ${APP_DIR}."
    exit 0
fi

mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Si la corrida de ayer sigue viva, esta no se empalma.
exec 9>/tmp/vigilar_renovacion_env.lock
if ! flock -n 9; then
    log "Ya hay una vigilancia en curso. Se omite esta corrida."
    exit 0
fi

# Sin sello = nadie armó el candado en la pantalla. No borrar.
if [ ! -f "$SELLO" ]; then
    log "Sin sello en ${SELLO}. El candado no está armado. No se borra nada."
    exit 0
fi

contenido="$(tr -d '[:space:]' < "$SELLO")"
if [ -z "$contenido" ]; then
    log "El sello está vacío. No se borra nada."
    exit 0
fi

# date de GNU entiende la forma 2026-10-07T15:44:00Z que escribe Django.
# Si la fecha está rota, salimos SIN borrar: un archivo dañado no es un vencimiento.
if ! sello_epoch="$(date -u -d "$contenido" +%s 2>/dev/null)"; then
    log "ERROR: no pude leer la fecha del sello (${contenido}). No se borra docker/.env."
    exit 1
fi

ahora="$(date -u +%s)"
edad="$((ahora - sello_epoch))"
limite="$((DIAS_VIGENCIA * 24 * 3600))"

# Igual que en Python: a los 60 días exactos todavía está vigente.
# Se borra solo cuando la edad es MAYOR a ese límite.
if [ "$edad" -le "$limite" ]; then
    dias_pasados="$((edad / 86400))"
    log "Renovación vigente (${dias_pasados} de ${DIAS_VIGENCIA} días). No se borra nada."
    exit 0
fi

if [ ! -f "${APP_DIR}/docker/.env" ]; then
    log "El plazo ya venció, pero docker/.env ya no está. No hay nada que borrar."
    exit 0
fi

cd "$APP_DIR"

log "Plazo vencido. Apagando el stack antes de borrar docker/.env."
# --env-file es obligatorio: sin él Compose leería otro .env.
# No usamos -v: eso sí borraría el disco de Postgres.
if ! docker compose --env-file docker/.env --profile cloudflare down; then
    log "ERROR al apagar el stack. docker/.env sigue en su sitio."
    exit 1
fi

rm -f docker/.env
log "docker/.env borrado. Restaura tu copia, levanta el stack y renueva en la pantalla antes de la siguiente corrida. Si olvidaste la clave, borra ${SELLO} por SSH para desarmar el candado."
