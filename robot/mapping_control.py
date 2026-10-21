"""Stationary SLAM lifecycle and portable map export; no movement goals are sent."""
import io
import re
import subprocess
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path


def map_paths(directory, name):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', name):
        raise ValueError('Map names must use 1–64 letters, numbers, underscores, or hyphens.')
    root = Path(directory).resolve()
    paths = [root / (name + ext) for ext in ('.yaml', '.pgm')]
    if any(p.is_symlink() or p.resolve().parent != root for p in paths):
        raise ValueError('Invalid map path.')
    return paths


def export_map(directory, name):
    metadata, image = map_paths(directory, name)
    if not metadata.is_file() or not image.is_file():
        raise ValueError('Map files are incomplete or missing.')
    if metadata.stat().st_size > 65536 or image.stat().st_size > 20 * 1024 * 1024:
        raise ValueError('Map files are too large for direct download.')
    contents = metadata.read_text()
    contents, count = re.subn(r'^image\s*:.*$', 'image: '+name+'.pgm', contents, flags=re.M)
    if count != 1:
        raise ValueError('Map metadata has no valid image path.')
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name+'.yaml', contents)
        archive.writestr(name+'.pgm', image.read_bytes())
    return output.getvalue()


class MappingControl:
    def __init__(self, navigation, lock, workspace='/control', runner=subprocess.run):
        self.navigation, self.lock = navigation, lock
        self.workspace = Path(workspace)
        self.maps = self.workspace / 'maps'
        self.runner = runner
        self.busy = False
        self.operation = 'idle'
        self.message = 'Start mapping, then drive slowly to explore the space.'
        self.error = ''
        self.last_saved = None
        self.started_at = None

    def fresh(self):
        return self.navigation.grid is not None and time.monotonic()-self.navigation.last_map < 10

    def status(self):
        active = self.fresh()
        waiting = self.started_at is not None and not active and time.monotonic()-self.started_at < 25
        message, error = self.message, self.error
        if self.started_at is not None and not active and not waiting and not self.busy:
            message = error = 'No map received. Check lidar or retry mapping.'
        elif active and not self.busy and not error:
            message = 'Map updating live. Drive manually to expand coverage.'
        grid = self.navigation.grid
        return dict(active=active, busy=self.busy, waiting=waiting,
                    operation=self.operation, message=message, error=error,
                    last_saved=self.last_saved,
                    revision=self.navigation.revision,
                    map=dict(width=grid['width'], height=grid['height'], resolution=grid['resolution']) if grid else None)

    def list_maps(self):
        self.maps.mkdir(exist_ok=True)
        result = []
        for metadata in self.maps.glob('*.yaml'):
            try:
                paths = map_paths(self.maps, metadata.stem)
                if all(p.is_file() for p in paths):
                    result.append(dict(name=metadata.stem, modified=metadata.stat().st_mtime,
                                       bytes=sum(p.stat().st_size for p in paths)))
            except ValueError:
                continue
        return sorted(result, key=lambda item: item['modified'], reverse=True)

    def new_name(self):
        return 'map_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')

    def command(self, *arguments):
        result = self.runner(['bash', str(self.workspace / 'manage.sh'), *arguments],
                             capture_output=True, text=True, timeout=40)
        if result.returncode:
            detail = (result.stderr or result.stdout or 'Service did not start')[-240:].strip()
            raise ValueError('Mapping operation failed: '+detail)

    def save(self, name):
        paths = map_paths(self.maps, name)
        if any(p.exists() for p in paths):
            raise ValueError('That map name already exists. Choose a new name.')
        self.command('save', name)
        if not all(p.is_file() and p.stat().st_size for p in paths):
            raise ValueError('Map save did not produce complete files. Please retry.')
        with self.lock:
            self.last_saved = name

    def request(self, action, name=None, backend=None):
        if self.busy or self.navigation.preparing:
            raise ValueError('A mapping operation is in progress. Please wait.')
        if action not in ('start', 'save', 'stop'):
            raise ValueError('Unknown mapping operation.')
        if backend is not None and backend not in ('cartographer', 'slam_toolbox'):
            raise ValueError('Unsupported mapping engine.')
        if action == 'start' and (self.fresh() or self.status()['waiting']):
            return
        if action == 'save' and not self.fresh():
            raise ValueError('Start mapping and wait for a map before saving.')
        should_save = action == 'save' or (action == 'stop' and self.fresh())
        if should_save:
            name = name or self.new_name()
            paths = map_paths(self.maps, name)
            if any(p.exists() for p in paths):
                raise ValueError('That map name already exists. Choose a new name.')
        self.busy = self.navigation.preparing = True
        self.operation = action
        self.error = ''
        self.message = {'start': 'Starting mapping. Waiting for the first map…',
                        'save': 'Saving map…', 'stop': 'Saving and finishing mapping…'}[action]
        if action == 'start':
            self.navigation.grid = self.navigation.png = None
            self.navigation.last_map = float('-inf')
            self.started_at = time.monotonic()

        def work():
            try:
                if action == 'start':
                    self.command('map-start', backend or 'cartographer')
                    message = 'Mapping started. Waiting for the map…'
                else:
                    if should_save:
                        self.save(name)
                    if action == 'stop':
                        self.command('map-stop')
                        with self.lock:
                            self.navigation.last_map = float('-inf')
                            self.started_at = None
                    message = ('Map saved: '+name) if should_save else 'Mapping finished.'
                    if action == 'stop' and should_save:
                        message += '; mapping finished.'
                with self.lock:
                    self.message = message
            except Exception as exc:
                with self.lock:
                    self.error = str(exc)
                    self.message = self.error
                    if action == 'start':
                        self.started_at = None
            finally:
                with self.lock:
                    self.busy = self.navigation.preparing = False
                    self.operation = 'idle'
        threading.Thread(target=work, daemon=True).start()
