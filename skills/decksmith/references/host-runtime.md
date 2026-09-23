# 配布先の実行環境

共有エンジンはPython 3.9+とNode.js 18+、PptxGenJS 4.0.1を使う。特定AIのSDKや非公開ライブラリを要求しない。標準プレビューにはLibreOfficeとPopplerのpdftoppmが必要。

1. scripts/doctor.pyで利用可能性を調べる。フォントと画像生成機能はホストの利用可能ツールから別途確認する。
2. Node依存が未導入なら、このSkillディレクトリで npm ci --ignore-scripts --no-audit --no-fund を実行する。ネットワークとインストールはホストの承認ルールに従う。
3. プラグインのキャッシュが読み取り専用なら、package.jsonとpackage-lock.jsonを作業用ディレクトリへコピーしてそこでnpm ciし、そのnode_modulesをDECKSMITH_NODE_MODULESに指定する。
4. 実行ファイルはPATHで検出する。必要な場合のみDECKSMITH_NODE、DECKSMITH_SOFFICE、DECKSMITH_PDFTOPPMで上書きできる。利用者に開発者の絶対パスを入力させない。
5. ホストに優先利用すべき依存ランタイムや操作記録の指示がある場合はその指示に従い、実行前に適用する。共有スクリプトからホスト専用処理は呼び出さない。
6. フォントは埋め込まれない。指定フォントの有無を確認し、代替が必要なら役割を保って記録する。LibreOfficeプレビューとPowerPoint本体の描画には差があり得る。

Codexは.codex-plugin/plugin.json、Claude Codeは.claude-plugin/plugin.json、Gemini CLIはgemini-extension.jsonを入口にする。共通のskills/decksmithを使用する。ブラウザー版のChatGPT・Claude・Geminiへの直接導入は対象外。

画像生成は[画像素材の接続契約](image-assets.md)を読む。ホストに画像生成機能があると決めつけず、提供画像・生成機能・利用者が設定した外部サービスを区別する。

--pptx-onlyはプレビュー環境がない場合の明示的な中間出力用。視覚確認済みの完成品として扱わない。
