# DeckSmith v0.8.0

## 主な変更

- Windows x64 PORTABLE版を正式な配布方式として追加。Python・Node.js・描画ライブラリを同梱し、利用PCへの個別インストールが不要です。PowerPoint連携によるプレビュー・PDF出力、またはPPTXのみの生成に対応します。
- 任意のstyle.yamlを解釈する制作手順を改善。デザイン方針、代表ページの試作、原稿の必須内容の保護、生成後の比較・レビューを支援します。
- privacy.modeの既定値をrestrictedへ変更。開始時に通信方針・画像生成の利用可否を表示し、normalを含む全モードでWeb検索・外部サービスの利用前に人間の承認を求めます。
- 画像生成できない場合は、画像なしでの制作か、画像位置に四角と編集可能な生成プロンプトを置くかを確認します。
- 全設定項目入りdecksmith.yamlの雛形と初期化コマンドを追加。
- README・USER_GUIDE・PORTABLE_GUIDEを整理。原稿・設定・参考資料をsetting/、納品物を同列のoutput/へ分離します。

## 更新時の注意

- output.directoryの省略時と雛形の値は../outputです（設定ファイル基準）。既存のdirectory: outputは明示指定として維持されるため、新構成では../outputへ変更してください。既存資料は自動移動しません。
- 既存のprivacy.mode: normalは維持します。ただし外部アクセスの事前承認は全モードで必要です。通信方針はAIへの指示であり、OSや拡張の通信を遮断するものではありません。
- PORTABLE版はWindows x64用です。プレビュー・PDFには導入・認証済みのWindowsデスクトップ版PowerPointが必要です。LibreOffice・Popplerは不要です。
- PORTABLE版はZIP全体を展開して使用してください。通常版はPython・Node.js等の準備が引き続き必要です。

## 配布物

- decksmith-v0.8.0-codex.zip
- decksmith-v0.8.0-claude.zip
- decksmith-v0.8.0-gemini.zip
- decksmith-v0.8.0-portable-win-x64.zip
- SHA256SUMS.txt

各配布物にVERSION、利用ガイド、設定雛形を含みます。

## 検証

共通処理の自動テスト、MacでのPPTX・PDF・PNG生成、Windowsランチャーの引数・保存先解決、PORTABLE ZIPの同梱資材を検査しています。今回の最終ZIPをWindows実機で再実行したものではありません。
