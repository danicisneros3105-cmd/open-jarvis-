# Qué puede hacer el asistente (y qué no)

Esta guía repasa la lista de deseos tarea por tarea y dice tres cosas de cada
una: con qué pieza se hace, si funciona ya, y qué riesgos tiene.

**Las piezas:**

- **Sergio** (núcleo OpenJarvis): el chat, la memoria, las tareas programadas y los
  canales. Decide qué hacer.
- **Clacky** (herramienta `clacky_task`): ejecuta en tu ordenador. Tiene
  terminal, archivos, búsqueda web y **control de tu Chrome real**. Sergio te
  pide confirmación antes de cada delegación.
- **Globo** (`globe_view`, `live_flights`, `live_earthquakes`,
  `upcoming_launches`): datos en vivo del mundo y el mapa 3D.

> **Sobre el modelo local:** un modelo de 8B corriendo en una laptop sirve
> para chatear, resumir y organizar. Para tareas largas en el navegador
> (Canva, formularios de varios pasos) usa un modelo por API (`engine =
> "cloud"`). Clacky usa automáticamente el mismo modelo que Sergio.

| Tarea | Con qué | Estado | Notas |
|---|---|---|---|
| Buscar en Google | Clacky (`clacky_task`) o `web_search` de Sergio | ✅ Funciona ya | *"Busca los 5 mejores portátiles para programar por menos de 800 €"* |
| Organizar tus archivos | Clacky (`clacky_task`) | ✅ Funciona ya | Empieza en una carpeta de prueba. Los archivos borrados pasan por una papelera (`trash_manager`). |
| Abrir y cerrar apps, instalar apps | Clacky (`clacky_task`) | ✅ En Linux/WSL | En Linux usa `apt`/`flatpak`. Desde WSL puede llamar a `winget` de Windows. Te pedirá confirmación en los comandos peligrosos. |
| Crear una presentación en Canva desde cero | Clacky + tu Chrome | 🟡 Posible, frágil | Inicia sesión en Canva tú primero; el agente controla tu Chrome. Más fiable: que genere el contenido y lo importe, o que use la [Canva Connect API](https://www.canva.dev/docs/connect/). Necesita modo API. |
| Revisar las stats de tu web | Clacky (navegador) o Sergio (tarea programada) | ✅ / 🟡 | Lo ideal es la API de Google Analytics o Search Console con un informe diario programado. |
| Escribir 100–500 correos personalizados a empresas | Sergio/Clacky (redactan) + tu proveedor de correo | 🟡 Con límites | Redactarlos es fácil. Para enviarlos usa una herramienta de envío masivo (Brevo, Mailgun…), no tu Gmail personal: Gmail bloquea las cuentas que envían en masa. Las leyes antispam (GDPR, CAN-SPAM, LFPDPPP en México…) exigen que el destinatario pueda darse de baja, que quede claro quién envía y, en algunos países, consentimiento previo. Recomendado: el agente prepara un CSV con los borradores, tú los revisas y los envía la herramienta. |
| Responder mensajes de Instagram y publicar videos | API oficial de Meta (cuenta Business/Creator) | 🟡 Requiere configurar | Automatizar Instagram controlando el navegador **viola sus términos y puede costarte la cuenta**. La vía segura es la Instagram Graph API (cuenta profesional + app de Meta). Pendiente de integrar como skill. |
| Llamar a la pizzería y reservar mesa a las 8 pm | Servicio de voz (Twilio + voz realtime, o ElevenLabs Agents) | 🔜 Fase 3 | Tiene coste por minuto y necesita un número de teléfono. En muchos sitios la ley exige que la IA diga que es una IA; el asistente lo hará al inicio de cada llamada. Alternativa simple: reservar por la web de la pizzería u OpenTable con el navegador. |
| Jugar al dinosaurio de Chrome toda la noche y avisarte del récord | Script con el navegador (sin IA, por reglas) | ✅ Fácil | No hace falta IA: basta un bot que detecta obstáculos. Ojo: el juego **no tiene récord mundial oficial** y el marcador se detiene en 99 999. El bot puede avisarte cuando llegue ahí o cuando supere tu propio récord. |
| Revisar tus tareas en la plataforma estudiantil (Moodle, etc.) | Clacky + navegador, o la API de Moodle | ✅ Revisar y avisar | Puede entrar, listar entregas y fechas, avisarte y ayudarte a estudiar o hacer borradores contigo. |
| …completarlas y subirlas solo | — | ❌ No incluido | Entregar como tuyo un trabajo hecho por la IA es fraude académico en casi todas las instituciones, y si te detectan te puede costar la materia. El asistente te ayuda a hacerlas (explicaciones, esquemas, revisión), pero la entrega la haces tú. |

## Cómo se le pide algo

En el chat de `sergio gui`:

- *"Ordena mi carpeta Descargas por tipo de archivo; enséñame antes la lista."*
- *"Entra a canva.com y crea una presentación de 8 diapositivas sobre la fotosíntesis."*
- *"¿Qué aviones pasan ahora sobre mi ciudad? Enséñamelo en el globo."*

## Próximas fases

1. **Hecho**: un núcleo, un comando, una interfaz, un modelo compartido,
   delegación a Clacky y globo controlado desde el chat.
2. **Fase 2**: skills de correo masivo (CSV, revisión y envío por un
   proveedor), informe diario de la web, avisos por Telegram, bot del
   dinosaurio y lector de Moodle.
3. **Fase 3**: llamadas de voz e Instagram con la API oficial; capas del globo
   (aviones, terremotos) dibujadas desde el chat.
