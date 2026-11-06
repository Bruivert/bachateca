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
    assert st["schema"] == 2, st.get("schema")
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
    assert exp["schema"] == 2 and "x" in exp["figures"]
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
    assert st["schema"] == 2 and len(st["actividad"]) >= 3, st.get("actividad")
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


def main():
    srv = serve()
    failed = 0
    with sync_playwright() as pw:
        exe = os.environ.get("CHROME")
        browser = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
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
