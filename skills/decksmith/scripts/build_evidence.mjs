// Native evidence objects only. No style-name routing or content inference.
const hex = color => color.slice(1);

export function addEvidence(deck, slide, e, box, background) {
  const fill = hex(e.fill ?? background);
  const color = hex(e.color);
  const fontSize = e.size * 0.75;
  if (e.type === "table") {
    const columns = e.column_widths ?? e.headers.map(() => e.width / e.headers.length);
    const heights = e.row_heights ?? [e.headers, ...e.rows].map(() => e.height / (e.rows.length + 1));
    const overrides = new Map((e.highlights ?? []).map(cell => [`${cell.row}/${cell.column}`, cell]));
    const rows = [e.headers, ...e.rows].map((row, r) => row.map((value, c) => {
      const override = overrides.get(`${r}/${c}`) ?? {};
      return {text:value, options:{
        color:hex(override.color ?? (r === 0 ? e.header_color ?? e.color : e.color)),
        fill:{color:hex(override.fill ?? (r === 0 ? e.header_fill ?? e.fill ?? background : e.fill ?? background))},
        bold:override.bold ?? r === 0,
        align:e.column_alignments?.[c] ?? "left",
      }};
    }));
    const padding = e.padding ?? 12;
    // PptxGenJS 4 uses inches below 1, and points at or above 1.
    const margin = padding < 96 ? padding / 96 : padding * 0.75;
    const visibleBorder = {type:(e.border_width ?? 1) === 0 ? "none" : "solid",
      color:hex(e.border_color ?? e.color), pt:(e.border_width ?? 1) * 0.75};
    const noBorder = {type:"none"};
    // Cell borders remain part of the native table when rows are edited.
    // PptxGenJS order is top, right, bottom, left.
    const border = e.border_mode === "none" ? noBorder : e.border_mode === "horizontal"
      ? [visibleBorder, noBorder, visibleBorder, noBorder] : visibleBorder;
    slide.addTable(rows, {...box, colW:columns.map(v => v / 96), rowH:heights.map(v => v / 96),
      fontFace:e.font, fontSize, color, margin, valign:"mid", autoPage:false,
      border,
    });
    return;
  }
  const data = e.series.map(series => ({name:series.name, labels:[...e.categories], values:[...series.values]}));
  const values = e.series.flatMap(series => series.values);
  const minimum = Math.min(0, ...values);
  const maximum = Math.max(0, ...values);
  const lower = Number.isFinite(minimum * 1.15) ? minimum * 1.15 : minimum;
  const upper = Number.isFinite(maximum * 1.15) ? maximum * 1.15 : maximum;
  const axisMin = e.axis_min ?? (minimum < 0 ? lower : 0);
  const axisMax = e.axis_max ?? (maximum > 0 ? upper : minimum < 0 ? 0 : 1);
  const format = e.number_format ?? "General";
  slide.addChart(e.chart_type === "line" ? deck.ChartType.line : deck.ChartType.bar, data, {
    ...box, lang:"ja-JP", chartColors:e.colors.map(hex),
    chartArea:{fill:{color:fill}, border:{color:fill, pt:0}, roundedCorners:false},
    plotArea:{fill:{color:fill}, border:{color:fill, pt:0}},
    showTitle:false, showValue:e.show_values ?? true,
    showLegend:e.show_legend ?? e.series.length > 1,
    legendPos:"b", legendColor:color, legendFontFace:e.font, legendFontSize:fontSize,
    dataLabelColor:color, dataLabelFontFace:e.font, dataLabelFontSize:fontSize,
    dataLabelFormatCode:format, dataLabelPosition:e.chart_type === "line" ? "t" : "outEnd",
    catAxisLabelColor:color, catAxisLabelFontFace:e.font, catAxisLabelFontSize:fontSize,
    catAxisOrientation:e.chart_type === "bar" ? "maxMin" : "minMax",
    catAxisLineShow:false, catAxisMajorTickMark:"none", catAxisMinorTickMark:"none",
    valAxisLabelColor:color, valAxisLabelFontFace:e.font, valAxisLabelFontSize:fontSize,
    valAxisLineShow:false, valAxisMajorTickMark:"none", valAxisMinorTickMark:"none",
    valAxisLabelFormatCode:format, valAxisMinVal:axisMin, valAxisMaxVal:axisMax,
    ...(e.axis_step !== undefined ? {valAxisMajorUnit:e.axis_step} : {}),
    showValAxisTitle:true, valAxisTitle:e.unit, valAxisTitleFontFace:e.font,
    // A full turn is horizontal. PptxGenJS omits 0, triggering vertical auto-rotation.
    valAxisTitleFontSize:fontSize, valAxisTitleColor:color, valAxisTitleRotate:360,
    valGridLine:{color:hex(e.grid_color ?? e.color), size:0.5},
    catGridLine:{style:"none"},
    barDir:e.chart_type === "bar" ? "bar" : "col", barGrouping:"clustered",
    barGapWidthPct:90, barOverlapPct:0,
    lineSize:2.5, lineDataSymbol:"circle", lineDataSymbolSize:7, lineSmooth:false,
  });
}
