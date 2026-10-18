"""Canvas production contracts shared by external MCP clients; no implicit paid calls."""
import copy
import json
import math
from . import store, yaoguang

GUIDE = '''漫剧平台制作流程（所有 MCP 客户端共用）
先列出项目、读取画布，再调用 studio_get_workflow。用户要完整制作时，优先使用流程工具，不要只创建文本卡后直接文生视频。
1. 剧本：保持场次、人物、台词和剧情事实。已有定稿直接复用；先明确本次制作范围。写剧本前调用 studio_get_creation_skill(stage=script)，拆分前读取 storyboard 和 assets 阶段技能，遵循项目实际绑定的方法，不凭空猜平台规则。
2. 拆分：由你理解剧本，按 studio_apply_breakdown 的结构整理资产与分镜。每镜写清动作、景别、站位、时长、台词、图像和视频提示词。只列出出镜资产；人物、场景和道具分开。角色身份描述服装和状态，默认身份复用来源角色图。不同身份必须属于同一个根角色。
3. 落画布：studio_apply_breakdown 一次建立分镜总表、根角色、身份、场景、道具、镜头图和视频卡，并建立引用。用稳定的 breakdown_id；重试同一内容不会重复建卡，内容改变请用新ID。
4. 先检查 studio_get_workflow 的 missing_assets。已有素材复用；缺少的根角色、场景、道具先生成，等待 studio_read_task 真正成功，再处理身份。默认身份无需重复生图。
5. 镜头：studio_prepare_shot 检查引用，返回镜头图ID、视频ID、缺失素材与下一步。先生成镜头图片，再生成视频。图片引用的是本镜头身份、场景、道具；视频沿用镜头图片和这些资产。禁止绕过缺失参考素材。
6. 完整制作：用户明确要求实际生成后，调用 studio_start_production(breakdown_id,shot_keys,confirm_generation=true)，平台后台自动推进资产→镜头图→视频。通过 studio_read_production 查看进度；失败先修正原因，再以同一范围重新启动。禁止用普通视频卡绕过完整任务。单卡自由创作才使用 studio_generate_media。只执行用户指定镜头，不擅自扩大范围。
7. 验收：读取真实图片/视频，检查人物、服装、场景、站位、动作、时长与原剧情。studio_record_review 只记录你实际观察的结果，没有观看不得填 passed。流程报告有成品不代表效果合格。
遇到失败记录原因，修正对应提示词或引用。禁止读取API密钥、伪造结果、用文字声称代替媒体。
'''

ASSET = {'type':'object','additionalProperties':False,'required':['key','kind','name','prompt'],'properties':{
 'key':{'type':'string'},'kind':{'type':'string','enum':['character','identity','location','prop']},'name':{'type':'string'},'prompt':{'type':'string'},'parent_key':{'type':'string'},'default':{'type':'boolean'}}}
SHOT = {'type':'object','additionalProperties':False,'required':['key','title','text','image_prompt','video_prompt','duration','asset_keys'],'properties':{
 'key':{'type':'string'},'title':{'type':'string'},'text':{'type':'string'},'image_prompt':{'type':'string'},'video_prompt':{'type':'string'},'duration':{'type':'number','minimum':1,'maximum':120},'asset_keys':{'type':'array','items':{'type':'string'},'minItems':1},'ratio':{'type':'string','enum':['16:9','9:16','1:1','4:3','3:4','21:9']}}}

def text(value,label,maxlen=10000):
 if not isinstance(value,str) or not value.strip() or len(value)>maxlen:raise ValueError(label+'不能为空或过长')
 return value.strip()

