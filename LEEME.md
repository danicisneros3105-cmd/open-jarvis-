# Sergio — tu asistente todo-en-uno

Un solo asistente personal que une el poder de tres proyectos:

| Pieza | Qué aporta | Dónde vive |
|---|---|---|
| **OpenJarvis** (núcleo, Python) | El cerebro: chat, memoria, tareas programadas, skills, voz, canales (Telegram…), IA local con Ollama o por API | `src/openjarvis/` |
| **OpenClacky** (Ruby) | Las manos: usa la terminal, tus archivos y **tu Chrome real** (entra a páginas, hace clic, rellena formularios) | `extensions/clacky/` |
| **God's Eye View** (JS) | Los ojos sobre el mundo: globo 3D con aviones, barcos, satélites y terremotos en vivo | `extensions/globe/` |

No son tres programas sueltos:

- **Un comando** (`sergio gui`) arranca todo, y al cerrarlo se apaga todo.
- **Una interfaz:** Chat, Globe y Clacky son pestañas de la misma app.
- **Un solo cerebro:** Clacky usa automáticamente el modelo que configures en
  Sergio, sea local o por API. No hay que configurarlo dos veces.
- **Una sola configuración:** `~/.openjarvis/config.toml`.
- **Herramientas cruzadas:** desde el chat de Sergio puedes pedir tareas que
  ejecuta Clacky, consultar datos en vivo del mundo y mover el globo.

## Instalar

**Windows 11** (PowerShell como administrador):

```powershell
git clone https://github.com/TU_USUARIO/sergio.git
cd sergio
Set-ExecutionPolicy -Scope Process Bypass; .\scripts\install-windows.ps1
```

**Linux o WSL:**

```bash
git clone https://github.com/TU_USUARIO/sergio.git ~/sergio
cd ~/sergio && ./scripts/install-todo-en-uno.sh
```

## Usar

```bash
uv run sergio gui                    # abre la app completa
uv run sergio extensions status      # estado de Clacky y del globo
uv run sergio extensions logs clacky # qué está haciendo Clacky
uv run sergio gui --no-extensions    # solo OpenJarvis
```

Ejemplos de cosas que puedes pedir en el chat:

- *"Muéstrame Tokio en visión nocturna"*: usa la herramienta `globe_view` y
  la pestaña Globe vuela hasta allí.
- *"¿Qué aviones pasan ahora sobre Madrid?"*: usa `live_flights`, con datos
  ADS-B en vivo.
- *"¿Hubo terremotos fuertes hoy cerca de México?"*: usa `live_earthquakes`
  (USGS).
- *"¿Cuándo es el próximo lanzamiento de SpaceX?"*: usa `upcoming_launches`.
- *"Organiza mi carpeta Descargas por tipo de archivo"*: usa `clacky_task`.
  Sergio te pide confirmación y Clacky lo ejecuta.

Para activar esas herramientas en un agente, añádelas a su lista de tools:

```toml
[tools]
enabled = ["web_search", "file_read", "clacky_task", "globe_view",
           "live_flights", "live_earthquakes", "upcoming_launches"]
```

## Configuración (`~/.openjarvis/config.toml`)

```toml
[intelligence]
default_model = "qwen3:8b"        # local con Ollama
# default_model = "claude-sonnet-5-5"   # por API (con engine "cloud" y ANTHROPIC_API_KEY)

[engine]
default = "ollama"                # o "cloud"

[extensions]
autostart = true                  # arrancar Clacky y el globo con `sergio gui`

[extensions.clacky]
enabled = true
port = 7070
timeout_seconds = 900             # tiempo máximo por tarea delegada

[extensions.globe]
enabled = true
port = 4173

[analytics]
enabled = false
```

Clacky lee el modelo de esta misma configuración:

| Motor de OpenJarvis | Cómo se conecta Clacky |
|---|---|
| `ollama` | A Ollama por su API compatible con OpenAI. |
| `vllm`, `sglang`, `llamacpp`, `lmstudio` | Al endpoint `/v1` de ese motor. |
| `cloud` con modelo `claude-*` | A Anthropic, con `ANTHROPIC_API_KEY`. |
| `cloud` con modelo `openrouter/...` | A OpenRouter, con `OPENROUTER_API_KEY`. |
| `cloud` con modelo `gemini-*` | A Google, con `GEMINI_API_KEY` o `GOOGLE_API_KEY`. |
| `cloud` con cualquier otro modelo | A OpenAI, con `OPENAI_API_KEY`. |

## Problemas que arregla la unión

- **Telemetría:** la de Clacky queda siempre apagada (`CLACKY_TELEMETRY=0`) y
  el instalador apaga también la analítica de OpenJarvis.
- **Embeber el globo:** el globo prohibía que otra página lo mostrara (CSP
  `frame-ancestors 'none'`). Ahora acepta solo a la interfaz local de Sergio
  (`GLOBE_FRAME_ANCESTORS`, limitado a orígenes loopback) y sigue bloqueando
  cualquier otro sitio.
- **Configuración duplicada:** antes cada proyecto tenía su propia
  configuración de modelo; ahora hay una sola.
- **Arranque manual:** antes había que lanzar tres servicios a mano; ahora el
  supervisor (`src/openjarvis/unified/`) los arranca, comprueba que responden
  y los detiene juntos.

## Estado y límites

- Comprobado en Linux: `sergio extensions start` levanta Clacky y el globo.
  `clacky_task` delega una tarea real a Clacky usando el modelo de OpenJarvis.
  Las pestañas Globe y Clacky se muestran dentro de la app, y el globo aplica
  la vista que pide el chat.
- `live_flights`, `live_earthquakes` y `upcoming_launches` están probadas con
  respuestas simuladas. Contra las APIs reales hay que probarlas en tu laptop.
- `clacky_task` da a Clacky control total del ordenador mientras dura la
  tarea, por eso Sergio pide confirmación antes de cada delegación.
- Qué tareas son viables y sus límites legales (correos masivos, Instagram,
  llamadas, tareas escolares): [docs/es/CAPACIDADES.md](docs/es/CAPACIDADES.md).

## Mantener al día

Los tres proyectos originales siguen mejorando. Para traer sus cambios:

```bash
git subtree pull --prefix=extensions/clacky https://github.com/clacky-ai/openclacky.git main --squash
git subtree pull --prefix=extensions/globe  https://github.com/bilawalsidhu/gods-eye-view.git main --squash
git pull https://github.com/open-jarvis/OpenJarvis.git main
```
