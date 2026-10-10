"""Reproduce communication design pilot inputs; not a layout selector or reviewer."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


PAGES = [
    dict(id="statement", purpose="運用案の中心となる変更を一文で示す", required_text=[
        "担当を決める場所を、一つに。", "受付が担当を割り当て、対応履歴を残す。",
        "これは架空の運用案です。効果は試行で検証します。"]),
    dict(id="comparison", purpose="同じ三つの観点で現状と試行案を比較する", required_text=[
        "変えるのは、担当の決め方。", "現状", "試行案", "窓口", "割当", "記録",
        "各担当へ直接", "受付へ一本化", "受信した人が探索", "受付が決定",
        "担当ごとのメモ", "共通の対応履歴", "応答時間の短縮は、まだ実証していません。"]),
    dict(id="feedback", purpose="未解決時だけ受付へ戻る経路を示す", required_text=[
        "未解決の案件だけ、受付へ戻す。", "受付", "担当へ割当", "担当", "対応・記録",
        "完了", "履歴を保存", "解決したとき", "未解決のとき",
        "完了した案件は、この運用では受付へ戻しません。"]),
    dict(id="criteria", purpose="独立した六つの条件を欠落なく示す", required_text=[
        "試行前に、6つの条件を揃える。", "受付担当", "窓口の責任者を決める",
        "受付時間", "対応する時間帯を決める", "記録項目", "必須の記録項目を決める",
        "引継ぎ先", "不在時の引継ぎ先を決める", "差戻し条件", "未解決の判断基準を決める",
        "見直し日", "試行を振り返る日を決める", "6項目は独立した確認条件です。順序や優先順位を表していません。"]),
]

COMMUNICATION = [
    dict(audience_question="運用の何を変えるのか", takeaway=PAGES[0]["required_text"][0],
         relationship="関係図なし", source_basis="原稿 statement",
         representation_reason="短い主張と補足だけで伝わるため、図解を足さない",
         reading_order="主張→割当と履歴→試行である条件", avoid_misreading="効果を実証済みとしない"),
    dict(audience_question="現状と試行案のどこが違うのか", takeaway=PAGES[1]["required_text"][0],
         relationship="窓口・割当・記録についての対応比較", source_basis="原稿 comparison",
         representation_reason="同じ三つの観点の位置と文字階層を揃える",
         reading_order="主張→現状と試行案の対応→未実証の条件", avoid_misreading="測定していない時間短縮を数値化しない"),
    dict(audience_question="いつ、どこへ戻るのか", takeaway=PAGES[2]["required_text"][0],
         relationship="受付→担当→完了。担当から受付へ戻るのは未解決時のみ", source_basis="原稿 feedback",
         representation_reason="通常経路と条件付き戻りをラベルと向きで区別",
         reading_order="主張→通常経路→条件付き差し戻し", avoid_misreading="完了から受付への循環はない"),
    dict(audience_question="試行前に何を決めるのか", takeaway=PAGES[3]["required_text"][0],
         relationship="六つの独立条件", source_basis="原稿 criteria",
         representation_reason="同等の文字階層で六項目を保持し、接続線を付けない",
         reading_order="主張→各条件の名前と説明→独立である注記", avoid_misreading="3項目への削減や優先順位を作らない"),
]

STYLES = {
    "paper": {
        "紙面": "温かい白 #F5F1E8 を背景、本文は #292C29。余白を広く取る。",
        "見出しの声": "Hiragino Mincho ProNの明朝。大きな日本語を左揃え。",
        "説明の声": "Hiragino Sans。役割によって本文とラベルの大きさを分ける。",
        "効かせ方": "朱色 #AC3F2A を主張と変更点に使う。色だけに意味を預けない。",
        "組み方": "比較は左右に対応、処理は左から右。線は細く、箱の塗りで埋めない。",
    },
    "night": {
        "地と文字": "濃紺 #10272D、文字は #E9F0EA。淡い青緑 #85DCC6 を強調に使う。",
        "文字の設計": "Hiragino Sans。見出しを太く、短い主張のページは右揃え。",
        "対比の組み方": "現状と試行案を上下に並べ、窓口・割当・記録を横方向に揃える。",
        "経路の組み方": "受付から担当へ下り、完了は右。戻り線は通常経路の外側へ。",
        "条件の組み方": "六条件を3列2段で等価に見せる。見出しと細い枠を使い、番号を付けない。",
    },
}


def save(path, value):
    with path.open("x", encoding="utf-8") as out:
        out.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def author_scene(mode):
    """Coordinates authored for these four pages only, not chosen by topic/type."""
    paper = mode == "paper"
    bg, ink, accent, muted = ("#F5F1E8", "#292C29", "#AC3F2A", "#62655E") if paper else (
        "#10272D", "#E9F0EA", "#85DCC6", "#AAC0C1")
    heading = "Hiragino Mincho ProN" if paper else "Hiragino Sans"
    slides = []
    elements = []

    def text(id_, value, x, y, w, h, size=44, role="body", color=None, align="left"):
        elements.append(dict(id=id_, type="text", text=value, x=x, y=y, width=w, height=h,
                             font=heading if role in ("heading", "display") else "Hiragino Sans",
                             size=size, role=role, color=color or ink, align=align,
                             bold=not paper and role in ("heading", "display")))

    def rect(id_, x, y, w, h, fill="none", stroke=None):
        elements.append(dict(id=id_, type="shape", geometry="rect", x=x, y=y, width=w,
                             height=h, fill=fill, stroke=stroke or muted, stroke_width=2))

    def line(id_, pts, color=None, closed=False, fill="none"):
        xs, ys = zip(*pts)
        x, y = min(xs), min(ys)
        elements.append(dict(id=id_, type="path", x=x, y=y,
                             width=max(max(xs)-x, 1), height=max(max(ys)-y, 1),
                             points=[[a-x, b-y] for a, b in pts], closed=closed,
                             stroke=color or muted, stroke_width=3, fill=fill))

    def arrow(id_, pts, color=None):
        line(id_, pts, color)
        ax, ay = pts[-2]; bx, by = pts[-1]
        dx, dy = bx-ax, by-ay
        length = (dx*dx+dy*dy)**.5
        ux, uy = dx/length, dy/length
        line(id_+"-head", [(bx,by), (bx-ux*17-uy*9,by-uy*17+ux*9),
                             (bx-ux*17+uy*9,by-uy*17-ux*9)], color, True, color or muted)

    def start(n):
        nonlocal elements
        elements = []
        text("edition", "問い合わせ対応 / 試行案", 120, 62, 1300, 55, 30, "caption", muted)
        text("page", f"{n+1:02d} / 04", 1640, 62, 160, 55, 30, "caption", muted, "right")
        line("top-rule", [(120,132),(1800,132)], muted)

    def finish(n):
        slides.append(dict(id=PAGES[n]["id"], background=bg, elements=elements))

    # Short message: no diagram.
    start(0)
    text("title", "担当を決める場所を、\n一つに。", 140, 292, 1630, 310,
         116 if paper else 110, "display", accent, "left" if paper else "right")
    text("statement-body", PAGES[0]["required_text"][1], 150 if paper else 650, 655,
         1120, 80, 44, align="left" if paper else "right")
    text("caveat", PAGES[0]["required_text"][2], 150, 940, 1620, 60, 30, "caption", muted)
    finish(0)

    # Comparison: columns on paper, rows on night. Identical content.
    start(1)
    text("title", PAGES[1]["required_text"][0], 120, 180, 1680, 125, 80, "heading")
    labels = ["窓口", "割当", "記録"]
    old = ["各担当へ直接", "受信した人が探索", "担当ごとのメモ"]
    new = ["受付へ一本化", "受付が決定", "共通の対応履歴"]
    if paper:
        text("old-heading", "現状", 440, 335, 600, 70, 48, "label", muted)
        text("new-heading", "試行案", 1130, 335, 650, 70, 48, "label", accent)
        for i, y in enumerate([460,610,760]):
            text(f"label-{i}", labels[i], 140, y+3, 260, 70, 36, "label", muted)
            text(f"old-{i}", old[i], 440, y, 620, 80, 44)
            text(f"new-{i}", new[i], 1130, y, 660, 80, 44, color=accent)
            line(f"row-{i}", [(140,y+107),(1790,y+107)], muted)
    else:
        for i,x in enumerate([435,905,1375]):
            text(f"label-{i}", labels[i], x, 355, 410, 65, 34, "label", muted)
        for name, vals, y, color in [("old",old,490,ink),("new",new,730,accent)]:
            rect(name+"-row",120,y-45,1680,180,stroke=muted if name=="old" else accent)
            text(name+"-heading", "現状" if name=="old" else "試行案", 158,y,230,80,44,"label",color)
            for i,x in enumerate([435,905,1375]):
                text(f"{name}-{i}",vals[i],x,y,410,90,40,color=color)
    text("caveat", PAGES[1]["required_text"][-1], 140, 960, 1650, 60, 30, "caption", muted)
    finish(1)

    # Only the unresolved path returns. No edge from completion to reception.
    start(2)
    text("title", PAGES[2]["required_text"][0],120,180,1680,125,80,"heading")
    nodes = [("intake","受付","担当へ割当"),("owner","担当","対応・記録"),("done","完了","履歴を保存")]
    coords = [(220,465),(810,465),(1400,465)] if paper else [(350,360),(350,665),(1300,665)]
    for (id_,name,detail),(x,y) in zip(nodes,coords):
        rect(id_+"-box",x,y,330 if paper else 440,175,stroke=accent if id_=="intake" else muted)
        text(id_+"-name",name,x+32,y+25,270 if paper else 380,75,52,"label",accent if id_=="intake" else ink)
        text(id_+"-detail",detail,x+32,y+110,275 if paper else 380,50,32,"body",muted)
    if paper:
        arrow("assign",[(560,548),(797,548)],ink)
        arrow("complete",[(1155,548),(1388,548)],ink)
        text("complete-condition","解決したとき",1150,460,250,65,32,"label",muted,"center")
        arrow("return",[(975,655),(975,808),(385,808),(385,655)],accent)
        text("return-condition","未解決のとき",520,740,370,60,38,"label",accent,"center")
    else:
        arrow("assign",[(570,550),(570,650)],ink)
        arrow("complete",[(805,750),(1284,750)],ink)
        text("complete-condition","解決したとき",850,668,400,65,36,"label",muted,"center")
        arrow("return",[(338,752),(180,752),(180,448),(338,448)],accent)
        text("return-condition","未解決のとき",225,567,300,65,32,"label",accent)
    text("caveat",PAGES[2]["required_text"][-1],140,960,1650,60,30,"caption",muted)
    finish(2)

    # Six equal conditions: no implied hierarchy, order or causal arrows.
    start(3)
    text("title",PAGES[3]["required_text"][0],120,180,1680,125,80,"heading")
    items = list(zip(PAGES[3]["required_text"][1:-1:2],PAGES[3]["required_text"][2:-1:2]))
    for i,(name,detail) in enumerate(items):
        if paper:
            x=140+(i%2)*860; y=385+(i//2)*180
            line(f"condition-mark-{i}",[(x,y+6),(x,y+109)],accent)
            text(f"condition-name-{i}",name,x+30,y,715,60,42,"label",accent)
            text(f"condition-detail-{i}",detail,x+30,y+70,715,70,38)
        else:
            x=120+(i%3)*570; y=390+(i//3)*260
            rect(f"condition-box-{i}",x,y,535,215,stroke=muted)
            text(f"condition-name-{i}",name,x+32,y+30,475,65,44,"label",accent)
            text(f"condition-detail-{i}",detail,x+32,y+121,475,65,34)
    text("caveat",PAGES[3]["required_text"][-1],140,960,1650,60,30,"caption",muted)
    finish(3)
    return slides


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root",required=True,type=Path)
    parser.add_argument("--skill-directory",type=Path,default=Path(__file__).resolve().parents[2]/"skills/decksmith")
    args=parser.parse_args()
    root=args.output_root.resolve()
    root.mkdir(parents=True,exist_ok=False)
    workflow=args.skill_directory.resolve()/"scripts/workflow.py"
    for mode,style in STYLES.items():
        p=root/mode/"setting";p.mkdir(parents=True)
        save(p/"style.yaml",style)
        save(p/"structure.yaml",dict(slides=PAGES))
        brief="架空の問い合わせ運用案。効果の数値は未測定。以下を全て画面に保持する。\n\n"
        for page in PAGES:
            brief+=f"## {page['id']}\n目的：{page['purpose']}\n"+"\n".join(page["required_text"])+"\n\n"
        (p/"brief.md").write_text(brief,encoding="utf-8")
        save(p/"decksmith.yaml",dict(slide=dict(width_px=1920,height_px=1080,aspect_ratio="16:9"),
             privacy=dict(mode="restricted"),input=dict(style="style.yaml",brief="brief.md"),
             output=dict(directory="../output",filename=f"{mode}.pptx",pdf=True,renderer="libreoffice"),
             images=dict(mode="provided_only",amount="none",type="auto",color="color",plan="show"),
             language="日本語",text=dict(amount="normal")))
        (p/"text-plan.md").write_text("全4ページnormal。brief.mdの各節の表示文をそのまま必須内容に固定。ノートへの移動なし。\n",encoding="utf-8")
        (p/"image-plan.md").write_text("全4ページ：画像なし。主張・比較・処理経路・確認条件をネイティブ文字と図形で示す試作。\n",encoding="utf-8")
        subprocess.run([sys.executable,str(workflow),"prepare","--project",str(p),"--image-capability","unverified"],check=True)
        subprocess.run([sys.executable,str(workflow),"freeze-content","--project",str(p),"--brief","brief.md"],check=True)
        style_sha, structure_sha=sha(p/"style.yaml"),sha(p/"structure.yaml")
        # The argument is an authored fixture name, never a user-facing style classifier.
        slides=author_scene(mode)
        headings=[f"{pg['id']}/title" for pg in PAGES]
        evidence_targets = ([
            ["statement/title", "comparison/old-0", "criteria/condition-detail-0"],
            headings,
            ["statement/statement-body", "comparison/label-0", "feedback/intake-detail"],
            ["statement/title", "comparison/new-heading", "feedback/return", "criteria/condition-name-0"],
            ["comparison/old-0", "comparison/new-0", "comparison/row-0", "feedback/assign", "feedback/complete"],
        ] if mode=="paper" else [
            ["statement/title", "statement/statement-body", "feedback/return"],
            headings+["statement/statement-body"],
            ["comparison/old-row", "comparison/new-row", "comparison/old-0", "comparison/new-0"],
            ["feedback/assign", "feedback/complete", "feedback/return", "feedback/return-condition"],
            [f"criteria/condition-box-{i}" for i in range(6)],
        ])
        reqs=[dict(source="/"+key,interpretation=value,status="implemented",targets=targets)
              for (key,value),targets in zip(style.items(),evidence_targets)]
        save(p/"scene.yaml",dict(schema_version="1.0",canvas=dict(width=1920,height=1080),style_sha256=style_sha,
             structure_sha256=structure_sha,requirements=reqs,slides=slides))
        heading="Hiragino Mincho ProN" if mode=="paper" else "Hiragino Sans"
        typo={role:dict(font=heading if role in ("heading","display") else "Hiragino Sans",min_size=size,
              reason="1920×1080の試作で役割を分けて実画像を確認する") for role,size in
              [("display",110),("heading",80),("body",32),("label",32),("caption",30)]}
        save(p/"design-plan.yaml",dict(style_sha256=style_sha,structure_sha256=structure_sha,
             signatures=[dict(source="/"+k,intent=v,visual_check=v+" 実PNGで文字・配置・線を確認する。") for k,v in style.items()],
             font_evidence="初回試作（2026-10-10、Mac）ではfc-matchでHiragino Mincho ProN W3とHiragino Sans W4を確認。再生成する環境では書体・ウェイトの実在を再確認し、描画後に日本語と置換を点検する。",
             typography=typo,representative_slides=[p["id"] for p in PAGES],
             slides=[dict(id=pg["id"],focal_element="title",focal_reason=c["takeaway"],
                 composition=c["representation_reason"]+"。"+c["reading_order"],
                 asset_decision="画像なしの試作。全てネイティブ文字・図形・関係線。",communication=c)
                 for pg,c in zip(PAGES,COMMUNICATION)]))
    print(root)


if __name__=="__main__":
    main()
