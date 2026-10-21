import json
from pathlib import Path
import sys
import tempfile
import time
import threading
import unittest
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'robot'))
from recording_core import Recorder,string_cdr,digest_file
from mcap.reader import make_reader


class RecordingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.r=Recorder(self.temp.name,reserve_bytes=1,max_spool_bytes=10000000,chunk_seconds=300)
        self.first=self.r.start('start','owner')
    def tearDown(self):
        if self.r.active:self.r.finish('owner')
        self.temp.cleanup()
    def sample(self,i):
        self.assertTrue(self.r.append('/sample','std_msgs/msg/String','string data\n',string_cdr({'i':i})))
    def messages(self):
        result=[]
        for chunk in self.r.list_chunks():
            with self.r.chunk_path(chunk['chunk_id']).open('rb') as stream:
                for schema,channel,msg in make_reader(stream).iter_messages():
                    if channel.topic=='/sample': result.append((chunk['instance_id'],msg.sequence,json.loads(msg.data[8:-1])['i']))
        return result
    def test_split_is_idempotent_and_partitions_samples_exactly(self):
        for i in range(30):self.sample(i)
        second=self.r.split('next','owner')
        self.assertEqual(second,self.r.split('next','owner'))
        for i in range(30,60):self.sample(i)
        self.r.finish('owner')
        rows=self.messages()
        self.assertEqual(sorted(r[2] for r in rows),list(range(60)))
        self.assertEqual(len({r[1] for r in rows}),60)
        self.assertTrue(all(row[0]==self.first['instance_id'] for row in rows if row[2]<30))
        self.assertTrue(all(row[0]==second['instance_id'] for row in rows if row[2]>=30))
    def test_ack_requires_checksum_and_size_before_deleting(self):
        self.sample(1);self.r.split('cut','owner')
        self.r.jobs.join()
        item=self.r.list_chunks()[0];path=self.r.chunk_path(item['chunk_id'])
        with self.assertRaises(ValueError):self.r.acknowledge(item['chunk_id'],'wrong',item['bytes'])
        self.assertTrue(path.exists())
        self.r.acknowledge(item['chunk_id'],item['sha256'],item['bytes'])
        self.assertFalse(path.exists())
        self.assertTrue(self.r.acknowledge(item['chunk_id'],item['sha256'],item['bytes'])['deleted'])
    def test_no_images_written_to_robot(self):
        self.assertFalse(self.r.append('/image','sensor_msgs/msg/Image','',b'private image'))
        self.r.finish('owner')
        self.assertEqual(self.r.snapshot()['received'],{})
    def test_recording_readiness_requires_fresh_computer_heartbeat(self):
        self.assertFalse(self.r.snapshot()['ready'])
        self.r.heartbeat('owner',True)
        self.assertTrue(self.r.snapshot()['ready'])
        self.r.pc_at-=1
        self.assertFalse(self.r.snapshot()['ready'])
    def test_overflow_and_disk_full_latch_fault(self):
        self.r.queue_limit=1
        self.assertFalse(self.r.append('/sample','std_msgs/msg/String','string data',b'12'))
        self.assertEqual(self.r.snapshot()['dropped'],1)
        self.assertFalse(self.r.snapshot()['ready'])
        self.r.disk_usage=lambda _:SimpleNamespace(free=0)
        self.assertFalse(self.r.capacity())
    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError):self.r.chunk_path('../secret')
    def test_split_returns_before_slow_disk_close_without_blocking_ingress(self):
        entered,release=threading.Event(),threading.Event()
        original=self.r.sink.close
        def slow_close():
            entered.set();release.wait(2);original()
        self.r.sink.close=slow_close
        self.sample(0)
        before=time.monotonic();boundary=self.r.split('slow_boundary','owner')
        self.assertLess(time.monotonic()-before,.2)
        self.assertTrue(entered.wait(1))
        self.r.heartbeat('owner',True)
        self.sample(1)
        self.assertTrue(self.r.snapshot()['ready'])
        release.set();self.r.finish('owner')
        rows=self.messages()
        self.assertEqual([(r[0],r[2]) for r in rows],[(self.first['instance_id'],0),(boundary['instance_id'],1)])

    def test_twenty_continuous_boundaries(self):
        for i in range(20):
            self.sample(i)
            self.r.split('cut_'+str(i),'owner')
        self.r.finish('owner')
        self.assertEqual(sorted(row[2] for row in self.messages()),list(range(20)))

if __name__=='__main__':unittest.main()
