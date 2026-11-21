# Adaptive Glyph Emission + 144×81 — esito

Data: 2026-11-21

## Implementazione

In una copia del preset, non nel file originale:

- Socket aggiunti al Geometry Nodes: `Emission Floor`, `Emission Ceiling`,
  `Emission Amount`.
- La luminanza del colore finale (Original RGB o Amber) viene rimappata:
  `L' = min(max(L, floor*amount), ceiling)`.
- Il guadagno `L'/L` viene applicato al colore RGB, preservando tonalità e
  saturazione; le alte luci sono limitate dal ceiling.
- Il remap è attivo solo per le istanze con indice > 0; le celle senza glifo
  restano nere.
- Gli attributi delle istanze e il materiale usano il colore rimappato.
- I Socket del modifier sono stati impostati dal job (Grid X/Y, Glyph Size,
  emissione) e il render è stato verificato, non solo il valore dei Socket.

## A/B/C/D sul villaggio 33 s

| Variante | Senza glifo | Glifo scuro | Visibile | Note |
|---|---:|---:|---:|---|
| A 96×54 | 26,8% | 8,6% | 64,6% | baseline |
| B 96×54 + emissione | 26,8% | 8,6% | 64,6% | diff vs A 0,067/255: impercettibile |
| C 144×81 | 27,7% | 7,9% | 64,3% | più dettaglio, stesse celle vuote |
| D 144×81 + emissione | 27,7% | 7,9% | 64,3% | diff vs C 0,001/255: nessun effetto |

L'emissione **non recupera i glifi assenti**: il 27% delle celle non ha un
carattere e il floor non può inventarlo. La 144×81 aumenta il dettaglio del
cielo, ma non riduce le celle senza glifo né rende riconoscibili castello e
case. La combinazione 144 + emissione non è una candidata.

Confronto: `_discovery/milestone5/village_abcd_compare.png`

## Perché l'emissione non basta

- Le celle senza glifo sono il 27%: il tone/index globale lascia neri gli
  edifici. L'emissione agisce solo sui glifi già presenti (64%).
- La 144×81 cambia la densità, non la distribuzione tonale: le celle vuote
  restano ~28%.
- Un tone globale più basso (C1/medium) schiarisce il cielo più degli edifici:
  serve una correzione **locale** o due livelli, non un altro floor.

## Benchmark griglie

| Griglia | Glifi | Tempo/frame |
|---|---:|---:|
| 96×54 | 5.184 | ~0,19 s |
| 144×81 | 11.664 | ~0,20 s |
| 192×108 | 20.736 | ~0,23 s |

La griglia non è il collo di bottiglia. La 144×81 è il compromesso di dettaglio,
ma da sola non risolve la leggibilità. Subcell 2×2 (stessa cardinalità della
192) non dimostrato superiore.

## Decisione

1. **Non promuovere** 144×81 + emissione: il guadagno visivo non è convincente.
2. La prossima modifica è **locale**, non un'altra soglia/griglia:
   - tone mapping locale sulla luma (recupero delle ombre senza schiarire il
     cielo), oppure
   - due livelli geometrici silhouette + tonal.
3. L'emissione adattiva resta utile **dopo** il recupero dei glifi: va combinata
   con il tone locale, non usata da sola.
4. Original RGB per scene colorate; Amber per scure/mono e NieR; la scelta per
   shot, non per nome.
5. La 144×81 può essere rivalutata insieme al tone locale; da sola non basta.
6. Nessuna implementazione in GUI/preset/Guess; nessun video 8 s promosso.
   Il video di riferimento resta `village_color_original_8s.mp4` (A/B 96×54).

## File

- Confronto: `_discovery/milestone5/village_abcd_compare.png`
- Emissione GN: `_discovery/milestone5/adaptive_job.py`
- A/B/C/D: `_discovery/milestone5/abcd_adapt.py`, `village_abcd_*.png`
- Griglie: `_discovery/milestone5/grid_bench/`
