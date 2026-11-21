# ASCII adaptive tone mapping — test 48–68 s

Data: 2026-11-20
Baseline: `ASCII_Cinematic_Balanced_v1` (B OPT, 80×45)
Test: Nier **48–68 s**, 600 frame, 30 fps
Preset adattivo di test: `G:\VDGP\ascii\presets\ASCII_Cinematic_Balanced_Adaptive_TEST_48-68.blend`

## Metodo

1. Estrazione frame a 10 fps per l'analisi, scala 320×180.
2. Rilevamento tagli: distanza istogramma 32 bin + salto di luminanza.
3. Segmentazione: tagli + variazioni sostenute di p50 (>0,09 per almeno 0,5 s), segmenti <1,2 s accorpati.
4. Per ogni shot: p5/p10/p25/p50/p95 sulla luminanza delle celle 80×45.
5. Riferimento: preset B (0.31/0.95), statistiche dello shot 50–52,2 s (p10 0,471, p95 0,694).
6. Auto: `shadow = 0.31 + (p10 − 0,471)`, `white = 0.95 + (p95 − 0,694)`, variazione massima ±0,06. Il white point non viene mai alzato sopra 0,95: alzarlo riduceva la densità ma **scuriva** l'intera scena (il caso 58,5 s).
7. Override manuali per gli shot piatti/chiari, con valori verificati su still.
8. Keyframe sui Socket_4/5 del modificatore: 2 frame ai tagli, 10 frame ai cambi morbidi. Valori costanti dentro lo shot.

Nessuna modifica a palette, griglia, font, gamma, saturazione o exposure.

## Tagli e shot

Tagli rilevati: **52,2 s** e **65,0 s**.

| Intervallo | p10 | p25 | p95 | Shadow | White | Origine |
|---|---:|---:|---:|---:|---:|---|
| 48,0–52,2 | 0,447 | 0,514 | 0,678 | **0,310** | **0,950** | reference pin |
| 52,2–59,1 | 0,455 | 0,525 | 0,957 | 0,294 | 0,950 | auto ±0,06 |
| 59,1–60,8 | 0,592 | 0,671 | 0,894 | **0,580** | **0,950** | override: primo piano piatto |
| 60,8–62,0 | 0,478 | 0,549 | 0,757 | 0,318 | 0,950 | auto |
| 62,0–65,0 | 0,447 | 0,514 | 0,694 | 0,286 | 0,950 | auto |
| 65,0–66,5 | 0,510 | 0,576 | 0,878 | **0,310** | **0,950** | override: inizio esplosione |
| 66,5–68,0 | 0,510 | 0,576 | 0,878 | **0,580** | **0,960** | override: parete finale |

Override:
- **59,1–60,8 — 0,58/0,95**: alza la soglia per separare 2B e il bordo dell'orbita; white a 0,95 per non spegnere le alte luci.
- **65,0–66,5 — 0,31/0,95**: l'inizio dell'esplosione ha ancora forma; resta identico a B.
- **66,5–68,0 — 0,58/0,96**: riduce la parete finale mantenendo bordo e 2B.

## Keyframe applicati

| Frame | Shadow | White | Note |
|---:|---:|---:|---|
| 1440 | 0.310 | 0.950 | inizio, pin |
| 1565 | 0.310 | 0.950 | taglio 52,2 (hold) |
| 1567 | 0.294 | 0.950 | dopo il taglio, 2 frame |
| 1772 | 0.294 | 0.950 | fine shot |
| 1782 | 0.580 | 0.950 | cambio morbido 59,1, 10 frame |
| 1823 | 0.580 | 0.950 | fine shot |
| 1833 | 0.318 | 0.950 | cambio morbido 60,8 |
| 1859 | 0.318 | 0.950 | fine shot |
| 1869 | 0.286 | 0.950 | cambio morbido 62,0 |
| 1949 | 0.286 | 0.950 | fine shot |
| 1951 | 0.310 | 0.950 | taglio 65,0, 2 frame |
| 1994 | 0.310 | 0.950 | fine inizio esplosione |
| 2004 | 0.580 | 0.960 | cambio morbido 66,5 |
| 2039 | 0.580 | 0.960 | fine test |

