from pathlib import Path
import sys,math,unittest
from types import SimpleNamespace as N
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'robot'))
from scan_quality import mapping_ranges,scan_metrics
class ScanQualityTests(unittest.TestCase):
    def test_isolated_far_noise_becomes_unknown_not_free(self):
        values=[2,2,6,2,2];out,n=mapping_ranges(values,.12,8)
        self.assertEqual(n,1);self.assertTrue(math.isnan(out[2]));self.assertEqual(values,[2,2,6,2,2])
    def test_near_obstacles_and_real_edges_remain(self):
        for values in ([2,2,.3,2,2],[2,2,6,6,6],[2,6,6,2,2],[float('nan'),6,2]):
            out,n=mapping_ranges(values,.12,8);self.assertEqual(n,0)
    def test_stale_or_sparse_scan_not_usable(self):
        msg=N(ranges=[2.]*360,range_min=.12,range_max=8,angle_min=-math.pi,angle_increment=math.pi/180,scan_time=.1,time_increment=.1/360,header=N(stamp=N(sec=100,nanosec=0),frame_id='laser'))
        self.assertTrue(scan_metrics(msg,100100000000)['usable'])
        self.assertFalse(scan_metrics(msg,102000000000)['usable'])
        msg.ranges=[0.]*360
        self.assertFalse(scan_metrics(msg,100100000000)['usable'])
