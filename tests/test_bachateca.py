#!/usr/bin/env python3
"""Pruebas automáticas de Bachateca en un navegador de verdad (Chromium, sin ventana).

Uso, desde la carpeta del repositorio:
    pip install playwright && playwright install chromium   # solo la primera vez
    python3 tests/test_bachateca.py

Cada prueba abre la app limpia (sin datos), así que no toca nada de tu iPhone ni de tu navegador.
En WebKit: BROWSER=webkit python3 tests/test_bachateca.py (se saltan las pruebas de cámara y micrófono).
Si tienes Chrome instalado y no quieres descargar Chromium: CHROME=/ruta/a/chrome python3 tests/test_bachateca.py
"""
import functools, http.server, json, os, socketserver, sys, threading, traceback
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = None
results = []


def serve():
    global URL
    class Quiet(http.server.SimpleHTTPRequestHandler):
        # Algunos Python sirven .md como descarga y open_app no podría abrir README.md.
        extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".md": "text/plain"}
        def log_message(self, *a):
            pass
    handler = functools.partial(Quiet, directory=ROOT)
    srv = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    URL = f"http://127.0.0.1:{srv.server_address[1]}/index.html?test"
    return srv


def test(fn=None, *, solo_chromium=None):
    """@test o @test(solo_chromium="motivo"): con motivo, la prueba se salta en WebKit."""
    def reg(f):
        f.solo_chromium = solo_chromium
        results.append(f)
        return f
    return reg(fn) if fn is not None else reg


def open_app(browser, seed=None, videos=None, init=None, ls=None):
    """App limpia. seed: estado guardado antes de abrirla (como si viniera de una versión anterior).
    ls: claves de localStorage que se siembran junto con el estado (valor = JSON).
    init: script que se añade después de sembrar, para que no afecte a la siembra."""
    ctx = browser.new_context(service_workers="block", viewport={"width": 390, "height": 844})
    # Sin hoja de compartir: así «Guardar en Fotos» y «Exportar» descargan el archivo y se puede comprobar.
    # (Chromium reciente la tiene y, sin ventana, se queda esperando.)
    ctx.add_init_script("delete Navigator.prototype.share; delete Navigator.prototype.canShare;")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and not m.text.startswith("Failed to load resource") and errors.append(m.text))
    page.on("response", lambda r: r.status >= 400 and not r.url.endswith("favicon.ico") and errors.append(f"{r.status} {r.url}"))
    if seed is not None or videos or ls:
        page.goto(URL.replace("index.html?test", "README.md"))  # mismo origen, sin arrancar la app
        page.evaluate("""async ([seed, videos, ls]) => {
          for (const [k, v] of Object.entries(ls || {})) localStorage.setItem(k, JSON.stringify(v));
          const db = await new Promise((res, rej) => { const r = indexedDB.open("bachateca", 1);
            r.onupgradeneeded = () => { r.result.createObjectStore("kv"); r.result.createObjectStore("videos"); };
            r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });
          await new Promise((res, rej) => { const t = db.transaction(["kv", "videos"], "readwrite");
            if (seed) t.objectStore("kv").put(seed, "state");
            for (const id of (videos || [])) t.objectStore("videos").put(new Blob([new Uint8Array(2048)], {type: "video/mp4"}), id);
            t.oncomplete = res; t.onerror = () => rej(t.error); });
          db.close();
        }""", [seed, videos or [], ls or {}])
    if init:
        ctx.add_init_script(init)
    page.goto(URL)
    page.wait_for_function("window.__bachateca && window.__bachateca.ready()")
    return ctx, page, errors


def stored_state(page):
    return page.evaluate("""() => new Promise((res, rej) => { const r = indexedDB.open("bachateca", 1);
      r.onsuccess = () => { const g = r.result.transaction("kv").objectStore("kv").get("state");
        g.onsuccess = () => { r.result.close(); res(g.result); }; g.onerror = () => rej(g.error); }; })""")


def fig(i, entrada, salida, **kw):
    f = {"id": f"f{i}", "nombre": f"Figura {i}", "tipo": "figura", "estado": "practica",
         "entrada": entrada, "salida": salida, "agarreIn": "", "agarreOut": "", "creado": 1000 + i}
    f.update(kw)
    return f


# ---------------------------------------------------------------- lógica
@test
def repaso_espaciado(browser):
    ctx, p, _ = open_app(browser)
    r = p.evaluate("""() => { const B = window.__bachateca, t = B.todayStr;
      const a = B.nextRep(undefined, "fluida");
      const b = B.nextRep({step: 2, aciertos: 2, fallos: 0}, "dudas");
      const c = B.nextRep({step: 4, aciertos: 4, fallos: 0}, "no");
      let d = undefined; for (let i = 0; i < 10; i++) d = B.nextRep(d, "fluida");
      return {a, b, c, d, t1: t(1), t3: t(3), t60: t(60)}; }""")
    assert r["a"]["step"] == 1 and r["a"]["due"] == r["t3"] and r["a"]["aciertos"] == 1, r["a"]
    assert r["b"]["step"] == 2 and r["b"]["due"] == r["t3"], r["b"]           # mitad de 7 días
    assert r["c"]["step"] == 0 and r["c"]["due"] == r["t1"] and r["c"]["fallos"] == 1, r["c"]
    assert r["d"]["step"] == 5 and r["d"]["due"] == r["t60"], r["d"]          # tope: 60 días
    ctx.close()


@test
def enlaces_por_posicion_y_agarre(browser):
    ctx, p, _ = open_app(browser)
    r = p.evaluate("""() => { const B = window.__bachateca;
      const a = {entrada: "Cerrada", salida: "Sombra", agarreOut: "Dos manos"};
      return [B.canFollow(a, {entrada: "Sombra", agarreIn: "Dos manos"}),
              B.canFollow(a, {entrada: "Sombra", agarreIn: ""}),
              B.canFollow(a, {entrada: "Sombra", agarreIn: "Izq–der"}),
              B.canFollow(a, {entrada: "Cerrada", agarreIn: "Dos manos"})]; }""")
    assert r == [True, True, False, False], r
    ctx.close()


@test
def cadenas_validas(browser):
    ctx, p, _ = open_app(browser)
    figs = {f["id"]: f for f in [
        fig(1, "Cerrada", "Abierta 2 manos", agarreOut="Dos manos"),
        fig(2, "Abierta 2 manos", "Sombra", agarreIn="Dos manos"),
        fig(3, "Sombra", "Abierta 1 mano"),
        fig(4, "Abierta 1 mano", "Cerrada"),
        fig(5, "Abierta 2 manos", "Abierta 2 manos", agarreIn="Izq–der"),
        fig(6, "Sombra", "Cerrada", estado="espera"),
    ]}
    p.evaluate("o => window.__bachateca.setFigs(o)", figs)
    bad = p.evaluate("""() => { const B = window.__bachateca, out = [];
      for (let k = 0; k < 200; k++) {
        const steps = B.makeChain("Cerrada").steps, fs = steps.filter(s => s.f).map(s => s.f);
        if (steps.length > 4) out.push("larga");
        if (new Set(fs.map(f => f.id)).size !== fs.length) out.push("repite");
        if (fs.some(f => f.estado === "espera")) out.push("lista de espera");
        if (fs.length && fs[0].entrada !== "Cerrada") out.push("inicio");
        for (let i = 1; i < fs.length; i++) if (!B.canFollow(fs[i-1], fs[i])) out.push("no encaja " + fs[i-1].id + "→" + fs[i].id);
      } return [...new Set(out)]; }""")
    assert bad == [], bad
    ctx.close()


@test
def migracion_pura(browser):
    ctx, p, _ = open_app(browser)
    r = p.evaluate("""() => { const B = window.__bachateca;
      const old = {figures: {a: {id: "a", nombre: "A"}, b: {id: "b", nombre: "B", tipo: "footwork", estado: "consolidada", hist: "x"}}, extra: 1};
      const snap = JSON.stringify(old);
      const m = B.migrate(old), m2 = B.migrate(m), newer = B.migrate({schema: B.SCHEMA + 1, figures: {}, futuro: true});
      return {m, same: JSON.stringify(m) === JSON.stringify(m2), untouched: JSON.stringify(old) === snap, newer, S: B.SCHEMA}; }""")
    m = r["m"]
    assert m["schema"] == r["S"], m
    assert m["figures"]["a"]["tipo"] == "figura" and m["figures"]["a"]["estado"] == "practica", m
    assert m["figures"]["b"]["tipo"] == "footwork" and m["figures"]["b"]["estado"] == "consolidada", m
    assert "hist" not in m["figures"]["b"], m
    assert m["extra"] == 1, "conserva lo que no conoce"
    assert r["same"], "repetir la migración no cambia nada"
    assert r["untouched"], "no modifica el original"
    assert r["newer"]["schema"] == r["S"] + 1 and r["newer"]["futuro"], "datos más nuevos se dejan igual"
    ctx.close()


# ---------------------------------------------------------------- arranque con datos de la 1.35
@test
def arranque_migra_y_guarda(browser):
    seed = {"figures": {"a": fig(1, "Cerrada", "Sombra", rep={"step": 2, "due": "2026-01-01", "aciertos": 2, "fallos": 0}),
                        "b": {"id": "b", "nombre": "Sin tipo", "estado": "disponible", "entrada": "Sombra", "salida": "Cerrada"}},
            "logs": {"l1": {"id": "l1", "fecha": "2026-10-30", "figs": ["a"]}},
            "positions": ["Cerrada", "Sombra"], "holds": ["Abrazo"], "classes": [], "linkRep": {"Cerrada": {"step": 1, "due": "2026-01-01"}},
            "campoFuturo": {"x": 1}}
    ctx, p, errors = open_app(browser, seed=seed)
    p.wait_for_timeout(400)
    st = stored_state(p)
    assert st["schema"] == p.evaluate("() => window.__bachateca.SCHEMA"), st.get("schema")
    assert set(st["figures"]) == {"a", "b"} and st["figures"]["b"]["tipo"] == "figura"
    assert st["figures"]["a"]["rep"]["step"] == 2, "no toca el repaso"
    assert st["logs"]["l1"]["figs"] == ["a"] and st["linkRep"]["Bachata\u241fCerrada"]["step"] == 1
    assert st["campoFuturo"] == {"x": 1}, "conserva campos desconocidos"
    assert st["classes"] == [], "respeta la lista de clases vacía"
    assert p.locator("#due-badge").inner_text() != "0"
    assert not errors, errors
    ctx.close()


# ---------------------------------------------------------------- importar copias
def import_text(p, text, replace=False):
    p.click("#btn-settings")
    p.click('[data-setv="importar"]')
    p.fill("#imp-text", text)
    p.click(f'[data-act="import-{"replace" if replace else "merge"}"]')
    p.wait_for_timeout(300)


@test
def importar_copia_antigua(browser):
    ctx, p, errors = open_app(browser)
    old = {"app": "bachateca", "version": 3, "figures": {"x": {"id": "x", "nombre": "Vieja"}}, "logs": {}, "positions": ["Cerrada", "Mano cruzada"]}
    import_text(p, json.dumps(old))
    S = p.evaluate("() => window.__bachateca.state()")
    assert S["figures"]["x"]["tipo"] == "figura" and S["figures"]["x"]["estado"] == "practica", S["figures"]["x"]
    assert "Mano cruzada" in S["positions"]
    exp = json.loads(p.evaluate("() => window.__bachateca.exportData()"))
    assert exp["schema"] == p.evaluate("() => window.__bachateca.SCHEMA") and "x" in exp["figures"]
    assert not errors, errors
    ctx.close()


@test
def importar_copia_mas_nueva_se_rechaza(browser):
    ctx, p, _ = open_app(browser)
    newer = {"app": "bachateca", "version": 3, "schema": 99, "figures": {"x": {"id": "x", "nombre": "Del futuro"}}}
    import_text(p, json.dumps(newer))
    assert "x" not in p.evaluate("() => window.__bachateca.state()")["figures"]
    assert "más nueva" in p.locator(".toast").inner_text()
    ctx.close()


@test
def reemplazar_con_copia_vacia_no_borra(browser):
    seed = {"figures": {"a": fig(1, "Cerrada", "Sombra")}, "logs": {}}
    ctx, p, _ = open_app(browser, seed=seed)
    import_text(p, json.dumps({"app": "bachateca", "figures": {}}), replace=True)
    assert "a" in p.evaluate("() => window.__bachateca.state()")["figures"]
    ctx.close()


# ---------------------------------------------------------------- vídeos sin copia
@test
def aviso_videos_sin_copia(browser):
    seed = {"figures": {f["id"]: f for f in [fig(1, "Cerrada", "Sombra", vid="v1"), fig(2, "Sombra", "Cerrada", vid="v2"),
                                              fig(3, "Sombra", "Cerrada")]}, "logs": {}}
    ctx, p, errors = open_app(browser, seed=seed, videos=["v1", "v2"])
    p.click("#btn-settings")
    note = p.locator('[data-act="save-vids"]')
    assert note.count() == 1 and "los 2" in note.inner_text(), note.all_inner_texts()
    assert "2 vídeos no tienen copia" in p.locator(".sheet").inner_text()
    p.evaluate("() => window.__bachateca.markVidSaved('f1', 'v1')")
    assert [f["id"] for f in p.evaluate("() => window.__bachateca.vidsUnsaved()")] == ["f2"]
    # Si cambias el vídeo de la figura, vuelve a contar como sin copia.
    p.evaluate("() => { const S = window.__bachateca.state(); S.figures.f1.vid = 'v9'; }")
    assert sorted(f["id"] for f in p.evaluate("() => window.__bachateca.vidsUnsaved()")) == ["f1", "f2"]
    # El botón comparte la tanda ya preparada (aquí no hay hoja de compartir: se descarga el primero).
    p.evaluate("() => { const S = window.__bachateca.state(); S.figures.f1.vid = 'v1'; }")
    p.keyboard.press("Escape")
    p.click("#btn-settings")
    p.wait_for_timeout(300)
    with p.expect_download() as dl:
        p.click('[data-act="save-vids"]')
    p.click('#confirm-root [data-cf="ok"]')
    assert dl.value.suggested_filename.startswith("Figura")
    p.wait_for_timeout(300)
    # Figura 2 es la más reciente, va primero; Figura 1 ya tenía copia: no queda ninguno.
    assert dl.value.suggested_filename == "Figura 2.mp4", dl.value.suggested_filename
    assert p.evaluate("() => window.__bachateca.vidsUnsaved().length") == 0
    assert "todos tus vídeos" in p.locator(".toast").inner_text()
    p.evaluate("() => window.__bachateca.flush()")
    p.wait_for_timeout(200)
    st = stored_state(p)
    assert sum(1 for f in st["figures"].values() if f.get("vid") and f.get("vidSaved") == f["vid"]) == 2
    assert not errors, errors
    ctx.close()


@test
def sin_videos_sin_aviso(browser):
    ctx, p, _ = open_app(browser, seed={"figures": {"a": fig(1, "Cerrada", "Sombra")}, "logs": {}})
    p.click("#btn-settings")
    assert p.locator('[data-act="save-vids"]').count() == 0
    ctx.close()


# ---------------------------------------------------------------- la app entera
@test
def recorrer_pestanas_sin_errores(browser):
    ctx, p, errors = open_app(browser)
    p.click('[data-act="examples"]')
    for t in ["repasar", "enlazar", "social", "repertorio"]:
        p.click(f'nav.tabs [data-tab="{t}"]')
        p.wait_for_timeout(150)
    p.click('nav.tabs [data-tab="repasar"]')
    p.click('[data-act="start-fig"]')
    p.click('[data-act="reveal"]')
    p.click('[data-grade="fluida"]')
    assert not errors, errors
    ctx.close()


# ---------------------------------------------------------------- Inicio (1.37)
def repertorio_inicio():
    """Figuras con repasos en distintos estados, un social con bloqueo y vídeo en una."""
    import datetime
    d = lambda n: (datetime.date.today() + datetime.timedelta(days=n)).isoformat()
    figs = [
        fig(1, "Cerrada", "Abierta 2 manos", estado="consolidada", rep={"step": 4, "due": d(10), "last": d(-20), "aciertos": 4, "fallos": 0}),
        fig(2, "Abierta 2 manos", "Sombra", rep={"step": 0, "due": d(0), "last": d(-1), "aciertos": 1, "fallos": 1}, vid="v1"),
        fig(3, "Sombra", "Abierta 1 mano", rep={"step": 1, "due": d(-6), "last": d(-9), "aciertos": 1, "fallos": 0}),
        fig(4, "Abierta 1 mano", "Cerrada", estado="disponible", rep={"step": 2, "due": d(0), "last": d(-7), "aciertos": 2, "fallos": 0}),
        fig(5, "Abierta 2 manos", "Hammerlock", estado="espera"),
    ]
    return {"figures": {f["id"]: f for f in figs},
            "logs": {"l1": {"id": "l1", "fecha": d(-2), "creado": 1, "figs": ["f1", "f4"], "bloqueo": "Sombra", "salio": "", "proximo": ""}},
            "linkRep": {"Sombra": {"step": 0, "due": d(0), "last": d(-3)}}}


@test
def inicio_con_datos(browser):
    ctx, p, errors = open_app(browser, seed=repertorio_inicio(), videos=["v1"])
    p.wait_for_timeout(400)
    v = p.locator("#v-inicio")
    assert v.is_visible(), "Inicio es la pantalla de entrada"
    txt = v.inner_text()
    assert "Tu entreno" in txt and "Empezar entreno" in txt, txt[:300]
    assert "Salidas desde Sombra" in txt and "te bloqueaste" in txt.lower(), "prioriza el bloqueo del último social"
    assert "Figuras que recuerdas" in txt
    ring = v.locator(".in-mem .in-big").inner_text()
    assert ring.startswith("3") and "de 4" in ring, ring      # 4 activas; olvidada solo la 2 (último repaso fallado); la 3 (6 días pendiente) está atrasada, no olvidada
    assert "1 atrasada" in v.locator(".in-mem").inner_text()
    assert "Olvidada" in v.locator(".carr").inner_text()
    assert v.locator("video[data-hvid]").count() == 1, "portada con el vídeo de la figura"
    st = stored_state(p)
    assert st["schema"] == p.evaluate("() => window.__bachateca.SCHEMA") and len(st["actividad"]) >= 3, st.get("actividad")
    assert not errors, errors
    ctx.close()


@test
def entreno_completo(browser):
    ctx, p, errors = open_app(browser, seed=repertorio_inicio())
    p.click('[data-mins="5"]')
    p.click('[data-act="train-start"]')
    assert p.locator("#v-repasar").is_visible()
    for _ in range(2):                                   # 5 min: 2 figuras
        p.click('[data-act="reveal"]'); p.click('[data-grade="fluida"]')
    p.click('[data-act="train-next"]')                   # sigue con las salidas
    assert "Sombra" in p.locator("#v-repasar .flash .big").inner_text()
    p.click('[data-act="reveal"]'); p.click('[data-grade="dudas"]')
    assert p.locator('[data-act="train-next"]').count() == 0, "con 5 min no hay cadena"
    p.click('[data-act="end"]')
    assert p.locator("#v-inicio").is_visible()
    import datetime
    p.evaluate("() => window.__bachateca.flush()"); p.wait_for_timeout(200)
    assert stored_state(p)["actividad"].get(datetime.date.today().isoformat()) == 3
    # 10 min: termina con una cadena en Enlazar
    p.click('[data-mins="10"]')
    p.click('[data-act="train-start"]')
    while p.locator('#v-repasar:visible [data-act="reveal"], #v-repasar:visible [data-act="train-next"]').count():
        if p.locator('#v-repasar:visible [data-act="train-next"]').count(): p.click('[data-act="train-next"]'); continue
        p.click('[data-act="reveal"]'); p.click('[data-grade="fluida"]')
        if not p.locator("#v-repasar").is_visible(): break
    assert p.locator("#v-enlazar").is_visible() and p.locator("#v-enlazar .chain").count() == 1
    assert not errors, errors
    ctx.close()


