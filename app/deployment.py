"""Managed installation only inside this product's runtime folder; never runs on startup."""
import asyncio
import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import threading
import zipfile
from pathlib import Path
import httpx
from .store import ROOT, get, put, now

MANIFEST = json.loads((ROOT/'workflows/h3-model-manifest.json').read_text(encoding='utf8'))
COMFY_SOURCE = json.loads((ROOT/'workflows/comfy-source-manifest.json').read_text(encoding='utf8'))
state_id = 'deployment_state'
DOWNLOAD_BLOCK = 64 * 1024**2
DOWNLOAD_ATTEMPTS = 5


def error_message(error):
    if isinstance(error,httpx.ReadTimeout): return 'ReadTimeout：下载连接长时间没有收到数据'
    if isinstance(error,httpx.ConnectTimeout): return 'ConnectTimeout：连接下载服务器超时'
    if isinstance(error,httpx.TimeoutException): return type(error).__name__+'：网络请求超时'
    if isinstance(error,httpx.HTTPStatusError):
        return 'HTTP '+str(error.response.status_code)+'：下载服务器 '+error.request.url.host+' 返回错误'
    return type(error).__name__+'：'+(str(error).strip() or '未返回错误详情')


class DownloadInterrupted(ValueError): pass


async def retry_delay(seconds):
    for _ in range(int(seconds*2)):
        if cancelled(): raise asyncio.CancelledError()
        await asyncio.sleep(.5)


def status():
    try: return get('settings', state_id)
    except KeyError: return {'id':state_id,'status':'idle','progress':0,'logs':[],'verified_sample':False}


def update(**fields):
    s=status(); s.update(fields); put('settings',s); return s


def log(text):
    s=status(); s['logs']=(s.get('logs',[])+[now()+' '+text])[-200:]; put('settings',s)


def hardware():
    gpus=[]
    try:
        result=subprocess.run(['nvidia-smi','--query-gpu=name,memory.total,driver_version','--format=csv,noheader,nounits'], capture_output=True,text=True,timeout=15,creationflags=0x08000000 if os.name=='nt' else 0)
        for line in result.stdout.strip().splitlines():
            name,mem,driver=[x.strip() for x in line.split(',')]; gpus.append({'name':name,'vram_gb':round(float(mem)/1024,1),'driver':driver})
    except (OSError, ValueError, subprocess.TimeoutExpired): pass
    ram=None
    if os.name=='nt':
        class Memory(ctypes.Structure):
            _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(n,ctypes.c_ulonglong) for n in ['total','available','page_total','page_available','virtual_total','virtual_available','extended']]
        m=Memory(); m.length=ctypes.sizeof(m)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)): ram=round(m.total/1024**3,1)
    free=round(shutil.disk_usage(ROOT).free/1024**3,1)
    size=round(sum(m['size'] for m in MANIFEST['models'])/1024**3,1)
    vram=max([g['vram_gb'] for g in gpus] or [0])
    reasons=[]
    if not gpus: reasons.append('未检测到 NVIDIA CUDA 显卡，推荐使用远程服务')
    if vram and vram<8: reasons.append('显存较低，首版未验证该设备的本地推理')
    if ram is not None and ram<31: reasons.append('内存不足约32GB，量化权重卸载可能受限')
    if free<size+20: reasons.append('磁盘空间不足，权重与运行环境至少需约'+str(round(size+20,1))+'GB空闲')
    return {'gpus':gpus,'ram_gb':ram,'free_gb':free,'download_gb':size,'recommended':'官方 Ref2VA pruned INT8 + NVFP4 文本编码器 / 低显存卸载' if vram>=8 else '远程 ComfyUI / API 服务',
            'recommendation_note':'按硬件资源推荐安装路径，生成速度与质量须以样片验证；12GB显卡使用低显存卸载，不保证实时生成。',
            'blockers':reasons,'can_deploy':not reasons,'manifest':MANIFEST,'target':str(ROOT/'runtime/h3')}


def cancelled(): return status()['status']=='cancelled'


async def command(args):
    if cancelled(): raise asyncio.CancelledError()
    log('执行：'+' '.join(str(x) for x in args[:4]))
    process=await asyncio.create_subprocess_exec(*map(str,args), stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT,
                                                 creationflags=0x08000000 if os.name=='nt' else 0)
    while True:
        try: line=await asyncio.wait_for(process.stdout.readline(),timeout=2)
        except asyncio.TimeoutError:
            if cancelled(): process.kill(); await process.wait(); raise asyncio.CancelledError()
            continue
        if not line: break
        log(line.decode(errors='replace').strip()[-500:])
        if cancelled(): process.kill(); await process.wait(); raise asyncio.CancelledError()
    if await process.wait(): raise ValueError('部署命令执行失败，请查看部署日志')


