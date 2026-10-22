"""Genera le grafiche Instagram di F.C. Cantone.

Storie 1080x1920:
    python render.py partita.json            # pre, convocati, risultato
    python render.py partita.json pre        # solo pre-partita
    python render.py partita.json convocati
    python render.py partita.json risultato
Post feed 1080x1350:
    python render.py partita.json post       # risultato per il feed
    python render.py partita.json pagelle    # carosello: copertina + una slide a giocatore
"""
import json
import sys
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent
TPL = ROOT / "templates"
OUT = ROOT / "out"
LOGO = (ROOT / "assets" / "logo_fccantone.png").resolve().as_uri()
NOME_NOI = "F.C. Cantone"
CAMPO = "Centro sportivo US Villa Cortese\nVia Pacinotti 19"

GIORNI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def sigla(nome):
    parole = [p for p in nome.replace(".", " ").split() if p[0].isalpha()]
    return "".join(p[0] for p in parole[:3]).upper() or "?"


def squadra_avversaria(d):
    a = d["avversario"]
    logo = a.get("logo")
    if logo:
        logo = (ROOT / logo).resolve().as_uri()
    s = a.get("sigla") or sigla(a["nome"])
    return {"nome": a["nome"], "logo": logo, "sigla": s,
            "sigla_size": 200 if len(s) <= 2 else 150,
            "sigla_size_small": 170 if len(s) <= 2 else 125}


def ordina(noi, loro, casa):
    """La squadra di casa sta sempre a sinistra."""
    return [noi, loro] if casa else [loro, noi]


def ctx_pre(d):
    g = date.fromisoformat(d["data"])
    noi = {"nome": NOME_NOI, "logo": LOGO}
    return {
        "competizione": d.get("competizione", ""),
        "squadre": ordina(noi, squadra_avversaria(d), d.get("casa", True)),
        "giorno": f"{GIORNI[g.weekday()]} {g.day} {MESI[g.month - 1]}",
        "ora": d["ora"],
        "campo": d.get("campo") or CAMPO,
    }


