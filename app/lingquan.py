"""Lingquan documented protocols. Discovery never submits a billed task."""
import asyncio
import base64
import copy
import io
import json
import math
import mimetypes
import re
from urllib.parse import quote
import httpx
from PIL import Image, ImageOps
from . import providers


def endpoint(p, path):
    base = providers.validate_url(p['base_url'])
    if base.endswith('/v1'): base = base[:-3]
    return base + path


def safe_detail(value, p):
    """Keep useful error text, never raw responses or credential-bearing URLs."""
    if not isinstance(value, (str, int, float)): return ''
    text = str(value)
    for key in providers.headers(p).values():
        for secret in (key, key.removeprefix('Bearer ')):
            if secret: text = text.replace(secret, '[已隐藏密钥]')
    text = re.sub(r'data:[^\s\"\'<>，；]+', '[已隐藏素材]', text, flags=re.I)
    text = re.sub(r'https?://[^\s\"\'<>，；]+', '[已隐藏地址]', text, flags=re.I)
    text = re.sub(r'(?i)(?:api[_ -]?key|access[_ -]?token|authorization|secret|token)\s*[:=]\s*(?:\"[^\"]*\"|\'[^\']*\'|[^\s,;，；]+)', '[已隐藏凭据]', text)
    text = re.sub(r'(?i)Bearer\s+[^\s,;，；]+|\bsk-[A-Za-z0-9_-]+', '[已隐藏凭据]', text)
    text = re.sub(r'[A-Za-z0-9+/=_-]{96,}', '[已隐藏长数据]', text)
    return ' '.join(text.split())[:500]


def response_diagnostics(p, response, data):
    messages = []
    def collect(value):
        if isinstance(value, dict):
            for key in ('msg', 'message', 'error', 'reason', 'detail', 'failure_reasons', '失败原因'):
                if key in value: collect(value[key])
        elif isinstance(value, list):
            for item in value[:5]: collect(item)
        else:
            message = safe_detail(value, p)
            if message and message not in messages: messages.append(message)
    collect(data)
    if isinstance(data.get('data'), dict): collect(data['data'])
    result = {'http_status':response.status_code, 'code':safe_detail(data.get('code'), p), 'message':'；'.join(messages)[:1000]}
    request_id = data.get('request_id') or response.headers.get('x-request-id')
    if request_id: result['request_id'] = safe_detail(request_id, p)
    return result


class LingquanResponseError(ValueError):
    def __init__(self, diagnostics, prefix='灵泉接口拒绝请求'):
        self.provider_diagnostics = diagnostics
        codes = f"HTTP {diagnostics['http_status']}" + (f"，错误码 {diagnostics['code']}" if diagnostics.get('code') else '')
        detail = diagnostics.get('message') or '接口未提供具体原因，请核查灵泉平台任务记录'
        request_id = '；请求 ID：' + diagnostics['request_id'] if diagnostics.get('request_id') else ''
        super().__init__(f'{prefix}（{codes}）：{detail}{request_id}；未自动重复提交')


async def request(p, method, path, **kwargs):
    if not p.get('secret'): raise ValueError('请填写灵泉 AI API Key')
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.request(method, endpoint(p, path), headers={**providers.headers(p), 'Accept-Language':'zh-CN', **({'anthropic-version':'2023-06-01'} if path == '/v1/messages' else {})}, **kwargs)
    try: data = response.json()
    except ValueError:
        providers.require_ok(response)
        raise ValueError('灵泉接口未返回有效 JSON')
    if not isinstance(data, dict): raise ValueError('灵泉接口响应格式无效')
    if not response.is_success or str(data.get('code')) not in ('None', '0', '200'):
        raise LingquanResponseError(response_diagnostics(p, response, data))
    return data


