# ブラウザー版の試験導入

DeckSmithはローカル実行を主対応にします。常駐サーバー・MCP・追加のLLM APIキーは必要ありません。ブラウザー版Claude／ChatGPTは、各サービスの実行環境で生成・プレビュー確認まで動く場合だけ対応を検討する任意の試験対象です。試験ZIPの作成や登録だけでは対応済みになりません。

## 用意するもの

- Claude：`decksmith-vX.Y.Z-claude-skill-experimental.zip`
- ChatGPT：`decksmith-vX.Y.Z-chatgpt-plugin-experimental.zip`

通常版と同じ共通スキル・生成エンジンを含みます。Python／Node.js／LibreOffice／Popplerなどの実行環境は同梱しません。Windows PORTABLE版をクラウド実行環境へアップロードしないでください。

Claudeではコード実行を有効にし、Customize > Skillsのスキルアップロードで試験ZIPを選びます。ZIP直下はdecksmithフォルダーです。[公式の登録方法](https://support.claude.com/en/articles/12512180-use-skills-in-claude)。

ChatGPTではスキル入りプラグインとして登録します。利用可能なPlugin Creatorで、試験ZIP内のSKILL.md・references・scripts・assetsを保持するよう指定してください。プラグインZIPの取込機能が使える場合は、その取込経路を使います。通常の会話へZIPを添付しただけでは登録完了とは扱いません。登録方法・利用できるツールはアカウントと管理設定によります。[公式の作成方法](https://learn.chatgpt.com/docs/build-plugins)、[開発者向け取込・配布](https://developers.openai.com/plugins/guides/submit-claude-plugin)。公開申請はこの試験の対象外です。

## 最初の依頼

```text
DeckSmithのブラウザー試験をしてください。
references/browser-trial.mdを読み、まず実行環境を診断してください。
利用可能な日本語フォントで3枚の実行テストを行い、PPTX・PDF・全PNGを確認してください。
不足するソフトの取得や外部接続は、既に承認された範囲だけで行ってください。
環境の制約で動かない場合は理由を示して終了してください。
別エンジンやMCPへの切り替えは不要です。
```

生成・プレビューが動いた後、独自のbrief.mdとstyle.yamlでも試してください。固定テストは実行系の確認であり、任意のスタイル解釈や画像生成の合格を意味しません。

## 判定と停止条件

| 状態 | 判定 |
| --- | --- |
| ZIPを登録できた | 登録のみ成功、生成は未検証 |
| 診断でランタイムが不足 | 実行環境が不足。無断取得や代替はしない |
| PPTXだけ作れた | プレビュー試験は未完了 |
| PPTX・PDF・全PNGができた | 生成成功、視覚確認待ち |
| 全ページを確認し、独自原稿・スタイルでも完了 | そのサービス・モードでの試験成功 |
| ブラウザー操作・管理ポリシー・サインインが利用できない | 試験未実施。DeckSmithの非互換とは断定しない |

試験が困難ならブラウザー対応を見送り、[ローカル版の利用ガイド](USER_GUIDE.md)に戻ります。クラウドMCPの開発・ホスティング・公開は行いません。

## 開発側の生成・診断

```bash
python3 scripts/package_plugin.py --output dist/browser-trial --browser-trial
python3 skills/decksmith/scripts/doctor.py --renderer libreoffice
python3 skills/decksmith/scripts/smoke_test.py \
  --workspace /path/to/new-smoke-workspace --renderer libreoffice --font "利用可能な日本語フォント名"
```

smoke_test.pyは通信・インストールを行わず、既存の作業フォルダーを拒否します。結果はsmoke-result.jsonへ保存し、視覚合格は自動作成しません。失敗した方式をnoneへ切り替えません。生成が通ったら[品質検証](skills/decksmith/references/quality-gates.md)に従い、review_deck.pyでレビューと成果物の一致を確認してください。
