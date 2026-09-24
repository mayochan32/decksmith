# DeckSmith v0.6.0

## プレビュー・PDFの作成方式を選択可能に

LibreOfficeとPopplerが導入できない環境向けに、output.rendererを追加しました。PPTX本体の生成方法は変わりません。

| 値 | 対象 | 動作 |
| --- | --- | --- |
| libreoffice（既定） | Windows／Mac | 従来のLibreOffice＋Popplerでプレビュー・任意のPDFを作成 |
| powerpoint | Windowsネイティブ環境のみ | デスクトップ版PowerPointでPNG・任意のPDFを作成。LibreOffice・Poppler不要 |
| none | Windows／Mac | PPTXのみ生成。変換ソフト不要、見た目は未確認 |

```yaml
output:
  renderer: powerpoint
  pdf: true
```

PPTXのみの場合はrenderer: none、pdf: falseを指定します。Python・Node.jsと描画ライブラリは引き続き必要です。既存の--pptx-onlyも使えます。

## その他の変更

- 環境確認を方式別に変更。doctor.py --config、--rendererに対応。
- noneでも構造検査を実行し、not_visually_reviewedとして記録。プレビュー画像は生成しません。
- noneとpdf: trueはエラー。失敗時に別方式へ自動で切り替えません。
- 利用ガイドと制作Skillの手順を更新。

## Windows PowerPoint方式の注意点

Windows PowerShellとデスクトップ版PowerPointを使用します。Mac・WSL・リモート/サービス環境でのPowerPoint操作は対象外です。

利用者の資料保護のため、PowerPointが起動中なら処理を止めます。資料を保存して終了した後に実行し、変換中はPowerPointを操作しないでください。アプリ全体の強制終了は行わないため、処理後やタイムアウト後にPowerPointが残った場合は手動で確認・終了してください。組織の実行ポリシーを変更・迂回する処理はありません。

**Windows PowerPointによる実機検証は未完了です。** COM登録の確認は実際の書き出し成功を保証しません。Windows環境での受入確認をお願いします。

## 配布と検証

Assetsのdecksmith-v0.6.0-codex.zip、decksmith-v0.6.0-claude.zip、decksmith-v0.6.0-gemini.zipから利用環境に合うものを取得してください。既存Skillは探索対象の外にバックアップし、同梱USER_GUIDE.mdに沿って新版を配置してください。VERSIONと--versionでv0.6.0を確認できます。

自動テスト47件成功。ローカルのPPTXのみ生成、従来のLibreOfficeによるPDF・画像変換を確認済みです。PowerPointアダプターのテストは模擬応答によるもので、Windows実機試験ではありません。VS Code各拡張・Gemini CLIや別OSでの一連の制作も未検証です。
