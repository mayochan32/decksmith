# 軸見出しと成果の強弱の適用例

利用者提供の参照画像を編集可能な文字・図形へ再構成する。元PPTX・元フォントは未提供。旧版との独立生成A/Bや完全再現ではない。

```bash
python3 benchmarks/matrix-hierarchy-pilot/prepare_pilot.py --output-root /tmp/matrix-hierarchy-pilot
python3 skills/decksmith/scripts/create_deck.py \
  --scene /tmp/matrix-hierarchy-pilot/setting/scene.yaml \
  --style /tmp/matrix-hierarchy-pilot/setting/style.yaml \
  --structure /tmp/matrix-hierarchy-pilot/setting/structure.yaml \
  --config /tmp/matrix-hierarchy-pilot/setting/decksmith.resolved.yaml
```

MacのHiragino Sans W9/Hiragino SansとLibreOffice、Popplerを利用する。必要ならDECKSMITH_SOFFICEとDECKSMITH_NODE_MODULESでローカル依存を指定。新規出力先を使い、再実行時の書体・字面を確認する。スクリプトは視覚合格を作らない。座標は作例専用であり、本体のレイアウトプリセットではない。

## 変更と参照画像からの解釈

- 軸名の専用領域を行見出しの上へ用意し、水平表示する。隠れた原文は読めないため、本文の用語で「3つの横断ケイパビリティ」と補う。
- 主張52px・W9、成果32px、項目名・説明25px、補助見出し22〜26pxとし、主張と成果へ視線を向ける。この数値は作例固有で、全資料の既定値ではない。
- OUTCOMESの分類名を上、2成果を横並びの大きな文字にする。文字と内側の余白から枠の高さを設計する。
- 4列×3行と12個の丸の赤黒配置を保持。丸の色の意味は創作しない。
- 左の従来SI→Uvanceは、表題にある変化を表す下向き矢印へ整理。画像右上で途中までしか見えない装飾ヘッダーは再現対象外。その他の見える主要文言は保持する。

## 確認結果（2026-10-11）

全1PNGを確認し、軸名の全文、成果の大きさと余白、主張の強さ、20文字要素と4列×3行の内容を照合。PDFのHiraginoSans-W9埋込みを確認。補助見出し4件の小さい文字の警告は、実画像の判読性と階層を確認して解決した。成果物一致・レビュー整合性検証とSkill検証に合格。PowerPointアプリ上の表示は未確認で、編集先では指定フォントが必要。

成果物：`artifacts/matrix-hierarchy-20261011/output/` の `comparison.html`、`uvance.pptx`、`uvance.pdf` とPNG・レビュー記録。参照画像と出力はコミット・配布しない。

PPTX SHA-256：`8a03ce59c3bd0c0306631aac5acde30ad7a53b3386b49b3aeff1e1db146bc28a`。

本体への反映は[設計指針](../../skills/decksmith/references/layout-balance.md)とdesign-plan・quality-gatesの参照。軸名の専用領域、成果枠と文字の釣り合い、内容の役割別の強弱を設計・視覚確認で扱う。図形の重なりの一律禁止や字面の自動検出は追加していない。生成ロジックの変更はないためコードテストを追加・全件再実行せず、実生成・描画・視覚確認・レビュー整合性を検証した。
