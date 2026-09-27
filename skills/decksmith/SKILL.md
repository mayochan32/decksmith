---
name: decksmith
description: 題材・構成・任意のスタイルYAMLから、AIがページを設計して編集可能なPowerPointを生成する。参考資料の表現を分析してスライドを制作する依頼にも使う。
---

# DeckSmith

利用者の題材、構成、スタイルを独立して扱う。スタイルの意味解釈とページ設計はこのSkillを読むAIの仕事。Pythonは意味解釈を行わず、JavaScriptは設計した要素を描画する。プラグインにスタイルプリセットや完成構図の一覧を持たない。

## 実行環境

同梱版のルートにPORTABLE_GUIDE.mdとdecksmith.cmdがある場合は、そのガイドを先に読む。正式なWindows PORTABLE版ではPython・Node.jsのインストールや直接起動を行わず、`decksmith.cmd --version`、`decksmith.cmd doctor --project <project>`、`decksmith.cmd build --project <project>`を使う。以下の直接Python実行例よりこの起動方法を優先する。描画方式はnoneまたはpowerpointを明示し、無断でnoneへ変更しない。

実行するSkillのscripts/version.pyまたはdoctor.pyから実際のバージョンを取得し、制作開始時に「DeckSmith vX.Y.Zで作成します」と利用者へ表示する。チャット履歴の版番号を使わない。

制作依頼を受けたら、外部操作・画像生成より前に[制作設定](references/project-settings.md)を読み、decksmith.yamlとプロンプトを解決する。privacyの既定はrestricted。開始時に通信モード、Web検索・外部サービスの承認条件、組み込み画像生成の許可と利用可否、ローカル処理の可否、利用中AIへの送信可能性を必ず表示する。normalを含む全モードでWeb検索・外部サービスは目的・利用先・送信情報を説明し、人間の事前承認を待つ。restrictedでは制限の例外であることも明示して承認を得る。設定値・画像計画の承認から通信の許可を推測しない。provided_onlyでは画像生成もしない。

最初に[実行環境](references/host-runtime.md)を読み、scripts/doctor.pyで依存を確認する。共通エンジンはPythonとNode.jsを使い、Codex・Claude Code・GitHub Copilot（VS Code Agentモード）・Gemini CLIで共通エンジンを使用する。Gemini CLIでの実利用は未検証。別のPresentations Skillや特定AIのSDKは必須にしない。

画像が必要ならホストの画像生成機能を確認して使用する。外部APIキーを前提にしない。機能なし・上限・生成失敗で必要画像を用意できない場合は、理由と対象ページを示して停止し、「画像なしで再配置」か「画像位置に四角を置き、中に編集可能な画像生成プロンプトを記載」かを人間に確認する。無回答で省略・図解への代替・外部サービスへの切り替えをしない。詳細は[画像素材](references/image-assets.md)。開発チャットの履歴、開発者の素材、リポジトリのartifacts/には依存しない。

## 制作

標準の作業構成はmy-presentations/setting/に原稿・style.yaml・decksmith.yamlを置き、同列のmy-presentations/output/に納品物を保存する。以下の<project>はsettingフォルダーを指す。設定内の相対パスは設定ファイル基準で、output.directoryの既定は../output。利用者が明示した別の保存先は維持する。

設定ファイルを用意したい利用者にはassets/decksmith.yamlを案内する。scripts/project_init.py（同梱版は`decksmith.cmd init --project <project> --renderer powerpoint`）で全項目入り雛形を作れる。既存ファイルを上書きしない。nullは未指定であり、素材ファイルの作成や内容の推測を許可する指定ではない。

構成を決める前に[制作設定の文字量](references/project-settings.md)を適用する。text.amountはminimal/less/normal（既定）/more/denseの5段階。brief.mdのページ別指定を全体設定より優先し、表示文と話者ノートを分けてから設計する。画面掲載必須の内容をノートへ逃がしたり、描画時に切り捨てたりしない。

素材制作前に[制作設定の画像方針・生成前計画](references/project-settings.md)を適用する。brief.mdのページ別画像指定を全体方針より優先し、privacyとprovided_onlyは維持する。images.plan=confirmでは計画を提示し承認を待って停止する。showは提示後に続行、skipは提示のみ省く。amount/type/colorを画像の設計・生成・最終レビューに反映する。

