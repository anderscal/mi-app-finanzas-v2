const DB_NAME = "finanzas_offline";
const DB_VERSION = 1;

const STORE_OPERACIONES = "operaciones_pendientes";

export function abrirBD() {
    return new Promise((resolve, reject) => {

        const request = indexedDB.open(
            DB_NAME,
            DB_VERSION
        );

        request.onupgradeneeded = (event) => {
            const db = event.target.result;

            if (
                !db.objectStoreNames.contains(
                    STORE_OPERACIONES
                )
            ) {
                const store = db.createObjectStore(
                    STORE_OPERACIONES,
                    {
                        keyPath: "uuid_operacion"
                    }
                );

                store.createIndex(
                    "estado_sync",
                    "estado_sync",
                    { unique: false }
                );
            }
        };

        request.onsuccess = () => {
            resolve(request.result);
        };

        request.onerror = () => {
            reject(request.error);
        };
    });
}


export async function guardarOperacionPendiente(operacion) {
    const db = await abrirBD();

    return new Promise((resolve, reject) => {
        const tx = db.transaction(
            STORE_OPERACIONES,
            "readwrite"
        );

        const store = tx.objectStore(STORE_OPERACIONES);

        store.add({
            ...operacion,
            estado_sync: "PENDIENTE",
            intentos: 0,
            ultimo_error: null,
            fecha_local: new Date().toISOString()
        });

        tx.oncomplete = () => {
            db.close();
            resolve(operacion.uuid_operacion);
        };

        tx.onerror = () => {
            const error = tx.error;
            db.close();
            reject(error);
        };

        tx.onabort = () => {
            const error = tx.error;
            db.close();
            reject(error);
        };
    });
}


export async function obtenerPendientes() {
    const db = await abrirBD();

    return new Promise((resolve, reject) => {

        const transaction = db.transaction(
            STORE_OPERACIONES,
            "readonly"
        );

        const store = transaction.objectStore(
            STORE_OPERACIONES
        );

        const index = store.index(
            "estado_sync"
        );

        const request = index.getAll(
            "PENDIENTE"
        );

        request.onsuccess = () => {
            resolve(request.result);
        };

        request.onerror = () => {
            reject(request.error);
        };
    });
}


export async function eliminarOperacion(uuidOperacion) {
    const db = await abrirBD();

    return new Promise((resolve, reject) => {
        const tx = db.transaction(
            STORE_OPERACIONES,
            "readwrite"
        );

        tx.objectStore(STORE_OPERACIONES)
            .delete(uuidOperacion);

        tx.oncomplete = () => {
            db.close();
            resolve();
        };

        tx.onerror = () => {
            const error = tx.error;
            db.close();
            reject(error);
        };

        tx.onabort = () => {
            const error = tx.error;
            db.close();
            reject(error);
        };
    });
}

export async function obtenerOperacionesLocales() {
    const db = await abrirBD();

    return new Promise((resolve, reject) => {
        const tx = db.transaction(
            STORE_OPERACIONES,
            "readonly"
        );

        let operaciones = [];

        const request = tx.objectStore(
            STORE_OPERACIONES
        ).getAll();

        request.onsuccess = () => {
            operaciones = request.result;
        };

        tx.oncomplete = () => {
            db.close();
            resolve(operaciones);
        };

        tx.onerror = () => {
            const error = tx.error;
            db.close();
            reject(error);
        };
    });
}


export async function actualizarOperacionLocal(
    uuidOperacion,
    cambios
) {
    const db = await abrirBD();

    return new Promise((resolve, reject) => {
        const tx = db.transaction(
            STORE_OPERACIONES,
            "readwrite"
        );

        const store = tx.objectStore(
            STORE_OPERACIONES
        );

        let noEncontrada = false;

        const request = store.get(uuidOperacion);

        request.onsuccess = () => {
            const actual = request.result;

            if (!actual) {
                noEncontrada = true;
                tx.abort();
                return;
            }

            store.put({
                ...actual,
                ...cambios,
                uuid_operacion: actual.uuid_operacion,
                datos: actual.datos,
                usuario_id: actual.usuario_id
            });
        };

        tx.oncomplete = () => {
            db.close();
            resolve();
        };

        tx.onabort = () => {
            const error = noEncontrada
                ? new Error("Operación local no encontrada")
                : tx.error;

            db.close();
            reject(error);
        };

        tx.onerror = () => {
            // El error se gestionará en onabort.
        };
    });
}


