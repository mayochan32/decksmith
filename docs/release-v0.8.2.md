# DeckSmith v0.8.2

## Windows実行環境の修正

子プロセスへ渡す環境変数が制限された環境で、SystemRootやWINDIRの欠落によりNode.js・PowerShellの起動に失敗する問題に対応しました。

- 通常版・Windows PORTABLE版共通で、不足または空のSystemRoot・WINDIRをWindows APIから補完します。補完はDeckSmithが起動する子プロセス限定です。
- OSの場所をCドライブに固定しません。取得失敗や既存値との矛盾は明確なエラーで停止し、既存値を自動上書きしません。
- 診断に補完対象・取得元を追加。プロセス起動失敗と起動後の異常終了を区別し、終了コードを表示します。
- DECKSMITH_WINDOWS_ENV_REPAIR=0で補完を禁止できます。Codex等の全体設定、権限、サンドボックス、実行ポリシーは変更しません。
- USER_GUIDE・PORTABLE_GUIDEに原因の切り分けと対処を追記しました。

DeckSmith起動前に親シェルやPython自体が起動できない場合は対象外です。環境変数の除外理由は自動判定できないため、組織が補完を禁止している場合は管理者に確認してください。

## 配布物

- decksmith-v0.8.2.zip：全対応AI環境共通の通常版
- decksmith-v0.8.2-portable-win-x64.zip：Windows x64用ランタイム同梱版
- SHA256SUMS.txt：配布ZIPの確認用ハッシュ

既存の原稿・設定・生成結果を保持し、通常版のSkillまたはPORTABLE一式を更新してください。Gemini CLIでの実利用は引き続き未検証です。

## 検証

自動テスト101件成功、Windows実機専用の1件は未実行。環境変数欠落・既存値・補完禁止・Windows API応答のモック検査、配布ZIPの内容、MacでのPPTX・PDF・PNG生成を確認しています。最終ZIPのWindows実機での起動・PowerPoint連携は未検証です。
