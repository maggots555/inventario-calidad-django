"use strict";
/**
 * lista_sucursales.ts
 * ===================
 *
 * Objetivo de negocio:
 *   Interactividad de la lista administrativa de sucursales:
 *   auto-envío de filtros, atajo Escape para limpiar, y modal de eliminar.
 *
 * Argumentos / entrada:
 *   - Formulario #lsFiltrosForm (data-clear-url con la URL limpia).
 *   - Botones .ls-btn-eliminar con data-url y data-nombre.
 *   - Modal #modalConfirmacion, #nombreSucursal y form #formEliminar.
 *
 * Efectos secundarios:
 *   Envía el GET de filtros, navega al limpiar, abre un Modal Bootstrap
 *   y asigna el action del POST de eliminación. No llama APIs.
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * tsc junta todos los .ts como scripts (no módulos). Si una función se llama
 * igual que en lista_empleados.ts, el compilador truena. Por eso envolvemos
 * todo en una IIFE: las funciones quedan privadas de este archivo.
 */
(function listaSucursalesMain() {
    /**
     * Obtiene bootstrap del window sin redeclarar la variable global.
     */
    function obtenerBootstrap() {
        return window.bootstrap;
    }
    /**
     * Auto-envía el formulario al cambiar un select o al dejar de escribir
     * en el buscador (espera 500 ms para no disparar un GET por cada letra).
     */
    function initFiltros() {
        const form = document.getElementById('lsFiltrosForm');
        if (!form || !(form instanceof HTMLFormElement)) {
            return;
        }
        // EXPLICACIÓN: los <select> no necesitan debounce; el cambio es un clic.
        form.querySelectorAll('select').forEach((select) => {
            select.addEventListener('change', () => {
                form.submit();
            });
        });
        const busqueda = document.getElementById('busqueda');
        if (!(busqueda instanceof HTMLInputElement)) {
            return;
        }
        let timeoutId = 0;
        busqueda.addEventListener('input', () => {
            window.clearTimeout(timeoutId);
            timeoutId = window.setTimeout(() => {
                form.submit();
            }, 500);
        });
    }
    /**
     * Escape limpia filtros si hay alguno activo (navega a data-clear-url).
     */
    function initEscape() {
        const form = document.getElementById('lsFiltrosForm');
        if (!form || !(form instanceof HTMLFormElement)) {
            return;
        }
        const clearUrl = form.dataset.clearUrl;
        if (!clearUrl) {
            return;
        }
        document.addEventListener('keydown', (event) => {
            if (event.key !== 'Escape') {
                return;
            }
            // Leemos los controles actuales: si alguno tiene valor, hay filtro activo.
            const busqueda = document.getElementById('busqueda');
            const estado = document.getElementById('estado');
            const ciudad = document.getElementById('ciudad');
            const valorBusqueda = busqueda instanceof HTMLInputElement ? busqueda.value : '';
            const valorEstado = estado instanceof HTMLSelectElement ? estado.value : '';
            const valorCiudad = ciudad instanceof HTMLSelectElement ? ciudad.value : '';
            // El chip "Con encargado" vive como hidden, no como select.
            const tieneEncargado = Boolean(form.querySelector('input[name="con_encargado"]'));
            if (valorBusqueda || valorEstado || valorCiudad || tieneEncargado) {
                window.location.href = clearUrl;
            }
        });
    }
    /**
     * Abre el modal de confirmación y pone la URL de eliminar en el form POST.
     */
    function abrirModalEliminar(boton) {
        const url = boton.dataset.url;
        const nombre = boton.dataset.nombre;
        if (!url || !nombre) {
            return;
        }
        const nombreEl = document.getElementById('nombreSucursal');
        const formEl = document.getElementById('formEliminar');
        const modalEl = document.getElementById('modalConfirmacion');
        if (!nombreEl ||
            !formEl ||
            !(formEl instanceof HTMLFormElement) ||
            !modalEl) {
            return;
        }
        nombreEl.textContent = nombre;
        // data-url viene de {% url %} en el HTML: no armamos la ruta a mano.
        formEl.action = url;
        const bootstrapApi = obtenerBootstrap();
        new bootstrapApi.Modal(modalEl).show();
    }
    /**
     * Enlaza los botones Eliminar (tabla escritorio y tarjetas móvil).
     */
    function initModalEliminar() {
        document.addEventListener('click', (event) => {
            const target = event.target;
            if (!(target instanceof Element)) {
                return;
            }
            const boton = target.closest('.ls-btn-eliminar');
            if (!boton) {
                return;
            }
            event.preventDefault();
            abrirModalEliminar(boton);
        });
    }
    document.addEventListener('DOMContentLoaded', () => {
        initFiltros();
        initEscape();
        initModalEliminar();
    });
})();
//# sourceMappingURL=lista_sucursales.js.map