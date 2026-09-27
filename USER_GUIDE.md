# DeckSmith 利用ガイド

`brief.md` で内容、`style.yaml` で見た目、`decksmith.yaml` で生成方法を指定し、AIエージェントへ制作を依頼します。このガイドでは作業フォルダーを `my-presentations/` とし、原稿・設定・参考資料は `setting/`、生成結果は同列の `output/` に分けます。

- [1. インストール方法](#1-インストール方法)
- [2. プレゼン資料生成方法](#2-プレゼン資料生成方法)
- [3. 困った時](#3-困った時)
- [4. 更新と配布](#4-更新と配布)

## 1. インストール方法

### 1.1. 配布物を選ぶ

[GitHub Releases](https://github.com/mayochan32/decksmith/releases)から、利用する版の配布物を入手して展開します。各リリースに実際に添付されているファイルを確認してください。ソースZIPにはPORTABLE用ランタイムは含まれません。

| 方式 | 対象 | 準備 |
| --- | --- | --- |
| Windows PORTABLE版（正式な配布方式） | Windows x64 | ZIPを丸ごと展開。Python・Node.js・npmの個別導入は不要 |
| 通常版 | Windows／Mac | Python 3.9+、Node.js 18+、npmと描画ライブラリを用意 |

どちらもAIエージェントと利用契約・認証、必要なフォントを別途用意します。ここではVS CodeのCodex／Claude Code拡張から使う手順を示します。DeckSmith自体はVS Code拡張ではなく、AIが読むSkillとローカルの描画処理です。

### 1.2. Windows PORTABLE版を導入する

1. Windows x64用PORTABLE ZIPを、例えば `C:\Tools\decksmith-portable` に展開します。フォルダー構成を保ち、全ファイルを展開してください。
2. VS Codeと利用するAI拡張の準備・サインインを済ませます。
3. 作業フォルダー `C:\work\my-presentations` と、その中に `setting` フォルダーを作り、VS Codeでは `my-presentations` を開きます。
4. プレビュー・PDFが必要ならWindowsデスクトップ版PowerPointを導入・認証します。LibreOffice・Popplerは不要です。

PowerShellで確認します。パスは実際の展開先に置き換えてください。

```powershell
& 'C:\Tools\decksmith-portable\decksmith.cmd' --version
& 'C:\Tools\decksmith-portable\decksmith.cmd' doctor --project 'C:\work\my-presentations\setting' --renderer powerpoint
```

PowerPointを使わずPPTXのみ作る場合は、最後を `--renderer none` にします。PythonやNode.js、npmをPCへ追加インストールする必要はありません。

PORTABLE版ではSkillだけを `.agents` や `.claude` へコピーせず、展開先のSkillと `decksmith.cmd` をAIに直接指定します。実行環境との位置関係を保つためです。詳細は[PORTABLE_GUIDE](PORTABLE_GUIDE.md)を参照してください。

### 1.3. 通常版を導入する

PORTABLE版を使う方は、この項目を飛ばしてください。

Python 3.9以上、Node.js 18以上とnpmを用意します。プレビュー方式に応じてLibreOffice＋Poppler、またはWindowsのデスクトップ版PowerPointも必要です。PPTXだけなら変換ソフトは不要です。YAMLライブラリは同梱されているため `pip install` は不要です。

導入元：[Python](https://www.python.org/downloads/)、[Node.js](https://nodejs.org/en/download)、[LibreOffice](https://www.libreoffice.org/download/)、[Poppler](https://poppler.freedesktop.org/)。

展開した通常版のDeckSmithフォルダーで、Skillを作業フォルダーへ登録します。

```bash
# Codex用
python3 scripts/setup_workspace.py --host codex --workspace "/path/to/my-presentations"

# Claude Code用
python3 scripts/setup_workspace.py --host claude --workspace "/path/to/my-presentations"
```

両方使う場合は `--host both`。Windowsでpython3がない場合は、インストール済みの `python` または `py -3` を使います。パス例は `C:\work\my-presentations` です。

| 利用先 | my-presentations内の配置先 | 呼び出し |
| --- | --- | --- |
| Codex | `.agents/skills/decksmith/` | `$decksmith` |
| Claude Code | `.claude/skills/decksmith/` | `/decksmith` |

登録処理は既存Skillを上書きせず、ネットワーク接続やソフトのインストールも行いません。`--dry-run` で事前確認できます。手動コピーの場合も `SKILL.md` だけでなくSkillフォルダー全体が必要です。

次に、ターミナルで **my-presentationsフォルダーへ移動して** 実行します。

```bash
# Codex用
npm ci --prefix .agents/skills/decksmith --ignore-scripts --no-audit --no-fund
python3 .agents/skills/decksmith/scripts/doctor.py

# Claude Code用
npm ci --prefix .claude/skills/decksmith --ignore-scripts --no-audit --no-fund
python3 .claude/skills/decksmith/scripts/doctor.py
```

利用する方だけ実行してください。両方登録した場合は両方で実行します。npmは初回にネットワークを使います。AIが実行する場合も取得の目的・利用先を示し、人間の承認を得ます。

doctorは既定でLibreOffice方式を確認します。設定前に別方式を検査するなら `--renderer powerpoint` または `--renderer none` を付けます。設定を用意した後は `--config setting/decksmith.yaml` で選択方式を確認できます。

WSL・SSH・Dev Containerでは、AIが実行する側に依存ソフトが必要です。PowerPoint連携はWindowsネイティブ環境のみで、Mac・WSL・サービスからの操作には対応しません。

## 2. プレゼン資料生成方法

作業フォルダーの例です。PORTABLE版の実行ファイル一式は、この外に置いて構いません。

```text
my-presentations/
  .agents/skills/decksmith/  ← 通常版Codex用。Claude用は .claude/skills/decksmith/
  setting/
    decksmith.yaml          ← 任意。サイズ、言語、通信制限、入出力などの制作設定
    style.yaml              ← 配色、書体、構図などのデザイン指定
    brief.md                ← 題材、対象読者、目的、残したい内容
    references/             ← 必要なら原稿、参考PDF、画像
  output/                   ← 生成結果（制作時に作成）
```

通常版のSkillは `my-presentations/` 直下に登録し、`setting/` の中には置きません。PORTABLE版では上記のSkill配置は不要です。`scene.yaml`、`structure.yaml`、制作計画やレビュー記録はAIが作る内部ファイルで、利用者が用意する必要はありません。制作中の内部ファイルは `setting/` 側、納品PPTX・PDF・プレビューは `output/` 側に保存します。

### 2.1. プレゼン内容を用意する（brief.md）

`setting/brief.md` に「何を、誰に、何のために伝えるか」を記載します。必須の内容・数値・条件と、参考情報を区別してください。

```markdown
# プレゼン制作の依頼

題材：新サービスの紹介
対象読者：初めてサービスを知るお客様
目的：特長と利用の流れを理解してもらう
ページ数：6ページ

## 必ず伝える内容
- 解決する課題
- サービスの特長
- 利用開始までの流れ
- 料金と問い合わせ先（添付資料の情報を使用）

## ページ別の指定
- 1ページ目：文字は少なめ。イメージ画像を大きく配置
- 3ページ目：画像なし。比較条件を省略しない

## 参考資料
- references/service.pdf：内容の根拠
- references/design.pdf：見た目だけの参考
```

内容はプロンプトで直接伝えても構いません。`brief.md` は必須ではありませんが、再制作や更新時に便利です。提供画像の配置場所・加工禁止などもここに記載できます。

ページ別の文字量・画像指定は全体設定より優先されます。ただし通信制限や「提供画像のみ」の指定を解除するものではありません。

### 2.2. スタイルを用意する（style.yaml）

**DeckSmithの最大の特徴は、任意のスタイルYAMLでPowerPointのデザイン・表現形式を指定できることです。** 配色、書体、文字の大小、構図、画像の扱い、装飾や質感などを指定します。プリセット名を選ぶ必要はありません。

作り方は **[こちらのQiita記事](https://qiita.com/mayochan32/items/18323a3f5201d08e8afc)** を参照してください。記事を参考に作成したYAMLをDeckSmithのスタイル指定として利用できます。NotebookLMの利用は必須ではありません。

YAMLを `setting/style.yaml` に保存します。Markdownの囲み記号は除き、インデントを保ってください。色コードは `"#1A4FA0"` のように引用符で囲みます。チャットへ貼り付けて保存を依頼しても構いません。

特定のキー名に合わせる必要はありません。AIが指定の意味を読み取り、資料の内容と組み合わせて設計します。同じ原稿を別のスタイルで作りたい場合は、このYAMLを差し替えて再設計を依頼します。未対応の効果は制約を説明し、勝手に無視しません。

### 2.3. 生成方法を用意する（decksmith.yaml）

サイズ、言語、文字量、画像方針、通信制限、出力先を指定します。デザインそのものは `style.yaml` に記述します。このファイルと各項目は省略可能です。

#### 雛形から作る

配布物の `templates/decksmith.yaml`、または `skills/decksmith/assets/decksmith.yaml` を `setting/decksmith.yaml` へコピーし、必要な値だけ変更します。

PORTABLE版は、PowerPoint用の値を設定して雛形を作れます。

```powershell
& 'C:\Tools\decksmith-portable\decksmith.cmd' init --project 'C:\work\my-presentations\setting' --renderer powerpoint
```

PPTXのみなら `--renderer none`。通常版のCodex配置なら、my-presentations内で次を実行します（Claude Codeは `.agents` を `.claude` に読み替え）。

```bash
python3 .agents/skills/decksmith/scripts/project_init.py --project setting
```

既存設定は上書きしません。`input.style`、`input.brief`、`output.filename`、`language` の `null` は未指定という意味です。雛形を直接コピーした場合、rendererは `libreoffice` なので、PORTABLE版では必ず `powerpoint` または `none` に変更してください。

#### 記入例：Windows PowerPointで確認する

```yaml
slide:
  width_px: 1920
  height_px: 1080
  aspect_ratio: "16:9"
privacy:
  mode: restricted
input:
  style: style.yaml
  brief: brief.md
output:
  directory: ../output
  filename: presentation.pptx
  renderer: powerpoint
  pdf: true
images:
  mode: auto
  amount: normal
  type: auto
  color: color
  plan: show
text:
  amount: normal
language: 日本語
```

相対パスは `decksmith.yaml` のあるフォルダーを基準にします。`style.yaml` と `brief.md` は同じ `setting/` 内、`../output` は一段上の `my-presentations/output/` を指します。出力先を省略した場合も `../output` です。既存設定に `directory: output` がある場合はその明示指定を優先するため、今回の構成へ切り替えるには `../output` に変更してください。既存ファイルは自動移動しません。

これは記入例で、全項目の既定値とは異なります。Macのプレビューには `renderer: libreoffice`、PPTXだけなら `renderer: none` と `pdf: false` を指定します。

#### 設定項目一覧

| 設定項目 | 意味・省略時 |
| --- | --- |
| slide.width_px | 幅。サイズ無指定時1920 |
| slide.height_px | 高さ。サイズ無指定時1080 |
| slide.aspect_ratio | 幅:高さ。サイズ無指定時16:9 |
| privacy.mode | restricted（既定）／normal。どちらもWeb・外部サービスは事前承認が必要 |
| output.directory | 設定ファイルから見た出力先。既定 `../output`（settingと同列） |
| output.filename | .pptx付きファイル名。省略時はAIが題材から決定 |
| input.style | スタイルYAML。省略時は依頼・添付から判断 |
| input.brief | 原稿・指示ファイル。省略時は依頼・添付から判断 |
| output.pdf | PDFも保存するか。既定false |
| output.renderer | libreoffice（既定）／powerpoint（Windowsのみ）／none（PPTXのみ） |
| images.mode | auto（既定）／provided_only |
| images.amount | normal（既定）／more／less／none：普通・多め・少なめ・画像なし |
| images.type | auto（既定）／illust／photo／icon／anime：おまかせ・イラスト・写実的・アイコン・アニメ |
| images.color | color（既定）／gray／monotone：カラー・白黒グレー・単一色相の濃淡 |
| images.plan | show（既定）／confirm／skip：計画提示して続行・承認待ち・提示省略 |
| language | 資料の言語。省略時は依頼内容から判断 |
| text.amount | minimal／less／normal（既定）／more／dense：文字・文章量の5段階 |


相対パスはdecksmith.yamlのあるフォルダー基準です。通常版・PORTABLE版とも、明確なプロンプトでの変更指定にも対応します。曖昧な矛盾は確認します。AIは適用した設定を `decksmith.resolved.yaml` に記録し、元の設定は保持します。

#### サイズ・言語・文字量

サイズの既定は横長16:9・1920×1080px。比率だけなら長辺1920pxを基準に計算し、比率と片方の寸法があればもう片方を求めます。両寸法と比率を指定する場合は一致させてください。pxは設計座標とプレビューの画素数で、PPTX自体は固定画像ではありません。

languageは `ja`／`en` に限らず、`日本語`／`english`／`イギリス英語` などでも指定できます。本文・見出し・説明用ノートへ適用します。

文字量はminimal（とても少ない）、less（少なめ）、normal（普通）、more（多め）、dense（とても多い）の5段階。単純な文字数制限ではなく、説明の詳しさと話者ノートへの振り分けを調整します。必須の数値・条件は勝手に削除せず、小さい文字で無理に詰め込みません。

#### 画像の設定

autoは提供画像や利用可能な生成画像を使用。provided_onlyは提供画像だけを使用し、生成・外部取得はしません。内容認識が使える場合は画像を実際に見て、スライドに合う位置を判断します。

量だけでなくページ内の面積・役割も考慮します。noneでも説明用の編集可能な図解は使えます。grayは白黒グレー、monotoneは単一色相の濃淡。色調は画像への指定で、本文や背景まで一律に変更しません。証拠画像を無断で作風変換することもありません。

生成前にAIが画像計画を作ります。showは提示して続行、confirmは承認待ち、skipは提示だけ省略します。Web検索・外部サービスの承認と、生成不可時の確認はskipでも省略しません。

#### 通信と承認

既定はrestricted。normalを明示した既存設定は維持しますが、**どちらのモードでもWeb検索・外部サービスの利用前に人間の承認が必要**です。目的・利用先・送信情報を説明し、restrictedでは制限の例外であることも確認します。無断でnormalへ切り替えません。

利用中のAIサービスの組み込み画像生成とローカル処理は、外部サービスと区別します。原稿・画像・プレビューは利用中AIへ送信され得ます。OS同期や拡張の通信を遮断する仕組みではありません。

#### プレビュー・PDF方式

| renderer | 利用環境 | 必要な変換ソフト | 出力 |
| --- | --- | --- | --- |
| powerpoint | Windows通常版／PORTABLE版 | デスクトップ版PowerPoint | PPTX・PNG、任意でPDF |
| libreoffice | Windows／Macの通常版 | LibreOffice＋Poppler | PPTX・PNG、任意でPDF |
| none | Windows通常版／PORTABLE版、Mac通常版 | 不要 | PPTXのみ、見た目未確認 |

PORTABLE版はlibreofficeを使用しません。noneとpdf=trueの組み合わせはエラーです。失敗を理由に別方式へ自動変更しません。

PowerPoint連携では、初期設定・認証を済ませ、開いている資料を保存してPowerPointを終了してから開始します。書き出し中は操作しないでください。利用者のアプリを強制終了しないため、終了後に空のプロセスが残る場合は手動で閉じます。

### 2.4. プレゼン資料生成を指示する

VS Codeで `my-presentations/` を開き、AIエージェントへ依頼します。以下の通常版の依頼例は、この作業フォルダーを基準に指定しています。設定内の相対パスは引き続き `setting/decksmith.yaml` 基準です。

#### PORTABLE版の依頼例

Codex・Claude Codeいずれも、実際の展開先と作業フォルダーを指定します。

```text
C:\Tools\decksmith-portable\skills\decksmith\SKILL.md と
C:\Tools\decksmith-portable\PORTABLE_GUIDE.md を読んでください。

C:\work\my-presentations\setting のbrief.md、style.yaml、decksmith.yamlに従って
PowerPointを作成してください。
実行には同梱のdecksmith.cmdを使い、PC側のPythonやNode.jsは使わないでください。
本文・数値・正確な図解は編集可能にし、指定された方式でプレビューを確認してください。
外部アクセスの承認が必要な場合や画像生成ができない場合は、先に確認してください。
```

#### 通常版：brief.mdから作る

```text
$decksmith
setting/brief.mdに記載した題材・対象読者・目的・必須内容に沿ってPowerPointを作ってください。
デザインはsetting/style.yaml、生成条件はsetting/decksmith.yamlに従ってください。
本文・数値・正確な図解は編集可能にし、全ページのプレビューを確認してください。
不明点や矛盾は確認してください。
```

Claude Codeでは先頭を `/decksmith` に置き換えます。PPTXのみの設定なら「全ページのプレビューを確認」を「見た目未確認として納品」に変えてください。

#### 通常版：内容をプロンプトで伝える

```text
$decksmith
新サービスを初めて知るお客様向けに、6ページのPowerPointを作ってください。
課題、特長、利用の流れ、料金、問い合わせ先を説明してください。
料金などの事実はsetting/references/service.pdfに従い、推測で補わないでください。
デザインはsetting/style.yaml、生成条件はsetting/decksmith.yamlに従い、
output/へ保存してください。本文・数値は編集可能にしてください。
```

brief.mdがない場合は `input.brief` をnullまたは省略にします。decksmith.yamlも省略する場合は、必要な条件と保存先をプロンプトで指定します。PORTABLE版では必ずPowerPoint方式かPPTXのみかを明示してください。

#### 制作中と完成後

AIは使用バージョン、通信方針、画像生成の利用可否を最初に案内します。画像計画・代表ページの試作・全体生成・レビューを進めます。承認が必要な場面では回答を待ちます。内部の設定・承認・内容保護・レビュー記録はAIが作成します。

通常は `my-presentations/output/`（settingと同列）にPPTX、同名の `.preview/` に確認画像と記録が保存されます。pdf=trueならPDFも保存。noneではPNG・PDFはなく、記録だけ残ります。

完成PPTXはPowerPoint等でも開き、改行・フォント・図解・数値を確認してください。修正は同じチャットで依頼できます。

```text
3枚目は図を大きくして、本文を短くしてください。
必須の内容と数値は変えず、元のファイルを残して別名で再生成してください。
修正後も表示を確認してください。
```

## 3. 困った時

### 3.1. 環境・実行の問題

| 症状 | 対処 |
| --- | --- |
| Skillが候補に出ない | 通常版は配置先・フォルダーの二重化を確認し、新規チャットや再読み込みを試す。PORTABLE版は候補への登録を前提にせず、展開先のSKILL.mdを直接指定する |
| PORTABLE版でbundled Pythonがない | ZIP全体を展開し直す。PC側のPythonへの切り替えでは解決しない |
| 通常版でnode／engineが見つからない | Node.jsのPATHと、登録したSkill内のnpm ciを確認する |
| PowerPointが使えない | Windowsデスクトップ版の導入・認証を確認。doctorのCOM登録確認だけでは書き出し成功を保証しない |
| PowerPointが起動中と表示 | 開いている資料を保存し、PowerPointを手動で終了する |
| スクリプト実行が拒否される | 診断結果と実行環境を確認し、組織の管理者へ相談する。制限を自動解除・迂回しない |
| soffice／pdftoppmが見つからない | 通常版のLibreOffice方式のみ必要。導入先とPATHを確認する |
| 日本語が四角になる・改行が違う | 実行先と閲覧先のフォントを確認。代替フォントで全ページを再確認する |
| 上書きを拒否される | 別名で生成する。既存の出力やレビュー記録は削除しない |
| YAMLエラー | 引用符・インデント・Markdown囲みを確認する |
| 見た目が指定と違う | 色だけでなく構図・文字の大小・余白・素材をstyle.yamlと照合するよう依頼する |

診断結果をチャットへ貼り、「不足と対処を説明し、追加インストール前に確認して」と依頼できます。PORTABLE版の詳細診断は[PORTABLE_GUIDE](PORTABLE_GUIDE.md)を参照してください。

### 3.2. MacでLibreOfficeが見つからない

通常版では、アプリが入っていてもPATHから見つからない場合があります。まず実在を確認します。

```bash
ls -l /Applications/LibreOffice.app/Contents/MacOS/soffice
export DECKSMITH_SOFFICE="/Applications/LibreOffice.app/Contents/MacOS/soffice"
python3 .agents/skills/decksmith/scripts/doctor.py
```

Claude Codeでは `.agents` を `.claude` に読み替えてください。別の導入先なら実際のパスを指定します。

exportはそのターミナルと子プロセスだけに有効です。起動済みの拡張へ自動反映されるとは限りません。AIにも「診断と生成の各実行でDECKSMITH_SOFFICEにこのパスを指定して」と伝えてください。

### 3.3. 画像生成できない

画像生成機能の有無は利用するAI環境によって異なります。機能なし・利用上限・生成失敗で必要画像を用意できない場合、AIは理由と対象ページを示し、次の選択を確認します。

1. **画像なしで作成**：文字・図解・余白を再配置する。
2. **四角と生成プロンプトを表示**：予定画像位置に四角を置き、その中に画像生成指示を編集可能な文字で記載する。

回答前に無断で画像省略・図解置換・別サービス接続はしません。一部だけ生成できた場合は失敗分について確認します。2は「画像差し替え待ち」として納品し、画像まで完成した資料とは扱いません。

### 3.4. 対応していない表現

専用のネイティブ表・グラフ要素、複雑なマスク、文字輪郭の液状ワープなどは未対応です。要求を無視せず、制約を説明して対応を相談します。noneで生成した資料は構造検査のみで、視覚確認済みにはなりません。

## 4. 更新と配布

### 4.1. バージョンを確認する

形式は `vx.y.z`（メジャー・マイナー・bugfix）。配布フォルダー直下またはSkill内のVERSIONで確認できます。

```powershell
# PORTABLE版
& 'C:\Tools\decksmith-portable\decksmith.cmd' --version
```

```bash
# 通常版（my-presentations内で実行）
python3 .agents/skills/decksmith/scripts/create_deck.py --version
# Claude Code用は .agents を .claude に変更
```

生成開始時と検証・レビュー記録にも版番号が残ります。スライド上には版番号を追加しません。

### 4.2. 新版へ更新する

PORTABLE版は新版ZIPを別フォルダーへ丸ごと展開し、AIへ指定するSKILL.md・ガイド・decksmith.cmdのパスを切り替えます。runtimeやSkillの一部だけを旧版と混在させないでください。`setting/` の原稿・設定・素材と、同列の `output/` の生成結果は保持します。

通常版は既存Skillを探索対象の外へバックアップし、新版を配置してnpm ciを実行します。登録処理は同名のSkillを上書きしません。旧Skillを同じskillsフォルダーに別名で残すと、重複認識の原因になります。

### 4.3. 別のPCへ配布する

PORTABLE版は展開フォルダー全体を渡します。通常版は配布物のガイドと登録処理を使い、配布先で依存ソフトを用意します。どちらも開発チャットや開発者の絶対パスには依存しません。AI環境・フォント・PowerPoint等の利用条件は各PCで確認してください。

正式仕様としてのPORTABLE版採用と、更新版ZIPの公開は別です。この文書は現在のソースを説明しています。公開済みZIPに含まれる機能は、そのリリースの説明とVERSIONを確認してください。

AI向けの詳しい制作補助は[workflow.md](skills/decksmith/references/workflow.md)を参照してください。
