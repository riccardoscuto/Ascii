from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

from gcf.ascii import media, preset, spatial, tone
from gcf.ascii.preset import PRESET_BLEND
from gcf.config import ROOT, blender_bin


BLENDER_JOB = ROOT / "gcf" / "ascii" / "blender_job.py"
JOB_SCRIPT_TIMEOUT = 6 * 60 * 60


class AsciiCanceled(Exception):
    pass


def _progress(cb, done, total, elapsed, stage):
    if cb:
        eta = None
        if done and elapsed and total:
            eta = elapsed * (total - done) / done
        cb(int(done), int(total), float(elapsed), eta, stage)


def _frames_dir(project, mode):
    return project.preview_frames_dir if mode == "preview" else project.frames_dir


def _count_frames(folder: Path) -> int:
    return len(list(folder.glob("f_*.png"))) if folder.exists() else 0


def _next_frame(folder: Path, total: int) -> int:
    """First frame not yet rendered; drops a truncated last PNG after a cancel."""
    frame = 1
    while frame <= total and (folder / f"f_{frame:04d}.png").exists():
        frame += 1
    if frame > 1:
        last = folder / f"f_{frame - 1:04d}.png"
        try:
            from PIL import Image
            with Image.open(last) as im:
                im.verify()
        except Exception:
            try:
                last.unlink()
            except OSError:
                pass
            frame -= 1
    return frame