@test
def apariencia(browser):
    ctx, p, _ = open_app(browser)
    assert "theme-dark" in p.evaluate("() => document.documentElement.className"), "oscuro por defecto"
    bg = p.evaluate("() => getComputedStyle(document.body).backgroundColor")
    assert bg == "rgb(6, 12, 26)", bg
    p.click("#btn-settings"); p.click('[data-tema="claro"]')
    assert "theme-light" in p.evaluate("() => document.documentElement.className")
    p.reload(); p.wait_for_function("window.__bachateca && window.__bachateca.ready()")
    assert "theme-light" in p.evaluate("() => document.documentElement.className"), "se recuerda al volver a abrir"
    assert p.evaluate("() => getComputedStyle(document.body).backgroundColor") != "rgb(6, 12, 26)"
    ctx.close()


# ---------------------------------------------------------------- Rediseño (1.38)
@test
def ficha_y_filtros(browser):
    ctx, p, errors = open_app(browser, seed=repertorio_inicio())
    p.click('nav.tabs [data-tab="repertorio"]')
    p.click('[data-fest="espera"]')
    assert p.locator("#v-repertorio .gcard").count() == 1, "chip «Lista de espera» filtra"
    p.click('[data-fest="todos"]')
    assert p.locator("#v-repertorio .gcard").count() == 5
    p.click('#v-repertorio [data-view="f2"]')
    sheet = p.locator(".sheet")
    assert "Memoria" in sheet.inner_text() and "Olvidada" in sheet.inner_text()
    assert sheet.locator('[data-edit="f2"]').count() >= 1 and sheet.locator('[data-promote="f2"]').count() == 1, "editar y promocionar siguen"
    p.click('[data-act="rev-one"]')
    assert p.locator("#v-repasar").is_visible() and "1 de 1" in p.locator("#v-repasar").inner_text()
    p.click('[data-act="reveal"]'); p.click('[data-grade="fluida"]')
    assert "Repaso terminado" in p.locator("#v-repasar").inner_text() or "a compás" in p.locator("#v-repasar").inner_text()
    assert not errors, errors
    ctx.close()


@test
def portadas_desde_el_video(browser):
    """Con un vídeo real, la app saca miniatura y portada grande y la galería la muestra."""
    import base64
    seed = {"figures": {"f1": fig(1, "Cerrada", "Sombra", vid="v1")}, "logs": {}}
    ctx, p, errors = open_app(browser, seed=seed)
    data = base64.b64encode(open(os.path.join(ROOT, "tests", "fixtures", "prueba-vertical.mp4"), "rb").read()).decode()
    p.evaluate("""async b64 => { const bin = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
      const db = await new Promise(r => { const q = indexedDB.open("bachateca", 1); q.onsuccess = () => r(q.result); });
      await new Promise(r => { const t = db.transaction("videos", "readwrite"); t.objectStore("videos").put(new Blob([bin], {type: "video/mp4"}), "v1"); t.oncomplete = r; }); db.close(); }""", data)
    p.reload(); p.wait_for_function("window.__bachateca && window.__bachateca.ready()")
    p.wait_for_function("window.__bachateca.covers().includes('v1')", timeout=20000)
    p.evaluate("() => window.__bachateca.flush()"); p.wait_for_timeout(300)
    st = stored_state(p)
    assert st["figures"]["f1"].get("thumb", "").startswith("data:image/jpeg"), "miniatura"
    assert "cover" not in json.dumps(st), "la portada no va en los datos ni en la copia"
    p.click('nav.tabs [data-tab="repertorio"]')
    p.wait_for_selector("#v-repertorio img.gm.has-cover", timeout=5000)
    w = p.evaluate("() => document.querySelector('#v-repertorio img.gm').naturalWidth")
    assert w >= 300, f"portada grande ({w} px)"
    assert not errors, errors
    ctx.close()


# ---------------------------------------------------------------- intentos (grabarme)
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "prueba-vertical.mp4")


def stored_video_sizes(page):
    """Tamaño de cada vídeo guardado (sin las portadas)."""
    return page.evaluate("""() => new Promise(res => { const q = indexedDB.open("bachateca", 1);
      q.onsuccess = () => { const st = q.result.transaction("videos").objectStore("videos"), out = {};
        const c = st.openCursor(); c.onsuccess = () => { const k = c.result; if (!k) { q.result.close(); return res(out); }
          if (!String(k.key).startsWith("cover:")) out[k.key] = k.value.size; k.continue(); }; }; })""")


def att(i, vid, **kw):
    a = {"id": f"i{i}", "fecha": "2026-11-0" + str(i), "creado": 5000 + i, "vid": vid, "vidTrim": {"start": 0, "end": 0},
         "vidInfo": {"bytes": 2048, "dur": 4, "comprimido": False}}
    a.update(kw)
    return a


@test
def migracion_3_intentos(browser):
    ctx, p, _ = open_app(browser)
    r = p.evaluate("""() => { const B = window.__bachateca;
      const old = {schema: 2, figures: {a: {id: "a", nombre: "A"}, b: {id: "b", nombre: "B", intentos: [{id: "i1", vid: "x"}]}}};
      const m = B.migrate(old), m2 = B.migrate(m);
      return {m, same: JSON.stringify(m) === JSON.stringify(m2), S: B.SCHEMA}; }""")
    assert r["S"] >= 3 and r["m"]["schema"] == r["S"], r
    assert r["m"]["figures"]["a"]["intentos"] == [], "cada figura empieza con la lista vacía"
    i1 = r["m"]["figures"]["b"]["intentos"]
    assert len(i1) == 1 and i1[0]["id"] == "i1" and i1[0]["vid"] == "x", "no toca los intentos que ya hay"
    assert r["same"], "repetir la migración no cambia nada"
    ctx.close()


@test
def intento_grabado(browser):
    """Ficha → «Elegir de Fotos» → recorte → guardar: el intento queda en la figura y su vídeo en el almacén."""
    ctx, p, errors = open_app(browser, seed={"figures": {"f1": fig(1, "Cerrada", "Sombra")}, "logs": {}})
    p.click('nav.tabs [data-tab="repertorio"]')
    p.click('#v-repertorio [data-view="f1"]')
    card = p.locator("section:has(#fv-i)")
    assert "Mis intentos" in card.inner_text() and "Grábate" in card.inner_text()
    assert p.locator("#att-cam").get_attribute("capture") == "environment", "«Grabarme» abre la cámara"
    p.set_input_files("#att-lib", FIXTURE)
    p.wait_for_selector("#att-form #ff-prev")
    assert p.locator("#ff-compact").is_checked(), "en los intentos se reduce el vídeo por defecto"
    assert p.locator('[data-vid="ai"]').count() == 0, "sin «Identificar con Claude»"
    p.wait_for_function("document.querySelector('#ff-prev').readyState >= 1")
    p.evaluate("""() => new Promise(r => { const v = document.querySelector('#ff-prev'); v.onseeked = r; v.currentTime = 0.5; })""")
    p.click('[data-vid="start"]')
    p.uncheck("#ff-compact")
    p.click('#att-form button[type="submit"]')
    p.wait_for_selector('[data-viewfig="f1"]', timeout=15000)
    assert "Intento guardado" in p.locator(".toast").inner_text()
    assert "Mis intentos · 1" in p.locator("section:has(#fv-i)").inner_text()
    p.evaluate("() => window.__bachateca.flush()"); p.wait_for_timeout(300)
    st = stored_state(p)
    ints = st["figures"]["f1"]["intentos"]
    assert len(ints) == 1, ints
    a = ints[0]
    assert abs(a["vidTrim"]["start"] - 0.5) < 0.05 and a["fecha"] == p.evaluate("() => window.__bachateca.todayStr()"), a
    assert a["vidInfo"]["comprimido"] is False and a.get("thumb", "").startswith("data:image/jpeg"), a.get("vidInfo")
    assert stored_video_sizes(p).get(a["vid"]) == os.path.getsize(FIXTURE), "el vídeo está en el almacén de vídeos"
    assert [x.get("att") for x in p.evaluate("() => window.__bachateca.vidsUnsaved()")] == [a["id"]], "cuenta en el aviso de copias"
    # Abrir el intento y guardarlo en Fotos: deja de contar como sin copia.
    p.click(f'[data-act="att-open"][data-att="{a["id"]}"]')
    p.wait_for_selector(f'[data-viewatt="{a["id"]}"] video')
    p.wait_for_timeout(300)
    with p.expect_download() as dl:
        p.click('[data-act="att-savevid"]')
    p.click('#confirm-root [data-cf="ok"]')
    assert dl.value.suggested_filename.startswith("Figura 1 · intento"), dl.value.suggested_filename
    p.wait_for_timeout(200)
    assert p.evaluate("() => window.__bachateca.vidsUnsaved().length") == 0
    assert not errors, errors
    ctx.close()


@test
def intento_en_aviso_de_copias(browser):
    f1 = fig(1, "Cerrada", "Sombra", vid="v1", vidSaved="v1", intentos=[att(1, "a1"), att(2, "a2", vidSaved="a2")])
    ctx, p, errors = open_app(browser, seed={"schema": 3, "figures": {"f1": f1}, "logs": {}}, videos=["v1", "a1", "a2"])
    us = p.evaluate("() => window.__bachateca.vidsUnsaved()")
    assert [(x["id"], x.get("att"), x["vid"]) for x in us] == [("f1", "i1", "a1")], us
    p.click("#btn-settings")
    assert "1 vídeo no tiene copia" in p.locator(".sheet").inner_text()
    p.evaluate("() => window.__bachateca.markVidSaved('f1', 'a1')")
    assert p.evaluate("() => window.__bachateca.vidsUnsaved().length") == 0
    assert not errors, errors
    ctx.close()


@test
def borrar_intento_y_figura_borra_videos(browser):
    f1 = fig(1, "Cerrada", "Sombra", vid="v1", intentos=[att(1, "a1"), att(2, "a2")])
    f2 = fig(2, "Sombra", "Cerrada", intentos=[att(3, "a3")])
    ctx, p, errors = open_app(browser, seed={"schema": 3, "figures": {"f1": f1, "f2": f2}, "logs": {}}, videos=["v1", "a1", "a2", "a3"])
    p.click('nav.tabs [data-tab="repertorio"]')
    p.click('#v-repertorio [data-view="f1"]')
    p.click('[data-act="att-open"][data-att="i1"]')
    p.click('[data-act="att-del"]')
    p.click('#confirm-root [data-cf="ok"]')
    p.wait_for_selector('[data-viewfig="f1"]')
    assert "Mis intentos · 1" in p.locator("section:has(#fv-i)").inner_text()
    # Deshacer lo recupera; volver a borrarlo y dejar que caduque el aviso borra el vídeo.
    p.click(".toast .undo")
    assert "Mis intentos · 2" in p.locator("section:has(#fv-i)").inner_text()
    p.click('[data-act="att-open"][data-att="i1"]')
    p.click('[data-act="att-del"]')
    p.click('#confirm-root [data-cf="ok"]')
    p.evaluate("() => document.activeElement && document.activeElement.blur()")   # con «Deshacer» enfocado el aviso espera más
    p.wait_for_function("!document.querySelector('.toast') || document.querySelector('.toast').hidden", timeout=15000)
    p.wait_for_timeout(300)
    assert sorted(stored_video_sizes(p)) == ["a2", "a3", "v1"], stored_video_sizes(p)
    # Borrar la figura borra su vídeo y los de sus intentos, no los de otras figuras.
    p.evaluate("() => window.__bachateca.deleteFigure('f1')")
    p.wait_for_timeout(300)
    assert sorted(stored_video_sizes(p)) == ["a3"], stored_video_sizes(p)
    assert not errors, errors
    ctx.close()


@test
def importar_conserva_intentos_locales(browser):
    ctx, p, errors = open_app(browser, seed={"schema": 3, "figures": {"f1": fig(1, "Cerrada", "Sombra", intentos=[att(1, "a1")])}, "logs": {}},
                              videos=["a1"])
    old = {"app": "bachateca", "version": 3, "schema": 2, "figures": {"f1": fig(1, "Cerrada", "Sombra", nombre="Renombrada")}, "logs": {}}
    import_text(p, json.dumps(old))
    p.click('#confirm-root [data-cf="ok"]')
    p.wait_for_timeout(300)
    f = p.evaluate("() => window.__bachateca.state().figures.f1")
    assert f["nombre"] == "Renombrada", "se aplica la copia"
    assert [a["id"] for a in f["intentos"]] == ["i1"], "el intento que solo está en este dispositivo se queda"
    assert not errors, errors
    ctx.close()


# ---------------------------------------------------------------- pulso de cada vídeo
def put_fixture(page, vid_ids):
    """Guarda el vídeo de prueba real con esos ids (para reproducirlo en la app) y recarga."""
    import base64
    data = base64.b64encode(open(FIXTURE, "rb").read()).decode()
    page.evaluate("""async ([b64, ids]) => { const bin = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
      const db = await new Promise(r => { const q = indexedDB.open("bachateca", 1); q.onsuccess = () => r(q.result); });
      await new Promise(r => { const t = db.transaction("videos", "readwrite");
        ids.forEach(id => t.objectStore("videos").put(new Blob([bin], {type: "video/mp4"}), id)); t.oncomplete = r; }); db.close(); }""", [data, vid_ids])
    page.reload(); page.wait_for_function("window.__bachateca && window.__bachateca.ready()")


def tap_at(page, sec):
    """Pausa el vídeo de la hoja en ese segundo y toca «Toca en el…»."""
    page.evaluate("""s => new Promise(r => { const v = document.querySelector('[data-pulso] video'); v.pause();
      if (Math.abs(v.currentTime - s) < 0.001) return r(); v.addEventListener('seeked', () => r(), {once: true}); v.currentTime = s; })""", sec)
    page.click("#pk-tap")


@test
def pulso_correspondencia(browser):
    """Tiempo de la música ↔ segundo del vídeo, por tramos rectos entre las marcas."""
    ctx, p, _ = open_app(browser)
    r = p.evaluate("""() => { const B = window.__bachateca, P = {vid: "v", marcas: [{b: 5, s: 4}, {b: 1, s: 2}, {b: 8, s: 5.8}]};
      return {b3: B.beatToSec(P, 3), b65: B.beatToSec(P, 6.5), b9: B.beatToSec(P, 9), b0: B.beatToSec(P, 0),
              s3: B.secToBeat(P, 3), s49: B.secToBeat(P, 4.9), back: B.secToBeat(P, B.beatToSec(P, 7.25)), bpm: B.pulsoBpm(P),
              ok: B.pulsoOk(P, "v"), otro: B.pulsoOk(P, "w"), uno: B.beatToSec({marcas: [{b: 1, s: 1}]}, 2),
              bien: B.checkMarcas(P.marcas), solo: B.checkMarcas([{b: 1, s: 1}]),
              hueco: B.checkMarcas([{b: 1, s: 1}, {b: 2, s: 1.5}, {b: 3, s: 2.5}]),
              doble: B.checkMarcas([{b: 1, s: 1}, {b: 2, s: 1.1}]),
              atras: B.checkMarcas([{b: 1, s: 2}, {b: 2, s: 1.5}]),
              extremos: B.checkMarcas([{b: 1, s: 1}, {b: 8, s: 4.5}]),
              lento: B.checkMarcas([{b: 1, s: 1}, {b: 8, s: 9}])}; }""")
    approx = lambda a, b: abs(a - b) < 1e-9
    assert approx(r["b3"], 3) and approx(r["b65"], 4.9), r            # 0,5 s por tiempo del 1 al 5; 0,6 s del 5 al 8
    assert approx(r["b9"], 6.4) and approx(r["b0"], 1.5), r           # fuera de las marcas, con el ritmo del tramo más cercano
    assert approx(r["s3"], 3) and approx(r["s49"], 6.5) and approx(r["back"], 7.25), r
    assert r["bpm"] == 111, r                                         # 7 tiempos en 3,8 s: 110,5
    assert r["ok"] and not r["otro"], "el pulso solo vale para su vídeo"
    assert r["uno"] is None, "con una marca no hay correspondencia"
    assert r["bien"] is None and r["extremos"] is None, r
    assert "al menos" in r["solo"] and "saltado" in r["hueco"] and "2 y el 3" in r["hueco"], r
    assert "dos veces" in r["doble"] and "hacia delante" in r["atras"] and "lento" in r["lento"], r
    ctx.close()


@test
def migracion_4_pulso(browser):
    ctx, p, _ = open_app(browser)
    r = p.evaluate("""() => { const B = window.__bachateca;
      const old = {schema: 3, figures: {a: {id: "a", nombre: "A", intentos: [], pulso: {vid: "v", marcas: [{b: 1, s: 0}, {b: 2, s: .5}]}}}};
      const m = B.migrate(old); return {m, same: JSON.stringify(B.migrate(m)) === JSON.stringify(m), S: B.SCHEMA}; }""")
    assert r["S"] >= 4 and r["m"]["schema"] == r["S"] and r["same"], r
    assert r["m"]["figures"]["a"]["pulso"]["marcas"][1]["s"] == 0.5, "conserva el pulso"
    ctx.close()


@test
def marcar_pulso_del_video_de_la_clase(browser):
    seed = {"schema": 4, "figures": {"f1": fig(1, "Cerrada", "Sombra", vid="v1", tiempo="1", tiempos="4")}, "logs": {}}
    ctx, p, errors = open_app(browser, seed=seed)
    put_fixture(p, ["v1"])
    p.click('nav.tabs [data-tab="repertorio"]')
    p.click('#v-repertorio [data-view="f1"]')
    card = p.locator("section:has(#fv-p)")
    assert "Sin marcar" in card.inner_text()
    p.click('[data-act="pk-open"]')
    p.wait_for_function("document.querySelector('[data-pulso] video').readyState >= 1")
    assert p.evaluate("() => document.querySelector('[data-pulso] video').playbackRate") == 0.5, "se marca a 0,5×"
    assert "Toca en el 1" in " ".join(p.locator("#pk-tap").inner_text().split())
    assert p.locator("#pk-save").is_disabled()
    # Un hueco (te saltas un tiempo) se avisa y no deja guardar; Deshacer lo arregla.
    tap_at(p, 0.2); tap_at(p, 1.2)
    assert "saltado" in p.locator("#pk-st").inner_text() and p.locator("#pk-save").is_disabled()
    p.click("#pk-undo")
    # Volver atrás en el vídeo y tocar no estropea las marcas.
    tap_at(p, 0.1)
    assert "antes que el anterior" in p.locator("#pk-st").inner_text()
    tap_at(p, 0.7); tap_at(p, 1.2); tap_at(p, 1.7)
    assert p.locator("#pk-tap").is_disabled() and "4 de 4 marcas · 120 golpes por minuto" in p.locator("#pk-st").inner_text()
    p.evaluate("""() => new Promise(r => { const v = document.querySelector('[data-pulso] video'); v.addEventListener('seeked', () => r(), {once: true}); v.currentTime = 1.25; })""")
    p.wait_for_timeout(100)
    assert p.locator("#pk-strip i.now").inner_text() == "3", "muestra en qué tiempo va el vídeo"
    p.click("#pk-save")
    p.wait_for_selector('[data-viewfig="f1"]')
    assert "120 bpm" in p.locator("section:has(#fv-p)").inner_text() and "4 tiempos marcados" in p.locator("section:has(#fv-p)").inner_text()
    p.evaluate("() => window.__bachateca.flush()"); p.wait_for_timeout(300)
    pu = stored_state(p)["figures"]["f1"]["pulso"]
    assert pu["vid"] == "v1" and pu["modo"] == "todos" and [m["b"] for m in pu["marcas"]] == [1, 2, 3, 4], pu
    assert [round(m["s"], 2) for m in pu["marcas"]] == [0.2, 0.7, 1.2, 1.7], pu
    # Si cambias el vídeo de la figura, el pulso deja de valer.
    p.evaluate("() => { const S = window.__bachateca.state(); S.figures.f1.vid = 'v2'; }")
    assert not p.evaluate("() => window.__bachateca.pulsoOk(window.__bachateca.state().figures.f1.pulso, 'v2')")
    assert not errors, errors
    ctx.close()


