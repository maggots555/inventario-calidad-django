# API de autofacturación SIGMA ↔ Portal VO

Documento técnico para el equipo del portal de facturación (VO).
Describe el contrato que expone SIGMA para que el cliente final genere su CFDI.

| Dato | Valor |
|---|---|
| Sistema | SIGMA — Sistema Integrado de Gestión Técnica |
| Host producción (México) | `https://mexico.sigmasystem.work` |
| Prefijo de rutas | `/facturacion-web/` |
| Formato | JSON (UTF-8) |
| Autenticación | API Key en header + JWT Bearer |
| Alcance | Solo México (CFDI 4.0). Otros países responden 400. |

---

## 1. Resumen del flujo

```
Cliente                Portal VO                       SIGMA
  │                        │                             │
  │── entra y se loguea ──►│                             │
  │── teclea "SAT9596-1" ─►│                             │
  │                        │── POST /authenticate ──────►│  (1) obtiene JWT
  │                        │◄── access_token ────────────│
  │                        │── GET /folio/SAT9596-1 ────►│  (2) pide la venta
  │                        │◄── encabezado + conceptos ──│
  │                        │                             │
  │                    (timbra el CFDI en su PAC)        │
  │                        │                             │
  │                        │── PUT /folio/SAT9596-1 ────►│  (3) devuelve XML/PDF
  │                        │◄── 204 No Content ──────────│
  │◄── entrega el CFDI ────│                             │
```

**Importante:** el `PUT` solo se acepta si antes hubo un `GET` del mismo `webId`.

---

## 2. El `webId`

Es el identificador que el cliente teclea en el portal. Lo genera SIGMA y se lo
muestra al cliente en su enlace de seguimiento.

```
SAT9596-1
└┬┘ └┬─┘ └┬
 │   │    └── documento: 1 = PUE diagnóstico, 2 = PPD anticipo, 3 = PUE de contado
 │   └─────── dígitos del folio del cliente (OOW-9596 → 9596)
 └─────────── prefijo de la sucursal
```

### Prefijos de sucursal vigentes

| Prefijo | Sucursal |
|---|---|
| `SAT` | Satélite |
| `DROP` | Drop Off Sur |
| `GDL` | Guadalajara |
| `MTY` | Monterrey |

La lista puede crecer. **No la codifiquen en duro**: traten el `webId` como texto
opaco que el usuario captura y que se manda tal cual en la URL.

### Tolerancia al leer

SIGMA acepta variantes para no castigar al cliente por un error de tecleo:

| Lo que manda el portal | Resultado |
|---|---|
| `SAT9596-1` | Forma canónica. Siempre funciona. |
| `sat9596-1` | Se normaliza a mayúsculas. |
| `SAT9596` | Funciona **si** el folio tiene un solo documento facturable. Si tiene dos, responde `400` pidiendo el tipo. |
| `9596` | Igual que el anterior, pero además falla con `400` si dos sucursales comparten el número de folio. |
| `SAT0123-1` | Los ceros a la izquierda se ignoran (equivale a `SAT123-1`). |

---

## 3. Tipos de documento

El método no sale del tipo de servicio. Sale del pago que registró SIGMA.

| Sufijo | `tipo_factura` | `metodo_pago` | Cuándo lo genera SIGMA | Concepto |
|---|---|---|---|---|
| `-1` | `1` | `PUE` | El diagnóstico está cubierto al 100% y el abono ya está validado. | `Diagnóstico` |
| `-3` | `1` | `PUE` | La reparación o los servicios se pagaron en una sola exhibición y ese dinero ya cubre el total. | Una línea por servicio y una línea por cada pieza aceptada |
| `-2` | `2` | `PPD` | Hay un anticipo validado de la reparación. | `Anticipo del bien o servicio` (línea única, sin detallar piezas) |

`-1` y `-3` son los dos PUE. `tipo_factura` sigue siendo `1` en ambos: el
sufijo distingue el documento, no un método SAT nuevo. Una orden puede
tener el diagnóstico y, además, el anticipo o el pago de contado.

### Qué clave lleva cada concepto

El diagnóstico (`-1`) y cada servicio del pago de contado (`-3`) salen con
la ClaveProdServ fija de esa línea. El anticipo (`-2`) no detalla servicios:
sigue siendo una sola línea (`84111506`).

