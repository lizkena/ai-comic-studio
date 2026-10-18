import {mergeProject} from './project-sync.js?v=20261006-direct';
const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);

// Serialize writes and preserve edits made while a request is in flight.
export function createProjectAutosave({state,api,baseline,remember,onStatus=()=>{},onError=()=>{},canAutosave=()=>true,schedule=setTimeout,cancel=clearTimeout}){
 let timer=null,flight=null;
 function queue(){cancel(timer);timer=schedule(()=>{if(canAutosave())save().catch(onError);},900);onStatus('pending');}
 async function write(){
  const s=state();if(!s.project||!s.dirty)return s.project;
  const snapshot=structuredClone(s.project),base=baseline()||snapshot;
  onStatus('saving');let saved;
  try{saved=await api('/projects/'+snapshot.id,'PUT',snapshot);}
  catch(error){
   if(!/刷新|已有更新/.test(error.message))throw error;
   const remote=await api('/projects/'+snapshot.id+'/workflow');
   const merged=mergeProject(base,snapshot,remote);
   if(merged.conflicts.length)throw Error('自动保存遇到内容冲突，编辑已保留，请刷新并选择要保留的内容');
   saved=await api('/projects/'+snapshot.id,'PUT',merged.project);
  }
  // Navigation may have selected another project while the network was busy.
  if(state().project?.id!==snapshot.id)return saved;
  const merged=mergeProject(snapshot,state().project,saved);
  state().project=merged.project;state().dirty=!equal(merged.project,saved);
  state().projects=state().projects.map(p=>p.id===snapshot.id?merged.project:p);
  remember(saved);onStatus(state().dirty?'pending':'saved');
  return saved;
 }
 async function save(){
  cancel(timer);
  if(flight){await flight;return state().dirty?save():state().project;}
  if(!state().project||!state().dirty)return state().project;
  flight=write();try{await flight;}catch(error){onStatus('error');throw error;}finally{flight=null;}
  // Flush edits made during this write before an explicit generation/navigation.
  return state().dirty?save():state().project;
 }
 return {queue,save,busy:()=>!!flight};
}