Tutte le fcurve sono **LINEAR**; 14 keyframe per canale. Verifica di valutazione:

```text
1560  0.310 / 0.950     (52 s, identico a B)
1755  0.294 / 0.950     (58.5 s)
1800  0.580 / 0.950     (60 s)
1965  0.310 / 0.950     (65.5 s, identico a B)
2025  0.580 / 0.960     (67.5 s)
```

## Frame rate e sincronizzazione

Mapping: `source_frame = scene_frame × (source_fps / 30) + (1 − source_fps / 30)`.

| Sorgente | Scale | Offset |
|---|---:|---:|
| 30 fps | 1.0 | 0.0 |
| 59,94 fps | 1.998 | −0.998 |
| 60 fps | 2.0 | −1.0 |

Self-check su frame 1, 1440, 9000: nessuna deriva. La sorgente Nier 59,94 fps usa 1.998/−0.998, non 2.0.

Nell'analisi di stabilità il picco di correlazione del movimento è a un offset di 1–2 frame di estrazione (0,774 al lag migliore). È un offset dell'estrazione frame, non del render: il render usa il mapping esatto sopra.

## Confronto critico

Frame allineati allo stesso frame sorgente, non allo stesso timestamp del video:

- `G:\VDGP\ascii\experiments\adaptive\fair_comparison.png`
- `G:\VDGP\ascii\experiments\adaptive\fair_crop_60_67.png`
- `G:\VDGP\ascii\experiments\adaptive\critical\critical_50_53.png`
- `G:\VDGP\ascii\experiments\adaptive\critical\critical_58_61.png`
- `G:\VDGP\ascii\experiments\adaptive\critical\critical_65_68.png`

Differenza media rispetto a B OPT sullo stesso frame:

| Frame | Diff media | Lettura |
|---:|---:|---|
| 52,0 s | **0,000** | identico: riferimento preservato |
| 58,5 s | 2,124 | leggermente più denso, nessuna perdita |
| 60,0 s | 28,047 | parete ridotta, 2B e bordo più leggibili |
| 65,5 s | **0,000** | identico: inizio esplosione preservato |
| 67,5 s | 28,023 | parete ridotta, più profondità; resta un campo |

Lettura onesta:

- A **52 s** nulla è cambiato: stesso frame, stessi parametri, diff 0.
- A **58,5 s** l'auto 0,294/0,95 rende l'immagine appena più densa di B; la struttura è la stessa.
- A **60 s** il muro di `@`/`W` si apre: il personaggio 2B e il bordo dell'orbita emergono, l'orbita resta una superficie chiara. Il miglioramento è nella separazione delle forme, non in un dettaglio inventato.
- A **65,5 s** l'inizio dell'esplosione è identico a B.
- A **67,5 s** la parete è meno uniforme e il bordo/2B si leggono, ma il fumo chiaro resta un campo. La sorgente non ha abbastanza struttura per andare oltre con una curva globale.

## Stabilità (600 frame, tone mapping adattivo)

Analisi con i parametri per-frame del piano, non con i valori fissi OPT.

| Metrica | Valore |
|---|---:|
| Churn medio | 21,1% |
| Churn p95 | 37,1% |
| Churn max | 86,6% (taglio/ramp) |
| Churn da quantizzazione, media | **0,68%** |
| Churn da quantizzazione, p95 | 1,17% |
| Churn da quantizzazione, max | 3,42% (a 62,2 s) |
| Reversali A→B→A / 1000 celle, media | 4,2 |
| Reversali max | 19,4 |
| Correlazione movimento (lag allineato) | **0,774** |
| Spike non spiegati | 3 (4,2 / 16,93 / 19,63 s: tagli e ramp) |
| Hue p95 / max | 1,61° / **2,87°** |
| Luma p95 / max | 0,014 / 0,124 |
| Area luminosa min / max | 7,6% / 86,0% |
| Baricentro p95 / max | 2,39 / 6,5 celle |
| Area scura media | 9,0% |

