// ============================================================================
// COMPARTIR EVIDENCIA EN VIDEO — Modal de selección y envío
// ============================================================================

interface VideoCardData {
    id: string;
    tipo: string;
    tipoDisplay: string;
    duracion: string;
    tamano: string;
    tieneThumbnail: boolean;
    thumbnailUrl: string;
}

const modalEl = document.getElementById('modalCompartirEvidencia');

if (modalEl) {
    const form = document.getElementById('formCompartirEvidencia') as HTMLFormElement | null;
    const btnEnviar = document.getElementById('btnEnviarEvidencia') as HTMLButtonElement | null;
    const selectAllCheckbox = document.getElementById('evSelectAll') as HTMLInputElement | null;
    const counterEl = document.getElementById('evCounter') as HTMLElement | null;
    const videoGrid = document.querySelector('.ev-video-grid') as HTMLElement | null;

    // --- Elementos de vista previa ---
    const previewArchivosEl = document.getElementById('evPreviewArchivos') as HTMLElement | null;
    const previewMensajeDiv = document.getElementById('evPreviewMensajePersonalizado') as HTMLElement | null;
    const previewMensajeTexto = document.getElementById('evTextoMensajePersonalizado') as HTMLElement | null;
    const mensajeTextarea = document.getElementById('evMensajePersonalizado') as HTMLTextAreaElement | null;

    const getSelectedCount = (): number => {
        return document.querySelectorAll<HTMLInputElement>(
            '.ev-video-checkbox:checked'
        ).length;
    };

    const updateCounter = (): void => {
        const count = getSelectedCount();
        if (counterEl) {
            counterEl.textContent = `${count} seleccionado${count !== 1 ? 's' : ''}`;
        }
        if (previewArchivosEl) {
            previewArchivosEl.innerHTML = `<i class="bi bi-camera-video"></i> ${count} video${count !== 1 ? 's' : ''}`;
        }
        if (btnEnviar) {
            const emailInvalido = btnEnviar.getAttribute('data-email-invalido') === 'true';
            btnEnviar.disabled = count === 0 || emailInvalido;
        }
    };

    const updateMensajePreview = (): void => {
        if (!mensajeTextarea || !previewMensajeDiv || !previewMensajeTexto) return;
        const texto = mensajeTextarea.value.trim();
        if (texto.length > 0) {
            previewMensajeTexto.textContent = texto;
            previewMensajeDiv.style.display = 'block';
        } else {
            previewMensajeDiv.style.display = 'none';
        }
    };

    const toggleCard = (card: HTMLElement, checkbox: HTMLInputElement): void => {
        if (checkbox.checked) {
            card.classList.add('ev-selected');
        } else {
            card.classList.remove('ev-selected');
        }
        updateCounter();
        updateSelectAll();
    };

    const updateSelectAll = (): void => {
        if (!selectAllCheckbox) return;
        const allCheckboxes = document.querySelectorAll<HTMLInputElement>('.ev-video-checkbox');
        const checkedCount = document.querySelectorAll<HTMLInputElement>('.ev-video-checkbox:checked').length;
        selectAllCheckbox.checked = allCheckboxes.length > 0 && checkedCount === allCheckboxes.length;
        selectAllCheckbox.indeterminate = checkedCount > 0 && checkedCount < allCheckboxes.length;
    };

    document.querySelectorAll<HTMLElement>('.ev-video-card').forEach(card => {
        const checkbox = card.querySelector<HTMLInputElement>('.ev-video-checkbox');
        if (!checkbox) return;

        card.addEventListener('click', (e: MouseEvent) => {
            const target = e.target as HTMLElement;
            if (target.closest('.ev-check-overlay')) {
                return;
            }
            checkbox.checked = !checkbox.checked;
            toggleCard(card, checkbox);
        });

        const overlay = card.querySelector<HTMLElement>('.ev-check-overlay');
        if (overlay) {
            overlay.addEventListener('click', (e: MouseEvent) => {
                e.stopPropagation();
                checkbox.checked = !checkbox.checked;
                toggleCard(card, checkbox);
            });
        }

        checkbox.addEventListener('change', () => {
            toggleCard(card, checkbox);
        });
    });

    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', () => {
            const shouldCheck = selectAllCheckbox.checked;
            document.querySelectorAll<HTMLInputElement>('.ev-video-checkbox').forEach(cb => {
                cb.checked = shouldCheck;
                const card = cb.closest('.ev-video-card') as HTMLElement;
                if (card) {
                    toggleCard(card, cb);
                }
            });
        });
    }

    // --- Listener para mensaje personalizado ---
    if (mensajeTextarea) {
        mensajeTextarea.addEventListener('input', updateMensajePreview);
    }

    if (form && btnEnviar) {
        form.addEventListener('submit', async (e: Event) => {
            e.preventDefault();

            const selectedCount = getSelectedCount();
            if (selectedCount === 0) {
                alert('Selecciona al menos un video para enviar.');
                return;
            }

            btnEnviar.disabled = true;
            const originalHTML = btnEnviar.innerHTML;
            btnEnviar.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Enviando...';

            try {
                const formData = new FormData(form);

                const response = await fetch(form.action, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                });

                const data = await response.json();

                if (data.success) {
                    const alertDiv = document.createElement('div');
                    alertDiv.className = 'alert alert-success mt-3';
                    alertDiv.innerHTML = `<i class="bi bi-check-circle-fill me-2"></i>${data.message}`;
                    form.prepend(alertDiv);

                    const bootstrap = (window as any).bootstrap;
                    if (bootstrap) {
                        const modalInstance = bootstrap.Modal.getInstance(modalEl);
                        if (modalInstance) {
                            setTimeout(() => {
                                modalInstance.hide();
                                window.location.reload();
                            }, 2000);
                        }
                    }
                } else {
                    alert(data.error || 'Error al enviar la evidencia.');
                    btnEnviar.disabled = false;
                    btnEnviar.innerHTML = originalHTML;
                }
            } catch (err) {
                console.error('[CompartirVideo] Error:', err);
                alert('Error de conexión. Intenta de nuevo.');
                btnEnviar.disabled = false;
                btnEnviar.innerHTML = originalHTML;
            }
        });
    }

    modalEl.addEventListener('hidden.bs.modal', () => {
        document.querySelectorAll<HTMLInputElement>('.ev-video-checkbox').forEach(cb => {
            cb.checked = false;
            const card = cb.closest('.ev-video-card') as HTMLElement;
            if (card) card.classList.remove('ev-selected');
        });
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = false;
        }
        updateCounter();

        // --- Limpiar mensaje personalizado ---
        if (mensajeTextarea) {
            mensajeTextarea.value = '';
        }
        updateMensajePreview();

        const alerts = form?.querySelectorAll('.alert-success, .alert-danger');
        alerts?.forEach(a => a.remove());

        if (btnEnviar) {
            const emailInvalido = btnEnviar.getAttribute('data-email-invalido') === 'true';
            btnEnviar.disabled = true;
            const originalText = btnEnviar.getAttribute('data-original-text') || btnEnviar.innerHTML;
            btnEnviar.innerHTML = originalText;
        }
    });

    updateCounter();
    updateMensajePreview();
}