def ctx_convocati(d):
    rosa = {p["nome"]: p for p in json.loads((ROOT / "rosa.json").read_text())}
    portieri = [{"nome": n, "numero": rosa.get(n, {}).get("numero"), "portiere": True}
                for n in d.get("portieri", [])]
    altri = []
    jolly_libero = True
    for n in d["convocati"]:
        if n in rosa:
            num = rosa[n]["numero"]
        elif jolly_libero:
            num, jolly_libero = 6, False  # maglia jolly per chi non è in rosa
            print(f"  '{n}' non è in rosa.json: gli assegno la 6 (jolly)")
        else:
            num = None
            print(f"  attenzione: '{n}' non è in rosa.json e la 6 è già presa")
        altri.append({"nome": n, "numero": num, "portiere": False})
    # numerati in ordine crescente, senza numero in fondo
    altri.sort(key=lambda p: (p["numero"] is None, p["numero"] or 0))
    giocatori = portieri + altri

    # maglie: 3 per riga fino a 12 giocatori, poi 4
    per_riga = 3 if len(giocatori) <= 12 else 4
    righe = -(-len(giocatori) // per_riga)
    w = 300 if per_riga == 3 else 230
    h = min(int(w * 0.9), (1110 - 60 * (righe - 1)) // righe)
    w = min(w, int(h / 0.9))
    for g in giocatori:
        # sulla maglia va il cognome, come sulle vostre (L.AURITANO)
        cognome = g["nome"].replace(". ", ".")
        g["cognome"] = cognome
        larghezza_utile = w * 0.56
        g["nm_size"] = int(min(h * 0.15, larghezza_utile / (0.42 * max(len(cognome), 4))))
    g = date.fromisoformat(d["data"])
    return {
        "logo": LOGO,
        "avversario": d["avversario"]["nome"],
        "giorno_breve": GIORNI[g.weekday()].lower(),
        "ora": d["ora"],
        "giocatori": giocatori,
        "w": w, "h": h, "gap": 60 if righe <= 3 else 40,
        "allenatore": d.get("allenatore"),
    }


def marcatori(lista):
    """Raggruppa i gol per giocatore, nell'ordine in cui compaiono: ["L. Auritano", "Rombolà", "L. Auritano"] -> L. Auritano x2, Rombolà x1."""
    conta = {}
    for m in lista:
        nome = m["nome"] if isinstance(m, dict) else m
        conta[nome] = conta.get(nome, 0) + 1
    return [{"nome": n, "gol": g} for n, g in conta.items()]


def ctx_risultato(d):
    r = d["risultato"]
    noi = {"chi": "noi", "nome": NOME_NOI, "logo": LOGO, "gol": r["noi"],
           "marcatori": marcatori(r.get("marcatori", []))}
    # per gli avversari niente marcatori
    loro = squadra_avversaria(d) | {"chi": "loro", "gol": r["loro"], "marcatori": []}
    return {
        "competizione": d.get("competizione", ""),
        "squadre": ordina(noi, loro, d.get("casa", True)),
        "vittoria": r["noi"] > r["loro"],
        "mvp": r.get("mvp"),
        "frase": r.get("frase"),
    }


# ---------- post feed ----------

def voto_fmt(v):
    """6.5 -> 6 + ½, 7 -> 7, "s.v." -> testo libero."""
    if isinstance(v, str):
        try:
            v = float(v.replace(",", "."))
        except ValueError:
            return {"intero": v, "fraz": None, "testo": True}
    intero, resto = int(v), v - int(v)
    fraz = {0.25: "+", 0.5: "½", 0.75: "-"}.get(round(resto, 2))
    if fraz == "-":  # 6.75 si scrive 7-
        intero += 1
    return {"intero": str(intero), "fraz": fraz, "testo": False}


def ctx_post(d):
    return ctx_risultato(d)


def ctx_pagelle(d):
    """Restituisce una lista di (template, contesto): copertina + una slide a giocatore."""
    rosa = {p["nome"]: p for p in json.loads((ROOT / "rosa.json").read_text())}
    pag = d["pagelle"]
    r = d["risultato"]
    ris = ctx_risultato(d)
    squadre = ris["squadre"]
    punteggio = f"{squadre[0]['gol']}-{squadre[1]['gol']}"
    mvp = pag.get("mvp", r.get("mvp"))
    giocatori = pag["giocatori"]
    tot = len(giocatori) + 1

    w, h = 400, 360
    slides, righe = [], []
    for i, g in enumerate(giocatori, start=1):
        nome = g["nome"]
        info = rosa.get(nome)
        vf = voto_fmt(g["voto"])
        if vf["testo"]:
            size = min(150, int(560 / max(len(vf["intero"]), 1)))
        else:
            size = 220 if len(vf["intero"]) == 1 else 170
            if vf["fraz"]:
                size -= 30
        cognome = nome.replace(". ", ".")
        comm = g.get("commento", "")
        materie = []
        for mn, mv in (g.get("materie") or {}).items():
            mf = voto_fmt(mv)
            num = 0 if mf["testo"] else float(mv) if not isinstance(mv, str) else float(mv.replace(",", "."))
            materie.append({"nome": mn, "voto": num, "pieni": round(num),
                            "testo": mf["intero"] + ("½" if mf["fraz"] == "½" else "")})
        foto = g.get("foto")
        if foto:
            foto = (ROOT / foto).resolve().as_uri()
        portiere = bool(info and info.get("portiere"))
        is_mvp = nome == mvp
        p = {
            "nome": nome, "cognome": cognome,
            "numero": info["numero"] if info else None,
            "portiere": portiere,
            "ruolo": g.get("ruolo") or ("Portiere" if portiere else ""),
            "sigla": sigla(nome), "foto": foto,
            "voto": vf | {"size": size},
            "titolo": g.get("titolo"), "commento": comm,
            "materie": materie[:3],
            "mvp": is_mvp,
            "timbro": g.get("timbro") or ("MVP" if is_mvp else None),
            "nm_size": int(min(h * 0.15, w * 0.56 / (0.42 * max(len(cognome), 4)))),
            "nome_size": min(110, int(560 / (0.46 * max(len(nome), 5)))),
            "comm_size": (48 if len(comm) <= 90 else 42 if len(comm) <= 140 else 38) if materie
                         else (64 if len(comm) <= 90 else 56 if len(comm) <= 140 else 48),
        }
        slides.append(("pagelle_giocatore.html", {
            "p": p, "w": w, "h": h, "logo": LOGO, "avversario": d["avversario"]["nome"],
            "punteggio": punteggio, "idx": i, "tot": tot}))
        righe.append({"nome": nome, "numero": p["numero"], "voto": vf, "mvp": is_mvp})

    squadra = pag.get("squadra")
    if squadra:
        squadra = {"voto": voto_fmt(squadra["voto"]), "commento": squadra.get("commento", "")}
    cols = 1 if len(righe) <= 8 else 2
    per_col = -(-len(righe) // cols)
    row_font = 62 if cols == 1 else 44
    cover = ("pagelle_cover.html", {
        "logo": LOGO, "squadre": squadre, "competizione": ris["competizione"],
        "squadra": squadra, "righe": righe, "cols": cols, "per_col": max(per_col, 5),
        "row_font": row_font})
    return [cover] + slides


# nome: (template, funzione contesto, altezza, multipagina)
TEMPLATES = {
    "pre": ("prepartita.html", ctx_pre, 1920, False),
    "convocati": ("convocati.html", ctx_convocati, 1920, False),
    "risultato": ("risultato.html", ctx_risultato, 1920, False),
    "post": ("post_risultato.html", ctx_post, 1350, False),
    "pagelle": (None, ctx_pagelle, 1350, True),
}
STORIE = ["pre", "convocati", "risultato"]


def main():
    data_path = Path(sys.argv[1])
    quali = sys.argv[2:] or STORIE
    d = json.loads(data_path.read_text())
    env = Environment(loader=FileSystemLoader(TPL), autoescape=True)
    OUT.mkdir(exist_ok=True)
    tag = f"{d['data']}_{sigla(d['avversario']['nome']).lower()}"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for q in quali:
            file, ctx_fn, altezza, multi = TEMPLATES[q]
            page = browser.new_page(viewport={"width": 1080, "height": altezza})
            pagine = ctx_fn(d) if multi else [(file, ctx_fn(d))]
            for n, (f, ctx) in enumerate(pagine, start=1):
                html = env.get_template(f).render(**ctx)
                tmp = TPL / f"_render_{q}.html"
                tmp.write_text(html, encoding="utf-8")
                page.goto(tmp.resolve().as_uri())
                page.evaluate("document.fonts.ready")
                suffix = f"{q}_{n:02d}" if multi else q
                out = OUT / f"{tag}_{suffix}.png"
                page.screenshot(path=str(out))
                tmp.unlink()
                print(f"  {out}")
            page.close()
        browser.close()


if __name__ == "__main__":
    main()
