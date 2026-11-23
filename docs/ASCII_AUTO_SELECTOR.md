# Auto ASCII Selector — architettura proposta

Stato: **prototipo offline implementato e verificato sul composito 14 s**.
Non è collegato alla GUI e non è una modalità di default; `ascii_mode="auto"` nel renderer
diretto resta rifiutata. La decisione automatica vive in `gcf/ascii/selector.py`.

## Obiettivo

Scegliere per ogni shot la strategia ASCII più leggibile senza usare il nome del gioco,
senza cambiare preset a ogni frame e senza perdere la continuità temporale.

## Pipeline

1. **Analisi preliminare**
   - hash della sorgente e del preset;
   - frame di analisi a 10 fps;
   - luma lineare, percentili, edge, saturazione, colore.

2. **Shot e illuminazione**
   - riuso del rilevamento cut/flash già presente in `tone.py` e `correction.py`;
   - confini raffinati al frame 30 fps;
   - un piano per shot, non per frame.

3. **Candidati**
   Per ogni shot, sugli stessi frame rappresentativi:
   - `legacy`: preset v2, 96×54, piano M3/M4, colore approvato;
   - `spatial`: 144×81, mappe D;
   - `spatial-conservative`: 144×81, mappe D-Conservative;
   - variante colore Original/Amber solo se già ammessa per la scena.

4. **Valutazione**
   Non basta la correlazione di luminanza o il numero di celle visibili. Score per:
   - **struttura**: correlazione tra edge della sorgente e copertura dei glifi;
   - **silhouette**: continuità dei contorni tra frame e conservazione delle forme;
   - **zone scure**: visibilità dei dettagli sotto la soglia di shadow;
   - **saturazione**: frazione di glifi pieni e clipping del cielo;
   - **densità del fondo**: celle vuote, entropia a blocchi, spazio negativo;
   - **colore**: errore di tinta/chroma sulle celle visibili, senza conversioni sui dati;
   - **stabilità**: delta indici e delta celle vuote tra frame consecutivi;
   - **regressione**: confronto con la baseline Legacy approvata sullo stesso shot.

5. **Scelta**
   - guardie dure: nessun frame nero/quasi nero, mappe sincrone, livelli indice validi,
     nessun errore di compressione;
   - score pesato solo dopo le guardie;
   - margine minimo tra primo e secondo candidato;
   - isteresi: la modalità resta bloccata per lo shot;
   - cambio solo al cut o a una transizione approvata, mai a metà inquadratura;
   - override manuale sempre prioritario.

6. **Piano deterministico**
   `selection_plan.json` registra per ogni shot:
   ```json
   {
     "version": 1,
     "source_sha1": "...",
     "preset_sha1": "...",
     "shots": [
       {"start": 0.0, "end": 4.2, "cut": false,
        "selected": "spatial-conservative",
        "scores": {"legacy": 0.61, "spatial": 0.74, "conservative": 0.81},
        "confidence": 0.07, "override": false,
        "candidate_maps": {"spatial": "hash", "conservative": "hash"}}
     ],
     "metrics": {"dark_spatial": "rejected", "sync": "PASS"},
     "renderer_version": "spatial-1"
   }
   ```

7. **Rendering**
   - il piano è letto dal progetto, non ricalcolato;
   - ogni shot usa la modalità scelta e le mappe già validate;
   - preview e finale usano lo stesso piano e le stesse mappe;
   - il renderer non cambia preset dentro lo shot.

## Guardie minime

- `legacy` deve restare disponibile e non deve perdere frame;
- `spatial` non viene scelto su scene dove produce quasi nero (caso dark Witcher);
- D-Conservative non viene scelto se il delta indici o la variazione delle celle vuote
  supera la baseline oltre la tolleranza;
- un cambio di modalità a metà shot è vietato salvo override esplicito;
- l'override manuale è registrato nel progetto e non viene sovrascritto.

## Gate del selettore

Prima di collegarlo alla GUI servono:

1. tre sorgenti eterogenee, con shot multipli;
2. confronto Auto vs scelta manuale "oracle" shot per shot;
3. nessuna regressione di struttura/colore rispetto alla baseline;
4. stabilità temporale provata su tutti i frame;
5. piano ispezionabile e deterministico;
6. stop/ripresa e cache verificati;
7. approvazione esplicita: Auto non è default.

Nessuna regola basata sul nome del videogioco.

## Prototipo offline

`gcf/ascii/selector.py` implementa:

- rilevamento shot dal piano tonale;
- tre candidati: Legacy 96, Spatial adaptive 144, Spatial-Conservative adaptive 144;
- scelta per shot del colore Original/Amber e di Auto/M3 in base a saturazione e luma;
- due frame rappresentativi per shot, renderizzati davvero dal backend;
- metriche: struttura/edge, ombre, densità e celle vuote, saturazione, colore, continuità
  tra frame e guardie su frame neri/quasi neri;
- margine di preferenza per la baseline e per il candidato più stabile;
- piano JSON con score, motivazione, progetti candidati e percorsi;
- rendering dei soli shot scelti e concatenazione del video Auto;
- `render_plan` accetta una mappa manuale per il confronto.

Comando sperimentale:

```powershell
python -m gcf ascii auto --project projects/<id>
```

Non è una modalità GUI e non è il default.

### Risultato sul composito 14 s

Shot: NieR dinamico, villaggio, foresta/fade, interno scuro; una dissolvenza graduale e
un cambio di luce sostenuto nella foresta.

| Shot | Intervallo | Auto | Manuale | Score Auto |
|---|---:|---|---|---:|
| S0 NieR | 0.0–3.1 | conservative | conservative | 0.434 |
| S1 villaggio | 3.1–7.1 | spatial | spatial | 0.556 |
| S2 foresta | 7.1–8.5 | conservative | conservative | 0.553 |
| S3 foresta/fade | 8.5–10.5 | conservative | conservative | 0.538 |
| S4 scuro | 10.5–14.0 | legacy | legacy | 0.648 |

Auto e manuale coincidono su **5/5** shot. Nessun caso in cui Auto sceglie una modalità
peggiore della selezione manuale. Lo scuro è riconosciuto dal guard: Spatial e
D-Conservative hanno score -1 (quasi nero), Legacy M3 vince.

File: `_discovery/milestone7/auto/` (`auto.mp4`, `manual.mp4`, `auto_vs_manual.mp4`,
`selection_timeline.png`, `gate_metrics.json`).

Limiti: due frame per shot, un solo composito, scoring ancora euristico; Auto non è
approvato per la GUI né per un uso universale. Il test manuale è una scelta visiva per
shot, non un dataset indipendente.
