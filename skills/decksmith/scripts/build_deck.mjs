import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

function parseArgs(argv) {
  const result = {};
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key?.startsWith("--") || !value) throw new Error(`Invalid argument near ${key ?? "end"}`);
    result[key.slice(2)] = value;
  }
  for (const required of ["spec", "output", "workspace"]) {
    if (!result[required]) throw new Error(`Missing --${required}`);
  }
  return result;
}

function addText(slide, text, position, options = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position,
    fill: "none",
    line: { fill: "none", width: 0 },
  });
  shape.text = text ?? "";
  shape.text.style = {
    typeface: options.typeface,
    fontSize: options.fontSize,
    bold: options.bold ?? false,
    color: options.color,
    alignment: options.alignment ?? "left",
    verticalAlignment: options.verticalAlignment ?? "top",
    autoFit: "shrinkText",
    wrap: "square",
    lineSpacing: options.lineSpacing,
    insets: options.insets ?? { top: 0, right: 0, bottom: 0, left: 0 },
  };
  return shape;
}

function addBulletList(slide, items, position, style) {
  const shape = addText(slide, "", position, style);
  shape.text.set((items ?? []).map((item) => ({
    bulletCharacter: "•",
    marginLeft: 24 * 12700,
    indent: -12 * 12700,
    spaceAfter: 750,
    runs: [String(item)],
  })));
  return shape;
}

function displayTitle(value, typography) {
  const text = String(value ?? "");
  return typography.uppercase_titles ? text.toUpperCase() : text;
}

function catalogEntry(style, layout) {
  return (style.layout_catalog ?? []).find((entry) => (entry.applies_to ?? []).includes(layout)) ?? {
    variant: "standard",
    type: "Default",
    design: "DeckSmith standard layout",
  };
}

function addDividerList(slide, items, position, style, variant) {
  const values = items ?? [];
  if (!values.length) return;
  const rowHeight = Math.min(82, position.height / values.length);
  values.forEach((item, index) => {
    const top = position.top + index * rowHeight;
    const label = variant === "terminal-list" ? `>_ ${String(item)}` : String(item);
    addText(slide, label, {
      left: position.left + (variant === "terminal-list" ? 18 : 0),
      top: top + 10,
      width: position.width - 24,
      height: rowHeight - 16,
    }, style);
    if (index < values.length - 1) {
      slide.shapes.add({
        geometry: "rect",
        position: { left: position.left, top: top + rowHeight - 3, width: position.width, height: 2 },
        fill: style.color,
        line: { fill: "none", width: 0 },
      });
    }
  });
}

async function addImage(slide, image, position, defaultFit, radius) {
  if (!image?.path) return false;
  const bytes = await fs.readFile(image.path);
  const extension = path.extname(image.path).toLowerCase();
  const contentTypes = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
  };
  const contentType = contentTypes[extension];
  if (!contentType) throw new Error(`Unsupported image type: ${image.path}`);
  slide.images.add({
    blob: bytes,
    contentType,
    alt: image.alt ?? "Slide image",
    prompt: image.prompt,
    fit: image.fit ?? defaultFit,
    geometry: "roundRect",
    borderRadius: radius,
    position,
  });
  return true;
}

function addPageFurniture(slide, slideNumber, total, style, fontFamily) {
  const { colors, typography, spacing, decoration } = style;
  if (decoration.accent_bar) {
    slide.shapes.add({
      geometry: "rect",
      position: { left: spacing.margin_x, top: 680, width: 54, height: 5 },
      fill: colors.accent,
      line: { fill: "none", width: 0 },
    });
  }
  if (decoration.page_numbers) {
    addText(
      slide,
      `${String(slideNumber).padStart(2, "0")} / ${String(total).padStart(2, "0")}`,
      { left: 1080, top: 664, width: 120, height: 30 },
      { typeface: fontFamily, fontSize: typography.small, color: colors.muted, alignment: "right" },
    );
  }
  if (decoration.frame_lines) {
    for (const position of [
      { left: 24, top: 20, width: 1232, height: 2 },
      { left: 24, top: 698, width: 1232, height: 2 },
    ]) {
      slide.shapes.add({
        geometry: "rect",
        position,
        fill: colors.accent,
        line: { fill: "none", width: 0 },
      });
    }
  }
}

function notesFor(slideSpec) {
  const parts = [];
  if (slideSpec.notes) parts.push(String(slideSpec.notes));
  for (const citation of slideSpec.citations ?? []) parts.push(`Source: ${citation}`);
  return parts.join("\n");
}

async function renderSlide(slide, previewPath, layoutPath) {
  const preview = await slide.export({ format: "png", scale: 1 });
  await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
  const layout = await slide.export({ format: "layout" });
  await fs.writeFile(layoutPath, await layout.text());
}

const args = parseArgs(process.argv.slice(2));
const specPath = path.resolve(args.spec);
const outputPath = path.resolve(args.output);
const workspaceDir = path.resolve(args.workspace);
const { SKILL_DIR, TMP_DIR, RUNTIME_PYTHON } = process.env;
for (const [name, value] of Object.entries({ SKILL_DIR, TMP_DIR, RUNTIME_PYTHON })) {
  if (!value || !path.isAbsolute(value)) throw new Error(`${name} must be an absolute path`);
}

