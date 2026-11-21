# ASCII color pipeline — v4

Data: 2026-11-20
Segmento di prova: Nier, **47,03–52,03 s** (150 frame a 30 fps).
Frame rappresentativo: **52,0 s** (scena 1560).

> Aggiornamento: preset B finalizzato e test esteso da 24 s in `docs/ASCII_PRESET_V1.md`.

## Riferimento BlueFox

Il progetto originale non parte da un'immagine ma da `bird_rainy.mp4` (640×360, 11,3 s): un uccello chiaro su foglie scure, con pioggia. Il render originale usa:

- griglia 128×128, `String to Curves` Size 0.010;
- font **Bfont Regular** (integrato in Blender, non Arial);
- alfabeto `" .,:+HXW"`;
- materiale Emission bianco, forza 1.0;
- fondo nero.

La leggibilità del riferimento nasce dal **contrasto della sorgente**: il soggetto è più chiaro dello sfondo. Il nostro frame Nier è l'opposto: sabbia chiara e foschia occupano la maggior parte dell'immagine, il boss è appena più chiaro della sabbia e il personaggio è una sagoma scura. Da qui il problema della "parete di simboli".

## Cosa non funzionava

1. **Gamma 0.78 usato come unico controllo**: per valori < 1 il gamma *schiarisce* le ombre, quindi le zone scure ricevevano comunque caratteri. Con la soglia a 0.10 non c'era separazione.
2. **Nessun punto di bianco**: la foschia a ~0.65–0.75 veniva mappata a metà rampa, riempiendo l'immagine di `H`/`W`.
3. **Arial Bold**: molto più pesante di Bfont; a 80×45 ogni cella sembrava piena.
4. **Rampa con passi ambigui**: `?`, `%`, `S`, `#`, `&` hanno coperture vicine; `X` e `H` sono quasi identici (0.087 vs 0.088) e dominavano.
5. **Colore slegato dalla densità**: la palette era guidata dalla luminanza grezza, il carattere dal gamma. Colore e densità potevano contraddirsi.

## Pipeline attuale

```text
Image Texture
  ├─ 4 campioni per cella (±1/4 cella) → media → colore medio
  └─ punto centrale
        ↓
  luminanza media + 0.20 × (centro − media)     contrasto locale
        ↓
  Shadow Mask: [soglia, punto bianco] → [0, 1]  soglia su luminanza originale
        ↓
  Gamma (potenza)                               > 1 scurisce
        ↓
  Contrast (Map Range SMOOTHSTEP)               finestra bassa/alta
        ↓
  Tone  ────────────────┬───────────────────────┐
                        ↓                       ↓
  Map Range → Instance Index            Palette.Fac → colore
  (String Length − 1)                   (stesso Tone)
```

Punti chiave:

- La soglia ombre è applicata **alla luminanza originale, prima del gamma**.
- Il gamma non è più l'unico controllo: c'è un punto di bianco e una S-curve.
- **Un solo valore `Tone` guida sia il carattere sia il colore**: la densità e la tinta non possono divergere.
- Il colore RGB (modalità Original) usa lo stesso `Tone` come base di luminanza: `Saturation(tone, colore medio)`.
- L'alfabeto è letto con la copertura reale del font: `" .,:;+HW@"`. `X` è stato rimosso perché duplicava `H`; `;` ammorbidisce il passaggio tra `.` e `+`.
- Font **Bfont Regular**, lo stesso del riferimento.
- **Dither deterministico per cella** (±0.03–0.06 di Tone, seed fisso): rompe la griglia regolare senza introdurre sfarfallio, perché dipende dall'indice del punto, non dal frame.
- 4 campioni per cella: riducono il rumore e lo sfarfallio rispetto al singolo pixel.

## Tre varianti

Tutte in modalità Cinematic, stesso segmento e stesso frame.

| | A — Soft Amber | B — Balanced | C — High Detail |
|---|---|---|---|
| Ruolo | più mezzitoni | **consigliata** | più dettaglio |
| Griglia | 80×45 | 80×45 | 96×54 |
| Glyph Size | 0.020 | 0.020 | 0.017 |
| Font | Bfont Regular | Bfont Regular | Bfont Regular |
| Rampa | `" .,:;+HW@"` | `" .,:;+HW@"` | `" .,:;+HW@"` |
| Soglia ombre | 0.24 | 0.30 | 0.32 |
| Punto bianco | 0.95 | 0.95 | 0.94 |
| Gamma | 0.80 | 0.82 | 0.85 |
| Finestra contrasto | 0.16–0.84 | 0.18–0.82 | 0.18–0.82 |
| Contrasto locale | 0.22 | 0.20 | 0.22 |
| Dither | 0.05 | 0.06 | 0.03 |
| Palette | ambra calda | ambra calda | oro neutro |
| Frame | `final_A_soft_still.png` | `final_B_balanced_still.png` | `final_C_detail_still.png` |
| Video | `grade_A_soft_5s.mp4` | `grade_B_balanced_5s.mp4` | `grade_C_detail_5s.mp4` |
| Scena | `preset_A_soft.blend` | `preset_B_balanced.blend` | `preset_C_detail.blend` |

Confronto: `final_compare_4up.png` (sorgente + A/B/C).
Confronti singoli: `final_source_vs_A.png`, `final_source_vs_B.png`, `final_source_vs_C.png`.
Stabilità: `final_flicker_grid.png` (0.3 / 2.5 / 4.7 s per ogni clip).

## Palette

Famiglia calda NieR, usata da A e B:

