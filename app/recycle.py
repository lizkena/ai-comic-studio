"""Reversible project removal and explicitly confirmed cleanup of exclusive media."""
import json
from urllib.parse import unquote
from pathlib import Path
from fastapi import APIRouter
from . import store

router = APIRouter(prefix='/api/recycle-bin')
ACTIVE = {'queued', 'running', 'waiting_dependency'}


def load(c, ident):
    row = c.execute('SELECT body FROM projects WHERE id=?', (ident,)).fetchone()
    if not row: raise KeyError(ident)
    return json.loads(row['body'])


def assert_idle(c, ident):
    if c.execute("SELECT 1 FROM job_summaries WHERE project_id=? AND status IN ('queued','running','waiting_dependency') LIMIT 1", (ident,)).fetchone():
        raise ValueError('该作品有排队或执行中的任务，请先在任务队列停止任务后再删除。')


def change(ident, deleted, revision=None):
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        p = load(c, ident)
        if bool(p.get('deleted_at')) == deleted: return p
        if revision is not None and p['revision'] != revision: raise ValueError('作品已有更新，请刷新后重试')
        assert_idle(c, ident)
        c.execute('INSERT INTO revisions VALUES(?,?,?)', (store.uid('rev'), ident, json.dumps({'at':store.now(), 'reason':'移入回收站' if deleted else '恢复作品', 'project':p}, ensure_ascii=False)))
        p['deleted_at'] = store.now() if deleted else None
        p['revision'] += 1; p['updated_at'] = store.now()
        c.execute('UPDATE projects SET body=? WHERE id=?', (json.dumps(p, ensure_ascii=False), ident))
        store.sync_summary(c, 'projects', p)
        return p


@router.get('')
def listing():
    return [{'id': p['id'], 'name':p['name'], 'deleted_at':p['deleted_at'], 'revision':p['revision'],
             'settings':p['settings'], 'segment_count':p['segment_count']}
            for p in sorted(store.project_summaries(deleted=True), key=lambda x:x.get('deleted_at') or '', reverse=True)]


@router.post('/{ident}/restore')
def restore(ident, payload:dict):
    project = change(ident, False, payload.get('revision'))
    return store.project_summary(project) if payload.get('summary') else project


def media_paths(value):
    result = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key=='url' and isinstance(item,str) and item.startswith('/media/'):
                result.update(media_paths({'file':unquote(item[7:])}))
            if key in ('file', 'tail', 'white', 'voice', 'thumbnail', 'cover') and isinstance(item, str) and not item.startswith(('http://', 'https://', 'data:')):
                candidate = (store.MEDIA / item).resolve()
                if candidate.is_relative_to(store.MEDIA.resolve()) and candidate.is_file(): result.add(candidate)
            result.update(media_paths(item))
    elif isinstance(value, list):
        for item in value: result.update(media_paths(item))
    return result


def purge(ids, confirm, revisions=None):
    if confirm is not True: raise ValueError('永久删除需要明确确认，删除后无法恢复')
    if not isinstance(ids, list) or not ids or any(not isinstance(i, str) for i in ids) or len(set(ids)) != len(ids): raise ValueError('请选择要永久删除的作品')
    removed_files = 0; retained_files = 0
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        projects = [load(c, ident) for ident in ids]
        for p in projects:
            if not p.get('deleted_at'): raise ValueError('只能永久删除回收站中的作品')
            if revisions and revisions.get(p['id']) != p['revision']: raise ValueError('回收站作品已有更新，请刷新后重试')
            assert_idle(c, p['id'])
        candidates = media_paths(projects)
        for ident in ids:
            row = c.execute('SELECT body FROM canvases WHERE project_id=?', (ident,)).fetchone()
            if row: candidates.update(media_paths(json.loads(row['body'])))
            row = c.execute('SELECT body FROM original_canvases WHERE project_id=?', (ident,)).fetchone()
            if row: candidates.update(media_paths(json.loads(row['body'])))
        for table in ('jobs', 'revisions'):
            for row in c.execute('SELECT body FROM ' + table):
                obj = json.loads(row['body'])
                project_id = obj.get('project_id') if table == 'jobs' else obj.get('project', {}).get('id')
                if project_id in ids: candidates.update(media_paths(obj))
        for ident in ids:
            c.execute('DELETE FROM projects WHERE id=?', (ident,))
            c.execute('DELETE FROM revisions WHERE project_id=?', (ident,))
        for row in c.execute('SELECT id,body FROM jobs').fetchall():
            if json.loads(row['body']).get('project_id') in ids: c.execute('DELETE FROM jobs WHERE id=?', (row['id'],))
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='assistant_messages'").fetchone():
            for ident in ids: c.execute('DELETE FROM assistant_messages WHERE project_id=?', (ident,))
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='assistant_memory'").fetchone():
            for ident in ids: c.execute('DELETE FROM assistant_memory WHERE project_id=?', (ident,))
        protected = set()
        for row in c.execute('SELECT body FROM canvases'): protected.update(media_paths(json.loads(row['body'])))
        for row in c.execute('SELECT body FROM original_canvases'): protected.update(media_paths(json.loads(row['body'])))
        for table in ('projects', 'jobs', 'revisions', 'library'):
            for row in c.execute('SELECT body FROM ' + table): protected.update(media_paths(json.loads(row['body'])))
        for path in candidates - protected:
            try: path.unlink(); removed_files += 1
            except OSError: retained_files += 1
        # Only remove the known per-project export. No recursive or calculated-directory deletion.
        for ident in ids:
            target = (store.DATA / 'exports' / (ident + '.zip')).resolve()
            if target.parent == (store.DATA / 'exports').resolve() and target.is_file():
                try: target.unlink(); removed_files += 1
                except OSError: retained_files += 1
    return {'deleted':len(ids), 'removed_files':removed_files, 'retained_files':retained_files}


@router.post('/empty')
def empty(payload:dict):
    return purge(payload.get('ids'), payload.get('confirm'), payload.get('revisions'))


@router.delete('/{ident}')
def delete(ident, payload:dict):
    if payload.get('revision') is None: raise ValueError('请刷新回收站后再永久删除')
    return purge([ident], payload.get('confirm'), {ident:payload['revision']})
