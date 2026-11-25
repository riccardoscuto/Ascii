# Milestone 7.2 — Unificazione e qualità percettiva

Data: 2026-11-25
Stato: architettura unificata e diagnosi completata. **Auto non approvato per la GUI**:
il sottoinsieme dei sei errori M7.1 passa da 0/6 a 2/6 corretti, restano quattro regressioni;
il target 90% non è raggiunto. Nessuna campagna di taratura delle soglie.

## 1. Unificazione

- `selector.select()` ora usa `evaluate_shot()` per ogni shot; il vecchio percorso a due
  still è stato rimosso.
- `rescore()` (vecchio algoritmo) rimosso: valutazione, selezione e CLI usano un solo motore.
- Dataset, CLI `gcf ascii auto` e futura GUI possono chiamare lo stesso percorso.
- No-choice nella CLI: se un shot è `none`, il video Auto non viene forzato e viene
  stampato l'elenco dei non recuperabili.
- `select()` usa un progetto shadow: il progetto originale non viene modificato.
- La sorgente analizzata è la **working source** effettiva del renderer. `evaluate_shot`
  costruisce un probe `media.prepare_working` per crop/formato, salvo il percorso
  `already_working=True` usato da `select`.
- Frame mancanti, finestre incomplete ed errori di rendering sono registrati in
  `window_errors`/`invalid_frames`; una finestra incompleta non viene mediata via.
- `media.extract_analysis()` è ora 180×320 per il verticale (320×180 orizzontale).
- `tone._frames()` usa un thumbnail verticale 90×160.
- `select()` usa la griglia 81×144 per il verticale, non più 144×81 fissa.

## 2. Rappresentazione comune

Nuovo modulo `gcf/ascii/perceptual.py`. Tutti i candidati vengono riportati a una griglia
comune: 64×36 orizzontale, 36×64 verticale.

Mappe derivate dal rendering:

- copertura effettiva dei glifi;
- luminanza dei glifi (solo pixel accesi);
- luminanza media delle celle (fondo nero incluso);
- colore dei glifi separato dal fondo;
- bordi e range locale;
- indice effettivo/livelli per i candidati Spatial (le mappe Legacy non sono equiparabili
  agli indici GN e non vengono più usate come se lo fossero).

## 3. Metriche percettive

- SSIM multiscala su luma ricostruita e normalizzata;
- SSIM sui bordi;
- correlazione edge e contrasto locale;
- dettaglio nelle ombre;
- perdita/compressione delle alte luci;
- densità nelle regioni uniformi;
- colore dei glifi con fondo nero escluso;
- leggibilità UI su celle a edge alto;
- continuità temporale su frame consecutivi, sottraendo il movimento della sorgente.

La percentuale di celle visibili non è più una metrica di qualità.

## 4. Diagnosi dei sei errori M7.1

Con i vecchi pesi:

| Caso | Candidato Auto | Vincente manuale | Componente decisiva |
|---|---|---|---|
| NieR esplosione | conservative | legacy | density 0.196 vs 0.090; saturation alta |
| Balatro 0/1/2 | conservative | legacy | density 0.194 vs 0.169; color Legacy 0 |
| Montagna | legacy | spatial | density 0.184 vs 0.090; temporal |
| Foresta fade 1 | legacy | spatial | density 0.188 vs 0.090; temporal |

`density` era il peso dominante e premiava alternativamente output troppo vuoti o troppo
pieni; il colore Legacy era artificialmente zero perché includeva il fondo nero.

### Saturazione degli indici

Su NieR esplosione (59 frame del candidato):

- indice 8: **54.3%** delle celle;
- indice ≥7: **66.1%**;
- tone ≥0.40: **48.8%**;
- con `index_floor=0.008`, `index_span=0.392` l'indice satura a `v≈0.40`.

Conservative preserva i due indici più densi, quindi non recupera il dettaglio
dell'esplosione. È un contributo reale alla perdita di dettaglio. **Nessuna correzione
dell'indice è stata promossa**: serve un A/B dedicato con span/floors alternativi e
verifica visiva.

## 5. Combinazioni colore

`evaluate_shot` valuta ora **entrambe le palette per ogni modalità**:

- Legacy Original/Amber;
- Spatial adaptive Original/Amber;
- Conservative adaptive Original/Amber.

Ogni modalità porta avanti la propria variante colore migliore; non si sceglie la modalità
prima della palette. La preselezione per saturazione resta solo come primo candidato, non
esclude l'altro. La ricerca di fallback su densità/tone/contrasto non è stata attivata:
prima va risolta la metrica UI/highlights.

## 6. Riesame dei sei errori con il nuovo motore

Dopo l'unificazione e le metriche comuni:

- **montagna**: ora Auto sceglie Spatial (corretto rispetto al manuale);
- **foresta fade 1**: ora Auto sceglie Spatial (corretto);
- **NieR esplosione**: Auto Spatial, manuale Legacy — resta errato;
- **Balatro 0/1/2**: Auto Spatial, manuale Legacy — restano errati.

Quindi 2/6 corretti, 4/6 ancora regressioni. Il colore scelto su questi shot resta Original
mentre il manuale preferisce Amber; la metrica colore/UI non è ancora sufficiente.

## 7. Validazione

- Dataset M7.1: 19/25 (76%), 6 regressioni visive, 1 scena non recuperabile.
- Nuovo motore: sei casi critici riesaminati (2 corretti, 4 errati); il rerun completo dei
  25 shot con il motore unificato non è stato dichiarato valido.
- Non è disponibile nel workspace una nuova registrazione di gameplay separata per gioco:
  il holdout indipendente richiesto non è stato eseguito. Il verticale e il black test
  coprono i controlli architetturali, non la generalizzazione su titoli nuovi.
- Il target ≥90% non è raggiunto. Non è sufficiente un numero: il caso Balatro/UI e
  l'esplosione restano visivamente sbagliati.
- Confronti anonimi A/B/C: `_discovery/milestone7_2/anonymous/` con `key.json`.
- Verticale: analysis 180×320 verificata; dataset M7.1 verticale già a 1080×1920.
- Audio: master/concat AAC verificati su NieR.
- Cache corrotta: rigenerazione con root identico.
- Stop/ripresa: 57/90 frame, ripresa 90/90, pixel identici al continuo.
- Transizione 3.1 s: step render 3.40 contro step sorgente 4.53; nessun salto artificiale.
- Test: 52 unit test OK.

## 8. Gate

**Auto non va integrato nella GUI.** L'architettura ora è unica e il no-choice funziona,
ma la qualità percettiva non è ancora sufficiente: UI complesse, esplosioni e palette
restano instabili.

Prossimo passo consigliato:

1. metrica UI/testo più forte (non solo coverage/edge);
2. A/B dedicato su `index_span`/`index_floor` per le esplosioni;
3. fallback densità/tone solo dopo una metrica che separi UI e sfondo;
4. rerun completo 25 shot + holdout separato per registrazione/gioco;
5. solo dopo, valutare la GUI.

Nessuna modifica a GUI, preset v2, Guess Generator o BlueFox. Nessun render da 5 minuti.
