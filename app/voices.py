"""Persistent character voice identity and exact script-to-audio provenance."""
import hashlib,json,re
from . import providers

SPEAKERS=('Vivian','Serena','Uncle_Fu','Dylan','Eric','Ryan','Aiden','Ono_Anna','Sohee')
def fingerprint(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def profile(asset):
    value=asset.get('voice_profile')
    if not isinstance(value,dict):raise ValueError(asset['name']+' 尚未在角色档案绑定音色')
    mode=value.get('mode','preset')
    if mode not in ('preset','reference','design_clone'):raise ValueError('不支持的本地音色模式')
    if mode=='preset' and value.get('speaker') not in SPEAKERS:raise ValueError('请选择有效的本地预设音色')
    if mode=='design_clone' and not value.get('description','').strip():raise ValueError('请填写角色的声音年龄、性别与音色描述')
    if mode=='reference':
        if not asset.get('voice') or not value.get('ref_text','').strip():raise ValueError('参考音色需要声音素材与准确的参考台词')
        providers.file_path(asset['voice'])
    return {**value,'mode':mode,'seed':int(value.get('seed',42)),'language':'Chinese'}

def identity(asset):
    value=profile(asset)
    # Emotional direction belongs to the line; it must never create a new speaker.
    result={k:value.get(k) for k in ('mode','speaker','description','seed','ref_text','language')}
    if value['mode']=='reference':result['reference_sha256']=hashlib.sha256(providers.file_path(asset['voice']).read_bytes()).hexdigest()
    return fingerprint(result)

def character(p,name):
    matches=[a for a in p['assets'] if a['kind']=='character' and name in [a['name'],*a.get('aliases',[])]]
    if len(matches)!=1:raise ValueError('对白角色不能唯一匹配角色档案：'+name)
    return matches[0]

def lines(p,segment):
    result=[]
    direction=segment.get('dialogue_direction',{})
    for shot_index,shot in enumerate(segment.get('shots',[])):
        for text in str(shot.get('dialogue','')).splitlines():
            if not text.strip():continue
            match=re.match(r'^\s*([^:：]+)[:：]\s*(.+)$',text)
            if not match:raise ValueError('对白必须使用“角色：原台词”格式：'+text)
            name,content=match.groups()
            asset=({'id':'narrator','name':'旁白','kind':'character','voice_profile':p['settings'].get('narrator_voice')} if name=='旁白' else character(p,name))
            voice=profile(asset)
            result.append({'character_id':asset['id'],'role':name,'text':content.strip(),
                'shot_index':shot_index,'window_start':float(shot['start']),'window_end':float(shot['end']),
                'emotion':direction.get(str(len(result)),voice.get('performance','自然交谈，避免朗读腔')),
                'voice_id':identity(asset),'profile':voice,'reference':asset.get('voice')})
    return result

def plan(p,segment):
    entries=lines(p,segment)
    return {'segment_id':segment['id'],'duration':float(segment['duration']),'lines':entries,
        'fingerprint':fingerprint({'duration':segment['duration'],'lines':entries})}

def validate_audio(p,segment):
    expected=plan(p,segment)
    if not expected['lines']:return
    record=segment.get('dialogue_manifest') or {}
    if record.get('fingerprint')!=expected['fingerprint']:raise ValueError(segment['title']+' 台词、表演或角色音色已改变，请重新生成配音')
    if record.get('file')!=segment.get('dialogue_audio'):raise ValueError('对白音频与台词清单不匹配')
    path=providers.file_path(record['file'])
    if hashlib.sha256(path.read_bytes()).hexdigest()!=record.get('sha256'):raise ValueError('对白音频文件已改变，请重新校验')
    cues=segment.get('dialogue_cues',[])
    if len(cues)!=len(expected['lines']):raise ValueError('配音条目数量与剧本不一致')
    for cue,line in zip(cues,expected['lines']):
        if any(cue.get(k)!=line[k] for k in ('text','character_id','voice_id')):raise ValueError('配音台词或角色音色与当前剧本不一致')
        if not line['window_start']<=cue['start']<cue['end']<=line['window_end']:raise ValueError('对白时间超出所属镜头')
