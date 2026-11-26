import {
  iniciarSesion,
  obtenerPerfil,
  ErrorDeRed,
  ErrorApi
} from '../api.js';

import {
  guardarToken,
  guardarUsuario,
  obtenerToken,
  cerrarSesion
} from '../sesion.js';


export async function render(c) {

  c.innerHTML = `
    <section class="auth">

      <div class="auth-marca">

        <img
          src="icons/icono.svg"
          alt=""
          width="64"
          height="64"
        >

        <h1>Hola de nuevo</h1>

        <p>Inicia sesión en tu cuenta.</p>

      </div>


      <form
        id="form-login"
        class="formulario"
        novalidate
      >

        <div class="campo">

          <label for="login-email">
            Correo electrónico
          </label>

          <input
            id="login-email"
            name="email"
            type="email"
            autocomplete="email"
            required
          >

        </div>


        <div class="campo">

          <label for="login-password">
            Contraseña
          </label>

          <input
            id="login-password"
            name="password"
            type="password"
            autocomplete="current-password"
            required
          >

          <button
            class="enlace"
            type="button"
            id="login-mostrar"
            aria-pressed="false"
          >
            Mostrar contraseña
          </button>

        </div>


        <p class="auth-pie">

          <a href="#/recuperar-contrasena">
            ¿Olvidaste tu contraseña?
          </a>

        </p>

        <p
          class="error-form"
          id="login-error"
          role="alert"
        ></p>

        <button
          class="btn btn-primario"
          type="submit"
        >
          Entrar
        </button>

      </form>


      <p class="auth-pie">

        ¿No tienes cuenta?

        <a href="#/registro">
          Crear una cuenta
        </a>

      </p>

    </section>`;


  const form = c.querySelector('#form-login');

  const error = c.querySelector('#login-error');

  const boton = form.querySelector(
    '[type="submit"]'
  );

  const mostrar = c.querySelector(
    '#login-mostrar'
  );

  const passwordInput = c.querySelector(
    '#login-password'
  );

  const vigente = () => (
    c.isConnected &&
    location.hash === '#/login'
  );

  let ocupada = false;


  mostrar.addEventListener('click', () => {

    const visible =
      passwordInput.type === 'password';

    passwordInput.type = visible
      ? 'text'
      : 'password';

    mostrar.setAttribute(
      'aria-pressed',
      String(visible)
    );

    mostrar.textContent = visible
      ? 'Ocultar contraseña'
      : 'Mostrar contraseña';
  });


  form.addEventListener('submit', async ev => {

    ev.preventDefault();

    if (ocupada || !vigente()) return;

    error.textContent = '';

    if (!navigator.onLine) {

      error.textContent =
        'Necesitas conexión para iniciar sesión.';

      return;
    }

    if (!form.reportValidity()) return;


    const email = form.elements.email.value.trim();

    const password = passwordInput.value;

    const anterior = obtenerToken();

    let propio = null;

    ocupada = true;

    boton.disabled = true;

    boton.textContent = 'Entrando…';


    try {

      const { access_token } = await iniciarSesion(
        email,
        password
      );

      if (
        !vigente() ||

        obtenerToken() !== anterior
      ) {

        return;
      }

      propio = access_token;

      guardarToken(propio);

      const perfil = await obtenerPerfil();

      if (obtenerToken() !== propio) {

        return;
      }

      if (!vigente()) {

        cerrarSesion();

        return;
      }

      guardarUsuario(perfil);

      form.reset();

      window.dispatchEvent(
        new Event('sesion-iniciada')
      );

      location.hash = '#/inicio';

    } catch (e) {

      if (
        propio &&

        obtenerToken() === propio
      ) {

        cerrarSesion();
      }

      if (!vigente()) return;


      if (e instanceof ErrorDeRed) {

        error.textContent =
          'No hay conexión con el servidor.';

      } else if (
        e instanceof ErrorApi &&
        e.estado === 401
      ) {

        error.textContent =
          'Correo o contraseña incorrectos.';

      } else {

        error.textContent =
          'No se pudo iniciar sesión.';
      }

    } finally {

      ocupada = false;

      boton.disabled = false;

      boton.textContent = 'Entrar';
    }
  });
}