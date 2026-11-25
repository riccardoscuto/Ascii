# Milestone 8 — Renderer Quality & Adaptive Reconstruction

Data: 2026-11-25
Aggiornamento: la correzione geometrica e il gate sono in docs/ASCII_MILESTONE8_1.md.
Stato: **gate non superato, nessuna promozione automatica**. I nuovi candidati migliorano
alcune condizioni (scurità, foreste, UI ad alta densità, alte luci), ma non sono
uniformemente migliori e il percorso Blender approvato conserva un difetto di
posizionamento dei glifi. Auto resta non approvato per la GUI.

## 1. Metriche corrette

`gcf/ascii/perceptual.py`:

- griglia comune **96×54** orizzontale e **54×96** verticale; griglia di dettaglio
  **144×81** / **81×144** per UI e dettagli fini;
- normalizzazione robusta separata per sorgente e rendering; la copertura dei glifi è
  una mappa distinta;
- SSIM multiscala su luminanza delle celle, su copertura e su luminanza dei glifi;
- highlight: variazione interna delle alte luci, span p90–p10, correlazione del
  contrasto locale e penalità per celle contemporaneamente sature in copertura e
  luminanza (una regione bianca piatta non ottiene più un buon punteggio);
- UI: edge SSIM/correlazione a 144×81, contrasto locale, frazione di celle UI con
  tratto conservato e penalità di saturazione;
- colore: confronto di cromaticità (hue/saturazione) ignorando l'intensità e il fondo
  nero;
- temporale: flicker sulle celle statiche separato dal movimento che segue la sorgente.

`gcf/ascii/selector.py`:

- `select()` e `evaluate_shot()` usano la stessa rappresentazione e le stesse metriche;
- `window_errors` e frame invalidi **invalidano il candidato**; il candidato non viene
  più valutato su una finestra incompleta;
- una scena nera intenzionale, una conversione fallita e un errore tecnico di rendering
  hanno stati e motivazioni distinte nel no-choice;
- un frame nero è accettato solo se anche la sorgente corrispondente è nera;
- la correzione automatica usa statistiche robuste su più finestre (p50, p95, range,
  saturazione), non la mediana di un singolo frame centrale;
- il vecchio percorso a due still e `rescore()` restano rimossi.

Verifiche: black test → `selected=none`, motivo `intentional black scene`, progetto
originale non modificato. Shot village → `spatial` 0.608, `conservative` 0.587,
`legacy` 0.541, nessun `window_error`.

## 2. Adaptive highlight compression

Nuove varianti in `gcf/ascii/spatial.py`, tutte adattive e non promosse:

- **B `range`**: indici mappati sui percentili della scena (`v_p02`–`v_p98`);
- **C `compress`**: range adattivo + spalla morbida sulle alte luci;
- **D `local`**: range adattivo + guadagno sul contrasto locale;
- **guarded**: variante diagnostica che protegge i due indici densi solo dove il
  contrasto locale lo giustifica.

Su NieR (frame 15, 144×81):

| Variante | structure | edge | highlight | UI | coverage | idx 8 | idx ≥7 |
|---|---:|---:|---:|---:|---:|---:|---:|
| adaptive | 0.630 | 0.127 | 0.739 | 0.700 | 0.388 | 23.3% | 51.1% |
| range | 0.544 | 0.171 | 0.788 | 0.690 | 0.177 | 3.7% | 8.2% |
| compress | 0.617 | 0.133 | 0.793 | 0.692 | 0.225 | 4.7% | 14.6% |
| local | 0.525 | 0.204 | 0.796 | 0.691 | 0.171 | 4.3% | 8.6% |
| guarded | 0.252 | 0.153 | 0.708 | 0.684 | 0.162 | 10.7% | 20.9% |

La saturazione dell'indice 8 scende dal 23.3% al 3.7–4.7%; `compress` conserva più
densità, `local` conserva più bordo. Conserva però un limite: `structure` premia ancora
la densità, quindi non basta come misura di qualità.