| Línea | `clave_producto_servicio` | `clave_unidad` | `cantidad` | Precio |
|---|---|---|---|---|
| Diagnóstico (webId `-1`) | `81111820` | `E48` | `1` | Neto del diagnóstico |
| Limpieza y mantenimiento | `72151800` | `E48` | `1` | Neto del servicio |
| Instalación / cambio de pieza (sin diagnóstico) | `81111814` | `E48` | `1` | Neto del servicio |
| Reinstalación de sistema operativo | `81111505` | `E48` | `1` | Neto del servicio |
| Respaldo de información | `81112218` | `E48` | `1` | Neto del servicio |
| Paquete oro, plata o premium | `43211600` | `E48` | `1` | Neto del paquete |
| Kit de limpieza | `43211600` | `H87` | `1` | Neto del kit |
| Pieza aceptada de la cotización o vendida en mostrador | La `clave_sat` del producto de almacén, si tiene 8 dígitos. Si está vacía o la pieza no viene de un producto: `01010101` | `H87` | Las unidades vendidas | Precio unitario sin IVA |

`precio` es el unitario sin IVA. El importe de la línea es `cantidad × precio`.
El `subtotal` del encabezado es la suma de esos importes.

La clave de una pieza no se copia a la cotización: SIGMA la lee del producto
al armar el documento. Si la capturan después de cotizar y el `-3` todavía
no está timbrado, el siguiente GET ya la trae. La de un servicio no sale del
producto: está fija en el catálogo de arriba. Un documento con UUID no se recalcula.

Varios anticipos del mismo servicio se suman en el mismo `-2` mientras no
esté timbrado. Después del UUID ese documento queda congelado y no nace otro
PPD: el saldo restante es complemento de pago y SIGMA no lo genera.

### Condición para que exista un documento

SIGMA solo publica un `webId` cuando **el pago está verificado** en la
cuenta de la empresa (transferencia, tarjeta de crédito o tarjeta de
débito). Un abono en `pendiente` no se factura. Los cobros en efectivo
que ya existían antes de este corte siguen contando.

Órdenes **dentro de garantía** nunca se autofacturan (el cliente no paga).

---

## 4. Endpoints

### 4.1 `POST /facturacion-web/authenticate`

Obtiene el JWT que se usa en los demás endpoints.

**Headers**

```
X-API-KEY: <api key entregada por SIGMA>
Content-Type: application/json
```

**Body**

```json
{ "secret": "<secret entregado por SIGMA>" }
```

**Respuesta 200**

```json
{ "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...." }
```

El token es HS256 y dura 1 hora en producción. Renovarlo al recibir un `401`.

**Errores**

| Código | Causa |
|---|---|
| 401 | API Key inválida, `secret` incorrecto o API sin configurar. |
| 400 | Body que no es JSON válido. |

---

### 4.2 `GET /facturacion-web/folio/{webId}`

Devuelve los datos de la venta lista para timbrar.

**Headers**

```
X-API-KEY: <api key>
Authorization: Bearer <access_token>
```

**Respuesta 200 — ejemplo PUE (diagnóstico de $500 + IVA)**

```json
{
  "encabezado": {
    "fecha_ticket": "2026-09-18T14:32:10-06:00",
    "folio": "OOW-9596",
    "web_id": "SAT9596-1",
    "tipo_factura": 1,
    "metodo_pago": "PUE",
    "forma_pago": "04",
    "moneda": "MXN",
    "subtotal": 500.00,
    "tasa_iva": 0.16,
    "iva": 80.00,
    "total": 580.00
  },
  "conceptos": [
    {
      "clave_producto_servicio": "81111820",
      "descripcion": "Diagnóstico",
      "clave_unidad": "E48",
      "precio": 500.00,
      "numero_identificacion": "None",
      "unidad": "E48",
      "objeto_impuesto": 2,
      "impuestos": "[4]",
      "empresa": "2",
      "clave_producto_cliente": "S0001",
      "cantidad": 1.0,
      "descuento": 0
    }
  ]
}
```

**Respuesta 200 — ejemplo PUE de contado (`-3`), servicio más una pieza**

