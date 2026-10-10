"""Author four editable balance studies. These coordinates are fixtures, not presets."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

BLUE = '#2055A0'
DOMAINS = ['持続可能な製造', 'リテール体験', '健全な生活', '信頼ある社会']
CAPS = ['デジタルシフト', '業務変革', 'ハイブリッドIT']
IDS = ['crossing-retained', 'crossing-recomposed', 'pills-balanced', 'panels-balanced']
TITLES = ['領域と共通基盤', '領域と共通基盤', '三つの能力', '三つの能力']
STYLE = {'色': '青と白、領域図は淡いグレー。能力図の最初の白塗りを維持する。',
         '文字': 'Hiragino Sans。並列ラベルは同じサイズと太さ。',
         '構成': '前半は四領域と共通基盤を交差または上下配置で表す。後半は同格の三項目。因果や順序を足さない。'}


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scenes():
    slides, plans = [], []
    for index, sid in enumerate(IDS):
        first = index < 2
        bg = '#F0F0EC' if first else BLUE
        ink = BLUE if first else '#FFFFFF'
        es, groups = [], []
        def label(eid, value, x, y, w, h, size=36, color=ink, align='center', role='label'):
            es.append(dict(id=eid, type='text', text=value, x=x, y=y, width=w, height=h,
                           size=size, font='Hiragino Sans', color=color, bold=True,
                           align=align, vertical='middle', role=role))
        def box(eid, x, y, w, h, fill='none', stroke=ink, radius=0, weight=2):
            es.append(dict(id=eid, type='shape', geometry='roundRect' if radius else 'rect',
                           x=x, y=y, width=w, height=h, fill=fill, stroke=stroke,
                           stroke_width=weight, radius=radius))
        def group(gid, prefix, n, checks, reason):
            groups.append(dict(id=gid, reason=reason,
                               members=[dict(shape=f'{prefix}-{i}', label=f'{prefix}-label-{i}') for i in range(n)], checks=checks))
        label('title', TITLES[index], 100, 76, 1400, 70, 48, align='left', role='heading')
        if first:
            # Keep meaningful intersections; reduce band mass and give headings breathing room.
            compact = index == 1
            top, height = (264, 140) if compact else (230, 500)
            for i, value in enumerate(DOMAINS):
                x = 110+i*350
                box(f'domain-{i}', x, top, 330, height, radius=24 if compact else 165)
                label(f'domain-label-{i}', value, x+10, top+(40 if compact else 48), 310, 60, 35)
            for i, value in enumerate(CAPS):
                y = (452 if compact else 404)+i*98
                box(f'cap-{i}', 80, y, 1440, 72, fill=BLUE, stroke='none', radius=12 if compact else 36)
                label(f'cap-label-{i}', value, 120, y+7, 1360, 58, 36, '#FFFFFF', 'left')
            group('domain-labels', 'domain', 4, dict(font_size=dict(max_spread=0), shape_width=dict(max_spread=0),
                  padding_top=dict(max_spread=0), gap_x=dict(max_spread=0)), '四領域は同格。見出し位置・寸法・間隔を揃える。')
            group('common-bands', 'cap', 3, dict(font_size=dict(max_spread=0), shape_height=dict(max_spread=0),
                  font_height_ratio=dict(min=.45, max=.55), text_box_center_y=dict(min=.48, max=.52), gap_y=dict(max_spread=0)),
                  '三つの共通基盤は同じ帯厚・文字階層とし、領域名を圧倒しない。')
        else:
            compact = index == 3
            y, h = (354, 184) if compact else (328, 240)
            for i, value in enumerate(CAPS):
                x = 100+i*480
                box(f'cap-{i}', x, y, 440, h, fill='#FFFFFF' if i == 0 else 'none',
                    stroke='#FFFFFF', radius=20 if compact else 120, weight=3)
                label(f'cap-label-{i}', value, x+24, y+(h-68)/2, 392, 68, 38, BLUE if i == 0 else '#FFFFFF')
            group('capability-labels', 'cap', 3, dict(font_size=dict(max_spread=0), shape_width=dict(max_spread=0),
                  shape_height=dict(max_spread=0), font_height_ratio=dict(min=.15, max=.23),
                  text_box_center_y=dict(min=.48, max=.52), text_box_center_x=dict(min=.48, max=.52),
                  padding_left=dict(max_spread=0), gap_x=dict(max_spread=0)),
                  '三項目の図形・文字・間隔を揃え、最初の白塗りは元図の強調として保持する。')
        slides.append(dict(id=sid, background=bg, elements=es))
        plans.append(dict(id=sid, focal_element='cap-label-0', focal_reason='関係全体を読ませる代表ラベル',
                          composition=('四領域と三基盤の交差を意図した重なりとして保持。' if index == 0 else
                           '四領域を上、全領域に共通する三基盤を下にまとめる。関係の解釈は仮定。' if index == 1 else
                           '三項目は同格。最初の白塗りは保持。')+
                          ('角丸パネルへ再構成する。' if index in (1,3) else '元のカプセル構成を保ち、寸法と余白を調整する。'),
                          asset_decision='編集可能な文字と図形。スクリーンショット自体は資料に埋め込まない。', balance_groups=groups))
    return slides, plans


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-root', type=Path, required=True)
    p.add_argument('--skill-directory', type=Path, default=Path(__file__).resolve().parents[2]/'skills/decksmith')
    a = p.parse_args(); root = a.output_root.resolve(); root.mkdir(parents=True, exist_ok=False)
    setting = root/'setting'; setting.mkdir()
    pages = [dict(id=sid, purpose='参照画像をもとにしたバランス調整の比較用作例',
                  required_text=[TITLES[i]]+(DOMAINS if i<2 else [])+CAPS,
                  notes='参照画像からの再構成。元PPTXの復元ではない。四領域と共通基盤という解釈は仮定。') for i,sid in enumerate(IDS)]
    save(setting/'style.yaml', STYLE); save(setting/'structure.yaml', dict(slides=pages))
    (setting/'brief.md').write_text('参照画像からの再構成。元のPPTXは未提供。意味の解釈は仮定。\n'+
        '\n\n'.join(f"## {pg['id']}\n"+'\n'.join(pg['required_text']) for pg in pages), encoding='utf-8')
    save(setting/'decksmith.yaml', dict(slide=dict(width_px=1600,height_px=900,aspect_ratio='16:9'),
        privacy=dict(mode='restricted'), input=dict(style='style.yaml',brief='brief.md'),
        output=dict(directory='../output',filename='layout-balance.pptx',pdf=True,renderer='libreoffice'),
        images=dict(mode='provided_only',amount='none',type='auto',color='color',plan='show'), language='日本語',text=dict(amount='normal')))
    (setting/'text-plan.md').write_text('全4ページnormal。各節の必須ラベルを全て画面に保持。', encoding='utf-8')
    (setting/'image-plan.md').write_text('全ページ画像なし。参照画像の構成を編集可能な図形と文字で再構成。', encoding='utf-8')
    workflow = a.skill_directory.resolve()/'scripts/workflow.py'
    for arguments in (['prepare','--image-capability','unverified'], ['freeze-content','--brief','brief.md']):
        subprocess.run([sys.executable,str(workflow),arguments[0],'--project',str(setting)]+arguments[1:],check=True)
    slides, plans = scenes(); style_sha, structure_sha = sha(setting/'style.yaml'), sha(setting/'structure.yaml')
    save(setting/'scene.yaml', dict(schema_version='1.0',canvas=dict(width=1600,height=900),style_sha256=style_sha,
        structure_sha256=structure_sha,requirements=[dict(source='/'+k,interpretation=v,status='implemented',
        targets=[f'{sid}/cap-label-0' for sid in IDS]) for k,v in STYLE.items()],slides=slides))
    save(setting/'design-plan.yaml', dict(style_sha256=style_sha,structure_sha256=structure_sha,
        signatures=[dict(source='/'+k,intent=v,visual_check=v+' 実際のPNGで確認する。') for k,v in STYLE.items()],
        font_evidence='MacでHiragino Sansを確認。再生成時は実在と日本語表示を確認する。',
        typography={role:dict(font='Hiragino Sans',min_size=size,reason='1600×900の短い日本語ラベル用') for role,size in [('heading',48),('label',35)]},
        representative_slides=IDS,slides=plans))
    print(root)

if __name__ == '__main__': main()
