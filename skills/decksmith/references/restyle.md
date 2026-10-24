# 既存資料のスタイル変換

## 対応範囲とルーティング

**PPTX入力で3モードに対応する。** モード①style_onlyは文章と配置を保持する。②style_and_textは文章を改善し、枠・配置・ページ構成を保持する。③redesignは元資料を根拠に文章・配置・ページ構成を再設計する。①②は複製・限定変更、③はstructure/sceneと元資料の対応表を使う。元ファイルと既存出力を上書きしない。

モードは利用者が選ぶ。指定済みなら再確認しない。CLIの--modeは1/2/3または上記の英語名。inspectは省略時①、applyは計画のmodeを使い、--modeを明示すると計画との不一致を拒否する。**PDF入力は先に[PDF取り込み](pdf-input.md)を読む。** 原PDFとの表示照合を経て同じ3モードへ接続する。図表の編集性などPPTXと保持条件が異なる。以下の直接複製・ネイティブ図表の説明はPPTX入力用。旧形式PPT入力は未対応。

①②で直接変更できる書式は、スライド背景、p:sp図形の塗り・線色、p:sp内の文字色・書体・文字サイズ・太字・斜体。②では通常runの文章も改善できる。画像、ネイティブ表・グラフ、マスター、レイアウト、ノート、埋め込みデータはそのまま残す。グループ内のp:spもIDで指定でき、グループ座標は保持する。画像内の文字、表・グラフ内の文字は直接の書き換え対象外。デジタル署名付き・Strict OOXML・重複ID等の読めない資料は明示して停止する。

①②では画像を塗りとして使う図形や背景を単色で覆う変更も拒否する。背景はレイアウト・マスターからの継承を確認する。テーマやプレースホルダーからの継承で画像の塗りを否定できない場合は、fillの変更を未対応として扱う。inventoryのfill_constraintとbackground_constraintを読み、画像を失う操作を作らない。

## 保持条件

以下の保持条件と既存の計画例はモード①用。モード②③固有の手順は後半を読む。

- 文章は文字単位で固定する。空白、明示改行、段落、フィールド、箇条書きの変更、誤字修正、翻訳もしない。
- 位置、寸法、回転、枠内余白、段落配置、重なり順、画像の切り抜き、グループ、ページ数・順序・サイズを固定する。
- フォント・文字サイズ・太字・斜体は見た目の折り返しに影響する。利用可能なフォントを確認し、元資料と変換後の全ページを比較する。自動検査の合格だけで「改行も完全保持」と案内しない。
- はみ出しや折り返しが変わったら、文章や枠を直さず、許可された書式を調整して別名で再生成する。保持と両立しない指定はpreservation_conflictとして対象と理由を示す。
- 新規制作の「構図を最適化する」「文字量を減らす」「図解を追加する」はモード①に適用しない。スタイルと保持条件が衝突したら保持を優先する。

## 1. 読み込みと計画

```bash
python3 <skill-directory>/scripts/restyle_deck.py inspect \
  --source <project>/original.pptx --style <project>/style.yaml \
  --destination <project>/restyle
```

Windows同梱版では直接Pythonを起動せず、次を使う。

```text
decksmith.cmd inspect-source --project <project> --source original.pptx --style style.yaml
```

新しいrestyleフォルダーにsource-inventory.jsonとrestyle-plan.yamlを作る。元資料のページ順、shape_id、文章、座標を読み、元資料のプレビューも実際に確認する。inventoryのkindとtext_style_supportedに従って対象を選ぶ。構図や写真の質感など、今回変更できない指定を色の変更だけで達成したと扱わない。

**計画はAIが作成する内部ファイル。利用者に書かせない。** 元のstyle.yamlは任意キー・任意言語のまま保ち、AIが意味を解釈する。プログラムは特定のスタイル名で分岐しない。inspectが作った元PPTX・スタイルのSHA-256を維持する。元ファイルが変わった場合は再解析し、ハッシュだけを差し替えない。

計画はYAMLまたはJSON。形式例：

```yaml
schema_version: '1.0'
mode: style_only
source_sha256: <inspectで取得した値>
style_sha256: <inspectで取得した値>
requirements:
  - source: /配色/文字
    interpretation: 見出しの文字色を指定色へ変更する
    status: implemented
    operations: [title-color]
  - source: /構図
    interpretation: 中央配置の指定だが、元の位置を優先する
    status: preservation_conflict
    reason: 文字枠を中央へ移動すると、モード①の配置固定に反するため
    operations: []
operations:
  - id: title-color
    slide: 1
    shape_id: '2'
    set:
      text_color: '#C92C1C'
```

