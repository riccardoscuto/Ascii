# Auto ASCII Correction

Data: 2026-11-20

Motore di analisi e correzione automatica per il preset Cinematic Balanced v2.
La GUI non è ancora stata modificata: il motore si attiva dal backend con
`project.params["auto_correction"] = True` e scrive un piano ispezionabile in
`projects/<id>/temp/plan.json`.

> Rifinitura M4: il criterio `visible_base < 28%` è stato sostituito da
> `dark_detail`, distribuzione spaziale, saturazione dei caratteri e flag
> `resolution_limited`. Target medio e limiti sono in
> `docs/ASCII_READABILITY.md`.

## 1. Diagnosi dello shadow crush

Sorgente: coda scura del gameplay da 63,3 s (`gameplay_63s.mp4`, 48,9-63,3 s).

| Metrica (media intervallo) | Valore |
|---|---:|
| p5 / p10 / p25 / p50 / p95 celle | 0,012 / 0,016 / 0,026 / 0,039 / 0,207 |
| Celle sotto Shadow 0,234 | 96,6% |
| Celle visibili con v2 (modello completo) | 2,3% |
| Celle con dettaglio potenzialmente recuperabile | ~19,7% |
| Luminanza media render v2 | 0,1 / 255 |
| Pixel neri nel render v2 | 99,9% |

La soglia di 0,234 non è l'unica causa. Il primo carattere visibile non dipende
solo da Shadow: la catena è

`x = clamp((luma - shadow) / (white - shadow)) ^ gamma`
`c = clamp((x - contrast_low) / (contrast_high - contrast_low))`

Con i valori v2 (shadow 0,234, white 0,91, gamma 0,82, contrast_low 0,18,
contrast_high 0,85) il primo glifo compare a luma **~0,345**: Contrast Low 0,18
contribuisce per circa 0,11, più di Shadow. Abbassare solo Shadow non basta.
Il test A/B ha quindi agito su shadow, white, contrast low, gamma e local
contrast insieme.

## 2. Analisi

`gcf/ascii/correction.py` legge i frame di analisi già estratti a 10 fps
(320x180) e per ogni campione calcola:

- p5, p10, p25, p50, p95 delle celle 96x54;
- media, deviazione, percentuale di pixel neri e sovraesposti;
- densità dei bordi e contrasto locale (max-min per cella);
- saturazione media;
- istogramma 32 bin per il rilevamento tagli;
- visibilità stimata con la curva v2 completa.

Il campione a 10 Hz è sufficiente per l'adattamento; i tagli vengono poi
rifiniti a 30 fps con una finestra di 0,4 s attorno al taglio (`_refine_cut_frames`).

## 3. Correzione adattiva

Baseline: i keyframe del piano v2 della stessa sorgente (shadow/white) più
gamma 0,82, contrast low 0,18, high 0,85, local 0,24.

Per ogni campione:

- `visible_base` = frazione di celle visibili con il look v2;
- se `visible_base >= 0,28` la scena è sana: nessuna correzione;
- se `visible_base <= 0,08` e la sorgente ha dettaglio (p95 >= 0,045, bordi
  >= 0,008) la correzione è piena;
- in mezzo si applica una transizione smoothstep.

Target per scene da recuperare:

- `shadow = clamp(p10 * 0,85, 0,01, 0,20)`
- `white = clamp(max(0,30, p95 * 1,15), shadow + 0,14, 0,95)`
- `gamma = clamp(0,82 + (0,25 - p50) * 0,5, 0,82, 0,95)`
- `contrast_low = 0,03` (0,06 per scene meno scure), `contrast_high = 0,85`
- `local_contrast = clamp(0,24 + (0,20 - p50) * 0,6, 0,24, 0,36)`

Font, griglia, glyph size, rampa e palette non vengono toccati. Se p95 < 0,045
o i bordi sono assenti, la scena è considerata intenzionalmente nera: nessuna
correzione e flag `intentional_dark`, senza inventare dettaglio.

## 4. Adattamento temporale

- Il video è diviso in episodi ai tagli rilevati (più i tagli del piano base).
- Il frame di cambio viene rifinito a 30 fps analizzando 0,4 s attorno al taglio,
  così il passaggio non anticipa o ritarda di un frame.
- I target sono filtrati con mediana 7 campioni (0,7 s) e EMA (0,45), quindi
  un flash breve non sposta i parametri.
- I flash (spike di luminanza isolati) sono marcati `flash` ed esclusi dai tagli
  e dai flag di qualità.
- Ai tagli il cambio è duro, su 1 frame, rifinito a 30 fps.
- Le variazioni graduali seguono con transizioni morbide (nessun taglio).
- I keyframe sono generati ogni 0,3 s (più i confini degli episodi) e scritti
  con interpolazione lineare.

