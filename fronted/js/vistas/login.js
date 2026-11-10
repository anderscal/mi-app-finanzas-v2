import { iniciarSesion, obtenerPerfil, ErrorDeRed, ErrorApi } from '../api.js';
import { guardarToken, guardarUsuario } from '../sesion.js';

export async function render(c) {
  c.innerHTML = `
    <section class="auth">
      <div class="auth-marca">
        <img src="icons/icono.svg" alt="" width="64" height="64">
        <h1>Hola de nuevo</h1>
        <p>Ingresa para ver tus cuentas y movimientos.</p>
      </div>
      <form id="form-login" class="formulario" novalidate>
        <div class="campo">
          <label for="login-email">Correo</label>
          <input id="login-email" name="email" type="email" autocomplete="email" required>
        </div>
        <div class="campo">
          <label for="login-password">Contraseña</label>
          <input id="login-password" name="password" type="password" autocomplete="current-password" required>
        </div>
        <p class="error-form" id="login-error" role="alert"></p>
        <button class="btn btn-primario" type="submit">Entrar</button>
      </form>
      <p class="auth-pie">¿No tienes cuenta? <a href="#/registro">Crear una cuenta</a></p>
    </section>`;

  const form = c.querySelector('#form-login');
  const error = c.querySelector('#login-error');

  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const email = form.email.value.trim();
    const password = form.password.value;
    if (!email || !password) {
      error.textContent = 'Escribe tu correo y tu contraseña.';
      return;
    }
    const boton = form.querySelector('button');
    boton.disabled = true;
    boton.textContent = 'Entrando…';
    error.textContent = '';
    try {
      const { access_token } = await iniciarSesion(email, password);
      guardarToken(access_token);
      guardarUsuario(await obtenerPerfil());
      window.dispatchEvent(new Event('sesion-iniciada'));
      location.hash = '#/inicio';
    } catch (e) {
      if (e instanceof ErrorDeRed) {
        error.textContent = 'No se pudo conectar con el servidor. Revisa tu internet o que el backend esté encendido.';
      } else if (e instanceof ErrorApi && e.estado === 401) {
        error.textContent = 'Correo o contraseña incorrectos.';
      } else {
        error.textContent = e.message;
      }
      boton.disabled = false;
      boton.textContent = 'Entrar';
    }
  });
}
