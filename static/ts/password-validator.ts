/**
 * Password Validator - Validación en tiempo real de contraseñas
 * 
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Este archivo TypeScript maneja toda la lógica de validación de contraseñas
 * en el lado del cliente (navegador). Proporciona feedback instantáneo mientras
 * el usuario escribe, sin necesidad de enviar el formulario.
 * 
 * Características:
 * - Indicador visual de fortaleza de contraseña (débil, moderada, fuerte)
 * - Checklist interactivo de requisitos
 * - Validación de coincidencia de contraseñas
 * - Botones para mostrar/ocultar contraseñas
 * - Validación de contraseña temporal (opcional con AJAX)
 */

// Interfaces para type safety en TypeScript
interface PasswordStrength {
    score: number;        // 0-4 (muy débil a muy fuerte)
    label: string;        // "Muy Débil", "Débil", etc.
    color: string;        // Color del indicador
    percentage: number;   // Porcentaje para la barra (0-100)
}

interface PasswordRequirement {
    id: string;
    label: string;
    test: (password: string) => boolean;
    met: boolean;
}

class PasswordValidator {
    private newPasswordInput!: HTMLInputElement;
    private confirmPasswordInput!: HTMLInputElement;
    private temporalPasswordInput!: HTMLInputElement;
    private strengthBar!: HTMLElement;
    private strengthText!: HTMLElement;
    private requirementsList!: HTMLElement;
    private matchFeedback!: HTMLElement;
    private requirements!: PasswordRequirement[];

