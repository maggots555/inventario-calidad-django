# Actualización de Configuración SSL: Validación Estricta en Cloudflare Tunnel

**Fecha de Implementación**: 12 de Febrero de 2026  
**Estado**: ✅ Completado y Verificado en Producción  
**Autor**: Equipo de Infraestructura SigmaSystem

---

## 📋 Resumen Ejecutivo

Se actualizó la configuración del túnel de Cloudflare para habilitar **validación estricta de certificados SSL**, eliminando la configuración insegura `noTLSVerify: true` que aceptaba cualquier certificado sin validación.

### Impacto
- ✅ **Seguridad mejorada**: Validación end-to-end del certificado Origin de Cloudflare
- ✅ **Sin downtime**: Cambio realizado sin interrupciones de servicio
- ✅ **Compatibilidad completa**: Todos los dominios funcionando correctamente
- ✅ **Cumplimiento de estándares**: Configuración SSL según mejores prácticas

---

## 🔒 Problema Identificado

### Configuración Anterior (Insegura)
```yaml
ingress:
  - hostname: mexico.sigmasystem.work
    service: https://localhost:443
    originRequest:
      noTLSVerify: true  # ⚠️ INSEGURO: Acepta cualquier certificado
```

### Riesgos de la Configuración Anterior
- **Man-in-the-Middle**: No validaba la autenticidad del certificado
- **Suplantación**: Cualquier servidor podría presentar un certificado inválido
- **Falsa sensación de seguridad**: El tráfico estaba cifrado pero sin autenticación del servidor
- **Incumplimiento de estándares**: No sigue las mejores prácticas de seguridad SSL/TLS

---

## ✅ Solución Implementada

### Nueva Configuración (Segura)
```yaml
ingress:
  - hostname: mexico.sigmasystem.work
    service: https://localhost:443
    originRequest:
      noTLSVerify: false  # ✅ Habilita validación de certificados
      originServerName: mexico.sigmasystem.work  # ✅ Valida el hostname del certificado
```

### Cambios Aplicados

#### 1. **Parámetro `noTLSVerify`**
- **Antes**: `true` (sin validación)
- **Después**: `false` (con validación estricta)
- **Función**: Fuerza a Cloudflare Tunnel a validar el certificado presentado por Nginx

#### 2. **Parámetro `originServerName`** (Nuevo)
- **Valor**: Hostname del dominio (ej. `mexico.sigmasystem.work`)
- **Función**: Especifica el nombre esperado en el certificado para la validación SNI (Server Name Indication)
- **Necesario porque**: El servicio backend está en `localhost:443`, pero el certificado es para `*.sigmasystem.work`

---

## 🔧 Proceso de Implementación

### Paso 1: Verificación del Certificado Origin
```bash
# Verificar certificado instalado en Nginx
openssl s_client -connect localhost:443 -servername mexico.sigmasystem.work </dev/null 2>/dev/null | openssl x509 -noout -text

# ✅ Confirmado:
# - Issuer: CloudFlare Origin SSL Certificate Authority
# - Validity: Hasta Feb 7, 2041 (14.99 años restantes)
# - SAN: *.sigmasystem.work, sigmasystem.work
# - TLS Version: TLS 1.3
```

### Paso 2: Backup de Configuración Actual
```bash
sudo cp /etc/cloudflared/config.yml \
        /etc/cloudflared/config.yml.backup-20260212-040731
```

### Paso 3: Actualización del Archivo de Configuración
```bash
sudo nano /etc/cloudflared/config.yml
```

**Cambios aplicados a cada entrada `ingress`:**
- Cambiar `noTLSVerify: true` → `false`
- Agregar `originServerName: [hostname-correspondiente]`
- Aplicado a los 3 dominios: `mexico`, `argentina`, y dominio principal

### Paso 4: Reinicio del Servicio
```bash
sudo systemctl restart cloudflared
sudo systemctl status cloudflared
```

### Paso 5: Verificación de Funcionamiento
```bash
# Verificar cada dominio
curl -I https://mexico.sigmasystem.work
curl -I https://argentina.sigmasystem.work
curl -I https://sigmasystem.work

# ✅ Todos respondieron correctamente:
# - HTTP/2 302 (mexico y argentina - redirección de login)
# - HTTP/2 301 (dominio principal - redirección a mexico)
```

