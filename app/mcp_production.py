"""Durable, scoped production executor. Each advance submits at most one real job."""
import asyncio
import copy
from . import store,yaoguang,mcp_workflow

RUNNERS={}

def task(graph):return graph.get('settings',{}).get('studioMcpProduction')

def scope(graph):
 t=task(graph)
 if not t:return None
 plan=graph.get('settings',{}).get('studioMcpBreakdowns',{}).get(t['breakdown_id'])
 if not plan:raise ValueError('制作计划已丢失，请重新整理')
 rows=[r for r in plan['shots'] if r['key'] in t['shot_keys']]
 if len(rows)!=len(t['shot_keys']):raise ValueError('制作范围已变化')
 byid={n['id']:n for n in graph['nodes']};allowed=set()
 for r in rows:
  allowed.update([r['frame_id'],r['video_id']])
  frame=byid.get(r['frame_id'])
  if not frame:raise ValueError('制作镜头已被删除')
  for ident in frame.get('studioMcpAssetIds',[]):
   allowed.add(ident);n=byid.get(ident,{})
   if n.get('studioIdentityParentId'):allowed.add(n['studioIdentityParentId'])
 return t,rows,allowed

def start(pid,graph,args):
 from .mcp_integration import save_graph
 from . import generation_supervision
 if generation_supervision.enabled(pid):raise ValueError('本项目为逐项监督模式，禁止自动批量推进；请使用已整理分镜的 studio_generate_media，一次仅生成获放行的卡片')
 if args.get('confirm_generation') is not True:raise ValueError('完整制作需要实际生成授权')
 plan=graph.get('settings',{}).get('studioMcpBreakdowns',{}).get(args['breakdown_id'])
 if not plan:raise ValueError('请先 studio_apply_breakdown 整理剧本与资产')
 keys=args.get('shot_keys')
 if not isinstance(keys,list) or not keys or any(not isinstance(k,str) for k in keys) or len(keys)!=len(set(keys)) or not set(keys)<={r['key'] for r in plan['shots']}:raise ValueError('指定镜头范围无效')
 previous=task(graph)
 if previous:
  if previous['breakdown_id']!=args['breakdown_id'] or set(previous['shot_keys'])!=set(keys):raise ValueError('已有制作任务，请先完成当前范围或使用独立测试作品')
  if previous['status']=='failed':previous.update(status='running',error='')
  save_graph(pid,graph);return copy.deepcopy(previous)
 mode=args.get('video_mode','references')
 if mode not in ('references','first_frame'):raise ValueError('视频参考模式无效')
 t={'id':store.uid('production'),'breakdown_id':args['breakdown_id'],'shot_keys':keys,'video_mode':mode,'status':'running','authorized_generation':True,'created_at':store.now(),'events':[],'error':''}
 graph.setdefault('settings',{})['studioMcpProduction']=t;scope(graph);save_graph(pid,graph);return copy.deepcopy(t)

async def advance(pid):
 from .mcp_integration import call_tool,save_graph,get_node
 graph=yaoguang.get_canvas(pid);t=task(graph)
 if not t:raise ValueError('制作任务不存在')
 if t['status']!='running':return t
 try:
  t,rows,allowed=scope(graph)
  # Always settle the real pending jobs before advancing dependent media.
  for n in graph['nodes']:
   if n['id'] in allowed and n.get('studioPendingTask'):
    pending=n['studioPendingTask']
    fresh=yaoguang.get_canvas(pid);current=task(fresh)
    if not any(e.get('task_id')==pending for e in current['events']):
     current['events'].append({'at':store.now(),'stage':'recovered_pending','node_id':n['id'],'task_id':pending});save_graph(pid,fresh)
    result=await call_tool('studio_read_task',{'project_id':pid,'task_id':n['studioPendingTask']})
    if result['status'] in ('failed','cancelled'):raise ValueError(result.get('error') or result['status'])
    if result['status']!='succeeded':return task(yaoguang.get_canvas(pid))
  for r in rows:
   graph=yaoguang.get_canvas(pid)
   state=await call_tool('studio_prepare_shot',{'project_id':pid,'frame_id':r['frame_id']})
   for missing in state['missing_assets']:
    if missing['reason']=='引用断开' or not missing['generate_node_id']:raise ValueError('引用已断开或素材卡已删除，请修复引用')
    await submit(pid,missing['generate_node_id'],'asset');return task(yaoguang.get_canvas(pid))
   if state['next_step']=='generate_frame':await submit(pid,r['frame_id'],'frame');return task(yaoguang.get_canvas(pid))
   if state['next_step']=='repair_video_link':raise ValueError('镜头图到视频的引用断开')
   if state['next_step']=='generate_video':await submit(pid,r['video_id'],'video');return task(yaoguang.get_canvas(pid))
  graph=yaoguang.get_canvas(pid);t=task(graph)
  states=[mcp_workflow.shot_state(graph,get_node(graph,r['frame_id'])) for r in rows]
  t['status']='completed' if all(s['next_step']=='complete' for s in states) else 'needs_review'
  save_graph(pid,graph);return t
 except Exception as e:
  graph=yaoguang.get_canvas(pid);t=task(graph);t.update(status='failed',error=str(e));t['events'].append({'at':store.now(),'stage':'failed','error':str(e)[:2000]});save_graph(pid,graph);return t

async def submit(pid,node_id,stage):
 from .mcp_integration import call_tool,save_graph
 result=await call_tool('studio_generate_media',{'project_id':pid,'node_id':node_id,'confirm_generation':True})
 graph=yaoguang.get_canvas(pid);t=task(graph);t['events'].append({'at':store.now(),'stage':stage,'node_id':node_id,'task_id':result.get('task_id'),'reused':result.get('reused',False)});save_graph(pid,graph)

def launch(pid):
 if pid in RUNNERS and not RUNNERS[pid].done():return
 async def drive():
  from .mcp_integration import LOCKS
  while True:
   async with LOCKS.setdefault(pid,asyncio.Lock()):
    t=await advance(pid)
   if t['status']!='running':break
   await asyncio.sleep(3)
 RUNNERS[pid]=asyncio.create_task(drive())

def recover():
 for p in store.project_summaries():
  try:
   t=task(yaoguang.get_canvas(p['id']))
   if t and t['status']=='running' and t.get('authorized_generation'):launch(p['id'])
  except (ValueError,KeyError):continue

def stop():
 for t in RUNNERS.values():
  if not t.done():t.cancel()

def refresh_review(pid,graph):
 from .mcp_integration import save_graph,get_node
 t=task(graph)
 if not t or t['status'] not in ('needs_review','completed'):return t
 _,rows,allowed=scope(graph);changed=False
 for n in graph['nodes']:
  jid=n.get('studioJobId')
  if n['id'] not in allowed or not jid or any(e.get('task_id')==jid for e in t['events']):continue
  try:job=store.get('jobs',jid)
  except KeyError:continue
  if job['project_id']!=pid or job.get('created_at','')<t['created_at']:continue
  t['events'].append({'at':job['created_at'],'stage':'video' if n.get('studioKind')=='video' else 'frame' if n.get('studioKind')=='shot' else 'asset','node_id':n['id'],'task_id':jid,'recovered':True});changed=True
 states=[mcp_workflow.shot_state(graph,get_node(graph,r['frame_id'])) for r in rows]
 status='completed' if all(s['next_step']=='complete' for s in states) else 'needs_review'
 if status!=t['status']:t['status']=status;changed=True
 if changed:save_graph(pid,graph)
 return t
