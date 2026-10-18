"""Start the workspace backend with no inherited launcher pipes."""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def launch(port, root=ROOT):
    if port not in range(8766,8787): raise ValueError('Invalid workspace port')
    root = Path(root)
    flags = (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if sys.platform=='win32' else 0
    with (root/'data/server.log').open('wb') as output, (root/'data/server-error.log').open('wb') as error:
        process = subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)],
            cwd=root, stdin=subprocess.DEVNULL, stdout=output, stderr=error, close_fds=True,
            creationflags=flags, start_new_session=sys.platform!='win32')
    return process.pid


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, required=True, choices=range(8766,8787))
    print(launch(parser.parse_args().port))
