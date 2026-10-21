import csv,json,tempfile,threading,unittest
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.request import Request,urlopen
from urllib.error import HTTPError
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
    def test_paths_and_symlinks_cannot_escape_dataset_root(self):
        for session,instance,name in [('../secret','instance','manifest.json'),('session','instance','../../secret'),('session','instance','/etc/passwd')]:
            with self.assertRaises(ValueError):self.store.file(session,instance,name)
        (self.folder/'escape').symlink_to('/etc/passwd')
        with self.assertRaises(ValueError):self.store.file('session','instance','escape')
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
