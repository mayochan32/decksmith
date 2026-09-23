# DeckSmith v0.5.0

## v0.4.0からの追加機能

decksmith.yamlに画像の制作方針と生成前計画の設定を追加しました。

```yaml
images:
  mode: auto
  amount: normal
  type: auto
  color: color
  plan: show
```

- amount: normal / more / less / none（普通・多め・少なめ・画像なし）
- type: auto / illust / photo / icon / anime
- color: color / gray / monotone
- plan: show / confirm / skip（提示して続行・承認待ち・提示省略）

プロンプトの「画像多め」「白黒のイラスト」などもAIが解釈します。brief.mdのページ別画像指定を全体設定より優先しますが、privacyとprovided_onlyの制約は維持します。

AIは画像制作前にimage-plan.mdを作成します。confirmでは計画への承認を待ってから制作します。画像量・作風の判断や承認待ちはAIの制作手順であり、描画エンジンが会話や画像の意味を自動判定する機能ではありません。

## 配布ZIPと更新

Assetsから利用環境に合うdecksmith-v0.5.0-codex.zip、decksmith-v0.5.0-claude.zip、decksmith-v0.5.0-gemini.zipを取得してください。VERSIONとUSER_GUIDE.mdを同梱しています。

既存のSkillを探索対象の外へバックアップし、同梱ガイドに従って新版を配置してください。自動上書きはしません。配置後に依存ライブラリを導入し、create_deck.py --versionでDeckSmith v0.5.0を確認できます。既存の設定ファイルはそのまま使用でき、新項目は既定値で補われます。

## 検証と制約

自動テスト39件成功。新設定の受理・拒否・既定値、PPTX生成と生成記録への設定保存、配布物の移動後の実行を確認しました。VS Code両拡張・Gemini CLIでの一連の制作、およびWindows／Linuxの実機確認は未完了です。外部サービス制限はネットワーク遮断機構ではありません。
