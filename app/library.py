"""Reusable local assets. Project copies pin a library version and keep their IDs."""
import copy
import json
from pathlib import Path
from . import store, providers
from fastapi import APIRouter

router=APIRouter(prefix='/api/library',tags=['assets'])

KINDS = ('character','location','prop','audio','image','video')
FIELDS = ('name','kind','description','tags','style','references','voice','voice_library_id','file','variants','origin','image_prompt')
IMAGES = ('.png','.jpg','.jpeg','.webp')
AUDIO = ('.wav','.mp3','.m4a','.ogg')
VIDEOS = ('.mp4','.mov','.webm','.mkv')


def validate(value):
    item = {k:copy.deepcopy(value[k]) for k in FIELDS if k in value}
    if item.get('kind') not in KINDS: raise ValueError('资产类型无效')
    if not isinstance(item.get('name'),str) or not item['name'].strip(): raise ValueError('请填写资产名称')
    item['name'] = item['name'].strip()[:120]
    item['description'] = str(item.get('description',''))[:20000]
    if not isinstance(item.get('tags',[]),list): raise ValueError('标签须为列表')
    item['tags'] = list(dict.fromkeys(str(t).strip()[:50] for t in item.get('tags',[]) if str(t).strip()))[:30]
    item.setdefault('references',[]); item.setdefault('variants',[])
    if not isinstance(item['references'],list) or not isinstance(item['variants'],list): raise ValueError('参考素材或造型列表无效')
    if any(not isinstance(v,dict) for v in item['variants']): raise ValueError('造型版本格式无效')
    for ref in item['references']:
        if not isinstance(ref,dict) or Path(providers.file_path(ref.get('file',''))).suffix.lower() not in IMAGES: raise ValueError('参考素材需要本地图片文件')
    if item.get('voice') and Path(providers.file_path(item['voice'])).suffix.lower() not in AUDIO: raise ValueError('声音需要本地音频文件')
    if item.get('voice_library_id'):
        sound = store.get('library',item['voice_library_id'])
        if sound['kind']!='audio' or not any(v['content'].get('file')==item.get('voice') for v in sound['versions']): raise ValueError('声音绑定与素材不匹配')
    if item.get('file'):
        suffix=Path(providers.file_path(item['file'])).suffix.lower()
        expected={'image':IMAGES,'audio':AUDIO,'video':VIDEOS}.get(item['kind'],IMAGES)
        if suffix not in expected: raise ValueError('素材文件与资产类型不匹配')
    if item['kind'] in ('image','audio','video') and not item.get('file'): raise ValueError('请上传该类型的素材文件')
    return item


def list_assets():
    return sorted((row for row in store.all_rows('library') if not row.get('deleted_at')),key=lambda x:x['updated_at'],reverse=True)


def create(value):
    item=validate(value);at=store.now()
    row={'id':store.uid('library'),'revision':1,'version':1,'favorite':False,'created_at':at,'updated_at':at,**item,
         'versions':[{'version':1,'at':at,'reason':'创建资产','content':copy.deepcopy(item)}]}
    return store.put('library',row)


def update(ident, value, reason='编辑资产', favorite=None):
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT body FROM library WHERE id=?',(ident,)).fetchone()
        if not old: raise KeyError(ident)
        old=json.loads(old['body'])
        if old.get('deleted_at'): raise ValueError('这项资产已从资产库删除，请刷新列表')
        if value.get('revision')!=old['revision']: raise ValueError('资产已更新，请重新打开后编辑；当前内容尚未覆盖')
        row=copy.deepcopy(old)
        if favorite is None:
            content=validate({**old,**value})
            if content.get('kind')!=old['kind']: raise ValueError('已有资产不能改变类型，请新建另一项资产')
            row.update(content);row['version']+=1
            row['versions'].append({'version':row['version'],'at':store.now(),'reason':reason,'content':copy.deepcopy(content)})
        else: row['favorite']=bool(favorite)
        row['revision']+=1;row['updated_at']=store.now()
        db.execute('UPDATE library SET body=? WHERE id=?',(json.dumps(row,ensure_ascii=False),ident))
    return row


