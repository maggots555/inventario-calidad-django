#!/bin/sh
# Levanta SIGMA en Docker usando docker/.env, no el .env de SQLite de la laptop.
#
# EXPLICACIÓN PARA PRINCIPIANTES:
# Compose, si no le dices nada, lee el archivo .env de la raíz. Ese archivo
# es el de desarrollo (SQLite). Este script le pide que lea docker/.env,
# donde están Postgres, Redis y el puerto 8080.

set -eu

cd "$(dirname "$0")/.."

if [ ! -f docker/.env ]; then
    cp docker/.env.example docker/.env
    echo "Se creó docker/.env a partir del ejemplo. Sirve para pruebas locales."
fi

exec docker compose --env-file docker/.env up -d --build "$@"
