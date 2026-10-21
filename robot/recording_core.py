"""Bounded, asynchronous MCAP spool. No camera bytes are ever written here."""
from concurrent.futures import Future
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shutil
import struct
import threading
import time
import uuid

from mcap.writer import Writer, CompressionType


ID = re.compile(r'^[A-Za-z0-9_-]{1,100}$')
GIB = 1024 ** 3


def utc():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    sync_directory(path.parent)


def sync_directory(path):
    descriptor = os.open(str(path), os.O_RDONLY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)


def digest_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''): digest.update(data)
    return digest.hexdigest()


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError('Invalid recording identifier')
    return value


def string_cdr(value):
    data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode() + b'\0'
    return b'\x00\x01\x00\x00' + struct.pack('<I', len(data)) + data


class McapSink:
    def __init__(self, path):
        self.path = Path(path)
        self.stream = self.path.open('xb')
        self.writer = Writer(self.stream, chunk_size=64 * 1024,
                             compression=CompressionType.ZSTD, enable_crcs=True,
                             enable_data_crcs=True)
        self.writer.start(profile='ros2', library='Limo Console')
        self.channels = {}

    def write(self, topic, typename, definition, data, stamp, sequence):
        key = (topic, typename, definition)
        if key not in self.channels:
            schema = self.writer.register_schema(typename, 'ros2msg', definition.encode())
            self.channels[key] = self.writer.register_channel(topic, 'cdr', schema)
        self.writer.add_message(self.channels[key], stamp, data,
                                publish_time=stamp, sequence=sequence % (2**32))

    def close(self):
        self.writer.finish()
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.stream.close()


