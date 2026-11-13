import { banda, pendienteBackend } from './comun.js';

export async function render(c) {
  c.innerHTML = `
    ${banda('Asistente financiero', { subtitulo: 'Analiza tus datos. No mueve tu dinero.' })}
    <section class="seccion">
      ${pendienteBackend('El asistente se activa cuando existan el AI Integration Gateway y el contexto con PostgreSQL y la ontología en Fuseki.', 'POST /asistente/preguntas')}
      <div class="chips chips-sugerencias">
        <button type="button" class="chip" disabled>¿En qué gasto de más?</button>
        <button type="button" class="chip" disabled>¿Llego a mi meta?</button>
        <button type="button" class="chip" disabled>¿Cuánto pagué de 4x1000?</button>
      </div>
      <form class="caja-pregunta" onsubmit="return false">
        <label for="pregunta" class="solo-lector">Escribe tu pregunta</label>
        <input id="pregunta" placeholder="Pregunta sobre tus finanzas…" disabled>
        <button type="submit" class="btn btn-primario btn-chico" disabled>Enviar</button>
      </form>
    </section>`;
}