async def fetch(url,target,size=None,digest=None):
    target.parent.mkdir(parents=True,exist_ok=True)
    if cancelled(): raise asyncio.CancelledError()
    if target.exists() and (not size or target.stat().st_size==size):
        if not digest or await asyncio.to_thread(hash_file,target)==digest: log('已校验，跳过 '+target.name); return
    part=target.with_suffix(target.suffix+'.part')
    offset=part.stat().st_size if part.exists() else 0
    if size and offset>size:
        part.replace(part.with_name(part.name+'.invalid-'+str(time.time_ns())))
        offset=0; log('已保留异常长度的旧下载，重新获取 '+target.name)
    if offset: log('从 '+str(round(offset/1024**3,2))+' GB 断点继续 '+target.name)
    total=size; failures=0; finished=bool(size and offset==size)
    update(current_file=target.name,bytes=offset,total_bytes=total,progress=round(offset/total*100,1) if total else None)
    async with httpx.AsyncClient(timeout=httpx.Timeout(60,read=120),follow_redirects=True) as client:
        while not finished:
            if cancelled(): raise asyncio.CancelledError()
            offset=part.stat().st_size if part.exists() else 0
            end=min(offset+DOWNLOAD_BLOCK,total)-1 if total else None
            headers={'Accept-Encoding':'identity','Cache-Control':'no-cache'}
            if end is not None: headers['Range']=f'bytes={offset}-{end}'
            elif offset: headers['Range']=f'bytes={offset}-'
            received=0; expected=None; partial=False
            try:
                # Resolve the official URL again for each bounded block; avoid stale
                # cached redirects containing an expired or differently ranged CDN URL.
                params={'download':'true','studio_range':str(offset)+'-'+str(time.time_ns())} if 'huggingface.co/' in url else None
                async with client.stream('GET',url,headers=headers,params=params) as response:
                    response.raise_for_status()
                    partial=response.status_code==206
                    if partial:
                        match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',response.headers.get('content-range',''))
                        if not match: raise DownloadInterrupted('服务器没有返回有效的续传区间')
                        start,stop,remote_total=map(int,match.groups())
                        if start!=offset or stop<start or stop>=remote_total or (end is not None and stop>end):
                            raise DownloadInterrupted('服务器返回的续传区间与本地断点不符')
                        if total and remote_total!=total: raise ValueError('下载文件总长度与固定清单不符：'+target.name)
                        total=total or remote_total; expected=stop-start+1
                    else:
                        if offset: log('服务器未接受续传，重新下载完整文件 '+target.name)
                        offset=0
                        length=response.headers.get('content-length')
                        expected=int(length) if length else None
                        if total and expected and expected!=total: raise ValueError('下载文件总长度与固定清单不符：'+target.name)
                        total=total or expected
                    last_update=0
                    with part.open('ab' if partial and offset else 'wb') as out:
                        async for chunk in response.aiter_bytes(1024*1024):
                            if cancelled(): raise asyncio.CancelledError()
                            if expected is not None and received+len(chunk)>expected:
                                raise DownloadInterrupted('服务器返回的数据超出下载区间')
                            out.write(chunk); received+=len(chunk); offset+=len(chunk)
                            stamp=time.monotonic()
                            if stamp-last_update>=1:
                                update(current_file=target.name,progress=round(offset/total*100,1) if total else None,bytes=offset,total_bytes=total)
                                last_update=stamp
                    if expected is not None and received!=expected: raise DownloadInterrupted('下载连接提前结束')
                    if not received: raise DownloadInterrupted('下载服务器未返回文件数据')
                failures=0
                update(bytes=offset,total_bytes=total,progress=round(offset/total*100,1) if total else None)
                finished=bool(total and offset==total) or not partial
            except (httpx.TransportError,httpx.HTTPStatusError,DownloadInterrupted) as error:
                retryable=not isinstance(error,httpx.HTTPStatusError) or error.response.status_code in (403,408,429,500,502,503,504)
                failures+=1
                offset=part.stat().st_size if part.exists() else 0
                # A disconnect after the last byte can be resolved by the final hash.
                if total and offset==total: finished=True; break
                detail=error_message(error)
                update(bytes=offset,total_bytes=total,progress=round(offset/total*100,1) if total else None)
                if not retryable or failures>=DOWNLOAD_ATTEMPTS:
                    raise DownloadInterrupted(target.name+' 下载中断（'+detail+'）。已保留 '+str(round(offset/1024**3,2))+' GB，可继续部署。') from error
                delay=min(2**failures,16)
                log(target.name+'：'+detail+'；'+str(delay)+'秒后自动续传（'+str(failures)+'/'+str(DOWNLOAD_ATTEMPTS-1)+'）')
                await retry_delay(delay)
    if size and part.stat().st_size!=size: raise ValueError('下载文件长度不符：'+target.name)
    if cancelled(): raise asyncio.CancelledError()
    update(current_file='校验 '+target.name,progress=100)
    if digest and await asyncio.to_thread(hash_file,part)!=digest:
        part.unlink(); raise ValueError('SHA256 校验失败，可重新部署：'+target.name)
    if cancelled(): raise asyncio.CancelledError()
    part.replace(target); log('下载并校验 '+target.name)


