import os
import logging
from webdav3.client import Client
from webdav3.exceptions import WebDavException, ResponseErrorCode

skipables_file = 'skipables.txt'
log = logging.getLogger(__name__)


def load_skipables_set(filename: str) -> set[str]:
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return {line.strip() for line in f if line.strip()}
    except FileNotFoundError:
        return set()


skip_set = load_skipables_set(skipables_file)


def join_remote(base: str, child: str) -> str:
    return base.rstrip('/') + '/' + child.lstrip('/')

def get_extension(path: str) -> str:
    root, extension = os.path.splitext(path)
    return extension

def pull_continue(client: Client, remote_dir: str, local_dir: str, use_skipables: bool, exclude_extensions: list[str]):
    os.makedirs(local_dir, exist_ok=True)

    entries = client.list(remote_dir)
    remote_basename = remote_dir.rstrip('/').split('/')[-1]

    for name in entries:
        if name in ('', '.', '..'):
            continue

        name_clean = name.rstrip('/')

        if name_clean == remote_basename:
            continue

        remote_path = remote_path = join_remote(remote_dir, name)

        if get_extension(path=remote_path) in exclude_extensions:
            continue

        if remote_path not in skip_set or not use_skipables:
            local_path = os.path.join(local_dir, name.strip('/'))

            if name.endswith('/'):
                pull_continue(client, remote_path, local_path, use_skipables, exclude_extensions)
                continue

            try:
                client.download_sync(remote_path=remote_path, local_path=local_path)
            except ResponseErrorCode as e:
                if getattr(e, 'code', None) == 403:
                    log.error(f'Keine Leserechte: {remote_path}')
                    try:
                        with open(skipables_file, 'a', encoding='utf-8') as f:
                            f.write(remote_path + '\n')
                        skip_set.add(remote_path)
                    except FileNotFoundError:
                        print('Pfad existiert nicht.')
                    except PermissionError:
                        print('Keine Schreibrechte für diese Datei/Ordner.')
                    except OSError as e:
                        print(f'Anderer I/O-Fehler: {e}')
                else:
                    log.error(f'HTTP-Fehler {getattr(e, 'code', '?')}: {remote_path} -> {e}')
                continue
            except WebDavException as e:
                log.error(f'WebDAV-Fehler: {remote_path} -> {e}')
                continue
