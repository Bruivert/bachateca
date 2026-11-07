# Fases 0 y 1 · Red de seguridad e integridad de datos · Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que ningún camino conocido pueda perder figuras, registros o progreso (P0-1, P0-2, P0-3, P1-1, P1-2), con instantáneas locales restaurables y pruebas automáticas en CI, sin quitar ninguna funcionalidad.

**Architecture:** Todo sigue en `index.html` (un IIFE). Se añaden: un modo seguro en el arranque, instantáneas en el almacén `kv` de IndexedDB (claves `snap:<ms>:<motivo>`), una validación de copias importadas y una fusión que no pisa. Las pruebas se añaden a `tests/test_bachateca.py` con su mismo estilo (`@test`, `open_app`, `window.__bachateca`).

**Tech Stack:** HTML/CSS/JS sin dependencias; Python 3 + Playwright 1.64 (Chromium y WebKit); GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-07-hoja-de-ruta.md` (fases 0 y 1, propuestas I1–I6, decisiones D1–D3).

## Global Constraints

- Ninguna dependencia nueva en la app; ningún archivo de app nuevo (todo en `index.html`, `sw.js`, `conteo.html`).
- `SCHEMA` se queda en `6`: el único campo nuevo es `guardado` (número, ms) en la raíz del estado, opcional y conservado por versiones anteriores.
- Textos de la interfaz en español, con el tono actual (frases cortas, de tú).
- Las 49 pruebas actuales siguen pasando. Solo cambian `importar_conserva_intentos_locales` (D1) y `aviso_videos_sin_copia` (D3), y solo en el paso que la decisión cambia.
- Ninguna prueba se desactiva. En WebKit se excluyen solo las que necesitan cámara o micrófono simulados, con el motivo escrito.
- Commits pequeños, uno por tarea, con las líneas de atribución de la sesión. Sin identificadores de modelo en el código ni en los comentarios.
- Pruebas: `python3 tests/test_bachateca.py` (Chromium) y `BROWSER=webkit python3 tests/test_bachateca.py`.

## Review Focus

1. Guardar una instantánea falla por falta de espacio → el guardado normal del estado tiene que seguir funcionando. (Tarea 5: `instantanea_que_falla_no_impide_guardar`)
2. Restaurar una instantánea hecha con una versión anterior de los datos → se migra antes de aplicarse. (Tarea 6: `restaurar_instantanea_antigua_migra`)
3. Navegador sin IndexedDB → sigue el modo localStorage de siempre, no el modo seguro. (Tarea 3: `sin_indexeddb_sigue_con_localstorage`)
4. Copia con `figures` como array, figuras `null` o `nombre` numérico → ni errores ni datos rotos. (Tarea 7: `copia_mal_formada_no_rompe`)
5. Las instantáneas no salen en la copia exportada ni cuentan como datos. (Tarea 6: `exportar_no_incluye_instantaneas`)

---

## Fase 0 · Red de seguridad

### Tarea 1: CI y prueba intermitente del conteo

**Files:**
- Create: `.github/workflows/pruebas.yml`
- Modify: `conteo.html:340-357` (bloque de grabación de la prueba 4)
- Test: `tests/test_bachateca.py` (sin cambios de pruebas)

**Interfaces:**
- Produces: un job `pruebas` que ejecuta la batería en cada push y pull request.

- [ ] **Step 1: Reproducir la intermitencia.** Ejecutar la batería completa 3 veces: `for i in 1 2 3; do python3 tests/test_bachateca.py | tail -1; done`. Esperado: al menos una vez «48 de 49», con `conteo_grabar_dentro_de_la_app_saca_el_pulso` y `first` negativo. Si no aparece en 3 ejecuciones, anotarlo y seguir (la causa está clara en el código).
- [ ] **Step 2: Arreglar `conteo.html`.** Mover `startCount(LONG, mix)` dentro de `rec.onstart`, después de `recAt = c.currentTime`, y guardar su resultado en una variable del bloque que lee `onstop` (`t0`). Es el mismo orden que ya usa la app en `rcStart` (`index.html:2237`).
- [ ] **Step 3: Verificar.** Ejecutar la batería 3 veces. Esperado: «49 de 49» las 3.
- [ ] **Step 4: Crear el workflow.** `ubuntu-latest`, Python 3.12, `pip install playwright==1.64.1`, `python -m playwright install --with-deps chromium`, `python3 tests/test_bachateca.py`. Disparadores: `push` y `pull_request`.
- [ ] **Step 5: Commit** «Pruebas en CI y conteo sin carrera al grabar».

### Tarea 2: Las pruebas también en WebKit

**Files:**
- Modify: `tests/test_bachateca.py` (`test`, `main`, y las pruebas que necesitan cámara)
- Modify: `.github/workflows/pruebas.yml` (segundo paso con WebKit)

**Interfaces:**
- Produces: `test(fn=None, *, solo_chromium: str | None = None)`; con `solo_chromium="motivo"` la prueba se salta en WebKit y se imprime `  salta FN (motivo)`. Variable de entorno `BROWSER` en `{"chromium", "webkit"}` (por defecto `chromium`); en WebKit no se pasan los argumentos de cámara simulada.

- [ ] **Step 1: Parametrizar el navegador** en `main()` según `BROWSER` y aceptar `solo_chromium` en el decorador.
- [ ] **Step 2: Marcar** como `solo_chromium="cámara y micrófono simulados"` las 5 pruebas que usan `getUserMedia`: `conteo_carga_la_voz_y_el_ritmo_de_las_figuras`, `conteo_suena_con_los_dos_motores`, `conteo_grabar_dentro_de_la_app_saca_el_pulso`, `grabarme_con_conteo`, `salir_de_grabar_apaga_la_camara`.
- [ ] **Step 3: Ejecutar en WebKit:** `python -m playwright install webkit && BROWSER=webkit python3 tests/test_bachateca.py`. Para cada fallo, decidir: limitación del motor de pruebas (por ejemplo, códecs) → `solo_chromium` con el motivo exacto; fallo de la app → **no marcarlo**, apuntarlo y avisar al usuario antes de seguir.
- [ ] **Step 4: Añadir el paso de WebKit al workflow** (`install --with-deps webkit` y la ejecución con `BROWSER=webkit`).
- [ ] **Step 5: Commit** «Pruebas también en WebKit».

---

## Fase 1 · Integridad de datos

### Tarea 3: Modo seguro si la lectura falla (I1, P0-1)

**Files:**
- Modify: `index.html:1104-1111` (`idbOpen`), `1188-1198` (`persist`, `saveNow`), `1117` (`vidPut`), `1257-1273` (`initStore`), `3788-3803` (`render`), manejador de clics (`3806+`), ganchos `4000-4003`
- Test: `tests/test_bachateca.py` (sección nueva «Integridad de datos»)

**Interfaces:**
- Produces:
  - `let safeMode = false;`
  - `async function readStored(): Promise<{ok: boolean, idb: object|null, ls: object|null}>`: hasta 3 intentos, separados 300 ms, para `idbOpen` y `kvGet("state")`. `ok:false` si tras los intentos falla alguno. Si `!window.indexedDB` → `{ok:true, idb:null, ls}` (modo localStorage de siempre).
  - `function safeHTML(): string`: aviso `<div class="note" id="safe-note" role="alert">` con el texto «No se han podido leer tus datos. Para no estropearlos, la app no guardará nada hasta que se lean bien.» y el botón `data-act="safe-retry"` «Volver a intentarlo» (hace `location.reload()`). Se pinta al principio de cada vista mientras `safeMode`.
  - En `window.__bachateca`: `safeMode: () => safeMode`.
- Comportamiento: con `safeMode`, `persist` no programa ningún guardado ni suma cambios para la copia, y avisa una sola vez con `toast("Modo seguro: los cambios no se guardan.")`; `saveNow` sale sin escribir; `vidPut` rechaza con `userMsg` «Modo seguro: no se pueden guardar vídeos.»; `assetsApi = null`. Se muestran los datos de `ls` si existen (solo lectura) o la app vacía.
- Helper de pruebas: `open_app(browser, seed=None, videos=None, init=None)`; `init` es un script que se añade con `ctx.add_init_script` **después** de sembrar los datos (para que no afecte a la siembra).

- [ ] **Step 1: Escribir las pruebas que fallan.**
  - `lectura_fallida_no_pisa_los_datos`: sembrar 30 figuras `r0…r29`; `init` hace que `IDBObjectStore.prototype.get` lance `UnknownError` para la clave `"state"` mientras `!globalThis.__sinParche`. Comprobar que `#safe-note` es visible y `__bachateca.safeMode()` es `true`; pulsar `[data-act="examples"]`, `flush()`, esperar 300 ms; poner `window.__sinParche = true` y leer con `stored_state(p)` (un contexto nuevo no serviría: no comparte el almacenamiento). Esperado: las 30 figuras siguen y no hay ninguna con `ejemplo`.
  - `lectura_fallida_una_vez_se_recupera`: el parche falla solo la primera vez. Esperado: 30 figuras en `state()`, sin `#safe-note`.
  - `sin_indexeddb_sigue_con_localstorage`: `init` = `Object.defineProperty(window, "indexedDB", {value: undefined, configurable: true})`. Cargar ejemplos y `flush()`. Esperado: sin `#safe-note`, y `JSON.parse(localStorage.getItem("bachateca.v1")).figures` tiene 8 figuras.