def restore(ident, version, expected):
    row=store.get('library',ident)
    old=next((v for v in row['versions'] if v['version']==version),None)
    if not old: raise ValueError('资产版本不存在')
    # Restore records a new revision, never truncates history or alters pinned copies.
    return update(ident,{**old['content'],'revision':expected},reason='恢复 v'+str(version))


def remove(ident, expected, confirm):
    if confirm is not True: raise ValueError('请确认删除这项资产库资产')
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        record=db.execute('SELECT body FROM library WHERE id=?',(ident,)).fetchone()
        if not record: raise KeyError(ident)
        row=json.loads(record['body'])
        if expected!=row['revision']: raise ValueError('资产已更新，请刷新后重新确认删除')
        if row.get('deleted_at'): raise ValueError('这项资产已删除，请刷新列表')
        # Keep the original record and files for pinned copies and voice bindings.
        row.update(deleted_at=store.now(),updated_at=store.now(),revision=row['revision']+1)
        db.execute('UPDATE library SET body=? WHERE id=?',(json.dumps(row,ensure_ascii=False),ident))
    return {'id':ident,'deleted':True,'revision':row['revision']}


def usage(ident):
    store.get('library',ident);result=[]
    for project in store.all_rows('projects'):
        direct=[a for a in project['assets'] if a.get('library_id')==ident]
        sounds=[a for a in project['assets'] if a.get('voice_library_id')==ident]
        ids={a['id'] for a in direct+sounds}
        segments=[s for s in project['segments'] if ids.intersection(s.get('character_ids',[])+s.get('prop_ids',[])+[s.get('location_id')])]
        artifacts=[a for a in project.get('artifacts',[]) if a.get('library_id')==ident]
        if direct or sounds or artifacts:
            result.append({'project_id':project['id'],'project_name':project['name'],'assets':[{'id':a['id'],'name':a['name'],'version':a.get('library_version')} for a in direct+sounds],
                           'segments':[{'id':s['id'],'name':s.get('title',s['id'])} for s in segments],'artifacts':len(artifacts)})
    return result


def import_project(ident, asset_id=None):
    project=store.get('projects',ident);existing=list_assets();created=[];skipped=0
    assets=[a for a in project['assets'] if not asset_id or a['id']==asset_id]
    if asset_id and not assets: raise ValueError('项目资产不存在')
    for asset in assets:
        if any(a.get('origin',{}).get('project_id')==ident and a.get('origin',{}).get('asset_id')==asset['id'] for a in existing):skipped+=1;continue
        created.append(create({**asset,'origin':{'project_id':ident,'project_name':project['name'],'asset_id':asset['id']}}))
    return {'items':created,'skipped':skipped}


def save_project_item(project_id, target_id, media_kind=None):
    """Save a project asset or the selected shot image/video, with repeat-safe versions."""
    project=store.get('projects',project_id)
    origin={'project_id':project_id,'project_name':project['name'],'target_id':target_id}
    if media_kind is None:
        asset=next((a for a in project['assets'] if a['id']==target_id),None)
        if not asset: raise ValueError('项目资产不存在')
        content=validate({**asset,'origin':{**origin,'media_kind':'asset'}})
    else:
        if media_kind not in ('image','video'): raise ValueError('请选择图片或视频')
        segment=next((s for s in project['segments'] if s['id']==target_id),None)
        if not segment: raise ValueError('项目分镜不存在')
        versions=segment.get('images' if media_kind=='image' else 'versions',[])
        selected=segment.get('current_image' if media_kind=='image' else 'current_version')
        chosen=next((v for v in versions if v['id']==selected),None)
        if not chosen or not chosen.get('file'): raise ValueError('请先生成或选用要保存的'+('图片' if media_kind=='image' else '视频'))
        # Each distinct media file is its own reusable material.
        content=validate({'kind':media_kind,'name':segment['title']+(' · 分镜图' if media_kind=='image' else ' · 视频'),
            'description':segment.get('image_prompt' if media_kind=='image' else 'prompt',''),
            'file':chosen['file'],'origin':{**origin,'media_kind':media_kind,'file':chosen['file']}})
    def same_origin(row):
        old=row.get('origin',{}); current=content['origin']
        return (old.get('project_id')==project_id and (old.get('target_id') or old.get('asset_id'))==target_id
                and old.get('media_kind','asset')==current['media_kind'] and old.get('file')==current.get('file'))
    existing=next((row for row in list_assets() if same_origin(row)),None)
    if existing:
        old=validate(existing)
        if old==content: return {'item':existing,'duplicate':True,'updated':False}
        saved=update(existing['id'],{**content,'revision':existing['revision']},reason='从项目保存新版本')
        return {'item':saved,'duplicate':False,'updated':True}
    return {'item':create(content),'duplicate':False,'updated':False}


