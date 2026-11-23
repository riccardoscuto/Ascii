from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from gcf.capture.obs import Obs
from gcf.capture.takes import (
    crop_rect,
    frame_at,
    list_takes,
    make_vertical_mp4,
    make_vertical_preview,
    probe,
    select_take,
    slug,
    take_id,
    write_take_metadata,
)
from gcf.config import ROOT, ffmpeg_bin, ffprobe_bin, project_dir
from gcf.ascii.project import AsciiProject
from gcf.ascii import preset as ascii_preset
from gcf.ascii import render as ascii_render
from gcf.ascii import selector as ascii_selector
from gcf.guess.cover import build_cover
from gcf.guess.round import InsufficientMaterial
from gcf.guess.short import build_game_round, build_short
from gcf.gui.project import Project


def parse_durations(value: str) -> tuple[float, ...]:
    try:
        parts = tuple(float(x) for x in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Formato durate: 2,2,2,3") from exc
    if len(parts) != 4 or any(p <= 0 for p in parts):
        raise argparse.ArgumentTypeError("Servono quattro durate positive: 2,2,2,3")
    return parts


def parse_size(value: str) -> tuple[int, int]:
    try:
        w, h = value.lower().split("x")
        w, h = int(w), int(h)
    except Exception as exc:
        raise argparse.ArgumentTypeError("Formato size: WxH, es. 1920x1080") from exc
    if w < 2 or h < 2 or w > 4096 or h > 4096:
        raise argparse.ArgumentTypeError("Dimensioni fuori range (2..4096).")
    return w, h


def cmd_doctor(_args) -> None:
    print("GCF Capture - doctor")
    print("root:", ROOT)
    print("ffmpeg:", ffmpeg_bin())
    print("ffprobe:", ffprobe_bin())
    portable = ROOT / "tools" / "obs-portable"
    print("obs portable:", portable, "OK" if (portable / "bin" / "64bit" / "obs64.exe").exists() else "MANCANTE")
    print("obs config:", (portable / "config" / "obs-studio"))
    personal = Path(os.environ.get("APPDATA", "")) / "obs-studio"
    print("obs personale:", personal, "(non usato dal tool)")


def cmd_setup(_args) -> None:
    obs = Obs()
    obs.ensure_running()
    version, ws = obs.version()
    video = obs.client.get_video_settings()
    print(f"OBS {version} / obs-websocket {ws}")
    print("video:", video.base_width, video.base_height, "->", video.output_width, video.output_height,
          f"{video.fps_numerator}/{video.fps_denominator}")
    print("scenes:", [s["sceneName"] for s in obs.client.get_scene_list().scenes])
    print("profile/collection: GCF / GCF (portable)")
    obs.close()


def cmd_windows(args) -> None:
    obs = Obs()
    items = obs.list_windows(args.kind)
    print(f"Finestre/capture disponibili ({args.kind}):")
    for i, item in enumerate(items):
        if not item.get("itemEnabled"):
            continue
        print(f" [{i}] {item['itemName']}")
    obs.close()


def cmd_close(_args) -> None:
    obs = Obs()
    pids = obs.close_portable()
    if pids:
        print("OBS portable chiuso, PID:", ", ".join(pids))
    else:
        print("Nessun OBS portable in esecuzione.")


def cmd_takes(args) -> None:
    rows = list_takes(project_dir(args.project), args.game)
    if not rows:
        print("Nessun take.")
        return
    for row in rows:
        mark = "*" if row["selected"] else " "
        print(f"{mark} {row['game']}/{row['take_id']}  {row['size'][0]}x{row['size'][1]} "
              f"{row['fps']}fps  {row['duration']}s  {row['capture']}")
        print(f"   {row['mp4']}")


def cmd_select(args) -> None:
    select_take(project_dir(args.project), args.game, args.take_id)
    print(f"Take selezionato: {args.game}/{args.take_id}")


def _prepare(obs: Obs, args) -> tuple:
    if args.size:
        width, height = args.size
    else:
        width, height = None, None
    setup = obs.setup_capture(
        capture=args.capture,
        width=width,
        height=height,
        window=args.window,
        monitor=args.monitor,
    )
    return setup


def cmd_preview(args) -> None:
    obs = Obs()
    setup = _prepare(obs, args)
    preview_dir = project_dir(args.project) / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    full = preview_dir / f"{slug(args.game)}_full.png"
    vertical = preview_dir / f"{slug(args.game)}_vertical.png"
    obs.screenshot(setup.scene, setup.width, setup.height, full)
    crop = crop_rect(setup.width, setup.height, args.offset)
    make_vertical_preview(full, vertical, crop)
    print("preview full:", full)
    print("preview verticale:", vertical)
    print("crop:", crop)
    print("scene:", setup.scene, "source:", setup.source)
    if args.open:
        os.startfile(vertical)
    obs.close()


def cmd_record(args) -> None:
    obs = Obs()
    setup = _prepare(obs, args)
    pdir = project_dir(args.project)
    tid = take_id(pdir, args.game)
    take_dir = pdir / "takes" / slug(args.game) / tid
    take_dir.mkdir(parents=True, exist_ok=True)

    preview_full = take_dir / "preview_full.png"
    preview_vertical = take_dir / "preview_vertical.png"
    obs.screenshot(setup.scene, setup.width, setup.height, preview_full)
    crop = crop_rect(setup.width, setup.height, args.offset)
    make_vertical_preview(preview_full, preview_vertical, crop)

    print("scene:", setup.scene, "source:", setup.source)
    print("crop previsto:", crop)
    print(f"registrazione {args.duration:.1f}s in {take_dir} ...")
    obs.start_record(take_dir)
    time.sleep(args.duration)
    mkv = obs.stop_record(take_dir)
    print("mkv:", mkv)
    source_info = probe(mkv)
    print("sorgente:", source_info)

    # The working take is vertical 1080x1920, silent. The MKV remains the
    # full-frame archival original.
    actual_crop = crop_rect(source_info["width"], source_info["height"], args.offset)
    mp4 = take_dir / "take.mp4"
    make_vertical_mp4(mkv, mp4, actual_crop)
    info = probe(mp4)
    print("take verticale:", info)

    verify = take_dir / "verify_vertical.png"
    frame_at(mp4, verify, at=min(1.0, max(0.0, info["duration"] / 2)))
    if actual_crop != crop:
        print("ATTENZIONE: dimensione registrata diversa dalla richiesta; crop aggiornato:", actual_crop)
        if actual_crop["w"] != crop["w"] or actual_crop["h"] != crop["h"]:
            make_vertical_preview(preview_full, preview_vertical, actual_crop)

    meta = write_take_metadata(
        project=args.project,
        game=args.game,
        take_dir=take_dir,
        capture=args.capture,
        target=setup.window or setup.monitor,
        requested_size=(setup.width, setup.height),
        crop=actual_crop,
        mkv=mkv,
        mp4=mp4,
        preview_full=preview_full,
        preview_vertical=preview_vertical,
        verify_vertical=verify,
    )
    print("take.json:", take_dir / "take.json")
    print("preview verticale:", preview_vertical)
    print("verifica verticale:", verify)
    print("sha256 mp4:", meta["sha256"]["mp4"])
    if args.open:
        os.startfile(verify)
    obs.close()


def cmd_guess_round(args) -> None:
    project = Project.load(project_dir(args.project))
    if args.game.isdigit():
        index = int(args.game) - 1
        if index < 0 or index >= len(project.games):
            raise SystemExit(f"Gioco fuori range: {args.game}")
    else:
        index = next(
            (i for i, g in enumerate(project.games)
             if g.title.casefold() == args.game.casefold()),
            -1,
        )
        if index < 0:
            raise SystemExit(f"Gioco non trovato: {args.game}")
    outdir = Path(args.outdir) if args.outdir else None
    manifest = build_game_round(
        project, index, outdir=outdir, number_text=args.number,
        durations=args.durations,
        beatmap_path=Path(args.beatmap) if args.beatmap else None,
        music_path=Path(args.music) if args.music else None,
    )
    out = Path(manifest["output"])
    if not out.is_absolute():
        out = ROOT / out
    print("round:", out)
    print("manifest:", out.parent / "manifest.json")
    print("events:", manifest["events"])
    print("sha256:", manifest["sha256"]["mp4"])
    if args.open:
        os.startfile(out)


def cmd_guess_cover(args) -> None:
    project = Project.load(project_dir(args.project))
    manifest = build_cover(project, title=args.title, duration=args.duration)
    out = Path(manifest["output"])
    if not out.is_absolute():
        out = ROOT / out
    print("cover:", out)
    print("preview:", ROOT / manifest["preview"])
    print("sha256:", manifest["sha256"]["mp4"])
    if args.open:
        os.startfile(out)


def cmd_gui(_args) -> None:
    from gcf.gui.app import run
    run()


def _ascii_project(args) -> AsciiProject:
    project = AsciiProject.load(Path(args.project))
    project.ascii_mode = args.mode
    project.spatial_variant = args.variant
    if args.density:
        project.params["density"] = int(args.density)
    elif args.mode == "spatial" and int(project.params.get("density", 54)) < 81:
        project.params["density"] = 81
    project.save()
    return project


def _ascii_progress(done, total, elapsed, eta, stage):
    if total <= 0:
        print(f"{stage}...")
        return
    if done == total or done == 1 or done % 30 == 0:
        print(f"{stage}: {done}/{total} frame, {elapsed:.0f}s")


def cmd_ascii_preview(args) -> None:
    project = _ascii_project(args)
    out = ascii_render.preview(project, _ascii_progress)
    print("preview:", out)


def cmd_ascii_still(args) -> None:
    project = _ascii_project(args)
    out = ascii_render.still(project, args.at, _ascii_progress)
    print("still:", out)


def cmd_ascii_auto(args) -> None:
    project = AsciiProject.load(Path(args.project))
    evidence = Path(args.evidence) if args.evidence else project.path / "selector_evidence"
    plan = ascii_selector.select(project, evidence, _ascii_progress)
    choices = {row["shot"]: row["selected"] for row in plan["shots"]}
    out = Path(args.out) if args.out else project.output_dir / "auto.mp4"
    ascii_selector.render_plan(plan, project, choices, out, _ascii_progress)
    print("selection:", project.selection_plan)
    print("auto video:", out)
    print("choices:", choices)


def cmd_ascii_render(args) -> None:
    project = _ascii_project(args)
    out = ascii_render.render(project, _ascii_progress)
    print("master:", out["master"])
    print("youtube:", out["youtube"])
    print("mode:", project.ascii_mode, "variant:", project.spatial_variant,
          "grid:", ascii_preset.grid_for(project.format, int(project.params["density"])))
    print("timings:", project.timings)


def cmd_guess_short(args) -> None:
    manifest = build_short(
        args.project,
        beatmap_path=Path(args.beatmap) if args.beatmap else None,
        durations=args.durations,
        music_path=Path(args.music) if args.music else None,
    )
    out = ROOT / manifest["output"]
    print("short:", out)
    print("manifest:", out.parent / "manifest.json")
    print("duration:", manifest["duration"])
    print("sha256:", manifest["sha256"]["output"])
    if args.open:
        os.startfile(out)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gcf", description="Gaming Content Factory")
    sub = p.add_subparsers(dest="cmd", required=True)

    cap = sub.add_parser("capture", help="OBS capture")
    cap_sub = cap.add_subparsers(dest="action", required=True)

    d = cap_sub.add_parser("doctor", help="check environment")
    d.set_defaults(func=cmd_doctor)

    s = cap_sub.add_parser("setup", help="launch/verify portable OBS")
    s.set_defaults(func=cmd_setup)

    c = cap_sub.add_parser("close", help="close only the portable OBS instance")
    c.set_defaults(func=cmd_close)

    w = cap_sub.add_parser("windows", help="list capture windows")
    w.add_argument("--kind", choices=["window_capture", "game_capture", "monitor_capture"],
                   default="window_capture")
    w.set_defaults(func=cmd_windows)

    tk = cap_sub.add_parser("takes", help="list recorded takes")
    tk.add_argument("--project", required=True)
    tk.add_argument("--game", default=None)
    tk.set_defaults(func=cmd_takes)

    sel = cap_sub.add_parser("select", help="select the preferred take")
    sel.add_argument("--project", required=True)
    sel.add_argument("--game", required=True)
    sel.add_argument("--take-id", required=True)
    sel.set_defaults(func=cmd_select)

    def common(sp):
        sp.add_argument("--project", required=True)
        sp.add_argument("--game", required=True)
        sp.add_argument("--capture", choices=["screen", "window", "game"], default="screen")
        sp.add_argument("--size", type=parse_size, default=None,
                        help="WxH; se omesso, rileva la dimensione della sorgente")
        sp.add_argument("--window", default=None)
        sp.add_argument("--monitor", type=int, default=None)
        sp.add_argument("--offset", type=int, default=0)
        sp.add_argument("--open", action="store_true")

    pv = cap_sub.add_parser("preview", help="capture a vertical preview")
    common(pv)
    pv.set_defaults(func=cmd_preview)

    rec = cap_sub.add_parser("record", help="record a take")
    common(rec)
    rec.add_argument("--duration", type=float, default=8.0)
    rec.set_defaults(func=cmd_record)

    guess = sub.add_parser("guess", help="Guess the Game")
    guess_sub = guess.add_subparsers(dest="action", required=True)
    rnd = guess_sub.add_parser("round", help="rebuild one round from its four clips")
    rnd.add_argument("--project", required=True)
    rnd.add_argument("--game", required=True, help="game title or 1-based index")
    rnd.add_argument("--number", default=None, help="round number text, e.g. '1.'")
    rnd.add_argument("--outdir", default=None)
    rnd.add_argument("--durations", type=parse_durations, default=None,
                     help="quattro durate in secondi: 2,2,2,3")
    rnd.add_argument("--beatmap", default=None, help="beatmap JSON della musica")
    rnd.add_argument("--music", default=None, help="traccia audio del round")
    rnd.add_argument("--open", action="store_true")
    rnd.set_defaults(func=cmd_guess_round)

    cv = guess_sub.add_parser("cover", help="build only the intro cover")
    cv.add_argument("--project", required=True)
    cv.add_argument("--title", default=None)
    cv.add_argument("--duration", type=float, default=None)
    cv.add_argument("--open", action="store_true")
    cv.set_defaults(func=cmd_guess_cover)

    sh = guess_sub.add_parser("short", help="build the full 60s Short")
    sh.add_argument("--project", required=True)
    sh.add_argument("--durations", type=parse_durations, default=None,
                    help="quattro durate in secondi: 2,2,2,3")
    sh.add_argument("--beatmap", default=None, help="beatmap JSON della musica")
    sh.add_argument("--music", default=None, help="traccia audio del montaggio")
    sh.add_argument("--open", action="store_true")
    sh.set_defaults(func=cmd_guess_short)

    gui = sub.add_parser("gui", help="Gaming Content Factory desktop app")
    gui.set_defaults(func=cmd_gui)

    asc = sub.add_parser("ascii", help="ASCII backend (Legacy / Spatial)")
    asc_sub = asc.add_subparsers(dest="action", required=True)

    def ascii_common(sp):
        sp.add_argument("--project", required=True)
        sp.add_argument("--mode", choices=["legacy", "spatial", "auto"], default="legacy")
        sp.add_argument("--variant", choices=["d", "conservative", "adaptive", "adaptive-conservative", "global"], default="d")
        sp.add_argument("--density", type=int, default=None,
                        help="griglia: 81 = 144x81 orizzontale")

    ap = asc_sub.add_parser("preview", help="anteprima 4 s")
    ascii_common(ap)
    ap.set_defaults(func=cmd_ascii_preview)

    ast = asc_sub.add_parser("still", help="frame singolo")
    ascii_common(ast)
    ast.add_argument("--at", type=float, default=0.0)
    ast.set_defaults(func=cmd_ascii_still)

    ar = asc_sub.add_parser("render", help="rendering completo")
    ascii_common(ar)
    ar.set_defaults(func=cmd_ascii_render)

    aa = asc_sub.add_parser("auto", help="prototipo offline del selettore Auto")
    aa.add_argument("--project", required=True)
    aa.add_argument("--evidence", default=None)
    aa.add_argument("--out", default=None)
    aa.set_defaults(func=cmd_ascii_auto)

    return p


def main() -> None:
    args = build_parser().parse_args()
    try:
        args.func(args)
    except InsufficientMaterial as exc:
        raise SystemExit(str(exc)) from None
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    main()
