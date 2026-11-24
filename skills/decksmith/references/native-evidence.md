# 数値と条件を、編集可能な表・グラフで見せる

数値の差・推移や、同じ観点による条件の比較を扱うときに読む。表やグラフの型を全ページへ適用するものではない。写真、引用、短い主張、関係図が適切なページでは、その表現を使う。

## 原稿から表示までの判断

- 先に、何を比較・確認するのかと、原稿の項目・数値・単位・期間・条件を確かめる。数量のない「強い／弱い」を、棒の長さや架空の点数へ変換しない。
- 差の大きさや推移を読む場合はグラフを検討する。複数の条件を同じ観点で詳しく照合する場合は表を検討する。短い項目の一覧を自動で表にせず、数値があるからというだけでグラフを選ばない。
- グラフは軸とラベルを読める面積を確保する。見出しと補足で図を小さくしすぎない。表の行が多ければ、原稿の条件を保って行高・列幅・ページ構成を検討し、下の行を削って収めない。
- 単位・比較条件・期間・重要な出典は、その図を読む場所で確認できるようにする。図が示す観測結果と、原因に関する推測を区別する。

## 元データを表示文と別に保存

sceneを作る前に、structure.yamlの各ページに`evidence`を記録し、freeze-contentを実行する。原稿・提供データから作り、完成sceneから逆生成しない。これにより、表示の丸めで同じ値に見えても、元データの書き換えを検出できる。

```yaml
slides:
  - id: arrivals
    purpose: 各回の来場者数の違いを示す
    required_text: [第1回, 第2回, 第3回, 人, '240', '320', '410']
    evidence:
      - id: visitors
        type: chart
        categories: [第1回, 第2回, 第3回]
        series:
          - name: 来場者数
            values: [240, 320, 410]
        unit: 人
```

sceneのtable/chartは`evidence_id`で同じページの元データIDを参照する。省略時は要素のidを使う。項目の順序・系列・数値・単位は元データと一致させる。新規の表・グラフには元データが必要。チャート形式や寸法・配色は設計として独立して決められる。

evidenceの表は`{id, type: table, headers, rows}`。headersは空でない文字列の配列、rowsは全列を持つ文字列の行配列。数値も`'2人'`や`'1.20'`のように表示どおりの文字列で残す。空セルは空文字で保持できる。chartは`{id, type: chart, categories, series, unit}`で、系列ごとに全カテゴリの有限な数値を持つ。

## sceneのネイティブグラフ

```yaml
- id: visitor-chart
  type: chart
  evidence_id: visitors
  x: 100
  y: 280
  width: 1720
  height: 660
  chart_type: column
  categories: [第1回, 第2回, 第3回]
  series:
    - name: 来場者数
      values: [240, 320, 410]
  unit: 人
  number_format: '#,##0'
  font: <利用環境で確認した書体>
  size: 32
  role: label
  color: '#21302B'
  colors: ['#237768']
  grid_color: '#D8DFDB'
  axis_min: 0
  axis_max: 500
  axis_step: 100
```

- chart_typeはbar（横棒）、column（縦棒）、line（折れ線）。現在は集合棒と通常の折れ線に対応。積み上げ・複合軸・円などへ無断変換しない。
- 共通の位置・寸法とfont/size/color、categories/series/unit/colorsが必要。colorsは系列数と同じ件数の`#RRGGBB`。fill省略時はスライド背景を使う。
- number_formatはGeneral（既定）、0、0.0、0.00、#,##0、#,##0.0、#,##0.00、0%、0.0%、0.00%。百分率の31%は値0.31とする。元データの精度と表示桁を別々に確認する。
- show_valuesは既定true。show_legendは複数系列なら既定true。非表示の値・系列名は、画面掲載必須の文字の保持には数えない。別途画面に必要ならネイティブ文字として表示する。
- axis_min/max/stepは任意。全データを含み、stepは正数。棒は0を含む軸を使う。折れ線で表示範囲を絞る場合も、比較の意味と誤読をレビューする。軸・値・凡例を画像へ焼き込まない。
- bar/columnはhighlightsで選んだ点の色を指定できる。例は`highlights: [{series: 0, category: 2, color: '#237768'}]`。series/categoryは0始まりの整数で、同じ点を重複指定しない。色は#RRGGBB。線グラフの個別点の強調は未対応。元の系列・カテゴリ・全値・軸・編集用ブックは変更せず、ネイティブの点書式として保持する。強調の根拠はcommunicationへ残す。全項目を別色にしたり、選んだ点だけ値を残したりしない。系列を示す色との対応、凡例、強調しない項目の判読性も画像で確かめる。

## sceneのネイティブ表

tableはheaders/rows、font/size/colorと共通の位置・寸法を持つ。全セルは文字列。列幅はcolumn_widths、行高はヘッダーを含むrow_heightsで指定でき、それぞれ幅・高さの合計と一致させる。省略時は等分。自動で別ページを追加しない。

fill/header_fill/header_color/border_colorは`#RRGGBB`、border_width/paddingはpx。column_alignmentsは列ごとのleft/center/right。highlightsは`{row, column, fill?, color?, bold?}`の配列で、ヘッダーを0行目として指定する。セル結合・画像セル・複雑な表内リッチテキストは未対応。回転はtable/chartとも未対応。

border_modeはall（既定）、horizontal（横罫線のみ）、none（罫線なし）。罫線はネイティブセルの一部として出力する。表をすっきり見せたい場合も、行境界を別の線で重ねて作らず、この指定を使う。行高を変えたときに罫線と表が離れることを避けられる。

```yaml
- id: conditions
  type: table
  x: 100
  y: 300
  width: 1720
  height: 540
  headers: [条件, 現行, 試行案]
  rows:
    - [受付人数, '2人', '3人']
    - [予約のない来場者, 同じ列で対応, 専用列で対応]
  column_widths: [420, 580, 720]
  row_heights: [100, 180, 260]
  font: <確認した書体>
  size: 36
  role: body
  color: '#21302B'
  header_fill: '#237768'
  header_color: '#FFFFFF'
  border_color: '#D8DFDB'
  border_mode: horizontal
  padding: 16
```

同じidの表データを先にstructureのevidenceへ保存する。背景・強調・文字量は指定スタイルと内容から決め、例の数値や色を既定の構図として使い回さない。

## 出力後の確認

構造検査では、全セル・表の行列と寸法、セルの文字色・太字と指定した塗り、グラフの系列色と個別点の強調、系列・カテゴリ・値・単位・表示形式、埋め込まれた編集用ブックとその参照を照合する。sourceの独立基準はsceneの値と別に検査する。

プレビューでは、凡例と系列の対応、負数・割合・単位、ラベルの切れ、軸、表の全行、比較の対称性を確認する。元データが正しく埋め込まれていても、グラフが読みやすいとは限らない。PowerPoint自体での編集・再保存は、その環境で実際に確認した場合だけ検証済みとする。
