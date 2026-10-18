const active=new Set(['queued','running','waiting_dependency']);
export function promptState(project,jobs,obj){
 const matching=jobs.filter(j=>j.project_id===project.id&&j.stage==='wf_prompts'&&j.workflow_options?.target_ids?.includes(obj.id));
 const job=matching.find(j=>active.has(j.status))||matching[0];
 if(job&&active.has(job.status))return {key:'running',label:job.status==='queued'?'排队中':'生成中',job};
 if(job?.status==='succeeded'&&job.pending_apply)return {key:'pending',label:'已生成 · 待采用',job};
 if(job?.status==='failed')return {key:'failed',label:obj.image_prompt?'重新生成失败 · 原提示词保留':'生成失败',job};
 if(obj.prompt_stale)return {key:'stale',label:'提示词需更新',job};
 if(obj.image_prompt?.trim())return {key:'ready',label:'提示词已生成',job};
 return {key:'empty',label:job?.status==='cancelled'?'已停止 · 未生成':'提示词未生成',job};
}
