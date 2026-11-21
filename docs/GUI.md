# GUI, cattura e montaggio

Data: 2026-11-19
Stato: modello a 4 clip, copertina personalizzabile e preset grafico implementati. Test tecnico da 60 s completato; accettazione con sei giochi reali ancora da fare.

## Avvio

Doppio clic su:

```
C:\Users\Riccardo\Desktop\Gaming Content Factory.lnk
```

oppure su `G:\VDGP\GamingContentFactory.vbs`.

Il launcher usa `pythonw.exe` e non apre il terminale. Il programma è PySide6.

## Modello del progetto

- Ogni gioco ha quattro slot: **Indizio 1**, **Indizio 2**, **Indizio 3**, **Risultato**.
- Sei giochi × quattro clip = **24 clip**.
- Ogni slot salva `take_id`, crop, sorgente, monitor e stato in `project.json`.
- Il progetto ricorda `current_index` e `current_clip`, quindi si riprende dal punto in cui è stato chiuso.
- I vecchi progetti con una sola registrazione vengono caricati migrando quel take su **Indizio 1**; restano incompleti finché non hanno le altre tre clip.

## Flusso implementato

1. **Nuovo Short**
   - sei campi per i titoli dei giochi;
   - sezione **Copertina** con titolo della challenge, categoria opzionale, sfondo, durata e anteprima;
   - il titolo può essere una categoria predefinita (Scenery, HUD, Menu, Skybox, Title Screen) o un testo libero;
   - lo sfondo può essere automatico o un'immagine scelta ora; dopo la creazione si registra la clip di sfondo dal monitor con “Registra sfondo”;
   - creazione automatica di `projects/<id>/project.json`.

2. **Pagina di registrazione**
   - avanzamento sempre visibile: **“Gioco 2 di 6 — Clip 3 di 4”**;
   - quattro schede clip con anteprima e stato **Pronta / Da registrare / Mancante**;
   - clic su una scheda per selezionare e sostituire una singola clip;
   - “Prendi video” prepara la cattura per la clip selezionata;
   - ogni clip può avere sorgente, monitor e posizione della cornice diversi;
   - sorgente predefinita **Monitor** con elenco “Schermo 1/2” e risoluzione; restano disponibili Finestra e Game Capture;
   - su monitor 2, se OBS non distingue gli schermi, usa il fallback FFmpeg `gdigrab`.

3. **Overlay interattivo**
   - finestra PySide6 trasparente, sempre in primo piano, sopra il gioco;
   - cornice 9:16 con maschera esterna, maniglie e dimensioni visibili;
   - trascinabile e ridimensionabile mantenendo il rapporto 9:16;
   - quando una clip ha già un crop, la cornice viene riposizionata su quel crop;
   - “Blocca” rende la cornice click-through (`WS_EX_TRANSPARENT`);
   - overlay e pannello usano `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` e non entrano nella registrazione;
   - pannello con REC, Stop, Riprova, Clip successiva / Gioco successivo, Precedente, Apri clip, Chiudi.

4. **Registrazione**
   - la cattura monitor registra l'intero schermo selezionato, indipendentemente dalla finestra attiva;
   - il cursore non viene registrato (`capture_cursor=False` in OBS, `-draw_mouse 0` in FFmpeg);
   - un timer avvisa se la finestra attiva è su un altro monitor; la sorgente non cambia mai da sola;
   - Stop salva MKV full-frame, crea `take.mp4` 1080x1920 60 fps senza audio e `take.json` con lo slot;
   - il crop viene calcolato dalla posizione globale della cornice rispetto al monitor e alla dimensione della sorgente.

5. **Dopo lo Stop**
   - anteprima verticale e anteprima della clip selezionata;
   - “Apri clip” per rivedere il take;
   - “Riprova” o REC registra un altro take per lo stesso slot; il take scelto diventa l'ultimo e i precedenti restano archiviati;
   - “Clip successiva” accetta la clip e passa allo slot seguente;
   - dopo la quarta clip compare **“Gioco successivo”**;
   - “Precedente” torna allo slot o al gioco precedente senza cancellare i take.

