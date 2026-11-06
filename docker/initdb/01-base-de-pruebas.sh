#!/bin/sh
# Segunda base, sólo para pruebas de integración (corre al crear el volumen de datos).
set -e
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE DATABASE ${POSTGRES_DB}_test"
