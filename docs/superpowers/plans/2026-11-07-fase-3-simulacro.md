# Fase 3 + simulacro de social · Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que enlaces, cadenas y repaso sean fiables (mismo baile, agarre elegido, el social cuenta como repaso, «atrasada» ≠ «olvidada»), convertir cada bloqueo en una pregunta para clase, que el conteo se oiga en el iPhone, y añadir el **simulacro de social**: decidir una salida desde una posición al azar antes del siguiente 1.

**Architecture:** Todo sigue en `index.html` (un IIFE). Se añade un baile seleccionado (`baileSel`) que filtran todas las funciones de enlaces; el generador de cadenas pasa a ser una función pura (`buildChain`) que reutiliza el simulacro; las preguntas para clase son una colección nueva (`S.preguntas`, migración 6→7); el simulacro es una hoja nueva que usa el conteo de Web Audio que ya existe (`cntAudio`, `cntLoad`, `cntPlay`) y actualiza el repaso de enlaces (`S.linkRep` vía `nextRep`).

**Tech Stack:** HTML/CSS/JS sin dependencias; Python 3 + Playwright 1.64 (Chromium; WebKit en CI no bloqueante).

**Spec:** `docs/superpowers/specs/2026-11-07-hoja-de-ruta.md` (fase 3: E1, E2, L1, L7, V4, V5; fase 4: L3; decisiones D4 y D5 aprobadas).

## Global Constraints

- Ninguna dependencia nueva ni archivo de app nuevo (todo en `index.html`; `sw.js` solo cambia `VERSION`).
- `SCHEMA` pasa de `6` a `7` **solo** en la Tarea 4 (preguntas para clase), con su paso en `MIGRATIONS` y prueba de migración. Ninguna otra tarea cambia la forma de los datos salvo campos opcionales que las versiones anteriores conservan (`log.repAntes`).
- D4 (aprobada): una figura marcada en un social cuenta como un repaso «Fluida», **como máximo una vez por día** por figura.
- D5 (aprobada): las cadenas incluyen figuras «en práctica», **señaladas**, con un interruptor «Solo seguras».
- Se conservan todas las funciones actuales. Las 89 pruebas siguen pasando; una prueba existente solo cambia si esta fase cambia a propósito lo que comprueba, y se dice en el informe y en el commit.
- Figuras sin `baile` cuentan como `"Bachata"`.
- Textos de la interfaz en español, tono actual. Accesibilidad como en el resto de la app: botones con texto o `aria-label`, `aria-pressed` en interruptores, avisos con `announce`.
- Toda interpolación de datos guardados en HTML va con `esc()`.
- Commits pequeños, uno por tarea, con las líneas de atribución de la sesión. Sin identificadores de modelo en el código.
- Pruebas: `CHROME=/opt/pw-browsers/chromium python3 tests/test_bachateca.py` (o la venv del scratchpad). Cada prueba nueva termina con `assert not errors, errors`.

## Review Focus

1. Usuario con figuras solo de bachata (el caso normal) → no ve ningún selector de baile ni cambia nada de lo que ve hoy. (Tarea 1: `un_solo_baile_sin_selector`)
2. Borrar un registro de social que contó como repaso → el repaso de esas figuras vuelve a como estaba; y deshacer el borrado lo vuelve a aplicar. (Tarea 3: `borrar_social_deshace_el_repaso`)
3. Importar una copia de la versión 1.50 (sin `preguntas`) o restaurar una instantánea antigua → migra a 7 sin perder nada; una copia de la 1.51 en una app 1.50 se rechaza (ya lo hace por `schema`). (Tarea 4: `migracion_7_preguntas`, `importar_preguntas`)
4. Simulacro con una posición sin salidas → no se queda colgado: lo dice y apunta la pregunta para clase. (Tarea 7: `simulacro_posicion_sin_salida`)
5. Cerrar la hoja del simulacro a mitad (o bloquear la pantalla) → el conteo se para y no queda sonando. (Tarea 7: `simulacro_cerrar_para_el_conteo`)

