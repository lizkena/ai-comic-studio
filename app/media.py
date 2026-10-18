import asyncio
import json
import shutil
from pathlib import Path
from PIL import Image, ImageStat
from .store import ROOT, MEDIA, uid
from .providers import settings, file_path


def binary(name):
    candidate = settings().get(name)
    if candidate and Path(candidate).is_file(): return candidate
    bundled = ROOT / 'runtime' / 'tools' / (name + '.exe')
    if bundled.is_file(): return str(bundled)
    found = shutil.which(name)
    if not found: raise ValueError('找不到 ' + name + '，请在设置中指定可执行文件')
    return found


async def run(args, cwd=None):
    process = await asyncio.create_subprocess_exec(*[str(x) for x in args], cwd=cwd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try: stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=1800)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        process.kill(); await process.wait(); raise
    if process.returncode: raise ValueError('媒体处理失败：' + stderr.decode(errors='replace')[-1800:])
    return stdout


async def probe(name):
    result = json.loads(await run([binary('ffprobe'), '-v', 'error', '-show_format', '-show_streams', '-of', 'json', file_path(name)]))
    if not any(s['codec_type'] == 'video' for s in result['streams']): raise ValueError('结果没有可播放视频流')
    return result


async def validate_audio(name):
    result=json.loads(await run([binary('ffprobe'),'-v','error','-show_streams','-of','json',file_path(name)]))
    if not any(s.get('codec_type')=='audio' for s in result.get('streams',[])):raise ValueError('素材没有可播放音频流')
    return result


async def tail(name, at=None):
    info = await probe(name); duration = float(info['format']['duration'])
    timestamp = max(0, duration - .12) if at is None else float(at)
    if not 0 <= timestamp < duration: raise ValueError('抽帧时间须在视频时长内')
    filename = uid('tail') + '.png'; target = MEDIA / filename
    await run([binary('ffmpeg'), '-y', '-v', 'error', '-ss', timestamp, '-i', file_path(name), '-frames:v', '1', target])
    with Image.open(target) as img:
        gray = img.convert('L'); stats = ImageStat.Stat(gray)
        dark = stats.mean[0] < 8 or stats.stddev[0] < 2
    return {'tail': filename, 'tail_at': round(timestamp, 3), 'tail_accepted': not dark,
            'tail_warning': '尾帧疑似黑场/无细节，请手动选择时间点' if dark else ''}


async def mix_audio(name, tracks, keep_source=True, source_gain=.5):
    """Mix timed dialogue, ambience and effects without replacing the source by default.

    Only disable source audio when a clean ambience stem is supplied separately.
    This mixes a timeline; it does not change actors' mouth movements.
    """
    info=await probe(name); duration=float(info['format']['duration'])
    args=[binary('ffmpeg'),'-y','-v','error','-i',file_path(name)]
    filters=[]; labels=[]
    if keep_source and any(s['codec_type']=='audio' for s in info['streams']):
        if not 0<=float(source_gain)<=2: raise ValueError('原音轨音量须在0–2之间')
        filters.append(f'[0:a]aresample=48000,aformat=channel_layouts=stereo,volume={float(source_gain)}[native]');labels.append('[native]')
    for index,track in enumerate(tracks,1):
        start=float(track.get('start',0));gain=float(track.get('gain',1))
        if not 0<=start<duration or not 0<=gain<=2: raise ValueError('音轨时间或音量无效')
        await validate_audio(track['file'])
        if track.get('loop'):args+=['-stream_loop','-1']
        args+=['-i',file_path(track['file'])]
        stop=min(float(track.get('duration',duration-start)),duration-start)
        if stop<=0:raise ValueError('音轨时长须大于0')
        delay=round(start*1000);label=f'track{index}'
        filters.append(f'[{index}:a]atrim=duration={stop},asetpts=N/SR/TB,aresample=48000,aformat=channel_layouts=stereo,volume={gain},adelay={delay}|{delay}[{label}]')
        labels.append(f'[{label}]')
    if not labels:raise ValueError('没有可混合的音轨')
    filters.append(''.join(labels)+f'amix=inputs={len(labels)}:normalize=0,asetpts=N/SR/TB,alimiter=limit=.95:level=false,apad=whole_dur={duration}[mixed]')
    target=uid('mixed')+'.mp4'
    args+=['-filter_complex',';'.join(filters),'-map','0:v:0','-map','[mixed]','-t',duration,'-c:v','copy','-c:a','aac','-ar','48000','-ac','2','-b:a','192k','-movflags','+faststart',MEDIA/target]
    await run(args)
    output=await probe(target)
    audio=next((s for s in output['streams'] if s['codec_type']=='audio'),{})
    if float(audio.get('duration',0))<duration-.1:raise ValueError('混音时长不足，未采用结果')
    return {'file':target,'audio_tracks':tracks,'kept_source_audio':keep_source,'lip_synced':False}