def apply_breakdown(pid,graph,args):
 """Validate the whole plan before a single CAS write; reuse existing named assets."""
 from .mcp_integration import save_graph
 ident=text(args['breakdown_id'],'拆分ID',100)
 source=next((n for n in graph['nodes'] if n['id']==args['source_node_id']),None)
 if not source or source.get('studioKind')!='text' or not source.get('text','').strip():raise ValueError('请提供已有剧本文本卡')
 assets=args['assets'];shots=args['shots']
 if not isinstance(assets,list) or not 1<=len(assets)<=150 or not isinstance(shots,list) or not 1<=len(shots)<=100:raise ValueError('资产或分镜数量无效')
 fingerprint=json.dumps({'source':source['id'],'source_text':source['text'],'assets':assets,'shots':shots},sort_keys=True,ensure_ascii=False)
 import hashlib
 digest=hashlib.sha256(fingerprint.encode()).hexdigest()
 registry=graph.setdefault('settings',{}).setdefault('studioMcpBreakdowns',{})
 if ident in registry:
  previous=registry[ident]
  if previous['digest']!=digest:raise ValueError('该拆分ID已有不同内容，请使用新ID')
  present={n['id'] for n in graph['nodes']}
  if any(n not in present for n in previous['node_ids']):raise ValueError('已有拆分的卡片被删除，请使用新ID重新整理')
  return {**previous,'reused':True}
 bykey={}
 for a in assets:
  if not isinstance(a,dict) or set(a)-set(ASSET['properties']):raise ValueError('资产字段无效')
  key=text(a.get('key'),'资产key',100)
  if key in bykey:raise ValueError('资产key重复')
  if a.get('kind') not in ('character','identity','location','prop'):raise ValueError('资产类型无效')
  text(a.get('name'),'资产名称',120);text(a.get('prompt'),'资产提示词')
  if 'default' in a and not isinstance(a['default'],bool):raise ValueError('默认身份标记无效')
  bykey[key]=a
 for a in assets:
  if a['kind']=='identity' and bykey.get(a.get('parent_key'),{}).get('kind')!='character':raise ValueError('身份必须引用本次拆分中的根角色')
 for key in bykey:
  defaults=[a for a in assets if a['kind']=='identity' and a.get('parent_key')==key and a.get('default')]
  if len(defaults)>1:raise ValueError('同一角色只能有一个默认身份')
 seen=set()
 for s in shots:
  if not isinstance(s,dict) or set(s)-set(SHOT['properties']):raise ValueError('镜头字段无效')
  key=text(s.get('key'),'镜头key',100)
  if key in seen:raise ValueError('镜头key重复')
  seen.add(key)
  for k in ('title','text','image_prompt','video_prompt'):text(s.get(k),'镜头'+k,120 if k=='title' else 10000)
  d=s.get('duration')
  if isinstance(d,bool) or not isinstance(d,(float,int)) or not math.isfinite(d) or not 1<=d<=120:raise ValueError('镜头时长无效')
  keys=s.get('asset_keys')
  if not isinstance(keys,list) or not keys or any(not isinstance(k,str) or k not in bykey for k in keys) or len(keys)!=len(set(keys)):raise ValueError('镜头引用资产无效')
  if not any(bykey[k]['kind']=='location' for k in keys):raise ValueError('每镜必须引用场景')
  roots=[]
  for k in keys:
   a=bykey[k]
   if a['kind'] in ('character','identity'):roots.append(a.get('parent_key') if a['kind']=='identity' else k)
  if len(roots)!=len(set(roots)):raise ValueError('同一镜头不能引用同一角色多套身份')
  if s.get('ratio','16:9') not in ('16:9','9:16','1:1','4:3','3:4','21:9'):raise ValueError('画面比例无效')
 unused=set(bykey)-{k for s in shots for k in s['asset_keys']}-{bykey[k].get('parent_key') for s in shots for k in s['asset_keys'] if bykey[k]['kind']=='identity'}
 if unused:raise ValueError('包含未出镜资产：'+','.join(sorted(unused)))
 mapping={};created=[];reused=[];base_x=max((n['x'] for n in graph['nodes']),default=0)+500
 def make(kind,title,prompt='',content='',x=0,y=0):
  n={'id':store.uid('mcp'),'type':'smart-prompt' if kind=='text' else 'smart-image','studioKind':kind,'title':title,'text':content,'studioPrompt':prompt,'studioImagePurpose':kind if kind in ('character','location','prop') else 'shot','images':[],'x':base_x+x,'y':y,'w':360,'h':520,'studioRatio':'16:9','studioDuration':8}
  if kind=='text':n['llmEnabled']=False
  graph['nodes'].append(n);created.append(n['id']);return n
 def connect(a,b):
  if not any(e['from']==a['id'] and e['to']==b['id'] for e in graph['connections']):graph['connections'].append({'from':a['id'],'to':b['id'],'kind':'input'})
 def asset_node(a,parent=None):
  existing=next((n for n in graph['nodes'] if n.get('studioKind')==('character' if parent else a['kind']) and (n.get('studioIdentityParentId')==parent['id'] and (n.get('studioIdentityDefault') if a.get('default') else n.get('studioIdentityName')==a['name']) if parent else not n.get('studioIdentityParentId') and (n.get('studioCharacter') or n.get('title'))==a['name'])),None)
  if existing:reused.append(existing['id']);return existing
  n=make('character' if parent else a['kind'],parent['title']+' · '+a['name'] if parent else a['name'],a['prompt'],y=len(mapping)*650)
  if a['kind']=='character':n['studioCharacter']=a['name']
  if parent:
   n.update(studioIdentityParentId=parent['id'],studioIdentityRootId=parent['id'],studioCharacter=parent.get('studioCharacter') or parent['title'],studioIdentityName=a['name'],studioIdentityDefault=a.get('default',False))
   if a.get('default'):n['studioPrompt']='';n['images']=copy.deepcopy(parent.get('images',[]))
   connect(parent,n)
  return n
 for a in assets:
  if a['kind']!='identity':mapping[a['key']]=asset_node(a)
 for a in assets:
  if a['kind']=='identity':mapping[a['key']]=asset_node(a,mapping[a['parent_key']])
 # Every root gets a default identity even when the supplied shot uses another costume.
 for a in assets:
  if a['kind']=='character':
   root=mapping[a['key']];default=asset_node({'kind':'identity','name':'默认身份','prompt':a['prompt'],'default':True},root)
   mapping[a['key']]=default
 table=make('text','分镜总表 · '+source['title'],content=json.dumps({'assets':assets,'shots':shots},ensure_ascii=False,indent=2),x=500)
 table['studioMcpBreakdownId']=ident;connect(source,table)
 shot_rows=[]
 for i,s in enumerate(shots):
  frame=make('shot',s['title']+' · 镜头图',s['image_prompt'],s['text'],x=1000,y=i*650)
  video=make('video',s['title']+' · 视频',s['video_prompt'],s['text'],x=1500,y=i*650)
  for n in (frame,video):n.update(studioDuration=s['duration'],studioRatio=s.get('ratio','16:9'),studioMcpBreakdownId=ident,studioMcpShotKey=s['key'])
  frame['studioMcpAssetIds']=[mapping[k]['id'] for k in s['asset_keys']];video['studioMcpFrameId']=frame['id']
  for k in s['asset_keys']:connect(mapping[k],frame)
  connect(frame,video)
  shot_rows.append({'key':s['key'],'frame_id':frame['id'],'video_id':video['id']})
 result={'digest':digest,'source_node_id':source['id'],'table_id':table['id'],'node_ids':list(dict.fromkeys(created+reused)),'shots':shot_rows,'created':created,'reused_assets':list(dict.fromkeys(reused))}
 registry[ident]=result;save_graph(pid,graph);return result