| Tone | Colore |
|---:|---|
| 0.00 | nero |
| 0.05–0.12 | marrone quasi nero |
| 0.24–0.36 | marrone scuro |
| 0.48–0.60 | ambra bruciata |
| 0.70–0.79 | arancio/oro |
| 0.87 | oro chiaro |
| 0.94–1.00 | crema |

C usa una variante con ombre più neutre e oro più alto, per mostrare che la palette non è vincolata a NieR.

La palette è guidata dallo stesso `Tone` della densità. Il risultato è volutamente **monocromatico caldo**: la profondità viene da nero → marrone → ambra → oro → crema, non da hue diversi. Per un altro gioco si cambiano gli stop della ColorRamp o si usa `Palette Mix` verso la palette fredda.

## Dati misurati

Su miniature 480×270, pixel non neri:

| Versione | Non neri | Saturazione media | Luminanza media |
|---|---:|---:|---:|
| Sorgente 52 s | 100% | 0.206 | 0.591 |
| A soft | 24.0% | 0.722 | 0.232 |
| B balanced | 16.4% | 0.751 | 0.204 |
| C detail | 11.5% | 0.699 | 0.190 |

Lettura: l'immagine finale è per l'83,6% nera (B). I caratteri superstiti sono saturi e caldi, ma occupano solo il 16% del frame; la profondità è nella grande area nera, non nel colore.

La saturazione alta è quella della palette, non della sorgente: i caratteri sono colori pieni, il fondo è nero. Non è un RGB fedele.

## Sfarfallio

Controllati tre fotogrammi per clip (0.3, 2.5, 4.7 s) in `final_flicker_grid.png`.

- I caratteri cambiano con la luminanza, in modo continuo.
- Il dither è fisso per cella: non lampeggia tra i frame.
- Il colore segue il Tone: le variazioni di tinta sono variazioni di luminanza, non rumore.
- Non si osservano cambi casuali di simbolo a parità di luminanza.

Resta un limite fisico: quando la camera entra nella superficie liscia dell'orbita, una superficie chiara e uniforme diventa un campo denso e regolare. È il comportamento corretto di un mapping per luminanza, ma è il punto più "texture" del segmento.

## Preset riutilizzabile

Le scene `preset_*.blend` hanno i parametri esposti sul modificatore Geometry Nodes dell'oggetto `video`. In Blender 5.3 l'accesso è:

```python
obj = bpy.data.objects["video"]
mod = obj.modifiers["GeometryNodes"]
ins = mod.properties.inputs

ins.Socket_0.value  = 80         # Grid X
ins.Socket_1.value  = 45         # Grid Y
ins.Socket_2.value  = 0.020      # Glyph Size
ins.Socket_3.value  = " .,:;+HW@" # Character Ramp
ins.Socket_4.value  = 0.30       # Shadow Threshold
ins.Socket_5.value  = 0.95       # White Point
ins.Socket_6.value  = 0.82       # Gamma
ins.Socket_7.value  = 0.18       # Contrast Low
ins.Socket_8.value  = 0.82       # Contrast High
ins.Socket_9.value  = 0.20       # Local Contrast
ins.Socket_10.value = 1.5        # Saturation
ins.Socket_11.value = 1.2        # Exposure
ins.Socket_12.value = 1.0        # Color Mode: 0 RGB, 1 Cinematic
ins.Socket_13.value = 0.06       # Dither Amp
ins.Socket_14.value = 0.0        # Palette Mix: 0 warm, 1 steel
```

Gli identificativi `Socket_N` sono quelli dei file attuali. Per una lettura robusta, mappare prima i nomi dall'interfaccia:

```python
ids = {i.name: i.identifier for i in mod.node_group.interface.items_tree
       if i.in_out == "INPUT" and i.item_type == "SOCKET"}
ins = mod.properties.inputs
getattr(ins, ids["Shadow Threshold"]).value = 0.30
```

Nota: in Blender 5.3 il vecchio `mod["Socket_4"]` non funziona; il contenitore è `mod.properties.inputs`.

Il font e gli stop delle palette restano nodi interni (Bfont Regular, ColorRamp `Palette` / `Palette Steel`). Il resto è pilotabile senza aprire i nodi.

## File

- Scena consigliata: `experiments\preset_B_balanced.blend`
- Altre: `experiments\preset_A_soft.blend`, `experiments\preset_C_detail.blend`
- Lavoro: `experiments\variants.blend`
- Video: `experiments\grade_A_soft_5s.mp4`, `grade_B_balanced_5s.mp4`, `grade_C_detail_5s.mp4`
- Still: `experiments\final_A_soft_still.png`, `final_B_balanced_still.png`, `final_C_detail_still.png`
- Confronti: `experiments\final_compare_4up.png`, `final_source_vs_B.png`, `final_flicker_grid.png`
- Sorgente: `G:\ascii\Nier_Automata_-_Emil_True_Final_Boss_Fight_Secret_Boss_Ending_Y.mp4`

## Limiti e prossimo passo

- Nier 52 s: sabbia e boss hanno luminanza vicina. Il boss si legge più come bordo/alone che come massa piena. Una curva più aggressiva lo scolpisce ma svuota la scena.
- 80×45 è più leggibile ma grosso; 96×54 è più fine ma la foschia liscia diventa un reticolo di `+`.
- Il segmento 47–52 s è scelto per composizione (due orbite, personaggio, terreno scuro); non è un giudizio sul resto della boss fight.
- Nessun render completo: si aspetta la scelta di A/B/C.

Dopo l'approvazione: scegliere la variante, rifinire la palette su 2–3 frame chiave, poi un test più lungo (20–30 s) prima del render completo.
