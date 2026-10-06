# SIGMA en Docker

SIGMA en producción corre en Docker, en el servidor **sic-sigma**. La misma receta sirve para probar en la laptop. Los secretos (claves, token del túnel, token de Drive) viven solo en `docker/.env` de cada máquina. Ese archivo no se sube a git.

Hasta que la rama `dockerizacion` se una a `master`, sic-sigma sigue en `dockerizacion`.

## Qué se levanta

Siete programas. Solo Nginx abre un puerto. Postgres y Redis se quedan en la red interna `sigma_interna`.

| Servicio | Para qué sirve | ¿Se publica? |
|---|---|---|
| `nginx` | Recibe el navegador y entrega CSS, JS y fotos | Sí, puerto `SIGMA_HTTP_PORT` (8080 si no se cambia) |
| `web` | Django con Gunicorn. Al arrancar migra y junta estáticos | No |
| `celery` | Correos, videos, PDF | No |
| `celery-beat` | Tareas con horario | No |
| `postgres` | Cuatro bases, una por país | No |
| `redis` | Cola `/0`, resultados `/1`, caché `/2` | No |
| `cloudflared` | Túnel hacia Cloudflare. Solo con el perfil `cloudflare` | No abre puertos. Cloudflare entra a `http://nginx:80` |

La imagen de la aplicación se llama `sigma-web:local`. Se construye en la máquina. No existe en Docker Hub. `web`, `celery` y `celery-beat` usan esa misma imagen.

## Dónde está cada cosa

| | Laptop | sic-sigma |
|---|---|---|
| Código y `compose.yaml` | carpeta del proyecto | `/srv/sic/apps/sigma` |
| Base, fotos, estáticos, logs | `docker-data/` (no va a git) | `/srv/sic/data/sigma` |
| Respaldos `.sql.gz` | no aplica | `/srv/sic/backups/sigma` |
| Variables | `docker/.env`, copiado del ejemplo | `docker/.env` del servidor. `DEBUG=False` |

`SIGMA_DATA_ROOT` en la laptop es `./docker-data`. En sic-sigma es `/srv/sic/data/sigma`.

## Bases de datos

Dentro de Docker los nombres son:

| País | Base | Alias de Django |
|---|---|---|
| México | `inventario_mexico` | `default` y `mexico` (es la misma base) |
| Argentina | `inventario_argentina` | `argentina` |
| Chile | `inventario_chile` | `chile` |
| Colombia | `inventario_colombia` | `colombia` |

En el servidor anterior, la base de México se llama `inventario_django`. Ese nombre no se usa en sic-sigma.

La primera vez que el disco de Postgres está vacío, `docker/postgres-init.sh` crea Argentina, Chile y Colombia. Si el disco ya tiene datos, ese script no vuelve a correr. Al arrancar, el contenedor `web` aplica migraciones en `default`, `argentina`, `chile` y `colombia`, y corre `collectstatic`. No migra `mexico` otra vez.

## Probar en la laptop

Tu usuario tiene que poder usar Docker. Si `docker info` dice "permission denied":

```bash
sudo usermod -aG docker "$USER"
```

Cierra la sesión y vuelve a entrar. Después, en la raíz del proyecto:

```bash
sh docker/levantar.sh
```

Ese script copia `docker/.env.example` a `docker/.env` si todavía no existe, y levanta los contenedores. La primera vez descarga Postgres, Redis y Nginx, construye la imagen y aplica las migraciones. La base queda vacía.

