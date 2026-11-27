#!/bin/sh

set -eu

umask 077


# ======================================
# VALIDAR CONFIGURACION
# ======================================

if [ "$(id -u)" != "0" ]; then

    echo "ERROR: se requiere root para preparar el volumen." >&2

    exit 1

fi


FUSEKI_USER="${FUSEKI_USER:-}"

FUSEKI_PASSWORD="${FUSEKI_PASSWORD:-}"

PORT="${PORT:-3030}"


if [ "$FUSEKI_USER" != "fp_backend" ]; then

    echo "ERROR: usuario tecnico Fuseki invalido." >&2

    exit 1

fi


case "$FUSEKI_PASSWORD" in

    ""|*[!A-Za-z0-9_-]*)

        echo "ERROR: password Fuseki invalida." >&2

        exit 1
        ;;

esac


LONGITUD="${#FUSEKI_PASSWORD}"


if [ "$LONGITUD" -lt 32 ] || \
   [ "$LONGITUD" -gt 128 ]; then

    echo "ERROR: longitud de password invalida." >&2

    exit 1

fi


case "$PORT" in

    ""|*[!0-9]*)

        echo "ERROR: puerto invalido." >&2

        exit 1
        ;;

esac


if [ "${#PORT}" -gt 5 ] || \
   [ "$PORT" -lt 1 ] || \
   [ "$PORT" -gt 65535 ]; then

    echo "ERROR: puerto fuera de rango." >&2

    exit 1

fi


# ======================================
# VALIDAR VOLUMEN PERSISTENTE
# ======================================

if ! mountpoint -q /datos/tdb2; then

    echo "ERROR: falta el volumen persistente TDB2." >&2

    exit 1

fi


chown 10001:10001 /datos/tdb2

chmod 700 /datos/tdb2


# ======================================
# CONFIGURAR AUTENTICACION
# ======================================

mkdir -p /run/fuseki

chmod 700 /run/fuseki


printf '%s: %s\n' \
    "$FUSEKI_USER" \
    "$FUSEKI_PASSWORD" \
    > /run/fuseki/passwd


chown 10001:10001 \
    /run/fuseki \
    /run/fuseki/passwd


chmod 600 /run/fuseki/passwd


unset FUSEKI_PASSWORD

unset FUSEKI_USER


# ======================================
# ARRANCAR FUSEKI SIN ROOT
# ======================================

echo "Fuseki: autenticacion configurada."

echo "Fuseki: volumen persistente disponible."

echo "Fuseki: iniciando servidor en puerto $PORT."


exec gosu fuseki java \
    -Xms64m \
    -Xmx192m \
    -Xss512k \
    -XX:+UseSerialGC \
    -XX:ActiveProcessorCount=1 \
    -XX:MaxDirectMemorySize=64m \
    -XX:ReservedCodeCacheSize=48m \
    -XX:+ExitOnOutOfMemoryError \
    -Dlog4j2.configurationFile=/opt/fuseki/log4j2.properties \
    -cp /opt/fuseki/fuseki.jar \
    org.apache.jena.fuseki.main.cmds.FusekiMainCmd \
    --conf=/opt/fuseki/config.ttl \
    --port="$PORT"