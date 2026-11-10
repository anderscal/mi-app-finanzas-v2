import {
    guardarOperacionPendiente,
    obtenerOperacionesLocales,
    actualizarOperacionLocal,
    eliminarOperacion
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


let erroresVisibles = [];


function obtenerErrorSeleccionado() {
    const uuid = elemento("operacionError").value;

    return erroresVisibles.find(
        op => op.uuid_operacion === uuid
    );
}


function actualizarBotonesError() {
    const operacion = obtenerErrorSeleccionado();

    const es422 = String(
        operacion?.ultimo_error || ""
    ).startsWith("HTTP 422");

    // Un 422 requiere corregir el contenido.
    // No sirve reenviar idénticos datos inválidos.
    elemento("reintentarError").disabled =
        !operacion || es422;

    elemento("descartarError").disabled =
        !operacion;
}

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

    // Recuperar únicamente las operaciones
    // rechazadas del usuario autenticado.
    erroresVisibles = operacionesUsuario.filter(
        op => op.estado_sync === "ERROR"
    );

    const selector = elemento("operacionError");
    const seleccionAnterior = selector.value;

    selector.replaceChildren();

    for (const operacion of erroresVisibles) {
        const opcion = document.createElement("option");

        opcion.value = operacion.uuid_operacion;

        opcion.textContent =
            `${operacion.datos?.monto ?? "?"} — ` +
            `${operacion.ultimo_error ?? "Sin detalle"}`;

        selector.appendChild(opcion);
    }

    if (erroresVisibles.some(
        op => op.uuid_operacion === seleccionAnterior
    )) {
        selector.value = seleccionAnterior;
    }

    actualizarBotonesError();
}


elemento("operacionError").addEventListener(
    "change",
    actualizarBotonesError
);



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
            elemento("probar401").disabled = true;
            elemento("probarRespuestaPerdida").disabled = true;
            elemento("crear422").disabled = true;

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
            elemento("probar401").disabled = false;
            elemento("probarRespuestaPerdida").disabled = false;
            elemento("crear422").disabled = false;

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

            const montoValido =
                /^(?:0|[1-9]\d{0,12})(?:\.\d{1,2})?$/.test(monto) &&
                Number(monto) > 0;

            if (!montoValido) {
                throw new Error(
                    "El monto debe ser positivo y tener " +
                    "máximo dos decimales. " +
                    "Ejemplo: 1000000.00"
                );
            }


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


// -----------------------------------
// PRUEBA: TOKEN INVÁLIDO / 401
// -----------------------------------

elemento("probar401").addEventListener(
    "click",
    async () => {
        if (!usuarioId) {
            informar("Primero debes iniciar sesión.");
            return;
        }

        elemento("probar401").disabled = true;

        try {
            informar(
                "PRUEBA 401: enviando con token inválido..."
            );

            const resumen = await sincronizarPendientes({
                token: "token-invalido-de-prueba",
                usuarioId: usuarioId,
                onEvento: informar
            });

            informar(
                "Resultado prueba 401: " +
                JSON.stringify(resumen)
            );

            await mostrarCola();

        } catch (error) {
            informar(
                "ERROR DE PRUEBA 401: " + error.message
            );

        } finally {
            elemento("probar401").disabled = !usuarioId;
        }
    }
);

// -----------------------------------
// PRUEBA: CONFIRMACIÓN PERDIDA
// -----------------------------------

elemento("probarRespuestaPerdida").addEventListener(
    "click",
    async () => {

        if (!usuarioId || !tokenActual) {
            informar("Primero debes iniciar sesión.");
            return;
        }

        elemento("probarRespuestaPerdida").disabled = true;

        // Guardar fetch original para restaurarlo.
        const fetchOriginal = window.fetch;

        try {
            informar(
                "PRUEBA: el servidor registrará el gasto, " +
                "pero simularemos una respuesta perdida."
            );

            // Interceptor temporal SOLO PARA ESTA PRUEBA.
            window.fetch = async (...argumentos) => {

                const respuesta = await fetchOriginal.apply(
                    window,
                    argumentos
                );

                const url = String(argumentos[0]);

                // Dejar que FastAPI complete la operación,
                // pero simular la pérdida de confirmación.
                if (
                    url.includes("/movimientos/normales") &&
                    respuesta.ok
                ) {
                    throw new TypeError(
                        "Simulación: confirmación perdida"
                    );
                }

                return respuesta;
            };

            const resumen = await sincronizarPendientes({
                token: tokenActual,
                usuarioId: usuarioId,
                onEvento: informar
            });

            informar(
                "Resultado primera solicitud: " +
                JSON.stringify(resumen)
            );

            await mostrarCola();

        } catch (error) {
            informar(
                "ERROR DE PRUEBA: " + error.message
            );

        } finally {

            // Restaurar inmediatamente el navegador.
            window.fetch = fetchOriginal;

            elemento("probarRespuestaPerdida").disabled =
                !usuarioId;
        }
    }
);


