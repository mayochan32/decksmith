# 文字と図形のバランス適用例

参照された二つの図のラベルを保持し、各2案を編集可能な文字・図形で作成する。交差を残した調整／領域と共通基盤を上下に分ける配置、カプセルの調整／コンパクトな角丸パネルの4ページ。参照画像は配布物に含めない。座標はこの作例専用で、本体のレイアウト選択には使わない。

```bash
python3 benchmarks/layout-balance-pilot/prepare_pilot.py --output-root /tmp/layout-balance-pilot
python3 skills/decksmith/scripts/create_deck.py \
  --scene /tmp/layout-balance-pilot/setting/scene.yaml \
  --style /tmp/layout-balance-pilot/setting/style.yaml \
  --structure /tmp/layout-balance-pilot/setting/structure.yaml \
  --config /tmp/layout-balance-pilot/setting/decksmith.resolved.yaml
```

MacのHiragino SansとLibreOfficeを利用。再実行先の書体と描画ツールを確認する。必要ならDECKSMITH_SOFFICE、DECKSMITH_NODE_MODULESでローカル依存を指定する。配布物の検証には--skill-directoryで同梱Skillを指定できる。通信・素材取得は不要。入力生成は新規フォルダー限定。スクリプトは視覚合格を作らない。

画像だけから元のPPTXの寸法や文字サイズを断定しない。四領域と三共通基盤という意味は作例上の仮定。旧版と新版を独立生成したA/Bでもなく、品質向上の実証でもない。測定は宣言した範囲と座標の整合性、字面は実画像で別に確認する。

[結果と制約](../../docs/research/layout-balance-results.md)
