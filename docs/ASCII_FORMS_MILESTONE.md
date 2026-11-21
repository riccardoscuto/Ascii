# ASCII forms & motion — milestone

Data: 2026-11-20
Baseline: Adaptive + B OPT, 80×45, 0.020
Frame di confronto statico: **60 s** (scena 1800, tone adattivo 0.58/0.95)
Scena C: `G:\VDGP\ascii\presets\ASCII_Cinematic_Balanced_96x54_TEST.blend`

> **Correzione 2026-11-20:** i test griglia/A-B-C-D di questa prima stesura regolavano i default dei nodi Grid/Size, ma quegli input sono pilotati dai Socket del modificatore. I file marcati 96×54/120×68 erano quindi ancora 80×45/0.020. I dati corretti sono in `docs/ASCII_C_96_VALIDATION.md` e nelle cartelle `gridgeom2` / `abcd2`. I video 5 s C/D e il +20% di churn non sono validi per 96×54 e sono deprecati.

## 1. Griglia e dimensione carattere

Il font è Bfont Regular; le celle della griglia sono quadrate. La dimensione "naturale" mantiene `Size / cell ≈ 0.90`; i valori più piccoli aumentano lo spazio negativo ma riducono l'inchiostro.

| Griglia | Cella | Size | Size/cella | Esito |
|---|---:|---:|---:|---|
| 80×45 | 0.0222 | 0.020 | 0.90 | riferimento; caratteri grandi, parete densa |
| 80×45 | 0.0222 | 0.017 | 0.77 | più spazio, simboli più distinti; soggetto più scarso |
| 80×45 | 0.0222 | 0.015 | 0.68 | troppo spazio; la parete diventa punteggiata |
| 96×54 | 0.0185 | 0.0166 | 0.90 | **migliore equilibrio** |
| 96×54 | 0.0185 | 0.0155 | 0.84 | più aria, meno massa |
| 120×68 | 0.0148 | 0.0133 | 0.90 | più dettaglio, ma rischio texture/pixel |
| 120×68 | 0.0148 | 0.0125 | 0.84 | troppo fine a dimensione normale |

Confronto: `G:\VDGP\ascii\experiments\gridgeom\gridgeom_full.png` e `gridgeom_crop.png`.

Il rapporto larghezza/altezza dei glifi è coerente con celle quadrate: il glifo visibile è più stretto della cella, quindi i side bearing lasciano spazio orizzontale. Non ci sono sovrapposizioni a 0.90; i valori 0.84/0.77 aprono il reticolo ma tolgono inchiostro. **96×54 / 0.0166** è il compromesso scelto: più celle e più forme, senza la grana fine di 120×68.

## 2. A/B/C/D sullo stesso frame (60 s)

Tutti con la stessa palette, gamma, threshold e white point adattivi; solo griglia/font/contorni cambiano.

| Versione | Griglia / Size | Cosa cambia | File |
|---|---|---|---|
| **A** Adaptive attuale | 80×45 / 0.020 | baseline | `experiments\gridgeom\80_020.png` |
| **B** Smaller glyphs | 80×45 / 0.017 | più spazio tra i simboli | `experiments\gridgeom\80_017.png` |
| **C** Higher resolution | 96×54 / 0.0166 | più celle, glifi più piccoli | `experiments\gridcritical\C_1800.png` |
| **D** Edge-aware | 96×54 / 0.0166 + edge map 0.8 | contorni direzionali | `experiments\edge\emap_s080.png` |

Confronto: `experiments\abcd\ABCD_full.png` e `ABCD_crop.png`.

