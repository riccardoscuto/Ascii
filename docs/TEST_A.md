# Test A — Cattura OBS

Data: 2026-11-19
Stato: **completato**, incluso un test Game Capture su un videogioco reale.

## Obiettivo

Verificare la catena:

```
OBS dedicato -> identificazione finestra -> auto-size -> preview 9:16
-> registrazione -> salvataggio -> take verticale 1080x1920 -> associazione al gioco
```

Senza modificare la configurazione OBS personale.

## Isolamento OBS

Copia **portable** di OBS 32.2.2:

```
G:\VDGP\tools\obs-portable\
  portable_mode.txt
  config\obs-studio\
    basic\profiles\GCF\basic.ini
    basic\scenes\GCF.json
    plugin_config\obs-websocket\config.json   # porta 4456, password locale
```

La configurazione personale in `C:\Users\Riccardo\AppData\Roaming\obs-studio` non viene usata dal tool. Hash prima/dopo:

| File personale | SHA-256 |
|---|---|
| `basic\scenes\Senza titolo.json` | `7F3B8F4BCEB3DB4CF8918540C7F60D4DC399A0DB863D1F6DE64940A2B51D96BD` |
| `basic\profiles\Senza titolo\basic.ini` | `FCEC2935A4FBC3B3710AC26260386741D114A87CC940310FCA86958DF312769A` |
| `global.ini` | `919F432F86FA5AE61267CA626AC35BFD47B03CAAC90BB847D0E2AC22BD621FDF` |

## Risolto il problema 960x540

Non era un problema di DPI o di coordinate logiche. La sorgente era 1920x1080; il problema era la trasformazione dello scene item OBS via WebSocket:

- con `alignment=0`, `position=0,0`, `scale=1` OBS rendeva solo un quarto della sorgente;
- impostando il canvas a 960x540 il contenuto sembrava corretto, ma era un workaround.

La trasformazione corretta è:

```
alignment = 5
positionX = 0
positionY = 0
scaleX = 1
scaleY = 1
boundsType = OBS_BOUNDS_NONE
```

Con questa combinazione una sorgente della stessa dimensione del canvas riempie il frame. La verifica è stata fatta con una matrice di trasformazioni: l'unica variante con bounding box pieno era `alignment=5`, `position=0,0`, `scale=1`.

Il tool ora:

1. crea una scena di probe e una sorgente;
2. legge `sourceWidth`/`sourceHeight` reali;
3. imposta il canvas a quella dimensione;
4. crea la scena finale e applica la trasformazione corretta.

Quindi **non serve più passare `--size`**: `--size` resta solo come override opzionale.

## Test con gameplay reale

Gioco: **Balatro** (Steam), Game Capture, finestra fullscreen 1920x1080.

- Auto-size: 1920x1080.
- Crop: `x=656, y=0, w=608, h=1080`.
- Take: **19,867 s**, `take.mp4` 1080x1920, 60 fps, 1192 frame, senza audio.
- MKV full-frame conservato come archivio.
- Preview e verify ispezionate: nessuna UI OBS, nessuna schermata nera, inquadratura verticale centrata.
- Il gioco è stato portato in una schermata di gameplay reale (mano di carte, “Gioca mano”/“Scarta”).

Percorso:

```
projects/test_a/takes/balatro/20261119_160135/
  GCF_20261119_160136.mkv
  take.mp4
  preview_full.png
  preview_vertical.png
  verify_vertical.png
  take.json
```

Nota: il footage Balatro è solo per il test tecnico locale; non va pubblicato senza verifica dei diritti.

## Preview in tempo reale

L'errore di trasformazione è risolto, quindi una scena OBS verticale dedicata è tecnicamente possibile:

- canvas 1080x1920;
- sorgente con crop 608x1080;
- scala a 1080x1920;
- preview OBS verticale esatta.

Per registrare full-frame e mostrare contemporaneamente una preview verticale servirebbe però un secondo canvas/output o una preview separata. Per ora il tool mantiene:

- registrazione full-frame + MKV archivio;
- preview verticale statica prima della registrazione;
- take verticale 1080x1920 dopo la registrazione.

La UI futura potrà mostrare la preview verticale live. Il requisito è conservato nell'architettura.

## Comandi

```powershell
cd G:\VDGP

.\.venv\Scripts\python.exe -m gcf capture doctor
.\.venv\Scripts\python.exe -m gcf capture setup

# Game Capture, dimensione automatica
.\.venv\Scripts\python.exe -m gcf capture preview --project test_a --game balatro --capture game --window "Balatro"
.\.venv\Scripts\python.exe -m gcf capture record  --project test_a --game balatro --capture game --window "Balatro" --duration 20

.\.venv\Scripts\python.exe -m gcf capture takes --project test_a --game balatro
.\.venv\Scripts\python.exe -m gcf capture select --project test_a --game balatro --take-id 20261119_160135
.\.venv\Scripts\python.exe -m gcf capture close
```

`--capture window` è il fallback per giochi non compatibili con Game Capture; `--capture screen` resta per test/fullscreen particolari.

## Limiti noti

1. Il crop 9:16 di un gioco 16:9 usa 608x1080 pixel e li porta a 1080x1920: è un ingrandimento 1,78x. È inerente al formato; con un gioco a 1440p/4K il crop è più nitido.
2. Il take è 60 fps; il montaggio Guess lo porta a 30 fps. Il take MP4 è sempre muto; il MKV conserva l'audio silenzioso/di gioco.
3. Lo stop della registrazione CLI è a durata (`--duration`); il pulsante di stop immediato arriverà con la UI.
4. L'importazione di MP4 già registrati non è ancora implementata.
5. La preview è statica; la preview verticale live è il passo successivo dell'architettura.
6. Le scene di test nella raccolta OBS portable non vengono ripulite automaticamente.

## Test automatici

```
python -m unittest discover -s tests -v
Ran 9 tests ... OK
```

## Prossimo passo

Il primo round Guess è stato costruito e verificato:

`projects/test_a/rounds/balatro_20261119_160135/round_01.mp4`

Vedi `docs/ROUND_01.md`.

