import {
  solicitarRecuperacion,
  restablecerContrasena,
  cambiarContrasena,
  ErrorApi,
  ErrorDeRed
} from '../api.js';

import {
  obtenerToken,
  cerrarSesion
} from '../sesion.js';

import { aviso } from '../util.js';


const TOKEN_VALIDO = /^[A-Za-z0-9_-]{43}$/;


// ======================================
// COMPONENTES COMPARTIDOS
// ======================================

function pantalla(
  c,
  titulo,
  subtitulo,
  contenido,
  volver,
  etiqueta
) {

  c.innerHTML = `
    <section class="auth">

      <div class="auth-marca">
        <img src="icons/icono.svg"
          alt="" width="56" height="56">

        <h1>${titulo}</h1>
        <p>${subtitulo}</p>
      </div>

      ${contenido}

      <p class="auth-pie">
        <a href="${volver}">${etiqueta}</a>
      </p>

    </section>`;
}


function campo(id, titulo, actual = false) {

  return `
    <div class="campo">

      <label for="${id}">${titulo}</label>

      <input
        id="${id}"
        name="${id}"
        type="password"
        autocomplete="${
          actual
            ? 'current-password'
            : 'new-password'
        }"
        ${actual ? '' : 'minlength="12"'}
        maxlength="128"
        required
      >

    </div>`;
}


function mostrarError(e, modo) {

  if (e instanceof ErrorDeRed) {

    return 'No hay conexión. Intenta de nuevo.';
  }

  if (e instanceof ErrorApi) {

    if (e.estado === 401) {

      return 'Inicia sesión nuevamente.';
    }

    if (e.estado === 429) {

      return 'Espera antes de volver a intentarlo.';
    }

    if (e.estado === 422) {

      if (
        modo === 'cambiar' &&
        /actual/i.test(e.message)
      ) {

        return 'Contraseña actual incorrecta.';
      }

      if (/diferente/i.test(e.message)) {

        return 'Elige una contraseña diferente.';
      }

      if (
        modo === 'restablecer' &&
        /enlace/i.test(e.message)
      ) {

        return 'Enlace inválido, vencido o utilizado.';
      }

      return 'Revisa los datos ingresados.';
    }

    if (e.estado >= 500) {

      return 'Servicio temporalmente no disponible.';
    }
  }

  return 'No se pudo completar la solicitud.';
}


// ======================================
// CONTROL DE FORMULARIOS
// ======================================

function conectarFormulario(
  c,
  modo,
  accion,
  etiqueta
) {

  const form = c.querySelector('form');

  const error = c.querySelector('.error-form');

  const boton = form.querySelector(
    '[type="submit"]'
  );

  const mostrar = form.querySelector(
    '[data-mostrar-password]'
  );

  let ocupada = false;


  if (mostrar) {

    mostrar.addEventListener('click', () => {

      const visible = mostrar.getAttribute(
        'aria-pressed'
      ) !== 'true';

      form.querySelectorAll(
        'input[data-secreto]'
      ).forEach(input => {

        input.type = visible
          ? 'text'
          : 'password';

      });

      mostrar.setAttribute(
        'aria-pressed',
        String(visible)
      );

      mostrar.textContent = visible
        ? 'Ocultar contraseñas'
        : 'Mostrar contraseñas';

    });
  }


  form.addEventListener('submit', async ev => {

    ev.preventDefault();

    if (ocupada || !c.isConnected) return;

    error.textContent = '';

    if (!navigator.onLine) {

      error.textContent =
        'Necesitas conexión a internet.';

      return;
    }

    if (!form.reportValidity()) return;

    const datos = Object.fromEntries(
      new FormData(form)
    );

    if (
      modo !== 'recuperar' &&

      datos.nueva_password !==
      datos.confirmacion_password
    ) {

      error.textContent =
        'Las contraseñas no coinciden.';

      return;
    }

    ocupada = true;

    boton.disabled = true;

    boton.textContent = 'Procesando…';

    try {

      await accion(datos, form);

    } catch (e) {

      if (c.isConnected) {

        error.textContent =
          mostrarError(e, modo);
      }

    } finally {

      ocupada = false;

      boton.disabled = false;

      boton.textContent = etiqueta;
    }
  });
}


// ======================================
// SOLICITAR RECUPERACION
// ======================================