- [ ] **Step 2: Ejecutar.** Esperado: las dos primeras FALLAN (no existe `safeMode`); la tercera puede pasar ya (lo protege de regresiones).
- [ ] **Step 3: Implementar** `readStored`, `safeMode`, `safeHTML` y los cambios en `persist`, `saveNow`, `vidPut`, `initStore`, `render` y el manejador (`safe-retry`). En `idbOpen`, la comprobación pasa a ser `!window.indexedDB`.
- [ ] **Step 4: Ejecutar** las tres pruebas nuevas y la batería completa. Esperado: todas pasan.
- [ ] **Step 5: Commit** «Modo seguro: no guardar si no se han podido leer los datos».

### Tarea 4: Usar la copia más reciente (I3, P0-3)

**Files:**
- Modify: `index.html:1100-1101` (`lsSet`), `1194-1198` (`saveNow`), `initStore`
- Test: `tests/test_bachateca.py`

**Interfaces:**
- Consumes: `readStored()` (Tarea 3).
- Produces:
  - `function lsSet(k, v): boolean`: `true` si se guardó.
  - En `saveNow`: antes de escribir, `S.guardado = Date.now()` (y en la copia que se escribe). Si `kvSet` va bien → `localStorage.removeItem(LS_FALLBACK)`. Si falla y `lsSet` también → `toast("No se ha podido guardar. Libera espacio en el iPhone y vuelve a intentarlo.")`. En el modo sin IndexedDB, el mismo aviso si `lsSet` devuelve `false`.
  - `initStore` elige entre `idb` y `ls` el que tenga mayor `guardado` (ausente = 0); si empatan, `idb`.

