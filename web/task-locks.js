import {actionDisplay,labelMarkup} from './action-labels.js?v=20261008-video-labels';
export const ACTIVE=new Set(['queued','running','waiting_dependency']);
const edit=(...writes)=>({reads:[],writes:writes.flat().filter(Boolean)});
export function taskScope(p,j,dependencies=true){
 const reads=new Set(['setup']),writes=new Set(),eps=p.outputs?.script?.episodes||[];
 const object=id=>{const seg=p.segments?.find(x=>x.id===id);if(seg){reads.add('segment:'+id);reads.add('board:'+seg.episode_id);reads.add('episode:'+seg.episode_id);for(const a of [...(seg.character_ids||[]),...(seg.prop_ids||[]),seg.location_id].filter(Boolean))reads.add('asset:'+a);writes.add('segment:'+id);}else{reads.add('asset:'+id);writes.add('asset:'+id);}};
 if(j.stage==='wf_setup'){reads.add('source');reads.add('chapter:*');writes.add('setup');writes.add('asset:*');}
 else if(j.stage==='wf_chapters'&&j.target_id){reads.add('chapter:'+j.target_id);writes.add('chapter:'+j.target_id);for(const ep of eps)if(ep.source_chapters?.includes(j.target_id)||ep.scenes?.some(sc=>sc.source_chapters?.includes(j.target_id)))writes.add('episode:'+ep.id);}
 else if(['wf_story','wf_continue','wf_chapters'].includes(j.stage)){reads.add('source');reads.add('chapter:*');writes.add('chapter:*');}
 else if(j.stage==='wf_script'){reads.add('chapter:'+j.target_id);writes.add('scriptchapter:'+j.target_id);for(const ep of eps)if(ep.source_chapters?.includes(j.target_id)||ep.scenes?.some(sc=>sc.source_chapters?.includes(j.target_id)))writes.add('episode:'+ep.id);}
 else if(j.stage==='wf_breakdown'){reads.add('episode:'+j.target_id);reads.add('asset:*');writes.add('board:'+j.target_id);}
 else if(j.stage==='wf_prompts'){for(const id of j.workflow_options?.target_ids||[])object(id);}
 else if(['image','video','white','polish'].includes(j.kind)||j.stage==='wf_video_prompt'){object(j.target_id);const seg=p.segments?.find(x=>x.id===j.target_id);if(dependencies&&j.kind==='video'&&seg?.continuity&&seg.previous_id)reads.add('segment:'+seg.previous_id);}
 else if(j.kind==='assembly'){for(const seg of p.segments||[])if(!j.target_id||seg.episode_id===j.target_id)reads.add('segment:'+seg.id);writes.add('export:'+(j.target_id||'*'));}
 else {reads.add('source');writes.add('*');}
 return {reads:[...reads],writes:[...writes]};
}
const overlaps=(aa,bb)=>aa.some(a=>bb.some(b=>a===b||a==='*'||b==='*'||a.endsWith(':*')&&b.startsWith(a.slice(0,-1))||b.endsWith(':*')&&a.startsWith(b.slice(0,-1))));
export const conflicts=(a,b)=>overlaps(a.writes,[...b.reads,...b.writes])||overlaps(a.reads,b.writes);
export function blockingTask(p,jobs,scope,videoSubmission=false){return scope&&jobs.find(j=>j.project_id===p.id&&ACTIVE.has(j.status)&&conflicts(scope,taskScope(p,j,!(videoSubmission&&j.kind==='video'))));}
export function bindingScope(p,path){
 const a=path?.split('.')||[];
 if(a[0]==='source')return edit('source');
 if(a[0]==='settings'||a[0]==='outputs'&&['production_setup','direction','characters','world'].includes(a[1]))return edit('setup');
 if(a[0]==='assets')return edit('asset:'+(p.assets?.[a[1]]?.id||'*'));
 if(a[0]==='segments')return edit('segment:'+(p.segments?.[a[1]]?.id||'*'));
 if(a[0]==='outputs'&&a[1]==='novel')return edit('chapter:'+(p.outputs.novel?.chapters?.[a[3]]?.id||'*'));
 if(a[0]==='outputs'&&a[1]==='script')return edit('episode:'+(p.outputs.script?.episodes?.[a[3]]?.id||'*'));
 return null;
}

