
import {
    guardarOperacionPendiente,
    obtenerOperacionesLocales
} from "./offline-db.js";

import {
    API_URL,
    sincronizarPendientes
} from "./sync.js";


const elemento = id => document.getElementById(id);

let tokenActual = null;
let usuarioId = null;


let guardando = false;
let formularioGuardado = false;


// Cada usuario tiene su propio borrador.
function claveBorrador() {
    return `finanzas_borrador_${usuarioId}`;
}


// Recuperar el UUID del formulario actual.
// Si no existe, generar uno nuevo.
function obtenerOCrearBorrador() {
    let borrador = null;

    try {
        borrador = JSON.parse(
            localStorage.getItem(claveBorrador())
        );
    } catch {
        borrador = null;
    }

    if (!borrador || !borrador.uuid) {
        borrador = {
            uuid: crypto.randomUUID(),
            guardado: false
        };

        localStorage.setItem(
            claveBorrador(),
            JSON.stringify(borrador)
        );
    }

    return borrador;
}



function informar(mensaje) {
    elemento("resultado").textContent +=
        "\n" + mensaje;
}


function fechaLocalHoy() {
    const hoy = new Date();

    const anio = hoy.getFullYear();
    const mes = String(hoy.getMonth() + 1).padStart(2, "0");
    const dia = String(hoy.getDate()).padStart(2, "0");

    return `${anio}-${mes}-${dia}`;
}


elemento("fecha").value = fechaLocalHoy();


async function mostrarCola() {
    const todas = await obtenerOperacionesLocales();

    const operacionesUsuario = todas.filter(op =>
        op.usuario_id === usuarioId &&
        op.tipo_operacion === "MOVIMIENTO_NORMAL"
    );

    elemento("cola").textContent = JSON.stringify(
        operacionesUsuario,
        null,
        2
    );
}


// -----------------------------------
// BOTÓN 1: LOGIN
// -----------------------------------

elemento("login").addEventListener(
    "click",
    async () => {

        try {
            tokenActual = null;
            usuarioId = null;

            elemento("guardar").disabled = true;
            elemento("sincronizar").disabled = true;

            const formulario = new URLSearchParams({
                username: elemento("email").value.trim(),
                password: elemento("password").value
            });

            const respuestaLogin = await fetch(
                API_URL + "/auth/login",
                {
                    method: "POST",
                    headers: {
                        "Content-Type":
                            "application/x-www-form-urlencoded"
                    },
                    body: formulario
                }
            );

            if (!respuestaLogin.ok) {
                throw new Error(
                    `Login rechazado: HTTP ${respuestaLogin.status}`
                );
            }

            const datosLogin = await respuestaLogin.json();
            const token = datosLogin.access_token;

            const respuestaPerfil = await fetch(
                API_URL + "/auth/me",
                {
                    headers: {
                        Authorization: `Bearer ${token}`
                    }
                }
            );

            if (!respuestaPerfil.ok) {
                throw new Error(
                    "No se pudo verificar el usuario"
                );
            }

            const perfil = await respuestaPerfil.json();

            const respuestaCuentas = await fetch(
                API_URL + "/auth/mis-cuentas",
                {
                    headers: {
                        Authorization: `Bearer ${token}`
                    }
                }
            );

            if (!respuestaCuentas.ok) {
                throw new Error(
                    "No se pudieron consultar las cuentas"
                );
            }

            const datosCuentas = await respuestaCuentas.json();

            tokenActual = token;
            usuarioId = perfil.id_usuario;

            // No conservar la contraseña en el formulario.
            elemento("password").value = "";

            const selector = elemento("cuenta");
            selector.replaceChildren();

            const cuentasActivas = datosCuentas.cuentas.filter(
                cuenta => cuenta.estado === "ACTIVA"
            );

            for (const cuenta of cuentasActivas) {
                const opcion = document.createElement("option");

                opcion.value = cuenta.id_cuenta;
                opcion.textContent =
                    `${cuenta.nombre_cuenta} ` +
                    `(ID ${cuenta.id_cuenta})`;

                selector.appendChild(opcion);
            }

           const borrador = obtenerOCrearBorrador();

formularioGuardado = borrador.guardado;

elemento("guardar").disabled =
    cuentasActivas.length === 0 || formularioGuardado;

elemento("nuevo").disabled =
    cuentasActivas.length === 0 || !formularioGuardado;

            elemento("sincronizar").disabled = false;

            informar(
                `Autenticado: ${perfil.email} ` +
                `(usuario ${usuarioId})`
            );

            informar(
                `Cuentas activas: ${cuentasActivas.length}`
            );

            await mostrarCola();

        } catch (error) {
            informar("ERROR DE LOGIN: " + error.message);
        }
    }
);


