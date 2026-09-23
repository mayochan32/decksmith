# DeckSmith

任意のスタイルYAMLをAIが解釈し、ページごとに設計して編集可能なPowerPointを作るプラグインです。名前付きのスタイルプリセットは持ちません。

初めて使う方は **[利用ガイド：VS CodeのCodex／Claude Codeから使う](USER_GUIDE.md)** を参照してください。導入、スタイルYAMLの用意、依頼例、画像生成、修正方法を説明しています。

## 生成の仕組み

利用者が題材・構成・スタイルを指定すると、プラグインのSkillを読むAIが内容を整理し、画像素材と各要素の配置を設計します。描画処理は、その設計を文字・画像・図形・パスとしてPPTXへ変換します。スタイル名による固定構図の選択は行いません。

意味解釈はホストのAIが行います。Pythonを単独で実行して自由記述YAMLからデザインを推論する製品ではありません。配布物にはAIの制作手順、シーン仕様、描画処理、検証処理を含めます。

## 利用環境

Python 3.9+、Node.js 18+を使用します。PPTX描画はPptxGenJS、プレビューはLibreOfficeとPopplerです。OpenAI専用ライブラリは不要です。画像生成は利用可能なホスト機能または許可された外部サービスに接続し、結果のPNG/JPEGを取り込みます。各社の画像APIを自動で呼ぶ機能はまだありません。

Codex、Claude Code、Gemini CLI用のマニフェストを用意し、共通のSkillとエンジンを配布します。ブラウザー版への直接導入は対象外。Claude Code・Gemini CLI内での一連の制作は未検証です。

YAMLの読み取りには同梱のPyYAML 6.0.3（純Python版、MIT）を使うため、ホストへの追加インストールは不要です。

## 開発

AIが用意する資料プロジェクトはstyle.yaml（元の指定）、structure.yaml（内容）、scene.yaml（設計）、assets/（資料専用素材）です。仕様は[シーン仕様](skills/decksmith/references/deck-spec.md)を参照してください。

```bash
npm ci --prefix skills/decksmith --ignore-scripts --no-audit --no-fund
python3 skills/decksmith/scripts/doctor.py
python3 skills/decksmith/scripts/create_deck.py \
  --scene project/scene.yaml --style project/style.yaml \
  --structure project/structure.yaml --output project/output/deck.pptx
```

実行ファイルはPATHで検出します。任意でDECKSMITH_NODE、DECKSMITH_NODE_MODULES、DECKSMITH_SOFFICE、DECKSMITH_PDFTOPPMを指定できます。詳細は[実行環境](skills/decksmith/references/host-runtime.md)を参照。

配布物は次のように作成します。hostはcodex、claude、geminiから選びます。開発用のサンプル、旧エンジン、node_modulesは含めません。依存は固定バージョンのロックファイルから導入します。

```bash
python3 scripts/package_plugin.py --host claude --output dist/claude
```

PPTXとプレビュー、未確認状態のレビュー台帳を出力します。成功終了は視覚品質の合格を意味しません。AIがすべてのページを確認して修正します。

## 現在の範囲

新しいシーン方式の初期実装です。文字の部分強調、要素別の書体、任意配置、回転、重なり、画像、基本図形、直線パスを扱います。専用のネイティブ表・グラフ要素やマスクは未実装で、未対応の指定を黙って置換せずエラーにします。

旧layout/composition形式は廃止しました。過去の制作物は残しますが、配布プラグインから呼び出しません。参考サンプルは評価用であり、実行時のプリセットではありません。
