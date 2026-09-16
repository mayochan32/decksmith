# DeckSmithスタイルシステム

DeckSmithの標準スタイルは、参考記事と同じ考え方で「全体デザイン設定」と「レイアウトバリエーション」を1つの`style.yaml`に保存する。利用者は自然言語、参考画像、既存スライド、またはYAMLで指定できる。

## 公開スタイルYAML

```yaml
Style: スタイル名
Overall Design Settings:
  Tone: 全体の印象と伝えたい感情
  Key Visual:
    Motif: 中心となる視覚モチーフ
    Decoration: 装飾の使い方
  Color Palette:
    Background: "#RRGGBB (説明)"
    Surface: "#RRGGBB (説明)"
    Main Text: "#RRGGBB (説明)"
    Accent: "#RRGGBB (説明)"
  Photography Style:
    - 被写体、光、構図、余白、避ける表現
  Typography:
    Display Heading: 見出しの分類、太さ、大小差、大文字の扱い
    Body: 本文の分類、行間、密度
  Common Layout Rules:
    Alignment: グリッドと整列
    Lines: 線、枠、区切り
    Whitespace: 余白と情報密度

Layout Variations (Catalog):
  - Type: バリエーション名
    Applies To: [cover]
    Design: 位置関係、大小差、色面、画像処理を具体的に記述

Points to Note When Applying the Design:
  - 適用時に守る可読性やブランド上の注意
```

必須項目は`Overall Design Settings`内の`Tone`、`Color Palette`、`Typography`と、1件以上の`Layout Variations (Catalog)`である。`Key Visual`、`Photography Style`、`Common Layout Rules`、適用時の注意は任意だが、参考画像から作る場合は可能な限り記録する。

`Applies To`には`cover`、`statement`、`bullets`、`split`、`image-left`、`image-right`、`full-bleed`、`closing`を指定できる。省略時は`Type`と`Design`の記述から推定する。意図しない推定を避けるため、保存用スタイルでは明示を推奨する。

## 参考資料からの作成

次の観察可能な特徴を抽出する。「美しい」「プロらしい」のような曖昧語だけに頼らない。

- スライドの縦横比と安全余白
- 基調色、補助色、文字色、アクセント色
- 書体の分類、ウェイト差、文字サイズの大小差
- 情報密度、余白、整列、グリッド
- 画像のトリミング、被写体の位置、光、彩度、質感
- 図形、線、角、影、反復要素
- 意図的に使用していない要素

複数の参考資料で特徴が一致しない場合は、反復回数と視覚的重要度を基準に優先し、推定をYAMLへ明記する。存命の作家名による模倣指示ではなく、観察可能な特徴へ言い換える。

## 内部コンパイル

`scripts/compile_spec.py`は公開スタイルYAMLを、配色、文字サイズ、余白、画像規則、装飾、レイアウトバリアントを含む内部仕様へ変換する。利用者が内部仕様を編集する必要はない。

現在認識する代表的なバリアントは次のとおり。

| バリアント | 主な記述例 | 対応レイアウト |
|---|---|---|
| `mega-title` | Mega、Massive、Magazine | cover |
| `dual-split` | Split、Comparison、Duality | split |
| `terminal-list` | Terminal、Boot Sequence | bullets |
| `divider-list` | Divider、Separated | bullets |
| `impact-statement` | Statement、Quote、Big Number | statement |
| `editorial-image` | Editorial、Portrait、Cutout | image-left／image-right |
| `full-bleed` | Full Bleed、Gallery | full-bleed |

従来の`creative-style.yaml`と`executable-style.yaml`は互換入力として残すが、新しいプロジェクトでは使用しない。
