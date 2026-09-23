# DeckSmith 利用ガイド

VS Codeの **Codex拡張** または **Claude Code拡張** から、題材とスタイルYAMLを渡してPowerPointを作る手順です。GitHub Copilotや一般のClaudeチャット拡張ではなく、各社の公式拡張を対象にしています。

DeckSmithは独立したVS Code拡張ではありません。AIが読む制作手順（Skill）と、PPTXを描画する共通エンジンを組み合わせて使います。スタイルプリセットの選択は不要です。

このガイドでは、配布パッケージに含まれるSkillを作業フォルダーに登録します。マーケットプレイスへの登録やCodexデスクトップアプリへのインストールとは別の導入方法です。

## 1. 最初に用意するもの

- VS Codeと、CodexまたはClaude Codeの公式拡張。拡張側でサインインを済ませます。
- このガイドと `scripts/setup_workspace.py` を含むDeckSmithの配布フォルダー、または同じ内容のソース一式。
- Python 3.9以上、Node.js 18以上とnpm。新規導入には、サポート中のPython／Node.js LTSを選んでください。
- プレビュー用のLibreOfficeとPoppler（`pdftoppm`）。
- 使用したいフォント。フォントはPPTXに埋め込まれません。

導入元：[Codex拡張の公式案内](https://learn.chatgpt.com/docs/codex/ide)、[Claude Code拡張の公式案内](https://code.claude.com/docs/en/vs-code)、[Python](https://www.python.org/downloads/)、[Node.js](https://nodejs.org/en/download)、[LibreOffice](https://www.libreoffice.org/download/)、[Poppler](https://poppler.freedesktop.org/)。

DeckSmith自体に各社のAPIキーを入力する必要はありません。AIの利用契約・認証は拡張側で行います。外部画像生成サービスを使う場合は、別途そのサービスの認証や料金が発生することがあります。

> この版はローカルの生成・配布物の移動試験済みです。ただし、VS Code両拡張内での一連の操作、およびWindows／Linuxでの実機試験は未完了です。公式のSkill配置仕様に基づく導入手順であり、すべての環境での動作確認済みという意味ではありません。未公開の開発版を使う場合、GitHubの既存ZIPにこの版が入っているとは限りません。

## 2. 作業フォルダーにDeckSmithを登録する

### フォルダーを開く

資料を保存するフォルダーを作り、VS Codeの「フォルダーを開く」で開いてください。例：`my-presentations`。

WSL・SSH・Dev Containerを使う場合、フォルダーとPython／Node／LibreOffice／Popplerは、**AIがコマンドを実行する側の環境**に用意します。Windows側にだけ入れたソフトがWSLで使えるとは限りません。

### 登録する

VS Codeのターミナルで、展開したDeckSmithフォルダーへ移動します。以下の `/path/to/my-presentations` は、実際の作業フォルダーの絶対パスに置き換えてください。

Codex用：

```bash
python3 scripts/setup_workspace.py --host codex --workspace "/path/to/my-presentations"
```

Claude Code用：

```bash
python3 scripts/setup_workspace.py --host claude --workspace "/path/to/my-presentations"
```

両方使う場合は `--host both` を指定します。Windowsで `python3` がない場合は、インストールしたPython 3.9以上の `python` または `py -3` に読み替えてください。Windowsのパス例は `"C:\Users\your-name\Documents\my-presentations"` です。

この補助スクリプトは、次の場所へSkill一式をコピーします。設定ファイルの変更、外部通信、依存ソフトのインストールは行いません。同名のフォルダーがある場合は上書きせず停止します。事前確認だけなら `--dry-run` を追加してください。

| 利用する拡張 | 作業フォルダー内の配置先 | チャットでの呼び出し |
| --- | --- | --- |
| Codex | `.agents/skills/decksmith/` | `$decksmith` |
| Claude Code | `.claude/skills/decksmith/` | `/decksmith` |

配置先と呼び出し方法は、[CodexのSkill仕様](https://learn.chatgpt.com/docs/build-skills)と[Claude CodeのSkill仕様](https://code.claude.com/docs/en/skills)に基づきます。Claudeのプラグイン方式で登録した場合の `/decksmith:decksmith` とは異なります。本ガイドのコピー方式では `/decksmith` です。

スクリプトを使わず、配布物の `skills/decksmith` フォルダーを上記の配置先に丸ごとコピーしても構いません。`SKILL.md` だけでなく、scripts・references・package.json・package-lock.jsonなども必要です。

### 依存ライブラリを用意する

ターミナルで **資料の作業フォルダー** に移動して実行します。

Codexの場合：

```bash
npm ci --prefix .agents/skills/decksmith --ignore-scripts --no-audit --no-fund
python3 .agents/skills/decksmith/scripts/doctor.py
```

Claude Codeの場合：

```bash
npm ci --prefix .claude/skills/decksmith --ignore-scripts --no-audit --no-fund
python3 .claude/skills/decksmith/scripts/doctor.py
```

両方登録した場合は両方の場所で実行します。npmは初回にネットワークを使います。PythonのYAMLライブラリは同梱しているため、`pip install` は不要です。

環境確認で `python`、`node`、`engine`、`soffice`、`pdftoppm` の `ready` がtrueになれば、描画とプレビューに必要な構成が見つかっています。`fonts` と `image_generation` は別途確認が必要です。

不足がある場合は、その結果を拡張のチャットに貼り、次のように依頼できます。

```text
DeckSmithの環境確認結果です。
不足しているソフトと、この環境に合った導入方法を教えてください。
既存の設定は上書きせず、追加インストールの前に内容を確認してください。
```

### macOSでLibreOfficeが見つからない場合

`soffice.ready` だけがfalseでも、LibreOfficeが未インストールとは限りません。現在のDeckSmithはPATHまたは `DECKSMITH_SOFFICE` で実行ファイルを探すため、macOSのアプリフォルダーにあるLibreOfficeを自動検出できない場合があります。

まず、標準のインストール先に実行ファイルがあるか確認します。

```bash
ls -l /Applications/LibreOffice.app/Contents/MacOS/soffice
```

見つかったら、資料の作業フォルダーで次を実行してください。確認コマンドは登録した拡張のものだけで構いません。

```bash
export DECKSMITH_SOFFICE="/Applications/LibreOffice.app/Contents/MacOS/soffice"

# Claude Code用
python3 .claude/skills/decksmith/scripts/doctor.py
# Codex用
python3 .agents/skills/decksmith/scripts/doctor.py
```

見つからない場合はLibreOfficeのインストール先を確認し、未導入なら前述の公式サイトから導入してください。別の場所にある場合は、その実行ファイルの絶対パスを指定します。

**このexportは実行したターミナルと、そこから起動する子プロセスにだけ有効です。** すでに起動中の拡張や別のターミナルへ自動反映されるとは限りません。環境確認が成功しても、拡張からの生成成功を確認したことにはなりません。

拡張のチャットで生成を依頼するときは、次の一文も添えてください。

```text
LibreOfficeの実行ファイルは /Applications/LibreOffice.app/Contents/MacOS/soffice です。
環境確認とPowerPoint生成の各コマンドを実行するときに、
環境変数 DECKSMITH_SOFFICE にこのパスを指定してください。
同じ実行環境でdoctor.pyを確認してから、プレビュー付きで生成してください。
```

`image_generation.status: host_or_user_supplied` は不足エラーではなく、画像生成に利用環境のツールまたは持ち込み素材を使うという意味です。`fonts.status: must_verify_on_target` も不足確定ではなく、使用するフォントを制作時に確認するという意味です。

### 拡張から認識を確認する

資料の作業フォルダーを開いた状態で、新しいチャットを開始します。Codexでは `$` の候補または `/skills`、Claude Codeでは `/` の候補からDeckSmithを探してください。出ない場合はVS Codeの「Developer: Reload Window」で再読み込みします。

まず「DeckSmithのSkillを読み、利用可能な生成環境を確認して」と依頼しても構いません。ファイル操作・コマンド実行・必要なネットワーク接続の承認を求められたら、対象と内容を確認してください。権限を一律に解除する必要はありません。

## 3. スタイルYAMLを用意する

作り方は、次の記事を参照してください。

**[【AI】NotebookLMのスライド資料を自在にコントロールする — mayochan32 / Qiita](https://qiita.com/mayochan32/items/18323a3f5201d08e8afc)**

参考画像から「presentation style maker」でスタイルYAMLを作る手順が紹介されています。記事はNotebookLM向けですが、作成したスタイルYAMLをDeckSmithへのデザイン指定として渡せます。NotebookLM自体の利用は必須ではありません。

YAMLを `style.yaml` として保存してください。Markdownの囲み記号を除き、インデントを保ちます。チャットに貼り付けて保存を依頼しても構いません。色コードは `"#FDF5E6"` のように引用符で囲むと、コメントとの混同を防げます。

DeckSmithはその都度YAMLの意味を解釈します。特定のキー名やスタイル名に合わせる必要はありません。ただし、現エンジンで表現できない効果はあります。指定の無視ではなく、制約や代案の説明を求めてください。

## 4. 最初のPowerPointを作る

### 任意の制作設定：decksmith.yaml

資料フォルダーの `decksmith.yaml` に制作条件を保存できます。ファイル・各項目とも省略可能です。デザインは引き続き `style.yaml` に記述します。

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
  directory: output
  filename: 相対性理論.pptx
  pdf: true
images:
  mode: auto
language: 日本語
```

| 設定項目 | 意味・省略時 |
| --- | --- |
| slide.width_px | 幅。サイズ無指定時1920 |
| slide.height_px | 高さ。サイズ無指定時1080 |
| slide.aspect_ratio | 幅:高さ。サイズ無指定時16:9 |
| privacy.mode | normal（既定）／restricted |
| output.directory | 出力先。既定output |
| output.filename | .pptx付きファイル名。省略時はAIが題材から決定 |
| input.style | スタイルYAML。省略時は依頼・添付から判断 |
| input.brief | 原稿・指示ファイル。省略時は依頼・添付から判断 |
| output.pdf | PDFも保存するか。既定false |
| images.mode | auto（既定）／provided_only |
| language | 資料の言語。省略時は依頼内容から判断 |

相対パスはこの設定ファイルがあるフォルダー基準です。`language` は `ja`／`en` だけでなく、`日本語`／`english`／`繁體中文`／`イギリス英語` などでも指定できます。意味が曖昧な場合はAIが確認します。本文・見出し・キャプション・説明用ノートへ適用し、固有名詞や引用原文は必要に応じて保持します。

`restricted` は利用中のAIサービスの組み込み機能（画像生成を含む）とローカル処理のみ利用します。Web検索・外部サイトへのアクセス・別サービスへの送信はしません。初回セットアップは対象外ですが、制作中の追加ダウンロードは停止して案内します。原稿・画像・プレビューは利用中のAIサービスへ送信され得ます。これはAIの操作ルールであり、OSのクラウド同期や拡張の通信まで遮断する機能ではありません。

`auto` は必要に応じて提供画像や生成画像を使います。`provided_only` は指定された画像のみを使用し、新規生成・外部取得はしません。画像認識による内容に合った配置、ローカル加工、編集可能な図形・図解の作成は可能です。配置指示があれば優先し、不足素材は相談します。

プロンプトでも指定できます。明確な変更指示は優先しますが、曖昧な矛盾は確認し、通信制限を黙って解除しません。AIは元の設定を残し、変更を `decksmith.resolved.yaml` に記録して使用します。出力先のプレビュー内にも適用設定を記録します。

生成処理はsceneと同じフォルダーのdecksmith.yamlを自動検出します。別ファイルは `--config` で指定します。設定確認だけなら `python3 <skill-directory>/scripts/project_config.py --config <project>/decksmith.yaml` を使えます。

### スライドのサイズ

指定がなければ **横長16:9・1920×1080px** で作ります。YAMLまたはプロンプトにサイズ指定があれば、そちらを優先します。たとえば「縦長9:16、1080×1920pxで作って」と依頼できます。

YAMLにも自由なキーで記述できます。例：

```yaml
スライドサイズ:
  幅px: 1080
  高さpx: 1920
```

比率だけの指定では長辺1920pxを基準に算出します。比率と片方の寸法があれば他方を算出します。指定同士が矛盾する場合は、明確な上書き指示がない限り確認します。AIが確定したサイズを伝えてから、そのサイズに合わせて各ページを設計します。

pxは設計座標とプレビューPNGの画素数です。PPTX自体は固定ピクセル画像ではなく、96px＝1インチとしてスライドの物理寸法へ変換します。

### 題材と資料を用意する

作業フォルダーに次を用意します。

```text
my-presentations/
  .agents/skills/decksmith/    ← Codex用。Claude用は .claude/skills/decksmith/
  relativity/
    decksmith.yaml           ← 任意。サイズ、言語、通信制限、入出力などの制作設定
    style.yaml               ← 配色、書体、構図などのデザイン指定
    brief.md                 ← 題材、対象読者、目的、残したい内容
    references/              ← 必要なら原稿、参考PDF、画像
```

`decksmith.yaml` は必須ではありません。用意する場合は資料フォルダー（この例では `relativity/`）に置きます。`input.style: style.yaml`、`input.brief: brief.md` と指定すれば、同じフォルダーのデザイン・原稿を参照できます。詳しい項目は上の「任意の制作設定：decksmith.yaml」を参照してください。

`brief.md` も必須ではありません。内容をチャットで直接伝えても大丈夫です。`scene.yaml` や `structure.yaml` はAIが作る内部ファイルなので、自分で書く必要はありません。

### Codexに依頼する例

**内容をプロンプトで直接伝える場合：**

```text
$decksmith
relativity/style.yaml のスタイルで、
相対性理論を初学者向けに説明するPowerPointを8枚作ってください。
光速不変、時間の遅れ、E=mc²、一般相対論、GPSを扱ってください。
必要なイラストは生成機能が使える場合に生成してください。
画像生成が使えない場合、必要な素材と代案を先に教えてください。
本文・数式・正確な図解は編集可能にしてください。
relativity/output/ に保存し、全ページのプレビューを確認してください。
出典はスピーカーノートに記録し、未対応の表現があれば説明してください。
```

**内容をbrief.mdで指定する場合：**

```text
$decksmith
relativity/brief.md を読んで、記載された題材・対象読者・目的・必須内容に沿って
PowerPointを作ってください。
制作設定は relativity/decksmith.yaml、デザインは relativity/style.yaml に従ってください。
画像の利用方法、言語、サイズ、保存先は制作設定に従ってください。
本文・数式・正確な図解は編集可能にし、全ページのプレビューを確認してください。
指定に矛盾や制作に必要な情報の不足があれば、確認してください。
```

この例は3ファイルを用意した場合です。`decksmith.yaml` がない場合は制作設定の指定を省き、必要な条件と保存先をプロンプトに書いてください。設定ファイルの `input.style` と `input.brief` にパスを書いてある場合は、次のように短く依頼できます。

```text
$decksmith
relativity/decksmith.yaml の制作設定と、そこで指定した原稿・スタイルを使って
PowerPointを作成し、全ページのプレビューを確認してください。
```

### Claude Codeに依頼する例

上のいずれの例も、先頭の `$decksmith` を `/decksmith` に置き換えて送信します。同じ題材・YAML・参考資料を渡せますが、AIや生成機能が異なれば、構図や画像は同一にはなりません。

ファイルはVS Codeのファイル参照機能で指定するか、開いている作業フォルダーからの相対パスを書いてください。参考PDFは「内容の根拠」か「見た目の参考」かを添えると意図が伝わります。

## 5. 画像生成について

Codexデスクトップで使えた画像生成が、VS CodeのCodex拡張でも使えるとは限りません。Claude Codeについても、画像生成機能が標準で使えると仮定しません。

- 利用可能な画像生成ツールがある場合：AIが呼び出し、素材を資料内の `assets/` に保存します。
- 画像生成がない場合：自分で用意した画像や、別サービスで生成して保存したPNG／JPEGを渡せます。
- 外部サービスを接続する場合：利用するツール、認証、料金、送信する内容を確認してください。DeckSmithに自動接続機能はありません。

画像なしで成立するスタイルなら、文字やネイティブ図形で制作できます。写真・質感・複雑なイラストが主役の指定では、素材なしで同等の見た目にはなりません。機密資料を外部生成サービスへ送ってよいかも確認してください。

## 6. 完成ファイルを確認して修正する

標準出力はPPTXと `同名.preview/` 内のページ画像です。`output.pdf: true` を指定すると、PPTXと同じ場所へ同名のPDFも保存します。falseでも品質確認用のプレビューは作成します。

PPTXをPowerPointなどで開き、特に改行、フォント、図解、数値を確認します。プレビューと実際のアプリでは表示差があり得ます。AIのプレビュー確認ができなかった場合は、未確認として扱ってください。

修正は同じチャットで具体的に伝えます。

```text
3枚目は図を大きくして、本文を短くしてください。
1枚目は見出しを背景の曲線に沿わせてください。
内容と数値は変えず、元のPPTXを残して別名で再生成してください。
修正後も全ページを確認してください。
```

別のスタイルを試す場合は新しいYAMLを渡し、同じ内容から再設計するよう頼みます。元の `style.yaml`、`structure.yaml`、`scene.yaml`、`assets/` を保存すると次の修正に使えます。

## 7. 困ったとき

| 症状 | 確認すること |
| --- | --- |
| DeckSmithが候補に出ない | 開いている作業フォルダー直下に正しい配置があるか。`decksmith/decksmith/SKILL.md` のように二重になっていないか。新規チャット／再読み込みを試す。組織のSkill利用制限も確認する。 |
| `Missing node`、エンジンが見つからない | Node.jsのPATHと、コピーしたSkill内でnpm ciを実行したかを確認する。 |
| `Missing soffice` | LibreOfficeの実行ファイルがPATHにない可能性。AIに実際の場所を調べさせ、`DECKSMITH_SOFFICE` を指定する。 |
| `Missing pdftoppm` | Popplerの導入場所を確認し、必要なら `DECKSMITH_PDFTOPPM` を指定する。 |
| 日本語が四角になる／改行が違う | 実行環境と閲覧環境に指定フォントがあるか。代替フォントを使ったら全ページを再確認する。 |
| 出力の上書きを拒否される | 別の出力名を指定する。既存ファイルを自動削除しない。 |
| YAMLエラー | 引用符、インデント、囲み記号を確認。元の意味を変えずに構文だけ直すよう依頼する。 |
| 見た目が単調／指定と違う | 背景色だけでなく構図・文字の大小・素材・余白をYAMLと照合するよう頼む。参考画像も添付する。 |
| ソフトは入っているのに拡張から見えない | VS Codeを再起動して環境変数を読み直す。リモート／WSLの場合は実行側を確認する。 |

`--pptx-only` はプレビューを省く中間出力用です。指定しても視覚確認済みにはなりません。現在はネイティブ表・グラフ専用要素、文字輪郭の液状ワープ、複雑なマスクなどが未対応です。

## 8. 更新と配布

### バージョンの確認

DeckSmithのバージョンは `vメジャー.マイナー.bugfix`（例：`v0.4.0`）です。配布フォルダー直下の `VERSION`、または配置済みSkill内の `VERSION` で確認できます。実際に使用しているコピーを確認するには、資料の作業フォルダーで実行してください。

```bash
# Codex用
python3 .agents/skills/decksmith/scripts/create_deck.py --version
# Claude Code用
python3 .claude/skills/decksmith/scripts/create_deck.py --version
```

生成開始時にも `DeckSmith vX.Y.Z` を表示し、環境確認結果とプレビュー内の検証・レビュー記録にもバージョンを残します。PPTXの見た目にはバージョン文字を追加しません。AIも制作開始時に使用バージョンを案内します。古い配布物ではこの確認コマンドに対応していません。

### 新版への更新

登録スクリプトは同名のSkillを更新しません。更新前に既存の `decksmith` フォルダーを、Skill探索対象の外へバックアップしてから新版を配置し、npm ciを実行してください。古いSkillを同じ `skills/` 内に別名で残すと重複認識の原因になります。資料の `output/` や `assets/` は削除しません。

別のPCに配布する場合、開発チャットの履歴や開発者の絶対パスは不要です。配布フォルダーのこのガイドと登録スクリプトを使い、配布先で依存ソフト・フォント・画像生成手段を確認してください。セットアップや修正を加えたコピーは、配布元の更新で自動同期されません。

公式仕様の確認日：2026-09-23。各拡張の操作や利用条件は変更されることがあります。