- [ ] **Step 1: Escribir las pruebas que fallan.**
  - `respaldo_mas_reciente_gana`: sembrar IndexedDB con `guardado: 1000` y 1 figura, y `localStorage["bachateca.v1"]` con `guardado: 2000` y 2 figuras (en la página de siembra). Esperado: `state().figures` tiene 2.
  - `guardar_bien_borra_el_respaldo`: con `bachateca.v1` sembrado, cargar ejemplos y `flush()`. Esperado: `localStorage.getItem("bachateca.v1") === null` y `stored_state(p)["guardado"]` es un número.
  - `sin_espacio_avisa`: `init` hace que `IDBObjectStore.prototype.put` lance `QuotaExceededError` para la clave `"state"` y que `Storage.prototype.setItem` lance para `"bachateca.v1"`. Cargar ejemplos y `flush()`. Esperado: `.toast` contiene «No se ha podido guardar».
- [ ] **Step 2: Ejecutar.** Esperado: FALLAN.
- [ ] **Step 3: Implementar** según las interfaces.
- [ ] **Step 4: Ejecutar** las pruebas nuevas y la batería. Esperado: pasan.
- [ ] **Step 5: Commit** «Al abrir, usar la copia guardada más reciente».

### Tarea 5: Instantáneas automáticas (I2, almacén)

