"""Shared execution entry for explicit studio buttons and agent tool calls."""
from . import workflow

STAGES = {'wf_breakdown', 'wf_prompts', 'wf_video_prompt'}


def submit(project, payload):
    from . import jobs
    stage = payload.get('stage')
    if stage not in STAGES: raise ValueError('智能体制作类型不受支持')
    if payload.get('revision', project['revision']) != project['revision']:
        raise ValueError('作品已更新，请刷新后提交')
    workflow.context(project, stage, payload.get('target_id'), payload.get('workflow_options'))
    # Both entrances use the same pinned skills/memory, task locks and result validation.
    return jobs.create(project, {**payload, 'kind':'text', 'preview':True})