```json
{
  "encabezado": {
    "fecha_ticket": "2026-09-21T12:10:00-06:00",
    "folio": "OOW-9596",
    "web_id": "SAT9596-3",
    "tipo_factura": 1,
    "metodo_pago": "PUE",
    "forma_pago": "28",
    "moneda": "MXN",
    "subtotal": 1000.00,
    "tasa_iva": 0.16,
    "iva": 160.00,
    "total": 1160.00
  },
  "conceptos": [
    {
      "clave_producto_servicio": "72151800",
      "descripcion": "Limpieza y Mantenimiento",
      "clave_unidad": "E48",
      "precio": 500.00,
      "numero_identificacion": "None",
      "unidad": "E48",
      "objeto_impuesto": 2,
      "impuestos": "[4]",
      "empresa": "2",
      "clave_producto_cliente": "S0001",
      "cantidad": 1.0,
      "descuento": 0
    },
    {
      "clave_producto_servicio": "43211503",
      "descripcion": "Bateria Dell 40 W",
      "clave_unidad": "H87",
      "precio": 500.00,
      "numero_identificacion": "None",
      "unidad": "H87",
      "objeto_impuesto": 2,
      "impuestos": "[4]",
      "empresa": "2",
      "clave_producto_cliente": "S0002",
      "cantidad": 1.0,
      "descuento": 0
    }
  ]
}
```

En el ejemplo la pieza ya tiene clave en el producto (`43211503`). Si el
producto no la tuviera, esa misma línea saldría con `01010101`.

**Respuesta 200 — ejemplo PPD (anticipo)**

```json
{
  "encabezado": {
    "fecha_ticket": "2026-09-18T11:05:00-06:00",
    "folio": "OOW-9596",
    "web_id": "SAT9596-2",
    "tipo_factura": 2,
    "metodo_pago": "PPD",
    "forma_pago": "03",
    "moneda": "MXN",
    "subtotal": 250.00,
    "tasa_iva": 0.16,
    "iva": 40.00,
    "total": 290.00
  },
  "conceptos": [
    {
      "clave_producto_servicio": "84111506",
      "descripcion": "Anticipo del bien o servicio",
      "clave_unidad": "ACT",
      "precio": 250.00,
      "numero_identificacion": "None",
      "unidad": "ACT",
      "objeto_impuesto": 2,
      "impuestos": "[4]",
      "empresa": "2",
      "clave_producto_cliente": "S0001",
      "cantidad": 1.0,
      "descuento": 0
    }
  ]
}
```

#### Campos del encabezado

| Campo | Tipo | Notas |
|---|---|---|
| `fecha_ticket` | ISO 8601 | Fecha del último pago registrado. |
| `folio` | string | Folio que el cliente conoce (`OOW-9596`). |
| `web_id` | string | El identificador canónico, con prefijo y sufijo. |
| `tipo_factura` | int | `1` PUE, `2` PPD. |
| `metodo_pago` | string | `PUE` o `PPD` (catálogo `c_MetodoPago`). |
| `forma_pago` | string | `c_FormaPago` de los abonos de ese documento: `03` transferencia, `04` crédito, `28` débito, `99` si en ese bolsillo se mezclaron. `01` solo en efectivo histórico. |
| `moneda` | string | Hoy siempre `MXN`. |
| `subtotal` | number | Importe **antes** de IVA. |
| `tasa_iva` | number | `0.16` para México. |
| `iva` | number | IVA trasladado. |
| `total` | number | `subtotal + iva`. Es lo que se timbra. |

**Todos los importes de `conceptos[].precio` son sin IVA** y son el precio
unitario. El importe de la línea es `cantidad × precio`. El `subtotal` del
encabezado es la suma de esos importes. En una pieza, `cantidad` puede ser
mayor a 1.

**Errores**

| Código | `razon` | Significado |
|---|---|---|
| 400 | `El webId no tiene un formato válido` | Texto sin dígitos o sufijo desconocido. |
| 400 | `hay más de una orden con el mismo folio` | Manden el `webId` con prefijo. |
| 400 | `el folio tiene más de un documento facturable...` | Manden el `webId` con sufijo (`-1`, `-2` o `-3`). |
| 400 | `la venta no tiene pagos validados para facturar` | Todavía no hay dinero verificado. |
| 400 | `la venta no está disponible para autofacturación` | Orden en garantía, cancelada o de sucursal sin facturación. |
| 400 | `la facturación en demanda solo aplica en México` | Se llamó a un host de otro país. |
| 401 | — | Falta API Key o el token expiró. |
| 404 | `No se encontró el folio` | El folio no existe o no tiene ese tipo de documento. |

Formato del cuerpo de error:

```json
{ "mensaje": "Bad Request", "razon": "El webId no tiene un formato válido" }
```

---

### 4.3 `PUT /facturacion-web/folio/{webId}`

Entrega a SIGMA el CFDI ya timbrado.

**Headers:** los mismos del `GET`.

**Body**

