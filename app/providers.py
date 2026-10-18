"""Explicit service adapters. API keys never leave the local backend after saving."""
import base64
import asyncio
import copy
import ctypes
import json
import os
from pathlib import Path
from urllib.parse import urlparse
import httpx
from .store import get, put, MEDIA, ROOT
from .presets import PROTOCOLS
from . import model_catalog


def protect(value, decrypt=False):
    if not value: return ''
    if os.name != 'nt': raise ValueError('当前密钥存储要求 Windows DPAPI')
    class Blob(ctypes.Structure):
        _fields_ = [('size', ctypes.c_ulong), ('data', ctypes.POINTER(ctypes.c_char))]
    raw = base64.b64decode(value) if decrypt else value.encode()
    buf = ctypes.create_string_buffer(raw); incoming = Blob(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    outgoing = Blob()
    function = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    if not function(ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing)):
        raise ValueError('Windows 密钥保护失败')
    try:
        data = ctypes.string_at(outgoing.data, outgoing.size)
        return data.decode() if decrypt else base64.b64encode(data).decode()
    finally: ctypes.windll.kernel32.LocalFree(outgoing.data)


def settings():
    try:
        value = get('settings', 'main')
        value['providers'] = [model_catalog.normalize(p) for p in value['providers']]
        return value
    except KeyError: return {'id': 'main', 'providers': [], 'ffmpeg': '', 'ffprobe': '', 'deployment': {}}


def public_settings():
    result = copy.deepcopy(settings())
    for p in result['providers']:
        p['has_key'] = bool(p.pop('secret', ''))
        p['has_ak'] = bool(p.pop('ak_secret', ''))
        p['has_sk'] = bool(p.pop('sk_secret', ''))
        p['video_profiles'] = {m['id']: model_catalog.resolve(p,'video',m['id']).get('capabilities',{}) for m in p.get('models',[]) if m['kind']=='video'}
    return result


def save_settings(value):
    value = copy.deepcopy(value)
    previous = settings(); by_id = {p['id']: p for p in previous['providers']}
    # Skill selection is owned by /api/skills/defaults, independent of model forms.
    if 'skill_defaults' in previous: value['skill_defaults']=previous['skill_defaults']
    else: value.pop('skill_defaults',None)
    ids = set()
    value['providers'] = [model_catalog.normalize(p) for p in value.get('providers', [])]
    for p in value.get('providers', []):
        if not p.get('id') or p['id'] in ids: raise ValueError('服务 ID 缺失或重复')
        ids.add(p['id'])
        if p.get('protocol') not in PROTOCOLS.get(p.get('kind'), {}): raise ValueError('服务用途与调用协议不匹配')
        if not p.get('name', '').strip(): raise ValueError('请填写服务名称')
        if p['protocol'] != 'comfy' and not p['models']: raise ValueError('请至少添加一个渠道模型')
        validate_url(p.get('base_url', ''))
        key = p.pop('api_key', None)
        p['secret'] = protect(key.strip()) if key and key.strip() else by_id.get(p['id'], {}).get('secret', '')
        if p.pop('clear_key', False): p['secret'] = ''
        p.pop('has_key', None)
        for field, encrypted, flag in [('access_key','ak_secret','has_ak'), ('secret_key','sk_secret','has_sk')]:
            key = p.pop(field, None)
            p[encrypted] = protect(key.strip()) if key and key.strip() else by_id.get(p['id'], {}).get(encrypted, '')
            p.pop(flag, None)
        if p.pop('clear_access_keys', False): p['ak_secret'] = p['sk_secret'] = ''
    put('settings', {'id': 'main', **value})
    return public_settings()


def validate_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('服务地址须为 http/https，密钥请填在独立输入框')
    return url.rstrip('/')


def endpoint(provider, path):
    base = validate_url(provider['base_url'])
    if base.endswith(path): return base
    return base + path


def headers(provider):
    key = protect(provider['secret'], True) if provider.get('secret') else ''
    if provider.get('auth_header') == 'api-key': return {'api-key': key} if key else {}
    return {'Authorization': 'Bearer ' + key} if key else {}


