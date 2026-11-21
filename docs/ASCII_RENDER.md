# ASCII render — Nier Automata

Data: 2026-11-20

## Sorgente

- Video effettivamente usato dalla Geometry Nodes: `G:\ascii\Nier_Automata_-_Emil_True_Final_Boss_Fight_Secret_Boss_Ending_Y.mp4`.
- Durata reale: **301,574 s = 5,02 min**; 1920x1080, 59,94 fps.
- Nel file esiste anche un datablock `Elden Ring - Malenia...mp4` con percorso mancante (`exists=false`). Non è usato dal nodo Image Texture. Se il render deve essere Elden Ring, va fornito il file e ricablabto il nodo.

## Scena ASCII (v3)

- Grid: **80 x 45** punti; caratteri grandi e ben separati.
- Font: **Arial Bold**; dimensione carattere: 0.020 unità (circa 18-20 px a 1080p).
- Set caratteri: `" .,:;+*?%S#@&"` con spazio iniziale.
- Densità: luminanza `0.2126 R + 0.7152 G + 0.0722 B` con gamma 0.78, mappata su `String Length - 1`.
- Colore per carattere: **palette per luminanza** blu → ciano → verde → giallo → arancio → bianco; le zone scure restano nere o blu.
- Materiale: Emission con attributo `clr`, forza 1.0. Niente luci o riflessioni.
- Color management: Standard, look None, esposizione 0.

La v1 usava 160x90 con il font Blender di default ed era un puntinato quasi invisibile. La v2 ha introdotto il grassetto, ma era ancora troppo fitta. La v3 riduce la griglia a 80x45 e usa una palette ad alto contrasto: i caratteri sono leggibili anche a finestra ridotta.

## Bug corretti

1. La Image Texture usava un vettore costante: tutti i punti campionavano lo stesso pixel. Ora usa la posizione del punto normalizzata sulla griglia.
2. Il frame della Image Texture era statico (`71 + 5`). Ora `Scene Time Frame × 2`, per riprodurre il video 60 fps a 30 fps.
3. Intervallo scena corretto: **1–9036** frame a 30 fps = 301,2 s.
4. Emission 500 → 1.0: il render era completamente bianco.
5. Griglia 513x513 → 160x90: da 17,5 milioni di vertici a circa 1 milione; il render passa da secondi/minuti per frame a ~0,2-0,3 s/frame.
6. Aggiunto lo spazio all'inizio del set: le zone scure restano nere invece di riempirsi di punti.

## Render completato (v3)

- Engine: **EEVEE**, 8 campioni TAA, 1920x1080, 30 fps, 9036 frame.
- Tempo effettivo: **circa 28 minuti**.
- File di scena: `G:\VDGP\ascii\nier_ascii_5min_palette.blend`.
- Master Blender: `G:\VDGP\ascii\render\nier_ascii_5min_master.mp4` (519 MB, H.264).
- Finale con audio: `G:\VDGP\ascii\render\nier_ascii_5min.mp4` (526 MB).
- Verifica ffprobe: 1920x1080, 30 fps, **301,200 s**, 9036 frame, H.264 + AAC stereo.
- L'audio AAC è quello originale del video Nier, aggiunto con mux.
- Preview rapida: `G:\VDGP\ascii\render\nier_ascii_preview_20s.mp4`.
- Still: `nier_ascii_still_30s.png`, `nier_ascii_still_120s.png`.
- Versioni precedenti: `nier_ascii_5min_v1.mp4`, `nier_ascii_5min_v2.mp4` e relative preview.
- Backup della scena originale: `G:\VDGP\_discovery\GN_ascii_art_with_color_backup.blend`.

## Scelte di look

- Il video sorgente è volutamente seppia/desaturato; il render mantiene i colori caldi con leggera saturazione (1.3) e contrasto, senza inventare una palette diversa.
- Le zone scure restano nere grazie allo spazio nel set di caratteri.
- La densità dei caratteri segue la luminanza; le zone chiare usano H/X/W, le mezze tinte +/:/, le scure punto/virgola.
- Il risultato è più leggibile a 1080p pieno che nei preview a metà risoluzione: i caratteri occupano circa 10–12 px e vanno guardati al 100%.

## Note

- La scena interattiva originale è rimasta aperta e non è stata sovrascritta; è stata salvata una copia ottimizzata.
- Il nome dell'oggetto/mesh contiene ancora “Elden Ring” per ragioni storiche, ma il video renderizzato è Nier.
