# Stato del progetto â€” 2026-11-19



## Fase corrente



Modello a 4 clip, copertina personalizzabile e preset grafico implementati; test tecnico completo da 60 s eseguito con clip ripetute. Resta l'accettazione con sei giochi reali. Il render ASCII Nier da 5,02 min Ã¨ completato e verificato.



## Verificato



- Ambiente Windows 11, Ryzen 5 5600X, 32 GB, RTX 3060 Ti 8 GB.

- FFmpeg 9.0.2 con NVENC, libx264, AAC.

- Blender 5.3 installato e funzionante in background; Blender 3.0.1 portable scaricato in `G:\VDGP\_tools\blender-3.0.1\blender-3.0.1-windows-x64\blender.exe`.

- Progetto ASCII BlueFox: `GN_ASCII_art.zip` in Downloads; copia di analisi in `G:\VDGP\_discovery\ascii_source\`.

- Il progetto Ã¨ Blender 3.0.1, 16:9, 1920x1080, 24 fps, Eevee, griglia 128x128, alfabeto `" .,:+HXW"`, filmato pilotato da `frame + 5`.

- Sostituzione del filmato con una clip 30 fps: riuscita.

- Render 3.0.1 a 1080p: circa 1-2 s/frame; 60 s a 30 fps stimati in circa 1 h.

- Confronto con il preview ufficiale BlueFox: 3.0.1 fedele; 5.3 cambia luminanza/densitÃ , non usabile per produzione senza migrazione validata.



## Spike 0.5 (placeholder)



- Sorgente sintetica testsrc2 10 s 1920x1080 30 fps + click audio; la registrazione PlaysTV LOTR trovata Ã¨ corrompita.

- 16:9: 150 frame in 102,5 s (0,68 s/frame); MP4 5,00 s 1920x1080 30 fps + AAC.

- 9:16: 150 frame in 93 s (0,62 s/frame); camera verticale con pan keyframed; MP4 5,00 s 1080x1920 30 fps + AAC.

- Resume: kill a 6 frame, rerun con 6 skip e 24 render; 30/30. Controllo PNG corretto (IEND a 12 byte).

- Stima 60 s: ~18-20 min a 16 campioni; ~1 h a 64 campioni (da confermare).

- Output verificati: `ascii_16x9_5s.mp4` (1920x1080, 150 frame, 5,000 s, SHA-256 `EB288E50â€¦B77D5`) e `ascii_9x16_5s.mp4` (1080x1920, 150 frame, 5,000 s, SHA-256 `F0E9392Bâ€¦63B00`).

- Artefatti: `G:\VDGP\_discovery\spike_ascii\`.



## Hash di riferimento



- ZIP originale: `61ADAD597614C66235093637066290A043DC779D96D809D76049329B284A72CA`

- `GN_ascii_art.blend`: `6D0383E761A8F8C21424B5804DD0314E549C05AED9017EEA06FED92FB8540C6B`

- `GN_ascii_art_with_color.blend`: `E0FBA0FCCDCF44294E26C733EF036BCB16517B62839311CB52CFB3AFAABEE996`



## Decisioni



- **Blender 3.0.1 pinnato** per la pipeline ASCII.

- **FFmpeg + Pillow/numpy** per il compositing Guess; Blender solo per ASCII.

- **SQLite + un worker**; niente microservizi, niente cloud obbligatorio.

- **Originali immutabili**; copie di lavoro; hash SHA-256; manifest.

- **Nessuna pubblicazione automatica**; upload iniziale privato e approvazione esplicita.

- **Diritti espliciti**: `cleared` / `pending` / `blocked`; il render/publish Ã¨ bloccato se non `cleared`.

- **Sequenza PNG** per i render ASCII, con resume.

- **Preset JSON**; configurazione senza YAML.

- Struttura modulare vs single-file: **da decidere** (raccomandato modulare).



## Aperte



- Conferma che `GN_ASCII_art.zip` sia il progetto acquistato.

- Licenza/ricevuta BlueFox e uso commerciale/derivati.

- Clip gameplay per il primo test (percorso, durata, fps, audio).

- Font e musica definitivi (o autorizzazione a placeholder OFL/silenzio).

- IdentitÃ  del canale e accesso YouTube (Fase 5).

- Strategia verticale: camera keyframe vs variante nativa 9:16.



## ASCII Nier 5,02 min



- Sorgente effettiva: `G:\ascii\Nier_Automata_-_Emil_True_Final_Boss_Fight_Secret_Boss_Ending_Y.mp4` (301,574 s, 59,94 fps).

- Il datablock â€œElden Ringâ€ nella scena ha percorso mancante e non Ã¨ usato dal nodo Image Texture.

- Griglia ASCII v3 80x45, font Arial Bold, caratteri `" .,:;+*?%S#@&"`, palette per luminanza bluâ†’cianoâ†’verdeâ†’gialloâ†’arancioâ†’bianco, emission 1.0.

- Corretti frame statico, campionamento UV e overesposizione; EEVEE 8 campioni.

- Render v3 completato in ~28 min: `G:\VDGP\ascii\render\nier_ascii_5min.mp4` (526 MB, 1920x1080, 30 fps, 301,200 s, 9036 frame, H.264 + AAC).

- Master v3: `nier_ascii_5min_master.mp4`; preview: `nier_ascii_preview_20s.mp4`; still: `nier_ascii_still_30s.png`, `nier_ascii_still_120s.png`.

- Versioni precedenti archiviate: `nier_ascii_5min_v1.mp4`, `nier_ascii_5min_v2.mp4`.

- Scena v3: `G:\VDGP\ascii\nier_ascii_5min_palette.blend`; backup in `_discovery`.

- Dettagli: `docs/ASCII_RENDER.md`.

- Analisi pipeline colore e confronti controllati: `docs/ASCII_COLOR_PIPELINE.md`. Test RGB sintetico corretto; la sorgente Nier Ã¨ seppia, quindi l'RGB fedele resta caldo/desaturato. In attesa di decidere sorgente e griglia prima di un nuovo render completo.



## ASCII colore v4 (2026-11-20)



- Riferimento BlueFox verificato: `bird_rainy.mp4`, Bfont Regular, rampa `" .,:+HXW"`, bianco su nero. Il contrasto viene dalla sorgente.

- Pipeline rifatta: media 4 campioni per cella, soglia ombre sulla luminanza originale prima del gamma, punto bianco, S-curve; un solo `Tone` guida carattere e palette; Bfont Regular; rampa `" .,:;+HW@"`; dither deterministico per cella.

- Tre varianti sullo stesso segmento Nier 47â€“52 s, frame 52 s: A soft 80Ã—45, B balanced 80Ã—45 (consigliata), C detail 96Ã—54.

- Video: `ascii/experiments/grade_A_soft_5s.mp4`, `grade_B_balanced_5s.mp4`, `grade_C_detail_5s.mp4` (5,000 s).

- Confronto sorgente + A/B/C: `ascii/experiments/final_compare_4up.png`; stabilitÃ : `final_flicker_grid.png`.

- Preset con controlli esposti: `preset_A_soft.blend`, `preset_B_balanced.blend`, `preset_C_detail.blend`; API `mod.properties.inputs.Socket_0..14`.

- Nessun render completo: si aspetta la scelta della variante.



## ASCII preset v1 (2026-11-20)



- B approvato come base; ottimizzato in modo incrementale: Shadow 0.30â†’0.31, Contrast High 0.82â†’0.85, Local Contrast 0.20â†’0.24, Dither 0.06â†’0.05. Griglia 80Ã—45, gamma 0.82, palette ambra invariati.

- Test esteso 20 s (Nier 48â€“68 s, 600 frame): `ascii/render/ASCII_Cinematic_Balanced_opt_20s.mp4` (17,1 Mbps, 1920Ã—1080, 30 fps, audio).

- Compressi di controllo: `..._web6M.mp4` (6,10 Mbps, SSIM 0.980) e `..._web2M.mp4` (2,16 Mbps, SSIM 0.919).

- StabilitÃ  su tutti i 600 frame: 19,0% di churn medio, 0,71% di churn da quantizzazione, 4,05 reversali/1000 celle, 0 spike non spiegati dalla sorgente, hue max 2,86Â°. Grafico e CSV in `ascii/experiments/stability20/`.

- Preset finale: `ascii/presets/ASCII_Cinematic_Balanced_v1.blend` + `.json`; controlli Socket_0..15, incluso `Source Frame Scale` (source_fps/30).

- Limite noto: le superfici chiare ravvicinate (60 s) e le esplosioni (67 s) restano una parete di `H`/`W`. Correzione proposta: tone mapping per shot con keyframe sugli shot; non implementata.

- Dettagli: `docs/ASCII_PRESET_V1.md`. Nessun render completo: attesa decisione sul limite.



## ASCII tone mapping adattivo (2026-11-20)



- Implementato: analisi tagli + segmenti, p10/p25/p95 per shot, auto Â±0,06, override, keyframe sui Socket_4/5, transizioni 2 frame ai tagli e 10 frame ai cambi morbidi.

- Test 48â€“68 s, 600 frame: `ascii/render/ASCII_Cinematic_Balanced_Adaptive_20s.mp4` (16,8 Mbps, audio).

- Shot: 48â€“52,2 pin 0.31/0.95; 52,2â€“59,1 auto 0.294/0.95; 59,1â€“60,8 override 0.58/0.95; 60,8â€“62 auto 0.318/0.95; 62â€“65 auto 0.286/0.95; 65â€“66,5 override 0.31/0.95; 66,5â€“68 override 0.58/0.96.

- Confronto fair: 52 s e 65,5 s **pixel-identical** a B; 58,5 s diff 2,1; 60 s e 67,5 s diff 28,0 (cambi voluti). Immagini in `ascii/experiments/adaptive/fair_comparison.png`.

- StabilitÃ  600 frame con parametri adattivi: quantizzazione 0,68% media / 3,42% max (un frame al ramp 62,2 s), hue max 2,87Â°, 3 spike a tagli/ramp. Correlazione movimento 0,774 al lag di estrazione allineato.

- Frame rate: mapping esatto 1.998/âˆ’0.998 per 59,94 fps; self-check 30/60/59,94 senza deriva. Keyframe verificati a 1560/1755/1800/1965/2025.

- Limite: 60 s migliora nella separazione 2B/bordo ma l'orbita resta liscia; 67,5 s resta un campo chiaro, anche se meno uniforme. La sorgente non contiene dettaglio sufficiente per una curva globale.

- Scena: `ascii/presets/ASCII_Cinematic_Balanced_Adaptive_TEST_48-68.blend`; tool `ascii/tools/adaptive_tonemap.py`, `apply_adaptive_tonemap.py`; piano `ascii/experiments/adaptive/adaptive_plan_48_68.json`.

- Baseline `ASCII_Cinematic_Balanced_v1.blend` e B originale preservati. Dettagli: `docs/ASCII_ADAPTIVE_TONEMAP.md`. Nessun render completo o GUI.



## ASCII forme e movimento (2026-11-20)



- Test griglia/font: 80Ã—45 con 0.020/0.017/0.015, 96Ã—54 con 0.0166/0.0155, 120Ã—68 con 0.0133/0.0125. **96Ã—54 / 0.0166** Ã¨ il migliore equilibrio; 120Ã—68 troppo fine.

- Confronto A/B/C/D sul frame 60 s: A 80/0.020, B 80/0.017, C 96/0.0166, D C + contorni. C consigliata; D aggiunge `- | / \` ma Ã¨ piÃ¹ rumorosa.

- Edge-aware: mappa contorni esterna 96Ã—54 (R forza, G orientamento, soglia fissa 60â†’110), `Edge Strength` 0.8, alfabeto a 13 simboli. Contorni reali su 2B/bordo; la superficie dell'orbita resta liscia.

- Zoom diagnostico 1.25Ã— a 60 s: il soggetto Ã¨ piÃ¹ leggibile, la parete resta; non applicato.

- Movimento: `render/ASCII_FORMS_C_10s.mp4` (52â€“62 s, 96Ã—54, 300 frame, 30 fps, audio) e `ASCII_FORMS_C_5s.mp4`; D `ASCII_FORMS_D_5s.mp4`. 5 s: C diff 0.0157/corr 0.714; D diff 0.0188/corr 0.713 (+20% churn).

- Scene: `presets/ASCII_Cinematic_Balanced_96x54_TEST.blend` (C), `presets/ASCII_Cinematic_EdgeAware_TEST.blend` (D). Baseline Adaptive preservata.

- Limiti: 60 s orbita liscia; 67,5 s fumo; 96Ã—54 compressione a basso bitrate da verificare. Dettagli: `docs/ASCII_FORMS_MILESTONE.md`. Nessun render completo/GUI.



## ASCII C 96Ã—54 â€” validazione (2026-11-20)



- C approvata come nuova baseline; preset consolidato in `ascii/presets/ASCII_Cinematic_Balanced_v2_96x54.blend` + `.json`, con tone mapping adattivo, palette Amber, 96Ã—54/0.0166. Versioni precedenti preservate.

- **Correzione:** la prima stesura dei test griglia regolava i default dei nodi mentre Grid/Size sono pilotati dai Socket; i file marcati 96Ã—54 erano 80Ã—45. La v2 e i test sono stati rifatti sui Socket reali (96/54/0.0166); dati validi in `docs/ASCII_C_96_VALIDATION.md`.

- Test esteso 48â€“68 s, 600 frame: `ascii/render/ASCII_C_96_20s.mp4` (19,30 Mbps, audio).

- Compressione: `..._8M.mp4` (8,28 Mbps, SSIM 0,983, PSNR 38,8); `..._2.5M.mp4` (2,68 Mbps, SSIM 0,923, PSNR 29,9); `..._720p4M.mp4` (1280Ã—720, 4,18 Mbps, SSIM 0,971, PSNR 36,3).

- 8 Mbps e 720p/4 Mbps superano la lettura a dimensione normale; 2,5 Mbps Ã¨ stress. Master conservato.

- Reframe 1.25Ã— opzionale su 58â€“63 s (C 96): `ascii/experiments/reframe/`, `ascii/render/ASCII_FORMS_C_reframe_5s.mp4`; 2B piÃ¹ grande, parete invariata; preset C non modificato.

- Forme/movimento: 5 s C 96 diff 0,01529, correlazione 0,719; D edge 96 resta statico e sperimentale.

- Report: `docs/ASCII_C_96_VALIDATION.md`. Preset base da considerare concluso dopo l'approvazione; prossimo passo automazione GCF. Nessun render 5 min/GUI.



## Capture OBS (Test A)



- OBS 32.2.2 **portable** in `G:\VDGP\tools\obs-portable`, profilo e raccolta `GCF`, WebSocket su porta 4456.

- Configurazione OBS personale non usata; hash di `Senza titolo.json`, `basic.ini` e `global.ini` invariati.

- Tool: `gcf capture doctor|setup|windows|preview|record|takes|select|close`.

- Auto-size: legge `sourceWidth/sourceHeight`, imposta il canvas e applica `alignment=5`, `position=0,0`, `scale=1`.

- Il problema 960x540 era la trasformazione OBS (alignment 0), non il DPI. Risolto.

- Game Capture reale verificato con **Balatro**: 1920x1080, take 19,867 s, 1080x1920 60 fps senza audio, MKV full-frame conservato.

- Test: `python -m unittest discover -s tests -v` (23 OK).



## Round Guess a 4 clip



- Modello: **6 giochi Ã— 4 clip** (Indizio 1, Indizio 2, Indizio 3, Risultato) = 24 clip.

- `gcf/guess/round.py`: quattro segmenti, numero sugli indizi, titolo solo sul risultato, trim senza speed-ramp, beatmap.

- Preset: 2 + 2 + 2 + 3 = 9 s per gioco; copertina 2 s + outro 4 s = 60 s.

- Indizi: parte centrale della clip; risultato: coda della clip.

- Numero ridotto (font 116, circa -39%) in alto a sinistra (`x=72`, `y=300`), bianco con contorno nero, senza sfondo.

- Titolo del gioco in ciano solo nella quarta clip.

- Etichette Indizio/Risultato solo nella GUI, mai nel video esportato.

- Test su un gioco: `projects/round4_test/rounds/test1/round_01.mp4`.

- 1080x1920, 30 fps, 9,000 s, 270 frame, AAC 48 kHz stereo.

- Eventi: numero a 0,0 s, fine numero a 5,95 s, reveal a 6,0 s.

- Evidenze: `_discovery/round4_*.png`, `_discovery/round4_test_9s.mp4`.

- Rigenerazione singolo round: `python -m gcf guess round --project <id> --game <titolo>` oppure â€œAnteprima roundâ€ nella GUI.

- Clip troppo corta: blocco verificato con messaggio â€œIndizio 2 di Balatro: Clip troppo corta: 1.50s, servono almeno 2.00s.â€

- Il vecchio round a take singolo resta in `docs/ROUND_01.md` come riferimento storico.



## Copertina e preset grafico



- `assets/presets/guess_default.json`: font, numero, titolo, testo copertina, colori, dimensioni, posizione, fade/slide, frasi in ciano.

- Dialogo **Grafica** nella GUI: selettore font (assets/Windows/Sfoglia), dimensioni e posizioni di numero/titolo, colori e contorni, parametri copertina e anteprima live.

- Salvataggio per progetto in `projects/<id>/graphics.json`; â€œRipristina presetâ€ torna al default.

- `gcf/guess/cover.py`: copertina animata da clip, immagine o sfondo generato; testo personalizzato; preview e still.

- Clip di sfondo: registrazione singola dal monitor, stesso overlay/crop/MKV full-frame, salvata in `cover_clip` e in `takes/_cover/`.

- Prestazioni: OBS pre-avviato, setup ~0,7â€“0,9 s, stop ~1,5â€“1,8 s, NVENC con fallback libx264, cache di round/copertina. Short completo: ~22,7 s al primo render, ~6 s con round/copertina invariati (prima ~45 s).

- Pulsante â€œRegistra sfondoâ€ nella pagina di registrazione; dopo lo stop lo sfondo passa a `{"type": "cover"}`.

- Testo e sfondo salvati nel progetto (`challenge_title`, `challenge_category`, `cover_background`, `cover_duration`, `cover_clip`).

- Copertina modificabile dal Nuovo Short e dal pulsante â€œCopertinaâ€ nella pagina di registrazione.

- Sfondo automatico = prima clip disponibile; alternative: una delle 24 clip o un'immagine.

- La copertina occupa i primi 2 s e l'outro si accorcia per mantenere il totale a 60 s.

- Evidenze: `_discovery/graphics_cover_015.png`, `graphics_cover_100.png`, `_discovery/gui_new_cover.png`, `gui_cover_dialog.png`, `gui_graphics_dialog.png`.

- Prova su clip reali Witcher 3 (progetto operatore, sola lettura): `_discovery/witcher_cover/cover.mp4`, `_discovery/witcher_round/round_01.mp4`, `witcher_round_f1.0.png`, `witcher_round_f7.0.png`.

- Dettagli: `docs/GRAPHICS.md`.



## GUI desktop (Step 1/2/3/4)



- PySide6, avvio da `C:\Users\Riccardo\Desktop\Gaming Content Factory.lnk` / `GamingContentFactory.vbs`, senza terminale.

- Nuovo Short con sei titoli, sezione Copertina (titolo, categoria, sfondo, durata, anteprima) e progetto JSON.

- Quattro slot per gioco; copertina modificabile dopo la creazione senza toccare le registrazioni.

- Avanzamento â€œGioco X di 6 â€” Clip Y di 4â€; schede clip con anteprima e stato; â€œClip successivaâ€ e, dopo la quarta, â€œGioco successivoâ€.

- Ogni slot salva take, crop, sorgente e monitor; si puÃ² tornare indietro, sostituire una clip e riprendere un progetto salvato.

- Overlay 9:16 topmost, trascinabile/ridimensionabile, click-through quando bloccato; cornice riposizionata sul crop salvato quando si riapre una clip.

- Cattura predefinita **monitor**: selezione â€œSchermo 1/2â€ con risoluzione; la registrazione resta sul monitor scelto anche cambiando finestra.

- Overlay e pannello esclusi dalla cattura con `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)`; verificato sia con OBS Display Capture sia con FFmpeg `gdigrab`.

- Monitor 2: OBS non distingue i due schermi (stesso `monitor_id`); fallback FFmpeg `gdigrab` a 1920x1080 verificato.

- Cursore escluso: `capture_cursor=False` in OBS e `-draw_mouse 0` in FFmpeg, verificato sui frame registrati.

- Avviso se la finestra attiva Ã¨ su un altro monitor; la sorgente non cambia mai da sola.

- OBS portable in background; take verticale 1080x1920 60 fps senza audio; MKV full-frame.

- Evidenze: `_discovery/gui_four_slots.png`, `slot_capture_*.png`, `monitor1_verify.png`, `monitor2_ffmpeg_verify.png`, `docs/GUI.md`.



## Short 60 s



- `gcf/guess/short.py`: 24 clip â†’ copertina 2 s + sei round da 9 s + outro 4 s = 60,000 s.

- 1080x1920, 30 fps, 1800 frame, AAC 48 kHz stereo; numeri, titoli e reveal sui beat.

- Errore `InsufficientMaterial` con elenco delle clip mancanti; `ClipTooShort` indica slot e gioco.

- â€œGenera Shortâ€ blocca la generazione finchÃ© mancano clip obbligatorie.

- Test tecnico completo: `projects/graphics_test/output/short.mp4`, 60,000 s, 1800 frame, con copertina personalizzata e 24 clip pulite ripetute.

- Copia: `_discovery/graphics_test_60s.mp4`.

- Il test usa clip ripetute, non sei gameplay reali differenti: l'accettazione finale con sei giochi Ã¨ ancora da fare.

- Il vecchio output demo `projects/short_20261119_175509/output/short.mp4` usa il modello precedente a un take per gioco e non Ã¨ piÃ¹ l'accettazione corrente.



## Prossimo passo



Verificare copertina, numero, reveal e transizione su `_discovery/graphics_test_60s.mp4`. Poi registrare le 24 clip reali dei sei giochi e generare lo Short finale da 60 s. Poi miniatura, metadati, rifinitura GUI, libreria, YouTube, ASCII.



## Artefatti di discovery



- `G:\VDGP\docs\ROUND_01.md` (round legacy a take singolo)

- `G:\VDGP\docs\GUI.md`, `docs\GRAPHICS.md`

- `G:\VDGP\_discovery\round4_clip1.png`, `round4_clip2.png`, `round4_clip3.png`, `round4_reveal.png`

- `G:\VDGP\_discovery\round4_test_9s.mp4`

- `G:\VDGP\_discovery\gui_four_slots.png`, `gui_new_cover.png`, `gui_cover_dialog.png`

- `G:\VDGP\_discovery\graphics_cover_015.png`, `graphics_cover_100.png`, `graphics_cover_195.png`

- `G:\VDGP\_discovery\graphics_transition_210.png`, `graphics_number_300.png`, `graphics_reveal_900.png`, `graphics_outro_565.png`

- `G:\VDGP\_discovery\graphics_test_60s.mp4`

- `G:\VDGP\_discovery\gui_graphics_dialog.png`

- `G:\VDGP\_discovery\witcher_cover\`, `witcher_round\`, `witcher_round_f1.0.png`, `witcher_round_f7.0.png`

- `G:\VDGP\_discovery\slot_capture_take.json`, `slot_capture_verify.png`

- `G:\VDGP\_discovery\cover_capture_take.json`

- `G:\VDGP\projects\round4_test\` (test storico a quattro clip)

- `G:\VDGP\projects\graphics_test\` (test copertina + 60 s, 24 clip ripetute)

- `G:\VDGP\docs\FEASIBILITY.md`

- `G:\VDGP\_discovery\inspect_blend.py`, `inspect_gn.py`

- `G:\VDGP\_discovery\inspect_color_53.json`, `inspect_gn_color_53.json`

- `G:\VDGP\_discovery\renders\` (render 3.0.1/5.3)

- `G:\VDGP\_discovery\ascii_test\` (sorgente 30 fps, copie di lavoro, render)

- `G:\VDGP\_discovery\cover1_f64.png`, `cover2_f64.png` (riferimento preview ufficiale, non per pubblicazione)
## Nuovo Video ASCII - Milestone 2 (2026-11-20)

- Collaudo end-to-end completato: gameplay 1920x1080 60 fps da 63,3 s renderizzato dalla GUI, stop a 242/1900, riapertura app e ripresa fino a 1900/1900.
- Master e YouTube 1920x1080 30 fps, 63,333 s, audio AAC 48 kHz; frame tutti validi e contigui.
- Prestazioni su preset 96x54: 0,183 s/frame (5,47 fps), RAM job ~1,0 GB, VRAM di sistema ~5,0-5,6 GB.
- Formato verticale 1920x1080 -> 1080x1920 verificato con crop centrale prima dell'ASCII.
- Frame rate 23,976/30/59,94/60 verificati con flash+beep: scarto A/V massimo 1 frame.
- Dettagli in `docs/ASCII_MILESTONE2.md`.

## Auto ASCII Correction (2026-11-20)

- Diagnosi shadow crush: con v2 il primo glifo compare a luma ~0,345 (shadow 0,234 + contrast low 0,18); nella coda scura il 96,6% delle celle e sotto soglia e solo il 2,3% e visibile.
- Motore in `gcf/ascii/correction.py`: analisi a 10 Hz, target per shadow/white/gamma/contrast/local, smoothing con mediana+EMA, flash esclusi, tagli rifiniti a 30 fps, qualita e override.
- Video 63,3 s: 1900 frame, 63,333 s; visibilita media 29,4% -> 43,8%; coda scura 0,6% -> 60,4%; max flicker 0,0026; 0 problemi.
- Scene luminose e NieR 48-58 s: nessuna regressione (Balatro pixel-identical; NieR parametri baseline).
- Toggle nella GUI, anteprima prima/dopo e override rinviate alla fase di rifinitura.

## Auto ASCII Correction - rifinitura M4 (2026-11-20)

- Criterio di intervento basato su `dark_detail` (celle scure con variazione locale), non solo sul 28% di celle visibili; aggiunti `saturated`, `edge_visible`, distribuzione a blocchi e flag `resolution_limited`.
- Balatro: carte e UI sotto la cella 96x54; il reframe 2x non recupera i valori. Il piano segnala la limitazione e non applica correzioni.
- Villaggio Witcher: gia leggibile, lasciato identico. Foresta Witcher: recuperata con target medio conservativo (shadow 0,15, white 0,74, gamma 0,87).
- Video 63,3 s: 1900 frame, 63,333 s, max flicker 0,0024, 0 problemi, 1 limitazione (Balatro).
- A/B e clip: `_discovery/milestone4/ab/` e `after/`; dettagli in `docs/ASCII_READABILITY.md`.

## Villaggio 33 s - diagnosi spazio colore (2026-11-21)

- Trovato il bug principale: Image Texture sRGB -> luma lineare nel modifier, mentre l'analisi M4 usava sRGB. Il villaggio passa da 49,2% (sRGB) a 14,7% (lineare) di celle visibili.
- Catena: v2 primo glifo a ~0,345 lineare; solo il cielo lo supera. Edifici e terreno neri.
- B (percentili lineari): 73,2% visibile, mappa indici con castello/case/alberi/terreno; C (locale 0,36): 75,8% ma piu rumore.
- B non e universale: foresta e coda scura peggiorano rispetto a M4/M3; serve selezione dei candidati per scena.
- Test griglia 142x80: piu dettaglio ma il cielo resta una parete di glifi; il limite residuo e rampa/griglia.
- Nessuna modifica a GUI o motore di produzione; confronto in ``_discovery/milestone5/village_ABC.png`` e ``village_ABC_8s.mp4``.

## Prototipo renderer strutturale (2026-11-21)

- Provati Tonal lineare, silhouette multiscala con componenti connesse, glyph matching 8x8 con maschere rasterizzate e combinazione; stessa griglia/font/palette/risoluzione.
- Iniezione esterna degli indici in Geometry Nodes verificata (test strip 0..14).
- Esito visivo: nessuna variante rende castello, tetti e case distinguibili; silhouette troppo densa sul cielo, matching a pattern, combinazione non risolve.
- Causa: una cella 20x20 px + un solo glifo non contengono insieme cielo, bordo e interno; la rampa/font limita la copertura.
- Non promosso; nessun video strutturale 8 s. Serve subcell/two-layer o set di glifi dedicato.
- Dettagli in ``docs/ASCII_STRUCTURAL_PROTOTYPE.md`` e ``_discovery/milestone5/village_struct_compare.png``.

## Colore originale e semplificazione (2026-11-21)

- Stessi indici ASCII su villaggio 33 s: A Amber, B Original RGB, C Adaptive (Original + 15% bianco). B vince: cielo blu, erba verde, pietra calda; A fonde gli oggetti.
- Semplificazione edge-preserving (guided, bilateral) prima del sampling: nessun miglioramento percepibile; non adottata.
- Video B Original 8 s: ``_discovery/milestone5/village_color_original_8s.mp4``; confronto A/B/C: ``village_color_ABC_8s.mp4``; statico: ``village_color_compare.png``.
- La pipeline colore non richiede geometrie nuove: Color Mode 0 e colore della cella; Amber resta per NieR. Castello/tetti ancora astratti.
- Multi-scena: Original RGB vince sul villaggio; su foresta/scuro/NieR/Balatro senza emissione i glifi scuri scompaiono (nero su nero), quindi Amber resta necessario o serve un floor di emissione nel GN.
- Semplificazione guided/bilateral: nessun guadagno percepibile.
- Benchmark griglie: 96x54 0,19 s/frame; 144x81 0,20; 192x108 0,23. La griglia 144x81 e il primo prototipo strutturale; subcell 2x2 (stessa cardinalita della 192) non e dimostrato superiore.
- Decisione in ``docs/ASCII_COLOR_AND_DECISION.md``; nessuna implementazione GUI/preset.

## Adaptive Glyph Emission + 144x81 (2026-11-21)

- Implementati in copia del preset i Socket Emission Floor/Ceiling/Amount; il remap di luminanza preserva hue/sat, limita le alte luci e agisce solo sui glifi con indice > 0.
- Villaggio A/B/C/D: A 96x54 26,8% senza glifo; B 96+emissione diff 0,067/255 (impercettibile); C 144x81 27,7% senza glifo; D 144+emissione diff 0,001/255 (nessun effetto).
- L'emissione non recupera i glifi assenti; la 144x81 aggiunge dettaglio ma non riduce le celle vuote. 144+emissione non promossa.
- Benchmark: 96 0,19 s/frame; 144 0,20; 192 0,23. La griglia non e il collo di bottiglia.
- Serve una correzione tonale locale o due livelli, non altra griglia/emissione. Dettagli in ``docs/ASCII_ADAPTIVE_GLYPH.md``.

## Milestone 6 — Spatial backend e D-Conservative (2026-11-21)

- Spatial D e D-Conservative integrati in `gcf/ascii/` con cache, manifest, modalita Legacy/Spatial e guard sugli indici 0-255.
- NieR 48-58 s: C 144 Spatial senza celle vuote; D-Conservative 31.9% celle vuote, 0 frame neri; A 96 approvato invariato come riferimento.
- Villaggio: Spatial piu denso e leggibile. Scuro: Spatial respinto (quasi nero); M3/M4 Legacy resta la soluzione.
- Auto non implementata: progetto in `docs/ASCII_AUTO_SELECTOR.md`; nessuna GUI modificata.
- Dettagli e metriche: `docs/ASCII_MILESTONE6.md`.

## Milestone 7 — Adaptive Spatial + Auto offline (2026-11-23)

- Aggiunte varianti Spatial adaptive e adaptive-conservative con target per shot, curva anti-flicker e flash esclusi dal piano.
- Prototipo Auto offline in `gcf/ascii/selector.py`: Legacy 96, Spatial adaptive 144, Conservative adaptive 144 su due frame per shot.
- Composito 14 s (NieR, villaggio, foresta/fade, scuro): Auto e manuale coincidono 5/5; nessuna scelta Auto peggiore.
- Stop/ripresa reale a 57/90 frame: ripresa completa, pixel identici al rendering continuo. Cache verificata anche contro mappe corrotte; piani Legacy riusati.
- Auto non collegato alla GUI e non default; M3/M4 Legacy resta la soluzione scura.
- Dettagli: `docs/ASCII_MILESTONE7.md`, `docs/ASCII_AUTO_SELECTOR.md`.

## Milestone 7.1 — Auto validation indipendente (2026-11-23)

- Valutazione su 3 finestre di 3 frame consecutivi, guardie per-frame, no-choice, verticale 9:16, audio e non mutazione.
- Dataset 25 shot eterogenei: 19/25 scelte corrette (76%), 19/24 colori corretti, 6 regressioni visive, 1 scena non recuperabile riconosciuta.
- Fallimenti principali: Balatro/UI, esplosione NieR, montagna, foresta fade. Auto non approvato per la GUI.
- Transizione 3.1 s senza salti artificiali; cache corrotta, stop/ripresa reale e piani Legacy verificati.
- Dettagli: docs/ASCII_MILESTONE7_1.md.

## Milestone 7.2 — Unificazione e metriche percettive (2026-11-25)

- select() unificato su evaluate_shot(); rimosso il vecchio rescore a due still. No-choice e CLI verificati.
- Rappresentazione comune 64x36/36x64, SSIM multiscala, edge, ombre, highlights, densita uniforme, colore glifi e UI.
- Diagnosis sei errori: density dominante; colore Legacy artificialmente 0; indice 8 saturo al 54,3% sull'esplosione.
- Riesame nuovo motore: 2/6 corretti, 4/6 ancora errati. Target 90% non raggiunto; Auto non va in GUI.
- Verticale/analysis 180x320, audio, cache, stop/ripresa e transizione 3.1 s verificati.
- Dettagli: docs/ASCII_MILESTONE7_2.md.

## Milestone 8 — Renderer Quality & Adaptive Reconstruction (2026-11-25)

- Metriche corrette (griglia 96x54 / 144x81, highlight interni, UI a dettaglio, colore cromatico, flicker spaziale).
- Varianti sperimentali range/compress/local/guarded: riducono l'indice 8 di NieR dal 23% al 4-5%; vincono su scuro/foresta, non su villaggio/montagna.
- Ricostruzione decoupled con atlante Bfont: migliore su scuro, foresta, Balatro e alte luci; non uniformemente migliore.
- Scoperto difetto di layout dei glifi nel preset Blender approvato (celle indice 0 con inchiostro, indice 8 al 66%); correzione sperimentale non risolta, non promossa.
- Balatro: 192x108 migliore, 144x81 vicino, 96x54 perde testo; saturazione indici stabile ~11%.
- Confronti anonimi 5 s in _discovery/milestone8/anonymous/; gate non superato, Auto non approvato.
- Dettagli: docs/ASCII_MILESTONE8.md.

## Milestone 8.1 — Glyph Renderer Fix (2026-11-25)

- Libreria glifi indipendente (Collection Info, mesh Bfont centrate, indice 0 vuoto) e grid vertices = celle + 1.
- Gate sintetico superato su 96x54, 144x81, 192x108 e verticali: indice 0, centro, angoli, checker, rampa, rampa riordinata, 9/9 mapping e bande colore.
- Scoperto e documentato il secondo difetto: il preset v2 creava 143x80 celle per mappe 144x81.
- Sequenza PNG + Scene Time crasha col nuovo grafo; validato index movie FFV1 e flag link_index_time.
- A/B/C/D su NieR, villaggio, foresta, scuro, Balatro, bird; D Blender con mappe indice/colore/intensita validato su scuro.
- Round editoriale Balatro 1080x1920, 30 fps, 9 s: tre clip ASCII 2 s + reveal 3 s, titolo/numero/musica Guess.
- Auto e GUI non toccati; preset v2 approvato intatto. Dettagli: docs/ASCII_MILESTONE8_1.md.

## Milestone 8.2 — Unified Renderer & Guess Production (2026-11-25)

- Renderer selezionabile: v2, glyph-library, glyph-library-decoupled; preset v2 intatto.
- Backend FFV1 index/color/intensity: validazione pixel esatta, stop/ripresa, cache e camera ortografica.
- Decoupled: cella finale 13px, normalizzazione per shot condivisa, clipping coerente, costo pattern+tonale.
- Confronto Blender 4 s su sei scene: Adaptive, Highlight, Decoupled.
- Tre round Guess (Balatro, Witcher 3, Nier) e montaggio 27 s 1080x1920 con titolo/musica/cuts.
- Auto e GUI non toccati; nessuna campagna 25 shot. Dettagli: docs/ASCII_MILESTONE8_2.md.