async def detail(p):
    data = await request(p, 'GET', '/v1/skills/models/-', params={'model':p['model']})
    if data.get('available_for_this_key') is False: raise ValueError('当前灵泉密钥未配置该模型的可用渠道，请在灵泉密钥管理中调整渠道策略')
    return data


async def models(p):
    data = await request(p, 'GET', '/v1/skills/models')
    rows = data.get('models')
    if not isinstance(rows, list): raise ValueError('灵泉模型列表格式无效：应返回 models 数组')
    kinds = {'chat':'text','image':'image','video':'video'}
    found = {x['name']: {'id':x['name'], 'kind':kinds[x['type']], 'protocol':'lingquan'}
             for x in rows if isinstance(x, dict) and isinstance(x.get('name'), str) and x['name']
             and x.get('type') in kinds and x.get('available_for_this_key') is not False}
    return {'ok':True, 'source':'remote', 'models':sorted(found), 'model_details':[found[k] for k in sorted(found)],
            'message':f'已拉取 {len(found)} 个文本、图片和视频模型；已排除密钥策略明确禁用的模型，调用权限以实际任务为准'}


def inline(name, total, field=None):
    path = providers.file_path(name)
    mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    if not (mime.startswith('image/') or mime.startswith('audio/')):
        raise ValueError('灵泉本地素材仅支持图片和音频；参考视频需要公网直链')
    if path.stat().st_size > 10*1024**2: raise ValueError('灵泉内联素材超过单文件 10MB 或合计 30MB，请先压缩')
    content = path.read_bytes()
    limits = (field or {}).get('upload_limits') or {}
    if limits and mime.startswith('image/'):
        label = (field or {}).get('label') or '参考图片'
        try:
            with Image.open(io.BytesIO(content)) as source:
                fmt = (source.format or '').lower()
                formats = limits.get('格式') or []
                if formats and not ({fmt, 'jpg' if fmt == 'jpeg' else fmt} & set(formats)):
                    raise ValueError(f'{label}格式不受支持，请使用 ' + '/'.join(formats))
                image = ImageOps.exif_transpose(source)
                width, height = image.size
                interval = limits.get('宽高比区间')
                if interval and not float(interval[0]) <= width/height <= float(interval[1]):
                    raise ValueError(f'{label}宽高比 {width}:{height} 超出接口允许范围 {interval[0]}–{interval[1]}')
                minimum = int(limits.get('最小边') or 0)
                # Prepare upload bytes only; keep the original tail/asset untouched.
                if min(width, height) < minimum:
                    scale = minimum/min(width, height)
                    image = image.resize((math.ceil(width*scale), math.ceil(height*scale)), Image.Resampling.LANCZOS)
                    output = io.BytesIO()
                    image.save(output, format='PNG')
                    content, mime = output.getvalue(), 'image/png'
                else:
                    mime = Image.MIME.get(source.format, mime)
        except (OSError, Image.DecompressionBombError) as error:
            raise ValueError(f'{label}文件损坏或无法读取，请重新选择图片') from error
    total[0] += len(content)
    if len(content) > 10*1024**2 or total[0] > 30*1024**2: raise ValueError('灵泉内联素材超过单文件 10MB 或合计 30MB，请先压缩')
    return 'data:' + mime + ';base64,' + base64.b64encode(content).decode()


def validate_params(meta, params, *, prompt):
    if not isinstance(prompt, str) or not prompt.strip(): raise ValueError('请填写生成提示词')
    definitions = {x['name']:x for x in meta.get('params', []) if isinstance(x, dict) and x.get('name')}
    # The model schema also lists prompt, but our request sends it at the top level.
    values = {**params, 'prompt':prompt}
    for name in params:
        if name not in definitions: raise ValueError('该灵泉模型不支持参数：' + name)
    for name, field in definitions.items():
        value = values.get(name)
        if field.get('required') and (value is None or value == '' or value == []): raise ValueError('请在该模型的参数 JSON 中设置：' + name)
        if value is None: continue
        options = field.get('options') or []
        if options:
            chosen = next((x for x in options if str(x.get('value')) == str(value)), None)
            if not chosen: raise ValueError('灵泉参数取值不受该模型支持：' + name)
            if chosen.get('currently_unavailable'): raise ValueError('灵泉该参数档位当前没有可用渠道：' + name)
            for key, allowed in (chosen.get('requires') or {}).items():
                if str(values.get(key)) not in [str(x) for x in allowed]: raise ValueError('灵泉参数组合不匹配：' + name + ' / ' + key)