**Files:**
- Modify: `index.html` (nuevo bloque «instantáneas» tras `saveNow`; `initStore`; `saveNow`; ganchos de prueba)
- Test: `tests/test_bachateca.py`

**Interfaces:**
- Consumes: `kvGet`, `kvSet`, `tx`, `safeMode`.
- Produces:
  - `const SNAP = "snap:", SNAP_KEEP = {diaria: 7, otras: 5};`
  - `async function takeSnapshot(reason: string, state = S): Promise<string|null>`: guarda en `kv` la clave `` `snap:${Date.now()}:${reason}` `` con `{at, reason, nFig, nLog, schema, state: clone(state)}`; luego poda: deja las `SNAP_KEEP.diaria` más recientes con `reason === "diaria"` y las `SNAP_KEEP.otras` más recientes del resto. Cualquier error → devuelve `null` sin lanzar. No hace nada en `safeMode`.
  - `async function listSnapshots(): Promise<Array<{key: string, at: number, reason: string, nFig: number, nLog: number}>>`, de la más reciente a la más antigua.
  - Motivos: `"diaria"`, `"antes-de-importar"`, `"antes-de-reemplazar"`, `"antes-de-restaurar"`, `"antes-de-encoger"`.
  - Diaria: en `initStore`, tras una carga correcta con datos y sin `safeMode`, si no hay ninguna `"diaria"` con `dayOf(at) === todayStr()` → `takeSnapshot("diaria")`.
  - Encogimiento: `let lastFigN = null;` (se fija al cargar y tras cada guardado correcto). En `saveNow`, si `n < lastFigN - 5 && n < lastFigN * 0.7` → antes de escribir, `await takeSnapshot("antes-de-encoger", await kvGet("state"))` (la copia guardada anterior, no la de memoria).
  - En `window.__bachateca`: `takeSnapshot`, `listSnapshots`.

- [ ] **Step 1: Escribir las pruebas que fallan.**
  - `instantanea_diaria_al_abrir`: sembrar 1 figura → `listSnapshots()` tiene 1 con `reason "diaria"` y `nFig 1`; recargar → sigue habiendo 1.
  - `instantaneas_se_rotan`: llamar 7 veces a `takeSnapshot("antes-de-importar")` → hay 5 de ese motivo y la `"diaria"` sigue.
  - `encoger_guarda_instantanea`: sembrar 20 figuras; `deleteFigure` de 10 vía ganchos; `flush()` → existe una `"antes-de-encoger"` con `nFig 20`.
  - `instantanea_que_falla_no_impide_guardar`: `init` hace que `put` lance para claves que empiezan por `"snap:"`. Cargar ejemplos y `flush()` → `stored_state(p)` tiene 8 figuras y no hay errores de página.
- [ ] **Step 2: Ejecutar.** Esperado: FALLAN.
- [ ] **Step 3: Implementar** según las interfaces.
- [ ] **Step 4: Ejecutar** las pruebas nuevas y la batería. Esperado: pasan.
- [ ] **Step 5: Commit** «Instantáneas automáticas de los datos».

### Tarea 6: Restaurar una instantánea desde Ajustes (I2, interfaz)

**Files:**
- Modify: `index.html:3670` (`SET_VIEWS`), `3672-3725` (`openSettings`), manejador de clics, ganchos de prueba
- Test: `tests/test_bachateca.py`

**Interfaces:**
- Consumes: `takeSnapshot`, `listSnapshots` (Tarea 5); `migrate`, `applyData`, `askConfirm`.
- Produces:
  - `SET_VIEWS.instantaneas = "Instantáneas"`; fila en el menú «Datos» con el número de instantáneas.
  - Cada instantánea en la lista: fecha y hora, motivo legible (`diaria` «Copia del día», `antes-de-importar` «Antes de importar», `antes-de-reemplazar` «Antes de reemplazar todo», `antes-de-restaurar` «Antes de restaurar», `antes-de-encoger` «Antes de borrar muchas figuras»), «N figuras · M registros» y el botón `data-act="snap-restore" data-key="…"` «Restaurar».
  - `async function restoreSnapshot(key: string): Promise<boolean>`: pregunta con `askConfirm({title: "¿Volver a esta instantánea?", msg: "Antes se guarda otra instantánea con tus datos de ahora, por si quieres deshacerlo. Los vídeos no cambian.", ok: "Restaurar"})`; si se confirma: `takeSnapshot("antes-de-restaurar")`, `applyData(migrate(valor.state))`, `persist({t: "meta"})`, `render()`, `openSettings()`, `toast("Restaurado: N figuras")`. Un indicador `restoring` ignora una segunda llamada mientras dura la primera.
  - En `window.__bachateca`: `restoreSnapshot`.

