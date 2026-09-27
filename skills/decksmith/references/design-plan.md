# 資料ごとのデザイン方針

入力YAMLを構図プリセットへ分類しない。design-plan.yamlはAIがその依頼のために作る設計記録。利用者に書かせない。名前・色が同じだけで過去資料の構図を使い回さない。

## 設計時の判断

- YAMLと参考資料から、色以外の特徴を抽出する。文字の密度、線の質、素材の処理、重なり、余白、大小差など。実際に見た参考ページをfont_evidenceやvisual_checkに記録してよい。
- 各ページでまず「何を理解してほしいか」を決め、その内容を主役にする。章番号や年号が最大でよいのは、それ自体がメッセージの場合。主役が説明文に埋もれていないかを見る。
- 文字サイズをポイントの固定値だけで決めず、キャンバスに対する比率と鑑賞距離で決める。本文・ラベル・注釈は区別する。小さな文字を増やしてtext.amountを満たさない。画面掲載必須の内容は無断でノートに移動しない。
- 文字の太さ・幅・行間も設計する。日本語のグリフが使える書体を調べる。Windowsはdoctor --fontsで一覧を確認できるが、ウェイト・文字欠け・置換は描画で再確認する。フォントが違う場合は似た役割の代案と差を記録し、使えるからというだけで本文書体を見出しにも採用しない。
- 構図に必要な素材を先に決める。画像を後から空いた箱へ入れるだけにしない。提供・生成画像の必要性、切り抜きや透明背景、文字安全域を指定し、実物を見てから配置する。画像なしが明示された場合は尊重する。画像生成不能は画像なしの指定ではない。
- 編集可能な比較図や関係線は正確に設計する。装飾写真を粗い図形へ置き換えたものを同等の表現と称さない。図解を単純化するなら何を理解しやすくしたのか説明できるものにする。

## ファイル形式

次は構造の例でありデザインの既定値ではない。書体・数値・要素IDはその資料に合わせて決める。

```yaml
style_sha256: <style.yamlのSHA-256>
structure_sha256: <structure.yamlのSHA-256>
signatures:
  - source: /Typography/Heading
    intent: 元YAMLの見出しの表現意図
    visual_check: プレビューで何を見て達成を判断するか
font_evidence: 調べたフォント名・利用可否・代替の差。推測を実測と書かない
typography:
  heading:
    font: <確認した書体>
    min_size: 96
    reason: このキャンバス・内容・スタイルに対して決めた根拠
  body:
    font: <確認した書体>
    min_size: 40
    reason: 投影時の読みやすさを考慮
representative_slides: [opening]
slides:
  - id: opening
    focal_element: title
    focal_reason: この内容を最初に読ませる理由
    composition: 主役・説明・素材・余白の関係
    asset_decision: 素材の役割と入手手段。使わない場合は理由
```

signaturesは元YAMLの実在するsourceを参照する。typographyの役割はdisplay/heading/body/caption/labelから必要なものだけを定義し、sceneの各textにroleを付ける。min_sizeは96DPI px。slidesは全ページを同じ順序で記録。追加の設計メモは保持できる。planはsceneと同じフォルダーから自動読込、別名は--design-planで指定。

## 代表ページと反復

全体を詳細化する前に、構図・文字量・素材の扱いが異なる代表ページを選ぶ。通常は2〜3ページ、少数の資料なら全ページでもよい。ページ数を増やしたり、カタログを網羅するために不要ページを追加しない。

代表ページだけ先に描画する場合はprototype/へ独立したstructure/scene/planを作り、元のstyle.yamlをコピーする。各ファイルの正しい指紋を使う。完成資料用structureから必須内容を削って済ませない。未達要件を含む試作は--draftで生成し、納品しない。

代表ページを実際に見て、内容の主役・スタイルの特徴・判読性を修正してから全体へ展開する。単に大きくする、画像数を増やす、同じレイアウトを繰り返すだけにしない。プレビューが使えないnoneモードではこの視覚工程を実施したと書かない。

## 達成状態

requirements.statusは以下を区別する。

- implemented: 要件を実装。targetsが必要。見た目は別途レビューする。
- not_applicable: reasonとreason_kindが必要。reason_kindはmetadata/content_absent/catalog_not_selected/user_excluded。user_excludedには利用者の明示指定をapprovalへ記録する。任意カタログの不採用は許容するが、スタイルの主要特徴までまとめて除外しない。
- approved_alternative: 元指定とは異なる承認済みの代替。reason、targets、利用者の承認内容と出所をapprovalに記録。AIが承認を作らない。
- blocked / asset_pending: 未対応表現・不足素材。reasonを記録。--draftでのみ描画でき、最終レビューは合格できない。

古い台帳のnot_applicableには理由を読み直してreason_kindを追記する。自動で一律分類しない。元スタイル・構成が変わったら方針も再解釈する。
