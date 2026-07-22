/**
 * lista_empleados.ts
 * ==================
 *
 * Objetivo de negocio:
 *   Interactividad de la lista administrativa de empleados:
 *   filtros con auto-submit y panel lateral (Offcanvas) con ficha +
 *   gestión de acceso al sistema.
 *
 * Argumentos / entrada:
 *   Elementos HTML con data-* en .empleado-row / .empleado-card / .btn-gestionar.
 *
 * Efectos secundarios:
 *   Abre Offcanvas Bootstrap, reescribe el DOM del panel, puede navegar
 *   o enviar formularios POST (revocar / desactivar).
 */

/** Estados de acceso al sistema (códigos del backend). */
type EstadoAcceso = 'sin_acceso' | 'pendiente' | 'activo' | 'revocado';

/** Datos que viajan en data-attributes de cada empleado. */
interface EmpleadoPanelData {
    id: string;
    nombre: string;
    cargo: string;
    area: string;
    rol: string;
    email: string;
    sucursal: string;
    jefe: string;
    activo: boolean;
    estadoAcceso: EstadoAcceso;
    lastLogin: string;
    fotoUrl: string;
    iniciales: string;
    tieneEmail: boolean;
    esAdmin: boolean;
    urlEditar: string;
    urlDarAcceso: string;
    urlReenviar: string;
    urlResetear: string;
    urlRevocar: string;
    urlReactivar: string;
    urlDesactivar: string;
    csrfToken: string;
}

/** API mínima de Bootstrap Offcanvas (cargado globalmente en base.html). */
interface BootstrapOffcanvasInstance {
    show(): void;
    hide(): void;
}

interface BootstrapOffcanvasStatic {
    getOrCreateInstance(
        element: Element | string,
        options?: Record<string, unknown>
    ): BootstrapOffcanvasInstance;
}

interface BootstrapGlobal {
    Offcanvas: BootstrapOffcanvasStatic;
}

/**
 * Obtiene bootstrap del window sin redeclarar la variable global
 * (otros módulos TS ya declaran `bootstrap`).
 */
function getBootstrap(): BootstrapGlobal {
    return (window as unknown as { bootstrap: BootstrapGlobal }).bootstrap;
}

/** Textos pedagógicos según estado de acceso. */
const TEXTOS_ACCESO: Record<
    EstadoAcceso,
    { titulo: string; descripcion: string; icono: string }
> = {
    sin_acceso: {
        titulo: 'Sin acceso',
        descripcion:
            'Este empleado aún no tiene usuario en SIGMA. Si le das acceso, se creará una cuenta y se enviará una contraseña temporal a su email.',
        icono: 'bi-x-circle',
    },
    pendiente: {
        titulo: 'Pendiente de activación',
        descripcion:
            'Ya tiene usuario, pero todavía no cambió la contraseña temporal. Puede reenviar las credenciales o resetear la contraseña.',
        icono: 'bi-hourglass-split',
    },
    activo: {
        titulo: 'Acceso activo',
        descripcion:
            'Puede iniciar sesión con normalidad. Desde aquí puedes resetear su contraseña o revocar el acceso si deja de necesitarlo.',
        icono: 'bi-check-circle-fill',
    },
    revocado: {
        titulo: 'Acceso revocado',
        descripcion:
            'Su usuario existe pero está desactivado: no puede entrar. Puedes reactivarlo (se enviará una nueva contraseña temporal).',
        icono: 'bi-lock-fill',
    },
};

/**
 * Lee data-* de un elemento disparador y arma el objeto tipado del panel.
 */
