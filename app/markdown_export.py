"""将项目分镜导出为 Markdown 文字分镜，供人类导演/摄影师审阅"""
from . import store


def generate_markdown_storyboard(project):
    """将项目的 segments 转换为 Markdown 文字分镜。"""
    lines = []

    # 文件头
    lines.append(f"# {project.get('name', '未命名作品')} - 分镜脚本\n")
    lines.append(f"项目ID: {project.get('id', '')}\n")
    lines.append(f"版本: {project.get('revision', 0)}\n")
    lines.append(f"生成时间: {store.now()}\n")
    lines.append("---\n")

    segments = project.get('segments', [])

    if not segments:
        lines.append("**暂无分镜内容**\n")
        return '\n'.join(lines)

    assets = {a['id']: a for a in project.get('assets', []) if a.get('id')}

    for idx, segment in enumerate(segments, 1):
        lines.append(f"\n## 镜头 {idx:02d} | {segment.get('title', '未命名小节')}\n")

        # 场景信息
        location_id = segment.get('location_id')
        location = assets.get(location_id, {})
        if location:
            lines.append(f"**场景**: {location.get('name', '未知场景')}\n")

        duration = segment.get('duration', 0)
        lines.append(f"**时长**: {duration} 秒\n")

        character_ids = segment.get('character_ids', [])
        if character_ids:
            character_names = [assets.get(cid, {}).get('name', '未知角色') for cid in character_ids]
            lines.append(f"**角色**: {', '.join(character_names)}\n")

        prop_ids = segment.get('prop_ids', [])
        if prop_ids:
            prop_names = [assets.get(pid, {}).get('name', '未知道具') for pid in prop_ids]
            lines.append(f"**道具**: {', '.join(prop_names)}\n")

        if segment.get('continuity'):
            lines.append(f"**衔接**: 接续上一镜头（ID: {segment.get('previous_id', 'N/A')}）\n")

        lines.append("\n### 画面内容\n")
        prompt = (segment.get('prompt') or '').strip()
        lines.append(f"{prompt}\n" if prompt else "（暂无画面描述）\n")

        shots = segment.get('shots', [])
        if shots:
            lines.append("\n### 镜号分解\n")
            for shot_idx, shot in enumerate(shots, 1):
                start = shot.get('start', 0)
                end = shot.get('end', 0)
                size = shot.get('size', '未标注')
                camera = shot.get('camera', '未标注')
                action = (shot.get('action') or '').strip()
                dialogue = (shot.get('dialogue') or '').strip()
                sound = (shot.get('sound') or '').strip()

                lines.append(f"\n**镜号 {shot_idx}** ({start}-{end}秒 | {size} | {camera})\n")

                if action:
                    lines.append(f"- **动作**: {action}\n")
                if dialogue:
                    lines.append(f"- **台词**: {dialogue}\n")
                if sound:
                    lines.append(f"- **音效**: {sound}\n")

        lines.append("\n---\n")

    lines.append(f"\n**总镜头数**: {len(segments)}\n")
    total = sum(_num(seg.get('duration')) for seg in segments)
    lines.append(f"**总时长**: {total:.1f} 秒\n")

    return '\n'.join(lines)


def _num(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
