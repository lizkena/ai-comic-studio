"""Opt-in project quality checkpoint: one explicitly released model job at a time."""
import json
import time
from . import store


def setup(c):
    c.execute('CREATE TABLE IF NOT EXISTS generation_supervision(project_id TEXT PRIMARY KEY, body TEXT NOT NULL)')


def load(c, pid):
    setup(c)
    row=c.execute('SELECT body FROM generation_supervision WHERE project_id=?',(pid,)).fetchone()
    return json.loads(row['body']) if row else None


def save(c, pid, value):
    c.execute('INSERT INTO generation_supervision(project_id,body) VALUES(?,?) ON CONFLICT(project_id) DO UPDATE SET body=excluded.body',(pid,json.dumps(value,ensure_ascii=False)))


def status(pid):
    with store.db() as c:
        return load(c,pid)


def enabled(pid):
    value=status(pid)
    return bool(value and value.get('enabled'))


def enable(pid):
    store.get('projects',pid)
    with store.db() as c:
        old=load(c,pid)
        if old and old.get('enabled'):return old
        value={'enabled':True,'state':'awaiting_approval','permit':None,'history':[]}
        save(c,pid,value)
        return value


def permit(pid,node_id,kind):
    if kind not in ('text','image','video','polish','white'):raise ValueError('Unsupported generation kind')
    if not isinstance(node_id,str) or not node_id:raise ValueError('Specify the exact node id')
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        value=load(c,pid)
        if not value or not value.get('enabled'):raise ValueError('Enable supervision first')
        if value.get('state')=='awaiting_review':raise ValueError('Review the previous attempt before releasing another')
        if value.get('permit'):raise ValueError('An unused permit already exists')
        active=c.execute("SELECT id FROM jobs WHERE json_extract(body,'$.project_id')=? AND json_extract(body,'$.status') IN ('queued','running','waiting_dependency') LIMIT 1",(pid,)).fetchone()
        if active:raise ValueError('Project already has a running generation')
        approval={'node_id':node_id,'kind':kind,'nonce':store.uid('release'),'expires_at':time.time()+900}
        value.update(state='released',permit=approval)
        save(c,pid,value)
        return approval


def claim(project,payload,job):
    """Called under jobs.submission_lock, immediately before saving a new job."""
    pid=project['id']
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        value=load(c,pid)
        if not value or not value.get('enabled') or job['kind']=='assembly':return
        if payload.get('auto'):raise ValueError('逐项监督项目禁止自动生成链；请等待逐项放行')
        node_id=payload.get('workflow_options',{}).get('canvas_node_id')
        if not node_id:
            target=next((s for s in project.get('segments',[]) if s.get('id')==job.get('target_id')),None)
            node_id=(target or {}).get('canvas_node_id') or job.get('target_id')
        approval=value.get('permit')
        if not approval or approval['expires_at']<time.time() or approval['node_id']!=node_id or approval['kind']!=job['kind']:
            raise ValueError('本项目采用逐项监督：当前生成未获放行，请先报告内容并等待检查；不要重复提交或绕过')
        value['history'].append({'at':store.now(),'node_id':node_id,'kind':job['kind'],'job_id':job['id'],'release':approval['nonce'],'review':None})
        value.update(permit=None,state='awaiting_review')
        save(c,pid,value)


def review(pid,job_id,verdict,observations):
    if verdict not in ('passed','needs_revision','failed'):raise ValueError('Invalid review verdict')
    if not observations.strip():raise ValueError('Actual observations required')
    job=store.get('jobs',job_id)
    if job['project_id']!=pid or job['status'] in ('queued','running','waiting_dependency'):raise ValueError('Wait for this project job to finish')
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        value=load(c,pid)
        if not value or not value['history'] or value['history'][-1]['job_id']!=job_id:raise ValueError('Review must match the latest released attempt')
        value['history'][-1]['review']={'at':store.now(),'verdict':verdict,'observations':observations}
        value.update(state='awaiting_approval',permit=None)
        save(c,pid,value)
        return value
