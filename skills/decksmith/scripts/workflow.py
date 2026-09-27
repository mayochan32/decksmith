"""Local workflow helpers. Never authorize network use or manufacture reviews."""
import argparse
import copy
import json
from pathlib import Path
import shutil
from compile_spec import SpecError, load_mapping, source_hash, compact, text_content, text
from project_config import resolve_config


def save_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def announce(config):
    policy = config['communication_policy']
    external = '事前承認が必要' if config['privacy']['mode'] == 'normal' else '使用不可（例外は明示的な事前承認が必要）'
    image = '使用しない' if policy['host_image_generation'] == 'disabled' else {
        'unverified':'機能が利用できる場合に許可（利用可否は未確認）',
        'available':'使用可（ホスト機能を確認済み）',
        'unavailable':'利用不可。必要画像がある場合は代案の選択を人間に確認'}[policy['host_image_capability']]
    return '\n'.join(['通信モード：' + config['privacy']['mode'],
        'Web検索・外部サービス：' + external, '利用中のAIサービスの画像生成：' + image,
        'ローカル処理：使用可', '原稿・画像・プレビューは利用中のAIサービスへ送信され得ます。通信遮断機能ではありません。'])


def policy_record(config, scene=None):
    path = Path(config['config_path']).with_suffix('.policy.json') if config['config_path'] else None
    if not path or not path.is_file(): return None
    record = load_mapping(path)
    if record.get('resolved_sha256') != source_hash(config['config_path']):
        raise SpecError('Policy record belongs to different resolved settings; review the change first')
    policy = record.get('policy', {})
    for key in ('web_search','external_services','host_image_generation'):
        if policy.get(key) != config['communication_policy'][key]:
            raise SpecError('Policy record conflicts with config: ' + key)
    if policy.get('host_image_capability') not in ('available','unavailable','unverified'):
        raise SpecError('Invalid recorded host image capability')
    approvals = {}
    for a in record.get('approvals', []):
        for key in ('id','purpose','destination','data','human_evidence','approved_at'):
            text(a.get(key), 'approval.'+key)
        if a['id'] in approvals: raise SpecError('Duplicate approval id')
        approvals[a['id']] = a
    for use in record.get('usage', []):
        kind = use.get('kind')
        if kind not in ('web_search','external_service','host_image_generation','local'):
            raise SpecError('Unknown recorded usage kind')
        if kind in ('web_search','external_service'):
            a = approvals.get(use.get('approval_id'))
            if not a: raise SpecError('External use lacks human approval record')
            if config['privacy']['mode']=='restricted' and a.get('restricted_exception') is not True:
                raise SpecError('Restricted external use needs explicit exception approval')
            for key in ('purpose','destination','data'):
                if use.get(key)!=a[key]: raise SpecError('External usage exceeds recorded approval scope: '+key)
            from datetime import datetime
            try:
                approved=datetime.fromisoformat(a['approved_at']);used=datetime.fromisoformat(use['used_at'])
                if approved.utcoffset() is None or used.utcoffset() is None or approved>used: raise ValueError()
            except (ValueError,TypeError,KeyError): raise SpecError('Approval must precede usage with timezone-aware timestamps')
        elif kind=='host_image_generation' and policy['host_image_generation']=='disabled':
            raise SpecError('Host image generation disabled by image settings')
    elements = {s['id']+'/'+e['id']:e for s in (scene or {}).get('slides',[]) for e in s['elements']}
    for fallback in record.get('image_fallbacks', []):
        for key in ('reason','human_evidence'): text(fallback.get(key),'image fallback '+key)
        if fallback.get('choice') not in ('omit','placeholder'): raise SpecError('Unapproved image fallback choice')
        if not fallback.get('slides'): raise SpecError('Image fallback requires affected slides')
        if fallback['choice']=='placeholder':
            text(fallback.get('prompt'),'placeholder prompt')
            if scene:
                box=elements.get(fallback.get('box'));label=elements.get(fallback.get('text'))
                if not box or box.get('geometry')!='rect' or not label or label['type']!='text':
                    raise SpecError('Placeholder requires editable rectangle and prompt text')
                if compact(fallback['prompt']) not in compact(text_content(label)):
                    raise SpecError('Placeholder prompt not retained in editable text')
                if not (box['x']<=label['x'] and box['y']<=label['y'] and
                        label['x']+label['width']<=box['x']+box['width'] and label['y']+label['height']<=box['y']+box['height']):
                    raise SpecError('Placeholder prompt must be inside its rectangle')
    return record


