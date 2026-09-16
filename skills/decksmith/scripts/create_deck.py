#!/usr/bin/env python3
"""DeckSmithプロジェクトをコンパイルし、PPTXと確認用プレビューを生成します。"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from compile_spec import SpecError, compile_spec


PRESENTATIONS_MARKER = Path("container_tools/mark_artifact_operation_started.mjs")
RUNTIME_ENV_ALIASES = {
    "RUNTIME_NODE": "CODEX_PRIMARY_RUNTIME_NODE",
    "RUNTIME_NODE_MODULES": "CODEX_PRIMARY_RUNTIME_NODE_MODULES",
    "RUNTIME_PYTHON": "CODEX_PRIMARY_RUNTIME_PYTHON",
}


def absolute_env_path(name: str) -> Path:
    alias = RUNTIME_ENV_ALIASES.get(name)
    value = os.environ.get(name) or (os.environ.get(alias) if alias else None)
    if not value:
        accepted = f"{name} または {alias}" if alias else name
        raise SpecError(f"必要なランタイム環境変数がありません: {accepted}")
    path = Path(value)
    if not path.is_absolute():
        raise SpecError(f"{name}は絶対パスである必要があります")
    return path


def is_presentations_skill_dir(path: Path) -> bool:
    """Return whether *path* is a usable built-in Presentations skill root."""
    return (path / PRESENTATIONS_MARKER).is_file()


def resolve_presentations_skill_dir(explicit: Path | None = None) -> Path:
    """Resolve the host-provided Presentations skill without user configuration."""
    candidates: list[tuple[str, Path]] = []

    if explicit is not None:
        candidates.append(("--presentations-skill-dir", explicit))

    for name in ("DECKSMITH_PRESENTATIONS_SKILL_DIR", "PRESENTATIONS_SKILL_DIR"):
        value = os.environ.get(name)
        if value:
            candidates.append((name, Path(value)))

    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        candidates.append(("CODEX_HOME", Path(codex_home) / "skills" / "builtins" / "presentations"))

    try:
        home = Path.home()
    except RuntimeError:
        home = None
    if home is not None:
        candidates.append(
            ("Codexの標準配置", home / ".codex" / "skills" / "builtins" / "presentations")
        )

    checked: list[str] = []
    for source, candidate in candidates:
        resolved = candidate.expanduser().resolve()
        checked.append(f"{source}: {resolved}")
        if is_presentations_skill_dir(resolved):
            return resolved

    details = "\n  ".join(checked) if checked else "候補なし"
    raise SpecError(
        "組み込みPresentationsを検出できません。DeckSmithはPresentationsが利用可能な"
        "ChatGPT／Codex環境で実行してください。利用者がディレクトリを作成する必要はありません。"
        "特殊な開発環境ではDECKSMITH_PRESENTATIONS_SKILL_DIRを設定できます。"
        f"\n確認した場所:\n  {details}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", required=True, type=Path)
    parser.add_argument("--structure", required=True, type=Path)
    parser.add_argument("--creative-style", required=True, type=Path)
    parser.add_argument("--executable-style", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--presentations-skill-dir",
        type=Path,
        help="開発者向け。通常は指定不要で、組み込みPresentationsを自動検出します。",
    )
    parser.add_argument("--allow-missing-images", action="store_true")
    parser.add_argument(
        "--skip-operation-marker",
        action="store_true",
        help="同じ成果物操作内で修正版を生成するときだけ指定します。",
    )
    args = parser.parse_args()

    try:
        runtime_node = absolute_env_path("RUNTIME_NODE")
        runtime_modules = absolute_env_path("RUNTIME_NODE_MODULES")
        runtime_python = absolute_env_path("RUNTIME_PYTHON")
    except SpecError as error:
        parser.error(str(error))

    try:
        presentations_skill_dir = resolve_presentations_skill_dir(args.presentations_skill_dir)
    except SpecError as error:
        parser.error(str(error))
    marker = presentations_skill_dir / PRESENTATIONS_MARKER

    output = args.output.resolve()
    if output.exists():
        parser.error(f"Refusing to overwrite existing output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    if output.parent.parent == output.parent:
        parser.error("Output must be placed inside a dedicated output directory")
    workspace = output.parent.parent
    build_dir = Path(
        tempfile.mkdtemp(prefix=f".{output.stem}.decksmith-build-", dir=workspace)
    )

    try:
        spec = compile_spec(
            args.topic.resolve(),
            args.structure.resolve(),
            args.creative_style.resolve(),
            args.executable_style.resolve(),
            args.allow_missing_images,
        )
        spec_path = build_dir / "deck-spec.json"
        import json

        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        builder_source = Path(__file__).with_name("build_deck.mjs")
        builder_copy = build_dir / "build_deck.mjs"
        shutil.copy2(builder_source, builder_copy)
        (build_dir / "node_modules").symlink_to(runtime_modules, target_is_directory=True)

        if not args.skip_operation_marker:
            subprocess.run(
                [
                    str(runtime_node),
                    str(marker),
                    "--operation-kind",
                    "create",
                    "--expected-output-count",
                    "1",
                    "--output-format",
                    "pptx",
                ],
                check=True,
            )

        environment = os.environ.copy()
        environment.update(
            {
                "SKILL_DIR": str(presentations_skill_dir),
                "TMP_DIR": str(build_dir),
                "RUNTIME_NODE": str(runtime_node),
                "RUNTIME_NODE_MODULES": str(runtime_modules),
                "RUNTIME_PYTHON": str(runtime_python),
            }
        )
        subprocess.run(
            [
                str(runtime_node),
                str(builder_copy),
                "--spec",
                str(spec_path),
                "--output",
                str(output),
                "--workspace",
                str(workspace),
            ],
            check=True,
            env=environment,
        )
    except (SpecError, subprocess.CalledProcessError) as error:
        print(f"DeckSmith failed: {error}", file=sys.stderr)
        return 2

    print(output)
    print(output.with_suffix(".preview"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
