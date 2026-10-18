export function createCanvas({state,api,esc,icon,render,toast,dialog,closeDialog,save,navigate,markSaved,loadAssistant,assistantView}){
 let pid=null,loaded=false,counter=0;const waiting=new Map();
 const frame=()=>document.querySelector('#original-canvas-frame');
 function post(data){frame()?.contentWindow?.postMessage({source:'studio-canvas-parent',...data},location.origin);}
 async function flush(){if(!loaded||!frame())return;const request=++counter;return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{waiting.delete(request);reject(Error('画布保存尚未完成，请稍后重试'));},15000);waiting.set(request,{resolve,reject,timer});post({type:'flush',request});});}
 async function open(id){await flush();await save();pid=id;loaded=false;const project=await api(`/projects/${id}/workflow`);state().project=project;state().dirty=false;markSaved(project);state().page='canvas';await loadAssistant();render();}
 function view(){const theme=document.documentElement.dataset.theme==='light'?'light':'dark';return `<main class="yaoguang-canvas-page" data-project="${esc(pid)}"><iframe id="original-canvas-frame" title="无限画布" src="/vendor/yaoguang/smart-canvas.html?id=${encodeURIComponent(pid)}&project=${encodeURIComponent(pid)}&theme=${theme}"></iframe><button class="original-assistant-trigger" data-wb="assistant-toggle" aria-label="打开创作助手" hidden></button><div class="canvas-assistant-overlay"></div></main>`;}
 function updateAssistant(){const page=document.querySelector('.yaoguang-canvas-page');if(page?.dataset.project!==pid)return false;page.querySelector('.canvas-assistant-overlay').innerHTML='';post({type:'theme',theme:document.documentElement.dataset.theme==='light'?'light':'dark'});return true;}
 function afterRender(){loaded=false;}
 function create(){dialog('新建无限画布',`<div class="field"><label for="canvas-name">作品名称</label><input id="canvas-name" value="自由创作短片" maxlength="120"></div><div class="field"><label for="canvas-source">已有文本（可留空）</label><textarea id="canvas-source" placeholder="粘贴剧本或已有分镜"></textarea></div>`,`<button class="primary" data-action="canvas-create">${icon('plus')}创建画布</button>`);}
 async function createProject(){const name=document.querySelector('#canvas-name').value.trim(),source=document.querySelector('#canvas-source').value;const p=await api('/canvas-projects','POST',{name,source,settings:{style:'写实电影'}});if(source.trim()){const graph=await api(`/yaoguang/${p.id}/canvases/${p.id}`);graph.canvas.nodes.push({id:'prompt_initial',type:'smart-prompt',x:180,y:140,w:316,h:260,title:'已有文本',text:source,images:[],llmEnabled:false});await api(`/yaoguang/${p.id}/canvases/${p.id}`,'PUT',{...graph.canvas,base_updated_at:0});}closeDialog();await open(p.id);Object.assign(state(),await api('/projects'));}
 window.addEventListener('message',async event=>{
  if(event.origin!==location.origin||event.source!==frame()?.contentWindow||event.data?.source!=='studio-original-canvas'||event.data.project!==pid)return;
  const data=event.data;
  if(data.type==='ready')loaded=true;
  if(data.type==='scope')state().canvasScope=data.scope;
  if(data.type==='flushed'){const pending=waiting.get(data.request);if(pending){clearTimeout(pending.timer);waiting.delete(data.request);data.error?pending.reject(Error(data.error)):pending.resolve();}}
  if(data.type==='return'){try{await returnProject();}catch(e){toast(e.message,true);}}
  if(data.type==='assistant')document.querySelector('.original-assistant-trigger')?.click();
 });
 async function returnProject(){await navigate('canvas-list');}
 async function refresh(){await flush();state().project=await api(`/projects/${pid}/workflow`);markSaved(state().project);post({type:'refresh'});}
 return {view,afterRender,updateAssistant,open,refresh,create,createProject,flush,poll:async()=>{},beforeAssistant:flush,assistantResult:async()=>{},isDirty:()=>false,returnProject};
}
