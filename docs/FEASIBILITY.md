# Gaming Content Factory — Fase 0: fattibilità e piano

Data: 2026-11-19
Stato: discovery completata, in attesa delle decisioni dell'operatore.

## 1. Ambiente verificato

| Componente | Stato |
|---|---|
| OS | Windows 11 Pro 26200, 64-bit |
| CPU | AMD Ryzen 5 5600X, 6 core / 12 thread |
| RAM | 32 GB |
| GPU | NVIDIA RTX 3060 Ti, 8 GB, driver 621.24 |
| GPU compute | CUDA e OptiX disponibili in Blender 5.3 |
| Encoder | NVENC H.264/HEVC disponibile in FFmpeg |
| Python | 3.13.0 (default, `M:\Nuova cartella (2)\python.exe`) |
| Python alternativi | 3.14, 3.9, 3.8 via `py` |
| Librerie Python | numpy 2.5.4, Pillow 12.3.0, pip 24.2 |
| FFmpeg | 9.0.2 full build (Gyan), con libx264/libx265/NVENC/AAC |
| Blender installati | 5.0, 5.1, 5.3 (eseguibili presenti) |
| Blender 3.0 / 4.2 | cartelle incomplete, senza `blender.exe` |
| Spazio | G: 452 GB liberi, M: 457 GB, C: 36 GB |