// -----------------------------------
// BOTÓN 2: GUARDAR OFFLINE
// -----------------------------------


elemento("guardar").addEventListener(
    "click",
    async () => {

        // Evitar clics simultáneos y repetidos.
        if (!usuarioId || guardando || formularioGuardado) {
            return;
        }

        guardando = true;
        elemento("guardar").disabled = true;

        try {
            const borrador = obtenerOCrearBorrador();

            // Usamos siempre el UUID del borrador.
            const uuid = borrador.uuid;

            const idCuenta = Number(
                elemento("cuenta").value
            );

            const idCategoria = Number(
                elemento("categoria").value
            );

            const monto = elemento("monto").value;

            if (
                !Number.isInteger(idCuenta) ||
                idCuenta <= 0 ||
                !Number.isInteger(idCategoria) ||
                idCategoria <= 0 ||
                !(Number(monto) > 0)
            ) {
                throw new Error(
                    "Cuenta, categoría o monto inválido"
                );
            }

            const datos = {
                uuid_local: uuid,
                id_cuenta: idCuenta,
                id_categoria: idCategoria,
                tipo: "GASTO",
                monto: monto,
                fecha_movimiento: elemento("fecha").value,
                descripcion: elemento("descripcion").value
            };

            // Revisar si el mismo UUID ya está
            // almacenado en IndexedDB.
            const operaciones = await obtenerOperacionesLocales();

            const existente = operaciones.find(
                op => op.uuid_operacion === uuid
            );

            if (existente) {
                // Nunca sobrescribir una operación
                // existente con datos diferentes.
                if (
                    existente.usuario_id !== usuarioId ||
                    existente.tipo_operacion !== "MOVIMIENTO_NORMAL" ||
                    JSON.stringify(existente.datos) !==
                    JSON.stringify(datos)
                ) {
                    throw new Error(
                        "El borrador ya fue guardado con otros datos"
                    );
                }

                informar(
                    "Esta operación ya estaba guardada localmente."
                );

            } else {
                await guardarOperacionPendiente({
                    uuid_operacion: uuid,
                    usuario_id: usuarioId,
                    tipo_operacion: "MOVIMIENTO_NORMAL",
                    datos: datos
                });

                informar(
                    `Operación guardada una sola vez. UUID: ${uuid}`
                );
            }

            // El formulario queda marcado como guardado.
            formularioGuardado = true;

            localStorage.setItem(
                claveBorrador(),
                JSON.stringify({
                    uuid: uuid,
                    guardado: true
                })
            );

            elemento("nuevo").disabled = false;

            await mostrarCola();

        } catch (error) {
            informar(
                "ERROR AL GUARDAR: " + error.message
            );

        } finally {
            guardando = false;

            // No habilitar Guardar si ya fue guardado.
            elemento("guardar").disabled =
                !usuarioId ||
                formularioGuardado ||
                !elemento("cuenta").value;
        }
    }
);


// -----------------------------------
// BOTÓN 3: SINCRONIZAR
// -----------------------------------

elemento("sincronizar").addEventListener(
    "click",
    async () => {

        elemento("sincronizar").disabled = true;

        try {
            const resumen = await sincronizarPendientes({
                token: tokenActual,
                usuarioId: usuarioId,
                onEvento: informar
            });

            informar(
                "Resumen: " + JSON.stringify(resumen)
            );

            await mostrarCola();

        } catch (error) {
            informar(
                "ERROR DE SINCRONIZACIÓN: " + error.message
            );
        } finally {
            elemento("sincronizar").disabled = !usuarioId;
        }
    }
);


elemento("nuevo").addEventListener(
    "click",
    () => {

        if (!usuarioId || guardando) {
            return;
        }

        // Solo una acción explícita inicia
        // una nueva operación financiera.
        const nuevoUUID = crypto.randomUUID();

        localStorage.setItem(
            claveBorrador(),
            JSON.stringify({
                uuid: nuevoUUID,
                guardado: false
            })
        );

        formularioGuardado = false;

        elemento("guardar").disabled =
            !elemento("cuenta").value;

        elemento("nuevo").disabled = true;

        informar(
            "Nueva operación preparada. " +
            "Ahora puedes registrar otro gasto."
        );
    }
);
