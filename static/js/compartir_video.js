"use strict";
// ============================================================================
// COMPARTIR EVIDENCIA EN VIDEO — Modal de selección y envío
// ============================================================================
const modalEl = document.getElementById('modalCompartirEvidencia');
if (modalEl) {
    const form = document.getElementById('formCompartirEvidencia');
    const btnEnviar = document.getElementById('btnEnviarEvidencia');
    const selectAllCheckbox = document.getElementById('evSelectAll');
    const counterEl = document.getElementById('evCounter');
    const videoGrid = document.querySelector('.ev-video-grid');
    // --- Elementos de vista previa ---
    const previewArchivosEl = document.getElementById('evPreviewArchivos');
    const previewMensajeDiv = document.getElementById('evPreviewMensajePersonalizado');
    const previewMensajeTexto = document.getElementById('evTextoMensajePersonalizado');
    const mensajeTextarea = document.getElementById('evMensajePersonalizado');
    const getSelectedCount = () => {
        return document.querySelectorAll('.ev-video-checkbox:checked').length;
    };
    const updateCounter = () => {
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
    const updateMensajePreview = () => {
        if (!mensajeTextarea || !previewMensajeDiv || !previewMensajeTexto)
            return;
        const texto = mensajeTextarea.value.trim();
        if (texto.length > 0) {
            previewMensajeTexto.textContent = texto;
            previewMensajeDiv.style.display = 'block';
        }
        else {
            previewMensajeDiv.style.display = 'none';
        }
    };
    const toggleCard = (card, checkbox) => {
        if (checkbox.checked) {
            card.classList.add('ev-selected');
        }
        else {
            card.classList.remove('ev-selected');
        }
        updateCounter();
        updateSelectAll();
    };
    const updateSelectAll = () => {
        if (!selectAllCheckbox)
            return;
        const allCheckboxes = document.querySelectorAll('.ev-video-checkbox');
        const checkedCount = document.querySelectorAll('.ev-video-checkbox:checked').length;
        selectAllCheckbox.checked = allCheckboxes.length > 0 && checkedCount === allCheckboxes.length;
        selectAllCheckbox.indeterminate = checkedCount > 0 && checkedCount < allCheckboxes.length;
    };
    document.querySelectorAll('.ev-video-card').forEach(card => {
        const checkbox = card.querySelector('.ev-video-checkbox');
        if (!checkbox)
            return;
        card.addEventListener('click', (e) => {
            const target = e.target;
            if (target.closest('.ev-check-overlay')) {
                return;
            }
            checkbox.checked = !checkbox.checked;
            toggleCard(card, checkbox);
        });
        const overlay = card.querySelector('.ev-check-overlay');
        if (overlay) {
            overlay.addEventListener('click', (e) => {
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
            document.querySelectorAll('.ev-video-checkbox').forEach(cb => {
                cb.checked = shouldCheck;
                const card = cb.closest('.ev-video-card');
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
        form.addEventListener('submit', async (e) => {
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
                    const bootstrap = window.bootstrap;
                    if (bootstrap) {
                        const modalInstance = bootstrap.Modal.getInstance(modalEl);
                        if (modalInstance) {
                            setTimeout(() => {
                                modalInstance.hide();
                                window.location.reload();
                            }, 2000);
                        }
                    }
                }
                else {
                    alert(data.error || 'Error al enviar la evidencia.');
                    btnEnviar.disabled = false;
                    btnEnviar.innerHTML = originalHTML;
                }
            }
            catch (err) {
                console.error('[CompartirVideo] Error:', err);
                alert('Error de conexión. Intenta de nuevo.');
                btnEnviar.disabled = false;
                btnEnviar.innerHTML = originalHTML;
            }
        });
    }
    modalEl.addEventListener('hidden.bs.modal', () => {
        document.querySelectorAll('.ev-video-checkbox').forEach(cb => {
            cb.checked = false;
            const card = cb.closest('.ev-video-card');
            if (card)
                card.classList.remove('ev-selected');
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
        const alerts = form === null || form === void 0 ? void 0 : form.querySelectorAll('.alert-success, .alert-danger');
        alerts === null || alerts === void 0 ? void 0 : alerts.forEach(a => a.remove());
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
//# sourceMappingURL=compartir_video.js.map