Test sintetico (stessa inquadratura, fade di luminosità + flash bianchi a 2 e
5 s): shadow passa da 0,060 a 0,010 seguendo il fade, i flash non cambiano i
parametri, max flicker 0,0062, nessun problema segnalato. Il piano marca le
variazioni graduali in `changes` (due intervalli, 1,2-2,2 s e 2,9-4,8 s).

## 5. Qualità automatica

Per ogni campione il motore simula la curva completa e calcola visibilità,
densità, deviazione degli indici, visibilità dei bordi e variazione dei
parametri. I flag sono:

- `too_empty` (visibilità < 5,5% dove la correzione doveva agire);
- `too_dense` / `dense_glyphs` solo se la correzione peggiora il baseline;
- `contrast_loss` (std degli indici < 55% del baseline);
- `edges_lost` solo se la correzione riduce la visibilità dei bordi;
- `flicker` (delta > 0,035 per campione dentro un episodio);
- `aggressive` (shadow < 0,008, white < 0,27, gamma > 1,0);
- `intentional_dark` (sorgente senza dettaglio, non è un problema).

Gli intervalli con flag persistenti (>= 0,5 s) finiscono in `problems` con i
motivi. Il piano supporta `correction_overrides` (lista di
`{start, end, params}`) per l'override manuale futuro.

## 6. Verifica A/B

### Coda scura (48,8-63,3 s, 436 frame)

| | v2 | Auto |
|---|---:|---:|
| Celle visibili | 0,6% | 60,4% |
| Luminanza media frame | 0,1 / 255 | 5,3 / 255 |
| Pixel neri | 99,9% | 94,4% |
| Correlazione con la sorgente | 0,10 | 0,77 |
| Parametri | 0,234 / 0,91 / 0,82 / 0,18 | 0,013 / 0,30 / 0,925 / 0,03 |

Lo sfondo resta nero (94% pixel neri): vengono mostrati solo i glifi con
struttura, non un grigio uniforme. Il volto, le mani e l'interno della stanza
sono leggibili.

### Scene luminose (primi 8 s, Balatro)

Auto non interviene (`visible_base` 0,35): parametri identici a v2 e frame
**pixel-identical** a 1, 4 e 7 s.

### NieR, 48-58 s

`visible_base` 0,933, `need` 0, nessuna correzione, nessun flag. Il render Auto
è equivalente a v2 (differenza media 0,2-0,6 / 255 su alcuni glifi, dovuta alla
quantizzazione dei keyframe; media e deviazione identiche).

### Video completo 63,3 s

- 1900 frame, 63,333333 s, 1920x1080 30 fps, audio AAC presente.
- Visibilità media 29,4% -> 43,8%; densità 12,7%; max flicker 0,0026.
- 0 campioni flaggati, 0 problemi.
- A 1 s e 26 s Auto è pixel-identical a v2.
- A 43 s e 48,8 s alza leggermente le ombre (visibilità 25,5% -> 29,9%).
- A 48,9 s il taglio è netto: frame 1468 (scena chiara) medio 1,84, frame 1469
  (scena scura) medio 5,31; nessun flash.
- A 49-62 s la coda scura passa da media 0,1 a 5,3-5,6 e da correlazione 0,10 a
  0,71-0,77.

Piano: `projects/ascii_20261120_200117/temp/plan.json` (634 campioni, 5
segmenti, keyframe completi, variazioni graduali, qualità e problemi).

## 7. Limiti

- Il motore non è ancora esposto nella GUI: opzione, anteprima prima/dopo,
  intensità e override arriveranno nella fase di rifinitura.
- L'override è supportato solo via parametro `correction_overrides`.
- La soglia di intervento (28% di celle visibili) è una scelta conservativa;
  scene volutamente dense (NieR) restano invariate.
- Il test NieR copre 10 s, non l'intero video da 5 min.
- Returnal non era disponibile.
- L'audio delle registrazioni gameplay è muto; la sincronizzazione audio/video è
  stata verificata con i test sintetici della Milestone 2.

## File

- Motore: `gcf/ascii/correction.py`
- Integrazione piano: `gcf/ascii/tone.py`, `gcf/ascii/preset.py`,
  `gcf/ascii/render.py`, `gcf/ascii/blender_job.py`
- Test: `tests/test_correction.py`
- A/B: `_discovery/milestone3/`
- Piano completo: `projects/ascii_20261120_200117/temp/plan.json`
- Output Auto 63 s: `projects/ascii_20261120_200117/output/{master,youtube}.mp4`