const spec = JSON.parse(await fs.readFile(specPath, "utf8"));
const style = spec.style.executable;
const { colors, typography, spacing, image: imageStyle } = style;
const utils = await import(pathToFileURL(path.join(SKILL_DIR, "container_tools/artifact_tool_utils.mjs")).href);
const fontFamily = typography.family || utils.resolvePresentationFont();
const presentation = Presentation.create({ slideSize: style.canvas });
const totalSlides = spec.slides.length;

for (let index = 0; index < spec.slides.length; index += 1) {
  const item = spec.slides[index];
  const slide = presentation.slides.add();
  slide.background.fill = colors.background;
  const catalog = catalogEntry(style, item.layout);
  const variant = catalog.variant;
  const mx = spacing.margin_x;
  const my = spacing.margin_y;
  const contentTop = my + typography.heading + spacing.title_gap;
  const commonBody = {
    typeface: fontFamily,
    fontSize: typography.body,
    color: colors.text,
    lineSpacing: typography.line_spacing,
  };

  if (item.layout === "cover") {
    if (variant === "mega-title") {
      const hasImage = await addImage(slide, item.image, { left: 786, top: 248, width: 494, height: 472 }, imageStyle.fit, imageStyle.corner_radius);
      if (!hasImage) {
        slide.shapes.add({
          geometry: "rect",
          position: { left: 0, top: 520, width: 1280, height: 200 },
          fill: colors.accent,
          line: { fill: "none", width: 0 },
        });
      }
      addText(slide, displayTitle(item.title, typography), { left: mx, top: 74, width: 1120, height: 360 }, {
        typeface: fontFamily,
        fontSize: Math.max(typography.title, 76),
        bold: true,
        color: colors.text,
        verticalAlignment: "middle",
        lineSpacing: typography.line_spacing,
      });
      if (item.subtitle) addText(slide, item.subtitle, { left: mx, top: 570, width: 650, height: 78 }, {
        ...commonBody,
        color: hasImage ? colors.muted : colors.on_accent,
      });
      const notes = notesFor(item);
      if (notes) slide.speakerNotes.textFrame.setText(notes);
      continue;
    }
    const hasImage = await addImage(slide, item.image, { left: 690, top: 0, width: 590, height: 720 }, imageStyle.fit, imageStyle.corner_radius);
    if (!hasImage) {
      slide.shapes.add({
        geometry: "rect",
        position: { left: 862, top: 0, width: 418, height: 720 },
        fill: colors.accent,
        line: { fill: "none", width: 0 },
      });
    }
    addText(slide, displayTitle(item.title, typography), { left: mx, top: 176, width: 660, height: 190 }, {
      typeface: fontFamily,
      fontSize: typography.title,
      bold: true,
      color: colors.text,
      verticalAlignment: "middle",
    });
    if (item.subtitle) addText(slide, item.subtitle, { left: mx, top: 402, width: 610, height: 92 }, {
      ...commonBody,
      color: colors.muted,
    });
  } else if (item.layout === "closing") {
    slide.background.fill = colors.accent;
    addText(slide, displayTitle(item.title, typography), { left: 130, top: 210, width: 1020, height: 160 }, {
      typeface: fontFamily,
      fontSize: typography.title,
      bold: true,
      color: colors.on_accent,
      alignment: "center",
      verticalAlignment: "middle",
    });
    if (item.subtitle) addText(slide, item.subtitle, { left: 210, top: 402, width: 860, height: 80 }, {
      ...commonBody,
      color: colors.on_accent,
      alignment: "center",
    });
  } else if (item.layout === "full-bleed" && item.image?.path) {
    await addImage(slide, item.image, { left: 0, top: 0, width: 1280, height: 720 }, imageStyle.fit, 0);
    slide.shapes.add({
      geometry: "rect",
      position: { left: 0, top: 0, width: 1280, height: 720 },
      fill: "#00000099",
      line: { fill: "none", width: 0 },
    });
    addText(slide, displayTitle(item.title, typography), { left: mx, top: 190, width: 900, height: 160 }, {
      typeface: fontFamily,
      fontSize: typography.title,
      bold: true,
      color: "#FFFFFF",
    });
    if (item.body) addText(slide, item.body, { left: mx, top: 390, width: 760, height: 150 }, {
      ...commonBody,
      color: "#FFFFFF",
    });
  } else {
    addText(slide, displayTitle(item.title, typography), { left: mx, top: my, width: 1128, height: 76 }, {
      typeface: fontFamily,
      fontSize: typography.heading,
      bold: true,
      color: colors.text,
    });

    if (item.layout === "statement") {
      const impact = variant === "impact-statement";
      addText(slide, item.body ?? item.subtitle ?? "", {
        left: impact ? mx : 135,
        top: impact ? 190 : 225,
        width: impact ? 1120 : 1010,
        height: impact ? 350 : 260,
      }, {
        typeface: fontFamily,
        fontSize: impact ? Math.max(typography.title, 68) : Math.max(typography.heading, 42),
        bold: true,
        color: colors.accent,
        alignment: impact ? "left" : "center",
        verticalAlignment: "middle",
      });
    } else if (item.layout === "split") {
      const columnWidth = (1128 - spacing.gutter) / 2;
      const blocks = [
        { value: item.left ?? {}, left: mx },
        { value: item.right ?? {}, left: mx + columnWidth + spacing.gutter },
      ];
      for (let blockIndex = 0; blockIndex < blocks.length; blockIndex += 1) {
        const block = blocks[blockIndex];
        const dual = variant === "dual-split";
        const blockFill = dual && blockIndex === 0 ? colors.accent : colors.surface;
        const blockText = dual && blockIndex === 0 ? colors.on_accent : colors.text;
        slide.shapes.add({
          geometry: "rect",
          position: { left: block.left, top: contentTop, width: columnWidth, height: 420 },
          fill: blockFill,
          line: { fill: "none", width: 0 },
          borderRadius: dual ? 0 : 18,
        });
        addText(slide, block.value.heading ?? "", { left: block.left + 30, top: contentTop + 30, width: columnWidth - 60, height: 52 }, {
          typeface: fontFamily,
          fontSize: 28,
          bold: true,
          color: blockText,
        });
        addBulletList(slide, block.value.items ?? [], { left: block.left + 30, top: contentTop + 108, width: columnWidth - 60, height: 260 }, {
          ...commonBody,
          color: blockText,
        });
      }
    } else if (item.layout === "image-left" || item.layout === "image-right") {
      const imageOnLeft = item.layout === "image-left";
      const imageLeft = imageOnLeft ? mx : 704;
      const textLeft = imageOnLeft ? 704 : mx;
      await addImage(slide, item.image, { left: imageLeft, top: contentTop, width: 500, height: 420 }, imageStyle.fit, imageStyle.corner_radius);
      if (item.body) addText(slide, item.body, { left: textLeft, top: contentTop, width: 500, height: 125 }, commonBody);
      if (item.bullets?.length) addBulletList(slide, item.bullets, { left: textLeft, top: contentTop + (item.body ? 145 : 0), width: 500, height: item.body ? 250 : 390 }, commonBody);
    } else if (item.layout === "bullets" && ["divider-list", "terminal-list"].includes(variant)) {
      if (item.body) addText(slide, item.body, { left: mx, top: contentTop, width: 1030, height: 90 }, commonBody);
      addDividerList(slide, item.bullets, {
        left: mx,
        top: contentTop + (item.body ? 112 : 0),
        width: 1120,
        height: item.body ? 300 : 410,
      }, {
        ...commonBody,
        color: variant === "terminal-list" ? colors.accent : colors.text,
        fontSize: variant === "terminal-list" ? Math.max(typography.body, 24) : typography.body,
      }, variant);
    } else {
      if (item.body) addText(slide, item.body, { left: mx, top: contentTop, width: 1030, height: 105 }, commonBody);
      if (item.bullets?.length) addBulletList(slide, item.bullets, { left: mx, top: contentTop + (item.body ? 130 : 0), width: 1030, height: item.body ? 310 : 420 }, commonBody);
    }

    addPageFurniture(slide, index + 1, totalSlides, style, fontFamily);
  }

  const notes = notesFor(item);
  if (notes) slide.speakerNotes.textFrame.setText(notes);
}

