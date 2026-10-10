# 内容を伝える設計の適用例

架空の問い合わせ運用案を、同じ表示文のまま2種類の日本語スタイルで設計する。各4ページ：図解を使わない主張、同条件の比較、条件付き差し戻し、6つの独立条件。原稿・図形はこの試作のために作成したもの。

これは新ガイドを読んだAIが設計した**適用例**。旧版との独立生成A/Bや品質向上率の測定ではない。スタイルと内容から実際に設計した座標を再生成するための開発用コードであり、DeckSmithのレイアウトプリセットには組み込まれない。

```bash
python3 benchmarks/communication-design-pilot/prepare_pilot.py --output-root /tmp/communication-design-pilot
# output-rootは新規フォルダー。出力される2つの制作フォルダーで、それぞれ：
python3 skills/decksmith/scripts/create_deck.py \
  --scene /tmp/communication-design-pilot/paper/setting/scene.yaml \
  --style /tmp/communication-design-pilot/paper/setting/style.yaml \
  --structure /tmp/communication-design-pilot/paper/setting/structure.yaml \
  --config /tmp/communication-design-pilot/paper/setting/decksmith.resolved.yaml
```

同じコマンドのpaperをnightに変えてもう一方を生成する。通常版の配布確認では`--skill-directory <展開先>/skills/decksmith`を指定できる。明朝・ゴシックはMac上のHiraginoを用いるため、別OSではフォントを確認し、代替を記録した新たな試作が必要。

通信はrestricted、画像はnone/provided_only。素材取得や画像生成は不要。LibreOfficeでPPTX→PDF→全ページPNGを生成する。完成後は人間またはAIが実際にPNGを読み、独立した原稿と比較してreview.jsonを記録する。スクリプトは視覚レビューの合格を作らない。

本番の比較手順とマージ条件は[比較検証](../../docs/research/design-evaluation.md)。今回の確認結果は[検証記録](../../docs/research/design-pilot-results.md)。