def _file_sha1(path: str | Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _mode(project) -> str:
    mode = str(getattr(project, "ascii_mode", "legacy") or "legacy")
    if mode not in spatial.ASCII_MODES:
        raise RuntimeError(f"Modalità ASCII non valida: {mode}")
    if mode == "auto":
        raise RuntimeError("Modalità Auto non approvata: manca il gate del selettore.")
    return mode


def _variant(project) -> str:
    variant = str(getattr(project, "spatial_variant", "d") or "d")
    if variant not in spatial.SPATIAL_VARIANTS:
        raise RuntimeError(f"Variante spaziale non valida: {variant}")
    return variant


def _signature(project, params: dict, plan: dict) -> str:
    mode = _mode(project)
    variant = _variant(project)
    maps = getattr(project, "spatial", {}) or {}
    payload = {
        "source_path": project.source,
        "source_sha1": _file_sha1(project.working_source),
        "preset_sha1": _file_sha1(PRESET_BLEND),
        "format": project.format,
        "start": project.interval_start,
        "duration": project.interval_duration,
        "params": {k: v for k, v in project.params.items() if k != "youtube_mbps"},
        "grid": [params.get("Grid X"), params.get("Grid Y")],
        "plan": {
            "total_frames": plan.get("total_frames"),
            "frame_scale": plan.get("frame_scale"),
            "frame_offset": plan.get("frame_offset"),
            "cuts": plan.get("cuts"),
            "keyframes": plan.get("keyframes"),
        },
        "mode": mode,
        "variant": variant,
        "map_key": maps.get("key"),
        "map_root": maps.get("index_root"),
        "renderer_version": spatial.RENDERER_VERSION if mode == "spatial" else "legacy-1",
    }
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _plan_context(project, data: dict, analysis_grid: tuple[int, int]) -> str:
    payload = {
        "source_sha1": _file_sha1(project.working_source),
        "preset_sha1": _file_sha1(PRESET_BLEND),
        "params": {k: v for k, v in project.params.items() if k != "youtube_mbps"},
        "grid": [data["grid"]["cols"], data["grid"]["rows"]],
        "analysis_grid": [int(analysis_grid[0]), int(analysis_grid[1])],
        "mode": _mode(project),
        "auto": bool(project.params.get("auto_correction", False)),
        "overrides": project.params.get("correction_overrides") or {},
        "plan_version": "tone-linear-1",
    }
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def prepare(project, progress=None) -> dict:
    project.ensure_dirs()
    started = time.time()
    ascii_mode = _mode(project)
    _progress(progress, 0, 0, 0, "Preparazione sorgente")
    media.prepare_working(project)
    _progress(progress, 0, 0, 0, "Analisi frame")
    media.extract_analysis(project)
    data = preset.resolve(project)
    grid = (data["grid"]["cols"], data["grid"]["rows"])
    analysis_grid = grid if ascii_mode == "spatial" else (tone.COLS, tone.ROWS)
    context = _plan_context(project, data, analysis_grid)
    plan = None
    if project.plan_path and Path(project.plan_path).exists():
        try:
            candidate = json.loads(Path(project.plan_path).read_text(encoding="utf-8"))
            same_context = project.plan_context == context if project.plan_context else True
            total = int(round(project.working_info["duration"] * 30))
            same_shape = (int(candidate.get("total_frames", -1)) == total
                          and abs(float(candidate.get("duration", -1)) -
                                  project.working_info["duration"]) < 0.05)
            if same_context and same_shape:
                plan = candidate
        except Exception:
            plan = None
    if plan is None:
        plan = tone.build_plan(project, project.working_info["fps"], data["shadow"], data["white"],
                               auto=bool(project.params.get("auto_correction", False)),
                               overrides=project.params.get("correction_overrides"),
                               analysis_grid=analysis_grid, ramp=data["ramp"])
    else:
        project.plan_path = str(project.plan_path)
    project.plan_context = context
    project.grid = {"cols": data["grid"]["cols"], "rows": data["grid"]["rows"],
                    "glyph": data["grid"]["glyph"], "resolution": list(data["resolution"])}
    project.overrides = project.params.get("correction_overrides") or {}
    project.ascii_mode = ascii_mode
    project.renderer_version = spatial.RENDERER_VERSION if ascii_mode == "spatial" else "legacy-1"
    project.timings["prepare"] = round(time.time() - started, 3)
    project.save()
    return {"params": data, "plan": plan, "mode": ascii_mode, "variant": _variant(project)}


def _job_payload(project, data: dict, plan: dict, mode: str, total: int,
                 frames_dir: Path, verification: Path, preview_frames: int = 0,
                 still_frame: int = 1, still_path: str = "", start_frame: int = 1,
                 end_frame: int | None = None, index_required: int | None = None) -> dict:
    by_name = {k: v for k, v in data["sockets"].items()
               if k not in ("Source Frame Scale", "Source Frame Offset")}
    expected = preset.expected(project, plan)
    ascii_mode = _mode(project)
    variant = _variant(project)
    maps = getattr(project, "spatial", {}) or {}
    spatial_info = {}
    if ascii_mode == "spatial":
        root = Path(maps["dir"])
        spatial_info = {
            "dir": str(root),
            "index_dir": str(root / "idx"),
            "manifest": maps.get("manifest", ""),
            "map_key": maps.get("key", ""),
            "index_root": maps.get("index_root", ""),
            "index_count": int(maps.get("frames", 0)),
            "kind": maps.get("kind", "spatial"),
            "conservative": bool(maps.get("conservative", False)),
            "target": maps.get("target", 0.0),
        }
    return {
        "mode": mode,
        "ascii_mode": ascii_mode,
        "spatial_variant": variant,
        "renderer_version": project.renderer_version,
        "spatial": spatial_info,
        "source": project.working_source,
        "plane": [data["grid"]["plane_x"], data["grid"]["plane_y"]],
        "resolution": list(data["resolution"]),
        "params": by_name,
        "expected": expected,
        "source_frame_scale": round(project.working_info["fps"] / 30.0, 6),
        "source_frame_offset": round(1.0 - project.working_info["fps"] / 30.0, 6),
        "plan": plan,
        "total_frames": total,
        "preview_frames": preview_frames,
        "frames_dir": str(frames_dir),
        "verification": str(verification),
        "still_frame": still_frame,
        "still_path": still_path,
        "start_frame": start_frame,
        "end_frame": int(end_frame if end_frame is not None else total),
        "index_required": int(index_required if index_required is not None else total),
    }


def _run_blender(project, payload: dict, total: int, frames_dir: Path,
                 progress=None, cancel=None, stage="Rendering") -> float:
    job_path = project.path / "temp" / f"job_{payload['mode']}.json"
    job_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    preset_copy = project.path / "temp" / "preset_work.blend"
    shutil.copy2(preset.PRESET_BLEND, preset_copy)
    log_path = project.path / "render.log"
    cmd = [blender_bin(), "-b", "--factory-startup", str(preset_copy),
           "--python", str(BLENDER_JOB), "--", str(job_path)]
    started = time.time()
    with open(log_path, "a", encoding="utf-8") as log:
        log.write("\n=== " + time.strftime("%Y-%m-%d %H:%M:%S") + " ===\n")
        log.write(" ".join(cmd) + "\n")
        log.flush()
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
        try:
            while proc.poll() is None:
                if cancel is not None and cancel.is_set():
                    proc.terminate()
                    try:
                        proc.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    raise AsciiCanceled("Rendering interrotto.")
                done = _count_frames(frames_dir)
                _progress(progress, done, total, time.time() - started, stage)
                time.sleep(0.6)
        finally:
            if proc.poll() is None:
                proc.kill()
    if proc.returncode != 0:
        tail = "\n".join(log_path.read_text(encoding="utf-8", errors="ignore").splitlines()[-30:])
        raise RuntimeError(f"Blender ha fallito (codice {proc.returncode}).\n{tail}")
    done = _count_frames(frames_dir)
    _progress(progress, done, total, time.time() - started, stage)
    return time.time() - started


def _read_verification(project, path: Path, payload: dict | None = None) -> dict:
    if not path.exists():
        raise RuntimeError("Verifica parametri Blender assente.")
    data = json.loads(path.read_text(encoding="utf-8"))
    project.verification = data
    if payload is None or payload.get("mode") != "segment":
        if data.get("frame_range", [1, 1])[0] != 1:
            raise RuntimeError("Frame range inatteso nella verifica.")
    if payload is not None:
        if data.get("ascii_mode") != payload.get("ascii_mode"):
            raise RuntimeError("Modalità ASCII non coerente nella verifica.")
        if payload.get("ascii_mode") == "spatial":
            maps = payload.get("spatial", {})
            if data.get("map_key") != maps.get("map_key"):
                raise RuntimeError("Chiave mappe non coerente nella verifica.")
            if data.get("index_count", 0) < payload.get("index_required", payload.get("total_frames", 0)):
                raise RuntimeError("Sequenza indici incompleta nella verifica.")
            if data.get("index_colorspace") != "Non-Color":
                raise RuntimeError("Colore degli indici non Non-Color.")
    return data


def _ensure_maps(project, data: dict, plan: dict, end: int,
                 progress=None, cancel=None) -> dict | None:
    if _mode(project) == "legacy":
        return None
    variant = _variant(project)
    kind = {"d": "spatial", "conservative": "conservative",
            "adaptive": "spatial", "adaptive-conservative": "conservative",
            "global": "global", "range": "spatial", "compress": "spatial",
            "local": "spatial", "guarded": "conservative"}[variant]
    started = time.time()
    try:
        manifest = spatial.ensure_maps(
            project, data, plan, end=end, kind=kind,
            conservative=variant in ("conservative", "adaptive-conservative", "guarded"),
            adaptive=variant in spatial.ADAPTIVE_VARIANTS,
            progress=progress, cancel=cancel,
            variant=variant if variant in ("range", "compress", "local", "guarded") else "")
    except RuntimeError as exc:
        if cancel is not None and cancel.is_set():
            raise AsciiCanceled("Generazione mappe interrotta.") from exc
        raise
    project.timings["maps"] = round(time.time() - started, 3)
    project.save()
    return manifest


def _maps_path(project) -> Path:
    return Path(project.spatial["dir"])


def render_window(project, start_frame: int, end_frame: int, out_dir: Path,
                  progress=None, cancel=None) -> list[Path]:
    """Render a short consecutive frame segment for selector sampling."""
    prepared = prepare(project, progress)
    data, plan = prepared["params"], prepared["plan"]
    total = plan["total_frames"]
    start_frame = max(1, int(start_frame))
    end_frame = min(total, int(end_frame))
    _ensure_maps(project, data, plan, end_frame, progress, cancel)
    out_dir.mkdir(parents=True, exist_ok=True)
    verification = project.path / "temp" / f"verification_segment_{start_frame}_{end_frame}.json"
    payload = _job_payload(project, data, plan, "segment", total, out_dir, verification,
                           start_frame=start_frame, end_frame=end_frame,
                           index_required=end_frame)
    _run_blender(project, payload, end_frame - start_frame + 1, out_dir,
                 progress, cancel, "Finestra selettore")
    _read_verification(project, verification, payload)
    return [out_dir / f"f_{i:04d}.png" for i in range(start_frame, end_frame + 1)]


def preview(project, progress=None, cancel=None) -> Path:
    prepared = prepare(project, progress)
    data, plan = prepared["params"], prepared["plan"]
    total = plan["total_frames"]
    preview_frames = max(1, min(120, int(round(min(4.0, project.working_info["duration"]) * 30))))
    _ensure_maps(project, data, plan, preview_frames, progress, cancel)
    frames = project.preview_frames_dir
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir(parents=True, exist_ok=True)
    verification = project.path / "temp" / "verification_preview.json"
    payload = _job_payload(project, data, plan, "preview", total, frames, verification,
                           preview_frames=preview_frames, index_required=preview_frames)
    render_seconds = _run_blender(project, payload, preview_frames, frames, progress, cancel, "Anteprima")
    project.timings["render_preview"] = round(render_seconds, 3)
    _read_verification(project, verification, payload)
    if _mode(project) == "spatial":
        spatial.validate_renders(frames, _maps_path(project), preview_frames,
                                 data["grid"]["cols"], data["grid"]["rows"])
    out = project.path / "preview" / "preview.mp4"
    _progress(progress, preview_frames, preview_frames, 0, "Codifica anteprima")
    media.encode_frames(project, frames, out, kind="preview")
    project.preview = str(out)
    project.status = "preview"
    project.save()
    return out


def still(project, at: float, progress=None, cancel=None) -> Path:
    prepared = prepare(project, progress)
    data, plan = prepared["params"], prepared["plan"]
    total = plan["total_frames"]
    frame = max(1, min(total, int(round(float(at) * 30)) + 1))
    _ensure_maps(project, data, plan, frame, progress, cancel)
    out = project.path / "preview" / f"still_{frame:04d}.png"
    verification = project.path / "temp" / "verification_still.json"
    payload = _job_payload(project, data, plan, "still", total, project.path / "preview",
                           verification, still_frame=frame, still_path=str(out),
                           index_required=frame)
    _run_blender(project, payload, 1, project.path / "preview", progress, cancel, "Frame singolo")
    _read_verification(project, verification, payload)
    if not out.exists():
        raise RuntimeError("Frame singolo non prodotto.")
    project.preview = str(out)
    project.status = "still"
    project.save()
    return out


def render(project, progress=None, cancel=None) -> dict:
    prepared = prepare(project, progress)
    data, plan = prepared["params"], prepared["plan"]
    total = plan["total_frames"]
    _ensure_maps(project, data, plan, total, progress, cancel)
    signature = _signature(project, data["sockets"], plan)
    frames = project.frames_dir
    if project.render_key and project.render_key != signature and frames.exists():
        shutil.rmtree(frames)
    project.render_key = signature
    frames.mkdir(parents=True, exist_ok=True)
    start = _next_frame(frames, total)
    verification = project.path / "temp" / "verification_full.json"
    payload = _job_payload(project, data, plan, "full", total, frames, verification,
                           start_frame=start, index_required=total)
    if start <= total:
        render_seconds = _run_blender(project, payload, total, frames, progress, cancel,
                                      "Rendering completo")
        project.timings["render"] = round(render_seconds, 3)
    _read_verification(project, verification, payload)
    if _count_frames(frames) < total:
        raise RuntimeError(f"Frame mancanti: {_count_frames(frames)}/{total}.")
    if _mode(project) == "spatial":
        step = 1 if total <= 900 else max(1, total // 450)
        spatial.validate_renders(frames, _maps_path(project), total,
                                 data["grid"]["cols"], data["grid"]["rows"], sample_step=step)
    _progress(progress, total, total, 0, "Codifica master")
    started = time.time()
    master = media.encode_frames(project, frames, project.master_path, kind="master")
    _progress(progress, total, total, 0, "Codifica YouTube")
    youtube = media.encode_frames(project, frames, project.youtube_path, kind="youtube")
    project.timings["encode"] = round(time.time() - started, 3)
    master_info = media.probe(master)
    youtube_info = media.probe(youtube)
    expected_duration = project.working_info["duration"]
    if abs(master_info["duration"] - expected_duration) > 0.2:
        raise RuntimeError(f"Durata master inattesa: {master_info['duration']} vs {expected_duration}")
    project.outputs = {
        "master": str(master), "youtube": str(youtube),
        "master_info": master_info, "youtube_info": youtube_info,
    }
    project.status = "done"
    project.save()
    _progress(progress, total, total, 0, "Completato")
    return project.outputs
