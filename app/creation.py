"""Creative presets and source-specific instructions, shared by every generation path."""
import math
import json

GENRES = [
    ('suspense', '悬疑', '围绕线索、人物动机和因果反转组织剧情；悬念逐步揭示，避免无依据反转。'),
    ('fantasy', '奇幻', '建立明确的幻想规则、能力代价与世界边界，保持事件因果和规则一致。'),
    ('xianxia', '玄幻修仙', '明确修行体系、境界限制、门派关系与人物成长，避免能力无代价升级。'),
    ('urban', '都市生活', '以现实生活和职业关系组织冲突，人物行为符合生活经验。'),
    ('romance', '情感爱情', '重视关系变化、情感动机和细节表达，避免人物为误会而失去合理判断。'),
    ('ancient', '古风历史', '保持时代氛围、称谓、服饰与社会关系一致；不把虚构故事宣称为史实。'),
    ('scifi', '科幻', '明确科技设定及其限制，以可理解的规则推动冲突，保持技术与世界观一致。'),
    ('apocalypse', '末世冒险', '围绕生存资源、环境威胁和团队选择展开，保持风险与行动代价。'),
    ('campus', '青春校园', '以成长、友谊和校园生活为中心，保持年龄、语言与行为一致。'),
    ('time_travel', '穿越重生', '明确时间变化、记忆优势及其边界，保持原时间线与新事件的因果关系。'),
]
STYLES = [
    ('cinematic_guofeng', '电影感国风动漫', '国风动漫人物与环境，电影式构图、分层光影和克制配色；镜头之间保持人物造型一致。'),
    ('anime_2d', '日系二维动画', '清晰二维线稿、赛璐璐色块与动画背景，保持线条与角色比例一致，避免写实皮肤或三维质感。'),
    ('guoman_3d', '三维国漫', '三维动画角色与环境，统一材质、体积光与空间透视，保持模型外观和服装一致。'),
    ('realistic', '写实电影', '真实人物比例、自然材质与摄影式光影，统一色彩和镜头语言，避免卡通或插画质感。'),
    ('watercolor', '水彩绘本', '柔和水彩笔触、纸张纹理与简洁构图，色彩和角色线条保持统一。'),
    ('ink', '东方水墨', '水墨晕染、留白与层次构图，保持人物辨识度、空间关系和墨色风格一致。'),
    ('cyberpunk', '赛博朋克动画', '科幻城市、霓虹与冷暖对比，统一动画角色设计和科技材质，避免每镜重新设计人物。'),
    ('comic', '漫画厚涂', '漫画造型、厚涂色彩与明确明暗关系，保持画风、角色轮廓和服装细节一致。'),
]


def catalog():
    return {'genres': [{'id': i, 'name': n, 'guidance': g} for i, n, g in GENRES],
            'styles': [{'id': i, 'name': n, 'guidance': g} for i, n, g in STYLES]}


def normalize_settings(settings):
    settings = dict(settings or {})
    for key, rows in [('genre', GENRES), ('style', STYLES)]:
        ident = settings.get(key + '_preset')
        if ident and ident != 'custom':
            selected = next((r for r in rows if r[0] == ident), None)
            if not selected: raise ValueError('未知的' + ('故事类型' if key == 'genre' else '视觉风格') + '预设')
            settings[key] = selected[1]
        if ident == 'custom' and not str(settings.get(key, '')).strip(): raise ValueError('请填写自定义' + ('故事类型' if key == 'genre' else '视觉风格'))
    if settings.get('ratio', '16:9') not in ('16:9', '9:16', '1:1'): raise ValueError('画面比例不支持')
    try: duration = float(settings.get('episode_duration', 40))
    except (TypeError, ValueError): raise ValueError('单集时长必须为正数')
    if not math.isfinite(duration) or duration <= 0: raise ValueError('单集时长必须为正数')
    settings['episode_duration'] = duration
    if settings.get('adaptation_mode', 'faithful') not in ('faithful', 'moderate'): raise ValueError('小说改编方式不支持')
    return settings


def start_stage(p):
    return {'idea': 'direction', 'novel': 'novel', 'script': 'script'}.get(p.get('entry'), 'direction')


