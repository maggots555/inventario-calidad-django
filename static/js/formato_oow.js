"use strict";
/**
 * Formato Digital OOW — wizard iPad (firmas, daños, guardar/finalizar).
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Este archivo se edita en static/ts/ y se compila a static/js/ con pnpm run build.
 * No edites el .js generado.
 */
function leerCookieCsrf() {
    const cookieNames = ['sigma_csrftoken', 'csrftoken'];
    for (const name of cookieNames) {
        const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
        if (match) {
            return decodeURIComponent(match[1]);
        }
    }
    return '';
}
function byId(id) {
    return document.getElementById(id);
}
function valorInput(id) {
    const el = byId(id);
    return el ? el.value : '';
}
function checked(id) {
    const el = byId(id);
    return Boolean(el && el.checked);
}
function setStatus(mensaje, esError = false) {
    const el = byId('formatoOowStatus');
    if (!el) {
        return;
    }
    el.textContent = mensaje;
    el.classList.toggle('text-danger', esError);
    el.classList.toggle('text-success', !esError && mensaje.length > 0);
}
function crearPad(canvas) {
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
    const pad = {
        canvas,
        ctx,
        dibujando: false,
        tieneTrazos: false,
    };
    const pos = (ev) => {
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        return {
            x: (ev.clientX - rect.left) * scaleX,
            y: (ev.clientY - rect.top) * scaleY,
        };
    };
    canvas.style.touchAction = 'none';
    canvas.addEventListener('pointerdown', (ev) => {
        pad.dibujando = true;
        canvas.setPointerCapture(ev.pointerId);
        const p = pos(ev);
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
    });
    canvas.addEventListener('pointermove', (ev) => {
        if (!pad.dibujando) {
            return;
        }
        const p = pos(ev);
        ctx.lineTo(p.x, p.y);
        ctx.stroke();
        pad.tieneTrazos = true;
    });
    const fin = (ev) => {
        if (!pad.dibujando) {
            return;
        }
        pad.dibujando = false;
        try {
            canvas.releasePointerCapture(ev.pointerId);
        }
        catch {
            // ignore
        }
    };
    canvas.addEventListener('pointerup', fin);
    canvas.addEventListener('pointercancel', fin);
    return pad;
}
function limpiarPad(pad) {
    pad.ctx.fillStyle = '#ffffff';
    pad.ctx.fillRect(0, 0, pad.canvas.width, pad.canvas.height);
    pad.ctx.strokeStyle = '#003366';
    pad.ctx.lineWidth = 2.5;
    pad.tieneTrazos = false;
}
function dibujarMarcoDiagrama(ctx, w, h, etiqueta) {
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
    }
    else if (etiqueta.includes('palm')) {
        ctx.strokeRect(m + 30, m + 40, w - m * 2 - 60, 80);
        ctx.strokeRect(w / 2 - 40, h - m - 70, 80, 40);
    }
    else if (etiqueta.includes('bottom') || etiqueta.includes('trasera')) {
        ctx.beginPath();
        ctx.arc(m + 50, m + 50, 18, 0, Math.PI * 2);
        ctx.arc(w - m - 50, m + 50, 18, 0, Math.PI * 2);
        ctx.arc(m + 50, h - m - 50, 18, 0, Math.PI * 2);
        ctx.arc(w - m - 50, h - m - 50, 18, 0, Math.PI * 2);
        ctx.stroke();
    }
    else if (etiqueta.includes('lat')) {
        for (let i = 0; i < 5; i++) {
            const y = m + 40 + i * 40;
            ctx.strokeRect(m + 30, y, 40, 18);
        }
    }
    ctx.fillStyle = '#003366';
    ctx.font = 'bold 16px Helvetica, Arial, sans-serif';
    ctx.fillText(etiqueta.toUpperCase(), m + 8, m - 6 > 14 ? m - 6 : 18);
}
function inicializarFormatoOow() {
    var _a, _b, _c, _d, _e, _f, _g, _h, _j, _k;
    const app = byId('formatoOowApp');
    if (!app) {
        return;
    }
    const urlGuardar = app.dataset.urlGuardar || '';
    const urlFinalizar = app.dataset.urlFinalizar || '';
    const urlPdf = app.dataset.urlPdf || '';
    const urlEvidencia = app.dataset.urlEvidencia || '';
    const dataEl = document.getElementById('formato-oow-data');
    let formatoInicial = {};
    if (dataEl && dataEl.textContent) {
        try {
            formatoInicial = JSON.parse(dataEl.textContent);
        }
        catch {
            formatoInicial = {};
        }
    }
    const canvasDano = byId('canvasDano');
    const canvasFirmaCli = byId('canvasFirmaCliente');
    if (!canvasDano || !canvasFirmaCli) {
        return;
    }
    const padDano = crearPad(canvasDano);
    const padFirmaCli = crearPad(canvasFirmaCli);
    // Firma cliente: trazo negro un poco más grueso
    padFirmaCli.ctx.strokeStyle = '#111827';
    padFirmaCli.ctx.lineWidth = 2.2;
    const vistasGuardadas = new Map();
    (formatoInicial.vistas_dano || []).forEach((v) => {
        vistasGuardadas.set(v.clave_vista, v);
    });
    const refrescarDiagrama = () => {
        const vistaSel = byId('vistaActiva');
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
            img.onload = () => {
                padDano.ctx.drawImage(img, 0, 0, canvasDano.width, canvasDano.height);
                padDano.ctx.strokeStyle = '#c00000';
                padDano.ctx.lineWidth = 3;
            };
            img.src = previa.imagen_url;
        }
    };
    const filtrarVistasPorTipo = () => {
        const tipo = valorInput('tipoDiagrama');
        const sel = byId('vistaActiva');
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
    const renderThumbsVistas = () => {
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
    (_a = byId('tipoDiagrama')) === null || _a === void 0 ? void 0 : _a.addEventListener('change', filtrarVistasPorTipo);
    (_b = byId('vistaActiva')) === null || _b === void 0 ? void 0 : _b.addEventListener('change', refrescarDiagrama);
    (_c = byId('btnLimpiarVista')) === null || _c === void 0 ? void 0 : _c.addEventListener('click', () => {
        refrescarDiagrama();
    });
    (_d = byId('btnGuardarVista')) === null || _d === void 0 ? void 0 : _d.addEventListener('click', () => {
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
    (_e = byId('btnLimpiarFirmaCli')) === null || _e === void 0 ? void 0 : _e.addEventListener('click', () => limpiarPad(padFirmaCli));
    (_f = byId('btnAceptarAvisoModal')) === null || _f === void 0 ? void 0 : _f.addEventListener('click', () => {
        const cb = byId('aceptaPrivacidad');
        if (cb) {
            cb.checked = true;
        }
    });
    const construirPayload = (incluirFlagsFinal) => {
        const radio = document.querySelector('input[name="comoEnteraste"]:checked');
        const payload = {
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
    const postJson = async (url, body) => {
        const resp = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': leerCookieCsrf(),
            },
            credentials: 'same-origin',
            body: JSON.stringify(body),
        });
        const data = (await resp.json());
        if (!resp.ok || !data.success) {
            throw new Error(String(data.error || 'Error en el servidor'));
        }
        return data;
    };
    (_g = byId('btnGuardarBorrador')) === null || _g === void 0 ? void 0 : _g.addEventListener('click', async () => {
        setStatus('Guardando borrador…');
        try {
            await postJson(urlGuardar, construirPayload(false));
            setStatus('Borrador guardado correctamente.');
        }
        catch (err) {
            setStatus(err instanceof Error ? err.message : 'Error al guardar', true);
        }
    });
    (_h = byId('btnFinalizar')) === null || _h === void 0 ? void 0 : _h.addEventListener('click', async () => {
        if (!checked('aceptaCondiciones') || !checked('aceptaPrivacidad')) {
            setStatus('Debes aceptar condiciones y aviso de privacidad.', true);
            return;
        }
        if (!padFirmaCli.tieneTrazos && !(formatoInicial.firma_cliente_url)) {
            setStatus('La firma del cliente es obligatoria.', true);
            return;
        }
        setStatus('Finalizando y generando PDF…');
        try {
            const data = await postJson(urlFinalizar, construirPayload(true));
            setStatus('Formato finalizado. Abriendo PDF…');
            const pdfUrl = String(data.pdf_url || urlPdf);
            window.open(pdfUrl + '?inline=1', '_blank');
        }
        catch (err) {
            setStatus(err instanceof Error ? err.message : 'Error al finalizar', true);
        }
    });
    const subirEvidencia = async (input, tipo) => {
        const file = input.files && input.files[0];
        if (!file) {
            return;
        }
        const fd = new FormData();
        fd.append('tipo', tipo);
        fd.append('imagen', file);
        fd.append('descripcion', tipo === 'escaneo_oow' ? 'Escaneo OOW' : 'Identificación oficial OOW');
        setStatus('Subiendo foto…');
        try {
            const resp = await fetch(urlEvidencia, {
                method: 'POST',
                headers: { 'X-CSRFToken': leerCookieCsrf() },
                credentials: 'same-origin',
                body: fd,
            });
            const data = (await resp.json());
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
            setStatus('Foto guardada.');
            input.value = '';
        }
        catch (err) {
            setStatus(err instanceof Error ? err.message : 'Error al subir foto', true);
        }
    };
    (_j = byId('fotoIdentificacion')) === null || _j === void 0 ? void 0 : _j.addEventListener('change', (ev) => {
        const t = ev.target;
        void subirEvidencia(t, 'identificacion_oow');
    });
    (_k = byId('fotoEscaneo')) === null || _k === void 0 ? void 0 : _k.addEventListener('change', (ev) => {
        const t = ev.target;
        void subirEvidencia(t, 'escaneo_oow');
    });
}
document.addEventListener('DOMContentLoaded', () => {
    inicializarFormatoOow();
});
//# sourceMappingURL=formato_oow.js.map