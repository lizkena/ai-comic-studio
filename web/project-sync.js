const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const object=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
const keyed=x=>Array.isArray(x)&&x.every(v=>object(v)&&typeof v.id==='string')&&new Set(x.map(v=>v.id)).size===x.length;

// Reconcile edits against the last loaded revision, including new generated versions.
export function mergeProject(base,local,remote,choices={}){
 const conflicts=[];
 function merge(b,l,r,path){
  if(equal(l,b))return structuredClone(r);
  if(equal(r,b)||equal(l,r))return structuredClone(l);
  if(object(b)&&object(l)&&object(r)){
   const out={};
   for(const key of new Set([...Object.keys(b),...Object.keys(l),...Object.keys(r)])){
    const value=merge(b[key],l[key],r[key],path?path+'.'+key:key);
    if(value!==undefined)out[key]=value;
   }
   return out;
  }
  if(keyed(b)&&keyed(l)&&keyed(r)){
   const bm=new Map(b.map(v=>[v.id,v])),lm=new Map(l.map(v=>[v.id,v])),rm=new Map(r.map(v=>[v.id,v]));
   const order=equal(l.map(v=>v.id),b.map(v=>v.id))?r:l;
   const other=order===r?l:r;
   return [...new Set([...order,...other,...b].map(v=>v.id))].map(id=>merge(bm.get(id),lm.get(id),rm.get(id),path+'['+id+']')).filter(v=>v!==undefined);
  }
  if(!choices[path])conflicts.push({path,local:l,remote:r});
  return structuredClone(choices[path]==='remote'?r:l);
 }
 const project=merge(base,local,remote,'');
 for(const key of ['revision','updated_at'])project[key]=remote[key];
 return {project,conflicts};
}

export function createProjectSync(ctx){
 const {state,api,render,dialog,closeDialog,toast,esc,icon}=ctx;
 let baseline=null,refreshing=false,pending=null;
 function remember(){const s=state();if(s.project&&!s.dirty&&!refreshing)baseline=structuredClone(s.project);}
 function backup(project){
  const draft={project:structuredClone(project),saved_at:new Date().toISOString()};
  state().refreshDraft=draft;
  try{sessionStorage.setItem('comic-refresh-draft-'+project.id,JSON.stringify(draft));}catch{/* The in-memory backup remains available. */}
 }
 function adopt(project,remote){
  const s=state();s.project=project;baseline=structuredClone(remote);
  s.dirty=!equal(project,remote);s.projects=s.projects.map(x=>x.id===project.id?project:x);
  closeDialog();render();toast(s.dirty?'已刷新，保留的编辑尚未保存':'已刷新为最新内容');
 }
 async function refresh(){
  const s=state();if(!s.project||refreshing)return;
  if(document.querySelector('dialog')?.open){toast('请先完成或关闭当前编辑弹窗，再刷新；编辑内容仍保留',true);return;}
  refreshing=true;const id=s.project.id;
  try{
   const remote=await api('/projects/'+id+'/workflow');
   if(state().project?.id!==id)return;
   const local=structuredClone(state().project);
   if(!state().dirty){adopt(remote,remote);return;}
   backup(local);
   if(!baseline||baseline.id!==id)throw Error('编辑基准不可用，当前编辑已保留，请先导出编辑备份');
   const result=mergeProject(baseline,local,remote);
   if(!result.conflicts.length){adopt(result.project,remote);return;}
   pending={base:structuredClone(baseline),local,remote,conflicts:result.conflicts};
   const display=v=>v===undefined?'（已删除）':typeof v==='string'?v:JSON.stringify(v,null,2);
   dialog('刷新 · 选择要保留的修改',`<p class="help mb">下列内容在后台和当前编辑中都发生了变化。请选择保留哪一份；其他编辑与新生成的素材会自动合并。</p>${result.conflicts.map((c,i)=>`<section class="panel mb"><h3>${esc(c.path)}</h3><div class="grid2 mt"><label class="check"><input type="radio" name="refresh-choice-${i}" value="local">保留我的编辑</label><label class="check"><input type="radio" name="refresh-choice-${i}" value="remote">使用最新内容</label><pre>${esc(display(c.local))}</pre><pre>${esc(display(c.remote))}</pre></div></section>`).join('')}`,`<button data-action="close-dialog">取消，继续编辑</button><button data-action="project-draft-export">${icon('download')}导出编辑备份</button><button class="primary" data-action="project-refresh-apply">应用选择并刷新</button>`,true);
  }finally{refreshing=false;}
 }
 function apply(){
  if(!pending)return;
  const choices={};
  pending.conflicts.forEach((c,i)=>{const value=document.querySelector(`[name="refresh-choice-${i}"]:checked`)?.value;if(!value)throw Error('请为每项冲突选择要保留的内容');choices[c.path]=value;});
  const result=mergeProject(pending.base,pending.local,pending.remote,choices);
  adopt(result.project,pending.remote);pending=null;
 }
 function exportDraft(){
  const draft=state().refreshDraft;if(!draft)throw Error('没有待导出的编辑备份');
  const url=URL.createObjectURL(new Blob([JSON.stringify(draft,null,2)],{type:'application/json'}));
  const a=document.createElement('a');a.href=url;a.download='作品编辑备份-'+draft.project.id+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 }
 return {remember,refresh,apply,exportDraft,busy:()=>refreshing,baseline:()=>baseline?structuredClone(baseline):null,markSaved:project=>{baseline=structuredClone(project);}};
}
