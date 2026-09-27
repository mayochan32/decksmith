# Windows PORTABLE配布物の作成

利用手順はルートの[PORTABLE_GUIDE](../PORTABLE_GUIDE.md)にあります。この文書は配布資材を作る担当者向けです。

ランチャーとランタイム固定情報はpackaging/windows/、共通Skillはskills/decksmith/を使います。runtime-lock.jsonに記載された公式ZIPをローカルに用意して実行します。

```sh
python3 scripts/package_portable.py --inputs dist/portable-inputs --output dist/decksmith-portable-win-x64.zip --cache .npm-cache
```

作成側にはPythonとnpmが必要です。利用側には同梱されるため別途導入不要です。cache指定時はnpmもオフライン。指定しない場合はネットワークを使うので事前承認が必要です。ランタイムZIPは固定SHA-256と照合し、署名検証とは区別します。依存物のライセンスを保持します。

配布物にはREADME、USER_GUIDE、PORTABLE_GUIDE、VERSION、全設定入り雛形を含めます。portable-manifest.jsonはdistribution=portable、対象OS、ランタイム版とハッシュを記録します。Windows実行検証の有無は正式配布方式の採用とは別の情報であり、作成処理だけでは検証済みにしません。

受け入れ時はWindows x64で、PC側Python/Nodeに依存しないこと、日本語・空白パス、PPTXのみ、PowerPointでのPNG/PDF出力、既存PowerPointセッションの保護、展開先を移動した後の実行を確認します。通信不要の描画試験と、ホストAI/画像生成の通信は区別します。
