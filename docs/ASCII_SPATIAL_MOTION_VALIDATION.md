# ASCII Spatial Tone Mapping — Validazione dinamica

Data: 2026-11-21
Ambito: C 144×81 globale vs D 144×81 spaziale, stesso font, palette, glyph size, risoluzione e sorgente.
Nessuna modifica a preset v2, GUI o Guess Generator. Nessun selettore automatico implementato.

## 1. Verifica della sorgente

I 240 PNG originali del villaggio sono stati confrontati per hash e differenza pixel.

| Sorgente | Frame | SHA1 unici | Diff mediana | Diff media | Diff max |
|---|---:|---:|---:|---:|---:|
| Villaggio 30–38 s | 240 | **51** | 0.0038 | 0.442 | 68.775 (cut, frame 18) |
| Bird/rain (proxy) | 240 | 192 | 5.6846 | 5.4291 | 19.505 |
| Foresta fade/flash | 240 | 237 | 2.2133 | 5.293 | 226.725 (flash) |
| Scura dark/flash | 240 | 235 | 0.0007 | 4.405 | 248.87 (flash) |

Il villaggio contiene 189 frame byte-identici su 240. Non è un errore di associazione o di
sequenza: i duplicati sono già nei PNG sorgente. La differenza pixel mediana è 0.0038/255,
contro 5.68/255 del bird: il villaggio è fermo, il bird è movimento reale. Gli hash unici
da soli non bastano (il rumore di codifica li rende tutti diversi); la differenza pixel
distingue il rumore dal movimento.

L'associazione sorgente → tono → indici → render è verificata dal manifest SHA1 per frame
e dal validatore (`C_validation.json`, `D_validation.json`). Sul bird lo shift 0 vince
185/238 (C) e 187/238 (D) contro i vicini; sul villaggio fermo lo shift test non è
significativo, ma il cut al frame 18 e il bird positivo coprono la sincronizzazione.

## 2. C/D a parità di griglia

- 144×81, 1920×1080, 30 fps, 240 frame (8 s), glyph 0.0111.
- C: indice globale esterno. D: indice spaziale con target fissato alla mediana della scena.
- Bird e foresta: Original RGB. Scura: Amber. Il colore è identico dentro la coppia C/D.
- La matrice a 144×81 isola il tone mapping; A 96×54 resta solo il riferimento approvato.

File: `motion_validation/<test>/C.mp4`, `D.mp4`, `CD.mp4`.
Bird: `bird/CD.mp4` (C|D) e `bird/D.mp4` (solo ASCII).
Foresta: `fade/CD.mp4`, `fade/D.mp4`.
Scura: video respinti in `dark/rejected/` (vedi sotto).

## 3. Movimento reale — bird/rain (proxy, non gameplay)

Il workspace non contiene gameplay con movimento evidente: i montaggi 63/69 s sono
inquadrature ferme, i round e i demo 60 s sono quiz statici, i take sono alberi/close-up
verticali o registrazioni di file explorer. L'unico movimento reale disponibile è il
bird/rain, usato come proxy di stress e dichiarato come tale.

Misure (240 frame):

- luminanza media: sorgente 65.50–78.82; C 5.58–9.52; D 7.90–12.40;
- correlazione sorgente: C 0.776, D 0.827; C/D tra loro 0.984;
- delta indici mediano: C 0.197, D 0.232 livelli glifo; massimo 0.683/0.771;
- 0 frame neri;
- validatore PASS: correlazione indice/render 0.826 (C), 0.832 (D);
- delta |D−C| medio 0.635 livelli; sui frame 60 e 120 la differenza è concentrata su
  uccello, mangiatoia e sfondo, non forma una zona staccata che si muove da sola.

Ispezione visiva: la silhouette dell'uccello resta continua; D aggiunge corpo e piumaggio
senza alone evidente. Non è una prova su gameplay, ma è una prova di movimento reale con
un soggetto che cambia posizione e un fondo in movimento (pioggia).

## 4. Foresta — rampa di luce e flash

- sorgente: rampa graduale e due flash brevi ai frame 62–63 e 152–153 (2 frame = 67 ms);
- C/D: 0 frame neri;
- correlazione sorgente: C 0.838, D 0.894;
- delta indici mediano: C 0.0765, D 0.1105;
- ai flash C e D salgono a 107.27 di media e tornano a 0.27/0.34 nei frame successivi,
  senza afterglow;
