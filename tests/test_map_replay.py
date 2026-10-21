import json
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
from PIL import Image
from harness.replay import inspect


class MapReplayTests(unittest.TestCase):
    def records(self, with_transform=True):
        q=NS(x=0,y=0,z=math.sin(math.pi/4),w=math.cos(math.pi/4))
        def message(topic,value,sequence):
            return None,NS(topic=topic),NS(sequence=sequence,log_time=100),value
        if with_transform:
            yield message('/tf',NS(transforms=[NS(header=NS(frame_id='map'),child_frame_id='odom',
                transform=NS(rotation=q,translation=NS(x=2,y=3)))]),0)
        yield message('/map',NS(header=NS(frame_id='map',stamp=NS(sec=1,nanosec=2)),
            info=NS(width=2,height=2,resolution=.05,origin=NS(position=NS(x=-1,y=-2),orientation=q)),
            data=[0,100,-1,50]),1)

    def test_map_image_orientation_and_context_transform(self):
        with tempfile.TemporaryDirectory() as directory,patch('harness.replay.messages',return_value=self.records()):
            root=Path(directory);report=inspect(root,export=True)
            info=json.loads((root/'map.json').read_text())
            self.assertTrue(info['alignment_available']);self.assertEqual(info['odom_to_map'][:2],[2,3])
            self.assertAlmostEqual(info['odom_to_map'][2],math.pi/2)
            self.assertAlmostEqual(info['origin'][2],math.pi/2)
            with Image.open(root/'map.png') as image:self.assertEqual(list(image.tobytes()),[225,145,250,42])
            self.assertEqual(report['topics'],{'/map':1})

    def test_missing_transform_is_not_assumed_identity(self):
        with tempfile.TemporaryDirectory() as directory,patch('harness.replay.messages',return_value=self.records(False)):
            inspect(directory,export=True)
            info=json.loads((Path(directory)/'map.json').read_text())
            self.assertFalse(info['alignment_available']);self.assertIsNone(info['odom_to_map'])
