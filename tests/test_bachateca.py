#!/usr/bin/env python3
"""Pruebas automáticas de Bachateca en un navegador de verdad (Chromium, sin ventana).

Uso, desde la carpeta del repositorio:
    pip install playwright && playwright install chromium   # solo la primera vez
    python3 tests/test_bachateca.py

Cada prueba abre la app limpia (sin datos), así que no toca nada de tu iPhone ni de tu navegador.
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


def test(fn):
    results.append(fn)
    return fn


def open_app(browser, seed=None, videos=None):
    """App limpia. seed: estado guardado antes de abrirla (como si viniera de una versión anterior)."""
    ctx = browser.new_context(service_workers="block", viewport={"width": 390, "height": 844})
    # Sin hoja de compartir: así «Guardar en Fotos» y «Exportar» descargan el archivo y se puede comprobar.
    # (Chromium reciente la tiene y, sin ventana, se queda esperando.)
    ctx.add_init_script("delete Navigator.prototype.share; delete Navigator.prototype.canShare;")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and not m.text.startswith("Failed to load resource") and errors.append(m.text))
    page.on("response", lambda r: r.status >= 400 and not r.url.endswith("favicon.ico") and errors.append(f"{r.status} {r.url}"))
    if seed is not None or videos:
        page.goto(URL.replace("index.html?test", "README.md"))  # mismo origen, sin arrancar la app
        page.evaluate("""async ([seed, videos]) => {
          const db = await new Promise((res, rej) => { const r = indexedDB.open("bachateca", 1);
            r.onupgradeneeded = () => { r.result.createObjectStore("kv"); r.result.createObjectStore("videos"); };
            r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });
          await new Promise((res, rej) => { const t = db.transaction(["kv", "videos"], "readwrite");
            if (seed) t.objectStore("kv").put(seed, "state");
            for (const id of (videos || [])) t.objectStore("videos").put(new Blob([new Uint8Array(2048)], {type: "video/mp4"}), id);
            t.oncomplete = res; t.onerror = () => rej(t.error); });
          db.close();
        }""", [seed, videos or []])
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
    assert st["logs"]["l1"]["figs"] == ["a"] and st["linkRep"]["Cerrada"]["step"] == 1
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
    assert ring.startswith("2") and "de 4" in ring, ring      # 4 activas; olvidadas: la 2 (último repaso fallado) y la 3 (6 días pendiente)
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
    assert r["S"] == 5 and r["m"]["schema"] == 5 and r["same"], r
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


# ---------------------------------------------------------------- prueba del conteo al grabar (conteo.html)
def open_conteo(browser, seed=None):
    ctx, p, errors = open_app(browser, seed=seed)
    p.goto(URL.replace("index.html?test", "conteo.html"))
    p.wait_for_function("window.__conteo && window.__conteo.lines.some(l => l.includes('Voz cargada'))", timeout=15000)
    return ctx, p, errors


def log_has(p, text, timeout=15000):
    p.wait_for_function("t => window.__conteo.lines.some(l => l.includes(t))", arg=text, timeout=timeout)


@test
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


@test
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


@test
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


def main():
    srv = serve()
    failed = 0
    with sync_playwright() as pw:
        exe = os.environ.get("CHROME")
        # Cámara y micrófono de mentira (para la prueba del conteo), sin pedir permiso.
        args = ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"]
        browser = pw.chromium.launch(args=args, **({"executable_path": exe} if exe else {}))
        for fn in results:
            try:
                fn(browser)
                print(f"  ok   {fn.__name__}")
            except Exception:
                failed += 1
                print(f"  FALLA {fn.__name__}")
                traceback.print_exc(limit=3)
        browser.close()
    srv.shutdown()
    print(f"\n{len(results) - failed} de {len(results)} pruebas correctas")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
