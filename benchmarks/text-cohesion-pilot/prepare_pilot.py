"""Recreate one supplied reference as an editable text-cohesion study, not a preset."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

COPY = {
    'edition': '05 — PARTNERSHIP',
    'title': 'サステナブルな未来を\n共に創る、長期の\n変革パートナーへ',
    'purpose-label': 'FUJITSU PURPOSE',
    'purpose': 'イノベーションによって社会に信頼をもたらし、世界をより持続可能にしていく',
    'purpose-detail': '受発注の関係を超えて顧客と共に社会的価値と企業価値を両立させます。',
    'model-label': 'パーパスドリブンな協業モデル',
    'model': '企業の成長（売上・効率）とESG/サステナビリティ（環境・社会性）の両立支援',
    'ecosystem-label': 'オープンエコシステム',
    'ecosystem': 'グローバルメガクラウドや先端スタートアップ、学術機関との連携プラットフォーム',
    'next-label': 'NEXT STEP',
    'next': '単なるITベンダーではなく、次の10年のビジネスモデルを共に描くパートナーとして、まずはPoC・ディスカッションからスタートしましょう',
}
STYLE = {'色と書体': '淡いグレー背景、青い太字の主張。Hiragino Sansを使用する。',
         '見出し': '大見出しは3行を一まとまりとし、行間より他ブロックとの余白を大きくする。',
         '情報のまとまり': '見出し、パーパス、協業の説明と次の行動の3段。下部3項目の上端を揃える。'}


def save(path, data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scene():
    es=[]; blue='#2055A0'
    def text(eid,x,y,w,h,size,role='body',color=blue,bold=False,align='left',vertical='top',spacing=1.15):
        display={'model':'企業の成長（売上・効率）と\nESG/サステナビリティ\n（環境・社会性）の両立支援',
                 'ecosystem':'グローバルメガクラウドや\n先端スタートアップ、学術機関との\n連携プラットフォーム',
                 'next':'単なるITベンダーではなく、\n次の10年のビジネスモデルを\n共に描くパートナーとして、\nまずはPoC・ディスカッションから\nスタートしましょう'}.get(eid,COPY[eid])
        es.append(dict(id=eid,type='text',text=display,x=x,y=y,width=w,height=h,font='Hiragino Sans',
                       size=size,role=role,color=color,bold=bold,align=align,vertical=vertical,line_spacing=spacing))
    def rect(eid,x,y,w,h,fill='none',stroke=blue,radius=0):
        es.append(dict(id=eid,type='shape',geometry='roundRect' if radius else 'rect',x=x,y=y,width=w,height=h,
                       fill=fill,stroke=stroke,stroke_width=2 if stroke!='none' else 0,radius=radius))
    rect('edition-box',80,44,310,46,radius=23)
    text('edition',90,48,290,36,22,'label',bold=True,align='center',vertical='middle')
    text('title',80,124,1440,280,88,'heading',bold=True,spacing=1.0)
    rect('purpose-box',80,476,260,44,fill=blue,stroke='none',radius=22)
    text('purpose-label',88,480,244,36,22,'label',color='#FFFFFF',bold=True,align='center',vertical='middle')
    text('purpose',370,475,1150,44,28,'label',bold=True)
    text('purpose-detail',370,528,1150,42,25,color='#222222')
    rect('separator',80,587,1440,1,fill='#2055A050',stroke='none')
    for name,x in [('model',80),('ecosystem',570)]:
        rect(name+'-box',x,628,440,46,radius=23)
        text(name+'-label',x+12,633,416,36,24,'label',bold=True,align='center',vertical='middle')
        text(name,x,695,440,138,25,color='#222222',spacing=1.25)
    rect('next-panel',1060,609,460,262,fill=blue,stroke='none',radius=28)
    rect('next-box',1084,628,196,46,stroke='#FFFFFF',radius=23)
    text('next-label',1094,633,176,36,22,'label',color='#FFFFFF',bold=True,align='center',vertical='middle')
    text('next',1084,695,412,160,24,color='#FFFFFF',bold=True,spacing=1.05)
    return dict(id='partnership',background='#E9E8E2',elements=es)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-root',required=True,type=Path)
    p.add_argument('--skill-directory',type=Path,default=Path(__file__).resolve().parents[2]/'skills/decksmith')
    a=p.parse_args();root=a.output_root.resolve();root.mkdir(parents=True,exist_ok=False);s=root/'setting';s.mkdir()
    save(s/'style.yaml',STYLE)
    save(s/'structure.yaml',dict(slides=[dict(id='partnership',purpose='主張とその根拠、次の行動をまとまりとして示す',required_text=list(COPY.values()),
        notes='利用者のスクリーンショットを参照した再構成。元PPTXとフォントは未確認。')]))
    (s/'brief.md').write_text('参照画像から転記。見出しの3行、パーパス、下部3項目の文章を全て画面に保持。\n\n'+'\n\n'.join(COPY.values()),encoding='utf-8')
    save(s/'decksmith.yaml',dict(slide=dict(width_px=1600,height_px=900,aspect_ratio='16:9'),privacy=dict(mode='restricted'),
        input=dict(style='style.yaml',brief='brief.md'),output=dict(directory='../output',filename='partnership.pptx',pdf=True,renderer='libreoffice'),
        images=dict(mode='provided_only',amount='none',type='auto',color='color',plan='show'),language='日本語',text=dict(amount='normal')))
    (s/'text-plan.md').write_text('1ページnormal。参照画像の全11文字要素を保持。大見出しは単一の複数行テキスト。',encoding='utf-8')
    (s/'image-plan.md').write_text('画像なし。編集可能な図形と文字で再構成。',encoding='utf-8')
    workflow=a.skill_directory.resolve()/'scripts/workflow.py'
    for args in (['prepare','--image-capability','unverified'],['freeze-content','--brief','brief.md']):
        subprocess.run([sys.executable,str(workflow),args[0],'--project',str(s)]+args[1:],check=True)
    hashes=dict(style_sha256=sha(s/'style.yaml'),structure_sha256=sha(s/'structure.yaml'))
    save(s/'scene.yaml',dict(schema_version='1.0',canvas=dict(width=1600,height=900),**hashes,
        requirements=[dict(source='/'+k,interpretation=v,status='implemented',targets=['partnership/'+eid for eid in targets])
          for (k,v),targets in zip(STYLE.items(),[['title','purpose','next'],['title'],['purpose-label','purpose','model-label','ecosystem-label','next-label']])],slides=[scene()]))
    save(s/'design-plan.yaml',dict(**hashes,signatures=[dict(source='/'+k,intent=v,visual_check=v+' 実際の字面と余白を確認。') for k,v in STYLE.items()],
        font_evidence='MacのHiragino Sansを使用。元画像の正確なフォントは不明。再生成時に利用可能な書体とウェイトを確認する。',
        typography={r:dict(font='Hiragino Sans',min_size=z,reason='見出し・ラベル・説明の階層を分ける') for r,z in [('heading',88),('label',22),('body',24)]},
        representative_slides=['partnership'],slides=[dict(id='partnership',focal_element='title',focal_reason='長期の変革パートナーという主張',
        composition='大見出し3行を一つの文字枠にする。主張→パーパス→協業と次の行動の順。各まとまりの外側に余白を取り、下部のラベルと本文の上端を揃える。',
        asset_decision='参照画像の文章を編集可能な文字と図形で再構成。画像は使わない。')]))
    print(root)

if __name__=='__main__': main()
