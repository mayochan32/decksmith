"""Read optional project settings without network access or language inference."""
import argparse
import json
import math
from pathlib import Path
from compile_spec import SpecError, keys, load_mapping


def nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise SpecError(label + " must be a non-empty string")
    return value.strip()


def resolve_config(path=None, base=None):
    base = Path(base or Path.cwd()).resolve()
    if path is not None and not Path(path).is_file():
        raise SpecError("Missing config: " + str(path))
    path = Path(path).resolve() if path else base / "decksmith.yaml"
    data = load_mapping(path) if path.is_file() else {}
    if path.exists() and not path.is_file():
        raise SpecError("Config must be a file: " + str(path))
    base = path.parent
    keys(data, "slide privacy output input images text language", "config")
    fields = {"slide":"width_px height_px aspect_ratio", "privacy":"mode",
              "output":"directory filename pdf renderer", "input":"style brief", "images":"mode amount type color plan", "text":"amount"}
    for name, allowed in fields.items():
        keys(data.get(name, {}), allowed, name)
    slide = data.get("slide", {})
    w, h = slide.get("width_px"), slide.get("height_px")
    for name in ("width_px", "height_px"):
        if name in slide and (type(slide[name]) is not int or slide[name] <= 0):
            raise SpecError("slide." + name + " must be a positive integer")
    ratio = None
    if "aspect_ratio" in slide:
        try:
            a, b = nonempty(slide["aspect_ratio"], "aspect_ratio").split(":")
            a, b = float(a), float(b)
            if not all(math.isfinite(v) and v > 0 for v in (a,b)):
                raise ValueError()
            ratio = a / b
            if not math.isfinite(ratio) or ratio <= 0:
                raise ValueError()
        except (ValueError, OverflowError):
            raise SpecError("aspect_ratio must be a positive width:height ratio")
    if w and h and ratio is not None and abs(w - h * ratio) > max(1, ratio):
        raise SpecError("Conflicting slide dimensions and aspect_ratio; clarify before rendering")
    ratio = ratio or (w / h if w and h else 16 / 9)
    if w is None and h is None:
        w, h = (1920, max(1, round(1920 / ratio))) if ratio >= 1 else (max(1, round(1920 * ratio)), 1920)
    elif w is None:
        w = max(1, round(h * ratio))
    elif h is None:
        h = max(1, round(w / ratio))
    privacy = data.get("privacy", {}).get("mode", "normal")
    text_amount = data.get("text", {}).get("amount", "normal")
    if text_amount not in ("minimal", "less", "normal", "more", "dense"):
        raise SpecError("text.amount must be one of: minimal, less, normal, more, dense")
    image_options = {
        "mode": ("auto", "provided_only"),
        "amount": ("normal", "more", "less", "none"),
        "type": ("auto", "illust", "photo", "icon", "anime"),
        "color": ("color", "gray", "monotone"),
        "plan": ("show", "confirm", "skip"),
    }
    images = {}
    for name, allowed in image_options.items():
        value = data.get("images", {}).get(name, allowed[0])
        if value not in allowed:
            raise SpecError("images." + name + " must be one of: " + ", ".join(allowed))
        images[name] = value
    if privacy not in ("normal", "restricted"):
        raise SpecError("privacy.mode must be normal or restricted")
    output = data.get("output", {})
    renderer = output.get("renderer", "libreoffice")
    if renderer not in ("libreoffice", "powerpoint", "none"):
        raise SpecError("output.renderer must be libreoffice, powerpoint or none")
    pdf = output.get("pdf", False)
    if type(pdf) is not bool:
        raise SpecError("output.pdf must be true or false")
    if renderer == "none" and pdf:
        raise SpecError("output.pdf cannot be true with output.renderer=none")
    filename = output.get("filename")
    if "filename" in output:
        filename = nonempty(filename, "output.filename")
        if "/" in filename or "\\" in filename or Path(filename).suffix.lower() != ".pptx":
            raise SpecError("output.filename must be a filename ending in .pptx")
    def local_path(value, label):
        value = nonempty(value, label)
        if "://" in value:
            raise SpecError(label + " must be a local path, not a URL")
        p = Path(value).expanduser()
        return str((base / p).resolve())
    inputs = {name:local_path(value, "input." + name) for name,value in data.get("input", {}).items()}
    for name, value in inputs.items():
        if not Path(value).is_file():
            raise SpecError("Missing input." + name + ": " + value)
    language = nonempty(data["language"], "language") if "language" in data else None
    return {"config_path":str(path) if path.is_file() else None,
            "canvas":{"width":w,"height":h}, "size_explicit":bool(slide),
            "privacy":{"mode":privacy}, "images":images, "text":{"amount":text_amount}, "language":language,
            "input":inputs, "output":{"directory":local_path(output.get("directory", "output"), "output.directory"),
                                        "filename":filename, "pdf":pdf, "renderer":renderer}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    try:
        if args.config and not args.config.is_file():
            raise SpecError("Missing config: " + str(args.config))
        print(json.dumps(resolve_config(args.config), ensure_ascii=False, indent=2))
    except (ValueError, OSError) as error:
        parser.exit(2, "DeckSmith: " + str(error) + "\n")
