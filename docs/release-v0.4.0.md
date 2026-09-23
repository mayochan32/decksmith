# DeckSmith v0.4.0

任意のスタイルYAMLから編集可能なPowerPointを制作するDeckSmithの初回GitHub Releaseです。

## 主な機能

- スタイルプリセットに依存しない、AIによるページ設計。
- Codex／Claude Code／Gemini CLI向けの配布構成。
- 任意のdecksmith.yamlによる11項目の制作設定。
- 既定1920×1080・16:9、サイズ指定の優先適用。
- 日本語・englishなどの言語名による指定。
- 提供画像の利用方針と、外部サービス制限モード。
- 編集可能なPPTX、プレビュー、任意のPDF出力。
- 配布物のVERSION、実行時表示、--versionによる版確認。

## 入手と導入

Assetsのdecksmith-v0.4.0-codex.zip、decksmith-v0.4.0-claude.zip、decksmith-v0.4.0-gemini.zipから利用環境に合うものを取得してください。ZIPには依存ライブラリ本体や生成サンプルは含みません。

VS CodeのCodex／Claude Code拡張では、展開したdecksmithフォルダー内のUSER_GUIDE.mdに従い、同梱の登録スクリプトでSkillを配置してください。Gemini CLIでの導入・制作は未検証です。

既存のSkillは自動上書きしません。更新前に探索対象の外へバックアップし、新版を配置してください。Python 3.9以上、Node.js 18以上とnpm、プレビュー用のLibreOffice・Poppler、使用フォントが必要です。

## 確認範囲と注意点

- 自動テスト36件成功。PPTX生成、設定・バージョン検査、移動した配布物からの実行を確認。
- PDFとプレビューの変換はローカルで確認済み。
- VS Code両拡張・Gemini CLIでの一連の制作、Windows／Linuxでの実機試験は未完了。
- restrictedは利用中のAIサービスの組み込み機能とローカル処理のみを使う操作ルールです。ネットワーク遮断機構ではありません。
- 専用のネイティブ表・グラフ要素、複雑なマスク、文字輪郭の液状ワープは未対応。
- macOSでLibreOfficeが検出されない場合の設定方法は利用ガイドを参照してください。
