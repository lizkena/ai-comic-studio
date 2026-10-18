"""Resource locks for user edits and submissions; unrelated shots may run together."""
from . import store

ACTIVE = {'queued', 'running', 'waiting_dependency'}


def scope(p, job, dependencies=True):
    stage, kind, target = job.get('stage'), job.get('kind'), job.get('target_id')
    reads, writes = {'setup'}, set()
    segments = p.get('segments', [])
    episodes = p.get('outputs', {}).get('script', {}).get('episodes', [])

    def object_scope(ident):
        seg = next((x for x in segments if x['id'] == ident), None)
        if seg:
            reads.update({'segment:' + ident, 'board:' + str(seg.get('episode_id')), 'episode:' + str(seg.get('episode_id'))})
            reads.update('asset:' + x for x in seg.get('character_ids', []) + seg.get('prop_ids', []) + [seg.get('location_id')] if x)
            # Writes are scoped to this target; shared references remain reads.
            writes.add('segment:' + ident)
        else:
            reads.add('asset:' + str(ident)); writes.add('asset:' + str(ident))

    if stage == 'wf_canvas_text':
        writes.add('canvasnode:'+str(job.get('workflow_options',{}).get('canvas_node_id','text')))
    elif stage == 'wf_setup':
        reads.update({'source', 'chapter:*'}); writes.update({'setup', 'asset:*'})
    elif stage == 'wf_chapters' and target:
        reads.add('chapter:' + str(target)); writes.add('chapter:' + str(target))
        for ep in episodes:
            if target in ep.get('source_chapters', []) or any(target in sc.get('source_chapters', []) for sc in ep.get('scenes', [])):
                writes.add('episode:' + ep['id'])
    elif stage in ('wf_story', 'wf_continue', 'wf_chapters'):
        reads.update({'source', 'chapter:*'}); writes.add('chapter:*')
    elif stage == 'wf_script':
        reads.add('chapter:' + str(target)); writes.add('scriptchapter:' + str(target))
        for ep in episodes:
            if target in ep.get('source_chapters', []) or any(target in sc.get('source_chapters', []) for sc in ep.get('scenes', [])):
                writes.add('episode:' + ep['id'])
    elif stage == 'wf_breakdown':
        reads.update({'episode:' + str(target), 'asset:*'}); writes.add('board:' + str(target))
    elif stage == 'wf_prompts':
        for ident in job.get('workflow_options', {}).get('target_ids', []): object_scope(ident)
    elif kind in ('image', 'video', 'white', 'polish') or stage == 'wf_video_prompt':
        object_scope(target)
        seg = next((x for x in segments if x['id'] == target), None)
        if dependencies and kind == 'video' and seg and seg.get('continuity') and seg.get('previous_id'):
            reads.add('segment:' + seg['previous_id'])
    elif kind == 'assembly':
        for seg in segments:
            if not target or seg.get('episode_id') == target: reads.add('segment:' + seg['id'])
        writes.add('export:' + str(target or '*'))
    else:
        reads.add('source'); writes.add('*')
    return {'reads': reads, 'writes': writes}


def overlaps(left, right):
    return any(a == b or a == '*' or b == '*' or (a.endswith(':*') and b.startswith(a[:-1])) or (b.endswith(':*') and a.startswith(b[:-1])) for a in left for b in right)


def conflicts(a, b):
    return overlaps(a['writes'], b['reads'] | b['writes']) or overlaps(a['reads'], b['writes'])


def assert_available(p, requested, exclude=None, submission=None):
    if not submission:
        reads = set(requested['reads'])
        for resource in requested['writes']:
            if resource.startswith('segment:'):
                seg = next((x for x in p.get('segments', []) if resource == 'segment:' + x['id']), None)
                if seg: reads.update({'board:'+str(seg.get('episode_id')), 'episode:'+str(seg.get('episode_id'))})
        requested = {**requested, 'reads':reads}
    for job in store.job_rows(project_id=p['id'], statuses=ACTIVE, full=True):
        if job.get('project_id') == p['id'] and job.get('status') in ACTIVE and job['id'] != exclude:
            snapshot = job.get('source_snapshot') or p
            chain = submission and submission.get('kind') == job.get('kind') == 'video'
            wanted = scope(p, submission, dependencies=False) if chain else requested
            if conflicts(wanted, scope(snapshot, job, dependencies=not chain)):
                raise ValueError('相关内容正在执行任务，请完成或停止任务后再操作（' + job['id'] + '）')


def assert_submission(p, payload, exclude=None):
    assert_available(p, scope(p, payload), exclude, submission=payload)


def changes(previous, incoming):
    """Only lock the edited resource, allowing autosaves elsewhere in the project."""
    result, reads = set(), set()
    if previous.get('source') != incoming.get('source'): result.add('source')
    if previous.get('settings') != incoming.get('settings'): result.add('setup')
    old, new = previous.get('outputs', {}), incoming.get('outputs', {})
    for key in ('production_setup', 'direction', 'characters', 'world'):
        if old.get(key) != new.get(key): result.add('setup')
    for key, group, field in [('novel', 'chapter', 'chapters'), ('script', 'episode', 'episodes')]:
        a = {x['id']: x for x in old.get(key, {}).get(field, [])}
        b = {x['id']: x for x in new.get(key, {}).get(field, [])}
        result.update(group + ':' + ident for ident in a.keys() | b.keys() if a.get(ident) != b.get(ident))
    for field, group in [('segments', 'segment'), ('assets', 'asset')]:
        a = {x['id']: x for x in previous.get(field, [])}
        b = {x['id']: x for x in incoming.get(field, [])}
        for ident in a.keys() | b.keys():
            if a.get(ident) == b.get(ident): continue
            result.add(group + ':' + ident)
            if group == 'segment':
                for seg in (a.get(ident), b.get(ident)):
                    if seg: reads.update({'board:'+str(seg.get('episode_id')), 'episode:'+str(seg.get('episode_id'))})
            if group == 'segment' and (ident not in a or ident not in b):
                result.add('board:' + str((a.get(ident) or b[ident]).get('episode_id')))
    if result: reads.add('setup')
    return {'reads': reads, 'writes': result}