const stagingDir = path.join(TMP_DIR, "finalizer");
await fs.mkdir(stagingDir, { recursive: true });
await fs.mkdir(path.dirname(outputPath), { recursive: true });
const candidatePath = path.join(stagingDir, "candidate.pptx");
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);

const previewDir = outputPath.replace(/\.pptx$/i, ".preview");
await fs.mkdir(previewDir, { recursive: true });
for (let index = 0; index < presentation.slides.items.length; index += 1) {
  const number = String(index + 1).padStart(2, "0");
  await renderSlide(
    presentation.slides.items[index],
    path.join(previewDir, `slide-${number}.png`),
    path.join(previewDir, `slide-${number}.layout.json`),
  );
}

const expectedSlideSizeEmu = "12192000,6858000";
await utils.finalizePresentation({
  explicitTotalSlideCount: totalSlides,
  requiredNativeTableOwnerSlides: [],
  requiredNativeChartOwnerSlides: [],
  workspaceDir,
  candidatePath,
  finalPath: outputPath,
  pythonExecutable: RUNTIME_PYTHON,
  integrityValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: [
    "--expected-slide-size-emu",
    expectedSlideSizeEmu,
    "--validate-bullet-geometry",
    "--validate-heading-fit",
  ],
  verifyArtifactToolImport: true,
  receiptPath: path.join(stagingDir, `${path.basename(outputPath)}.validation.json`),
});

console.log(JSON.stringify({ output: outputPath, previewDir, slides: totalSlides }));
