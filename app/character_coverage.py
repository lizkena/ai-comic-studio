"""Cross-check real speakers against shot character references."""
import re

NON_CHARACTERS = {'旁白', '解说', '解说员', '系统', '系统提示', '系统音', '画外音', '字幕', '音效', '环境音', 'vo', 'os', 'v.o.', 'o.s.'}


def speaker_name(value):
    name = str(value or '').strip()
    name = re.sub(r'[（(](?:画外音|旁白|内心独白|内心|VO|OS|V\.O\.|O\.S\.)[）)]$', '', name, flags=re.I).strip()
    return '' if name.casefold() in NON_CHARACTERS else name


def required_speakers(segment, scene=None):
    names = set()
    lines = [sh.get('dialogue', '') for sh in segment.get('shots', [])]
    if isinstance(segment.get('dialogue_text'), str): lines.append(segment['dialogue_text'])
    for text in lines:
        if not isinstance(text, str): continue
        for line in text.splitlines():
            line = re.sub(r'^\s*\d+:\d+(?:\.\d+)?\s*[–—-]\s*\d+:\d+(?:\.\d+)?\s*', '', line)
            match = re.match(r'^\s*([^:：\n]{1,80})[:：]', line)
            if match:
                name = speaker_name(match[1])
                if name: names.add(name)
    # Also catch a source speaker who visibly acts but has no line in this shot.
    action = '\n'.join(sh.get('action', '') for sh in segment.get('shots', []))
    for dialogue in (scene or {}).get('dialogue', []):
        name = speaker_name(dialogue.get('character'))
        if name and name in action: names.add(name)
    return names


def missing_speakers(segment, assets, scene=None):
    associated = {a['name'] for a in assets if a.get('kind') == 'character' and a['id'] in segment.get('character_ids', [])}
    return sorted(required_speakers(segment, scene) - associated)