6. **Copertina e grafica**
   - pulsante **Grafica**: font, dimensioni, posizioni, colori, contorni e frasi in ciano;
   - anteprima live della copertina e salvataggio per progetto in `projects/<id>/graphics.json`;
   - pulsante “Copertina” nella pagina di registrazione;
   - pulsante **“Registra sfondo”**: registra una singola clip dal monitor con la stessa cornice 9:16, lo stesso crop e lo stesso MKV full-frame delle altre clip;
   - la clip di sfondo è salvata in `cover_clip` e diventa automaticamente lo sfondo della copertina;
   - titolo, categoria, sfondo e durata modificabili anche dopo aver registrato le clip;
   - anteprima live e “Anteprima animata” per generare solo la copertina;
   - il testo viene salvato nel progetto e usato automaticamente nei primi secondi dello Short.

7. **Montaggio**
   - “Anteprima round” genera il round del gioco corrente dalle sue quattro clip, senza rifare gli altri giochi;
   - “Genera Short” è attivo solo con tutte le 24 clip e blocca la generazione indicando le clip mancanti;
   - una clip troppo corta blocca il round con un messaggio che indica slot e gioco.

## Composizione

- Copertina: 2 s iniziali, testo animato sincronizzato con l'inizio della musica; lo sfondo è la clip registrata dal monitor (oppure una clip/immagine scelta).
- Indizio 1: 2 s centrali della clip.
- Indizio 2: 2 s centrali della clip.
- Indizio 3: 2 s centrali della clip.
- Risultato: 3 s finali della quarta clip.
- Totale: 2 s copertina + 54 s round + 4 s outro = **60 s**.
- Numero del round: bianco con contorno nero, senza sfondo, in alto a sinistra (`x=72`, `y=300`, font 116 nel preset iniziale). Resta visibile da 0 a 6 s.
- Il nome del gioco compare a 6 s, solo nella quarta clip, in ciano.
- Le etichette Indizio/Risultato restano solo nella GUI; il video esportato non le disegna.
- Le clip lunghe vengono tagliate: gli indizi usano la parte centrale, il risultato la coda. Nessun rallentamento o accelerazione.
- I tagli coincidono con la beatmap: preset 2+2+2+3 su griglia 120 BPM.
- Posizione, dimensione, colori e font di numero, titolo e copertina si modificano dal pulsante **Grafica** (preset per progetto) o dal preset `assets/presets/guess_default.json`; dettagli in `docs/GRAPHICS.md`.
- Durate, beatmap e musica sono configurabili da CLI:
  `python -m gcf guess round --project <id> --game <titolo> --durations 2,2,2,3 --beatmap <json> --music <wav>`
  e allo stesso modo con `guess short`.
- Formato finale: 1080x1920, 30 fps, 1800 frame, H.264 + AAC 48 kHz stereo.

## Prestazioni

Misure sulla macchina di sviluppo (Ryzen 5 5600X, RTX 3060 Ti):

- OBS viene avviato in background all'apertura del progetto: il primo “Prendi video” non aspetta più i ~3 s di avvio.
- Setup sorgente OBS ridotto da ~2,2 s a ~0,7–0,9 s.
- Stop clip ridotto da ~2,5 s a ~1,5–1,8 s (polling file più rapido, niente screenshot OBS, niente doppio probe).
- Codifica con NVENC quando disponibile, altrimenti libx264 `veryfast`.
- Round: da ~4,9 s a ~2,9 s. Copertina: da ~2,5 s a ~1,6 s.
- Short completo: da ~45 s a ~22,7 s al primo render; i render successivi riusano round e copertina invariati e scendono a ~6 s.
- La cache si invalida se cambiano clip, crop, preset grafico, musica, beatmap, titolo o durata della copertina.
- L'anteprima della copertina è ritardata di 120 ms durante la digitazione per non ricalcolare a ogni tasto.

## File principali

```
gcf/gui/app.py        # finestra, slot clip, flusso
gcf/gui/overlay.py    # cornice interattiva + pannello
gcf/gui/capture.py    # sessione OBS/FFmpeg + crop da overlay
gcf/gui/windows.py    # finestre Windows, monitor e client rect
gcf/gui/project.py    # project.json, 4 clip per gioco, copertina
gcf/guess/round.py    # round da 4 clip, overlay, beatmap, trim
gcf/guess/cover.py    # copertina animata, testo, sfondo
gcf/guess/short.py    # montaggio 60 s da 24 clip, round singolo
assets/presets/guess_default.json
GamingContentFactory.vbs
```

