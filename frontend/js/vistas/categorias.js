
import {
  obtenerCategorias,
  crearCategoriaFinanciera,
  actualizarCategoriaFinanciera,
  desactivarCategoriaFinanciera,
  ErrorDeRed
} from '../api.js';

import { operacionesLocales } from '../offline.js';

import {
  esc,
  aviso,
  guardarCache
} from '../util.js';


export async function render(c) {

  let categorias = [];
  let editando = null;
  let ocupada = false;

  c.innerHTML = `
    <header class="banda banda-form">
      <div class="banda-fila">
        <a
          class="btn-icono"
          href="#/inicio"
          aria-label="Volver al inicio"
        >
          ←
        </a>
        <h1 class="banda-titulo">
          Mis categorías
        </h1>
      </div>
    </header>

    <section class="seccion">
      <h2>Crear categoría</h2>

      <form id="form-crear-categoria">

        <div class="campo">
          <label for="cat-nombre">
            Nombre de la categoría
          </label>
          <input
            id="cat-nombre"
            name="nombre_categoria"
            maxlength="60"
            placeholder="Ej. Mantenimiento del hogar"
            required
          >
        </div>

        <div class="campo">
          <label for="cat-tipo">
            Tipo de categoría
          </label>
          <select
            id="cat-tipo"
            name="tipo_categoria"
            required
          >
            <option value="GASTO">Gasto</option>
            <option value="INGRESO">Ingreso</option>
          </select>
        </div>

        <button
          type="submit"
          class="btn btn-primario"
          disabled
        >
          + Crear categoría
        </button>
      </form>

      <p
        id="cat-mensaje"
        class="error-form"
        role="alert"
      ></p>
    </section>

    <section class="seccion">
      <div class="seccion-titulo">
        <h2>Categorías disponibles</h2>
      </div>

      <div id="cat-lista">
        <p>Cargando categorías...</p>
      </div>
    </section>
  `;

  const formulario = c.querySelector(
    '#form-crear-categoria'
  );

  const lista = c.querySelector('#cat-lista');
  const mensaje = c.querySelector('#cat-mensaje');

  const limpiarNombre = valor =>
    valor.trim().replace(/\s+/g, ' ');


  // -------------------------------------
  // MOSTRAR CATEGORÍAS
  // -------------------------------------

  function pintar() {

    function grupo(tipo, titulo) {

      const elementos = categorias.filter(cat =>
        cat.estado === 'ACTIVA' &&
        cat.tipo_categoria === tipo
      );

      const tarjetas = elementos.map(cat => {

        const id = Number(cat.id_categoria);

        if (!Number.isSafeInteger(id) || id <= 0) {
          return '';
        }

        const esSistema = cat.es_sistema === true;
        const estaEditando = editando === id;

        return `
          <article class="tarjeta-gris">

            <div class="seccion-titulo">
              <strong>
                ${esc(cat.nombre_categoria)}
              </strong>

              <small>
                ${esSistema ? 'Del sistema' : 'Personal'}
              </small>
            </div>

            ${esSistema ? `
              <p class="nota">
                Esta categoría es del sistema y
                no puede modificarse.
              </p>
            ` : estaEditando ? `
              <form data-editar-id="${id}">

                <div class="campo">
                  <label>
                    Nuevo nombre
                    <input
                      name="nombre_categoria"
                      maxlength="60"
                      value="${esc(cat.nombre_categoria)}"
                      required
                    >
                  </label>
                </div>

                <button
                  type="submit"
                  class="btn btn-primario"
                >
                  Guardar
                </button>

                <button
                  type="button"
                  class="btn"
                  data-accion="cancelar"
                  data-id="${id}"
                >
                  Cancelar
                </button>

              </form>
            ` : `
              <div class="banda-fila">

                <button
                  type="button"
                  class="btn"
                  data-accion="editar"
                  data-id="${id}"
                >
                  Editar
                </button>

                <button
                  type="button"
                  class="btn"
                  data-accion="desactivar"
                  data-id="${id}"
                >
                  Desactivar
                </button>

              </div>
            `}

          </article>
        `;
      }).join('');

      return `
        <div class="seccion">
          <h3>${titulo}</h3>

          ${tarjetas || `
            <p class="vacio">
              No hay categorías de este tipo.
            </p>
          `}
        </div>
      `;
    }

    lista.innerHTML =
      grupo('GASTO', 'Gastos') +
      grupo('INGRESO', 'Ingresos');
  }


  // -------------------------------------
  // EJECUTAR OPERACIONES SEGURAS
  // -------------------------------------

  async function ejecutar(accion, actualizar, textoExito) {

    if (ocupada) return false;

    if (!navigator.onLine) {
      mensaje.textContent =
        'Necesitas conexión para administrar categorías.';
      return false;
    }

    ocupada = true;
    mensaje.textContent = '';

    const botones = [
      ...c.querySelectorAll('button')
    ];

    botones.forEach(b => {
      b.disabled = true;
    });

    try {

      const resultado = await accion();

      actualizar(resultado);

      // Actualiza la misma caché que utiliza Registrar.
      guardarCache('categorias', categorias);

      pintar();

      aviso(textoExito, 'ok');

      return true;

    } catch (e) {

      if (e instanceof ErrorDeRed) {
        mensaje.textContent =
          'No se recibió confirmación del servidor. ' +
          'Vuelve a consultar las categorías antes de ' +
          'repetir la operación.';
      } else {
        mensaje.textContent =
          e.message || 'No se pudo completar la operación.';
      }

      return false;

    } finally {

      ocupada = false;

      botones.forEach(b => {
        if (b.isConnected) b.disabled = false;
      });

    }
  }


  // -------------------------------------
  // CREAR CATEGORÍA
  // -------------------------------------

  formulario.addEventListener('submit', async ev => {

    ev.preventDefault();

    const nombre = limpiarNombre(
      formulario.elements.nombre_categoria.value
    );

    const tipo =
      formulario.elements.tipo_categoria.value;

    if (!nombre || nombre.length > 60) {
      mensaje.textContent =
        'Escribe un nombre de máximo 60 caracteres.';
      return;
    }

    if (!['GASTO', 'INGRESO'].includes(tipo)) {
      mensaje.textContent = 'Selecciona un tipo válido.';
      return;
    }

    await ejecutar(

      () => crearCategoriaFinanciera({
        nombre_categoria: nombre,
        tipo_categoria: tipo
      }),

      nueva => {
        categorias.push(nueva);
        formulario.reset();
      },

      'Categoría creada correctamente.'
    );
  });


  // -------------------------------------
  // ABRIR EDICIÓN Y DESACTIVAR
  // -------------------------------------

  lista.addEventListener('click', async ev => {

    const boton = ev.target.closest(
      'button[data-accion]'
    );

    if (!boton || ocupada) return;

    const id = Number(boton.dataset.id);
    const accion = boton.dataset.accion;

    const categoria = categorias.find(
      cat => Number(cat.id_categoria) === id
    );

    if (!categoria || categoria.es_sistema) {
      return;
    }

    if (accion === 'editar') {
      editando = id;
      pintar();
      return;
    }

    if (accion === 'cancelar') {
      editando = null;
      pintar();
      return;
    }

    if (accion === 'desactivar') {

      mensaje.textContent = '';

      if (!navigator.onLine) {
        mensaje.textContent =
          'Necesitas conexión para desactivar.';
        return;
      }

      // No desactivar categorías mientras existan
      // operaciones locales por resolver.
      let locales;

      try {
        locales = await operacionesLocales();

        if (!Array.isArray(locales)) {
          throw new Error(
            'No se pudo verificar la cola offline.'
          );
        }

      } catch {
        mensaje.textContent =
          'No se pudo verificar la cola offline. ' +
          'Por seguridad, no se desactivó la categoría.';
        return;
      }

      if (locales.length > 0) {
        mensaje.textContent =
          'Tienes operaciones locales pendientes ' +
          'o en revisión. Sincronízalas o resuelve ' +
          'sus errores antes de desactivar categorías.';
        return;
      }

      const confirmado = window.confirm(
        `¿Desactivar "${categoria.nombre_categoria}"?\n\n` +
        'No aparecerá para movimientos nuevos. ' +
        'Los movimientos anteriores se conservarán.'
      );

      if (!confirmado) return;

      await ejecutar(

        () => desactivarCategoriaFinanciera(id),

        () => {
          categorias = categorias.filter(
            cat => Number(cat.id_categoria) !== id
          );
          editando = null;
        },

        'Categoría desactivada correctamente.'
      );
    }
  });


  // -------------------------------------
  // GUARDAR CAMBIOS DE NOMBRE
  // -------------------------------------

  lista.addEventListener('submit', async ev => {

    const form = ev.target.closest(
      'form[data-editar-id]'
    );

    if (!form) return;

    ev.preventDefault();

    const id = Number(form.dataset.editarId);

    const nombre = limpiarNombre(
      form.elements.nombre_categoria.value
    );

    if (!nombre || nombre.length > 60) {
      mensaje.textContent =
        'Escribe un nombre válido.';
      return;
    }

    await ejecutar(

      () => actualizarCategoriaFinanciera(id, {
        nombre_categoria: nombre
      }),

      actualizada => {
        categorias = categorias.map(cat =>
          Number(cat.id_categoria) === id
            ? actualizada
            : cat
        );

        editando = null;
      },

      'Categoría actualizada correctamente.'
    );

  });


  // -------------------------------------
  // CARGA INICIAL DESDE FASTAPI
  // -------------------------------------

  try {

    const respuesta = await obtenerCategorias();

    if (!Array.isArray(respuesta)) {
      throw new Error(
        'El servidor devolvió categorías inválidas.'
      );
    }

    categorias = respuesta.filter(
      cat => cat.estado === 'ACTIVA'
    );

    guardarCache('categorias', categorias);

    pintar();

    formulario.querySelector(
      'button[type="submit"]'
    ).disabled = false;

  } catch (e) {

    lista.innerHTML = `
      <p class="vacio">
        No se pudieron cargar las categorías.
      </p>
    `;

    mensaje.textContent =
      e instanceof ErrorDeRed
        ? 'Necesitas conexión para administrar categorías.'
        : e.message;
  }

}
