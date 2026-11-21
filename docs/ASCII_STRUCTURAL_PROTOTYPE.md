# Prototipo renderer strutturale — esito

Data: 2026-11-21

## Architettura provata

- Griglia 96×54, font Bfont, palette Cinematic Amber, 1920×1080.
- **Tonal**: normalizzazione dai percentili **lineari** (B), con la rampa
  `" .,:;=+-*/\\|HW@"`.
- **Silhouette**: luma B sfocata a 5 celle, contorni forti, componenti connesse
  di almeno 8 celle; solo quei contorni usano `|`, `-`, `/`, `\`.
- **Glyph matching**: per ogni cella, patch 8×8 (blur 1) confrontata con le
  maschere 8×8 dei 15 glifi rasterizzati dal renderer; similarità di forma +
  penalità di copertura tonale; soglia di confidenza.
- **Combinazione**: silhouette dove c'è un contorno affidabile, altrimenti
  matching, altrimenti tonale.
- Gli indici sono preparati esternamente e iniettati in Geometry Nodes tramite
  una seconda Image Texture; Blender resta il renderer dei glifi.

## Verifica degli indici

- Atlas di 15 glifi renderizzato dal preset; maschere estratte dalle celle.
- Test strip con indici 0..14: il render mostra la sequenza `: - = * / \ | H W @`
  nell'ordine previsto. L'iniezione degli indici funziona.
- La luma tonale è calcolata in **lineare** (shadow 0,0058, white 0,6355,
  gamma 0,85, low 0,02, high 0,90): coerente con il modifier.

## Confronto

`_discovery/milestone5/village_struct_compare.png`

| Variante | Esito |
|---|---|
| A — B lineare | 73,2% visibile; struttura, cielo denso |
| B — silhouette | cielo a slash, edifici quasi neri; non leggibile |
| C — glyph matching 8×8 | pattern di glifi; non emergono le forme |
| D — combinazione | non aggiunge riconoscibilità |

Nessuna variante rende castello, tetti, case e separazione cielo/terreno
distinguibili senza la sorgente. Il test statico è fallito; non è stato
prodotto un video strutturale da 8 s. Il video B lineare resta il riferimento
tonale (`village_ABC_8s.mp4`).

## Perché fallisce

- La cella 96×54 copre 20×20 px: una cella sul bordo contiene insieme cielo
  luminoso e parete scura. Un solo glifo non può rappresentare entrambi.
- La silhouette media le nuvole: con blur 5 celle e componenti ≥8 restano
  abbastanza contorni di cielo da riempire la parte alta di `/`; gli edifici
  scuri restano pochi glifi.
- Il glyph matching 8×8 sceglie forme coerenti con il patch, ma la forma del
  glifo occupa comunque l'intera cella; il risultato è un pattern, non una
  silhouette continua.
- La rampa/font a 20 px ha una copertura limitata: `H/W/@` sono molto densi,
  `/\|` sono sottili; il compromesso tonale tende a favorire i secondi o a
  lasciare neri gli interni.

## Modifica strutturale necessaria

Non un altro parametro. Serve una delle seguenti:

1. **Subcell / più glifi per cella** (es. 2×2 subglifi) per rappresentare
   insieme bordo e superficie, senza aumentare la griglia globale.
2. **Due livelli reali**: silhouette continua + tonal, con priorità locale e
   continuità tra celle; la sola sostituzione di un glifo per cella non basta.
3. **Set di glifi più ricco** con forme di copertura intermedie e maschere
   progettate per la cella, non solo i caratteri del font corrente.
4. **Griglia più alta solo per scene ricche**, come opzione, non come default.

La correzione sRGB→lineare è necessaria e va mantenuta, ma non è sufficiente.
Il prototipo non viene promosso; nessuna modifica a GUI, preset o pipeline di
produzione.

## File

- Indici: `_discovery/milestone5/structural_indices.py`
- Iniezione GN: `_discovery/milestone5/shape_job2.py`
- Maschere: `_discovery/milestone5/masks/`
- Confronto: `_discovery/milestone5/village_struct_compare.png`
- Test indici: `_discovery/milestone5/shape/test_render/f_0001.png`
- Video tonale B: `_discovery/milestone5/village_ABC_8s.mp4`
