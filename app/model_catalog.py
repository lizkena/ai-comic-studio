"""Channel model registry; legacy single-model settings remain readable."""
import copy
from . import seedance
from urllib.parse import urlparse
from .presets import PROTOCOLS

KINDS = ('image', 'text', 'video')


def classify(item):
    declared = str(item.get('type') or item.get('kind') or '').lower()
    aliases = {'chat':'text','chat/completions':'text','llm':'text','image':'image','text':'text','video':'video'}
    if declared in aliases: return aliases[declared]
    ident = item['id'].lower()
    if any(x in ident for x in ('video','seedance','sora','veo','kling','wan2','wan-','hailuo')): return 'video'
    if any(x in ident for x in ('image','flux','stable-diffusion','seedream','dall-e','midjourney','nano-banana')): return 'image'
    if any(x in ident for x in ('gpt','claude','gemini','deepseek','qwen','mimo','glm','kimi','minimax','llama','chat')): return 'text'
    return 'unclassified'


def normalize(channel):
    result = copy.deepcopy(channel)
    kind = result.get('kind', 'text')
    entries = result.get('models')
    if entries is None:
        entries = [{'id':result['model'], 'kind':kind, 'protocol':result.get('protocol')} ] if result.get('model') else []
    if not isinstance(entries, list): raise ValueError('渠道模型必须为列表')
    unique = {}
    for entry in entries:
        if not isinstance(entry, dict): raise ValueError('渠道模型格式无效')
        ident = str(entry.get('id', '')).strip()
        model_kind = entry.get('kind')
        if not ident or model_kind not in KINDS: raise ValueError('请填写模型 ID 并选择聊天、生图或视频类型')
        protocol = entry.get('protocol') or (result.get('protocol') if result.get('protocol') in PROTOCOLS[model_kind] else 'json-video' if model_kind == 'video' else 'openai')
        if protocol not in PROTOCOLS[model_kind]: raise ValueError('模型类型与调用协议不匹配')
        params = entry.get('lingquan_params', {})
        if not isinstance(params, dict): raise ValueError('灵泉模型参数应为 JSON 对象')
        unique[(model_kind, ident)] = {'id':ident,'kind':model_kind,'protocol':protocol, **({'lingquan_params':copy.deepcopy(params)} if protocol == 'lingquan' else {})}
        for key in seedance.MODEL_KEYS:
            if key in entry: unique[(model_kind, ident)][key] = copy.deepcopy(entry[key])
    result['models'] = list(unique.values())
    # Primary model is retained only as a compatibility default, never as a limit.
    primary = [m for m in result['models'] if m['kind'] == kind]
    if primary and result.get('model') not in [m['id'] for m in primary]: result['model'] = primary[0]['id']
    return result


def resolve(channel, kind, model=None):
    result = normalize(channel)
    candidates = [m for m in result['models'] if m['kind'] == kind]
    if not candidates:
        if kind == 'video' and result.get('protocol') == 'comfy': return result
        raise ValueError('该渠道尚未配置当前用途的模型')
    if model:
        chosen = next((m for m in candidates if m['id'] == model), None)
        if not chosen: raise ValueError('所选模型已移除或类型不匹配，请重新选择')
    else: chosen = next((m for m in candidates if m['id'] == result.get('model')), candidates[0])
    result.update(kind=kind, model=chosen['id'], protocol=chosen['protocol'])
    for key in seedance.MODEL_KEYS:
        if key in chosen: result[key] = copy.deepcopy(chosen[key])
    # Channel-specific announcement, 2026-10-14. Do not infer capabilities for
    # similarly named models on other gateways or local Comfy deployments.
    if (kind == 'video' and chosen['id'] == 'minimax-h3' and chosen['protocol'] == 'json-video'
            and urlparse(result.get('base_url', '')).hostname == 'api.ai-tudou.net'):
        result['capabilities'] = {**result.get('capabilities', {}),
                                  'advertised_audio_reference': True,
                                  'audio_reference': bool(result.get('contract', {}).get('fields', {}).get('audio_references')),
                                  'video_reference': True,
                                  'max_images': 9, 'max_audio': 3, 'max_video': 3,
                                  'min_duration': 3, 'max_duration': 15}
    if chosen['protocol'] == 'lingquan': result['lingquan_params'] = copy.deepcopy(chosen.get('lingquan_params', {}))
    return seedance.profile(result) if kind == 'video' else result
