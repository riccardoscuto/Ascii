# ASCII C 96×54 — validazione e reframe

Data: 2026-11-20
Baseline approvata: **C — 96×54 / 0.0166**
Preset aggiornato: `G:\VDGP\ascii\presets\ASCII_Cinematic_Balanced_v2_96x54.blend`
Manifest: `ASCII_Cinematic_Balanced_v2_96x54.json`

## Correzione importante

La prima stesura dei test griglia regolava i **default dei nodi** Grid/Size, ma quegli input sono pilotati dai **Socket del modificatore**. I file marcati 96×54 erano quindi ancora 80×45/0.020. Ho corretto impostando `Grid X=96`, `Grid Y=54`, `Glyph Size=0.0166` sui Socket reali e rifatto:

- test griglie: `G:\VDGP\ascii\experiments\gridgeom2\`;
- A/B/C/D: `G:\VDGP\ascii\experiments\abcd2\`;
- master 20 s, compressione, reframe e preset v2.

I dati sotto sono quelli corretti. I vecchi file `gridgeom`, `abcd`, `CD_critical`, `ASCII_FORMS_C_10s/5s`, `ASCII_FORMS_D_5s` sono deprecati (80×45).

## Preset v2

- Griglia **96×54**, Glyph Size **0.0166**, Bfont Regular.
- Rampa `" .,:;+HW@"`.
- Palette Amber, gamma 0.82, shadow 0.31, white 0.95, contrasto 0.18–0.85, local 0.24, dither 0.05.
- Tone mapping adattivo conservato; keyframe 48–68 s inclusi nella scena di test. Il backend genera il piano per la sorgente.
- `Source Frame Scale` 1.998 / offset −0.998 per Nier 59,94 fps.
- Versioni precedenti preservate: v1, Adaptive_TEST, 96x54_TEST (ora allineata alla v2), EdgeAware_TEST (96, sperimentale).

## Griglia e font corretti

| Griglia | Size | Esito |
|---|---:|---|
| 80×45 | 0.020 | riferimento; simboli grandi, parete densa |
| 80×45 | 0.017 | più spazio; soggetto meno massiccio |
| 80×45 | 0.015 | troppo sparso |
| 96×54 | 0.0166 | **migliore equilibrio** |
| 96×54 | 0.0155 | più aria, meno inchiostro |
| 120×68 | 0.0133 | troppo fine; rischio texture |
| 120×68 | 0.0125 | troppo fine |

Confronto corretto: `gridgeom2_full.png`, `gridgeom2_crop.png`.

La C reale 96×54 ha molte più celle e più dettaglio della precedente 80; i simboli restano leggibili a 1920 (celle 16 px). 120×68 non aggiunge forme utili e comincia a leggersi come texture.

## A/B/C/D corretti (frame 60 s)

| | Versione | Configurazione |
|---|---|---|
| A | Adaptive | 80×45 / 0.020 |
| B | Smaller glyphs | 80×45 / 0.017 |
| C | Higher resolution | 96×54 / 0.0166 |
| D | Edge-aware | 96×54 / 0.0166 + contorni 0.8 |

Confronto: `G:\VDGP\ascii\experiments\abcd2\ABCD2_full.png`, `ABCD2_crop.png`.

- **C** è la migliore: più celle, 2B e bordo dell'orbita più definiti, nessuna perdita di leggibilità dei glifi.
- **B** aumenta lo spazio ma riduce la massa; **A** resta più grosso.
- **D** aggiunge `- | / \` su 2B e bordi; la parete dell'orbita resta liscia. D resta sperimentale: non è stata rifatta una validazione di movimento 96; il vecchio +20% di churn era su 80 e non è valido per 96.

## Test esteso 48–68 s

- Master: `G:\VDGP\ascii\render\ASCII_C_96_20s.mp4`
- 20,0 s, 600 frame, 1920×1080, 30 fps, **19,30 Mbps**, audio.
- Contiene 52 s, 58,5 s, 60 s, 65,5 s, 67,5 s; non solo scene buone.

## Compressione corretta

| Versione | Bitrate | Dimensione | SSIM All / Y | PSNR avg / min |
|---|---:|---:|---:|---:|
| Master | 19,30 Mbps | 48,2 MB | — | — |
| **8 Mbps** | 8,28 Mbps | 20,7 MB | **0,983 / 0,992** | 38,8 / 33,9 dB |
| 2,5 Mbps (stress) | 2,68 Mbps | 6,7 MB | 0,923 / 0,946 | 29,9 / 23,7 dB |
| **720p / 4 Mbps** | 4,18 Mbps | 10,4 MB | **0,971 / 0,986** | 36,3 / 28,9 dB* |

\* 720p confrontato con un riferimento 720p near-lossless.

File:
- `ASCII_C_96_20s_8M.mp4`
- `ASCII_C_96_20s_2.5M.mp4`
- `ASCII_C_96_20s_720p4M.mp4`

Frame a dimensione normale: `experiments\compression96\compression96_60.png`, `compression96_67.png`, `compression96_all.png`, `compression96_60_crop.png`.

Lettura:
- **8 Mbps**: glifi leggibili a 1080 e nella vista 960; vicino al master; è la versione web consigliata.
- **2,5 Mbps**: bordi morbidi, glifi piccoli che perdono definizione; stress test, non target.
- **720p / 4 Mbps**: leggibile a 1280×720; più morbido del 1080, adatto a chi guarda a risoluzione inferiore. 5–6 Mbps è più sicuro.

## Reframe 1.25× — opzionale

- Sequenza 58–63 s (2B piccolo, parete dell'orbita).
- Crop centrale 1.25× fisso per lo shot; nessun keyframe di zoom, nessun salto.
- Sorgente pre-ritagliata: `experiments\reframe\zoom_src_58_63.mp4`.
- No reframe (8 Mbps): `render\ASCII_FORMS_C_no_reframe_5s_8M.mp4` (C 96, 58–63).
- Reframe (8 Mbps): `render\ASCII_FORMS_C_reframe_5s_8M.mp4` (C 96, 1.25×).
- Versioni high-quality: `ASCII_FORMS_C_no_reframe_5s.mp4`, `ASCII_FORMS_C_reframe_5s.mp4`.
- Confronto: `experiments\reframe\reframe_compare_96.png`.
- Il preset C non è modificato; è preparazione video opzionale per shot.

Risultato: 2B e il bordo dell'orbita sono più grandi e leggibili; la parete chiara resta. Il reframe aiuta la dimensione del soggetto, non inventa dettaglio sulla superficie.

## Forme e movimento

- C 96: 5 s (58–63) diff media **0,01529**, p95 0,02956, max 0,0406; correlazione sorgente **0,719** a lag 0.
- Il movimento di 2B/orbita è più leggibile che a 80; i caratteri restano distinti.
- D edge 96 è solo statico (60 s); non è attivato per default.
- Nessuna stabilizzazione temporale aggiuntiva.

## Giudizio

C 96 passa la compressione a **8 Mbps** e a **720p/4 Mbps**. Il 2,5 Mbps è marginale ma non è il target. Il limite residuo è di contenuto: 60 s (orbita liscia) e 67,5 s (fumo) non hanno abbastanza struttura per una curva globale; il reframe 1,25× migliora la dimensione del soggetto, non la superficie.

Se questa lettura è accettata, il preset base C può considerarsi concluso e si può passare all'automazione GCF.

## File

- Preset: `presets\ASCII_Cinematic_Balanced_v2_96x54.blend`, `.json`
- Scena D 96: `presets\ASCII_Cinematic_EdgeAware_TEST.blend`
- Master: `render\ASCII_C_96_20s.mp4`
- Compressi: `render\ASCII_C_96_20s_8M.mp4`, `..._2.5M.mp4`, `..._720p4M.mp4`
- Griglie corrette: `experiments\gridgeom2\`
- A/B/C/D corretti: `experiments\abcd2\`
- Compressione: `experiments\compression96\`
- Reframe: `experiments\reframe\`, `render\ASCII_FORMS_C_no_reframe_5s.mp4`, `..._reframe_5s.mp4`
- Report forme precedente: `docs\ASCII_FORMS_MILESTONE.md` (vedi nota di correzione)

Nessun render dei 5 minuti, nessuna GUI.
