export async function submitAgentAction(api, project, payload) {
  const topic=localStorage.getItem('comic-assistant-topic-'+project.id)||'main';
  const requestId=crypto.randomUUID();
  const emit=(phase,extra={})=>window.dispatchEvent(new CustomEvent('studio-agent-action',{detail:{projectId:project.id,requestId,phase,...extra}}));
  emit('start');
  try {
    const result=await api(`/projects/${project.id}/assistant/actions`,'POST',{...payload,revision:project.revision,request_id:requestId,topic_id:topic});
    emit('result',{message:result.message});
    if(!result.job)throw Error(result.message?.reply||'助手没有提交制作任务，请查看对话记录');
    return result.job;
  } finally {
    emit('end');
  }
}
