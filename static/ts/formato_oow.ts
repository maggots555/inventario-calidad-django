/**
 * Formato Digital OOW — wizard iPad (firmas, daños, guardar/finalizar).
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Este archivo se edita en static/ts/ y se compila a static/js/ con pnpm run build.
 * No edites el .js generado.
 */

interface VistaDanoGuardada {
  clave_vista: string;
  etiqueta_dano: string;
  imagen_data?: string;
  imagen_url?: string;
}

interface FormatoOowPayload {
  tipo_diagrama: string;
  accesorio_cargador: boolean;
  accesorio_maletin: boolean;
  accesorio_mouse: boolean;
  accesorio_teclado: boolean;
  accesorio_monitor: boolean;
  accesorio_otros: boolean;
  accesorios_otros_detalle: string;
  contrasena_equipo: string;
  observaciones_tecnicas: string;
  disclaimer_pc_audit: boolean;
  acepta_condiciones: boolean;
  acepta_privacidad: boolean;
  email_envio: string;
  como_enteraste: string;
  firma_cliente_data: string;
  vistas_dano: VistaDanoGuardada[];
  enviar_email?: boolean;
  forzar_regenerar?: boolean;
}

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
  const box = byId('formatoOowStatusBox');
  const el = byId('formatoOowStatus');
  const spinner = byId('formatoOowSpinner');
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
  const overlay = byId('formatoOowOverlay');
  if (!overlay) {
    return;
  }
  overlay.hidden = !visible;
  overlay.setAttribute('aria-hidden', visible ? 'false' : 'true');
  const t = byId('formatoOowOverlayTitulo');
  const d = byId('formatoOowOverlayTexto');
  if (t && titulo) {
    t.textContent = titulo;
  }
  if (d && texto) {
    d.textContent = texto;
  }
}

