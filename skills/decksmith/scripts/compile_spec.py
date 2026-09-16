#!/usr/bin/env python3
"""Validate DeckSmith YAML inputs and emit one canonical JSON spec."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml


SUPPORTED_LAYOUTS = {
    "cover",
    "statement",
    "bullets",
    "split",
    "image-left",
    "image-right",
    "full-bleed",
    "closing",
}
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


class SpecError(ValueError):
    pass


def load_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SpecError(f"Input file does not exist: {path}")
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise SpecError(f"Expected a YAML mapping in {path}")
    return value


def require_text(mapping: dict[str, Any], key: str, context: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SpecError(f"{context}.{key} must be a non-empty string")
    return value.strip()


def normalize_color(value: Any, fallback: str, key: str) -> str:
    candidate = value if isinstance(value, str) else fallback
    if not HEX_COLOR.match(candidate):
        raise SpecError(f"style.colors.{key} must use #RRGGBB")
    return candidate.upper()


def resolve_image(slide: dict[str, Any], base_dir: Path, allow_missing: bool) -> None:
    image = slide.get("image")
    if image is None:
        return
    if not isinstance(image, dict):
        raise SpecError(f"slide {slide['id']}: image must be a mapping")
    raw_path = image.get("path")
    if raw_path:
        image_path = Path(str(raw_path)).expanduser()
        if not image_path.is_absolute():
            image_path = (base_dir / image_path).resolve()
        image["path"] = str(image_path)
        if not image_path.is_file() and not allow_missing:
            raise SpecError(f"slide {slide['id']}: image does not exist: {image_path}")
    elif image.get("prompt") and not allow_missing:
        raise SpecError(
            f"slide {slide['id']}: image prompt exists but no generated image path was supplied"
        )


def compile_spec(
    topic_path: Path,
    structure_path: Path,
    creative_path: Path,
    executable_path: Path,
    allow_missing_images: bool = False,
) -> dict[str, Any]:
    topic = load_mapping(topic_path)
    structure = load_mapping(structure_path)
    creative = load_mapping(creative_path)
    executable = load_mapping(executable_path)

    project = {
        "title": require_text(topic, "title", "topic"),
        "audience": require_text(topic, "audience", "topic"),
        "objective": require_text(topic, "objective", "topic"),
        "language": str(topic.get("language") or "ja-JP"),
        "output_filename": str(topic.get("output_filename") or "deck.pptx"),
        "facts": topic.get("facts") or [],
        "constraints": topic.get("constraints") or [],
    }
    if not project["output_filename"].lower().endswith(".pptx"):
        raise SpecError("topic.output_filename must end with .pptx")

    raw_slides = structure.get("slides")
    if not isinstance(raw_slides, list) or not raw_slides:
        raise SpecError("structure.slides must be a non-empty list")

    slides: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, raw_slide in enumerate(raw_slides, start=1):
        if not isinstance(raw_slide, dict):
            raise SpecError(f"structure.slides[{index}] must be a mapping")
        slide = dict(raw_slide)
        slide_id = require_text(slide, "id", f"structure.slides[{index}]")
        if slide_id in ids:
            raise SpecError(f"Duplicate slide id: {slide_id}")
        ids.add(slide_id)
        layout = require_text(slide, "layout", f"slide {slide_id}")
        if layout not in SUPPORTED_LAYOUTS:
            raise SpecError(f"slide {slide_id}: unsupported layout '{layout}'")
        require_text(slide, "title", f"slide {slide_id}")
        resolve_image(slide, structure_path.parent, allow_missing_images)
        slides.append(slide)

    canvas = executable.get("canvas") or {}
    colors = executable.get("colors") or {}
    typography = executable.get("typography") or {}
    spacing = executable.get("spacing") or {}
    image = executable.get("image") or {}
    decoration = executable.get("decoration") or {}

    normalized_style = {
        "name": str(executable.get("name") or creative.get("name") or "decksmith-style"),
        "canvas": {
            "width": int(canvas.get("width", 1280)),
            "height": int(canvas.get("height", 720)),
        },
        "colors": {
            "background": normalize_color(colors.get("background"), "#F7F4EE", "background"),
            "surface": normalize_color(colors.get("surface"), "#EAE5DA", "surface"),
            "text": normalize_color(colors.get("text"), "#17202A", "text"),
            "muted": normalize_color(colors.get("muted"), "#66717D", "muted"),
            "accent": normalize_color(colors.get("accent"), "#315CFF", "accent"),
            "on_accent": normalize_color(colors.get("on_accent"), "#FFFFFF", "on_accent"),
        },
        "typography": {
            "family": typography.get("family"),
            "title": int(typography.get("title", 58)),
            "heading": int(typography.get("heading", 38)),
            "body": int(typography.get("body", 24)),
            "small": int(typography.get("small", 16)),
            "line_spacing": float(typography.get("line_spacing", 1.08)),
        },
        "spacing": {
            "margin_x": int(spacing.get("margin_x", 76)),
            "margin_y": int(spacing.get("margin_y", 56)),
            "gutter": int(spacing.get("gutter", 36)),
            "title_gap": int(spacing.get("title_gap", 28)),
        },
        "image": {
            "corner_radius": int(image.get("corner_radius", 20)),
            "fit": str(image.get("fit") or "cover"),
            "generated_limit": int(image.get("generated_limit", 6)),
        },
        "decoration": {
            "page_numbers": bool(decoration.get("page_numbers", True)),
            "accent_bar": bool(decoration.get("accent_bar", True)),
        },
    }
    if normalized_style["canvas"] != {"width": 1280, "height": 720}:
        raise SpecError("MVP supports a 1280x720 (16:9) canvas only")
    if normalized_style["image"]["fit"] not in {"cover", "contain"}:
        raise SpecError("style.image.fit must be cover or contain")

    return {
        "schema_version": "0.1",
        "project": project,
        "style": {"creative": creative, "executable": normalized_style},
        "slides": slides,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", required=True, type=Path)
    parser.add_argument("--structure", required=True, type=Path)
    parser.add_argument("--creative-style", required=True, type=Path)
    parser.add_argument("--executable-style", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--allow-missing-images", action="store_true")
    args = parser.parse_args()

    try:
        spec = compile_spec(
            args.topic.resolve(),
            args.structure.resolve(),
            args.creative_style.resolve(),
            args.executable_style.resolve(),
            args.allow_missing_images,
        )
    except SpecError as error:
        parser.error(str(error))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.out.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
