# PDF入力

PDFも既存資料の3モードへ入力できる。出力はPPTXで、必要ならPDFも生成する。PDFの解析・描画はローカルで行う。外部変換サービスやOCRサービスには送信しない。

## 対応範囲

| PDFの状態 | ①スタイルのみ／②文章改善・配置固定 | ③全体再設計 |
| --- | --- | --- |
| 文字を正しく抽出できる、同一サイズの通常ページ | 取り込み後の表示照合に合格した場合に対応 | 抽出文字と図の出典を保持して再設計 |
| スキャン・文字なし・回転文字・縦書き・複雑な文字変形・注釈／フォーム・クロップ・不可視／透過文字・文字を覆う図・Formの入れ子・標準以外のUserUnitなど | 未対応と判定。勝手に③へ変更しない | 該当ページを画像の参考資料として取り込む |
| ページサイズが混在 | 未対応 | 最大幅・高さの作業キャンバスへ原寸で取り込み、再設計 |
| 暗号化PDF／壊れたPDF | 拒否 | 拒否 |

通常ページの文字を座標・書体・サイズ・色とともに編集可能な文字枠へ復元する。各抽出行は勝手に折り返さない固定枠とし、②の文章改善ではその枠に収まる表現にする。PDFは元の段落・単語・論理的な読み順を完全には保持していないため、抽出結果と実際の原ページを必ず照合する。①の文字・配置保持は、原ページとの視覚確認と、取り込み後PPTXに対する構造検査の両方で確認する。PDFとPPTXの内部構造が同一になる保証ではない。

図・表・グラフ・背景は96dpiの画像レイヤーとして見た目を保持する。PDFの図表を編集可能な表・グラフや元データへ復元する機能はない。画像レイヤー内の配色・線・背景の直接変更も①②では行わない。画像の上から背景色を覆ってスタイルを達成したことにしない。スタイル指定を画像部分へ適用できない場合は部分適用／未対応として記録する。編集可能な元PPTXがある場合はそちらを優先する。

スキャン等ではOCRを自動実行しない。③の画像取り込みだけで「本文も編集可能になった」と案内しない。AIが原ページを読んで文章を作り直す場合も、原ページ内の数値・条件・出典を実際に照合する。内容画像を保持・参照し、画像自体の省略が必要なら既存の元要素対応表の承認条件に従う。

## ローカル依存

通常のPPTX制作にPDF専用依存は不要。PDF入力を使う環境にはPython 3.10+と、Skill直下のpdf-requirements.txtに記載したpdfplumber、pypdf、pypdfium2、Pillowが必要。必要な準備と通信について既存の承認条件を守り、勝手にインストール・取得しない。

通常版は実行中のPythonを使い、別のローカルPDF用Pythonは`DECKSMITH_PDF_PYTHON`で指定できる。準備済みの依存フォルダーは`DECKSMITH_PDF_MODULES`で指定できる。環境内の任意の場所を自動探索したり、依存不足を外部サービスで補ったりしない。

```bash
python3 <skill-directory>/scripts/doctor.py --pdf-input --renderer libreoffice
```

Windows PORTABLE版の基本ランタイムにはPDF専用依存を同梱していない。管理者等が同梱Pythonと互換の依存を配布物内のruntime/pdf/へ準備した場合のみ、ランチャーがそのフォルダーを読み込む。ホストのPythonや任意の環境変数へは切り替えない。`decksmith.cmd doctor --project <project> --pdf-input`で確認する。この追加経路のWindows実機検証は未実施。

## 解析と取り込み確認

```bash
python3 <skill-directory>/scripts/restyle_deck.py inspect \
  --source <project>/original.pdf --style <project>/style.yaml \
  --mode 2 --destination <project>/pdf-restyle \
  --config <project>/decksmith.yaml --renderer libreoffice
```

同梱版は`inspect-source --source original.pdf --mode 2 --destination pdf-restyle --renderer powerpoint`。利用者に内部ファイルを書かせない。

新しい作業先には次を保存する。

- restyle-plan.yaml：原PDFの指紋、モード、取り込みファイルの指紋、conversion_review。
- pdf/analysis.json：ページごとの対応可否・制約・抽出文字・書体対応。
- pdf/source/slide-XX.png：原PDFから直接描画した比較画像。
- normalized-source/slide-XX.png：復元したPPTXの比較画像。noneでは生成しない。
- pdf-source.pptx：検査対象となる取り込み後のPPTX。手作業で修正しない。
- pptx/：既存の3モード共通の内部計画・inventory。③は元要素対応表とassetsも含む。

**AIは原PDFとnormalized-sourceを全ページ見比べてから、外側のconversion_reviewを記録する。** reviewerを記入し、pagesを原順で一度ずつ列挙する。各ページにpage（1始まり整数）、status: passed、text_evidence、layout_evidence、graphics_evidenceが必要。元の文字、空白、数値、位置、折り返し、図、判読性を具体的に確認する。未確認のまま合格を作らない。抽出対象外ページは、文字が画像内に残っていることも確認する。

復元書体が利用できない、文字がずれる・切れる場合は、元PDFの書体名と利用可能な書体の対応をJSONで作り、`inspect --pdf-font-map <font-map.json>`で新しい作業先へ再取り込みする。例：`{"Helvetica": "Arial", "SourceHanSansJP-Regular": "Noto Sans CJK JP"}`。analysisのfontsで実際の元フォント名を確認し、再描画を見て妥当性を判断する。ハッシュや座標を手で書き換えて合格させない。①②で忠実に復元できなければ制約を伝え、元PPTX等が必要な理由を示す。

## スタイル適用と最終確認

AIはpptx/restyle-plan.yamlを[既存資料の変換手順](restyle.md)に従って完成させる。③のscene、structure、design-planはpptx/内に作る。外側のprepared_filesに含まれる取り込みファイルは変更しない。

```bash
python3 <skill-directory>/scripts/restyle_deck.py apply \
  --source <project>/original.pdf --style <project>/style.yaml \
  --plan <project>/pdf-restyle/restyle-plan.yaml --mode 2 \
  --config <project>/decksmith.yaml --output <project>/../output/restyled.pptx
```

同梱版は`restyle --source original.pdf --plan pdf-restyle/restyle-plan.yaml --mode 2 --renderer powerpoint`。元PDF、取り込みPPTX、元画像、解析記録の変更を拒否する。描画方式も取り込み確認時と合わせる。検査・描画・記録がすべて成功してから出力を公開する。既存出力を上書きしない。

最終.preview/source/は**原PDFから直接描画したページ**であり、復元PPTXの画像へ置き換えない。pdf-conversion.json、pdf-plan.json、変更レポートに原PDFの指紋・制約・取り込み確認を記録する。最終review.jsonには各モードの既存項目に加え、pdf_source_sha256（原PDFの指紋）、pdf_fidelity_evidence（原PDFと最終結果を比較した具体的根拠）が必要。source_sha256は内部の取り込みPPTXの指紋なので混同しない。

noneまたはdraftでは取り込みの視覚合格を要求しないが、未対応ページの①②は生成できない。noneは「見た目未確認」、draftは完成扱い不可を維持する。原PDF由来の画像がある場合は、その部分の編集性・スタイル未適用範囲も納品時に説明する。