class Recorder:
    """Single ordered writer; boundaries never restart subscriptions or motion."""
    def __init__(self, root, *, reserve_bytes=2*GIB, max_spool_bytes=2*GIB,
                 chunk_bytes=64*1024**2, chunk_seconds=10, queue_bytes=32*1024**2,
                 sink_factory=McapSink, disk_usage=shutil.disk_usage):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.reserve = reserve_bytes
        self.max_spool = max_spool_bytes
        self.chunk_limit, self.chunk_seconds = chunk_bytes, chunk_seconds
        self.queue_limit = queue_bytes
        self.sink_factory, self.disk_usage = sink_factory, disk_usage
        self.lock = threading.RLock()
        self.jobs = queue.Queue()
        self.pending_bytes = 0
        self.session = self.instance = self.sink = None
        self.active = False
        self.writer_ready = False
        self.last_progress = time.monotonic()
        self.error = ''
        self.dropped = 0
        self.sequence = 0
        self.received = Counter()
        self.written = Counter()
        self.requests = {}
        self.latest = {}
        self.chunks = {}
        self.completed = []
        self.instance_number=0
        self.ingress_instance=None
        self.pc_at = float('-inf')
        self.pc_ok = False
        self.owner = None
        self.free_bytes = self.disk_usage(self.root).free
        self.spool_bytes = 0
        self._load_existing()
        self.worker = threading.Thread(target=self._work, daemon=True, name='mcap-writer')
        self.worker.start()

    def _load_existing(self):
        for path in self.root.glob('*/*/*.manifest.json'):
            try:
                manifest = json.loads(path.read_text())
                name = identifier(manifest['chunk_id'])
                self.chunks[name] = manifest
                retained = path.with_name(name+'.mcap')
                if manifest.get('deleted') and retained.is_file() and not retained.is_symlink():
                    if digest_file(retained) == manifest['sha256']:
                        retained.unlink()
            except (OSError, ValueError, KeyError): continue
        # Preserve interrupted streams for offline salvage, never silently delete them.
        for path in self.root.glob('*/*/*.partial.mcap'):
            marker = path.with_suffix('.interrupted.json')
            if not marker.exists(): atomic_json(marker, {'status': 'interrupted', 'file': path.name, 'detected_at': utc()})

    def fault(self, reason):
        with self.lock:
            self.error = str(reason)
            self.pc_ok = False

    def capacity(self):
        free = self.disk_usage(self.root).free
        used = 0
        for path in self.root.glob('*/*/*'):
            try:
                if path.is_file(): used += path.stat().st_size
            except FileNotFoundError: pass
        with self.lock:
            self.free_bytes, self.spool_bytes = free, used
            if self.active and (free < self.reserve or used >= self.max_spool):
                self.error = 'Robot recording storage is full'
        return free >= self.reserve and used < self.max_spool

    def heartbeat(self, owner, healthy):
        with self.lock:
            if owner != self.owner or not self.active: raise ValueError('Recording owner mismatch')
            self.pc_at = time.monotonic()
            self.pc_ok = healthy is True

    def snapshot(self):
        with self.lock:
            healthy = self.active and self.writer_ready and not self.error and time.monotonic()-self.last_progress < 2
            ready = healthy and self.pc_ok and time.monotonic()-self.pc_at < .75
            return dict(active=self.active, ready=bool(ready), error=self.error,
                        session_id=self.session, instance_id=self.instance,
                        queue_bytes=self.pending_bytes, dropped=self.dropped,
                        received=dict(self.received), written=dict(self.written),
                        free_bytes=self.free_bytes, spool_bytes=self.spool_bytes,
                        sequence=self.sequence, pending_chunks=sum(not c.get('deleted') for c in self.chunks.values()))

    def _command(self, action, payload):
        future = Future()
        with self.lock:
            payload = dict(payload, boundary=dict(monotonic_ns=time.monotonic_ns(), wall_ns=time.time_ns(), sequence=self.sequence))
            if action in ('start', 'finish'): self.active = False; self.pc_ok = False
            self.jobs.put((action, payload, future))
        return future.result(timeout=20)

    def start(self, request_id, owner, metadata=None):
        identifier(request_id); identifier(owner)
        with self.lock:
            if request_id in self.requests: return self.requests[request_id]
            if self.active and time.monotonic()-self.pc_at < .75:
                raise ValueError('Another recorder is active')
        if not self.capacity(): raise ValueError('Robot recording storage is full')
        return self._command('start', dict(request_id=request_id, owner=owner, metadata=metadata or {}))

    def split(self, request_id, owner, name=''):
        identifier(request_id)
        if not isinstance(name, str) or len(name)>120: raise ValueError('Instance name is too long')
        with self.lock:
            if request_id in self.requests: return self.requests[request_id]
            if owner != self.owner or not self.active or self.error: raise ValueError('Recording is not ready')
            self.instance_number+=1
            boundary=dict(session_id=self.session,previous_instance_id=self.ingress_instance,
                          instance_id=f'{self.instance_number:04d}_{uuid.uuid4().hex[:12]}',name=name,
                          monotonic_ns=time.monotonic_ns(),wall_ns=time.time_ns(),sequence=self.sequence,started_at=utc())
            self.ingress_instance=boundary['instance_id']
            self.requests[request_id]=dict(boundary)
            # The ordered ingress boundary is established immediately. Disk closure
            # belongs to the writer; never hold the PC's frame/heartbeat loop for fsync.
            self.jobs.put(('split',dict(request_id=request_id,name=name,boundary=boundary),Future()))
            return dict(boundary)

    def finish(self, owner, interrupted=False):
        if owner != self.owner: raise ValueError('Recording owner mismatch')
        return self._command('finish', {'interrupted':bool(interrupted)})

    def append(self, topic, typename, definition, data, *, latched=False):
        # Source samples are serialized ROS messages. Image streams are prohibited.
        if typename in ('sensor_msgs/msg/Image', 'sensor_msgs/msg/CompressedImage'):
            return False
        stamp, mono = time.time_ns(), time.monotonic_ns()
        payload = (topic, typename, definition, bytes(data), stamp, mono)
        with self.lock:
            if latched: self.latest[topic] = payload
            if not self.active or self.error: return False
            if self.pending_bytes+len(data) > self.queue_limit:
                self.dropped += 1
                self.error = 'Recording queue overflow'
                return False
            self.sequence += 1
            self.received[topic] += 1
            self.pending_bytes += len(data)
            self.jobs.put(('sample', (self.sequence, payload), None))
        return True

    def event(self, name, data):
        return self.append('/console/recording_events', 'std_msgs/msg/String', 'string data\n',
                           string_cdr(dict(event=name, data=data, monotonic_ns=time.monotonic_ns(), wall_ns=time.time_ns())))

    def _open(self):
        self.chunk_id = uuid.uuid4().hex
        folder = self.root / self.session / self.instance
        folder.mkdir(parents=True, exist_ok=True)
        self.partial = folder / (self.chunk_id + '.partial.mcap')
        self.sink = self.sink_factory(self.partial)
        self.chunk_started = time.monotonic()
        self.chunk_uncompressed = 0
        self.chunk_count = Counter()
        self.chunk_first = self.chunk_last = None
        with self.lock: context = list(self.latest.values())
        for payload in context:
            topic, typename, definition, data, stamp, mono = payload
            # Repeated latched calibration is explicitly marked, not a new source sample.
            self.sink.write(topic, typename, definition, data, stamp, 0)
        self.sink.write('/console/chunk', 'std_msgs/msg/String', 'string data\n',
                        string_cdr(dict(session_id=self.session, instance_id=self.instance,
                                        chunk_id=self.chunk_id, context_topics=list(self.latest))),time.time_ns(),0)

    def _close(self):
        if self.sink is None: return
        self.sink.close()
        self.sink = None
        final = self.partial.with_name(self.chunk_id+'.mcap')
        os.replace(self.partial, final)
        sync_directory(final.parent)
        manifest = dict(version=1, chunk_id=self.chunk_id, session_id=self.session,
                        instance_id=self.instance, filename=final.name, bytes=final.stat().st_size,
                        sha256=digest_file(final), counts=dict(self.chunk_count),
                        first_sequence=self.chunk_first,last_sequence=self.chunk_last,
                        closed_at=utc(), deleted=False)
        atomic_json(final.with_suffix('.manifest.json'), manifest)
        with self.lock: self.chunks[self.chunk_id] = manifest

    def _new_instance(self, name='', captured=None):
        old = self.instance
        self.instance = (captured or {}).get('instance_id') or f'{len(self.completed)+1:04d}_{uuid.uuid4().hex[:12]}'
        boundary = dict(session_id=self.session, previous_instance_id=old,
                        instance_id=self.instance, name=name, monotonic_ns=time.monotonic_ns(),
                        wall_ns=time.time_ns(), sequence=self.sequence, started_at=utc())
        if captured: boundary.update(captured)
        self.boundary = boundary
        self._open()
        self.writer_ready = True
        atomic_json(self.partial.parent/'instance.json',dict(boundary,status='recording'))
        return dict(boundary)

    def _end_instance(self, status, boundary=None):
        if not self.instance: return
        self._close()
        path = self.root/self.session/self.instance/'instance.json'
        value = json.loads(path.read_text())
        value.update(status=status, ended_at=utc(), end_monotonic_ns=(boundary or {}).get('monotonic_ns',time.monotonic_ns()),
                     end_sequence=(boundary or {}).get('sequence',self.sequence))
        value['chunk_ids']=[c['chunk_id'] for c in self.chunks.values()
                            if c['session_id']==self.session and c['instance_id']==self.instance]
        atomic_json(path,value)
        self.completed.append(self.instance)

    def _work(self):
        while True:
            try: action, payload, future = self.jobs.get(timeout=.25)
            except queue.Empty:
                self.last_progress = time.monotonic()
                if self.active and self.sink and time.monotonic()-self.chunk_started>=self.chunk_seconds:
                    try: self._close(); self._open()
                    except Exception as exc: self.fault(exc)
                continue
            try:
                if action == 'sample':
                    sequence, sample = payload
                    topic, typename, definition, data, stamp, mono = sample
                    with self.lock: self.pending_bytes -= len(data)
                    if self.sink is not None:
                        self.sink.write(topic,typename,definition,data,stamp,sequence)
                        self.chunk_uncompressed += len(data)
                        self.chunk_count[topic] += 1
                        self.chunk_first = sequence if self.chunk_first is None else self.chunk_first
                        self.chunk_last = sequence
                        with self.lock: self.written[topic] += 1
                        if self.chunk_uncompressed>=self.chunk_limit or time.monotonic()-self.chunk_started>=self.chunk_seconds:
                            self._close();self._open()
                else:
                    # The writer owns file lifecycle. Ingress keeps queueing during fsync.
                    request = payload.get('request_id')
                    if action!='split' and request in self.requests:
                        result = self.requests[request]
                    elif action == 'start':
                        if self.sink: self._end_instance('interrupted')
                        self.session = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_')+uuid.uuid4().hex[:8]
                        self.instance = None; self.completed=[]
                        self.error='';self.dropped=0;self.sequence=0
                        self.received.clear();self.written.clear()
                        self.owner=payload['owner'];self.pc_ok=False
                        (self.root/self.session).mkdir()
                        atomic_json(self.root/self.session/'session.json',dict(version=1,session_id=self.session,started_at=utc(),metadata=payload['metadata']))
                        result=self._new_instance();self.instance_number=1;self.ingress_instance=self.instance;self.active=True
                    elif action == 'split':
                        self._end_instance('complete',payload['boundary'])
                        result=self._new_instance(payload['name'],payload['boundary'])
                    elif action == 'finish':
                        self._end_instance('interrupted' if self.error or payload.get('interrupted') else 'complete',payload['boundary'])
                        self.active=False;self.pc_ok=False;self.writer_ready=False
                        result={'session_id':self.session,'status':'finished'}
                    else: raise ValueError('Unknown recorder command')
                    if request:self.requests[request]=result
                    future.set_result(result)
            except Exception as exc:
                self.fault(exc)
                if future: future.set_exception(exc)
            finally:
                self.last_progress=time.monotonic()
                self.jobs.task_done()

    def list_chunks(self):
        with self.lock: return [dict(value) for value in self.chunks.values() if not value.get('deleted')]

    def chunk_path(self, chunk_id):
        identifier(chunk_id)
        with self.lock: info=self.chunks.get(chunk_id)
        if not info or info.get('deleted'): raise ValueError('Chunk unavailable')
        path=self.root/identifier(info['session_id'])/identifier(info['instance_id'])/info['filename']
        if path.is_symlink() or not path.is_file():raise ValueError('Chunk unavailable')
        return path

    def acknowledge(self, chunk_id, sha256, size):
        identifier(chunk_id)
        with self.lock:
            info=self.chunks.get(chunk_id)
            if not info or info['sha256']!=sha256 or info['bytes']!=size:
                raise ValueError('Archive checksum or size mismatch')
            if info.get('deleted'):return {'deleted':True,'chunk_id':chunk_id}
            path=self.chunk_path(chunk_id)
            # A receipt is durable before removal; retry after interruption is safe.
            receipt=dict(info,archived_at=utc(),deleted=True)
            atomic_json(path.with_suffix('.manifest.json'),receipt)
            path.unlink();sync_directory(path.parent)
            self.chunks[chunk_id]=receipt
        return {'deleted':True,'chunk_id':chunk_id}
