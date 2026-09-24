# 配布先の実行環境

共有エンジンはPython 3.9+とNode.js 18+、PptxGenJS 4.0.1を使う。特定AIのSDKや非公開ライブラリを要求しない。標準プレビューにはLibreOfficeとPopplerのpdftoppmが必要。

1. scripts/doctor.py --config <project>/decksmith.yamlで選択方式の利用可能性を調べる。設定ファイルがなければ--rendererで明示する。引数なしはカレントフォルダーのdecksmith.yamlまたは既定方式を使う。fontsとimage_generationは別途確認。
2. Node依存が未導入なら、このSkillディレクトリで npm ci --ignore-scripts --no-audit --no-fund を実行する。ネットワークとインストールはホストの承認ルールに従う。
3. プラグインのキャッシュが読み取り専用なら、package.jsonとpackage-lock.jsonを作業用ディレクトリへコピーしてそこでnpm ciし、そのnode_modulesをDECKSMITH_NODE_MODULESに指定する。
4. 実行ファイルはPATHで検出する。必要な場合のみDECKSMITH_NODE、DECKSMITH_SOFFICE、DECKSMITH_PDFTOPPMで上書きできる。利用者に開発者の絶対パスを入力させない。
5. ホストに優先利用すべき依存ランタイムや操作記録の指示がある場合はその指示に従い、実行前に適用する。共有スクリプトからホスト専用処理は呼び出さない。
6. フォントは埋め込まれない。指定フォントの有無を確認し、代替が必要なら役割を保って記録する。LibreOfficeプレビューとPowerPoint本体の描画には差があり得る。

Codexは.codex-plugin/plugin.json、Claude Codeは.claude-plugin/plugin.json、Gemini CLIはgemini-extension.jsonを入口にする。共通のskills/decksmithを使用する。ブラウザー版のChatGPT・Claude・Geminiへの直接導入は対象外。

画像生成は[画像素材の接続契約](image-assets.md)を読む。ホストに画像生成機能があると決めつけず、提供画像・生成機能・利用者が設定した外部サービスを区別する。

output.renderer=none（または--pptx-only）はWindows/Macで変換ソフトなしにPPTXのみ生成する。見た目未確認として明示納品し、利用者による確認を依頼する。noneでもPython、Node、エンジンは必要。

powerpointはWindowsネイティブ環境のWindows PowerShell（powershell.exe）からデスクトップ版PowerPointのCOMを使用。DECKSMITH_POWERSHELLでパス指定可能。LibreOffice/Popplerや追加のPython COMライブラリは不要。Mac・WSL・リモート/サービスでの自動化は対象外。PowerShell実行ポリシーを変更・迂回しない。組織の制限で実行できなければ説明し、別方式への変更を相談する。

doctorはCOM登録だけ確認し、PowerPointを起動しない。実際の書き出し動作の保証ではない。書き出し前にPowerPointが起動中なら停止し、利用者に保存・終了を依頼する。処理中はPowerPointを手動操作しないよう案内する。生成した資料だけを読み取り専用で開いて閉じる。利用者の資料保護のためアプリ全体のQuitや強制終了は行わないので、処理後やタイムアウト後にPowerPointが残ることがある。手動確認・終了を案内し、自動でプロセスをkillしない。Windows実機での検証は別途必要。