- [ ] **Step 1: Escribir las pruebas que fallan.**
  - `restaurar_instantanea`: sembrar 3 figuras; `takeSnapshot("antes-de-importar")`; `deleteFigure` de las 3; Ajustes → `[data-setv="instantaneas"]` → el `snap-restore` de esa instantánea → confirmar. Esperado: 3 figuras en `state()` y en `listSnapshots()` hay una `"antes-de-restaurar"` con `nFig 0`.
  - `restaurar_instantanea_antigua_migra`: guardar directamente en `kv` una instantánea con `schema: 5` y una figura sin `partes`; restaurarla. Esperado: la figura tiene `partes == []` y `state().schema == SCHEMA`.
  - `exportar_no_incluye_instantaneas`: con 2 instantáneas, `exportData()` no contiene `"snap:"` ni una clave `snapshots`, y `Object.keys(state())` no contiene ninguna clave que empiece por `snap`.
- [ ] **Step 2: Ejecutar.** Esperado: FALLAN.
- [ ] **Step 3: Implementar** según las interfaces.
- [ ] **Step 4: Ejecutar** las pruebas nuevas y la batería. Esperado: pasan.
- [ ] **Step 5: Commit** «Restaurar instantáneas desde Ajustes».

### Tarea 7: Escapar ids y validar las copias (I4, P1-1)

**Files:**
- Modify: `index.html`: todas las interpolaciones de ids en atributos sin `esc` (1360, 1374, 1530, 1794, 1861, 2007, 2010, 2025, 2097-2099, 2111, 2125, 2129, 2189, 2306, 2312, 2313, 2459, 2464, y las que encuentre el grep del Step 3); `importData` (3727)
- Test: `tests/test_bachateca.py`

**Interfaces:**
- Produces:
  - `const ID_RE = /^[A-Za-z0-9_-]{1,64}$/;`
  - `function sanitizeImport(d): {figures: object, logs: object, descartadas: number}`. Una figura se queda si es un objeto (no array), `ID_RE.test(f.id)` y `typeof f.nombre === "string" && f.nombre.trim()`. Un registro se queda si es un objeto, `ID_RE.test(l.id)` y `typeof l.fecha === "string"`; su `figs` se filtra a textos. Si `d.figures` es un array o no es un objeto → `figures: {}`. `descartadas` cuenta figuras y registros quitados. La clave de salida es el `id`.
  - `importData` llama a `sanitizeImport` después de `migrate`. Si `descartadas > 0`, el aviso final añade `` ` · ${descartadas} descartadas por estar mal formadas` ``.
  - En `window.__bachateca`: `sanitizeImport`.

- [ ] **Step 1: Escribir las pruebas que fallan.**
  - `copia_con_id_malicioso_no_ejecuta`: importar una figura con `id` `` x"><img src=x onerror="window.__pwn=1"> ``; ir a Repertorio. Esperado: `window.__pwn` es `undefined`, la figura no está en `state()` y `.toast` contiene «descartada».
  - `id_raro_en_los_datos_se_escapa`: sembrar directamente en IndexedDB una figura con `id` `` a"b `` (sin pasar por importar); abrir Repertorio y su ficha. Esperado: sin errores de página y `getAttribute("data-view") === 'a"b'` en su tarjeta.
  - `copia_mal_formada_no_rompe`: importar `{"figures": [1, 2]}`, luego `{"figures": {"a": null, "b": {"id": "b", "nombre": 3}}}`. Esperado: sin errores de página, `state().figures` vacío y un aviso en cada caso.
