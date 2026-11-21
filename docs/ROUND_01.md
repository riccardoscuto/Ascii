# Guess — Round 01 (Balatro)

Data: 2026-11-19
Stato: documento storico del round a take singolo. Il modello corrente usa quattro clip per gioco; vedi `docs/GUI.md`.

## Obiettivo

Verificare, su un singolo round, tutti gli elementi del format:

- filmato gameplay reale;
- numero bianco con contorno nero;
- reveal del titolo azzurro;
- musica placeholder;
- taglio e reveal sincronizzati al beat;
- esportazione verticale 1080x1920.

## Sorgente

Take Game Capture:

```
projects/test_a/takes/balatro/20261119_160135/take.mp4
```

- 1080x1920, 60 fps, 19,867 s, senza audio;
- MKV full-frame conservato.

## Timeline

Durata round: **10,000 s**, 30 fps, 300 frame.

| Evento | Tempo | Beat (120 BPM) |
|---|---|---|
| Inizio scena | 0,000 s | beat 0 |
| Numero “1.” | 0,500 s | beat 1 |
| Taglio clue → reveal | 4,000 s | beat 8 (downbeat) |
| Titolo “BALATRO” | 4,000 s | beat 8 |
| Fine | 10,000 s | beat 20 |

Segmenti dal take:

- clue: 1,0–5,0 s;
- reveal: 10,0–16,0 s.

Il taglio a 4,000 s coincide con l’apparizione del titolo e con il downbeat della traccia placeholder.

## Overlay

- Font: Montserrat Variable, asse Weight 800 (ExtraBold).
- Numero: bianco, contorno nero, dimensione 190 px, centro a y=800.
- Titolo: ciano `#00B7FF`, contorno nero, dimensione 120 px, centro a y=1000.
- Ombra morbida sotto entrambi.
- Numero visibile da 0,5 s; titolo visibile da 4,0 s.
- Fade-in: 0,18 s numero, 0,22 s titolo.

File generati:

```
number.png
title.png
```

## Musica placeholder

Generata localmente, 120 BPM, 10 s:

```
assets/music/placeholder_120.wav
assets/music/placeholder_120.json
```

La traccia è un click/percussione con basso ogni 2 s: serve solo a verificare il sync. Non è la musica definitiva.

Per sostituirla:

1. fornire una traccia con licenza;
2. creare la relativa beatmap;
3. aggiornare gli indici degli eventi nel preset.

## Output

```
projects/test_a/rounds/balatro_20261119_160135/
  round_01.mp4
  manifest.json
  frame_0.6.png
  frame_0.8.png
  frame_4.1.png
  frame_4.4.png
  frame_5.0.png
```

Verifica ffprobe:

- 1080x1920;
- H.264;
- 30 fps;
- 10,000 s;
- 300 frame;
- AAC 48 kHz stereo;
- 10,000 s audio.

Frame verificati:

- `frame_0.8.png`: numero “1.” bianco, contorno nero, scena Balatro.
- `frame_4.4.png`: taglio al reveal, titolo “BALATRO” ciano, contorno nero, numero ancora visibile.

## Riproduzione

Il comando del round a take singolo è stato rimosso. Il round corrente usa quattro clip per gioco:

```powershell
cd G:\VDGP
.\.venv\Scripts\python.exe -m gcf guess round --project <id> --game <titolo>
```

Dettagli in `docs/GUI.md`.

## Limiti

- Il footage Balatro è solo per il test tecnico; non va pubblicato senza verifica dei diritti.
- Il crop 9:16 taglia la sidebar sinistra e parte della mano: è il comportamento normale su un gioco 16:9. Per i giochi scenici del canale il crop sarà più naturale.
- Il titolo e il numero usano un fade, non un pop/scale completo; il preset potrà aggiungere animazioni.
- Non ci sono intro/outro né countdown: il round è isolato.
- La musica è un placeholder tecnico, non una traccia pubblicabile.

## Prossimo passo

Dopo approvazione visiva:

1. sostituire la musica placeholder con quella definitiva e la sua beatmap;
2. estendere il motore a sei giochi;
3. costruire la timeline da 60 s con intro/outro brevi;
4. generare miniatura e metadati;
5. verificare il video completo prima di qualsiasi pubblicazione.
