"""Manual project assets and shot links share stable IDs with generation."""
import copy
from . import store, task_locks

KINDS = {'character', 'location', 'prop'}


def linked(segment, asset):
    if asset['kind'] == 'location': return segment.get('location_id') == asset['id']
    return asset['id'] in segment.get('character_ids' if asset['kind'] == 'character' else 'prop_ids', [])


def touch(segment):
    segment['prompt_stale'] = True
    segment['video_prompt_stale'] = True
    segment['status'] = 'stale' if segment.get('versions') else 'draft'


def unlink(segment, asset, assets):
    if asset['kind'] == 'location':
        if segment.get('location_id') == asset['id']: segment['location_id'] = ''
    else:
        field = 'character_ids' if asset['kind'] == 'character' else 'prop_ids'
        segment[field] = [ident for ident in segment.get(field, []) if ident != asset['id']]
    valid = {v['id'] for a in assets if a['id'] in segment.get('character_ids', []) for v in a.get('variants', [])}
    segment['variant_ids'] = [ident for ident in segment.get('variant_ids', []) if ident in valid]
    touch(segment)


def load(ident, payload):
    project = store.get('projects', ident)
    if payload.get('revision') != project['revision']: raise ValueError('作品已更新，请刷新后再编辑资产')
    return project


def edit_shot(ident, payload):
    p = load(ident, payload)
    segment = next((s for s in p['segments'] if s['id'] == payload.get('segment_id')), None)
    if not segment: raise ValueError('分镜已不存在')
    operation = payload.get('operation')
    if operation not in ('create', 'link', 'unlink'): raise ValueError('请选择新建、关联或移除本镜关联')
    if operation == 'create':
        value = payload.get('asset')
        if not isinstance(value, dict) or value.get('kind') not in KINDS: raise ValueError('请选择角色、场景或道具')
        name = value.get('name', ''); description = value.get('description', '')
        if not isinstance(name, str) or not name.strip(): raise ValueError('请填写资产名称')
        if len(name.strip()) > 120 or not isinstance(description, str) or len(description) > 20000: raise ValueError('资产名称或描述过长')
        asset = next((a for a in p['assets'] if a['kind'] == value['kind'] and a['name'] == name.strip()), None)
        if asset is None:
            asset = {'id':store.uid(value['kind']), 'kind':value['kind'], 'name':name.strip(), 'description':description,
                'references':[], 'variants':[], 'version':1, 'status':'draft', 'manual':True}
            if asset['kind'] == 'character': asset['variants'] = [{'id':store.uid('variant'), 'name':'默认服装', 'description':''}]
    else:
        asset = next((a for a in p['assets'] if a['id'] == payload.get('asset_id')), None)
        if not asset or asset['kind'] not in KINDS: raise ValueError('项目资产已不存在')
    task_locks.assert_available(p, {'reads':set(), 'writes':{'segment:'+segment['id'], 'asset:'+asset['id']}})
    if operation == 'unlink':
        if not linked(segment, asset): return p
        unlink(segment, asset, p['assets'])
    else:
        if not any(a['id'] == asset['id'] for a in p['assets']): p['assets'].append(asset)
        asset['episode_ids'] = list(dict.fromkeys(asset.get('episode_ids', []) + [segment.get('episode_id')]))
        if asset['kind'] == 'location': segment['location_id'] = asset['id']
        else:
            field = 'character_ids' if asset['kind'] == 'character' else 'prop_ids'
            segment[field] = list(dict.fromkeys(segment.get(field, []) + [asset['id']]))
            if asset['kind'] == 'character':
                if not asset.get('variants'): asset['variants'] = [{'id':store.uid('variant'), 'name':'默认服装', 'description':''}]
                variants = {v['id'] for v in asset['variants']}
                if not variants.intersection(segment.get('variant_ids', [])):
                    segment['variant_ids'] = segment.get('variant_ids', []) + [asset['variants'][0]['id']]
        touch(segment)
    p['outputs']['storyboard'] = {'segments':p['segments']}
    return store.save_project(p, payload['revision'], '手动编辑分镜资产关联')


def delete_asset(ident, payload):
    p = load(ident, payload)
    if payload.get('confirm') is not True: raise ValueError('请确认从项目删除资产并清理镜头关联')
    asset = next((a for a in p['assets'] if a['id'] == payload.get('asset_id')), None)
    if not asset: raise ValueError('项目资产已不存在')
    affected = [s for s in p['segments'] if linked(s, asset)]
    task_locks.assert_available(p, {'reads':set(), 'writes':{'asset:'+asset['id']} | {'segment:'+s['id'] for s in affected}})
    for segment in affected: unlink(segment, asset, p['assets'])
    p.setdefault('archived_assets', []).append({'asset':copy.deepcopy(asset), 'removed_at':store.now(),
        'segment_ids':[s['id'] for s in affected]})
    p['assets'] = [a for a in p['assets'] if a['id'] != asset['id']]
    p['outputs']['storyboard'] = {'segments':p['segments']}
    return store.save_project(p, payload['revision'], '从项目删除资产（保留归档及媒体文件）')
