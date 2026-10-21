import csv,json,tempfile,threading,unittest,time,zipfile
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from unittest.mock import patch
from companion.datasets import Datasets
from companion.server import Gateway,make_handler

class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.folder=self.root/'session'/'instance';self.folder.mkdir(parents=True)
        (self.folder/'manifest.json').write_text(json.dumps({'session_id':'session','instance_id':'instance','status':'complete','video_closed':True,'video_frames':2}))
        (self.folder/'frames.csv').write_text('frame,source_sequence,capture_monotonic_ns,source_ros_stamp_ns,receive_wall_ns,pts_us,width,height,rgb_sha256\n0,1,100,100,100,0,16,16,hash\n1,2,200,200,200,100000,16,16,hash\n')
        self.store=Datasets(self.root)
    def test_catalog_reloads_prior_sessions(self):
        self.assertEqual(self.store.catalog()['sessions'][0]['instances'][0]['video_frames'],2)
        self.assertEqual(Datasets(self.root).describe('session','instance')['frame_count'],2)
    def add_segment(self,name='second',closed=True):
        folder=self.root/'session'/name;folder.mkdir()
        (folder/'manifest.json').write_text(json.dumps({'session_id':'session','instance_id':name,'status':'complete' if closed else 'recording','video_closed':closed,'video_frames':2,'name':name}))
        (folder/'frames.csv').write_bytes((self.folder/'frames.csv').read_bytes())
        return folder
    def wait_job(self,collection,key):
        deadline=time.monotonic()+3
        while collection[key]['state'] in ('queued','running') and time.monotonic()<deadline:time.sleep(.01)
        self.assertNotIn(collection[key]['state'],('queued','running'))
        return collection[key]
    def test_session_summary_keeps_segments_and_sensor_totals(self):
        second=self.add_segment()
        header='source_ros_stamp_ns,x_m,y_m,linear_m_s,angular_rad_s,derived_acceleration_m_s2\n'
        for folder,start,count in [(self.folder,1000000000,5),(second,11000000000,7)]:
            (folder/'odometry.csv').write_text(header+f'{start},1,2,.1,.2,\n{start+100000000},2,3,.2,.3,1\n')
            (folder/'sensors').mkdir();(folder/'sensors'/'test.manifest.json').write_text(json.dumps({'counts':{'/scan':count}}))
        result=self.store.describe_session('session')
        self.assertEqual(result['frame_count'],4);self.assertEqual(result['topics'],{'/scan':12})
        self.assertEqual([s['time_offset_s'] for s in result['segments']],[0,10])
        self.assertEqual(result['segments'][1]['trajectory'][0][0],0)
        self.assertEqual(result['source_directory'],str(self.folder.parent));self.assertTrue(result['closed'])
    def test_session_zip_preserves_boundaries_originals_and_configuration(self):
        second=self.add_segment();(self.folder/'camera.mp4').write_bytes(b'first');(second/'camera.mp4').write_bytes(b'second')
        (self.folder.parent/'configuration.json').write_text('{"version":1}')
        self.store.bundle_session('session');result=self.wait_job(self.store.bundles,('session',None))
        self.assertEqual(result['state'],'done')
        with zipfile.ZipFile(self.store.bundle_file('session',None)) as archive:
            self.assertEqual(archive.read('instance/camera.mp4'),b'first');self.assertEqual(archive.read('second/camera.mp4'),b'second')
            self.assertIn('configuration.json',archive.namelist());self.assertIsNone(archive.testzip())
        self.assertEqual((second/'camera.mp4').read_bytes(),b'second')
    def test_batch_export_reports_failure_and_continues_other_segments(self):
        self.add_segment('second');self.add_segment('third')
        def inspect(folder,export):
            if folder.name=='second':raise ValueError('Archive checksum mismatch')
            return {'complete_received_stream':True,'topics':{'/scan':5}}
        with patch('harness.replay.inspect',side_effect=inspect) as replay:
            self.store.export_session('session');result=self.wait_job(self.store.jobs,('session',None))
        self.assertEqual(replay.call_count,3);self.assertEqual(result['state'],'partial');self.assertEqual(result['instances_done'],3)
        self.assertEqual([r['state'] for r in result['results']],['done','error','done'])
        with (self.folder.parent/'exports/instances.csv').open() as file:rows=list(csv.DictReader(file))
        self.assertEqual(rows[1]['error'],'Archive checksum mismatch')
        self.assertEqual(Datasets(self.root).describe_session('session')['export']['state'],'partial')
    def test_session_operations_reject_open_segments_and_escaping_files(self):
        self.add_segment(closed=False)
        for operation in [self.store.export_session,self.store.bundle_session]:
            with self.assertRaises(ValueError):operation('session')
        with self.assertRaises(ValueError):self.store.file('session',None,'../secret')
        (self.folder.parent/'outside').symlink_to('/etc')
        with self.assertRaises(ValueError):self.store.file('session',None,'outside/passwd')
    def test_paths_and_symlinks_cannot_escape_dataset_root(self):
        for session,instance,name in [('../secret','instance','manifest.json'),('session','instance','../../secret'),('session','instance','/etc/passwd')]:
            with self.assertRaises(ValueError):self.store.file(session,instance,name)
        (self.folder/'escape').symlink_to('/etc/passwd')
        with self.assertRaises(ValueError):self.store.file('session','instance','escape')
    def test_package_contains_original_files_and_source_configuration(self):
        (self.folder/'camera.mp4').write_bytes(b'original-video-bytes')
        (self.folder.parent/'configuration.json').write_text('{"version":1}')
        self.store.bundle('session','instance')
        deadline=time.monotonic()+3
        while self.store.bundles[('session','instance')]['state'] in ('queued','running') and time.monotonic()<deadline:time.sleep(.01)
        path=self.store.bundle_file('session','instance')
        with zipfile.ZipFile(path) as archive:
            self.assertEqual(archive.read('camera.mp4'),b'original-video-bytes')
            self.assertIn('_session/configuration.json',archive.namelist())
            self.assertIsNone(archive.testzip())
        self.assertTrue((self.folder/'camera.mp4').is_file())

    def test_video_range_seeking_and_idle_browsing(self):
        (self.folder/'camera.mp4').write_bytes(b'0123456789')
        gateway=Gateway(None,self.root);server=ThreadingHTTPServer(('127.0.0.1',0),BaseHTTPRequestHandler);server.RequestHandlerClass=make_handler(gateway,server.server_port)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            url='http://127.0.0.1:'+str(server.server_port)+'/local/data/file?session=session&instance=instance&file=camera.mp4'
            with urlopen(Request(url,headers={'Range':'bytes=2-5'})) as response:
                self.assertEqual(response.status,206);self.assertEqual(response.read(),b'2345');self.assertEqual(response.headers['Content-Range'],'bytes 2-5/10')
            with self.assertRaises(HTTPError) as error:urlopen(Request(url,headers={'Range':'bytes=50-60'}))
            self.assertEqual(error.exception.code,416)
            self.assertFalse(gateway.coordinator.active)
        finally:server.shutdown();server.server_close()