function setBotonesOcupados(ocupado: boolean): void {
  const ids = ['btnGuardarBorrador', 'btnFinalizar'];
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

function dibujarMarcoDiagrama(ctx: CanvasRenderingContext2D, w: number, h: number, etiqueta: string): void {
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = '#334155';
  ctx.lineWidth = 3;
  const m = 24;
  ctx.strokeRect(m, m, w - m * 2, h - m * 2);
  // Líneas guía internas según vista (esquema simple)
  ctx.strokeStyle = '#94a3b8';
  ctx.lineWidth = 1.5;
  if (etiqueta.includes('pantalla') || etiqueta.includes('frente')) {
    ctx.strokeRect(m + 20, m + 20, w - m * 2 - 40, h - m * 2 - 40);
  } else if (etiqueta.includes('palm')) {
    ctx.strokeRect(m + 30, m + 40, w - m * 2 - 60, 80);
    ctx.strokeRect(w / 2 - 40, h - m - 70, 80, 40);
  } else if (etiqueta.includes('bottom') || etiqueta.includes('trasera')) {
    ctx.beginPath();
    ctx.arc(m + 50, m + 50, 18, 0, Math.PI * 2);
    ctx.arc(w - m - 50, m + 50, 18, 0, Math.PI * 2);
    ctx.arc(m + 50, h - m - 50, 18, 0, Math.PI * 2);
    ctx.arc(w - m - 50, h - m - 50, 18, 0, Math.PI * 2);
    ctx.stroke();
  } else if (etiqueta.includes('lat')) {
    for (let i = 0; i < 5; i++) {
      const y = m + 40 + i * 40;
      ctx.strokeRect(m + 30, y, 40, 18);
    }
  }
  ctx.fillStyle = '#003366';
  ctx.font = 'bold 16px Helvetica, Arial, sans-serif';
  ctx.fillText(etiqueta.toUpperCase(), m + 8, m - 6 > 14 ? m - 6 : 18);
}

function inicializarFormatoOow(): void {
  const app = byId('formatoOowApp');
  if (!app) {
    return;
  }

  const urlGuardar = app.dataset.urlGuardar || '';
  const urlFinalizar = app.dataset.urlFinalizar || '';
  const urlPdf = app.dataset.urlPdf || '';
  const urlEvidencia = app.dataset.urlEvidencia || '';

  const dataEl = document.getElementById('formato-oow-data');
  let formatoInicial: { vistas_dano?: VistaDanoGuardada[]; firma_cliente_url?: string } = {};
  if (dataEl && dataEl.textContent) {
    try {
      formatoInicial = JSON.parse(dataEl.textContent) as typeof formatoInicial;
    } catch {
      formatoInicial = {};
    }
  }

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

  const vistasGuardadas: Map<string, VistaDanoGuardada> = new Map();
  (formatoInicial.vistas_dano || []).forEach((v) => {
    vistasGuardadas.set(v.clave_vista, v);
  });

  const refrescarDiagrama = (): void => {
    const vistaSel = byId('vistaActiva') as HTMLSelectElement | null;
    const clave = vistaSel ? vistaSel.value : 'pantalla';
    const label = vistaSel && vistaSel.selectedOptions[0]
      ? vistaSel.selectedOptions[0].text
      : clave;
    dibujarMarcoDiagrama(padDano.ctx, canvasDano.width, canvasDano.height, label);
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
    }
  };

  const filtrarVistasPorTipo = (): void => {
    const tipo = valorInput('tipoDiagrama');
    const sel = byId('vistaActiva') as HTMLSelectElement | null;
    if (!sel) {
      return;
    }
    Array.from(sel.options).forEach((opt) => {
      const grupo = opt.getAttribute('data-grupo') || '';
      opt.hidden = grupo !== tipo;
    });
    const visible = Array.from(sel.options).find((o) => !o.hidden);
    if (visible) {
      sel.value = visible.value;
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

  byId('btnLimpiarFirmaCli')?.addEventListener('click', () => limpiarPad(padFirmaCli));

  byId('btnAceptarAvisoModal')?.addEventListener('click', () => {
    const cb = byId('aceptaPrivacidad') as HTMLInputElement | null;
    if (cb) {
      cb.checked = true;
    }
  });

  const construirPayload = (incluirFlagsFinal: boolean): FormatoOowPayload => {
    const radio = document.querySelector('input[name="comoEnteraste"]:checked') as HTMLInputElement | null;
    const payload: FormatoOowPayload = {
      tipo_diagrama: valorInput('tipoDiagrama'),
      accesorio_cargador: checked('accCargador'),
      accesorio_maletin: checked('accMaletin'),
      accesorio_mouse: checked('accMouse'),
      accesorio_teclado: checked('accTeclado'),
      accesorio_monitor: checked('accMonitor'),
      accesorio_otros: checked('accOtros'),
      accesorios_otros_detalle: valorInput('accOtrosDetalle'),
      contrasena_equipo: valorInput('contrasenaEquipo'),
      observaciones_tecnicas: valorInput('observacionesTecnicas'),
      disclaimer_pc_audit: checked('disclaimerPcAudit'),
      acepta_condiciones: checked('aceptaCondiciones'),
      acepta_privacidad: checked('aceptaPrivacidad'),
      email_envio: valorInput('emailEnvio'),
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

  const postJson = async (url: string, body: FormatoOowPayload): Promise<Record<string, unknown>> => {
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
    const actions = byId('formatoOowStatusActions');
    if (actions) {
      actions.hidden = true;
    }
    setBotonesOcupados(true);
    setStatus('Guardando borrador…', false, true);
    try {
      await postJson(urlGuardar, construirPayload(false));
      setStatus('Borrador guardado correctamente.', false, false);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Error al guardar', true, false);
    } finally {
      setBotonesOcupados(false);
    }
  });

  byId('btnFinalizar')?.addEventListener('click', async () => {
    const actions = byId('formatoOowStatusActions');
    if (actions) {
      actions.hidden = true;
    }
    if (!checked('aceptaCondiciones') || !checked('aceptaPrivacidad')) {
      setStatus('Debes aceptar condiciones y aviso de privacidad.', true, false);
      return;
    }
    if (!padFirmaCli.tieneTrazos && !(formatoInicial.firma_cliente_url)) {
      setStatus('La firma del cliente es obligatoria.', true, false);
      return;
    }

    setBotonesOcupados(true);
    setOverlay(
      true,
      'Generando PDF…',
      'Estamos guardando el formato y creando el documento. Puede tardar unos segundos. No cierres ni bloquees la tablet.',
    );
    setStatus('1/2 Guardando datos del formato…', false, true);

    try {
      // Pequeña pausa para que el overlay se pinte en pantalla (iPad)
      await new Promise<void>((resolve) => {
        window.setTimeout(() => resolve(), 50);
      });
      setStatus('2/2 Generando PDF del formato…', false, true);
      const data = await postJson(urlFinalizar, construirPayload(true));
      const pdfUrl = String(data.pdf_url || urlPdf) + '?inline=1';

      setOverlay(false);
      setStatus(
        '¡Listo! Formato finalizado y PDF generado. Si no se abrió solo, usa el botón de abajo.',
        false,
        false,
      );
      if (actions) {
        actions.hidden = false;
      }
      const linkPdf = byId('btnVerPdfGenerado') as HTMLAnchorElement | null;
      if (linkPdf) {
        linkPdf.href = pdfUrl;
      }

      // En iPad Safari window.open a veces se bloquea tras un await largo
      const ventana = window.open(pdfUrl, '_blank');
      if (!ventana) {
        setStatus(
          'PDF generado. El navegador bloqueó la ventana emergente: toca “Ver / descargar PDF”.',
          false,
          false,
        );
      }
    } catch (err) {
      setOverlay(false);
      setStatus(err instanceof Error ? err.message : 'Error al finalizar', true, false);
    } finally {
      setBotonesOcupados(false);
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
      fd.append('descripcion', tipo === 'escaneo_oow' ? 'Escaneo OOW' : 'Identificación oficial OOW');
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
        imagen?: { url: string; tipo: string };
      };
      if (!resp.ok || !data.success || !data.imagen) {
        throw new Error(data.error || 'No se pudo subir la imagen');
      }
      const lista = byId('listaEvidencias');
      const vacias = byId('evidenciasVacias');
      if (vacias) {
        vacias.remove();
      }
      if (lista) {
        const a = document.createElement('a');
        a.href = data.imagen.url;
        a.target = '_blank';
        a.rel = 'noopener';
        a.className = 'formato-oow-thumb';
        a.innerHTML = `<img src="${data.imagen.url}" alt="${tipo}"><span>${tipo}</span>`;
        lista.prepend(a);
      }
      setStatus('Foto guardada.', false, false);
      input.value = '';
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Error al subir foto', true, false);
    }
  };

  byId('fotoIdentificacion')?.addEventListener('change', (ev: Event) => {
    const t = ev.target as HTMLInputElement;
    void subirEvidencia(t, 'identificacion_oow');
  });
  byId('fotoEscaneo')?.addEventListener('change', (ev: Event) => {
    const t = ev.target as HTMLInputElement;
    void subirEvidencia(t, 'escaneo_oow');
  });
}

document.addEventListener('DOMContentLoaded', () => {
  inicializarFormatoOow();
});