@test
def marcar_pulso_de_un_intento_solo_extremos(browser):
    """Lo mínimo: el primer y el último tiempo. Una figura que empieza en el 5 cuenta 5, 6, 7, 8."""
    seed = {"schema": 4, "figures": {"f1": fig(1, "Cerrada", "Sombra", tiempo="5", tiempos="4", intentos=[att(1, "a1")])}, "logs": {}}
    ctx, p, errors = open_app(browser, seed=seed)
    put_fixture(p, ["a1"])
    p.click('nav.tabs [data-tab="repertorio"]')
    p.click('#v-repertorio [data-view="f1"]')
    assert p.locator("section:has(#fv-p)").count() == 0, "sin vídeo de la clase no hay pulso que marcar"
    p.click('[data-act="att-open"][data-att="i1"]')
    p.click('[data-act="pk-open"][data-att="i1"]')
    p.wait_for_function("document.querySelector('[data-pulso] video').readyState >= 1")
    p.click('[data-pkmodo="extremos"]')
    assert "Toca en el 5" in " ".join(p.locator("#pk-tap").inner_text().split())
    tap_at(p, 0.3)
    assert "Toca en el 8" in " ".join(p.locator("#pk-tap").inner_text().split())
    tap_at(p, 1.8)
    assert "golpes por minuto" in p.locator("#pk-st").inner_text()
    # Cerrar con marcas sin guardar pregunta antes.
    p.click('[data-act="close"]')
    assert p.locator("#confirm-root .confirm").count() == 1
    p.click('#confirm-root [data-cf="no"]')
    p.click("#pk-save")
    p.wait_for_selector('[data-viewatt="i1"]')
    assert "120 bpm" in p.locator('[data-viewatt="i1"]').inner_text()
    pu = p.evaluate("() => window.__bachateca.state().figures.f1.intentos[0].pulso")
    assert pu["vid"] == "a1" and pu["modo"] == "extremos" and [m["b"] for m in pu["marcas"]] == [5, 8], pu
    p.click('[data-viewatt] [data-view="f1"]')
    assert "120 bpm" in p.locator("section:has(#fv-i)").inner_text(), "el pulso del intento se ve en la lista"
    # Quitar el pulso.
    p.click('[data-act="att-open"][data-att="i1"]')
    p.click('[data-act="pk-open"][data-att="i1"]')
    p.click("#pk-del")
    p.wait_for_selector('[data-viewatt="i1"]')
    assert "pulso" not in p.evaluate("() => window.__bachateca.state().figures.f1.intentos[0]")
    assert not errors, errors
    ctx.close()


# ---------------------------------------------------------------- comparar por tiempos
def cmp_seed(**kw):
    """La clase a 0,5 s por tiempo (120 bpm) y el intento a 0,3 s (200 bpm): otro pulso, que no es un fallo."""
    a = att(1, "a1", pulso={"vid": "a1", "modo": "todos", "marcas": [{"b": 1, "s": 0.1}, {"b": 2, "s": 0.4}, {"b": 3, "s": 0.7}, {"b": 4, "s": 1.0}]}, marcadores=[])
    f = fig(1, "Cerrada", "Sombra", vid="v1", tiempo="1", tiempos="4", errores=[], intentos=[a],
            pulso={"vid": "v1", "modo": "extremos", "marcas": [{"b": 1, "s": 0.2}, {"b": 4, "s": 1.7}]})
    f.update(kw)
    return {"schema": 5, "figures": {"f1": f}, "logs": {}}


def times(page):
    return page.evaluate("() => [document.querySelector('#cmp-t').currentTime, document.querySelector('#cmp-m').currentTime]")


def wait_seeked(page):
    page.wait_for_function("!document.querySelector('#cmp-t').seeking && !document.querySelector('#cmp-m').seeking")


@test
def migracion_5_marcas_y_errores(browser):
    ctx, p, _ = open_app(browser)
    r = p.evaluate("""() => { const B = window.__bachateca;
      const old = {schema: 4, figures: {a: {id: "a", nombre: "A", intentos: [{id: "i1", vid: "x"}]}, b: {id: "b", nombre: "B", errores: [{id: "e", nota: "n"}]}}};
      const m = B.migrate(old); return {m, same: JSON.stringify(B.migrate(m)) === JSON.stringify(m), S: B.SCHEMA}; }""")
    m = r["m"]["figures"]
    assert r["S"] >= 5 and r["m"]["schema"] == r["S"] and r["same"], r
    assert m["a"]["errores"] == [] and m["a"]["intentos"][0]["marcadores"] == [], m
    assert m["b"]["errores"] == [{"id": "e", "nota": "n"}], m
    ctx.close()


@test
def comparar_falta_el_pulso(browser):
    seed = cmp_seed(pulso=None)
    ctx, p, errors = open_app(browser, seed=seed)
    p.click('nav.tabs [data-tab="repertorio"]'); p.click('#v-repertorio [data-view="f1"]')
    p.click('[data-act="att-open"][data-att="i1"]')
    assert p.locator('[data-act="cmp-open"]').count() == 0
    txt = p.locator("section:has(#fv-cmp)").inner_text()
    assert "falta marcar el pulso del vídeo de la clase" in txt and "de este intento" not in txt, txt
    assert p.locator('section:has(#fv-cmp) [data-act="pk-open"]').count() == 1
    assert not errors, errors
    ctx.close()


@test
def comparar_por_tiempos(browser):
    """El 3 de la clase con tu 3: cada vídeo en su segundo, aunque vayan a otro pulso."""
    ctx, p, errors = open_app(browser, seed=cmp_seed())
    put_fixture(p, ["v1", "a1"])
    p.click('nav.tabs [data-tab="repertorio"]'); p.click('#v-repertorio [data-view="f1"]')
    p.click('[data-act="att-open"][data-att="i1"]')
    p.click('[data-act="cmp-open"]')
    p.wait_for_selector("[data-cmp] #cmp-line [data-cb]")
    p.wait_for_function("document.querySelector('#cmp-t').readyState >= 1 && document.querySelector('#cmp-m').readyState >= 1")
    wait_seeked(p)
    assert "200 bpm" in p.locator("#cmp-tempo").inner_text() and "120" in p.locator("#cmp-tempo").inner_text()
    assert "no un fallo" in p.locator("#cmp-tempo").inner_text(), "el pulso es un dato"
    assert [round(x, 2) for x in times(p)] == [0.2, 0.1], times(p)            # los dos en su 1
    assert p.locator("#cmp-line [data-cb]").all_inner_texts() == ["1", "2", "3", "4"]
    p.click('#cmp-line [data-cb="3"]'); wait_seeked(p)
    assert [round(x, 2) for x in times(p)] == [1.2, 0.7], times(p)            # el 3 de la clase y tu 3
    assert p.locator("#cmp-b").inner_text() == "3" and "cur" in p.locator('#cmp-line [data-cb="3"]').get_attribute("class")
    p.click("#cmp-next"); wait_seeked(p)
    assert [round(x, 2) for x in times(p)] == [1.7, 1.0] and p.locator("#cmp-b").inner_text() == "4", times(p)
    p.click("#cmp-prev"); p.click("#cmp-prev"); wait_seeked(p)
    assert p.locator("#cmp-b").inner_text() == "2", "tiempo a tiempo hacia atrás"
    p.click("#cmp-mirror")
    assert "mirror" in p.locator("#cmp-t").get_attribute("class"), "espejo de la clase"
    # Tramo del 2 al 3 en bucle, a 1×: tu vídeo sigue a la clase tiempo a tiempo.
    p.click("#cmp-range"); p.click('#cmp-line [data-cb="2"]'); p.click('#cmp-line [data-cb="3"]')
    assert p.locator("#cmp-range").inner_text() == "Tramo: 2–3" and "out" in p.locator('#cmp-line [data-cb="1"]').get_attribute("class")
    p.click("#cmp-play")
    p.wait_for_timeout(1600)                                                   # más de una vuelta del tramo (1 s)
    r = p.evaluate("""() => { const B = window.__bachateca, S = B.state().figures.f1, t = document.querySelector('#cmp-t').currentTime, m = document.querySelector('#cmp-m').currentTime;
      const b = B.secToBeat(S.pulso, t); return {b, err: m - B.beatToSec(S.intentos[0].pulso, b), st: B.cmpState()}; }""")
    assert r["st"]["playing"] and 1.9 <= r["b"] < 4.05, r                     # dentro del tramo (vuelve al 2)
    assert abs(r["err"]) < 0.2, r                                              # tu vídeo en el mismo tiempo que la clase
    p.click("#cmp-play")
    assert not p.evaluate("() => window.__bachateca.cmpState().playing")
    assert not errors, errors
    ctx.close()


@test
def comparar_empieza_en_el_1_aunque_se_pierda_el_salto(browser):
    """En el iPhone, el salto inicial al 1 a veces se pierde y la clase empezaba desde el principio del archivo (en el 7)."""
    # El 1 de la clase en el segundo 1,0 a 200 bpm: el principio del archivo cae unos 3 tiempos antes (en el 6–7).
    seed = cmp_seed(pulso={"vid": "v1", "modo": "extremos", "marcas": [{"b": 1, "s": 1.0}, {"b": 4, "s": 1.9}]})
    ctx, p, errors = open_app(browser, seed=seed)
    put_fixture(p, ["v1", "a1"])
    p.click('nav.tabs [data-tab="repertorio"]'); p.click('#v-repertorio [data-view="f1"]')
    p.click('[data-act="att-open"][data-att="i1"]'); p.click('[data-act="cmp-open"]')
    p.wait_for_function("document.querySelector('#cmp-t').readyState >= 2 && document.querySelector('#cmp-m').readyState >= 2")
    wait_seeked(p)
    beat = """() => { const B = window.__bachateca, S = B.state().figures.f1, t = document.querySelector('#cmp-t').currentTime, m = document.querySelector('#cmp-m').currentTime;
      const b = B.secToBeat(S.pulso, t); return {t, b, err: m - B.beatToSec(S.intentos[0].pulso, b), st: B.cmpState()}; }"""
    # 1) El salto se pierde antes de reproducir: los dos vídeos siguen en el segundo 0.
    p.evaluate("() => { document.querySelector('#cmp-t').currentTime = 0; document.querySelector('#cmp-m').currentTime = 0; }")
    wait_seeked(p)
    p.click("#cmp-play")
    p.wait_for_timeout(120)
    r = p.evaluate(beat)
    assert r["st"]["playing"] and 0.95 <= r["b"] < 2.5, r                    # la clase arranca en su 1, no en el 6–7
    assert abs(r["err"]) < 0.2, r
    # 2) Ya en marcha, la clase vuelve al principio del archivo: se lleva al 1 una vez.
    p.evaluate("() => { document.querySelector('#cmp-t').currentTime = 0; }")
    p.wait_for_timeout(150)
    r = p.evaluate(beat)
    assert r["st"]["playing"] and 0.95 <= r["b"] < 2.5, r
    assert abs(r["err"]) < 0.2, r
    p.click("#cmp-play")
    assert not errors, errors
    ctx.close()


@test
def marcas_y_errores_que_cometo(browser):
    ctx, p, errors = open_app(browser, seed=cmp_seed())
    put_fixture(p, ["v1", "a1"])
    p.click('nav.tabs [data-tab="repertorio"]'); p.click('#v-repertorio [data-view="f1"]')
    p.click('[data-act="att-open"][data-att="i1"]'); p.click('[data-act="cmp-open"]')
    p.wait_for_function("document.querySelector('#cmp-t') && document.querySelector('#cmp-t').readyState >= 1 && document.querySelector('#cmp-m').readyState >= 1")
    p.click('#cmp-line [data-cb="4"]')
    p.click('[data-cmk="error"]')
    assert "Error en el 4" in p.locator("#cmp-form").inner_text()
    p.fill("#cmp-nota", "el brazo izquierdo se queda bajo")
    p.check("#cmp-toerr")
    p.click("#cmp-fsave")
    p.click('#cmp-line [data-cb="2"]')
    p.click('[data-cmk="bien"]'); p.click("#cmp-fsave")
    p.click('[data-cmk="error"]'); p.fill("#cmp-nota", "me adelanto"); p.click("#cmp-fsave")
    assert "mk" in p.locator('#cmp-line [data-cb="4"]').get_attribute("class"), "la marca se ve en la línea"
    items = p.locator("#cmp-marks li").all_inner_texts()
    assert len(items) == 3 and "en el 2" in items[0] and "en el 4" in items[2] and "En tus errores" in items[2], items
    # Un error que no estaba en tus errores puede pasar después.
    p.click("#cmp-marks [data-cerr]")
    f = p.evaluate("() => window.__bachateca.state().figures.f1")
    assert [m["tipo"] for m in sorted(f["intentos"][0]["marcadores"], key=lambda m: m["b"])] == ["bien", "error", "error"], f["intentos"][0]["marcadores"]
    assert sorted(e["nota"] for e in f["errores"]) == ["el brazo izquierdo se queda bajo", "me adelanto"], f["errores"]
    assert all(e["desde"] == "i1" for e in f["errores"])
    # Las marcas se ven en el intento; los errores, en la ficha y al repasar la figura.
    p.click('[data-act="cmp-back"]')
    assert "Tus marcas" in p.locator('[data-viewatt="i1"]').inner_text()
    p.click('[data-viewatt] [data-view="f1"]')
    assert "el brazo izquierdo se queda bajo" in p.locator("section:has(#fv-e)").inner_text()
    p.click('[data-act="rev-one"]')
    assert "Ojo con" in p.locator("#v-repasar").inner_text() and "me adelanto" in p.locator("#v-repasar").inner_text()
    # Quitar un error desde la ficha.
    p.click('[data-tab="repertorio"]'); p.click('#v-repertorio [data-view="f1"]')
    p.click('section:has(#fv-e) [data-act="err-del"] >> nth=0')
    assert len(p.evaluate("() => window.__bachateca.state().figures.f1.errores")) == 1
    p.evaluate("() => window.__bachateca.flush()"); p.wait_for_timeout(300)
    assert len(stored_state(p)["figures"]["f1"]["intentos"][0]["marcadores"]) == 3
    assert not errors, errors
    ctx.close()


# ---------------------------------------------------------------- figuras incompletas (se enseñan por partes)
def inc_fig(**kw):
    """Una figura que aún nos están enseñando: sin salida conocida y con el vídeo de la última clase."""
    f = fig(1, "Cerrada", "", estado="incompleta", vid="v1", vidTrim={"start": 0, "end": 0}, parteFecha="2026-10-30",
            rep={"step": 0, "due": "2026-10-30", "aciertos": 0, "fallos": 0}, partes=[], intentos=[], errores=[])
    f.update(kw)
    return f


@test
def migracion_6_partes(browser):
    ctx, p, _ = open_app(browser)
    r = p.evaluate("""() => { const B = window.__bachateca;
      const old = {schema: 5, figures: {a: {id: "a", nombre: "A"}, b: {id: "b", nombre: "B", partes: [{id: "x", fecha: "2026-11-01"}]}}};
      const m = B.migrate(old); return {m, same: JSON.stringify(B.migrate(m)) === JSON.stringify(m), S: B.SCHEMA}; }""")
    assert r["S"] >= 6 and r["m"]["schema"] == r["S"] and r["same"], r
    assert r["m"]["figures"]["a"]["partes"] == [] and r["m"]["figures"]["b"]["partes"][0]["id"] == "x", r["m"]
    ctx.close()


@test
def incompleta_por_partes(browser):
    """Cada clase trae un vídeo que junta lo anterior y lo nuevo: pasa a ser el de la figura y el anterior queda en Partes."""
    ctx, p, errors = open_app(browser, seed={"schema": 6, "figures": {"f1": inc_fig()}, "logs": {}})
    put_fixture(p, ["v1"])
    p.click('nav.tabs [data-tab="repertorio"]')
    p.click('[data-fest="incompleta"]')
    assert p.locator("#v-repertorio .gcard").count() == 1 and "Incompleta" in p.locator("#v-repertorio .gcard").inner_text()
    assert p.locator('[data-fest="incompletas"]').inner_text() == "Sin entrada/salida", "el filtro de antes cambia de nombre"
    p.click('#v-repertorio [data-view="f1"]')
    card = p.locator("section:has(#fv-pt)")
    assert "Partes · 1" in card.inner_text() and "Parte 1 · 30 oct" in card.inner_text(), card.inner_text()
    assert p.locator('[data-act="inc-done"]').count() == 1 and p.locator('[data-promote="f1"]').count() == 0
    assert "Falta dónde acaba" not in p.locator(".sheet").inner_text(), "una incompleta no pide la salida"
    # Parte 2: el vídeo de hoy, con nota.
    p.click('[data-act="pt-new"]')
    assert p.locator('[data-vid="ai"]').count() == 0 and p.locator("#ff-cam").count() == 1
    p.set_input_files("#ff-file", FIXTURE)
    p.wait_for_selector("#pt-form #ff-prev")
    p.wait_for_function("document.querySelector('#ff-prev').readyState >= 1")
    p.fill("#pt-nota", "el giro final")
    p.click('#pt-form button[type="submit"]')
    p.wait_for_selector('[data-viewfig="f1"]', timeout=15000)
    assert "Parte 2 guardada" in p.locator(".toast").inner_text()
    card = p.locator("section:has(#fv-pt)").inner_text()
    assert "Partes · 2" in card and "Parte 2 ·" in card and "el giro final" in card and "Parte 1 · 30 oct" in card, card
    f = p.evaluate("() => window.__bachateca.state().figures.f1")
    hoy = p.evaluate("() => window.__bachateca.todayStr()")
    assert f["vid"] != "v1" and f["parteFecha"] == hoy and f["parteNota"] == "el giro final", f
    assert [(x["vid"], x["fecha"]) for x in f["partes"]] == [("v1", "2026-10-30")], f["partes"]
    assert f["rep"]["due"] == hoy, "lo nuevo se repasa hoy"
    assert sorted(stored_video_sizes(p)) == sorted(["v1", f["vid"]]), "los dos vídeos siguen guardados"
    assert {x.get("parte") for x in p.evaluate("() => window.__bachateca.vidsUnsaved()")} == {None, f["partes"][0]["id"]}, "las partes cuentan en el aviso de copias"
    # Ver la parte 1 y borrarla, con Deshacer.
    pid = f["partes"][0]["id"]
    p.click(f'[data-act="pt-open"][data-pt="{pid}"]')
    p.wait_for_selector(f'[data-viewpt="{pid}"] video')
    assert "Parte 1 · 30 oct" in p.locator(".sheet").inner_text()
    p.click('[data-act="pt-del"]'); p.click('#confirm-root [data-cf="ok"]')
    p.wait_for_selector('[data-viewfig="f1"]')
    assert "Partes · 1" in p.locator("section:has(#fv-pt)").inner_text()
    p.click(".toast .undo")
    assert "Partes · 2" in p.locator("section:has(#fv-pt)").inner_text()
    assert not errors, errors
    ctx.close()


@test
def incompleta_se_repasa_cada_dia(browser):
    ctx, p, errors = open_app(browser, seed={"schema": 6, "figures": {"f1": inc_fig(rep={"step": 3, "due": "2026-10-30", "aciertos": 3, "fallos": 0})}, "logs": {}})
    p.click('nav.tabs [data-tab="repertorio"]')
    p.click('#v-repertorio [data-view="f1"]')
    p.click('[data-act="rev-one"]')
    p.click('[data-act="reveal"]'); p.click('[data-grade="fluida"]')
    r = p.evaluate("() => ({f: window.__bachateca.state().figures.f1, t1: window.__bachateca.todayStr(1)})")
    assert r["f"]["rep"]["due"] == r["t1"], r["f"]["rep"]                     # mañana otra vez, aunque fuera fluida
    assert not errors, errors
    ctx.close()


@test
def incompleta_fuera_de_social_y_enlazar(browser):
    figs = {"f1": inc_fig(salida="Sombra"), "f2": fig(2, "Cerrada", "Sombra", estado="disponible"), "f3": fig(3, "Sombra", "Cerrada")}
    ctx, p, errors = open_app(browser, seed={"schema": 6, "figures": figs, "logs": {}})
    ids = p.evaluate("() => window.__bachateca.exitsFrom('Cerrada').map(f => f.id)")
    assert ids == ["f2"], ids
    p.click('nav.tabs [data-tab="social"]')
    p.check("#soc-incl")                                                        # ni con «Incluir las que están en práctica»
    txt = p.locator("#v-social").inner_text()
    assert "Figura 2" in txt and "Figura 3" in txt and "Figura 1" not in txt, txt
    assert not errors, errors
    ctx.close()