- validatore PASS con warning atteso per tono piatto durante il flash.

La clip è una registrazione con controlli del player in basso: l'artefatto è nella sorgente
ed è presente in C e D. Non è un artefatto del tone mapping.

## 5. Scena scura — risultato negativo

Con tone fisso, C e D producono 233/240 frame neri (medie 0.11–0.12, solo i flash a 107).
Il validatore FAIL su frame neri e tono piatto al flash. I video sono stati spostati in
`dark/rejected/` e non sono materiale approvato.

Conclusione: D non è applicabile alle scene scure senza la correzione M3/Amber. La regola
di selezione deve escluderle; il risultato conferma la decisione precedente.

## 6. Controlli automatici

`validate_render.py` verifica, frame per frame:

- sequenza completa e numerazione `f_0001…f_0240` / `i_…` / `t_…`;
- livelli indice nell'intervallo 0–255 e nelle 9 classi attese (0, 32, 64, 96, 128, 160,
  192, 223, 255);
- manifest SHA1 di sorgente, tono, indice e render;
- correlazione indice/render per frame e test di shift −1/0/+1;
- correlazione luminanza sorgente/render;
- frame neri non giustificati;
- proof del job: griglia, fps, risoluzione, offset 0, scala 1, sRGB sorgente, Non-Color indici.

Esito: bird C/D PASS, foresta C/D PASS, scura C/D FAIL. Il FAIL della scura è la
segnalazione diagnostica richiesta: il video nero non passa il gate.

## 7. Gate provvisorio (prima del clip gameplay)

**Provvisorio: non superato per il movimento gameplay.** I test disponibili passano
tecnicamente (bird proxy, foresta fade/flash) e D resta stabile, ma mancava la prova
richiesta su un clip 8–12 s di gameplay con movimento evidente. Il clip è stato poi
trovato e il gate è completato nella sezione 8.

La scena scura conferma che D non è universale: M3/Amber resta il percorso approvato.
Nessuna GUI, preset o selettore è stato modificato.

## 8. Gate gameplay reale — Nier 10.01 s

Clip trovato nel workspace: `projects/ascii_20261120_195505/source/working.mp4`
(Nier, intervallo 48–58 s, 1920×1080, 60 fps, 10.01 s). A 30 fps: 300 frame,
300 SHA1 unici, differenza consecutiva mediana 3.87/255, media 5.18, massimo 39.95.
È movimento reale, non una sequenza duplicata.

Impostazioni: C/D 144×81, 1920×1080, 30 fps, 300 frame, Amber, tone M3 del progetto
(shadow 0.3264, white 0.962, gamma 0.82, contrast 0.18–0.85, local 0.24), target D 0.2965.
Stesso font, palette, glyph size, sorgente.

| Metrica | C globale | D spaziale |
|---|---:|---:|
| Frame quasi neri (media < 0.5/255) | **114/300** | **0/300** |
| Correlazione luminanza sorgente | 0.943 | **0.994** |
| Delta indici mediano / massimo | 0.1786 / 3.05 | **0.1598 / 0.81** |
| Shift 0 (su 298) | 294 | **298** |
| Correlazione indice/render | 0.853 | 0.849 |
| Validatore | **FAIL** | **PASS** |

Visivo:

- C a 144 è quasi vuoto nei primi 2.5 s; a 5–7.5 s mostra solo blob luminosi.
  Perde pianeta, nave, HUD e minimappa.
- D mantiene pianeta, sole, nave, HUD e minimappa; il movimento di camera e le esplosioni
  sono leggibili.
- Costo di D: il fondo è completamente riempito, nessuna cella vuota (livello minimo 32/255),
  quindi lo spazio negativo è quasi assente e l'immagine è più texture che figura.

Verdetto: **D supera questo gate tecnico e il criterio di riconoscimento sul clip reale**;
C 144 con tone M3 collassa. D non è universale: il fondo denso è un limite reale, quindi va
usato solo su scene complesse/luminose dove C perde struttura, non come default. C/M3 a 96
resta valido dove funziona; M3/Amber resta la soluzione per le scene scure.

Conferma necessaria prima dell'integrazione in Auto ASCII Correction: il gate è superato,
ma l'integrazione non è stata eseguita.

