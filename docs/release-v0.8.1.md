# DeckSmith v0.8.1

## 配布物を2種類に統一

- **decksmith-v0.8.1.zip**：通常版。Codex・Claude Code・GitHub Copilot・Gemini CLI向け資材をすべて同梱します。
- **decksmith-v0.8.1-portable-win-x64.zip**：Windows x64用PORTABLE版。共通Skillに加えてPython・Node.js・描画ライブラリを同梱します。

AIツール別のZIPは廃止しました。通常版の生成エンジン・Skillは共通で、各AIツールの登録情報を同梱しています。利用しないAIツールの準備は不要です。ファイル確認用のSHA256SUMS.txtも添付します。

## GitHub Copilot対応

VS CodeのAgentモードを利用対象に追加しました。通常版はsetup_workspace.py --host copilotで.github/skills/decksmith/へ配置できます。既存設定は上書きしません。PORTABLE版は展開先のSKILL.mdとdecksmith.cmdを直接指定します。

Gemini CLIはターミナルでの実行を想定して引き続き提供しますが、導入から制作までの実利用は未検証です。ブラウザー版GeminiやGemini Code Assist向けではありません。

## 更新方法と検証範囲

展開先のUSER_GUIDE.mdを参照してください。既存の原稿・設定・生成結果は保持し、SkillまたはPORTABLE一式を更新します。設定項目・PPTX生成処理はv0.8.0と共通です。

通常版の全登録情報の同梱、Codex・Claude・Copilotへの配置、既存ファイルの保護、配布内リンク、Windows同梱資材、共通エンジンによるPPTX・PDF・PNG生成を自動テストで確認しています。最終ZIPのWindows実機・各AI拡張での一連の再検証は未実施です。