@test
def ya_esta_completa(browser):
    """Termina: pasa a Disponible, entra en el repaso normal y puede borrar los vídeos de las partes anteriores."""
    f = inc_fig(salida="Sombra", partes=[{"id": "p1", "fecha": "2026-10-23", "creado": 1, "vid": "v0"}])
    ctx, p, errors = open_app(browser, seed={"schema": 6, "figures": {"f1": f}, "logs": {}}, videos=["v0", "v1"])
    p.click('nav.tabs [data-tab="repertorio"]')
    p.click('#v-repertorio [data-view="f1"]')
    p.click('[data-act="inc-done"]')
    assert "el vídeo de la parte anterior" in p.locator("#inc-form").inner_text()
    p.click('[data-incto="disponible"]')
    p.check("#inc-del")
    p.click('#inc-form button[type="submit"]')
    p.wait_for_selector('[data-viewfig="f1"]')
    g = p.evaluate("() => window.__bachateca.state().figures.f1")
    assert g["estado"] == "disponible" and g["partes"] == [] and g["vid"] == "v1", g
    assert p.locator("section:has(#fv-pt)").count() == 0, "sin partes no hay tarjeta"
    p.wait_for_timeout(300)
    assert sorted(stored_video_sizes(p)) == ["v1"], stored_video_sizes(p)
    assert not errors, errors
    ctx.close()


@test
def ya_esta_completa_pide_la_salida(browser):
    """Si aún no pone dónde acaba, se abre la ficha para completarlo; las partes se quedan (no se marcó borrarlas)."""
    f = inc_fig(partes=[{"id": "p1", "fecha": "2026-10-23", "creado": 1, "vid": "v0"}])
    ctx, p, errors = open_app(browser, seed={"schema": 6, "figures": {"f1": f}, "logs": {}}, videos=["v0", "v1"])
    p.click('nav.tabs [data-tab="repertorio"]')
    p.click('#v-repertorio [data-view="f1"]')
    p.click('[data-act="inc-done"]'); p.click('#inc-form button[type="submit"]')
    p.wait_for_selector("#fig-form")
    assert "indica dónde empieza y dónde acaba" in p.locator("#fig-form").inner_text()
    assert p.locator('#ff-estado [data-est="practica"]').get_attribute("aria-pressed") == "true"
    p.select_option("#ff-out", "Sombra")
    p.click('#fig-form button[type="submit"]')
    p.wait_for_selector('[data-viewfig="f1"]')
    g = p.evaluate("() => window.__bachateca.state().figures.f1")
    assert g["estado"] == "practica" and g["salida"] == "Sombra" and len(g["partes"]) == 1, g
    assert "Partes de la clase · 2" in p.locator("section:has(#fv-pt)").inner_text(), "terminada, las partes siguen en la ficha"
    assert not errors, errors
    ctx.close()


# ---------------------------------------------------------------- prueba del conteo al grabar (conteo.html)
def open_conteo(browser, seed=None):
    ctx, p, errors = open_app(browser, seed=seed)
    p.goto(URL.replace("index.html?test", "conteo.html"))
    p.wait_for_function("window.__conteo && window.__conteo.lines.some(l => l.includes('Voz cargada'))", timeout=15000)
    return ctx, p, errors


def log_has(p, text, timeout=15000):
    p.wait_for_function("t => window.__conteo.lines.some(l => l.includes(t))", arg=text, timeout=timeout)


@test(solo_chromium="cámara y micrófono simulados")
def conteo_carga_la_voz_y_el_ritmo_de_las_figuras(browser):
    f = fig(1, "Cerrada", "Sombra", vid="v1", nombre="Entrada a sombra",
            pulso={"vid": "v1", "modo": "extremos", "marcas": [{"b": 1, "s": 0}, {"b": 8, "s": 3.5}]})
    ctx, p, errors = open_conteo(browser, seed={"schema": 5, "figures": {"f1": f, "f2": fig(2, "Sombra", "Cerrada")}, "logs": {}})
    ons = p.evaluate("() => Object.values(window.__conteo.onset)")
    assert len(ons) == 8 and all(0 <= o < 0.2 for o in ons), ons            # dónde empieza la voz en cada número
    opts = p.locator("#c-fig option").all_inner_texts()
    assert opts[1:] == ["Entrada a sombra · 120 bpm"], opts                   # solo las figuras con pulso
    p.select_option("#c-fig", "120")
    assert p.evaluate("() => window.__conteo.st.bpm") == 120
    # Marcar el ritmo tocando: 4 toques a 0,4 s → 150 bpm.
    for _ in range(4):
        p.dispatch_event("#c-tap", "pointerdown"); p.wait_for_timeout(400)
    assert 140 <= p.evaluate("() => window.__conteo.st.bpm") <= 160, p.evaluate("() => window.__conteo.st.bpm")
    # Leer las figuras no cambia los datos de la app.
    assert stored_state(p)["figures"]["f1"]["pulso"]["marcas"][1]["s"] == 3.5
    assert not errors, errors
    ctx.close()


@test(solo_chromium="cámara y micrófono simulados")
def conteo_suena_con_los_dos_motores(browser):
    ctx, p, errors = open_conteo(browser)
    p.click("#c-try")
    log_has(p, "Conteo con Web Audio a 125 bpm")
    p.wait_for_function("document.querySelector('#c-beat').textContent !== ''", timeout=3000)
    p.click("#c-stop")
    assert p.evaluate("() => window.__conteo.run()") is None
    p.click('[data-eng="audio"]')
    log_has(p, "Archivo de audio listo")
    p.click("#c-try")
    log_has(p, "Conteo con archivo de audio")
    p.wait_for_timeout(800)
    assert p.evaluate("() => { const r = window.__conteo.run(); return r && r.eng === 'audio' && !r.audio.paused && r.audio.currentTime > 0.3; }")
    p.click("#c-stop")
    assert not errors, errors
    ctx.close()


@test(solo_chromium="cámara y micrófono simulados")
def conteo_grabar_dentro_de_la_app_saca_el_pulso(browser):
    ctx, p, errors = open_conteo(browser)
    p.click("#c-cam")
    log_has(p, "cámara encendida")
    p.click("#c-rec")
    log_has(p, "grabando")
    p.wait_for_timeout(2500)
    p.click("#c-rec")
    p.wait_for_function("window.__conteo.lastAuto", timeout=10000)
    a = p.evaluate("() => window.__conteo.lastAuto")
    assert a["size"] > 0 and abs(a["beat"] - 0.48) < 1e-9, a                 # 125 bpm
    assert 0 <= a["first"] < 0.6, a                                           # el 1 suena al poco de empezar a grabar
    assert [m["b"] for m in a["marcas"]] == list(range(1, 9)), a
    assert p.locator("#c-out video").count() == 1 and "Pulso sacado solo" in p.locator("#c-out").inner_text()
    p.click('#c-out [data-heard="sí"]')
    assert "SÍ se oye el conteo" in p.locator("#log").inner_text()
    assert not errors, errors
    ctx.close()


@test
def service_worker_no_confunde_las_paginas(browser):
    """Abrir conteo.html no puede guardarse como si fuera la app: sin conexión se abriría la prueba."""
    ctx = browser.new_context(service_workers="allow", viewport={"width": 390, "height": 844})
    p = ctx.new_page()
    app = URL.replace("?test", "")
    p.goto(app)
    p.wait_for_function("navigator.serviceWorker && navigator.serviceWorker.controller", timeout=15000) if p.evaluate("!!navigator.serviceWorker.controller") else None
    p.evaluate("() => navigator.serviceWorker.ready")
    p.reload(); p.wait_for_function("!!navigator.serviceWorker.controller", timeout=15000)
    p.goto(URL.replace("index.html?test", "conteo.html")); p.wait_for_timeout(500)
    r = p.evaluate("""async () => { const ks = await caches.keys(), c = await caches.open(ks.find(k => k.startsWith("bachateca-")));
      const app = await c.match("./index.html"), lab = await c.match(location.href);
      return {app: app ? await app.text() : "", lab: lab ? await lab.text() : ""}; }""")
    assert "<title>Bachateca</title>" in r["app"], r["app"][:200]
    assert "<title>Prueba del conteo</title>" in r["lab"], r["lab"][:200]
    ctx.close()


# ---------------------------------------------------------------- vídeos que no cargan (play tachado en Safari)
def ficha_video(p):
    return p.evaluate("""() => { const v = document.querySelector('.fv-media video'); return v && {src: v.getAttribute('src'), rs: v.readyState, err: v.error && v.error.code}; }""")


@test
def video_de_la_ficha_se_recupera(browser):
    """Si la dirección guardada del vídeo deja de valer, la ficha lo vuelve a leer en vez de quedarse con el play tachado."""
    ctx, p, errors = open_app(browser, seed={"schema": 5, "figures": {"f1": fig(1, "Cerrada", "Sombra", vid="v1")}, "logs": {}})
    put_fixture(p, ["v1"])
    p.click('nav.tabs [data-tab="repertorio"]'); p.click('#v-repertorio [data-view="f1"]')
    p.wait_for_function("document.querySelector('.fv-media video') && document.querySelector('.fv-media video').readyState >= 1")
    first = ficha_video(p)["src"]
    p.evaluate("() => { window._old = document.querySelector('.fv-media video'); }")
    p.click('[data-act="close"]'); p.wait_for_timeout(200)
    assert p.evaluate("() => window._old.getAttribute('src')") is None, "el vídeo que se va de la pantalla suelta el archivo"
    assert p.evaluate("() => window.__bachateca.dropVidUrl('v1')"), "había dirección guardada"
    p.click('#v-repertorio [data-view="f1"]')
    p.wait_for_function("document.querySelector('.fv-media video') && document.querySelector('.fv-media video').readyState >= 1", timeout=10000)
    again = ficha_video(p)
    assert again["src"] != first and again["err"] is None, again
    assert p.locator(".vid-err").count() == 0
    ctx.close()


@test
def video_roto_lo_dice(browser):
    """Un vídeo que no se puede reproducir avisa con el código del error."""
    ctx, p, errors = open_app(browser, seed={"schema": 5, "figures": {"f1": fig(1, "Cerrada", "Sombra", vid="v1")}, "logs": {}}, videos=["v1"])
    p.click('nav.tabs [data-tab="repertorio"]'); p.click('#v-repertorio [data-view="f1"]')
    p.wait_for_selector(".vid-err", timeout=10000)
    d = p.locator(".vid-diag").inner_text()
    # Ni directo ni como copia en memoria: dice el error y los datos del archivo para poder averiguarlo.
    assert "error 4" in d and "tipo video/mp4" in d and "formato desconocido" in d and "Safari dice" in d, d
    assert "probado: frag: error 4, plain: error 4, mem: error 4" in d, d
    assert p.locator(".vid-err [data-copydiag]").count() == 1
    assert p.evaluate("() => localStorage.getItem('bachateca.vidmode')") is None, "si nada funciona, no se cambia de modo"
    ctx.close()


@test
def formato_del_video_por_su_contenido(browser):
    ctx, p, _ = open_app(browser)
    r = p.evaluate("""() => { const B = window.__bachateca, b = s => [...s].map(c => c.charCodeAt(0));
      return [B.sniffVideo(b("\\0\\0\\0\\x14ftypqt  \\0\\0")), B.sniffVideo(b("\\0\\0\\0\\x18ftypisom\\0\\0")),
              B.sniffVideo([0x1a, 0x45, 0xdf, 0xa3, 0, 0, 0, 0, 0, 0, 0, 0]), B.sniffVideo(new Array(12).fill(0))]; }""")
    assert [x["type"] for x in r] == ["video/quicktime", "video/mp4", "video/webm", ""], r
    assert r[0]["marca"] == "qt" and r[1]["marca"] == "isom", r
    ctx.close()


@test
def videos_como_copia_en_memoria(browser):
    """Cuando un iPhone necesita la copia en memoria, la app la usa siempre: el vídeo se ve igual."""
    ctx, p, errors = open_app(browser, seed={"schema": 5, "figures": {"f1": fig(1, "Cerrada", "Sombra", vid="v1")}, "logs": {}})
    put_fixture(p, ["v1"])
    p.evaluate("() => localStorage.setItem('bachateca.vidmode', JSON.stringify('mem'))")
    p.reload(); p.wait_for_function("window.__bachateca && window.__bachateca.ready()")
    p.click('nav.tabs [data-tab="repertorio"]'); p.click('#v-repertorio [data-view="f1"]')
    p.wait_for_function("document.querySelector('.fv-media video') && document.querySelector('.fv-media video').readyState >= 1", timeout=10000)
    v = ficha_video(p)
    assert v["err"] is None and "#t=" not in v["src"] and p.locator(".vid-err").count() == 0, v
    assert not errors, errors
    ctx.close()


@test
def inicio_no_acumula_videos(browser):
    """El vídeo grande de Inicio se repinta a menudo: los anteriores tienen que soltar el archivo."""
    seed = repertorio_inicio()
    ctx, p, errors = open_app(browser, seed=seed)
    p.evaluate("() => { window._seen = []; new MutationObserver(() => document.querySelectorAll('video[data-hvid]').forEach(v => { if (!window._seen.includes(v)) window._seen.push(v); })).observe(document.body, {childList: true, subtree: true}); }")
    for _ in range(4):
        p.click('nav.tabs [data-tab="repertorio"]'); p.click('nav.tabs [data-tab="inicio"]')
    p.wait_for_timeout(300)
    r = p.evaluate("() => ({n: window._seen.length, loaded: window._seen.filter(v => !v.isConnected && v.getAttribute('src')).length})")
    assert r["n"] >= 2 and r["loaded"] == 0, r
    assert not errors, errors
    ctx.close()


@test
def videos_sin_coletilla(browser):
    """Modo «plain»: la ficha pide el vídeo sin «#t=» y lo lleva al inicio de la figura al cargar."""
    ctx, p, errors = open_app(browser, seed={"schema": 5, "figures": {"f1": fig(1, "Cerrada", "Sombra", vid="v1", vidTrim={"start": 0.8, "end": 0})}, "logs": {}})
    put_fixture(p, ["v1"])
    p.evaluate("() => localStorage.setItem('bachateca.vidmode', JSON.stringify('plain'))")
    p.reload(); p.wait_for_function("window.__bachateca && window.__bachateca.ready()")
    p.click('nav.tabs [data-tab="repertorio"]'); p.click('#v-repertorio [data-view="f1"]')
    p.wait_for_function("document.querySelector('.fv-media video') && document.querySelector('.fv-media video').readyState >= 1", timeout=10000)
    v = ficha_video(p)
    assert v["err"] is None and "#t=" not in v["src"], v
    p.wait_for_function("Math.abs(document.querySelector('.fv-media video').currentTime - 0.8) < 0.05")
    assert not errors, errors
    ctx.close()


# ---------------------------------------------------------------- grabarme con conteo (dentro de la app)
@test
def pulso_automatico_del_conteo(browser):
    """El conteo dijo «1» en 0,5 s y cada tiempo dura 0,5 s: la figura empieza en el 1 (o el 5) más cercano al recorte."""
    ctx, p, _ = open_app(browser)
    r = p.evaluate("""() => { const B = window.__bachateca, A = {first: 0.5, beat: 0.5};
      const m = (f, st, sh) => B.autoPulso(A, f, st, sh).marcas;
      return {uno: m({tiempo: "1", tiempos: "8"}, 0.7, 0), luego: m({tiempo: "1", tiempos: "8"}, 4.4, 0),
              cinco: m({tiempo: "5", tiempos: "4"}, 2.6, 0), recortado: m({tiempo: "5", tiempos: "4"}, 2.6, 2.5),
              pronto: m({tiempo: "1", tiempos: "8"}, 0, 0), sin: B.autoPulso(null, {}, 0, 0)}; }""")
    assert [(x["b"], x["s"]) for x in r["uno"]] == [(b, 0.5 + (b - 1) * 0.5) for b in range(1, 9)], r["uno"]
    assert r["luego"][0] == {"b": 1, "s": 4.5}, r["luego"]                 # el siguiente «1»
    assert [(x["b"], x["s"]) for x in r["cinco"]] == [(5, 2.5), (6, 3.0), (7, 3.5), (8, 4.0)], r["cinco"]
    assert r["recortado"][0] == {"b": 5, "s": 0}, "al reducir el vídeo empieza en el recorte"
    assert r["pronto"][0] == {"b": 1, "s": 0.5} and r["sin"] is None, r
    ctx.close()


@test(solo_chromium="cámara y micrófono simulados")
def grabarme_con_conteo(browser):
    seed = cmp_seed(intentos=[])
    ctx, p, errors = open_app(browser, seed=seed)
    put_fixture(p, ["v1"])
    p.click('nav.tabs [data-tab="repertorio"]'); p.click('#v-repertorio [data-view="f1"]')
    btn = p.locator('[data-act="rc-open"]')
    assert "120 bpm" in btn.inner_text(), "al pulso del vídeo de la clase"
    btn.click()
    p.wait_for_function("!document.querySelector('#rc-go').disabled", timeout=10000)
    assert "120 bpm" in p.locator("[data-recc]").inner_text()
    p.click("#rc-go")
    p.wait_for_function("document.querySelector('#rc-beat').textContent !== ''", timeout=5000)
    assert p.evaluate("() => window.__bachateca.rcState().recording")
    p.wait_for_timeout(2500)
    p.click("#rc-go")
    p.wait_for_selector("#att-form #ff-prev", timeout=10000)
    assert p.evaluate("() => window.__bachateca.rcState()") is None, "la cámara se apaga al parar"
    assert "El pulso se guarda solo" in p.locator("#att-form").inner_text()
    assert not p.locator("#ff-compact").is_checked(), "ya está en calidad media: no hace falta reducirlo"
    p.click('#att-form button[type="submit"]')
    p.wait_for_selector('[data-viewfig="f1"]', timeout=15000)
    a = p.evaluate("() => window.__bachateca.state().figures.f1.intentos[0]")
    pu = a["pulso"]
    assert pu["modo"] == "auto" and pu["vid"] == a["vid"] and [m["b"] for m in pu["marcas"]] == [1, 2, 3, 4], pu
    assert p.evaluate("p => window.__bachateca.pulsoOk(p, p.vid)", pu) and abs(p.evaluate("p => Math.round(60 * 3 / (p.marcas[3].s - p.marcas[0].s))", pu) - 120) <= 1, pu
    assert 0.3 <= pu["marcas"][0]["s"] <= 1.2, pu                            # el primer «1» suena medio segundo después de empezar
    # Con los dos pulsos, ya se puede comparar sin marcar nada a mano.
    p.click(f'[data-act="att-open"][data-att="{a["id"]}"]')
    assert p.locator('[data-act="cmp-open"]').count() == 1
    assert not errors, errors
    ctx.close()


@test(solo_chromium="cámara y micrófono simulados")
def salir_de_grabar_apaga_la_camara(browser):
    ctx, p, errors = open_app(browser, seed=cmp_seed(intentos=[]))
    p.click('nav.tabs [data-tab="repertorio"]'); p.click('#v-repertorio [data-view="f1"]')
    p.click('[data-act="rc-open"]')
    p.wait_for_function("!document.querySelector('#rc-go').disabled", timeout=10000)
    p.evaluate("() => { window._tracks = document.querySelector('#rc-live').srcObject.getTracks(); }")
    p.click('[data-recc] [data-view="f1"]')
    p.wait_for_selector('[data-viewfig="f1"]')
    assert p.evaluate("() => window.__bachateca.rcState()") is None
    p.wait_for_timeout(100)
    assert p.evaluate("() => window._tracks.every(t => t.readyState === 'ended')"), "cámara y micrófono apagados"
    # Cerrar a mitad de una grabación pregunta antes.
    p.click('[data-act="rc-open"]')
    p.wait_for_function("!document.querySelector('#rc-go').disabled", timeout=10000)
    p.click("#rc-go"); p.wait_for_timeout(500)
    p.click('[data-recc] [data-act="close"]')
    assert p.locator("#confirm-root .confirm").count() == 1
    p.click('#confirm-root [data-cf="ok"]')
    assert p.evaluate("() => window.__bachateca.rcState()") is None
    assert not errors, errors
    ctx.close()


# ---- integridad de datos

def _parche_lectura(solo_primera):
    # Hace fallar la lectura de «state»; con __sinParche deja de fallar para poder leer desde la misma página.
    cond = "!globalThis.__veces++" if solo_primera else "!globalThis.__sinParche"
    return f"""globalThis.__veces = 0; const g = IDBObjectStore.prototype.get;
      IDBObjectStore.prototype.get = function (k) {{
        if (k === "state" && {cond}) throw new DOMException("simulado", "UnknownError");
        return g.apply(this, arguments); }};"""


