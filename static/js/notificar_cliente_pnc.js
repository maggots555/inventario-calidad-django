"use strict";
/**
 * notificar_cliente_pnc.ts
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Modal «Notificar cliente: sin piezas (PNC)» en enviada_front.
 * Envía el aviso al cliente, pasa la solicitud a enviada_cliente y
 * (si hay orden) sincroniza ST a PNC en el backend.
 */
/**
 * Lee la configuración JSON embebida en el template.
 */
function leerConfig() {
    const el = document.getElementById('notificarClientePncConfig');
    if (!el || !el.textContent) {
        return null;
    }
    try {
        return JSON.parse(el.textContent);
    }
    catch (error) {
        console.error('[PNC-CLIENTE] Config JSON inválida:', error);
        return null;
    }
}
/**
 * Obtiene el valor de la cookie CSRF (prod usa sigma_csrftoken).
 */
function obtenerCsrfToken(fallback) {
    const nombres = ['sigma_csrftoken', 'csrftoken'];
    const cookies = document.cookie.split(';');
    for (const nombre of nombres) {
        for (const parte of cookies) {
            const [k, v] = parte.trim().split('=');
            if (k === nombre && v) {
                return decodeURIComponent(v);
            }
        }
    }
    return fallback;
}
/**
 * Inicializa el botón de envío del modal PNC al cliente.
 */
function initNotificarClientePnc() {
    const config = leerConfig();
    const form = document.getElementById('formNotificarClientePnc');
    const btn = document.getElementById('btnNotificarClientePnc');
    if (!config || !form || !btn) {
        return;
    }
    btn.addEventListener('click', (evento) => {
        evento.preventDefault();
        void enviarAvisoPnc(config, form, btn);
    });
}
/**
 * POST al endpoint y recarga la página si fue exitoso.
 */
async function enviarAvisoPnc(config, form, btn) {
    const emailInput = form.querySelector('#email_cliente_pnc');
    const email = ((emailInput === null || emailInput === void 0 ? void 0 : emailInput.value) || '').trim();
    if (!email) {
        alert('El email del cliente es requerido.');
        emailInput === null || emailInput === void 0 ? void 0 : emailInput.focus();
        return;
    }
    const textoOriginal = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Enviando...';
    try {
        const formData = new FormData(form);
        const csrf = obtenerCsrfToken(config.csrfToken);
        const response = await fetch(config.urlNotificarClientePnc, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrf,
            },
            credentials: 'same-origin',
        });
        const data = (await response.json());
        if (data.success) {
            const modalEl = document.getElementById('modalNotificarClientePnc');
            if (modalEl) {
                const bsLib = window['bootstrap'];
                const instancia = bsLib === null || bsLib === void 0 ? void 0 : bsLib.Modal.getInstance(modalEl);
                if (instancia) {
                    instancia.hide();
                }
            }
            alert(data.message || 'Aviso PNC enviado. La solicitud pasó a Enviada al Cliente.');
            window.location.reload();
            return;
        }
        alert(data.error || 'No se pudo enviar el aviso PNC al cliente.');
    }
    catch (error) {
        console.error('[PNC-CLIENTE] Error de red:', error);
        alert('Error de conexión. Verifica tu internet e intenta de nuevo.');
    }
    finally {
        btn.disabled = false;
        btn.innerHTML = textoOriginal;
    }
}
document.addEventListener('DOMContentLoaded', () => {
    initNotificarClientePnc();
});
//# sourceMappingURL=notificar_cliente_pnc.js.map