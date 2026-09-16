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
HEX_IN_TEXT = re.compile(r"#[0-9A-Fa-f]{6}")


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


def normalized_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def mapping_value(mapping: dict[str, Any], *names: str) -> Any:
    wanted = {normalized_key(name) for name in names}
    for key, value in mapping.items():
        if normalized_key(key) in wanted:
            return value
    return None


def text_value(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        values = [text_value(item) for item in value]
        return " ".join(item for item in values if item)
    if isinstance(value, dict):
        values = [text_value(item) for item in value.values()]
        return " ".join(item for item in values if item)
    return ""


def collect_colors(value: Any, path: tuple[str, ...] = ()) -> list[tuple[str, str]]:
    colors: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            colors.extend(collect_colors(child, path + (normalized_key(key),)))
    elif isinstance(value, list):
        for child in value:
            colors.extend(collect_colors(child, path))
    elif isinstance(value, str):
        for match in HEX_IN_TEXT.findall(value):
            colors.append(("/".join(path), match.upper()))
    return colors


def find_color(
    colors: list[tuple[str, str]],
    terms: tuple[str, ...],
    fallback: str,
    *,
    prefer_last: bool = False,
) -> str:
    matches = [color for path, color in colors if any(term in path for term in terms)]
    if not matches:
        return fallback
    return matches[-1] if prefer_last else matches[0]


def layout_targets(type_name: str, design: str) -> list[str]:
    raw_words = f"{type_name} {design}".lower()
    words = f"{normalized_key(raw_words)} {raw_words}"
    targets: list[str] = []
    rules = (
        (("cover", "title", "opening", "magazine", "表紙", "タイトル"), ["cover"]),
        (("quote", "statement", "bignumber", "datacontrast", "statistics", "引用", "数値"), ["statement"]),
        (("split", "comparison", "conflict", "duality", "比較", "分割"), ["split"]),
        (("list", "menu", "contents", "terminal", "timeline", "process", "リスト", "目次", "工程"), ["bullets"]),
        (("image", "portrait", "profile", "product", "editorial", "画像", "人物"), ["image-left", "image-right"]),
        (("gallery", "moodboard", "fullbleed", "ギャラリー"), ["full-bleed"]),
        (("closing", "conclusion", "finalact", "ending", "まとめ", "結論"), ["closing"]),
    )
    for keywords, values in rules:
        if any(keyword in words for keyword in keywords):
            targets.extend(values)
    return list(dict.fromkeys(targets)) or ["bullets"]


def layout_variant(type_name: str, design: str) -> str:
    raw_words = f"{type_name} {design}".lower()
    words = f"{normalized_key(raw_words)} {raw_words}"
    if any(word in words for word in ("mega", "massive", "giant", "magazine", "titleblock")):
        return "mega-title"
    if any(word in words for word in ("terminal", "bootsequence", "systemlog")):
        return "terminal-list"
    if any(word in words for word in ("divider", "horizontalline", "separated")):
        return "divider-list"
    if any(word in words for word in ("duality", "split", "comparison", "conflict")):
        return "dual-split"
    if any(word in words for word in ("quote", "statement", "bignumber", "statistics")):
        return "impact-statement"
    if any(word in words for word in ("overlap", "layer", "cutout", "portrait", "editorial")):
        return "editorial-image"
    if any(word in words for word in ("gallery", "moodboard", "fullbleed")):
        return "full-bleed"
    return "standard"


def compile_article_style(style: dict[str, Any]) -> dict[str, Any]:
    overall = mapping_value(style, "Overall Design Settings", "Overall Design")
    if not isinstance(overall, dict):
        raise SpecError("style.yaml requires an 'Overall Design Settings' mapping")

    tone = text_value(mapping_value(overall, "Tone"))
    palette = mapping_value(overall, "Color Palette")
    typography_source = mapping_value(overall, "Typography")
    common_rules = mapping_value(overall, "Common Layout Rules", "Design Considerations")
    photography = mapping_value(overall, "Photography Style", "Imagery")
    key_visual = mapping_value(overall, "Key Visual", "Visual Motif")
    application_notes = mapping_value(
        style,
        "Points to Note When Applying the Design",
        "Points to note when applying the design",
        "Application Notes",
    )
    if not tone:
        raise SpecError("style.yaml requires Overall Design Settings.Tone")
    if not isinstance(palette, dict):
        raise SpecError("style.yaml requires Overall Design Settings.Color Palette")
    if not isinstance(typography_source, dict):
        raise SpecError("style.yaml requires Overall Design Settings.Typography")

    colors_found = collect_colors(palette)
    background = find_color(colors_found, ("base", "background"), "#F7F4EE", prefer_last=True)
    text = find_color(colors_found, ("maintext", "body"), "#17202A")
    if text == "#17202A":
        text = find_color(colors_found, ("textcolor", "text"), text, prefer_last=True)
    accent = find_color(
        colors_found,
        ("emphasis", "accent", "primarypurple", "primarycyan", "primary"),
        colors_found[0][1] if colors_found else "#315CFF",
    )
    if accent == background and len(colors_found) > 1:
        accent = colors_found[0][1]
    on_accent = "#FFFFFF" if any(color == "#FFFFFF" for _, color in colors_found) else background
    surface = find_color(colors_found, ("secondary", "surface"), background)

    typography_text = text_value(typography_source).lower()
    rules_text = text_value(common_rules).lower()
    image_text = " ".join((text_value(photography), text_value(key_visual))).lower()
    massive = any(word in typography_text for word in ("massive", "giant", "huge", "ultra-condensed", "extra condensed"))
    spacious = any(word in f"{rules_text} {tone.lower()}" for word in ("whitespace", "negative space", "余白", "breath"))
    font_family = "Nimbus Sans"
    if "serif" in typography_text and "sans-serif" not in typography_text and "sans serif" not in typography_text:
        font_family = "Nimbus Roman"

    catalog_source = mapping_value(style, "Layout Variations (Catalog)", "Layout Variations")
    if not isinstance(catalog_source, list) or not catalog_source:
        raise SpecError("style.yaml requires a non-empty 'Layout Variations (Catalog)' list")
    catalog = []
    for index, entry in enumerate(catalog_source, start=1):
        if not isinstance(entry, dict):
            raise SpecError(f"Layout Variations (Catalog)[{index}] must be a mapping")
        type_name = text_value(mapping_value(entry, "Type"))
        design = text_value(mapping_value(entry, "Design"))
        if not type_name or not design:
            raise SpecError(f"Layout Variations (Catalog)[{index}] requires Type and Design")
        explicit_targets = mapping_value(entry, "Applies To", "AppliesTo")
        if isinstance(explicit_targets, str):
            applies_to = [explicit_targets]
        elif isinstance(explicit_targets, list):
            applies_to = [str(value) for value in explicit_targets]
        else:
            applies_to = layout_targets(type_name, design)
        unknown = sorted(set(applies_to) - SUPPORTED_LAYOUTS)
        if unknown:
            raise SpecError(f"Layout Variations (Catalog)[{index}] has unsupported Applies To: {unknown}")
        catalog.append(
            {
                "type": type_name,
                "design": design,
                "applies_to": applies_to,
                "variant": layout_variant(type_name, design),
            }
        )

    return {
        "name": str(mapping_value(style, "Style", "Name") or "article-style"),
        "source_format": "article-style-yaml-v1",
        "tone": tone,
        "canvas": {"width": 1280, "height": 720},
        "colors": {
            "background": background,
            "surface": surface,
            "text": text,
            "muted": text,
            "accent": accent,
            "on_accent": on_accent,
        },
        "typography": {
            "family": font_family,
            "title": 78 if massive else 58,
            "heading": 44 if massive else 38,
            "body": 22 if massive else 24,
            "small": 16,
            "line_spacing": 1.04 if massive else 1.08,
            "description": text_value(typography_source),
            "uppercase_titles": "uppercase" in typography_text or "all caps" in typography_text,
            "massive": massive,
        },
        "spacing": {
            "margin_x": 88 if spacious else 68,
            "margin_y": 64 if spacious else 52,
            "gutter": 40 if spacious else 32,
            "title_gap": 30 if spacious else 24,
        },
        "image": {
            "corner_radius": 0 if any(word in image_text for word in ("cutout", "切り抜", "editorial")) else 18,
            "fit": "cover",
            "generated_limit": 6,
            "prompt_guidance": text_value(photography) or text_value(key_visual),
            "grayscale": any(word in image_text for word in ("grayscale", "black and white", "monochrome", "白黒")),
        },
        "decoration": {
            "page_numbers": True,
            "accent_bar": True,
            "frame_lines": any(word in rules_text for word in ("line", "frame", "border", "罫線", "枠")),
        },
        "layout_catalog": catalog,
        "common_layout_rules": text_value(common_rules),
        "key_visual": text_value(key_visual),
        "application_notes": text_value(application_notes),
    }


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
    executable_path: Path | None = None,
    allow_missing_images: bool = False,
) -> dict[str, Any]:
    topic = load_mapping(topic_path)
    structure = load_mapping(structure_path)
    creative = load_mapping(creative_path)
    executable = load_mapping(executable_path) if executable_path else compile_article_style(creative)

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
            "description": str(typography.get("description") or ""),
            "uppercase_titles": bool(typography.get("uppercase_titles", False)),
            "massive": bool(typography.get("massive", False)),
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
            "prompt_guidance": str(image.get("prompt_guidance") or ""),
            "grayscale": bool(image.get("grayscale", False)),
        },
        "decoration": {
            "page_numbers": bool(decoration.get("page_numbers", True)),
            "accent_bar": bool(decoration.get("accent_bar", True)),
            "frame_lines": bool(decoration.get("frame_lines", False)),
        },
        "source_format": str(executable.get("source_format") or "decksmith-executable-v1"),
        "tone": str(executable.get("tone") or creative.get("intent") or ""),
        "layout_catalog": executable.get("layout_catalog") or [],
        "common_layout_rules": str(executable.get("common_layout_rules") or ""),
        "key_visual": str(executable.get("key_visual") or ""),
        "application_notes": str(executable.get("application_notes") or ""),
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
    parser.add_argument("--style", type=Path)
    parser.add_argument("--creative-style", type=Path)
    parser.add_argument("--executable-style", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--allow-missing-images", action="store_true")
    args = parser.parse_args()

    if args.style:
        if args.creative_style or args.executable_style:
            parser.error("--style cannot be combined with legacy style arguments")
        creative_style = args.style.resolve()
        executable_style = None
    else:
        if not args.creative_style or not args.executable_style:
            parser.error("provide --style or both legacy style arguments")
        creative_style = args.creative_style.resolve()
        executable_style = args.executable_style.resolve()

    try:
        spec = compile_spec(
            args.topic.resolve(),
            args.structure.resolve(),
            creative_style,
            executable_style,
            allow_missing_images=args.allow_missing_images,
        )
    except SpecError as error:
        parser.error(str(error))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.out.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
