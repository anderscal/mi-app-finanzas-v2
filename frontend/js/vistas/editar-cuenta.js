
import {
    obtenerMisCuentas,
    actualizarCuentaFinanciera,
    desactivarCuentaFinanciera,
    ErrorDeRed
} from '../api.js';

import { obtenerUsuario } from '../sesion.js';

import {
    obtenerOperacionesLocales
} from '../offline-db.js';

import {
    cop,
    esc,
    icono,
    aviso
} from '../util.js';


// Detecta operaciones locales que utilizan esta cuenta.
async function operacionesSinResolver(idCuenta) {
    const idUsuario = Number(
        obtenerUsuario()?.id_usuario
    );

    if (!Number.isSafeInteger(idUsuario) || idUsuario <= 0) {
        throw new Error('No se pudo identificar al usuario.');
    }

    const operaciones = await obtenerOperacionesLocales();

    return operaciones.filter(op => {
        if (Number(op.usuario_id) !== idUsuario) {
            return false;
        }

        if (!['PENDIENTE', 'ERROR'].includes(op.estado_sync)) {
            return false;
        }

        const datos = op.datos || {};

        return [
            datos.id_cuenta,
            datos.id_cuenta_origen,
            datos.id_cuenta_destino
        ].some(id => Number(id) === idCuenta);
    });
}


