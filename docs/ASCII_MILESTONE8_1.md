# Milestone 8.1 — Glyph Renderer Fix & Production Readiness

Data: 2026-11-25
Stato: **gate geometrico superato**, preset v2 approvato intatto, Auto e GUI non toccati.
Il renderer corretto è ancora **sperimentale**: non è selezionato da `preset.py` e non
sostituisce la pipeline di produzione.

## 1. Independent glyph library

`ascii/presets/experimental/ASCII_M8_1_GlyphLibrary.blend` è una copia sperimentale del
preset v2 con una libreria indipendente di glifi:

- nove mesh Bfont indipendenti nella collezione nascosta `M8_Glyphs`;
- spazio = mesh vuota, quindi l'indice 0 non istanzia nulla;
- bbox di ogni glifo centrata sull'origine; scala uniforme via `Glyph Size`;
- `Collection Info` con `Separate Children`/`Reset Children` e un solo
  `Instance on Points`;
- UV, colore e indice restano riferiti alla cella originale;
- nessuna tabella di offset della stringa completa.

È stato scoperto un secondo difetto geometrico: il preset v2 passava
`Vertices X/Y = Grid X/Y`, ma il nodo Grid di Blender crea **una faccia in meno** per
asse. Il renderer approvato aveva quindi 143×80 celle per mappe 144×81. Il preset
sperimentale usa `Grid X/Y + 1` vertici, ottenendo esattamente 144×81 celle. Questo
spiega il disallineamento UV di mezza cella e la riga centrale mancante osservata nei
primi test sintetici.

## 2. Gate geometrico e fotometrico

`_discovery/milestone8_1/gate_report.json`, visual sheet
`_discovery/milestone8_1/synth/gate_sheet.png`.

Sorgenti sintetiche, camera ortografica per il gate, stessa risoluzione effettiva per
cella del renderer diagnostico:

- tutte le celle indice 0 nere;
- glifo singolo al centro e ai bordi/angoli;
- frame uniforme per ciascun indice 1–8;
- scacchiera spazio/denso;
- rampa crescente di densità;
- rampa con caratteri riordinati (`"@WH+;:,. "`) e indici aggiornati;
- bande RGB pure e griglie 96×54, 144×81, 192×108 e verticali 54×96, 81×144, 108×192.

Risultato: **tutti i sei grid passano** (indice 0, centro, angoli, checker, rampa),
mappatura uniforme indice/carattere **9/9**, rampa riordinata corretta, bande colore
corrette. Il gate usa una soglia di inchiostro 0.05 lineare per separare il glifo
dall'antialiasing.

Confronto con l'atlante diagnostico alla stessa cella (144×81, cella 10 px):

| Mappa | MAE copertura | correlazione |
|---|---:|---:|
| tutti @ | 0.215 | — (costante) |
| checker | 0.107 | 0.9999 |
| rampa | 0.066 | 0.9913 |

Blender produce glifi più spessi a 10 px; la differenza è dovuta ad antialiasing,
scala del tratto e gestione colore, non a un offset di cella. L'atlante è stato
rigenerato dai **mesh testuali completi** (`tools/make_text_glyph_atlas.py`): il
vecchio atlante derivato da String to Curves tagliava il fondo di `@`.

### Nota sul percorso di animazione

Con il grafo a libreria indipendente, la sequenza PNG collegata a `Scene Time.Frame`
provoca un crash Blender 5.3 durante `frame_set`. La soluzione validata è una **movie
lossless** delle mappe indice (FFV1), che segue il frame della scena senza quel link.
`gcf/ascii/blender_job.py` espone il campo opzionale `link_index_time` (default true),
così il preset approvato non cambia comportamento.

## 3. A/B/C/D

Confronti a piena risoluzione in `_discovery/milestone8_1/ab/`:

- **A** — Blender v2 approvato, mappe adattive;
- **B** — Blender corretto, stesse mappe e parametri;
- **C** — Blender corretto + Adaptive Highlight Compression (`compress`);
- **D** — Blender corretto + Decoupled Reconstruction. Nella tabella delle sei scene
  D è il renderer reference decoupled; l'integrazione Blender con mappe
  indice/colore/intensità separate è validata separatamente su scena scura.

Metriche principali (`structure / edge / highlight / UI / color / coverage`):

