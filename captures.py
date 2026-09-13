"""Persistent user photographs; never part of the disposable survey cache."""
from contextlib import contextmanager
from datetime import date, datetime, timezone
import hashlib
from pathlib import Path
import re
import shutil
import sqlite3
import threading
import uuid

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 25 * 1024 * 1024
MAX_PIXELS = 32_000_000
RESERVE_BYTES = 2 * 1024 ** 3
upload_lock = threading.Lock()


class DuplicateCapture(ValueError):
    pass


class CaptureStore:
    def __init__(self, root):
        self.root = (Path(root) / 'captures').resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS captures (
                    id TEXT PRIMARY KEY, object_id TEXT NOT NULL, object_name TEXT NOT NULL,
                    scope_id TEXT NOT NULL, scope_name TEXT NOT NULL, fov_width REAL, fov_height REAL,
                    filename TEXT NOT NULL, extension TEXT NOT NULL, sha256 TEXT NOT NULL,
                    bytes INTEGER NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL,
                    uploaded_at TEXT NOT NULL, observed_on TEXT, note TEXT NOT NULL, trashed INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS capture_objects ON captures(object_id, scope_id, trashed);
                CREATE UNIQUE INDEX IF NOT EXISTS capture_unique_active
                  ON captures(object_id, scope_id, sha256) WHERE trashed=0;
                CREATE TABLE IF NOT EXISTS favorites (
                    object_id TEXT NOT NULL, scope_id TEXT NOT NULL,
                    PRIMARY KEY(object_id, scope_id)
                );
            ''')

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.root / 'captures.sqlite3', timeout=20)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def add(self, stream, filename, target, scope, observed_on='', note=''):
        filename = re.split(r'[/\\]', filename or '')[-1]
        ext = Path(filename).suffix.lower()
        if ext not in ('.jpg', '.jpeg', '.png'):
            raise ValueError('Alleen JPG/JPEG en PNG zijn toegestaan.')
        if len(filename) > 180 or any(ord(c) < 32 for c in filename):
            raise ValueError('Ongeldige bestandsnaam.')
        if len(note) > 1000:
            raise ValueError('De notitie mag maximaal 1000 tekens bevatten.')
        if observed_on:
            try:
                observed_on = date.fromisoformat(observed_on).isoformat()
            except ValueError:
                raise ValueError('Kies een geldige opnamedatum.')
        body = stream.read(MAX_BYTES + 1)
        if not body or len(body) > MAX_BYTES:
            raise ValueError('Maximaal 25 MB per foto.')
        digest = hashlib.sha256(body).hexdigest()
        ident = uuid.uuid4().hex
        temp = self.root / ('.pending-' + ident)
        dest = self.root / ident
        with upload_lock:
            if shutil.disk_usage(self.root).free < RESERVE_BYTES + len(body) + 25 * 1024 ** 2:
                raise OSError('Te weinig vrije ruimte; er blijft 2 GB vrij voor het systeem.')
            with self.db() as db:
                if db.execute('SELECT id FROM captures WHERE object_id=? AND scope_id=? AND sha256=? AND trashed=0',
                              (target['id'], scope['id'], digest)).fetchone():
                    raise DuplicateCapture('Deze foto staat al bij dit object en deze telescoop.')
            temp.mkdir()
            try:
                original = temp / ('original' + ext)
                original.write_bytes(body)
                with Image.open(original, formats=['JPEG', 'PNG']) as im:
                    if im.format != ('PNG' if ext == '.png' else 'JPEG'):
                        raise ValueError('Bestandsinhoud en bestandsextensie komen niet overeen.')
                    if im.width * im.height > MAX_PIXELS or getattr(im, 'n_frames', 1) != 1:
                        raise ValueError('Maximaal 32 megapixels; gebruik een stilstaande foto.')
                    im.verify()
                with Image.open(original, formats=['JPEG', 'PNG']) as im:
                    im.load()
                    photo = ImageOps.exif_transpose(im)
                    width, height = photo.size
                    if photo.mode in ('I', 'I;16', 'I;16B'):
                        photo = photo.point(lambda x: x / 256).convert('L')
                    if photo.mode in ('RGBA', 'LA') or (photo.mode == 'P' and 'transparency' in photo.info):
                        rgba = photo.convert('RGBA')
                        photo = Image.new('RGB', photo.size, '#020402')
                        photo.paste(rgba, mask=rgba.getchannel('A'))
                    else:
                        photo = photo.convert('RGB')
                    for label, size in [('preview', (1920, 1920)), ('thumb', (400, 300))]:
                        reduced = photo.copy()
                        reduced.thumbnail(size, Image.Resampling.LANCZOS)
                        reduced.save(temp / (label + '.jpg'), 'JPEG', quality=88)
                temp.rename(dest)
                with self.db() as db:
                    db.execute('INSERT INTO captures VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)',
                               (ident, target['id'], target['name'], scope['id'], scope['name'], scope['width'], scope['height'],
                                filename, ext, digest, len(body), width, height, datetime.now(timezone.utc).isoformat(), observed_on or None, note.strip()))
                return self.get(ident)
            except (UnidentifiedImageError, Image.DecompressionBombError, SyntaxError) as exc:
                raise ValueError('Geen geldige JPG- of PNG-afbeelding.') from exc
            except sqlite3.IntegrityError as exc:
                raise DuplicateCapture('Deze foto is al opgeslagen.') from exc
            finally:
                assert temp.resolve().parent == self.root and dest.resolve().parent == self.root
                if temp.exists():
                    shutil.rmtree(temp)
                # A failed transaction must not leave a published original behind.
                if dest.exists() and not self.get(ident):
                    shutil.rmtree(dest)

    def get(self, ident, include_trash=False):
        if not re.fullmatch('[a-f0-9]{32}', ident):
            return None
        with self.db() as db:
            row = db.execute('SELECT * FROM captures WHERE id=?' + ('' if include_trash else ' AND trashed=0'), (ident,)).fetchone()
        return dict(row) if row else None

    def listing(self, object_id='', scope_id='', query='', page=0, trash=False):
        where, values = ['trashed=?'], [int(trash)]
        for key, value in [('object_id', object_id), ('scope_id', scope_id)]:
            if value:
                where.append(key + '=?'); values.append(value)
        if query:
            where.append('(object_name LIKE ? OR note LIKE ?)'); values.extend(['%' + query + '%'] * 2)
        clause = ' AND '.join(where)
        with self.db() as db:
            total = db.execute('SELECT count(*) FROM captures WHERE ' + clause, values).fetchone()[0]
            page = min(max(0, page), max(0, (total - 1) // 6))
            rows = db.execute('SELECT * FROM captures WHERE ' + clause + ' ORDER BY uploaded_at DESC, id LIMIT 6 OFFSET ?', values + [page * 6]).fetchall()
        return dict(items=[dict(r) for r in rows], total=total, page=page)

    def summary(self):
        with self.db() as db:
            rows = db.execute('SELECT object_id,scope_id,count(*) AS count FROM captures WHERE trashed=0 GROUP BY object_id,scope_id').fetchall()
            scopes = db.execute('SELECT scope_id AS id, MAX(scope_name) AS name FROM captures GROUP BY scope_id').fetchall()
            used = db.execute('SELECT COALESCE(SUM(bytes),0) FROM captures').fetchone()[0]
            favorites = db.execute('SELECT object_id,scope_id FROM favorites ORDER BY object_id').fetchall()
        counts = {}
        for r in rows:
            counts.setdefault(r['object_id'], {})[r['scope_id']] = r['count']
        selected = {}
        for row in favorites:
            selected.setdefault(row['scope_id'], []).append(row['object_id'])
        return dict(counts=counts, favorites=selected, scopes=[dict(r) for r in scopes], original_bytes=used,
                    free_bytes=shutil.disk_usage(self.root).free)

    def favorite(self, object_id, scope_id, enabled):
        with self.db() as db:
            if enabled:
                db.execute('INSERT OR IGNORE INTO favorites VALUES (?,?)', (object_id, scope_id))
            else:
                db.execute('DELETE FROM favorites WHERE object_id=? AND scope_id=?', (object_id, scope_id))

    def trash(self, ident, trashed):
        if not self.get(ident, True):
            raise KeyError(ident)
        try:
            with self.db() as db:
                db.execute('UPDATE captures SET trashed=? WHERE id=?', (int(trashed), ident))
        except sqlite3.IntegrityError as exc:
            raise DuplicateCapture('Er staat al een actieve kopie bij dit object en deze telescoop.') from exc
