"""Native official image/video contracts; never log signed headers/credentials."""
import asyncio
import base64
import hashlib
import hmac
import json
import mimetypes
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse, quote
import httpx
from . import providers as p


def data_url(name):
    path = p.file_path(name)
    return 'data:' + (mimetypes.guess_type(path.name)[0] or 'application/octet-stream') + ';base64,' + base64.b64encode(path.read_bytes()).decode()


async def request(provider, path, payload=None, extra=None):
    async with httpx.AsyncClient(timeout=240 if provider['kind'] == 'image' else 120) as client:
        headers = {**p.headers(provider), **(extra or {})}
        if payload is None: response = await client.get(p.endpoint(provider, path), headers=headers)
        else: response = await client.post(p.endpoint(provider, path), headers=headers, json=payload)
        p.require_ok(response)
        result = response.json()
    if result.get('code') or result.get('error'):
        raise ValueError('官方接口拒绝请求，请检查模型权限、额度和参数（响应包含错误码）')
    return result


def signed_headers(provider, query, body, timestamp=None):
    ak = p.protect(provider.get('ak_secret', ''), True)
    sk = p.protect(provider.get('sk_secret', ''), True)
    if not ak or not sk: raise ValueError('即梦官方服务需要填写 Access Key 和 Secret Key')
    stamp = timestamp or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    digest = hashlib.sha256(body).hexdigest()
    host = urlparse(p.validate_url(provider['base_url'])).netloc
    fields = {'content-type': 'application/json', 'host': host, 'x-content-sha256': digest, 'x-date': stamp}
    names = ';'.join(sorted(fields))
    canonical = '\n'.join(['POST', '/', query, ''.join(k + ':' + fields[k] + '\n' for k in sorted(fields)), names, digest])
    scope = stamp[:8] + '/cn-north-1/cv/request'
    sign_text = '\n'.join(['HMAC-SHA256', stamp, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    signing_key = sk.encode()
    for step in (stamp[:8], 'cn-north-1', 'cv', 'request'):
        signing_key = hmac.new(signing_key, step.encode(), hashlib.sha256).digest()
    signature = hmac.new(signing_key, sign_text.encode(), hashlib.sha256).hexdigest()
    return {**fields, 'Authorization': f'HMAC-SHA256 Credential={ak}/{scope}, SignedHeaders={names}, Signature={signature}'}


async def cv_request(provider, action, payload):
    parsed = urlparse(p.validate_url(provider['base_url']))
    if parsed.path not in ('', '/') or parsed.query:
        raise ValueError('即梦服务地址应为根地址，不附带路径或查询参数')
    query = urlencode({'Action': action, 'Version': '2022-08-31'})
    body = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    headers = signed_headers(provider, query, body)
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(provider['base_url'].rstrip('/') + '/?' + query, headers=headers, content=body)
        p.require_ok(response); result = response.json()
    if result.get('code') != 10000:
        # Raw messages may echo input credentials; return only the documented numeric code.
        code = result.get('code')
        raise ValueError('即梦官方请求失败（错误码 ' + (str(code) if isinstance(code, int) else '未知') + '），请检查权限、额度和参数')
    return result.get('data', {})


def video_payload(provider, bundle):
    duration = float(bundle['duration'])
    if not duration.is_integer(): raise ValueError('当前官方视频接口要求整数秒，请修改小节时长')
    cap = provider.get('capabilities', {})
    if not cap.get('min_duration', .5) <= duration <= cap.get('max_duration', 15):
        raise ValueError('小节时长超出当前视频服务范围')
    if cap.get('durations') and duration not in cap['durations']:
        raise ValueError('当前模型时长支持：' + '、'.join(map(str, cap['durations'])) + ' 秒')
    images = [r for r in bundle['references'] if r['purpose'] != 'voice']
    audio = [r for r in bundle['references'] if r['purpose'] == 'voice']
    if len(images) > cap.get('max_images', 9): raise ValueError('参考图数量超出当前模型能力，不能自动丢弃素材')
    if audio and not cap.get('audio_reference'): raise ValueError('当前官方视频模型不支持声音参考，请调整素材或选择支持的服务')
    if len(audio) > cap.get('max_audio', 3): raise ValueError('音频参考数量超出当前模型能力')
    protocol = provider['protocol']
    if protocol == 'ark':
        content = [{'type': 'text', 'text': bundle['prompt']}]
        for r in images:
            content.append({'type': 'image_url', 'image_url': {'url': data_url(r['file'])}, 'role': 'reference_image'})
        for r in audio:
            content.append({'type': 'audio_url', 'audio_url': {'url': data_url(r['file'])}, 'role': 'reference_audio'})
        return {'model': provider['model'], 'content': content, 'duration': int(duration), 'ratio': bundle['ratio'], 'seed': bundle['seed']}
    if protocol == 'dashscope':
        if duration not in (5,10,15): raise ValueError('当前万相 2.6 视频适配支持 5、10、15 秒')
        if audio: raise ValueError('当前万相预设不接受角色声音参考，请选择 Seedance 或调整声音素材')
        is_i2v = '-i2v' in provider['model']
        if is_i2v and len(images) != 1: raise ValueError('万相首帧生视频需要且只能传入一张图片')
        if not is_i2v and images: raise ValueError('万相文生视频不接受参考图，请选择首帧生视频或多图参考模型')
        inputs = {'prompt': bundle['prompt']}
        if is_i2v: inputs['img_url'] = data_url(images[0]['file'])
        sizes = {'16:9': '1280*720', '9:16': '720*1280', '1:1': '960*960'}
        if bundle['ratio'] not in sizes: raise ValueError('当前万相预设支持比例 16:9、9:16、1:1')
        params = {'duration': int(duration), 'seed': bundle['seed']}
        params.update({'resolution': '720P'} if is_i2v else {'size': sizes[bundle['ratio']]})
        return {'model': provider['model'], 'input': inputs, 'parameters': params}
    if protocol == 'jimeng':
        if duration not in (5,10): raise ValueError('即梦视频 3.0 1080P 支持 5 或 10 秒')
        if provider['model'] != 'jimeng_t2v_v30_1080p': raise ValueError('当前即梦视频适配支持 jimeng_t2v_v30_1080p；其他版本请使用对应专用通道')
        if images or audio: raise ValueError('此即梦文生视频通道不接受参考素材，请选择 Seedance 多图通道')
        return {'req_key': provider['model'], 'prompt': bundle['prompt'], 'seed': bundle['seed'], 'frames': int(duration) * 24 + 1, 'aspect_ratio': bundle['ratio']}
    raise ValueError('未知官方视频协议')


async def video_submit(provider, bundle):
    payload = video_payload(provider, bundle)
    if provider['protocol'] == 'jimeng':
        result = await cv_request(provider, 'CVSync2AsyncSubmitTask', payload); remote = result.get('task_id')
    elif provider['protocol'] == 'ark':
        result = await request(provider, '/contents/generations/tasks', payload); remote = result.get('id')
    else:
        path = '/services/aigc/' + ('image2video' if '-i2v' in provider['model'] else 'video-generation') + '/video-synthesis'
        result = await request(provider, path, payload, {'X-DashScope-Async': 'enable'}); remote = result.get('output', {}).get('task_id')
    if not remote: raise ValueError('提交响应缺少任务 ID，请核查官方记录后再重试，避免重复费用')
    return str(remote), payload


async def video_poll(provider, remote, target):
    protocol = provider['protocol']
    if protocol == 'jimeng':
        result = await cv_request(provider, 'CVSync2AsyncGetResult', {'req_key': provider['model'], 'task_id': remote})
        state = result.get('status'); url = result.get('video_url'); success = state == 'done'
        failure = state in ('not_found', 'expired', 'failed')
    elif protocol == 'ark':
        result = await request(provider, '/contents/generations/tasks/' + quote(remote, safe=''))
        state = result.get('status'); url = result.get('content', {}).get('video_url'); success = state == 'succeeded'
        failure = state in ('failed', 'cancelled', 'expired')
    else:
        result = (await request(provider, '/tasks/' + quote(remote, safe=''))).get('output', {})
        state = result.get('task_status'); url = result.get('video_url'); success = state == 'SUCCEEDED'
        failure = state in ('FAILED', 'CANCELED', 'UNKNOWN')
    if failure: raise ValueError('官方视频任务失败或已过期，请在服务控制台核查')
    if not success: return None
    if not isinstance(url, str) or not url: raise ValueError('官方视频任务完成但未返回视频地址')
    return await p.download(url, target)


def image_payload(provider, prompt, reference):
    model = provider['model']; size = provider.get('size') or '1024x1024'
    if provider['protocol'] == 'ark':
        payload = {'model': model, 'prompt': prompt, 'size': size, 'response_format': 'url', 'stream': False}
        if reference: payload['image'] = data_url(reference)
        return payload
    if provider['protocol'] == 'dashscope':
        content = ([{'image': data_url(reference)}] if reference else []) + [{'text': prompt}]
        return {'model': model, 'input': {'messages': [{'role': 'user', 'content': content}]}, 'parameters': {'size': size.replace('x', '*'), 'n': 1}}
    if model != 't2i_v40_jimeng': raise ValueError('当前即梦图片适配支持官方 SP 通道 t2i_v40_jimeng')
    if reference: raise ValueError('即梦此通道要求公网参考图链接；本地参考图编辑或白模转换请选择千问或 Seedream')
    try: width, height = map(int, size.replace('*', 'x').split('x'))
    except ValueError: raise ValueError('即梦图片尺寸需为 宽x高，例如 2048x2048')
    payload = {'req_key': model, 'prompt': prompt, 'width': width, 'height': height, 'force_single': True}
    return payload


async def image_generate(provider, prompt, target, reference=None):
    payload = image_payload(provider, prompt, reference)
    if provider['protocol'] == 'jimeng':
        result = await cv_request(provider, 'CVSync2AsyncSubmitTask', payload)
        remote = result.get('task_id')
        if not remote: raise ValueError('即梦图片提交未返回任务 ID，请在控制台核查')
        for _ in range(200):
            result = await cv_request(provider, 'CVSync2AsyncGetResult', {'req_key': provider['model'], 'task_id': remote, 'req_json': json.dumps({'return_url': True})})
            if result.get('status') in ('failed', 'not_found', 'expired'): raise ValueError('即梦图片任务失败或过期')
            if result.get('status') == 'done': break
            await asyncio.sleep(3)
        else: raise ValueError('即梦图片查询超时，请在控制台查看任务 ' + str(remote))
        urls = result.get('image_urls', []); binary = result.get('binary_data_base64', [])
        item = {'url': urls[0]} if urls else {'b64_json': binary[0]} if binary else {}
    elif provider['protocol'] == 'dashscope':
        result = await request(provider, '/services/aigc/multimodal-generation/generation', payload)
        items = p.dotted(result, 'output.choices.0.message.content', [])
        item = next(({'url': i['image']} for i in items if i.get('image')), {})
    else:
        result = await request(provider, '/images/generations', payload); item = p.dotted(result, 'data.0', {})
    if item.get('b64_json'): target.write_bytes(base64.b64decode(item['b64_json']))
    elif item.get('url'): await p.download(item['url'], target)
    else: raise ValueError('官方图片接口未返回图片')
    from PIL import Image
    with Image.open(target) as image: image.verify()
    return target.name


async def check(provider):
    # These services have no free universal /models probe. Never submit a paid generation for a test button.
    p.validate_url(provider['base_url'])
    if not provider.get('model'): raise ValueError('请填写模型 ID')
    if provider['protocol'] == 'jimeng': signed_headers(provider, 'Action=CVSync2AsyncGetResult&Version=2022-08-31', b'{}')
    elif not provider.get('secret'): raise ValueError('请先保存 API Key')
    return {'ok': True, 'scope': 'configuration', 'models': [], 'message': '配置检查通过；尚未验证官方权限与生成结果，实际生成需提交任务'}
