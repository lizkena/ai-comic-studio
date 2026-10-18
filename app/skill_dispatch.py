"""Content-aware, opt-in professional instruction modules; never execute their tools."""
import copy,json,re
from . import store
VERSION='skill-dispatch-v1'
KINDS={'shot_prompt','video_prompt','breakdown','scene_prompt','character_prompt','general'}

def keyword_match(request, words):
 # Negative mentions must not activate optional modules (e.g. “不要打斗”).
 text=request.lower()
 for word in words:
  word=word.lower()
  positive=re.sub(r'(?:没有|不要|不需要|无需|不含|无|非)\s*'+re.escape(word),'',text)
  if word in positive:return True
 return False
def modules():
 rows=[]
 for path in sorted((store.ROOT/'skill_modules').glob('*/adapter.json')):
  row=json.loads(path.read_text(encoding='utf-8'));row['folder']=path.parent
  rows.append(row)
 return rows
def set_enabled(ident,enabled):
 if not isinstance(enabled,bool):raise ValueError('启用状态必须为布尔值')
 m=next((m for m in modules() if m['id']==ident),None)
 if not m:raise ValueError('找不到专业补充技能')
 folder=m.pop('folder');m['enabled']=enabled
 path=folder/'adapter.json';temp=folder/'adapter.json.tmp'
 temp.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)
 return {'id':ident,'enabled':enabled}
def task(p,payload):
 stage=payload.get('stage','');options=payload.get('workflow_options',{})
 if stage=='wf_breakdown':return 'breakdown','剧本拆分任务'
 if stage=='wf_video_prompt' or options.get('canvas_task')=='video_prompt':return 'video_prompt','视频提示词整理任务'
 if stage=='wf_prompts':
  ids=options.get('target_ids') or [payload.get('target_id')]
  if any(n['id'] in ids for n in p.get('segments',[])):return 'shot_prompt','选中了镜头提示词目标'
  targets=[a for a in p.get('assets',[]) if a['id'] in ids]
  if targets and all(a['kind']=='location' for a in targets):return 'scene_prompt','选中了场景提示词目标'
  return 'character_prompt','资产提示词任务，保留资产专用规则'
 if stage=='wf_canvas_text':
  # Use the selected card rather than unrelated project/story keywords.
  from .yaoguang import get_canvas
  node=next((n for n in get_canvas(p['id'])['nodes'] if n['id']==options.get('canvas_node_id')),None)
  if node:
   role=node.get('studioKind')
   if role=='character':return 'character_prompt','选中角色或身份卡'
   if role=='location':return 'scene_prompt','选中场景卡'
   if role in ('shot','txt2img','image'):return 'shot_prompt','选中镜头或图片卡'
  request=str(options.get('canvas_user_request') or options.get('canvas_message') or payload.get('instruction','')).lower()
  if any(w in request for w in ('分镜','运镜','镜头提示词','storyboard','camera movement')):return 'shot_prompt','当前请求涉及分镜或运镜'
 return 'general','未匹配专业任务'
def resolve(base,p,payload):
 out=copy.deepcopy(base)
 if payload.get('kind')!='text' or p.get('settings',{}).get('skills_auto_dispatch') is False:return out
 kind,reason=task(p,payload);disabled=set(p.get('settings',{}).get('disabled_skill_modules',[]))
 options=payload.get('workflow_options',{})
 request=str(payload.get('instruction',''))+' '+str(options.get('canvas_message',''))+' '+str(options.get('canvas_user_request',''))
 if payload.get('stage') in ('wf_breakdown','wf_prompts','wf_video_prompt'):
  from . import workflow
  context=workflow.context(copy.deepcopy(p),payload['stage'],payload.get('target_id'),payload.get('workflow_options',{}))
  scoped={k:v for k,v in context.items() if k not in ('settings','setup','assets','source_storyboard')}
  request+=' '+json.dumps(scoped,ensure_ascii=False)
 selected=[]
 for m in modules():
  if not m.get('enabled') or m['id'] in disabled or base['stage'] not in m.get('stages',[]) or kind not in m.get('task_types',[]):continue
  words=m.get('keywords',[])
  if words and not keyword_match(request,words):continue
  selected.append(m)
 selected=sorted(selected,key=lambda m:(-m.get('priority',0),m['id']))[:2]
 content=[];routing=[]
 for m in selected:
  docs=[]
  refs=list(m.get('references',{}).get(kind,[]))
  for rule in m.get('reference_rules',[]):
   if kind in rule.get('task_types',[]) and keyword_match(request,rule.get('keywords',[])):
    refs.extend(rule.get('files',[]))
  refs=list(dict.fromkeys(refs))
  for name in ['SKILL.md',*refs]:
   path=(m['folder']/name).resolve()
   if not path.is_relative_to(m['folder'].resolve()) or path.suffix!='.md':raise ValueError('技能引用文件必须是模块内的 Markdown')
   docs.append(path.read_text(encoding='utf-8')[:18000])
  content.append('\n\n专业补充模块 '+m['name']+'：\n'+'\n'.join(docs))
  routing.append({'id':m['id'],'name':m['name'],'version':m['version'],'task_type':kind,'reason':reason,'references':refs})
 if routing:
  boundary='补充技能仅提供本任务的专业方法，不改变用户事实、项目风格、卡片用途、平台输出JSON、参考职责、资产视图布局和制作范围；不调用技能自带脚本或推荐渠道。没有实际查看媒体不得宣称已验收。文档模板中的年代、人物、色名、颗粒或污迹不得作为本项目默认设定。'
  out['content']+='\n'+boundary+''.join(content)+'\n'+boundary
  out['auto_dispatch']={'version':VERSION,'modules':routing}
 return out