Rispetto a B OPT (churn medio 19,0%, quantizzazione 0,71%, hue max 2,86°):

- La media e il p95 della quantizzazione restano simili.
- Il massimo sale a 3,42% in un frame al confine 62,0 s: è lo spostamento globale 0,318→0,286 su 10 frame, non flicker casuale. Se si vuole azzerare anche quel picco, portare la transizione morbida a 16 frame; non è stato fatto per non allungare ulteriormente il test.
- I 3 spike coincidono con i tagli (52,2 / 65,0) e il ramp finale (67,6): sono cambi di contenuto o di parametro, non instabilità del dither.
- La palette è continua: hue max 2,87°, quindi nessun pumping cromatico.
- Le silhouette non fanno salti: baricentro max 6,5 celle.

Grafico e dati: `G:\VDGP\ascii\experiments\stability_adapt2\`.

## Risorse

- Render adattivo 20 s: **69,4 s** totali, 0,116 s/frame, 3,47 s per secondo di output.
- Master: `G:\VDGP\ascii\render\ASCII_Cinematic_Balanced_Adaptive_20s.mp4`, 16,8 Mbps, 1920×1080, 30 fps, 600 frame, audio.
- Baseline B OPT: `ASCII_Cinematic_Balanced_opt_20s.mp4`.

## Verdetto

| Criterio | Esito |
|---|---|
| 52 s almeno altrettanto leggibile | **Sì, pixel-identical** |
| 60 s migliora visibilmente | **Parziale/sì**: 2B, bordo e profondità migliori; l'orbita resta liscia |
| Esplosioni con profondità, non parete uniforme | **Parziale**: 65,5 identico a B; 67,5 meno piatto ma ancora un campo |
| Nessuna transizione luminosa artificiale | Sì: keyframe lineari, hold dentro gli shot, 2/10 frame; un picco di quantizzazione a 62,2 s |
| Estetica coerente | Sì: palette, griglia, font e gamma invariati |

Il sistema adattivo **migliora i casi 58–61 s senza degradare 52 s e 65,5 s**. Non risolve completamente il 67,5 s: la sorgente è un'esplosione chiara e uniforme, e una curva globale non può inventare struttura. Continuare a modificare i parametri globali produrrebbe solo un campo più o meno denso, non più riconoscibile.

**Non considero chiuso il caso 67,5 s.** Opzioni, in ordine di costo:
1. Accettare l'esplosione come flash di 1,5 s: il resto del test è leggibile.
2. Ritagliare il test a 48–66,5 s (18,5 s) per l'approvazione estetica, tenendo 65–68 come stress test separato.
3. Maschera/roto manuale solo per l'esplosione, per separare fumo e personaggio: non parametrica, ma onesta.
4. Un `Balanced Web` a 0.021 non risolve la mancanza di dettaglio; migliora solo la lettura dei bordi.

## File del sistema

- Analisi: `G:\VDGP\ascii\tools\adaptive_tonemap.py`
- Config: `G:\VDGP\ascii\tools\adaptive_config_48_68.json`
- Applicazione keyframe: `G:\VDGP\ascii\tools\apply_adaptive_tonemap.py`
- Piano: `G:\VDGP\ascii\experiments\adaptive\adaptive_plan_48_68.json`
- Scena adattiva: `G:\VDGP\ascii\presets\ASCII_Cinematic_Balanced_Adaptive_TEST_48-68.blend`
- Baseline preservata: `G:\VDGP\ascii\presets\ASCII_Cinematic_Balanced_v1.blend`, `preset_B_balanced.blend`
- Varianti A/C intatte: `preset_A_soft.blend`, `preset_C_detail.blend`
