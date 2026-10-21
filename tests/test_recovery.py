from pathlib import Path
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'robot'))
from recording_core import McapSink,string_cdr
from mcap.reader import make_reader
from harness.recover import recover
class RecoveryTests(unittest.TestCase):
    def test_truncated_footer_retains_messages_and_original(self):
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)/'interrupted.mcap';sink=McapSink(source)
            for i in range(40):sink.write('/test','std_msgs/msg/String','string data\n',string_cdr({'i':i}),100+i,i+1)
            sink.close();original=source.read_bytes()[:-60];source.write_bytes(original)
            out=Path(root)/'recovered.mcap';result=recover(source,out)
            self.assertEqual(result['recovered_records'],40);self.assertFalse(result['complete_recording'])
            self.assertEqual(source.read_bytes(),original)
            with out.open('rb') as file:self.assertEqual(len(list(make_reader(file).iter_messages())),40)
