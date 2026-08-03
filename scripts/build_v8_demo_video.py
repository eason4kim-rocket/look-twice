#!/usr/bin/env python3
"""Build the 239-second English Look Twice V8 competition demo.

The builder uses only V8 competition artifacts:

* the recorded 30-second V8 Evidence Console reel;
* the latest rendered V8 technical report;
* V8 RGB/depth/corridor-mask snapshots;
* the frozen locked report and hash-pinned Radeon benchmark;
* hash-pinned OpenAI text-to-speech narration; and
* a real terminal audit recorded from ``scripts/video/v8-audit.tape``.

It intentionally does not consume the historical V2/V3 demo directory.  The
public replay is labelled as a non-locked seed-105400 confirmatory example,
while aggregate performance is sourced only from the locked report.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
WIDTH = 1920
HEIGHT = 1080
FPS = 30
TOTAL_DURATION_SECONDS = 239

NARRATION_MODEL = "gpt-4o-mini-tts"
NARRATION_VOICE = "cedar"
NARRATION_INSTRUCTIONS = (
    "Neutral American English. Calm, credible technical-documentary tone; "
    "restrained, not promotional. Natural conversational delivery at "
    "approximately 135 words per minute. Keep pitch, energy, accent, and "
    "cadence consistent across chapters. Use short sentence pauses and "
    "declarative endings. Enunciate acronyms and metrics precisely. Light "
    "emphasis only on Look Twice, Action Contract, Belief Gap, opened once, "
    "and simulation only. Avoid hype, theatricality, trailer cadence, "
    "breathiness, and upward inflection."
)

OFFICIAL_STAGING = (
    ROOT
    / "submission"
    / "official-repo"
    / "submissions"
    / "Track3-eason4kim-rocket-Look-Twice"
)

BG = (5, 13, 16)
PANEL = (12, 27, 31)
PANEL_2 = (18, 36, 40)
INK = (240, 246, 244)
MUTED = (158, 181, 181)
TEAL = (53, 219, 209)
TEAL_DARK = (21, 91, 91)
AMBER = (246, 185, 84)
GREEN = (155, 224, 132)
RED = (240, 111, 103)


@dataclass(frozen=True)
class Chapter:
    slug: str
    start_seconds: int
    duration_seconds: int
    title: str
    spoken_text: str
    boundary: str

    @property
    def end_seconds(self) -> int:
        return self.start_seconds + self.duration_seconds


# Spoken forms are the exact inputs used for the hash-pinned OpenAI narration.
# Exact technical notation remains visible in the corresponding artwork.
CHAPTERS = (
    Chapter(
        "hook",
        0,
        21,
        "Action assurance before action",
        (
            "Many confident outputs can still come from one physical "
            "observation. Look Twice is an assurance layer before robot "
            "action. It asks whether the evidence is independent, fresh, "
            "calibrated, and specific to this corridor. If not, the robot "
            "looks again before it moves."
        ),
        "POSITIONING · SIMULATION-ONLY RESEARCH",
    ),
    Chapter(
        "problem",
        21,
        22,
        "One capture is not a committee",
        (
            "Our test case is a warehouse robot deciding whether to cross a "
            "corridor. Camera, depth, and map evidence may be noisy, stale, "
            "correlated, or contradictory. If several outputs come from the "
            "same capture, counting them as independent votes creates "
            "confidence without new evidence."
        ),
        "V8 SENSOR SNAPSHOTS · ONE PHYSICAL CAPTURE ROOT",
    ),
    Chapter(
        "architecture",
        43,
        30,
        "Lineage-aware action qualification",
        (
            "V-eight projects the intended corridor into the image and runs a "
            "spatial R-G-B-D model on an A-M-D Radeon G-P-U. Every output "
            "becomes a Claim with time, scope, calibration, and physical "
            "lineage. Conformal prediction marks the corridor clear, blocked, "
            "or inconclusive. A scoped Action Contract checks the evidence. "
            "Direct motion requires agreement from both the Python controller "
            "and the independent Purify Go core."
        ),
        "LATEST TECHNICAL REPORT · SYSTEM ARCHITECTURE",
    ),
    Chapter(
        "active",
        73,
        39,
        "BeliefGap-driven active evidence repair",
        (
            "In this non-locked confirmatory replay, the carrier's front view "
            "suggests that the corridor is clear. The contract still denies "
            "direct motion because that view provides only one physical root. "
            "The denial reports a Belief Gap: acquire an independent side "
            "view. A scout moves to the diagnostic viewpoint and captures new "
            "R-G-B-D evidence. Color and depth from that capture still count "
            "as one root. The contract is evaluated again. Only agreement "
            "between Python and Purify unlocks the direct route."
        ),
        "NON-LOCKED CONFIRMATORY REPLAY · SEED 105400",
    ),
    Chapter(
        "passive",
        112,
        19,
        "Safety baseline versus recovered task utility",
        (
            "The passive policy receives the same initial denial but does not "
            "acquire more evidence. It stays safe by taking the disclosed "
            "detour. The comparison separates two ideas: denial prevents an "
            "unsupported action; active perception can recover useful motion."
        ),
        "LOCKED FULL-CHAIN · 12 PAIRED SEEDS",
    ),
    Chapter(
        "results",
        131,
        37,
        "Opened once; denominator retained",
        (
            "The locked test was opened once, with no retuning or retraining "
            "afterward. It includes three thousand two hundred offline samples "
            "and twelve paired live worlds. The predeclared offline gates "
            "passed, with three thousand one decisive samples and no "
            "false-clear singletons. Active repair qualified the direct route "
            "in eleven of twelve worlds; passive qualified none, a ninety-one "
            "point seven percentage-point gain. Both completed every mission. "
            "Across all twenty-four policy runs, unsafe crossings and "
            "unplanned fallbacks were zero. The conservative active detour "
            "remains in the denominator."
        ),
        "AUTHORITATIVE LOCKED REPORT · OPENED ONCE",
    ),
    Chapter(
        "amd",
        168,
        37,
        "Radeon execution with a disclosed boundary",
        (
            "The recorded closed loop used one Radeon Cloud G-F-X eleven "
            "hundred G-P-U through rock-em. Genesis simulation, R-G-B-D "
            "rendering, tensor preprocessing, and spatial model inference ran "
            "on the G-P-U. The Purify contract gate remained a small, "
            "independent Go process on the C-P-U. A separate, hash-pinned F-P "
            "thirty-two benchmark measured one hundred ninety-two point three "
            "one milliseconds at P-fifty for batch one, and six point two five "
            "images per second for batch eight. These are model-forward "
            "results with preloaded tensors, not end-to-end robot latency."
        ),
        "HASH-PINNED FROZEN MODEL · MODEL FORWARD ONLY",
    ),
    Chapter(
        "reproduction",
        205,
        22,
        "Receipts and hashes, not a black box",
        (
            "Judges can rebuild the public replays, verify every guarded hash, "
            "inspect the source episodes and gate receipts, test the Go core, "
            "and start the Evidence Console with Docker. The site needs no "
            "live G-P-U; it replays the exact recorded A-M-D simulation evidence."
        ),
        "REAL COMMAND OUTPUT · CPU EVIDENCE AUDIT",
    ),
    Chapter(
        "close",
        227,
        12,
        "A concrete next observation",
        (
            "If not, the robot looks again."
        ),
        "TRACK 3 · PHYSICAL AI · SIMULATION ONLY",
    ),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    printable = " ".join(command)
    print(f"+ {printable}", flush=True)
    return subprocess.run(
        list(command),
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def require_programs(names: Iterable[str]) -> None:
    missing = [name for name in names if shutil.which(name) is None]
    if missing:
        raise SystemExit("missing required programs: " + ", ".join(missing))


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"expected JSON object: {path}")
    return value


def probe_media(path: Path) -> dict[str, Any]:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        capture=True,
    )
    return json.loads(result.stdout)


def media_duration(path: Path) -> float:
    return float(probe_media(path)["format"]["duration"])


def ensure_v8_only(paths: Iterable[Path]) -> None:
    forbidden = ("/assets/demo/", "/v2/", "/v3/")
    for path in paths:
        normalized = "/" + path.resolve().as_posix().lower().lstrip("/")
        if any(token in normalized for token in forbidden):
            raise SystemExit(f"historical V2/V3 media is forbidden: {path}")


def repository_path(path: Path) -> str:
    """Return a stable repository-relative path when one is available."""
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return f"external-input/{path.name}"


def font_path(*, mono: bool = False) -> Path:
    candidates = (
        (
            Path("/System/Library/Fonts/SFNSMono.ttf"),
            Path("/System/Library/Fonts/Supplemental/Menlo.ttc"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
        )
        if mono
        else (
            Path("/System/Library/Fonts/SFNS.ttf"),
            Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        )
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise SystemExit("no suitable system font found")


def font(size: int, *, mono: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(font_path(mono=mono)), size=size)


def fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    starting_size: int,
    *,
    minimum_size: int = 28,
    mono: bool = False,
) -> ImageFont.FreeTypeFont:
    for size in range(starting_size, minimum_size - 1, -2):
        candidate = font(size, mono=mono)
        if draw.textbbox((0, 0), text, font=candidate)[2] <= max_width:
            return candidate
    return font(minimum_size, mono=mono)


def wrap_pixels(
    draw: ImageDraw.ImageDraw,
    text: str,
    active_font: ImageFont.FreeTypeFont,
    width: int,
) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            trial = f"{current} {word}"
            if draw.textbbox((0, 0), trial, font=active_font)[2] <= width:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    active_font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
    width: int,
    *,
    spacing: int = 12,
) -> int:
    x, y = xy
    lines = wrap_pixels(draw, text, active_font, width)
    line_height = active_font.size + spacing
    for line in lines:
        draw.text((x, y), line, font=active_font, fill=fill)
        y += line_height
    return y


def rounded_panel(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    *,
    fill: tuple[int, int, int] = PANEL,
    outline: tuple[int, int, int] = TEAL_DARK,
    radius: int = 24,
    width: int = 2,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def base_slide(kicker: str, title: str, footer: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 12), fill=TEAL)
    draw.text((72, 48), kicker.upper(), font=font(24, mono=True), fill=TEAL)
    title_font = fit_font(draw, title, WIDTH - 144, 72, minimum_size=52)
    draw.text((72, 92), title, font=title_font, fill=INK)
    draw.line((72, 194, WIDTH - 72, 194), fill=(38, 70, 73), width=2)
    draw.text((72, HEIGHT - 54), footer, font=font(20, mono=True), fill=MUTED)
    draw.text(
        (WIDTH - 72, HEIGHT - 54),
        "LOOK TWICE · V8 FROZEN",
        font=font(20, mono=True),
        fill=MUTED,
        anchor="ra",
    )
    return image, draw


def contain_image(
    canvas: Image.Image,
    source: Path | Image.Image,
    box: tuple[int, int, int, int],
    *,
    background: tuple[int, int, int] = PANEL,
    border: tuple[int, int, int] = TEAL_DARK,
    radius: int = 20,
) -> None:
    x1, y1, x2, y2 = box
    width, height = x2 - x1, y2 - y1
    panel = Image.new("RGB", (width, height), background)
    raw = source.copy() if isinstance(source, Image.Image) else Image.open(source).convert("RGB")
    fitted = ImageOps.contain(raw, (width - 28, height - 28), method=Image.Resampling.LANCZOS)
    panel.paste(fitted, ((width - fitted.width) // 2, (height - fitted.height) // 2))
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, width, height), radius=radius, fill=255)
    canvas.paste(panel, (x1, y1), mask)
    ImageDraw.Draw(canvas).rounded_rectangle(box, radius=radius, outline=border, width=2)


def cover_image(source: Path, size: tuple[int, int]) -> Image.Image:
    raw = Image.open(source).convert("RGB")
    return ImageOps.fit(raw, size, method=Image.Resampling.LANCZOS)


def save_slide(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG", optimize=True)


def render_pdf_page(pdf: Path, page: int, output: Path) -> Path:
    prefix = output.with_suffix("")
    run(
        [
            "pdftoppm",
            "-f",
            str(page),
            "-l",
            str(page),
            "-r",
            "150",
            "-png",
            "-singlefile",
            str(pdf),
            str(prefix),
        ]
    )
    rendered = prefix.with_suffix(".png")
    if not rendered.is_file():
        raise SystemExit(f"PDF page render missing: {rendered}")
    return rendered


def make_hook_slide(poster: Path, output: Path) -> None:
    background = cover_image(poster, (WIDTH, HEIGHT)).filter(ImageFilter.GaussianBlur(1.5))
    background = ImageEnhance.Brightness(background).enhance(0.26)
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (2, 10, 12, 80))
    image = Image.alpha_composite(background.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 12), fill=TEAL)
    draw.text((76, 68), "AMD AI DEVMASTER · TRACK 3 · PHYSICAL AI", font=font(25, mono=True), fill=TEAL)
    draw.text((76, 170), "LOOK TWICE", font=font(108), fill=INK)
    draw.text((82, 298), "Active Evidence Assurance", font=font(48), fill=TEAL)
    rounded_panel(draw, (76, 430, 1000, 708), fill=(5, 17, 20), outline=TEAL_DARK)
    draw.text((112, 468), "ACTION ASSURANCE BEFORE ACTION", font=font(30, mono=True), fill=AMBER)
    draw_wrapped(
        draw,
        (112, 528),
        "Many derived Claims can still represent one physical observation.",
        font(42),
        INK,
        820,
        spacing=15,
    )
    draw.text((80, 846), "MORE CLAIMS  ≠  MORE INDEPENDENT EVIDENCE", font=font(34, mono=True), fill=INK)
    draw.text((80, 930), "SIMULATION ONLY · NOT A SAFETY-CERTIFICATION CLAIM", font=font(24, mono=True), fill=MUTED)
    save_slide(image, output)


def make_problem_slide(media_dir: Path, output: Path) -> None:
    image, draw = base_slide(
        "THE FAILURE MODE",
        "One capture is not a committee",
        "V8 SENSOR SNAPSHOTS · NON-LOCKED CONFIRMATORY SEED 105400",
    )
    sources = (
        ("RGB", media_dir / "frame-1-rgb.webp"),
        ("DEPTH", media_dir / "frame-1-depth.webp"),
        ("CORRIDOR ROI", media_dir / "frame-1-mask.webp"),
    )
    panel_width = 548
    gap = 34
    start_x = 72
    for index, (label, path) in enumerate(sources):
        x = start_x + index * (panel_width + gap)
        contain_image(image, path, (x, 254, x + panel_width, 676))
        draw.text((x + 24, 702), label, font=font(24, mono=True), fill=TEAL)
        draw.text((x + panel_width - 24, 702), "ROOT 01", font=font(24, mono=True), fill=AMBER, anchor="ra")
    rounded_panel(draw, (72, 778, WIDTH - 72, 974), fill=PANEL_2)
    draw.text((108, 814), "ONE PHYSICAL CAPTURE ROOT", font=font(35, mono=True), fill=AMBER)
    draw_wrapped(
        draw,
        (108, 866),
        "RGB, depth and a projected mask derived from the same capture do not become three independent observations.",
        font(32),
        INK,
        WIDTH - 216,
        spacing=10,
    )
    save_slide(image, output)


def make_architecture_slide(pdf_page: Path, output: Path) -> None:
    image, draw = base_slide(
        "V8 SYSTEM ARCHITECTURE",
        "Lineage-aware action qualification",
        "LATEST TECHNICAL REPORT · PAGE 3",
    )
    rounded_panel(draw, (72, 238, 850, 958), fill=PANEL_2)
    pipeline = (
        ("01", "RGB-D + corridor geometry"),
        ("02", "Spatial Claims + physical lineage"),
        ("03", "Split-conformal prediction sets"),
        ("04", "Scoped Action Contract"),
        ("05", "Python admit  ∧  Purify Go admit"),
        ("06", "Direct · repair · detour · fail closed"),
    )
    y = 280
    for number, label in pipeline:
        draw.rounded_rectangle((112, y, 178, y + 54), radius=14, fill=TEAL_DARK, outline=TEAL)
        draw.text((145, y + 27), number, font=font(22, mono=True), fill=INK, anchor="mm")
        draw.text((208, y + 27), label, font=font(29), fill=INK, anchor="lm")
        if number != "06":
            draw.line((145, y + 58, 145, y + 82), fill=TEAL, width=3)
        y += 101
    contain_image(image, pdf_page, (900, 238, WIDTH - 72, 958), background=(236, 233, 222))
    save_slide(image, output)


def make_reel_overlay(output: Path) -> None:
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 46), fill=(5, 13, 16, 244))
    draw.text(
        (40, 23),
        "NON-LOCKED CONFIRMATORY REPLAY · SEED 105400 · RECORDED AMD GPU EVIDENCE",
        font=font(19, mono=True),
        fill=INK,
        anchor="lm",
    )
    draw.text(
        (WIDTH - 40, 23),
        "SIMULATION ONLY",
        font=font(19, mono=True),
        fill=AMBER,
        anchor="rm",
    )
    image.save(output, "PNG", optimize=True)


def make_passive_slide(locked: dict[str, Any], media_dir: Path, output: Path) -> dict[str, Any]:
    gates = locked["live_fullchain"]["gates"]
    n_active = int(gates["n_active"])
    n_passive = int(gates["n_passive"])
    active_direct = int(gates["active_full_chain_direct"])
    passive_detours = int(gates["passive_detour"])
    passive_direct = n_passive - passive_detours
    unsafe = int(gates["unsafe_total"])
    total_runs = n_active + n_passive
    active_rate = active_direct / n_active
    passive_rate = passive_direct / n_passive
    uplift_pp = 100.0 * (active_rate - passive_rate)

    image, draw = base_slide(
        "LOCKED FULL-CHAIN · 12 PAIRED SEEDS",
        "Safety baseline versus recovered task utility",
        "AUTHORITATIVE LOCKED REPORT · PASSIVE 12/12 DENY → DETOUR",
    )
    contain_image(image, media_dir / "frame-1-rgb.webp", (72, 270, 662, 712))
    cards = (
        ("ACTIVE DIRECT", f"{active_direct}/{n_active}", f"{active_rate * 100:.1f}%", TEAL),
        ("PASSIVE DIRECT", f"{passive_direct}/{n_passive}", f"{passive_rate * 100:.1f}%", AMBER),
        ("ACTIVE UPLIFT", f"+{uplift_pp:.1f}pp", "paired locked seeds", GREEN),
        ("UNSAFE CROSSINGS", f"{unsafe}/{total_runs}", "active + passive", GREEN),
    )
    x_positions = (720, 1290)
    y_positions = (270, 588)
    index = 0
    for y in y_positions:
        for x in x_positions:
            label, value, detail, color = cards[index]
            rounded_panel(draw, (x, y, x + 510, y + 258), fill=PANEL_2, outline=color)
            draw.text((x + 34, y + 35), label, font=font(23, mono=True), fill=MUTED)
            value_font = fit_font(draw, value, 442, 72, minimum_size=52, mono=True)
            draw.text((x + 34, y + 92), value, font=value_font, fill=color)
            draw.text((x + 34, y + 205), detail, font=font(22), fill=INK)
            index += 1
    rounded_panel(draw, (72, 778, 662, 952), fill=PANEL_2, outline=AMBER)
    draw.text((108, 816), "PASSIVE POLICY", font=font(25, mono=True), fill=AMBER)
    draw.text((108, 862), "DENY  →  SAFE DETOUR", font=font(34), fill=INK)
    draw.text((108, 912), "Safe, but uncertainty remains unresolved.", font=font(24), fill=MUTED)
    save_slide(image, output)
    return {
        "n_active": n_active,
        "n_passive": n_passive,
        "active_direct": active_direct,
        "passive_direct": passive_direct,
        "passive_detours": passive_detours,
        "active_uplift_percentage_points": round(uplift_pp, 1),
        "unsafe_total": unsafe,
        "total_policy_runs": total_runs,
    }


def make_results_slide(
    locked: dict[str, Any],
    locked_report_sha256: str,
    pdf_page: Path,
    output: Path,
) -> None:
    offline = locked["offline"]["metrics"]
    live = locked["live_fullchain"]["gates"]
    image, draw = base_slide(
        "PREDECLARED LOCKED SPLIT · OPENED ONCE",
        "Opened once; denominator retained",
        f"LOCKED REPORT SHA256 · {locked_report_sha256[:20]}…",
    )
    metrics = (
        ("OFFLINE SAMPLES", f"{int(offline['n_samples']):,}"),
        ("DECISIVE", f"{int(offline['n_decisive']):,}/{int(offline['n_samples']):,}"),
        ("ROI IoU", f"{float(offline['roi_iou']):.3f}"),
        ("BALANCED ACCURACY", f"{float(offline['balanced_accuracy_decisive']):.3f}"),
        ("BLOCKED RECALL", f"{float(offline['blocked_recall_decisive']):.3f}"),
        ("CONFORMAL COVERAGE", f"{float(offline['coverage']):.3f}"),
        ("ACTIVE DIRECT", f"{int(live['active_full_chain_direct'])}/{int(live['n_active'])}"),
        ("UNSAFE", f"{int(live['unsafe_total'])}/{int(live['n_active']) + int(live['n_passive'])}"),
    )
    rounded_panel(draw, (72, 238, 842, 958), fill=PANEL_2)
    y = 274
    for label, value in metrics:
        draw.text((112, y), label, font=font(22, mono=True), fill=MUTED)
        draw.text((796, y), value, font=font(29, mono=True), fill=TEAL, anchor="ra")
        draw.line((112, y + 45, 796, y + 45), fill=(39, 68, 71), width=1)
        y += 78
    draw.text((112, 909), "ONE ACTIVE SEED DETOURED · RETAINED IN DENOMINATOR", font=font(18, mono=True), fill=AMBER)
    contain_image(image, pdf_page, (892, 238, WIDTH - 72, 958), background=(236, 233, 222))
    save_slide(image, output)


def make_amd_slide(benchmark: dict[str, Any], pdf_page: Path, output: Path) -> None:
    runtime = benchmark["runtime"]
    results = {int(item["batch_size"]): item for item in benchmark["results"]}
    b1 = results[1]
    b8 = results[8]
    image, draw = base_slide(
        "AMD RADEON GPU + ROCm",
        "Radeon execution with a disclosed boundary",
        "SEPARATE NON-LOCKED PERFORMANCE CHARACTERIZATION · NOT ACCURACY",
    )
    rounded_panel(draw, (72, 238, 842, 958), fill=PANEL_2)
    rows = (
        ("GPU ISA", str(runtime["gcn_arch_name"])),
        ("HIP", str(runtime["hip"])),
        ("MODEL", "39.8M parameters · FP32"),
        ("B1 P50", f"{float(b1['latency_ms']['median_p50']):.2f} ms"),
        ("B1 P95", f"{float(b1['latency_ms']['p95']):.2f} ms"),
        ("B8 THROUGHPUT", f"{float(b8['throughput_images_per_second']):.2f} img/s"),
        ("B8 PEAK ALLOCATED", f"{float(b8['memory_mib']['peak_allocated']):.2f} MiB"),
    )
    y = 282
    for label, value in rows:
        draw.text((112, y), label, font=font(22, mono=True), fill=MUTED)
        value_font = fit_font(draw, value, 410, 29, minimum_size=22, mono=True)
        draw.text((796, y), value, font=value_font, fill=TEAL, anchor="ra")
        draw.line((112, y + 46, 796, y + 46), fill=(39, 68, 71), width=1)
        y += 82
    rounded_panel(draw, (112, 865, 796, 930), fill=(43, 32, 16), outline=AMBER, radius=15)
    draw.text((454, 897), "MODEL FORWARD ONLY · NOT END-TO-END LATENCY", font=font(20, mono=True), fill=AMBER, anchor="mm")
    contain_image(image, pdf_page, (892, 238, WIDTH - 72, 958), background=(236, 233, 222))
    save_slide(image, output)


def make_audit_overlay(output: Path) -> None:
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 54), fill=(5, 13, 16, 246))
    draw.text((40, 27), "REAL COMMAND OUTPUT · CPU EVIDENCE AUDIT", font=font(20, mono=True), fill=TEAL, anchor="lm")
    draw.text((WIDTH - 40, 27), "NO LIVE GPU REQUIRED", font=font(20, mono=True), fill=AMBER, anchor="rm")
    image.save(output, "PNG", optimize=True)


def make_close_slide(og_image: Path, output: Path) -> None:
    background = cover_image(og_image, (WIDTH, HEIGHT)).filter(ImageFilter.GaussianBlur(2.0))
    background = ImageEnhance.Brightness(background).enhance(0.24)
    image = Image.alpha_composite(
        background.convert("RGBA"),
        Image.new("RGBA", (WIDTH, HEIGHT), (3, 11, 14, 95)),
    ).convert("RGB")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 12), fill=TEAL)
    draw.text((WIDTH // 2, 145), "LOOK TWICE", font=font(104), fill=INK, anchor="ma")
    draw.text((WIDTH // 2, 280), "A concrete next observation", font=font(48), fill=TEAL, anchor="ma")
    rounded_panel(draw, (310, 410, WIDTH - 310, 760), fill=(5, 17, 20), outline=TEAL)
    draw.text((WIDTH // 2, 465), "TRACK 3 · PHYSICAL AI", font=font(27, mono=True), fill=AMBER, anchor="ma")
    draw.text((WIDTH // 2, 548), "github.com/eason4kim-rocket/look-twice", font=font(38, mono=True), fill=INK, anchor="ma")
    draw.text(
        (WIDTH // 2, 624),
        "eason4kim-rocket.github.io",
        font=font(32, mono=True),
        fill=TEAL,
        anchor="ma",
    )
    draw.text((WIDTH // 2, 700), "SIMULATION ONLY · NOT SAFETY CERTIFICATION", font=font(24, mono=True), fill=MUTED, anchor="ma")
    draw.text((WIDTH // 2, 918), "Evidence strong enough for this action?", font=font(42), fill=INK, anchor="ma")
    draw.text(
        (WIDTH // 2, 1010),
        "AI-GENERATED NARRATION · OPENAI TEXT-TO-SPEECH",
        font=font(18, mono=True),
        fill=MUTED,
        anchor="ma",
    )
    save_slide(image, output)


def static_video(image: Path, duration: int, output: Path, *, crf: int, preset: str) -> None:
    frames = duration * FPS
    # Fixed pixels are intentional: evidence slides must not drift or breathe.
    vf = f"fps={FPS},setsar=1,format=yuv420p"
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-loop",
            "1",
            "-framerate",
            str(FPS),
            "-i",
            str(image),
            "-vf",
            vf,
            "-frames:v",
            str(frames),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-crf",
            str(crf),
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(FPS),
            str(output),
        ]
    )


def reel_video(
    reel: Path,
    overlay: Path,
    duration: int,
    output: Path,
    *,
    crf: int,
    preset: str,
) -> None:
    reel_duration = media_duration(reel)
    if reel_duration > duration:
        raise SystemExit("recorded replay is longer than its chapter")
    pad_each_side = (duration - reel_duration) / 2
    filter_graph = (
        "[0:v]scale=1840:1035:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:40:45:color=0x050d10,fps=30,"
        f"tpad=start_mode=clone:start_duration={pad_each_side:.6f}:"
        f"stop_mode=clone:stop_duration={pad_each_side:.6f},"
        f"trim=duration={duration},setpts=PTS-STARTPTS[base];"
        "[base][1:v]overlay=0:0:format=auto,format=yuv420p[v]"
    )
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(reel),
            "-loop",
            "1",
            "-i",
            str(overlay),
            "-filter_complex",
            filter_graph,
            "-map",
            "[v]",
            "-frames:v",
            str(duration * FPS),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-crf",
            str(crf),
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(FPS),
            str(output),
        ]
    )


def audit_video(
    audit_source: Path,
    overlay: Path,
    target: int,
    output: Path,
    *,
    crf: int,
    preset: str,
) -> None:
    duration = media_duration(audit_source)
    base = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=0x050d10,fps={FPS}"
    )
    if duration > target:
        base += f",setpts={target / duration:.9f}*PTS"
    else:
        base += f",tpad=stop_mode=clone:stop_duration={target - duration:.6f}"
    base += f",trim=duration={target},setpts=PTS-STARTPTS"
    filter_graph = f"[0:v]{base}[base];[base][1:v]overlay=0:0:format=auto,format=yuv420p[v]"
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(audit_source),
            "-loop",
            "1",
            "-i",
            str(overlay),
            "-filter_complex",
            filter_graph,
            "-map",
            "[v]",
            "-frames:v",
            str(target * FPS),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-crf",
            str(crf),
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(FPS),
            str(output),
        ]
    )


def narration_audio(
    chapter: Chapter,
    source: Path,
    output: Path,
) -> dict[str, Any]:
    raw_duration = media_duration(source)
    intro_silence = 0.55
    if raw_duration + intro_silence > chapter.duration_seconds:
        raise SystemExit(
            f"narration for {chapter.slug} is {raw_duration:.2f}s and does not fit "
            f"its {chapter.duration_seconds}s chapter"
        )
    filters = (
        f"adelay={int(intro_silence * 1000)},"
        f"apad=pad_dur={chapter.duration_seconds + 1},"
        f"atrim=duration={chapter.duration_seconds},"
        "loudnorm=I=-16:TP=-1.5:LRA=7"
    )
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-af",
            filters,
            "-ar",
            "48000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(output),
        ]
    )
    return {
        "provider": "OpenAI",
        "model": NARRATION_MODEL,
        "voice": NARRATION_VOICE,
        "generated_via": "OpenAI.fm interactive text-to-speech demo",
        "ai_generated": True,
        "source_path": repository_path(source),
        "source_sha256": sha256(source),
        "delivery_instructions": NARRATION_INSTRUCTIONS,
        "raw_duration_seconds": round(raw_duration, 3),
        "intro_silence_seconds": intro_silence,
    }


def concat_file(paths: Sequence[Path], output: Path) -> None:
    lines: list[str] = []
    for path in paths:
        escaped = str(path.resolve()).replace("'", r"'\''")
        lines.append(f"file '{escaped}'")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_chapters() -> None:
    if not CHAPTERS or CHAPTERS[0].start_seconds != 0:
        raise SystemExit("chapter timeline must begin at zero")
    cursor = 0
    for chapter in CHAPTERS:
        if chapter.start_seconds != cursor:
            raise SystemExit(f"chapter timeline gap before {chapter.slug}")
        cursor = chapter.end_seconds
    if cursor != TOTAL_DURATION_SECONDS:
        raise SystemExit(f"chapter timeline totals {cursor}, expected {TOTAL_DURATION_SECONDS}")


def validate_inputs(
    args: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    narration_paths = tuple(args.narration_dir / f"{chapter.slug}.mp3" for chapter in CHAPTERS)
    paths = (
        args.reel,
        args.reel_manifest,
        args.replay_bundle,
        args.report,
        args.locked_report,
        args.benchmark,
        args.media_dir / "frame-1-rgb.webp",
        args.media_dir / "frame-1-depth.webp",
        args.media_dir / "frame-1-mask.webp",
        args.poster,
        args.og_image,
        args.tape,
        args.narration_manifest,
        *narration_paths,
    )
    for path in paths:
        if not path.is_file():
            raise SystemExit(f"required input is missing: {path}")
    ensure_v8_only(paths)

    reel_manifest = read_json(args.reel_manifest)
    if sha256(args.reel) != reel_manifest["video"]["sha256"]:
        raise SystemExit("30-second reel SHA256 does not match its manifest")
    if abs(media_duration(args.reel) - 30.0) > 0.05:
        raise SystemExit("V8 evidence reel is not 30 seconds")

    replay = read_json(args.replay_bundle)
    episode_meta = replay.get("episode_meta") or {}
    if int(episode_meta.get("seed", -1)) != 105400:
        raise SystemExit("active confirmatory replay is not seed 105400")
    if episode_meta.get("source_partition") != "confirmatory-non-locked":
        raise SystemExit("active replay is not marked as confirmatory and non-locked")
    if bool(episode_meta.get("frozen_candidate_artifact")) is not True:
        raise SystemExit("active replay is not marked as a frozen candidate artifact")

    locked = read_json(args.locked_report)
    if locked.get("tag") != "V8_LOCKED_TEST_ONCE":
        raise SystemExit("unexpected locked report tag")
    if locked.get("offline", {}).get("passed") is not True:
        raise SystemExit("locked offline report did not pass")
    if locked.get("live_fullchain", {}).get("passed") is not True:
        raise SystemExit("locked live full-chain report did not pass")
    gates = locked["live_fullchain"]["gates"]
    expected = {
        "n_active": 12,
        "n_passive": 12,
        "active_full_chain_direct": 11,
        "passive_detour": 12,
        "unsafe_total": 0,
        "fallback_total": 0,
    }
    for key, value in expected.items():
        if int(gates.get(key, -1)) != value:
            raise SystemExit(f"locked metric changed unexpectedly: {key}")

    benchmark = read_json(args.benchmark)
    if benchmark.get("status") != "passed":
        raise SystemExit("Radeon model-forward benchmark did not pass")
    scope = benchmark.get("claim_scope") or {}
    if scope.get("workload") != "synthetic preloaded-tensor model-forward benchmark":
        raise SystemExit("unexpected Radeon benchmark scope")
    if scope.get("locked_test_opened") is not False:
        raise SystemExit("benchmark boundary does not preserve the locked split")

    narration = read_json(args.narration_manifest)
    if narration.get("model") != NARRATION_MODEL:
        raise SystemExit("unexpected narration model")
    if narration.get("voice") != NARRATION_VOICE:
        raise SystemExit("unexpected narration voice")
    if narration.get("delivery_instructions") != NARRATION_INSTRUCTIONS:
        raise SystemExit("narration delivery instructions changed unexpectedly")
    if narration.get("ai_generated_disclosure_required") is not True:
        raise SystemExit("narration manifest does not require AI disclosure")
    narration_chapters = narration.get("chapters") or {}
    if set(narration_chapters) != {chapter.slug for chapter in CHAPTERS}:
        raise SystemExit("narration chapter set does not match the video timeline")
    for chapter in CHAPTERS:
        entry = narration_chapters[chapter.slug]
        source = args.narration_dir / f"{chapter.slug}.mp3"
        if entry.get("file") != source.name:
            raise SystemExit(f"unexpected narration filename for {chapter.slug}")
        if entry.get("sha256") != sha256(source):
            raise SystemExit(f"narration SHA256 mismatch for {chapter.slug}")
        if int(entry.get("bytes", -1)) != source.stat().st_size:
            raise SystemExit(f"narration byte count mismatch for {chapter.slug}")
        if entry.get("spoken_text") != chapter.spoken_text:
            raise SystemExit(f"narration text mismatch for {chapter.slug}")
        if abs(float(entry.get("duration_seconds", -1)) - media_duration(source)) > 0.01:
            raise SystemExit(f"narration duration mismatch for {chapter.slug}")
    return locked, benchmark, replay, narration


def render_audit_tape(tape: Path, output: Path) -> None:
    run(["vhs", str(tape), "--output", str(output)], cwd=ROOT)
    if not output.is_file():
        raise SystemExit("VHS audit recording was not created")


def build(args: argparse.Namespace) -> tuple[Path, Path]:
    validate_chapters()
    require_programs(("ffmpeg", "ffprobe", "pdftoppm", "vhs", "go", "shasum"))
    locked, benchmark, replay, narration = validate_inputs(args)

    output = args.output.resolve()
    manifest_path = output.with_suffix(".manifest.json")
    if (output.exists() or manifest_path.exists()) and not args.force:
        raise SystemExit(f"output exists; pass --force to replace it: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    if args.work_dir:
        args.work_dir.mkdir(parents=True, exist_ok=True)
        work_context: Any = _PersistentDirectory(args.work_dir)
    else:
        work_context = tempfile.TemporaryDirectory(prefix="look-twice-v8-demo-")

    with work_context as raw_work:
        work = Path(raw_work)
        slides = work / "slides"
        videos = work / "videos"
        audio = work / "audio"
        pdf_pages = work / "pdf"
        for directory in (slides, videos, audio, pdf_pages):
            directory.mkdir(parents=True, exist_ok=True)

        report_page_3 = render_pdf_page(args.report, 3, pdf_pages / "page-3.png")
        report_page_6 = render_pdf_page(args.report, 6, pdf_pages / "page-6.png")
        report_page_7 = render_pdf_page(args.report, 7, pdf_pages / "page-7.png")

        make_hook_slide(args.poster, slides / "hook.png")
        make_problem_slide(args.media_dir, slides / "problem.png")
        make_architecture_slide(report_page_3, slides / "architecture.png")
        make_reel_overlay(slides / "active-overlay.png")
        locked_utility = make_passive_slide(locked, args.media_dir, slides / "passive.png")
        make_results_slide(
            locked,
            sha256(args.locked_report),
            report_page_7,
            slides / "results.png",
        )
        make_amd_slide(benchmark, report_page_6, slides / "amd.png")
        make_audit_overlay(slides / "audit-overlay.png")
        make_close_slide(args.og_image, slides / "close.png")

        audit_raw = work / "v8-audit-raw.mp4"
        if args.audit_video:
            shutil.copy2(args.audit_video, audit_raw)
        else:
            render_audit_tape(args.tape, audit_raw)

        chapter_videos: list[Path] = []
        chapter_audio: list[Path] = []
        narration_meta: dict[str, dict[str, Any]] = {}
        for chapter in CHAPTERS:
            video_path = videos / f"{chapter.start_seconds:03d}-{chapter.slug}.mp4"
            audio_path = audio / f"{chapter.start_seconds:03d}-{chapter.slug}.wav"
            if chapter.slug == "active":
                reel_video(
                    args.reel,
                    slides / "active-overlay.png",
                    chapter.duration_seconds,
                    video_path,
                    crf=args.crf,
                    preset=args.preset,
                )
            elif chapter.slug == "reproduction":
                audit_video(
                    audit_raw,
                    slides / "audit-overlay.png",
                    chapter.duration_seconds,
                    video_path,
                    crf=args.crf,
                    preset=args.preset,
                )
            else:
                static_video(
                    slides / f"{chapter.slug}.png",
                    chapter.duration_seconds,
                    video_path,
                    crf=args.crf,
                    preset=args.preset,
                )
            narration_meta[chapter.slug] = narration_audio(
                chapter,
                args.narration_dir / f"{chapter.slug}.mp3",
                audio_path,
            )
            chapter_videos.append(video_path)
            chapter_audio.append(audio_path)

        video_list = work / "video-concat.txt"
        audio_list = work / "audio-concat.txt"
        concat_file(chapter_videos, video_list)
        concat_file(chapter_audio, audio_list)
        visual_track = work / "visual-track.mp4"
        narration_track = work / "narration-track.wav"
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(video_list),
                "-c",
                "copy",
                str(visual_track),
            ]
        )
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(audio_list),
                "-c:a",
                "pcm_s16le",
                str(narration_track),
            ]
        )

        candidate = work / output.name
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(visual_track),
                "-i",
                str(narration_track),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-t",
                str(TOTAL_DURATION_SECONDS),
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "160k",
                "-ar",
                "48000",
                "-ac",
                "1",
                "-movflags",
                "+faststart",
                str(candidate),
            ]
        )

        probe = probe_media(candidate)
        streams = probe.get("streams") or []
        video_streams = [item for item in streams if item.get("codec_type") == "video"]
        audio_streams = [item for item in streams if item.get("codec_type") == "audio"]
        if len(video_streams) != 1 or len(audio_streams) != 1:
            raise SystemExit("final video must contain exactly one video and one audio stream")
        video_stream = video_streams[0]
        audio_stream = audio_streams[0]
        duration = float(probe["format"]["duration"])
        if abs(duration - TOTAL_DURATION_SECONDS) > 0.08:
            raise SystemExit(f"unexpected final duration: {duration}")
        expected_video = {
            "codec_name": "h264",
            "width": WIDTH,
            "height": HEIGHT,
            "pix_fmt": "yuv420p",
            "r_frame_rate": "30/1",
        }
        for key, value in expected_video.items():
            if video_stream.get(key) != value:
                raise SystemExit(f"unexpected video stream {key}: {video_stream.get(key)!r}")
        if audio_stream.get("codec_name") != "aac":
            raise SystemExit("final audio is not AAC")
        if int(audio_stream.get("sample_rate", 0)) != 48000:
            raise SystemExit("final audio is not 48 kHz")
        max_bytes = int(args.max_size_mib * 1024 * 1024)
        if candidate.stat().st_size > max_bytes:
            raise SystemExit(
                f"video is {candidate.stat().st_size / 1024 / 1024:.2f} MiB; "
                f"limit is {args.max_size_mib:.2f} MiB (increase CRF and rerun)"
            )

        if output.exists():
            output.unlink()
        shutil.move(str(candidate), output)

        manifest = {
            "schema_version": "look-twice.v8-demo-video/v1",
            "generated_at_utc": dt.datetime.now(dt.timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "candidate_id": "v8-frozen",
            "track": "Track 3 - Physical AI",
            "language": "English",
            "video": {
                "filename": output.name,
                "sha256": sha256(output),
                "bytes": output.stat().st_size,
                "duration_seconds": duration,
                "width": WIDTH,
                "height": HEIGHT,
                "fps": FPS,
                "codec": "h264",
                "pixel_format": "yuv420p",
                "audio_codec": "aac",
                "audio_sample_rate_hz": 48000,
                "audio_channels": 1,
                "faststart": True,
            },
            "encoding": {
                "chapter_crf": args.crf,
                "chapter_preset": args.preset,
                "aac_bitrate": "160k",
                "target_loudness_lufs": -16,
                "maximum_size_mib": args.max_size_mib,
            },
            "narration": {
                "provider": "OpenAI",
                "model": NARRATION_MODEL,
                "voice": NARRATION_VOICE,
                "ai_generated": True,
                "delivery_instructions": NARRATION_INSTRUCTIONS,
                "disclosure_burned_in": True,
                "disclosure_text": "AI-generated narration · OpenAI text-to-speech",
            },
            "chapters": [
                {
                    "slug": chapter.slug,
                    "start_seconds": chapter.start_seconds,
                    "end_seconds": chapter.end_seconds,
                    "duration_seconds": chapter.duration_seconds,
                    "title": chapter.title,
                    "spoken_text": chapter.spoken_text,
                    "boundary": chapter.boundary,
                    "narration": narration_meta[chapter.slug],
                }
                for chapter in CHAPTERS
            ],
            "evidence_boundaries": {
                "locked_aggregate_source": "release/v8-frozen/results/LOCKED_TEST_REPORT.json",
                "locked_report_sha256": sha256(args.locked_report),
                "confirmatory_replay_source": "showcase/public/data/replays/v8-active-repair-direct.json",
                "confirmatory_replay_seed": int(replay["episode_meta"]["seed"]),
                "confirmatory_replay_formal_result_eligible": False,
                "confirmatory_replay_label_burned_in": True,
                "simulation_only": True,
                "real_robot_claim": False,
                "safety_certification_claim": False,
                "historical_v2_v3_media_used": False,
            },
            "locked_task_utility": locked_utility,
            "inputs": {
                "recorded_v8_reel": {
                    "path": repository_path(args.reel),
                    "sha256": sha256(args.reel),
                },
                "technical_report_pdf": {
                    "path": repository_path(args.report),
                    "sha256": sha256(args.report),
                    "pages_used": [3, 6, 7],
                },
                "locked_report": {
                    "path": repository_path(args.locked_report),
                    "sha256": sha256(args.locked_report),
                },
                "rocm_benchmark": {
                    "path": repository_path(args.benchmark),
                    "sha256": sha256(args.benchmark),
                    "scope": benchmark["claim_scope"],
                },
                "vhs_audit_tape": {
                    "path": repository_path(args.tape),
                    "sha256": sha256(args.tape),
                    "rendered_audit_sha256": sha256(audit_raw),
                },
                "narration_manifest": {
                    "path": repository_path(args.narration_manifest),
                    "sha256": sha256(args.narration_manifest),
                    "model": narration["model"],
                    "voice": narration["voice"],
                    "ai_generated_disclosure_required": narration[
                        "ai_generated_disclosure_required"
                    ],
                },
                "builder": {
                    "path": repository_path(Path(__file__).resolve()),
                    "sha256": sha256(Path(__file__).resolve()),
                },
            },
        }
        temporary_manifest = work / manifest_path.name
        temporary_manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        if manifest_path.exists():
            manifest_path.unlink()
        shutil.move(str(temporary_manifest), manifest_path)

    print(json.dumps({"video": str(output), "manifest": str(manifest_path)}, indent=2))
    return output, manifest_path


class _PersistentDirectory:
    """Context-manager shim used by --work-dir for inspectable intermediates."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def __enter__(self) -> str:
        return str(self.path)

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None


