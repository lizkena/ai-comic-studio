"""Seedance 2.5 official content contract (checked 2026-10-16).

https://docs.volcengine.com/docs/ark/create-video-generation-task-api?lang=zh
Gateway endpoints are independent of the official content schema.
"""
import base64,copy,json,math,mimetypes,ipaddress
from urllib.parse import urlparse,quote
import httpx

MODEL_KEYS=('contract','capabilities','resolution','generate_audio','watermark','camera_fixed','video_options')
RATIOS=['16:9','4:3','1:1','3:4','9:16','21:9','adaptive']

def is_25(provider):
    model=provider.get('model','').lower()
    return provider.get('protocol') in ('ark','json-video') and (model=='seedance-2.5' or model.startswith(('doubao-seedance-2-5-','dreamina-seedance-2-5-')))

def profile(provider):
    if not is_25(provider):return provider
    out=copy.deepcopy(provider)
    out['capabilities']={'min_duration':4,'max_duration':30,'max_images':30,'max_audio':10,'max_video':10,
                         'audio_reference':True,'video_reference':True,'ratios':RATIOS,
                         'resolutions':['480p','720p','1080p'],'first_frame':True,'native_audio':True,
                         }
    selected=next((m for m in provider.get('models',[]) if m['id']==provider['model']),{})
    out['capabilities'].update(selected.get('capabilities',{}))
    for key,default in [('resolution','720p'),('generate_audio',True),('watermark',False),('video_options',{})]:
        out[key]=copy.deepcopy(selected.get(key,default))
    out['video_adapter']='seedance25-official-content-v1'
    return out

def context(provider):
    return {'provider_id':provider['id'],'model':provider['model'],'protocol':provider['protocol'],
            'adapter':provider.get('video_adapter','configured'),
            'capabilities':copy.deepcopy(provider.get('capabilities',{})),
            'resolution':provider.get('resolution','720p'),
            'rules':('Seedance 2.5：4–30秒整数；480p/720p/1080p；首帧/首尾帧与全模态参考互斥。'
                     '单首帧时保持图片画幅；有其他资产时按参考生视频编排并用文字说明起点，不宣称严格锁帧。'
                     '素材编号按本次清单，不沿用H3编号或专用语法。' if is_25(provider) else '按当前模型能力与实际素材整理，不沿用其他模型的参数限制。')}

def payload(provider,bundle):
    from . import providers
    from PIL import Image
    options={**provider.get('video_options',{}),**bundle.get('video_options',{})}
    duration=float(bundle['duration'])
    if not math.isfinite(duration) or not duration.is_integer() or not 4<=duration<=30:
        raise ValueError('Seedance 2.5 视频时长须为4–30秒整数，未提交')
    ratio=bundle['ratio'];resolution=options.get('resolution') or provider.get('resolution') or '720p'
    if ratio not in RATIOS:raise ValueError('Seedance 2.5 不支持当前画幅，未提交')
    if resolution not in ('480p','720p','1080p'):raise ValueError('Seedance 2.5 分辨率须为480p、720p或1080p，未提交')
    groups={'image':[],'audio':[],'video':[]};seen=set()
    for ref in bundle.get('references',[]):
        key=ref.get('file') or ref.get('url')
        if key in seen:continue
        seen.add(key)
        if ref.get('url'):
            url=ref['url'];parsed=urlparse(url)
            if not (url.startswith('asset://') or parsed.scheme=='https' and parsed.hostname and not parsed.username and not parsed.password):
                raise ValueError('Seedance 视频参考须为HTTPS公网URL或asset://资产ID')
            if parsed.scheme=='https':
                if parsed.hostname.lower() in ('localhost','localhost.localdomain') or parsed.hostname.endswith('.local'): raise ValueError('视频参考地址必须可由远程服务访问')
                try: address=ipaddress.ip_address(parsed.hostname)
                except ValueError: address=None
                if address and not address.is_global: raise ValueError('视频参考不能使用内网地址')
            groups['video'].append((ref,url));continue
        path=providers.file_path(ref['file']);kind=(mimetypes.guess_type(path.name)[0] or '').split('/')[0]
        if kind not in groups:raise ValueError('Seedance 2.5 不支持该参考素材类型')
        if kind=='video':raise ValueError('Seedance官方格式不接受本地视频Base64，请提供HTTPS公网视频URL或asset://资产ID；未上传、未提交')
        limit=30 if kind=='image' else 15
        if path.stat().st_size>=limit*1024**2:raise ValueError(f'Seedance参考{kind}超过{limit}MB，未提交')
        if kind=='image':
            with Image.open(path) as im:
                w,h=im.size
                if not 300<=w<=6000 or not 300<=h<=6000 or not .4<=w/h<=2.5:raise ValueError('Seedance参考图边长须300–6000像素，宽高比0.4–2.5，未提交')
        elif path.suffix.lower() not in ('.wav','.mp3'):raise ValueError('Seedance参考音频须为WAV或MP3，未提交')
        mime=mimetypes.guess_type(path.name)[0]
        groups[kind].append((ref,'data:'+mime+';base64,'+base64.b64encode(path.read_bytes()).decode()))
    for kind,limit in [('image',30),('audio',10),('video',10)]:
        if len(groups[kind])>limit:raise ValueError(f'Seedance 2.5 参考{kind}数量超过{limit}，未提交')
    first=bundle.get('first_frame');last=bundle.get('last_frame')
    if first and not any(r.get('file')==first for r,_ in groups['image']):raise ValueError('指定首帧不在参考图片中')
    if last and (not first or not any(r.get('file')==last for r,_ in groups['image'])):raise ValueError('指定尾帧须与首帧一起存在于参考图片中')
    strict=bool(first and len(groups['image'])==(2 if last else 1) and not groups['audio'] and not groups['video'])
    if last and not strict:raise ValueError('严格首尾帧不能与其他图片、音频或视频参考混用，未提交')
    prompt=bundle['prompt'];content=[];bindings=[];labels={'image':'图片','audio':'音频','video':'视频'}
    for kind,refs in groups.items():
        for i,(r,url) in enumerate(refs,1):
            role=('first_frame' if r.get('file')==first else 'last_frame') if strict else 'reference_'+kind
            content.append({'type':kind+'_url',kind+'_url':{'url':url},'role':role})
            bindings.append(f"{labels[kind]}{i}：{r.get('name','参考素材')}，用途 {r.get('purpose','reference')}")
            if not strict and first and r.get('file')==first:bindings.append(f'以图片{i}所示状态作为起点，其他素材仅用于其对应参考职责。')
    if strict:ratio='adaptive'
    content.insert(0,{'type':'text','text':'\n'.join(bindings+[prompt])})
    result={'model':provider['model'],'content':content,'duration':int(duration),'ratio':ratio,'resolution':resolution,'seed':bundle.get('seed',42)}
    for key in ('generate_audio','watermark'):
        value=options.get(key,provider.get(key,True if key=='generate_audio' else False))
        if not isinstance(value,bool):raise ValueError(key+'须为布尔值')
        result[key]=value
    if not strict and any(groups.values()):result['omni_reference_task_type']='reference'
    if len(json.dumps(result).encode())>64*1024**2:raise ValueError('Seedance请求体超过64MB，未提交')
    return result

