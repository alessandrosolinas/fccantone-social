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

## Post feed (1080x1350)

    python render.py partita.json post       # risultato per il feed
    python render.py partita.json pagelle    # carosello pagelle

- Pagelle: copertina con il registro dei voti + una figurina a giocatore
- Dati in "pagelle" (vedi pagelle_esempio.json): voto (6.5 diventa 6½, "s.v." va bene),
  titolo, commento, materie (fino a 3, voto 0-10), timbro opzionale, foto opzionale in assets/
- "squadra": voto e commento collettivo in copertina
- MVP preso da pagelle.mvp o da risultato.mvp: bordo cangiante e timbro
- partite/: JSON delle partite giocate, con i convocati da cui partono le pagelle