def provider_for(p, kind, explicit=None):
    ident = explicit or p.get('bindings', {}).get(kind)
    found = next((x for x in settings()['providers'] if x['id'] == ident), None)
    if not found: raise ValueError('尚未选择' + {'text':'文字','image':'图像','video':'视频','white':'白模'}.get(kind,kind) + '服务，请在右侧选择或在设置中添加')
    return model_catalog.resolve(found, kind, p.get('model_bindings', {}).get(kind))


def parse_json(text):
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[-1].rsplit('```', 1)[0]
    try: return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find('{'), text.rfind('}')
        if start < 0: raise ValueError('文字模型未返回 JSON 对象')
        try: return json.loads(text[start:end+1])
        except json.JSONDecodeError as error: raise ValueError('模型 JSON 格式错误：' + str(error))


class SubmissionNotSentError(ValueError):
    """Media preparation failed before a generation request was sent."""


class ModelOutputError(ValueError):
    """A bad model response, distinct from an HTTP/authentication failure."""
    def __init__(self, message, raw_output='', diagnostics=None):
        super().__init__(message)
        self.raw_output = raw_output
        self.diagnostics = diagnostics or {}


async def text_generate(provider, instructions, context, schema):
    if provider.get('protocol') == 'lingquan':
        from .lingquan import text_generate as generate
        return await generate(provider, instructions, context, schema)
    if provider.get('kind') != 'text' or provider.get('protocol') != 'openai':
        raise ValueError('文字阶段需要 OpenAI 兼容 chat/completions 服务')
    payload = {'model': provider['model'], 'messages': [
        {'role': 'system', 'content': instructions + '\n严格返回 JSON，不使用 Markdown 围栏。保留输入中的稳定 ID，不添加已完成的视频或假素材。输出结构：' + json.dumps(schema, ensure_ascii=False)},
        {'role': 'user', 'content': json.dumps(context, ensure_ascii=False)}], 'temperature': provider.get('temperature', .75),
        provider.get('token_field', 'max_tokens'): int(provider.get('max_tokens', 6000))}
    options = provider.get('text_options', {})
    # Keep optional official flags separate from the required prompt/model fields.
    for key in ('thinking', 'enable_thinking', 'reasoning_effort', 'reasoning_split'):
        if key in options: payload[key] = options[key]
    if provider.get('json_mode'): payload['response_format'] = {'type': 'json_object'}
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(endpoint(provider, '/chat/completions'), headers=headers(provider), json=payload)
        require_ok(response)
        result = response.json()
    choices = result.get('choices') or []
    choice = choices[0] if choices and isinstance(choices[0], dict) else {}
    message = choice.get('message') or {}
    content = message.get('content') if isinstance(message, dict) else None
    diagnostics = {'finish_reason': choice.get('finish_reason'), 'output_characters': len(content) if isinstance(content, str) else 0,
                   'max_output_tokens': payload[provider.get('token_field', 'max_tokens')], 'usage': result.get('usage', {})}
    if choice.get('finish_reason') == 'length':
        raise ModelOutputError('模型输出达到长度上限，结果被截断；未写入作品。请缩短本次输出或分批处理。', content or '', diagnostics)
    if not isinstance(content, str) or not content.strip():
        raise ModelOutputError('模型没有返回可用的正文数据，未写入作品。', '', diagnostics)
    try: output = parse_json(content)
    except ValueError as error:
        diagnostics['parse_error'] = str(error)
        raise ModelOutputError('模型返回的 JSON 数据格式有误，未写入作品。', content, diagnostics) from error
    return output, result.get('usage', {}), payload


def require_ok(response):
    if response.is_success: return
    # Do not echo raw provider responses, which may contain credential-bearing URLs.
    reasons = {401: '密钥无效或已过期', 403: '服务拒绝访问', 404: '接口或模型不存在', 429: '服务限流或额度不足', 500:'服务内部错误', 502:'服务网关错误', 503:'服务暂不可用'}
    raise ValueError(f"服务 HTTP {response.status_code}：" + reasons.get(response.status_code, '请求失败，请检查参数与服务日志'))


