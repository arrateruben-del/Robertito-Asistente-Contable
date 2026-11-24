# Robertito · Asistente contable

Backend del bot de Telegram **[@Elrobertbot](https://t.me/Elrobertbot)** con su
**Telegram Mini App**. Robertito ayuda al estudio contable a:

- 🧾 **Clientes** — calcular una **retención de Ganancias** (Régimen General RG 830 AFIP).
- 📊 **Estudio** — generar el **archivo mensual para SICORE** (retenciones/percepciones de AFIP).

Todo el texto de cara al usuario está en **español rioplatense**.

---

## URLs públicas

- **Bot:** https://t.me/Elrobertbot
- **Mini App (hosteada por nosotros):** https://robertito-bot-ruben.abacusai.cloud/app
- **Webhook:** `https://robertito-bot-ruben.abacusai.cloud/webhook/<secret_path>` (secret en `.env`)
- **Health:** https://robertito-bot-ruben.abacusai.cloud/health

> La Mini App publicada (botones Clientes / Estudio) hace deep-link a
> `t.me/Elrobertbot?start=clientes|estudio`. El **botón de menú** del bot y el
> **web_app button** abren esta Mini App hosteada dentro de Telegram (Telegram
> exige HTTPS, que nuestro dominio provee).

---

## Arquitectura

```
Robertito-Asistente-Contable/
├── bot/                     # Backend del bot
│   ├── app.py               # Servidor FastAPI (webhook + Mini App + /health)
│   ├── config.py            # Config + ESCALA DE RETENCIÓN (parametrizable)
│   ├── retencion.py         # Cálculo de retención de Ganancias (RG 830)
│   ├── sicore.py            # Generador del archivo de importación SICORE (ancho fijo)
│   ├── db.py                # Persistencia SQLite (tabla retenciones)
│   ├── handlers.py          # Lógica de conversación (flujos Clientes / Estudio)
│   └── telegram_api.py      # Cliente mínimo de la Bot API (httpx)
├── webapp/
│   └── index.html           # Mini App (diseño oficial — NO rediseñar)
├── scripts/
│   ├── poblar_env.py        # Genera .env con el token (sin imprimirlo)
│   └── registrar_telegram.py# setWebhook + setChatMenuButton + setMyCommands
├── deploy/
│   ├── robertito-bot.service      # Unit systemd
│   └── robertito-bot-ruben.conf   # Vhost nginx
├── data/                    # SQLite (ignorado por git)
├── requirements.txt
├── .env.example
└── .gitignore
```

**Framework:** FastAPI + Uvicorn en **modo webhook** (no polling), más `httpx`
para llamar a la Bot API. Elegido por ser simple de mantener e integrarse
directamente con nginx, y poder servir la Mini App estática desde el mismo proceso.

**Flujo:** Telegram → nginx (`robertito-bot-ruben.vm.internal`) → Uvicorn (`127.0.0.1:8081`).

---

## Endpoints

| Método | Ruta                      | Descripción                                   |
|--------|---------------------------|-----------------------------------------------|
| POST   | `/webhook/<secret_path>`  | Recibe updates de Telegram (valida secret token) |
| GET    | `/app` y `/`              | Sirve la Mini App (`webapp/index.html`)       |
| GET    | `/health`                 | Healthcheck (`ok`)                            |

El webhook valida el header `X-Telegram-Bot-Api-Secret-Token` contra
`WEBHOOK_SECRET_TOKEN`, y la ruta secreta contra `WEBHOOK_SECRET_PATH`.

---

## Comandos y deep-links del bot

- `/start` — mensaje de bienvenida con teclado inline (Clientes / Estudio) y botón que abre la Mini App.
- `/start clientes` — inicia el flujo de retención de Ganancias.
- `/start estudio` — inicia el flujo del archivo SICORE.
- `/ayuda` — vuelve a mostrar el menú.
- `/cancelar` — cancela la operación en curso.

Dentro de los flujos: `/omitir` (saltar CUIT) y `/actual` (período corriente).

---

## Persistencia

SQLite en `data/robertito.db` (ignorado por git). Tabla:

```sql
retenciones(id, fecha, monto_base, retencion, cuit_opcional, periodo, chat_id, creado_en)
```

Cada cálculo de retención se guarda; el archivo SICORE del período se construye
con esos datos reales acumulados. Si un período no tiene datos, se genera una
**plantilla de ejemplo** con la estructura de registro.

---

## Control de acceso

La Mini App indica *"Acceso disponible para chats habilitados"*. El backend
soporta una **allowlist opcional** de chat IDs vía `ALLOWED_CHAT_IDS` (lista
separada por comas en el `.env`). Si está **vacía, se permite a todos** (no se
bloquea por defecto).

---

## Cómo configurar

1. Crear el venv e instalar dependencias:
   ```bash
   python3 -m venv venv
   ./venv/bin/pip install -r requirements.txt
   ```
2. Generar el `.env` con el token (lo lee del secrets file del VM, sin imprimirlo):
   ```bash
   ./venv/bin/python scripts/poblar_env.py
   ```
   > Alternativa manual: `cp .env.example .env` y completar los valores.
3. Registrar el webhook, el botón de menú y los comandos en Telegram:
   ```bash
   ./venv/bin/python scripts/registrar_telegram.py
   ```

Variables del `.env` (ver `.env.example`): `BOT_TOKEN`, `WEBHOOK_URL`,
`WEBAPP_URL`, `WEBHOOK_SECRET_PATH`, `WEBHOOK_SECRET_TOKEN`, `ALLOWED_CHAT_IDS`,
`PORT`, `CUIT_AGENTE_RETENCION`.

---

## Cómo desplegar

El unit systemd y el vhost nginx viven en `deploy/` y se symlinkean a `/etc`:

```bash
sudo ln -sf $PWD/deploy/robertito-bot.service /etc/systemd/system/robertito-bot.service
sudo ln -sf $PWD/deploy/robertito-bot-ruben.conf /etc/nginx/conf.d/robertito-bot-ruben.conf
sudo systemctl daemon-reload
sudo systemctl enable --now robertito-bot
sudo nginx -t && sudo systemctl reload nginx
```

Verificación:
```bash
systemctl is-active robertito-bot
curl -s -H 'Host: robertito-bot-ruben.vm.internal' http://localhost/health
curl -s -H 'Host: robertito-bot-ruben.vm.internal' http://localhost/app | head
```

---

## Cómo ajustar la escala de retención

Toda la escala está centralizada en `bot/config.py`, en el dict
`ESCALA_RETENCION`. Se puede ajustar sin tocar la lógica:

- `minimo_no_sujeto`: mínimo no sujeto a retención por concepto.
- `tramos`: lista de tramos con `desde`, `hasta`, `fijo`, `alicuota`, `excedente_sobre`.
- `retencion_minima`: importe mínimo por debajo del cual no se retiene.

Fórmula aplicada (Régimen General):

```
base_sujeta = max(0, monto_pago - minimo_no_sujeto)
retencion   = monto_fijo + alicuota * (base_sujeta - excedente_sobre)
```

> ⚠️ Los valores cargados son **ilustrativos** y **deben validarse/actualizarse**
> con la normativa vigente (RG 830 AFIP y sus modificatorias, Anexo VIII).

El diseño de registro del archivo SICORE (campos de ancho fijo y códigos) está
documentado en `bot/sicore.py`; también debe validarse contra el diseño oficial
de AFIP vigente.

---

## Stack

- Python 3.12, FastAPI, Uvicorn, httpx
- SQLite (persistencia)
- nginx (reverse proxy) + systemd (servicio)
