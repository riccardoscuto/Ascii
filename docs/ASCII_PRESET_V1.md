# ASCII Cinematic Balanced v1 — milestone

Data: 2026-11-20
Preset: **B — Balanced 80×45**, ottimizzato (OPT)
File finale: `G:\VDGP\ascii\presets\ASCII_Cinematic_Balanced_v1.blend`

> Follow-up: tone mapping per shot e test 48–68 s in `docs/ASCII_ADAPTIVE_TONEMAP.md`.

## Esito in breve

- Il preset B è stato rifinito con quattro modifiche isolate e misurate.
- Test esteso di **20,0 s** (600 frame) su Nier **48–68 s**, con audio.
- Stabilità verificata su **tutti i 600 frame**, non su tre screenshot.
- Due ricodifiche H.264 di controllo: **6 Mbps** e **2 Mbps**.
- Il preset finale è parametrico, con controllo della scala frame per sorgenti a fps diversi.
- **Milestone non completamente chiusa:** le inquadrature ravvicinate molto chiare (es. 60 s) restano un campo denso di `H`/`W`; la scena perde leggibilità. Correzione proposta al fondo.

## Perché 48–68 s

La scansione del video a 2 fps (301 s) mostra che l'intera boss fight è high-key. Il primo test scelto, 116–140 s, era troppo sbilanciato sui primi piani chiari: 9 frame su 13 con oltre il 40% di celle dense. È stato scartato.

La finestra **48–68 s** è più varia:

- 48–50 s: orbite e personaggio su fondo scuro;
- 52 s: frame approvato del preset;
- 54–56 s: esplosione;
- 58 s: dopo-esplosione scuro;
- 60 s: orbita in primo piano (punto debole);
- 62–64 s: combattimento scuro;
- 66–68 s: nuova esplosione.

È un compromesso migliore tra movimento, cambi di luce, primo piano e sfondo. Non elimina il limite delle superfici chiare, ma non lo nasconde.

## Parametri finali

| Parametro | B iniziale | B ottimizzato | Motivo |
|---|---:|---:|---|
| Grid | 80×45 | 80×45 | invariato |
| Glyph Size | 0.020 | 0.020 | invariato |
| Ramp | `" .,:;+HW@"` | `" .,:;+HW@"` | invariato |
| Shadow Threshold | 0.30 | **0.31** | riduce il churn vicino al nero; +0,7 punti di celle vuote a 52 s |
| White Point | 0.95 | 0.95 | invariato |
| Gamma | 0.82 | 0.82 | 0.78 è stato scartato: schiarisce la foschia |
| Contrast Range | 0.18–0.82 | 0.18–**0.85** | distribuisce meglio le alte luci, meno `@` |
| Local Contrast | 0.20 | **0.24** | bordi più netti, separazione soggetto/fondo |
| Dither | 0.06 | **0.05** | meno variazione nelle aree piatte |
| Saturation | 1.5 | 1.5 | invariato |
| Exposure | 1.2 | 1.2 | invariato |
| Color Mode | 1.0 | 1.0 | Cinematic |
| Palette Mix | 0.0 | 0.0 | ambra calda |
| Source Frame Scale | 2.0 | 2.0 | 59,94 fps → 30 fps |

Effetto misurabile sulle alte luci (percentuale di celle `@`):

| Frame | B iniziale | OPT |
|---|---:|---:|
| 47 s | 17,3% | 10,5% |
| 52 s | 2,1% | 1,2% |
| 124 s | 15,7% | 9,7% |
| 136 s | 14,9% | 10,4% |

Le celle `H`/`W` restano, ma diminuiscono le celle completamente sature: le alte luci hanno più gradazione e la compressione trova meno bianco piatto.

## Test scartati

- **Gamma 0.78**: schiarisce la foschia e aumenta la parete di caratteri. Scartato.
- **Emission 1.1**: brucia le alte luci verso il bianco. Scartato.
- **White Point 0.98**: sposta leggermente il top-end ma non risolve le pareti. Non adottato.
- **Contrast High 0.88**: riduce ancora `@` ma scurisce troppo il soggetto. Preferito 0.85.
- **Soppressione delle alte luci piatte**: testata con un mask di dettaglio. Riduce la densità della parete, ma svuota l'orbita approvata a 52 s e non rende comunque riconoscibile la scena larga. Scartata.

## Test esteso

- Sorgente: Nier, **48–68 s** (frame scena 1440–2039).
- 600 frame, 1920×1080, 30 fps, EEVEE 8 campioni.
- Master: `G:\VDGP\ascii\render\ASCII_Cinematic_Balanced_opt_20s.mp4`
- Durata 20,000 s, 17,1 Mbps, H.264 + AAC.
- Il test precedente 116–140 s (24 s) resta in `..._opt_24s.mp4` come storico, non è il deliverable.

Frame rappresentativi: `G:\VDGP\ascii\experiments\compression20\representative_frames_20s.png` (52, 58, 60, 64 s).