async def download(url, target):
    validate_url(url)
    async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
        async with client.stream('GET', url) as response:
            require_ok(response)
            size = 0
            with target.open('wb') as out:
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > 2 * 1024**3: raise ValueError('结果超过2GB，请手工导入')
                    out.write(chunk)
    return target.name


def file_path(name):
    path = (MEDIA / name).resolve()
    if path.parent != MEDIA.resolve() or not path.is_file(): raise ValueError('素材文件不存在或路径无效')
    return path


def async_image_contract(provider):
    contract = provider.get('image_contract')
    if contract: return contract
    if urlparse(provider.get('base_url', '')).hostname == 'api.ai-tudou.net' and (provider.get('model', '').endswith('-async') or provider.get('model') == 'gpt-image-2-all'):
        return {'submit_path': '/images/generations/async', 'poll_path': '/tasks/{id}'}
    return None


async def async_image_generate(provider, prompt, target, reference=None, remote_id=None, submitted=None):
    contract = async_image_contract(provider)
    async with httpx.AsyncClient(timeout=120) as client:
        if not remote_id:
            payload = {'model': provider['model'], 'prompt': prompt, 'size': provider.get('size', '16:9'),
                       'resolution': provider.get('resolution', '1k'), 'quality': provider.get('quality', 'medium')}
            refs = reference if isinstance(reference, list) else [reference] if reference else []
            if refs:
                import mimetypes
                payload['images'] = ['data:' + (mimetypes.guess_type(r)[0] or 'image/png') + ';base64,' + base64.b64encode(file_path(r).read_bytes()).decode() for r in refs]
            response = await client.post(endpoint(provider, contract['submit_path']), headers=headers(provider), json=payload)
            require_ok(response)
            result = response.json(); remote_id = dotted(result, 'data.id') or result.get('task_id') or result.get('id')
            if not remote_id: raise ValueError('异步生图响应没有任务 ID，请核查服务记录，未自动重复提交')
            if submitted: submitted(str(remote_id))
        poll_failures = 0
        for _ in range(360):
            await asyncio.sleep(5)
            try:
                response = await client.get(endpoint(provider, contract['poll_path'].replace('{id}', str(remote_id))), headers=headers(provider))
                if response.status_code in (408,429,500,502,503,504):
                    raise httpx.HTTPStatusError('临时查询错误 '+str(response.status_code),request=response.request,response=response)
            except (httpx.TransportError,httpx.HTTPStatusError) as error:
                poll_failures += 1
                if poll_failures >= 5:raise ValueError('异步生图查询连接中断；已保留任务 ID，可恢复查询：'+(str(error) or type(error).__name__)) from error
                continue
            poll_failures = 0
            require_ok(response); result = response.json(); data = result.get('data', result)
            state = str(data.get('status', '')).lower()
            if state in ('failed', 'error', 'cancelled'): raise ValueError('异步生图任务失败，请检查渠道任务记录；已保留任务 ID')
            if state not in ('completed', 'succeeded', 'success'): continue
            item = dotted(data, 'result.images.0', {})
            url = item.get('url')
            if isinstance(url, list): url = url[0] if url else None
            if not url: raise ValueError('异步生图已完成但没有图片地址；已保留任务 ID')
            for attempt in range(3):
                try:
                    await download(url, target)
                    break
                except httpx.TransportError as error:
                    if attempt==2:raise ValueError('异步生图已完成，图片下载连接中断；已保留任务 ID，可恢复下载：'+(str(error) or type(error).__name__)) from error
                    await asyncio.sleep(3)
            from PIL import Image
            with Image.open(target) as image: image.verify()
            return target.name
    raise ValueError('异步生图查询超时；已保留任务 ID，恢复时继续查询')