requirementsはstyle.yamlの全末端値をJSON Pointerで一度ずつ網羅する。例は対応する2項目のスタイルの場合のみ有効。statusはimplemented / partially_implemented / preservation_conflict / unsupported / not_applicable。implementedとpartially_implementedは実在するoperation IDが必須。partially_implementedは未適用の対象と理由をreasonへ記録する。例えば全体の文字色指定を通常の文字だけに適用し、ネイティブ表の文字を保持する場合は部分適用とする。それ以外の除外状態はreasonが必須でoperationsは空。metadataなど適用対象外の指定のみnot_applicableにし、未対応機能を非該当に偽装しない。unsupportedが残った計画は--draft以外では生成できない。

操作のslideは**元資料のページ順による1始まり**。ファイル名のslide番号と混同しない。shape_idはinventoryの文字列ID。背景はshape_id: backgroundとしてfillのみを指定する。

| setの項目 | 値・意味 |
| --- | --- |
| fill | #RRGGBB。図形またはスライド背景の塗り |
| line_color | #RRGGBB。線色のみ。線幅・矢印は保持 |
| text_color | #RRGGBB。対象の文字・フィールド・段落の既定文字色 |
| font | 利用可能な書体名。欧文・日本語・複合文字の書体指定 |
| font_size | 1〜400の数値。単位pt |
| bold / italic | true / false |

同じページ・同じ対象の同じ属性を複数操作で変更することは禁止。textやx/y等の変更属性は拒否する。

## 2. 変換

```bash
python3 <skill-directory>/scripts/restyle_deck.py apply \
  --source <project>/original.pptx --style <project>/style.yaml \
  --plan <project>/restyle/restyle-plan.yaml \
  --config <project>/decksmith.yaml \
  --output <project>/../output/restyled.pptx --next-output
```

```text
decksmith.cmd restyle --project <project> --source original.pptx --style style.yaml --renderer powerpoint --next-output
```

通常版のrendererはlibreoffice / powerpoint / none。同梱版はpowerpoint / none。変換失敗時の自動切り替えはない。--config省略時は計画と同じフォルダーの設定を探すため、setting/decksmith.yamlを使う場合は明示する。output.pdf=trueでPDFも出力可能。noneは利用者の明示指定時に限り使い、見た目未確認のまま納品する。

PPTXを複製して許可された書式だけを書き換える。検査と描画が完了するまで納品先に結果を作らない。既存のPPTX、PDF、同名.preview（切れたシンボリックリンクも含む）は上書きしない。

## 3. レビューと納品

出力PPTXと同名.previewに次を保存する。

- restyle-report.md / .json：変更操作、保持検査、未適用項目と理由。
- source-inventory.json / restyle-plan.json / style.yaml：入力と解釈の記録。
- slide-XX.png：変換後。source/slide-XX.png：同じ描画方式による元資料。
- review-manifest.json：PPTX、プレビュー、記録の指紋。noneではPNGはない。

全ページで内容、配置、折り返し、判読性、スタイルを別々に比較する。特に元資料のフォント自体が代替表示されていないかを確認し、PowerPointでの確認が必要なら限界を伝える。変更操作を適用できたことと、指定スタイルの視覚的達成を区別する。

確認後、実際に観察した根拠でreview.jsonを作る。output_sha256、source_sha256、reviewer、unresolved_items（合格時は空）、pages、requirementsが必要。pagesはmanifestと同じidを順番どおりに列挙し、content/layout/wrapping/legibility/styleの各項目にstatus: passedと具体的なevidenceを書く。requirementsも全sourceにstatus: passedと、適用結果または除外が妥当である根拠を記録する。policy-recordがある場合はpolicy_evidenceも必要。架空の確認・自動承認は作らない。

```bash
python3 <skill-directory>/scripts/review_deck.py --output <project>/../output/restyled.pptx
```

同梱版は既存のreviewコマンドを使う。PPTXや比較画像、記録が変わっていたらレビューは拒否される。--draftは完成扱いできない。保持条件との衝突による除外がある場合は、検証後もpassed_with_exclusionsとして未適用項目を利用者へ伝える。

