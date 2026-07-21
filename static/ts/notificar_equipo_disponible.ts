/**
 * Botón "Notificar equipo disponible" en detalle de orden.
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Cuando la orden está en Finalizado, recepción puede avisar al cliente por
 * correo de que ya puede recolectar el equipo. Este módulo:
 * 1) Confirma con el usuario
 * 2) Hace POST a la vista Django (CSRF)
 * 3) Si OK, deja el botón como "Equipo notificado" (deshabilitado)
 */

(function (): void {
  'use strict';

  interface RespuestaNotificar {
    success: boolean;
    message?: string;
    error?: string;
    ya_notificado?: boolean;
    email?: string;
  }

  /**
   * Lee la cookie CSRF (producción usa sigma_csrftoken).
   */
  function obtenerCsrfToken(): string {
    const cookieNames: string[] = ['sigma_csrftoken', 'csrftoken'];
    const cookies = document.cookie.split(';');
    for (const name of cookieNames) {
      for (const row of cookies) {
        const trimmed = row.trim();
        if (trimmed.startsWith(`${name}=`)) {
          return decodeURIComponent(trimmed.substring(name.length + 1));
        }
      }
    }
    return '';
  }

  function marcarBotonNotificado(btn: HTMLButtonElement): void {
    btn.disabled = true;
    btn.classList.remove('btn-success');
    btn.classList.add('btn-outline-success');
    btn.innerHTML =
      '<i class="bi bi-check-circle-fill me-1"></i> Equipo notificado';
    btn.title = 'Ya se notificó al cliente';
  }

  async function enviarNotificacion(btn: HTMLButtonElement): Promise<void> {
    const url = btn.dataset.url;
    if (!url) {
      window.alert('No se encontró la URL de notificación.');
      return;
    }

    const email = btn.dataset.email || 'el cliente';
    const folio = btn.dataset.folio || '';
    const confirmar = window.confirm(
      `¿Enviar el correo de "equipo disponible para recolección" a ${email}` +
        (folio ? ` (folio ${folio})` : '') +
        '?\n\nEsta acción no se puede deshacer desde aquí.'
    );
    if (!confirmar) {
      return;
    }

    const textoOriginal = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML =
      '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Enviando…';

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'X-CSRFToken': obtenerCsrfToken(),
          Accept: 'application/json',
        },
        credentials: 'same-origin',
      });

      const data = (await response.json()) as RespuestaNotificar;

      if (!response.ok || !data.success) {
        window.alert(data.error || 'No se pudo enviar la notificación.');
        // Si ya estaba notificado, dejar el botón en estado final
        if (data.ya_notificado) {
          marcarBotonNotificado(btn);
          return;
        }
        btn.disabled = false;
        btn.innerHTML = textoOriginal;
        return;
      }

      marcarBotonNotificado(btn);
      window.alert(
        data.message ||
          'Correo encolado. El cliente recibirá el aviso en breve.'
      );
    } catch (err) {
      console.error('[notificar_equipo_disponible]', err);
      window.alert('Error de red al notificar. Intenta de nuevo.');
      btn.disabled = false;
      btn.innerHTML = textoOriginal;
    }
  }

  function init(): void {
    const btn = document.getElementById(
      'btnNotificarEquipoDisponible'
    ) as HTMLButtonElement | null;
    if (!btn) {
      return;
    }

    btn.addEventListener('click', () => {
      void enviarNotificacion(btn);
    });

    // Si la URL trae el ancla, resaltar el bloque al abrir desde la campanita
    if (window.location.hash === '#notificar-equipo-disponible') {
      const bloque = document.getElementById('notificar-equipo-disponible');
      if (bloque) {
        bloque.scrollIntoView({ behavior: 'smooth', block: 'center' });
        bloque.classList.add('border', 'border-success', 'rounded', 'p-2');
        window.setTimeout(() => {
          bloque.classList.remove('border', 'border-success', 'rounded', 'p-2');
        }, 4000);
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
