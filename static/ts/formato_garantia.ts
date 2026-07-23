/**
 * Formato Digital Garantía Dell — wizard iPad.
 * Envuelto en IIFE para no chocar con helpers globales de formato_oow.ts
 * (tsc trata ambos archivos como scripts en el mismo scope).
 */
(() => {
/**
 * Formato Digital Garantía Dell — wizard iPad (firmas, daños, guardar/finalizar).
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Clonado y adaptado desde formato_oow.ts: mismos canvas/firmas/emails,
 * pero con accesorios Dell, número de cargador y solo foto PC Audit (sin INE).
 * Se edita en static/ts/ y se compila a static/js/ con pnpm run build.
 */

interface VistaDanoGuardada {
  clave_vista: string;
  etiqueta_dano: string;
  imagen_data?: string;
  imagen_url?: string;
}

interface FormatoGarantiaPayload {
  tipo_diagrama: string;
  accesorio_cargador: boolean;
  accesorio_teclado: boolean;
  accesorio_pluma: boolean;
  accesorio_mouse: boolean;
  accesorio_monitor: boolean;
  accesorio_caja: boolean;
  accesorio_bateria: boolean;
  accesorio_docking: boolean;
  accesorio_microsd_sim: boolean;
  accesorio_otros: boolean;
  accesorios_otros_detalle: string;
  numero_cargador: string;
  observaciones_tecnicas: string;
  disclaimer_pc_audit: boolean;
  acepta_condiciones: boolean;
  acepta_privacidad: boolean;
  email_envio: string;
  emails_envio: string[];
  como_enteraste: string;
  firma_cliente_data: string;
  vistas_dano: VistaDanoGuardada[];
  enviar_email?: boolean;
  forzar_regenerar?: boolean;
  /** Si true: regenera PDF sin reenviar correo (formato ya finalizado) */
  solo_regenerar?: boolean;
}

/** Máximo de correos para compartir el PDF del formato Garantía */
const MAX_EMAILS_ENVIO = 3;

interface PadState {
  canvas: HTMLCanvasElement;
  ctx: CanvasRenderingContext2D;
  dibujando: boolean;
  tieneTrazos: boolean;
}

function leerCookieCsrf(): string {
  const cookieNames: string[] = ['sigma_csrftoken', 'csrftoken'];
  for (const name of cookieNames) {
    const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
    if (match) {
      return decodeURIComponent(match[1]);
    }
  }
  return '';
}

function byId(id: string): HTMLElement | null {
  return document.getElementById(id);
}

function valorInput(id: string): string {
  const el = byId(id) as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement | null;
  return el ? el.value : '';
}

function checked(id: string): boolean {
  const el = byId(id) as HTMLInputElement | null;
  return Boolean(el && el.checked);
}

function setStatus(mensaje: string, esError: boolean = false, cargando: boolean = false): void {
  const box = byId('formatoGarantiaStatusBox');
  const el = byId('formatoGarantiaStatus');
  const spinner = byId('formatoGarantiaSpinner');
  if (!el || !box) {
    return;
  }
  box.hidden = mensaje.length === 0;
  el.textContent = mensaje;
  el.classList.toggle('text-danger', esError);
  el.classList.toggle('text-success', !esError && !cargando && mensaje.length > 0);
  el.classList.toggle('text-primary', cargando);
  if (spinner) {
    spinner.hidden = !cargando;
  }
}

function setOverlay(visible: boolean, titulo?: string, texto?: string): void {
  const overlay = byId('formatoGarantiaOverlay');
  if (!overlay) {
    return;
  }
  overlay.hidden = !visible;
  overlay.setAttribute('aria-hidden', visible ? 'false' : 'true');
  const t = byId('formatoGarantiaOverlayTitulo');
  const d = byId('formatoGarantiaOverlayTexto');
  if (t && titulo) {
    t.textContent = titulo;
  }
  if (d && texto) {
    d.textContent = texto;
  }
}

function setBotonesOcupados(ocupado: boolean): void {
  const ids = ['btnGuardarBorrador', 'btnFinalizar', 'btnRegenerarPdf', 'btnReenviarEmail'];
  ids.forEach((id) => {
    const btn = byId(id) as HTMLButtonElement | null;
    if (btn) {
      btn.disabled = ocupado;
    }
  });
}

function crearPad(canvas: HTMLCanvasElement): PadState {
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    throw new Error('No se pudo inicializar el canvas');
  }
  // Fondo blanco para que el PNG tenga contraste en el PDF
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = '#003366';
  ctx.lineWidth = 2.5;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  const pad: PadState = {
    canvas,
    ctx,
    dibujando: false,
    tieneTrazos: false,
  };

  const pos = (ev: PointerEvent): { x: number; y: number } => {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    return {
      x: (ev.clientX - rect.left) * scaleX,
      y: (ev.clientY - rect.top) * scaleY,
    };
  };

  // EXPLICACIÓN PARA PRINCIPIANTES:
  // En iPad, mantener el dedo provoca menú de selección de texto / callout.
  // Desactivamos selección, callout y gestos del navegador sobre el canvas.
  canvas.style.touchAction = 'none';
  canvas.style.userSelect = 'none';
  (canvas.style as CSSStyleDeclaration & { webkitUserSelect?: string }).webkitUserSelect = 'none';
  (canvas.style as CSSStyleDeclaration & { webkitTouchCallout?: string }).webkitTouchCallout = 'none';
  canvas.setAttribute('draggable', 'false');

  const bloquearGesto = (ev: Event): void => {
    ev.preventDefault();
  };
  canvas.addEventListener('contextmenu', bloquearGesto);
  canvas.addEventListener('selectstart', bloquearGesto);
  canvas.addEventListener('dragstart', bloquearGesto);
  // touchstart con passive:false permite preventDefault en Safari/iPadOS
  canvas.addEventListener('touchstart', bloquearGesto, { passive: false });
  canvas.addEventListener('touchmove', bloquearGesto, { passive: false });

  canvas.addEventListener('pointerdown', (ev: PointerEvent) => {
    ev.preventDefault();
    pad.dibujando = true;
    canvas.setPointerCapture(ev.pointerId);
    const p = pos(ev);
    ctx.beginPath();
    ctx.moveTo(p.x, p.y);
  });

  canvas.addEventListener('pointermove', (ev: PointerEvent) => {
    if (!pad.dibujando) {
      return;
    }
    ev.preventDefault();
    const p = pos(ev);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    pad.tieneTrazos = true;
  });

  const fin = (ev: PointerEvent): void => {
    if (!pad.dibujando) {
      return;
    }
    ev.preventDefault();
    pad.dibujando = false;
    try {
      canvas.releasePointerCapture(ev.pointerId);
    } catch {
      // ignore
    }
  };
  canvas.addEventListener('pointerup', fin);
  canvas.addEventListener('pointercancel', fin);
  canvas.addEventListener('pointerleave', (ev: PointerEvent) => {
    // Si el dedo sale del canvas sin soltar, terminamos el trazo
    if (pad.dibujando) {
      fin(ev);
    }
  });

  return pad;
}

function limpiarPad(pad: PadState): void {
  pad.ctx.fillStyle = '#ffffff';
  pad.ctx.fillRect(0, 0, pad.canvas.width, pad.canvas.height);
  pad.ctx.strokeStyle = '#003366';
  pad.ctx.lineWidth = 2.5;
  pad.tieneTrazos = false;
}

/**
 * Dibuja un puerto USB-A (rectángulo con muesca).
 */
function dibujarPuertoUsb(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  ancho: number,
  alto: number,
): void {
  ctx.strokeRect(x, y, ancho, alto);
  ctx.beginPath();
  ctx.moveTo(x + 3, y + alto * 0.35);
  ctx.lineTo(x + ancho - 3, y + alto * 0.35);
  ctx.stroke();
}

/**
 * Dibuja un jack de audio (círculo).
 */
function dibujarJackAudio(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  radio: number,
): void {
  ctx.beginPath();
  ctx.arc(cx, cy, radio, 0, Math.PI * 2);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(cx, cy, radio * 0.4, 0, Math.PI * 2);
  ctx.stroke();
}

/**
 * Dibuja el perfil lateral de un equipo (laptop / AIO / torre) con puertos.
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * En lugar de un cuadro genérico, dibujamos un chasis delgado horizontal
 * (como si vieras el costado del equipo) y varios tipos de puertos.
 */
function dibujarPerfilLateral(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  m: number,
  esIzquierdo: boolean,
): void {
  // Chasis: franja horizontal al centro (perfil delgado)
  const chasisY = h * 0.38;
  const chasisAlto = Math.max(42, h * 0.18);
  const chasisX = m + 28;
  const chasisAncho = w - m * 2 - 56;

  ctx.lineWidth = 2.2;
  ctx.strokeStyle = '#334155';
  // Cuerpo principal redondeado visualmente con rectángulo
  ctx.strokeRect(chasisX, chasisY, chasisAncho, chasisAlto);

  // Bisagras / engrosamiento del lado de la pantalla (laptop)
  const bisagraAncho = 18;
  if (esIzquierdo) {
    ctx.fillStyle = '#e2e8f0';
    ctx.fillRect(chasisX, chasisY - 6, bisagraAncho, chasisAlto + 12);
    ctx.strokeRect(chasisX, chasisY - 6, bisagraAncho, chasisAlto + 12);
  } else {
    ctx.fillStyle = '#e2e8f0';
    ctx.fillRect(chasisX + chasisAncho - bisagraAncho, chasisY - 6, bisagraAncho, chasisAlto + 12);
    ctx.strokeRect(chasisX + chasisAncho - bisagraAncho, chasisY - 6, bisagraAncho, chasisAlto + 12);
  }

  // Línea de ranura del chasis
  ctx.strokeStyle = '#94a3b8';
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  ctx.moveTo(chasisX + 8, chasisY + chasisAlto / 2);
  ctx.lineTo(chasisX + chasisAncho - 8, chasisY + chasisAlto / 2);
  ctx.stroke();

  // Zona de puertos a lo largo del perfil
  const puertoY = chasisY + chasisAlto * 0.22;
  const puertoAlto = chasisAlto * 0.55;
  let x = chasisX + (esIzquierdo ? 36 : 28);
  ctx.strokeStyle = '#475569';
  ctx.lineWidth = 1.6;

  // Orden típico: lado izq → DC, USB, HDMI, USB-C, audio
  // lado der → USB, SD, USB-C, Kensington
  const dibujarEtiquetaMini = (texto: string, px: number): void => {
    ctx.save();
    ctx.fillStyle = '#64748b';
    ctx.font = '9px Helvetica, Arial, sans-serif';
    ctx.fillText(texto, px, chasisY + chasisAlto + 16);
    ctx.restore();
  };

  if (esIzquierdo) {
    // Power / DC barrel
    ctx.beginPath();
    ctx.arc(x + 8, puertoY + puertoAlto / 2, puertoAlto * 0.38, 0, Math.PI * 2);
    ctx.stroke();
    dibujarEtiquetaMini('DC', x);
    x += 28;

    // USB-A
    dibujarPuertoUsb(ctx, x, puertoY, 22, puertoAlto);
    dibujarEtiquetaMini('USB', x);
    x += 32;

    // HDMI (rectángulo más ancho)
    ctx.strokeRect(x, puertoY + 2, 28, puertoAlto - 4);
    ctx.beginPath();
    ctx.moveTo(x + 4, puertoY + puertoAlto - 6);
    ctx.lineTo(x + 24, puertoY + puertoAlto - 6);
    ctx.stroke();
    dibujarEtiquetaMini('HDMI', x);
    x += 38;

    // USB-C (ranura delgada)
    ctx.strokeRect(x, puertoY + puertoAlto * 0.25, 18, puertoAlto * 0.5);
    dibujarEtiquetaMini('USB-C', x - 2);
    x += 30;

    // Audio jack
    dibujarJackAudio(ctx, x + 8, puertoY + puertoAlto / 2, puertoAlto * 0.32);
    dibujarEtiquetaMini('Audio', x);
  } else {
    // USB-A
    dibujarPuertoUsb(ctx, x, puertoY, 22, puertoAlto);
    dibujarEtiquetaMini('USB', x);
    x += 32;

    // Lector SD (ranura ancha baja)
    ctx.strokeRect(x, puertoY + puertoAlto * 0.35, 34, puertoAlto * 0.4);
    dibujarEtiquetaMini('SD', x + 8);
    x += 44;

    // USB-C
    ctx.strokeRect(x, puertoY + puertoAlto * 0.25, 18, puertoAlto * 0.5);
    dibujarEtiquetaMini('USB-C', x - 2);
    x += 30;

    // USB-A segundo
    dibujarPuertoUsb(ctx, x, puertoY, 22, puertoAlto);
    dibujarEtiquetaMini('USB', x);
    x += 32;

    // Kensington lock (círculo pequeño)
    ctx.beginPath();
    ctx.arc(x + 7, puertoY + puertoAlto / 2, 6, 0, Math.PI * 2);
    ctx.stroke();
    dibujarEtiquetaMini('Lock', x);
  }

  // Patas del equipo debajo del chasis
  ctx.strokeStyle = '#64748b';
  ctx.lineWidth = 1.5;
  const pataY = chasisY + chasisAlto;
  ctx.strokeRect(chasisX + 20, pataY, 14, 10);
  ctx.strokeRect(chasisX + chasisAncho - 34, pataY, 14, 10);
}

/**
 * Lateral de torre/PC: chasis vertical con bahías y panel trasero esquemático.
 *
 * @param esIzquierdo - true = lateral izquierdo; false = derecho; undefined = genérico (legacy)
 */
function dibujarLateralPcTorre(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  m: number,
  esIzquierdo?: boolean,
): void {
  const cajaX = w * 0.28;
  const cajaY = m + 28;
  const cajaAncho = w * 0.44;
  const cajaAlto = h - m * 2 - 40;

  ctx.strokeStyle = '#334155';
  ctx.lineWidth = 2.4;
  ctx.strokeRect(cajaX, cajaY, cajaAncho, cajaAlto);

  // Panel frontal (izquierda del lateral tipico)
  ctx.fillStyle = '#f1f5f9';
  ctx.fillRect(cajaX, cajaY, 22, cajaAlto);
  ctx.strokeRect(cajaX, cajaY, 22, cajaAlto);

  // Bahía óptica / drive
  ctx.strokeStyle = '#64748b';
  ctx.lineWidth = 1.5;
  ctx.strokeRect(cajaX + 28, cajaY + 24, cajaAncho - 40, 28);
  ctx.beginPath();
  ctx.moveTo(cajaX + 36, cajaY + 38);
  ctx.lineTo(cajaX + cajaAncho - 20, cajaY + 38);
  ctx.stroke();

  // Botón power + LED
  ctx.beginPath();
  ctx.arc(cajaX + 11, cajaY + cajaAlto * 0.55, 6, 0, Math.PI * 2);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(cajaX + 11, cajaY + cajaAlto * 0.55 + 18, 3, 0, Math.PI * 2);
  ctx.fillStyle = '#22c55e';
  ctx.fill();

  // Rejilla de ventilación
  ctx.strokeStyle = '#94a3b8';
  for (let i = 0; i < 8; i++) {
    const y = cajaY + cajaAlto * 0.62 + i * 10;
    ctx.beginPath();
    ctx.moveTo(cajaX + 32, y);
    ctx.lineTo(cajaX + cajaAncho - 16, y);
    ctx.stroke();
  }

  // Patas
  ctx.strokeStyle = '#64748b';
  ctx.strokeRect(cajaX + 8, cajaY + cajaAlto, 16, 8);
  ctx.strokeRect(cajaX + cajaAncho - 24, cajaY + cajaAlto, 16, 8);

  ctx.fillStyle = '#64748b';
  ctx.font = '10px Helvetica, Arial, sans-serif';
  // EXPLICACIÓN PARA PRINCIPIANTES:
  // Texto bajo la torre: indica si es lateral izq./der. o genérico (vistas viejas).
  let leyenda = 'Torre / PC';
  if (esIzquierdo === true) {
    leyenda = 'Torre / PC — LATERAL IZQ.';
  } else if (esIzquierdo === false) {
    leyenda = 'Torre / PC — LATERAL DER.';
  }
  ctx.fillText(leyenda, cajaX, cajaY + cajaAlto + 22);
}

/**
 * Lateral de All in One: perfil delgado vertical (monitor) + pie.
 */
function dibujarLateralAio(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  m: number,
  esIzquierdo: boolean,
): void {
  // Perfil delgado del panel (como ver el AIO de costado)
  const panelAncho = Math.max(28, w * 0.07);
  const panelX = w / 2 - panelAncho / 2;
  const panelY = m + 30;
  const panelAlto = h * 0.55;

  ctx.strokeStyle = '#334155';
  ctx.lineWidth = 2.4;
  ctx.strokeRect(panelX, panelY, panelAncho, panelAlto);

  // Pantalla (cara frontal sutil)
  if (esIzquierdo) {
    ctx.fillStyle = '#e2e8f0';
    ctx.fillRect(panelX - 6, panelY + 8, 6, panelAlto - 16);
    ctx.strokeRect(panelX - 6, panelY + 8, 6, panelAlto - 16);
  } else {
    ctx.fillStyle = '#e2e8f0';
    ctx.fillRect(panelX + panelAncho, panelY + 8, 6, panelAlto - 16);
    ctx.strokeRect(panelX + panelAncho, panelY + 8, 6, panelAlto - 16);
  }

  // Cuello / soporte
  const cuelloAncho = 14;
  const cuelloX = w / 2 - cuelloAncho / 2;
  const cuelloY = panelY + panelAlto;
  const cuelloAlto = h * 0.14;
  ctx.strokeRect(cuelloX, cuelloY, cuelloAncho, cuelloAlto);

  // Base
  const baseAncho = w * 0.35;
  const baseX = w / 2 - baseAncho / 2;
  const baseY = cuelloY + cuelloAlto;
  ctx.strokeRect(baseX, baseY, baseAncho, 16);

  // Puertos en el canto inferior/trasero del panel (no como laptop)
  ctx.strokeStyle = '#475569';
  ctx.lineWidth = 1.4;
  const puertoBaseY = panelY + panelAlto - 36;
  const ladoPuertos = esIzquierdo ? panelX + panelAncho + 10 : panelX - 40;
  // HDMI
  ctx.strokeRect(ladoPuertos, puertoBaseY, 26, 12);
  // USB
  ctx.strokeRect(ladoPuertos, puertoBaseY + 16, 18, 10);
  // DC
  ctx.beginPath();
  ctx.arc(ladoPuertos + 10, puertoBaseY + 38, 6, 0, Math.PI * 2);
  ctx.stroke();

  ctx.fillStyle = '#64748b';
  ctx.font = '9px Helvetica, Arial, sans-serif';
  ctx.fillText('HDMI', ladoPuertos, puertoBaseY - 4);
  ctx.fillText('USB', ladoPuertos, puertoBaseY + 14);
  ctx.fillText('DC', ladoPuertos, puertoBaseY + 52);

  ctx.fillStyle = '#64748b';
  ctx.font = '10px Helvetica, Arial, sans-serif';
  ctx.fillText('All in One (perfil)', baseX, baseY + 30);
}

function dibujarMarcoDiagrama(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  etiqueta: string,
  claveVista: string = '',
): void {
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, w, h);

  const m = 24;
  const etiquetaNorm = etiqueta.toLowerCase();
  const clave = (claveVista || '').toLowerCase();

  // Título de la vista
  ctx.fillStyle = '#003366';
  ctx.font = 'bold 15px Helvetica, Arial, sans-serif';
  ctx.fillText(etiqueta.toUpperCase(), m, 18);

  ctx.strokeStyle = '#334155';
  ctx.lineWidth = 2;

  // --- Laterales: distinto esquema según laptop / PC / AIO ---
  // Laptop: lat_izq / lat_der → perfil horizontal con puertos
  if (clave === 'lat_izq' || clave === 'lat_der') {
    dibujarPerfilLateral(ctx, w, h, m, clave === 'lat_izq');
    return;
  }
  // PC escritorio: laterales izq/der (y "lateral" legacy) → torre vertical
  if (clave === 'esc_lat_izq' || clave === 'esc_lat_der' || clave === 'lateral') {
    const esIzq =
      clave === 'esc_lat_izq' ? true : clave === 'esc_lat_der' ? false : undefined;
    dibujarLateralPcTorre(ctx, w, h, m, esIzq);
    return;
  }
  // All in One: aio_lat_* → perfil delgado de monitor + pie
  if (clave === 'aio_lat_izq' || clave === 'aio_lat_der') {
    dibujarLateralAio(ctx, w, h, m, clave === 'aio_lat_izq');
    return;
  }

  // Marco exterior para el resto de vistas
  ctx.lineWidth = 3;
  ctx.strokeRect(m, m + 8, w - m * 2, h - m * 2 - 8);
  ctx.strokeStyle = '#94a3b8';
  ctx.lineWidth = 1.5;

  if (etiquetaNorm.includes('pantalla') || etiquetaNorm.includes('frente')) {
    // Marco tipo pantalla (laptop / AIO / monitor)
    ctx.strokeRect(m + 20, m + 28, w - m * 2 - 40, h - m * 2 - 58);
    // Bisel inferior
    ctx.beginPath();
    ctx.moveTo(m + 20, h - m - 28);
    ctx.lineTo(w - m - 20, h - m - 28);
    ctx.stroke();
    // Cámara / notch superior
    ctx.beginPath();
    ctx.arc(w / 2, m + 40, 4, 0, Math.PI * 2);
    ctx.fillStyle = '#94a3b8';
    ctx.fill();
    // Pie AIO solo en pantalla de AIO
    if (clave.startsWith('aio_')) {
      ctx.strokeStyle = '#64748b';
      ctx.strokeRect(w / 2 - 12, h - m - 22, 24, 14);
      ctx.strokeRect(w / 2 - 50, h - m - 10, 100, 8);
    }
  } else if (etiquetaNorm.includes('top cover') || (etiquetaNorm.includes('top') && !etiquetaNorm.includes('laptop'))) {
    // Tapa superior laptop
    ctx.strokeRect(m + 30, m + 40, w - m * 2 - 60, h - m * 2 - 70);
    ctx.beginPath();
    ctx.arc(w / 2, h / 2, 22, 0, Math.PI * 2);
    ctx.stroke();
  } else if (etiquetaNorm.includes('palm') || etiquetaNorm.includes('teclado')) {
    // Zona teclado
    ctx.strokeRect(m + 30, m + 40, w - m * 2 - 60, h * 0.38);
    for (let fila = 0; fila < 4; fila++) {
      const y = m + 55 + fila * 22;
      for (let col = 0; col < 10; col++) {
        const x = m + 45 + col * ((w - m * 2 - 100) / 10);
        ctx.strokeRect(x, y, 14, 14);
      }
    }
    ctx.strokeRect(w / 2 - 50, h - m - 85, 100, 55);
  } else if (etiquetaNorm.includes('bottom') || etiquetaNorm.includes('trasera')) {
    ctx.beginPath();
    ctx.arc(m + 50, m + 55, 16, 0, Math.PI * 2);
    ctx.arc(w - m - 50, m + 55, 16, 0, Math.PI * 2);
    ctx.arc(m + 50, h - m - 45, 16, 0, Math.PI * 2);
    ctx.arc(w - m - 50, h - m - 45, 16, 0, Math.PI * 2);
    ctx.stroke();
    for (let i = 0; i < 6; i++) {
      const y = m + 90 + i * 14;
      ctx.beginPath();
      ctx.moveTo(m + 90, y);
      ctx.lineTo(w - m - 90, y);
      ctx.stroke();
    }
  } else if (etiquetaNorm.includes('superior')) {
    ctx.strokeRect(m + 40, m + 40, w - m * 2 - 80, h - m * 2 - 60);
  } else if (etiquetaNorm.includes('base') || etiquetaNorm.includes('soporte')) {
    ctx.strokeRect(m + 80, m + 50, w - m * 2 - 160, 28);
    ctx.strokeRect(w / 2 - 55, m + 90, 110, h - m * 2 - 110);
  }
}