export async function render(c, parametro) {
    const idCuenta = Number(parametro);

    if (
        !Number.isSafeInteger(idCuenta) ||
        idCuenta <= 0
    ) {
        c.innerHTML =
            '<p class="error-general">Cuenta no válida.</p>';
        return;
    }

    c.innerHTML = `
    <header class="banda">
      <div class="banda-fila">
        <a
          class="btn-icono"
          href="#/inicio"
          aria-label="Volver al inicio"
        >
          ${icono('atras')}
        </a>
        <h1 class="banda-titulo">Administrar cuenta</h1>
      </div>
    </header>
    <div class="cuerpo-form" id="ec-contenido">
      <p>Cargando cuenta...</p>
    </div>
  `;

    const contenido = c.querySelector('#ec-contenido');

    try {
        // Administrar cuentas requiere conexión.
        if (!navigator.onLine) {
            throw new Error(
                'Necesitas conexión para administrar cuentas.'
            );
        }

        const respuesta = await obtenerMisCuentas();

        const cuenta = respuesta.cuentas.find(
            item => Number(item.id_cuenta) === idCuenta
        );

        if (!cuenta) {
            throw new Error(
                'La cuenta no existe o no pertenece a tu usuario.'
            );
        }

        const activa = cuenta.estado === 'ACTIVA';

        contenido.innerHTML = `
      <div class="tarjeta-gris">
        <strong>${esc(cuenta.nombre_cuenta)}</strong>
        <p>Tipo: ${esc(cuenta.tipo_cuenta)}</p>
        <p>Saldo actual: ${cop(cuenta.saldo_actual)}</p>
        <p>Estado: ${esc(cuenta.estado)}</p>
      </div>

      ${activa ? `
        <form id="ec-form" class="formulario" novalidate>

          <div class="campo">
            <label for="ec-nombre">Nombre de cuenta</label>
            <input
              id="ec-nombre"
              name="nombre_cuenta"
              maxlength="80"
              value="${esc(cuenta.nombre_cuenta)}"
              required
            >
          </div>

          <div class="campo">
            <label for="ec-institucion">
              Institución financiera (opcional)
            </label>
            <input
              id="ec-institucion"
              name="institucion"
              maxlength="80"
              value="${esc(cuenta.institucion || '')}"
            >
          </div>

          <p class="nota">
            El saldo inicial y el tipo de cuenta
            no pueden modificarse desde esta pantalla.
          </p>

          <p id="ec-error" class="error-form"
             role="alert"></p>

          <button
            id="ec-guardar"
            class="btn btn-primario"
            type="submit"
          >
            Guardar cambios
          </button>

          <button
            id="ec-desactivar"
            class="btn btn-peligro"
            type="button"
          >
            Desactivar cuenta
          </button>

        </form>
      ` : `
        <p class="nota">
          Esta cuenta está inactiva y se conserva
          para mantener su historial financiero.
        </p>
      `}
    `;

        if (!activa) return;

        const form = contenido.querySelector('#ec-form');
        const error = contenido.querySelector('#ec-error');
        const guardar = contenido.querySelector('#ec-guardar');
        const desactivar = contenido.querySelector('#ec-desactivar');

        let solicitudEnCurso = false;

        function bloquearBotones() {
            guardar.disabled = true;
            desactivar.disabled = true;
        }

        function habilitarBotones() {
            solicitudEnCurso = false;
            guardar.disabled = false;
            desactivar.disabled = false;
        }

        // -------------------------
        // EDITAR CUENTA
        // -------------------------

        form.addEventListener('submit', async (evento) => {
            evento.preventDefault();

            if (solicitudEnCurso) return;

            error.textContent = '';

            const nombre = form.elements.nombre_cuenta.value.trim();
            const institucion =
                form.elements.institucion.value.trim();

            if (!nombre || nombre.length > 80) {
                error.textContent =
                    'El nombre debe tener entre 1 y 80 caracteres.';
                return;
            }

            if (!navigator.onLine) {
                error.textContent =
                    'Necesitas conexión para guardar cambios.';
                return;
            }

            solicitudEnCurso = true;
            bloquearBotones();

            try {
                const actualizada =
                    await actualizarCuentaFinanciera(idCuenta, {
                        nombre_cuenta: nombre,
                        institucion: institucion || null
                    });

                aviso(
                    `Cuenta "${actualizada.nombre_cuenta}" actualizada.`,
                    'ok'
                );

                location.hash = '#/inicio';

            } catch (e) {
                if (e instanceof ErrorDeRed) {
                    error.textContent =
                        'No se recibió confirmación. Vuelve a Mis ' +
                        'cuentas y verifica los datos antes de ' +
                        'intentar otra vez.';
                    return;
                }

                error.textContent = e.message;
                habilitarBotones();
            }
        });


        // -------------------------
        // DESACTIVAR CUENTA
        // -------------------------

        desactivar.addEventListener('click', async () => {
            if (solicitudEnCurso) return;

            error.textContent = '';

            if (!navigator.onLine) {
                error.textContent =
                    'Necesitas conexión para desactivar la cuenta.';
                return;
            }

            solicitudEnCurso = true;
            bloquearBotones();

            try {
                const sinResolver =
                    await operacionesSinResolver(idCuenta);

                if (sinResolver.length > 0) {
                    error.textContent =
                        `Esta cuenta tiene ${sinResolver.length} ` +
                        'operación(es) locales pendientes o ' +
                        'rechazadas. Revísalas en Movimientos ' +
                        'antes de desactivarla.';

                    habilitarBotones();
                    return;
                }

                const confirmado = window.confirm(
                    '¿Desactivar la cuenta "' +
                    cuenta.nombre_cuenta + '"?\n\n' +
                    'Solo se permite si su saldo actual es cero.\n' +
                    'El historial financiero se conservará.'
                );

                if (!confirmado) {
                    habilitarBotones();
                    return;
                }

                // Repetimos la verificación por si la cola cambió
                // mientras el usuario confirmaba la acción.
                const revision =
                    await operacionesSinResolver(idCuenta);

                if (revision.length > 0) {
                    error.textContent =
                        'Existen operaciones sin sincronizar. ' +
                        'No se desactivó la cuenta.';
                    habilitarBotones();
                    return;
                }

                const resultado =
                    await desactivarCuentaFinanciera(idCuenta);

                aviso(
                    `Cuenta "${resultado.nombre_cuenta}" desactivada.`,
                    'ok'
                );

                location.hash = '#/inicio';

            } catch (e) {
                if (e instanceof ErrorDeRed) {
                    error.textContent =
                        'No se recibió confirmación. Consulta ' +
                        'el estado de la cuenta antes de reintentar.';
                    return;
                }

                error.textContent = e.message;
                habilitarBotones();
            }
        });

    } catch (e) {
        contenido.innerHTML =
            `<p class="error-general">${esc(e.message)}</p>`;
    }
}