- [ ] **Step 2: Ejecutar.** Esperado: FALLAN.
- [ ] **Step 3: Escapar.** Envolver con `esc(...)` cada interpolación de id en atributos. Verificar con `grep -nE '="\$\{[A-Za-z_.]*id\}"' index.html`. Esperado: sin resultados.
- [ ] **Step 4: Implementar** `sanitizeImport` y su uso en `importData`.
- [ ] **Step 5: Ejecutar** las pruebas nuevas y la batería. Esperado: pasan.
- [ ] **Step 6: Commit** «Escapar los ids y validar las copias importadas».

### Tarea 8: Importar sin pisar tus figuras (I5, P0-2, decisiones D1 y D2)

**Files:**
- Modify: `index.html:3727-3762` (`importData`)
- Modify: `tests/test_bachateca.py:525-535` (`importar_conserva_intentos_locales`, solo el paso que añade la confirmación)
- Test: `tests/test_bachateca.py`

**Interfaces:**
- Consumes: `takeSnapshot` (Tarea 5), `sanitizeImport` (Tarea 7), `askConfirm`.
- Produces:
  - `function figDiffers(a, b): boolean`: compara las dos figuras sin `intentos` ni `partes`, con un `JSON.stringify` de claves ordenadas de forma recursiva (que el orden de las claves no cuente como diferencia).
  - Flujo de `importData(replace)`:
    1. Antes de cambiar nada: `await takeSnapshot(replace ? "antes-de-reemplazar" : "antes-de-importar")`.
    2. Al añadir (`replace = false`), las figuras de la copia se reparten en **nuevas** (el id no existe), **iguales** (`!figDiffers`) y **distintas**. Si hay distintas: `askConfirm({title: \`${n} ${n===1?"figura ya está y es distinta":"figuras ya están y son distintas"}\`, msg: "La copia tiene otra versión de figuras que ya tienes (nombre, estado, repaso o notas).", ok: "Usar las de la copia", cancel: "Conservar las mías"})`. Cerrar o cancelar = conservar.
    3. Se aplican siempre las nuevas; las distintas, solo si se eligió «Usar las de la copia» (con la fusión de intentos y partes de ahora); las iguales no se tocan. Registros: al añadir, solo los ids que faltan.
    4. Aviso: `` `${pl(nuevas,"figura añadida","figuras añadidas")}` `` + `` ` · ${iguales} ya estaban` `` si hay + `` ` · se conservan tus ${d}` `` o `` ` · ${d} actualizadas con la copia` `` según la elección.
  - Al reemplazar (D2): las figuras que no están en la copia se quitan con `delete S.figures[id]; persist({t: "figdel", id})`, **sin** borrar sus vídeos. El texto de la confirmación pasa a ser: «Se queda solo lo que hay en la copia (N figuras). Antes se guarda una instantánea de tus datos: podrás volver atrás en Ajustes → Instantáneas.»

- [ ] **Step 1: Escribir las pruebas que fallan.**
  - `anadir_conserva_mis_figuras` (reproduce P0-2): sembrar `f1` con `vid "vA"`; exportar; cambiar en `state()` `notas`, `estado: "consolidada"`, `rep.step: 4` y `vid: "vB"`; importar la copia con «Añadir»; en la confirmación, pulsar «Conservar las mías». Esperado: `notas`, `estado`, `rep.step == 4` y `vid == "vB"` intactos, y `.toast` contiene «se conservan tus 1».
  - `anadir_solo_nuevas_sin_preguntar`: importar una copia con solo figuras nuevas. Esperado: no aparece `#confirm-root .confirm` y se añaden.
  - `importar_guarda_instantanea`: tras cualquier importación, `listSnapshots()` tiene una `"antes-de-importar"`.
  - `reemplazar_no_borra_videos_al_momento`: sembrar `f1` con `vid "v1"` (y el vídeo); «Reemplazar todo» con una copia que solo tiene `f2`; confirmar. Esperado: `"v1"` sigue en `stored_video_sizes(p)`; restaurar la `"antes-de-reemplazar"` → `f1` vuelve con `vid "v1"`.
