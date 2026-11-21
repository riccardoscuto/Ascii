# Villaggio 33 s — diagnosi della perdita e confronto A/B/C

Data: 2026-11-21

Frame di riferimento: `G:\VDGP\_discovery\milestone5\village_33.png`
(33 s del gameplay da 63,3 s).

## 1. Catena completa

| Passaggio | Cielo | Edifici | Vegetazione | Terreno |
|---|---:|---:|---:|---:|
| RGB sRGB | 0,60-0,80 | 0,20-0,40 | 0,20-0,50 | 0,30-0,50 |
| Image Texture sRGB → lineare | 0,30-0,60 | 0,03-0,13 | 0,03-0,20 | 0,07-0,20 |
| v2 shadow 0,234 / low 0,18 | sopra soglia | sotto soglia | sotto soglia | sotto soglia |
| Indici caratteri | 5-7 | 0 | 0 | 0 |

Il nodo `Image Texture` del preset è **sRGB**; Blender converte in lineare prima
del modifier. Il luma del modifier, quindi, è **lineare**. L'analisi M4 leggeva
i frame con Pillow in **sRGB**: le due distribuzioni non coincidono.

Numeri sul villaggio:

| | sRGB | lineare |
|---|---:|---:|
| p10 | 0,0713 | 0,0075 |
| p50 | 0,3479 | 0,1158 |
| p95 | 0,7845 | 0,5870 |
| v2 visibile | **50,7%** | **14,7%** |
| v2 dense (@/W) | 17,2% | 5,3% |

Con v2 il primo glifo compare a **~0,345 lineare** (sRGB ~0,62): solo il cielo
lo supera. Case, torre, alberi e terreno sono neri. La soglia sRGB del 28% e
`dark_detail 0,47` della M4 non descrivevano il render: il villaggio era al
14,7%, non al 49%. Questa è la causa principale, prima della griglia.

La griglia 96×54 perde comunque il dettaglio fine; è il secondo limite.

## 2. A/B/C sullo stesso frame

Parametri:

- **A** — M4/v2: shadow 0,234, white 0,925, gamma 0,82, low 0,18, high 0,85,
  local 0,24. 14,7% visibile.
- **B** — normalizzazione dai percentili **lineari**: shadow 0,0058,
  white 0,6355, gamma 0,85, low 0,02, high 0,90, local 0,24. 73,2% visibile.
- **C** — B + contrasto locale: shadow 0,0051, white 0,6066, gamma 0,80,
  low 0,015, high 0,92, local 0,36. 75,8% visibile.

La mappa indici B mostra la struttura: cielo come picco, edifici come silhouette
scure, terreno texturizzato. Il rendering a glifi resta denso, ma A mostra solo
il cielo. C aggiunge texture e rumore; B è più pulito.

Il test **A/B/C statico** è in `_discovery/milestone5/village_ABC.png`.
Il video di 8 s (30-38 s) è `_discovery/milestone5/village_ABC_8s.mp4`
(sorgente | A | B). Il progetto B è `projects/ascii_20261121_110117`.

**Test strutturale aggiuntivo** — griglia 142×80 (densità 80, glyph 0,01125):
`_discovery/milestone5/village_density80.png`. Aumenta il dettaglio
(castello, alberi, prato) ma il cielo resta una parete di glifi densi: la
griglia aiuta, non risolve da sola la rampa.

## 3. Perché B non è una formula universale

Ho applicato la stessa normalizzazione lineare anche a foresta e coda scura:

- foresta: p95 lineare 0,293 → white 0,322; il risultato è troppo denso e
  rumoroso, peggiore del target medio M4;
- coda scura: p95 lineare 0,039 → white 0,043; il risultato è più scuro e meno
  leggibile del recupero M3 (white 0,30).

Quindi B è il candidato giusto **per il villaggio**, non il nuovo target
globale. La produzione dovrà generare più candidati per scena e scegliere quello
con il miglior punteggio strutturale, non applicare una formula unica.

## 4. Correzione locale e spazio colore

- Ho provato un tone map locale a 96×54 (luma compressa/liftata per regione,
  blur per evitare aloni) e due intensità. Non ha battuto B: il cielo diventa
  comunque una parete di glifi e il guadagno è marginale.
- CAS 0,5 luma e unsharp luma: differenza < 1% dei glifi, non usati.
- La componente cromatica non è stata modificata; il colore resta quello del
  preset. L'esposizione del preset agisce sul colore, non sulla scelta dei
  caratteri.

## 5. Limite strutturale

Anche B, che recupera l'informazione, produce un campo di glifi denso: a 96×54
la rampa unica `" .,:;+HW@"` non separa in modo netto texture del cielo e
silhouette degli edifici. Per soddisfare "edifici distinguibili senza guardare
l'originale" serve una modifica strutturale, non un'altra soglia:

- griglia più alta per le scene ricche (es. 144×81), oppure
- selezione dei caratteri guidata da bordi/silhouette (edge-aware) o un
  secondo passaggio di silhouette, oppure
- rampa/contrasto dei glifi dedicata alle forme grandi.

Queste modifiche cambiano il renderer/griglia e non sono state applicate in
questo test.

## 6. Cosa è stato verificato

- Il modifier usa i Socket reali (shadow/white/gamma/low/high/local) e le
  verifiche dei keyframe passano.
- La Image Texture è sRGB; il luma del modifier è lineare; la vista è Standard.
- Il colore non è stato alterato nei test B/C.
- Nessuna modifica alla GUI, nessun render dell'intero gameplay.

## 7. Conclusione

La perdita principale del villaggio è **color-space**: l'analisi M4 in sRGB
dichiarava 49% una scena che il render vedeva al 14,7%. B la porta al 73,2% e
recupera la struttura, ma il rendering a 96×54 resta denso. B è il primo
candidato convincente per il villaggio; non è ancora la soluzione definitiva
per foresta, scuro e per la leggibilità "senza originale".

**Verdetto della prova:** B è il primo candidato che recupera la struttura
(14,7% → 73,2% di celle visibili; mappa indici con castello, case, alberi e
terreno). Non soddisfa ancora il criterio "edifici distinguibili senza
guardare l'originale": il rendering a 96×54 con la rampa attuale resta denso.
La perdita principale è lo spazio colore; il limite residuo è la
rampa/griglia, non un'altra soglia.

Prima di modificare il motore di produzione va deciso se:

1. B è sufficiente come miglioramento del villaggio (in tal caso si corregge
   l'analisi in lineare e si aggiunge la selezione dei candidati); oppure
2. serve la modifica strutturale (griglia/rampa/edge-aware), perché B non basta.
