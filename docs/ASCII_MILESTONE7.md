# Milestone 7 — Adaptive Spatial + Auto Selector offline

Data: 2026-11-23
Stato: Adaptive Spatial e prototipo Auto implementati e verificati sul composito 14 s.
Auto non collegato alla GUI, non default; Legacy M3/M4 resta la soluzione per le scene scure.
Nessuna modifica a preset v2, GUI o Guess Generator.

## 1. Spatial adattivo

Aggiunte due varianti sperimentali, senza toccare D e D-Conservative fissi:

- `adaptive`: stesso indice D, con target per shot e curva intra-shot;
- `adaptive-conservative`: regola D-Conservative con target e percentili per shot.

Le varianti `d` e `conservative` restano riproducibili: mappe, manifest e parametri sono
ancora quelli del gate precedente.

Per ogni shot l'analisi calcola:

- target mediano della luma lineare;
- percentili edge/std locali per D-Conservative;
- una curva target a 10 fps, interpolata a 30 fps;
- esclusione dei flash brevi dal target (run ≤ 5 frame);
- smoothing esponenziale e limite di variazione di 4% del target per frame;
- cambio di target solo al cut, non a metà shot.

Sul composito la foresta/fade ha mostrato un flash al frame 1 del candidato S3:
il target è rimasto `0.097–0.200`, non è stato trascinato a `0.98`, e il flash resta
visibile nel contenuto. Il target varia gradualmente dentro lo shot; nessun cambio
improvviso di densità.

## 2. Composito di test

`_discovery/milestone7/composite_light.mp4`, 14 s, 420 frame, 1920×1080, 30 fps:

- NieR dinamico 0–3.5 s;
- dissolvenza graduale verso il villaggio;
- villaggio luminoso 3.5–7 s;
- foresta con rampa/flash 7–10.5 s;
- interno scuro The Witcher 10.5–14 s.

Cambio netto e dissolvenza sono presenti; la foresta contiene una variazione di luce
sostenuta dentro la stessa inquadratura.

## 3. Auto Selector offline

`gcf/ascii/selector.py` confronta, per ogni shot:

1. Legacy 96×54;
2. Spatial adaptive 144×81;
3. Spatial-Conservative adaptive 144×81.

Ogni candidato viene renderizzato su due frame rappresentativi. Le metriche includono
struttura/edge, silhouette, ombre, densità/celle vuote, saturazione, colore, continuità
temporale e guardie su nero/quasi nero. Non si usa il nome del gioco. Se i punteggi sono
vicini si preferisce la baseline o il candidato più stabile; il cambio avviene solo tra
shot.

Piano: `projects/ascii_20261123_143432/temp/selection_plan.json`.
Comando sperimentale: `python -m gcf ascii auto --project projects/<id>`.

## 4. Timeline Auto

| Shot | Intervallo | Auto | Manuale | Score |
|---|---:|---|---|---:|
| S0 NieR | 0.0–3.1 | conservative | conservative | 0.434 |
| S1 villaggio | 3.1–7.1 | spatial | spatial | 0.556 |
| S2 foresta | 7.1–8.5 | conservative | conservative | 0.553 |
| S3 foresta/fade | 8.5–10.5 | conservative | conservative | 0.538 |
| S4 scuro | 10.5–14.0 | legacy | legacy | 0.648 |

Auto e manuale coincidono **5/5**. Nessun caso in cui Auto sceglie una modalità peggiore
della selezione manuale. Lo scuro viene riconosciuto: Spatial e Conservative hanno score
`-1` per render quasi nero, quindi vince Legacy M3.

File: `_discovery/milestone7/auto/auto.mp4`, `manual.mp4`, `auto_vs_manual.mp4`,
`selection_timeline.png`, `gate_metrics.json`, `manual_plan.json`.
Auto e manuale hanno lo stesso SHA256 (`A7B6025C…ABD334`).

## 5. Stabilità e cache

- Mappe corrotte: un file indice corrotto ha forzato la rigenerazione; il nuovo
  `index_root` è identico a quello registrato.
- Cache: se cambia solo il bitrate, mappe e frame non vengono rigenerati.
- Stop/ripresa reale: processo Blender chiuso a 57 frame su 90; ripresa → 90/90,
  numerazione sequenziale, **differenza pixel 0** rispetto al rendering continuo.
- Preview/finale: frame identici pixel per pixel nella prova da 2 s.
- Vecchi piani Legacy: il piano approvato viene riusato se il contesto coincide o se è un
  piano legacy senza contesto; keyframes e hash del file restano invariati.
- Flash/fade: target stabile, guardie su frame neri, nessun frame mancante.
- Test automatici: **50 test OK** (`python -m unittest discover -s tests`).

D-Conservative adattivo sul composito:

| Shot | Vuote min–max | Delta indici med/max | Target |
|---|---:|---:|---:|
| S0 NieR | 22.8–48.2% | 0.569 / 1.094 | 0.257–0.298 |
| S2 foresta | 30.6–38.9% | 0.300 / 0.534 | 0.111–0.191 |
| S3 foresta/fade | 0–44.2% | 0.271 / 4.434 (flash) | 0.097–0.200 |

Il picco massimo di S3 è il frame di flash; il target non cambia. Le aree stabili non
mostrano pulsazioni oltre il movimento della sorgente.

Variazione nelle aree a luminanza stabile (30% delle celle con minore delta sorgente):

| Shot | Delta indici aree stabili | Delta indici totale |
|---|---:|---:|
| S0 NieR | 0.242 | 0.569 |
| S1 villaggio | 0.031 | 0.063 |
| S2 foresta | 0.210 | 0.315 |
| S3 foresta/fade | 0.201 | 0.486 |

Le aree stabili cambiano meno del totale; il residuo maggiore su NieR è dovuto al
movimento/effetti della scena, non a un cambio di piano.

## 6. Prestazioni

- Mappe adattive: ~2.5 s per 60 frame di shot; ~5 s per 90 frame.
- Render Blender: ~0.29 s/frame.
- Auto offline: due still per candidato per shot; il costo maggiore è il render dei
  candidati, non l'analisi.
- Composito 14 s: 420 frame, Auto e manuale 14.0 s.

## 7. Gate

- Adaptive Spatial: **verificato** su transizioni e luce sostenuta; flash escluso dal piano.
- D-Conservative adattivo: **candidato migliore** su NieR/foresta, sperimentale.
- Auto offline: **5/5** scelte coincidenti con il manuale, nessuna regressione osservata
  sul composito. Non è approvato per GUI/default e non è stato testato su 5 minuti.
- Scuro: Legacy M3/M4 obbligatorio.
- GUI, preset v2, BlueFox, Guess Generator: invariati.

Prossimo passo, solo dopo approvazione: ampliare il dataset Auto, validare più shot e
solo allora collegarlo alla GUI. Nessun render completo da cinque minuti.