- [ ] **Step 2: Ejecutar.** Esperado: FALLAN.
- [ ] **Step 3: Actualizar `importar_conserva_intentos_locales` (D1):** después de `import_text`, pulsar `#confirm-root [data-cf="ok"]` («Usar las de la copia») y esperar 300 ms. El resto de comprobaciones no cambian.
- [ ] **Step 4: Implementar** según las interfaces.
- [ ] **Step 5: Ejecutar** las pruebas nuevas y la batería. Esperado: pasan.
- [ ] **Step 6: Commit** «Importar sin pisar tus figuras, con instantánea previa».

### Tarea 9: Una copia descargada no se da por hecha sin preguntar (I6, P1-2, decisión D3)

**Files:**
- Modify: `index.html:3156-3162` (`shareOrDownload`), `934-945` (`askConfirm`), `985-990` (`exportBackup`), `2319-2326` (`attSaveVid`), `2758-2765` (`ptSaveVid`), `3041-3046` (`savevid` en `renderVidbox`), `3203-3227` (`saveVidBatch`)
- Modify: `tests/test_bachateca.py` (`aviso_videos_sin_copia`, solo el paso que añade la confirmación)
- Test: `tests/test_bachateca.py`

**Interfaces:**
- Produces:
  - `async function shareOrDownload(file): Promise<"compartido"|"descargado"|false>`.
  - `askConfirm({title, msg, ok, cancel, danger = true})`: con `danger: false`, el botón de aceptar no lleva la clase `danger`.
  - `async function confirmSaved(how: "compartido"|"descargado"|false, what: string): Promise<boolean>`: `"compartido"` → `true`; `false` → `false`; `"descargado"` → `askConfirm({title: \`¿Se ha guardado ${what}?\`, msg: "Compruébalo en Archivos o en Descargas.", ok: "Sí, está guardada", cancel: "No", danger: false})`.
  - Los cinco llamadores marcan la copia o el vídeo como guardado solo si `confirmSaved` devuelve `true`. Textos de `what`: «la copia», «el vídeo», «los vídeos».

- [ ] **Step 1: Escribir la prueba que falla.** `exportar_por_descarga_pregunta`: las pruebas ya quitan `navigator.share`. Ajustes → Exportar → aparece la confirmación → «No» → `localStorage.getItem("bachateca.backup.at")` es `null`. Repetir → «Sí, está guardada» → `bachateca.backup.at` es un número.
- [ ] **Step 2: Ejecutar.** Esperado: FALLA (no aparece la confirmación).
- [ ] **Step 3: Actualizar `aviso_videos_sin_copia` (D3):** después de la descarga, pulsar `#confirm-root [data-cf="ok"]` antes de comprobar `vidsUnsaved()`.
- [ ] **Step 4: Implementar** según las interfaces.
- [ ] **Step 5: Ejecutar** la prueba nueva y la batería. Esperado: pasan.
- [ ] **Step 6: Commit** «Preguntar si la copia descargada se ha guardado».

### Tarea 10: Versión 1.50 y documentación

**Files:**
- Modify: `index.html:1205` (`APP_VERSION = "1.50"`), `sw.js:2` (`VERSION = "bachateca-v50"`), `README.md` §1, §4 y §5

- [ ] **Step 1: README.**
  - §1: la lista de archivos a subir es «todo el contenido del repositorio», con la carpeta `sonidos/` mencionada expresamente (si falta, la app no funciona sin conexión).
  - §4: un párrafo sobre las instantáneas («Ajustes → Instantáneas: la app guarda sola una copia al día y antes de importar o restaurar; no sustituyen a Exportar, porque viven en el mismo iPhone»).
  - §5: el ejemplo de versión pasa a `bachateca-v50` → `v51`.
- [ ] **Step 2: Subir las versiones** en `index.html` y `sw.js`.
- [ ] **Step 3: Verificación final.** Batería completa 3 veces en Chromium y una en WebKit. Esperado: todo en verde salvo las marcadas `solo_chromium`, todas las veces.
- [ ] **Step 4: Commit** «Bachateca 1.50: datos protegidos».
- [ ] **Step 5: Lista manual para el usuario** (no la hace el agente): la lista de la hoja de ruta (§4), más: abrir Ajustes → Instantáneas y restaurar la «Copia del día»; exportar y elegir «No» en la pregunta; importar una copia antigua con «Añadir» y elegir «Conservar las mías».
