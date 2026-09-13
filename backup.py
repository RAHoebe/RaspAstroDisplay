"""Consistent, downloadable ZIP backups. User images are never treated as a cache."""
from datetime import datetime, timezone
from contextlib import closing
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import tempfile
import threading
import uuid
import zipfile

from captures import RESERVE_BYTES, upload_lock
from providers import save_json, read_json


def sha256(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def create_archive(state, store, settings, destination):
    state, destination = Path(state), Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix='.snapshot-') as temp:
        temp = Path(temp)
        database = temp / 'captures.sqlite3'
        # Publish/upload is the only operation that adds image files; trash never removes them.
        with upload_lock, store.db() as source, closing(sqlite3.connect(database)) as target:
            source.backup(target)
            rows = target.execute('SELECT id,extension FROM captures').fetchall()
        files = {'state/captures/captures.sqlite3': database}
        for ident, extension in rows:
            for variant in ('original' + extension, 'preview.jpg', 'thumb.jpg'):
                file = store.root / ident / variant
                if not file.is_file():
                    raise OSError('A capture file is missing; backup was not completed.')
                files[f'state/captures/{ident}/{variant}'] = file
        for name, value in settings.items():
            file = temp / name
            file.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
            files['state/' + name] = file
        total = sum(p.stat().st_size for p in files.values())
        if shutil.disk_usage(destination.parent).free < total + RESERVE_BYTES:
            raise OSError('Not enough free space to create a ZIP backup.')
        manifest = dict(format='rasp-astro-display-backup', version=1,
                        created_at=datetime.now(timezone.utc).isoformat(), files={}, captures=len(rows))
        pending = destination.with_suffix('.pending')
        try:
            with zipfile.ZipFile(pending, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
                for name, file in files.items():
                    manifest['files'][name] = dict(bytes=file.stat().st_size, sha256=sha256(file))
                    archive.write(file, name)
                archive.writestr('manifest.json', json.dumps(manifest, indent=2))
                archive.writestr('RESTORE.txt', 'Use tools/restore-backup.py with an empty destination.\n'
                                    'The state directory contains captures, settings and favorites.\n'
                                    'Originals and trash are included. External star catalogs and temporary caches are excluded.\n')
            pending.replace(destination)
        finally:
            pending.unlink(missing_ok=True)
        return manifest


class BackupManager:
    def __init__(self, state, store):
        self.state, self.store = Path(state), store
        self.folder = self.state / 'exports'
        self.folder.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.active = None

    def status(self):
        value = read_json(self.folder / 'status.json', {})
        if value.get('status') == 'running' and self.active is None:
            value = dict(value, status='failed', error='Backup interrupted. Please try again.')
        return value

    def start(self, settings):
        with self.lock:
            if self.active:
                return self.status()
            ident = uuid.uuid4().hex
            self.active = ident
            save_json(self.folder / 'status.json', dict(id=ident, status='running'))
        def work():
            try:
                manifest = create_archive(self.state, self.store, settings, self.folder / (ident + '.zip'))
                save_json(self.folder / 'status.json', dict(id=ident, status='ready', captures=manifest['captures'],
                          created_at=manifest['created_at'], url='/backup-file/' + ident))
                for old in sorted(self.folder.glob('*.zip'), key=lambda p: p.stat().st_mtime, reverse=True)[2:]:
                    old.unlink(missing_ok=True)
            except Exception as exc:
                save_json(self.folder / 'status.json', dict(id=ident, status='failed', error=str(exc)))
            finally:
                with self.lock:
                    self.active = None
        threading.Thread(target=work, daemon=True, name='backup').start()
        return dict(id=ident, status='running')


def restore_archive(archive_path, destination):
    """Verify paths, sizes and hashes before publishing a NEW state directory."""
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('Destination must not exist; restore to a new directory first.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        info = archive.getinfo('manifest.json')
        if info.file_size > 16 * 1024 * 1024:
            raise ValueError('Manifest is too large.')
        manifest = json.loads(archive.read(info))
        if manifest.get('format') != 'rasp-astro-display-backup' or manifest.get('version') != 1:
            raise ValueError('Unsupported backup format.')
        members = archive.infolist()
        if len({m.filename for m in members}) != len(members):
            raise ValueError('Duplicate archive member.')
        total = 0
        for name, expected in manifest['files'].items():
            path = PurePosixPath(name)
            if (not name.startswith('state/') or '..' in path.parts or '\\' in name or ':' in name
                    or path.is_absolute() or len(path.parts) < 2):
                raise ValueError('Unsafe archive member.')
            member = archive.getinfo(name)
            if member.file_size != expected['bytes'] or (member.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Invalid backup member.')
            total += member.file_size
        if total + RESERVE_BYTES > shutil.disk_usage(destination.parent).free:
            raise OSError('Not enough free space to restore this backup.')
        with tempfile.TemporaryDirectory(dir=destination.parent, prefix='.astro-restore-') as temp:
            temp = Path(temp)
            for name, expected in manifest['files'].items():
                target = temp.joinpath(*PurePosixPath(name).parts[1:])
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(name) as source, target.open('wb') as out:
                    shutil.copyfileobj(source, out, length=1024 * 1024)
                if sha256(target) != expected['sha256']:
                    raise ValueError('Backup checksum mismatch.')
            with closing(sqlite3.connect(temp / 'captures/captures.sqlite3')) as db:
                if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('Invalid capture database.')
            temp.rename(destination)
    return manifest