function leerDatosEmpleado(el: HTMLElement): EmpleadoPanelData | null {
    const d = el.dataset;
    if (!d.empleadoId || !d.nombre) {
        return null;
    }

    const estado = (d.estadoAcceso || 'sin_acceso') as EstadoAcceso;

    return {
        id: d.empleadoId,
        nombre: d.nombre,
        cargo: d.cargo || '',
        area: d.area || '',
        rol: d.rol || '',
        email: d.email || '',
        sucursal: d.sucursal || 'Sin asignar',
        jefe: d.jefe || 'Sin asignar',
        activo: d.activo === 'true',
        estadoAcceso: estado,
        lastLogin: d.lastLogin || '',
        fotoUrl: d.fotoUrl || '',
        iniciales: d.iniciales || 'US',
        tieneEmail: d.tieneEmail === 'true',
        esAdmin: d.esAdmin === 'true',
        urlEditar: d.urlEditar || '',
        urlDarAcceso: d.urlDarAcceso || '',
        urlReenviar: d.urlReenviar || '',
        urlResetear: d.urlResetear || '',
        urlRevocar: d.urlRevocar || '',
        urlReactivar: d.urlReactivar || '',
        urlDesactivar: d.urlDesactivar || '',
        csrfToken: d.csrfToken || '',
    };
}

/**
 * Escapa texto para insertarlo de forma segura en HTML.
 */
function escapeHtml(texto: string): string {
    const div = document.createElement('div');
    div.textContent = texto;
    return div.innerHTML;
}

/**
 * Construye el markup del avatar (foto o iniciales).
 */
function htmlAvatar(data: EmpleadoPanelData, claseExtra: string): string {
    if (data.fotoUrl) {
        return `<div class="le-avatar ${claseExtra}"><img src="${escapeHtml(data.fotoUrl)}" alt="${escapeHtml(data.nombre)}"></div>`;
    }
    return `<div class="le-avatar ${claseExtra}" aria-hidden="true">${escapeHtml(data.iniciales)}</div>`;
}

/**
 * Botones de acción según estado (solo para administradores).
 */
