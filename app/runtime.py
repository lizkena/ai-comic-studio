"""Read-only runtime identity and restart readiness; never submits a job."""
import hashlib
import json
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTANCE_ID = uuid.uuid4().hex


def backend_fingerprint(root=ROOT):
    root = Path(root)
    digest = hashlib.sha256()
    files = list((root/'app').rglob('*.py')) + list((root/'workflows').glob('*.json'))
    for path in sorted(files):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b'\0')
        digest.update(path.read_bytes())
        digest.update(b'\0')
    return digest.hexdigest()


LOADED_FINGERPRINT = backend_fingerprint()


def activity(data):
    database = Path(data)/'studio.sqlite3'
    counts = {'jobs':0, 'assistant':0, 'deployment':0}
    if not database.exists(): return {**counts, 'busy':False}
    # One consistent read snapshot, including assistant calls and model downloads.
    with closing(sqlite3.connect(database.as_uri()+'?mode=ro', uri=True, timeout=10)) as connection:
        connection.execute('BEGIN')
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'jobs' in tables:
            if 'job_summaries' in tables:
                counts['jobs'] = connection.execute("SELECT COUNT(*) FROM job_summaries WHERE status IN ('queued','running','waiting_dependency')").fetchone()[0]
            else:
                counts['jobs'] = connection.execute("SELECT COUNT(*) FROM jobs WHERE json_extract(body,'$.status') IN ('queued','running','waiting_dependency')").fetchone()[0]
        if 'assistant_messages' in tables:
            counts['assistant'] = connection.execute("SELECT COUNT(*) FROM assistant_messages WHERE json_extract(body,'$.status')='running'").fetchone()[0]
        if 'settings' in tables:
            row = connection.execute("SELECT body FROM settings WHERE id='deployment_state'").fetchone()
            if row: counts['deployment'] = int(json.loads(row[0]).get('status')=='running')
    return {**counts, 'busy':any(counts.values())}
