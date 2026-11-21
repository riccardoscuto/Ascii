# Nuovo Video ASCII — flusso in app

Data: 2026-11-20

Primo milestone: import MP4, preset v2, anteprima, render completo e MP4 finali senza aprire Blender.

## Percorso nell'interfaccia

Home -> **Nuovo Video ASCII**. Il Guess Generator resta invariato; i progetti `ascii_*` sono esclusi dalla lista "Progetti recenti" del Guess. La riga **Riapri progetto** carica un progetto ASCII esistente e permette di riprendere il rendering dopo aver chiuso l'app.

## Pipeline

1. `gcf/ascii/media.py` sonda la sorgente con FFprobe, taglia l'eventuale intervallo, applica crop/reframe 16:9 o 9:16 e scala a 1920x1080 o 1080x1920 a 30 fps. La sorgente originale non viene mai modificata.
2. `gcf/ascii/tone.py` estrae un'analisi a 10 fps e genera un piano adattivo nuovo per quella sorgente (nessun override o keyframe Nier).
3. `gcf/ascii/blender_job.py` lavora su una **copia temporanea** `projects/<id>/temp/preset_work.blend`: sostituisce `Image Texture.001`, cancella le vecchie azioni, imposta i Socket reali del modifier, crea i keyframe shadow/white e verifica i valori.
4. Il render produce una sequenza PNG in `projects/<id>/frames/` (anteprima separata in `preview_frames/`).
5. `render.py` codifica master H.264 CRF 12 e YouTube H.264 1080p/30 fps AAC 48 kHz, bitrate predefinito 8 Mbps (regolabile 6-20). La durata viene forzata a frame/30 e l'audio viene paddato, cosi l'ultimo frame non viene perso.

## Formati

- Orizzontale: griglia 96x54, piano 1.775625 x 0.999647, 1920x1080.
- Verticale: griglia 54x96, piano invertito 0.999647 x 1.775625, 1080x1920; il reframe avviene sulla sorgente prima dell'ASCII, senza stirare.
- La UV del piano viene ricalcolata per il formato: la v2 orizzontale usa `(1/plane_x, 1/plane_y)` + offset `(0.5, 0.5)`; senza questo il verticale ripeteva l'immagine.

## Verificato

- Orizzontale `bird_rainy.mp4` (640x360, 23,976 fps, 11,34 s, audio): anteprima 4 s e render completo 340 frame; master e YouTube 1920x1080 30 fps con audio AAC stereo.
- Verticale take Witcher 3 (1080x1920, 60 fps, 4,35 s, senza audio): 130 frame, 1080x1920 30 fps, nessuna ripetizione; il file finale è muto perché la take non ha audio.
- Flusso GUI su intervallo 2-4 s: anteprima + render completo dall'interfaccia, 60 frame, master e YouTube con audio.
- Parametri verificati dal job: grid 96x54 o 54x96, glyph 0.01666, gamma 0.82, contrasto alto 0.85, color mode 1, scala frame = fps sorgente / 30, offset = 1 - scala.
- Stop: il processo Blender viene terminato; i frame restano. Al riavvio il render riparte dal primo frame mancante e scarta un ultimo PNG troncato.
- Test: `tests/test_ascii.py` (griglia, crop, fps frazionari, piano adattivo, ripresa).

## Limiti noti

- L'anteprima è di 4 s (massimo 120 frame); il resto si controlla col frame singolo.
- Il verticale è stato validato su una take 9:16 reale; altre inquadrature possono richiedere un reframe manuale.
- Non è stato eseguito un render da 5 minuti in questa fase.

Il collaudo end-to-end e le prestazioni sono in `docs/ASCII_MILESTONE2.md`.