モード①の説明資料では元資料の意図を推測で作り直さず、変更レポートを標準の説明資料とする。納品時は「保持検査の結果」「スタイルの適用範囲」「視覚確認の状態」を区別して案内する。

## モード②：文章改善・配置固定

inspectに`--mode 2`を指定する。Windows同梱版も`inspect-source --mode 2`で同じ雛形を作る。①のoperationsによるスタイル変更に加え、AIがrewrites、protected_terms、protection_reviewを完成させる。数値・固有名詞・単位・条件・出典を元資料から確認し、表現を改善する。主張や条件を創作しない。

```yaml
mode: style_and_text
# schema_version、元ファイルとstyleの指紋、requirements、operationsは①と共通。
protection_review: 元資料の数値、単位、対象地域、出典を確認した。
protected_terms:
  - {slide: 1, shape_id: '2', text: 東京}
  - {slide: 1, shape_id: '2', text: '10%'}
rewrites:
  - id: concise-body
    slide: 1
    shape_id: '2'
    edits:
      - run: 0
        before: 東京で10%改善することを目標にしています。
        after: 東京で10%改善を目指します。
        reason: 対象と目標値を保ち、冗長な表現を短くする。
```

runはinventoryのtext_runsに記録した0始まりの番号。p:sp内の既存の通常文字列だけを変更し、フィールド、段落、明示改行、箇条書き、リンク、枠内余白、座標、重なり、図表、画像、ノートは保持する。複数runにまたがる文は、元の強調やリンクの範囲に注意して各runへ新しい文字を割り当てる。run自体を追加・削除しない。表・グラフ内の文字や画像内の文字は②の書き換え対象外。複雑な書式の再構成は③で扱う。

style.yamlに文体や簡潔さの指定がある場合、そのrequirements.operationsには対応するrewriteのidを指定できる。書式operationとrewriteのidは区別する。文章改善が利用者の指示に由来し、スタイルの項目に対応しない場合は、rewriteを無理にスタイル要件へ割り当てなくてよい。

通常の折り返しは枠内で変わってよい。枠を動かさず、新しい文章と指定書式で収める。構造上の段落や明示改行を増減する操作は今回の②に含まない。文字切れやはみ出しを理由に枠を拡大したり、数値や条件を削除したりしない。必要なら文章を再改善する。

beforeの完全一致、変更runの重複禁止、各枠内の数値トークンの保持、protected_termsの出現回数の保持を検査する。これは意味の同一性を自動保証しない。protection_reviewには確認した対象を具体的に記録し、固有名詞や条件の保護を空欄で済ませない。追加APIや固定の言い換え辞書は不要で、文章改善はホストAIが行う。

applyは①と共通で`--mode 2`を付けられる。計画は内部ファイルであり利用者に書かせない。変更レポートにはbefore/after/reasonが保存される。最終reviewの各ページはcontent/meaning/layout/overflow/legibility/styleを確認する。元と同じ折り返しかではなく、新しい文章が固定枠内で読めるかを見る。

review.jsonにはrewritesを追加し、全rewriteのidを一度ずつstatus: passedと意味を保持した根拠evidenceで確認する。protection_evidenceに数値・単位・条件・出典の照合根拠を書く。①のwrappingだけのレビューを流用しない。

## モード③：元資料を根拠に全体を再設計

```bash
python3 <skill-directory>/scripts/restyle_deck.py inspect \
  --source <project>/original.pptx --style <project>/style.yaml \
  --mode 3 --destination <project>/redesign
```

source-content.jsonに元のスライド要素、文字、表の文字、グラフのキャッシュ値、話者ノートを保存し、画像素材もassets/へ抽出する。グループは内部を保持する一つの要素として扱う。元資料のプレビューを全ページ読み、マスター由来の文字・画像・背景の情報も確認する。マスターから継承した内容はsource-contentの要素一覧に自動抽出されないため、見える重要情報を設計へ引き継ぎ、その根拠を原ページのレビューに記録する。原データと出力sceneを混同しない。

AIが目的・対象読者・元の主張を確認し、[内容と読み順](communication-design.md)、[構図](composition-design.md)、[スタイル](style-system.md)、[シーン仕様](deck-spec.md)、[デザイン方針](design-plan.md)を使ってscene.yaml、structure.yaml、design-plan.yamlを作る。ページの統合・分割・順序変更、文章改善、位置・寸法の変更が可能。原文の単純な拡大縮小や固定構図の適用で済ませない。表示必須の事実をノートだけに移さない。

