"""User-facing video download names; internal media IDs remain stable."""
import re

def safe_name(value):
    name=re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(value or '')).strip().rstrip('. ')
    return name[:70] or '未命名'

def download_name(project, episode_id=None, segment=None, version=None):
    episodes=project.get('outputs',{}).get('script',{}).get('episodes',[])
    eid=segment.get('episode_id') if segment else episode_id
    episode=next((e for e in episodes if e['id']==eid),None)
    parts=[safe_name(project.get('name'))]
    if episode:
        parts.append(f"第{episodes.index(episode)+1:02d}集")
        parts.append(safe_name(episode.get('title')))
    if segment:
        siblings=[s for s in project['segments'] if s.get('episode_id')==eid]
        parts.extend([f"镜头{siblings.index(segment)+1:02d}",safe_name(segment.get('title'))])
        versions=segment.get('versions',[])
        parts.append(f"v{versions.index(version)+1:02d}")
    else:
        parts.append('成片')
    return '_'.join(parts)+'.mp4'
