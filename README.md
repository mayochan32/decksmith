# DeckSmith

DeckSmithは、「題材」「構成」「スタイル」を個別に指定し、編集可能なPowerPointファイルを生成するChatGPT／Codex向けプラグインです。

スタイルは、[指定方式の参考記事](https://qiita.com/mayochan32/items/18323a3f5201d08e8afc)と同じ考え方で、全体設定とレイアウトカタログを1つのYAMLに記述します。推論と画像生成には、サインイン中のChatGPT／Codexワークスペースの機能を使うため、APIキーやローカルGPUは必要ありません。

## できること

- 題材・構成・スタイルを対話形式で個別に指定
- 記事形式の詳細なスタイルYAMLを保存し、別の資料へ再利用
- 参考画像から同じ形式のスタイルYAMLを作成
- Codex内蔵の画像生成を利用
- YAMLから再現性のあるPPTXを生成
- 文字や情報を表すオブジェクトを編集可能な状態で保持
- PPTXの構造検査と、全スライドのPNGプレビュー生成
- GitHub経由で社内配布・一般公開へ拡張

## 3つの入力

1. **題材**：何を、誰に、何のために伝えるか
2. **構成**：スライド数、話の順序、各スライドの役割
3. **スタイル**：トーン、キービジュアル、配色、写真、書体、共通ルール、レイアウトバリエーション

標準のプロジェクトファイルは`topic.yaml`、`structure.yaml`、`style.yaml`の3つです。`style.yaml`は人が読んで再利用できる仕様書であり、DeckSmithがPPTX生成用の数値と規則へ自動変換します。

## ChatGPT／Codexでの使い方

通常は自然言語で依頼するだけです。Presentationsの保存場所やAPIキーを入力する必要はありません。

```text
DeckSmithでPowerPointを作って。
題材：生成AI導入の社内提案
構成：課題、解決策、導入計画、費用対効果
スタイル：添付した参考画像を分析し、記事形式のスタイルYAMLとして保存して使う
```

スタイルYAMLを直接指定する場合は、次の大項目を含めます。完全な例は[`article-style.yaml`](skills/decksmith/assets/examples/article-style.yaml)を参照してください。

```yaml
Style: Electric Blueprint
Overall Design Settings:
  Tone: "知的で未来的。高いコントラストで整理して見せる。"
  Key Visual:
    Motif: "暗い設計図面に発光する情報レイヤーを重ねる。"
  Color Palette:
    Background: "#0B1020 (Deep Navy)"
    Main Text: "#F4F7FF (Soft White)"
    Accent: "#52E5FF (Electric Cyan)"
  Photography Style:
    - "暗い背景に被写体を明瞭に配置する。"
  Typography:
    Display Heading: "Massive condensed sans-serif."
    Body: "Clean sans-serif."
  Common Layout Rules:
    Lines: "Use thin cyan frame lines."

Layout Variations (Catalog):
  - Type: "Mega Title Cover"
    Applies To: [cover]
    Design: "A massive title occupies most of the canvas."
```

## 開発者向け：付属サンプルの実行

Codexのプレゼンテーション用ランタイムが利用できる環境で、`skills/decksmith`から実行します。

```bash
"${RUNTIME_PYTHON:-${CODEX_PRIMARY_RUNTIME_PYTHON:-python3}}" scripts/create_deck.py \
  --topic assets/examples/topic.yaml \
  --structure assets/examples/structure.yaml \
  --style assets/examples/article-style.yaml \
  --output output/decksmith-mvp.pptx
```

PPTXと、目視確認用の`.preview`ディレクトリが生成されます。既存の出力ファイルは上書きしません。

Presentationsの場所とCodexランタイムは自動検出します。特殊な開発環境で自動検出できない場合に限り、`DECKSMITH_PRESENTATIONS_SKILL_DIR`環境変数、または`--presentations-skill-dir`オプションで明示できます。従来の`--creative-style`と`--executable-style`の組も互換用として利用できますが、新規利用では`--style`を使用してください。

## 日本語フォントについて

日本語テキストは、編集可能な文字としてPPTXに保存されます。ただし、PNGプレビューで正確に検査するには、実行環境にCJKフォントが必要です。利用可能な日本語フォントがない環境ではPPTX内の文字は保持されますが、プレビューの日本語部分を視覚検査済みとは扱いません。

一般公開前には、Noto Sans JPなど再配布可能なフォントについて、ライセンス、ランタイムへの登録、PowerPoint側の代替表示を確認します。

## 機密情報の扱い

社内テンプレート、ロゴ、機密資料を公開リポジトリや公開プラグインへ含めないでください。会社が許可したワークスペース、または会社専用の非公開リポジトリで管理します。入力内容には、サインイン先のChatGPTワークスペースに設定されたデータ処理方針が適用されます。

## 現在の位置づけ

記事形式のスタイルYAML、基本レイアウト、PPTX生成、プレビュー、構造検査までを実装したMVPです。現時点のレイアウトカタログは、Mega Title、Dual Split、Terminal／Divider List、Impact Statement、Editorial Image、Full Bleedを解釈します。記事内の自由記述を完全に再現するものではないため、一般公開前にスタイル変換規則と日本語フォント対応を拡充します。
