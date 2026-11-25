# Milestone 8.2 — Unified ASCII Renderer & Guess Production Prototype

Data: 2026-11-25
Stato: **renderer corretto selezionabile e riproducibile; tre round editoriali prodotti**.
Preset v2, BlueFox e GUI non sono stati modificati. Auto non è stato riscritto né
rieseguito sui 25 shot.

## 1. Renderer selezionabile

`gcf/ascii/preset.py` espone tre renderer espliciti:

- `v2` — preset approvato, comportamento invariato;
- `glyph-library` — preset sperimentale con libreria glifi indipendente, griglia
  corretta e camera ortografica;
- `glyph-library-decoupled` — stesso renderer con mappe indice, colore e intensità
  separate.

`AsciiProject.renderer` e il CLI `--renderer` selezionano il percorso.
`preset.blend_for()` e `preset.renderer_version()` sono usati da firma cache, plan
context, chiavi mappe e copia del preset Blender. Cambiare renderer invalida mappe,
cache e piano.

File sperimentali:

- `ascii/presets/experimental/ASCII_M8_2_GlyphLibrary.blend`
- `ascii/presets/experimental/ASCII_M8_2_Decoupled.blend`

La camera è ortografica con `ortho_scale = 1.775625…`, così il piano è inquadrato
esattamente senza perdere le celle esterne.

## 2. FFV1 index movie backend

Il percorso sperimentale non dipende più da script esterni:

- `spatial.encode_index_movie()` produce un FFV1 RGB24 lossless dalla sequenza indice;
- `spatial.validate_index_movie()` decodifica il movie e confronta **ogni pixel** con
  i PNG: valori esatti, nessuna conversione gamma;
- `spatial.encode_png_movie()` / `validate_png_movie()` fanno lo stesso per indice,
  colore e intensità del renderer decoupled;
- `blender_job.py` carica il movie con colorspace `Non-Color`; il movie segue il frame
  della scena senza il link `Scene Time` che provocava il crash Blender 5.3;
- il job verifica i percorsi dei movie e la coerenza delle mappe.

Verifiche (`_discovery/milestone8_2/backend_checks.json`):

- indice 30/30 frame esatto;
- stop/ripresa: 8 frame parziali, poi 30/30; frame 16 pixel-identico al riferimento;
- due render still consecutivi pixel-identici (diff 0.0);
- due segmenti 16–16 identici;
- firme cache diverse per i tre renderer;
- orizzontale e verticale 1080×1920.

## 3. Decoupled consistency

Correzioni in `gcf/ascii/reference.py`:

- `cell_px_for(project)` deriva la cella dalla risoluzione/griglia finale (13 px a
  1080p/144×81), non più il 12 fisso;
- copertura calcolata sui tile alla risoluzione finale;
- clipping cromatico nello stesso ordine tra reference e mappe Blender (chroma
  clippata, poi intensità);
- normalizzazione **per shot persistente** condivisa da still, video e generazione
  mappe (`shot_context`), con protezione flash;
- desired tone-map + source normalizzati dallo stesso contesto;
- scelta del glifo con costo congiunto: correlazione pattern **e** errore tonale
  ottenibile con copertura/intensità reali;
- mappe `idx/`, `color/`, `intensity/` consumate dal preset decoupled.

Il renderer reference non è più considerato equivalente a Blender per costruzione:
le differenze di AA, intensità e color management sono misurate separatamente.

## 4. Confronto sul renderer Blender corretto

Sei scene, clip da 4 s, tutte sul backend Blender corretto:

- Adaptive (`glyph-library` / `adaptive`);
- Adaptive Highlight Compression (`glyph-library` / `compress`);
- Decoupled (`glyph-library-decoupled` / `compress`).

Conservative/`adaptive-conservative`/`guarded` restano selezionabili come varianti
sperimentali, ma non sono nelle clip principali.

Artefatti: `_discovery/milestone8_2/compare/` (clip, still 1920×1080/1080×1920, sheet,
crop 1:1 `crop_<scena>.png`).

| Scena | Adaptive | Highlight | Decoupled |
|---|---|---|---|
| NieR | molto denso, @ bianchi | riduce il clipping, più +/H | più colore/tono, meno clipping |
| villaggio | denso e leggibile | più aperto | colore e dettaglio, un po' più morbido |
| foresta | buona struttura | più edge | colore/ombre migliori |
| scuro | quasi vuoto | recupera dettaglio | recupera dettaglio e colore |
| Balatro | carte/UI più leggibili | più aperto, UI più debole | più colore, UI meno densa |
| bird/rain | bianco, sparse | edge più marcati | colore/UI migliori |

La valutazione è visiva: le clip sono in `compare/<scena>_<modalità>.mp4` e i crop a
piena risoluzione in `compare/crop_<scena>.png`. Non vengono usati score al posto del
giudizio.

## 5. Direzione prodotto

Il prodotto principale è **Guess the Game in ASCII**. Il convertitore è un modulo
riutilizzabile: il backend `AsciiProject` + renderer selezionabile produce le clip che
il Guess Generator concatena con il template esistente.

Il format resta:

- tre indizi ASCII da 2 s;
- reveal originale da 3 s;
- numero e titolo solo durante il reveal;
- musica e tagli sincronizzati;
- verticale 1080×1920, 30 fps.

Controllo spoiler: gli indizi Balatro mostrano carte/UI ma non il titolo; Witcher è un
primo piano di Geralt senza testo identificativo; NieR mostra HUD/dialogo e non il nome
del gioco. Il titolo appare solo nell'overlay del reveal.

## 6. Prototipo multi-game

`_discovery/milestone8_2/rounds/three_rounds.mp4`

- 1080×1920, 30 fps, 27.03 s, audio;
- round 1 Balatro: adattivo, tre indizi + reveal;
- round 2 The Witcher 3: decoupled+compress, primo piano di Geralt;
- round 3 NieR:Automata: highlight compression, HUD/explosione;
- numero `1./2./3.`, titolo solo al reveal, musica 120 BPM e tagli 2/2/2/3;
- montaggio unico senza immagini sorgente o metriche affiancate.

Frame di controllo: `_discovery/milestone8_2/rounds/three_rounds_frames.png`.

## 7. Gate e limiti

- Nessuna modifica a preset v2, BlueFox, GUI o Guess Generator di produzione.
- Nessun render da cinque minuti; nessuna campagna Auto 25 shot.
- Il renderer libreria è sperimentale e non è il default.
- Il gate sintetico usava camera ortografica; il preset M8.2 usa ortografia anche in
  produzione, con bordo pieno.
- Still, segmenti e ripresa sono deterministici nelle verifiche M8.2.
- La scelta delle modalità nei tre round è manuale; Auto non è un prerequisito.
- Gli indizi NieR sono volutamente scuri/sparsi; la modalità highlight è stata scelta
  per non perdere l'esplosione del reveal.

Prossimi passi: valutazione visiva dei tre round e del confronto a sei scene; solo dopo
eventuale promozione del renderer nella GUI e ripresa di Auto.
