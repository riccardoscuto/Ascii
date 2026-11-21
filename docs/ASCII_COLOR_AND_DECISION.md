# Colore e semplificazione — esito e decisione

Data: 2026-11-21

## 1. Confronto colore (stessi indici ASCII)

Villaggio 33 s, B lineare, rampa 8 caratteri, griglia/font invariati.

| Variante | Esito |
|---|---|
| **A — Cinematic Amber** | cielo, pietra, terra e vegetazione fusi nella stessa ambra; edifici difficili |
| **B — Original RGB** | cielo blu, erba verde/gialla, pietra e tetti caldi; separazione netta; **migliore** |
| **C — Adaptive Color** | Original + 15% bianco: ombre più visibili, colori leggermente più chiari |

Il colore è l'elemento che mancava: a parità di glifi, B rende immediatamente
distinguibili cielo, terreno, alberi e costruzioni. C è utile sulle ombre ma
desatura leggermente; B resta il riferimento naturale.

Frame comparativo: `_discovery/milestone5/village_color_compare.png`
Video A/B: `_discovery/milestone5/village_color_ABC_8s.mp4` (sorgente | Amber | Original)
Solo Original: `_discovery/milestone5/village_color_original_8s.mp4`

La pipeline colore non richiede nuove geometrie: `Color Mode = 0` e il colore
della cella. La palette Amber va mantenuta per NieR/mono; per scene ricche di
colore il modo Original/Adaptive è la scelta corretta. La selezione automatica
può usare saturazione e varietà di hue per shot (non implementata).

## 2. Semplificazione

Provati `guided` (radius 10, eps 0.02) e `bilateral` (sigmaS 20, sigmaR 0.25,
solo luma) prima del campionamento. Il risultato ASCII è molto simile a B senza
preprocessing: nuvole e prato restano complessi, i contorni non migliorano in
modo percepibile. La semplificazione non viene adottata.

## 3. Cosa resta

Il colore migliora la separazione, ma castello, tetti e case restano una
silhouette scura dentro un campo di glifi. Se questo non basta, le opzioni
strutturali sono:

| Opzione | Vantaggi | Limiti | Costo | Modifiche BlueFox |
|---|---|---|---|---|
| Griglia adattiva più densa (es. 144×81) | più dettaglio dove serve | cambia look/glyph, non risolve da sola il cielo | ~2,25× istanze | preset alternativo, grid/glyph, nessun cambio di materiale |
| Subcell ASCII 2×2 | bordo + superficie nella stessa cella, 4× risoluzione | glifi piccoli, selezione complessa | ~4× istanze | nuovo ramo GN, griglia 2×2, maschere/selezione, glyph size |
| Due livelli geometrici (silhouette + tonal) | contorni continui espliciti | priorità, flicker, compositing | ~2× istanze | due sistemi di istanze/materiale, regole di priorità |
| Atlante tipografico più ricco (box drawing, blocchi) | più forme per cella | non è più ASCII puro; cambia font/rampa | ~1× | font/atlas, ramp, palette |
| AI/upscaling | qualità potenziale | costo, non deterministico, vincolo esplicito | alto | fuori scope |

Stima attuale: ~0,2 s/frame a 96×54. 2×2 ≈ 0,8 s/frame; 144×81 ≈ 0,45;
due livelli ≈ 0,4. Per 60 s a 30 fps: ~6-7 min oggi, ~25 min con 2×2.

## 4. Generalizzazione rapida (5 scene)

Confronto A/B/C su villaggio, foresta, scuro, NieR e Balatro (frame 33/44/54/52/2):

- **Villaggio**: B Original vince; A Amber fonde gli oggetti.
- **Foresta/scuro/NieR/Balatro**: B/C Original senza emissione perdono i glifi scuri
  (nero su nero); A Amber resta leggibile. Non è una regressione del colore:
  è l'assenza di un livello di emissione per i glifi scuri.
- L'adattamento per-cellula provato (+lift se index>=1) non ha cambiato il
  villaggio (le zone scure non hanno glifi) né le scene scure; serve un
  controllo di emissione **nel Geometry Nodes**, agganciato all'indice del
  glifo, con floor e protezione alte luci.
- La semplificazione guided/bilateral non migliora in modo percepibile.

Conclusione: **Original RGB non è universale**. Il selettore deve scegliere per
shot: Original per scene luminose e colorate, Amber per scene scure/mono e per
NieR; l'emissione adattiva va integrata nel renderer, non nel colore sorgente.
La scelta non può basarsi sul nome del gioco.

## 5. Benchmark griglie

Frame del villaggio, preset v2, 1 frame, EEVEE:

| Griglia | Glifi | Tempo/frame |
|---|---:|---:|
| 96×54 | 5.184 | ~0,19 s |
| 144×81 | 11.664 | ~0,20 s |
| 192×108 | 20.736 | ~0,23 s |

Il costo del renderer è quasi indipendente dal numero di glifi a questi livelli;
il limite è la qualità, non il tempo. La griglia 192×108 produce più dettaglio
ma glifi da 10 px; la 144×81 è il compromesso. Il subcell 2×2 ha lo stesso
numero di glifi della 192×108 ma richiede selezione/geometria aggiuntiva: non
è automaticamente superiore.

## 6. Raccomandazione finale

1. **Colore**: Original RGB per scene luminose/colorate; Amber per scene
   scure/mono e NieR. La scelta va fatta sul rendering ASCII (luminanza media
   dei glifi, saturazione, clipping), non sul nome del gioco.
2. **Emissione**: implementare nel GN un floor di luminanza per i glifi con
   indice > 0 e protezione delle alte luci; il lift per-cellula sul video non
   basta. Non è stato implementato.
3. **Dettaglio**: la griglia 144×81 è il primo prototipo strutturale da
   provare, non il subcell 2×2: costa ~5% in più e non richiede nuova
   architettura di selezione. La 192×108 è l'alternativa se serve più dettaglio.
4. **Subcell 2×2**: stessa cardinalità della 192×108; va dimostrato il vantaggio
   prima di implementarlo.
5. **Due livelli**: utile solo per la continuità delle silhouette; costo ~2×;
   dopo la prova della griglia.
6. Nessuna implementazione in questa fase: GUI, preset v2 e Guess invariati.

## File

- Confronto colore villaggio: `_discovery/milestone5/village_color_compare.png`
- Video: `_discovery/milestone5/village_color_ABC_8s.mp4`,
  `village_color_original_8s.mp4`
- Confronto multi-scena: `_discovery/milestone5/scenes/` e
  `scene_*_B/C.png`
- Benchmark: `_discovery/milestone5/grid_bench/`
- Test colore: `_discovery/milestone5/color_test/`
- Semplificazione: `_discovery/milestone5/simplify_test/`
- Indici/colore: `color_test.py`, `color_job.py`, `color_video.py`,
  `scene_color.py`