// -----------------------------------
// REINTENTAR OPERACIÓN RECHAZADA
// -----------------------------------

elemento("reintentarError").addEventListener(
    "click",
    async () => {
        const operacion = obtenerErrorSeleccionado();

        if (
            !operacion ||
            operacion.usuario_id !== usuarioId ||
            operacion.estado_sync !== "ERROR"
        ) {
            return;
        }

        if (String(operacion.ultimo_error).startsWith(
            "HTTP 422"
        )) {
            informar(
                "Los datos inválidos no pueden reenviarse " +
                "sin corregirlos."
            );
            return;
        }

        try {
            await actualizarOperacionLocal(
                operacion.uuid_operacion,
                {
                    estado_sync: "PENDIENTE",
                    ultimo_error: null
                }
            );

            informar(
                "Operación preparada para reintentar. " +
                "Se conservaron el UUID, la cuenta, " +
                "el monto y los demás datos originales."
            );

            await mostrarCola();

        } catch (error) {
            informar(
                "Error al preparar reintento: " +
                error.message
            );
        }
    }
);

// -----------------------------------
// DESCARTAR OPERACIÓN LOCAL RECHAZADA
// -----------------------------------

elemento("descartarError").addEventListener(
    "click",
    async () => {
        const operacion = obtenerErrorSeleccionado();

        if (
            !operacion ||
            operacion.usuario_id !== usuarioId ||
            operacion.estado_sync !== "ERROR"
        ) {
            return;
        }

        const confirmar = window.confirm(
            "¿Descartar esta operación de IndexedDB?\n\n" +
            "UUID: " + operacion.uuid_operacion + "\n\n" +
            "Se eliminará únicamente la copia local.\n" +
            "Esto NO anula movimientos de PostgreSQL.\n\n" +
            "Antes de descartarla, verifica que no " +
            "se haya registrado en el servidor."
        );

        if (!confirmar) {
            return;
        }

        try {
            await eliminarOperacion(
                operacion.uuid_operacion
            );

            informar(
                "Registro local descartado: " +
                operacion.uuid_operacion
            );

            informar(
                "Si necesitas registrar otro gasto, " +
                "pulsa 'Nueva operación'."
            );

            await mostrarCola();

        } catch (error) {
            informar(
                "Error al descartar: " +
                error.message
            );
        }
    }
);

// -----------------------------------
// PRUEBA CONTROLADA DE ERROR 422
// -----------------------------------

elemento("crear422").addEventListener(
    "click",
    async () => {

        if (!usuarioId) {
            informar("Primero debes iniciar sesión.");
            return;
        }

        elemento("crear422").disabled = true;

        try {
            const uuid = crypto.randomUUID();

            await guardarOperacionPendiente({
                uuid_operacion: uuid,
                usuario_id: usuarioId,
                tipo_operacion: "MOVIMIENTO_NORMAL",

                datos: {
                    uuid_local: uuid,

                    id_cuenta: Number(
                        elemento("cuenta").value
                    ),

                    id_categoria: Number(
                        elemento("categoria").value
                    ),

                    tipo: "GASTO",
                    monto: "100.00",

                    // Intencionalmente inválido.
                    fecha_movimiento: "FECHA_INVALIDA",

                    descripcion: "PRUEBA CONTROLADA 422"
                }
            });

            informar(
                "Prueba 422 creada localmente. UUID: " +
                uuid
            );

            await mostrarCola();

        } catch (error) {
            informar(
                "Error al crear prueba 422: " +
                error.message
            );

        } finally {
            elemento("crear422").disabled = !usuarioId;
        }
    }
);