async def submit(p, prompt, params, meta=None):
    try:
        meta = meta or await detail(p)
        params = copy.deepcopy(params)
        # Saved model parameters must never replace the current compiled prompt.
        params.pop('prompt', None)
        validate_params(meta, params, prompt=prompt)
        body = {'model':p['model'], 'prompt':prompt, 'params':params}
        if len(json.dumps(body).encode()) > 50*1024**2: raise ValueError('灵泉请求体超过 50MB，请压缩素材')
    except Exception as error:
        raise providers.SubmissionNotSentError(str(error)) from error
    # Errors after this boundary may represent an accepted/billed task.
    data = await request(p, 'POST', '/v1/media/generate', json=body)
    task = data.get('data', {}).get('task_id') if isinstance(data.get('data'), dict) else None
    if not task: raise ValueError('灵泉创建响应缺少 task_id；为避免重复扣费不会自动重提，请核查平台任务记录')
    return str(task), body


async def poll(p, remote, target):
    data = await request(p, 'GET', '/v1/media/status', params={'task_id':remote})
    if data.get('is_final') is not True: return None
    if data.get('state') == 'failed':
        diagnostics = response_diagnostics(p, httpx.Response(200), data)
        raise LingquanResponseError(diagnostics, '灵泉生成任务失败，已保留任务 ID')
    if data.get('state') != 'success': raise ValueError('灵泉任务终态格式无效，已保留任务 ID')
    url = data.get('result_url')
    if not isinstance(url, str) or not url: raise ValueError('灵泉任务成功但没有结果地址，已保留任务 ID')
    return await providers.download(url, target)


async def video_params(p, bundle):
    """Discover and prepare parameters without submitting a generation task."""
    meta = await detail(p)
    fields = {x['name']:x for x in meta.get('params', [])}
    names = set(fields)
    params = copy.deepcopy(p.get('lingquan_params') or {})
    if 'duration' in names: params['duration'] = str(bundle['duration']).removesuffix('.0')
    if 'aspect_ratio' in names: params['aspect_ratio'] = bundle['ratio']
    if 'resolution' in names: params.setdefault('resolution', p.get('resolution') or '768P')
    refs = bundle.get('references', [])
    # A real preceding tail becomes the next first frame, rather than a loose reference.
    first = next((r['file'] for r in refs if r.get('purpose') == 'continuity'), None) or bundle.get('first_frame') or next((r['file'] for r in refs if r.get('purpose') == 'shot'), None)
    if bundle.get('video_input_mode')=='references':first=None
    total = [0]
    if first:
        if 'images' not in names or 'mode' not in names: raise ValueError('当前灵泉模型不支持已指定的首帧衔接，请选择 MiniMax H3 首尾帧模式')
        params['mode'] = 'shouweizhen'
        params['images'] = [inline(first, total, fields['images'])]
        if bundle.get('last_frame'): params['images'].append(inline(bundle['last_frame'], total, fields['images']))
    elif refs:
        if 'image_url' not in names: raise ValueError('该灵泉模型未定义多图参考，请改用首帧输入或支持参考生的模型')
        params['mode'] = 'cankaosheng'
        images = [r for r in refs if r.get('purpose') != 'voice']
        if len(images) > 9: raise ValueError('灵泉 H3 最多支持 9 张参考图')
        params['image_url'] = [inline(r['file'], total, fields['image_url']) for r in images]
        audio = [r for r in refs if r.get('purpose') == 'voice']
        if audio:
            if 'audio_url' not in names or len(audio) > 3: raise ValueError('该灵泉模型不支持这些音频参考')
            params['audio_url'] = [inline(r['file'], total) for r in audio]
    return params, meta