    constructor() {
        // Inicializar cuando el DOM esté listo
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.init());
        } else {
            this.init();
        }
    }

    private init(): void {
        // Obtener elementos del DOM
        this.newPasswordInput = document.getElementById('id_nueva_contraseña') as HTMLInputElement;
        this.confirmPasswordInput = document.getElementById('id_confirmar_contraseña') as HTMLInputElement;
        this.temporalPasswordInput = document.getElementById('id_contraseña_temporal') as HTMLInputElement;

        // Verificar que los elementos existen
        if (!this.newPasswordInput || !this.confirmPasswordInput) {
            console.error('❌ No se encontraron los campos de contraseña');
            return;
        }

        // Crear elementos de UI para feedback visual
        this.createUIElements();

        // Definir requisitos de contraseña
        this.setupRequirements();

        // Configurar event listeners
        this.setupEventListeners();

        // Configurar botones de mostrar/ocultar
        this.setupToggleButtons();

        console.log('✅ Password Validator inicializado correctamente');
    }

    /**
     * Crea los elementos de UI para mostrar feedback visual
     */
    private createUIElements(): void {
        // Crear contenedor de fortaleza de contraseña
        const strengthContainer = this.createStrengthIndicator();
        this.newPasswordInput.parentElement?.appendChild(strengthContainer);

        // Crear checklist de requisitos
        const requirementsContainer = this.createRequirementsChecklist();
        this.newPasswordInput.parentElement?.appendChild(requirementsContainer);

        // Crear feedback de coincidencia
        const matchContainer = this.createMatchFeedback();
        this.confirmPasswordInput.parentElement?.appendChild(matchContainer);
    }

    /**
     * Crea el indicador visual de fortaleza de contraseña
     */
    private createStrengthIndicator(): HTMLElement {
        const container = document.createElement('div');
        container.className = 'password-strength-container mt-2';
        container.innerHTML = `
            <div class="password-strength-label mb-1">
                <small id="strength-text" class="text-muted">Fortaleza: <span class="fw-bold">-</span></small>
            </div>
            <div class="progress" style="height: 8px;">
                <div id="strength-bar" class="progress-bar" role="progressbar" 
                     style="width: 0%" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">
                </div>
            </div>
        `;

        this.strengthBar = container.querySelector('#strength-bar') as HTMLElement;
        this.strengthText = container.querySelector('#strength-text span') as HTMLElement;

        return container;
    }

    /**
     * Crea el checklist interactivo de requisitos
     */
    private createRequirementsChecklist(): HTMLElement {
        const container = document.createElement('div');
        container.className = 'password-requirements mt-3';
        container.innerHTML = `
            <div class="requirements-header mb-2">
                <small class="text-muted"><i class="bi bi-list-check"></i> <strong>Requisitos de seguridad:</strong></small>
            </div>
            <ul id="requirements-list" class="list-unstyled mb-0">
                <!-- Los requisitos se agregan dinámicamente -->
            </ul>
        `;

        this.requirementsList = container.querySelector('#requirements-list') as HTMLElement;

        return container;
    }

    /**
     * Crea el feedback de coincidencia de contraseñas
     */
    private createMatchFeedback(): HTMLElement {
        const container = document.createElement('div');
        container.className = 'password-match-feedback mt-2';
        container.innerHTML = `
            <small id="match-feedback" class="d-none"></small>
        `;

        this.matchFeedback = container.querySelector('#match-feedback') as HTMLElement;

        return container;
    }

    /**
     * Define los requisitos que debe cumplir la contraseña
     */
    private setupRequirements(): void {
        this.requirements = [
            {
                id: 'length',
                label: 'Mínimo 8 caracteres',
                test: (pwd) => pwd.length >= 8,
                met: false
            },
            {
                id: 'letters',
                label: 'Incluye letras (a-z, A-Z)',
                test: (pwd) => /[a-zA-Z]/.test(pwd),
                met: false
            },
            {
                id: 'numbers',
                label: 'Incluye números (0-9)',
                test: (pwd) => /[0-9]/.test(pwd),
                met: false
            },
            {
                id: 'special',
                label: 'Símbolos especiales (recomendado)',
                test: (pwd) => /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(pwd),
                met: false
            }
        ];

        // Renderizar la lista inicial
        this.renderRequirements();
    }

    /**
     * Renderiza la lista de requisitos en el DOM
     */
    private renderRequirements(): void {
        this.requirementsList.innerHTML = this.requirements.map(req => `
            <li id="req-${req.id}" class="requirement-item ${req.met ? 'met' : 'unmet'}">
                <i class="bi ${req.met ? 'bi-check-circle-fill text-success' : 'bi-circle text-muted'}"></i>
                <span class="ms-2">${req.label}</span>
                ${req.id === 'length' ? '<span class="char-count text-muted ms-1"></span>' : ''}
            </li>
        `).join('');
    }

    /**
     * Configura los event listeners para los campos
     */
    private setupEventListeners(): void {
        // Validación en tiempo real de nueva contraseña
        this.newPasswordInput.addEventListener('input', () => {
            this.validatePassword();
        });

        // Validación de coincidencia de contraseñas
        this.confirmPasswordInput.addEventListener('input', () => {
            this.checkPasswordMatch();
        });

        // Limpiar feedback cuando empieza a escribir la confirmación
        this.confirmPasswordInput.addEventListener('focus', () => {
            this.matchFeedback.classList.remove('d-none');
        });

        // Validación de contraseña temporal al salir del campo
        if (this.temporalPasswordInput) {
            this.temporalPasswordInput.addEventListener('blur', () => {
                this.validateTemporalPassword();
            });
        }
    }

    /**
     * Valida la fortaleza de la contraseña y actualiza el UI
     */
    private validatePassword(): void {
        const password = this.newPasswordInput.value;

        // Actualizar requisitos
        this.requirements.forEach(req => {
            req.met = req.test(password);
        });

        // Actualizar contador de caracteres
        const lengthReq = this.requirementsList.querySelector('#req-length .char-count');
        if (lengthReq) {
            lengthReq.textContent = password.length > 0 ? `(${password.length}/8)` : '';
        }

        // Renderizar requisitos actualizados
        this.renderRequirements();

        // Calcular y mostrar fortaleza
        const strength = this.calculateStrength(password);
        this.updateStrengthIndicator(strength);

        // Re-validar coincidencia si ya escribió en confirmación
        if (this.confirmPasswordInput.value.length > 0) {
            this.checkPasswordMatch();
        }
    }

    /**
     * Calcula la fortaleza de la contraseña
     */
    private calculateStrength(password: string): PasswordStrength {
        if (password.length === 0) {
            return { score: 0, label: '-', color: '#6c757d', percentage: 0 };
        }

        let score = 0;
        const metRequirements = this.requirements.filter(req => req.met).length;

        // Puntuación base por requisitos cumplidos
        score = metRequirements;

        // Ajustes adicionales
        if (password.length >= 12) score += 0.5;
        if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score += 0.5; // Mayúsculas y minúsculas
        
        // Penalización por contraseñas comunes
        if (this.isCommonPassword(password)) {
            score = Math.max(1, score - 1);
        }

        // Normalizar score a 0-4
        const normalizedScore = Math.min(4, Math.max(0, score));

        // Determinar label, color y porcentaje
        const strengthLevels: PasswordStrength[] = [
            { score: 0, label: 'Muy Débil', color: '#dc3545', percentage: 20 },
            { score: 1, label: 'Débil', color: '#fd7e14', percentage: 40 },
            { score: 2, label: 'Moderada', color: '#ffc107', percentage: 60 },
            { score: 3, label: 'Fuerte', color: '#28a745', percentage: 80 },
            { score: 4, label: 'Muy Fuerte', color: '#198754', percentage: 100 }
        ];

        return strengthLevels[Math.round(normalizedScore)];
    }

    /**
     * Verifica si la contraseña está en la lista de contraseñas comunes
     */
    private isCommonPassword(password: string): boolean {
        const commonPasswords = [
            'password', '12345678', '123456789', 'qwerty', 'abc123',
            'password123', '1234567890', 'admin', 'letmein', 'welcome'
        ];
        return commonPasswords.includes(password.toLowerCase());
    }

    /**
     * Actualiza el indicador visual de fortaleza
     */
    private updateStrengthIndicator(strength: PasswordStrength): void {
        // Actualizar barra de progreso
        this.strengthBar.style.width = `${strength.percentage}%`;
        this.strengthBar.style.backgroundColor = strength.color;
        this.strengthBar.setAttribute('aria-valuenow', strength.percentage.toString());

        // Actualizar texto
        this.strengthText.textContent = strength.label;
        this.strengthText.style.color = strength.color;

        // Animación suave
        this.strengthBar.style.transition = 'all 0.3s ease';
    }

    /**
     * Verifica si las contraseñas coinciden
     */
    private checkPasswordMatch(): void {
        const newPassword = this.newPasswordInput.value;
        const confirmPassword = this.confirmPasswordInput.value;

        if (confirmPassword.length === 0) {
            this.matchFeedback.classList.add('d-none');
            return;
        }

        this.matchFeedback.classList.remove('d-none');

        if (newPassword === confirmPassword) {
            this.matchFeedback.innerHTML = '<i class="bi bi-check-circle-fill text-success"></i> Las contraseñas coinciden';
            this.matchFeedback.className = 'password-match-feedback mt-2 text-success';
        } else {
            this.matchFeedback.innerHTML = '<i class="bi bi-x-circle-fill text-danger"></i> Las contraseñas no coinciden';
            this.matchFeedback.className = 'password-match-feedback mt-2 text-danger';
        }
    }

    /**
     * Valida la contraseña temporal (puede extenderse con AJAX)
     */
    private validateTemporalPassword(): void {
        const temporalPassword = this.temporalPasswordInput.value;

        if (temporalPassword.length === 0) {
            return;
        }

        // Aquí se podría agregar validación AJAX con el backend
        // Por ahora solo validación básica del lado del cliente
        console.log('🔍 Validando contraseña temporal...');
        
        // Ejemplo de cómo se vería con AJAX (comentado para implementación futura):
        /*
        fetch('/validar-password-temporal/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken()
            },
            body: JSON.stringify({ password: temporalPassword })
        })
        .then(response => response.json())
        .then(data => {
            if (data.valid) {
                this.showTemporalPasswordFeedback(true);
            } else {
                this.showTemporalPasswordFeedback(false);
            }
        });
        */
    }

    /**
     * Configura los botones de mostrar/ocultar contraseña
     */
    private setupToggleButtons(): void {
        const passwordFields = [
            this.temporalPasswordInput,
            this.newPasswordInput,
            this.confirmPasswordInput
        ];

        passwordFields.forEach(field => {
            if (!field) return;

            // Crear botón toggle
            const toggleButton = document.createElement('button');
            toggleButton.type = 'button';
            toggleButton.className = 'btn btn-outline-secondary btn-sm password-toggle';
            toggleButton.innerHTML = '<i class="bi bi-eye"></i>';
            toggleButton.setAttribute('aria-label', 'Mostrar contraseña');

            // Agregar evento click
            toggleButton.addEventListener('click', () => {
                this.togglePasswordVisibility(field, toggleButton);
            });

            // Insertar botón después del input
            const wrapper = document.createElement('div');
            wrapper.className = 'input-group';
            
            field.parentNode?.insertBefore(wrapper, field);
            wrapper.appendChild(field);
            wrapper.appendChild(toggleButton);
        });
    }

    /**
     * Alterna la visibilidad de la contraseña
     */
    private togglePasswordVisibility(input: HTMLInputElement, button: HTMLButtonElement): void {
        const icon = button.querySelector('i');
        
        if (input.type === 'password') {
            input.type = 'text';
            icon?.classList.replace('bi-eye', 'bi-eye-slash');
            button.setAttribute('aria-label', 'Ocultar contraseña');
        } else {
            input.type = 'password';
            icon?.classList.replace('bi-eye-slash', 'bi-eye');
            button.setAttribute('aria-label', 'Mostrar contraseña');
        }
    }

    /**
     * Obtiene el token CSRF para peticiones AJAX
     */
    private getCSRFToken(): string {
        const cookieValue = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
        return cookieValue || '';
    }
}

// Inicializar el validador cuando se carga el script
new PasswordValidator();