def dialogue_subtitles(cues, start, stop, width, height):
    """Render literal text after scaling, with cue times relative to the retained clip."""
    def clock(seconds):
        ticks=max(0,round(seconds*100));seconds,centis=divmod(ticks,100);minutes,seconds=divmod(seconds,60);hours,minutes=divmod(minutes,60)
        return f'{hours}:{minutes:02d}:{seconds:02d}.{centis:02d}'
    lines=[]
    for cue in cues:
        begin=max(start,float(cue['start']));end=min(stop,float(cue['end']))
        if end<=begin:continue
        text=str(cue['text']).replace('\\','＼').replace('{','｛').replace('}','｝').replace('\r','').replace('\n','\\N')
        lines.append(f'Dialogue: 0,{clock(begin-start)},{clock(end-start)},Default,,0,0,0,,{text}')
    if not lines:return None
    content=f'''[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft YaHei,{40 if width>=1000 else 32},&H00FFFFFF,&H00FFFFFF,&H00101010,&H80101010,0,0,0,0,100,100,0,0,1,2,1,2,50,50,30,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    target=MEDIA/(uid('subtitles')+'.ass');target.write_text(content+'\n'.join(lines)+'\n',encoding='utf-8-sig')
    return target


async def compose(p, episode_id=None):
    selected = [s for s in p['segments'] if not episode_id or s.get('episode_id') == episode_id]
    if not selected: raise ValueError('没有可剪辑的小节')
    names = []
    ratio = p['settings']['ratio']; width, height = (1280, 720) if ratio == '16:9' else (720, 1280) if ratio == '9:16' else (720, 720)
    for segment in selected:
        version = next((v for v in segment.get('versions', []) if v['id'] == segment.get('current_version')), None)
        if not version or not version.get('file'): raise ValueError(segment['title'] + ' 没有选用视频')
        source = file_path(version['file']); info = await probe(source.name)
        start = float(segment.get('trim_start', 0)); stop = float(segment.get('trim_end') or info['format']['duration'])
        if not 0 <= start < stop <= float(info['format']['duration']) + .1: raise ValueError(segment['title'] + ' 裁剪区间无效')
        target = MEDIA / (uid('normalized') + '.mp4'); names.append(target)
        args = [binary('ffmpeg'), '-y', '-v', 'error', '-ss', start, '-i', source]
        audio = any(s['codec_type'] == 'audio' for s in info['streams'])
        if not audio: args += ['-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=48000']
        subtitle=dialogue_subtitles(version.get('dialogue_cues',[]),start,stop,width,height) if p['settings'].get('subtitles',True) else None
        video_filter=f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24'
        if subtitle:video_filter+=f",subtitles=filename='{subtitle.name}'"
        args += ['-t', stop-start, '-map', '0:v:0', '-map', '0:a:0' if audio else '1:a:0', '-vf', video_filter, '-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-ar','48000','-ac','2',target]
        try:await run(args,cwd=MEDIA)
        finally:
            if subtitle:subtitle.unlink(missing_ok=True)
    listing = MEDIA / (uid('concat') + '.txt')
    # Names are generated by the application; do not interpolate user-controlled paths.
    listing.write_text('\n'.join("file '" + f.name + "'" for f in names), encoding='utf-8')
    target = MEDIA / (uid('episode') + '.mp4')
    try:
        await run([binary('ffmpeg'), '-y', '-v','error','-f','concat','-safe','1','-i',listing,'-c','copy','-movflags','+faststart',target])
    finally:
        listing.unlink(missing_ok=True)
        for f in names: f.unlink(missing_ok=True)
    return {'id': uid('artifact'), 'file': target.name, 'episode_id': episode_id, 'sources': [{'segment_id':s['id'], 'version_id':s['current_version']} for s in selected]}