async def video_submit(p, bundle):
    try:
        params, meta = await video_params(p, bundle)
        prompt = bundle['prompt']
    except Exception as error:
        raise providers.SubmissionNotSentError(str(error)) from error
    return await submit(p, prompt, params, meta)


async def image_params(p, reference):
    meta = await detail(p)
    names = {x['name'] for x in meta.get('params', [])}
    params = copy.deepcopy(p.get('lingquan_params') or {})
    if 'size' in names: params.setdefault('size', p.get('size') or 'auto')
    if 'quality' in names: params.setdefault('quality', 'auto')
    refs = reference if isinstance(reference, list) else [reference] if reference else []
    if refs:
        if 'images' not in names: raise ValueError('该灵泉模型不支持 images 参考图片')
        total = [0]; params['images'] = [inline(r, total) for r in refs]
    return params, meta


async def image_generate(p, prompt, target, reference=None, remote_id=None, submitted=None):
    if not remote_id:
        try:
            params, meta = await image_params(p, reference)
        except Exception as error:
            raise providers.SubmissionNotSentError(str(error)) from error
        remote_id, _ = await submit(p, prompt, params, meta)
        if submitted: submitted(remote_id)
    for _ in range(120):
        result = await poll(p, remote_id, target)
        if result:
            from PIL import Image
            with Image.open(target) as image: image.verify()
            return result
        await asyncio.sleep(5)
    raise ValueError('灵泉生图查询超时；已保留任务 ID，恢复时继续查询原任务')


async def text_generate(p, instructions, context, schema):
    meta = await detail(p)
    system = instructions + '\n严格返回 JSON，不使用 Markdown 围栏。保留输入中的稳定 ID。输出结构：' + json.dumps(schema, ensure_ascii=False)
    user = json.dumps(context, ensure_ascii=False)
    fmt = meta.get('api_format')
    limit = int(p.get('max_tokens') or 6000)
    if fmt == 'openai':
        channel = {**p, 'protocol':'openai', 'base_url':endpoint(p, '/v1')}
        return await providers.text_generate(channel, instructions, context, schema)
    if fmt == 'anthropic':
        body = {'model':p['model'], 'system':system, 'messages':[{'role':'user', 'content':user}], 'max_tokens':limit}
        data = await request(p, 'POST', '/v1/messages', json=body)
        text = ''.join(x.get('text','') for x in data.get('content', []) if x.get('type') == 'text')
        truncated = data.get('stop_reason') == 'max_tokens'
    elif fmt == 'gemini':
        body = {'systemInstruction':{'parts':[{'text':system}]}, 'contents':[{'role':'user','parts':[{'text':user}]}],
                'generationConfig':{'maxOutputTokens':limit, 'responseMimeType':'application/json'}}
        data = await request(p, 'POST', '/v1beta/models/' + quote(p['model'], safe='') + ':generateContent', json=body)
        candidate = (data.get('candidates') or [{}])[0]
        text = ''.join(x.get('text','') for x in candidate.get('content', {}).get('parts', []) if not x.get('thought'))
        truncated = candidate.get('finishReason') == 'MAX_TOKENS'
    else: raise ValueError('灵泉文本模型协议无法识别，请拉取模型或核对模型 ID')
    if truncated: raise providers.ModelOutputError('模型输出达到长度上限，未写入作品', text)
    try: output = providers.parse_json(text)
    except ValueError as error: raise providers.ModelOutputError('模型返回的 JSON 数据格式有误，未写入作品', text) from error
    return output, data.get('usage', data.get('usageMetadata', {})), body