```json
{
  "uuid": "A1B2C3D4-E5F6-7890-ABCD-EF1234567890",
  "fechaTimbrado": "2026-09-18T14:35:22",
  "cadenaOriginalSAT": "||1.1|A1B2...||",
  "noCertificadoSAT": "00001000000512345678",
  "noCertificadoCFDI": "00001000000587654321",
  "selloSAT": "Gk3...==",
  "selloCFDI": "Yt9...==",
  "qrCode": "https://verificacfdi.facturaelectronica.sat.gob.mx/...",
  "cfdi": "<?xml version=\"1.0\"?><cfdi:Comprobante ...>",
  "pdf64": "JVBERi0xLjQKJc..."
}
```

| Campo | Obligatorio | Notas |
|---|---|---|
| `uuid` | Sí | Folio fiscal, máximo 36 caracteres. |
| `cfdi` | Sí | XML en texto plano **o** en base64. Ambos se aceptan. |
| `pdf64` | Sí | PDF en base64. Acepta prefijo `data:application/pdf;base64,`. |
| `fechaTimbrado` | No | ISO 8601. Si falta, SIGMA usa la hora de recepción. |
| Resto | No | Se guardan tal cual para auditoría. |

**Respuesta 204 No Content** — sin cuerpo.

**Errores**

| Código | `razon` | Significado |
|---|---|---|
| 404 | `Solo se recibirán datos de facturas timbradas que se hayan solicitado previamente por el método GET` | Falta el `GET` del mismo `webId`. |
| 400 | `Payload de CFDI inválido o incompleto` | Falta `uuid`, `cfdi` o `pdf64`, o el base64 no decodifica. |
| 400 | `la venta ya tiene una factura timbrada` | Ya existe otro UUID para ese documento. |

**Idempotencia:** reenviar el **mismo** `uuid` devuelve `204` otra vez y no
duplica nada. Es seguro reintentar ante un timeout de red.

---

## 5. Límites y seguridad

| Aspecto | Valor |
|---|---|
| Rate limit `authenticate` | 30 peticiones por minuto por IP. |
| Rate limit `folio` (GET/PUT) | 60 peticiones por minuto por IP. |
| Transporte | HTTPS obligatorio. |
| Credenciales | API Key y `secret` se entregan por canal seguro, nunca por correo en texto plano. |
| CSRF | Estos endpoints están exentos (son de servidor a servidor). |

La API Key **nunca** viaja al navegador del cliente. El enlace que SIGMA le
muestra al cliente solo lleva el `webId` como parámetro:

```
http://<portal-vo>/facturador?webId=SAT9596-1
```

---

## 6. Prueba mínima de conectividad

```bash
# 1) Token
curl -s -X POST https://mexico.sigmasystem.work/facturacion-web/authenticate \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"secret":"'"$SECRET"'"}'

# 2) Consultar una venta
curl -s https://mexico.sigmasystem.work/facturacion-web/folio/SAT9596-1 \
  -H "X-API-KEY: $API_KEY" \
  -H "Authorization: Bearer $TOKEN"

# 3) Devolver el CFDI timbrado
curl -s -X PUT https://mexico.sigmasystem.work/facturacion-web/folio/SAT9596-1 \
  -H "X-API-KEY: $API_KEY" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @cfdi_timbrado.json -o /dev/null -w "%{http_code}\n"
```

Una respuesta `204` en el paso 3 cierra el ciclo completo.

---

## 7. Preguntas abiertas con el proveedor

1. **Sufijo del `webId`.** SIGMA lo entrega como `SAT9596-1`. Si el portal no
   acepta el guion, se puede cambiar el separador o quitarlo; es un cambio
   menor de un solo módulo.
2. **Importe del PPD.** Hoy se factura el anticipo ya verificado. Si el SAT o
   el PAC exigen facturar el total de la operación en lugar del anticipo, hay
   que confirmarlo antes de salir a producción.
3. **Catálogo de claves SAT.** Diagnóstico: `81111820`. Limpieza: `72151800`.
   Instalación de partes: `81111814`. Reinstalación de SO: `81111505`.
   Respaldo: `81112218`. Paquetes oro/plata/premium: `43211600`.
   Anticipo: `84111506`. Kit de limpieza: `43211600`.
   Piezas sin clave propia: `01010101`.
   No hace falta que el portal resuelva el catálogo: usa la clave que llega
   en cada concepto.

---

**Última actualización:** Septiembre 2026
**Contacto técnico SIGMA:** equipo de desarrollo interno