async def image_generate(provider, prompt, target, reference=None, remote_id=None, submitted=None):
    if provider.get('protocol') == 'lingquan':
        from .lingquan import image_generate as generate
        return await generate(provider, prompt, target, reference, remote_id, submitted)
    if async_image_contract(provider):
        return await async_image_generate(provider, prompt, target, reference, remote_id, submitted)
    if isinstance(reference, list):
        if len(reference) > 1: raise ValueError('当前图片协议仅支持一张参考图')
        reference = reference[0] if reference else None
    if provider.get('protocol') in ('ark', 'dashscope', 'jimeng'):
        from .official import image_generate as official_image
        return await official_image(provider, prompt, target, reference)
    async with httpx.AsyncClient(timeout=240) as client:
        if reference:
            with file_path(reference).open('rb') as img:
                response = await client.post(endpoint(provider, '/images/edits'), headers=headers(provider),
                    data={'model': provider['model'], 'prompt': prompt, 'n': '1', 'size': provider.get('size', '1024x1024')},
                    files={'image': (reference, img, 'image/png')})
        else:
            response = await client.post(endpoint(provider, '/images/generations'), headers=headers(provider),
                json={'model': provider['model'], 'prompt': prompt, 'n': 1, 'size': provider.get('size', '1024x1024')})
        require_ok(response); item = response.json()['data'][0]
    if item.get('b64_json'): target.write_bytes(base64.b64decode(item['b64_json']))
    elif item.get('url'): await download(item['url'], target)
    else: raise ValueError('图像服务没有返回 url 或 b64_json')
    from PIL import Image
    with Image.open(target) as image: image.verify()
    return target.name


def mapping_check(provider):
    workflow = provider.get('workflow', {})
    if not isinstance(workflow, dict) or not workflow or 'nodes' in workflow:
        raise ValueError('须导入 ComfyUI API 格式工作流（开发者模式→导出 API），普通画布 JSON 无法直接提交')
    if not all(isinstance(n, dict) and 'class_type' in n and isinstance(n.get('inputs'), dict) for n in workflow.values()):
        raise ValueError('API 工作流节点须包含 class_type 和 inputs')
    mapping = provider.get('mapping', {})
    for field in ('prompt', 'duration', 'seed'):
        m = mapping.get(field)
        if not m: raise ValueError('工作流缺少映射：' + field)
        node = workflow.get(str(m.get('node')))
        if not node or m.get('input') not in node['inputs']: raise ValueError('映射节点/字段不存在：' + field)
    slots=set()
    for field in ('images','audio'):
        for m in mapping.get(field, []):
            if str(m.get('node')) not in workflow or m.get('input') not in workflow[str(m['node'])]['inputs']:
                raise ValueError('参考素材映射无效：' + field)
            slot=(str(m['node']),m['input'])
            if slot in slots: raise ValueError('参考映射槽位重复，会覆盖素材：'+str(slot))
            slots.add(slot)
    output = mapping.get('output_node')
    if not output or str(output) not in workflow: raise ValueError('请映射视频输出节点 output_node')
    return workflow, mapping


async def comfy_check(provider):
    workflow, mapping = mapping_check(provider)
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(endpoint(provider, '/object_info')); require_ok(response); info = response.json()
        response = await client.get(endpoint(provider, '/system_stats')); require_ok(response); stats = response.json()
    missing = sorted({n['class_type'] for n in workflow.values()} - set(info))
    missing_models = []
    for node in workflow.values():
        spec = info.get(node['class_type'], {}).get('input', {})
        inputs = {**spec.get('required', {}), **spec.get('optional', {})}
        for key, val in node['inputs'].items():
            choices = inputs.get(key, [None])[0]
            if isinstance(val, str) and isinstance(choices, list) and val not in choices:
                missing_models.append(node['class_type'] + '.' + key + ': ' + val)
    return {'ok': not missing and not missing_models, 'missing_nodes': missing, 'missing_models': missing_models, 'stats': stats, 'message': '服务和节点已检查；本地 H3 仍需样片验收'}