Percorsi FFmpeg:
`C:\Users\Riccardo\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin\`

Nota: la directory utente Blender è `G:\dati blender` e contiene molti add-on che producono errori in background. Le automazioni devono usare `--factory-startup` per isolare l'ambiente.

## 2. Progetto ASCII analizzato

File trovato: `C:\Users\Riccardo\Downloads\GN_ASCII_art.zip`
Contenuto:
- `GN_ascii_art.blend` (865 KB, header `BLENDER-v301`)
- `GN_ascii_art_with_color.blend` (896 KB, header `BLENDER-v301`)
- `bird_rainy.mp4` (640x360, 24 fps, 272 frame, 11,3 s)

Copia di analisi non distruttiva:
`G:\VDGP\_discovery\ascii_source\GN_ASCII_art\`

### Struttura tecnica

- Scena unica, render EEVEE, 1920x1080, 24 fps, frame 1-250, view transform Filmic.
- Un solo oggetto mesh: piano 16:9 (1,7738 x 1,0002), UV 0..1, con modificatore Geometry Nodes.
- Geometry Nodes:
  - `Subdivide Mesh` livello 7 = griglia 128 x 128 = 16.384 celle.
  - `Mesh to Points` -> `Instance on Points` con caratteri generati da `String to Curves` + `Fill Curve`.
  - Alfabeto nel nodo `String`: `" .,:+HXW"` (9 simboli; lo spazio è il nero).
  - `Image Texture` (Geometry Nodes) legge il filmato tramite UV.
  - Luminanza -> `RGB Curves` -> `Map Range` -> indice del carattere.
  - Colore per cella -> attributo -> materiale `Emission` (versione a colori).
  - `Math` con driver `frame` e offset +5: il frame del filmato è `frame scena + 5`.
- Nessuna libreria esterna, nessun text block, nessun audio, nessun font esterno.
- Due varianti: monocromatica e a colori.

### Test eseguiti

1. Apertura e render in Blender 5.3: riusciti; il grafo dei nodi è integro, Filmic è preservato.
2. Confronto con il preview ufficiale BlueFox (video di copertina Gumroad, 1920x1080 24 fps): il render in **Blender 3.0.1** corrisponde all'aspetto originale (scuro, rado, caratteri bianchi sul soggetto). Il render in **Blender 5.3** è molto più chiaro e denso: non è fedele. La differenza è di resa del colore/luminanza, non di geometria.
3. Sostituzione del filmato con una clip 1920x1080 30 fps: riuscita in entrambe le versioni; in 3.0.1 l'aspetto resta quello del progetto.
4. Benchmark GPU, 1920x1080, frame 60:
   - Blender 3.0.1, 16 campioni: 1,88 s/frame (primo frame, include shader compile)
   - Blender 3.0.1, 64 campioni: 1,98 s/frame (primo frame)
   - Blender 5.3, 16 campioni: 1,38 s/frame
   - Blender 5.3, 64 campioni: 4,41 s/frame
   - avvio Blender: circa 1,5 s
5. Stima 3.0.1, 60 s a 30 fps (1800 frame): circa 1 h, più encoding. Il costo è accettabile.
6. Salvataggio di una copia di lavoro e riapertura: riuscito; il percorso relativo del filmato resta valido.
7. Confronto PSNR con il preview ufficiale: 3.0.1 ≈ 20,3 dB, 5.3 ≈ 16,5 dB (valori indicativi, il preview è compresso). La differenza visiva conferma la scelta.
8. Reframe verticale in 3.0.1: 1080x1920, `sensor_fit='VERTICAL'`, sensore verticale effettivo 20,25 mm (stessa FOV verticale del 16:9), pan camera x = -0,4 / 0 / +0,4. Nessuna deformazione; personaggi quadrati; 0,3-0,9 s/frame. Il soggetto va seguito con keyframe manuali.

### Vincoli scoperti

- Il progetto è salvato con Blender 3.0.1. **La versione di produzione per questo asset è Blender 3.0.1**: il render 5.3 cambia sensibilmente luminanza e densità dei caratteri. La copia portable è in `G:\VDGP\_tools\blender-3.0.1\blender-3.0.1-windows-x64\blender.exe`.
- La sincronizzazione è 1:1 tra frame di scena e frame del filmato: **gli fps della scena devono coincidere con gli fps della sorgente**. Per sorgenti a 60 fps si può convertire a 30 fps oppure rendering a 60 fps (costo doppio).
- L'offset +5 è un parametro del grafo, non una costante di sistema: va impostato a 0 per partire dal primo frame.
- Il progetto è nativamente 16:9. La versione 9:16 richiede una riprogettazione dell'inquadratura (camera con keyframe), non uno stretch.
- Il pacchetto ZIP non contiene licenza, README o ricevuta. I termini d'uso commerciale vanno recuperati.
- La resa dipende molto dalla luminanza della sorgente: un gameplay scuro produce pochi caratteri. I preset devono esporre contrasto/luminosità e la preview è obbligatoria.

## 3. Valutazione di fattibilità

Complessivamente **fattibile**. I due rischi tecnici principali sono già stati ridotti:

1. **ASCII**: il progetto è semplice e automatizzabile (un solo filmato, un solo modificatore, nessuna dipendenza esterna). La sostituzione della sorgente funziona. Restano da provare la parità 3.0.1/5.3 e il reframe verticale.
2. **Guess**: la produzione di un MP4 verticale esatto è un problema di compositing 2D, risolvibile con Python + Pillow/numpy + FFmpeg. Il rischio non è tecnico ma editoriale: scelta degli indizi, spoiler, qualità del montaggio.

Rischi residui:
- licenza del progetto Blender e dei materiali di gioco;
- **fedeltà del render**: 5.3 non è compatibile visivamente; la pipeline deve pinnare 3.0.1 (o una migrazione futura con correzione colore validata);
- costi di rendering ASCII per gameplay lunghi;
- qualità e stabilità dell'API YouTube (quota, OAuth, monetizzazione non garantita);
- rilevamento privacy (nomi/username/notifiche) non affidabile al 100% in automatico;
- dipendenza da un unico PC e da percorsi locali.

## 4. Architettura proposta

Applicazione Python locale, CLI-first, senza microservizi, senza cloud obbligatorio.

```
CLI (poi UI locale)
        |
        v
Servizi applicativi
  ├── Catalog           SQLite: giochi, asset, diritti, progetti
  ├── Media library     file immutabili + hash SHA-256 + ffprobe
  ├── Guess engine      timeline 60 s, crop/zoom, testi, audio -> FFmpeg
  ├── ASCII engine      wrapper bpy -> Blender -> PNG -> FFmpeg
  ├── Job queue         SQLite + un worker, log, cancel, resume
  ├── Publishing        metadati, thumbnail, YouTube OAuth (gated)
  └── Analytics         YouTube Analytics API (fase 6)
