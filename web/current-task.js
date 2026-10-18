export const ACTIVE_TASKS=new Set(['queued','running','waiting_dependency']);
export function taskTime(value){return value?Date.parse(value.replace(' ','T')):NaN;}
export function completedTime(job){
 if(job.completed_at)return taskTime(job.completed_at);
 const log=[...(job.logs||[])].reverse().find(x=>/任务完成|失败|已取消/.test(x.message));
 return taskTime(log?.at||job.updated_at);
}
export function currentTask(jobs,projectId,now=Date.now()){
 const scoped=jobs.filter(j=>j.project_id===projectId);
 const running=scoped.filter(j=>ACTIVE_TASKS.has(j.status)).sort((a,b)=>(taskTime(b.started_at||b.created_at)||0)-(taskTime(a.started_at||a.created_at)||0));
 if(running.length)return {job:running[0],activeCount:running.length};
 const recent=scoped.filter(j=>['succeeded','failed','cancelled'].includes(j.status)&&now-completedTime(j)>=0&&now-completedTime(j)<15000).sort((a,b)=>completedTime(b)-completedTime(a));
 return recent.length?{job:recent[0],activeCount:0}:null;
}
