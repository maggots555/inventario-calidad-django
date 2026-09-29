/**
 * Memoria de Atrás / Adelante para el lienzo de daños estéticos.
 *
 * Objetivo: que el técnico deshaga un trazo (como Ctrl+Z) sin borrar
 * todo el diagrama. Cada paso es una foto de los pixeles al soltar el
 * dedo o el stylus. El PDF y la base de datos siguen recibiendo un PNG.
 *
 * Este archivo no usa import/export: se carga como <script> antes del
 * wizard (OOW, Garantía Dell o Venta Mostrador) y deja la clase en el
 * ámbito global de la página.
 *
 * Efectos secundarios: lee y escribe pixeles del canvas. No toca la red
 * ni la base de datos.
 */

/** Cuántas fotos guardamos. 640×400 pesa ~1 MB; 25 caben en una tablet. */
const TOPE_FOTOS_TRAZO = 25;

/**
 * Compara dos fotos del lienzo.
 *
 * Objetivo: no apilar un paso de "Limpiar" si el dibujo no cambió.
 * Argumentos: dos ImageData del mismo canvas.
 * Efectos: ninguno; solo lee los números de color.
 */
function fotosLienzoIguales(anterior: ImageData, siguiente: ImageData): boolean {
  const datosA = anterior.data;
  const datosB = siguiente.data;
  if (datosA.length !== datosB.length) {
    return false;
  }
  // EXPLICACIÓN PARA PRINCIPIANTES:
  // Cada pixel son 4 números (rojo, verde, azul, transparencia).
  // Saltamos de 4 en 4. Si un canal cambia, las fotos no son la misma.
  for (let i = 0; i < datosA.length; i += 4) {
    const rojoDistinto = datosA[i] !== datosB[i];
    const verdeDistinto = datosA[i + 1] !== datosB[i + 1];
    const azulDistinto = datosA[i + 2] !== datosB[i + 2];
    const alfaDistinto = datosA[i + 3] !== datosB[i + 3];
    if (rojoDistinto || verdeDistinto || azulDistinto || alfaDistinto) {
      return false;
    }
  }
  return true;
}

/**
 * Pila de fotos del lienzo de daños.
 *
 * Objetivo: Atrás vuelve al trazo anterior y Adelante lo recupera.
 * La foto 0 es la base (diagrama vacío o vista ya guardada). Atrás
 * no puede borrar esa base: esas rayas ya iban dentro de un PNG.
 */
class HistorialTrazosDano {
  private fotos: ImageData[] = [];
  private indice = -1;
  private trazoEnCurso = false;
  private bloqueado = false;
  private alCambiar: (() => void) | null = null;

  /**
   * Objetivo: recordar el contexto donde se pinta el daño.
   * Argumentos: ctx del canvas #canvasDano.
   * Efectos: ninguno todavía; la primera foto la toma reiniciar().
   */
  constructor(private readonly ctx: CanvasRenderingContext2D) {}

  /**
   * Objetivo: avisar a los botones cuando haya algo que deshacer.
   * Argumentos: fn sin parámetros, la llama este objeto.
   * Efectos: guarda el callback. No pinta nada.
   */
  definirAlCambiar(fn: () => void): void {
    this.alCambiar = fn;
  }

  /**
   * Objetivo: anotar que el dedo se arrastró. Un toque sin mover no es trazo.
   * Argumentos: ninguno.
   * Efectos: marca la bandera interna. La foto se toma al soltar.
   */
  marcarMovimiento(): void {
    if (this.bloqueado) {
      return;
    }
    this.trazoEnCurso = true;
  }

  /**
   * Objetivo: al soltar el dedo, guardar la foto de este trazo.
   * Argumentos: ninguno.
   * Efectos: apila una ImageData y apaga el botón Adelante si había rehacer.
   */
  cerrarTrazo(): void {
    if (this.bloqueado || !this.trazoEnCurso) {
      this.trazoEnCurso = false;
      return;
    }
    this.trazoEnCurso = false;
    this.empujarFotoActual();
  }

  /**
   * Objetivo: ignorar trazos mientras carga la imagen ya guardada.
   * Argumentos: ninguno.
   * Efectos: un trazo a medias se descarta; esa espera la tapa la imagen.
   */
  bloquear(): void {
    this.bloqueado = true;
    this.trazoEnCurso = false;
  }

  /**
   * Objetivo: volver a aceptar trazos cuando el diagrama ya está listo.
   * Argumentos: ninguno.
   * Efectos: quita el bloqueo. No toma foto.
   */
  liberar(): void {
    this.bloqueado = false;
  }

