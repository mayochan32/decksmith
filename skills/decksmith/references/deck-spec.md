# 入力とシーン仕様 1.0

style.yamlは利用者の任意のYAMLマッピング。キー名も言語も制限しない。内容はAIが解釈する。

structure.yaml:
```yaml
slides:
  - id: opening
    purpose: 問いを示す
    required_text: ["伝えたい問い", "必ず残す説明"]
    notes: 根拠や補足
    citations: []
```
required_textは連続する文字列単位。改行や空白の追加は可能。数値・重要ラベルの欠落を避けるため元の内容を適切な単位で記録する。

scene.yaml:
```yaml
schema_version: "1.0"
style_sha256: <style.yamlのバイト列のSHA-256>
structure_sha256: <structure.yamlのバイト列のSHA-256>
canvas: {width: 1280, height: 720}
requirements:
  - source: /配色/主役
    interpretation: 見出しを指定された朱色で描く
    status: implemented
    targets: [opening/title]
slides:
  - id: opening
    background: "#F2F0E9"
    elements:
      - id: title
        type: text
        x: 60
        y: 80
        width: 1100
        height: 200
        text: 伝えたい問い
        font: <実環境で確認した書体>
        size: 72
        color: "#C92C1C"
        bold: true
```

すべての座標とサイズは96DPIのpx。キャンバスを固定しない。elementsの順番が背面から前面への重なり順。全要素の共通項目はid/type/x/y/width/height。任意でrotation（度）、overflow_reason（意図的なはみ出しの説明）。

- text: textまたはrunsの片方。font/size/colorが必須。bold/italic/align（left/center/right/justify）/vertical（top/middle/bottom）/line_spacingが任意。runsは{text, font?, size?, color?, bold?, italic?}の配列で、部分強調と書体の混在を表す。自動縮小しない。
- shape: geometryはrect/roundRect/ellipse/line/triangle/rightArrow。fill/strokeは#RRGGBB、#RRGGBBAAまたはnone。stroke_width/radiusはpx。水平線は高さを小さい正数にする。
- path: pointsは要素のローカル座標の[x,y]配列。closed、fill、stroke、stroke_widthが任意。正確な関係線・編集可能な図解のための機能。
- image: scene.yamlのディレクトリ内の相対path、altが必須。PNG/JPEG。WebP等は事前にPNGへ変換する。fitはcontain（既定）またはcover。promptを記録可能。回転は共通のrotationを使う。

未知のキー/要素はエラー。表やグラフの専用要素、クリッピングマスク、グループ変換はこの初期アダプターでは未実装。要求された場合は対応を追加する。黙って無視しない。グループ相当の配置は各要素の明示座標で表現できる。

requirementsはstyle.yamlのすべての末端値を重複なく網羅する。not_applicableの場合はreasonを記録し、AIが妥当性を確認する。ソース指紋と台帳は追跡可能性のためであり、AIによる意味理解の正しさを自動保証しない。

以前のlayout/compositionによる形式は廃止した。旧資料を作り直す場合は元の題材・YAMLを読んで新しいstructureとsceneを設計する。