Lettura:
- **B** rende i singoli simboli più distinguibili ma perde massa nel soggetto; la parete chiara resta.
- **C** è il salto utile: più celle, più gradazione, 2B e bordo dell'orbita più definiti. I caratteri restano leggibili a 1920 (celle 16 px).
- **D** aggiunge `- | / \` reali sui contorni forti, soprattutto attorno a 2B e al bordo dell'orbita; la superficie dell'orbita resta liscia.
- **C** è la scelta consigliata; **D** è un'alternativa sperimentale.

## 3. Edge-aware

### Metodo

- Mappa contorni preparata esternamente a **96×54**, la stessa griglia ASCII.
- Sobel su luminanza; R = forza del contorno (smoothstep 60→110), G = orientamento in 4 bin (`-`, `|`, `/`, `\`).
- La mappa è campionata nel Geometry Nodes come **dato**, non sovrapposta come linea: i caratteri direzionali sono veri glifi ASCII.
- Alfabeto: `" .,:;+HW@-|/\\"` — 9 livelli di luminanza (0–8) + 4 direzionali (9–12).
- `Edge Strength` regolabile; usato 0.8. La soglia è cotta nella mappa, fissa per evitare flicker da soglia adattiva.
- La palette, la griglia, il font e il tone mapping restano quelli di C.

### Risultati sui frame critici

File: `experiments\edge\CD_critical.png`, `CD_60_crop.png`, `CD_67_crop.png`.

- **52 s**: C e D leggibili; D aggiunge qualche contorno anche sull'HUD, ma il riferimento resta.
- **58,5 s**: D marca il bordo della collina/struttura; più definizione, leggero rumore.
- **60 s**: D separa meglio 2B e il bordo dell'orbita; la superficie chiara resta una parete. Nessun dettaglio inventato.
- **65,5 / 67,5 s**: D aggiunge contorni al personaggio e al fumo; l'esplosione resta un campo chiaro.
- La mappa contorni è reale e aiuta le silhouette, ma non risolve una superficie sorgente quasi uniforme.

## 4. Zoom 1.25×

Diagnostica, non applicata automaticamente. Il frame 60 è stato ritagliato 1.25× al centro e renderizzato con C 96×54.

Confronto: `experiments\edge\zoom_compare_full.png`, `zoom_compare_crop.png`.

Il soggetto diventa più grande: 2B e il bordo dell'orbita sono più leggibili. La parete dell'orbita resta. Quindi la dimensione del soggetto contribuisce, ma la mancanza di contrasto sulla superficie è il limite principale. Un reframe 1.25× può essere usato su shot eroici, non su tutto il gameplay.

## 5. Movimento

### Video

- **C — 96×54 / 0.0166**, 52–62 s, 10,0 s, 300 frame, 1920×1080, 30 fps, audio:
  `G:\VDGP\ascii\render\ASCII_FORMS_C_10s.mp4`
- **C — 5 s** (58–63 s): `ASCII_FORMS_C_5s.mp4`
- **D — edge-aware — 5 s** (58–63 s): `ASCII_FORMS_D_5s.mp4`

### Misura 5 s (150 frame, 58–63 s)

| Versione | Diff media frame | Diff p95 | Diff max | Correlazione sorgente (lag 1) |
|---|---:|---:|---:|---:|
| C 96×54 | 0,0157 | 0,0320 | 0,0421 | 0,714 |
| D edge | 0,0188 | 0,0353 | 0,0478 | 0,713 |

D aumenta il churn di circa il 20%: i contorni cambiano con l'orientamento dei bordi, non con flicker casuale, ma il risultato è più rumoroso. C segue il movimento con lo stesso 0,714 e una superficie più stabile.

### Lettura

- A 96×54 il movimento di 2B e dell'orbita è più leggibile che a 80×45; le forme non diventano una texture.
- D mantiene i contorni nel movimento, ma aggiunge caratteri direzionali sparsi e un 20% di churn in più.
- Non è stata introdotta stabilizzazione temporale aggiuntiva: il churn non è un flicker casuale.
- Il test è pensato per essere guardato senza il sorgente accanto; **C** è la versione consigliata per questo criterio.

## 6. Stato di accettazione

| Criterio | Esito |
|---|---|
| Riconoscibilità delle forme | **C** migliore di A/B; 60 s ancora limitato dall'orbita liscia |
| Leggibilità del movimento | **C** buona, correlazione 0,714; D più rumorosa |
| Estetica ASCII | C pulita; D più “a contorni” ma sparsa |
| Dettaglio fine | 96×54 è il limite utile; 120×68 troppo fine |
| 52 s preservato | Sì; D aggiunge solo piccoli contorni |
| Nessuna pixelazione | C sì; 120 no |
| Flicker eccessivo | C no; D +20% di churn |
| Preset parametrico | Sì: Grid, Size, Edge Strength; mappa contorni esterna |

**Raccomandazione:** adottare **C — 96×54 / 0.0166** come nuova baseline per questa milestone, mantenendo 80×45 come variante di confronto e l'edge-aware D come esperimento separato.

Limiti dichiarati:
- 60 s: l'orbita è una superficie chiara quasi uniforme; C/D separano 2B e il bordo, non inventano dettaglio sulla superficie.
- 67,5 s: il fumo claro resta un campo; la sorgente non offre struttura sufficiente.
- 120×68: non adottato, rischio texture/pixel.
- 96×54 ha glifi più piccoli: la compressione a basso bitrate non è stata ritestata in questa milestone; il 6 Mbps del test precedente dovrebbe reggere, ma va verificato prima della pubblicazione.

## 7. File

- Scena C: `G:\VDGP\ascii\presets\ASCII_Cinematic_Balanced_96x54_TEST.blend`
- Scena D edge: `G:\VDGP\ascii\presets\ASCII_Cinematic_EdgeAware_TEST.blend`
- Baseline Adaptive: `G:\VDGP\ascii\presets\ASCII_Cinematic_Balanced_Adaptive_TEST_48-68.blend` (preservata)
- Griglia: `experiments\gridgeom\`
- A/B/C/D: `experiments\abcd\`
- Contorni critici: `experiments\edge\CD_critical.png`
- Zoom: `experiments\edge\zoom_compare_full.png`
- Movimento: `render\ASCII_FORMS_C_10s.mp4`, `ASCII_FORMS_C_5s.mp4`, `ASCII_FORMS_D_5s.mp4`
- Mappe contorni: `ascii\tools\make_edge_map_96.py`, `make_edge_maps.py`, `make_edge_seq.py`
- Dettagli e storia: `docs\ASCII_ADAPTIVE_TONEMAP.md`, `docs\ASCII_PRESET_V1.md`

Nessun render dei 5 minuti, nessuna modifica alla GUI, nessun intervento sulla color correction generale.
