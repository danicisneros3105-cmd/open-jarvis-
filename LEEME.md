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

## Evolución: Sergio se adapta a ti

1. **Aprende en cada conversación.** La memoria (`[memory] enabled = true`, que
   el instalador activa) extrae en segundo plano datos duraderos: tus
   preferencias, cómo te gusta que te hable, personas, rutinas y metas.
2. **Consolida tu perfil.** Una vez al día, al abrir `sergio gui`, reescribe
   `~/.openjarvis/USER.md` con lo aprendido. Cuando dos datos se contradicen,
   gana el más nuevo; los duplicados se fusionan. Ese perfil va en cada
   conversación.
3. **Se puede revisar y deshacer.** Cada versión anterior se guarda como
   `USER.md.<fecha>.bak` (se conservan las 5 últimas). Lo que el escáner de
   seguridad marca como sospechoso nunca entra en tu perfil.

```bash
uv run sergio evolve --show     # evolucionar ahora y ver el perfil
uv run sergio memory list       # ver todo lo que ha aprendido
```

## Mejores respuestas con menos tokens

- **LLMLingua-2** ([microsoft/LLMLingua](https://github.com/microsoft/LLMLingua),
  licencia MIT, gratis) comprime entre 2 y 5 veces los resultados largos de
  páginas web, PDFs y búsquedas antes de pasárselos al modelo. Conserva los
  números (precios, fechas, teléfonos). Nunca toca código, archivos ni
  comandos. Se instala con `./scripts/install-todo-en-uno.sh --ahorro-tokens`
  (unos 2 GB) y se activa con `[compression] tool_output = true`. Si falla,
  Sergio usa el texto original.
- **Ya existía en OpenJarvis:** la compresión de sesiones largas (activa) y un
  enrutador que puede mandar las preguntas simples al modelo pequeño (hay que
  configurarlo). La evolución también ahorra tokens: envía un perfil
  consolidado en lugar de cientos de datos sueltos.

## Llamadas y WhatsApp (siguiente fase)

**Repos gratis que hacen falta** (se añaden como dependencias de Python):

| Repo | Para qué | Licencia |
|---|---|---|
| [pipecat-ai/pipecat](https://github.com/pipecat-ai/pipecat) | Motor de voz en tiempo real: oye, piensa y habla sin pausas en una llamada | BSD-2 |
| [pipecat-ai/pipecat-flows](https://github.com/pipecat-ai/pipecat-flows) | Guiones de conversación paso a paso (reservar una mesa: saludo, fecha, hora, personas, confirmar) para que no se pierda en la llamada | BSD-2 |

**Ya incluidos en Sergio:** WhatsApp (API oficial de Meta en
`channels/whatsapp.py`), voz a texto (faster-whisper) y texto a voz (Kokoro,
con voces en español).

**Lo único que no es gratis es la línea telefónica**, porque ningún software
puede llamar a un teléfono real sin un operador:

- **Una cuenta en Twilio o Telnyx con un número virtual.** Sirve para llamar
  a Ecuador y a otros países. Se paga por minuto según el país de destino.
- **Ese mismo número se registra en WhatsApp Business** (API oficial de Meta).
  Así Sergio tiene su propio WhatsApp sin que necesites el tuyo.
- **Hablar con Sergio desde el navegador** (PC o móvil) no usa línea
  telefónica: es gratis.
- **En toda llamada a terceros, Sergio dice primero que es un asistente de
  IA**, y no marca ningún número sin tu confirmación.

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