function inicializarFormatoGarantia(): void {
  const app = byId('formatoGarantiaApp');
  if (!app) {
    return;
  }

  const urlGuardar = app.dataset.urlGuardar || '';
  const urlFinalizar = app.dataset.urlFinalizar || '';
  const urlReenviar = app.dataset.urlReenviar || '';
  const urlPdf = app.dataset.urlPdf || '';
  const urlEvidencia = app.dataset.urlEvidencia || '';
  // Plantilla con 999999999: se sustituye por el id real al eliminar
  const urlEliminarEvidenciaTpl = app.dataset.urlEliminarEvidencia || '';

  const dataEl = document.getElementById('formato-garantia-data');
  let formatoInicial: {
    vistas_dano?: VistaDanoGuardada[];
    firma_cliente_url?: string;
    email_envio?: string;
    emails_envio?: string[];
  } = {};
  if (dataEl && dataEl.textContent) {
    try {
      formatoInicial = JSON.parse(dataEl.textContent) as typeof formatoInicial;
    } catch {
      formatoInicial = {};
    }
  }

  /**
   * Resalta una sección y hace scroll (tablet: el operador ve qué falta).
   */
  const enfocarSeccion = (seccionId: string): void => {
    document.querySelectorAll('.formato-oow-card.is-error-focus').forEach((el) => {
      el.classList.remove('is-error-focus');
    });
    const seccion = byId(seccionId);
    if (!seccion) {
      return;
    }
    seccion.classList.add('is-error-focus');
    seccion.scrollIntoView({ behavior: 'smooth', block: 'start' });
    window.setTimeout(() => {
      seccion.classList.remove('is-error-focus');
    }, 3500);
  };

  /**
   * Lee los correos escritos en los inputs dinámicos (máx. 3).
   */
  const leerEmailsEnvio = (): string[] => {
    const lista = byId('emailsEnvioLista');
    if (!lista) {
      return [];
    }
    const valores: string[] = [];
    const vistos = new Set<string>();
    lista.querySelectorAll<HTMLInputElement>('input[type="email"]').forEach((input) => {
      const email = input.value.trim();
      if (!email) {
        return;
      }
      const clave = email.toLowerCase();
      if (vistos.has(clave)) {
        return;
      }
      vistos.add(clave);
      valores.push(email);
    });
    return valores.slice(0, MAX_EMAILS_ENVIO);
  };

  /**
   * Actualiza el botón "Agregar otro correo" según cuántos campos hay.
   */
  const actualizarBtnAgregarEmail = (): void => {
    const lista = byId('emailsEnvioLista');
    const btn = byId('btnAgregarEmail') as HTMLButtonElement | null;
    if (!lista || !btn) {
      return;
    }
    const cantidad = lista.querySelectorAll('.formato-oow-email-row').length;
    btn.disabled = cantidad >= MAX_EMAILS_ENVIO;
    btn.title = cantidad >= MAX_EMAILS_ENVIO
      ? 'Máximo 3 correos'
      : 'Agregar otro destinatario';
  };

  /**
   * Crea una fila de email (input + botón quitar si no es el primero).
   */
  const crearFilaEmail = (valor: string, indice: number): HTMLDivElement => {
    const row = document.createElement('div');
    row.className = 'formato-oow-email-row';

    const input = document.createElement('input');
    input.type = 'email';
    input.className = 'form-control';
    input.placeholder = indice === 0
      ? 'correo@cliente.com'
      : `correo adicional ${indice + 1}`;
    input.value = valor;
    input.autocomplete = 'email';
    input.setAttribute('aria-label', `Correo ${indice + 1} para recibir el formato`);

    row.appendChild(input);

    // El primero no se quita (siempre hay al menos un campo); los demás sí
    if (indice > 0) {
      const btnQuitar = document.createElement('button');
      btnQuitar.type = 'button';
      btnQuitar.className = 'btn btn-outline-danger btn-sm formato-oow-email-quitar';
      btnQuitar.setAttribute('aria-label', 'Quitar este correo');
      btnQuitar.innerHTML = '<i class="bi bi-trash"></i>';
      btnQuitar.addEventListener('click', () => {
        row.remove();
        actualizarBtnAgregarEmail();
      });
      row.appendChild(btnQuitar);
    }

    return row;
  };

  /**
   * Inicializa 1–3 campos de email desde el borrador guardado.
   */
  const inicializarEmailsEnvio = (): void => {
    const lista = byId('emailsEnvioLista');
    if (!lista) {
      return;
    }
    lista.innerHTML = '';
    // Preferir lista JSON; si no, el email_envio legacy
    let iniciales = (formatoInicial.emails_envio || []).filter((e) => Boolean(e && e.trim()));
    if (iniciales.length === 0 && formatoInicial.email_envio) {
      iniciales = [formatoInicial.email_envio];
    }
    if (iniciales.length === 0) {
      iniciales = [''];
    }
    iniciales.slice(0, MAX_EMAILS_ENVIO).forEach((email, i) => {
      lista.appendChild(crearFilaEmail(email, i));
    });
    actualizarBtnAgregarEmail();
  };

  inicializarEmailsEnvio();

  byId('btnAgregarEmail')?.addEventListener('click', () => {
    const lista = byId('emailsEnvioLista');
    if (!lista) {
      return;
    }
    const cantidad = lista.querySelectorAll('.formato-oow-email-row').length;
    if (cantidad >= MAX_EMAILS_ENVIO) {
      return;
    }
    lista.appendChild(crearFilaEmail('', cantidad));
    actualizarBtnAgregarEmail();
    const inputs = lista.querySelectorAll<HTMLInputElement>('input[type="email"]');
    const ultimo = inputs[inputs.length - 1];
    if (ultimo) {
      ultimo.focus();
    }
  });

  const canvasDano = byId('canvasDano') as HTMLCanvasElement | null;
  const canvasFirmaCli = byId('canvasFirmaCliente') as HTMLCanvasElement | null;
  if (!canvasDano || !canvasFirmaCli) {
    return;
  }

  const padDano = crearPad(canvasDano);
  const padFirmaCli = crearPad(canvasFirmaCli);

  // Firma cliente: trazo negro un poco más grueso
  padFirmaCli.ctx.strokeStyle = '#111827';
  padFirmaCli.ctx.lineWidth = 2.2;

  /**
   * Actualiza checklist sticky (firma / condiciones / privacidad).
   *
   * EXPLICACIÓN PARA PRINCIPIANTES:
   * Antes de Finalizar, la barra inferior muestra en verde lo listo
   * y en ámbar lo pendiente, para no perderse en el scroll largo.
   */
  const actualizarChecklistRequeridos = (): void => {
    const tieneFirma = padFirmaCli.tieneTrazos || Boolean(formatoInicial.firma_cliente_url);
    const items: Array<{ id: string; listo: boolean; chipId?: string }> = [
      { id: 'checkItemFirma', listo: tieneFirma, chipId: 'chipFirma' },
      { id: 'checkItemCondiciones', listo: checked('aceptaCondiciones') },
      { id: 'checkItemPrivacidad', listo: checked('aceptaPrivacidad'), chipId: 'chipEnvio' },
    ];
    items.forEach((item) => {
      const el = byId(item.id);
      if (!el) {
        return;
      }
      el.classList.toggle('is-listo', item.listo);
      el.classList.toggle('is-pendiente', !item.listo);
      if (item.chipId) {
        const chip = byId(item.chipId);
        if (chip) {
          chip.classList.toggle('is-listo', item.listo);
          chip.classList.toggle('is-pendiente', !item.listo);
        }
      }
    });
  };

  /**
   * Actualiza la miniatura de firma (igual que las previews de daños).
   */
  const actualizarPreviewFirma = (src: string): void => {
    const wrap = byId('firmaClientePreviewWrap');
    const img = byId('firmaClientePreviewImg') as HTMLImageElement | null;
    if (!wrap || !img) {
      return;
    }
    if (!src) {
      wrap.hidden = true;
      img.removeAttribute('src');
      return;
    }
    img.src = src;
    wrap.hidden = false;
  };

  /**
   * Carga una firma ya guardada en el canvas para que el usuario la vea.
   */
  const cargarFirmaEnCanvas = (url: string): void => {
    const img = new Image();
    img.onload = (): void => {
      padFirmaCli.ctx.fillStyle = '#ffffff';
      padFirmaCli.ctx.fillRect(0, 0, canvasFirmaCli.width, canvasFirmaCli.height);
      // Centrar la firma proporcionalmente en el canvas
      const scale = Math.min(
        canvasFirmaCli.width / img.width,
        canvasFirmaCli.height / img.height,
      );
      const w = img.width * scale;
      const h = img.height * scale;
      const x = (canvasFirmaCli.width - w) / 2;
      const y = (canvasFirmaCli.height - h) / 2;
      padFirmaCli.ctx.drawImage(img, x, y, w, h);
      padFirmaCli.ctx.strokeStyle = '#111827';
      padFirmaCli.ctx.lineWidth = 2.2;
      padFirmaCli.tieneTrazos = true;
      actualizarPreviewFirma(url);
      actualizarChecklistRequeridos();
    };
    img.src = url;
  };

  if (formatoInicial.firma_cliente_url) {
    cargarFirmaEnCanvas(formatoInicial.firma_cliente_url);
  }

  const vistasGuardadas: Map<string, VistaDanoGuardada> = new Map();
  (formatoInicial.vistas_dano || []).forEach((v) => {
    vistasGuardadas.set(v.clave_vista, v);
  });

  // EXPLICACIÓN PARA PRINCIPIANTES:
  // En iPad Safari, option.hidden NO oculta opciones del <select>.
  // Por eso guardamos el catálogo completo y reconstruimos el select
  // dejando solo las vistas del tipo de equipo elegido.
  type VistaOpcion = { value: string; label: string; grupo: string };
  const catalogoVistas: VistaOpcion[] = (() => {
    const selInit = byId('vistaActiva') as HTMLSelectElement | null;
    if (!selInit) {
      return [];
    }
    return Array.from(selInit.options).map((opt) => ({
      value: opt.value,
      label: opt.textContent || opt.value,
      grupo: opt.getAttribute('data-grupo') || '',
    }));
  })();

  const refrescarDiagrama = (): void => {
    const vistaSel = byId('vistaActiva') as HTMLSelectElement | null;
    const clave = vistaSel ? vistaSel.value : 'pantalla';
    const label = vistaSel && vistaSel.selectedOptions[0]
      ? vistaSel.selectedOptions[0].text
      : clave;
    dibujarMarcoDiagrama(padDano.ctx, canvasDano.width, canvasDano.height, label, clave);
    padDano.ctx.strokeStyle = '#c00000';
    padDano.ctx.lineWidth = 3;
    padDano.tieneTrazos = false;

    // Si hay imagen previa de la vista, mostrarla de fondo
    const previa = vistasGuardadas.get(clave);
    if (previa && previa.imagen_url) {
      const img = new Image();
      img.onload = (): void => {
        padDano.ctx.drawImage(img, 0, 0, canvasDano.width, canvasDano.height);
        padDano.ctx.strokeStyle = '#c00000';
        padDano.ctx.lineWidth = 3;
      };
      img.src = previa.imagen_url;
    } else if (previa && previa.imagen_data) {
      const img = new Image();
      img.onload = (): void => {
        padDano.ctx.drawImage(img, 0, 0, canvasDano.width, canvasDano.height);
        padDano.ctx.strokeStyle = '#c00000';
        padDano.ctx.lineWidth = 3;
      };
      img.src = previa.imagen_data;
    }
  };

  const filtrarVistasPorTipo = (): void => {
    const tipo = valorInput('tipoDiagrama');
    const sel = byId('vistaActiva') as HTMLSelectElement | null;
    if (!sel) {
      return;
    }
    const valorAnterior = sel.value;
    const delTipo = catalogoVistas.filter((v) => v.grupo === tipo);

    // Vaciar y recrear opciones (compatible con iPad)
    sel.innerHTML = '';
    delTipo.forEach((v) => {
      const opt = document.createElement('option');
      opt.value = v.value;
      opt.textContent = v.label;
      opt.setAttribute('data-grupo', v.grupo);
      sel.appendChild(opt);
    });

    // Conservar la vista si sigue siendo válida para este tipo
    const sigueValida = delTipo.some((v) => v.value === valorAnterior);
    if (sigueValida) {
      sel.value = valorAnterior;
    } else if (delTipo.length > 0) {
      sel.value = delTipo[0].value;
    }
    refrescarDiagrama();
  };

  const renderThumbsVistas = (): void => {
    const cont = byId('vistasGuardadas');
    if (!cont) {
      return;
    }
    cont.innerHTML = '';
    if (vistasGuardadas.size === 0) {
      cont.innerHTML = '<p class="text-muted small mb-0">Ninguna vista guardada aún.</p>';
      return;
    }
    vistasGuardadas.forEach((v) => {
      const card = document.createElement('div');
      card.className = 'formato-oow-vista-thumb';
      const src = v.imagen_data || v.imagen_url || '';
      card.innerHTML = `
        <img src="${src}" alt="${v.clave_vista}">
        <span>${v.clave_vista}${v.etiqueta_dano ? ' — ' + v.etiqueta_dano : ''}</span>
      `;
      cont.appendChild(card);
    });
  };

  filtrarVistasPorTipo();
  renderThumbsVistas();

  byId('tipoDiagrama')?.addEventListener('change', filtrarVistasPorTipo);
  byId('vistaActiva')?.addEventListener('change', refrescarDiagrama);

  byId('btnLimpiarVista')?.addEventListener('click', () => {
    refrescarDiagrama();
  });

  byId('btnGuardarVista')?.addEventListener('click', () => {
    const clave = valorInput('vistaActiva');
    const etiqueta = valorInput('etiquetaDano');
    const dataUrl = canvasDano.toDataURL('image/png');
    vistasGuardadas.set(clave, {
      clave_vista: clave,
      etiqueta_dano: etiqueta,
      imagen_data: dataUrl,
    });
    renderThumbsVistas();
    setStatus(`Vista “${clave}” guardada en memoria (se enviará al guardar).`);
  });

  // Al soltar el dedo/pluma en la firma, refrescar la miniatura preview
  canvasFirmaCli.addEventListener('pointerup', () => {
    if (padFirmaCli.tieneTrazos) {
      actualizarPreviewFirma(canvasFirmaCli.toDataURL('image/png'));
      actualizarChecklistRequeridos();
    }
  });

  byId('btnLimpiarFirmaCli')?.addEventListener('click', () => {
    limpiarPad(padFirmaCli);
    padFirmaCli.ctx.strokeStyle = '#111827';
    padFirmaCli.ctx.lineWidth = 2.2;
    actualizarPreviewFirma('');
    // Si borra, ya no cuenta la firma previa del servidor hasta que vuelva a firmar
    formatoInicial.firma_cliente_url = undefined;
    actualizarChecklistRequeridos();
  });

  byId('aceptaCondiciones')?.addEventListener('change', () => {
    actualizarChecklistRequeridos();
  });

  byId('btnAceptarAvisoModal')?.addEventListener('click', () => {
    const cb = byId('aceptaPrivacidad') as HTMLInputElement | null;
    if (cb) {
      cb.checked = true;
    }
    actualizarChecklistRequeridos();
  });

  byId('aceptaPrivacidad')?.addEventListener('change', () => {
    actualizarChecklistRequeridos();
  });

  actualizarChecklistRequeridos();

  const construirPayload = (incluirFlagsFinal: boolean): FormatoGarantiaPayload => {
    const radio = document.querySelector('input[name="comoEnteraste"]:checked') as HTMLInputElement | null;
    const payload: FormatoGarantiaPayload = {
      tipo_diagrama: valorInput('tipoDiagrama'),
      accesorio_cargador: checked('accCargador'),
      accesorio_teclado: checked('accTeclado'),
      accesorio_pluma: checked('accPluma'),
      accesorio_mouse: checked('accMouse'),
      accesorio_monitor: checked('accMonitor'),
      accesorio_caja: checked('accCaja'),
      accesorio_bateria: checked('accBateria'),
      accesorio_docking: checked('accDocking'),
      accesorio_microsd_sim: checked('accMicrosdSim'),
      accesorio_otros: checked('accOtros'),
      accesorios_otros_detalle: valorInput('accOtrosDetalle'),
      numero_cargador: valorInput('numeroCargador'),
      observaciones_tecnicas: valorInput('observacionesTecnicas'),
      disclaimer_pc_audit: checked('disclaimerPcAudit'),
      acepta_condiciones: checked('aceptaCondiciones'),
      acepta_privacidad: checked('aceptaPrivacidad'),
      email_envio: leerEmailsEnvio()[0] || '',
      emails_envio: leerEmailsEnvio(),
      como_enteraste: radio ? radio.value : '',
      firma_cliente_data: padFirmaCli.tieneTrazos ? canvasFirmaCli.toDataURL('image/png') : '',
      vistas_dano: Array.from(vistasGuardadas.values()),
    };
    if (incluirFlagsFinal) {
      payload.enviar_email = checked('enviarEmail');
      payload.forzar_regenerar = true;
    }
    return payload;
  };

  /**
   * Flujo común: guardar datos + generar PDF (finalizar o regenerar).
   */
  const ejecutarGeneracionPdf = async (opciones: {
    soloRegenerar: boolean;
    mensajeExito: string;
  }): Promise<void> => {
    const actions = byId('formatoGarantiaStatusActions');
    if (actions) {
      actions.hidden = true;
    }
    // EXPLICACIÓN PARA PRINCIPIANTES:
    // Validamos en orden: si falta algo, scroll a esa sección y no generamos PDF.
    if (!checked('aceptaCondiciones')) {
      setStatus('Debes aceptar las condiciones de entrega del equipo.', true, false);
      enfocarSeccion('seccion-firma');
      actualizarChecklistRequeridos();
      return;
    }
    if (!checked('aceptaPrivacidad')) {
      setStatus('Debes aceptar el aviso de privacidad.', true, false);
      enfocarSeccion('seccion-envio');
      actualizarChecklistRequeridos();
      return;
    }
    if (!padFirmaCli.tieneTrazos && !(formatoInicial.firma_cliente_url)) {
      setStatus('La firma del cliente es obligatoria.', true, false);
      enfocarSeccion('seccion-firma');
      actualizarChecklistRequeridos();
      return;
    }

    setBotonesOcupados(true);
    setOverlay(
      true,
      opciones.soloRegenerar ? 'Regenerando PDF…' : 'Generando PDF…',
      'Estamos guardando el formato y creando el documento. Puede tardar unos segundos. No cierres ni bloquees la tablet.',
    );
    setStatus(
      opciones.soloRegenerar
        ? '1/2 Guardando cambios…'
        : '1/2 Guardando datos del formato…',
      false,
      true,
    );

    try {
      await new Promise<void>((resolve) => {
        window.setTimeout(() => resolve(), 50);
      });
      setStatus(
        opciones.soloRegenerar ? '2/2 Regenerando PDF…' : '2/2 Generando PDF del formato…',
        false,
        true,
      );

      const payload = construirPayload(true);
      if (opciones.soloRegenerar) {
        // EXPLICACIÓN PARA PRINCIPIANTES:
        // solo_regenerar = true → el servidor NO encola el correo.
        payload.solo_regenerar = true;
        payload.enviar_email = false;
        payload.forzar_regenerar = true;
      }

      const data = await postJson(urlFinalizar, payload);
      // EXPLICACIÓN PARA PRINCIPIANTES:
      // La URL del PDF es siempre la misma (/.../pdf/). Sin un parámetro que cambie
      // (v=timestamp), el navegador puede mostrar el PDF ANTERIOR en caché aunque
      // el servidor ya regeneró el archivo. Por eso “Regenerar” parecía no actualizar
      // el número del cargador, y “Enviar correo” sí (el adjunto lee el archivo nuevo).
      const pdfUrlBase = String(data.pdf_url || urlPdf);
      const pdfUrl =
        `${pdfUrlBase}?inline=1&v=${Date.now()}`;

      setOverlay(false);
      setStatus(opciones.mensajeExito, false, false);
      if (actions) {
        actions.hidden = false;
      }
      const linkPdf = byId('btnVerPdfGenerado') as HTMLAnchorElement | null;
      if (linkPdf) {
        linkPdf.href = pdfUrl;
      }

      const ventana = window.open(pdfUrl, '_blank');
      if (!ventana) {
        setStatus(
          'PDF listo. El navegador bloqueó la ventana emergente: toca “Ver / descargar PDF”.',
          false,
          false,
        );
      }
    } catch (err) {
      setOverlay(false);
      setStatus(err instanceof Error ? err.message : 'Error al generar el PDF', true, false);
    } finally {
      setBotonesOcupados(false);
    }
  };

  const postJson = async (url: string, body: FormatoGarantiaPayload): Promise<Record<string, unknown>> => {
    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': leerCookieCsrf(),
      },
      credentials: 'same-origin',
      body: JSON.stringify(body),
    });
    const data = (await resp.json()) as Record<string, unknown>;
    if (!resp.ok || !data.success) {
      throw new Error(String(data.error || 'Error en el servidor'));
    }
    return data;
  };

  byId('btnGuardarBorrador')?.addEventListener('click', async () => {
    const actions = byId('formatoGarantiaStatusActions');
    if (actions) {
      actions.hidden = true;
    }
    setBotonesOcupados(true);
    setStatus('Guardando…', false, true);
    try {
      const data = await postJson(urlGuardar, construirPayload(false));
      if (padFirmaCli.tieneTrazos) {
        actualizarPreviewFirma(canvasFirmaCli.toDataURL('image/png'));
      }
      const formatoResp = data.formato as { firma_cliente_url?: string } | undefined;
      if (formatoResp && formatoResp.firma_cliente_url) {
        formatoInicial.firma_cliente_url = formatoResp.firma_cliente_url;
        actualizarPreviewFirma(formatoResp.firma_cliente_url);
      }
      const mensaje = String(data.mensaje || 'Datos guardados.');
      setStatus(mensaje, false, false);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Error al guardar', true, false);
    } finally {
      setBotonesOcupados(false);
    }
  });

  byId('btnFinalizar')?.addEventListener('click', () => {
    void ejecutarGeneracionPdf({
      soloRegenerar: false,
      mensajeExito:
        '¡Listo! Formato finalizado y PDF generado. Si no se abrió solo, usa el botón de abajo.',
    });
  });

  // Botón solo visible cuando el formato ya está finalizado
  byId('btnRegenerarPdf')?.addEventListener('click', () => {
    void ejecutarGeneracionPdf({
      soloRegenerar: true,
      mensajeExito:
        'PDF regenerado (sin reenviar correo). Si no se abrió solo, usa el botón de abajo.',
    });
  });

  /**
   * Reenvía el PDF actual por correo (no regenera el documento).
   * Usa los emails del formulario (hasta 3).
   */
  byId('btnReenviarEmail')?.addEventListener('click', async () => {
    const emails = leerEmailsEnvio();
    if (emails.length === 0) {
      setStatus(
        'Captura al menos un correo en “Email(s) para recibir el formato”.',
        true,
        false,
      );
      return;
    }
    const confirmar = window.confirm(
      `¿Reenviar el PDF del formato a?\n\n${emails.join('\n')}\n\n`
      + 'Esto no regenera el PDF; usa el documento actual.',
    );
    if (!confirmar) {
      return;
    }

    const actions = byId('formatoGarantiaStatusActions');
    if (actions) {
      actions.hidden = true;
    }
    setBotonesOcupados(true);
    setStatus('Encolando reenvío por correo…', false, true);
    try {
      // Solo mandamos los emails; el servidor actualiza destinatarios y encola Celery
      const data = await postJson(urlReenviar, {
        ...construirPayload(false),
        emails_envio: emails,
        email_envio: emails[0] || '',
      });
      setStatus(String(data.mensaje || 'Correo encolado.'), false, false);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Error al reenviar', true, false);
    } finally {
      setBotonesOcupados(false);
    }
  });

  /**
   * Crea la miniatura de una evidencia con botón eliminar.
   *
   * EXPLICACIÓN PARA PRINCIPIANTES:
   * Al subir o al cargar la página, cada foto lleva un botón rojo (X).
   * Al hacer clic pedimos confirmación y llamamos al endpoint de borrado.
   */
  const crearItemEvidencia = (opts: {
    id: number;
    url: string;
    etiqueta: string;
  }): HTMLDivElement => {
    const wrap = document.createElement('div');
    wrap.className = 'formato-oow-evidencia-item';
    wrap.dataset.imagenId = String(opts.id);

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'formato-oow-evidencia-eliminar';
    btn.title = 'Eliminar esta foto';
    btn.setAttribute('aria-label', 'Eliminar foto de escaneo');
    btn.innerHTML = '<i class="bi bi-x-lg" aria-hidden="true"></i>';

    const enlace = document.createElement('a');
    enlace.href = opts.url;
    enlace.target = '_blank';
    enlace.rel = 'noopener';
    enlace.className = 'formato-oow-thumb';
    enlace.innerHTML = `<img src="${opts.url}" alt="${opts.etiqueta}"><span>${opts.etiqueta}</span>`;

    wrap.appendChild(btn);
    wrap.appendChild(enlace);
    return wrap;
  };

  const urlParaEliminarEvidencia = (imagenId: number): string => {
    if (!urlEliminarEvidenciaTpl) {
      return '';
    }
    return urlEliminarEvidenciaTpl.replace('999999999', String(imagenId));
  };

  const mostrarListaVaciaSiHaceFalta = (): void => {
    const lista = byId('listaEvidencias');
    if (!lista) {
      return;
    }
    if (lista.querySelectorAll('.formato-oow-evidencia-item').length > 0) {
      return;
    }
    if (byId('evidenciasVacias')) {
      return;
    }
    const p = document.createElement('p');
    p.className = 'text-muted small mb-0';
    p.id = 'evidenciasVacias';
    p.textContent = 'Sin evidencias aún.';
    lista.appendChild(p);
  };

  const eliminarEvidencia = async (item: HTMLElement): Promise<void> => {
    const rawId = item.dataset.imagenId || '';
    const imagenId = Number.parseInt(rawId, 10);
    if (!Number.isFinite(imagenId) || imagenId <= 0) {
      setStatus('No se pudo identificar la foto a eliminar.', true, false);
      return;
    }
    const url = urlParaEliminarEvidencia(imagenId);
    if (!url) {
      setStatus('URL de eliminación no configurada.', true, false);
      return;
    }
    // Confirmación para evitar borrados accidentales en iPad
    if (!window.confirm('¿Eliminar esta foto de escaneo? Esta acción no se puede deshacer.')) {
      return;
    }

    setStatus('Eliminando foto…', false, true);
    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'X-CSRFToken': leerCookieCsrf() },
        credentials: 'same-origin',
      });
      const data = (await resp.json()) as { success?: boolean; error?: string; mensaje?: string };
      if (!resp.ok || !data.success) {
        throw new Error(data.error || 'No se pudo eliminar la foto');
      }
      item.remove();
      mostrarListaVaciaSiHaceFalta();
      setStatus(data.mensaje || 'Foto eliminada.', false, false);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Error al eliminar foto', true, false);
    }
  };

  // Delegación: un solo listener para botones ya existentes y los nuevos al subir
  byId('listaEvidencias')?.addEventListener('click', (ev: Event) => {
    const target = ev.target as HTMLElement | null;
    const btn = target?.closest('.formato-oow-evidencia-eliminar') as HTMLElement | null;
    if (!btn) {
      return;
    }
    ev.preventDefault();
    ev.stopPropagation();
    const item = btn.closest('.formato-oow-evidencia-item') as HTMLElement | null;
    if (item) {
      void eliminarEvidencia(item);
    }
  });

  const subirEvidencia = async (input: HTMLInputElement, tipo: string): Promise<void> => {
    const file = input.files && input.files[0];
    if (!file) {
      return;
    }
    const fd = new FormData();
    fd.append('tipo', tipo);
    fd.append('imagen', file);
    fd.append('descripcion', 'Escaneo PC Audit Garantía');
    setStatus('Subiendo foto…', false, true);
    try {
      const resp = await fetch(urlEvidencia, {
        method: 'POST',
        headers: { 'X-CSRFToken': leerCookieCsrf() },
        credentials: 'same-origin',
        body: fd,
      });
      const data = (await resp.json()) as {
        success?: boolean;
        error?: string;
        imagen?: { id: number; url: string; tipo: string };
      };
      if (!resp.ok || !data.success || !data.imagen || !data.imagen.url) {
        throw new Error(data.error || 'No se pudo subir la imagen');
      }
      const lista = byId('listaEvidencias');
      const vacias = byId('evidenciasVacias');
      if (vacias) {
        vacias.remove();
      }
      if (lista && data.imagen.id) {
        const item = crearItemEvidencia({
          id: data.imagen.id,
          url: data.imagen.url,
          etiqueta: 'Resultado de escaneo — Formato Garantía Dell',
        });
        lista.prepend(item);
      }
      setStatus('Foto guardada.', false, false);
      input.value = '';
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Error al subir foto', true, false);
    }
  };

  // EXPLICACIÓN PARA PRINCIPIANTES:
  // En Garantía Dell NO pedimos INE; solo resultado de PC Audit.
  byId('fotoEscaneo')?.addEventListener('change', (ev: Event) => {
    const t = ev.target as HTMLInputElement;
    void subirEvidencia(t, 'escaneo_garantia');
  });

  // EXPLICACIÓN PARA PRINCIPIANTES:
  // Botón de cámara junto a "Número del cargador": reutiliza scanner_codigo.ts
  // (misma idea que inventario). Al detectar, solo llena el textbox — sin AJAX.
  const btnEscanearCargador = byId('btnEscanearCargador');
  const inputNumeroCargador = byId('numeroCargador') as HTMLInputElement | null;
  btnEscanearCargador?.addEventListener('click', () => {
    if (!inputNumeroCargador) {
      setStatus('No se encontró el campo del número de cargador.', true, false);
      return;
    }
    if (typeof window.abrirScannerCodigo !== 'function') {
      setStatus(
        'El scanner no está disponible. Recarga la página o escribe el número a mano.',
        true,
        false,
      );
      return;
    }
    window.abrirScannerCodigo({
      targetInput: inputNumeroCargador,
      tituloModal: 'Escanear número del cargador',
      onDetect: () => {
        setStatus('Número del cargador capturado con el scanner.', false, false);
      },
    });
  });
}

document.addEventListener('DOMContentLoaded', () => {
  inicializarFormatoGarantia();
});

})();
