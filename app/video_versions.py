"""Remove a storyboard video version without destroying shots or shared media."""
import copy
from fastapi import APIRouter
from . import store,domain,task_locks
router=APIRouter(prefix='/api/projects')
def remove(project_id,segment_id,version_id,revision):
    p=store.get('projects',project_id)
    if revision is None or p['revision']!=revision:raise ValueError('作品已更新，请刷新后再删除视频')
    s=next((s for s in p['segments'] if s['id']==segment_id),None)
    if not s:raise ValueError('分镜不存在')
    v=next((v for v in s.get('versions',[]) if v['id']==version_id),None)
    if not v:raise ValueError('视频版本不存在或已经删除')
    for j in store.job_rows(project_id=project_id, statuses=store.ACTIVE_JOBS, full=True):
        if j.get('project_id')!=project_id or j['status'] not in ('queued','running','waiting_dependency'):continue
        if j.get('target_id')==segment_id and j['kind']=='video':raise ValueError('这个分镜正在生成视频，请完成或停止任务后再删除')
        if any(r.get('source_version')==version_id for r in j.get('input_bundle',{}).get('references',[])):raise ValueError('这个版本正在用于镜头衔接，请等待当前任务完成')
        target=next((x for x in p['segments'] if x['id']==j.get('target_id')),None)
        if s.get('current_version')==version_id and target and target.get('continuity') and target.get('previous_id')==segment_id and j['kind']=='video':raise ValueError('这个版本正在被连续任务使用，请等待当前任务完成')
    task_locks.assert_available(p, {'reads':set(), 'writes':{'segment:'+segment_id}})
    s.setdefault('deleted_versions',[]).append({**copy.deepcopy(v),'deleted_at':store.now()})
    s['versions']=[x for x in s['versions'] if x['id']!=version_id]
    if s.get('current_version')==version_id:
        s.update(current_version=None,status='draft',trim_start=0,trim_end=None)
        domain.stale_dependents(p,segment_id)
    return store.save_project(p,revision,'删除分镜视频版本：'+s['title']+'；保留素材与历史以便恢复')

@router.post('/{project_id}/segments/{segment_id}/videos/{version_id}/delete')
def delete_version(project_id,segment_id,version_id,payload:dict):
    return remove(project_id,segment_id,version_id,payload.get('revision'))