Sugli altri scenari:

- **villaggio / montagna**: `adaptive` resta il migliore per structure e UI;
  `compress`/`local` diventano troppo radi;
- **foresta**: `local` e `compress` hanno edge e UI migliori di `adaptive`;
- **scuro**: `adaptive` ha copertura 0.003 (quasi vuoto), `range`/`compress`/`local`
  hanno copertura 0.03–0.04, highlight 0.84–0.89 e UI 0.75–0.78. È il guadagno più
  netto della milestone;
- **Conservative**: la regola che protegge incondizionatamente i due indici densi non
  risolve l'esplosione; `guarded` riduce l'indice 8 ma perde struttura. Non va promossa
  come correzione.

## 3. Decoupled glyph reconstruction

`gcf/ascii/reference.py` implementa un prototipo isolato:

- atlante dei glifi del font Bfont usato da Blender, rasterizzato dal grafo
  String→Curves→Fill;
- separazione tra forma del glifo, luminanza desiderata della cella, copertura,
  intensità del tratto, cromaticità e contrasto locale;
- per le celle texturate il glifo è scelto per correlazione con il pattern locale della
  sorgente (con prior verso glifi sparsi); per le celle piatte resta l'indice tonale;
- l'intensità del tratto segue la luminanza desiderata (gamma 0.8), non la luminosità
  del colore sorgente applicata una seconda volta;
- limite estetico: intensità massima 0.98, penalità per glifi densi in celle scure.

Confronto con la pipeline corrente (stessi frame, 144×81; reference pattern v2):

| Scena | variante | structure | edge | highlight | UI | color |
|---|---|---|---:|---:|---:|---:|---:|
| NieR | dec adaptive | 0.513 | 0.111 | 0.690 | 0.689 | 0.955 |
| NieR | dec local | 0.562 | 0.202 | 0.813 | 0.699 | 0.886 |
| villaggio | dec adaptive | 0.667 | 0.328 | 0.641 | 0.534 | 0.775 |
| montagna | dec adaptive | 0.702 | 0.306 | 0.576 | 0.580 | 0.840 |
| foresta | dec local | 0.652 | 0.498 | 0.671 | 0.541 | 0.658 |
| scuro | dec local | 0.629 | 0.676 | 0.905 | 0.784 | 0.883 |
| Balatro 192×108 | dec adaptive | 0.734 | 0.550 | 0.628 | 0.787 | — |

La ricostruzione decoupled è chiaramente migliore su **scuro, foresta, Balatro** e sulle
alte luci di NieR; è simile o leggermente inferiore su villaggio/montagna. Non è una
vittoria universale: il colore separato aiuta, la forma del glifo può diventare rumorosa
sulle trame naturali.

Confronto visivo: `_discovery/milestone8/lab/pipeline_vs_decoupled.png`.

## 4. Renderer diagnostico indipendente e perdita di informazione

`reference.py` rasterizza l'atlante reale, con la stessa griglia e lo stesso font, ma
non sostituisce Blender. Confronto a parità di mappe adattive:

| Scena | renderer | structure | edge | UI | coverage | glyph_luma |
|---|---|---:|---:|---:|---:|---:|
| villaggio | reference | 0.644 | 0.257 | 0.436 | 0.096 | 0.044 |
| villaggio | Blender | 0.679 | 0.257 | 0.586 | 0.149 | 0.134 |
| NieR | reference | 0.693 | 0.142 | 0.689 | 0.289 | 0.112 |
| NieR | Blender | 0.630 | 0.127 | 0.700 | 0.388 | 0.266 |
| Balatro 192×108 | reference | 0.678 | 0.390 | 0.585 | 0.088 | 0.030 |
| Balatro 192×108 | Blender | 0.708 | 0.408 | 0.676 | 0.168 | 0.110 |

Blender produce glifi più spessi e luminosi; il reference è più sottile. La differenza
non è solo nella scelta del glifo: margini, antialiasing e gestione colore contano.