function htmlAcciones(data: EmpleadoPanelData): string {
    if (!data.esAdmin) {
        return `<div class="le-panel-readonly-note"><i class="bi bi-eye"></i> Modo solo lectura: no puedes gestionar el acceso.</div>`;
    }

    const botones: string[] = [];

    // EXPLICACIÓN PARA PRINCIPIANTES:
    // Según el estado mostramos un botón "principal" distinto.
    // Las acciones peligrosas abren un bloque de confirmación inline.
    if (data.estadoAcceso === 'sin_acceso') {
        if (data.tieneEmail) {
            botones.push(
                `<a class="btn btn-success" href="${escapeHtml(data.urlDarAcceso)}"><i class="bi bi-key-fill"></i> Dar acceso al sistema</a>`
            );
        } else {
            botones.push(
                `<button type="button" class="btn btn-success" disabled title="Necesita email"><i class="bi bi-key-fill"></i> Dar acceso (falta email)</button>`
            );
            botones.push(
                `<a class="btn btn-outline-primary" href="${escapeHtml(data.urlEditar)}"><i class="bi bi-pencil"></i> Editar para agregar email</a>`
            );
        }
    } else if (data.estadoAcceso === 'revocado') {
        botones.push(
            `<a class="btn btn-success" href="${escapeHtml(data.urlReactivar)}"><i class="bi bi-unlock-fill"></i> Reactivar acceso</a>`
        );
    } else if (data.estadoAcceso === 'pendiente') {
        botones.push(
            `<a class="btn btn-primary" href="${escapeHtml(data.urlReenviar)}"><i class="bi bi-envelope-fill"></i> Reenviar credenciales</a>`
        );
        botones.push(
            `<a class="btn btn-outline-warning" href="${escapeHtml(data.urlResetear)}"><i class="bi bi-arrow-clockwise"></i> Resetear contraseña</a>`
        );
        botones.push(
            `<button type="button" class="btn btn-outline-danger" data-le-confirm="revocar"><i class="bi bi-shield-x"></i> Revocar acceso</button>`
        );
    } else {
        // activo
        botones.push(
            `<a class="btn btn-outline-warning" href="${escapeHtml(data.urlResetear)}"><i class="bi bi-arrow-clockwise"></i> Resetear contraseña</a>`
        );
        botones.push(
            `<button type="button" class="btn btn-outline-danger" data-le-confirm="revocar"><i class="bi bi-shield-x"></i> Revocar acceso</button>`
        );
    }

    botones.push(
        `<div class="btn-row">
            <a class="btn btn-outline-primary" href="${escapeHtml(data.urlEditar)}"><i class="bi bi-pencil"></i> Editar</a>
            ${
                data.activo
                    ? `<button type="button" class="btn btn-outline-secondary" data-le-confirm="desactivar"><i class="bi bi-person-dash"></i> Desactivar</button>`
                    : ''
            }
        </div>`
    );

    // Bloques de confirmación (ocultos hasta que el usuario pulse)
    const confirmRevocar = `
        <div class="le-confirm-box d-none" id="leConfirmRevocar" data-confirm-for="revocar">
            <p><strong>¿Revocar acceso de ${escapeHtml(data.nombre)}?</strong><br>
            No podrá iniciar sesión. Su ficha de empleado se conserva y podrás reactivarlo después.</p>
            <form method="post" action="${escapeHtml(data.urlRevocar)}">
                <input type="hidden" name="csrfmiddlewaretoken" value="${escapeHtml(data.csrfToken)}">
                <div class="btn-row">
                    <button type="button" class="btn btn-outline-secondary" data-le-cancel-confirm>Cancelar</button>
                    <button type="submit" class="btn btn-warning"><i class="bi bi-shield-x"></i> Sí, revocar</button>
                </div>
            </form>
        </div>`;

    const confirmDesactivar = data.activo
        ? `
        <div class="le-confirm-box d-none" id="leConfirmDesactivar" data-confirm-for="desactivar">
            <p><strong>¿Desactivar a ${escapeHtml(data.nombre)}?</strong><br>
            Quedará como empleado inactivo en la empresa (soft-delete). No elimina su historial.</p>
            <div class="btn-row">
                <button type="button" class="btn btn-outline-secondary" data-le-cancel-confirm>Cancelar</button>
                <a class="btn btn-danger" href="${escapeHtml(data.urlDesactivar)}"><i class="bi bi-person-dash"></i> Sí, desactivar</a>
            </div>
        </div>`
        : '';

    return `<div class="le-panel-actions" id="lePanelActions">
        ${botones.join('\n')}
        ${confirmRevocar}
        ${confirmDesactivar}
    </div>`;
}

/**
 * Pinta todo el cuerpo del Offcanvas con la ficha del empleado.
 */
function renderPanel(body: HTMLElement, data: EmpleadoPanelData): void {
    const info = TEXTOS_ACCESO[data.estadoAcceso];
    const lastLoginHtml = data.lastLogin
        ? `<div><dt>Último acceso</dt><dd>${escapeHtml(data.lastLogin)}</dd></div>`
        : '';

    body.innerHTML = `
        <div class="le-panel-hero">
            ${htmlAvatar(data, 'le-avatar--lg')}
            <div class="le-panel-hero-text">
                <h2>${escapeHtml(data.nombre)}</h2>
                <p>${escapeHtml(data.cargo)}${data.area ? ' · ' + escapeHtml(data.area) : ''}</p>
                ${
                    data.rol
                        ? `<p class="le-panel-rol"><i class="bi bi-person-badge"></i> ${escapeHtml(data.rol)}</p>`
                        : ''
                }
            </div>
        </div>

        <div class="le-panel-section">
            <div class="le-panel-section-title">Datos</div>
            <dl class="le-panel-dl">
                <div><dt>Rol sistema</dt><dd>${data.rol ? escapeHtml(data.rol) : '<span class="text-muted">Sin rol</span>'}</dd></div>
                <div><dt>Email</dt><dd>${data.email ? escapeHtml(data.email) : '<span class="text-muted">Sin email</span>'}</dd></div>
                <div><dt>Sucursal</dt><dd>${escapeHtml(data.sucursal)}</dd></div>
                <div><dt>Jefe directo</dt><dd>${escapeHtml(data.jefe)}</dd></div>
                <div><dt>Estado laboral</dt><dd>${
                    data.activo
                        ? '<span class="le-status le-status--activo">Activo</span>'
                        : '<span class="le-status le-status--inactivo-emp">Inactivo</span>'
                }</dd></div>
                ${lastLoginHtml}
            </dl>
        </div>

        <div class="le-panel-section">
            <div class="le-panel-section-title">Acceso al sistema</div>
            <div class="le-acceso-box">
                <span class="le-status le-status--${escapeHtml(data.estadoAcceso)}">
                    <i class="bi ${info.icono}"></i> ${escapeHtml(info.titulo)}
                </span>
                <p>${escapeHtml(info.descripcion)}</p>
            </div>
        </div>

        ${htmlAcciones(data)}
    `;

    cablearConfirmaciones(body);
}