Abre [http://localhost:8080/login/](http://localhost:8080/login/). Para crear un usuario de prueba:

```bash
docker compose --env-file docker/.env exec web python manage.py createsuperuser
```

Usa siempre `--env-file docker/.env`. Si lo omites, Compose puede leer el `.env` de la raíz, que es el de SQLite, y la base no coincide.

```bash
docker compose --env-file docker/.env ps
docker compose --env-file docker/.env logs -f web
docker compose --env-file docker/.env logs -f celery
docker compose --env-file docker/.env down
```

`down` apaga los contenedores y no borra `docker-data/`.

El túnel no se levanta en la laptop. Hace falta el perfil y un token, y el token solo está en el servidor:

```bash
docker compose --env-file docker/.env --profile cloudflare up -d
```

## Cómo se actualiza sic-sigma

El código de Django va dentro de la imagen. Un `git pull` no cambia lo que ya está corriendo hasta que se reconstruye.

En `/srv/sic/apps/sigma`, si cambió Python, plantillas, CSS, JavaScript o `requirements-docker.txt`:

```bash
git pull
docker compose --env-file docker/.env --profile cloudflare up -d --build web celery celery-beat
```

`--build` vuelve a armar la imagen. Sin esa bandera, Compose reutiliza `sigma-web:local` aunque el código en disco sea nuevo. Al encender, `web` migra y junta los estáticos. No hace falta correr `collectstatic` a mano ni activar un entorno virtual: en este servidor no hay `venv`.

Si solo cambió `docker/.env` (un host, una clave):

```bash
docker compose --env-file docker/.env --profile cloudflare up -d --force-recreate web celery celery-beat
```

Eso crea contenedores nuevos con las variables nuevas y no reconstruye la imagen. `restart` enciende el mismo contenedor y se queda con las variables viejas.

Si no cambió nada y solo quieres reiniciar:

```bash
docker compose --env-file docker/.env restart web celery
```

`--profile cloudflare` mantiene el túnel en el mismo proyecto. Los comandos de arriba no llevan secretos: los leen de `docker/.env`.

Logs de Gunicorn y Celery:

```bash
docker compose --env-file docker/.env logs -f --tail 50 web
docker compose --env-file docker/.env logs -f --tail 50 celery
```

Los de Django están en `/srv/sic/data/sigma/logs/`.

## Fotos

En disco quedan en `media/mexico`, `media/argentina`, `media/chile` y `media/colombia`, dentro de `SIGMA_DATA_ROOT`. El contenedor las ve en `/app/media`.

No pongas en `docker/.env` la ruta del servidor anterior (`/mnt/django_storage/media`). Esa carpeta no existe dentro del contenedor.

Celery y Beat montan la carpeta de estáticos en solo lectura. Con `DEBUG=False` la necesitan para arrancar. Si se quita, fallan al buscar el favicon.

## Respaldo de las 3:00

El cron del servidor ejecuta `docker/backup_sigma.sh`. El reloj de sic-sigma es hora de México, así que `0 3 * * *` son las 3:00 de la mañana. No uses las 9:00 pensando que el host está en UTC.

Ese script:

1. Volcado de las cuatro bases a `/srv/sic/backups/sigma`.
2. Sube esos `.sql.gz` a Drive, carpeta `SIGMA-Backups/postgresql`.
3. Sube fotos nuevas de los cuatro países a `SIGMA-Backups/media/<país>`.

Usa `rclone copy`. Copia lo que falta o cambió. No borra en Drive una foto que todavía no esté en este disco. El log queda en `/srv/sic/data/sigma/logs/backup_sigma.log` y cierra con `=== Respaldo terminado ===`.

Un cambio en ese script llega con `git pull`. No hace falta `--build`: el cron lee el archivo del disco.

No apuntes este cron a `scripts/backup_postgres.sh`. Ese script es del servidor anterior y solo vuelca `inventario_django`.

Celery Beat es otra cosa. Corre dentro del contenedor, en UTC. Un horario `hour=8` en Django son las 02:00 en México.

## Túnel

Los hostnames públicos están en el túnel `sic-sigma`: `mexico`, `argentina`, `chile`, `colombia` y el dominio sin subdominio `sigmasystem.work`. En Cloudflare el servicio es HTTP hacia `nginx:80`.

El token se llama `CLOUDFLARE_TUNNEL_TOKEN` y solo existe en el `docker/.env` del servidor. No se copia a la guía, al chat ni a git. El túnel del servidor anterior no se reutiliza.

`ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS` del servidor incluyen esos dominios. Si falta uno, Django responde que el host no está permitido. Se agrega en `docker/.env` y se recrean `web`, `celery` y `celery-beat` sin `--build`.

## Qué no hacer

- No subir `docker/.env`, `docker-data/` ni la configuración de rclone.
- No publicar el puerto de Postgres ni el de Redis.
- No hacer `git pull` ni reiniciar Gunicorn en el servidor anterior como si ahí siguiera la página. Ese equipo queda encendido mientras se observa sic-sigma. Su cron de respaldo está comentado a propósito: si vuelve a correr, puede subir la base atrasada.
- No mezclar esta guía con reglas de agentes. Esas viven en `AGENTS.md`, sección 12.
