"""A/B 测试系统：对比默认模式 vs 电影感模式 vs 专家模式的生成质量。

记录存放在 data/ab_tests/（随工作区数据目录走，不写入程序目录）。
本模块只负责记录与统计；选定最佳版本仅作记录，不会自动改写镜头内容。
"""
import json
from pathlib import Path

from . import store, jobs as jobs_module
from .store import uid

MODES = ('default', 'cinematic', 'expert')
VARIANT_NAMES = {'default': '默认模式', 'cinematic': '电影感模式', 'expert': '专家模式'}


def _dir():
    path = store.DATA / 'ab_tests'
    path.mkdir(parents=True, exist_ok=True)
    return path


def _file(test_id):
    return _dir() / f'{test_id}.json'


def _save_ab_test(test):
    _file(test['id']).write_text(json.dumps(test, ensure_ascii=False, indent=2), encoding='utf-8')


def create_ab_test(project_id, segment_id, test_name='', description=''):
    """对同一 segment 分别用三种模式创建预览任务，供用户对比。"""
    project = store.get('projects', project_id)
    segment = next((s for s in project.get('segments', []) if s['id'] == segment_id), None)
    if not segment:
        raise KeyError(segment_id)

    test = {
        'id': uid('ab_test'),
        'project_id': project_id,
        'segment_id': segment_id,
        'test_name': test_name or f'A/B测试 - {segment.get("title", "未命名")}',
        'description': description,
        'created_at': store.now(),
        'status': 'running',
        'variants': [],
        'winner': None,
        'ratings': {},
        'notes': ''
    }

    variant_settings = {
        'default': {'cinematic_mode': False, 'expert_mode': False},
        'cinematic': {'cinematic_mode': True, 'expert_mode': False},
        'expert': {'cinematic_mode': False, 'expert_mode': True, 'export_markdown': True},
    }

    for mode in MODES:
        # 只在内存里改设定：jobs.create 会深拷贝为任务快照，不影响项目存储
        project.setdefault('settings', {}).update(variant_settings[mode])
        job = jobs_module.create(project, {
            'kind': 'text',
            'stage': 'storyboard',
            'target_id': segment_id,
            'instruction': f'用{VARIANT_NAMES[mode]}重新生成这个镜头，供 A/B 对比',
            'preview': True,
            'ab_test': {'test_id': test['id'], 'variant_id': mode},
        })
        test['variants'].append({
            'id': mode,
            'name': VARIANT_NAMES[mode],
            'job_id': job['id'],
            'status': 'pending',
            'result': None,
            'generated_at': None,
            'error': None,
        })

    _save_ab_test(test)
    return test


def get_ab_test(test_id):
    path = _file(test_id)
    if not path.exists():
        raise KeyError(test_id)
    return json.loads(path.read_text(encoding='utf-8'))


def list_ab_tests(project_id=None):
    tests = []
    for f in _dir().glob('*.json'):
        try:
            test = json.loads(f.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            continue
        if project_id is None or test.get('project_id') == project_id:
            tests.append(test)
    tests.sort(key=lambda t: t.get('created_at', ''), reverse=True)
    return tests


def update_ab_test_variant(test_id, variant_id, job_result, job_id=None, error=None):
    """任务完成/失败时回填变体（由 jobs 完成回调调用）。"""
    test = get_ab_test(test_id)
    variant = next((v for v in test['variants'] if v['id'] == variant_id), None)
    if not variant:
        raise KeyError(variant_id)

    variant['status'] = 'failed' if error else 'completed'
    variant['result'] = job_result if not error else None
    variant['error'] = error
    variant['generated_at'] = store.now()
    if job_id:
        variant['job_id'] = job_id

    if all(v['status'] in ('completed', 'failed') for v in test['variants']):
        test['status'] = 'completed'
        test['completed_at'] = store.now()

    _save_ab_test(test)
    return test


def rate_variant(test_id, variant_id, rating, notes=''):
    """用户对变体评分（1-5 分）。"""
    if not isinstance(rating, int) or not (1 <= rating <= 5):
        raise ValueError('评分必须是 1-5 的整数')

    test = get_ab_test(test_id)
    if not any(v['id'] == variant_id for v in test['variants']):
        raise KeyError(variant_id)

    test['ratings'][variant_id] = {'score': rating, 'notes': notes, 'rated_at': store.now()}
    _save_ab_test(test)
    return test


def select_winner(test_id, variant_id, notes=''):
    """记录用户选定的最佳版本（仅记录，不自动应用）。"""
    test = get_ab_test(test_id)
    if not any(v['id'] == variant_id for v in test['variants']):
        raise KeyError(variant_id)

    test['winner'] = variant_id
    test['notes'] = notes
    test['selected_at'] = store.now()
    _save_ab_test(test)
    return test


def get_ab_test_statistics(project_id=None):
    """各模式胜率、平均评分、平均耗时（由真实的变体时间戳计算）。"""
    tests = list_ab_tests(project_id)

    completed = [t for t in tests if t.get('status') == 'completed']

    win_counts = {m: 0 for m in MODES}
    for test in completed:
        if test.get('winner') in win_counts:
            win_counts[test['winner']] += 1
    total_winners = sum(win_counts.values())
    win_rates = {m: round(c / total_winners * 100, 1) if total_winners else 0 for m, c in win_counts.items()}

    rating_sum = {m: 0 for m in MODES}
    rating_count = {m: 0 for m in MODES}
    for test in completed:
        for variant_id, data in (test.get('ratings') or {}).items():
            if variant_id in rating_sum and isinstance(data.get('score'), int):
                rating_sum[variant_id] += data['score']
                rating_count[variant_id] += 1
    avg_ratings = {m: round(rating_sum[m] / rating_count[m], 2) if rating_count[m] else 0 for m in MODES}

    # 平均耗时：用变体 generated_at 与该测试 created_at 的差值
    durations = {m: [] for m in MODES}
    for test in completed:
        created = _parse_time(test.get('created_at'))
        for variant in test.get('variants', []):
            if variant.get('id') in durations and variant.get('generated_at') and created:
                done = _parse_time(variant['generated_at'])
                if done and done >= created:
                    durations[variant['id']].append((done - created).total_seconds())
    avg_seconds = {m: round(sum(v) / len(v), 1) if v else None for m, v in durations.items()}

    return {
        'total_tests': len(tests),
        'completed_tests': len(completed),
        'win_rates': win_rates,
        'avg_ratings': avg_ratings,
        'avg_generation_seconds': avg_seconds,
        'cost_comparison': None,  # 无 token 计费记录，不输出虚构成本
        'recommendation': _generate_recommendation(win_rates, avg_ratings, total_winners),
    }


def _parse_time(value):
    if not value:
        return None
    try:
        from datetime import datetime
        return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return None


def _generate_recommendation(win_rates, avg_ratings, total_winners=0):
    if not total_winners and not any(avg_ratings.values()):
        return '数据不足，无法生成推荐'

    scores = {m: win_rates.get(m, 0) * 0.6 + avg_ratings.get(m, 0) * 20 * 0.4 for m in MODES}
    best = max(scores, key=scores.get)
    notes = {
        'default': '默认模式速度和成本占优，适合日常创作与快速迭代。',
        'cinematic': '电影感模式在质量与成本间较均衡，适合关键镜头与中等预算项目。',
        'expert': '专家模式质量最高，适合高预算项目与需要人类审阅的完整文字分镜。',
    }
    return f'推荐使用：{VARIANT_NAMES[best]}。{notes[best]}'