async def comfy_submit(provider, bundle):
    workflow, mapping = mapping_check(provider); workflow = copy.deepcopy(workflow); mapping = copy.deepcopy(mapping)
    def set_input(m, value): workflow[str(m['node'])]['inputs'][m['input']] = value
    for key in ('prompt', 'duration', 'seed', 'ratio'):
        if mapping.get(key):
            value = bundle[key]
            if key == 'ratio': value = mapping.get('ratio_values', {}).get(value, value)
            set_input(mapping[key], value)
    image_refs = [r for r in bundle['references'] if r['purpose'] != 'voice']
    audio_refs = [r for r in bundle['references'] if r['purpose'] == 'voice']
    # H3 references alone do not pin a frame. Use the native timeline guide for
    # a predecessor's selected tail instead of treating it as another picture.
    h3 = next(((key, node) for key, node in workflow.items() if node['class_type'] == 'MiniMaxH3ReferenceToVideo'), None)
    if h3:
        if bundle.get('speech_segment') is not None:
            from . import native_audio
            speakers = {r['speaker'] for r in native_audio.dialogue_rows(bundle['speech_segment'])}
            audio_refs = [r for r in audio_refs if r.get('name') in speakers or r.get('asset_id') in speakers]
        if len(audio_refs) > 3: raise ValueError('H3 每镜最多支持 3 个角色音色参考，请减少本镜头说话角色')
        # Build only the actual reference inputs, with the same order as Audio tags.
        # This is reference conditioning, never a timeline audio guide.
        for key in list(h3[1]['inputs']):
            if key.startswith('ref_audios.'): del h3[1]['inputs'][key]
        mapping['audio'] = []
        for index, reference in enumerate(audio_refs):
            node_id = 'studio_voice_reference_' + str(index)
            if node_id in workflow: raise ValueError('工作流包含保留的音色参考节点名称')
            workflow[node_id] = {'class_type':'LoadAudio','inputs':{'audio':reference['file']}}
            h3[1]['inputs']['ref_audios.ref_audio_' + str(index)] = [node_id,0]
            mapping['audio'].append({'node':node_id,'input':'audio'})
    render = bundle.get('render') or {}
    if render:
        if not h3: raise ValueError('本地 H3 画质参数需要原生 H3 工作流')
        for key in ('width', 'height'):
            value = render.get(key)
            if not isinstance(value, int) or not 32 <= value <= 4096 or value % 32: raise ValueError('H3 分辨率必须为 32 的倍数，且介于 32 与 4096')
            h3[1]['inputs'][key] = value
        steps = render.get('steps')
        if not isinstance(steps, int) or not 1 <= steps <= 100: raise ValueError('H3 采样步数需在 1–100 之间')
        schedulers = [n for n in workflow.values() if n['class_type'] == 'BasicScheduler']
        if len(schedulers) != 1: raise ValueError('工作流采样器不唯一，无法应用 H3 画质参数')
        schedulers[0]['inputs']['steps'] = steps
    anchors = [r for r in image_refs if r['purpose'] == 'continuity'] if h3 else []
    if not anchors and h3 and bundle.get('first_frame'):
        anchors = [{'file': bundle['first_frame'], 'purpose': 'first_frame'}]
    dialogue = bundle.get('dialogue_audio')
    if dialogue and not h3: raise ValueError('固定对白音频需要支持时间轴音频引导的 H3 工作流')
    if anchors or dialogue:
        image_refs = [r for r in image_refs if r['purpose'] != 'continuity']
        h3_id, h3_node = h3
        original = [h3_id, 0]
        guide_id = 'studio_continuity_guide'
        if guide_id in workflow or 'studio_continuity_image' in workflow: raise ValueError('工作流包含保留的衔接节点名称')
        workflow[guide_id] = {'class_type': 'MiniMaxH3AddGuide', 'inputs': {'positive': original, 'latent': [h3_id, 1],
            'vae': h3_node['inputs']['vae'], 'frame_idx': 0}}
        if anchors:
            workflow['studio_continuity_image'] = {'class_type': 'LoadImage', 'inputs': {'image': anchors[0]['file']}}
            workflow[guide_id]['inputs']['image'] = ['studio_continuity_image', 0]
        if dialogue:
            workflow['studio_dialogue_audio'] = {'class_type': 'LoadAudio', 'inputs': {'audio': dialogue}}
            workflow[guide_id]['inputs'].update(audio=['studio_dialogue_audio', 0], audio_vae=h3_node['inputs']['audio_vae'])
        consumers = [node for key, node in workflow.items() if key != guide_id and node['inputs'].get('conditioning') == original]
        if not consumers: raise ValueError('未找到 H3 条件输入的采样器，无法注入首帧衔接')
        for node in consumers: node['inputs']['conditioning'] = [guide_id, 0]
    if h3:
        if len(image_refs) > 9: raise ValueError('H3 每镜最多支持 9 张图像参考，请减少关联参考图')
        for key in list(h3[1]['inputs']):
            if key.startswith('ref_images.'): del h3[1]['inputs'][key]
        mapping['images'] = []
        for index, reference in enumerate(image_refs):
            node_id = 'studio_image_reference_' + str(index)
            if node_id in workflow: raise ValueError('工作流包含保留的图像参考节点名称')
            workflow[node_id] = {'class_type':'LoadImage','inputs':{'image':reference['file']}}
            h3[1]['inputs']['ref_images.ref_image_' + str(index)] = [node_id,0]
            mapping['images'].append({'node':node_id,'input':'image'})
        from . import native_audio
        set_input(mapping['prompt'], native_audio.h3_prompt(bundle, image_refs, audio_refs))
    if len(image_refs) > len(mapping.get('images', [])): raise ValueError('图像参考数量超过工作流映射槽位，不能静默丢弃素材')
    if len(audio_refs) > len(mapping.get('audio', [])): raise ValueError('声音参考数量超过工作流映射槽位，不能静默丢弃音色')
    async with httpx.AsyncClient(timeout=60) as client:
        if anchors:
            with file_path(anchors[0]['file']).open('rb') as f:
                response = await client.post(endpoint(provider, '/upload/image'), files={'image': (anchors[0]['file'], f)}, data={'overwrite': 'true'})
            require_ok(response); uploaded = response.json()
            workflow['studio_continuity_image']['inputs']['image'] = (uploaded.get('subfolder', '').rstrip('/') + '/' if uploaded.get('subfolder') else '') + uploaded['name']
        if dialogue:
            with file_path(dialogue).open('rb') as f:
                response = await client.post(endpoint(provider, '/upload/image'), files={'image': (dialogue, f)}, data={'overwrite': 'true'})
            require_ok(response); uploaded = response.json()
            workflow['studio_dialogue_audio']['inputs']['audio'] = (uploaded.get('subfolder', '').rstrip('/') + '/' if uploaded.get('subfolder') else '') + uploaded['name']
        for group, refs in [('images', image_refs), ('audio', audio_refs)]:
            for index, slot in enumerate(mapping.get(group, [])):
                if index >= len(refs):
                    # Unused loader slots would otherwise send the template's unrelated image.
                    if refs: reference = refs[-1]
                    else: raise ValueError('工作流要求参考素材但当前输入为空，请改用文生视频工作流')
                else: reference = refs[index]
                with file_path(reference['file']).open('rb') as f:
                    response = await client.post(endpoint(provider, '/upload/image'), files={'image': (reference['file'], f)}, data={'overwrite': 'true'})
                require_ok(response); uploaded = response.json(); name = uploaded['name']
                if uploaded.get('subfolder'): name = uploaded['subfolder'] + '/' + name
                set_input(slot, name)
        response = await client.post(endpoint(provider, '/prompt'), json={'prompt': workflow, 'client_id': bundle['project_id']})
        require_ok(response); result = response.json()
        if result.get('node_errors'): raise ValueError('ComfyUI 节点参数校验失败，请在工作流设置中检查')
    return result['prompt_id'], workflow


