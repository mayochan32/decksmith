# 制作補助（全ホスト共通）

同梱版は `decksmith.cmd <操作>`、通常版は `python3 <skill>/scripts/workflow.py <操作>`。標準構成では `<project>` は `my-presentations/setting`。原稿・設定・制作中の内部ファイルはこの中、最終PPTX・PDF・プレビューは同列の `my-presentations/output`（設定の `output.directory: ../output`）へ保存する。以下はローカル処理のみ。承認・意味解釈・視覚判断を自動生成しない。

## 開始時の設定

`prepare --project <project> --image-capability available`

機能未確認ならunverified、利用不可ならunavailable。--configでAIが解決した設定、--destinationで新しい保存名を指定可能。既定はdecksmith.resolved.yamlとdecksmith.resolved.policy.json。後続buildは必ず `--config decksmith.resolved.yaml` を指定。noticeをチャットへ示し、確認済みの機能状態も伝える。プロンプト由来の変更は--source-evidenceに実際の指示を記録する。既存設定は上書きしない。

policy記録のapprovals/usage/image_fallbacksは初期は空。実際の回答・操作だけを追記する。承認を創作しない。

- approvals: `[{id, purpose, destination, data, human_evidence, approved_at, restricted_exception}]`
- usage: `[{kind, approval_id, purpose, destination, data, used_at}]`
- image_fallbacks: `[{choice, reason, human_evidence, slides, prompt, box, text}]`

kindはweb_search/external_service/host_image_generation/local。外部操作のpurpose/destination/dataは承認された目的・利用先・送信情報の範囲と一致させる。時刻はタイムゾーン付きISO形式（例2026-09-28T10:00:00+09:00）で承認が実行より前であること。restrictedの例外はその明示承認を得てrestricted_exception=trueにする。通常の画像計画の承認で代用しない。ホスト画像生成とlocalは外部承認フィールド不要。

画像代案choiceはomitまたはplaceholder。slidesは対象スライドID配列。placeholderのbox/textはそれぞれ四角とプロンプト文字のslideID/elementID。promptは四角内に表示する画像生成指示。omitではbox/text/prompt不要。理由と実際の回答根拠は両方で必須。

prepareのpolicyは許可条件の記録であって、実施済み・承認済みの証明ではない。buildで整合性を検査してコピーするが、実際の会話・ツール履歴との照合は最終レビューが必要。旧入力も描画できるが、新規制作では必ずprepareを使う。

## 原稿の必須内容を先に固定

原稿から指定言語・文字量を適用してstructure.yamlを作成し、scene設計前に:

`freeze-content --project <project> --brief brief.md`

プロンプトだけの場合も原文をローカルに保存する。content-contract.jsonは原稿指紋と必須文字列を保持し、既存基準を上書きしない。原稿のどの主張・数値・条件に対応するかtext-plan.mdに記録。sceneの全テキストから基準を作ると検査が循環するため禁止。

後から言い換え・翻訳する場合はcontent-changes.jsonへ `{"changes":[{"slide":"s01","original":"元の必須文字列","replacement":"変更後","reason":"変更理由","source_evidence":"原稿上の根拠"}]}` を記録する。意味の変更・削除には人間の確認も必要。元基準は消さない。原稿自体が変わる場合は新しい制作フォルダーで再解釈・基準作成し、指紋だけ更新しない。

buildは必須文字列（または根拠付き置換後）が編集可能テキストに残るか検査する。意味の同等性は自動判定しない。review.jsonのsource_content_evidenceに原稿・基準・変更記録を独立に照合した結果を残す。

## 代表ページの試作

`prototype --project <project> --config decksmith.resolved.yaml --destination prototype-01 --slides opening comparison`

scene/structure/design-plan/style、必要画像、独立基準を新規フォルダーへ取り出す。参照・順序・指紋を整合させ、本番は変更しない。試作外の要件はblockedとし試作だけで完成扱いしない。試作側を `build --draft` で生成する。別の試作は別フォルダーへ。この操作は通信の許可を与えない。

## 修正後の比較・納品

`compare --project <project> --previous ../output/deck.pptx --output ../output/deck-002.pptx`

通常版workflow.pyのcompareは--project不要（パスを直接指定）。PPTXとPNGの指紋を照合しchanged/unchanged/removedを返す。changedは個別に再確認、unchangedは同一画像の確認記録を引き継げるが、全体の順序・内容・スタイル要件は再確認する。自動でpassedにしない。

レビュー対象はbuildが返したoutputを使用し、連番最大だから完成と判断しない。review結果を確認しDELIVERY.mdへ納品対象を明記する。policy記録がある場合はreview.jsonのpolicy_evidenceへ実際の利用と承認の照合結果を書く。プレースホルダー納品はdelivery_status=awaiting_imagesとし、review結果もawaiting_images。noneは見た目未確認のまま。