### Difetto di posizionamento dei glifi

L'atlante reale del font ha copertura: `.` 1.1%, `H` 19%, `@` 31.9%. Nel render Blender
approvato, le celle con indice 0 contengono 0.65% di inchiostro e le celle con indice 8
arrivano al **66%**: i glifi sono traslati della loro posizione di layout nella stringa
`" .,:;+HW@"`. Il grafo usa `String to Curves` con l'intera rampa e `Pick Instance`
senza compensare l'offset di layout.

La correzione sperimentale in `_discovery/milestone8/ASCII_M8_Experimental*.blend`
(spostamento dei punti/gligi con tabella degli offset) riduce l'indice 8 a ~59% ma non
elimina l'inchiostro nelle celle 0 (1.2%). **Non è stata promossa**: il difetto resta
aperto e va risolto nel grafo di produzione, non con una tabella fragile.

## 5. UI e Balatro

Balatro è stato testato con il sorgente reale (`milestone5/scenes/balatro_source.mp4`,
1920×1080) e con il take verticale 1080×1920. Griglie:

| griglia | structure | UI | coverage | idx 8 |
|---|---:|---:|---:|---:|
| 96×54 | 0.597 | 0.621 | 0.112 | 10.6% |
| 144×81 | 0.640 | 0.672 | 0.143 | 11.2% |
| 192×108 | 0.708 | 0.676 | 0.168 | 10.8% |

La saturazione degli indici è stabile (~11%): il problema UI non è principalmente la
saturazione. A 192×108 semi, ranghi e disposizione delle carte sono riconoscibili; a
144×81 lo sono ancora; a 96×54 il testo e i semi si perdono. Il guadagno maggiore viene
dalla griglia più alta e dal colore separato, non da una regola sul gioco.

## 6. Confronti anonimi

- Still anonimi A/B/C a piena risoluzione e video 1920×1080 / 1080×1920 di 5 s:
  `_discovery/milestone8/anonymous/`.
- Chiave delle modalità: `_discovery/milestone8/anonymous/key.json`.

| Scena | A | B | C |
|---|---|---|---|
| NieR | compress | adaptive | decoupled |
| villaggio | adaptive | compress | decoupled |
| foresta | compress | decoupled | adaptive |
| scuro | compress | decoupled | adaptive |
| Balatro | adaptive | decoupled | compress |
| bird/rain | adaptive | decoupled | compress |

- Video generati con il **renderer diagnostico reference**, non con Blender di
  produzione; servono a giudicare movimento e stabilità, non a sostituire il gate.
- Sheet di scena: `sheet_<scena>.png`; frame: `<scena>_<label>_fNNN.png`.
- Un video Blender sperimentale di 5 s non è stato promosso: il difetto di layout dei
  glifi renderebbe il confronto fuorviante.

## 7. Gate

**Non superato.**

- Il percorso Blender approvato ha ancora il difetto di layout dei glifi: va corretto
  prima di qualsiasi nuova campagna di selezione.
- I nuovi candidati migliorano dark/foresta/UI/highlights, ma non sono uniformemente
  migliori su villaggio/montagna.
- Le metriche sono più corrette, ma `structure` continua a premiare la densità; il
  giudizio visivo resta necessario.
- Auto non è stato rieseguito sui 25 shot e non è approvato per la GUI.

Prossimi passi, in ordine:

1. correggere il posizionamento dei glifi nel grafo di produzione (punti/griglia con
   UV originale, oppure atlante di glifi) e verificare la copertura per indice contro
   l'atlante;
2. promuovere solo una variante di highlight dopo A/B visivo su esplosioni e superfici
   luminose;
3. usare la ricostruzione decoupled come candidato sperimentale, non come default;
4. solo dopo, rerun Auto 25 shot + holdout separato per registrazione/gioco.

Nessuna modifica a GUI, preset v2 approvati, Guess Generator o BlueFox. Nessun render
completo da cinque minuti.