def paths(provider):
    host=urlparse(provider['base_url']).hostname
    if host=='api.ai-tudou.net':
        contract=next((m.get('contract',{}) for m in provider.get('models',[]) if m['id']==provider['model']),{})
        poll=contract.get('poll_path') or provider.get('contract',{}).get('poll_path')
        if not poll:
            raise ValueError('土豆 Seedance 2.5 尚缺已核实的查询接口；请在该模型的 contract 中填写 submit_path 与 poll_path，未提交生成')
        return contract.get('submit_path','/videos/generations'),poll
    if provider['protocol']=='ark':return '/contents/generations/tasks','/contents/generations/tasks/{id}'
    contract=provider.get('contract',{})
    return contract.get('submit_path','/contents/generations/tasks'),contract.get('poll_path','/contents/generations/tasks/{id}')

async def submit(provider,bundle):
    from . import providers
    from . import media
    try:
        path,_=paths(provider)
        total=0;seen=set()
        for ref in bundle.get('references',[]):
            if ref.get('file') and ref['file'] not in seen and (mimetypes.guess_type(ref['file'])[0] or '').startswith('audio/'):
                seen.add(ref['file'])
                info=await media.validate_audio(ref['file'])
                duration=max(float(s.get('duration',0)) for s in info['streams'] if s.get('codec_type')=='audio')
                if not 2<=duration<=30: raise ValueError('Seedance 参考音频时长须为2–30秒，未提交')
                total+=duration
        if total>30: raise ValueError('Seedance 参考音频总时长不得超过30秒，未提交')
        body=payload(provider,bundle)
    except Exception as error:raise providers.SubmissionNotSentError(str(error)) from error
    async with httpx.AsyncClient(timeout=120) as client:
        response=await client.post(providers.endpoint(provider,path),headers=providers.headers(provider),json=body)
        providers.require_ok(response);result=response.json()
    remote=providers.dotted(result,provider.get('contract',{}).get('id_path','id')) or result.get('id') or providers.dotted(result,'data.id') or result.get('task_id') or providers.dotted(result,'data.task_id')
    if not remote:raise ValueError('Seedance提交未返回任务ID，请核查渠道记录，禁止自动重复提交')
    return str(remote),body

async def poll(provider,remote,target):
    from . import providers
    _,path=paths(provider)
    async with httpx.AsyncClient(timeout=60) as client:
        response=await client.get(providers.endpoint(provider,path.replace('{id}',quote(remote,safe=''))),headers=providers.headers(provider))
        providers.require_ok(response);result=response.json()
    data=result.get('data',result);contract=provider.get('contract',{})
    state=providers.dotted(result,contract.get('status_path','status')) or data.get('status')
    if state in ('failed','cancelled','expired','error'):raise ValueError('Seedance视频任务失败，请检查渠道任务记录；已保留任务ID')
    if state not in ('succeeded','completed','success'):return None
    url=providers.dotted(data,'content.video_url') or providers.dotted(data,'result.video_url') or providers.dotted(result,contract.get('result_path','url'))
    if not isinstance(url,str):raise ValueError('Seedance任务完成但缺少视频地址')
    return await providers.download(url,target)