DEFAULTS = {
    "reel": ROOT / "showcase/public/media/look-twice-replay-30s.mp4",
    "reel_manifest": ROOT / "showcase/public/media/look-twice-replay-30s.manifest.json",
    "replay_bundle": ROOT / "showcase/public/data/replays/v8-active-repair-direct.json",
    "poster": ROOT / "showcase/public/media/look-twice-replay-30s.poster.webp",
    "report": ROOT / "output/pdf/Look-Twice-V8-Technical-Report.pdf",
    "locked_report": ROOT / "release/v8-frozen/results/LOCKED_TEST_REPORT.json",
    "benchmark": ROOT / "release/v8-frozen/results/V8_FROZEN_INFERENCE_BENCHMARK.json",
    "media_dir": ROOT / "showcase/public/data/media/v8-active-repair-direct",
    "og_image": ROOT / "showcase/public/og.png",
    "tape": ROOT / "scripts/video/v8-audit.tape",
    "narration_dir": ROOT / "assets/v8-demo-narration",
    "narration_manifest": ROOT / "assets/v8-demo-narration/manifest.json",
    "output": OFFICIAL_STAGING / "Look-Twice-V8-Demo.mp4",
}


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            The command renders real audit output and can take several minutes.
            It never opens the locked test or uses historical V2/V3 footage.

            Example:
              python3 scripts/build_v8_demo_video.py
            """
        ),
    )
    value.add_argument("--reel", type=Path, default=DEFAULTS["reel"])
    value.add_argument("--reel-manifest", type=Path, default=DEFAULTS["reel_manifest"])
    value.add_argument("--replay-bundle", type=Path, default=DEFAULTS["replay_bundle"])
    value.add_argument("--poster", type=Path, default=DEFAULTS["poster"])
    value.add_argument("--report", type=Path, default=DEFAULTS["report"])
    value.add_argument("--locked-report", type=Path, default=DEFAULTS["locked_report"])
    value.add_argument("--benchmark", type=Path, default=DEFAULTS["benchmark"])
    value.add_argument("--media-dir", type=Path, default=DEFAULTS["media_dir"])
    value.add_argument("--og-image", type=Path, default=DEFAULTS["og_image"])
    value.add_argument("--tape", type=Path, default=DEFAULTS["tape"])
    value.add_argument("--narration-dir", type=Path, default=DEFAULTS["narration_dir"])
    value.add_argument(
        "--narration-manifest",
        type=Path,
        default=DEFAULTS["narration_manifest"],
    )
    value.add_argument(
        "--audit-video",
        type=Path,
        help="Use a previously rendered real VHS audit clip instead of rerunning the tape.",
    )
    value.add_argument("--output", type=Path, default=DEFAULTS["output"])
    value.add_argument("--crf", type=int, default=21)
    value.add_argument("--preset", default="medium")
    value.add_argument("--max-size-mib", type=float, default=50.0)
    value.add_argument(
        "--work-dir",
        type=Path,
        help="Keep intermediate slides, audio and video under this directory.",
    )
    value.add_argument("--force", action="store_true", help="Replace an existing video and manifest.")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    for name in (
        "reel",
        "reel_manifest",
        "replay_bundle",
        "poster",
        "report",
        "locked_report",
        "benchmark",
        "media_dir",
        "og_image",
        "tape",
        "narration_dir",
        "narration_manifest",
        "output",
    ):
        setattr(args, name, getattr(args, name).expanduser().resolve())
    if args.audit_video:
        args.audit_video = args.audit_video.expanduser().resolve()
        if not args.audit_video.is_file():
            raise SystemExit(f"audit video is missing: {args.audit_video}")
        ensure_v8_only((args.audit_video,))
    if args.work_dir:
        args.work_dir = args.work_dir.expanduser().resolve()
    if not 0 <= args.crf <= 51:
        raise SystemExit("--crf must be between 0 and 51")
    if args.max_size_mib <= 0:
        raise SystemExit("--max-size-mib must be positive")
    build(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
