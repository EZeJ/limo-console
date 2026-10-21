import io
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'robot'))
from mapping_control import MappingControl, export_map, map_paths


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.maps = self.root / 'maps'; self.maps.mkdir()
        self.nav = SimpleNamespace(grid={'width':10,'height':10,'resolution':.05},
                                   last_map=time.monotonic(), revision=1, preparing=False)

    def create_map(self, name):
        (self.maps / (name+'.yaml')).write_text('image: /control/maps/'+name+'.pgm\nresolution: 0.05\norigin: [0, 0, 0]\n')
        (self.maps / (name+'.pgm')).write_bytes(b'P5\n1 1\n255\n\xff')

    def wait(self, control):
        until=time.monotonic()+2
        while control.busy and time.monotonic()<until:time.sleep(.005)
        self.assertFalse(control.busy)

    def test_download_is_portable_and_does_not_change_original(self):
        self.create_map('room')
        with zipfile.ZipFile(io.BytesIO(export_map(self.maps, 'room'))) as archive:
            self.assertEqual(set(archive.namelist()), {'room.yaml','room.pgm'})
            self.assertIn('image: room.pgm', archive.read('room.yaml').decode())
        self.assertIn('/control/maps/', (self.maps/'room.yaml').read_text())

    def test_traversal_and_symlinks_rejected(self):
        for name in ('../secret', '/tmp/a', '', 'a/b', 'a;cmd'):
            with self.subTest(name=name), self.assertRaises(ValueError):map_paths(self.maps,name)
        (self.maps/'escape.yaml').symlink_to(self.root/'outside.yaml')
        with self.assertRaises(ValueError):map_paths(self.maps,'escape')

    def test_failed_save_keeps_mapping_running(self):
        calls=[]
        def run(args, **kwargs):
            calls.append(args);return SimpleNamespace(returncode=1,stderr='save failed',stdout='')
        control=MappingControl(self.nav,threading.RLock(),self.root,run)
        control.request('stop');self.wait(control)
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0][-2],'save')
        self.assertTrue(control.error)
        self.assertTrue(control.fresh())

    def test_stop_saves_before_stopping_slam(self):
        calls=[]
        def run(args, **kwargs):
            calls.append(args)
            if args[-2]=='save':self.create_map(args[-1])
            return SimpleNamespace(returncode=0,stderr='',stdout='')
        control=MappingControl(self.nav,threading.RLock(),self.root,run)
        control.request('stop');self.wait(control)
        self.assertEqual(calls[0][-2],'save')
        self.assertEqual(calls[1][-1],'map-stop')
        self.assertIsNotNone(control.last_saved)
        self.assertFalse(control.fresh())

    def test_duplicate_name_cannot_overwrite_existing_map(self):
        self.create_map('room')
        control=MappingControl(self.nav,threading.RLock(),self.root)
        with self.assertRaises(ValueError):control.request('save',name='room')
        self.assertFalse(control.busy)


if __name__=='__main__':unittest.main()
