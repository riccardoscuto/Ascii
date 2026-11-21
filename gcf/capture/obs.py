from __future__ import annotations

import base64
import socket
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from obsws_python import ReqClient

from gcf.config import load_obs_config

_START_LOCK = threading.Lock()


@dataclass
class CaptureSetup:
    scene: str
    source: str
    capture: str
    window: str | None
    monitor: str | None
    width: int
    height: int


class Obs:
    def __init__(self) -> None:
        self.cfg = load_obs_config()
        self.host = self.cfg["host"]
        self.port = int(self.cfg["port"])
        self.client: ReqClient | None = None
        self.proc: subprocess.Popen | None = None

    def port_open(self) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            return sock.connect_ex((self.host, self.port)) == 0

    def connect(self, timeout: float = 10.0) -> None:
        if self.client is not None:
            return
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            try:
                self.client = ReqClient(
                    host=self.host,
                    port=self.port,
                    password=self.cfg["password"],
                    timeout=8,
                )
                self.client.get_version()
                return
            except Exception as exc:  # connection refused / auth
                last = exc
                time.sleep(0.5)
        raise SystemExit(f"Impossibile connettersi a obs-websocket: {last}")

    def ensure_running(self) -> None:
        with _START_LOCK:
            if self.port_open():
                self.connect()
                return
            exe = Path(self.cfg["obs_exe"])
            workdir = Path(self.cfg["obs_workdir"])
            if not exe.exists():
                raise SystemExit(f"OBS portable non trovato: {exe}")
            self.proc = subprocess.Popen(
                [str(exe), "--portable", "--profile", "GCF", "--collection", "GCF",
                 "--disable-shutdown-check", "--minimize-to-tray"],
                cwd=str(workdir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            deadline = time.time() + 30
            while time.time() < deadline:
                if self.port_open():
                    self.connect()
                    return
                time.sleep(0.4)
            raise SystemExit("OBS non ha aperto obs-websocket entro 30 s.")

    def close(self) -> None:
        if self.client is not None:
            try:
                self.client.disconnect()
            except Exception:
                pass
            self.client = None

    def close_portable(self) -> list[str]:
        """Close only the portable OBS instance, never the installed one."""
        self.close()
        portable = Path(self.cfg["obs_exe"]).resolve().parents[2]
        script = (
            "Get-CimInstance Win32_Process -Filter \"Name='obs64.exe'\" | "
            "Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith('"
            + str(portable).replace("'", "''")
            + "', [System.StringComparison]::OrdinalIgnoreCase) } | "
            "ForEach-Object { $p = Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue; "
            "if ($p) { $p.CloseMainWindow() | Out-Null; Start-Sleep -Seconds 3; "
            "if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force }; $p.Id } }"
        )
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=True, check=False,
        )
        pids = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        time.sleep(1)
        # A forced close leaves OBS's sentinel behind, which makes the next
        # launch show a crash dialog. The portable config is disposable.
        sentinel = portable / "config" / "obs-studio" / ".sentinel"
        if sentinel.exists():
            for entry in sentinel.iterdir():
                try:
                    entry.unlink()
                except OSError:
                    pass
        return pids

    def version(self) -> tuple[str, str]:
        v = self.client.get_version()
        return v.obs_version, v.obs_web_socket_version

    def current_profile(self) -> str:
        # The API has no direct current-profile getter in older versions; the
        # portable instance is always launched with the GCF profile.
        return "GCF"

    def _scene_item_id(self, scene: str, source: str) -> int:
        return self.client.get_scene_item_id(scene, source).scene_item_id

    def _wait_source_size(self, scene: str, source: str, timeout: float = 8.0) -> tuple[int, int]:
        item_id = self._scene_item_id(scene, source)
        deadline = time.time() + timeout
        while time.time() < deadline:
            tr = self.client.get_scene_item_transform(scene, item_id).scene_item_transform
            w, h = int(tr["sourceWidth"]), int(tr["sourceHeight"])
            if w > 0 and h > 0:
                return w, h
            time.sleep(0.2)
        return 0, 0

    def list_property_items(self, source: str, prop: str) -> list[dict]:
        r = self.client.get_input_properties_list_property_items(source, prop)
        return list(r.property_items)

    def _create_source(self, scene: str, source: str, kind: str, settings: dict) -> None:
        self.client.create_input(scene, source, kind, settings, True)

    def _set_source_property(self, source: str, prop: str, value: str) -> None:
        self.client.set_input_settings(source, {prop: value}, True)

    def _pick_monitor(self, source: str, monitor: int | None) -> tuple[str, str]:
        items = [i for i in self.list_property_items(source, "monitor_id") if i["itemEnabled"]]
        if not items:
            raise SystemExit("Nessun monitor disponibile in OBS.")
        if monitor is not None:
            if monitor < 0 or monitor >= len(items):
                raise SystemExit(f"Indice monitor fuori range: {monitor}")
            item = items[monitor]
        else:
            item = next((i for i in items if "0,0" in i["itemName"]), items[0])
        return item["itemValue"], item["itemName"]

    def _pick_window(self, source: str, needle: str) -> tuple[str, str]:
        items = [i for i in self.list_property_items(source, "window") if i["itemEnabled"]]
        matches = [i for i in items if needle.lower() in i["itemName"].lower()]
        if not matches:
            listing = "\n".join(f"  {i['itemName']}" for i in items)
            raise SystemExit(f"Nessuna finestra contiene {needle!r}. Disponibili:\n{listing}")
        if len(matches) > 1:
            listing = "\n".join(f"  {i['itemName']}" for i in matches)
            raise SystemExit(f"Più finestre corrispondono a {needle!r}:\n{listing}\nUsa un testo più specifico.")
        return matches[0]["itemValue"], matches[0]["itemName"]

    def setup_capture(
        self,
        capture: str,
        width: int | None,
        height: int | None,
        window: str | None = None,
        monitor: int | None = None,
    ) -> CaptureSetup:
        self.ensure_running()
        assert self.client is not None
        stamp = datetime.now().strftime("%H%M%S")
        probe_scene = f"GCF Probe {stamp}"
        scene = f"GCF Capture {stamp}"
        source = f"GCF Source {stamp}"

        # Probe at a safe canvas first. OBS stores per-item scale_ref at
        # creation time, so the final canvas must be known before the final
        # scene item is created.
        probe_w = width or 1920
        probe_h = height or 1080
        self.client.set_video_settings(60, 1, probe_w, probe_h, probe_w, probe_h)
        time.sleep(0.3)
        self.client.create_scene(probe_scene)

        monitor_name = None
        window_name = None
        if capture == "screen":
            self._create_source(probe_scene, source, "monitor_capture", {"capture_cursor": False})
            value, monitor_name = self._pick_monitor(source, monitor)
            self._set_source_property(source, "monitor_id", value)
        elif capture == "window":
            if not window:
                raise SystemExit("--window obbligatorio per --capture window")
            self._create_source(probe_scene, source, "window_capture", {})
            value, window_name = self._pick_window(source, window)
            self._set_source_property(source, "window", value)
        elif capture == "game":
            if not window:
                raise SystemExit("--window obbligatorio per --capture game")
            self._create_source(probe_scene, source, "game_capture", {"capture_mode": "window"})
            value, window_name = self._pick_window(source, window)
            self._set_source_property(source, "window", value)
        else:
            raise SystemExit(f"Capture sconosciuta: {capture}")

        self.client.set_current_program_scene(probe_scene)
        source_w, source_h = self._wait_source_size(probe_scene, source)
        if (width is None or height is None):
            if source_w <= 0 or source_h <= 0:
                raise SystemExit("Sorgente non attiva: avvia il gioco o la finestra e riprova.")
            width, height = source_w, source_h
        if width <= 0 or height <= 0:
            raise SystemExit(f"Dimensione sorgente non valida: {width}x{height}")

        self.client.set_video_settings(60, 1, width, height, width, height)
        time.sleep(0.3)
        self.client.create_scene(scene)
        self.client.create_scene_item(scene, source, True)
        item_id = self._scene_item_id(scene, source)
        # OBS 32: alignment 5 with position 0,0 and scale 1 makes a
        # source whose size equals the canvas fill it. Alignment 0 was
        # rendering only a quarter in earlier tests.
        self.client.set_scene_item_transform(
            scene, item_id,
            {
                "alignment": 5,
                "positionX": 0.0,
                "positionY": 0.0,
                "cropLeft": 0,
                "cropRight": 0,
                "cropTop": 0,
                "cropBottom": 0,
                "scaleX": 1.0,
                "scaleY": 1.0,
                "boundsType": "OBS_BOUNDS_NONE",
                "boundsWidth": 1.0,
                "boundsHeight": 1.0,
                "cropToBounds": False,
            },
        )
        self.client.set_current_program_scene(scene)
        try:
            self.client.remove_scene(probe_scene)
        except Exception:
            pass
        return CaptureSetup(scene, source, capture, window_name, monitor_name, width, height)

    def screenshot(self, scene: str, width: int, height: int, path: Path) -> None:
        r = self.client.get_source_screenshot(scene, "png", width, height, -1)
        data = r.image_data.split(",", 1)[-1]
        path.write_bytes(base64.b64decode(data))

    def start_record(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.client.set_record_directory(str(directory))
        self.client.start_record()

    def stop_record(self, directory: Path) -> Path:
        r = self.client.stop_record()
        path = Path(getattr(r, "output_path", "") or "")
        if not path.exists():
            deadline = time.time() + 10
            while time.time() < deadline:
                files = sorted(directory.glob("*.mkv"), key=lambda p: p.stat().st_mtime)
                if files:
                    path = files[-1]
                    break
                time.sleep(0.2)
        if not path.exists():
            raise SystemExit(f"Registrazione non trovata in {directory}")
        # Wait for OBS to release the muxer/file.
        deadline = time.time() + 10
        last = -1
        while time.time() < deadline:
            size = path.stat().st_size
            if size > 0 and size == last:
                break
            last = size
            time.sleep(0.15)
        return path

    def list_windows(self, kind: str) -> list[dict]:
        self.ensure_running()
        stamp = datetime.now().strftime("%H%M%S")
        scene = f"GCF Probe {stamp}"
        source = f"GCF Probe Source {stamp}"
        self.client.create_scene(scene)
        try:
            self.client.create_input(scene, source, kind, {}, True)
            prop = "monitor_id" if kind == "monitor_capture" else "window"
            return self.list_property_items(source, prop)
        finally:
            try:
                self.client.remove_input(source)
            except Exception:
                pass
            try:
                self.client.remove_scene(scene)
            except Exception:
                pass