redesign/restyle-plan.yamlのscene/structure/design_planは、その計画からの相対パス。画像はsceneからの相対パス。元ファイルとstyleの指紋は再解析なしで更新しない。protected_termsは`{source_id: s1/o2, text: 東京}`形式。protection_reviewも必須。

mappingはsource-content.jsonの各idを一度ずつ網羅する。各項目にsource_id、status、classification（contentまたはdecoration）、targets、reasonを指定する。

| status | 意味・追加項目 |
| --- | --- |
| preserved | 文字または画像を保持して移動。文字のafterは原文と一致させる |
| rewritten | 文章改善。afterに出力文字列、reasonに改善理由を記録 |
| redesigned | 装飾や図形を再構成。文字がある場合はafterも必要 |
| native | 表・グラフ・グループ・複雑な図形を編集可能なまま取り込む |
| omitted | 省略。targetsは空で理由必須。content、表・グラフ・グループ・ノートの省略には明示的な利用者承認の根拠approvalが必要。承認を創作しない |

targetsはsceneの`スライドID/要素ID`、ノートは`スライドID/notes`。統合した一つの要素へ複数の原要素を対応づけてもよい。afterはそのtargetsに実在する文字列とし、原要素の数値を保つ。重複した原文を統合する際も対応を省略しない。数値を伴う新たな主張を創作せず、元資料での根拠を最終レビューで照合する。

### 編集可能な表・グラフ・グループ

sceneに配置用のrect図形を作り、nativeのtargetsにそのIDを一つ指定する。生成後にこの図形を元のネイティブ要素へ置き換えるため、納品物に四角のプレースホルダーは残らない。元の表・グラフの文字列もstructureのrequired_textへ記録できる。source-contentに基づくnative文字列を追加して検査し、画像化して済ませない。

```yaml
mapping:
  - source_id: s2/o4
    status: native
    classification: content
    targets: [evidence/chart]
    reason: 元のグラフと埋め込みデータを保ち、比較しやすい位置へ移す。
```

元オブジェクトと、実際に参照するグラフデータ・埋め込みワークブック・画像等だけを取り込み、新しい位置・寸法へ変換する。依存データのバイト列と出力のネイティブ構造を検査する。内部のデータや書式は保持し、元の表やグラフの内部書式を全面的にスタイル変更する機能ではない。内部書式も必須のスタイル指定で変更できない場合は未達として示す。外部リンクは取得しない。内部スライドへの古いリンクや未対応のAlternateContentを黙ってコピーせず拒否する。コネクターをnativeで保持する場合は接続対象も同じ出力ページへ取り込む。

元の画像をエビデンスとして使う場合は、抽出した素材をsceneのimageとして使うかnativeで保持する。装飾画像を作り直す・省略する場合はclassification: decorationとし、理由を記録する。source-content内のnative_requiredがtrueの要素は画像や通常テキストへの置換を拒否する。

### 生成と最終確認

```bash
python3 <skill-directory>/scripts/restyle_deck.py apply \
  --source <project>/original.pptx --style <project>/style.yaml \
  --mode 3 --plan <project>/redesign/restyle-plan.yaml \
  --config <project>/decksmith.yaml --output <project>/../output/redesigned.pptx
```

Windows同梱版では`inspect-source --mode 3 --destination redesign`、`restyle --mode 3 --plan redesign/restyle-plan.yaml`を使う。出力・PDF・上書き保護は①②と共通。

レポートには全原要素のbefore、after、移動先、理由、元と結果のページ数を記録する。比較画像は元と結果で枚数が異なってよい。ノート、必須内容、保護語を含め、意味・条件が残ったことを実際に確認する。構造保持合格ではなく、再設計と出典対応の検査合格として案内する。

reviewの各出力ページはcontent/meaning/layout/overflow/legibility/styleを確認する。加えてmappingに全source_idのstatus: passedとevidence、source_pagesに全原ページのid（1始まり文字列）のstatus: passedとevidence、protection_evidenceに保護内容の照合を書く。design-checks.jsonの警告はwarning_resolutionsへ根拠を記録する。元と結果のページを一対一と決めつけず、統合・分割先をたどる。変更レポートとともにページ別design-notes.mdも作成し、内容・構図の判断を説明する。
