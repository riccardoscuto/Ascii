# Milestone 7.1 — Auto Selector: validazione indipendente

Data: 2026-11-23
Stato: prototipo Auto **non approvato per la GUI**. Accuratezza indipendente 19/25 (76%),
6 regressioni visive, 1 scena dichiarata non recuperabile. Il gate M7 sul composito
restava 5/5, ma il dataset eterogeneo ha mostrato i limiti del punteggio.

## 1. Correzioni temporali

Il confronto non usa più due frame distanti. Per ogni shot:

- 3 finestre rappresentative (15%, 45%, 75%);
- 3 frame consecutivi per finestra (9 frame per candidato);
- guardie su **ogni frame**: nero/quasi nero, max pixel, frame mancanti;
- delta indice/lit tra frame consecutivi confrontato col delta della sorgente;
- il movimento reale non viene penalizzato; viene misurato l'eccesso artificiale:
  `max(0, delta_candidato − delta_sorgente × 8 × 1.5)`.

## 2. Dataset indipendente

25 shot, 23 orizzontali e 2 verticali 9:16:

- NieR dinamico 4 shot;
- Balatro/UI 3 shot;
- montagna, villaggio 3, foresta 2, scuro 3;
- foresta fade 2, dark flash 2;
- bird/rain 2;
- Witcher verticale 2;
- black test 1 (guardia no-choice).

Sorgenti: NieR, The Witcher 3, Balatro, foresta/fade, dark flash, bird/rain, vertical take.
Non sono stati riadattati parametri per titolo.

Ogni shot è stato valutato con Legacy 96, Spatial adaptive 144, Conservative adaptive 144;
per il colore è stata valutata anche la variante alternativa sul candidato scelto.

## 3. Accuratezza Auto vs manuale

| Metrica | Risultato |
|---|---:|
| Shot totali | 25 |
| Shot leggibili | 24 |
| Non recuperabili (black test) | 1 |
| Scelte modalità corrette | 19/25 (76.0%) |
| Colore corretto sui leggibili | 19/24 (79.2%) |
| Regressioni visive | 6 |
| Regressioni di score | 0 |

Le 6 regressioni visive:

| Shot | Auto | Manuale | Nota |
|---|---|---|---|
| NieR esplosione | conservative | legacy | Spatial/Conservative bruciano l'esplosione; Legacy conserva il contrasto |
| Balatro 0 | conservative | legacy | il fondo e le carte si riempiono; Legacy legge meglio UI/testi |
| Balatro 1 | conservative | legacy | idem |
| Balatro 2 | conservative | legacy | idem |
| Montagna | legacy | spatial | Spatial mostra più paesaggio/nuvole |
| Foresta fade 1 | legacy | spatial | Spatial conserva più struttura forestale |

Il punteggio Auto era **più alto** del manuale in tutte e 6: quindi le metriche non
misurano ancora ciò che rende leggibile l'ASCII. Non è una regressione del renderer, è
un limite del selettore.

Mismatch colore: NieR 1/2 e Balatro 0/1/2 scelgono Original dove il manuale preferisce
Amber. La preselezione per saturazione non basta.

Scena non recuperabile: black test → tutti i candidati score `-1`, Auto risponde `none`
con motivazione `no acceptable candidate`. La guardia funziona ma non è stata nascosta
da una media.

## 4. Formato verticale, audio e non mutazione

- Verticale 9:16: 2 shot 1080×1920, griglia 81×144, rendering e metriche corretti.
- Audio: shot NieR con audio reale → master candidato con AAC; concat Auto con audio
  preservato (`audio_test.mp4`, 2.533 s, stream AAC).
- Non mutazione: `selector.select` usa un progetto shadow; `evaluate_shot` crea solo
  progetti candidati. Il progetto originale non viene modificato.
- Preset, Legacy, fixed D/D-Conservative e rendering approvati restano invariati.

## 5. Transizione 3.1 s

Confronto frame per frame 2.8–3.7 s tra sorgente e Auto:

- step massimo sorgente: 5.74;
- step massimo render: 6.02;
- step al cambio modalità (3.1 s): 3.40, sotto il passo della sorgente (4.53);
- nessun salto nero o cambio di densità artificiale evidente.

File: `_discovery/milestone7_1/transition/transition_3_1.png` e `.json`.

## 6. Cache, ripresa e compatibilità

- Mappe corrotte: rigenerazione, `index_root` identico.
- Stop/ripresa reale: chiuso a 57/90 frame, ripresa 90/90, pixel identici al continuo.
- Piani Legacy: riuso del piano approvato, keyframes e hash invariati.
- Bitrate: mappe e frame non ricalcolati.
- Test: 51 test unitari OK.

## 7. Gate

**Auto non è abbastanza affidabile per la GUI.** Accuratezza 76%, sei regressioni visive,
in particolare UI complesse, esplosioni e paesaggi luminosi. Il vecchio 5/5 del composito
non era rappresentativo.

Prossimo passo consigliato: migliorare il punteggio con metriche di contrasto/testo,
protezione delle alte luci e spazio negativo, ampliare il dataset con altri giochi reali
e ripetere il gate. Nessuna integrazione GUI, nessun default Auto, nessun render da
cinque minuti.

File: `_discovery/milestone7_1/dataset/summary.json`, `dataset_results.json`,
`sheets/*.png`, `black_0`, `audio_test.mp4`.