## Verifiche effettive

### GUI a quattro slot

- `_discovery/gui_four_slots.png`: progetto `round4_test`, quattro schede con anteprima, “Clip 3 di 4”, avanzamento 4/24, “Anteprima round” attivo e “Genera Short” disattivato.
- Il test automatico `test_four_clips_per_game_and_navigation` verifica 4 slot, completamento del gioco e navigazione avanti/indietro.
- `test_legacy_single_take_migrates_to_clue_1` verifica la compatibilità con i vecchi progetti.

### Cattura per slot

- Registrazione reale nello slot **Indizio 3** con OBS Display Capture.
- `take.json` salvato con `slot: 2`, `slot_key: clue_3`, `slot_label: Indizio 3`.
- Solo lo slot 3 del progetto è stato compilato; gli altri sono rimasti vuoti.
- Evidenze: `_discovery/slot_capture_take.json`, `_discovery/slot_capture_verify.png`.

### Round con quattro clip

- Progetto storico: `projects/round4_test/`.
- Quattro clip distinte ricavate dal take Balatro esistente e marcate a video `INDIZIO 1`, `INDIZIO 2`, `INDIZIO 3`, `RISULTATO`. Le scritte erano marker impressi nelle clip di test, non un overlay del motore.
- Round: `projects/round4_test/rounds/test1/round_01.mp4`.
- Verifica ffprobe: 1080x1920, 30 fps, 9,000 s, 270 frame, H.264 + AAC 48 kHz stereo.
- Frame: `_discovery/round4_clip1.png`, `round4_clip2.png`, `round4_clip3.png`, `round4_reveal.png`.
- Sequenza verificata: indizio 1 con numero “1.”, indizio 2 con numero, indizio 3 con numero, quarto segmento con “BALATRO” e senza numero.
- Eventi: numero a 0,0 s, fine numero a 5,95 s, reveal a 6,0 s.
- Il round è stato rigenerato anche dalla GUI con “Anteprima round” e dalla CLI `guess round`.
- Clip troppo corta verificata: Indizio 2 da 1,50 s → blocco con “Indizio 2 di Balatro: Clip troppo corta: 1.50s, servono almeno 2.00s.”
- Video di riferimento: `_discovery/round4_test_9s.mp4`.

### Copertina e grafica 60 s

Test tecnico con 24 clip **pulite** (senza etichette), sei giochi che riusano le stesse quattro clip per verificare assemblaggio e durata.

- Progetto: `projects/graphics_test/`.
- Copertina: “GUESS THE GAME FROM ITS TITLE SCREEN”, categoria Title Screen, sfondo auto (prima clip), durata 2 s.
- Output: `projects/graphics_test/output/short.mp4`, copia `_discovery/graphics_test_60s.mp4`.
- Verifica ffprobe: 1080x1920, 30 fps, **60,000 s**, 1800 frame, H.264 + AAC 48 kHz stereo.
- Copertina in-frame: `graphics_cover_015.png` (fade/slide iniziale), `graphics_cover_100.png` (testo pieno), `graphics_cover_195.png` (ultimo frame copertina).
- Transizione: `graphics_transition_210.png` mostra il gioco 1 subito dopo la copertina.
- Numero piccolo in alto a sinistra: `graphics_number_300.png`; niente etichette Indizio/Risultato.
- Reveal: `graphics_reveal_800.png` e `graphics_reveal_900.png` con “BALATRO” in ciano e senza numero.
- Outro: `graphics_outro_565.png`; il video termina a 60,000 s.
- Copertina rigenerabile da sola: `guess cover --project graphics_test`; round singolo: `guess round --project graphics_test --game Balatro`.
- Prova GUI: `gui_new_cover.png` (sezione Copertina nel Nuovo Short), `gui_cover_dialog.png` (modifica dopo la creazione, con anteprima).
- Personalizzazione: `gui_graphics_dialog.png` mostra i selettori; `_discovery/font_cover_preview.png` è una copertina resa con Impact. Il salvataggio crea `projects/<id>/graphics.json`; la cache di round/copertina si invalida quando il preset cambia.

