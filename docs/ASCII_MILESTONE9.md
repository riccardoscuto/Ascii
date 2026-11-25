# Milestone 9 — Guess the Game in ASCII: workflow di produzione

Data: 2026-11-25
Stato: **workflow integrato, cache selettiva e montaggio a 3 round verificati; collaudo
editoriale a 6 giochi ancora bloccato dalle clip disponibili**.

Preset v2 e BlueFox non sono stati modificati. Auto Selector non è stato rieseguito.
La GUI non è stata riscritta: il percorso Guess ASCII è una modalità del workflow
esistente e il convertitore standalone resta uno strumento avanzato.

## 1. Correzioni backend

### Contesto per shot

`gcf/ascii/reference.py` non calcola più la normalizzazione da frame 1 alla durata
totale. `shot_context(project, frame)` usa i tagli del piano e restituisce il contesto
dello shot che contiene il frame.

- Il contesto completo viene salvato in `temp/decoupled/shot_context.json` con la
  chiave delle mappe e del renderer.
- Un contesto calcolato su mappe parziali (anteprima) **non** viene scritto su disco;
  il render completo lo ricalcola sull'intero shot.
- Still, preview, generazione mappe e video di riferimento usano la stessa funzione.
- I test unitari coprono shot 1/2, persistenza e rifiuto del contesto parziale.

### Integrità delle mappe e dei movie

- `spatial.map_content_hash()` calcola lo SHA-1 dei byte di indice e tone, non solo del
  percorso o della dimensione.
- `render._signature()` include l'hash del contenuto delle mappe e lo SHA-1 dei movie
  decoupled, oltre a renderer, versione, preset e parametri.
- I movie decoupled recuperati dalla cache vengono decodificati e confrontati pixel per
  pixel con le PNG prima di essere riusati. Se la validazione fallisce, le mappe e i
  movie vengono rigenerati.
- Il test reale corrompe `color_movie.mkv`, richiama `_ensure_maps()` e verifica che il
  movie venga ricostruito e validato: `_discovery/milestone9/checks/checks.json`.

### Keyframe senza crash

La verifica dei keyframe non usa più `scene.frame_set()`: valuta le F-curve inserite
alla frame richiesta. Questo evita l'access violation di Blender 5.3 con i movie indice
e permette di verificare i keyframe anche su `glyph-library` e
`glyph-library-decoupled`.

I controlli M8.2 restano verdi: indice 30/30 esatto, still deterministici, stop/ripresa
7→30 con frame 16 identico, segmenti identici, firme diverse per i tre renderer.

### Frame rate diversi

`reference.frame_time(project, frame)` usa la timeline di output a 30 fps e non il frame
rate della sorgente. Il test con una sorgente 60 fps (1 s nero + 1 s bianco) verifica
che il frame 20 sia nero e il frame 40 bianco.

### Parametri e palette

`preset.resolve()` non forza più `Palette Mix = 0`. Il parametro `palette` è esposto
nella GUI Guess, nella GUI standalone e nella CLI; `Color Mode` sceglie tra colore
originale e palette, `Palette Mix` tra amber e steel.

Il renderer decoupled applica la stessa scelta nel backend quando genera la mappa
colore. Il test reale misura una differenza media di 12.192/255 tra le mappe amber e
steel e una differenza visibile negli still Blender. Anche luminosità e contrasto sono
applicati alle mappe: gamma 0.82 contro 1.20 produce una differenza media di 0.954/255
nelle mappe di intensità, con identità esatta ai valori predefiniti.

## 2. Modello Guess per gli indizi

`gcf/gui/project.py` aggiunge a ogni `ClipEntry` un blocco `ascii` con:

- renderer (`glyph-library` o `glyph-library-decoupled`);
- modalità (`adaptive`, `highlight`, `decoupled`) e variante spaziale;
- densità, palette/colore, gamma, ombre, contrasto;
- intervallo e durata del segmento;
- percorso della clip ASCII e del progetto ASCII;
- stato (`recorded`, `converted`, `approved`, `dirty`);
- fingerprint dei parametri e firma della cache;
- override.

I primi tre slot sono indizi convertibili; il quarto è il reveal originale e non viene
mai convertito. Le registrazioni originali non vengono sovrascritte: ogni conversione
ha un `AsciiProject` separato sotto `projects/<short>/ascii/<gioco>/clue_N`.

`gcf/guess/ascii_clip.py` è il modulo condiviso da GUI e CLI:

- `import_video()` copia o normalizza una clip importata in un take separato;
- `preview()`, `compare()` e `convert()` usano il backend `AsciiProject`/`render`;
- `convert()` riusa la clip se il fingerprint non cambia;
- `approve()` è esplicito e non viene inferito dal rendering.

## 3. GUI

Nel workflow esistente, il pulsante **Indizio ASCII** apre l'editor del clip corrente.
L'editor permette di:

