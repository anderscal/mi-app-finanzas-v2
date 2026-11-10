
import {
    obtenerOperacionesLocales,
    actualizarOperacionLocal,
    eliminarOperacion
} from "./offline-db.js";


export const API_URL = "http://127.0.0.1:8000";

const RUTAS = {
    MOVIMIENTO_NORMAL: "/movimientos/normales",
    TRANSFERENCIA: "/transferencias/",
    ABONO_OBLIGACION: "/obligaciones/abonos"
};

function describirErrorHTTP(cuerpo) {
    const detalle = cuerpo?.detail;

    if (typeof detalle === "string") {
        return detalle;
    }

    if (Array.isArray(detalle)) {
        return detalle.map(error => {
            const campo = Array.isArray(error.loc)
                ? error.loc.join(".")
                : "datos";

            return `${campo}: ${error.msg || "Valor inválido"}`;
        }).join(" | ");
    }

    return "La operación fue rechazada";
}

let sincronizando = false;


export async function sincronizarPendientes({
    token,
    usuarioId,
    onEvento = () => { }
}) {
    if (!token || !usuarioId) {
        throw new Error(
            "Debes iniciar sesión antes de sincronizar"
        );
    }

    if (sincronizando) {
        onEvento("Ya hay una sincronización en curso");
        return;
    }

    sincronizando = true;

    const resumen = {
        sincronizadas: 0,
        pendientes: 0,
        errores: 0
    };

    try {
        const todas = await obtenerOperacionesLocales();

        // Solo operaciones pertenecientes
        // al usuario actualmente autenticado.
        const operaciones = todas
            .filter(op =>
                op.usuario_id === usuarioId &&
                RUTAS[op.tipo_operacion] &&
                (
                    op.estado_sync === "PENDIENTE" ||
                    op.estado_sync === "ERROR"
                )
            )
            .sort((a, b) =>
                a.fecha_local.localeCompare(b.fecha_local)
            );

        for (const operacion of operaciones) {

            // No avanzar sobre un error anterior:
            // otra operación puede depender de él.

            if (operacion.estado_sync === "ERROR") {
                onEvento(
                    "Sincronización detenida: existe una operación " +
                    "anterior que requiere revisión.\n" +
                    "UUID: " + operacion.uuid_operacion + "\n" +
                    "Motivo: " + (
                        operacion.ultimo_error ||
                        "Error no especificado"
                    ) + "\n" +
                    "Revisa o descarta esa operación antes " +
                    "de continuar con las siguientes."
                );

                resumen.errores++;
                break;
            }


            const uuid = operacion.uuid_operacion;

            await actualizarOperacionLocal(uuid, {
                intentos: (operacion.intentos || 0) + 1,
                ultimo_error: null
            });

            let respuesta;

            try {
                respuesta = await fetch(
                    API_URL + RUTAS[operacion.tipo_operacion],
                    {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "Authorization": `Bearer ${token}`
                        },
                        body: JSON.stringify(operacion.datos)
                    }
                );
            } catch (error) {
                await actualizarOperacionLocal(uuid, {
                    estado_sync: "PENDIENTE",
                    ultimo_error: "Sin conexión con FastAPI"
                });

                onEvento(
                    "Sin conexión. La operación sigue pendiente."
                );

                resumen.pendientes++;
                break;
            }

            const cuerpo = await respuesta.json()
                .catch(() => ({}));

            if (respuesta.ok) {
                const campoUuid =
                    operacion.tipo_operacion === "TRANSFERENCIA"
                        ? "uuid_operacion"
                        : "uuid_local";

                const confirmado =
                    typeof cuerpo.creado === "boolean" &&
                    String(cuerpo[campoUuid]).toLowerCase() ===
                    String(uuid).toLowerCase();


                if (!confirmado) {
                    await actualizarOperacionLocal(uuid, {
                        estado_sync: "PENDIENTE",
                        ultimo_error:
                            "El servidor respondió, pero no fue posible " +
                            "confirmar la operación."
                    });

                    onEvento(
                        "Confirmación no verificable. " +
                        "La operación se conserva para reintentar " +
                        "con el mismo UUID."
                    );

                    resumen.pendientes++;
                    break;
                }


                // Confirmación válida del backend.
                await eliminarOperacion(uuid);

                resumen.sincronizadas++;

                onEvento(
                    cuerpo.creado
                        ? "Operación registrada en PostgreSQL"
                        : "Operación existente reconocida por UUID"
                );

                continue;
            }

            if (respuesta.status === 401) {
                await actualizarOperacionLocal(uuid, {
                    estado_sync: "PENDIENTE",
                    ultimo_error:
                        "Sesión expirada. Inicia sesión nuevamente."
                });

                onEvento(
                    "Sesión expirada: vuelve a iniciar sesión."
                );

                resumen.pendientes++;
                break;
            }

            if ([400, 403, 404, 409, 422].includes(
                respuesta.status
            )) {
                await actualizarOperacionLocal(uuid, {
                    estado_sync: "ERROR",
                    ultimo_error:
                        `HTTP ${respuesta.status}: ` +
                        describirErrorHTTP(cuerpo)
                });

                onEvento(
                    `Operación rechazada: HTTP ${respuesta.status}`
                );

                resumen.errores++;
                break;
            }

            // Fallos del servidor o respuestas transitorias.
            await actualizarOperacionLocal(uuid, {
                estado_sync: "PENDIENTE",
                ultimo_error:
                    `HTTP ${respuesta.status}: reintentar`
            });

            onEvento(
                "El servidor no pudo completar la solicitud."
            );

            resumen.pendientes++;
            break;
        }

        return resumen;

    } finally {
        sincronizando = false;
    }
}