サイズ指定がなければ横長16:9・1920×1080pxで制作する。YAMLやプロンプトにサイズ・縦横比・向きの指定があれば既定値より優先し、設計前に解釈してscene.canvasへ明記する。寸法の補完と矛盾の扱いは[シーン仕様](references/deck-spec.md)の「スライドサイズ」に従う。確定した寸法を利用者へ伝え、そのキャンバスに合わせて素材・文字・図形を設計する。

1. 題材・構成・スタイルを依頼から読み取る。指定済みなら再質問せず進む。参考資料は実際に見て、内容の資料かデザインの資料かを区別する。
2. 元のスタイルYAMLをstyle.yamlとして保持する。独自キーや日本語の記述を、既知のキー名へ書き換えて意味を失わせない。[解釈と設計](references/style-system.md)を読む。
3. 内容をstructure.yamlへ整理する。各ページにid、purpose、required_text（必ず残す文字列）を記録する。根拠と出典も保持する。内容の短縮は設計前に行い、描画時に切り捨てない。[制作補助](references/workflow.md)のfreeze-contentで原稿由来の基準を保存してからsceneを設計する。修正後のsceneからrequired_textや基準を逆生成しない。変更が必要なら原文・変更後・理由・原稿上の根拠を別記し、最終レビューで意味と必須条件を照合する。
4. 元YAMLの各末端値を要件台帳へ対応づけ、[デザイン方針](references/design-plan.md)に従ってdesign-plan.yamlを作る。スタイル固有の特徴、各ページの意味上の主役、文字の役割・書体・サイズ、素材の必要性を座標設計より先に決める。Typeは利用者の説明用の名前であり、描画エンジンの選択キーではない。作れない要件はblocked/asset_pendingとし、非該当に偽装しない。
5. 必要な素材を資料内のassets/へ生成・保存する。被写体、配置先、文字安全域、透過、質感を具体的に指定する。事実を示す画像は提供資料を使う。写真や装飾の生成画像に本文や数値を焼き込まない。
6. [シーン仕様](references/deck-spec.md)に従いscene.yamlを作る。自由な位置・寸法・重なり・回転・文字組みを要素単位で指定する。これはAIが作る内部ファイルであり、利用者に書かせない。初期アダプターはtext/shape/path/imageに対応する。ネイティブ表・グラフ等を必要とする依頼では、アダプターを実装・検証してから進め、画像化や箇条書きへの置換で済ませない。
7. 元ファイルのSHA-256をsceneへ記録する。元のYAMLが変わったら必ず再解釈して設計を更新する。ハッシュだけを更新して流用しない。
8. このSkillのscripts/create_deck.pyを実行する。設定はsceneと同じフォルダーのdecksmith.yamlを自動検出する。別ファイルや解決済み設定は--configで渡す。input.style、output.filenameが設定済みなら--style、--outputは省略できる。

   ```bash
   python3 <skill-directory>/scripts/create_deck.py \
     --scene <project>/scene.yaml --style <project>/style.yaml \
     --structure <project>/structure.yaml --output <project>/../output/deck.pptx
   ```

   --validate-onlyは入力検証だけを行う。既存出力を上書きしない。output.rendererはlibreoffice（既定）、powerpoint（Windowsのみ）、none。--rendererでも指定でき、--pptx-onlyはnoneの別名。noneは利用者の明示指定時に「PPTX生成済み・見た目未確認」として納品可能。変換失敗を理由に無断でnoneへ切り替えない。ホスト専用の操作記録はホスト側で実行する。
9. まず代表ページの構図をプレビューで比較し、全体へ展開する。代表ページの扱いは[デザイン方針](references/design-plan.md)に従う。続いて[品質検証](references/quality-gates.md)に従い全ページを見る。単に文字が収まったかではなく、内容・判読性・スタイルを別々に評価する。修正時は--next-outputで別名生成し、outputフォルダーを削除しない。review.jsonを記録後、scripts/review_deck.py --output <pptx>（同梱版はreview --project <project> --output <pptx>）を実行して納品物とレビューの一致を確認する。noneでは見た目未確認を保持する。

## 設計の判断

背景と色を変えるだけで済ませない。情報の読み順、主役、余白、文字の占有率、題材固有の画像を一体として考える。見出しと本文の書体を分けられる。文字の一部分だけの強調、前景画像との重なり、意図的なはみ出しを必要に応じて設計する。

文字・正確なラベル・関係線・数値は編集可能にする。質感やイラストは画像を活用する。完成ページ全体を画像として貼って編集可能と説明しない。下位の描画機能に制約があれば記録し、無視しない。
