# 行間と情報のまとまりの適用例

利用者提供の1枚の参照画像について、文章を保持して編集可能な文字・図形で再構成する。元PPTXと正確な書体・寸法は未提供。旧版との独立生成A/Bや完全再現ではない。

```bash
python3 benchmarks/text-cohesion-pilot/prepare_pilot.py --output-root /tmp/text-cohesion-pilot
python3 skills/decksmith/scripts/create_deck.py \
  --scene /tmp/text-cohesion-pilot/setting/scene.yaml \
  --style /tmp/text-cohesion-pilot/setting/style.yaml \
  --structure /tmp/text-cohesion-pilot/setting/structure.yaml \
  --config /tmp/text-cohesion-pilot/setting/decksmith.resolved.yaml
```

MacのHiragino Sans、LibreOffice、Popplerを使用。必要に応じてDECKSMITH_SOFFICEとDECKSMITH_NODE_MODULESで既存のローカル依存を指定する。新規出力先を使い、書体と全PNGを確認してからレビューを記録する。スクリプトは合格を作らない。座標は作例専用であり、本体のレイアウトプリセットではない。

2026-10-11の成果物は `artifacts/text-cohesion-reviewed-20261011/output/`。`comparison.html`、`partnership.pptx`、`partnership.pdf` とプレビュー・レビュー記録。参照画像と生成物はコミット・配布しない。

大見出しを単一の3行文字枠にし、ラベルを説明の隣へ離す。下部ラベルと本文の上端を揃え、説明文の改行を意味の区切りに調整。描画でバッジの折返しが見つかったため、文字縮小ではなく幅を広げて修正した。最終PNGで全11文字要素、文字の切れ、余白を確認し、成果物一致検証に合格。補助ラベル3件の小さい文字の警告は、実画像で1行の判読性と階層を確認して解決。

PPTX SHA-256：`20affbdffdf42b3711c67c46c5225b0a14224a3d9f0631e0d1cdbd085b8f77b8`。

本体への反映は[設計指針](../../skills/decksmith/references/layout-balance.md)と、design-plan・quality-gatesからの参照。行間、情報群の内外の距離、字面とラベルの接触を視覚確認する。字面の自動計測・自動修正機能は追加していない。生成ロジックの変更はないためコードテストの追加・全件再実行は行わず、実生成・描画・視覚確認・レビュー整合性・Skill検証を実施した。
