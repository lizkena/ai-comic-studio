"""Official endpoints, checked 2026-10-03. Presets contain no credentials/prices."""
import copy

PROTOCOLS = {
    'text': {'openai': 'OpenAI 兼容文本 API'},
    'image': {'openai': 'OpenAI 图片 API', 'ark': '火山方舟 Seedream', 'dashscope': '百炼 Qwen-Image', 'jimeng': '即梦官方 AK / SK'},
    'video': {'ark': '火山方舟 Seedance', 'dashscope': '百炼万相异步 API', 'jimeng': '即梦官方 AK / SK', 'comfy': 'ComfyUI 工作流', 'json-video': '自定义异步 JSON'},
}

for _kind in PROTOCOLS:
    PROTOCOLS[_kind]['lingquan'] = '灵泉 AI（自动匹配模型协议）'

def preset(ident, name, kind, protocol, base, models, docs, note, **defaults):
    return {'id': ident, 'name': name, 'kind': kind, 'models': models, 'docs_url': docs, 'note': note,
            'defaults': {'name': name, 'kind': kind, 'protocol': protocol, 'base_url': base,
                         'model': models[0] if models else '', 'currency': 'CNY', 'unit_price': None, **defaults}}

ARK = 'https://ark.cn-beijing.volces.com/api/v3'
DASH = 'https://dashscope.aliyuncs.com/api/v1'
CV = 'https://visual.volcengineapi.com'
PRESETS = [
    preset('qwen-text', '千问 · 阿里云百炼', 'text', 'openai', 'https://dashscope.aliyuncs.com/compatible-mode/v1',
           ['qwen-plus', 'qwen-max', 'qwen-turbo'], 'https://help.aliyun.com/zh/model-studio/model-calling-in-sub-workspace',
           '默认北京地域；密钥需与地域一致，也可修改为业务空间专属地址。', json_mode=True, text_options={'enable_thinking': False}),
    preset('mimo-text', '小米 · MiMo', 'text', 'openai', 'https://api.xiaomimimo.com/v1',
           ['mimo-v2.6-pro', 'mimo-v2.6-flash'], 'https://mimo.mi.com/docs/zh-CN/api/chat/openai-api',
           '使用小米开放平台 API Key。多模态理解模型归入文本服务。', auth_header='api-key', token_field='max_completion_tokens', temperature=1.0, text_options={'thinking': {'type': 'disabled'}}),
    preset('deepseek-text', 'DeepSeek · 官方', 'text', 'openai', 'https://api.deepseek.com',
           ['deepseek-flash', 'deepseek-v4-pro'], 'https://api-docs.deepseek.com/quick_start/pricing/',
           '使用 DeepSeek 开放平台密钥，支持自行填写账户可用的模型 ID。', json_mode=True, text_options={'thinking': {'type': 'disabled'}}),
    preset('ark-text', '火山引擎 · 豆包', 'text', 'openai', ARK,
           ['doubao-seed-2-1-pro-260628', 'doubao-seed-2-0-lite-260428'], 'https://docs.volcengine.com/docs/ark/chat-api?lang=zh',
           '使用方舟 API Key；模型服务需开通，也可填写 ep- 开头的接入点 ID。', text_options={'thinking': {'type': 'disabled'}}),
    preset('glm-text', '智谱 · GLM', 'text', 'openai', 'https://open.bigmodel.cn/api/paas/v4',
           ['glm-5.3', 'glm-4.7', 'glm-4.7-flash'], 'https://docs.bigmodel.cn/api-reference/模型-api/对话补全',
           '使用智谱开放平台 API Key，模型以控制台已开通列表为准。', text_options={'thinking': {'type': 'disabled'}}),
    preset('kimi-text', '月之暗面 · Kimi', 'text', 'openai', 'https://api.moonshot.cn/v1',
           ['kimi-k3', 'kimi-k2.6'], 'https://platform.kimi.com/docs/get-api-key',
           '使用 Kimi 开放平台 API Key；国际账户请修改为对应地域地址。默认保留思考模式。', temperature=1.0, max_tokens=16000),
    preset('minimax-text', 'MiniMax · 官方', 'text', 'openai', 'https://api.minimax.cn/v1',
           ['MiniMax-M3', 'MiniMax-M3.1-Flash-Preview', 'MiniMax-M2.7'], 'https://platform.minimax.cn/docs/api-reference/text-openai-api',
           '国内按量付费 API 地址；思考内容单独返回，预留较大输出上限。', temperature=1.0, token_field='max_completion_tokens', max_tokens=16000, text_options={'reasoning_split': True}),
    preset('qwen-image', '千问 · Qwen-Image', 'image', 'dashscope', DASH,
           ['qwen-image-2.0-pro', 'qwen-image-2.0'], 'https://help.aliyun.com/zh/model-studio/qwen-image-api',
           '支持文生图和参考图编辑，可用于白模转换。默认北京地域。', size='1024*1024'),
    preset('ark-image', '火山引擎 · Seedream', 'image', 'ark', ARK,
           ['doubao-seedream-5-0-lite-260128', 'doubao-seedream-4-5-251128'], 'https://docs.volcengine.com/docs/ark/seedream-4-0-5-0?lang=zh',
           '使用方舟 API Key，支持文生图和参考图编辑。', size='2048x2048'),
    preset('jimeng-image', '即梦 · 图片 4.0', 'image', 'jimeng', CV,
           ['t2i_v40_jimeng'], 'https://www.volcengine.com/docs/85621/1863351',
           '官方 SP 通道，使用 AK / SK，需开通对应服务。本版支持文生图；本地参考图编辑 / 白模请选择千问或 Seedream。', size='2048x2048', supports_edit=False),
    preset('ark-video', '火山引擎 · Seedance', 'video', 'ark', ARK,
           ['doubao-seedance-2-0-260128'], 'https://docs.volcengine.com/docs/ark/create-video-generation-task-api?lang=zh',
           '使用方舟 API Key，支持多张图片和音频参考；可填写已开通的模型 / ep- 接入点。',
           capabilities={'min_duration': 4, 'max_duration': 15, 'audio_reference': True, 'max_images': 9, 'max_audio': 3}),
    preset('wan-video', '通义万相 · 文生视频', 'video', 'dashscope', DASH,
           ['wan2.6-t2v'], 'https://help.aliyun.com/en/model-studio/legacy-wan-text-to-video-api-reference',
           '纯文生视频，不接收角色 / 尾帧参考图。时长支持 5、10、15 秒。',
           capabilities={'min_duration': 5, 'max_duration': 15, 'durations': [5,10,15], 'max_images': 0, 'audio_reference': False}),
    preset('wan-i2v', '通义万相 · 首帧生视频', 'video', 'dashscope', DASH,
           ['wan2.6-i2v', 'wan2.6-i2v-flash'], 'https://help.aliyun.com/en/model-studio/legacy-image-to-video-api-reference/',
           '仅接收一张首帧图；多张资产参考请先合成首帧或选择 Seedance。',
           capabilities={'min_duration': 5, 'max_duration': 15, 'durations': [5,10,15], 'max_images': 1, 'audio_reference': False}),
    preset('jimeng-video', '即梦 · 视频 3.0 1080P', 'video', 'jimeng', CV,
           ['jimeng_t2v_v30_1080p'], 'https://docs.volcengine.com/docs/JimengAI/JimengAI-VideoGeneration301080P-Text-to-Video-InterfaceDocumentation?lang=zh',
           '官方 AK / SK 通道，纯文生视频，时长支持 5 或 10 秒。多图参考请使用方舟 Seedance。',
           capabilities={'min_duration': 5, 'max_duration': 10, 'durations': [5,10], 'max_images': 0, 'audio_reference': False}),
    preset('comfy-video', '本地 · ComfyUI / H3', 'video', 'comfy', 'http://127.0.0.1:8190', [],
           'https://docs.comfy.org/interface/features/developer-mode', '导入 API 格式工作流并确认字段映射后使用，无需官方 API Key。'),
]

for _kind, _models in [('text', ['tt-5.6-sol', 'sn-5-5']), ('image', ['tt-image-2', 'banana-2', 'qwen-image']), ('video', ['minimax-h3'])]:
    _item = preset('lingquan-' + _kind, '灵泉 AI', _kind, 'lingquan', 'https://api.lk888.ai', _models,
                   'https://may.lk888.ai/apidoc', '第三方聚合渠道；同一渠道支持多个文本、图片和视频模型。请拉取模型，按密钥权限选择；图片与视频异步生成。',
                   size='auto', resolution='768P', lingquan_params={},
                   capabilities={'min_duration':4, 'max_duration':15, 'max_images':9, 'audio_reference':True, 'max_audio':3})
    _item['category'] = 'third_party'
    PRESETS.append(_item)

def catalog():
    return {'checked_at': '2026-10-03', 'protocols': copy.deepcopy(PROTOCOLS), 'items': copy.deepcopy(PRESETS)}