def guidance(p, stage=None, visual_only=False):
    from . import agent_memory
    settings = p.get('settings', {})
    lines = []
    memory = agent_memory.guidance(p)
    if memory: lines.append(memory)
    setup = p.get('outputs', {}).get('production_setup')
    if setup:
        selected = {k: setup.get(k) for k in ('era', 'region', 'visual_style', 'cinematography')}
        if not visual_only: selected.update(genre=setup.get('genre'), synopsis=setup.get('synopsis'), characters=setup.get('characters'))
        lines.append('当前作品的统一剧本设定（手动修改优先）：'+json.dumps(selected, ensure_ascii=False))
    for key, rows, label in [('genre', GENRES, '故事类型'), ('style', STYLES, '视觉风格')]:
        name = settings.get(key, '')
        # A manually edited label takes precedence over a previously selected preset.
        chosen = None if settings.get(key + '_preset') == 'custom' else next((r for r in rows if r[1] == name), None)
        lines.append(label + '：' + name + ('。' + chosen[2] if chosen else '。遵循用户的自定义描述。'))
    if not visual_only:
        lines.append('时长规则：单集总时长由 AI 根据剧情和对白自行判断，不受旧 episode_duration 或固定总时长要求限制；保留用户明确的单镜头时长限制，不为凑总时长拉长动作或删减剧情。')
        entry = p.get('entry', 'idea')
        if entry == 'novel':
            lines.append('来源为导入小说。以已有章节为改编依据，保留原人物、事件因果和原文来源；不要把原文当成一句灵感另写无关故事。')
            lines.append('忠于原著：仅做影视化压缩和场景整理，保留主要情节与人物动机。' if settings.get('adaptation_mode', 'faithful') == 'faithful' else '适度改编：可调整叙事节奏和场次表达，保留主线、人物身份和关键事件，说明改编之处。')
        elif entry == 'script':
            lines.append('来源为作者已有剧本。整理场次、角色、动作和时长，保留原剧情与原对白；不回退到小说创作，不擅自改写作者内容。')
        else: lines.append('来源为用户灵感。先明确故事方向，再根据用户选择展开人物、世界与剧本。')
        lines.append('类型与画风只指导创作表达，不覆盖用户明确要求保留的事实、剧情或对白。')
    return '\n'.join(lines)


def genre_instruction(genre_id):
    """返回指定题材的创作指引，找不到返回空字符串。"""
    for gid, _name, instruction in GENRES:
        if gid == genre_id:
            return instruction
    return ''


def genre_label(genre_id):
    """返回指定题材的中文名，找不到返回 genre_id 本身。"""
    for gid, name, _instruction in GENRES:
        if gid == genre_id:
            return name
    return genre_id


GENRE_IDS = [gid for gid, _, _ in GENRES]
GENRE_OPTIONS = [{'id': gid, 'label': name} for gid, name, _ in GENRES]


# 电影感核心约束（压缩版，8 条核心规则）
CINEMATIC_CORE_RULES = """
【电影感镜头核心约束】

1. 光源动机：画面每处亮度必须有明确来源（窗户/灯具/霓虹/火光/屏幕），写明光的方向与衰减。禁止"侧光""环境光"这种无源描述。室内说明光从哪个具体位置来，室外明确太阳/月光/街灯方向。

2. 机位配比：侧45度是对话与叙事的默认机位（占30-40%），比正面立体、比侧面保留交流感。常规镜头（平视+正面/过肩+平稳运镜）压缩至≤30%，作为呼吸基准。大仰角、大俯角各≤3次/集，只给权力碾压、命运顶点或绝望孤独时刻。

3. 景别与情绪：情绪越强景别越紧（愤怒/惊讶推到近景特写），动作越大景别越松（追逐/打斗用中景全景）。但重锤情绪（生死/离别/真相/崩溃）反着用更有力——悲伤爆发反而拉远让人物在环境中渺小，震撼瞬间反而固定大特写让观众无处可逃。

4. 运镜跟随情绪：平静用极缓慢推镜或横移（让画面保持流动），紧张上升用手持微晃，冲突升级用手持晃动，情绪爆发顶点（≥8分）用手持剧烈晃动（地平线失稳、焦点呼吸）。固定镜头≤10%，只给重锤凝固瞬间或段落句号。运镜速度=情绪强度。

5. 画面持续变化：含台词镜头必须二选一——(1)说话时一直有具体动作（走位/手势/递物/整理物件/转身），动作推进叙事或情绪，不允许无意义小动作填时长；(2)静止后立即切镜（换角度/换景别/切反应/切空镜）。静止说话不超约3秒（一句完整对话）。禁止站桩说话。

6. 镜头经济性：一个镜头同时推进多层（剧情+人物+情绪+空间），至少承载两层信息。删除与上一镜信息重复的镜头。能删则删、能并则并。每个镜头必须给观众"新信息"——给不出新信息就是废镜。

7. 场景空间约束：室内普通层高（≤3m）禁止鸟瞰、大远景、远景。依场景物理空间选择景别和运镜——过肩需要机位退1.5-2米，拉镜需要背后有空间，侧面机位需要人物侧向不贴墙，环绕需要主体周围360度可放机位。室内大俯角必须找到真实高点（楼梯口/二层回廊/高柜顶），无高点则降级为30-45度俯拍。

8. 表演外化：情绪靠小动作（指节发白/拇指摩挲/拳头紧握/反复开关打火机）和微表情（瞳孔收缩/嘴角极轻微抽动/喉结滚动/呼吸变浅/睫毛颤动）外化。克制原则——藏七分露三分。禁止表情包式表演（五官扭曲/龇牙咧嘴/涕泪横流/捶胸顿足）。愤怒可以是压低的声音+攥紧的拳头，悲伤可以是红了眼眶却别过脸，惊讶可以是短暂停顿+呼吸乱半拍。

以上约束内部遵守，输出仍为平台要求的 JSON 结构（segments/shots/prompt/duration/资产ID引用）。光源动机、机位角度、运镜方式、表演细节写入 prompt 和 shots 的 action 字段。
"""
