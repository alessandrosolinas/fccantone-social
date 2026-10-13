# Storie Instagram F.C. Cantone

Genera le storie 1080x1920 da un file JSON con i dati della partita.

    pip install jinja2 playwright
    python render.py partita.json             # pre, convocati, risultato
    python render.py partita.json risultato   # solo una

- rosa.json: nomi e numeri (i nomi in "convocati" devono coincidere)
- partita_esempio.json: modello dei dati partita
- assets/: logo; i loghi avversari vanno qui e si indicano in "avversario.logo"
- casa: true/false decide chi sta a sinistra
- campo: se non indicato usa US Villa Cortese, via Pacinotti 19
- Con una vittoria il risultato ha lo sfondo a righe pieno
