import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from companion.archive import archive_chunk
from companion.coordinator import Coordinator

class ArchiveTests(unittest.TestCase):
    def item(self,data):return dict(session_id='session',instance_id='instance',chunk_id='chunk',bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    def test_corrupt_or_truncated_transfer_never_acknowledges(self):
        for data in (b'broken',b'ab'):
            with tempfile.TemporaryDirectory() as root,patch('companion.archive.urlopen',return_value=io.BytesIO(data)),patch('companion.archive.json_request') as ack:
                with self.assertRaises(ValueError):archive_chunk('http://127.0.0.1:1',root,self.item(b'abcdef'))
                ack.assert_not_called()
                self.assertFalse((Path(root)/'session/instance/sensors/chunk.mcap').exists())
    def test_durable_receipt_precedes_ack_and_retry_reuses_file(self):
        data=b'synthetic sensor archive'
        with tempfile.TemporaryDirectory() as root:
            def ack(*args):
                folder=Path(root)/'session/instance/sensors'
                self.assertEqual((folder/'chunk.mcap').read_bytes(),data)
                self.assertTrue(json.loads((folder/'chunk.manifest.json').read_text())['verified_on_computer'])
                return {'deleted':True}
            with patch('companion.archive.urlopen',return_value=io.BytesIO(data)),patch('companion.archive.json_request',side_effect=ack):
                archive_chunk('http://127.0.0.1:1',root,self.item(data))
            with patch('companion.archive.urlopen') as download,patch('companion.archive.json_request',side_effect=ack):
                archive_chunk('http://127.0.0.1:1',root,self.item(data));download.assert_not_called()
    def test_instance_cannot_complete_before_all_declared_chunks_arrive(self):
        with tempfile.TemporaryDirectory() as root:
            coordinator=Coordinator('unused',root,reserve_bytes=1)
            item={'path':root,'incidents':[]}
            remote={'status':'complete','chunk_ids':['first','last']}
            self.assertEqual(coordinator.completion(item,remote),'pending_transfer')
            folder=Path(root)/'sensors';folder.mkdir()
            for name in ('first','last'):(folder/(name+'.manifest.json')).write_text('{"verified_on_computer":true}')
            self.assertEqual(coordinator.completion(item,remote),'complete')
            item['incidents'].append({'reason':'lost frame'})
            self.assertEqual(coordinator.completion(item,remote),'interrupted')
