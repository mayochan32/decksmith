# ブラウザー版の任意試験

ローカル版が主対応。ブラウザー版は必要なランタイムとプレビューを使える場合だけ試す。利用者のPCのPATH・フォント・ファイルへアクセスできると仮定しない。サーバーやAPIキーは要求しない。

## 最初の確認

1. スキルの登録／参照、Pythonの実行、Node.jsとPptxGenJS、LibreOfficeとpdftoppm、書き込み可能な作業先、PNGの視覚確認が利用可能か調べる。ホストが提供するランタイムを優先する。固定の開発者パスを使用しない。
2. `python3 <skill>/scripts/doctor.py --renderer libreoffice`を実行する。依存が足りなければ結果を示す。診断はインストールや通信を行わない。追加取得には共通の通信方針を適用し、明示的な承認がある範囲だけ実行する。使えない環境では試験を止め、ローカル版を案内する。
3. 診断が通れば `python3 <skill>/scripts/smoke_test.py --workspace <新しい作業フォルダー> --renderer libreoffice --font <利用可能な日本語フォント>`を実行する。PPTX・PDF・3枚のPNGと生成記録を確認する。これは固定の実行テストであり、任意のstyle.yamlの解釈能力や画像生成の試験ではない。
4. 3枚のPNGを個別に開いて本文・日本語・文字の切れ・配色を確認する。確認結果は共通の[品質検証](quality-gates.md)に従いreview.jsonへ記録し、review_deck.pyで納品物との一致を確認する。スクリプトは視覚合格を自動作成しない。
5. 次に利用者の原稿と独自のstyle.yamlで通常の制作手順を試す。固定テストだけでブラウザー対応済みと宣言しない。実行したサービス・モード・日付と、成功／失敗の段階を保存する。

未対応と未検証を区別する。サインイン・アップロード機能・管理ポリシー・ブラウザー操作ツールの問題は、DeckSmithの生成失敗とは別に記録する。失敗を理由にMCP導入・外部API・別生成エンジンへ切り替えない。PPTXのみの明示指定時はnoneを使用できるが、ブラウザー版のプレビュー試験成功には数えない。

## 試験用ZIP

- Claude：`decksmith-vX.Y.Z-claude-skill-experimental.zip`。ZIP直下はdecksmith/SKILL.mdを含むスキルフォルダー。
- ChatGPT：`decksmith-vX.Y.Z-chatgpt-plugin-experimental.zip`。スキル入りプラグイン。ローカル導入とWebへの登録は別経路であり、通常の会話へのZIP添付だけでプラグインが登録されると説明しない。利用可能なPlugin Creatorまたは公式のスキル入りプラグイン取込経路で検証する。公開申請・一般公開は別の作業。

依存ランタイムは同梱しない。node_modulesやOS専用のPORTABLEランタイムをアップロードしない。登録・実行機能の利用条件は各アカウント／管理設定による。