def prepare(project, config_path=None, destination=None, capability='unverified', source=None):
    config = resolve_config(config_path, project)
    dest = Path(destination or project / 'decksmith.resolved.yaml')
    # Output uses the public config schema, never the diagnostic fields.
    public = {k: config[k] for k in ('privacy','input','output','images','text','language')}
    public['slide'] = {'width_px':config['canvas']['width'], 'height_px':config['canvas']['height']}
    policy = dict(config['communication_policy'], host_image_capability=capability)
    if source:
        policy['mode_source'] = 'prompt'
        policy['source_evidence'] = source
    config['communication_policy'] = policy
    record = dest.with_suffix('.policy.json')
    if dest.exists() or dest.is_symlink() or record.exists() or record.is_symlink():
        raise SpecError('Refusing to overwrite resolved settings or policy record; choose a new --destination')
    save_new(dest, public)
    save_new(record, {'resolved_sha256':source_hash(dest), 'policy':policy,
                      'approvals':[], 'usage':[], 'image_fallbacks':[]})
    return {'settings':str(dest), 'policy_record':str(record), 'notice':announce(config)}


def freeze(project, structure_path=None, brief_path=None):
    structure_path = Path(structure_path or project / 'structure.yaml')
    structure = load_mapping(structure_path)
    # Capture BEFORE visual design; never derive this baseline from scene text.
    slides = structure.get('slides', [])
    if not slides or len({s['id'] for s in slides}) != len(slides):
        raise SpecError('Content baseline requires distinct slides')
    for slide in slides:
        if not slide.get('required_text'):
            raise SpecError('Each slide needs required_text before freezing')
        for value in slide['required_text']: text(value, 'required_text')
    brief = Path(brief_path or project / 'brief.md').resolve()
    if not brief.is_file():
        raise SpecError('Save the supplied brief/prompt locally before freezing content')
    contract = {'source':str(brief), 'source_sha256':source_hash(brief),
                'slides':[{'id':s['id'], 'required_text':s['required_text']} for s in slides]}
    dest = project / 'content-contract.json'
    save_new(dest, contract)
    return {'contract':str(dest), 'sha256':source_hash(dest)}


def check_content(project, scene):
    path = project / 'content-contract.json'
    if not path.is_file(): return None  # Legacy inputs remain renderable; skill requires new baseline.
    contract = load_mapping(path)
    if source_hash(Path(contract['source'])) != contract['source_sha256']:
        raise SpecError('Brief changed since content freeze; review source changes, do not just refresh hashes')
    if [s['id'] for s in contract['slides']] != [s['id'] for s in scene['slides']]:
        raise SpecError('Content baseline slide order differs')
    changes_path = project / 'content-changes.json'
    changes = load_mapping(changes_path).get('changes', []) if changes_path.is_file() else []
    seen = set()
    for change in changes:
        key = (change['slide'], change['original'])
        if key in seen: raise SpecError('Duplicate content change')
        seen.add(key)
        text(change.get('replacement'), 'content replacement')
        text(change.get('reason'), 'content change reason')
        text(change.get('source_evidence'), 'content change source evidence')
    expected = {(s['id'], t) for s in contract['slides'] for t in s['required_text']}
    if not seen <= expected: raise SpecError('Unknown content change target')
    for original, rendered in zip(contract['slides'], scene['slides']):
        native = compact(''.join(text_content(e) for e in rendered['elements'] if e['type']=='text'))
        for required in original['required_text']:
            value = next((c['replacement'] for c in changes if (c['slide'],c['original'])==(original['id'],required)), required)
            if compact(value) not in native:
                raise SpecError(original['id'] + ': missing independent content requirement: ' + value)
    return {'baseline':contract, 'changes':changes,
            'assurance':'literal retention only; semantic equivalence and source coverage require review'}