@test
def exportar_por_descarga_pregunta(browser):
    ctx, p, errors = open_app(browser, seed={"schema": 6, "figures": {"f1": fig(1, "a", "b", id="f1")}})
    p.click("#btn-settings")
    p.wait_for_selector('[data-act="export"]')
    with p.expect_download():
        p.click('[data-act="export"]')
    p.wait_for_selector('#confirm-root [data-cf="ok"]')
    assert "¿Se ha guardado la copia?" in p.locator("#confirm-root").inner_text()
    p.click("#confirm-root .cancel")
    p.wait_for_timeout(200)
    assert p.evaluate("() => localStorage.getItem('bachateca.backup.at')") is None
    with p.expect_download():
        p.click('[data-act="export"]')
    p.click('#confirm-root [data-cf="ok"]')
    p.wait_for_timeout(200)
    assert p.evaluate("() => +localStorage.getItem('bachateca.backup.at')") > 0
    assert not errors, errors
    ctx.close()


@test
def lectura_fallida_no_pisa_los_datos(browser):
    seed = {"schema": 6, "figures": {f"r{i}": fig(i, "a", "b", id=f"r{i}") for i in range(30)}}
    ctx, p, errors = open_app(browser, seed=seed, init=_parche_lectura(False))
    assert p.locator("#safe-note").is_visible()
    assert p.evaluate("() => window.__bachateca.safeMode()") is True
    p.evaluate("() => document.querySelector('[data-act=\"examples\"]').click()")
    p.evaluate("() => window.__bachateca.flush()")
    p.wait_for_timeout(300)
    p.evaluate("() => { window.__sinParche = true; }")
    st = stored_state(p)
    assert len(st["figures"]) == 30, len(st["figures"])
    assert not any(f.get("ejemplo") for f in st["figures"].values())
    assert not errors, errors
    ctx.close()


@test
def lectura_fallida_una_vez_se_recupera(browser):
    seed = {"schema": 6, "figures": {f"r{i}": fig(i, "a", "b", id=f"r{i}") for i in range(30)}}
    ctx, p, errors = open_app(browser, seed=seed, init=_parche_lectura(True))
    assert p.locator("#safe-note").count() == 0
    assert len(p.evaluate("() => window.__bachateca.state().figures")) == 30
    assert p.evaluate("() => window.__bachateca.safeMode()") is False
    assert not errors, errors
    ctx.close()


@test
def modo_seguro_conserva_el_aviso_al_buscar(browser):
    ctx, p, errors = open_app(browser, init=_parche_lectura(False))
    p.evaluate("() => document.querySelector('[data-act=examples]').click()")
    p.click('[data-tab="repertorio"]')
    p.fill("#f-q", "a")
    p.type("#f-q", "b")
    assert p.locator("#v-repertorio #safe-note").count() == 1
    assert p.locator("#v-repertorio #safe-note").is_visible()
    assert not errors, errors
    ctx.close()


@test
def sin_indexeddb_sigue_con_localstorage(browser):
    ctx, p, errors = open_app(browser, init='Object.defineProperty(window, "indexedDB", {value: undefined, configurable: true});')
    assert p.locator("#safe-note").count() == 0
    p.evaluate("() => document.querySelector('[data-act=\"examples\"]').click()")
    p.evaluate("() => window.__bachateca.flush()")
    n = p.evaluate("() => Object.keys(JSON.parse(localStorage.getItem('bachateca.v1')).figures).length")
    assert n == 8, n
    assert not errors, errors
    ctx.close()


@test
def respaldo_mas_reciente_gana(browser):
    a = {"schema": 6, "guardado": 1000, "figures": {"f1": fig(1, "a", "b")}}
    b = {"schema": 6, "guardado": 2000, "figures": {"f1": fig(1, "a", "b"), "f2": fig(2, "a", "b")}}
    ctx, p, errors = open_app(browser, seed=a, ls={"bachateca.v1": b})
    assert len(p.evaluate("() => window.__bachateca.state().figures")) == 2
    assert not errors, errors
    ctx.close()


@test
def guardar_bien_borra_el_respaldo(browser):
    b = {"schema": 6, "guardado": 2000, "figures": {}}   # sin figuras, para que se vea el botón de ejemplos
    ctx, p, errors = open_app(browser, ls={"bachateca.v1": b})
    p.evaluate("() => document.querySelector('[data-act=\"examples\"]').click()")
    p.evaluate("() => window.__bachateca.flush()")
    assert p.evaluate("() => localStorage.getItem('bachateca.v1')") is None
    assert isinstance(stored_state(p)["guardado"], (int, float))
    assert not errors, errors
    ctx.close()


@test
def sin_espacio_avisa(browser):
    init = """const put = IDBObjectStore.prototype.put;
      IDBObjectStore.prototype.put = function (v, k) {
        if (k === "state") throw new DOMException("simulado", "QuotaExceededError");
        return put.apply(this, arguments); };
      const set = Storage.prototype.setItem;
      Storage.prototype.setItem = function (k) {
        if (k === "bachateca.v1") throw new DOMException("simulado", "QuotaExceededError");
        return set.apply(this, arguments); };"""
    ctx, p, errors = open_app(browser, init=init)
    p.evaluate("() => document.querySelector('[data-act=\"examples\"]').click()")
    p.evaluate("() => window.__bachateca.flush()")
    p.wait_for_selector(".toast")
    assert "No se ha podido guardar" in p.inner_text(".toast")
    assert not errors, errors
    ctx.close()


@test
def instantanea_diaria_al_abrir(browser):
    seed = {"schema": 6, "guardado": 1000, "figures": {"f1": fig(1, "a", "b")}}
    ctx, p, errors = open_app(browser, seed=seed)
    # La diaria se hace sin retrasar el arranque: se espera a que aparezca.
    p.wait_for_function("async () => (await window.__bachateca.listSnapshots()).length === 1")
    sn = p.evaluate("() => window.__bachateca.listSnapshots()")
    assert len(sn) == 1 and sn[0]["reason"] == "diaria" and sn[0]["nFig"] == 1, sn
    p.reload()
    p.wait_for_function("window.__bachateca && window.__bachateca.ready()")
    p.wait_for_timeout(500)   # margen para que una diaria repetida (error) llegara a escribirse
    assert len(p.evaluate("() => window.__bachateca.listSnapshots()")) == 1
    assert not errors, errors
    ctx.close()


@test
def instantaneas_se_rotan(browser):
    seed = {"schema": 6, "guardado": 1000, "figures": {"f1": fig(1, "a", "b")}}
    ctx, p, errors = open_app(browser, seed=seed)
    p.evaluate("""async () => { for (let i = 0; i < 7; i++) await window.__bachateca.takeSnapshot("antes-de-importar"); }""")
    sn = p.evaluate("() => window.__bachateca.listSnapshots()")
    assert len([x for x in sn if x["reason"] == "antes-de-importar"]) == 5, sn
    assert len([x for x in sn if x["reason"] == "diaria"]) == 1, sn
    assert not errors, errors
    ctx.close()


@test
def encoger_guarda_instantanea(browser):
    seed = {"schema": 6, "guardado": 1000, "figures": {f"f{i}": fig(i, "a", "b") for i in range(20)}}
    ctx, p, errors = open_app(browser, seed=seed)
    p.evaluate("""async () => { const B = window.__bachateca;
      for (let i = 0; i < 10; i++) B.deleteFigure("f" + i);
      await B.flush(); }""")
    sn = p.evaluate("() => window.__bachateca.listSnapshots()")
    enc = [x for x in sn if x["reason"] == "antes-de-encoger"]
    assert len(enc) == 1 and enc[0]["nFig"] == 20, sn
    assert len(stored_state(p)["figures"]) == 10
    assert not errors, errors
    ctx.close()


@test
def instantanea_que_falla_no_impide_guardar(browser):
    seed = {"schema": 6, "guardado": 1000, "figures": {f"f{i}": fig(i, "a", "b") for i in range(20)}}
    init = """const put = IDBObjectStore.prototype.put;
      IDBObjectStore.prototype.put = function (v, k) {
        if (typeof k === "string" && k.startsWith("snap:")) throw new DOMException("simulado", "QuotaExceededError");
        return put.apply(this, arguments); };"""
    ctx, p, errors = open_app(browser, seed=seed, init=init)
    # El encogimiento intenta la instantánea dentro de la misma transacción: aborta, y el guardado se reintenta solo.
    p.evaluate("""async () => { const B = window.__bachateca;
      for (let i = 0; i < 10; i++) B.deleteFigure("f" + i);
      await B.flush(); }""")
    assert len(stored_state(p)["figures"]) == 10
    # Con la diaria también fallando, la app arranca y enseña las figuras.
    p.reload()
    p.wait_for_function("window.__bachateca && window.__bachateca.ready()")
    assert len(p.evaluate("() => window.__bachateca.state().figures")) == 10
    assert not errors, errors
    ctx.close()


@test
def restaurar_instantanea(browser):
    seed = {"schema": 6, "guardado": 1000, "figures": {f"f{i}": fig(i, "a", "b") for i in range(3)}}
    ctx, p, errors = open_app(browser, seed=seed)
    p.wait_for_function("async () => (await window.__bachateca.listSnapshots()).length === 1")
    key = p.evaluate("() => window.__bachateca.takeSnapshot('antes-de-importar')")
    p.evaluate("() => { for (const id of ['f0', 'f1', 'f2']) window.__bachateca.deleteFigure(id); }")
    assert len(p.evaluate("() => window.__bachateca.state().figures")) == 0
    p.click("#btn-settings")
    p.click('[data-setv="instantaneas"]')
    p.click(f'[data-act="snap-restore"][data-key="{key}"]')
    p.click('#confirm-root [data-cf="ok"]')
    p.wait_for_function("Object.keys(window.__bachateca.state().figures).length === 3")
    assert "Restaurado: 3 figuras" in p.inner_text(".toast")
    sn = p.evaluate("() => window.__bachateca.listSnapshots()")
    antes = [x for x in sn if x["reason"] == "antes-de-restaurar"]
    assert len(antes) == 1 and antes[0]["nFig"] == 0, sn
    assert p.is_visible("#sheet-t") and "Instantáneas" in p.inner_text("#sheet-t")
    assert not errors, errors
    ctx.close()


@test
def restaurar_instantanea_antigua_migra(browser):
    seed = {"schema": 6, "guardado": 1000, "figures": {"f1": fig(1, "a", "b")}}
    ctx, p, errors = open_app(browser, seed=seed)
    p.wait_for_function("async () => (await window.__bachateca.listSnapshots()).length === 1")
    p.evaluate("""() => new Promise((res, rej) => {
      const r = indexedDB.open("bachateca", 1);
      r.onsuccess = () => { const t = r.result.transaction("kv", "readwrite");
        t.objectStore("kv").put({at: 5000, reason: "diaria", nFig: 1, nLog: 0, schema: 5,
          state: {schema: 5, figures: {v1: {id: "v1", nombre: "vieja", entrada: "a", salida: "b", estado: "practica"}}, logs: {}}}, "snap:5000:diaria");
        t.oncomplete = () => res(); t.onerror = () => rej(t.error); };
      r.onerror = () => rej(r.error); })""")
    p.evaluate("() => { window.__t = window.__bachateca.restoreSnapshot('snap:5000:diaria'); }")
    p.click('#confirm-root [data-cf="ok"]')
    assert p.evaluate("() => window.__t") is True
    p.wait_for_function("window.__bachateca.state().figures.v1")
    r = p.evaluate("() => { const s = window.__bachateca.state(); return {partes: s.figures.v1.partes, schema: s.schema, S: window.__bachateca.SCHEMA}; }")
    assert r["partes"] == [] and r["schema"] == r["S"], r
    assert not errors, errors
    ctx.close()


@test
def exportar_no_incluye_instantaneas(browser):
    seed = {"schema": 6, "guardado": 1000, "figures": {"f1": fig(1, "a", "b")}}
    ctx, p, errors = open_app(browser, seed=seed)
    p.evaluate("""async () => { await window.__bachateca.takeSnapshot("antes-de-importar");
      await window.__bachateca.takeSnapshot("antes-de-importar"); }""")
    assert len(p.evaluate("() => window.__bachateca.listSnapshots()")) >= 2
    ex = p.evaluate("() => window.__bachateca.exportData()")
    assert "snap:" not in ex and "snapshots" not in ex
    assert not [k for k in p.evaluate("() => Object.keys(window.__bachateca.state())") if k.startswith("snap")]
    assert not errors, errors
    ctx.close()


_PUT_SNAP = """(snap) => new Promise((res, rej) => {
  const r = indexedDB.open("bachateca", 1);
  r.onsuccess = () => { const t = r.result.transaction("kv", "readwrite");
    t.objectStore("kv").put(snap, "snap:5000:diaria");
    t.oncomplete = () => res(); t.onerror = () => rej(t.error); };
  r.onerror = () => rej(r.error); })"""
_SNAP_1FIG = {"at": 5000, "reason": "diaria", "nFig": 1, "nLog": 0, "schema": 6,
              "state": {"schema": 6, "figures": {"v1": {"id": "v1", "nombre": "vieja", "entrada": "a", "salida": "b", "estado": "practica", "partes": []}}, "logs": {}}}


@test
def restaurar_en_modo_seguro_no_hace_nada(browser):
    seed = {"schema": 6, "figures": {f"r{i}": fig(i, "a", "b", id=f"r{i}") for i in range(3)}}
    ctx, p, errors = open_app(browser, seed=seed, init=_parche_lectura(False))
    assert p.evaluate("() => window.__bachateca.safeMode()") is True
    antes = p.evaluate("() => JSON.stringify(window.__bachateca.state())")
    p.evaluate(_PUT_SNAP, _SNAP_1FIG)
    assert p.evaluate("() => window.__bachateca.restoreSnapshot('snap:5000:diaria')") is False
    assert "Modo seguro" in p.inner_text(".toast")
    assert p.evaluate("() => JSON.stringify(window.__bachateca.state())") == antes
    assert "v1" not in p.evaluate("() => window.__bachateca.state().figures")
    assert not errors, errors
    ctx.close()


@test
def restaurar_sin_copia_previa_no_cambia_nada(browser):
    seed = {"schema": 6, "guardado": 1000, "figures": {f"r{i}": fig(i, "a", "b", id=f"r{i}") for i in range(3)}}
    ctx, p, errors = open_app(browser, seed=seed)
    p.wait_for_function("async () => (await window.__bachateca.listSnapshots()).length === 1")
    p.evaluate(_PUT_SNAP, _SNAP_1FIG)
    p.evaluate("""() => { const put = IDBObjectStore.prototype.put;
      IDBObjectStore.prototype.put = function (v, k) {
        if (typeof k === "string" && k.startsWith("snap:")) throw new DOMException("simulado", "QuotaExceededError");
        return put.apply(this, arguments); }; }""")
    p.evaluate("() => { window.__t = window.__bachateca.restoreSnapshot('snap:5000:diaria'); }")
    p.click('#confirm-root [data-cf="ok"]')
    assert p.evaluate("() => window.__t") is False
    assert "No he cambiado nada" in p.inner_text(".toast")
    assert len(p.evaluate("() => window.__bachateca.state().figures")) == 3
    assert not errors, errors
    ctx.close()


@test
def copia_con_id_malicioso_no_ejecuta(browser):
    ctx, p, errors = open_app(browser)
    mal = {"schema": 6, "figures": {"x": {"id": 'x"><img src=x onerror="window.__pwn=1">', "nombre": "Mala", "entrada": "a", "salida": "b"}}, "logs": {}}
    import_text(p, json.dumps(mal))
    assert "descartada" in p.locator(".toast").inner_text()
    p.fill("#imp-text", "")
    p.keyboard.press("Escape")
    p.click('[data-tab="repertorio"]')
    p.wait_for_timeout(200)
    assert p.evaluate("() => window.__pwn") is None
    assert p.evaluate("() => Object.keys(window.__bachateca.state().figures).length") == 0
    assert not errors, errors
    ctx.close()


@test
def id_raro_en_los_datos_se_escapa(browser):
    seed = {"schema": 6, "figures": {'a"b': fig(1, "a", "b", id='a"b', rep={"step": 1, "due": "2000-01-01", "aciertos": 0, "fallos": 0})}, "logs": {}}
    ctx, p, errors = open_app(browser, seed=seed)
    p.click('[data-tab="repertorio"]')
    p.wait_for_timeout(200)
    assert p.locator("#v-repertorio .gcard").first.get_attribute("data-view") == 'a"b'
    p.locator("#v-repertorio .gcard").first.click()
    p.wait_for_timeout(300)
    assert p.locator(".fview").count() == 1
    p.keyboard.press("Escape")
    p.click('nav.tabs [data-tab="repasar"]')
    p.click('[data-act="start-fig"]')
    p.click('[data-act="reveal"]')
    p.click('[data-grade="fluida"]')
    assert p.locator('[data-promote]').first.get_attribute("data-promote") == 'a"b'
    assert not errors, errors
    ctx.close()


@test
def copia_mal_formada_no_rompe(browser):
    ctx, p, errors = open_app(browser)
    import_text(p, json.dumps({"figures": [1, 2]}))
    assert p.locator(".toast").inner_text().strip()
    p.fill("#imp-text", json.dumps({"figures": {"a": None, "b": {"id": "b", "nombre": 3}}}))
    p.click('[data-act="import-merge"]')
    p.wait_for_timeout(300)
    assert "descartadas" in p.locator(".toast").inner_text()
    assert p.evaluate("() => Object.keys(window.__bachateca.state().figures).length") == 0
    p.fill("#imp-text", json.dumps({"figures": {"a": {"id": "a", "nombre": "A"}}, "logs": {"l": {"id": "l", "fecha": "2026-01-01", "figs": "abc"}}}))
    p.click('[data-act="import-merge"]')
    p.wait_for_timeout(300)
    p.keyboard.press("Escape")
    p.click('nav.tabs [data-tab="social"]')
    p.click('[data-act="log-open"]')
    p.wait_for_timeout(300)
    assert p.locator(".sheet").count() == 1
    assert not errors, errors
    ctx.close()


@test
def reemplazar_no_borra_lo_que_venia_mal_formado(browser):
    seed = {"schema": 6, "figures": {"f1": fig(1, "a", "b", id="f1"), "f2": fig(2, "a", "b", id="f2")}, "logs": {}}
    ctx, p, errors = open_app(browser, seed=seed)
    bak = {"schema": 6, "figures": {"f1": fig(1, "a", "b", id="f1"), "f2": {"id": "f2", "nombre": " "}}, "logs": {}}
    import_text(p, json.dumps(bak), replace=True)
    assert "1 entrada está mal formada" in p.locator(".confirm").inner_text()
    p.click('[data-cf="ok"]')
    p.wait_for_timeout(300)
    ids = p.evaluate("() => Object.keys(window.__bachateca.state().figures).sort()")
    assert ids == ["f1", "f2"], ids
    assert not errors, errors
    ctx.close()


@test
def sanear_copia_filtra_figuras_y_registros(browser):
    ctx, p, errors = open_app(browser)
    r = p.evaluate("""() => window.__bachateca.sanitizeImport({figures: {
      a: {id: "a", nombre: "Ok"}, b: {id: "b", nombre: "  "}, c: [1], 'd e': {id: "d e", nombre: "x"}},
      logs: {l1: {id: "l1", fecha: "2026-01-01", figs: ["a", 3]}, l2: {id: "l2"}, l3: null}})""")
    assert list(r["figures"]) == ["a"] and list(r["logs"]) == ["l1"], r
    assert r["logs"]["l1"]["figs"] == ["a"] and r["descartadas"] == 5, r
    assert p.evaluate("() => window.__bachateca.sanitizeImport({figures: [1]}).figures") == {}
    ctx.close()


_SNAP_FALLA = """() => { const put = IDBObjectStore.prototype.put;
  IDBObjectStore.prototype.put = function (v, k) {
    if (typeof k === "string" && k.startsWith("snap:")) throw new DOMException("simulado", "QuotaExceededError");
    return put.apply(this, arguments); }; }"""


