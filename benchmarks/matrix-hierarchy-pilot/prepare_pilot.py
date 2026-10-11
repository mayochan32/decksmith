"""Reconstruct a supplied matrix reference with reserved axis space and text hierarchy."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

COPY = {
 'edition':'02  /  UVANCE / DIRECTION',
 'title':'個別受託から『社会課題解決の標準化』へ',
 'brand':'Fujitsu Uvance',
 'summary':'4つの業界課題 × 3つの横断ケイパビリティを共通モデル化。グローバルの知見を、短期間で実装する。',
 'old-label':'従来のSI', 'old':'要件定義から数年\n個別スクラッチ開発',
 'new-label':'UVANCE', 'new':'ベストプラクティスを\n共通化\n迅速に課題へ対応',
 'column-axis':'4 VERTICALS  /  社会・業界課題',
 'row-axis':'3つの\n横断ケイパビリティ',
 'domain-0':'持続可能な\n製造', 'domain-1':'リテール\n体験', 'domain-2':'健全な\n生活', 'domain-3':'信頼ある\n社会',
 'cap-0':'デジタルシフト', 'cap-1':'業務変革', 'cap-2':'ハイブリッドIT',
 'outcomes-label':'OUTCOMES', 'outcome-0':'ESG/CO2排出量可視化', 'outcome-1':'サプライチェーン寸断リスク低減',
}
STYLE={'色と書体':'赤・黒・温かい白と薄い背景グリッド。主張はHiragino Sans W9、説明はHiragino Sans。',
       '階層':'主張を最大・極太、成果を次に大きく、図のラベルと説明を補助とする。OUTCOMESの英語見出しより成果の中身を強くする。',
       '関係図':'4列×3行と赤黒の丸の配置を保持。軸見出しは表の外の専用領域に水平配置し、他の図形と接触させない。'}


def save(p,data): p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def scene():
 es=[];red='#D12B1A';black='#151515';paper='#F3F1E9'
 def box(eid,x,y,w,h,fill='none',stroke='none',weight=1,geometry='rect'):
  es.append(dict(id=eid,type='shape',geometry=geometry,x=x,y=y,width=w,height=h,fill=fill,stroke=stroke,stroke_width=weight))
 def text(eid,x,y,w,h,size,role='label',color=black,bold=True,align='left',vertical='top',spacing=1.05):
  es.append(dict(id=eid,type='text',text=COPY[eid],x=x,y=y,width=w,height=h,font='Hiragino Sans W9' if role=='heading' else 'Hiragino Sans',
                 size=size,role=role,color=color,bold=False if role=='heading' else bold,align=align,vertical=vertical,line_spacing=spacing))
 for x in range(60,1600,80):box(f'grid-x-{x}',x,0,1,900,fill='#2929290C')
 for y in range(60,900,80):box(f'grid-y-{y}',0,y,1600,1,fill='#2929290C')
 text('edition',60,24,1480,32,22,color=red)
 text('title',60,78,1480,76,52,'heading',red)
 text('brand',60,155,1480,40,26,color=red)
 text('summary',60,214,1480,46,25,'body',bold=False)
 text('column-axis',665,275,870,35,23,color=red)
 text('row-axis',400,296,240,70,23,color=red,align='center',vertical='middle')
 for i in range(4):
  x=665+i*220;color=red if i%2==0 else black
  box(f'domain-box-{i}',x,318,205,72,fill=color)
  text(f'domain-{i}',x+8,325,189,58,25,color='#FFFFFF',align='center',vertical='middle')
 for row in range(3):
  y=410+row*96
  box(f'cap-box-{row}',400,y,240,80,fill=red if row==1 else paper,stroke=red)
  text(f'cap-{row}',408,y+14,224,52,25,color='#FFFFFF' if row==1 else red,align='center',vertical='middle')
  for col in range(4):
   x=665+col*220;color=red if (row+col)%2==0 else black
   box(f'cell-{row}-{col}',x,y,205,80,fill=color+'10',stroke=color+'80')
   box(f'dot-{row}-{col}',x+88.5,y+26,28,28,fill=color,geometry='ellipse')
 box('old-box',60,318,300,160,fill=black)
 text('old-label',80,336,260,36,22,color='#FFFFFF')
 text('old',80,388,260,74,25,'body','#FFFFFF')
 es.append(dict(id='transition',type='path',x=195,y=486,width=30,height=24,points=[[0,0],[30,0],[15,24]],closed=True,fill=red,stroke='none',stroke_width=0))
 box('new-box',60,520,300,162,fill=red)
 text('new-label',80,532,260,34,22,color='#FFFFFF')
 text('new',80,573,260,104,25,'body','#FFFFFF')
 box('outcomes-box',400,736,1140,116,fill=paper,stroke=red,weight=2)
 text('outcomes-label',428,746,1084,32,22,color=red)
 text('outcome-0',428,788,450,48,32,align='center')
 box('outcomes-divider',902,786,1,45,fill=red+'70')
 text('outcome-1',927,788,585,48,32,align='center')
 return dict(id='uvance',background=paper,elements=es)


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-root',type=Path,required=True)
 p.add_argument('--skill-directory',type=Path,default=Path(__file__).resolve().parents[2]/'skills/decksmith')
 a=p.parse_args();root=a.output_root.resolve();root.mkdir(parents=True,exist_ok=False);s=root/'setting';s.mkdir()
 save(s/'style.yaml',STYLE);save(s/'structure.yaml',dict(slides=[dict(id='uvance',purpose='共通モデル化の主張と成果を優先し、4列×3行の関係図を読めるようにする',
  required_text=list(COPY.values()),notes='添付画像からの再構成。隠れた軸見出しは本文の用語で「3つの横断ケイパビリティ」と補った。右上の切れた装飾ヘッダーは再現しない。丸の色は意味を推定せず参照の配置を保持。')]))
 (s/'brief.md').write_text('参照画像から文章を転記。隠れた縦軸見出しは本文の用語で「3つの横断ケイパビリティ」と補う。左右に切れた装飾メタデータは再現対象外。丸の意味を追加しない。\n\n'+'\n\n'.join(COPY.values()),encoding='utf-8')
 save(s/'decksmith.yaml',dict(slide=dict(width_px=1600,height_px=900,aspect_ratio='16:9'),privacy=dict(mode='restricted'),input=dict(style='style.yaml',brief='brief.md'),
  output=dict(directory='../output',filename='uvance.pptx',pdf=True,renderer='libreoffice'),images=dict(mode='provided_only',amount='none',type='auto',color='color',plan='show'),language='日本語',text=dict(amount='normal')))
 (s/'text-plan.md').write_text('1ページnormal。主張52px、成果32px、説明・行列ラベル25px、補助見出し22〜26px。全表示文を保持。',encoding='utf-8')
 (s/'image-plan.md').write_text('画像なし。ネイティブ文字と図形で編集可能にする。',encoding='utf-8')
 workflow=a.skill_directory.resolve()/'scripts/workflow.py'
 for args in (['prepare','--image-capability','unverified'],['freeze-content','--brief','brief.md']):
  subprocess.run([sys.executable,str(workflow),args[0],'--project',str(s)]+args[1:],check=True)
 hashes=dict(style_sha256=sha(s/'style.yaml'),structure_sha256=sha(s/'structure.yaml'))
 save(s/'scene.yaml',dict(schema_version='1.0',canvas=dict(width=1600,height=900),**hashes,requirements=[dict(source='/'+k,interpretation=v,status='implemented',
  targets=['uvance/'+eid for eid in targets]) for (k,v),targets in zip(STYLE.items(),[['title','old-box','new-box'],['title','outcome-0','outcome-1'],['row-axis','column-axis','cell-0-0','cell-2-3']])],slides=[scene()]))
 save(s/'design-plan.yaml',dict(**hashes,signatures=[dict(source='/'+k,intent=v,visual_check=v+' 実PNGで確認。') for k,v in STYLE.items()],
  font_evidence='Macで実在確認済みのHiragino Sans W9とHiragino Sans。再生成時は使用書体と実画像を確認する。',
  typography={r:dict(font='Hiragino Sans W9' if r=='heading' else 'Hiragino Sans',min_size=z,reason='主張・成果・説明を異なる強さにする') for r,z in [('heading',52),('label',22),('body',25)]},
  representative_slides=['uvance'],slides=[dict(id='uvance',focal_element='title',focal_reason='個別受託から社会課題解決の標準化へ、という変化が主張。成果は次に読む要点。',
   composition='上に主張と説明、左に従来とUvance、右に4列×3行。軸見出しを表外の専用領域へ水平配置。最下部の成果は英語ラベルより中身を大きくする。',
   asset_decision='全て編集可能な文字・図形。参照の赤黒の丸を保持し、凡例の意味は創作しない。')]))
 print(root)

if __name__=='__main__':main()
