# 開発・配布の手順

利用者向けの機能説明はREADME.md、導入方法はUSER_GUIDE.mdを参照。

## バージョン管理

正本は `skills/decksmith/VERSION`（`vx.y.z`）。互換性を壊す変更はメジャー、互換性を保つ機能追加はマイナー、不具合修正はbugfixを上げる。メジャー更新時は下位2桁、マイナー更新時はbugfixを0へ戻す。

```bash
python3 scripts/release_version.py --check
# 次版を決めたときだけ実行（例）
python3 scripts/release_version.py --set v0.4.1
```

更新コマンドはSkill内とリポジトリ直下のVERSION、各ホストのmanifest、npmのpackage/lockを同期する。チェック時にはルートのVERSIONとの一致も検査する。JSONメタデータはvなし、利用者への表示はv付き。依存ライブラリの版は変更しない。Gitタグ・push・Release公開は自動では行わない。

## 生成処理の直接実行

AIが用意する資料はstyle.yaml（指定）、structure.yaml（内容）、scene.yaml（設計）、assets/（素材）。仕様は[シーン仕様](../skills/decksmith/references/deck-spec.md)を参照。

```bash
npm ci --prefix skills/decksmith --ignore-scripts --no-audit --no-fund
python3 skills/decksmith/scripts/doctor.py
python3 skills/decksmith/scripts/create_deck.py \
  --scene project/scene.yaml --style project/style.yaml \
  --structure project/structure.yaml --output project/output/deck.pptx
```

実行ファイルはPATHで検出する。DECKSMITH_NODE、DECKSMITH_NODE_MODULES、DECKSMITH_SOFFICE、DECKSMITH_PDFTOPPMで指定可能。詳細は[実行環境](../skills/decksmith/references/host-runtime.md)を参照。

成功終了は視覚品質の合格を意味しない。レビュー台帳は未確認状態で生成し、AIが全ページを確認して修正する。

## テストと配布

```bash
python3 -m unittest discover -s tests
# 描画環境がある場合
DECKSMITH_RENDER_TEST=1 python3 -m unittest discover -s tests
python3 scripts/package_plugin.py --host claude --output dist/claude
```

hostはcodex、claude、gemini。既存の配布フォルダーは上書きしない。版番号の不一致はエラーにし、配布ルートにVERSIONを同梱する。開発サンプル・旧エンジン・node_modulesは配布対象外。依存はロックファイルから導入する。

## Windows PowerPointの受入確認

Macでの単体テストはWindowsのCOM動作を検証しない。Windowsの対話ログイン環境でPowerPointの初期設定を済ませ、資料を保存してアプリを閉じ、PowerShellから次を実行する（このテストはPowerPointを起動する）。

```powershell
$env:DECKSMITH_RENDER_TEST = "1"
$env:DECKSMITH_POWERPOINT_TEST = "1"
python -m unittest discover -s tests -p test_render_contract.py
```

PNGの寸法・枚数、PDF生成、出力保護を検査する。さらに実資料で日本語・空白入りパス、指定フォント、複数ページの外観を確認する。起動中の既存資料がある場合の拒否と資料保持、実行ポリシーによる拒否、タイムアウト時に既存資料を終了しないことも確認する。PowerPointが残る場合は利用者が確認・終了し、テストで全プロセスを強制終了しない。

使用する公式API：[Presentations.Open](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.presentations.open)、[Slide.Export](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.slide.export)、[ExportAsFixedFormat](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.presentation.exportasfixedformat)。
