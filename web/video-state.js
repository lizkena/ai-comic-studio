import {icon} from './icons.js?v=20261008-all-icons';
export function videoState(segment,job){
 if(job&&['running','queued','waiting_dependency'].includes(job.status))return job.status;
 if(job?.status==='failed')return 'failed';
 return segment.versions?.some(v=>v.id===segment.current_version)?'succeeded':'draft';
}
export function videoBadge(state){
 const busy=['running','queued','waiting_dependency'].includes(state);
 const label={running:'生成中',queued:'排队中',waiting_dependency:'等待衔接',succeeded:'已完成',failed:'失败',draft:'待生成'}[state]||'待生成';
 const mark=state==='succeeded'?icon('circle-check','wf-state-mark'):busy?'<span class="wf-state-spinner" aria-hidden="true"></span>':'';
 return `<span class="wf-video-state ${state}" ${busy?'aria-busy="true"':''}>${mark}${label}</span>`;
}
