"""Local catalog and application service shared by desktop, browser and MCP.

Source bytes and calibrated arrays are immutable. A recipe is reproducible from
its source array; exact results/prefixes can be reused in bounded memory caches.
Saving a recipe appends a run and changes only the active view.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import base64
import copy
import io
import json
import math
import os
import sqlite3
import threading
import uuid

import numpy as np
from PIL import Image

from .cache import MemoryCache


def _now():
    return datetime.now(timezone.utc).isoformat()


def _clean(value):
    if type(value) in (str, int, bool) or value is None:
        return value
    if type(value) is float:
        return value if math.isfinite(value) else None
    if isinstance(value, np.ndarray):
        return _clean(value.tolist())
    if isinstance(value, np.generic):
        return _clean(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _json(value):
    return json.dumps(_clean(value), ensure_ascii=False, allow_nan=False)


def _safe_name(value):
    return ''.join(c if c.isalnum() or c in '-_.' else '_' for c in str(value))[:120]


class Workbench:
    def __init__(self, data_dir):
        from .native_backend import describe
        self.scientific_backend = describe()
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        for name in ('originals', 'arrays'):
            (self.data_dir / name).mkdir(exist_ok=True)
        self._lock = threading.RLock()
        self._results = MemoryCache(128 * 1024 * 1024, 24)
        self._thumbnails = MemoryCache(24 * 1024 * 1024, 256)
        self._import_lock = threading.Lock()
        self._jobs_lock = threading.Lock()
        self._import_job = None
        self._import_thread = None
        self._import_cancel = threading.Event()
        self._closing = False
        self._db = sqlite3.connect(self.data_dir / 'catalog.sqlite3', check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute('PRAGMA foreign_keys=ON')
        self._db.execute('PRAGMA journal_mode=WAL')
        self._db.executescript('''
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, source_path TEXT UNIQUE NOT NULL,
                imported_at TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
                synthetic INTEGER NOT NULL DEFAULT 0, import_errors TEXT NOT NULL DEFAULT '[]');
            CREATE TABLE IF NOT EXISTS samples (
                id TEXT PRIMARY KEY, label TEXT NOT NULL, metadata TEXT NOT NULL DEFAULT '{}');
            CREATE TABLE IF NOT EXISTS scans (
                id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
                sample_id TEXT REFERENCES samples(id), filename TEXT NOT NULL, sha256 TEXT NOT NULL,
                source_artifact TEXT, array_artifact TEXT NOT NULL, metadata TEXT NOT NULL,
                statistics TEXT NOT NULL, operations TEXT NOT NULL DEFAULT '[]',
                history TEXT NOT NULL DEFAULT '[]', starred INTEGER NOT NULL DEFAULT 0,
                review_status TEXT NOT NULL DEFAULT 'unreviewed',
                UNIQUE(session_id,filename,sha256));
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, scan_id TEXT NOT NULL REFERENCES scans(id), created_at TEXT NOT NULL,
                operations TEXT NOT NULL, history TEXT NOT NULL, statistics TEXT NOT NULL,
                origin TEXT NOT NULL DEFAULT 'deterministic-scientific-core');
            CREATE TABLE IF NOT EXISTS measurements (
                id TEXT PRIMARY KEY, scan_id TEXT NOT NULL REFERENCES scans(id), created_at TEXT NOT NULL,
                kind TEXT NOT NULL, operations TEXT NOT NULL, parameters TEXT NOT NULL, result TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS exports (
                id TEXT PRIMARY KEY, scan_id TEXT REFERENCES scans(id), session_id TEXT REFERENCES sessions(id),
                created_at TEXT NOT NULL, format TEXT NOT NULL, manifest TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS scan_views (
                scan_id TEXT PRIMARY KEY REFERENCES scans(id), display TEXT NOT NULL DEFAULT '{}',
                masking TEXT NOT NULL DEFAULT 'exclude', visible INTEGER NOT NULL DEFAULT 1,
                mask_history TEXT NOT NULL DEFAULT '[]', mask_cursor INTEGER NOT NULL DEFAULT -1,
                mask_serial INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS mask_revisions (
                scan_id TEXT NOT NULL REFERENCES scans(id), revision INTEGER NOT NULL,
                created_at TEXT NOT NULL, data BLOB NOT NULL, edit TEXT NOT NULL,
                PRIMARY KEY(scan_id, revision));
            PRAGMA user_version=2;
        ''')
        columns = {r['name'] for r in self._db.execute('PRAGMA table_info(sessions)')}
        for name, definition in (('archived', 'INTEGER NOT NULL DEFAULT 0'),
                                 ('source_history', "TEXT NOT NULL DEFAULT '[]'")):
            if name not in columns:
                self._db.execute(f'ALTER TABLE sessions ADD COLUMN {name} {definition}')
        self._db.execute('PRAGMA user_version=3')
        self._db.commit()

    def close(self):
        with self._jobs_lock:
            self._closing = True
            self._import_cancel.set()
            worker = self._import_thread
        if worker:
            worker.join()
        with self._lock:
            self._results.clear()
            self._thumbnails.clear()
            self._db.close()

    def dispatch(self, method, payload=None):
        methods = {
            'bootstrap': self.bootstrap, 'import_folder': self.import_folder,
            'start_import': self.start_import, 'import_status': self.import_status,
            'cancel_import': self.cancel_import, 'list_folders': self.list_folders,
            'session': self.session, 'scan': self.scan, 'update_session': self.update_session,
            'update_scan': self.update_scan, 'process': self.process, 'preview': self.preview,
            'profile': self.profile, 'step_height': self.step_height, 'measure_area': self.measure_area,
            'export_scan': self.export_scan, 'export_session': self.export_session,
            'demo': self.demo, 'search_scans': self.search_scans,
            'edit_mask': self.edit_mask, 'update_mask': self.update_mask,
            'set_display': self.set_display, 'display_range': self.display_range,
        }
        if method not in methods:
            raise ValueError('Unknown operation: ' + str(method))
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise ValueError('Request parameters must be an object.')
        # Import I/O and job control must never wait behind the catalog lock.
        if method in ('import_folder', 'start_import', 'import_status', 'cancel_import'):
            return _clean(methods[method](**payload))
        with self._lock:
            return _clean(methods[method](**payload))

    def _row(self, id):
        row = self._db.execute('SELECT * FROM scans WHERE id=?', (id,)).fetchone()
        if row is None:
            raise ValueError('Image not found.')
        return row

    def _session_row(self, id):
        row = self._db.execute('SELECT * FROM sessions WHERE id=?', (id,)).fetchone()
        if row is None:
            raise ValueError('Session not found.')
        return row

    def _summary(self, row):
        meta = json.loads(row['metadata'])
        keys = ('filename', 'channel', 'direction', 'acquisition', 'width_um', 'height_um',
                'value_unit', 'width', 'height', 'instrument', 'position', 'x_offset_um',
                'y_offset_um', 'scan_angle_deg', 'warnings', 'calibration', 'orientation')
        item = {key: meta.get(key) for key in keys}
        item.update(id=row['id'], session_id=row['session_id'], filename=row['filename'],
                    starred=bool(row['starred']), review_status=row['review_status'],
                    statistics=json.loads(row['statistics']), operations=json.loads(row['operations']))
        item['warnings'] = item.get('warnings') or []
        return item

    def _session_summary(self, row):
        scans = self._db.execute('SELECT * FROM scans WHERE session_id=? ORDER BY filename,id', (row['id'],)).fetchall()
        return {'id': row['id'], 'name': row['name'], 'source_path': row['source_path'],
                'imported_at': row['imported_at'], 'notes': row['notes'], 'synthetic': bool(row['synthetic']),
                'scan_count': len(scans), 'channels': sorted({json.loads(s['metadata']).get('channel', 'Unknown') for s in scans}),
                'starred_count': sum(bool(s['starred']) for s in scans),
                'reviewed_count': sum(s['review_status'] == 'reviewed' for s in scans),
                'import_errors': json.loads(row['import_errors']), 'archived': bool(row['archived']),
                'source_history': json.loads(row['source_history'])}

    def list_folders(self):
        return [self._session_summary(r) for r in self._db.execute(
            'SELECT * FROM sessions ORDER BY archived,name COLLATE NOCASE,id')]

    def bootstrap(self):
        sessions = [self._session_summary(r) for r in self._db.execute(
            'SELECT * FROM sessions WHERE archived=0 ORDER BY imported_at DESC,id')]
        active = self._db.execute("SELECT value FROM settings WHERE key='active_session_id'").fetchone()
        active_id = active['value'] if active else None
        if active_id not in {s['id'] for s in sessions}:
            active_id = sessions[0]['id'] if sessions else None
        return {'sessions': sessions, 'active_session_id': active_id,
                'import_job': self.import_status()}

    def session(self, id):
        row = self._session_row(id)
        result = self._session_summary(row)
        result['scans'] = [self._summary(r) for r in self._db.execute('SELECT * FROM scans WHERE session_id=? ORDER BY filename,id', (id,))]
        self._db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('active_session_id',?)", (id,))
        self._db.commit()
        return result

    def _write_immutable(self, path, content):
        if path.exists():
            if path.read_bytes() != content:
                raise ValueError('Managed source integrity check failed.')
            return
        temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
        temporary.write_bytes(content)
        os.replace(temporary, path)
        try:
            path.chmod(0o444)
        except OSError:
            pass

    def _prepare_scan(self, array, metadata):
        from .science import statistics
        identifier = uuid.uuid4().hex
        artifact = 'arrays/' + identifier + '.npy'
        array_file = self.data_dir / artifact
        np.save(array_file, np.asarray(array, dtype=np.float64), allow_pickle=False)
        metadata = dict(metadata, array_sha256=hashlib.sha256(array_file.read_bytes()).hexdigest())
        metadata.setdefault('warnings', [])
        return identifier, artifact, metadata, statistics(array)

    def _insert_scan(self, session_id, filename, digest, array, metadata, original=None, prepared=None):
        existing = self._db.execute('SELECT id FROM scans WHERE session_id=? AND filename=? AND sha256=?', (session_id, filename, digest)).fetchone()
        if existing:
            return existing['id']
        identifier, artifact, metadata, stats = prepared or self._prepare_scan(array, metadata)
        metadata = dict(metadata, filename=filename)
        self._db.execute('''INSERT INTO scans(id,session_id,filename,sha256,source_artifact,array_artifact,metadata,statistics)
                            VALUES(?,?,?,?,?,?,?,?)''',
                         (identifier, session_id, filename, digest, original, artifact, _json(metadata), _json(stats)))
        return identifier

    def import_status(self):
        with self._jobs_lock:
            return copy.deepcopy(self._import_job)

    def cancel_import(self):
        with self._jobs_lock:
            if self._import_job and self._import_job['status'] == 'running':
                self._import_cancel.set()
                self._import_job['cancelling'] = True
            return copy.deepcopy(self._import_job)

    def start_import(self, path, session_id=None):
        if not isinstance(path, str) or not path.strip():
            raise ValueError('Choose a source folder.')
        with self._jobs_lock:
            if self._closing:
                raise ValueError('The workspace is closing.')
            if self._import_job and self._import_job['status'] == 'running':
                raise ValueError('An import is already running. Wait for it or cancel it first.')
            self._import_cancel.clear()
            self._import_job = dict(id=uuid.uuid4().hex, status='running', path=path,
                                    session_id=session_id, total=0, completed=0, added=0,
                                    skipped=0, errors=[], filename='', cancelling=False)
            self._import_thread = threading.Thread(target=self._run_import,
                args=(path, session_id), name='afm-folder-import', daemon=True)
            self._import_thread.start()
            return copy.deepcopy(self._import_job)

    def _run_import(self, path, session_id):
        def progress(**values):
            with self._jobs_lock:
                self._import_job.update(values)
        try:
            result = self.import_folder(path, session_id, _progress=progress, _cancel=self._import_cancel)
            progress(status='cancelled' if self._import_cancel.is_set() else 'completed',
                     session_id=result['id'] if result else None, filename='')
        except Exception as exc:
            progress(status='failed', message=str(exc), filename='')

    def import_folder(self, path, session_id=None, *, _progress=None, _cancel=None):
        # Serialize imports, not the rest of the service. Only short catalog writes
        # hold _lock; file reads, decoding, arrays and statistics happen outside it.
        from .importers import load_scan
        progress = _progress or (lambda **values: None)
        cancelled = _cancel.is_set if _cancel else (lambda: False)
        with self._import_lock:
            folder = Path(path).expanduser().resolve()
            if not folder.is_dir():
                raise ValueError('Source folder is unavailable. Reconnect it in Folders.')
            candidates = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in ('.tif', '.tiff'))
            if not candidates:
                raise ValueError('No supported AFM TIFF files were found directly inside this folder.')
            with self._lock:
                linked = self._db.execute('SELECT * FROM sessions WHERE source_path=?', (str(folder),)).fetchone()
                row = self._session_row(session_id) if session_id else linked
                if row and row['synthetic']:
                    raise ValueError('Synthetic examples cannot be reconnected to instrument folders.')
                if linked and row and linked['id'] != row['id']:
                    raise ValueError('This folder already belongs to another session.')
                identifier = row['id'] if row else uuid.uuid4().hex
                exists = row is not None
                known = {(r['filename'], r['sha256']) for r in self._db.execute(
                    'SELECT filename,sha256 FROM scans WHERE session_id=?', (identifier,))}
            added = skipped = completed = 0
            errors = []
            progress(total=len(candidates), session_id=identifier if exists else None)
            for source in candidates:
                if cancelled():
                    break
                progress(filename=source.name)
                try:
                    if source.stat().st_size > 512 * 1024 * 1024:
                        raise ValueError('AFM file exceeds the 512 MB import limit.')
                    content = source.read_bytes()
                    digest = hashlib.sha256(content).hexdigest()
                    if (source.name, digest) in known:
                        skipped += 1
                    else:
                        artifact = 'originals/' + digest + '/' + source.name
                        target = self.data_dir / artifact
                        target.parent.mkdir(exist_ok=True)
                        self._write_immutable(target, content)
                        del content
                        parsed = load_scan(target)
                        metadata = dict(parsed['metadata'], filename=source.name,
                                        source_filename=source.name, source_path=str(source),
                                        source_sha256=digest, imported_at=_now())
                        import re
                        match = re.match(r'^(\d+)(?:__|_)', source.stem)
                        if match:
                            metadata['acquisition'] = match.group(1)
                        prepared = self._prepare_scan(parsed['data'], metadata)
                        with self._lock, self._db:
                            if not exists:
                                self._db.execute('INSERT INTO sessions(id,name,source_path,imported_at) VALUES(?,?,?,?)',
                                                 (identifier, folder.name, str(folder), _now()))
                                exists = True
                            self._insert_scan(identifier, source.name, digest, None, metadata, artifact, prepared)
                        del parsed, prepared
                        known.add((source.name, digest))
                        added += 1
                except (ValueError, OSError, KeyError, TypeError, OverflowError) as exc:
                    errors.append({'filename': source.name, 'error': str(exc)})
                completed += 1
                progress(completed=completed, added=added, skipped=skipped,
                         errors=list(errors), session_id=identifier if exists else None)
            if not exists:
                if cancelled():
                    return None
                details = '; '.join(f"{e['filename']}: {e['error']}" for e in errors[:3])
                raise ValueError('No calibrated AFM images could be imported. ' + details)
            with self._lock, self._db:
                if row and row['source_path'] != str(folder) and not cancelled() and (added or skipped):
                    history = json.loads(row['source_history'])
                    history.append({'path': row['source_path'], 'changed_at': _now()})
                    self._db.execute('UPDATE sessions SET source_path=?,source_history=? WHERE id=?',
                                     (str(folder), _json(history), identifier))
                self._db.execute('UPDATE sessions SET import_errors=? WHERE id=?', (_json(errors), identifier))
                # Do not change the active session while the user browses during import.
                result = self._session_summary(self._session_row(identifier))
                result['scans'] = [self._summary(r) for r in self._db.execute(
                    'SELECT * FROM scans WHERE session_id=? ORDER BY filename,id', (identifier,))]
                result['import_summary'] = dict(added=added, skipped=skipped, errors=errors)
                return result

    def _array(self, row, operations=None, raw=False):
        from .science import apply_recipe
        operations = [] if raw else json.loads(row['operations']) if operations is None else operations
        self._validate_operations(operations)
        metadata = json.loads(row['metadata'])
        if any(op.get('type') in {'terrace_plane', 'auto_2d', 'auto_characterize', 'three_point'} for op in operations if isinstance(op, dict)):
            channel = metadata.get('channel', '').lower()
            if metadata.get('value_unit') != 'nm' or not any(name in channel for name in ('height', 'topography', 'topo')) or 'error' in channel:
                raise ValueError('2D material processing requires a calibrated height channel.')
        # Identity includes the immutable source, calibration/orientation metadata,
        # and every parameter (including resolved mask snapshots). A live mask or
        # display edit cannot silently alter a previously cached recipe.
        digest = hashlib.sha256((row['array_artifact'] + row['metadata']).encode('utf-8'))
        keys = [digest.hexdigest()]
        for op in operations:
            digest.update(json.dumps(op, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8'))
            keys.append(digest.hexdigest())
        cached = self._results.get(keys[-1])
        if cached is not None:
            return cached[0], json.loads(cached[1])
        # Resume only an identical recipe prefix, using the same scientific core.
        # After eviction/restart, replay from the source if no prefix is cached.
        for prefix in range(len(operations) - 1, -1, -1):
            cached = self._results.get(keys[prefix])
            if cached is not None:
                array, history = cached[0], json.loads(cached[1])
                break
        else:
            prefix, history = 0, []
            array = np.load(self.data_dir / row['array_artifact'], allow_pickle=False)
            array.flags.writeable = False
            self._results.put(keys[0], (array, '[]'), array.nbytes + 2)
        if operations:
            array, added = apply_recipe(array, operations[prefix:], metadata=metadata)
            for step in added:
                step['step'] += prefix
            history += added
            array.flags.writeable = False
            encoded = _json(history)
            self._results.put(keys[-1], (array, encoded), array.nbytes + len(encoded.encode('utf-8')))
        return array, history

    def _detail(self, row, operations=None, raw=False, data_encoding='json', prepared=None):
        from .science import statistics
        self._validate_encoding(data_encoding)
        array, history = prepared if prepared is not None else self._array(row, operations=operations, raw=raw)
        detail = self._summary(row)
        detail['metadata'] = json.loads(row['metadata'])
        detail['history'] = json.loads(row['history']) if raw else history
        detail['statistics'] = history[-1]['after'] if history else statistics(array)
        detail['mask'] = self._mask_detail(row)
        detail['display'] = self._display(row)
        detail['masked_statistics'] = None
        detail['masked_statistics_error'] = None
        if detail['mask']['masking'] != 'ignore':
            try:
                detail['masked_statistics'] = (detail['statistics'] if detail['mask']['masking'] == 'exclude' and not detail['mask']['count']
                                               else statistics(array, mask=self._mask_array(row), masking=detail['mask']['masking']))
            except ValueError as exc:
                detail['masked_statistics_error'] = str(exc)
        # Display-only nearest sampling. All measurements and CSV exports use full resolution.
        display_height, display_width = min(512, array.shape[0]), min(512, array.shape[1])
        ys = np.floor((np.arange(display_height) + .5) * array.shape[0] / display_height).astype(int)
        xs = np.floor((np.arange(display_width) + .5) * array.shape[1] / display_width).astype(int)
        display = array[np.ix_(ys, xs)]
        if data_encoding == 'f64le':
            # Exact display samples, including NaNs, without per-pixel JSON work.
            detail.update(data_base64=base64.b64encode(display.astype('<f8', copy=False).tobytes()).decode('ascii'),
                          data_encoding='f64le')
        else:
            detail['data'] = display.tolist()
        detail.update(data_width=display.shape[1], data_height=display.shape[0],
                      display_sampling={'method': 'nearest_pixel_center', 'source_width': array.shape[1], 'source_height': array.shape[0]}, raw=bool(raw))
        if operations is not None:
            detail['operations'] = operations
        return _clean(detail)

    @staticmethod
    def _validate_encoding(data_encoding):
        if data_encoding not in ('json', 'f64le'):
            raise ValueError('Image encoding must be json or f64le.')

    def scan(self, id, raw=False, data_encoding='json'):
        return self._detail(self._row(id), raw=bool(raw), data_encoding=data_encoding)

    def preview(self, id, operations, data_encoding='json'):
        row = self._row(id)
        operations = self._resolve_operations(row, operations)
        result = self._detail(row, operations=operations, data_encoding=data_encoding)
        result['preview'] = True
        return result

    @staticmethod
    def _validate_operations(operations):
        if not isinstance(operations, list) or len(operations) > 100:
            raise ValueError('A recipe must be a list of at most 100 operations.')

    def process(self, id, operations, data_encoding='json'):
        from .science import statistics
        self._validate_encoding(data_encoding)
        row = self._row(id)
        operations = self._resolve_operations(row, operations)
        array, history = self._array(row, operations=operations)
        stats = history[-1]['after'] if history else statistics(array)
        with self._db:
            self._db.execute('INSERT INTO runs(id,scan_id,created_at,operations,history,statistics) VALUES(?,?,?,?,?,?)',
                             (uuid.uuid4().hex, id, _now(), _json(operations), _json(history), _json(stats)))
            self._db.execute('UPDATE scans SET operations=?,history=?,statistics=?,review_status=? WHERE id=?',
                             (_json(operations), _json(history), _json(stats), 'unreviewed', id))
        return self._detail(self._row(id), data_encoding=data_encoding, prepared=(array, history))

    def update_session(self, id, name=None, notes=None, archived=None):
        self._session_row(id)
        if name is not None and (not isinstance(name, str) or not name.strip() or len(name) > 300):
            raise ValueError('Session name must contain 1–300 characters.')
        if notes is not None and (not isinstance(notes, str) or len(notes) > 20000):
            raise ValueError('Session notes must be text of at most 20,000 characters.')
        if archived is not None and not isinstance(archived, bool):
            raise ValueError('Archived must be true or false.')
        with self._db:
            if archived is not None:
                self._db.execute('UPDATE sessions SET archived=? WHERE id=?', (int(archived), id))
            if name is not None:
                self._db.execute('UPDATE sessions SET name=? WHERE id=?', (name.strip(), id))
            if notes is not None:
                self._db.execute('UPDATE sessions SET notes=? WHERE id=?', (notes, id))
        return self.session(id)

    def update_scan(self, id, starred=None, review_status=None, data_encoding='json'):
        self._validate_encoding(data_encoding)
        self._row(id)
        if starred is not None and not isinstance(starred, bool):
            raise ValueError('Starred must be true or false.')
        if review_status is not None and review_status not in ('reviewed', 'unreviewed'):
            raise ValueError('Review status must be reviewed or unreviewed.')
        with self._db:
            if starred is not None:
                self._db.execute('UPDATE scans SET starred=? WHERE id=?', (int(starred), id))
            if review_status is not None:
                self._db.execute('UPDATE scans SET review_status=? WHERE id=?', (review_status, id))
        return self.scan(id, data_encoding=data_encoding)

    def _view(self, row):
        view = self._db.execute('SELECT * FROM scan_views WHERE scan_id=?', (row['id'],)).fetchone()
        return dict(view) if view else {'scan_id': row['id'], 'display': '{}', 'masking': 'exclude',
                                      'visible': 1, 'mask_history': '[]', 'mask_cursor': -1, 'mask_serial': 0}

    def _store_view(self, view):
        self._db.execute('''INSERT OR REPLACE INTO scan_views
            (scan_id,display,masking,visible,mask_history,mask_cursor,mask_serial) VALUES(?,?,?,?,?,?,?)''',
            tuple(view[key] for key in ('scan_id', 'display', 'masking', 'visible', 'mask_history', 'mask_cursor', 'mask_serial')))

    def _mask_bytes(self, row, view=None):
        view = self._view(row) if view is None else view
        meta = json.loads(row['metadata'])
        shape = (meta['height'], meta['width'])
        history = json.loads(view['mask_history'])
        revision = history[view['mask_cursor']] if view['mask_cursor'] >= 0 else None
        if revision is None:
            data = bytes((shape[0]*shape[1]+7)//8)
        else:
            data = bytes(self._db.execute('SELECT data FROM mask_revisions WHERE scan_id=? AND revision=?',
                                         (row['id'], revision)).fetchone()['data'])
        return data, shape, revision

    def _mask_array(self, row):
        data, shape, _ = self._mask_bytes(row)
        return np.unpackbits(np.frombuffer(data, dtype=np.uint8), count=shape[0]*shape[1]).reshape(shape).astype(bool)

    def _mask_detail(self, row):
        view = self._view(row)
        data, shape, revision = self._mask_bytes(row, view)
        count = int(np.unpackbits(np.frombuffer(data, dtype=np.uint8), count=shape[0]*shape[1]).sum())
        return {'width': shape[1], 'height': shape[0], 'count': count, 'revision': view['mask_serial'],
                'content_revision': revision, 'data_base64': base64.b64encode(data).decode('ascii'),
                'encoding': 'row-major numpy.packbits, big bit order', 'masking': view['masking'],
                'visible': bool(view['visible']), 'can_undo': view['mask_cursor'] >= 0,
                'can_redo': view['mask_cursor'] < len(json.loads(view['mask_history']))-1,
                'coordinate_frame': 'normalized_scan_footprint_pixel_centres'}

    def edit_mask(self, id, action, roi=None, points=None, radius=None, mode='add', lower=None, upper=None):
        """Edit a persistent selection, never source pixels or prior recipe masks."""
        from .view_state import edit_raster
        row = self._row(id)
        view = self._view(row)
        history = json.loads(view['mask_history'])
        if action in {'undo', 'redo'}:
            cursor = view['mask_cursor'] + (-1 if action == 'undo' else 1)
            if not -1 <= cursor < len(history):
                raise ValueError('No mask edit to ' + action + '.')
            view['mask_cursor'] = cursor
        else:
            array = self._array(row)[0] if action == 'threshold' else None
            edited = edit_raster(self._mask_array(row), action, roi=roi, points=points, radius=radius,
                                 mode=mode, lower=lower, upper=upper, array=array)
            revision = view['mask_serial']+1
            data = np.packbits(edited).tobytes()
            edit = {'action': action, 'roi': roi, 'points': points, 'radius_pixels': radius, 'mode': mode,
                    'lower': lower, 'upper': upper, 'origin': 'user-selection'}
            if action == 'threshold':
                edit['operations'] = json.loads(row['operations'])
            history = history[:view['mask_cursor']+1]+[revision]
            view['mask_history'] = _json(history)
            view['mask_cursor'] = len(history)-1
        view['mask_serial'] += 1
        with self._db:
            if action not in {'undo', 'redo'}:
                self._db.execute('INSERT INTO mask_revisions VALUES(?,?,?,?,?)', (id, revision, _now(), data, _json(edit)))
            self._store_view(view)
        return self._mask_detail(row)

    def update_mask(self, id, masking=None, visible=None):
        row = self._row(id)
        view = self._view(row)
        if masking is not None:
            if masking not in {'include', 'exclude', 'ignore'}:
                raise ValueError('Masking must be include, exclude or ignore.')
            view['masking'] = masking
        if visible is not None:
            if not isinstance(visible, bool):
                raise ValueError('Mask visibility must be true or false.')
            view['visible'] = int(visible)
        with self._db:
            self._store_view(view)
        return self._mask_detail(row)

    def _display(self, row):
        from .view_state import display_settings
        return display_settings(json.loads(self._view(row)['display']))

    def set_display(self, id, settings):
        from .view_state import display_settings
        row = self._row(id)
        view = self._view(row)
        validated = display_settings(settings)
        view['display'] = _json(validated)
        with self._db:
            self._store_view(view)
        return validated

    def display_range(self, id, mode='full', clip_percent=2, roi=None, raw=False, operations=None):
        from .view_state import range_info
        row = self._row(id)
        if not isinstance(raw, bool):
            raise ValueError('raw must be true or false.')
        if operations is not None:
            operations = self._resolve_operations(row, operations)
        array, _ = self._array(row, operations=operations, raw=raw)
        return range_info(array, mode=mode, clip_percent=clip_percent, roi=roi)

    def _resolve_operations(self, row, operations):
        self._validate_operations(operations)
        result = copy.deepcopy(operations)
        for op in result:
            if not isinstance(op, dict):
                raise ValueError('Every recipe operation must be an object.')
            use_saved = op.pop('use_saved_mask', False)
            if not isinstance(use_saved, bool):
                raise ValueError('use_saved_mask must be true or false.')
            if use_saved:
                if 'mask' in op:
                    raise ValueError('Specify a saved mask or an explicit mask, not both.')
                op['mask'] = self._mask_array(row).astype(np.uint8).tolist()
                op.setdefault('masking', self._view(row)['masking'])
        return result

    def _measurement_mask(self, row, mask, masking, use_saved_mask, default):
        if not isinstance(use_saved_mask, bool):
            raise ValueError('use_saved_mask must be true or false.')
        snapshot = None
        if use_saved_mask:
            if mask is not None:
                raise ValueError('Specify a saved mask or an explicit mask, not both.')
            mask = self._mask_array(row).astype(np.uint8).tolist()
            view = self._view(row)
            detail = self._mask_detail(row)
            snapshot = {key: detail[key] for key in ('revision', 'content_revision', 'count')}
            masking = view['masking'] if masking is None else masking
        return mask, default if masking is None else masking, snapshot

    def _measurement(self, row, kind, params, result):
        identifier = uuid.uuid4().hex
        result.update(id=identifier, scan_id=row['id'], value_unit=json.loads(row['metadata'])['value_unit'],
                      operations=json.loads(row['operations']), origin='deterministic-scientific-core',
                      scientific_backend=self.scientific_backend,
                      claim_status='computed-measurement', created_at=_now())
        with self._db:
            self._db.execute('INSERT INTO measurements VALUES(?,?,?,?,?,?,?)',
                             (identifier, row['id'], result['created_at'], kind, row['operations'], _json(params), _json(result)))
        return result

    def profile(self, id, start, end, samples=None, interpolation='linear', averaging_width_pixels=1,
                sampling='gwyddion', mask=None, masking=None, use_saved_mask=False):
        from .science import profile
        row = self._row(id)
        meta = json.loads(row['metadata'])
        array, _ = self._array(row)
        mask, masking, snapshot = self._measurement_mask(row, mask, masking, use_saved_mask, 'ignore')
        parameters = {'start': start, 'end': end, 'samples': samples, 'interpolation': interpolation,
                      'averaging_width_pixels': averaging_width_pixels, 'sampling': sampling,
                      'mask': mask, 'masking': masking}
        result = profile(array, meta['width_um'], meta['height_um'], **parameters)
        if snapshot is not None:
            result['saved_mask'] = snapshot
            parameters['saved_mask'] = snapshot
        return self._measurement(row, 'profile', parameters, result)

    def measure_area(self, id, roi=None, mask=None, masking=None, use_saved_mask=False):
        from .science import statistics
        row = self._row(id)
        array, _ = self._array(row)
        mask, masking, snapshot = self._measurement_mask(row, mask, masking, use_saved_mask, 'include')
        parameters = {'roi': roi, 'mask': mask, 'masking': masking}
        result = {'statistics': statistics(array, **parameters), **parameters, 'algorithm_version': '3.0.0'}
        if snapshot is not None:
            result['saved_mask'] = snapshot
            parameters['saved_mask'] = snapshot
        return self._measurement(row, 'area', parameters, result)

    def step_height(self, id, region_a, region_b, mask=None, masking=None, use_saved_mask=False):
        from .science import step_height
        row = self._row(id)
        array, _ = self._array(row)
        mask, masking, snapshot = self._measurement_mask(row, mask, masking, use_saved_mask, 'include')
        result = step_height(array, region_a, region_b, mask=mask, masking=masking)
        params = {'region_a': region_a, 'region_b': region_b, 'mask': mask, 'masking': masking}
        result.update(mask=mask, masking=masking)
        if snapshot is not None:
            result['saved_mask'] = snapshot
            params['saved_mask'] = snapshot
        return self._measurement(row, 'step_height', params, result)

    def _manifest(self, row, display=None):
        from .science import ALGORITHM_VERSION
        meta = json.loads(row['metadata'])
        result = {'schema': 'afm-workbench.scan.v1', 'scan': self._summary(row), 'metadata': meta,
                  'source_sha256': row['sha256'], 'source_artifact': row['source_artifact'],
                  'history': json.loads(row['history']), 'created_at': _now(),
                  'origin': 'synthetic' if self._session_row(row['session_id'])['synthetic'] else 'instrument',
                  'claim_status': 'computed-measurement', 'scientific_core_version': ALGORITHM_VERSION,
                  'scientific_backend': self.scientific_backend,
                  'environment': {'numpy': np.__version__},
                  'measurements': [json.loads(r['result']) for r in self._db.execute('SELECT result FROM measurements WHERE scan_id=? ORDER BY created_at', (row['id'],))],
                  'runs': [dict(r) for r in self._db.execute('SELECT id,created_at,operations,history,statistics FROM runs WHERE scan_id=? ORDER BY created_at', (row['id'],))]}
        for run in result['runs']:
            for key in ('operations', 'history', 'statistics'):
                run[key] = json.loads(run[key])
        result['mask'] = self._mask_detail(row)
        result['mask']['revisions'] = [dict(r) for r in self._db.execute(
            'SELECT revision,created_at,edit FROM mask_revisions WHERE scan_id=? ORDER BY revision', (row['id'],))]
        for revision in result['mask']['revisions']:
            revision['edit'] = json.loads(revision['edit'])
        result['display'] = {'settings': display if display is not None else self._display(row),
                             'purpose': 'Display only; does not transform numerical data.'}
        return result

    def export_scan(self, id, format='json', display=None):
        row = self._row(id)
        manifest = self._manifest(row, display)
        name = _safe_name(Path(row['filename']).stem)
        if display and display.get('preview'):
            raise ValueError('Keep or discard the preview before exporting numerical data or provenance.')
        raw = bool(display and display.get('raw'))
        if format == 'json':
            manifest['exported_view'] = 'original' if raw else 'processed'
            content = json.dumps(_clean(manifest), indent=2, ensure_ascii=False, allow_nan=False)
            result = {'filename': name + '.provenance.json', 'content': content, 'mime': 'application/json'}
        elif format == 'csv':
            array, _ = self._array(row, raw=raw)
            meta = json.loads(row['metadata'])
            output = io.StringIO()
            header = '\n'.join(['AFM Workbench calibrated numerical matrix',
                                'value_unit=' + meta['value_unit'], 'width_um=' + str(meta['width_um']),
                                'height_um=' + str(meta['height_um']), 'source_sha256=' + row['sha256'],
                                'view=' + ('original' if raw else 'processed'),
                                'operations=' + ('[]' if raw else row['operations']),
                                'orientation=' + _json(meta.get('orientation')), 'missing_values=nan'])
            np.savetxt(output, array, delimiter=',', fmt='%.17g', header=header)
            result = {'filename': name + ('.original.csv' if raw else '.csv'), 'content': output.getvalue(), 'mime': 'text/csv'}
        else:
            raise ValueError('Export format must be csv or json.')
        with self._db:
            self._db.execute('INSERT INTO exports VALUES(?,?,?,?,?,?)', (uuid.uuid4().hex, id, row['session_id'], _now(), format, _json(manifest)))
        return result

    def export_session(self, id):
        session = self.session(id)
        manifest = {'schema': 'afm-workbench.session.v1', 'created_at': _now(), 'session': session,
                    'scans': [self._manifest(row) for row in self._db.execute('SELECT * FROM scans WHERE session_id=? ORDER BY filename,id', (id,))],
                    'note': 'Provenance manifest. Full-resolution array dimensions, calibration and recipes are included; source data and numerical arrays are not embedded.'}
        with self._db:
            self._db.execute('INSERT INTO exports VALUES(?,?,?,?,?,?)', (uuid.uuid4().hex, None, id, _now(), 'session-json', _json(manifest)))
        return {'filename': _safe_name(session['name']) + '.session.json', 'content': json.dumps(_clean(manifest), indent=2, ensure_ascii=False, allow_nan=False), 'mime': 'application/json'}

    def search_scans(self, query=''):
        query = str(query).casefold()
        result = []
        for row in self._db.execute('SELECT * FROM scans ORDER BY session_id,filename'):
            summary = self._summary(row)
            session = self._session_row(row['session_id'])
            if query in ' '.join(str(summary.get(k, '')) for k in ('filename', 'channel', 'direction', 'acquisition')).casefold() or query in (session['name'] + ' ' + session['notes']).casefold():
                result.append(summary)
        return {'scans': result}

    # Display-only browse leveling for unprocessed height thumbnails. Uses the
    # same recipe implementation as explicit corrections; nothing is saved.
    BROWSE_LEVELING = ({'type': 'align_scan', 'method': 'median', 'axis': 'auto'},
                       {'type': 'plane', 'method': 'gwyddion'})

    def _browse_levelable(self, row):
        meta = json.loads(row['metadata'])
        channel = (meta.get('channel') or '').lower()
        return (not json.loads(row['operations']) and meta.get('value_unit') == 'nm'
                and 'error' not in channel and any(name in channel for name in ('height', 'topograph')))

    def thumbnail(self, id, recipe=True, palette=None, contrast=None, level=False):
        with self._lock:
            row = self._row(id)
            key = (row['array_artifact'], row['metadata'], row['operations'] if recipe else '[]',
                   self._view(row)['display'], bool(recipe), palette, contrast, bool(level))
            cached = self._thumbnails.get(key)
            if cached is not None:
                return cached
            leveled = False
            if recipe and level and self._browse_levelable(row):
                # Without a recorded scan axis, line alignment refuses; fall back to the plane alone.
                for recipe_ops in (self.BROWSE_LEVELING, self.BROWSE_LEVELING[1:]):
                    try:
                        array, _ = self._array(row, operations=[dict(op) for op in recipe_ops])
                        leveled = True
                        break
                    except (ValueError, RuntimeError):
                        continue
                else:
                    array, _ = self._array(row, raw=not recipe)
            else:
                array, _ = self._array(row, raw=not recipe)
            settings = self._display(row)
            palette = palette or settings['palette']
            if leveled and contrast is None:
                # Saved manual limits describe the stored data, not this leveled view.
                contrast = 'auto'
            if contrast is None and settings['mode'] == 'manual':
                lo, hi = settings['minimum'], settings['maximum']
            else:
                from .view_state import range_info
                mode = ('percentile' if contrast == 'auto' else 'full') if contrast is not None else settings['mode']
                limits = range_info(array, mode=mode, clip_percent=2 if contrast == 'auto' else settings['clip_percent'])
                lo, hi = limits['minimum'], limits['maximum']
            array = array[::max(1, math.ceil(array.shape[0] / 384)), ::max(1, math.ceil(array.shape[1] / 384))]
            valid = array[np.isfinite(array)]
            if valid.size == 0:
                raise ValueError('Image contains no finite values.')
            fraction = np.clip((np.nan_to_num(array, nan=lo) - lo) / (hi - lo if hi > lo else 1), 0, 1)
            palettes = {
                'amber': [(26, 21, 18), (79, 49, 29), (151, 105, 57), (221, 181, 117), (255, 245, 216)],
                'viridis': [(68, 1, 84), (59, 82, 139), (33, 145, 140), (94, 201, 98), (253, 231, 37)],
                'gray': [(15, 20, 18), (248, 250, 247)],
            }
            colors = np.array(palettes.get(palette, palettes['amber']))
            rgb = np.stack([np.interp(fraction, np.linspace(0, 1, len(colors)), colors[:, channel]) for channel in range(3)], axis=-1).astype(np.uint8)
            rgb[~np.isfinite(array)] = (168, 177, 158)
            image = Image.fromarray(rgb)
            output = io.BytesIO()
            image.save(output, format='PNG')
            png = output.getvalue()
            self._thumbnails.put(key, png, len(png))
            return png

    def demo(self):
        source = 'synthetic://afm-workbench/demo-v1'
        existing = self._db.execute('SELECT id FROM sessions WHERE source_path=?', (source,)).fetchone()
        if existing:
            return self.session(existing['id'])
        identifier = uuid.uuid4().hex
        y, x = np.mgrid[0:256, 0:256] / 255
        rng = np.random.default_rng(260824)
        with self._db:
            self._db.execute('INSERT INTO sessions(id,name,source_path,imported_at,notes,synthetic) VALUES(?,?,?,?,?,1)',
                             (identifier, 'Terraces & islands · example', source, _now(),
                              'Synthetic AFM session: two positions, height and phase, forward and backward. Explore analysis without touching experimental data.'))
            for acquisition, x_pos, y_pos in [('001', 0., 0.), ('002', 4.5, 2.5)]:
                islands = sum(12 * np.exp(-((x-a)**2 + (y-b)**2) / r) for a,b,r in [(0.25,.3,.008),(.7,.65,.015),(.65,.22,.003)])
                height = islands + 4*(x > .48+.07*np.sin(y*9)) + x*2-y + .15*rng.standard_normal(x.shape)
                if acquisition == '002':
                    height = 8*np.sin(x*14+y*3)**2 + 3*y + .2*rng.standard_normal(x.shape)
                for channel, unit in [('Z Height', 'nm'), ('NCM Phase', '°')]:
                    for direction in ('Forward', 'Backward'):
                        array = height if channel == 'Z Height' else height * 2 + 5*np.sin(y*8)
                        array = array + (0.12 if direction == 'Backward' else 0.)
                        filename = f'{acquisition}__synthetic_{channel}_{direction}.tiff'
                        metadata = {'channel': channel, 'direction': direction, 'acquisition': acquisition,
                                    'width_um': 5., 'height_um': 5., 'width': 256, 'height': 256,
                                    'value_unit': unit, 'instrument': 'Synthetic example',
                                    'position': {'x_um':x_pos,'y_um':y_pos,'reference':'center','rotation_deg':0.,'calibrated':True},
                                    'x_offset_um':x_pos,'y_offset_um':y_pos,'scan_angle_deg':0.,
                                    'calibration': {'scale': 1., 'offset': 0., 'source': 'Deterministic synthetic generator v1'},
                                    'orientation': {'array_rows': 'top to bottom', 'array_columns': 'left to right', 'display': 'stored array'},
                                    'warnings': [], 'original_metadata': {'origin': 'synthetic', 'seed':260824}}
                        digest = hashlib.sha256(array.tobytes()).hexdigest()
                        self._insert_scan(identifier, filename, digest, array, metadata)
        return self.session(identifier)