### Clip di sfondo

- Registrazione reale con `GuiCaptureSession(cover=True)`: stessa sorgente monitor, stessa cornice, stesso MKV full-frame.
- `take.json`: `game: Copertina`, `slot: null`; la clip è in `takes/_cover/<take_id>/`.
- Il progetto salva `cover_clip` e passa `cover_background` a `{"type": "cover"}`.
- La copertina rigenerata usa `takes/_cover/.../take.mp4` e il suo crop.
- Evidenza: `_discovery/cover_capture_take.json`.

### Prova su clip reali (Witcher 3)

- Usate in sola lettura le quattro clip già registrate nel progetto dell'operatore `short_20261119_210841`; il progetto non è stato modificato.
- Copertina: `_discovery/witcher_cover/cover.mp4` + `cover_preview.png`, titolo “GUESS THE GAME FROM ITS TITLE SCREEN”, sfondo automatico dalla prima clip.
- Round: `_discovery/witcher_round/round_01.mp4`; 1080x1920, 30 fps, 9,000 s, 270 frame.
- Frame: `_discovery/witcher_round_f1.0.png` (numero piccolo in alto a sinistra, nessuna etichetta), `witcher_round_f7.0.png` (titolo “THE WITCHER 3” in ciano).
- Le quattro clip hanno crop diversi, a conferma che ogni slot conserva la propria inquadratura.

### Cattura monitor

- Schermo 1 via OBS Display Capture: `monitor1_verify.png`, nessun overlay e nessun pannello.
- Schermo 2 via FFmpeg `gdigrab` (`-offset_x 1920 -draw_mouse 0`): `monitor2_ffmpeg_full.png`, `monitor2_ffmpeg_verify.png`; il crop resta corretto.
- Esclusione overlay verificata con `WDA_EXCLUDEFROMCAPTURE`: `_discovery/gdigrab_wda.png`.

### Cursore e avviso monitor

- Cursore mosso sopra la sorgente durante la registrazione: non compare nei frame (`cursor_obs_a.png`, `cursor_obs_b.png`).
- Con finestra di prova sul monitor 1 e cattura preparata sul monitor 2 compare “Finestra attiva su un altro monitor...”; sulla stessa coppia l'avviso sparisce. La sorgente non viene mai cambiata automaticamente.

### Test automatici

```
python -m unittest discover -s tests -v
Ran 23 tests ... OK
```

### OBS personale

La configurazione OBS personale non è stata usata. Hash invariati:

- `Senza titolo.json`: `7F3B8F4B...51D96BD`
- `basic.ini`: `FCEC2935...F312769A`
- `global.ini`: `919F432F...BD621FDF`

OBS portable viene avviato in background con `--minimize-to-tray`.

## Limiti attuali

1. Il video da 60 s è stato verificato con clip ripetute (`graphics_test`), non con sei gameplay reali differenti.
2. Le clip del test derivano dal take Balatro esistente, non da quattro nuove registrazioni live. Il flusso di cattura per slot è stato verificato separatamente.
3. La GUI non ha ancora uno storico take selezionabile: registrando di nuovo uno slot, l'ultimo take sostituisce quello scelto; i take precedenti restano su disco.
4. Il punto di ingresso delle clip è automatico (centro per gli indizi, coda per il risultato); non c'è ancora una scelta manuale in/out.
5. Durate e preset sono configurabili da file/CLI, non ancora da una schermata di impostazioni grafiche.
6. Le scorciatoie globali F9/F10 non sono implementate; si usano i pulsanti del pannello.
7. In fullscreen **esclusivo** l'overlay potrebbe non apparire; usare borderless/finestra.
8. La GUI è funzionale ma non è ancora rifinita graficamente.

## Prossimo step

1. Verificare copertina, numero, reveal e transizione su `_discovery/graphics_test_60s.mp4`.
2. Registrare le 24 clip reali dei sei giochi con la GUI.
3. Generare lo Short finale da 60 s e controllare i sei contenuti reali.
4. Miniatura, metadati e rifinitura GUI.
5. Solo dopo: libreria, YouTube, ASCII.
