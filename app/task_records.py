"""Persistent per-project execution records; completed generation != adopted draft."""
from . import store, jobs, domain

LABELS={'wf_story':'灵感生成故事','wf_setup':'分析剧本设定','wf_continue':'续写章节',
    'wf_chapters':'章节拆分与大纲','wf_script':'生成章节剧本','wf_breakdown':'拆分剧本与资产',
    'wf_prompts':'生图与视频提示词','wf_video_prompt':'完善视频提示词',
    **{stage:label for stage,label,_ in domain.STAGES}}
KINDS={'text':'文字生成','polish':'资产描述润色','image':'图片生成','video':'视频生成','white':'白模生成','assembly':'成片导出'}
ACTIVE={'queued','running','waiting_dependency'}


def listing(ident, limit=None, offset=0, status='all', stage='all', query=''):
    p, labels=store.project_overview(ident)
    records=[]
    for job in store.job_rows(project_id=ident):
        row=jobs.public(job)
        selected_ids=job.get('workflow_options',{}).get('target_ids',[]) if job.get('stage')=='wf_prompts' else []
        target_id=job.get('target_id') or (selected_ids[0] if len(selected_ids)==1 else None)
        target_label=labels.get(target_id) or job.get('target_label_snapshot')
        logs=job.get('logs',[])
        # Older records can identify a logged finish; never present last edit as finish.
        started=job.get('started_at') if 'started_at' in job else next((x['at'] for x in reversed(logs) if x.get('message')=='开始执行'),None)
        finished=job.get('completed_at')
        if not finished and job['status'] not in ACTIVE:
            finished=next((x['at'] for x in reversed(logs) if x.get('message') in ('任务完成','用户停止任务') or x.get('message','').startswith('已停止本地处理')),None)
        row['pending_apply']=bool(job.get('pending_apply') and job['status']=='succeeded')
        applied=job.get('applied_by_user') or any(x.get('message')=='用户已应用改稿' for x in logs)
        adoption='待采用' if row['pending_apply'] else '已放弃建议' if job.get('discarded') else '已自动更新' if job.get('applied_automatically') else '已采用' if applied else ''
        row.update(stage_label=LABELS.get(job['stage'],job['stage']),kind_label=KINDS.get(job['kind'],job['kind']),
            target_label=('所选 ' + str(len(selected_ids)) + ' 个目标') if len(selected_ids)>1 else target_label or ('原目标已移除' if target_id else '整个作品'),
            execution_started_at=started,execution_completed_at=finished,adoption=adoption)
        records.append(row)
    records.sort(key=lambda j:(j.get('created_at',''),j['id']),reverse=True)
    stages=list(dict.fromkeys((j['stage'],j['stage_label']) for j in records))
    needle=query.casefold().strip()
    matching=[j for j in records if
        (status=='all' or status=='active' and j['status'] in ACTIVE or status=='pending' and j.get('pending_apply') or j['status']==status)
        and (stage=='all' or j['stage']==stage)
        and (not needle or needle in ' '.join(str(j.get(k) or '') for k in ('id','target_label','stage_label','kind_label','model')).casefold())]
    return {'project_id':ident,'project_name':p['name'],'tasks':matching[offset:offset+limit] if limit is not None else matching,
        'counts':store.job_counts(ident), 'stages':stages, 'matching_total':len(matching), 'offset':offset, 'limit':limit}
