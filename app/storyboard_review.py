"""分镜专业审查：检查已生成的 JSON 是否符合电影级约束。支持可定制规则。"""
import re
from . import store


def _num(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


# 规则检查函数映射
def check_rule_1(segment, project):
    """规则1: 光源动机检查"""
    issues = []
    suggestions = []
    prompt = segment.get('prompt', '')

    light_sources = re.findall(r'(窗户|窗|灯|霓虹|火|屏幕|太阳|月光|街灯|车灯|烛|蜡烛)', prompt)
    if not light_sources:
        issues.append('未明确光源来源，可能导致无源补光')
        suggestions.append('在 prompt 中指明光从哪里来（如"窗户透入的黄昏逆光""天花板灯具向下打光"）')
    elif len(light_sources) == 1 and '室内' in prompt:
        suggestions.append('室内场景建议说明光的方向与衰减（如"左侧窗户逆光，右侧墙面暗部"）')

    return issues, suggestions


def check_rule_2(segment, project):
    """规则2: 纵深主层机制检查"""
    issues = []
    suggestions = []
    prompt = segment.get('prompt', '')

    # 检查是否滥用雾/模糊
    fog_count = len(re.findall(r'(雾|haze|fog|blur|模糊)', prompt, re.IGNORECASE))
    if fog_count > 2:
        suggestions.append('雾/模糊/blur 使用过多，建议改用光/曝光分离或大气透视制造纵深')

    return issues, suggestions


def check_rule_3(segment, project):
    """规则3: 五层色彩思维检查"""
    issues = []
    suggestions = []
    prompt = segment.get('prompt', '')

    has_palette = bool(re.search(r'(palette|色调|主色调)', prompt, re.IGNORECASE))
    has_saturation = bool(re.search(r'(saturation|饱和度)', prompt, re.IGNORECASE))
    has_film_stock = bool(re.search(r'(film_stock|胶片|Kodak|Fuji)', prompt, re.IGNORECASE))

    if not (has_palette and has_saturation and has_film_stock):
        suggestions.append('建议在 prompt 中添加完整五层色彩方案（palette/saturation/film_stock/grain/halation）')

    return issues, suggestions


def check_rule_4(segment, project):
    """规则4: 景别与情绪匹配检查"""
    issues = []
    suggestions = []
    shots = segment.get('shots', [])

    has_scale = any(re.search(r'(特写|近景|中景|全景|远景|大远景)', s.get('size', '')) for s in shots)
    if not has_scale:
        suggestions.append('建议在 shots 中标注景别（size 字段）')

    return issues, suggestions


def check_rule_5(segment, project):
    """规则5: 焦段约束检查"""
    issues = []
    suggestions = []
    prompt = segment.get('prompt', '')

    has_focal_length = bool(re.search(r'(\d+mm|鱼眼|微距|超广角|广角|标准|中长焦|长焦)', prompt))
    if not has_focal_length:
        suggestions.append('建议在 prompt 中标注焦段（如"85mm""广角24mm"）')

    return issues, suggestions


def check_rule_6(segment, project):
    """规则6: 机位角度约束检查"""
    issues = []
    suggestions = []
    prompt = segment.get('prompt', '')

    has_angle = bool(re.search(r'(侧|正面|过肩|仰|俯|平视|斜|主观|视角|荷兰角)', prompt))
    if not has_angle:
        suggestions.append('建议在 prompt 中明确机位角度（如"侧45度""微仰15度"）')

    return issues, suggestions


def check_rule_7(segment, project):
    """规则7: 运镜方式约束检查"""
    issues = []
    suggestions = []
    shots = segment.get('shots', [])

    if len(shots) == 0:
        issues.append('小节缺少 shots 镜号分解')
        return issues, suggestions

    fixed_count = sum(1 for s in shots if '固定' in s.get('camera', ''))
    if fixed_count / len(shots) > 0.3:
        issues.append(f'固定镜头占比 {fixed_count}/{len(shots)} = {fixed_count/len(shots)*100:.0f}% 超过30%建议上限')
        suggestions.append('将部分固定镜头改为极缓慢推镜或横移，让画面保持流动')

    cameras = [s.get('camera', '').strip() for s in shots]
    if all(not c for c in cameras):
        suggestions.append('建议在 shots 的 camera 字段写明运镜方式（推镜/横移/手持微晃/固定等）')

    return issues, suggestions


def check_rule_8(segment, project):
    """规则8: 景深策略约束检查"""
    issues = []
    suggestions = []
    prompt = segment.get('prompt', '')

    has_depth = bool(re.search(r'(浅景深|深景深|焦点转换|背景虚化)', prompt))
    if not has_depth:
        suggestions.append('建议在 prompt 中明确景深策略（浅景深/深景深/焦点转换）')

    return issues, suggestions


def check_rule_9(segment, project):
    """规则9: 人物群像管理检查"""
    issues = []
    suggestions = []

    character_ids = segment.get('character_ids', [])
    if len(character_ids) >= 3:
        shots = segment.get('shots', [])
        group_shots = sum(1 for s in shots if s.get('size') in ['全景', '中全景', '中景', '远景', '大远景'])
        if group_shots == 0:
            suggestions.append('3人及以上场景建议至少有1个群像镜头（全景/中全景/中景）')

    return issues, suggestions


def check_rule_10(segment, project):
    """规则10: 表演三通道外化检查"""
    issues = []
    suggestions = []
    prompt = segment.get('prompt', '')
    shots = segment.get('shots', [])

    has_emotion_words = re.search(r'(愤怒|悲伤|高兴|惊讶|恐惧|焦虑|紧张|犹豫)', prompt)
    has_action_detail = re.search(r'(指节|拇指|拳头|眼眶|瞳孔|嘴角|喉结|呼吸|睫毛|视线)', prompt)

    if has_emotion_words and not has_action_detail:
        suggestions.append('prompt 中有情绪词但缺少具体表演细节，建议写小动作或微表情（如"指节发白""眼眶泛红""呼吸变浅"）')

    for i, shot in enumerate(shots):
        action = shot.get('action', '')
        if any(emo in action for emo in ['愤怒', '悲伤', '高兴', '惊讶', '恐惧']) and not any(detail in action for detail in ['手', '眼', '呼吸', '视线', '肩', '拳']):
            suggestions.append(f'镜号 {i+1} 的 action 有情绪词但缺少动作外化，建议加小动作（如"攥紧拳头""视线游移"）')

    return issues, suggestions


def check_rule_11(segment, project):
    """规则11: 场景空间类型约束检查"""
    issues = []
    suggestions = []
    prompt = segment.get('prompt', '')

    location_id = segment.get('location_id')
    if location_id:
        asset = next((a for a in project.get('assets', []) if a.get('id') == location_id), None)
        if asset:
            desc = (asset.get('description') or '').lower()
            name = (asset.get('name') or '').lower()
            is_indoor = any(kw in desc or kw in name for kw in ['室内', '房间', '卧室', '客厅', '办公室', '教室', '走廊'])

            if is_indoor:
                if re.search(r'(鸟瞰|上帝视角)', prompt):
                    issues.append('室内场景使用了鸟瞰，普通层高物理不可行')
                    suggestions.append('改用全景 + 低角度仰拍制造空间感，或找到真实高点（楼梯口/二层回廊）')

                shots = segment.get('shots', [])
                if any('大远景' in s.get('size', '') or '远景' in s.get('size', '') for s in shots):
                    issues.append('室内普通层高使用了大远景/远景，景别超出空间物理范围')
                    suggestions.append('改用全景或中全景')

    return issues, suggestions


def check_rule_12(segment, project):
    """规则12: 画面内容约束检查"""
    issues = []
    suggestions = []
    prompt = segment.get('prompt', '')

    vague_positions = re.findall(r'(左边|右边|旁边|附近)', prompt)
    if len(vague_positions) > 2:
        suggestions.append('prompt 中有较多模糊方位词（左边/右边/旁边），建议绑定场景锚点（如"窗户旁""门框右侧"）')

    return issues, suggestions


def check_rule_13(segment, project):
    """规则13: 人物出现节制检查"""
    issues = []
    suggestions = []

    shots = segment.get('shots', [])
    character_ids = segment.get('character_ids', [])

    if len(character_ids) == 0 and len(shots) > 0:
        action_texts = [s.get('action', '') for s in shots]
        if not any('无人物' in a or '局部' in a or '空镜' in a for a in action_texts):
            suggestions.append('非人物镜头建议在 action 中明确标注"无人物"或说明承载的情绪/信息')

    return issues, suggestions


def check_rule_14(segment, project):
    """规则14: 衔接约束检查"""
    issues = []
    suggestions = []

    prompt = segment.get('prompt', '')
    if '视线' not in prompt and '看向' not in prompt:
        suggestions.append('对话/对峙场景建议在 prompt 中明确视线方向（如"看向画面右侧"）')

    return issues, suggestions


def check_rule_15(segment, project):
    """规则15: 台词约束检查"""
    issues = []
    suggestions = []
    shots = segment.get('shots', [])

    for i, shot in enumerate(shots):
        dialogue = shot.get('dialogue', '').strip()
        if dialogue and len(dialogue) > 50:
            if i == len(shots) - 1 or shots[i+1].get('dialogue', '').strip():
                suggestions.append(f'镜号 {i+1} 台词较长（{len(dialogue)}字），建议切镜插入反应镜头或空镜')

    return issues, suggestions


def check_rule_16(segment, project):
    """规则16: 音频约束检查"""
    issues = []
    suggestions = []
    shots = segment.get('shots', [])

    for i, shot in enumerate(shots):
        sound = shot.get('sound', '').lower()
        if any(kw in sound for kw in ['背景音乐', 'bgm', '配乐', '氛围音乐']):
            issues.append(f'镜号 {i+1} 包含背景音乐，应删除（仅保留音效和人声）')

    return issues, suggestions


def check_rule_17(segment, project):
    """规则17: 画面持续变化原则检查"""
    issues = []
    suggestions = []
    shots = segment.get('shots', [])

    for i, shot in enumerate(shots):
        dialogue = shot.get('dialogue', '').strip()
        action = shot.get('action', '').strip()
        shot_duration = _num(shot.get('end')) - _num(shot.get('start'))

        if dialogue and not action:
            issues.append(f'镜号 {i+1} 有台词但缺少同步动作，可能站桩说话')
            suggestions.append(f'镜号 {i+1} 在台词时加入具体动作（如"边说边整理桌上文件""转身面向窗户"），或拆分成多镜切换')

        if dialogue and action and shot_duration > 5:
            suggestions.append(f'镜号 {i+1} 时长 {shot_duration:.1f}秒较长，建议切镜（换角度/切反应）避免单镜站桩')

    return issues, suggestions


def check_rule_18(segment, project):
    """规则18: 长台词切镜规则检查"""
    issues = []
    suggestions = []
    shots = segment.get('shots', [])

    for i, shot in enumerate(shots):
        dialogue = shot.get('dialogue', '').strip()
        if dialogue and len(dialogue) > 50:
            suggestions.append(f'镜号 {i+1} 长台词切镜优先级：听者反应（人物）> 动作过渡 > 双人同框 > 物件特写（非人物）')

    return issues, suggestions


def check_rule_19(segment, project):
    """规则19: 镜头经济性与节奏检查"""
    issues = []
    suggestions = []
    shots = segment.get('shots', [])

    if len(shots) > 8:
        suggestions.append(f'镜头数量 {len(shots)} 个较多，检查是否有信息重复的镜头可以合并')

    for i in range(len(shots) - 1):
        action1 = shots[i].get('action', '').strip()
        action2 = shots[i+1].get('action', '').strip()
        if action1 and action2 and action1 == action2:
            issues.append(f'镜号 {i+1} 和 {i+2} 的 action 完全相同，信息重复')
            suggestions.append(f'合并镜号 {i+1} 和 {i+2}，或为其中一个增加新信息（反应/空间关系/细节）')

    return issues, suggestions


# 规则检查器映射表
RULE_CHECKERS = {
    1: check_rule_1,
    2: check_rule_2,
    3: check_rule_3,
    4: check_rule_4,
    5: check_rule_5,
    6: check_rule_6,
    7: check_rule_7,
    8: check_rule_8,
    9: check_rule_9,
    10: check_rule_10,
    11: check_rule_11,
    12: check_rule_12,
    13: check_rule_13,
    14: check_rule_14,
    15: check_rule_15,
    16: check_rule_16,
    17: check_rule_17,
    18: check_rule_18,
    19: check_rule_19,
}

CORE_RULES = [1, 4, 6, 7, 10, 11, 16, 17]


def review_segment(segment, project, rules='core', enabled_rules=None):
    """
    审查单个 segment。

    rules: 'core' 只检查8条核心 | 'full' 检查完整19条 | 'custom' 自定义规则
    enabled_rules: list of int, 1-19，仅当 rules='custom' 时有效
    """
    issues = []
    suggestions = []

    if rules == 'core':
        rule_ids = CORE_RULES
    elif rules == 'full':
        rule_ids = list(range(1, 20))
    elif rules == 'custom' and enabled_rules:
        rule_ids = [int(r) for r in enabled_rules if isinstance(r, int) and 1 <= r <= 19]
    else:
        rule_ids = CORE_RULES

    for rule_id in rule_ids:
        checker = RULE_CHECKERS.get(rule_id)
        if checker:
            rule_issues, rule_suggestions = checker(segment, project)
            issues.extend(rule_issues)
            suggestions.extend(rule_suggestions)

    score = max(0, 100 - len(issues) * 15 - len(suggestions) * 5)

    return {
        'segment_id': segment.get('id', ''),
        'title': segment.get('title', ''),
        'issues': issues,
        'suggestions': suggestions,
        'score': score,
        'grade': '优秀' if score >= 90 else '良好' if score >= 70 else '合格' if score >= 60 else '需优化',
        'checked_rules': rule_ids
    }


def review_project_storyboard(project_id, rules='core', enabled_rules=None):
    """
    审查整个项目的分镜。

    rules: 'core' | 'full' | 'custom'
    enabled_rules: list of int, 1-19，仅当 rules='custom' 时有效
    """
    project = store.get('projects', project_id)
    segments = project.get('segments', [])

    if not segments:
        return {
            'segments': [],
            'summary': {
                'total_segments': 0,
                'avg_score': 0,
                'total_issues': 0,
                'total_suggestions': 0,
                'overall_grade': '暂无分镜',
                'global_issues': [],
                'global_suggestions': []
            }
        }

    results = [review_segment(seg, project, rules, enabled_rules) for seg in segments]

    avg_score = sum(r['score'] for r in results) / len(results)
    total_issues = sum(len(r['issues']) for r in results)
    total_suggestions = sum(len(r['suggestions']) for r in results)

    global_issues = []
    global_suggestions = []

    check_global = rules == 'full' or (rules == 'custom' and (6 in (enabled_rules or []) or 7 in (enabled_rules or [])))

    if check_global:
        total_shots = sum(len(seg.get('shots', [])) for seg in segments)
        if total_shots > 0:
            side_45_count = 0
            fixed_count = 0
            for seg in segments:
                prompt = seg.get('prompt', '')
                shots = seg.get('shots', [])
                if '侧45' in prompt or '侧四十五' in prompt:
                    side_45_count += len(shots)
                fixed_count += sum(1 for s in shots if '固定' in s.get('camera', ''))

            side_45_ratio = side_45_count / total_shots if total_shots > 0 else 0
            fixed_ratio = fixed_count / total_shots if total_shots > 0 else 0

            if side_45_ratio < 0.3:
                global_suggestions.append(f'全片侧45度机位占比 {side_45_ratio*100:.0f}% 低于建议30%，可增加侧45度机位（对话与叙事的默认机位）')

            if fixed_ratio > 0.3:
                global_issues.append(f'全片固定镜头占比 {fixed_ratio*100:.0f}% 超过30%建议上限，应替换为微运镜（极缓慢推拉横移）')

    return {
        'segments': results,
        'summary': {
            'total_segments': len(segments),
            'avg_score': round(avg_score, 1),
            'total_issues': total_issues,
            'total_suggestions': total_suggestions,
            'overall_grade': '优秀' if avg_score >= 90 else '良好' if avg_score >= 70 else '合格' if avg_score >= 60 else '需优化',
            'global_issues': global_issues,
            'global_suggestions': global_suggestions,
            'rules_mode': rules,
            'enabled_rules': enabled_rules if rules == 'custom' else None
        }
    }


def get_rule_catalog():
    """返回所有可用规则的目录，供前端展示"""
    return {
        'core_rules': CORE_RULES,
        'all_rules': [
            {'id': 1, 'name': '光源动机铁律', 'category': '光线与色彩'},
            {'id': 2, 'name': '纵深主层机制', 'category': '光线与色彩'},
            {'id': 3, 'name': '五层色彩思维', 'category': '光线与色彩'},
            {'id': 4, 'name': '景别与情绪匹配', 'category': '机位与景别'},
            {'id': 5, 'name': '焦段约束', 'category': '机位与景别'},
            {'id': 6, 'name': '机位角度约束', 'category': '机位与景别'},
            {'id': 7, 'name': '运镜方式约束', 'category': '运镜与节奏'},
            {'id': 8, 'name': '景深策略约束', 'category': '运镜与节奏'},
            {'id': 9, 'name': '人物群像管理', 'category': '人物与表演'},
            {'id': 10, 'name': '表演三通道外化', 'category': '人物与表演'},
            {'id': 11, 'name': '场景空间类型约束', 'category': '场景与空间'},
            {'id': 12, 'name': '画面内容约束', 'category': '画面内容与细节'},
            {'id': 13, 'name': '人物出现节制', 'category': '画面内容与细节'},
            {'id': 14, 'name': '衔接约束', 'category': '衔接与镜头经济性'},
            {'id': 15, 'name': '台词约束', 'category': '衔接与镜头经济性'},
            {'id': 16, 'name': '音频约束', 'category': '衔接与镜头经济性'},
            {'id': 17, 'name': '画面持续变化原则', 'category': '衔接与镜头经济性'},
            {'id': 18, 'name': '长台词切镜规则', 'category': '衔接与镜头经济性'},
            {'id': 19, 'name': '镜头经济性与节奏', 'category': '衔接与镜头经济性'},
        ]
    }
