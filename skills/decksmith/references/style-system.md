# DeckSmithスタイルシステム

DeckSmithは、視覚的な意図と、PowerPointで実行できる規則を分離する。利用者は自然言語または参考画像でスタイルを指定し、エージェントがYAMLを作成する。

## クリエイティブスタイル

`creative-style.yaml`には、資料から受ける印象や世界観を記録する。描画エンジンが変わっても再利用できる内容にする。

```yaml
name: quiet-editorial
intent: 落ち着きと信頼感があり、余白を広く使う
keywords:
  - エディトリアル
  - 控えめ
  - 人間味
palette_direction: 温かみのある白、チャコール、寒色系のアクセント1色
imagery:
  medium: エディトリアル写真
  lighting: 柔らかな方向性のある自然光
  composition: 非対称で、十分なネガティブスペースを確保
  people: 自然な瞬間を捉えた人物表現
  avoid:
    - 画像内の文字
    - ロゴ
    - 光沢感の強い作り込まれたストック写真
texture: 控えめな紙の質感
motion: なし
```

観察可能な特徴として記述する。「美しい」「プロらしい」のような曖昧な表現だけに頼らず、構図、光、色、質感、被写体の扱いを具体化する。

## 実行可能スタイル

`executable-style.yaml`は、クリエイティブスタイルを決定的なレイアウト値へ変換する。座標とフォントサイズの単位には、96 DPIのCSSピクセルを使用する。

```yaml
name: quiet-editorial-16x9
canvas:
  width: 1280
  height: 720
colors:
  background: "#F7F4EE"
  surface: "#ECE7DD"
  text: "#1C232B"
  muted: "#66717D"
  accent: "#315CFF"
  on_accent: "#FFFFFF"
typography:
  family: null
  title: 58
  heading: 38
  body: 24
  small: 16
  line_spacing: 1.08
spacing:
  margin_x: 76
  margin_y: 56
  gutter: 36
  title_gap: 28
image:
  corner_radius: 20
  fit: cover
  generated_limit: 6
decoration:
  page_numbers: true
  accent_bar: true
```

`family: null`を指定すると、ランタイムがインストール済みフォントから選択する。テンプレートまたは利用者の指定で必要な場合だけ、フォント名を明示する。

日本語の業務資料では游ゴシックやNoto Sans JPが候補になるが、強制する前に実行環境で利用できることを確認する。

## 参考資料の分析項目

参考画像または既存スライドから、次の特徴を抽出する。

- スライドの縦横比と安全余白
- 基調色、補助色、文字色、アクセント色
- 書体の分類、ウェイトの差、概算の文字サイズ
- 情報密度、余白、整列、グリッド
- 画像のトリミング、被写体の位置、光、彩度、質感
- 図形の形状、線の太さ、角の処理、影
- ページ番号やフッターなどの反復要素
- 意図的に使用していないと考えられる要素

複数の参考資料で特徴が一致しない場合は、最も多く繰り返される特徴を優先し、推定した判断を`creative-style.yaml`へ記録する。