export function createTaskLocks({project,state,context,toast,describeAction=()=>null}){
 const pending=new Map();let sequence=0;
 const job=(stage,target,options={})=>({kind:'text',stage,target_id:target,workflow_options:options});
 function requested(el){
  const p=project();if(!p)return null;const c=context(),d=el.dataset,name=d.flow||d.action,id=d.id?.split('|')[0],sid=id||c.segment?.id;
  if(d.bind)return bindingScope(p,d.bind);
  const upload=d.flowVoiceUpload||d.flowVoice||d.flowUpload||d.uploadAsset||d.uploadVoice;
  if(upload)return edit((p.assets.some(x=>x.id===upload)?'asset:':'segment:')+upload);
  if(d.flowMode||d.flowDuration||d.versionSegment||d.segmentId)return edit('segment:'+(d.flowMode||d.flowDuration||d.versionSegment||d.segmentId));
  if(el.id==='wf-source-file')return edit('source','chapter:*');
  if(el.id==='video-upload')return edit('segment:'+state().importSegment);
  if(d.wbUpload||d.wbImage)return edit('segment:'+(d.wbUpload||c.segment?.id));
  if(d.wbApply)return edit('*');
  const stages={story:'wf_story',setup:'wf_setup',continue:'wf_continue','chapters-generate':'wf_chapters','outline-one':'wf_chapters','script-one':'wf_script',breakdown:'wf_breakdown','video-prompt':'wf_video_prompt'};
  if(stages[name])return taskScope(p,job(stages[name],id||(name==='breakdown'?c.episode?.id:sid)));
  if(name==='outlines-generate')return combined(c.chapters.filter(x=>c.selected.has(x.id)).map(x=>taskScope(p,job('wf_chapters',x.id))));
  if(name==='scripts-generate')return combined(c.chapters.filter(x=>c.selected.has(x.id)).map(x=>taskScope(p,job('wf_script',x.id))));
  if(name==='prompts'||name==='prompts-one')return taskScope(p,job('wf_prompts',null,{target_ids:name==='prompts-one'?[id]:c.promptObjects.filter(x=>c.selected.has(x.id)).map(x=>x.id)}));
  if(['image-one','image-library','images-generate'].includes(name))return combined((name!=='images-generate'?[id]:c.imageObjects.filter(x=>!c.selected.size||c.selected.has(x.id)).map(x=>x.id)).map(target=>taskScope(p,{kind:'image',target_id:target})));
  if(['video-generate','white','polish-asset'].includes(name))return taskScope(p,{kind:name==='white'?'white':name==='polish-asset'?'polish':'video',target_id:name==='polish-asset'?(id||state().selected):sid},name!=='video-generate');
  if(name==='generate-image')return taskScope(p,{kind:'image',target_id:id});
  if(name==='generate-video')return taskScope(p,{kind:'video',target_id:id},false);
  if(['voice-clear','save-asset','add-variant','clear-voice','remove-reference','sync-characters'].includes(name))return edit('asset:'+(id||'*'));
  if(name==='tail-submit')return edit('segment:'+state().tailSegment);
  if(['chapter-edit','rewrite-chapter'].includes(name))return edit('chapter:'+(id||c.chapters[state().chapter||0]?.id));
  if(name==='script-edit')return edit('episode:'+id);
  if(['shot-asset-add','shot-asset-link','shot-asset-remove','shot-asset-create'].includes(name))return edit('segment:'+id.split('|')[0],'asset:*');
  if(['project-asset-delete','project-asset-delete-confirm'].includes(name))return edit('asset:'+id,p.segments.filter(s=>[...(s.character_ids||[]),...(s.prop_ids||[]),s.location_id].includes(id)).map(s=>'segment:'+s.id));
  if(['setup-edit','setup-save','person-add','person-edit','split-settings','project-settings'].includes(name))return edit('setup');
  if(['chapters-sort','chapter-up','chapter-down','source-append','source-import-append','source-import-replace','source-save','source-use','source-pick','split-local','add-chapter'].includes(name))return edit('source','chapter:*');
  if(['shot-edit','shot-save','dialogue-time','video-more','import-video','video-delete','video-delete-confirm','image-adopt','reference-adopt','asset-edit','manual-tail','tail-submit','accept-white','asset-delete','delete-asset','delete-ref','accept-tail','select-version'].includes(name)||d.asset)return edit((p.assets.some(x=>x.id===(id||d.asset))?'asset:':'segment:')+(id||d.asset||c.segment?.id));
  if(['delete-shots','delete-shots-confirm'].includes(name))return edit(c.segments.filter(x=>c.selected.has(x.id)).map(x=>'segment:'+x.id));
  if(['add-shot','confirm-shots'].includes(name))return edit('board:'+c.episode?.id);
  if(name==='manage-episodes')return edit('episode:*');
  if(['add-episode','episode-create'].includes(name))return edit('episode:*');
  if(['compose','compose-start'].includes(name))return taskScope(p,{kind:'assembly',target_id:c.episode?.id});
  if(['draft-apply','job-apply','job-retry','job-retry-ack'].includes(name)){const j=state().jobs.find(x=>x.id===(id||state().previewJob||state().retryJob));return j?taskScope(p,j):null;}
  if(['author-refine','generate','refine','auto','auto-start','batch-submit','restore','json-save','edit-json','asset-create'].includes(name))return edit('*');
  if(['dialog-save','save-close'].includes(name))return combined([...document.querySelectorAll('dialog [data-bind]')].map(x=>bindingScope(p,x.dataset.bind)).filter(Boolean));
  return null;
 }
 function combined(scopes){return {reads:[...new Set(scopes.flatMap(x=>x.reads))],writes:[...new Set(scopes.flatMap(x=>x.writes))]};}
 function blocker(el){const p=project();if(!p)return null;const binding=el.dataset.bind||'';if(/^(bindings|model_bindings)\./.test(binding)){const key=binding.split('.')[1],kind=key==='video'?'video':key==='image'?'image':'text';return state().jobs.find(j=>j.project_id===p.id&&ACTIVE.has(j.status)&&(j.kind===kind||kind==='text'&&j.kind==='polish'));}const r=normalize(requested(el),el);if(!r)return null;return blockingTask(p,state().jobs,r,['video-generate','generate-video'].includes(el.dataset.flow||el.dataset.action))||[...pending.values()].find(x=>x.project_id===p.id&&conflicts(r,x.scope));}
 function normalize(r,el){if(!r||el.dataset.flow==='video-generate')return r;const reads=new Set(r.reads);if(r.writes.length)reads.add('setup');for(const res of r.writes){if(res.startsWith('segment:')){const seg=project().segments.find(x=>'segment:'+x.id===res);if(seg){reads.add('board:'+seg.episode_id);reads.add('episode:'+seg.episode_id);}}}return {...r,reads:[...reads]};}
 function refresh(){if(!project())return;for(const el of document.querySelectorAll('button[data-flow],button[data-action],button[data-asset],[data-wb-apply],[data-wb-image],input[data-bind],textarea[data-bind],select[data-bind],input[type=file],[data-flow-voice],[data-flow-voice-upload],[data-flow-mode],[data-flow-duration],[data-version-segment],[data-ref],[data-video-text]')){
   if(el.dataset.lockBase===undefined)el.dataset.lockBase=el.disabled?'1':'0';
   if(el.dataset.lockTitle===undefined)el.dataset.lockTitle=el.title||'';
   const info=describeAction(el);
   if(info?.disabled!==undefined)el.dataset.lockBase=info.disabled?'1':'0';
   const blocked=blocker(el),locked=!!blocked;
   const disabled=locked||el.dataset.lockBase==='1'||el.dataset.submitting==='1';
   if(el.dataset.videoText)el.setAttribute('contenteditable',disabled?'false':'plaintext-only');
   if(el.disabled!==disabled)el.disabled=disabled;
   if(el.getAttribute('aria-busy')!==String(locked))el.setAttribute('aria-busy',String(locked));
   const title=locked?'相关任务进行中，完成或停止后可操作':el.dataset.lockTitle;
   if(el.title!==title)el.title=title;
   el.classList.toggle('task-locked',locked);
   if(info){
    if(el.dataset.lockLabel===undefined)el.dataset.lockLabel=el.innerHTML;
    const label=(locked?'<i class="project-task-spinner" aria-hidden="true"></i> ':'')+labelMarkup(el.dataset.lockLabel,actionDisplay(info,blocked));
    if(el.innerHTML!==label)el.innerHTML=label;
   }else if(el.dataset.flow==='breakdown'){
    const ep=el.dataset.id||context().episode?.id,own=state().jobs.find(j=>j.project_id===project().id&&j.stage==='wf_breakdown'&&j.target_id===ep&&ACTIVE.has(j.status));
    const label=own?'<i class="project-task-spinner" aria-hidden="true"></i> '+(own.status==='queued'?'排队中…':'生成中…'):el.dataset.breakdownLabel;
    if(label&&el.innerHTML!==label)el.innerHTML=label;
   }else if(['story','setup','continue','chapters-generate','script-one','scripts-generate','prompts','prompts-one','image-one','images-generate','video-prompt','video-generate'].includes(el.dataset.flow)){
    if(el.dataset.lockLabel===undefined)el.dataset.lockLabel=el.innerHTML;
    const label=locked?'<i class="project-task-spinner" aria-hidden="true"></i> '+(blocked.status==='queued'?'排队中…':blocked.status==='running'?'生成中…':'任务进行中…'):el.dataset.lockLabel;
    if(el.innerHTML!==label)el.innerHTML=label;
   }
  }
 }
 function begin(el){const blocked=blocker(el);if(blocked)throw Error('相关任务进行中，请完成或停止后再操作');const r=normalize(requested(el),el),token=++sequence;if(r)pending.set(token,{...describeAction(el),project_id:project().id,scope:r,status:'submitting'});el.dataset.submitting='1';refresh();return token;}
 function end(token,el){pending.delete(token);if(el?.isConnected){delete el.dataset.submitting;el.disabled=el.dataset.lockBase==='1';}refresh();}
 // Recheck before the app's normal handlers, including controls in an open editor.
 const guard=event=>{const el=event.target.closest('button,input,select,textarea');if(el&&blocker(el)){event.preventDefault();event.stopImmediatePropagation();toast('相关任务进行中，请完成或停止后再操作',true);}};
 document.addEventListener('click',guard,true);document.addEventListener('change',guard,true);document.addEventListener('input',guard,true);
 let scheduled=false;new MutationObserver(()=>{if(!scheduled){scheduled=true;queueMicrotask(()=>{scheduled=false;refresh();});}}).observe(document.body,{childList:true,subtree:true});
 return {refresh,begin,end,blocker};
}
