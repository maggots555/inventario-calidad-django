/**
 * notificar_cliente_pnc.ts
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Modal «Notificar / reenviar aviso PNC al cliente».
 * Primer aviso (enviada_front): pasa a enviada_cliente, marca el flag
 * y (si hay orden) sincroniza ST a PNC.
 * Reenvío (enviada_cliente + flag): solo vuelve a encolar el correo.
 */

interface NotificarClientePncConfig {
    urlNotificarClientePnc: string;
    csrfToken: string;
}

interface NotificarClientePncResponse {
    success: boolean;
    message?: string;
    error?: string;
    data?: {
        task_id: string;
        email_cliente: string;
        solicitud: string;
        estado: string;
    };
}

/**
 * Lee la configuración JSON embebida en el template.
 */
function leerConfig(): NotificarClientePncConfig | null {
    const el = document.getElementById('notificarClientePncConfig');
    if (!el || !el.textContent) {
        return null;
    }
    try {
        return JSON.parse(el.textContent) as NotificarClientePncConfig;
    } catch (error) {
        console.error('[PNC-CLIENTE] Config JSON inválida:', error);
        return null;
    }
}

/**
 * Obtiene el valor de la cookie CSRF (prod usa sigma_csrftoken).
 */
function obtenerCsrfToken(fallback: string): string {
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
function initNotificarClientePnc(): void {
    const config = leerConfig();
    const form = document.getElementById('formNotificarClientePnc') as HTMLFormElement | null;
    const btn = document.getElementById('btnNotificarClientePnc') as HTMLButtonElement | null;

    if (!config || !form || !btn) {
        return;
    }

    btn.addEventListener('click', (evento: MouseEvent) => {
        evento.preventDefault();
        void enviarAvisoPnc(config, form, btn);
    });
}

/**
 * POST al endpoint y recarga la página si fue exitoso.
 */
async function enviarAvisoPnc(
    config: NotificarClientePncConfig,
    form: HTMLFormElement,
    btn: HTMLButtonElement,
): Promise<void> {
    const emailInput = form.querySelector<HTMLInputElement>('#email_cliente_pnc');
    const email = (emailInput?.value || '').trim();
    if (!email) {
        alert('El email del cliente es requerido.');
        emailInput?.focus();
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

        const data = (await response.json()) as NotificarClientePncResponse;

        if (data.success) {
            const modalEl = document.getElementById('modalNotificarClientePnc');
            if (modalEl) {
                const bsLib = (window as unknown as Record<string, unknown>)['bootstrap'] as {
                    Modal: { getInstance(el: HTMLElement): { hide(): void } | null };
                } | undefined;
                const instancia = bsLib?.Modal.getInstance(modalEl);
                if (instancia) {
                    instancia.hide();
                }
            }
            alert(data.message || 'Aviso PNC enviado. La solicitud pasó a Enviada al Cliente.');
            window.location.reload();
            return;
        }

        alert(data.error || 'No se pudo enviar el aviso PNC al cliente.');
    } catch (error) {
        console.error('[PNC-CLIENTE] Error de red:', error);
        alert('Error de conexión. Verifica tu internet e intenta de nuevo.');
    } finally {
        btn.disabled = false;
        btn.innerHTML = textoOriginal;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    initNotificarClientePnc();
});
