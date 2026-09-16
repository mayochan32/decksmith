# DeckSmith

DeckSmithは、「題材」「構成」「スタイル」を個別に指定し、編集可能なPowerPointファイルを生成するChatGPT／Codex向けプラグインです。

MVPはSkillのみで構成しています。推論と画像生成には、利用者がサインインしているChatGPT／Codexワークスペースの機能を使用するため、APIキーの設定やローカルGPUは必要ありません。

## MVPでできること

- 題材・構成・スタイルを対話形式で指定
- 参考画像からスタイルを二段階で抽出
- Codex内蔵の画像生成を利用
- YAMLから再現性のあるPPTXを生成
- 文字や情報を表すオブジェクトを編集可能な状態で保持
- PPTXの構造検査と、全スライドのPNGプレビュー生成
- 個人利用から、GitHub経由の社内配布・一般公開へ拡張可能

## 処理の考え方

DeckSmithは、入力を次の3要素に分けて扱います。

1. **題材**：何を、誰に、何のために伝えるか
2. **構成**：スライド数、話の順序、各スライドの役割
3. **スタイル**：雰囲気、参考画像、配色、余白、文字サイズ、画像表現

スタイルはさらに次の2ファイルへ分離します。

- `creative-style.yaml`：雰囲気や世界観などの創造的な意図
- `executable-style.yaml`：配色、余白、文字サイズなどの実行可能な規則

## 使い方

通常は、ChatGPT／CodexでDeckSmithを選択し、自然言語で依頼します。Presentationsの保存場所やAPIキーを入力する必要はありません。

```text
DeckSmithでPowerPointを作って。
題材：生成AI導入の社内提案
構成：課題、解決策、導入計画、費用対効果
スタイル：添付した参考画像に合わせる
```

DeckSmithは、実行環境に組み込まれたPresentations機能を内部で呼び出します。利用者がPresentationsのディレクトリを作成したり、その場所を調べたりする必要はありません。

## 開発者向け：付属サンプルの実行

Codexのプレゼンテーション用ランタイムが利用できる環境で、`skills/decksmith`から実行します。

```bash
"${RUNTIME_PYTHON:-${CODEX_PRIMARY_RUNTIME_PYTHON:-python3}}" scripts/create_deck.py \
  --topic assets/examples/topic.yaml \
  --structure assets/examples/structure.yaml \
  --creative-style assets/examples/creative-style.yaml \
  --executable-style assets/examples/executable-style.yaml \
  --output output/decksmith-mvp.pptx
```

PPTXと、目視確認用の`.preview`ディレクトリが生成されます。既存の出力ファイルは上書きしません。

Presentationsの場所とCodexランタイムは自動検出します。特殊な開発環境で自動検出できない場合に限り、`DECKSMITH_PRESENTATIONS_SKILL_DIR`環境変数、または`--presentations-skill-dir`オプションで明示できます。この設定は一般利用者向けではありません。

## 日本語フォントについて

日本語テキストは、編集可能な文字としてPPTXに保存されます。ただし、PNGプレビューで正確に検査するには、実行環境に日本語フォントが必要です。

`executable-style.yaml`の`typography.family`には、実行環境で利用できるCJKフォントを指定してください。一般公開前には、Noto Sans JPなど再配布可能なフォントについて、ライセンスとランタイムへの登録方法を確認したうえで同梱または依存関係として定義する予定です。

## 機密情報の扱い

社内テンプレート、ロゴ、機密資料を公開プラグインへ含めないでください。これらは会社が許可したワークスペース、または会社専用の非公開プラグインで管理します。利用者が入力した内容には、サインイン先のChatGPTワークスペースに設定されたデータ処理方針が適用されます。

## 現在の位置づけ

このバージョンは、基本レイアウト、YAML検証、PPTX生成、プレビュー、構造検査までを確認するMVPです。一般公開前には、日本語フォント対応、実際の参考画像を使ったスタイル再現テスト、会社向け非公開配布の検証を行います。
