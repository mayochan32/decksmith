# DeckSmith Windows PORTABLE版ガイド

Windows x64向けの正式な配布方式です。Python・Node.js・描画ライブラリを同梱しており、**利用PCへのPython・Node.js・npmのインストールは不要**です。ZIPを全展開し、`decksmith.cmd` から起動します。起動時の追加ダウンロードはありません。

LibreOffice・Popplerも不要です。ただし、AIエージェントとその認証、必要なフォントは別途用意します。プレビュー・PDFの作成には、導入・認証済みのWindowsデスクトップ版PowerPointが必要です。PowerPointなしでもPPTXのみ生成できます。

内容・スタイル・生成条件の作り方は[USER_GUIDE](USER_GUIDE.md)、機能概要は[README](README.md)を参照してください。

## 1. 導入

配布物は通常版 `decksmith-vX.Y.Z.zip` と、このWindows用 `decksmith-vX.Y.Z-portable-win-x64.zip` の2種類です。どちらもAIツール共通で、Codex・Claude Code・Copilot・Gemini CLI別のZIPはありません。Gemini CLIの実利用は未検証です。

1. [GitHub Releases](https://github.com/mayochan32/decksmith/releases)でWindows x64用PORTABLE配布物を確認し、ZIPを入手します。ソースZIPはランタイム同梱版ではありません。
2. 例えば `C:\Tools\decksmith-portable` に、ZIPの全ファイルを構成を保って展開します。
3. VS Codeと利用するAIエージェントを準備し、サインインします。
4. 作業フォルダー `C:\work\my-presentations` と、その中に `setting` を作ります。VS Codeでは `my-presentations` を開きます。

展開先にはdecksmith.cmd、launcher.py、runtime/、skills/、templates/、VERSION、各ガイドがあります。Skillだけを別の場所へコピーせず、展開フォルダー全体で使ってください。

PowerShellで確認します。

```powershell
& 'C:\Tools\decksmith-portable\decksmith.cmd' --version
& 'C:\Tools\decksmith-portable\decksmith.cmd' doctor --project 'C:\work\my-presentations\setting' --renderer powerpoint
```

PowerPointを使わない場合は `--renderer none` にします。通常のdoctorはCOM登録の確認だけで、PowerPointを起動しません。実際の書き出し成功を保証するものではありません。

## 2. 原稿・スタイル・生成設定を用意する

`my-presentations/setting/` に以下を置きます。生成結果はsetting内ではなく、同列の `my-presentations/output/` に保存します。

- `brief.md`：題材・対象読者・目的・必須内容。
- `style.yaml`：配色・書体・構図・画像表現など。作り方は[Qiitaの記事](https://qiita.com/mayochan32/items/18323a3f5201d08e8afc)を参照。
- `decksmith.yaml`：サイズ・言語・通信・画像方針・出力方式。

全設定入り雛形を作るには次を実行します。既存ファイルは上書きしません。

```powershell
& 'C:\Tools\decksmith-portable\decksmith.cmd' init --project 'C:\work\my-presentations\setting' --renderer powerpoint
```

PowerPointなしなら `--renderer none`。templates/decksmith.yamlを直接コピーすることもできますが、その場合はrendererをlibreofficeからpowerpointまたはnoneへ変更してください。共通雛形の既定値をPORTABLE側で暗黙に読み替えることはしません。

PowerPointでプレビューとPDFを作る設定：

```yaml
output:
  directory: ../output
  renderer: powerpoint
  pdf: true
  filename: presentation.pptx
```

PowerPointを使わずPPTXのみ生成する設定：

```yaml
output:
  directory: ../output
  renderer: none
  pdf: false
  filename: presentation.pptx
```

noneではPNG・PDFは生成せず、PPTXを「見た目未確認」として出力します。PORTABLE版はlibreofficeを使用しません。

## 3. AIに生成を依頼する

Codex・Claude Code・GitHub Copilot（VS CodeのAgentモード）などへ、実際のパスを指定して依頼します。呼び出し候補へ登録されていることを前提にしません。

```text
C:\Tools\decksmith-portable\skills\decksmith\SKILL.md と
C:\Tools\decksmith-portable\PORTABLE_GUIDE.md を読んでください。
C:\work\my-presentations\setting のbrief.md、style.yaml、decksmith.yamlに従って
PowerPointを作成してください。
実行には同梱のdecksmith.cmdを使ってください。
PC側のPythonやNode.jsを使ったり、追加インストールしたりしないでください。
```

Copilotも上記のSKILL.mdを直接指定し、共通のdecksmith.cmdを使います。PORTABLE版のSkillだけを `.github/skills/` へコピーしないでください。Gemini CLIも提供対象ですが実利用は未検証です。

原稿や設定はプロンプトでも指定できます。AIが内部ファイルを作成し、同梱エンジンで生成します。利用者がscene.yamlなどを手書きする必要はありません。

通信モードの既定はrestricted。normalを含む全モードで、Web検索・外部サービス利用は目的・送信先・送信情報を示して人間の承認を待ちます。必要な画像を生成できない場合は「画像なし」か「四角＋生成プロンプト」かを確認します。

## 4. PowerPointを使うときの注意

- Windowsデスクトップ版を手動起動し、認証・初期設定を済ませてください。ブラウザー版は対象外です。
- 開いている資料を保存し、PowerPointを終了してから生成を開始してください。起動中なら安全のため処理を拒否します。
- 書き出し中はPowerPointを操作しないでください。
- 処理は生成した資料だけを開いて閉じます。アプリ全体の強制終了はしません。空のPowerPointプロセスが残る場合は手動で終了してください。
- Windows PowerShell・COMを使います。Mac・WSL・リモートサービスからのPowerPoint操作には対応しません。
- 組織の実行ポリシーを自動解除・迂回しません。
- フォントはPCのものを使い、PPTXへ埋め込みません。

実際のPNG・PDF書き出しを診断するには、PowerPointを閉じてから実行します。

```powershell
& 'C:\Tools\decksmith-portable\decksmith.cmd' doctor --project 'C:\work\my-presentations\setting' --renderer powerpoint --test-export
```

この操作は一時資料を使ってPowerPointを起動します。正式な配布方式であっても、組織ポリシーやOfficeの構成ごとの動作確認は必要です。PORTABLE版は仮想マシンや通信遮断サンドボックスではありません。

## 5. 診断・再生成コマンド

通常はAIが実行します。`<folder>` には `C:\work\my-presentations\setting` を指定します。コマンドの相対パスは--project基準、設定内の相対パスはdecksmith.yaml基準です。既定の出力先は `../output` です。

| 操作 | 用途 |
| --- | --- |
| `--version` | 同梱版のバージョン表示 |
| `init --project <folder> --renderer powerpoint` | 全設定入り雛形の作成 |
| `doctor --project <folder> --fonts` | 依存・PowerPoint登録・フォント一覧 |
| `prepare --project <folder>` | 解決済み設定と通信方針の記録 |
| `freeze-content --project <folder> --brief brief.md` | 原稿由来の必須内容を保存 |
| `prototype --project <folder> --destination prototype-01 --slides <ID...>` | 代表ページの抽出 |
| `validate --project <folder>` | 描画せず入力を検証 |
| `build --project <folder> --next-output` | 既存出力を残して生成 |
| `compare --project <folder> --previous ../output/old.pptx --output ../output/new.pptx` | 描画されたページの差分確認 |
| `review --project <folder> --output ../output/presentation.pptx` | 納品物とレビュー記録の整合性確認 |

prepare後のvalidate/build/prototypeには `--config decksmith.resolved.yaml` を付けます。build/validateは--scene、--structure、--style、--output、--design-planも指定可能です。

--draftは未達要件を含む試作専用で、完成品にはしません。reviewはAIが実際に見た結果を記録した後の整合性検査であり、自動の美的評価ではありません。[制作補助の詳細](skills/decksmith/references/workflow.md)も参照してください。

## 6. 更新・再配布

新版は別フォルダーへ丸ごと展開し、AIに指定するパスを変更します。旧版のruntime・Skillを混ぜないでください。`setting/` の原稿・設定・素材と、同列の `output/` の生成結果は保持します。

別PCへ渡す場合も展開フォルダー全体を渡します。配布物直下のVERSIONと `--version` で版番号を確認できます。AIエージェント・PowerPointの利用契約は同梱されません。

このガイドは現在のソースの正式仕様です。新しいZIPの公開を意味するものではありません。公開済み配布物に含まれる機能はリリースの説明とVERSIONで確認してください。
