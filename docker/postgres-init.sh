#!/bin/bash
# Crea las bases de los otros países la primera vez que el volumen está vacío.
#
# EXPLICACIÓN PARA PRINCIPIANTES:
# La imagen oficial de PostgreSQL ya crea UNA base: la de POSTGRES_DB
# (inventario_mexico). SIGMA usa una base por país. Este script corre
# una sola vez, cuando la carpeta de datos todavía no existe.
# Si recreas el contenedor pero el volumen sigue ahí, este script NO
# vuelve a correr (los datos se conservan).

set -eu

crear_base() {
    nombre="$1"
    echo "Creando base de datos: ${nombre}"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
        -c "CREATE DATABASE ${nombre} OWNER \"${POSTGRES_USER}\";"
}

crear_base inventario_argentina
crear_base inventario_chile
crear_base inventario_colombia