/**
 * Muestra/oculta bloques de confirmación inline (revocar / desactivar).
 */
function cablearConfirmaciones(root: HTMLElement): void {
    const acciones = root.querySelector('#lePanelActions');
    if (!acciones) {
        return;
    }

    acciones.querySelectorAll<HTMLElement>('[data-le-confirm]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const tipo = btn.getAttribute('data-le-confirm');
            acciones.querySelectorAll<HTMLElement>('[data-confirm-for]').forEach((box) => {
                box.classList.toggle('d-none', box.getAttribute('data-confirm-for') !== tipo);
            });
        });
    });

    acciones.querySelectorAll('[data-le-cancel-confirm]').forEach((btn) => {
        btn.addEventListener('click', () => {
            acciones.querySelectorAll<HTMLElement>('[data-confirm-for]').forEach((box) => {
                box.classList.add('d-none');
            });
        });
    });
}

/**
 * Abre el panel lateral con los datos del disparador.
 */
function abrirPanel(trigger: HTMLElement): void {
    const data = leerDatosEmpleado(trigger);
    if (!data) {
        return;
    }

    const panel = document.getElementById('panelEmpleado');
    const body = document.getElementById('panelEmpleadoBody');
    const title = document.getElementById('panelEmpleadoLabel');
    if (!panel || !body) {
        return;
    }

    if (title) {
        title.textContent = 'Ficha de empleado';
    }

    renderPanel(body, data);
    getBootstrap().Offcanvas.getOrCreateInstance(panel).show();
}

/**
 * Auto-envía el formulario de filtros al cambiar un select.
 */
function initFiltrosAutoSubmit(): void {
    const form = document.getElementById('leFiltrosForm');
    if (!form || !(form instanceof HTMLFormElement)) {
        return;
    }

    form.querySelectorAll('select').forEach((select) => {
        select.addEventListener('change', () => {
            form.submit();
        });
    });
}

/**
 * Enlaza clics en filas, tarjetas y botón Gestionar.
 */
function initAperturaPanel(): void {
    document.addEventListener('click', (event: MouseEvent) => {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }

        // Disparadores válidos: fila, tarjeta o botón "Gestionar"
        const trigger = target.closest<HTMLElement>(
            '.empleado-row, .empleado-card, .btn-gestionar'
        );
        if (!trigger) {
            return;
        }

        // Dentro de una fila, ignorar clics en enlaces ajenos (no el botón gestionar)
        if (
            trigger.classList.contains('empleado-row') &&
            target.closest('a') &&
            !target.closest('.btn-gestionar')
        ) {
            return;
        }

        // btn-gestionar usa los data-* de la fila padre
        let fuente: HTMLElement = trigger;
        if (trigger.classList.contains('btn-gestionar') && !trigger.dataset.empleadoId) {
            const fila = trigger.closest<HTMLElement>('.empleado-row, .empleado-card');
            if (!fila) {
                return;
            }
            fuente = fila;
        }

        event.preventDefault();
        abrirPanel(fuente);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initFiltrosAutoSubmit();
    initAperturaPanel();
});