@test
def anadir_conserva_mis_figuras(browser):
    seed = {"schema": 6, "figures": {"f1": fig(1, "a", "b", vid="vA")}, "logs": {}}
    ctx, p, errors = open_app(browser, seed=seed, videos=["vA"])
    copia = p.evaluate("() => window.__bachateca.exportData()")
    p.evaluate("""() => { const f = window.__bachateca.state().figures.f1;
      Object.assign(f, {notas: "mías", estado: "consolidada", vid: "vB", rep: {...(f.rep || {}), step: 4}}); }""")
    import_text(p, copia)
    assert "1 figura ya está y es distinta" in p.locator("#confirm-root .confirm").inner_text()
    p.click('#confirm-root [data-cf="no"]')
    p.wait_for_timeout(300)
    f = p.evaluate("() => window.__bachateca.state().figures.f1")
    assert (f["notas"], f["estado"], f["rep"]["step"], f["vid"]) == ("mías", "consolidada", 4, "vB"), f
    assert "se conservan tus 1" in p.locator(".toast").inner_text()
    assert not errors, errors
    ctx.close()


@test
def anadir_solo_nuevas_sin_preguntar(browser):
    seed = {"schema": 6, "figures": {"f1": fig(1, "a", "b")}, "logs": {}}
    ctx, p, errors = open_app(browser, seed=seed)
    import_text(p, json.dumps({"schema": 6, "figures": {"f2": fig(2, "a", "b"), "f3": fig(3, "a", "b")}, "logs": {}}))
    assert p.locator("#confirm-root .confirm").count() == 0
    assert sorted(p.evaluate("() => Object.keys(window.__bachateca.state().figures)")) == ["f1", "f2", "f3"]
    assert "2 figuras añadidas" in p.locator(".toast").inner_text()
    assert not errors, errors
    ctx.close()


@test
def importar_guarda_instantanea(browser):
    seed = {"schema": 6, "figures": {"f1": fig(1, "a", "b")}, "logs": {}}
    ctx, p, errors = open_app(browser, seed=seed)
    import_text(p, json.dumps({"schema": 6, "figures": {"f2": fig(2, "a", "b")}, "logs": {}}))
    sn = [x for x in p.evaluate("() => window.__bachateca.listSnapshots()") if x["reason"] == "antes-de-importar"]
    assert len(sn) == 1 and sn[0]["nFig"] == 1, sn
    assert not errors, errors
    ctx.close()


@test
def reemplazar_no_borra_videos_al_momento(browser):
    seed = {"schema": 6, "figures": {"f1": fig(1, "a", "b", vid="v1")}, "logs": {}}
    ctx, p, errors = open_app(browser, seed=seed, videos=["v1"])
    import_text(p, json.dumps({"schema": 6, "figures": {"f2": fig(2, "a", "b")}, "logs": {}}), replace=True)
    assert "Antes se guarda una instantánea" in p.locator("#confirm-root .confirm").inner_text()
    p.click('#confirm-root [data-cf="ok"]')
    p.wait_for_timeout(300)
    assert list(p.evaluate("() => window.__bachateca.state().figures")) == ["f2"]
    p.evaluate("() => window.__bachateca.flush()"); p.wait_for_timeout(300)
    assert "v1" in stored_video_sizes(p), stored_video_sizes(p)
    sn = [x for x in p.evaluate("() => window.__bachateca.listSnapshots()") if x["reason"] == "antes-de-reemplazar"]
    assert len(sn) == 1, sn
    p.evaluate("k => { window.__t = window.__bachateca.restoreSnapshot(k); }", sn[0]["key"])
    p.click('#confirm-root [data-cf="ok"]')
    assert p.evaluate("() => window.__t") is True
    assert p.evaluate("() => window.__bachateca.state().figures.f1.vid") == "v1"
    assert not errors, errors
    ctx.close()


@test
def cancelar_reemplazo_no_guarda_instantanea(browser):
    seed = {"schema": 6, "figures": {"f1": fig(1, "a", "b")}, "logs": {}}
    ctx, p, errors = open_app(browser, seed=seed)
    import_text(p, json.dumps({"schema": 6, "figures": {"f2": fig(2, "a", "b")}, "logs": {}}), replace=True)
    p.click('#confirm-root [data-cf="no"]')
    p.wait_for_timeout(300)
    assert list(p.evaluate("() => window.__bachateca.state().figures")) == ["f1"]
    assert not [x for x in p.evaluate("() => window.__bachateca.listSnapshots()") if x["reason"] == "antes-de-reemplazar"]
    assert not errors, errors
    ctx.close()


@test
def importar_sin_copia_previa_no_cambia_nada(browser):
    seed = {"schema": 6, "guardado": 1000, "figures": {"f1": fig(1, "a", "b")}, "logs": {}}
    ctx, p, errors = open_app(browser, seed=seed)
    p.wait_for_function("async () => (await window.__bachateca.listSnapshots()).length === 1")
    antes = p.evaluate("() => JSON.stringify(window.__bachateca.state())")
    p.evaluate(_SNAP_FALLA)
    import_text(p, json.dumps({"schema": 6, "figures": {"f2": fig(2, "a", "b")}, "logs": {}}))
    assert "No he cambiado nada" in p.locator(".toast").inner_text()
    assert p.evaluate("() => JSON.stringify(window.__bachateca.state())") == antes
    assert not errors, errors
    ctx.close()


@test
def importar_en_modo_seguro_no_hace_nada(browser):
    seed = {"schema": 6, "figures": {"f1": fig(1, "a", "b")}, "logs": {}}
    ctx, p, errors = open_app(browser, seed=seed, init=_parche_lectura(False))
    assert p.evaluate("() => window.__bachateca.safeMode()") is True
    antes = p.evaluate("() => JSON.stringify(window.__bachateca.state())")
    import_text(p, json.dumps({"schema": 6, "figures": {"f2": fig(2, "a", "b")}, "logs": {}}))
    assert "Modo seguro: no se puede importar." in p.locator(".toast").inner_text()
    assert p.evaluate("() => JSON.stringify(window.__bachateca.state())") == antes
    ctx.close()


@test
def figuras_distintas_sin_orden_ni_intentos(browser):
    ctx, p, errors = open_app(browser)
    r = p.evaluate("""() => { const d = window.__bachateca.figDiffers;
      return [d({id: "a", nombre: "A", rep: {step: 1, due: "x"}, intentos: [1]}, {rep: {due: "x", step: 1}, nombre: "A", id: "a", partes: [2]}),
              d({id: "a", nombre: "A"}, {id: "a", nombre: "B"}), d({id: "a", rep: {step: 1}}, {id: "a", rep: {step: 4}})]; }""")
    assert r == [False, True, True], r
    assert not errors, errors
    ctx.close()


@test
def anadir_trae_intentos_y_partes_nuevos(browser):
    local_i1 = att(1, "a1", notas="mía")
    for distinta in (False, True):
        seed = {"schema": 6, "figures": {"f1": fig(1, "a", "b", intentos=[local_i1], partes=[])}, "logs": {}}
        ctx, p, errors = open_app(browser, seed=seed, videos=["a1"])
        copia = json.loads(p.evaluate("() => window.__bachateca.exportData()"))
        f = copia["figures"]["f1"]
        f["intentos"] = [att(1, "a1", notas="de la copia"), att(2, "a2")]
        f["partes"] = [{"id": "p1", "nombre": "Parte 1", "creado": 7000}]
        if distinta:
            f["notas"] = "de la copia"
        import_text(p, json.dumps(copia))
        if distinta:
            p.click('#confirm-root [data-cf="no"]')
            p.wait_for_timeout(300)
        else:
            assert p.locator("#confirm-root .confirm").count() == 0
        g = p.evaluate("() => window.__bachateca.state().figures.f1")
        assert [a["id"] for a in g["intentos"]] == ["i1", "i2"], g["intentos"]
        assert g["intentos"][0] == local_i1, "el intento local no cambia"
        assert [x["id"] for x in g["partes"]] == ["p1"], g["partes"]
        assert g.get("notas") != "de la copia", "se conservan los campos locales"
        p.evaluate("() => window.__bachateca.flush()"); p.wait_for_timeout(300)
        assert [a["id"] for a in stored_state(p)["figures"]["f1"]["intentos"]] == ["i1", "i2"]
        assert not errors, errors
        ctx.close()


# ---- revisión final: importar sin romper nada

@test
def copia_con_entradas_internas_rotas(browser):
    seed = {"schema": 6, "figures": {"f9": fig(9, "a", "b")}, "logs": {}}
    ctx, p, errors = open_app(browser, seed=seed)
    f2 = fig(2, "a", "b", intentos=[None, att(1, "a1", marcadores=[None, {"id": "m1", "b": 3, "tipo": "bien"}, {"id": "m 2", "b": 1}])],
             partes="x", errores=[{"id": "e1", "nota": "ok"}, 7, {"nota": "sin id"}])
    bak = {"schema": 6, "figures": {"f1": fig(1, "a", "b"), "f2": f2}, "logs": {}}
    import_text(p, json.dumps(bak), replace=True)
    p.click('#confirm-root [data-cf="ok"]')
    p.wait_for_timeout(300)
    S = p.evaluate("() => window.__bachateca.state().figures")
    assert sorted(S) == ["f1", "f2"], list(S)
    g = S["f2"]
    assert [a["id"] for a in g["intentos"]] == ["i1"] and g["partes"] == [], g
    assert [m["id"] for m in g["intentos"][0]["marcadores"]] == ["m1"], g["intentos"][0]
    assert [e["id"] for e in g["errores"]] == ["e1"], g["errores"]
    assert "Repertorio restaurado" in p.locator(".toast").inner_text()
    r = p.evaluate("""() => { const d = {figures: {a: {id: "a", nombre: "A", intentos: [null, {id: "i"}], partes: "x"}}};
      const s = JSON.stringify(d); const out = window.__bachateca.sanitizeImport(d); return [JSON.stringify(d) === s, out.figures.a.partes, out.figures.a.intentos.length]; }""")
    assert r == [True, [], 1], r
    p.evaluate("() => window.__bachateca.flush()"); p.wait_for_timeout(300)
    assert sorted(stored_state(p)["figures"]) == ["f1", "f2"]
    assert not errors, errors
    ctx.close()


@test
def importar_que_falla_deja_todo_como_estaba(browser):
    seed = {"schema": 6, "figures": {"f1": fig(1, "a", "b"), "f2": fig(2, "a", "b")}, "logs": {}}
    ctx, p, errors = open_app(browser, seed=seed)
    antes = p.evaluate("() => JSON.stringify(window.__bachateca.state().figures)")
    p.evaluate("() => window.__bachateca.failImportOnce()")
    bak = {"schema": 6, "figures": {"f3": fig(3, "a", "b"), "f4": fig(4, "a", "b")}, "logs": {}}
    import_text(p, json.dumps(bak), replace=True)
    p.click('#confirm-root [data-cf="ok"]')
    p.wait_for_timeout(400)
    assert "No se pudo importar la copia. He dejado tus datos como estaban." in p.locator(".toast").inner_text()
    assert p.evaluate("() => JSON.stringify(window.__bachateca.state().figures)") == antes
    p.evaluate("() => window.__bachateca.flush()"); p.wait_for_timeout(300)
    assert sorted(stored_state(p)["figures"]) == ["f1", "f2"]
    # Solo falla una vez: la siguiente importación funciona.
    p.fill("#imp-text", json.dumps(bak))
    p.click('[data-act="import-replace"]')
    p.click('#confirm-root [data-cf="ok"]')
    p.wait_for_timeout(300)
    assert sorted(p.evaluate("() => Object.keys(window.__bachateca.state().figures)")) == ["f3", "f4"]
    assert not errors, errors
    ctx.close()


_TRAMPA = "<img src=x onerror=window.__pwn=1>"


def _figura_trampa():
    return fig(1, "Cerrada", "Sombra", usos=_TRAMPA, estado='x" onmouseover="window.__pwn=1', tipo='y" onmouseover="window.__pwn=1',
               tiempo=_TRAMPA, tiempos=_TRAMPA,
               rep={"step": _TRAMPA, "aciertos": _TRAMPA, "fallos": "<b>" + _TRAMPA, "due": "2000-01-01"})


def _recorrer_con_trampas(p):
    p.wait_for_timeout(200)
    for t in ["repertorio", "repasar", "enlazar", "social", "inicio"]:
        p.click(f'nav.tabs [data-tab="{t}"]')
        p.wait_for_timeout(150)
        p.mouse.move(100, 300); p.mouse.move(200, 500)
    p.click('nav.tabs [data-tab="repertorio"]')
    p.locator('#v-repertorio [data-view="f1"]').first.click()
    p.wait_for_timeout(300)
    p.mouse.move(100, 300); p.mouse.move(200, 500)
    p.keyboard.press("Escape")
    p.click('nav.tabs [data-tab="social"]')
    p.click('[data-act="log-open"]')
    p.wait_for_timeout(300)
    p.keyboard.press("Escape")
    p.wait_for_timeout(200)


@test
def copia_con_campos_trampa_no_ejecuta(browser):
    ctx, p, errors = open_app(browser)
    import_text(p, json.dumps({"schema": 6, "figures": {"f1": _figura_trampa()}, "logs": {}}))
    p.fill("#imp-text", "")
    p.keyboard.press("Escape")
    f = p.evaluate("() => window.__bachateca.state().figures.f1")
    assert f["estado"] == "practica" and f["tipo"] == "figura" and "usos" not in f, f
    assert (f["rep"]["step"], f["rep"]["aciertos"], f["rep"]["fallos"]) == (0, 0, 0), f["rep"]
    _recorrer_con_trampas(p)
    assert p.evaluate("() => window.__pwn") is None
    assert not errors, errors
    ctx.close()
    # Datos ya guardados con esos campos (sin pasar por importar): se escapan al pintarlos.
    # f1 con tipo válido (así se pintan usos, estado y repaso); f2 con tipo desconocido, que no debe romper nada.
    f2 = {**_figura_trampa(), "id": "f2"}
    ctx, p, errors = open_app(browser, seed={"schema": 6, "figures": {"f1": {**_figura_trampa(), "tipo": "figura"}, "f2": f2}, "logs": {}})
    _recorrer_con_trampas(p)
    assert p.evaluate("() => window.__pwn") is None
    assert not errors, errors
    ctx.close()


@test
def importar_dos_veces_a_la_vez_solo_cuenta_una(browser):
    seed = {"schema": 6, "figures": {"f1": fig(1, "a", "b")}, "logs": {}}
    ctx, p, errors = open_app(browser, seed=seed)
    p.click("#btn-settings")
    p.click('[data-setv="importar"]')
    p.fill("#imp-text", json.dumps({"schema": 6, "figures": {"f2": fig(2, "a", "b")}, "logs": {}}))
    p.evaluate("() => { const b = document.querySelector('[data-act=\"import-merge\"]'); b.click(); b.click(); }")
    p.wait_for_timeout(500)
    sn = [x for x in p.evaluate("() => window.__bachateca.listSnapshots()") if x["reason"] == "antes-de-importar"]
    assert len(sn) == 1, sn
    assert sorted(p.evaluate("() => Object.keys(window.__bachateca.state().figures)")) == ["f1", "f2"]
    assert not errors, errors
    ctx.close()


# ---- revisión final: al actualizar desde 1.49

@test
def copia_local_sin_fecha_se_guarda_aparte(browser):
    a = {"schema": 6, "figures": {"f1": fig(1, "a", "b")}, "logs": {}}
    b = {"schema": 6, "figures": {"f1": fig(1, "a", "b"), "f2": fig(2, "a", "b")}, "logs": {}}
    ctx, p, errors = open_app(browser, seed=a, ls={"bachateca.v1": b})
    assert list(p.evaluate("() => window.__bachateca.state().figures")) == ["f1"]
    sn = [x for x in p.evaluate("() => window.__bachateca.listSnapshots()") if x["reason"] == "copia-local"]
    assert len(sn) == 1 and sn[0]["nFig"] == 2, sn
    p.evaluate("() => window.__bachateca.flush()"); p.wait_for_timeout(300)
    assert p.evaluate("() => localStorage.getItem('bachateca.v1')") is None
    p.click("#btn-settings")
    p.click('[data-setv="instantaneas"]')
    p.wait_for_selector('#snap-list [data-act="snap-restore"]')
    assert "Copia guardada aparte" in p.locator("#snap-list").inner_text()
    assert not errors, errors
    ctx.close()
    # Si no se puede guardar aparte, la copia local no se borra.
    ctx, p, errors = open_app(browser, seed=a, ls={"bachateca.v1": b}, init=f"({_SNAP_FALLA})();")
    p.evaluate("() => window.__bachateca.flush()"); p.wait_for_timeout(300)
    assert p.evaluate("() => Object.keys(JSON.parse(localStorage.getItem('bachateca.v1')).figures).length") == 2
    assert not errors, errors
    ctx.close()


@test
def indexeddb_mas_reciente_gana(browser):
    a = {"schema": 6, "guardado": 2000, "figures": {"f1": fig(1, "a", "b")}}
    b = {"schema": 6, "guardado": 1000, "figures": {"f1": fig(1, "a", "b"), "f2": fig(2, "a", "b")}}
    ctx, p, errors = open_app(browser, seed=a, ls={"bachateca.v1": b})
    assert list(p.evaluate("() => window.__bachateca.state().figures")) == ["f1"]
    assert not errors, errors
    ctx.close()


# ---- revisión final: detalles

@test
def ajustes_cuenta_instantaneas_sin_leerlas(browser):
    seed = {"schema": 6, "guardado": 1000, "figures": {"f1": fig(1, "a", "b")}, "logs": {}}
    ctx, p, errors = open_app(browser, seed=seed)
    p.wait_for_function("async () => (await window.__bachateca.listSnapshots()).length === 1")
    p.evaluate("""() => { window.__snapGets = 0; const g = IDBObjectStore.prototype.get;
      IDBObjectStore.prototype.get = function (k) { if (typeof k === "string" && k.startsWith("snap:")) window.__snapGets++;
        return g.apply(this, arguments); }; }""")
    p.click("#btn-settings")
    p.wait_for_function("document.querySelector('#snap-n') && document.querySelector('#snap-n').textContent === '1'")
    assert p.evaluate("() => window.__snapGets") == 0
    p.click('[data-setv="instantaneas"]')
    p.wait_for_selector('#snap-list [data-act="snap-restore"]')
    assert p.evaluate("() => window.__snapGets") >= 1
    assert not errors, errors
    ctx.close()


@test
def exportar_en_modo_seguro_no_hace_nada(browser):
    seed = {"schema": 6, "figures": {"f1": fig(1, "a", "b")}, "logs": {}}
    ctx, p, errors = open_app(browser, seed=seed, init=_parche_lectura(False))
    assert p.evaluate("() => window.__bachateca.safeMode()") is True
    descargas = []
    p.on("download", lambda d: descargas.append(d))
    p.click("#btn-settings")
    for act in ("export", "copy"):
        p.click(f'.sheet [data-act="{act}"]')
        p.wait_for_timeout(300)
        assert "Modo seguro: no se puede exportar." in p.locator(".toast").inner_text(), act
        assert p.locator('#confirm-root [data-cf="ok"]').count() == 0
    assert not descargas
    assert p.evaluate("() => localStorage.getItem('bachateca.backup.at')") is None
    assert p.locator("#exp-text").is_hidden()
    ctx.close()


@test
def video_de_intento_sin_guardar_sigue_en_el_aviso(browser):
    f1 = fig(1, "Cerrada", "Sombra", intentos=[att(1, "a1")])
    ctx, p, errors = open_app(browser, seed={"schema": 6, "figures": {"f1": f1}, "logs": {}}, videos=["a1"])
    assert [x.get("att") for x in p.evaluate("() => window.__bachateca.vidsUnsaved()")] == ["i1"]
    p.click('nav.tabs [data-tab="repertorio"]')
    p.click('#v-repertorio [data-view="f1"]')
    p.click('[data-act="att-open"][data-att="i1"]')
    p.wait_for_selector('[data-viewatt="i1"] video')
    p.wait_for_timeout(300)
    with p.expect_download():
        p.click('[data-act="att-savevid"]')
    p.wait_for_selector('#confirm-root [data-cf="ok"]')
    assert "¿Se ha guardado el vídeo?" in p.locator("#confirm-root").inner_text()
    assert p.locator('#confirm-root [data-cf="ok"]').inner_text() == "Sí, está guardado"
    p.click("#confirm-root .cancel")
    p.wait_for_timeout(200)
    assert [x.get("att") for x in p.evaluate("() => window.__bachateca.vidsUnsaved()")] == ["i1"]
    assert not errors, errors
    ctx.close()