```

Struttura cartelle:

```
G:\VDGP\
  app\                    # package Python (modulare)
    config.py
    db.py
    media\
    guess\
    ascii\
    jobs\
    publish\
    analytics\
    cli.py
  presets\
    guess\*.json
    ascii\*.json
  data\
    catalog.sqlite
    library\              # originali, immutabili
    projects\<id>\
      project.json
      input\
      work\
      output\
      logs\
  tools\
    blender-3.0.1\        # portable, se confermato
  docs\
  tests\
```

Scelte:
- SQLite con WAL, foreign key, schema versionato; niente ORM.
- Un solo worker di rendering (una GPU); coda persistente su SQLite.
- Blender e FFmpeg come sottoprocessi, mai importati nel processo applicativo.
- File originali mai modificati; copie di lavoro versionate; hash e manifest per la riproducibilità.
- Preset JSON; configurazione con `tomllib`/JSON, senza YAML.
- Output ASCII come sequenza PNG + encoding FFmpeg: consente resume, ispezione e recupero dopo crash.
- Guess come compositing Python frame-by-frame verso pipe FFmpeg: controllo esatto di tempi, crop e testi; niente filter graph monolitico.
- Pubblicazione solo dopo approvazione esplicita; upload iniziale privato.

## 5. Pipeline Guess — impostazione MVP

- 30 fps, 1800 frame = 60,000 s esatti.
- Intro 2 s; 6 round da 9 s (270 frame ciascuno); outro 4 s.
- Round: dettaglio estremo (3 s), inquadratura più ampia (2,5 s), countdown 3-2-1 (2 s), reveal (1,5 s).
- Sei giochi distinti, selezione manuale o proposta automatica da approvare.
- Regioni di interesse normalizzate per asset (`detail`, `wide`, `reveal`), con preview.
- Crop 9:16 senza deformazioni; per il reveal, immagine intera con sfondo sfocato oppure crop più ampio.
- Testi e countdown generati come overlay RGBA; font OFL o font fornito dall'operatore.
- Musica autorizzata; senza licenza il render finale è bloccato (il test può usare silenzio).
- Verifica finale con ffprobe: durata, risoluzione, fps, stream audio, frame count.
- Manifest con hash di asset, preset, font, musica e comando FFmpeg.

Punto critico: la scelta degli indizi resta manuale. Il generatore assembla, non giudica. Il rilevamento automatico di titoli/loading screen non è affidabile nella prima versione.

## 6. Pipeline ASCII — impostazione MVP

- Input: MP4 personale; ffprobe; hash; copia immutabile.
- Trim e conforming a un intermedio di lavoro (default 1920x1080, fps = sorgente o 30).
- Audio estratto separatamente e rimuxato a fine rendering.
- Blender:
  - **versione pinnata 3.0.1** (non 5.3: cambia il look);
  - copia del `.blend` originale;
  - sostituzione del datablock movie per `source == 'MOVIE'`, non per nome;
  - `scene.render.fps = fps sorgente`; frame range 1..N;
  - offset del driver a 0;
  - risoluzione e campioni da preset;
  - salvataggio copia di lavoro e rendering su PNG;
  - log strutturati e progresso.
- Preview: pochi frame rappresentativi o 3-5 s a bassa risoluzione.
- Produzione: sequenza PNG, resume automatico dei frame mancanti, encoding finale.
- 16:9: camera originale, 1920x1080.
- 9:16: stessa scena, camera verticale con keyframe manuali di pan/zoom; il soggetto viene seguito, non stirato. In alternativa, in una fase successiva, variante nativa con griglia 9:16.
- Integrità: ffprobe su durata/risoluzione/fps, hash del manifest, originale intatto.

## 6bis. Spike 0.5 — pipeline ASCII su placeholder

Sorgente: clip sintetica `testsrc2` 10 s, 1920x1080, 30 fps, con click audio. La registrazione PlaysTV LOTR trovata su G: è corrompita (`moov atom not found`) e non è stata usata.

- 16:9: 150 frame, Blender 3.0.1, 1080p, 16 campioni → **102,5 s** (0,68 s/frame); MP4 5,00 s, 1920x1080, 30 fps, AAC.
- 9:16: 150 frame, 1080x1920, camera verticale con pan keyframed da -0,2 a +0,2 → **93 s** (0,62 s/frame); MP4 5,00 s, 1080x1920, 30 fps, AAC.
- Resume: processo ucciso dopo 6 frame; il rerun ha saltato 6 frame e reso 24; 30/30 frame. È stato corretto il controllo di validità PNG (tail `IEND` a 12 byte, non 8).
- Stima 60 s a 30 fps: **circa 18–20 min** a 16 campioni; circa 1 h a 64 campioni (stima da frame singolo, da confermare su sequenza).
- Il placeholder sintetico non sostituisce il test su gameplay reale: leggibilità e contrasto vanno valutati sulla clip dell'operatore.

Artefatti: `G:\VDGP\_discovery\spike_ascii\` (frame, MP4, log, montage).

## 7. Milestone

| Fase | Contenuto | Gate di accettazione |
|---|---|---|
| 0 | Discovery, analisi .blend, test sostituzione, benchmark | Report + baseline 3.0.1 + licenza |
| 0.5 | Spike ASCII: confronto 3.0.1/5.3, preview 5 s, reframe verticale | Parità visiva o differenza motivata; originale intatto |
| 0.5b | Spike su placeholder: 16:9 + 9:16 + resume | **fatto**; manca la clip gameplay reale |
| 1 | Core: config, SQLite, media library, import, ffprobe, preset, diritti | 6 giochi importati, dedupe, blocco diritti |
| 2 | Guess MVP: timeline, crop, testi, countdown, musica, MP4 | 60,000 s, 1080x1920, 6 giochi, audio ok |
| 3 | ASCII MVP completo: preview, render, resume, 16:9 + 9:16 | Clip 10 s nei due formati, errori gestiti |
| 4 | Job queue, progetti, metadati, riproducibilità | Due job in coda, cancel/resume, manifest |
| 5 | UI locale + YouTube privato | Upload privato di test, nessuna pubblicazione automatica |
| 6 | Analytics, nuove categorie, tracking, benchmark | Metriche e confronti, nessuna auto-pubblicazione |

## 8. Primo test pratico proposto

Obiettivo: dimostrare che il progetto ASCII originale accetta un gameplay diverso mantenendo l'estetica, e misurare il costo reale.

1. Usare una copia di `GN_ascii_art_with_color.blend`.
2. Conformare una clip gameplay di 10 s a 1920x1080, 30 fps, H.264.
3. Renderizzare in Blender 3.0.1 e 5.3 i frame 1, 30, 60, 90 con la nuova sorgente.
4. Confrontare i due render (SSIM/PSNR) e verificare colore, nitidezza, sincronizzazione.
5. Renderizzare 5 s (150 frame) a 1080p/16 campioni, encodare, rimuxare l'audio.
6. Provare cancel/resume: interrompere a metà, riavviare, verificare i frame mancanti.
7. Rifare gli stessi 5 s in 1080x1920 con camera verticale e 2-3 keyframe manuali; confrontare con un crop ingenuo.
8. Registrare tempi, dimensione output, eventuali differenze.

Criteri di successo:
- originale non modificato (hash invariato);
- output 16:9 e 9:16 riproducibili;
- ASCII riconoscibile e coerente;
- sincronizzazione audio/video corretta;
- resume funzionante;
- tempi misurati, non stimati.

## 9. Informazioni e file necessari

- Conferma che `GN_ASCII_art.zip` sia il progetto BlueFox acquistato.
- Licenza/ricevuta BlueFox e termini di uso commerciale/derivati.
- Clip gameplay personale per il test (percorso, durata, fps, audio sì/no).
- Eventuale musica autorizzata e font di branding (o autorizzazione a usare un font OFL e audio di test).
- Nome/identità del canale, se già deciso (non necessario per il test tecnico).
- Accesso al canale YouTube e progetto Google Cloud solo in fase 5.

## 10. Aperte

- Struttura modulare vs single-file (decisione richiesta).
- Versione Blender di produzione: **3.0.1** per fedeltà; 5.3 solo per altri task o dopo migrazione validata.
- Parità estetica 3.0.1 vs preview ufficiale: buona visivamente; differenza residua dovuta a compressione/antialiasing.
- Strategia verticale: camera keyframe vs variante nativa 9:16.
- Licenza del progetto ASCII.
- Font e musica definitivi.
- Soglia di approvazione umana e checklist diritti/privacy.