async def comfy_poll(provider, remote_id, target):
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(endpoint(provider, '/history/' + remote_id)); require_ok(response)
        history = response.json().get(remote_id)
        if not history: return None
        status = history.get('status', {})
        if status.get('status_str') == 'error':
            messages = json.dumps(status.get('messages', []), ensure_ascii=False)
            if 'out of memory' in messages.lower(): raise ValueError('ComfyUI 显存不足，请降低时长/分辨率或启用卸载')
            raise ValueError('ComfyUI 执行失败，请检查服务端节点日志')
        output = history.get('outputs', {}).get(str(provider['mapping']['output_node']), {})
        items = output.get('videos', []) + output.get('gifs', []) + output.get('images', [])
        videos = [x for x in items if Path(x.get('filename', '')).suffix.lower() in ('.mp4', '.webm', '.mov', '.mkv')]
        if not videos:
            if status.get('completed'): raise ValueError('输出节点没有视频文件，请检查 output_node 映射')
            return None
        item = videos[0]
        response = await client.get(endpoint(provider, '/view'), params={k:item.get(k, '') for k in ('filename','subfolder','type')}); require_ok(response)
        target.write_bytes(response.content)
    return target.name


def dotted(obj, path, default=None):
    for part in path.split('.'):
        try: obj = obj[int(part)] if isinstance(obj, list) else obj[part]
        except (KeyError, IndexError, TypeError, ValueError): return default
    return obj


