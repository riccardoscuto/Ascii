# Milestone 2 — collaudo end-to-end

Data: 2026-11-20

## Sorgenti usate

- **Gameplay 63,34 s**: concatenazione senza ricodifica di sei registrazioni reali 1920x1080 60 fps gia presenti nei progetti (Balatro 19,9 s + cinque take The Witcher 3). Le tracce audio OBS sono presenti ma **mute** (-91 dB): la presenza dell'audio e la sincronizzazione con contenuto reale sono state verificate nel test 4 con beep sintetici.
- **Witcher 210933**: 1920x1080 60 fps, 6,28 s, per il test 16:9 -> 9:16.
- **Sorgenti sintetiche** 1280x720 a 23,976 / 30 / 59,94 / 60 fps con flash bianco e beep a 1, 3, 5 s.

## Test 1 — gameplay lungo, dalla GUI

| Voce | Valore |
|---|---|
| Sorgente | 1920x1080, 60 fps, 63,34 s, audio presente (muto) |
| Anteprima | 51,0 s (include preparazione sorgente e analisi) |
| Frame renderizzati | 1900 / 1900 |
| Durata master | 63,333333 s = 1900 / 30 |
| Master | 1920x1080, 30 fps, H.264 CRF 12, AAC 48 kHz stereo, 12,5 MB |
| YouTube | 1920x1080, H.264 ~3,2 Mbps, AAC 48 kHz stereo, 24,1 MB |
| Frame validi | 1900, tutti PNG integri, contigui, 1900 hash distinti |
| Parametri | 96x54, glyph 0,01666, scala 2,0 / offset -1,0, 6 intervalli e 5 tagli nel piano |

Output: `projects/ascii_20261120_184044/output/master.mp4` e `youtube.mp4`.
Still di controllo: `_discovery/milestone2/final_sync_master_*.png`.

Inizio e metà corrispondono alla sorgente. La coda (ultimi ~14 s) e una registrazione molto scura di The Witcher 3: il preset v2 con shadow 0,234 produce pochi caratteri e la scena risulta quasi nera. Non e un errore di sincronizzazione (i pochi glifi seguono le zone luminose della sorgente), ma un limite del look v2 sul materiale molto scuro.

## Test 2 — stop e ripresa

- Stop dal pulsante dopo 240 frame: fermato a **242 frame**, ultimo PNG valido, processo Blender del job terminato (`blender_job.py` assente).
- UI utilizzabile durante il render: latenza massima misurata 102,8 ms per ciclo eventi.
- Chiusura e riapertura dell'app: progetto riaperto dalla lista, **242/1900** frame presenti, rendering ripreso dal frame 243 e completato.
- Chiusura dell'app **durante** un render: chiusura in 1,7 s, processo Blender terminato, 32 frame conservati, riapertura e ripresa fino a 180/180.
- Un PNG troncato viene scartato e rieseguito: coperto da `tests/test_ascii.py` e dal caso reale osservato prima della correzione.

## Test 3 — 1920x1080 -> 1080x1920

- Sorgente 1920x1080 60 fps, 6,28 s.
- Working source: crop centrale 608x1080 -> 1080x1920 (prima dell'ASCII), nessuna deformazione.
- Griglia 54x96, glyph 0,01666, piano invertito.
- Master: 1080x1920, 30 fps, 188 frame, 6,266667 s, audio presente (muto).
- Nessuna ripetizione di immagine; il soggetto centrale resta nel crop.
- Limite: il crop centrale taglia il panorama laterale (montagna a destra). Un editor di reframe resta una milestone separata.

Output: `projects/ascii_20261120_185055/output/master.mp4`.

## Test 4 — frame rate e audio

Sorgenti 6 s, 180 frame attesi a 30 fps. Flash bianco e beep a 1 / 3 / 5 s.

| Sorgente | Scala / offset | Frame | Durata | Flash (s) | Beep (s) |
|---|---|---:|---:|---:|---:|
| 23,976 | 0,799201 / 0,200799 | 180 | 6,000 | 1,033 | 1,00 |
| 30 | 1,0 / 0,0 | 180 | 6,000 | 1,000 | 1,00 |
| 59,94 | 1,998002 / -0,998002 | 180 | 6,000 | 1,033 | 1,00 |
| 60 | 2,0 / -1,0 | 180 | 6,000 | 1,000 | 1,00 |

Lo scarto massimo video/audio e di **1 frame (33 ms)**, dovuto alla quantizzazione del flash nella sorgente; nessuna deriva accumulata sui tre eventi.

Intervallo 1,5-4,5 s dalla GUI: 90 frame, 3,000 s, flash e beep a 1,5 s. Il ritaglio parte da 1,5 s, la durata e 3,0 s e l'audio resta allineato.

## Test 5 — qualita e prestazioni

- Frame renderizzati: 1900; tempo per frame medio **0,183 s**, mediana 0,182, p95 0,218, massimo 0,79; **5,47 fps**.
- Nessun rallentamento progressivo: prima meta 0,194 s/frame, seconda 0,171 s/frame.
- RAM processo Blender del job: 0,94 -> 1,03 GB working set; picco privato 3,95 GB.
- VRAM di sistema: 4,99 -> 5,01 GB, picco 5,62 GB su 8 GB (include altre istanze Blender dell'utente).
- Disco: frame 1,42 GB (1900 PNG), preview_frames 94 MB, analisi 53 MB, sorgente 65 MB, output 36,6 MB.
- Stima 5 min: 9000 frame x 0,183 s ~ **27,5 min** di render, ~6,7 GB di PNG temporanei, piu preparazione e codifica.

## Correzioni applicate

1. **Ultimo frame perso nella codifica**: `-shortest` tagliava il video alla durata dell'audio (un frame in meno). Ora la codifica usa `-t = frame/30` e `apad` sull'audio; master e YouTube hanno esattamente 1900 frame e 63,333333 s.
2. **Ripresa**: il render riparte dal primo frame mancante anche dopo chiusura e riapertura dell'app (nuova lista "Riapri progetto" nella pagina ASCII); un PNG troncato viene eliminato e rifatto.

## Problemi residui

- Il preset v2 schiaccia le ombre: su una scena molto scura (media 0,06) l'ASCII diventa quasi nero. Il piano adattivo abbassa lo shadow solo fino a 0,234 per il blend 60/40 col base 0,31. Da decidere nella prossima fase: abbassare il floor o dare piu peso allo shot.
- Le registrazioni gameplay disponibili hanno audio OBS muto; la sincronizzazione con audio reale e coperta dal test 4 e dal test bird precedente.
- Il filmato da 63 s e una concatenazione di take reali, non una sessione continua; i tagli sono utili come stress test ma non sostituiscono un gameplay unico da 60 s.
- Il pulsante "Interrompi" disabilitato non cambia aspetto (solo rifinitura UI).
