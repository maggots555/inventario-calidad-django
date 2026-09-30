# SIGMA en Docker (rama `dockerizacion`)

Esta guía es para **probar** SIGMA dentro de contenedores. No reemplaza al servidor que hoy está en producción. La rama `master` sigue siendo el proyecto sin Docker.

## Qué vas a levantar

Seis programas, cada uno en su contenedor:

| Servicio | Para qué sirve | ¿Se abre en tu PC? |
|---|---|---|
| `nginx` | Recibe el navegador y entrega CSS, JS y fotos | Sí, puerto **8080** |
| `web` | Django con Gunicorn | No (solo lo ve Nginx) |
| `celery` | Tareas lentas (correos, videos, PDF) | No |
| `celery-beat` | Tareas con horario | No |
| `postgres` | Cuatro bases: México, Argentina, Chile, Colombia | No |
| `redis` | Cola de Celery y caché | No |

Los archivos de la base, las fotos y los logs quedan en la carpeta `docker-data/` de tu laptop. Esa carpeta no se sube a git. Si borras los contenedores, los datos siguen ahí.

## Primer arranque en la laptop

Tu usuario de Linux tiene que poder hablar con Docker. Si `docker info` responde
"permission denied", pide una vez (y vuelve a entrar a la sesión):

```bash
sudo usermod -aG docker "$USER"
```

Después, desde la raíz del proyecto, en la rama `dockerizacion`:

```bash
sh docker/levantar.sh
```

Ese script copia `docker/.env.example` a `docker/.env` si todavía no existe,
y levanta los contenedores. La primera vez tarda: descarga Postgres, Redis y
Nginx, construye la imagen de SIGMA en tu PC y aplica las migraciones en las
cuatro bases.

Esa imagen se llama `sigma-web:local` y solo vive en tu computadora. Compose
no la busca en internet (`pull_policy: build`). Si en un arranque anterior
viste `pull access denied for sigma-web`, era ese intento de descarga: la
página podía abrir igual porque después la imagen se construyó aquí.

Cuando termine, abre [http://localhost:8080/login/](http://localhost:8080/login/). La base está vacía: todavía no hay usuarios. Para crear uno de prueba:

```bash
docker compose --env-file docker/.env exec web python manage.py createsuperuser
```

## Comandos del día a día

```bash
# Ver si están corriendo
docker compose --env-file docker/.env ps

# Ver el arranque de Django (migraciones, errores)
docker compose --env-file docker/.env logs -f web

# Ver el worker de Celery
docker compose --env-file docker/.env logs -f celery

# Apagar sin borrar datos
docker compose --env-file docker/.env down
```

Usa siempre `--env-file docker/.env`. Si omites esa bandera, Compose puede leer el `.env` de la laptop (SQLite) y la base de Docker no va a coincidir.

## Cuando se monte en el servidor `sic-sigma`

IT dejó estas carpetas (no hace falta sudo; el usuario `sigma` ya puede usarlas):

| Qué | Dónde |
|---|---|
| Este `compose.yaml`, el `Dockerfile` y `docker/` | `/srv/sic/apps/sigma` |
| Base, fotos y Redis | `/srv/sic/data/sigma` |
| Respaldos | `/srv/sic/backups/sigma` |

En el servidor, dentro de `docker/.env`:

- `SIGMA_DATA_ROOT=/srv/sic/data/sigma`
- `DEBUG=False`
- `SECRET_KEY` y `DB_PASSWORD` nuevos (no los de esta guía)
- `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` y `SITE_URL` con el dominio real

PostgreSQL y Redis siguen sin publicarse a la red. El acceso público (Cloudflare) es un paso posterior: el servidor viejo se queda encendido hasta que esa prueba salga bien.

No subas `docker/.env` ni `docker-data/` a git.
