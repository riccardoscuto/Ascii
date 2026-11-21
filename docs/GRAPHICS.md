# Preset grafico

Data: 2026-11-19
File predefinito: `assets/presets/guess_default.json`

Il preset controlla font, numero del round, titolo del reveal e testo della copertina. La GUI lo legge a ogni rendering.

Si può modificare dal pulsante **Grafica** nella pagina di registrazione: font, dimensioni, posizioni, colori, contorni, frasi evidenziate e anteprima. Il salvataggio crea `projects/<id>/graphics.json`, quindi ogni progetto può avere il proprio stile; “Ripristina preset” riparte dal default.

Il font è un percorso a un file `.ttf`/`.otf`. Il selettore elenca i font in `assets/fonts` e alcuni font comuni di Windows; “Sfoglia” accetta qualsiasi font installato o file locale.

## Font

```json
"font": "assets/fonts/Montserrat-Variable.ttf"
```

Vale per numero, titolo, copertina e card dell'outro. Un percorso relativo viene risolto rispetto alla root del progetto.

## Numero del round

```json
"number": {
  "font_size": 116,
  "x": 72,
  "y": 300,
  "anchor": "lt",
  "color": [255, 255, 255, 255],
  "outline": [0, 0, 0, 255],
  "stroke": 8
}
```

- `font_size`: dimensione in pixel. Il valore iniziale è circa il 39% in meno rispetto al vecchio 190.
- `x`, `y`: posizione del bordo superiore sinistro, misurata sul frame 1080x1920.
- `anchor`: `lt` = left-top.
- Nessuno sfondo o rettangolo viene disegnato dietro al numero.
- Il numero resta visibile da 0 s fino a poco prima del reveal.

## Titolo del reveal

```json
"title": {
  "font_size": 120,
  "y": 1000,
  "max_width": 940,
  "color": [0, 183, 255, 255],
  "outline": [0, 0, 0, 255],
  "stroke": 7
}
```

Compare solo nella quarta clip, dal momento del reveal.

## Copertina

```json
"cover": {
  "font_size": 104,
  "center_y": 880,
  "max_width": 800,
  "line_gap": 18,
  "color": [255, 255, 255, 255],
  "highlight_color": [0, 183, 255, 255],
  "outline": [0, 0, 0, 255],
  "stroke": 9,
  "highlight_phrases": ["THE GAME"],
  "fade_in": 0.35,
  "slide_px": 28
}
```

- `highlight_phrases`: frasi colorate in ciano. La corrispondenza ignora maiuscole/minuscole e la frase non viene spezzata su due righe quando possibile.
- Le altre parole restano bianche con contorno nero.
- `max_width` controlla l'a capo automatico.
- `center_y` è il centro verticale del blocco di testo.
- `fade_in` e `slide_px` controllano l'animazione iniziale, sincronizzata con l'inizio della musica.
- La copertina non ha sfondi o rettangoli dietro al testo.

## Sfondo della copertina

La clip di sfondo è una **registrazione singola** fatta dallo stesso monitor, con la stessa cornice 9:16 e lo stesso salvataggio full-frame delle altre clip. Non fa parte delle 24 clip dei giochi: è una clip aggiuntiva del progetto.

Si registra dalla pagina di registrazione con il pulsante **“Registra sfondo”**. Dopo lo stop, `project.json` contiene `cover_clip` con take, crop, monitor e stato, e lo sfondo passa automaticamente a `{"type": "cover"}`.

La scelta è salvata in `project.json`:

```json
"cover_background": {"type": "auto"}
"cover_background": {"type": "cover"}
"cover_background": {"type": "clip", "game": "Balatro", "slot": 0}
"cover_background": {"type": "image", "path": "G:\\percorso\\immagine.png"}
```

- `auto`: usa la clip di sfondo registrata; se manca, la prima clip del progetto.
- `cover`: usa la clip di sfondo registrata.
- `clip`: usa una delle 24 clip dei giochi.
- `image`: usa un'immagine scelta.
- Se la clip o l'immagine non sono disponibili, il renderer usa una clip disponibile o uno sfondo grafico generato.

## Testo e durata

Salvati nel progetto:

```json
"challenge_title": "GUESS THE GAME FROM ITS TITLE SCREEN",
"challenge_category": "Title Screen",
"cover_duration": 2.0
```

La copertina occupa i primi `cover_duration` secondi. L'outro si accorcia automaticamente per mantenere il totale a 60 secondi; se non c'è spazio sufficiente, la generazione viene bloccata.

## Rigenerare solo una parte

```powershell
cd G:\VDGP
.\.venv\Scripts\python.exe -m gcf guess cover --project <id> --open
.\.venv\Scripts\python.exe -m gcf guess round --project <id> --game <titolo> --open
.\.venv\Scripts\python.exe -m gcf guess short --project <id>
```

Nella GUI: “Copertina” → “Anteprima animata” per la sola copertina; “Anteprima round” per il gioco corrente.

## Etichette degli slot

Indizio 1/2/3/Risultato restano visibili solo nella GUI. Il motore video non disegna etichette di slot: durante gli indizi c'è solo il numero, durante il risultato solo il nome del gioco. Le vecchie clip di test `round4_test` avevano le etichette impresse nel video di prova; il progetto `graphics_test` usa clip pulite.