def hash_file(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(8*1024**2),b''): h.update(block)
    return h.hexdigest()


async def install_source(root):
    """Fetch a verified official revision without GitHub's rate-limited REST API."""
    comfy=root/'ComfyUI'
    if (comfy/'main.py').exists():
        log('复用已安装的 ComfyUI 源码')
        return comfy
    commit=COMFY_SOURCE['commit']
    log('ComfyUI 固定提交 '+commit+'，直接下载官方源码，无需查询 GitHub API')
    update(comfy_commit=commit,current_file='ComfyUI 官方源码',progress=0)
    archive=root/'comfy-source.zip'
    await fetch(COMFY_SOURCE['url'],archive,COMFY_SOURCE['size'],COMFY_SOURCE['sha256'])
    unpacked=root/('ComfyUI-'+commit)
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            dest=(root/item.filename).resolve()
            if not dest.is_relative_to(unpacked.resolve()): raise ValueError('部署压缩包路径非法')
        required=['main.py','requirements.txt','comfy_extras/nodes_minimax_h3.py']
        if any('ComfyUI-'+commit+'/'+name not in z.namelist() for name in required):
            raise ValueError('ComfyUI 源码不完整或不包含 H3 支持')
        z.extractall(root)
    if cancelled(): raise asyncio.CancelledError()
    if comfy.exists(): comfy.rename(root/('ComfyUI-incomplete-'+str(int(time.time()))))
    unpacked.rename(comfy)
    (comfy/'.comic-studio-source.json').write_text(json.dumps(COMFY_SOURCE,indent=2),encoding='utf8')
    log('ComfyUI 官方源码校验与解压完成')
    return comfy


async def install():
    root=ROOT/'runtime/h3'; root.mkdir(parents=True,exist_ok=True)
    try:
        hw=await asyncio.to_thread(hardware)
        if hw['blockers']: raise ValueError('；'.join(hw['blockers']))
        update(status='running',logs=[],error=None,progress=0,current_file='准备环境',verified_sample=False)
        log('部署目标 '+str(root)); log('权重来源与版本 '+MANIFEST['revision'])
        comfy=await install_source(root)
        py=root/'venv/Scripts/python.exe' if os.name=='nt' else root/'venv/bin/python'
        if not py.exists(): await command([sys.executable,'-m','venv',root/'venv'])
        marker=root/'dependencies.ready'
        if not marker.exists():
            update(current_file='安装 PyTorch CUDA 与 ComfyUI 依赖',progress=None,bytes=0,total_bytes=0)
            # Python 3.10's bundled pip misreads modern wheel names and falls back
            # to source builds against the CUDA-only index. Upgrade in our venv first.
            await command([py,'-m','pip','install','--upgrade','pip','setuptools','wheel','--index-url','https://pypi.org/simple','--progress-bar','off'])
            await command([py,'-m','pip','install','torch','torchvision','torchaudio','--index-url','https://download.pytorch.org/whl/cu128','--progress-bar','off'])
            await command([py,'-m','pip','install','-r',comfy/'requirements.txt','--progress-bar','off'])
            marker.write_text(now())
        for model in MANIFEST['models']:
            await fetch(model['url'],comfy/'models'/model['directory']/model['name'],model['size'],model.get('sha256'))
        templates=comfy/'user/default/workflows'; templates.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/'workflows/official-h3-r2v-ui.json',templates/'AI-Comic-H3.json')
        update(status='installed',progress=100,current_file='',verified_sample=False)
        log('安装完成。启动 ComfyUI 后导出 API 工作流并映射输入，成功样片后完成可用验收。')
    except asyncio.CancelledError: update(status='cancelled'); log('部署已停止，已完成文件和部分下载保留，可继续部署')
    except Exception as e:
        detail=error_message(e)[:600]
        update(status='failed',error=detail,error_type=type(e).__name__); log('失败：'+detail)


