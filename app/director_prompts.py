"""Model-neutral directing guidance added to existing prompt-writing actions.

Original platform implementation informed by Seedance-Director-4.0's separation
of directing, reference responsibilities and compilation. No external skill
runtime, persona, stage ordering or Seedance-specific limits are imported.
"""
import copy
import json
import re

VERSION = 'director-compiler-v1.1'

VIDEO_RULES = '''视频提示词导演编译补充：
先在内部核对镜头事实，再输出可执行的完整提示词；不要输出分析过程或额外流程指令。
用户剧情、原对白、指定动作、时长、画幅、角色身份与项目风格是基准，不改写对白，不新增人物、道具、事件，不改变镜头顺序。不为凑格式增加内容。
参考职责：人物或身份图只约束身份与当前造型，不继承定妆站姿和展示背景；场景图约束空间地标、材质与光线，不锁死摄影构图；道具图约束外形与本镜持握状态；镜头图约束构图，只有标记 first_frame 才能称为首帧。音频仅在已有样本时注明音色或声音职责；视频参考明确其动作、机位或连续性用途，不混作人物身份图。
按输入引用清单逐字使用 token，名称、类别与 token 一一对应；不能把某个编号绑定到另一物件。只写已提供的素材，不编造参考图或已观看的内容。
镜头调度：用景别、机位侧、画框方位和已有地标交代关系；身体朝向与视线分别说明，动作对象必须清楚。人物围绕剧情中的对象行动，只有用户要求对镜头讲话时才使用采访站位。已有站位或运镜不得擅自替换。
时间组织：从起始姿态，经动作触发、过程及必要反应，到结束姿态；简单动作保持简洁，复杂动作说明接触、重心与受力结果。一镜以一种主要运镜服务叙事，不堆叠无目的运镜。使用输入时长，分段时从0连续覆盖到总时长，动作与台词留有自然反应时间。
摄影质感：遵循项目统一风格，明确有效的光源方向、光色、材质差异与景深。不靠“电影级、8K、杰作”替代具体拍法。写实项目中的人物、环境与生物采用一致的摄影光线、尺度、接触阴影及皮肤/布料/骨甲材质，避免游戏展示和塑料质感。
结束与衔接：用“结束状态：”明确位置、身体朝向和视线、哪只手持物、动作余势与情绪方向；原文未定的具体细节不编造。仅在输入提供前镜状态时继承；计划状态不是实际成品状态，没有实际尾帧不能声称已验证衔接。不得把“同上一镜”当作完整描述。
按内容需要组织为画面基准、参考职责、动作与摄影、声音、结束与衔接；不强制固定段数。不输出“导演意图”、内部评价或编译分析，意图落实到实际拍法。优先消除矛盾、重复和过载，再补缺失信息。输出长度随镜头复杂度决定。'''

IMAGE_RULES = '''静态提示词导演补充：保留已有资产类型、视图布局与关联，不改为另一类卡片。
继承项目统一视觉风格与光色逻辑。角色描述身份和当前造型，场景描述几何地标、纵深与材质，道具描述外形、尺度与状态，镜头图描述这一瞬间的构图、人物朝向与视线。静态图不塞整段动作过程或对白。
写实项目用具体摄影光线、真实尺度、材质表面差异与接触阴影描述，包括非人类生物；不以“电影感”代替可见事实。不新增剧情事实，不改变用户指定的姿势、站位或资产布局。'''


def enhancement(stage, options=None):
    options = options or {}
    if stage == 'wf_video_prompt' or (stage == 'wf_canvas_text' and options.get('canvas_task') == 'video_prompt'):
        return VIDEO_RULES
    if stage == 'wf_prompts':
        return IMAGE_RULES
    if stage == 'wf_canvas_text' and options.get('canvas_user_request'):
        return ('画布智能体提示词补充：继续遵守原 operations JSON 格式和用户授权范围，不新增制作步骤。'
                '给角色、场景、道具、镜头图卡编写 prompt 时使用以下静态规范。'
                '给视频卡编写 prompt 时区分身体朝向与视线、交代动作起止与运镜，'
                '复用实际卡片名称；写好提示词不等于已经生成媒体。\n' + IMAGE_RULES)
    return ''


def enrich_context(p, stage, ctx, options=None):
    """Provide predecessor facts without fabricating a visual inspection."""
    if stage != 'wf_video_prompt':
        return ctx
    segment = ctx['segment']
    previous = next((s for s in p.get('segments', []) if s['id'] == segment.get('previous_id')), None)
    if previous and segment.get('continuity'):
        selected = next((v for v in previous.get('versions', []) if v['id'] == previous.get('current_version')), {})
        ctx['continuity_source'] = {
            'previous_segment_id': previous['id'],
            'planned_shots': copy.deepcopy(previous.get('shots', [])),
            'planned_prompt': previous.get('prompt', ''),
            'actual_tail_file': selected.get('tail') if selected.get('tail_accepted') else None,
            'visual_inspection_performed': False,
        }
    return ctx


def canvas_references(options):
    if options.get('canvas_task') != 'video_prompt':
        return None
    try:
        value = json.loads(options.get('canvas_message', ''))
    except (ValueError, TypeError):
        raise ValueError('视频整理输入须包含结构化引用清单')
    refs = value.get('references', []) if isinstance(value, dict) else None
    if not isinstance(refs, list) or len(refs) > 40:
        raise ValueError('视频整理引用清单无效')
    if any(not isinstance(r, dict) or not isinstance(r.get('token'), str) or
           not re.fullmatch(r'【[^\n【】]*·R\d+】', r['token']) or
           not isinstance(r.get('name'), str) or
           r.get('category') not in ('character', 'location', 'prop', 'shot', 'audio', 'video') for r in refs):
        raise ValueError('视频整理引用信息无效')
    if len({r['token'] for r in refs}) != len(refs):
        raise ValueError('视频整理引用标记重复')
    return refs


def finalize_canvas(text, options):
    refs = canvas_references(options)
    if refs is None:
        return text
    allowed = {r['token'] for r in refs}
    if any(token not in allowed for token in re.findall(r'【[^\n【】]*·R\d+】', text)):
        raise ValueError('整理结果引用了未连接的素材，请重新整理')
    # Bind names to addresses deterministically; a language model does not own numbering.
    roles = {'character': '人物身份与当前造型', 'location': '场景空间、材质与光线',
             'prop': '道具外形与状态', 'shot': '镜头构图参考',
             'audio': '声音参考', 'video': '动作与摄影参考'}
    lines = [f"{r['token']}：{r['name']}，用于" + ('本镜头首帧' if r.get('role') == 'first_frame' else roles[r['category']]) for r in refs]
    header = '参考素材对应关系（按实际连接）：\n' + '\n'.join(lines) + '\n\n' if lines else ''
    text = text.strip()
    while header and text.startswith(header): text = text[len(header):].strip()
    return header + text
