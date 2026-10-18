"""Draft connection checks never persist settings or submit generation jobs."""
import copy
import httpx
from . import providers, presets, model_catalog


def prepare(payload):
    p = copy.deepcopy(payload)
    if p.get('protocol') not in presets.PROTOCOLS.get(p.get('kind'), {}):
        raise ValueError('服务用途与调用渠道不匹配')
    base = providers.validate_url(p.get('base_url', ''))
    stored = next((x for x in providers.settings()['providers'] if x['id'] == p.get('id')), {})
    same = base == stored.get('base_url', '').rstrip('/') and p.get('protocol') == stored.get('protocol') and (p.get('auth_header') or 'bearer') == (stored.get('auth_header') or 'bearer')
    # Ignore encrypted fields sent by clients. Never forward a saved credential to a changed address.
    for incoming, encrypted, clear in [('api_key','secret','clear_key'), ('access_key','ak_secret','clear_access_keys'), ('secret_key','sk_secret','clear_access_keys')]:
        value = p.pop(incoming, '') or ''
        p[encrypted] = providers.protect(value.strip()) if value.strip() else stored.get(encrypted, '') if same else ''
        if p.get(clear): p[encrypted] = ''
    return p


def suggestions(p, message):
    item = next((x for x in presets.PRESETS if x['id'] == p.get('preset_id') and x['kind'] == p.get('kind')), None)
    return {'ok':False, 'source':'preset', 'models':item['models'] if item else [], 'message':message + '；可选择预设建议或手动填写模型 ID'}


async def models(p):
    if p['protocol'] == 'lingquan':
        from .lingquan import models as discover
        return await discover(p)
    if p['protocol'] != 'openai':
        return suggestions(p, '该渠道未提供通用模型列表接口')
    if not p.get('secret'): raise ValueError('请填写 API Key；修改渠道地址后需重新填写密钥')
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(providers.endpoint(p, '/models'), headers=providers.headers(p))
    if r.status_code in (404,405,501): return suggestions(p, '当前渠道不支持模型拉取')
    providers.require_ok(r)
    try: data = r.json()
    except ValueError: raise ValueError('模型接口返回了非 JSON 内容，请检查基础地址是否需要追加 /v1')
    if not isinstance(data, dict) or not isinstance(data.get('data'), list): raise ValueError('模型列表返回格式无效')
    found = sorted({x['id'] for x in data['data'] if isinstance(x,dict) and isinstance(x.get('id'),str) and x['id']})
    if not found: return {'ok':True,'source':'remote','models':[],'message':'渠道连接成功，但返回的模型列表为空'}
    details = []
    for ident in found:
        item = next(x for x in data['data'] if isinstance(x,dict) and x.get('id') == ident)
        details.append({'id':ident, 'kind':model_catalog.classify(item)})
    return {'ok':True,'source':'remote','models':found,'model_details':details,'message':f'已从渠道拉取 {len(found)} 个模型；请选择并确认模型类型'}


async def probe(p):
    if p['protocol'] == 'comfy': return await providers.comfy_check(p)
    if p['protocol'] in ('ark','dashscope','jimeng'):
        from .official import check
        return await check(p)
    if p['protocol'] in ('openai', 'lingquan'):
        result = await models(p)
        if result['source'] != 'remote':
            return {**result,'scope':'unsupported','message':'该渠道不支持通用连接检测，密钥和模型权限尚未验证'}
        return {**result,'scope':'connection','message':'连接测试通过；生成能力需实际任务验证'}
    path = p.get('contract', {}).get('health_path')
    if not path: return {'ok':False,'scope':'unsupported','message':'请在自定义渠道的高级映射中填写 health_path，以便测试连接'}
    if not path.startswith('/') or path.startswith('//'): raise ValueError('health_path 应为站内接口路径')
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(providers.endpoint(p,path),headers=providers.headers(p))
    providers.require_ok(r)
    return {'ok':True,'scope':'connection','message':'连接测试通过；生成能力需实际任务验证'}