export const recuperar = {

  render(c) {

    pantalla(
      c,

      'Recuperar acceso',

      'Recibe un enlace de recuperación.',

      `
      <form class="formulario" novalidate>

        <div class="campo">

          <label for="rec-email">
            Correo electrónico
          </label>

          <input
            id="rec-email"
            name="email"
            type="email"
            autocomplete="email"
            maxlength="100"
            required
          >

        </div>

        <p class="error-form" role="alert"></p>

        <button
          class="btn btn-primario"
          type="submit"
        >
          Enviar enlace
        </button>

      </form>`,

      '#/login',

      'Volver a iniciar sesión'
    );


    conectarFormulario(

      c,

      'recuperar',

      async (datos, form) => {

        await solicitarRecuperacion(
          datos.email.trim()
        );

        if (!c.isConnected) return;

        form.reset();

        const mensaje = document.createElement('p');

        mensaje.className = 'tarjeta-gris';

        mensaje.setAttribute('role', 'status');

        mensaje.textContent =
          'Si la cuenta existe, recibirás un enlace. ' +
          'Revisa tu correo.';

        form.replaceWith(mensaje);
      },

      'Enviar enlace'
    );
  }
};


// ======================================
// FORMULARIO DE NUEVA CONTRASENA
// ======================================

function formularioPassword(actual, etiqueta) {

  return `
    <form class="formulario" novalidate>

      ${
        actual
          ? campo(
              'password_actual',
              'Contraseña actual',
              true
            )
          : ''
      }

      ${campo(
        'nueva_password',
        'Nueva contraseña'
      )}

      <small class="ayuda">
        Mínimo 12 caracteres.
      </small>

      ${campo(
        'confirmacion_password',
        'Confirmar contraseña'
      )}

      <button
        class="enlace"
        type="button"
        data-mostrar-password
        aria-pressed="false"
      >
        Mostrar contraseñas
      </button>

      <p class="error-form" role="alert"></p>

      <button
        class="btn btn-primario"
        type="submit"
      >
        ${etiqueta}
      </button>

    </form>`;
}


function marcarSecretos(c) {

  c.querySelectorAll(
    'input[type="password"]'
  ).forEach(input => {

    input.setAttribute('data-secreto', '');

  });
}


function finalizar(c, form, tokenInicial) {

  form.reset();

  // No cerrar una sesion diferente
  // iniciada durante la solicitud.

  if (obtenerToken() !== tokenInicial) {

    return;
  }

  if (tokenInicial !== null) {

    cerrarSesion();
  }

  if (!c.isConnected && tokenInicial === null) {

    return;
  }

  aviso(
    'Contraseña actualizada. Inicia sesión.',
    'ok'
  );

  location.hash = '#/login';
}


// ======================================
// RESTABLECER MEDIANTE ENLACE
// ======================================

export const restablecer = {

  render(c, token) {

    if (
      typeof token !== 'string' ||

      !TOKEN_VALIDO.test(token)
    ) {

      pantalla(

        c,

        'Enlace no disponible',

        'Solicita un nuevo enlace.',

        `
        <a
          class="btn btn-primario"
          href="#/recuperar-contrasena"
        >
          Solicitar enlace
        </a>`,

        '#/login',

        'Volver a iniciar sesión'
      );

      return;
    }


    const tokenInicial = obtenerToken();

    pantalla(

      c,

      'Nueva contraseña',

      'Elige una contraseña segura.',

      formularioPassword(
        false,
        'Restablecer'
      ),

      '#/login',

      'Cancelar'
    );

    marcarSecretos(c);


    conectarFormulario(

      c,

      'restablecer',

      async (datos, form) => {

        await restablecerContrasena({
          ...datos,
          token
        });

        finalizar(
          c,
          form,
          tokenInicial
        );
      },

      'Restablecer'
    );
  }
};


// ======================================
// CAMBIAR CONTRASENA AUTENTICADA
// ======================================

export const cambiar = {

  render(c) {

    const tokenInicial = obtenerToken();

    pantalla(

      c,

      'Cambiar contraseña',

      'Deberás iniciar sesión nuevamente.',

      formularioPassword(
        true,
        'Guardar cambios'
      ),

      '#/inicio',

      'Cancelar'
    );

    marcarSecretos(c);


    conectarFormulario(

      c,

      'cambiar',

      async (datos, form) => {

        if (
          !tokenInicial ||

          obtenerToken() !== tokenInicial
        ) {

          throw new ErrorApi(
            401,
            'Sesión no disponible.'
          );
        }

        await cambiarContrasena(datos);

        finalizar(
          c,
          form,
          tokenInicial
        );
      },

      'Guardar cambios'
    );
  }
};