---

## 📁 Archivos Modificados

### `/etc/cloudflared/config.yml`
**Ubicación**: Servidor de producción  
**Servicio**: `cloudflared.service`  
**Backup**: `/etc/cloudflared/config.yml.backup-20260212-040731`

**Estructura actualizada:**
```yaml
tunnel: [TUNNEL_ID]
credentials-file: /etc/cloudflared/[TUNNEL_ID].json

ingress:
  # Dominio México (Producción)
  - hostname: mexico.sigmasystem.work
    service: https://localhost:443
    originRequest:
      noTLSVerify: false
      originServerName: mexico.sigmasystem.work

  # Dominio Argentina (Producción)
  - hostname: argentina.sigmasystem.work
    service: https://localhost:443
    originRequest:
      noTLSVerify: false
      originServerName: argentina.sigmasystem.work

  # Dominio Principal (Redirección)
  - hostname: sigmasystem.work
    service: https://localhost:443
    originRequest:
      noTLSVerify: false
      originServerName: sigmasystem.work

  # Fallback (404)
  - service: http_status:404
```

---

## 🧪 Pruebas de Validación

### Prueba 1: Conectividad HTTPS
```bash
curl -I https://mexico.sigmasystem.work
# ✅ Resultado: HTTP/2 302
```

### Prueba 2: Certificado SSL
```bash
openssl s_client -connect mexico.sigmasystem.work:443 -servername mexico.sigmasystem.work
# ✅ Resultado: TLS 1.3, certificado válido de Cloudflare
```

### Prueba 3: Estado del Servicio
```bash
sudo systemctl status cloudflared
# ✅ Resultado: active (running)
```

### Prueba 4: Logs del Túnel
```bash
sudo journalctl -u cloudflared -n 50 --no-pager
# ✅ Resultado: Sin errores, conexiones establecidas correctamente
```

---

## 📊 Comparación: Antes vs Después

| Aspecto | Antes (`noTLSVerify: true`) | Después (`noTLSVerify: false`) |
|---------|----------------------------|--------------------------------|
| **Validación de Certificado** | ❌ Ninguna | ✅ Completa |
| **Protección MITM** | ❌ Vulnerable | ✅ Protegido |
| **Verificación SNI** | ❌ No | ✅ Sí (`originServerName`) |
| **Cifrado** | ✅ Sí (TLS 1.3) | ✅ Sí (TLS 1.3) |
| **Autenticación** | ❌ No | ✅ Sí |
| **Cumplimiento de Estándares** | ❌ No | ✅ Sí |
| **Rendimiento** | ⚡ Igual | ⚡ Igual |

---

## 🔐 Flujo de Seguridad SSL Actual

```
[Usuario]
    ↓ HTTPS (TLS 1.3)
[Cloudflare Edge]
    ↓ Cloudflare Tunnel (encriptado)
[cloudflared daemon]
    ↓ HTTPS (TLS 1.3)
    ↓ ✅ Validación de Certificado Origin
    ↓ ✅ Verificación SNI (originServerName)
[Nginx :443]
    ↓ HTTP (localhost)
[Gunicorn :8000]
    ↓
[Django App]
```

### Capas de Seguridad
1. **Edge → Tunnel**: Cifrado propietario de Cloudflare
2. **Tunnel → Nginx**: TLS 1.3 con validación estricta
3. **Nginx → Gunicorn**: HTTP en localhost (red interna segura)

---

## 📝 Notas Técnicas

### ¿Por qué `originServerName` es necesario?

El parámetro `originServerName` es esencial cuando:
- El servicio backend usa `localhost` o una IP
- El certificado SSL está emitido para un dominio (ej. `*.sigmasystem.work`)
- Se requiere validación SNI (Server Name Indication)

**Sin `originServerName`:**
```
❌ cloudflared → "Hola localhost:443, dame tu certificado"
❌ Nginx → "Aquí está mi certificado para *.sigmasystem.work"
❌ cloudflared → "ERROR: Esperaba 'localhost', pero el certificado es para '*.sigmasystem.work'"
```

**Con `originServerName`:**
```
✅ cloudflared → "Hola localhost:443, quiero validar como 'mexico.sigmasystem.work'"
✅ Nginx → "Aquí está mi certificado para *.sigmasystem.work"
✅ cloudflared → "OK: 'mexico.sigmasystem.work' coincide con '*.sigmasystem.work'"
```

