# DeckSmithプロジェクトファイル仕様

利用者は自然言語で入力する。DeckSmithは、再現と検証ができるように内容を4つのYAMLファイルへ変換する。

## `topic.yaml`

```yaml
title: 必須の資料タイトル
audience: 必須の対象者説明
objective: 必須の意思決定または学習目標
language: ja-JP
output_filename: deck.pptx
facts:
  - claim: 任意の事実情報
    source: https://example.com/source
constraints:
  - 任意の内容上の制約
```

## `structure.yaml`

MVPでは、`cover`、`statement`、`bullets`、`split`、`image-left`、`image-right`、`full-bleed`、`closing`のレイアウトを使用できる。

```yaml
slides:
  - id: cover
    layout: cover
    title: 必須のタイトル
    subtitle: 任意のサブタイトル
    notes: 任意の発表者ノート
    citations: []

  - id: problem
    layout: image-right
    title: 必須のタイトル
    body: 任意の本文
    bullets:
      - 任意の箇条書き
    image:
      path: assets/problem.png
      alt: アクセシビリティ用の画像説明
      fit: cover
      prompt: 再現用に保存する画像生成プロンプト
    citations:
      - https://example.com/source

  - id: comparison
    layout: split
    title: 必須のタイトル
    left:
      heading: 現状
      items:
        - 1つ目の要点
    right:
      heading: 提案後
      items:
        - 1つ目の要点
```

各スライドには、一意で変化しない`id`、対応レイアウト、`title`が必要である。相対パスで指定した画像は、`structure.yaml`が置かれているディレクトリを基準に解決する。

## スタイルファイル

[スタイルシステム](style-system.md)に従う。`creative-style.yaml`にはデザイン上の意図を保存し、`executable-style.yaml`には描画に必要な具体的な値を保存する。

## 生成される正規化済み仕様

`scripts/create_deck.py`は4つのYAMLを検証して統合し、非公開のビルドディレクトリへ正規化済みJSONを生成する。JavaScript製ビルダーは、そのJSONだけを入力として使用する。

画像ファイルが存在しない場合、最終生成は失敗する。未生成画像を含む下書きが必要な場合だけ、`--allow-missing-images`を明示的に指定する。