- vedere/aprire l'originale e importare un video;
- scegliere l'intervallo utile;
- selezionare Adaptive, Highlight Compression o Decoupled;
- regolare densità, luminosità, ombre, contrasto e colore/palette;
- generare un'anteprima o un confronto a tre modalità;
- generare la clip ASCII;
- interrompere e riprendere;
- approvare il risultato.

Gli slot mostrano `Da registrare`, `Da convertire`, `Da rigenerare`, `Da approvare`,
`Approvata`; il reveal mostra `Pronta`. I parametri sono salvati per clip e ripristinati
alla riapertura. Il pulsante **Montaggio 3 round** produce il montaggio dei primi tre
round approvati; **Genera Short** richiede tutti e sei i giochi.

La Home usa `GUESS THE GAME IN ASCII` come percorso principale; il convertitore
standalone è raggiungibile da **Strumento ASCII**.

## 4. Montaggio e cache selettiva

`gcf/guess/short.py` usa il backend esistente `build_round_segments`:

- gli indizi passano le clip ASCII approvate;
- il reveal passa la registrazione originale;
- il fingerprint del round include file, parametri ASCII, stato, preset, musica e
  beatmap;
- se manca una conversione ASCII il round fallisce, senza fallback a v2 o all'originale.

Test reale di rigenerazione selettiva (`_discovery/milestone9/selective_regeneration.json`):

- modifica del secondo indizio di The Witcher 3 (gioco 2);
- solo quella clip ASCII viene rigenerata;
- solo il round 2 viene ricodificato;
- round 1 e 3 restano invariati;
- il montaggio finale viene ricostruito;
- 810 frame, 27.0 s.

## 5. Collaudo end-to-end

### Tre giochi reali

`projects/short_20261125_170256` contiene Balatro, The Witcher 3 e NieR:Automata con
tre indizi ASCII approvati e reveal originali.

- `_discovery/milestone9/build.py` produce le conversioni tramite `ascii_clip` e il
  montaggio tramite `build_short_preview`.
- Output: `projects/short_20261125_170256/output/short_preview.mp4`.
- 1080×1920, 30 fps, **810 frame**, 27.0 s, audio AAC.
- Frame di controllo: `_discovery/milestone9/preview_frames/`.
- Il numero è discreto in alto a sinistra; il titolo compare solo al reveal.
- Balatro, Witcher e NieR non mostrano il nome del gioco negli indizi.

### Sei giochi

Il collaudo editoriale a sei giochi resta **bloccato**: nel repository ci sono solo tre
giochi reali con materiale idoneo. Il fixture `graphics_test` (sei giochi con clip
sintetiche ripetute) viene usato solo come prova strutturale della durata e del numero
di frame, non come accettazione editoriale.

Risultato strutturale (`_discovery/milestone9/fixture6_manifest.json`):

- 6 round da 9 s, intro 2 s, outro 4 s;
- 1080×1920, 30 fps, **1800 frame**, 60.0 s;
- audio AAC, `metadata.json` e `manifest.json` presenti;
- `metadata.json` non contiene i titoli dei giochi;
- nessun frame aggiuntivo alle giunzioni.

Il fixture non viene dichiarato come collaudo editoriale finale.

## 6. Identità editoriale e spoiler

- Copertina configurabile dal progetto, titolo predefinito `GUESS THE GAME IN ASCII`.
- Tre indizi ASCII da 2 s, reveal originale da 3 s, round da 9 s.
- Numero discreto (64 px, in alto a sinistra) durante gli indizi.
- Titolo del gioco solo durante il reveal.
- Musica continua e tagli 2/2/2/3.
- Outro finale.
- `metadata.json` pubblico non elenca i titoli dei giochi; il manifest locale li
  conserva per tracciabilità.
- Nessuna degradazione artificiale degli indizi.

## 7. Limiti

- L'approvazione estetica delle conversioni resta aperta.
- Il collaudo completo a 60 s e 1800 frame è strutturale finché non ci sono sei giochi
  reali e 24 clip idonee.
- Auto Selector non è stato rieseguito e non è un prerequisito.
- La GUI non è stata riscritta; il convertitore standalone resta disponibile.
- I preset approvati v2 e BlueFox non sono stati modificati.

## 8. Comandi utili

```powershell
# convertire/approvare un indizio
python -m gcf.cli guess ascii-convert --project short_... --game 1 --slot 1 `
  --mode adaptive --density 81 --color original --start 1.0 --approve

# confronto delle tre modalità
python -m gcf.cli guess ascii-compare --project short_... --game 1 --slot 1

# montaggio dei primi tre round
python -m gcf.cli guess ascii-rounds --project short_... --games 3

# Short completo (sei giochi approvati)
python -m gcf.cli guess short --project short_...
```