Contact sheet dell'intero segmento: `...\test_20s_contact_sheet.png`.
Confronto B iniziale / OPT: `...\B_vs_OPT_20s.png`.

## Stabilità temporale (600 frame)

Analisi su tutti i frame, con sorgente allineata al render. Il grafico completo è `G:\VDGP\ascii\experiments\stability20\stability_analysis.png`; i dati per frame sono in `stability_frames.csv`.

| Metrica | Valore |
|---|---:|
| Celle che cambiano simbolo, media | 19,0% |
| Celle che cambiano, p95 | 33,4% |
| Celle che cambiano, max | 78,3% (a un taglio/flash) |
| Cambi con variazione di tone < 0,01, media | **0,71%** |
| Cambi con tone < 0,01, max | **1,78%** |
| Reversali A→B→A per 1000 celle, media | 4,05 |
| Reversali per 1000 celle, max | 13,89 |
| Correlazione movimento ASCII / sorgente | **0,855** |
| Spike di movimento non spiegati dalla sorgente | **0** |
| Salto di hue, p95 / max | 1,72° / **2,86°** |
| Salto di luminanza, p95 / max | 0,013 / 0,122 |
| Area luminosa, min / max | 7,6% / 97,4% |
| Salto massimo dell'area luminosa | 33,4 punti (flash) |
| Spostamento baricentro, p95 / max | 2,72 / 6,28 celle |

Lettura:

- I picchi di cambio simbolo coincidono con tagli, flash ed esplosioni: non sono flicker casuale. La correlazione 0,855 e **zero spike non spiegati** confermano che il movimento ASCII segue la sorgente.
- Il churn da quantizzazione è sotto il 2%: il dither è fisso per cella e non lampeggia.
- I reversali A→B→A sono rari (4 per 1000 celle in media).
- Il colore è continuo: il salto massimo di hue è 2,86°, quindi la palette non "pompa".
- Il baricentro delle aree luminose non fa salti da taglio (max 6,3 celle): il segmento è più continuo del test 116–140 s.

Nessuna stabilizzazione temporale aggiuntiva è stata necessaria: introdurrebbe trascinamento senza risolvere il problema delle superfici chiare.

## Compressione

Master 17,1 Mbps, ricodificato con libx264, 1080p30, GOP 60, audio copiato.

| Versione | Bitrate | Dimensione | SSIM All | SSIM Y | PSNR avg / min |
|---|---:|---:|---:|---:|---:|
| Web 6 Mbps | 6,10 Mbps | 15,3 MB | 0,980 | 0,991 | 37,6 / 31,6 dB |
| Web 2 Mbps | 2,16 Mbps | 5,4 MB | 0,919 | 0,939 | 28,8 / 22,2 dB |

- **6 Mbps**: visivamente vicino al master; caratteri netti, nessun artefatto evidente.
- **2 Mbps**: bordi più morbidi, ringing/blocking attorno ai simboli e nel fondo scuro. Leggibile a dimensione normale, ma non trasparente. È il limite di stress, non il target.

Flicker aggiunto dalla compressione:

| Versione | Correlazione movimento | Errore medio diff | Floor statico (orig → comp) |
|---|---:|---:|---:|
| 6 Mbps | 0,999 | 0,00035 | 0,00450 → 0,00442 |
| 2 Mbps | 0,989 | 0,00109 | 0,00450 → 0,00422 |

La compressione non alza il floor statico: non introduce flicker temporale. Al 2 Mbps perde soprattutto dettaglio spaziale sui bordi.

Confronto pieno e crop 1:1: `...\compression_full_20s.png` e `...\compression_crop_20s.png`.

Raccomandazione: pubblicare a **6 Mbps o superiore** per il 1080p. Se la piattaforma impone ~2 Mbps, serve una variante **Balanced Web** con Glyph Size 0.021 e Contrast High 0.86; non è stata prodotta perché il target 6 Mbps supera il controllo.

## Tempi e risorse

- Render 20 s: **74,4 s** totali, 0,124 s/frame, 3,72 s di render per secondo di output.
- Risorse misurate durante il render 24 s con lo stesso preset: GPU ~45% media (60% picco), VRAM 4,3 GB media / **5,25 GB picco**, CPU ~43%, temperatura ~49 °C, potenza ~84 W media / 97 W picco. La misura include il carico del desktop; il valore GPU è indicativo.
- Stima non misurata per 5 minuti: ~18–19 min con la stessa scena e gli stessi campioni.

## Preset per il backend

Il file finale è `G:\VDGP\ascii\presets\ASCII_Cinematic_Balanced_v1.blend`. I parametri sono sul modificatore Geometry Nodes dell'oggetto `video`; l'immagine sorgente è nel nodo `Image Texture.001`.

In Blender 5.3:

