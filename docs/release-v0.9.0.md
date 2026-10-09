# DeckSmith v0.9.0

ローカル版を主軸に、Claude Code／Codex／ChatGPTデスクトップ向けのプラグイン配布を整備しました。生成エンジンと制作手順は共通のままです。

- ルートplugin.jsonにAgent Plugins形式を追加し、既存のClaude・Codex互換manifestも維持。
- Claude CodeとCodex向けのローカルmarketplaceを同梱。既存の作業フォルダーへのSkill登録も利用可能。
- 通常版ZIPを生成する--zipと、ブラウザー試験用ZIPを生成する--browser-trialを追加。
- 通信・追加インストールを行わずに3枚のPPTX・PDF・PNGを検証できるsmoke_test.pyを追加。視覚判断はAIまたは人間が別途行う。
- ブラウザー試験の判定・停止条件を追加。正式なブラウザー対応ではなく、クラウドMCPやホスティングは追加していない。

各クライアントでの登録・ブラウザー実行・Windows PowerPointの実機確認は、ローカル生成の検証とは別に扱います。配布物の作成は公開済みリリースを意味しません。

検証結果は[配布検証](validation-v0.9.0.md)を参照。Macでの配布物単独生成、3枚の日本語プレビュー、レビュー整合性を確認しました。自動テスト110件中108件成功、Windows実機とPORTABLE ZIP検査の2件は未実施です。
