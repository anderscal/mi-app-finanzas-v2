
import {
    crearCuentaFinanciera,
    ErrorDeRed
} from '../api.js';

import {
    icono,
    aviso
} from '../util.js';


export async function render(c) {

    c.innerHTML = `
    <form id="form-crear-cuenta" novalidate>

      <header class="banda banda-form">
        <div class="banda-fila">

          <a
            class="btn-icono"
            href="#/inicio"
            aria-label="Volver al inicio"
          >
            ${icono('atras')}
          </a>

          <h1 class="banda-titulo">
            Nueva cuenta
          </h1>

        </div>
      </header>

      <div class="cuerpo-form">

        <div class="campo">
          <label for="cc-nombre">
            Nombre de la cuenta
          </label>

          <input
            id="cc-nombre"
            name="nombre_cuenta"
            maxlength="80"
            placeholder="Ej. Cuenta principal"
            required
          >
        </div>

        <div class="campo">
          <label for="cc-tipo">
            Tipo de cuenta
          </label>

          <select id="cc-tipo" name="tipo_cuenta" required>
            <option value="AHORROS">Ahorros</option>
            <option value="CORRIENTE">Corriente</option>
            <option value="EFECTIVO">Efectivo</option>
          </select>
        </div>

        <div class="campo">
          <label for="cc-institucion">
            Institución financiera (opcional)
          </label>

          <input
            id="cc-institucion"
            name="institucion"
            maxlength="80"
            placeholder="Ej. Bancolombia"
          >
        </div>

        <div class="campo">
          <label for="cc-saldo">
            Saldo inicial (COP)
          </label>

          <input
            id="cc-saldo"
            name="saldo_inicial"
            type="text"
            inputmode="decimal"
            value="0.00"
            required
          >
        </div>

        <p class="nota">
          El saldo inicial representa el dinero
          que ya tienes al registrar la cuenta.
        </p>

        <p
          id="cc-error"
          class="error-form"
          role="alert"
        ></p>

      </div>

      <div class="pie-form">

        <button
          class="btn btn-primario"
          type="submit"
        >
          Crear cuenta financiera
        </button>

      </div>

    </form>
  `;

    const form = c.querySelector('#form-crear-cuenta');
    const error = c.querySelector('#cc-error');
    const boton = form.querySelector('button[type="submit"]');

    form.addEventListener('submit', async (ev) => {

        ev.preventDefault();

        if (boton.disabled) return;

        error.textContent = '';

        const nombre = form.elements.nombre_cuenta.value.trim();
        const tipo = form.elements.tipo_cuenta.value;
        const institucion = form.elements.institucion.value.trim();

        const saldo = form.elements.saldo_inicial.value
            .trim()
            .replace(',', '.');

        if (!nombre || nombre.length > 80) {
            error.textContent = 'Escribe un nombre válido.';
            return;
        }

        if (
            !['AHORROS', 'CORRIENTE', 'EFECTIVO'].includes(tipo)
        ) {
            error.textContent = 'Selecciona un tipo válido.';
            return;
        }

        const saldoValido =
            /^(?:0|[1-9]\d{0,12})(?:\.\d{1,2})?$/.test(saldo);

        if (!saldoValido) {
            error.textContent =
                'El saldo debe ser positivo o cero, ' +
                'sin separadores de miles y con máximo dos decimales.';
            return;
        }

        // Crear cuentas requiere conexión.
        if (!navigator.onLine) {
            error.textContent =
                'Necesitas conexión para crear una cuenta financiera.';
            return;
        }

        const datos = {
            nombre_cuenta: nombre,
            tipo_cuenta: tipo,
            institucion: institucion || null,
            saldo_inicial: saldo
        };

        boton.disabled = true;
        boton.textContent = 'Creando cuenta…';

        try {

            const cuenta = await crearCuentaFinanciera(datos);

            aviso(
                `Cuenta "${cuenta.nombre_cuenta}" creada correctamente.`,
                'ok'
            );

            location.hash = '#/inicio';

        } catch (e) {

            if (e instanceof ErrorDeRed) {

                error.textContent =
                    'No se recibió confirmación del servidor. ' +
                    'Regresa a Mis cuentas y comprueba si se creó ' +
                    'antes de intentarlo nuevamente.';

                // No habilitar el reenvío inmediato:
                // es posible que PostgreSQL ya la haya creado.
                return;
            }

            error.textContent = e.message;

            boton.disabled = false;
            boton.textContent = 'Crear cuenta financiera';
        }

    });
}