async def generic_submit(provider, bundle):
    # User-configured third-party/official async JSON API. References use data URLs.
    contract = provider.get('contract', {})
    tudou_h3 = urlparse(provider.get('base_url', '')).hostname == 'api.ai-tudou.net' and provider.get('model') == 'minimax-h3'
    reference_sources = list(bundle['references'])
    if tudou_h3 and bundle.get('first_frame'):
        first_index = next((i for i, r in enumerate(reference_sources) if r['file'] == bundle['first_frame']), None)
        if first_index is None:
            raise ValueError('首帧没有包含在真实参考素材中')
        reference_sources.insert(0, reference_sources.pop(first_index))
    payload = copy.deepcopy(contract.get('body', {}))
    for field in ('model', 'prompt', 'duration', 'ratio', 'seed'):
        key = contract.get('fields', {}).get(field)
        if key: payload[key] = provider['model'] if field == 'model' else bundle[field]
    refs = []
    import mimetypes
    counts = {'image': 0, 'audio': 0, 'video': 0}
    for r in reference_sources:
        f = file_path(r['file']); mime = mimetypes.guess_type(f.name)[0] or 'application/octet-stream'
        modality = mime.split('/')[0]
        if modality not in counts: raise ValueError('视频参考素材类型不支持：' + f.suffix)
        counts[modality] += 1
        refs.append({'purpose': r['purpose'], 'uri': 'data:' + mime + ';base64,' + base64.b64encode(f.read_bytes()).decode()})
    cap = provider.get('capabilities', {})
    if counts['video'] and not cap.get('video_reference'):
        raise ValueError('当前第三方渠道未声明支持视频参考，未提交')
    if counts['audio'] and cap.get('audio_reference') is False:
        raise ValueError('当前第三方渠道配置未启用经过验证的音频参考，未提交')
    for modality, key in [('image', 'max_images'), ('audio', 'max_audio'), ('video', 'max_video')]:
        if key in cap and counts[modality] > cap[key]:
            raise ValueError('参考' + {'image':'图片','audio':'音频','video':'视频'}[modality] + '超过当前渠道上限')
    if refs:
        key = contract.get('fields', {}).get('references')
        if not key and not tudou_h3: raise ValueError('当前第三方协议没有配置多模态素材字段')
        if key: payload[key] = refs
    if bundle.get('first_frame'):
        key=contract.get('fields',{}).get('first_frame')
        if not key and not tudou_h3:raise ValueError('当前视频渠道没有首帧字段映射，未提交')
        first=next((r['uri'] for r,original in zip(refs,reference_sources) if original['file']==bundle['first_frame']),None)
        if not first:raise ValueError('首帧没有包含在真实参考素材中')
        if tudou_h3 and not first.startswith('data:image/'):
            raise ValueError('首帧必须是图片，未提交')
        if key and not tudou_h3: payload[key]=first
    if tudou_h3:
        # The old generic references[{purpose,uri}] is silently ignored by this
        # gateway. Its request decoder confirms images is a string array.
        # Audio/video mappings require a verified channel contract, not merely
        # an announcement that the upstream model has those capabilities.
        old_key = contract.get('fields', {}).get('references')
        if old_key: payload.pop(old_key, None)
        ratio_key = contract.get('fields', {}).get('ratio')
        if ratio_key and ratio_key != 'aspect_ratio': payload.pop(ratio_key, None)
        payload['aspect_ratio'] = bundle['ratio']
        payload.setdefault('resolution', '720p')
        if not 3 <= bundle['duration'] <= 15 or int(bundle['duration']) != bundle['duration']:
            raise ValueError('土豆 H3 时长须为 3–15 秒的整数，未提交')
        grouped = {'image': [], 'audio': [], 'video': []}
        binding = []
        labels = {'image':'图', 'audio':'音频', 'video':'视频'}
        for ref, source in zip(refs, reference_sources):
            kind = ref['uri'][5:].split('/')[0]
            grouped[kind].append(ref['uri'])
            binding.append(f"{labels[kind]}{len(grouped[kind])}：{source.get('name','参考素材')}，用途 {source['purpose']}")
        for kind, field in [('image','image_references'), ('audio','audio_references'), ('video','video_references')]:
            if not grouped[kind]: continue
            key = contract.get('fields', {}).get(field) or {'image':'images', 'video':'videos'}.get(kind)
            if not key:
                raise ValueError('土豆 H3 已公告支持参考' + ('音频' if kind=='audio' else '视频') + '，但当前尚未验证对应参数映射，未提交；请提供站方最新请求示例')
            target = payload
            parts = key.split('.')
            for part in parts[:-1]: target = target.setdefault(part, {})
            target[parts[-1]] = grouped[kind]
        if binding:
            prompt_key = contract.get('fields', {}).get('prompt', 'prompt')
            if bundle.get('first_frame'):
                binding.append('以图一为首帧，保持图一的构图、人物站位与起始状态；其他图片按上述用途作为参考。')
            payload[prompt_key] = '\n'.join(binding) + '\n\n' + payload.get(prompt_key, '')
    path = contract.get('submit_path', '')
    if not path.startswith('/') or '://' in path: raise ValueError('提交路径应为相对服务路径，例如 /v1/videos')
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(endpoint(provider, path), headers=headers(provider), json=payload); require_ok(response)
        result = response.json()
    remote = dotted(result, contract.get('id_path', 'id'))
    if not remote: raise ValueError('提交响应缺少任务 ID；为避免重复费用不会自动重试提交，请核查服务记录')
    return str(remote), payload


