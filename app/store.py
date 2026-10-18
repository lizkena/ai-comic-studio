"""Independent, durable workspace. Nothing reads the old canvas application's data."""
import os
import json
import sqlite3
import uuid
import time
from pathlib import Path
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get('COMIC_STUDIO_DATA', str(ROOT / 'data'))).resolve()
MEDIA = DATA / 'media'
for directory in (DATA, MEDIA, DATA / 'exports'):
    directory.mkdir(parents=True, exist_ok=True)


def uid(prefix='obj'):
    return prefix + '_' + uuid.uuid4().hex[:12]


def now():
    return time.strftime('%Y-%m-%d %H:%M:%S')


@contextmanager
def db():
    connection = sqlite3.connect(DATA / 'studio.sqlite3', timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA journal_mode=WAL')
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize():
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(id TEXT PRIMARY KEY, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS library(id TEXT PRIMARY KEY, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS revisions(id TEXT PRIMARY KEY, project_id TEXT, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS canvases(project_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS original_canvases(project_id TEXT PRIMARY KEY, updated_at INTEGER NOT NULL, body TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS delete_project_original_canvas AFTER DELETE ON projects
        BEGIN DELETE FROM original_canvases WHERE project_id=OLD.id; END;
        CREATE TRIGGER IF NOT EXISTS delete_project_canvas AFTER DELETE ON projects
        BEGIN DELETE FROM canvases WHERE project_id=OLD.id; END;
        ''')
        initialize_summaries(c)


ACTIVE_JOBS = ('queued', 'running', 'waiting_dependency')
JOB_LIST_FIELDS = ('id', 'project_id', 'project_name', 'kind', 'stage', 'target_id', 'status',
    'created_at', 'updated_at', 'started_at', 'completed_at', 'provider_id', 'model', 'skill',
    'logs', 'error', 'remote_id', 'uncertain', 'pending_apply', 'discarded', 'applied_by_user',
    'applied_automatically', 'chain_paused', 'attempt', 'preview', 'auto', 'remaining',
    'workflow_options', 'source_revision')


def project_summary(project):
    result = {k:project.get(k) for k in ('id', 'name', 'entry', 'sample', 'revision', 'updated_at', 'deleted_at', 'stage_status')}
    result['settings'] = {k:v for k,v in project.get('settings', {}).items()
                          if k in ('ratio', 'genre', 'style', 'genre_preset', 'style_preset', 'free_canvas')}
    result.update(source=project.get('source', '')[:500], asset_count=len(project.get('assets', [])),
                  segment_count=len(project.get('segments', [])))
    return result


def target_labels(project):
    objects = list(project.get('assets', [])) + list(project.get('segments', []))
    for output in project.get('outputs', {}).values():
        if isinstance(output, dict):
            for key in ('chapters', 'episodes', 'characters'):
                objects.extend(output.get(key, []))
    labels = {}
    for x in objects:
        if isinstance(x, dict) and x.get('id'):
            labels.setdefault(x['id'], x.get('title') or x.get('name') or '')
    return labels


def sync_summary(c, table, obj):
    """Update the small read model in the same transaction as its source record."""
    if table == 'projects':
        c.execute('INSERT OR REPLACE INTO project_summaries VALUES(?,?,?,?,?)',
            (obj['id'], obj.get('revision', 0), obj.get('deleted_at'),
             json.dumps(project_summary(obj), ensure_ascii=False), json.dumps(target_labels(obj), ensure_ascii=False)))
    elif table == 'jobs':
        result = {k:obj[k] for k in JOB_LIST_FIELDS if k in obj}
        result.setdefault('logs', [])
        result['has_result'] = bool(obj.get('result'))
        result['result'] = {k:obj['result'][k] for k in ('file', 'tail') if k in obj['result']} if isinstance(obj.get('result'), dict) and obj['result'].get('file') else None
        options = obj.get('workflow_options') or {}
        selected = options.get('target_ids', []) if obj.get('stage') == 'wf_prompts' else []
        target = obj.get('target_id') or (selected[0] if len(selected) == 1 else None)
        snapshot = obj.get('source_snapshot') or {}
        result['target_label_snapshot'] = target_labels(snapshot).get(target)
        ordinal = c.execute('SELECT rowid FROM jobs WHERE id=?', (obj['id'],)).fetchone()[0]
        c.execute('INSERT OR REPLACE INTO job_summaries VALUES(?,?,?,?,?,?,?,?,?)',
            (obj['id'], obj.get('project_id'), obj.get('status'), obj.get('identity'),
             obj.get('created_at', ''), obj.get('updated_at', ''), ordinal,
             int(bool(obj.get('pending_apply') and obj.get('status') == 'succeeded')),
             json.dumps(result, ensure_ascii=False)))


def initialize_summaries(c):
    c.executescript('''
        CREATE TABLE IF NOT EXISTS project_summaries(id TEXT PRIMARY KEY, revision INTEGER, deleted_at TEXT, body TEXT NOT NULL, target_labels TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS project_summary_visibility ON project_summaries(deleted_at);
        CREATE TABLE IF NOT EXISTS job_summaries(id TEXT PRIMARY KEY, project_id TEXT, status TEXT, identity TEXT, created_at TEXT, updated_at TEXT, ordinal INTEGER, pending_apply INTEGER, body TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS job_summary_project_status ON job_summaries(project_id,status,ordinal DESC);
        CREATE INDEX IF NOT EXISTS job_summary_status ON job_summaries(status,ordinal DESC);
        CREATE INDEX IF NOT EXISTS job_summary_identity ON job_summaries(identity,status);
        CREATE TRIGGER IF NOT EXISTS remove_project_summary AFTER DELETE ON projects BEGIN DELETE FROM project_summaries WHERE id=OLD.id; END;
        CREATE TRIGGER IF NOT EXISTS remove_job_summary AFTER DELETE ON jobs BEGIN DELETE FROM job_summaries WHERE id=OLD.id; END;
    ''')
    c.execute('BEGIN IMMEDIATE')
    # Backfill only missing IDs. Existing databases are read once, one record at a time.
    for table, summary in (('projects', 'project_summaries'), ('jobs', 'job_summaries')):
        for row in c.execute(f'SELECT source.body FROM {table} source LEFT JOIN {summary} cached ON cached.id=source.id WHERE cached.id IS NULL'):
            sync_summary(c, table, json.loads(row['body']))


def project_summaries(deleted=False):
    with db() as c:
        rows = c.execute('SELECT body FROM project_summaries WHERE deleted_at IS '+('NOT NULL' if deleted else 'NULL')+' ORDER BY json_extract(body,\'$.updated_at\') DESC,id DESC')
        return [json.loads(r['body']) for r in rows]


def project_overview(ident):
    with db() as c:
        row = c.execute('SELECT body,target_labels FROM project_summaries WHERE id=? AND deleted_at IS NULL', (ident,)).fetchone()
    if not row: raise KeyError(ident)
    return json.loads(row['body']), json.loads(row['target_labels'])


def job_rows(project_id=None, statuses=None, identity=None, full=False, visible=False, limit=None, offset=0):
    """Indexed selection; execution explicitly requests full immutable snapshots."""
    where, args = [], []
    if project_id is not None: where.append('s.project_id=?'); args.append(project_id)
    if statuses is not None:
        if not statuses: return []
        where.append('s.status IN ('+','.join('?' for _ in statuses)+')'); args.extend(statuses)
    if identity is not None: where.append('s.identity=?'); args.append(identity)
    if visible: where.append('EXISTS(SELECT 1 FROM project_summaries p WHERE p.id=s.project_id AND p.deleted_at IS NULL)')
    query = ('SELECT original.body FROM job_summaries s JOIN jobs original ON original.id=s.id' if full else 'SELECT s.body FROM job_summaries s')
    query += (' WHERE '+' AND '.join(where) if where else '') + ' ORDER BY s.ordinal DESC'
    if limit is not None: query += ' LIMIT ? OFFSET ?'; args.extend((limit, offset))
    with db() as c: return [json.loads(r['body']) for r in c.execute(query, args)]


def job_counts(project_id):
    with db() as c:
        rows = c.execute('SELECT status,count(*) AS n,sum(pending_apply) AS pending FROM job_summaries WHERE project_id=? GROUP BY status', (project_id,)).fetchall()
    counts = {'total':0, 'active':0, 'succeeded':0, 'failed':0, 'cancelled':0, 'pending_apply':0}
    for r in rows:
        counts['total'] += r['n']; counts['pending_apply'] += r['pending'] or 0
        if r['status'] in ACTIVE_JOBS: counts['active'] += r['n']
        elif r['status'] in counts: counts[r['status']] += r['n']
    return counts


def all_rows(table):
    assert table in ('projects', 'jobs', 'settings', 'revisions', 'library')
    with db() as c:
        return [json.loads(r['body']) for r in c.execute(f'SELECT body FROM {table} ORDER BY rowid DESC')]


def get(table, ident, include_deleted=False):
    assert table in ('projects', 'jobs', 'settings', 'library')
    with db() as c:
        row = c.execute(f'SELECT body FROM {table} WHERE id=?', (ident,)).fetchone()
    if not row:
        raise KeyError(ident)
    obj = json.loads(row['body'])
    if table == 'projects' and obj.get('deleted_at') and not include_deleted:
        raise ValueError('作品已移入回收站，请先恢复作品。')
    return obj


def put(table, obj):
    assert table in ('projects', 'jobs', 'settings', 'library')
    with db() as c:
        if table == 'jobs' and obj.get('status') in ('queued', 'running', 'waiting_dependency'):
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT body FROM projects WHERE id=?', (obj.get('project_id'),)).fetchone()
            if obj.get('project_id') and not row: raise KeyError(obj['project_id'])
            if row and json.loads(row['body']).get('deleted_at'): raise ValueError('回收站作品不能提交或恢复任务，请先恢复作品。')
        c.execute(f'INSERT OR REPLACE INTO {table}(id,body) VALUES(?,?)', (obj['id'], json.dumps(obj, ensure_ascii=False)))
        if table in ('projects', 'jobs'): sync_summary(c, table, obj)
    return obj


def save_project(project, expected=None, reason='编辑', transaction_hook=None):
    if project.get('segments'):
        project['outputs']['storyboard']={'segments':project['segments']}
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        old_row = c.execute('SELECT body FROM projects WHERE id=?', (project['id'],)).fetchone()
        old = json.loads(old_row['body']) if old_row else None
        if not old and (expected is not None or project.get('revision', 0) > 0): raise KeyError(project['id'])
        if old and old.get('deleted_at'): raise ValueError('作品已移入回收站，请先恢复作品。')
        project.pop('deleted_at', None)
        if old and expected is not None and old['revision'] != expected:
            raise ValueError('项目已有更新，请先刷新后再保存，编辑内容尚未覆盖。')
        if old:
            c.execute('INSERT INTO revisions VALUES(?,?,?)', (uid('rev'), old['id'], json.dumps({'at': now(), 'reason': reason, 'project': old}, ensure_ascii=False)))
        project['revision'] = (old or {}).get('revision', 0) + 1
        project['updated_at'] = now()
        if transaction_hook:
            transaction_hook(c, project)
        c.execute('INSERT OR REPLACE INTO projects VALUES(?,?)', (project['id'], json.dumps(project, ensure_ascii=False)))
        sync_summary(c, 'projects', project)
    return project


def revisions(project_id):
    with db() as c:
        return [{'id': r['id'], **json.loads(r['body'])} for r in c.execute('SELECT id,body FROM revisions WHERE project_id=? ORDER BY rowid DESC LIMIT 100', (project_id,))]


initialize()
