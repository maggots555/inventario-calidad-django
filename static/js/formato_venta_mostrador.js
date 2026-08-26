"use strict";
/**
 * Formato Digital Venta Mostrador — wizard iPad (firmas, daños opcionales, PDF).
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Este archivo se edita en static/ts/ y se compila a static/js/ con pnpm run build.
 * No edites el .js generado.
 *
 * Diferencia vs OOW: NO hay requisitos. Generar PDF siempre está permitido.
 */
const MAX_EMAILS_ENVIO_VM = 3;
(function formatoVentaMostradorApp() {
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
    function setStatus(mensaje, esError = false, cargando = false) {
        const box = byId('formatoVmStatusBox');
        const el = byId('formatoVmStatus');
        const spinner = byId('formatoVmSpinner');
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
    function setOverlay(visible, titulo, texto) {
        const overlay = byId('formatoVmOverlay');
        if (!overlay) {
            return;
        }
        overlay.hidden = !visible;
        overlay.setAttribute('aria-hidden', visible ? 'false' : 'true');
        const t = byId('formatoVmOverlayTitulo');
        const d = byId('formatoVmOverlayTexto');
        if (t && titulo) {
            t.textContent = titulo;
        }
        if (d && texto) {
            d.textContent = texto;
        }
    }
    function setBotonesOcupados(ocupado) {
        const ids = ['btnGuardarBorrador', 'btnFinalizar', 'btnRegenerarPdf', 'btnReenviarEmail'];
        ids.forEach((id) => {
            const btn = byId(id);
            if (btn) {
                btn.disabled = ocupado;
            }
        });
    }
    function crearPad(canvas) {
        const ctx = canvas.getContext('2d');
        if (!ctx) {
            throw new Error('No se pudo inicializar el canvas');
        }
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
        canvas.style.userSelect = 'none';
        canvas.setAttribute('draggable', 'false');
        const bloquearGesto = (ev) => {
            ev.preventDefault();
        };
        canvas.addEventListener('contextmenu', bloquearGesto);
        canvas.addEventListener('touchstart', bloquearGesto, { passive: false });
        canvas.addEventListener('touchmove', bloquearGesto, { passive: false });
        canvas.addEventListener('pointerdown', (ev) => {
            ev.preventDefault();
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
            ev.preventDefault();
            const p = pos(ev);
            ctx.lineTo(p.x, p.y);
            ctx.stroke();
            pad.tieneTrazos = true;
        });
        const fin = (ev) => {
            if (!pad.dibujando) {
                return;
            }
            ev.preventDefault();
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
        canvas.addEventListener('pointerleave', (ev) => {
            if (pad.dibujando) {
                fin(ev);
            }
        });
        return pad;
    }
    function limpiarPad(pad, stroke = '#003366') {
        pad.ctx.fillStyle = '#ffffff';
        pad.ctx.fillRect(0, 0, pad.canvas.width, pad.canvas.height);
        pad.ctx.strokeStyle = stroke;
        pad.ctx.lineWidth = 2.5;
        pad.tieneTrazos = false;
    }
    /**
     * Dibuja un esquema simple de la cara del equipo (igual idea que OOW,
     * sin puertos detallados: basta para marcar rayones).
     */
    function dibujarMarcoDiagrama(ctx, w, h, etiqueta, claveVista = '') {
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, w, h);
        const m = 24;
        const etiquetaNorm = etiqueta.toLowerCase();
        const clave = (claveVista || '').toLowerCase();
        ctx.fillStyle = '#003366';
        ctx.font = 'bold 15px Helvetica, Arial, sans-serif';
        ctx.fillText(etiqueta.toUpperCase(), m, 18);
        ctx.strokeStyle = '#334155';
        ctx.lineWidth = 2;
        // Laterales: perfil horizontal simple
        if (clave.includes('lat_') || clave.includes('lateral')) {
            const chasisY = h * 0.38;
            const chasisAlto = Math.max(42, h * 0.18);
            ctx.strokeRect(m + 28, chasisY, w - m * 2 - 56, chasisAlto);
            ctx.fillStyle = '#64748b';
            ctx.font = '11px Helvetica, Arial, sans-serif';
            ctx.fillText('Perfil / puertos — marca daños aquí', m + 28, chasisY + chasisAlto + 18);
            return;
        }
        ctx.lineWidth = 3;
        ctx.strokeRect(m, m + 8, w - m * 2, h - m * 2 - 8);
        ctx.strokeStyle = '#94a3b8';
        ctx.lineWidth = 1.5;
        if (etiquetaNorm.includes('pantalla') || etiquetaNorm.includes('frente')) {
            ctx.strokeRect(m + 20, m + 28, w - m * 2 - 40, h - m * 2 - 58);
            ctx.beginPath();
            ctx.arc(w / 2, m + 40, 4, 0, Math.PI * 2);
            ctx.fillStyle = '#94a3b8';
            ctx.fill();
        }
        else if (etiquetaNorm.includes('top')) {
            ctx.strokeRect(m + 30, m + 40, w - m * 2 - 60, h - m * 2 - 70);
            ctx.beginPath();
            ctx.arc(w / 2, h / 2, 22, 0, Math.PI * 2);
            ctx.stroke();
        }
        else if (etiquetaNorm.includes('palm') || etiquetaNorm.includes('teclado')) {
            ctx.strokeRect(m + 30, m + 40, w - m * 2 - 60, h * 0.38);
            for (let fila = 0; fila < 4; fila++) {
                const y = m + 55 + fila * 22;
                for (let col = 0; col < 10; col++) {
                    const x = m + 45 + col * ((w - m * 2 - 100) / 10);
                    ctx.strokeRect(x, y, 14, 14);
                }
            }
            ctx.strokeRect(w / 2 - 50, h - m - 85, 100, 55);
        }
        else if (etiquetaNorm.includes('bottom') || etiquetaNorm.includes('trasera')) {
            ctx.beginPath();
            ctx.arc(m + 50, m + 55, 16, 0, Math.PI * 2);
            ctx.arc(w - m - 50, m + 55, 16, 0, Math.PI * 2);
            ctx.arc(m + 50, h - m - 45, 16, 0, Math.PI * 2);
            ctx.arc(w - m - 50, h - m - 45, 16, 0, Math.PI * 2);
            ctx.stroke();
        }
        else if (etiquetaNorm.includes('base') || etiquetaNorm.includes('soporte')) {
            ctx.strokeRect(m + 80, m + 50, w - m * 2 - 160, 28);
            ctx.strokeRect(w / 2 - 55, m + 90, 110, h - m * 2 - 110);
        }
    }
    function leerJsonScript(id) {
        const el = document.getElementById(id);
        if (!el || !el.textContent) {
            return null;
        }
        try {
            return JSON.parse(el.textContent);
        }
        catch {
            return null;
        }
    }
    async function postJson(url, payload) {
        var _a, _b;
        const resp = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': (_b = (_a = window.getCsrfToken) === null || _a === void 0 ? void 0 : _a.call(window)) !== null && _b !== void 0 ? _b : '',
            },
            body: JSON.stringify(payload),
        });
        const data = (await resp.json());
        if (!resp.ok || data.success === false) {
            throw new Error(String(data.error || 'Error en el servidor'));
        }
        return data;
    }
    function inicializarFormatoVm() {
        var _a, _b, _c, _d, _e, _f, _g, _h, _j, _k, _l;
        const app = byId('formatoVmApp');
        if (!app) {
            return;
        }
        const urlGuardar = app.getAttribute('data-url-guardar') || '';
        const urlFinalizar = app.getAttribute('data-url-finalizar') || '';
        const urlReenviar = app.getAttribute('data-url-reenviar') || '';
        const urlPdf = app.getAttribute('data-url-pdf') || '';
        const formatoInicial = leerJsonScript('formato-vm-data') || {};
        const ordenInicial = leerJsonScript('orden-vm-data') || {};
        // Tabla de conceptos (solo lectura)
        const tbody = byId('tablaConceptosVm');
        if (tbody) {
            const lineas = ordenInicial.conceptos || [];
            if (lineas.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" class="text-muted">Sin conceptos en venta mostrador todavía.</td></tr>';
            }
            else {
                tbody.innerHTML = lineas.map((linea) => (`<tr>
          <td>${linea.cantidad}</td>
          <td>${linea.descripcion}</td>
          <td class="text-end">$${linea.precio_unitario}</td>
          <td class="text-end">$${linea.importe}</td>
        </tr>`)).join('');
                const aplicaIva = Boolean(ordenInicial.aplica_iva);
                tbody.innerHTML += `
        <tr><td colspan="3" class="text-end fw-semibold">SUBTOTAL</td><td class="text-end">$${ordenInicial.subtotal || '0.00'}</td></tr>
        ${aplicaIva ? `<tr><td colspan="3" class="text-end fw-semibold">IVA 16%</td><td class="text-end">$${ordenInicial.iva || '0.00'}</td></tr>` : ''}
        <tr><td colspan="3" class="text-end fw-bold">TOTAL</td><td class="text-end fw-bold">$${ordenInicial.total || '0.00'}</td></tr>
      `;
            }
        }
        // Emails (hasta 3)
        const listaEmails = byId('emailsEnvioLista');
        const emailsIniciales = (formatoInicial.emails_envio || []).filter((e) => e);
        const renderEmails = (valores) => {
            if (!listaEmails) {
                return;
            }
            listaEmails.innerHTML = '';
            const n = Math.max(1, Math.min(MAX_EMAILS_ENVIO_VM, valores.length || 1));
            for (let i = 0; i < n; i++) {
                const wrap = document.createElement('div');
                wrap.className = 'input-group mb-2';
                wrap.innerHTML = `
        <input type="email" class="form-control email-envio-vm" placeholder="correo@cliente.com"
               value="${valores[i] || ''}" autocomplete="email">
      `;
                listaEmails.appendChild(wrap);
            }
        };
        renderEmails(emailsIniciales.length ? emailsIniciales : ['']);
        (_a = byId('btnAgregarEmail')) === null || _a === void 0 ? void 0 : _a.addEventListener('click', () => {
            const actuales = Array.from(document.querySelectorAll('.email-envio-vm'))
                .map((el) => el.value);
            if (actuales.length >= MAX_EMAILS_ENVIO_VM) {
                setStatus('Máximo 3 correos.', true);
                return;
            }
            actuales.push('');
            renderEmails(actuales);
        });
        const leerEmailsEnvio = () => {
            return Array.from(document.querySelectorAll('.email-envio-vm'))
                .map((el) => el.value.trim())
                .filter((v) => v.length > 0)
                .slice(0, MAX_EMAILS_ENVIO_VM);
        };
        const canvasDano = byId('canvasDano');
        const canvasFirmaCis = byId('canvasFirmaCis');
        const canvasFirmaCli = byId('canvasFirmaCliente');
        if (!canvasDano || !canvasFirmaCis || !canvasFirmaCli) {
            return;
        }
        const padDano = crearPad(canvasDano);
        const padFirmaCis = crearPad(canvasFirmaCis);
        const padFirmaCli = crearPad(canvasFirmaCli);
        padFirmaCis.ctx.strokeStyle = '#111827';
        padFirmaCli.ctx.strokeStyle = '#111827';
        const vistasGuardadas = new Map();
        (formatoInicial.vistas_dano || []).forEach((v) => {
            vistasGuardadas.set(v.clave_vista, v);
        });
        const catalogoVistas = (() => {
            const selInit = byId('vistaActiva');
            if (!selInit) {
                return [];
            }
            return Array.from(selInit.options).map((opt) => ({
                value: opt.value,
                label: opt.textContent || opt.value,
                grupo: opt.getAttribute('data-grupo') || '',
            }));
        })();
        const clavesDelTipoActual = () => {
            const tipo = valorInput('tipoDiagrama') || 'laptop';
            return new Set(catalogoVistas.filter((v) => v.grupo === tipo).map((v) => v.value));
        };
        const limpiarVistasDeOtroTipo = () => {
            const permitidas = clavesDelTipoActual();
            Array.from(vistasGuardadas.keys()).forEach((clave) => {
                if (!permitidas.has(clave)) {
                    vistasGuardadas.delete(clave);
                }
            });
        };
        const pintarMiniaturas = () => {
            const wrap = byId('vistasGuardadas');
            if (!wrap) {
                return;
            }
            wrap.innerHTML = '';
            vistasGuardadas.forEach((vista) => {
                const src = vista.imagen_data || vista.imagen_url || '';
                if (!src) {
                    return;
                }
                const item = document.createElement('div');
                item.className = 'formato-oow-vista-thumb';
                item.innerHTML = `<img src="${src}" alt="${vista.clave_vista}"><span>${vista.clave_vista}</span>`;
                wrap.appendChild(item);
            });
        };
        const filtrarVistasPorTipo = () => {
            const sel = byId('vistaActiva');
            if (!sel) {
                return;
            }
            const tipo = valorInput('tipoDiagrama') || 'laptop';
            const actuales = catalogoVistas.filter((v) => v.grupo === tipo);
            sel.innerHTML = '';
            actuales.forEach((v) => {
                const opt = document.createElement('option');
                opt.value = v.value;
                opt.textContent = v.label;
                opt.setAttribute('data-grupo', v.grupo);
                sel.appendChild(opt);
            });
            limpiarVistasDeOtroTipo();
            refrescarDiagrama();
            pintarMiniaturas();
        };
        const refrescarDiagrama = () => {
            const vistaSel = byId('vistaActiva');
            const clave = vistaSel ? vistaSel.value : 'pantalla';
            const label = vistaSel && vistaSel.selectedOptions[0]
                ? vistaSel.selectedOptions[0].text
                : clave;
            dibujarMarcoDiagrama(padDano.ctx, canvasDano.width, canvasDano.height, label, clave);
            padDano.ctx.strokeStyle = '#c00000';
            padDano.ctx.lineWidth = 3;
            padDano.tieneTrazos = false;
            const previa = vistasGuardadas.get(clave);
            const src = (previa === null || previa === void 0 ? void 0 : previa.imagen_data) || (previa === null || previa === void 0 ? void 0 : previa.imagen_url) || '';
            if (src) {
                const img = new Image();
                img.onload = () => {
                    padDano.ctx.drawImage(img, 0, 0, canvasDano.width, canvasDano.height);
                    padDano.ctx.strokeStyle = '#c00000';
                    padDano.ctx.lineWidth = 3;
                };
                img.src = src;
            }
        };
        (_b = byId('tipoDiagrama')) === null || _b === void 0 ? void 0 : _b.addEventListener('change', filtrarVistasPorTipo);
        (_c = byId('vistaActiva')) === null || _c === void 0 ? void 0 : _c.addEventListener('change', refrescarDiagrama);
        (_d = byId('btnLimpiarVista')) === null || _d === void 0 ? void 0 : _d.addEventListener('click', () => {
            refrescarDiagrama();
        });
        (_e = byId('btnGuardarVista')) === null || _e === void 0 ? void 0 : _e.addEventListener('click', () => {
            const clave = valorInput('vistaActiva');
            if (!clave) {
                return;
            }
            vistasGuardadas.set(clave, {
                clave_vista: clave,
                etiqueta_dano: valorInput('etiquetaDano'),
                imagen_data: canvasDano.toDataURL('image/png'),
            });
            pintarMiniaturas();
            setStatus('Vista guardada (opcional).', false);
        });
        const cargarFirma = (pad, canvas, url, previewId, wrapId) => {
            if (!url) {
                return;
            }
            const img = new Image();
            img.onload = () => {
                pad.ctx.fillStyle = '#ffffff';
                pad.ctx.fillRect(0, 0, canvas.width, canvas.height);
                const scale = Math.min(canvas.width / img.width, canvas.height / img.height);
                const w = img.width * scale;
                const h = img.height * scale;
                pad.ctx.drawImage(img, (canvas.width - w) / 2, (canvas.height - h) / 2, w, h);
                pad.ctx.strokeStyle = '#111827';
                pad.tieneTrazos = true;
                const preview = byId(previewId);
                const wrap = byId(wrapId);
                if (preview) {
                    preview.src = url;
                }
                if (wrap) {
                    wrap.hidden = false;
                }
            };
            img.src = url;
        };
        cargarFirma(padFirmaCis, canvasFirmaCis, formatoInicial.firma_entrega_cis_url || '', 'firmaCisPreviewImg', 'firmaCisPreviewWrap');
        cargarFirma(padFirmaCli, canvasFirmaCli, formatoInicial.firma_entrega_cliente_url || '', 'firmaClientePreviewImg', 'firmaClientePreviewWrap');
        (_f = byId('btnLimpiarFirmaCis')) === null || _f === void 0 ? void 0 : _f.addEventListener('click', () => {
            limpiarPad(padFirmaCis, '#111827');
        });
        (_g = byId('btnLimpiarFirmaCli')) === null || _g === void 0 ? void 0 : _g.addEventListener('click', () => {
            limpiarPad(padFirmaCli, '#111827');
        });
        filtrarVistasPorTipo();
        const construirPayload = (incluirFlagsFinal) => {
            const payload = {
                tipo_diagrama: valorInput('tipoDiagrama'),
                empresa_cliente: valorInput('empresaCliente'),
                persona_contacto: valorInput('personaContacto'),
                numero_cargador: valorInput('numeroCargador'),
                email_envio: leerEmailsEnvio()[0] || '',
                emails_envio: leerEmailsEnvio(),
                firma_entrega_cis_data: padFirmaCis.tieneTrazos ? canvasFirmaCis.toDataURL('image/png') : '',
                firma_entrega_cliente_data: padFirmaCli.tieneTrazos ? canvasFirmaCli.toDataURL('image/png') : '',
                vistas_dano: Array.from(vistasGuardadas.values()),
            };
            if (incluirFlagsFinal) {
                payload.enviar_email = checked('enviarEmail');
                payload.forzar_regenerar = true;
            }
            return payload;
        };
        const ejecutarGeneracionPdf = async (opciones) => {
            const actions = byId('formatoVmStatusActions');
            if (actions) {
                actions.hidden = true;
            }
            setBotonesOcupados(true);
            setOverlay(true, 'Generando PDF…', 'No cierres la tablet.');
            setStatus('Generando PDF…', false, true);
            try {
                const payload = construirPayload(true);
                payload.solo_regenerar = opciones.soloRegenerar;
                const data = await postJson(urlFinalizar, payload);
                const pdfUrl = String(data.pdf_url || urlPdf) + '?inline=1';
                setStatus(opciones.mensajeExito, false, false);
                if (actions) {
                    actions.hidden = false;
                    const link = byId('btnVerPdfGenerado');
                    if (link) {
                        link.href = pdfUrl;
                    }
                }
                window.open(pdfUrl, '_blank');
            }
            catch (err) {
                setStatus(err instanceof Error ? err.message : 'Error al generar el PDF', true);
            }
            finally {
                setOverlay(false);
                setBotonesOcupados(false);
            }
        };
        (_h = byId('btnGuardarBorrador')) === null || _h === void 0 ? void 0 : _h.addEventListener('click', async () => {
            setBotonesOcupados(true);
            setStatus('Guardando…', false, true);
            try {
                const data = await postJson(urlGuardar, construirPayload(false));
                setStatus(String(data.mensaje || 'Guardado'), false);
            }
            catch (err) {
                setStatus(err instanceof Error ? err.message : 'Error al guardar', true);
            }
            finally {
                setBotonesOcupados(false);
            }
        });
        (_j = byId('btnFinalizar')) === null || _j === void 0 ? void 0 : _j.addEventListener('click', () => {
            void ejecutarGeneracionPdf({
                soloRegenerar: false,
                mensajeExito: 'Nota de venta generada.',
            });
        });
        (_k = byId('btnRegenerarPdf')) === null || _k === void 0 ? void 0 : _k.addEventListener('click', () => {
            void ejecutarGeneracionPdf({
                soloRegenerar: true,
                mensajeExito: 'PDF regenerado (sin reenviar correo).',
            });
        });
        (_l = byId('btnReenviarEmail')) === null || _l === void 0 ? void 0 : _l.addEventListener('click', async () => {
            const emails = leerEmailsEnvio();
            if (emails.length === 0) {
                setStatus('Captura al menos un correo para reenviar.', true);
                return;
            }
            setBotonesOcupados(true);
            setStatus('Encolando correo…', false, true);
            try {
                const data = await postJson(urlReenviar, { emails_envio: emails });
                setStatus(String(data.mensaje || 'Correo encolado'), false);
            }
            catch (err) {
                setStatus(err instanceof Error ? err.message : 'Error al reenviar', true);
            }
            finally {
                setBotonesOcupados(false);
            }
        });
    }
    document.addEventListener('DOMContentLoaded', inicializarFormatoVm);
})();
//# sourceMappingURL=formato_venta_mostrador.js.map