def reuse(ident, project_id, version=None, target_asset_id=None):
    row=store.get('library',ident);project=store.get('projects',project_id);revision=project['revision']
    if row.get('deleted_at'): raise ValueError('这项资产已删除，不能再次复用')
    selected=next((v for v in row['versions'] if v['version']==(version or row['version'])),None)
    if not selected: raise ValueError('资产版本不存在')
    content=validate(selected['content'])
    if target_asset_id:
        if content['kind']!='audio': raise ValueError('绑定声音请选择声音资产')
        asset=next((a for a in project['assets'] if a['id']==target_asset_id and a['kind']=='character'),None)
        if not asset: raise ValueError('请选择项目中的角色')
        asset.update(voice=content['file'],voice_library_id=ident,voice_library_version=selected['version'])
        for s in project['segments']:
            if target_asset_id in s.get('character_ids',[]):s['status']='stale'
    elif content['kind'] in ('character','location','prop'):
        duplicate=next((a for a in project['assets'] if a.get('library_id')==ident and a.get('library_version')==selected['version']),None)
        if duplicate:return {'project':project,'duplicate':True,'asset_id':duplicate['id']}
        asset=copy.deepcopy(content);asset['id']=store.uid(content['kind']);asset['source_id']=asset['id'];asset.update(status='draft',confirmed=False,version=1,library_id=ident,library_version=selected['version'])
        mapping={v['id']:store.uid('variant') for v in asset.get('variants',[]) if v.get('id')}
        for v in asset.get('variants',[]):v['id']=mapping.get(v.get('id')) or store.uid('variant')
        for r in asset['references']:
            if r.get('variant_id'):r['variant_id']=mapping.get(r['variant_id'])
        project['assets'].append(asset)
    else:
        duplicate=next((a for a in project['artifacts'] if a.get('library_id')==ident and a.get('library_version')==selected['version']),None)
        if duplicate:return {'project':project,'duplicate':True}
        project['artifacts'].append({'id':store.uid('material'),'type':'library_'+content['kind'],'name':content['name'],'file':content['file'],'library_id':ident,'library_version':selected['version']})
    saved=store.save_project(project,revision,reason='从资产库复用 '+content['name'])
    return {'project':saved,'duplicate':False}


@router.get('')
def api_list():return list_assets()


@router.post('')
def api_create(payload:dict):return create(payload)


@router.post('/import-project')
def api_import(payload:dict):return import_project(payload['project_id'],payload.get('asset_id'))


@router.post('/save-project-item')
def api_save_project_item(payload:dict):
    return save_project_item(payload['project_id'],payload['target_id'],payload.get('media_kind'))


@router.get('/{ident}/usage')
def api_usage(ident):return usage(ident)


@router.get('/{ident}')
def api_get(ident):return store.get('library',ident)


@router.put('/{ident}')
def api_update(ident,payload:dict):return update(ident,payload)


@router.post('/{ident}/favorite')
def api_favorite(ident,payload:dict):return update(ident,payload,favorite=payload.get('favorite',False))


@router.post('/{ident}/delete')
def api_delete(ident,payload:dict):return remove(ident,payload.get('revision'),payload.get('confirm'))


@router.post('/{ident}/restore')
def api_restore(ident,payload:dict):return restore(ident,int(payload['version']),payload['revision'])


@router.post('/{ident}/reuse')
def api_reuse(ident,payload:dict):return reuse(ident,payload['project_id'],payload.get('version'),payload.get('target_asset_id'))