# ---- fase 3
@test
def cadena_no_mezcla_bailes(browser):
    ctx, p, errors = open_app(browser)
    figs = {f["id"]: f for f in [fig(1, "Cerrada", "Abierta 2 manos"),
                                 fig(2, "Abierta 2 manos", "Cerrada", baile="Salsa", nombre="Salsera")]}
    p.evaluate("o => window.__bachateca.setFigs(o)", figs)
    r = p.evaluate("""() => { const B = window.__bachateca, mix = [];
      for (let k = 0; k < 30; k++) B.makeChain("Cerrada").steps.forEach(s => { if (s.f && s.f.baile === "Salsa") mix.push(s.f.id); });
      const a = B.exitsFrom("Abierta 2 manos").map(f => f.id);
      B.setBaile("Salsa");
      return [mix, a, B.exitsFrom("Abierta 2 manos").map(f => f.id), B.exitsFrom("Cerrada").map(f => f.id)]; }""")
    assert r == [[], [], ["f2"], []], r
    assert not errors, errors
    ctx.close()


@test
def social_y_enlazar_por_baile(browser):
    ctx, p, errors = open_app(browser)
    figs = {f["id"]: f for f in [fig(1, "Cerrada", "Abierta 2 manos", nombre="Bachatera"),
                                 fig(2, "Abierta 2 manos", "Cerrada", baile="Salsa", nombre="Salsera")]}
    p.evaluate("o => window.__bachateca.setFigs(o)", figs)
    p.click('nav.tabs [data-tab="enlazar"]')
    assert p.locator("#v-enlazar [data-baile]").count() == 2
    p.click('nav.tabs [data-tab="social"]')
    assert p.locator("#v-social [data-baile]").count() == 2
    p.check("#soc-incl")
    assert "Bachatera" in p.inner_text("#v-social") and "Salsera" not in p.inner_text("#v-social")
    p.click('#v-social [data-baile="Salsa"]')
    t = p.inner_text("#v-social")
    assert "Salsera" in t and "Bachatera" not in t, t
    assert p.get_attribute('#v-social [data-baile="Salsa"]', "aria-pressed") == "true"
    assert not errors, errors
    ctx.close()


@test
def baile_viejo_vuelve_a_bachata(browser):
    ctx, p, errors = open_app(browser)
    both = {f["id"]: f for f in [fig(1, "Cerrada", "Abierta 2 manos"), fig(2, "Abierta 2 manos", "Cerrada", baile="Salsa")]}
    p.evaluate("o => window.__bachateca.setFigs(o)", both)
    p.evaluate("() => window.__bachateca.setBaile('Salsa')")
    only = {f["id"]: f for f in [fig(1, "Cerrada", "Abierta 2 manos"), fig(2, "Abierta 2 manos", "Cerrada")]}
    p.evaluate("o => window.__bachateca.setFigs(o)", only)
    p.click('nav.tabs [data-tab="enlazar"]')
    assert p.locator("[data-baile]").count() == 0
    assert p.locator("#v-enlazar .card").count() >= 1
    assert not errors, errors
    ctx.close()


@test
def repasar_elige_baile(browser):
    ctx, p, errors = open_app(browser)
    figs = {f["id"]: f for f in [fig(1, "Cerrada", "Abierta 2 manos"),
                                 fig(2, "Abierta 2 manos", "Cerrada", baile="Salsa"),
                                 fig(3, "Sombra", "Cerrada", baile="Salsa")]}
    p.evaluate("o => window.__bachateca.setFigs(o)", figs)
    p.click('nav.tabs [data-tab="repasar"]')
    assert p.locator("#v-repasar [data-baile]").count() == 2
    assert "<b>1</b>" in p.inner_html("#v-repasar").split("Figuras</h3>")[0]
    p.click('#v-repasar [data-baile="Salsa"]')
    assert "<b>2</b>" in p.inner_html("#v-repasar").split("Figuras</h3>")[0]
    assert not errors, errors
    ctx.close()


@test
def un_solo_baile_sin_selector(browser):
    ctx, p, errors = open_app(browser)
    figs = {f["id"]: f for f in [fig(1, "Cerrada", "Abierta 2 manos"), fig(2, "Abierta 2 manos", "Cerrada")]}
    p.evaluate("o => window.__bachateca.setFigs(o)", figs)
    p.click('nav.tabs [data-tab="enlazar"]')
    assert p.locator("[data-baile]").count() == 0
    p.click('nav.tabs [data-tab="social"]')
    assert p.locator("[data-baile]").count() == 0
    n = p.evaluate("() => window.__bachateca.makeChain('Cerrada').steps.filter(s => s.f).length")
    assert n == 2, n
    assert not errors, errors
    ctx.close()


@test
def cadena_respeta_el_agarre_elegido(browser):
    ctx, p, errors = open_app(browser)
    figs = {f["id"]: f for f in [fig(0, "Cerrada", "Abierta 2 manos", estado="disponible"),
                                 fig(1, "Abierta 2 manos", "Cerrada", agarreIn="Dos manos", estado="disponible"),
                                 fig(2, "Abierta 2 manos", "Cerrada", agarreIn="Izq–der", estado="disponible")]}
    p.evaluate("o => window.__bachateca.setFigs(o)", figs)
    p.click('nav.tabs [data-tab="enlazar"]')
    p.click('#v-enlazar [data-pos="Abierta 2 manos"]')
    p.click('#v-enlazar [data-hold="Izq–der"]')
    p.click('#v-enlazar [data-act="chain"]')
    assert p.inner_text("#v-enlazar .chain .step:first-child b") == "Figura 2"
    r = p.evaluate("""() => { const B = window.__bachateca, pool = Object.values(B.state().figures), out = [];
      for (let k = 0; k < 20; k++) out.push(B.buildChain(pool, {start: "Abierta 2 manos", hold: "Izq–der"}).steps[0].f.id);
      return out; }""")
    assert set(r) == {"f2"}, r
    assert not errors, errors
    ctx.close()


@test
def cadena_agarres_exactos(browser):
    ctx, p, errors = open_app(browser)
    figs = {f["id"]: f for f in [fig(1, "Cerrada", "Abierta 2 manos", agarreOut="Dos manos"),
                                 fig(2, "Abierta 2 manos", "Cerrada")]}
    p.evaluate("o => window.__bachateca.setFigs(o)", figs)
    r = p.evaluate("""() => { const B = window.__bachateca, pool = Object.values(B.state().figures), n = {a: 0, b: 0};
      for (let k = 0; k < 30; k++) {
        if (B.buildChain(pool, {start: "Cerrada", strict: true}).steps.filter(s => s.f).length > 1) n.a++;
        if (B.buildChain(pool, {start: "Cerrada"}).steps.filter(s => s.f).length > 1) n.b++;
      }
      return n; }""")
    assert r == {"a": 0, "b": 30}, r
    assert not errors, errors
    ctx.close()


@test
def cadena_solo_seguras_y_avisos(browser):
    ctx, p, errors = open_app(browser)
    figs = {f["id"]: f for f in [fig(1, "Cerrada", "Abierta 2 manos", estado="disponible", agarreOut="Dos manos"),
                                 fig(2, "Abierta 2 manos", "Cerrada", estado="practica", nombre="Practicona")]}
    p.evaluate("o => window.__bachateca.setFigs(o)", figs)
    p.click('nav.tabs [data-tab="enlazar"]')
    p.click('#v-enlazar [data-pos="Cerrada"]')
    p.click('#v-enlazar [data-act="chain"]')
    t = p.inner_text("#v-enlazar .chain")
    assert "Practicona" in t and "en práctica" in t and "agarre sin indicar" in t, t
    p.click('#v-enlazar [data-chainopt="safe"]')
    assert p.get_attribute('#v-enlazar [data-chainopt="safe"]', "aria-pressed") == "true"
    assert p.evaluate("() => document.activeElement.dataset.chainopt") == "safe"
    t = p.inner_text("#v-enlazar .chain")
    assert "Practicona" not in t and "en práctica" not in t, t
    assert p.get_attribute('#v-enlazar [data-chainopt="strict"]', "aria-pressed") == "false"
    assert not errors, errors
    ctx.close()


@test
def cadena_aviso_de_agarre_solo_si_cuenta(browser):
    ctx, p, errors = open_app(browser)
    figs = {f["id"]: f for f in [fig(1, "Cerrada", "Abierta 2 manos", agarreIn="Dos manos"),
                                 fig(2, "Abierta 2 manos", "Cerrada")]}
    p.evaluate("o => window.__bachateca.setFigs(o)", figs)
    r = p.evaluate("""() => { const B = window.__bachateca, a = Object.values(B.state().figures);
      return [B.buildChain([a[0]], {start: "Cerrada", hold: ""}).steps[0].vago,
              B.buildChain([a[1]], {start: "Abierta 2 manos", hold: "Dos manos"}).steps[0].vago,
              B.buildChain([a[1]], {start: "Abierta 2 manos", hold: ""}).steps[0].vago]; }""")
    assert r == [False, True, False], r
    assert not errors, errors
    ctx.close()


@test
def buildChain_es_pura(browser):
    ctx, p, errors = open_app(browser)
    figs = {f["id"]: f for f in [fig(1, "Cerrada", "Abierta 2 manos"), fig(2, "Cerrada", "Abierta 2 manos"),
                                 fig(3, "Abierta 2 manos", "Cerrada"), fig(4, "Abierta 2 manos", "Cerrada")]}
    p.evaluate("o => window.__bachateca.setFigs(o)", figs)
    r = p.evaluate("""() => { const B = window.__bachateca, pool = Object.values(B.state().figures);
      const ids = () => B.buildChain(pool, {start: "Cerrada"}, () => 0).steps.map(s => s.f ? s.f.id : "dead");
      return [ids(), ids()]; }""")
    assert r[0] == r[1] and len(r[0]) == 4, r
    assert not errors, errors
    ctx.close()

@test
def social_cuenta_como_repaso(browser):
    hoy = __import__("datetime").date.today()
    d = lambda n: (hoy + __import__("datetime").timedelta(days=n)).isoformat()
    seed = {"figures": {"f1": fig(1, "Cerrada", "Abierta 2 manos", rep={"step": 1, "due": d(0), "last": d(-1), "aciertos": 1, "fallos": 0}),
                        "f2": fig(2, "Abierta 2 manos", "Cerrada", estado="incompleta", rep={"step": 1, "due": d(0), "last": d(-1)})}}
    ctx, p, errors = open_app(browser, seed=seed)
    p.click('nav.tabs [data-tab="social"]')
    p.click('[data-act="log-open"]')
    p.click('[data-logfig="f1"]'); p.click('[data-logfig="f2"]')
    p.click('[data-act="log-save"]')
    r = p.evaluate("() => { const S = window.__bachateca.state(); return [S.figures.f1.rep, S.figures.f2.rep, Object.values(S.logs)[0], S.actividad] }")
    assert r[0]["step"] == 2 and r[0]["last"] == r[2]["fecha"] and r[0]["due"] == d(7), r
    assert r[1]["step"] == 1 and r[1]["due"] == d(0), "la incompleta no cambia su repaso"
    assert r[2]["repAntes"]["f1"]["step"] == 1 and "f2" not in r[2]["repAntes"], r[2]
    assert r[3][r[2]["fecha"]] == 1, r[3]
    p.click('[data-act="log-again"]')
    p.click('[data-logfig="f1"]')
    p.click('[data-act="log-save"]')
    r = p.evaluate("() => window.__bachateca.state().figures.f1.rep.step")
    assert r == 2, "como máximo un repaso por día y figura"
    assert not errors, errors
    ctx.close()


@test
def borrar_social_deshace_el_repaso(browser):
    import datetime
    d = lambda n: (datetime.date.today() + datetime.timedelta(days=n)).isoformat()
    seed = {"figures": {"f1": fig(1, "Cerrada", "Abierta 2 manos", rep={"step": 1, "due": d(0), "last": d(-1), "aciertos": 1, "fallos": 0})}}
    ctx, p, errors = open_app(browser, seed=seed)
    p.click('nav.tabs [data-tab="social"]')
    p.click('[data-act="log-open"]')
    p.click('[data-logfig="f1"]')
    p.click('[data-act="log-save"]')
    assert p.evaluate("() => window.__bachateca.state().figures.f1.rep.step") == 2
    p.click('[data-act="close"]') if p.locator('[data-act="close"]').count() else None
    p.click('[data-act="log-open"]') if p.locator('[data-dellog]').count() == 0 else None
    p.click('[data-dellog]')
    r = p.evaluate("() => window.__bachateca.state().figures.f1.rep")
    assert r["step"] == 1 and r["due"] == d(0), r
    p.click(".toast .undo")
    r = p.evaluate("() => window.__bachateca.state().figures.f1")
    assert r["rep"]["step"] == 2 and r["usos"] == 1, r
    assert not errors, errors
    ctx.close()


@test
def atrasada_no_es_olvidada(browser):
    import datetime
    d = lambda n: (datetime.date.today() + datetime.timedelta(days=n)).isoformat()
    seed = {"figures": {"f1": fig(1, "Cerrada", "Abierta 2 manos", nombre="Retrasada", rep={"step": 3, "due": d(-5), "last": d(-20), "aciertos": 3, "fallos": 0}),
                        "f2": fig(2, "Abierta 2 manos", "Cerrada", nombre="Fallada", rep={"step": 0, "due": d(0), "last": d(-1), "aciertos": 0, "fallos": 1})}}
    ctx, p, errors = open_app(browser, seed=seed)
    ms = p.evaluate("() => [window.__bachateca.memState(window.__bachateca.state().figures.f1), window.__bachateca.memState(window.__bachateca.state().figures.f2)]")
    assert ms == ["atrasada", "olvidada"], ms
    p.click('nav.tabs [data-tab="repertorio"]')
    assert "Atrasada" in p.locator('#v-repertorio [data-view="f1"]').inner_text()
    assert "Olvidada" not in p.locator('#v-repertorio [data-view="f1"]').inner_text()
    assert "Olvidada" in p.locator('#v-repertorio [data-view="f2"]').inner_text()
    p.click('nav.tabs [data-tab="inicio"]')
    txt = p.locator("#v-inicio .in-mem").inner_text()
    assert "1 atrasada" in txt and "1 olvidada" in txt and p.locator("#v-inicio .in-mem .in-big").inner_text().startswith("1"), txt
    assert not errors, errors
    ctx.close()


@test
def borrar_social_tras_repasar_conserva_el_repaso(browser):
    import datetime
    d = lambda n: (datetime.date.today() + datetime.timedelta(days=n)).isoformat()
    seed = {"figures": {"f1": fig(1, "Cerrada", "Abierta 2 manos", rep={"step": 1, "due": d(0), "last": d(-1), "aciertos": 1, "fallos": 0})}}
    ctx, p, errors = open_app(browser, seed=seed)
    p.click('nav.tabs [data-tab="social"]')
    p.click('[data-act="log-open"]'); p.click('[data-logfig="f1"]'); p.click('[data-act="log-save"]')
    p.evaluate("() => { const f = window.__bachateca.state().figures.f1; f.rep.due = window.__bachateca.todayStr(); }")
    p.click('[data-act="close"]')
    p.click('nav.tabs [data-tab="repasar"]')
    p.click('[data-act="start-fig"]'); p.click('[data-act="reveal"]'); p.click('[data-grade="no"]')
    r = p.evaluate("() => window.__bachateca.state().figures.f1.rep")
    assert r["step"] == 0 and r["fallos"] == 1, r
    p.click('nav.tabs [data-tab="social"]')
    p.click('[data-act="log-open"]')
    p.click('[data-dellog]')
    r = p.evaluate("() => window.__bachateca.state().figures.f1.rep")
    assert r["step"] == 0 and r["fallos"] == 1, r
    assert not errors, errors
    ctx.close()


@test
def social_de_ayer_no_cuenta_si_ya_repasaste_hoy(browser):
    import datetime, time
    d = lambda n: (datetime.date.today() + datetime.timedelta(days=n)).isoformat()
    rep = {"step": 2, "due": d(7), "last": d(0), "aciertos": 2, "fallos": 0}
    seed = {"figures": {"f1": fig(1, "Cerrada", "Abierta 2 manos", rep=dict(rep))}}
    ctx, p, errors = open_app(browser, seed=seed, ls={"bachateca.salieron": {"t": int(time.time() * 1000), "d": d(-1), "ids": ["f1"], "bloq": ""}})
    p.click('nav.tabs [data-tab="social"]')
    p.click('[data-act="log-open"]')
    p.click('[data-act="log-save"]')
    r = p.evaluate("() => [Object.values(window.__bachateca.state().logs)[0].fecha, window.__bachateca.state().figures.f1.rep]")
    assert r[0] == d(-1) and r[1] == rep, r
    assert not errors, errors
    ctx.close()


@test
def migracion_7_preguntas(browser):
    ctx, p, errors = open_app(browser)
    r = p.evaluate("""() => { const B = window.__bachateca, t = B.todayStr;
      const old = {schema: 6, figures: {}, logs: {a: {id: "a", fecha: t(-10), bloqueo: "Sombra"}, b: {id: "b", fecha: t(-3), bloqueo: "Sombra"},
        c: {id: "c", fecha: t(-90), bloqueo: "Cerrada"}, d: {id: "d", fecha: t(-1), bloqueo: ""}}};
      const m = B.migrate(old), m2 = B.migrate(m), m3 = B.migrate({...m, schema: 6});
      const sinPreg = B.migrate({schema: 6, figures: {}});
      return {m, same: JSON.stringify(m) === JSON.stringify(m2), n3: Object.keys(m3.preguntas).length, sinPreg: sinPreg.preguntas, t3: t(-3), S: B.SCHEMA}; }""")
    assert r["S"] == 8 and r["m"]["schema"] == 8, r
    qs = list(r["m"]["preguntas"].values())
    assert len(qs) == 1 and qs[0]["pos"] == "Sombra" and qs[0]["creada"] == r["t3"] and qs[0]["baile"] == "Bachata" and not qs[0].get("resuelta"), qs
    assert r["same"] and r["n3"] == 1, "repetir la migración no duplica"
    assert r["sinPreg"] == {}, r["sinPreg"]
    assert len(r["m"]["logs"]) == 4, "no borra registros"
    assert not errors, errors
    ctx.close()


@test
def bloqueo_crea_pregunta_y_figura_la_resuelve(browser):
    ctx, p, errors = open_app(browser, seed={"figures": {"f1": fig(1, "Cerrada", "Sombra")}})
    p.click('nav.tabs [data-tab="social"]')
    p.click('[data-act="log-open"]')
    p.select_option("#lg-bloq", "Sombra")
    p.click('[data-act="log-save"]')
    p.click('[data-act="log-again"]')
    p.select_option("#lg-bloq", "Sombra")
    p.click('[data-act="log-save"]')
    p.click('[data-act="close"]')
    qs = p.evaluate("() => Object.values(window.__bachateca.state().preguntas)")
    assert len(qs) == 1 and qs[0]["pos"] == "Sombra" and qs[0]["baile"] == "Bachata", qs
    p.click('nav.tabs [data-tab="inicio"]')
    assert "Desde Sombra, ¿qué figura sencilla puedo hacer?" in p.locator("#v-inicio").inner_text()
    assert "Para tu próxima clase" in p.locator("#v-inicio").inner_text()
    # Una figura nueva en práctica desde Sombra: un solo aviso con su mensaje y la pregunta.
    p.click("#btn-new")
    p.click('[data-act="to-full"]')
    p.fill("#ff-nombre", "Salida nueva")
    p.click('#ff-estado [data-est="practica"]')
    p.select_option("#ff-in", "Sombra")
    p.select_option("#ff-out", "Cerrada")
    p.click('#fig-form button[type="submit"]')
    t = p.locator(".toast").inner_text()
    assert "Figura guardada. ¿Responde a tu pregunta desde Sombra?" in t, t
    p.click(".toast .undo")
    q, fid = p.evaluate("""() => { const S = window.__bachateca.state(); return [Object.values(S.preguntas)[0],
      Object.values(S.figures).find(f => f.nombre === "Salida nueva").id]; }""")
    assert q["resuelta"] == p.evaluate("() => window.__bachateca.todayStr()") and q["figId"] == fid, q
    assert "Para tu próxima clase" not in p.locator("#v-inicio").inner_text()
    assert not errors, errors
    ctx.close()


