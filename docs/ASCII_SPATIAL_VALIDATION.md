# ASCII Spatial Tone Mapping — Validazione video

Data: 2026-11-21
Ambito: villaggio 30–38 s (240 frame, 30 fps), preset v2 invariato, nessuna modifica a GUI o Guess Generator.

## 1. Causa del video nero

La mappa degli indici veniva salvata con i valori grezzi `0–8` in PNG, non riscalata a `0–255`.
In lettura il nodo Image Texture restituiva `valore / 255`, quindi l'indice massimo diventava
`8/255 = 0.031`; la Map Range del preset lo riportava a `0.25`, cioè al glifo 0 (spazio).
Tutte le celle finivano sul glifo vuoto: render nero, non errore di decodifica MP4.

Prova: i frame indice 1, 120 e 240 contenevano solo i valori 0–8 (istogramma), mentre il
render aveva media 0.08/255 e massimo 1/255. Il frame singolo funzionava perché
`spatial_render.py` riscalava già gli indici con `+0.001`.

Correzione: `round(min(1, indice/8 + 0.001) * 255)`. Il `+0.001` mantiene il valore sopra
il confine del livello e evita il troncamento al glifo inferiore.

## 2. Pipeline affidabile da sequenza PNG

Il render non legge più MP4: sorgente e indici sono sequenze PNG.

- Sorgente: `spatial_video/frames/f_0001.png … f_0240.png`, color space sRGB.
- Indici: `spatial_video_v2/idx/i_0001.png … i_0240.png`, color space Non-Color.
- Frame: indice 1-based, `Source Frame Scale = 1`, `Source Frame Offset = 0`.
- Nessuna conversione cromatica sugli indici: PNG 8 bit, lettura Non-Color, Map Range 0–1 → 0–8.
- Stop/ripresa: reso in tre blocchi (1–3, 4–6, 7–240); 240 frame presenti, nessun buco,
  nessun duplicato. Il job accetta `start`/`end`.
- Verifica di allineamento su sequenze sintetiche:
  - indice: frame 1 vuoto, 2 pieno, 3 vuoto → render 0.08, 94.45, 0.08;
  - sorgente: nero, bianco, nero → render 0.08, 130.48, 0.08.
  Entrambe le sequenze sono 1-based e sincronizzate.
- Verifica reale: confronto celle indice/render ai frame 1, 120, 240.
  Accordo 98.1%, 94.5%, 94.5%; flip 92.6/77/77%, mirror 92.3/76.7/76.5%.
  L'orientamento UV è corretto. Il cambio scena al frame 18 è riprodotto correttamente
  (montagna → villaggio), senza frame neri.

## 3. Video D

File validi:

- `_discovery/milestone5/spatial_video_v2/village_D_8s.mp4` — 1920×1080, 30 fps, 240 frame, 8.000 s.
- `.../village_D_8s_720p.mp4` — 1280×720, 240 frame.
- `.../village_AD_8s.mp4` — A 96 globale | D 144 spaziale.
- `.../village_SD_8s.mp4` — sorgente | D.
- `.../diagnosi_D.png` — sorgente, tono, indici, render ai frame 1/120/240.
- `.../temporal_D.png` — stabilità.

Misure:

- 0 frame neri su 240; media D 17.88/255 (min 17.60, max 20.63).
- Baseline A: media 10.81/255 (min 10.62, max 12.71).
- Correlazione media luminanza sorgente/D: 0.991.
- Delta indici: mediana 0.0004 livelli glifo; massimo 2.90 al frame 18 (cambio scena);
  massimo fuori dal cut 0.18. Nessun flicker o pulsing nel resto della sequenza.
- Il clip 30–38 s è un'inquadratura bloccata: dopo il cut del frame 18 la sorgente è ferma
  (differenza media 0.014/255). Non c'è movimento di camera o gameplay continuo.
- 720p: glifi leggibili; i glifi pieni diventano anelli, la struttura resta riconoscibile.