---

### Tarea 1: Enlaces del mismo baile (E1)

**Files:**
- Modify: `index.html` — `canFollow` y `exitsFrom` (~886-895), `arrivals`, `linkPositions`, `dueLinks`, `coverage` (~1857), `renderEnlazar` (~1861), `makeChain` (~1920), `renderSocial` (~1962), `socialFootwork`, `showBlock` (~2020), `graphHTML`, `trainPlan` (~1518), `nextFrom`, `openView` («Y después»)
- Test: `tests/test_bachateca.py` (sección nueva «# ---- fase 3»)

**Interfaces:**
- Produces:
  - `const baileOf = f => f.baile || "Bachata";`
  - `const LS_BAILE = "bachateca.baile"; let baileSel = lsGet(LS_BAILE) || "Bachata";`
  - `const bailes = () => string[]` — bailes distintos de las figuras usables, ordenados con «Bachata» primero.
  - `canFollow(p, n)` además exige `baileOf(p) === baileOf(n)`.
  - `exitsFrom(pos, hold, excl)` y `arrivals(pos)` filtran por `baileOf(f) === baileSel`. (Todo lo que se apoya en ellas — cobertura, mapa, Social, bloqueo, repaso de enlaces, entreno — queda filtrado.)
  - `function baileChipsHTML(): string` — grupo de botones `data-baile="…"` con `aria-pressed`, que **solo se pinta si `bailes().length > 1`**; se muestra arriba de Enlazar y de Social. Al tocarlo: `baileSel = …; lsSet(LS_BAILE, …); chain = null; linkPos = null; render()`.
  - Si `baileSel` ya no existe entre `bailes()`, vuelve a `"Bachata"` (o al primero).
  - En `window.__bachateca`: `setBaile(b)`.

- [ ] **Step 1: Escribir las pruebas que fallan.**
  - `cadena_no_mezcla_bailes`: figuras Bachata A (Cerrada→Abierta 2 manos) y Salsa S (Abierta 2 manos→Cerrada), ambas en práctica; 30 veces `makeChain("Cerrada")` → ningún paso es S. Con `setBaile("Salsa")`, `exitsFrom("Abierta 2 manos")` contiene S y no A.
  - `social_y_enlazar_por_baile`: con figuras de los dos bailes, Enlazar y Social muestran `[data-baile]` con 2 botones; Social (con «Incluir las que están en práctica») no lista la figura de salsa mientras `baileSel` es Bachata; tras tocar «Salsa», sí.
  - `un_solo_baile_sin_selector`: solo figuras de bachata (sin campo `baile`) → `[data-baile]` no existe en Enlazar ni en Social, y las cadenas funcionan como antes.
- [ ] **Step 2: Ejecutar.** Esperado: FALLAN las dos primeras.
- [ ] **Step 3: Implementar** según las interfaces.
- [ ] **Step 4: Ejecutar** las nuevas y la batería. Esperado: todo verde (incluidas `cadenas_validas` y `enlaces_por_posicion_y_agarre`).
- [ ] **Step 5: Commit** «Enlaces y cadenas del mismo baile».

### Tarea 2: Cadenas con el agarre elegido, avisos y «Solo seguras» (E2, D5)

**Files:**
- Modify: `index.html` — `makeChain` → `buildChain` (~1920), `renderChain` (~1936), botón `data-act="chain"` (~3870 en la versión anterior; búscalo), `renderEnlazar`
- Test: `tests/test_bachateca.py`

**Interfaces:**
- Consumes: `canFollow`, `baileOf`, `baileSel` (Tarea 1).
- Produces:
  - `function buildChain(pool, {start, hold = "", strict = false, n = 4}, rnd = Math.random): {steps}` — función pura: no lee `S` ni el DOM. Primer paso: `f.entrada === start && holdFits(hold, f.agarreIn, strict)`; siguientes: `canFollowStrict(prev, f, strict)`. Sin repetir figuras. Pasos iguales a los de hoy (`{f}` o `{dead, hold, usedUp}`).
  - `const holdFits = (a, b, strict) => strict ? (!!a && !!b && a === b) : holdOk(a, b);`
  - `makeChain(start)` queda como envoltorio: `pool` = figuras `usable && placed` del `baileSel`, filtradas a `ready` si `chainSafe`; llama a `buildChain(pool, {start, hold: linkHold, strict: chainStrict})`.
  - `const LS_CHAIN = "bachateca.cadena"; let {safe: chainSafe = false, strict: chainStrict = false} = lsGet(LS_CHAIN) || {};`
  - Dos interruptores en «Practicar enlaces»: `data-chainopt="safe"` «Solo seguras» y `data-chainopt="strict"` «Agarres exactos», con `aria-pressed`; al tocar, se guardan y se genera otra cadena.
  - En `renderChain`, cada paso con figura añade: `· en práctica` si `!ready(f)`; y `· agarre sin indicar` si el enlace con el paso anterior (o con `hold` en el primero) dependió de un agarre vacío (`!a || !b`).
  - En `window.__bachateca`: `buildChain`.

- [ ] **Step 1: Escribir las pruebas que fallan.**
  - `cadena_respeta_el_agarre_elegido`: desde «Abierta 2 manos» hay F1 (agarreIn «Dos manos») y F2 (agarreIn «Izq–der»); con `linkHold = "Izq–der"` (tocando el chip de agarre en Enlazar) y «Generar cadena», el primer paso es siempre F2 (20 veces vía `buildChain` con el mismo `hold`).
  - `cadena_agarres_exactos`: con `strict: true`, una figura sin `agarreIn` nunca sigue a otra (`buildChain` 30 veces); sin `strict`, sí puede.
  - `cadena_solo_seguras_y_avisos`: con «Solo seguras» activo, ningún paso tiene `!ready(f)`; sin él, una figura en práctica aparece con el texto «en práctica»; una figura sin agarre aparece con «agarre sin indicar».
  - `buildChain_es_pura`: `buildChain(pool, {start: "Cerrada"}, () => 0)` dos veces da los mismos ids (determinista con `rnd` fijo).
- [ ] **Step 2: Ejecutar.** Esperado: FALLAN.
- [ ] **Step 3: Implementar** según las interfaces.
- [ ] **Step 4: Ejecutar** las nuevas y la batería. Esperado: todo verde.
- [ ] **Step 5: Commit** «Cadenas con el agarre elegido, solo seguras y avisos».

### Tarea 3: El social cuenta como repaso; «atrasada» no es «olvidada» (L1, D4)

**Files:**
- Modify: `index.html` — `saveLog` (~2135), `deleteLog` (~2151), `memState` (~1506), `MEM`, `MEM_ORDER`, `renderInicio` (porcentaje «Figuras que recuerdas» y etiquetas), CSS (una clase `t-amber` junto a `.t-grey` ~559 y su variante de tema claro ~729)
- Test: `tests/test_bachateca.py`

**Interfaces:**
- Produces:
  - En `saveLog`, para cada figura marcada que sea `usable` y cuyo `rep.last !== l.fecha`: guarda `l.repAntes[id] = clone(f.rep || null)` y aplica `f.rep = nextRep(f.rep, "fluida")` con `f.rep.last = l.fecha` (no `todayStr()`, por los socials registrados otro día). Las incompletas no cambian su repaso (siguen cada día). `S.actividad[l.fecha]` suma 1 si al menos una figura contó.
  - `deleteLog`: para cada `id` de `l.repAntes`, si la figura existe y `f.rep.last === l.fecha`, restaura `f.rep = l.repAntes[id]`. El «Deshacer» del borrado vuelve a aplicar exactamente lo que había antes de borrar (guarda los `rep` que quitó).
  - `memState(f)`: `"olvidada"` solo si `(step 0 && fallos > 0)`; nuevo `"atrasada"` si `r.due < todayStr(-3)` (y no es olvidada); luego `dominada`/`inestable` como hoy.
  - `MEM.atrasada = ["Atrasada", "t-amber"]`; `MEM_ORDER = {olvidada:0, atrasada:1, inestable:2, nueva:3, dominada:4}`.
  - Inicio: «Figuras que recuerdas» cuenta todo lo que no es `olvidada`; la etiqueta de atrasadas sale aparte (`N atrasadas`, `t-amber`).

- [ ] **Step 1: Escribir las pruebas que fallan.**
  - `social_cuenta_como_repaso`: figura F en práctica con `rep {step:1, due: hoy}`; marcarla en Social y guardar el registro → `rep.step == 2`, `rep.last == fecha del registro`, `rep.due == todayStr(7)`; registrar otro social el mismo día con F → `rep.step` sigue en 2.
  - `borrar_social_deshace_el_repaso`: tras lo anterior (un solo registro), borrar el registro → `rep` vuelve a `{step:1, due: hoy}`; «Deshacer» → `rep.step == 2` otra vez.
  - `atrasada_no_es_olvidada`: figura con `rep {step:3, due: hace 5 días, fallos:0, last: hace 20 días}` → `memState` = `"atrasada"` (vía un gancho `memState` en `__bachateca`) y la tarjeta de Repertorio dice «Atrasada», no «Olvidada»; figura con `step 0, fallos 1` → «Olvidada».
- [ ] **Step 2: Ejecutar.** Esperado: FALLAN.
- [ ] **Step 3: Implementar** según las interfaces (exponer `memState` en los ganchos).
- [ ] **Step 4: Ejecutar** las nuevas y la batería. Si alguna prueba existente de Inicio dependía de «olvidada» por retraso, ajustarla y explicarlo.
- [ ] **Step 5: Commit** «El social cuenta como repaso; atrasada no es olvidada».

### Tarea 4: Preguntas para clase (L7, SCHEMA 7)

**Files:**
- Modify: `index.html` — `SCHEMA`/`MIGRATIONS` (~1040), `applyData`, `exportData` (~3858), `sanitizeImport` (~3889) e `importData` (fusión), `saveLog`, `saveFigure`, `renderInicio`, `openLog` (panel «Dónde te bloqueas»)
- Test: `tests/test_bachateca.py`

**Interfaces:**
- Produces:
  - Datos: `S.preguntas = {[id]: {id, pos, baile, creada: "YYYY-MM-DD", resuelta?: "YYYY-MM-DD", figId?: string}}`.
  - Migración 6→7: `c.preguntas` = objeto (si falta); y por cada posición con `bloqueo` en `c.logs` en los últimos 60 días, una pregunta abierta (una por posición, `creada` = fecha del último bloqueo, `baile: "Bachata"`). Repetible sin duplicar (no crea si ya hay una abierta para esa posición).
  - `function askFor(pos): void` — crea una pregunta abierta para `pos` y `baileSel` si no existe ya una abierta igual; `persist({t:"meta"})`.
  - `saveLog` llama a `askFor(l.bloqueo)` si hay bloqueo.
  - `saveFigure`: si la figura es `usable && placed` y existe una pregunta abierta con `pos === f.entrada` y mismo baile, y la figura es nueva o acaba de pasar a usable → `toast("¿Responde a tu pregunta desde ${pos}?", {label: "Sí", fn: () => resolve(id, f.id)})`.
  - `function resolveQuestion(id, figId?)`: pone `resuelta = todayStr()` y `figId`.
  - Inicio: panel «Para tu próxima clase» con cada pregunta abierta: «Desde ${pos}, ¿qué figura sencilla puedo hacer?», botón `data-act="q-done" data-id` «Ya tengo salida» (resuelve con Deshacer) y `data-act="q-del"` «Quitar» (con Deshacer). Si no hay abiertas, no se pinta.
  - `exportData` incluye `preguntas`. `sanitizeImport` valida cada pregunta (objeto, `ID_RE` en `id`, `pos` texto no vacío, fechas `YYYY-MM-DD` o se quitan) y cuenta descartadas. `importData`: «Añadir» añade las que faltan por `id`; «Reemplazar» las sustituye.

- [ ] **Step 1: Escribir las pruebas que fallan.**
  - `migracion_7_preguntas`: `migrate` de datos con `schema: 6` y dos logs con bloqueo en «Sombra» (hace 10 y 3 días) y uno en «Cerrada» hace 90 días → una sola pregunta abierta, para «Sombra», `creada` = hace 3 días; repetir `migrate` no cambia nada; `SCHEMA == 7`.
  - `bloqueo_crea_pregunta_y_figura_la_resuelve`: registrar un social con bloqueo en «Sombra» → Inicio muestra «Desde Sombra, ¿qué figura sencilla puedo hacer?»; registrar otro bloqueo en «Sombra» no la duplica; guardar una figura nueva en práctica de Sombra→Cerrada → aviso con «Sí»; pulsarlo → la pregunta tiene `resuelta` y `figId`, y desaparece de Inicio.
  - `importar_preguntas`: exportar con una pregunta, borrarla, importar con «Añadir» → vuelve; una pregunta con `id` inválido en la copia se descarta y se cuenta.
- [ ] **Step 2: Ejecutar.** Esperado: FALLAN.
- [ ] **Step 3: Implementar** según las interfaces. Revisar las pruebas existentes que comprueban `SCHEMA` o el `schema` exportado: deben seguir pasando porque leen `SCHEMA` del gancho.
- [ ] **Step 4: Ejecutar** las nuevas y la batería. Esperado: todo verde.
- [ ] **Step 5: Commit** «Preguntas para clase a partir de los bloqueos».

### Tarea 5: El conteo se oye en el iPhone (V4)

**Files:**
- Modify: `index.html` — `cntAudio` (~2238), `rcStart`, `rcCleanup`
- Test: `tests/test_bachateca.py`

**Interfaces:**
- Produces: `function setAudioSession(type: "playback" | "play-and-record" | "auto"): void` — si existe `navigator.audioSession`, pone `navigator.audioSession.type = type` dentro de `try`. `cntAudio()` llama a `setAudioSession("playback")` al crear el contexto; `rcStart` llama a `setAudioSession(rc.mic ? "play-and-record" : "playback")` antes de `resume()`; `rcCleanup` vuelve a `"auto"`.

- [ ] **Step 1: Escribir la prueba que falla.** `conteo_pide_sesion_de_audio` (marcarla `solo_chromium="cámara y micrófono simulados"`): `init` define `navigator.audioSession = {type: "auto"}` con un setter que guarda el historial en `window.__as`; abrir «Grabarme con conteo», grabar 1 s, parar → `__as` contiene `"play-and-record"` y termina en `"auto"`.
- [ ] **Step 2: Ejecutar.** Esperado: FALLA.
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Ejecutar** la nueva y la batería. Esperado: todo verde.
- [ ] **Step 5: Commit** «Conteo audible con el iPhone en silencio».

### Tarea 6: Copia en memoria solo para el vídeo que la necesita (V5)

**Files:**
- Modify: `index.html` — `vidObjUrl` (~1143), el manejador de error de `hydrateVideos` (paso «mem»), `vidMode`
- Test: `tests/test_bachateca.py`

**Interfaces:**
- Produces:
  - `const LS_VIDMEM = "bachateca.vidmem";` — lista de ids de vídeo que necesitaron la copia en memoria (máximo 200, los más recientes).
  - `vidObjUrl(id)` usa `vidMemUrl` solo si `id` está en esa lista **o** si `LS_VIDMODE` es `"mem"` (dispositivos que ya lo tenían guardado: se respeta).
  - Cuando el paso «mem» hace que un vídeo cargue, se añade su id a `LS_VIDMEM` **en vez de** guardar `"mem"` como modo global. Los modos `"frag"`/`"plain"` siguen siendo globales como hoy.
  - En `window.__bachateca`: `vidUrlKind(id): "mem" | "blob" | null` (de una marca guardada junto a cada URL en `vidCache`).

- [ ] **Step 1: Escribir la prueba que falla.** `copia_en_memoria_solo_para_ese_video`: `LS_VIDMEM = ["v1"]`, dos figuras con vídeos `v1` y `v2` (fixture real); abrir las dos fichas → `vidUrlKind("v1") == "mem"`, `vidUrlKind("v2") == "blob"`, ambos sin error.
- [ ] **Step 2: Ejecutar.** Esperado: FALLA.
- [ ] **Step 3: Implementar.** `videos_como_copia_en_memoria` (modo global antiguo) debe seguir pasando sin cambios.
- [ ] **Step 4: Ejecutar** la nueva y la batería. Esperado: todo verde.
- [ ] **Step 5: Commit** «Copia en memoria solo para el vídeo que la necesita».

### Tarea 7: Simulacro de social (L3)

**Files:**
- Modify: `index.html` — hoja nueva (junto a las de grabación), botón en Social y panel en Repasar, manejador de clics, ganchos de prueba, CSS mínimo (reutilizar `.bk-pulse`, `.flash`, `.grade` donde sirvan)
- Test: `tests/test_bachateca.py`

**Interfaces:**
- Consumes: `exitsFrom`, `arrivals`, `baileSel` (Tarea 1); `askFor` (Tarea 4); `cntAudio`, `cntLoad`, `cntPlay`, `setAudioSession` (Tarea 5); `nextRep`, `S.linkRep`, `askWake`/`releaseWake`.
- Produces:
  - Estado `let sim = null; // {rondas, i, bpm, voz, t0, nodes, raf, timeout, cola:[{pos, hold}], res:[{pos, hold, beats|null, g}], fase:"decide"|"revela"|"fin"}`.
  - `function simPositions(): Array<{pos, hold, w}>` — posiciones del `baileSel` con salidas o con llegadas; `hold` = un agarre de llegada al azar entre los de `arrivals(pos)` (o `""`); peso `w = 1 + (pos === último bloqueo ? 2 : 0) + (salidas seguras < 2 ? 1 : 0) + (pregunta abierta ? 1 : 0)`.
  - `function openSim(): void` — hoja `data-sim` con: título «Simulacro de social», texto «Te digo dónde estás mientras suena el pulso. Decide una salida antes del siguiente 1.», selector de rondas (6 / 10, `data-simn`), golpes por minuto (`input#sim-bpm`, 90–150, por defecto la media de `pulsoBpm` de las figuras con pulso marcado, o 120), sonido Voz/Pitidos, botón «Empezar» (`#sim-go`). Si `simPositions()` está vacío: mensaje «Aún no tienes posiciones con salidas. Añade dónde empiezan y acaban tus figuras.» y sin botón.
  - Ronda (`fase "decide"`): muestra «Estás en» + posición + agarre (`holdName`) y un botón grande «La tengo» (`#sim-ok`). Suena el conteo 1–8 al `bpm` con `cntPlay` (voz o pitidos). Si se pulsa «La tengo», se guarda `beats` = tiempos transcurridos (con decimal) y pasa a «revela»; si llega el siguiente 1 (8 tiempos) sin pulsar, `beats = null` y pasa a «revela» con «Se acabó el tiempo».
  - `fase "revela"`: lista las salidas (`exitsFrom(pos, hold)`, como en el repaso de enlaces: nombre, ruta, «en práctica» si no es segura); si no hay ninguna: «Desde aquí aún no tienes salida: básico y pide una en clase.» y llama a `askFor(pos)`. Botones de nota «No me salió» / «Dudé» / «La tenía» (`data-simg="no|dudas|fluida"`); con tiempo agotado, «La tenía» no se ofrece. La nota actualiza `S.linkRep[pos] = nextRep(S.linkRep[pos], g)` y `S.actividad[hoy]++`, y pasa a la ronda siguiente.
  - `fase "fin"`: resumen: rondas, cuántas «La tenía», media de tiempos hasta decidir (solo las decididas), y la lista «Dónde dudaste» (posiciones con «no», «dudas» o tiempo agotado) con botón «Ver salidas» que hace `goto-pos`. Botones «Otra vez» y «Hecho».
  - Cerrar la hoja (cualquier camino), `visibilitychange` a oculto o terminar: `simStop()` para todos los nodos de audio, cancela el `raf` y el `timeout` y llama a `releaseWake()` si no hace falta. El observador de nodos retirados (como el de `rcCleanup`) también lo llama.
  - Entradas: botón «Simulacro» en Social (`data-act="sim-open"`) y un panel en Repasar «Simulacro de social» con el mismo botón.
  - En `window.__bachateca`: `simState()` → `{fase, i, rondas, pos, beats}`, `simForce(colaDePosiciones)` para fijar el orden en pruebas.

- [ ] **Step 1: Escribir las pruebas que fallan.**
  - `simulacro_completo`: tres posiciones con salidas; `simForce` con 2 rondas fijas; abrir desde Social, elegir 6 rondas no (usar `simForce`), bpm 150, Empezar → `fase "decide"`; pulsar «La tengo» → «revela» con las salidas de esa posición; «La tenía» → segunda ronda; esperar a que se acabe el tiempo (8 tiempos a 150 bpm ≈ 3,2 s) → «revela» con «Se acabó el tiempo» y sin «La tenía»; «No me salió» → «fin»; el resumen dice «1 de 2» y lista la segunda posición en «Dónde dudaste»; `S.linkRep` de la primera tiene `step 1` y la segunda `fallos 1`.
  - `simulacro_posicion_sin_salida`: una posición con llegadas pero sin salidas; `simForce([esa])` → al revelar dice «aún no tienes salida» y existe una pregunta abierta para esa posición.
  - `simulacro_cerrar_para_el_conteo`: empezar y cerrar la hoja a mitad → `simState()` es `null`; los nodos de audio se paran (comprobarlo con un `init` que envuelva `AudioScheduledSourceNode.prototype.stop` y cuente llamadas > 0).
  - `simulacro_sin_posiciones`: sin figuras con ruta → mensaje y sin `#sim-go`.
- [ ] **Step 2: Ejecutar.** Esperado: FALLAN.
- [ ] **Step 3: Implementar** según las interfaces.
- [ ] **Step 4: Ejecutar** las nuevas y la batería. Esperado: todo verde.
- [ ] **Step 5: Commit** «Simulacro de social».

### Tarea 8: Versión 1.51 y documentación

**Files:**
- Modify: `index.html` (`APP_VERSION = "1.51"`), `sw.js` (`VERSION = "bachateca-v51"`), `README.md`, `docs/superpowers/specs/2026-11-07-hoja-de-ruta.md` (§5: D4 y D5 aprobadas)

- [ ] **Step 1: README.** Sección nueva corta «Practicar para el social»: el simulacro (dónde está y qué hace con el repaso) y las preguntas para clase. En «Pruebas automáticas», mencionar `BROWSER=webkit` y `playwright install webkit`. En «Versión de los datos», que la 1.51 pasa los datos a la versión 7.
- [ ] **Step 2: Subir versiones** y marcar D4/D5 como aprobadas en la hoja de ruta.
- [ ] **Step 3: Verificación final.** Batería completa 3 veces en Chromium. Esperado: todo verde las 3.
- [ ] **Step 4: Commit** «Bachateca 1.51: simulacro de social y enlaces fiables».
- [ ] **Step 5: Lista manual en iPhone (para el usuario):** la de la hoja de ruta, más: hacer un simulacro con el iPhone en silencio y comprobar que suena; cerrar la app a mitad de simulacro y volver; registrar un social y ver que la figura deja de estar pendiente; con alguna figura de salsa, comprobar el selector de baile.