| Scena | A | B | C | D |
|---|---|---|---|---|
| NieR | .631/.133/.753/.700/.925/.389 | .641/.139/.759/.700/.926/.399 | .617/.142/.814/.694/.895/.232 | .668/.209/.692/.688/.891/.196 |
| villaggio | .677/.260/.706/.533/.651/.150 | .673/.266/.695/.551/.659/.153 | .605/.183/.694/.481/.654/.091 | .647/.210/.638/.534/.674/.080 |
| foresta | .535/.263/.676/.428/.562/.057 | .569/.337/.704/.461/.590/.060 | .594/.395/.738/.496/.576/.075 | .662/.412/.680/.587/.681/.068 |
| scuro | .451/.519/.599/.591/.159/.003 | .455/.523/.615/.639/.172/.004 | .592/.586/.934/.818/.482/.046 | .712/.646/.916/.794/.827/.053 |
| Balatro | .723/.419/.709/.678/.522/.168 | .712/.422/.699/.677/.532/.170 | .610/.307/.695/.582/.335/.107 | .615/.380/.633/.542/.841/.083 |
| bird/rain | .577/.619/.694/.753/.475/.054 | .581/.627/.699/.726/.456/.056 | .592/.628/.713/.728/.475/.060 | .665/.623/.684/.790/.770/.057 |

Lettura:

- **A→B**: differenza piccola ma coerente su foresta, bird e UI Balatro; nessuna
  regressione severa. La correzione geometrica è dimostrata dal gate sintetico, non
  dal solo punteggio.
- **C**: vince su NieR/scuro (highlight e UI), perde densità su villaggio/Balatro.
- **D**: vince su foresta, scuro e bird per struttura/UI/colore; su Balatro migliora il
  colore ma perde struttura/UI; su villaggio è intermedio.
- **D Blender** (scuro): structure .659, edge .551, highlight .912, UI .798, color .782;
  il reference D dà .712/.646/.916/.794/.827
(_discovery/milestone8_1/dark_D_blender.png). L'integrazione con mappe separate è
  quindi coerente, con perdita dovuta al renderer Blender.

### Decoupled: correzioni M8.1

- normalizzazione **per shot** della tone map, con mediana robusta e protezione flash;
- normalizzazione sorgente dalle frame di analisi, non dal singolo frame;
- copertura calcolata sul glifo alla risoluzione finale, non sull'atlante 64 px;
- colore normalizzato per luminanza, non per canale massimo;
- intensità e glifo scelti insieme: pattern locale per celle texturate, indice tonale
  per celle piatte, intensità risolta da luminanza desiderata e copertura reale;
- la tone map è usata direttamente nella ricostruzione, non solo caricata;
- mappe separate `idx/`, `color/`, `intensity/` scritte da
  `reference.write_decoupled_maps()` e lette dal grafo Blender sperimentale.

## 4. Prototipo editoriale Guess the Game

`_discovery/milestone8_1/editorial/round_01/round_01.mp4`

- 1080×1920, 30 fps, 9.0 s, audio AAC;
- tre clip ASCII da 2 s (Balatro verticale, tre momenti diversi);
- reveal originale da 3 s;
- numero `1.` e titolo `BALATRO` tramite il preset Guess Generator esistente;
- musica placeholder 120 BPM e tagli 2/2/2/3 allineati al beatmap;
- nessuna modifica alla GUI, al Guess Generator di produzione o ai preset approvati.

Frame di controllo: `_discovery/milestone8_1/editorial/round_01/frames_montage.png`.

## 5. Gate e limiti

**Gate geometrico superato; gate Auto non toccato.**

- Il preset sperimentale non è approvato per la produzione e non è selezionato da
  `preset.py`.
- Auto non è stato rieseguito sui 25 shot; nessuna campagna soglie.
- Il gate sintetico usa camera ortografica; la produzione è prospettica e ritaglia
  leggermente le celle più esterne. È una scelta di framing, non un overlap.
- D Blender è validato su una scena scura; A/B/C/D completi usano D reference.
- I video anonimi della M8 precedente usano l'atlante vecchio; questo milestone
  rigenera l'atlante e il renderer, non i vecchi artefatti.

Prossimi passi:

1. promuovere il preset libreria solo dopo approvazione visiva del round editoriale;
2. integrare il percorso movie-index nel renderer di produzione con flag esplicito;
3. validare D Blender su tutte le sei scene e rifinire il costo congiunto;
4. solo dopo, rerun Auto 25 shot + holdout separato.