  /**
   * Objetivo: empezar de cero al cambiar de vista (Top Cover, Palmrest, etc.).
   * Argumentos: ninguno. Lee los pixeles que ya están en el canvas.
   * Efectos: deja una sola foto (la base). Atrás y Adelante quedan apagados.
   */
  reiniciar(): void {
    this.trazoEnCurso = false;
    this.bloqueado = false;
    // La base es lo que se ve ahora: diagrama solo, o la vista ya guardada.
    this.fotos = [this.capturar()];
    this.indice = 0;
    this.avisar();
  }

  /**
   * Objetivo: "Limpiar trazos" también se puede deshacer.
   * Argumentos: ninguno. El canvas ya debe mostrar el diagrama limpio.
   * Efectos: apila esa foto. Atrás regresa a lo que había justo antes.
   */
  fijarLimpieza(): void {
    this.trazoEnCurso = false;
    this.bloqueado = false;
    this.empujarFotoActual();
  }

  /**
   * Objetivo: saber si el botón Atrás debe encenderse.
   * Argumentos: ninguno.
   * Efectos: ninguno.
   */
  puedeDeshacer(): boolean {
    return this.indice > 0;
  }

  /**
   * Objetivo: saber si el botón Adelante debe encenderse.
   * Argumentos: ninguno.
   * Efectos: ninguno.
   */
  puedeRehacer(): boolean {
    return this.indice >= 0 && this.indice < this.fotos.length - 1;
  }

  /**
   * Objetivo: volver un trazo atrás (Ctrl+Z).
   * Argumentos: ninguno.
   * Efectos: pega la foto anterior en el canvas y deja el lápiz en rojo.
   */
  deshacer(): void {
    if (!this.puedeDeshacer()) {
      return;
    }
    this.indice -= 1;
    this.pegarActual();
  }

  /**
   * Objetivo: recuperar el trazo que se acaba de deshacer (Ctrl+Y).
   * Argumentos: ninguno.
   * Efectos: pega la foto siguiente y deja el lápiz en rojo.
   */
  rehacer(): void {
    if (!this.puedeRehacer()) {
      return;
    }
    this.indice += 1;
    this.pegarActual();
  }

  /**
   * Objetivo: copiar los pixeles actuales del lienzo.
   * Argumentos: ninguno.
   * Efectos: crea un ImageData nuevo. No modifica el canvas.
   */
  private capturar(): ImageData {
    const lienzo = this.ctx.canvas;
    return this.ctx.getImageData(0, 0, lienzo.width, lienzo.height);
  }

  /**
   * Objetivo: guardar la foto de ahora y olvidar el "adelante".
   * Argumentos: ninguno.
   * Efectos: crece la pila (tope 25). Si la foto es idéntica, no apila.
   */
  private empujarFotoActual(): void {
    const foto = this.capturar();
    const actual = this.indice >= 0 ? this.fotos[this.indice] : undefined;
    // Un segundo "Limpiar" sobre el mismo dibujo no merece otro paso.
    if (actual && fotosLienzoIguales(actual, foto)) {
      this.avisar();
      return;
    }
    // Igual que un editor de texto: dibujar después de Atrás borra el rehacer.
    this.fotos = this.fotos.slice(0, this.indice + 1);
    this.fotos.push(foto);
    // Conservamos la base (índice 0) y tiramos el trazo más viejo.
    while (this.fotos.length > TOPE_FOTOS_TRAZO) {
      this.fotos.splice(1, 1);
    }
    this.indice = this.fotos.length - 1;
    this.avisar();
  }

  /**
   * Objetivo: mostrar en pantalla la foto en la que está parada la pila.
   * Argumentos: ninguno.
   * Efectos: reemplaza los pixeles y deja el lápiz rojo para el siguiente trazo.
   */
  private pegarActual(): void {
    const foto = this.fotos[this.indice];
    if (!foto) {
      return;
    }
    this.ctx.putImageData(foto, 0, 0);
    // putImageData no cambia el color del lápiz. Los daños se marcan en rojo.
    this.ctx.strokeStyle = '#c00000';
    this.ctx.lineWidth = 3;
    this.ctx.lineCap = 'round';
    this.ctx.lineJoin = 'round';
    this.avisar();
  }

  /**
   * Objetivo: refrescar Atrás / Adelante (encender o apagar).
   * Argumentos: ninguno.
   * Efectos: llama al callback de la página, si ya se registró.
   */
  private avisar(): void {
    if (this.alCambiar) {
      this.alCambiar();
    }
  }
}

/**
 * Objetivo: escuchar el dedo en el lienzo de daños y anotar cada trazo.
 * No se usa en las firmas: esas solo tienen "Limpiar firma".
 *
 * Argumentos:
 * - canvas: el elemento #canvasDano.
 * - historial: la pila de fotos de esa vista.
 * - estaDibujando: dice si el dedo sigue apoyado (lo lleva el pad).
 *
 * Efectos: registra listeners. Al soltar, puede apilar una foto.
 */