def prototype(project, destination, ids, config_path=None):
    from compile_spec import compile_scene
    from design_quality import check_plan
    cfg = resolve_config(config_path, project)
    style = Path(cfg['input'].get('style', project/'style.yaml'))
    # Validate references before copying. compile_scene rejects out-of-project assets.
    compiled = compile_scene(project/'scene.yaml', style, project/'structure.yaml', allow_draft=True)
    scene = load_mapping(project/'scene.yaml')
    plan = check_plan(project/'design-plan.yaml', compiled)
    check_content(project, compiled)
    if not ids or len(set(ids))!=len(ids) or not set(ids)<={s['id'] for s in scene['slides']}:
        raise SpecError('Choose distinct existing slide IDs')
    destination = Path(destination).resolve()
    if destination == project.resolve() or destination in project.resolve().parents:
        raise SpecError('Prototype destination must not replace source project')
    if destination.exists() or destination.is_symlink(): raise SpecError('Prototype destination already exists')
    structure = load_mapping(project/'structure.yaml')
    for data in (scene, structure, plan): data['slides'] = [s for s in data['slides'] if s['id'] in ids]
    plan['representative_slides'] = [s['id'] for s in scene['slides']]
    for req in scene['requirements']:
        if 'targets' in req:
            req['targets'] = [t for t in req['targets'] if t.split('/')[0] in ids]
            if not req['targets']:
                req.update(status='blocked', reason='Implemented outside this prototype; final source remains unchanged')
                del req['targets']
    destination.mkdir(parents=True)
    shutil.copy2(style, destination/'style.yaml')
    for s in scene['slides']:
        for e in s['elements']:
            if e['type']=='image':
                source=(project/e['path']).resolve()
                relative=source.relative_to(project.resolve())
                target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(source,target)
                e['path']=relative.as_posix()
    save_new(destination/'structure.yaml',structure)
    for data in (scene,plan):
        data['structure_sha256']=source_hash(destination/'structure.yaml')
        data['style_sha256']=source_hash(destination/'style.yaml')
    save_new(destination/'scene.yaml',scene);save_new(destination/'design-plan.yaml',plan)
    config = {k:copy.deepcopy(cfg[k]) for k in ('privacy','input','output','images','text','language')}
    config['slide']={'width_px':scene['canvas']['width'],'height_px':scene['canvas']['height']}
    config['input']['style']='style.yaml'
    config['output'].update(directory='output',filename='prototype.pptx')
    save_new(destination/'decksmith.yaml',config)
    baseline=project/'content-contract.json'
    if baseline.is_file():
        data=load_mapping(baseline);data['slides']=[s for s in data['slides'] if s['id'] in ids]
        save_new(destination/'content-contract.json',data)
        changes=project/'content-changes.json'
        if changes.is_file():
            save_new(destination/'content-changes.json',{'changes':[c for c in load_mapping(changes)['changes'] if c['slide'] in ids]})
    return {'project':str(destination),'draft_required':True,'slides':[s['id'] for s in scene['slides']]}


def compare(first, second):
    def read(output):
        folder=Path(output).with_suffix('.preview')
        manifest=load_mapping(folder/'review-manifest.json')
        if source_hash(output)!=manifest['output_sha256']: raise SpecError('PPTX changed since rendering')
        result={}
        for s in manifest['slides']:
            name=s['preview']
            if not name: raise SpecError('Cannot compare without rendered previews')
            if Path(name).name!=name: raise SpecError('Invalid preview filename')
            digest=source_hash(folder/name)
            if digest!=manifest['preview_sha256'][name]: raise SpecError('Preview changed since rendering')
            result[s['id']]=digest
        return result
    a,b=read(first),read(second)
    return {'changed':[s for s in b if b[s]!=a.get(s)],'unchanged':[s for s in b if b[s]==a.get(s)],
            'removed':[s for s in a if s not in b], 'assurance':'pixel identity only; not automatic review approval'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='action',required=True)
    for name in ('prepare','freeze-content','prototype'):
        command=sub.add_parser(name);command.add_argument('--project',type=Path,required=True)
        if name in ('prepare','prototype'):
            command.add_argument('--config',type=Path);command.add_argument('--destination',type=Path,required=name=='prototype')
        if name=='prepare':
            command.add_argument('--image-capability',choices=('available','unavailable','unverified'),default='unverified')
            command.add_argument('--source-evidence')
        if name=='freeze-content':
            command.add_argument('--structure',type=Path);command.add_argument('--brief',type=Path)
        if name=='prototype':command.add_argument('--slides',nargs='+',required=True)
    command=sub.add_parser('compare');command.add_argument('--previous',type=Path,required=True);command.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    try:
        if a.action=='compare':result=compare(a.previous,a.output)
        else:
            project=a.project.resolve()
            def local(v):return (project/v).resolve() if v else None
            if a.action=='prepare':result=prepare(project,local(a.config),local(a.destination),a.image_capability,a.source_evidence)
            elif a.action=='freeze-content':result=freeze(project,local(a.structure),local(a.brief))
            else:result=prototype(project,local(a.destination),a.slides,local(a.config))
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,OSError,KeyError,TypeError) as e:p.exit(2,'DeckSmith workflow: '+str(e)+'\n')


if __name__=='__main__':main()
