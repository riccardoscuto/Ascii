# Milestone 6 — Spatial Tone Mapping nel backend

Data: 2026-11-21
Stato: backend Legacy/Spatial integrato e verificato; D-Conservative sperimentale accettato
per il gate; Auto progettata ma non approvata; nessuna modifica a GUI, preset v2 o Guess Generator.

## 1. Backend riproducibile

Il motore sperimentale è ora in `gcf/ascii/`:

- `luma.py` — sRGB → luma lineare, campioni cella, range/std locali.
- `spatial.py` — mappe globali/spatial/conservative, cache, manifest, validazione.
- `render.py` — modalità Legacy/Spatial, mappe, firma di cache, stop/ripresa.
- `blender_job.py` — iniezione della sequenza indici nel GN, verifica del job.
- `preset.py`, `tone.py`, `correction.py` — griglie parametriche e luma lineare.
- `cli.py` — `gcf ascii preview|still|render --mode legacy|spatial|auto`.

Nessun percorso `_discovery` è usato dal backend.

### Modalità

| Modalità | Stato | Uso |
|---|---|---|
| `legacy` | approvata | preset v2, 96×54, piano M3/M4 |
| `spatial` | approvata come motore | 144×81, indice esterno |
| `auto` | non approvata | rifiutata dal backend finché non passa il gate |

Varianti Spatial: `d` (attuale), `conservative` (D-Conservative), `global` (solo controllo
sperimentale C 144, non è una modalità di produzione).

## 2. Correzioni richieste

- Densità: `preset.grid_for` arriva a 160; `density=81` produce 144×81 e glyph 0.01111.
- `tone.py`: griglia di analisi parametrica, non più fissa 80×45.
- `correction.py`: griglia parametrica, blocchi e indici calcolati sulla griglia scelta.
- Luma: le celle di analisi sono in luce lineare, coerenti con il shader; cut/flash restano
  metriche percettive.
- Firma di cache: sorgente SHA1, preset SHA1, parametri, piano, griglia, modalità, variante,
  hash delle mappe e versione renderer. Il bitrate di export è escluso.
- Indici: codifica 0–255 con 9 livelli, verifica prima e dopo il render; le mappe grezze
  `0–8` vengono rifiutate.
- Progetto: conserva modalità, variante, griglia, piano, mappe e hash, renderer version,
  override e tempi.
- Legacy resta il percorso 96×54 con preset v2 invariato. I nuovi piani usano luma lineare
  (correzione richiesta) e possono quindi differire dai piani sRGB dei progetti più vecchi;
  l'output A approvato è conservato come riferimento e non è stato modificato.

## 3. D-Conservative

Regola locale, senza quota fissa di celle vuote:

- struttura = edge relativo `|L − B| / B`;
- texture = deviazione standard locale 5×5;
- protezione delle alte luci con la luma corretta;
- soglie dai percentili della scena (p50/p85 di edge e std), non globali;
- le celle sotto la soglia diventano vuote, quelle intermedie perdono un livello;
- i glifi 7–8 non vengono rimossi.

Risultato su NieR 48–58 s: celle vuote **0% → 31.9%**, media render 36.26 → 32.74,
0 frame neri/quasi neri. La silhouette e gli elementi principali restano riconoscibili;
il fondo piatto si separa meglio.

Costo: il delta indici mediano sale da 0.158 (C) a 0.548 (D-Conservative), massimo 1.81
al cut; le variazioni delle celle vuote sono graduali (0.03/frame) e non mostrano flicker
fuori da cut/flash. Va comunque validato a video prima di un uso più ampio.

## 4. A/B/C/D su NieR 48–58 s

A = output approvato M3/v2 96×54; B = C globale 144×81; C = Spatial 144×81;
D = D-Conservative 144×81. Stesso clip, font, palette, glyph e tone.

| | A Legacy 96 | B globale 144 | C Spatial 144 | D Conservative 144 |
|---|---:|---:|---:|---:|
| Media luminanza | 14.03 | 9.01 | 36.26 | 32.74 |
| Frame neri | 0 | 0 | 0 | 0 |
| Frame quasi neri | 0 | 22 | 0 | 0 |
| Celle vuote | n/d | 65.1% | 0.0% | 31.9% |
| Corr. sorgente | 0.965 | 0.953 | 0.976 | 0.977 |
| Delta indici mediano | n/d | 0.244 | 0.158 | 0.548 |
| Delta indici massimo | n/d | 3.20 | 0.81 | 1.81 |
| Corr. YouTube/indice | n/d | 0.820 | 0.804 | 0.745 |