async def generic_poll(provider, remote_id, target):
    contract = provider.get('contract', {}); path = contract.get('poll_path', '').replace('{id}', remote_id)
    if not path.startswith('/') or '://' in path: raise ValueError('查询路径配置错误')
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(endpoint(provider, path), headers=headers(provider)); require_ok(response); result = response.json()
    state = dotted(result, contract.get('status_path', 'status'))
    if state in contract.get('failure_states', ['failed', 'error', 'cancelled']):
        detail = dotted(result,'data.error.message') or dotted(result,'error.message') or dotted(result,'data.fail_reason')
        raise ValueError('视频服务任务失败：' + (detail[:1000] if isinstance(detail,str) and detail.strip() else str(state)))
    if state not in contract.get('success_states', ['succeeded', 'completed']): return None
    url = dotted(result, contract.get('result_path', 'url'))
    if not isinstance(url, str): raise ValueError('任务完成但没有结果 URL，请检查响应映射')
    return await download(url, target)


async def video_submit(provider, bundle):
    from . import seedance
    if seedance.is_25(provider): return await seedance.submit(provider,bundle)
    if provider['protocol'] == 'lingquan':
        from .lingquan import video_submit as submit
        return await submit(provider, bundle)
    if provider['protocol'] == 'comfy': return await comfy_submit(provider, bundle)
    if provider['protocol'] == 'json-video': return await generic_submit(provider, bundle)
    from .official import video_submit as official_submit
    return await official_submit(provider, bundle)


async def video_poll(provider, remote, target):
    from . import seedance
    if seedance.is_25(provider): return await seedance.poll(provider,remote,target)
    if provider['protocol'] == 'lingquan':
        from .lingquan import poll
        return await poll(provider, remote, target)
    if provider['protocol'] == 'comfy': return await comfy_poll(provider, remote, target)
    if provider['protocol'] == 'json-video': return await generic_poll(provider, remote, target)
    from .official import video_poll as official_poll
    return await official_poll(provider, remote, target)
