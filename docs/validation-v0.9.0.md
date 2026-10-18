# v0.9.0 配布検証 — 2026-10-06

## 結果

| 対象 | 結果 |
| --- | --- |
| 自動テスト | 110件中108件成功、2件スキップ |
| スキルの形式検証・版番号の一致 | 成功 |
| 通常版・Claudeスキル試験版・ChatGPTプラグイン試験版ZIP | 作成済み。生成エンジン・参照ファイル・登録情報の同梱を検査 |
| 別の場所へ展開した配布物だけでの生成 | MacでPPTX・PDF・3枚のPNGを生成。元の開発素材は使用しない |
| 編集可能な本文・図形・ページ寸法・原稿保持 | 構造検査に成功 |
| 日本語を含む3枚の実画像の確認 | Hiragino Sans指定・LibreOffice描画で、内容・文字の切れ・配色を確認 |
| review.jsonと納品物の一致 | review_deck.pyでpassed |
| Claude Code／Codex／ChatGPTデスクトップの実画面からのプラグイン導入 | 未実施。登録情報と配布物の検査とは区別する |
| Claude／ChatGPTのブラウザー版 | 未実施。正式対応には含めない |

スキップはWindows実機の環境変数回帰テストと、別途生成したWindows PORTABLE ZIPの検査。Windows版PowerPointのCOM書き出しもMacの検証対象ではない。

ブラウザー制御の初期化でエラーが発生し、Claudeへのアクセスは管理ポリシーの確認機能が利用できず拒否された。制限を迂回して試験は行っていない。この結果はDeckSmithのブラウザー非互換を意味せず、実行可否は未判定。試験用ZIPと診断・生成テストを残す。

## 検証成果物

ローカルの `artifacts/plugin-release-check-20261006/` に以下を保存した。生成物はリポジトリの同梱対象外。

- 3枚のテストPPTX：`output/decksmith-smoke.pptx`
- PDF：`output/decksmith-smoke.pdf`
- 視覚レビュー記録：`output/decksmith-smoke.preview/review.json`
- 試験範囲の記録：`verification-summary.json`

固定の実行テストは任意のスタイル解釈・画像生成の評価ではない。クラウドMCP・ホスティング・公開申請・GitHub公開は行っていない。

## ガイド更新時の再確認 — 2026-10-10

READMEとUSER_GUIDEの導入方法・依頼例・更新手順を揃えた後、通常の自動テストを再実行し、110件中106件成功、4件スキップ。描画環境を使う2件は今回の実行では有効にせず、Windows実機とPORTABLE ZIP検査も対象外。10月6日の描画・視覚確認結果とは区別する。

版番号はv0.9.0で一致し、通常版へ同梱するガイドの相対ファイルリンクも検査した。今回のpushはソースの反映であり、GitHub Releasesへの配布ZIP公開は別途行う。

## リリース用最終確認 — 2026-10-12

内容に応じた構図・バランス・画像の重ね方と、ページ別Markdown説明の納品手順をmainへ統合した版を対象とした。通常版とWindows PORTABLE版を新しく作成し、両方のZIPに共通Skillと説明資料ガイドが含まれることを確認した。

- 全119件中118件成功、Windows実機の環境変数回帰テスト1件は未実施。描画テストと生成したPORTABLE ZIP検査を有効化して実行した。
- PORTABLEのPython／Node.jsはruntime-lock.jsonのSHA-256と一致。npm依存は既存キャッシュからオフラインで導入した。
- 通常版の配布物単独での生成、LibreOfficeのPDF・PNG出力、PORTABLE内の実行ファイルの形式・パス設定・同梱JavaScriptのホストNodeによる読込を検査。Windowsバイナリの実行確認とは区別する。
- 両ZIPの全共通Skillファイルと利用ガイドをソースにバイト単位で照合。版番号v0.9.0を確認し、試作画像・PPTX・ローカル作業物が含まれていないことを確認した。
- 今回の公開用ファイルは `dist/release-v0.9.0-20261012/` に保存。10月6日に作った通常版・ブラウザー試験用ZIPとは別物。

| 公開用ファイル | SHA-256 |
| --- | --- |
| decksmith-v0.9.0.zip | 7974094598bc4158480873dc88a1f2b24df212ce6455e714ece5805e78ba3aaa |
| decksmith-v0.9.0-portable-win-x64.zip | ceea7792cac638d77909fdd756cc7c6e73c052b14c62040fb9da8bf3893150c1 |

Windows実機・PowerPointでの確認、各クライアント画面からの導入、ブラウザー実行は引き続き未実施。

## 制作開始用設定の同梱 — 2026-10-18

通常版とWindows PORTABLE版のZIP直下にsetting/decksmith.yamlを追加。通常版は共通雛形と一致、PORTABLE版はrendererのみpowerpointへ変更した。出力先../output、原稿・スタイルのnullを維持したことを確認。既存のtemplates/decksmith.yamlも保持。

全119件中118件成功、Windows実機専用の1件は未実施。実際に作成したPORTABLE ZIPの設定・同梱JavaScriptを検査し、両ZIPの共通Skillとガイドを現在のソースと照合した。

更新用ファイルはdist/release-v0.9.0-settings-20261018/へ保存。公開済みタグは移動せず、v0.9.0の添付ZIPとチェックサムを更新する。以前のZIPはローカルに保持している。

| 更新用ファイル | SHA-256 |
| --- | --- |
| decksmith-v0.9.0.zip | 574f542045a38d577615591f870c2ed91e2678e16bd74d68df775e891d69b662 |
| decksmith-v0.9.0-portable-win-x64.zip | 2c0725375e111f1dd799017178d1454d37c246d8d39b9469a3e87426ba1b0c55 |