B è il controllo globale: troppo vuoto e con 22 frame quasi neri. C è leggibile ma
riempie tutto il fondo. D-Conservative recupera spazio negativo e mantiene pianeta, nave,
HUD e minimappa; resta più denso di A/B ma è la variante più vicina all'obiettivo.

File: `_discovery/milestone6/abcd/` (`A_approved.mp4`, `B.mp4`, `C.mp4`, `D.mp4`,
`CD.mp4`, `ABCD.mp4`, `abcd_compare.png`, `abcd_metrics.json`).

## 5. Tre sorgenti

| Sorgente | Legacy | Spatial |
|---|---|---|
| Villaggio 30–38 s | media 11.18, 0 neri, 44.5 s render | media 19.81, 17.6% vuote, 0 neri, 69.7 s |
| Scuro 49–57 s | media 5.37, 0 neri, M3/Auto | media 0.54, 89.8% vuote, **REJECTED** |

Lo Spatial scuro è quasi nero ed è stato respinto dal guard automatico. M3/M4 Legacy resta
la soluzione approvata per le scene scure.

File: `_discovery/milestone6/three/` (`three_compare.png`, `projects.json`,
`rejected/dark_spatial.mp4`).

## 6. Verifiche tecniche

- **Stop/ripresa**: cancel dopo 9 s, 0 frame; ripresa completata 120/120.
- **Determinismo**: still ripetuto → differenza pixel 0; frame 30–60 rigenerati dopo
  cancellazione → differenza pixel 0; root delle mappe identico.
- **Cache bitrate**: cambiando solo `youtube_mbps`, mappe 0.15 s, nessun rerender,
  solo ricodifica (3.9 s sul test da 2 s).
- **Guard**: mappe 0–8 rifiutate; frame neri/quasi neri e disallineamento indice/render
  segnalati; dark Spatial FAIL.
- **Manifest**: SHA1 per frame di sorgente, tono, indice e render; map key e index root
  nel progetto e nella verifica Blender.
- **Compressione**: correlazione indice/frame YouTube 0.80 (C), 0.75 (D); i glifi restano
  leggibili a 8 Mbps, con perdita maggiore sulla variante conservativa più rada.

## 7. Prestazioni

NieR 10 s, 300 frame, 144×81:

| Fase | Tempo |
|---|---:|
| Preparazione sorgente + analisi + piano | 5.8 s |
| Mappe Spatial | 15.8–16.0 s (~0.05 s/frame) |
| Render Blender | 86–93 s (~0.30 s/frame) |
| Codifica master + YouTube | 14–16 s |

Il collo di bottiglia è il render Blender, non più la generazione mappe. La vecchia
implementazione Python era ~0.52 s/frame; la versione NumPy è ~10× più rapida.
Caching e map key evitano di rigenerare mappe per cambi di bitrate o di sola codifica.

## 8. Gate

- Legacy/Spatial backend: **verificati**.
- D-Conservative: **accettato come variante sperimentale**, non come default universale.
- Legacy non è stato sostituito: preset v2, 96×54 e piano M3/M4 restano il percorso
  approvato; il fix luma lineare cambia i nuovi piani, non il preset.
- Auto: **non approvata**, solo progetto in `docs/ASCII_AUTO_SELECTOR.md`.
- Scene scure: Legacy M3/M4 obbligatorio; Spatial scuro respinto.
- GUI, preset v2, BlueFox e Guess Generator: invariati.
- La GUI continua a creare progetti Legacy; Spatial è pilotato dal CLI finché il selettore
  non sarà approvato e collegato. Aprire un progetto Spatial nella GUI attuale non è
  supportato (la densità GUI è limitata e sovrascriverebbe la griglia).

Prossimo passo, solo dopo approvazione: implementare il selettore Auto e validarlo su
shot multipli prima di collegarlo alla GUI.