_service_process = None
_service_start_lock = threading.Lock()
_service_ready_lock = asyncio.Lock()


def start_service():
    with _service_start_lock:
        return _start_service()


def _start_service():
    global _service_process
    root=ROOT/'runtime/h3'; py=root/'venv/Scripts/python.exe'; comfy=root/'ComfyUI'
    if not py.exists() or not (root/'dependencies.ready').exists(): raise ValueError('请先完成部署')
    address='http://127.0.0.1:8190'
    try:
        response=httpx.get(address+'/system_stats',timeout=2)
        response.raise_for_status()
        args=response.json().get('system',{}).get('argv',[])
        if not args or Path(args[0]).resolve()!=(comfy/'main.py').resolve():
            raise ValueError('端口 8190 已被其他服务占用，请先处理该服务或使用其他地址接入')
        return {'pid':status().get('service_pid'),'url':address,'message':'本地 ComfyUI 服务已运行，直接打开即可'}
    except httpx.TransportError: pass
    except httpx.HTTPStatusError: raise ValueError('端口 8190 已被其他服务占用，请查看本地服务配置')
    if _service_process is not None and _service_process.poll() is None:
        return {'pid':_service_process.pid,'url':address,'message':'本地 H3 服务正在启动'}
    # Loopback-only and managed process; never touches an existing ComfyUI installation.
    with (root/'comfy.log').open('a',encoding='utf8') as out:
        process=subprocess.Popen([str(py),'-X','utf8','-u',str(comfy/'main.py'),'--listen','127.0.0.1','--port','8190','--lowvram','--reserve-vram','3.5'],cwd=comfy,stdout=out,stderr=out,creationflags=0x08000000 if os.name=='nt' else 0)
    _service_process = process
    update(service_pid=process.pid); return {'pid':process.pid,'url':address,'message':'服务正在启动，日志保存在 runtime/h3/comfy.log'}


def is_managed_h3(provider):
    from urllib.parse import urlsplit
    url=urlsplit(provider.get('base_url',''))
    return provider.get('protocol')=='comfy' and url.scheme=='http' and url.hostname in ('127.0.0.1','localhost') and url.port==8190 and url.path in ('','/')


async def service_ready():
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            response=await client.get('http://127.0.0.1:8190/system_stats')
        response.raise_for_status()
        args=response.json().get('system',{}).get('argv',[])
        if not args or Path(args[0]).resolve()!=(ROOT/'runtime/h3/ComfyUI/main.py').resolve():
            raise ValueError('端口 8190 被其他服务占用，无法自动启动本地 H3')
        return True
    except (httpx.ConnectError,httpx.ConnectTimeout,httpx.ReadTimeout):
        return False
    except (httpx.HTTPStatusError, ValueError, TypeError) as error:
        raise ValueError('本地 H3 服务检查失败：'+str(error)) from error


async def ensure_service_ready(progress, timeout=180, interval=1):
    # One managed launch even when several video jobs arrive together.
    async with _service_ready_lock:
        if await service_ready(): return
        progress('正在自动启动本地 H3 服务，启动完成后将提交视频')
        await asyncio.to_thread(start_service)
        loop=asyncio.get_running_loop();started=loop.time();reported=started
        while loop.time()-started<timeout:
            if await service_ready():
                progress('本地 H3 服务已就绪，继续提交视频')
                return
            if _service_process is not None and _service_process.poll() is not None:
                raise ValueError('本地 H3 启动进程已退出，请查看 runtime/h3/comfy.log')
            if loop.time()-reported>=10:
                progress(f'正在等待本地 H3 启动（{int(loop.time()-started)} 秒），视频尚未提交')
                reported=loop.time()
            await asyncio.sleep(interval)
        raise ValueError('本地 H3 启动等待超时，视频尚未提交，请查看 runtime/h3/comfy.log')
