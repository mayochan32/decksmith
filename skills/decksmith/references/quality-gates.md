# 品質検証

入力検証、PPTX構造検証、視覚検証を区別する。

## 自動検証

design-plan.yamlがあれば参照元・ページ・主役要素・文字役割を検証する。design-checks.jsonのサイズ比・書体差はレビューの手がかりであって、美的評価の合否ではない。スタイルに意図された小さな注釈等は、実物を確認して理由付きで許容できる。旧sceneの生成は可能だが、設計方針なしでスタイル適合を合格にしない。
- 元のstyle/structureのSHA-256、全スタイル項目の台帳対応、参照先の存在。
- スライド順序と件数、必須文字列のネイティブ文字内への保持。
- 未対応要素・未知キー・欠損画像・不正数値・意図しない領域外配置を拒否。
- PPTXパッケージのXMLと内部参照、ページ寸法、要素数、ネイティブ文字・図形・パスの保持。フォントの実在と置換は別途確認する。

## 視覚検証

output.renderer=noneの場合は視覚検証を省き、not_visually_reviewedを保持する。構造検査は行い、「PPTX生成済み・見た目未確認」として利用者に確認を依頼する。利用者が明示指定した場合に限り、この状態で納品できる。画像のない記録フォルダーをプレビューと称さない。

プレビューを生成した場合のreview-manifest.jsonはpending_visual_reviewで始まる。AIは全PNGを個別に見て、元YAML、必要なら参考資料と照合する。元PPTXをPowerPointで開いたと主張するのは実際に開いた場合だけ。

1. 全内容・数値・ラベル・出典を確認する。
   原稿とcontent-contract.jsonを独立に照合し、content-changes.jsonの意味の同等性を確認する。sceneから検査基準を逆生成しない。policy記録と実際の会話・ツール履歴も照合する。
2. 大小差、文字組み、色、線、質感、整列、画像の処理を各要件と比較する。
3. 文字の重なり、切れ、意図しない改行、小さすぎる文字、画像の切り取りを調べる。
4. 資料全体の読み順と構図の変化を確認する。
5. 問題はsceneまたは素材を修正し、新しい名前で再出力して再確認する。
   [制作補助](workflow.md)のcompareで未変更PNGを特定できる。画素一致は視覚合格そのものではない。画像上のラベルが繰り返し読めなくなる場合は文字領域と構図を見直す。
6. text-plan.mdのページ別文字量と照合する。キーワード中心／説明中心の意図、判読性、必須内容・条件の保持、話者ノートの保存を確認する。more/denseで根拠のない水増し、minimal/lessで必須内容の脱落がないかも確認する。

review.jsonに出力PPTXのSHA-256、確認したページ、確認結果、変更箇所、未解決事項を記録する。既知の制約を消してpassedにしない。未対応の指定や重大な視覚問題が残れば完成品としない。

## 納品時の整合性チェック

`python3 <skill>/scripts/review_deck.py --output <pptx>`を使う。同梱版は`decksmith.cmd review --project <project> --output output/<name>.pptx`。別のレビューは--reviewで指定できる。実行は読取専用で、合格の視覚判断を自動作成しない。

review.jsonは以下の形式。manifestの指紋を対象PNG/PPTXと照合した上で記録する。証拠文は実際に確認した具体的な内容とし、全項目に同じ「問題なし」をコピーしない。

```json
{
  "output_sha256": "<対象PPTXのSHA-256>",
  "reviewer": "<実際に確認したAIまたは利用者>",
  "unresolved_items": [],
  "pages": [{
    "id": "opening",
    "content": {"status": "passed", "evidence": "必須の内容と条件の確認結果"},
    "legibility": {"status": "passed", "evidence": "表示サイズでの文字・重なり・切れの確認結果"},
    "style": {"status": "passed", "evidence": "design-planの特徴と実際の画面の比較結果"}
  }],
  "requirements": [{"source": "/Typography/Heading", "status": "passed", "evidence": "達成・非該当・承認済み代替の妥当性を確認した根拠"}],
  "warning_resolutions": {"<design-checksのwarning ID>": "修正または意図された例外を確認した根拠"}
}
```

pages/requirementsはそれぞれ全ページ・全要件を網羅する。未解決ならunresolved_itemsへ残し、該当箇所はfailedにする。承認済み代替があれば最終結果はpassed_with_approved_alternativesとして区別する。生成manifestのpending_visual_reviewは生成時点の状態であり、最終状態はreviewコマンドの結果を使う。

PPTX、PNG、設計方針、測定レポートの指紋不一致は停止する。PowerPointで再保存した場合も再生成・再確認する。指紋だけの書き換えは不可。構造検証・視覚レビュー・スタイルレビュー・成果物一致は別々の保証であり、ツールの合格だけでデザイン品質が保証されたとは説明しない。

## 開発の受入検証
同じ内容で複数のスタイルを作り、さらに未知の日本語YAMLを使う。プラグインのコードを変更せずに、配置・色・書体・素材が指定に応じて変化することを確認する。反対の配置指示、5項目以上、文中強調、異なる書体、画像の重なりを含める。配布用ディレクトリのみを別の作業場所へコピーして実行し、開発用ファイルへの依存を検出する。意味解釈はAIの仕事なので、コードテストだけで成功と判定しない。
