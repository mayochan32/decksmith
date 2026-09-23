# Portable engine implementation — 2026-09-23

## Implemented

- Shared Skill interprets arbitrary user YAML; no bundled style presets or layout catalog.
- Renderer now uses pinned PptxGenJS 4.0.1, image-size 1.2.1, Python stdlib and vendored PyYAML.
- No OpenAI SDK, artifact-tool or private presentation runtime required by shared code.
- Codex, Claude Code and Gemini CLI manifests share one Skill.
- doctor.py reports missing runtime dependencies without installing anything.
- Independent OOXML validation plus LibreOffice/Poppler previews; visual review remains a separate gate.
- Image-generation handoff documented as provider-independent asset requests/results. Actual provider APIs are not implemented.
- package_plugin.py excludes development outputs, old implementation and installed dependencies.

## Validation

- 17 tests passed, including actual PPTX rendering: native editable text, mixed fonts, color, rotation, layer ordering and custom paths.
- Plugin and Skill metadata validators passed.
- Three existing scenes (editorial, blackboard, field-notes), nine pages rendered and visually inspected.
- Found Japanese glyph loss in headless preview. Fixed macOS fontconfig discovery locally per render, without modifying global configuration. Original failed previews remain diagnostic artifacts; use *-verified.pptx and associated review.json.
- Clean package dependencies installed with npm ci --offline from populated npm cache in a new temporary directory. No development node_modules copied.
- Relocated Claude package generated PPTX and all three previews using an environment cleared of provider variables; Japanese text in the resulting preview was inspected.
- System Python/Node used for portable tests. This session uses the host-provided LibreOffice binary through the generic DECKSMITH_SOFFICE override.

## Remaining acceptance work

- Actual Claude Code and Gemini CLI sessions, installation/discovery and model-driven YAML interpretation have not been exercised: binaries absent in this environment.
- Windows/Linux and Microsoft PowerPoint rendering not tested.
- These nine slides test renderer migration, not parity with the full NotebookLM reference designs.
- Font availability and model design ability remain environment-dependent.
- Browser ChatGPT/Claude/Gemini integration, native tables/charts, and automatic provider image API adapters remain out of scope for this release.
- Packages are local development builds; no GitHub push, public release or host installation was performed.
