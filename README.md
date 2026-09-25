# 🏀 Calendario Virtus Bologna (LBA + EuroLeague)

Calendario da iscrivere su Apple Calendar (e Google/Outlook) con tutte le partite della Virtus Bologna, preso dai dati ufficiali di **legabasket.it** ed **euroleaguebasketball.net** e aggiornato automaticamente una volta al giorno (alle 7:17 ora italiana, 6:17 con l'ora solare).

Cosa fa:
- tutte le partite di campionato LBA, playoff, Coppa Italia e Supercoppa, più EuroLeague (regular season, play-in, playoff, Final Four);
- titoli nel formato `🇮🇹 Virtus vs. Armani Olimpia Milano` (in casa) o `🇪🇺 Virtus @ Real Madrid` (in trasferta): 🇮🇹 Serie A, 🇪🇺 EuroLeague, 🏆 Coppa Italia e Supercoppa;
- le partite senza orario ufficiale appaiono come evento “tutto il giorno” (con *orario da definire* nella descrizione) e diventano un evento con l'orario giusto appena viene pubblicato;
- nella descrizione, oltre a giornata/turno, i precedenti contro lo stesso avversario:
  - regular season (LBA ed EuroLeague): il risultato dell'andata nella stessa competizione, solo per le partite di ritorno;
  - playoff Serie A e playoff EuroLeague: le gare già giocate della serie, da gara 2 in poi;
  - play-in e Final Four di EuroLeague, Coppa Italia e Supercoppa: nulla.

Vengono generati tre calendari nella cartella `docs/`: `virtus.ics` (tutto), `virtus-lba.ics` e `virtus-euroleague.ics` (così puoi dare colori diversi alle due competizioni).

## Messa in funzione (una volta sola)

1. **Crea un repository pubblico** su GitHub (es. `virtus-calendar`) e carica questi file mantenendo la struttura delle cartelle, compresa `.github/workflows/`.
2. **Attiva GitHub Pages**: *Settings → Pages → Build and deployment → Source: Deploy from a branch*, branch `main`, cartella `/docs`, *Save*.
3. **Lancia il primo aggiornamento**: tab *Actions* → *Aggiorna calendario Virtus* → *Run workflow*. Dopo circa un minuto nella cartella `docs/` compaiono i file `.ics`.
4. Il calendario sarà a questo indirizzo (sostituisci `TUO-UTENTE`):
   `https://TUO-UTENTE.github.io/virtus-calendar/virtus.ics`
   e la pagina per iscriversi a `https://TUO-UTENTE.github.io/virtus-calendar/`.

## Iscriversi da Apple Calendar

- **iPhone**: apri la pagina `https://TUO-UTENTE.github.io/virtus-calendar/` in Safari e tocca il calendario che vuoi, oppure *Impostazioni → App → Calendario → Account → Aggiungi account → Altro → Aggiungi calendario sottoscritto* e incolla l'URL.
- **Mac**: app Calendario → *Archivio → Nuovo abbonamento calendario…* → incolla l'URL. Come *Posizione* scegli **iCloud** così lo vedi anche su iPhone e iPad, e imposta *Aggiornamento automatico* su “Ogni giorno”.
- Gli avvisi (es. 1 ora prima della partita) si impostano in Calendario → Impostazioni → Avvisi, perché i calendari in abbonamento non li portano con sé.

## Provarlo sul tuo computer

```bash
python3 virtus_calendar.py --out docs
```

Serve solo Python 3.11 o più recente, nessuna libreria da installare.

## Se qualcosa smette di funzionare

- **Il workflow fallisce**: apri il run fallito in *Actions* e guarda il log. Se una fonte non risponde, lo script si ferma senza toccare i file, quindi il calendario resta quello dell'ultimo aggiornamento riuscito.
- **Aggiornamenti fermi d'estate**: GitHub sospende i workflow programmati dopo 60 giorni senza attività nel repository. Se succede, in *Actions* compare un pulsante per riattivarlo.
- **Cambia la stagione EuroLeague**: il codice (es. `E2026`) viene calcolato da solo in base alla data; dal 1° luglio passa alla stagione successiva.
- **Cambia il sito della LBA**: lo script usa l'API interna del sito (`/api/championships/...`). Se la Lega la modifica, va aggiornata la funzione `fetch_lba_games`.

Progetto amatoriale, non affiliato a Virtus Pallacanestro Bologna, LBA o EuroLeague.
