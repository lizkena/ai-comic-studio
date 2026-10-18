"""分镜专业审查：检查已生成的 JSON 是否符合电影级约束。"""
import re
from . import store


def _num(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def review_segment(segment, project, rules='core'):
    """
    审查单个 segment。
    rules: 'core' 只检查8条核心 | 'full' 检查完整19条（预留）
    返回：{'issues': [...], 'suggestions': [...], 'score': 0-100}
    """
    issues = []
    suggestions = []
    prompt = segment.get('prompt', '')
    shots = segment.get('shots', [])
    duration = segment.get('duration', 0)

    # === 规则1: 光源动机检查 ===
    light_sources = re.findall(r'(窗户|窗|灯|霓虹|火|屏幕|太阳|月光|街灯|车灯|烛|蜡烛)', prompt)
    if not light_sources:
        issues.append('未明确光源来源，可能导致无源补光')
        suggestions.append('在 prompt 中指明光从哪里来（如"窗户透入的黄昏逆光""天花板灯具向下打光"）')
    elif len(light_sources) == 1 and '室内' in prompt:
        suggestions.append('室内场景建议说明光的方向与衰减（如"左侧窗户逆光，右侧墙面暗部"）')

    # === 规则2: 机位配比检查 ===
    # 这个需要全局统计，单镜只检查是否有机位角度描述
    if not re.search(r'(侧|正面|过肩|仰|俯|平视|斜|主观|视角)', prompt):
        suggestions.append('建议在 prompt 中明确机位角度（如"侧45度""微仰15度"）')

    # === 规则3: 景别检查 ===
    has_scale = any(re.search(r'(特写|近景|中景|全景|远景|大远景)', s.get('size', '')) for s in shots)
    if not has_scale:
        suggestions.append('建议在 shots 中标注景别（size 字段）')

    # === 规则4: 运镜检查 ===
    if len(shots) == 0:
        issues.append('小节缺少 shots 镜号分解')
    else:
        fixed_count = sum(1 for s in shots if '固定' in s.get('camera', ''))
        if fixed_count / len(shots) > 0.3:
            issues.append(f'固定镜头占比 {fixed_count}/{len(shots)} = {fixed_count/len(shots)*100:.0f}% 超过30%建议上限')
            suggestions.append('将部分固定镜头改为极缓慢推镜或横移，让画面保持流动')

        # 检查是否有运镜方式描述
        cameras = [s.get('camera', '').strip() for s in shots]
        if all(not c for c in cameras):
            suggestions.append('建议在 shots 的 camera 字段写明运镜方式（推镜/横移/手持微晃/固定等）')

    # === 规则5: 画面持续变化检查 ===
    for i, shot in enumerate(shots):
        dialogue = shot.get('dialogue', '').strip()
        action = shot.get('action', '').strip()
        shot_duration = _num(shot.get('end')) - _num(shot.get('start'))

        if dialogue and not action:
            issues.append(f'镜号 {i+1} 有台词但缺少同步动作，可能站桩说话')
            suggestions.append(f'镜号 {i+1} 在台词时加入具体动作（如"边说边整理桌上文件""转身面向窗户"），或拆分成多镜切换')

        if dialogue and action and shot_duration > 5:
            suggestions.append(f'镜号 {i+1} 时长 {shot_duration:.1f}秒较长，建议切镜（换角度/切反应）避免单镜站桩')

    # === 规则6: 镜头经济性检查 ===
    if len(shots) > 8:
        suggestions.append(f'镜头数量 {len(shots)} 个较多，检查是否有信息重复的镜头可以合并')

    # 检查相邻 shots 的 action 是否重复
    for i in range(len(shots) - 1):
        action1 = shots[i].get('action', '').strip()
        action2 = shots[i+1].get('action', '').strip()
        if action1 and action2 and action1 == action2:
            issues.append(f'镜号 {i+1} 和 {i+2} 的 action 完全相同，信息重复')
            suggestions.append(f'合并镜号 {i+1} 和 {i+2}，或为其中一个增加新信息（反应/空间关系/细节）')

    # === 规则7: 场景空间约束检查 ===
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

                if any('大远景' in s.get('size', '') or '远景' in s.get('size', '') for s in shots):
                    issues.append('室内普通层高使用了大远景/远景，景别超出空间物理范围')
                    suggestions.append('改用全景或中全景')

    # === 规则8: 表演外化检查 ===
    has_emotion_words = re.search(r'(愤怒|悲伤|高兴|惊讶|恐惧|焦虑|紧张|犹豫)', prompt)
    has_action_detail = re.search(r'(指节|拇指|拳头|眼眶|瞳孔|嘴角|喉结|呼吸|睫毛|视线)', prompt)

    if has_emotion_words and not has_action_detail:
        suggestions.append('prompt 中有情绪词但缺少具体表演细节，建议写小动作或微表情（如"指节发白""眼眶泛红""呼吸变浅"）')

    # 检查 shots 的 action 字段是否有表演细节
    for i, shot in enumerate(shots):
        action = shot.get('action', '')
        if any(emo in action for emo in ['愤怒', '悲伤', '高兴', '惊讶', '恐惧']) and not any(detail in action for detail in ['手', '眼', '呼吸', '视线', '肩', '拳']):
            suggestions.append(f'镜号 {i+1} 的 action 有情绪词但缺少动作外化，建议加小动作（如"攥紧拳头""视线游移"）')

    # === 计算得分 ===
    score = max(0, 100 - len(issues) * 15 - len(suggestions) * 5)

    return {
        'segment_id': segment.get('id', ''),
        'title': segment.get('title', ''),
        'issues': issues,
        'suggestions': suggestions,
        'score': score,
        'grade': '优秀' if score >= 90 else '良好' if score >= 70 else '合格' if score >= 60 else '需优化'
    }


def review_project_storyboard(project_id, rules='core'):
    """审查整个项目的分镜。"""
    project = store.get('projects', project_id)
    segments = project.get('segments', [])

    if not segments:
        return {
            'segments': [],
            'summary': {
                'total_segments': 0,
                'avg_score': 0,
                'total_issues': 0,
                'overall_grade': '暂无分镜'
            }
        }

    results = [review_segment(seg, project, rules) for seg in segments]

    avg_score = sum(r['score'] for r in results) / len(results)
    total_issues = sum(len(r['issues']) for r in results)
    total_suggestions = sum(len(r['suggestions']) for r in results)

    # 全局检查：机位配比（需要统计全部 segments）
    global_issues = []
    global_suggestions = []

    total_shots = sum(len(seg.get('shots', [])) for seg in segments)
    if total_shots > 0:
        # 统计机位类型（简化版，只检查侧45度和固定）
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
            'global_suggestions': global_suggestions
        }
    }