def ready_asset(graph,n):
 if n.get('images'):return True
 if n.get('studioIdentityDefault'):
  parent=next((x for x in graph['nodes'] if x['id']==n.get('studioIdentityParentId')),None)
  return bool(parent and parent.get('images'))
 return False

def shot_state(graph,frame):
 byid={n['id']:n for n in graph['nodes']};video=next((n for n in graph['nodes'] if n.get('studioMcpFrameId')==frame['id']),None)
 expected=frame.get('studioMcpAssetIds',[]);missing=[]
 for ident in expected:
  n=byid.get(ident)
  linked=any(e['from']==ident and e['to']==frame['id'] for e in graph['connections'])
  if not n or not linked or not ready_asset(graph,n):
   parent=byid.get(n.get('studioIdentityParentId')) if n else None
   generate=parent if parent and (n.get('studioIdentityDefault') or not ready_asset(graph,parent)) else n
   missing.append({'node_id':ident,'title':n.get('title') if n else '已删除资产','reason':'引用断开' if n and not linked else '素材缺失','generate_node_id':generate['id'] if generate else None,'task_id':generate.get('studioPendingTask') if generate else None})
 video_linked=bool(video and any(e['from']==frame['id'] and e['to']==video['id'] for e in graph['connections']))
 pending=[{'node_id':n['id'],'task_id':n['studioPendingTask']} for n in (frame,video) if n and n.get('studioPendingTask')]
 review=video.get('studioMcpReview') if video else None
 if review and review.get('media_urls')!=[m['url'] for m in video.get('images',[])]:review=None
 next_step='read_task' if pending or any(m['task_id'] for m in missing) else 'prepare_assets' if missing else 'generate_frame' if not frame.get('images') else 'repair_video_link' if not video_linked else 'generate_video' if not video.get('images') else 'complete' if review and review['verdict']=='passed' else 'revise_media' if review else 'review_media'
 return {'key':frame.get('studioMcpShotKey'),'frame_id':frame['id'],'video_id':video['id'] if video else None,'missing_assets':missing,'pending_tasks':pending,'next_step':next_step,'review':review}

def workflow_state(graph):
 return {'guide':GUIDE,'breakdowns':list(graph.get('settings',{}).get('studioMcpBreakdowns',{})),'shots':[shot_state(graph,n) for n in graph['nodes'] if n.get('studioKind')=='shot' and n.get('studioMcpShotKey')],
 'next_step_if_no_breakdown':'选择剧本文本卡，按流程契约分析并调用 studio_apply_breakdown；仅落卡不调用付费模型。','acceptance_checklist':['人物与身份','场景与道具','站位与构图','动作与剧情','台词与时长']}

def prepare_shot(pid,graph,node_id):
 from .mcp_integration import save_graph
 frame=next((n for n in graph['nodes'] if n['id']==node_id and n.get('studioMcpAssetIds')),None)
 if not frame:raise ValueError('请提供流程拆分建立的镜头图ID')
 changed=False
 for n in graph['nodes']:
  if n['id'] in frame['studioMcpAssetIds'] and n.get('studioIdentityDefault') and not n.get('images'):
   parent=next((x for x in graph['nodes'] if x['id']==n.get('studioIdentityParentId')),None)
   if parent and parent.get('images'):n['images']=copy.deepcopy(parent['images']);changed=True
 if changed:save_graph(pid,graph)
 return shot_state(graph,frame)
