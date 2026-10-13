"""Genera le storie Instagram di F.C. Cantone (1080x1920 PNG).

Uso:
    python render.py partita.json            # tutte e tre
    python render.py partita.json pre        # solo pre-partita
    python render.py partita.json convocati
    python render.py partita.json risultato
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
    }


TEMPLATES = {
    "pre": ("prepartita.html", ctx_pre),
    "convocati": ("convocati.html", ctx_convocati),
    "risultato": ("risultato.html", ctx_risultato),
}


def main():
    data_path = Path(sys.argv[1])
    quali = sys.argv[2:] or list(TEMPLATES)
    d = json.loads(data_path.read_text())
    env = Environment(loader=FileSystemLoader(TPL), autoescape=True)
    OUT.mkdir(exist_ok=True)
    tag = f"{d['data']}_{sigla(d['avversario']['nome']).lower()}"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        for q in quali:
            file, ctx_fn = TEMPLATES[q]
            html = env.get_template(file).render(**ctx_fn(d))
            tmp = TPL / f"_render_{q}.html"
            tmp.write_text(html, encoding="utf-8")
            page.goto(tmp.resolve().as_uri())
            page.evaluate("document.fonts.ready")
            out = OUT / f"{tag}_{q}.png"
            page.screenshot(path=str(out))
            tmp.unlink()
            print(f"  {out}")
        browser.close()


if __name__ == "__main__":
    main()