### Compatibilidad del Certificado Origin

El certificado Cloudflare Origin instalado:
- **Tipo**: Wildcard (`*.sigmasystem.work`)
- **Incluye**: Dominio raíz (`sigmasystem.work`)
- **Cubre**: Todos los subdominios (`mexico`, `argentina`, futuros países)
- **Validez**: 15 años (hasta 2041)
- **Renovación necesaria**: No hasta 2041

---

## 🚀 Impacto en Producción

### ✅ Beneficios Inmediatos
- **Seguridad reforzada**: Protección contra certificados fraudulentos
- **Cumplimiento**: Alineado con mejores prácticas de la industria
- **Auditabilidad**: Configuración verificable y documentada
- **Preparación para futuras certificaciones**: ISO 27001, SOC 2, etc.

### ✅ Sin Efectos Negativos
- **Rendimiento**: Sin cambios (latencia idéntica)
- **Disponibilidad**: Sin downtime durante el cambio
- **Compatibilidad**: Todos los clientes y navegadores funcionan igual
- **Costo**: Sin cargos adicionales

---

## 📚 Referencias

### Documentación Oficial
- [Cloudflare Tunnel Configuration](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/tunnel-guide/)
- [Origin CA Certificates](https://developers.cloudflare.com/ssl/origin-configuration/origin-ca/)
- [TLS/SSL Best Practices](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/)

### Estándares de Seguridad
- **RFC 5280**: X.509 Certificate and CRL Profile
- **RFC 6125**: Domain-Based Application Service Identity
- **RFC 8446**: TLS 1.3 Protocol

---

## 🔄 Mantenimiento Futuro

### Checklist para Nuevos Países
Al agregar un nuevo país (ej. `chile.sigmasystem.work`):

```yaml
- hostname: chile.sigmasystem.work
  service: https://localhost:443
  originRequest:
    noTLSVerify: false              # ✅ SIEMPRE false
    originServerName: chile.sigmasystem.work  # ✅ Hostname del nuevo país
```

### Renovación de Certificado (2041)
Cuando se acerque la expiración del certificado Origin:
1. Generar nuevo certificado en Cloudflare Dashboard
2. Reemplazar en Nginx (`/etc/nginx/ssl/`)
3. Recargar Nginx: `sudo systemctl reload nginx`
4. **No requiere** cambios en `config.yml` (configuración ya correcta)

### Monitoreo Recomendado
```bash
# Verificar expiración del certificado
echo | openssl s_client -connect localhost:443 -servername mexico.sigmasystem.work 2>/dev/null | openssl x509 -noout -enddate

# Verificar estado del túnel
sudo systemctl status cloudflared

# Logs en tiempo real
sudo journalctl -u cloudflared -f
```

---

## 👥 Roles y Responsabilidades

| Rol | Responsabilidad |
|-----|----------------|
| **DevOps** | Monitoreo del servicio `cloudflared`, renovación de certificados |
| **Seguridad** | Auditorías periódicas de configuración SSL/TLS |
| **Desarrollo** | Asegurar que nuevas funcionalidades respeten HTTPS |
| **Infraestructura** | Backups de `/etc/cloudflared/config.yml` |

---

## ✅ Checklist de Cambios Realizados

- [x] Backup de configuración original creado
- [x] `noTLSVerify` cambiado de `true` a `false` (3 dominios)
- [x] `originServerName` agregado para cada dominio
- [x] Servicio `cloudflared` reiniciado exitosamente
- [x] Pruebas de conectividad realizadas (3/3 dominios OK)
- [x] Verificación de certificados SSL completada
- [x] Logs del servicio revisados (sin errores)
- [x] Documentación creada y archivada
- [x] Equipo notificado del cambio

---

## 📞 Contacto y Soporte

Para preguntas sobre esta configuración:
- **Equipo de Infraestructura**: `infra@sigmasystem.work`
- **Documentación del Proyecto**: `/docs/implementaciones/`
- **Issues y Mejoras**: Repositorio Git del proyecto

---

**Última Actualización**: 12 de Febrero de 2026  
**Próxima Revisión**: Anual o al agregar nuevos dominios  
**Criticidad**: Alta (Infraestructura de Seguridad)
