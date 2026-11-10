import { registrarUsuario, iniciarSesion, obtenerPerfil, ErrorDeRed } from '../api.js';
import { guardarToken, guardarUsuario } from '../sesion.js';

export async function render(c) {
  c.innerHTML = `
    <section class="auth">
      <div class="auth-marca">
        <img src="icons/icono.svg" alt="" width="56" height="56">
        <h1>Crea tu cuenta</h1>
        <p>Tus datos financieros quedan protegidos con tu contraseña.</p>
      </div>
      <form id="form-registro" class="formulario" novalidate>
        <div class="fila-2">
          <div class="campo"><label for="r-nombre1">Primer nombre</label><input id="r-nombre1" name="nombre_1" autocomplete="given-name" maxlength="50" required></div>
          <div class="campo"><label for="r-nombre2">Segundo nombre <span class="opcional">opcional</span></label><input id="r-nombre2" name="nombre_2" maxlength="50"></div>
        </div>
        <div class="fila-2">
          <div class="campo"><label for="r-apellido1">Primer apellido</label><input id="r-apellido1" name="apellido_1" autocomplete="family-name" maxlength="50" required></div>
          <div class="campo"><label for="r-apellido2">Segundo apellido <span class="opcional">opcional</span></label><input id="r-apellido2" name="apellido_2" maxlength="50"></div>
        </div>
        <div class="campo"><label for="r-email">Correo</label><input id="r-email" name="email" type="email" autocomplete="email" maxlength="100" required></div>
        <div class="campo">
          <label for="r-password">Contraseña</label>
          <input id="r-password" name="password" type="password" autocomplete="new-password" minlength="12" maxlength="128" required aria-describedby="r-ayuda">
          <small id="r-ayuda" class="ayuda">Mínimo 12 caracteres.</small>
        </div>
        <div class="campo"><label for="r-confirmar">Repite la contraseña</label><input id="r-confirmar" name="confirmar" type="password" autocomplete="new-password" required></div>
        <p class="error-form" id="registro-error" role="alert"></p>
        <button class="btn btn-primario" type="submit">Crear cuenta</button>
      </form>
      <p class="auth-pie">¿Ya tienes cuenta? <a href="#/login">Iniciar sesión</a></p>
    </section>`;

  const form = c.querySelector('#form-registro');
  const error = c.querySelector('#registro-error');

  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const d = Object.fromEntries(new FormData(form));
    Object.keys(d).forEach((k) => { if (k !== 'password' && k !== 'confirmar') d[k] = d[k].trim(); });

    if (!d.nombre_1 || !d.apellido_1 || !d.email) { error.textContent = 'Completa nombre, apellido y correo.'; return; }
    if (d.password.length < 12) { error.textContent = 'La contraseña debe tener al menos 12 caracteres.'; return; }
    if (d.password !== d.confirmar) { error.textContent = 'Las contraseñas no coinciden.'; return; }

    const boton = form.querySelector('button');
    boton.disabled = true;
    boton.textContent = 'Creando cuenta…';
    error.textContent = '';
    try {
      await registrarUsuario(d);
      const { access_token } = await iniciarSesion(d.email, d.password);
      guardarToken(access_token);
      guardarUsuario(await obtenerPerfil());
      location.hash = '#/inicio';
    } catch (e) {
      error.textContent = e instanceof ErrorDeRed
        ? 'No se pudo conectar con el servidor.'
        : e.message;
      boton.disabled = false;
      boton.textContent = 'Crear cuenta';
    }
  });
}
