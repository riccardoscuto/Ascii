# Auto ASCII Correction — rifinitura qualitativa (M4)

> Correzione 2026-11-21: le metriche M4 erano calcolate in sRGB, mentre il
> render usa luma lineare. Il villaggio al 49,2% sRGB è al 14,7% lineare.
> La soglia `dark_detail >= 0,55` non è valida. Vedi
> `docs/ASCII_VILLAGE_DIAGNOSIS.md` per la diagnosi e il test A/B/C.

Data: 2026-11-20

Dopo la Milestone 3 il recupero delle scene scure era netto, ma Balatro e parte
di The Witcher restavano difficili da interpretare. Il criterio `visible_base <
28%` premiava scene con molti caratteri anche quando questi non descrivevano
nulla. Questa fase sostituisce quel criterio con indicatori di struttura e
limita la correzione alle scene che possono davvero migliorare.

## 1. Nuovi indicatori

Per ogni campione (10 Hz) il piano calcola:

- `visible`: celle con almeno un carattere;
- `dark_detail`: celle sotto il punto nero effettivo (0,345) con variazione
  locale > 0,04 — dettaglio recuperabile, non solo buio;
- `saturated`: celle mappate sui caratteri piu densi (@/W);
- `edge_visible`: percentuale di celle con bordo che ricevono un carattere;
- `block_entropy`, `empty_blocks`, `dense_blocks`: distribuzione spaziale su
  48 blocchi (8x6);
- `index_std`: varieta tonale dei caratteri;
- `resolution_limited`: dettaglio fine ma nessun dettaglio recuperabile a
  livello di cella.

La soglia del 28% non e piu il criterio principale. Per le scene medie decide
`dark_detail`; per le scene davvero scure resta `visible` (sotto l'8%) perche
li il problema e l'assenza totale di caratteri.

## 2. Analisi dei segmenti

| Segmento | p10 | p50 | p95 | visible | dark_detail | saturate | edge_vis | Esito |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Balatro 2 s | 0,192 | 0,322 | 0,937 | 34,3% | 18,8% | 10,5% | 49,3% | resolution limited |
| Villaggio 33 s | 0,082 | 0,341 | 0,780 | 49,2% | 47,2% | 13,2% | 44,6% | gia leggibile, invariato |
| Foresta 44 s | 0,082 | 0,239 | 0,518 | 25,8% | 67,3% | 2,4% | 24,7% | corretto |
| Coda scura 58 s | 0,016 | 0,039 | 0,208 | 0,6% | 26,4% | 0,0% | 2,4% | corretto (M3) |
| NieR 52 s | 0,471 | 0,608 | 0,831 | ~93% | 0% | 43% | 100% | invariato |

**Balatro** — le carte occupano circa 3 celle per carta e i semi/valori sono
sotto la cella. Il pannello UI ha testo alto 1-2 celle. Non e un problema di
contrasto: anche il test di reframe 2x lascia la fan di carte come un blocco e
taglia la UI. Serve una griglia piu alta o una cattura dedicata; il motore
segnala `resolution_limited` e non applica correzioni.

**Villaggio** — il castello, le case e gli alberi sono gia leggibili con v2; il
47% di celle scure ha dettaglio, ma abbassare la soglia aggiunge soprattutto
erba e fogliame, cioe texture. Lasciato invariato per non peggiorare una scena
gia buona.

**Foresta** — il 67% delle celle e scuro con dettaglio; con v2 la scena e quasi
nera. Il lift controllato recupera alberi e prato. Resta una scena di texture:
le foglie non sono risolvibili a 96x54, ma il contenuto e piu leggibile.

**NieR** — nessuna cella scura con dettaglio; il look denso approvato resta
identico.

## 3. Correzione

Target medio (solo se `dark_detail >= 0,55`):

- `shadow = clamp(p10*0,85 + 0,07, 0,08, 0,18)`
- `white = clamp(p95*1,2, 0,70, 0,95)`
- `gamma = 0,88`, `contrast_low = 0,09`, `contrast_high = 0,92`,
  `local_contrast = 0,28`

La forza e `(dark_detail - 0,55) / 0,15`, quindi la foresta (0,67) arriva a
0,82 e non a una correzione piena. Target scuro (p50 < 0,18 o visible < 8%)
invariato rispetto alla M3: shadow 0,013, white 0,30, gamma 0,925, low 0,03,
local 0,336.

Esperimenti sul contrasto locale:

- CAS 0,5 solo luma, con local 0,36: differenza visiva marginale rispetto al
  solo local 0,36; non usato.
- `unsharp` luma: stessa conclusione, non usato.
- Il contrasto locale interno al preset (Socket Local Contrast) e la curva
  gamma/contrast high sono bastati; la componente cromatica non e stata toccata.
- Reframe Balatro 2x: carte ancora illeggibili, UI tagliata; nessuno zoom
  automatico.

## 4. A/B

File: `_discovery/milestone4/ab/*.mp4` (sorgente | prima | dopo, 4 s) e
`_discovery/milestone4/after/*.mp4` (solo ASCII).

| Scena | Prima (M3) | Dopo (M4) | Esito |
|---|---|---|---|
| Balatro 0-4 s | 8,01 / 255 | 8,01 | identico, resolution limited |
| Villaggio 30-34 s | 8,74 | 8,74 | identico (diff 0,0) |
| Foresta 42-46 s | 2,17 | 4,59 | piu contenuto, diff 3,94 |
| Witcher scuro 52-56 s | 5,28 | 5,28 | identico |
| NieR 50-54 s | - | - | parametri v2, diff 0,6 / 255 |

Video completo 63,3 s:

- 1900 frame, 63,333333 s, 1920x1080 30 fps, audio AAC presente;
- visibilita media 29,4% -> 46,8%;
- max flicker 0,0024; 0 problemi;
- 1 limitazione: Balatro 0-19,8 s `resolution_limited`.

Piano: `projects/ascii_20261120_214015/temp/plan.json`.
Output: `projects/ascii_20261120_214015/output/{master,youtube}.mp4`.

## 5. Limiti

- Il miglioramento della foresta e reale ma resta texture-limited: a 96x54 le
  foglie non diventano oggetti. Non e stato alzato il numero di caratteri per
  compensare.
- Balatro non e recuperabile con il tone mapping; il flag e l'azione suggerita
  (reframe/griglia piu alta) sono espliciti. Il reframe 2x non basta.
- Il villaggio resta v2: la soglia `dark_detail >= 0,55` lo esclude.
- La GUI non e stata toccata.
- Il test NieR e di 4 s; il video completo da 5 min non e stato rieseguito.

## Gate

- Scena media migliorata: **foresta si**, con limite di texture documentato.
- Scene gia buone: **identiche** (villaggio, scuro, Balatro, NieR).
- Nessun flicker artificiale: **si** (0,0024).
- Frame count, durata, audio: **si** (1900 / 63,333 / AAC).
- Piano ispezionabile con metriche e limitazioni: **si**.
- Il limite di Balatro e riconosciuto, non mascherato: **si**.