```python
obj = bpy.data.objects["video"]
mod = obj.modifiers["GeometryNodes"]
ins = mod.properties.inputs

ins.Socket_4.value = 0.31    # Shadow Threshold
ins.Socket_8.value = 0.85    # Contrast High
ins.Socket_9.value = 0.24    # Local Contrast
ins.Socket_13.value = 0.05   # Dither Amp
ins.Socket_15.value = 2.0    # Source Frame Scale
```

`Source Frame Scale` va impostato a `source_fps / 30.0`: 2.0 per 59,94 fps, 1.0 per 30 fps, 2.0 per 60 fps. Senza questo, un video a 30 fps verrebbe campionato a metà.

Mappa completa:

| Socket | Nome | Valore |
|---|---|---:|
| 0 | Grid X | 80 |
| 1 | Grid Y | 45 |
| 2 | Glyph Size | 0.020 |
| 3 | Character Ramp | `" .,:;+HW@"` |
| 4 | Shadow Threshold | 0.31 |
| 5 | White Point | 0.95 |
| 6 | Gamma | 0.82 |
| 7 | Contrast Low | 0.18 |
| 8 | Contrast High | 0.85 |
| 9 | Local Contrast | 0.24 |
| 10 | Saturation | 1.5 |
| 11 | Exposure | 1.2 |
| 12 | Color Mode | 1.0 |
| 13 | Dither Amp | 0.05 |
| 14 | Palette Mix | 0.0 |
| 15 | Source Frame Scale | 2.0 |

Manifest: `G:\VDGP\ascii\presets\ASCII_Cinematic_Balanced_v1.json`.

Il preset è salvato con output PNG e range 1–9036. Il backend imposta risoluzione, range, fps, percorso e formato (PNG sequence o FFMPEG). La sostituzione della sorgente va fatta sul nodo `Image Texture.001`; il resto della catena non cambia.

## Limite noto e correzione proposta

**Problema:** a 60 s (12 s nel test) l'orbita in primo piano riempie il frame con una superficie chiara e quasi uniforme. Con B iniziale circa il 60% delle celle è `@`; OPT lo riduce, ma resta un campo denso di `H`/`W` e la scena non si legge. Lo stesso vale per l'esplosione a 66–68 s.

**Perché non è risolvibile con una curva globale:** la superficie dell'orbita e la sabbia hanno la stessa luminanza. Abbassare la densità per aprire la parete svuota anche il frame approvato a 52 s. La prova di soppressione delle alte luci lo conferma.

**Correzione specifica consigliata:** tone mapping **per shot**, non per frame.

1. Rilevare i tagli (cambio istogramma / differenza frame).
2. Per ogni shot, calcolare p5 e p95 della luminanza e impostare `Shadow Threshold` e `White Point` con un limite di variazione (es. ±0,06) rispetto al preset.
3. Animare i due socket con keyframe sui confini dello shot, interpolazione lineare su 2–4 frame, per evitare pop.
4. Override manuale per gli shot eroici o problematici (60 e 67 s).

Questo mantiene il look approvato a 52 s e recupera le superfici chiare, senza toccare la GUI né il sistema Geometry Nodes.

Alternativa: variante **Balanced Web** a 0.021/0.86 se si pubblica a 2 Mbps.

## Stato di accettazione

| Criterio | Esito |
|---|---|
| Scena riconoscibile | **Parziale**: 52 s sì; 58/64 s dipende dal movimento; 60 e 67 s no (parete chiara) |
| Caratteri distinguibili | Sì |
| Ombre senza rumore eccessivo | Sì |
| Colori con profondità e gradazioni | Sì |
| Nessun artefatto temporale importante | Sì (churn solo a tagli/flash) |
| Leggibile dopo compressione | Sì a 6 Mbps; marginale a 2 Mbps |
| Preset parametrico e riutilizzabile | Sì |

La milestone è quindi **da approvare con riserva**. Non considero chiuso il lavoro finché non viene deciso se accettare il limite delle superfici chiare o implementare il tone mapping per shot.

## Artefatti

- Master: `G:\VDGP\ascii\render\ASCII_Cinematic_Balanced_opt_20s.mp4`
- Compressi: `..._web6M.mp4`, `..._web2M.mp4`
- B vs OPT: `G:\VDGP\ascii\experiments\compression20\B_vs_OPT_20s.png`
- Frame rappresentativi: `...\representative_frames_20s.png`
- Contact sheet 20 s: `...\test_20s_contact_sheet.png`
- Compressione: `...\compression_full_20s.png`, `...\compression_crop_20s.png`
- Stabilità: `G:\VDGP\ascii\experiments\stability20\stability_analysis.png`, `stability_frames.csv`, `stability_summary.json`
- Preset: `G:\VDGP\ascii\presets\ASCII_Cinematic_Balanced_v1.blend`, `.json`
- Test precedente 116–140 s (storico): `G:\VDGP\ascii\render\ASCII_Cinematic_Balanced_opt_24s.mp4`