function vigilarTrazosDelLienzo(
  canvas: HTMLCanvasElement,
  historial: HistorialTrazosDano,
  estaDibujando: () => boolean,
): void {
  canvas.addEventListener('pointermove', () => {
    // Solo cuenta si el dedo está apoyado. Mover el mouse sin clic no es trazo.
    if (estaDibujando()) {
      historial.marcarMovimiento();
    }
  });
  const cerrar = (): void => {
    historial.cerrarTrazo();
  };
  canvas.addEventListener('pointerup', cerrar);
  canvas.addEventListener('pointercancel', cerrar);
  canvas.addEventListener('pointerleave', cerrar);
}

/**
 * Objetivo: el foco está en un campo de texto, no en el lienzo.
 * Argumentos: el elemento que recibió la tecla.
 * Efectos: ninguno. Sirve para no robar Ctrl+Z de Observaciones.
 */
function esCampoDeTexto(el: HTMLElement): boolean {
  const etiqueta = el.tagName;
  if (etiqueta === 'INPUT' || etiqueta === 'TEXTAREA' || etiqueta === 'SELECT') {
    return true;
  }
  return el.isContentEditable;
}

/**
 * Objetivo: conectar los botones Atrás / Adelante y los atajos de teclado.
 *
 * Argumentos: historial del lienzo de daños de esta página.
 * Efectos: click en #btnDeshacerTrazo y #btnRehacerTrazo, y Ctrl/Cmd+Z / Y
 * cuando el cursor no está dentro de un campo de texto.
 */
function engancharControlesHistorialTrazos(historial: HistorialTrazosDano): void {
  const btnAtras = document.getElementById('btnDeshacerTrazo') as HTMLButtonElement | null;
  const btnAdelante = document.getElementById('btnRehacerTrazo') as HTMLButtonElement | null;

  const refrescarBotones = (): void => {
    if (btnAtras) {
      btnAtras.disabled = !historial.puedeDeshacer();
    }
    if (btnAdelante) {
      btnAdelante.disabled = !historial.puedeRehacer();
    }
  };

  historial.definirAlCambiar(refrescarBotones);
  btnAtras?.addEventListener('click', () => {
    historial.deshacer();
  });
  btnAdelante?.addEventListener('click', () => {
    historial.rehacer();
  });

  // Ctrl en Windows/Linux, Cmd en Mac. Shift+Z también rehace, como en un editor.
  document.addEventListener('keydown', (ev: KeyboardEvent) => {
    const destino = ev.target instanceof HTMLElement ? ev.target : null;
    if (destino && esCampoDeTexto(destino)) {
      return;
    }
    const conModificador = ev.ctrlKey || ev.metaKey;
    if (!conModificador || ev.altKey) {
      return;
    }
    const tecla = ev.key.toLowerCase();
    if (tecla === 'z' && !ev.shiftKey) {
      ev.preventDefault();
      historial.deshacer();
    } else if (tecla === 'y' || (tecla === 'z' && ev.shiftKey)) {
      ev.preventDefault();
      historial.rehacer();
    }
  });

  refrescarBotones();
}

/**
 * Objetivo: anclar el historial cuando el diagrama (y la foto guardada) ya se ve.
 *
 * Argumentos:
 * - historial: pila de la vista actual.
 * - ctx: contexto del lienzo de daños.
 * - src: URL o data-URL de la vista ya guardada. Vacío si todavía no hay.
 * - generacion: número de esta petición de redibujo.
 * - generacionActual: lee el número más nuevo (por si el técnico cambió de vista).
 * - esLimpieza: true si pulsó "Limpiar trazos" (Atrás debe poder volver).
 *
 * Efectos: si hay imagen, la dibuja al cargar y toma la foto base.
 * Una carga vieja no pisa la vista que el técnico acaba de elegir.
 */
function cerrarBaseDelLienzo(
  historial: HistorialTrazosDano,
  ctx: CanvasRenderingContext2D,
  src: string,
  generacion: number,
  generacionActual: () => number,
  esLimpieza: boolean,
): void {
  const aplicar = (): void => {
    // El técnico ya se fue a otra vista: esta carga llegó tarde.
    if (generacion !== generacionActual()) {
      return;
    }
    // El lápiz de daños es rojo y grueso. drawImage no restaura eso.
    ctx.strokeStyle = '#c00000';
    ctx.lineWidth = 3;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    historial.liberar();
    if (esLimpieza) {
      historial.fijarLimpieza();
    } else {
      historial.reiniciar();
    }
  };

  if (!src) {
    aplicar();
    return;
  }

  // Mientras llega el PNG guardado, no anotes trazos: esa imagen los tapa.
  historial.bloquear();
  const img = new Image();
  img.onload = (): void => {
    if (generacion !== generacionActual()) {
      return;
    }
    ctx.drawImage(img, 0, 0, ctx.canvas.width, ctx.canvas.height);
    aplicar();
  };
  img.onerror = (): void => {
    aplicar();
  };
  img.src = src;
}