@test
def preguntas_ya_tengo_salida_y_quitar_con_deshacer(browser):
    import datetime
    hoy = datetime.date.today().isoformat()
    seed = {"schema": 7, "figures": {"f1": fig(1, "Cerrada", "Sombra")},
            "preguntas": {"q1": {"id": "q1", "pos": "Sombra", "baile": "Bachata", "creada": hoy},
                          "q2": {"id": "q2", "pos": "Hammerlock", "baile": "Bachata", "creada": hoy}}}
    ctx, p, errors = open_app(browser, seed=seed)
    assert p.locator('#v-inicio [data-act="q-done"]').count() == 2
    p.click('#v-inicio [data-act="q-done"][data-id="q1"]')
    assert p.evaluate("() => window.__bachateca.state().preguntas.q1.resuelta") == hoy
    assert "Desde Sombra" not in p.locator("#v-inicio").inner_text()
    p.click(".toast .undo")
    assert not p.evaluate("() => window.__bachateca.state().preguntas.q1.resuelta")
    assert "Desde Sombra" in p.locator("#v-inicio").inner_text()
    p.click('#v-inicio [data-act="q-del"][data-id="q2"]')
    assert "q2" not in p.evaluate("() => window.__bachateca.state().preguntas")
    p.click(".toast .undo")
    assert "q2" in p.evaluate("() => window.__bachateca.state().preguntas")
    p.wait_for_timeout(300)
    assert set(stored_state(p)["preguntas"]) == {"q1", "q2"}
    assert not errors, errors
    ctx.close()


@test
def importar_preguntas(browser):
    import datetime
    hoy = datetime.date.today().isoformat()
    seed = {"schema": 7, "figures": {"f1": fig(1, "Cerrada", "Sombra")},
            "preguntas": {"q1": {"id": "q1", "pos": "Sombra", "baile": "Bachata", "creada": hoy}}}
    ctx, p, errors = open_app(browser, seed=seed)
    exp = json.loads(p.evaluate("() => window.__bachateca.exportData()"))
    assert exp["preguntas"]["q1"]["pos"] == "Sombra", exp.get("preguntas")
    exp["preguntas"]["mal id!"] = {"id": "mal id!", "pos": "Cerrada"}
    exp["preguntas"]["q3"] = {"id": "q3", "pos": "Cerrada", "creada": "ayer", "resuelta": "2026-11-01"}
    p.click('#v-inicio [data-act="q-del"][data-id="q1"]')
    assert p.evaluate("() => window.__bachateca.state().preguntas") == {}
    import_text(p, json.dumps(exp))
    assert "1 descartadas" in p.locator(".toast").inner_text(), p.locator(".toast").inner_text()
    qs = p.evaluate("() => window.__bachateca.state().preguntas")
    assert set(qs) == {"q1", "q3"} and qs["q1"]["pos"] == "Sombra", qs
    assert "creada" not in qs["q3"] and qs["q3"]["resuelta"] == "2026-11-01", qs["q3"]
    # Reemplazar: se queda solo lo de la copia.
    p.evaluate("() => { window.__bachateca.state().preguntas.qx = {id: 'qx', pos: 'Hammerlock', baile: 'Bachata', creada: '2026-11-01'}; }")
    p.click('[data-act="close"]')
    exp2 = {**exp, "preguntas": {"q1": exp["preguntas"]["q1"]}}
    import_text(p, json.dumps(exp2), replace=True)
    p.click('.confirm [data-cf="ok"]')
    p.wait_for_timeout(300)
    assert set(p.evaluate("() => window.__bachateca.state().preguntas")) == {"q1"}
    r = p.evaluate("() => window.__bachateca.sanitizeImport({figures: {}, preguntas: {a: {id: 'a', pos: ''}, b: 5, c: {id: 'c', pos: 'Sombra'}}})")
    assert set(r["preguntas"]) == {"c"} and r["descartadas"] == 2, r
    assert not errors, errors
    ctx.close()


@test(solo_chromium="cámara y micrófono simulados")
def conteo_pide_sesion_de_audio(browser):
    # Safari 16.4+: sin audioSession "playback" el interruptor de silencio del iPhone calla el conteo.
    init = """Object.defineProperty(navigator, 'audioSession', {configurable: true, value: (() => {
      window.__as = []; let t = 'auto';
      return {get type(){ return t; }, set type(v){ t = v; window.__as.push(v); }};
    })()});"""
    ctx, p, errors = open_app(browser, seed=cmp_seed(intentos=[]), init=init)
    put_fixture(p, ["v1"])
    p.click('nav.tabs [data-tab="repertorio"]'); p.click('#v-repertorio [data-view="f1"]')
    p.locator('[data-act="rc-open"]').click()
    p.wait_for_function("!document.querySelector('#rc-go').disabled", timeout=10000)
    p.click("#rc-go")
    p.wait_for_function("document.querySelector('#rc-beat').textContent !== ''", timeout=5000)
    p.wait_for_timeout(1000)
    p.click("#rc-go")
    p.wait_for_selector("#att-form #ff-prev", timeout=10000)
    h = p.evaluate("() => window.__as")
    assert "play-and-record" in h and h[-1] == "auto", h
    assert not errors, errors
    ctx.close()


@test
def copia_en_memoria_solo_para_ese_video(browser):
    """Si un vídeo necesitó la copia en memoria, solo ese la usa: los demás siguen como blob."""
    seed = {"schema": 6, "figures": {"f1": fig(1, "Cerrada", "Sombra", vid="v1"), "f2": fig(2, "Sombra", "Cerrada", vid="v2")}, "logs": {}}
    ctx, p, errors = open_app(browser, seed=seed, ls={"bachateca.vidmem": ["v1"]})
    put_fixture(p, ["v1", "v2"])
    p.reload(); p.wait_for_function("window.__bachateca && window.__bachateca.ready()")
    p.click('nav.tabs [data-tab="repertorio"]')
    for f in ("f1", "f2"):
        p.click(f'#v-repertorio [data-view="{f}"]')
        p.wait_for_function("document.querySelector('.fv-media video') && document.querySelector('.fv-media video').readyState >= 1", timeout=10000)
        assert ficha_video(p)["err"] is None
        p.click('[data-act="close"]'); p.wait_for_timeout(200)
    k = p.evaluate("() => [window.__bachateca.vidUrlKind('v1'), window.__bachateca.vidUrlKind('v2')]")
    assert k == ["mem", "blob"], k
    assert not errors, errors
    ctx.close()


def sim_figs():
    return {f["id"]: f for f in [fig(1, "Cerrada", "Sombra", estado="disponible"),
                                 fig(2, "Sombra", "Abierta 2 manos"),
                                 fig(3, "Abierta 2 manos", "Cerrada")]}


@test
def simulacro_completo(browser):
    ctx, p, errors = open_app(browser, seed={"figures": sim_figs()})
    st = lambda: p.evaluate("() => window.__bachateca.simState()")
    p.evaluate("() => window.__bachateca.simForce(['Cerrada', 'Sombra'])")
    p.click('nav.tabs [data-tab="social"]')
    p.click('#v-social [data-act="sim-open"]')
    assert "Decide una salida antes del siguiente 1." in p.inner_text("[data-sim]")
    assert p.locator("[data-simn]").count() == 2
    p.fill("#sim-bpm", "150")
    p.click("#sim-go")
    s = st()
    assert s["fase"] == "decide" and s["i"] == 0 and s["rondas"] == 2 and s["pos"] == "Cerrada", s
    assert "Cerrada" in p.inner_text("[data-sim] .big")
    p.click("#sim-ok")
    s = st()
    assert s["fase"] == "revela" and isinstance(s["beats"], (int, float)), s
    assert "Figura 1" in p.inner_text("[data-sim]")
    p.click('[data-simg="fluida"]')
    s = st()
    assert s["fase"] == "decide" and s["i"] == 1 and s["pos"] == "Sombra", s
    p.wait_for_function("window.__bachateca.simState().fase === 'revela'", timeout=8000)
    t = p.inner_text("[data-sim]")
    assert "Se acabó el tiempo" in t and "Figura 2" in t, t
    assert st()["beats"] is None
    assert p.locator('[data-simg="fluida"]').count() == 0
    p.click('[data-simg="no"]')
    assert st()["fase"] == "fin"
    t = p.inner_text("[data-sim]")
    assert "1 de 2" in t and "Dónde dudaste" in t, t
    assert "Sombra" in t.split("Dónde dudaste")[1]
    assert p.locator('[data-sim] [data-act="goto-pos"][data-p="Sombra"]').count() == 1
    lr = p.evaluate("() => window.__bachateca.state().linkRep")
    assert lr["Bachata\u241fCerrada"]["step"] == 1 and lr["Bachata\u241fSombra"]["fallos"] == 1, lr
    hoy = p.evaluate("() => window.__bachateca.todayStr()")
    assert p.evaluate("() => window.__bachateca.state().actividad")[hoy] == 2
    p.click('[data-sim] [data-act="goto-pos"][data-p="Sombra"]')
    assert p.locator("[data-sim]").count() == 0 and st() is None
    assert p.evaluate("() => location.hash") == "#enlazar" or p.locator("#v-enlazar").is_visible()
    assert not errors, errors
    ctx.close()


@test
def simulacro_posicion_sin_salida(browser):
    ctx, p, errors = open_app(browser, seed={"figures": {"f1": fig(1, "Cerrada", "Sombra")}})
    p.evaluate("() => window.__bachateca.simForce(['Sombra'])")
    p.click('nav.tabs [data-tab="repasar"]')
    assert "Simulacro de social" in p.inner_text("#v-repasar")
    p.click('#v-repasar [data-act="sim-open"]')
    p.click("#sim-go")
    p.click("#sim-ok")
    assert "aún no tienes salida" in p.inner_text("[data-sim]")
    qs = p.evaluate("() => Object.values(window.__bachateca.state().preguntas || {})")
    assert any(q["pos"] == "Sombra" and not q.get("resuelta") for q in qs), qs
    assert not errors, errors
    ctx.close()


@test
def simulacro_cerrar_para_el_conteo(browser):
    init = """(() => { window.__stops = 0; const o = AudioScheduledSourceNode.prototype.stop;
      AudioScheduledSourceNode.prototype.stop = function(...a){ window.__stops++; return o.apply(this, a); }; })();"""
    ctx, p, errors = open_app(browser, seed={"figures": sim_figs()}, init=init)
    p.evaluate("() => window.__bachateca.simForce(['Cerrada'])")
    p.click('nav.tabs [data-tab="social"]')
    p.click('#v-social [data-act="sim-open"]')
    p.click("#sim-go")
    p.wait_for_function("window.__bachateca.simState() && window.__bachateca.simState().beats > 1", timeout=5000)
    antes = p.evaluate("() => window.__stops")
    p.click('[data-sim] [data-act="close"]')
    assert p.locator("[data-sim]").count() == 0
    assert p.evaluate("() => window.__bachateca.simState()") is None
    assert p.evaluate("() => window.__stops") > antes
    assert not errors, errors
    ctx.close()


@test
def simulacro_sin_posiciones(browser):
    ctx, p, errors = open_app(browser, seed={"figures": {"f1": fig(1, "", "")}})
    p.click('nav.tabs [data-tab="social"]')
    p.click('#v-social [data-act="sim-open"]')
    assert "Aún no tienes posiciones con salidas. Añade dónde empiezan y acaban tus figuras." in p.inner_text("[data-sim]")
    assert p.locator("#sim-go").count() == 0
    assert not errors, errors
    ctx.close()


@test
def simulacro_solo_falta_el_agarre(browser):
    figs = {f["id"]: f for f in [fig(1, "Cerrada", "Sombra", agarreOut="Dos manos"),
                                 fig(2, "Sombra", "Cerrada", agarreIn="Izq–der"),
                                 fig(3, "Sombra", "Abierta", agarreIn="Izq–der", estado="disponible")]}
    ctx, p, errors = open_app(browser, seed={"figures": figs})
    p.evaluate("() => window.__bachateca.simForce([{pos: 'Sombra', hold: 'Dos manos'}])")
    p.click('nav.tabs [data-tab="social"]')
    p.click('#v-social [data-act="sim-open"]')
    p.click("#sim-go")
    p.click("#sim-ok")
    t = p.inner_text("[data-sim]")
    assert "Con Dos manos aún no tienes salida desde aquí." in t and "Figura 2" in t, t
    assert "pide una en clase" not in t, t
    assert p.locator("[data-sim] .exits.dim-all li").count() == 2
    assert p.locator("[data-sim] .exits li.dim").count() == 1
    seg = [x for x in p.locator("[data-sim] .exits li").all_inner_texts() if "Figura 3" in x]
    assert len(seg) == 1 and "en práctica" not in seg[0], seg
    qs = p.evaluate("() => Object.values(window.__bachateca.state().preguntas || {}).filter(q => !q.resuelta)")
    assert qs == [], qs
    assert not errors, errors
    ctx.close()


@test
def simulacro_una_subida_por_dia(browser):
    ctx, p, errors = open_app(browser, seed={"figures": sim_figs()})
    p.evaluate("() => window.__bachateca.simForce(['Cerrada', 'Sombra', 'Cerrada'])")
    p.click('nav.tabs [data-tab="social"]')
    p.click('#v-social [data-act="sim-open"]')
    p.click("#sim-go")
    for _ in range(3):
        p.click("#sim-ok"); p.click('[data-simg="fluida"]')
    lr = p.evaluate("() => window.__bachateca.state().linkRep")
    assert lr["Bachata\u241fCerrada"]["step"] == 1 and lr["Bachata\u241fSombra"]["step"] == 1, lr
    hoy = p.evaluate("() => window.__bachateca.todayStr()")
    assert p.evaluate("() => window.__bachateca.state().actividad")[hoy] == 3
    assert not errors, errors
    ctx.close()


@test
def copia_con_repantes_raro(browser):
    import datetime
    hoy = datetime.date.today().isoformat()
    rep = {"step": 1, "due": hoy, "last": hoy, "aciertos": 1, "fallos": 0}
    ctx, p, errors = open_app(browser)
    cp = {"app": "bachateca", "version": 3, "figures": {"f1": fig(1, "Cerrada", "Sombra", rep=rep)},
          "logs": {"l1": {"id": "l1", "fecha": hoy, "figs": ["f1"], "repAntes": {"f1": {"step": "x", "due": "<b>"}}, "repDespues": {"f1": rep}}}}
    import_text(p, json.dumps(cp))
    p.click('[data-act="close"]')
    p.click('nav.tabs [data-tab="social"]')
    p.click('[data-act="log-open"]')
    p.click('[data-dellog]')
    r = p.evaluate("() => window.__bachateca.state().figures.f1.rep")
    assert r is None or (isinstance(r["step"], int) and ("due" not in r or r["due"][:2] == "20")), r
    assert not errors, errors
    ctx.close()


@test
def cadena_opciones_sin_cadena_no_generan(browser):
    ctx, p, errors = open_app(browser)
    p.evaluate("o => window.__bachateca.setFigs(o)", {"f1": fig(1, "Cerrada", "Sombra", estado="disponible")})
    p.click('nav.tabs [data-tab="enlazar"]')
    p.click('#v-enlazar [data-pos="Cerrada"]')
    p.click('#v-enlazar [data-chainopt="safe"]')
    assert p.locator("#v-enlazar .chain").count() == 0
    assert not errors, errors
    ctx.close()


# ---- fase 4
@test
def migracion_8_repaso_por_baile(browser):
    ctx, p, errors = open_app(browser)
    r = p.evaluate("""() => { const B = window.__bachateca, t = B.todayStr;
      const old = {schema: 7, figures: {}, linkRep: {Cerrada: {step: 2, due: t(3)}, "Salsa\u241fSombra": {step: 1, due: t(1)}}};
      const m = B.migrate(old), m2 = B.migrate(m), m3 = B.migrate({...m, schema: 7});
      return {m, same: JSON.stringify(m) === JSON.stringify(m2), same3: JSON.stringify(m) === JSON.stringify(m3), S: B.SCHEMA}; }""")
    assert r["S"] == 8 and r["m"]["schema"] == 8, r
    lr = r["m"]["linkRep"]
    assert sorted(lr) == ["Bachata\u241fCerrada", "Salsa\u241fSombra"] and lr["Bachata\u241fCerrada"]["step"] == 2, lr
    assert r["same"] and r["same3"], "repetir la migración no cambia nada"
    assert not errors, errors
    ctx.close()


@test
def repaso_de_enlaces_separado_por_baile(browser):
    figs = {f["id"]: f for f in [fig(1, "Cerrada", "Abierta 2 manos"), fig(2, "Abierta 2 manos", "Cerrada"),
                                  fig(3, "Cerrada", "Abierta 2 manos", baile="Salsa"), fig(4, "Abierta 2 manos", "Cerrada", baile="Salsa")]}
    ctx, p, errors = open_app(browser, seed={"figures": figs})
    p.click('nav.tabs [data-tab="repasar"]')
    p.click('#v-repasar [data-act="start-link"]')
    for _ in range(3):
        if p.locator('[data-act="reveal"]').count() == 0: break
        p.click('[data-act="reveal"]'); p.click('[data-grade="fluida"]')
    lr = p.evaluate("() => window.__bachateca.state().linkRep")
    assert "Bachata\u241fCerrada" in lr and not any(k.startswith("Salsa") for k in lr), lr
    p.click('#v-repasar [data-act="end"]')
    p.evaluate("() => window.__bachateca.setBaile('Salsa')")
    p.click('nav.tabs [data-tab="repasar"]')
    assert p.locator('#v-repasar [data-act="start-link"]').count() == 1, "en salsa siguen pendientes"
    assert "2 posiciones tocan" in p.inner_text("#v-repasar"), p.inner_text("#v-repasar")
    assert not errors, errors
    ctx.close()


@test
def renombrar_posicion_mueve_su_repaso(browser):
    seed = {"schema": 8, "figures": {"f1": fig(1, "Cerrada", "Sombra"), "f2": fig(2, "Sombra", "Cerrada", baile="Salsa")},
            "linkRep": {"Bachata\u241fCerrada": {"step": 1, "due": "2030-01-01"}, "Salsa\u241fCerrada": {"step": 2, "due": "2030-01-02"},
                        "Salsa\u241fSombra": {"step": 0, "due": "2030-01-03"}}}
    ctx, p, errors = open_app(browser, seed=seed)
    p.evaluate("() => { const B = window.__bachateca; B.renameItem('pos', B.state().positions.indexOf('Cerrada'), 'Pegados'); }")
    lr = p.evaluate("() => window.__bachateca.state().linkRep")
    assert sorted(lr) == ["Bachata\u241fPegados", "Salsa\u241fPegados", "Salsa\u241fSombra"], lr
    assert lr["Salsa\u241fPegados"]["step"] == 2 and lr["Bachata\u241fPegados"]["step"] == 1
    assert not errors, errors
    ctx.close()


def main():
    nombre = os.environ.get("BROWSER", "chromium")
    if nombre not in ("chromium", "webkit"):
        sys.exit(f"BROWSER debe ser «chromium» o «webkit», no «{nombre}»")
    srv = serve()
    failed = skipped = 0
    with sync_playwright() as pw:
        if nombre == "chromium":
            exe = os.environ.get("CHROME")
            # Cámara y micrófono de mentira (para la prueba del conteo), sin pedir permiso.
            args = ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"]
            browser = pw.chromium.launch(args=args, **({"executable_path": exe} if exe else {}))
        else:
            browser = pw.webkit.launch()
        for fn in results:
            if nombre == "webkit" and fn.solo_chromium:
                skipped += 1
                print(f"  salta {fn.__name__} ({fn.solo_chromium})")
                continue
            try:
                fn(browser)
                print(f"  ok   {fn.__name__}")
            except Exception:
                failed += 1
                print(f"  FALLA {fn.__name__}")
                traceback.print_exc(limit=3)
        browser.close()
    srv.shutdown()
    total = len(results) - skipped
    extra = f" ({skipped} saltadas)" if skipped else ""
    print(f"\n{total - failed} de {total} pruebas correctas{extra}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
