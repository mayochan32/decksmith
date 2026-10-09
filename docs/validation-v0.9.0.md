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