Prestazioni (144×81, 1920×1080):

- mappe tono+indici: 125.1 s / 240 = 0.52 s/frame (Python, single thread);
- render Blender: 81.6 s / 240 = 0.34 s/frame (tre avvii inclusi);
- risorse: RAM 1.16 GB, privato 3.72 GB, VRAM 7.31 GB di picco;
- 8 s totali: circa 3.5 minuti. La generazione mappe è il collo di bottiglia.

## 4. Generalizzazione — matrice 144×81

`scene_matrix/scene_matrix_compare.png`, dati in `scene_matrix/metrics.json`.
Stessa griglia, font e glyph size; unica differenza: mappa globale o spaziale.
La matrice usa il target mediano della scena, non il nome del gioco.

| Scena | p50 | vuote G→S | recuperate | perse | sat G→S | cielo sat G→S |
|---|---:|---:|---:|---:|---:|---:|
| Villaggio | 0.116 | 27.7% → 18.5% | 9.3% | 0.1% | 6.9% → 9.8% | 11.0% → 15.6% |
| Foresta | 0.057 | 39.2% → 27.4% | 12.1% | 0.3% | 1.7% → 2.4% | 3.2% → 4.2% |
| Scuro | 0.003 | 94.7% → 89.8% | 4.9% | 0.0% | 0.0% → 0.0% | 0.0% → 0.0% |
| NieR | 0.318 | 0.0% → 0.0% | 0.0% | 0.0% | 1.8% → 26.1% | 0.3% → 18.6% |
| Balatro | 0.106 | 12.7% → 3.9% | 8.7% | 0.0% | 10.1% → 11.4% | 0.7% → 0.8% |

Lettura:

- Villaggio e foresta: lo spaziale recupera struttura; il cielo si infittisce ma resta
  sotto la soglia candidata di saturazione (+4.6 e +1.0 punti).
- NieR: regressione netta, cielo saturo 0.3% → 18.6%; da mantenere globale.
- Scuro: lo spaziale non risolve il buio (94.7% celle vuote, p50 0.0034); serve M3/Amber.
- Balatro: lo spaziale migliora l'area di gioco, ma i testi UI restano il limite della griglia.

Regola candidata, solo dati e non implementata:

```
spaziale se:
  p50 >= 0.02
  e recuperate >= 8%
  e perse <= 2%
  e (cielo_sat_spaziale - cielo_sat_globale) <= 5 punti
```

Separa le cinque scene come sopra. Non è una validazione statistica: è una soglia da
verificare su più scene e su un clip in movimento.

## 5. Gate

Il bug del nero è risolto e la pipeline è riproducibile. D è superiore ad A su villaggio e
foresta, stabile su 240 frame, sincrono al cut, leggibile a 720p.

Limite decisivo: il materiale disponibile (63 s e 69 s) è un montaggio di inquadrature
bloccate. Non esiste movimento continuo da validare; il test temporale copre solo una
transizione dura e 7.4 s di scena ferma.

Decisione consigliata: **D è tecnicamente affidabile e può entrare in Auto ASCII Correction
solo come modalità opzionale, dietro le metriche sopra. Non va abilitato per default finché
un clip reale in movimento non supera lo stesso controllo.** Nessuna integrazione eseguita.

## 6. Limiti residui

- Cielo più denso nello spaziale (+0.9 livelli medi, saturazione +4.6 punti sul villaggio):
  è il limite visivo principale, entro la soglia candidata ma da tenere sotto controllo.
- Scene scure: M3/Amber resta il riferimento; D a tono fisso non le recupera.
- NieR: saturazione del cielo; la regola lo esclude.
- Balatro: testi UI sotto la soglia della griglia; non è un problema di tone mapping.
- Movimento continuo: non testato.
- La baseline A usa 96×54; la matrice isola il tono a 144×81 per entrambe le modalità.
- Il clip 30–38 s inizia con 0.6 s della scena precedente; A, D e i confronti condividono
  lo stesso taglio, quindi restano allineati.
