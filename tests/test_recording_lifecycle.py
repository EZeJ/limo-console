"""Recording lifecycle must be independent of stopping the chassis."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from companion.coordinator import Coordinator
from companion.server import Gateway, make_handler


class LifecycleTests(unittest.TestCase):
    def test_connecting_does_not_start_recording(self):
        with patch('companion.server.Coordinator') as factory:
            gateway=Gateway('http://127.0.0.1:1','unused')
            factory.return_value.start.assert_not_called()
            self.assertFalse(gateway.initializing)

    def test_robot_stop_does_not_finish_recording(self):
        forwarded=[]
        class Upstream(BaseHTTPRequestHandler):
            def do_POST(self):
                forwarded.append(self.path)
                self.rfile.read(int(self.headers['Content-Length']))
                self.send_response(200);self.send_header('Content-Length','2');self.end_headers();self.wfile.write(b'{}')
            def log_message(self,*args):pass
        upstream=ThreadingHTTPServer(('127.0.0.1',0),Upstream)
        with patch('companion.server.Coordinator') as factory:
            gateway=Gateway('http://127.0.0.1:'+str(upstream.server_port),'unused')
            server=ThreadingHTTPServer(('127.0.0.1',0),BaseHTTPRequestHandler)
            server.RequestHandlerClass=make_handler(gateway,server.server_port)
            for service in (upstream,server):threading.Thread(target=service.serve_forever,daemon=True).start()
            try:
                with urlopen(Request('http://127.0.0.1:'+str(server.server_port)+'/stop',data=b'{}',headers={'X-Limo-Control':'1'})) as response:
                    self.assertEqual(response.status,200)
                self.assertEqual(forwarded,['/stop'])
                factory.return_value.close.assert_not_called()
            finally:
                for service in (upstream,server):service.shutdown();service.server_close()

    def test_driving_responses_keep_computer_frame_count_and_instance(self):
        class Upstream(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                body=json.dumps({'mode':'manual','recording':{'ready':True,'instance_id':'robot-old'}}).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            def log_message(self,*args):pass
        upstream=ThreadingHTTPServer(('127.0.0.1',0),Upstream)
        with patch('companion.server.Coordinator') as factory:
            factory.return_value.status.return_value={'active':True,'healthy':True,'frames':1234,'instance_id':'computer-current'}
            gateway=Gateway('http://127.0.0.1:'+str(upstream.server_port),'unused')
            server=ThreadingHTTPServer(('127.0.0.1',0),BaseHTTPRequestHandler);server.RequestHandlerClass=make_handler(gateway,server.server_port)
            for service in (upstream,server):threading.Thread(target=service.serve_forever,daemon=True).start()
            try:
                with urlopen(Request('http://127.0.0.1:'+str(server.server_port)+'/drive',data=b'{}',headers={'X-Limo-Control':'1'})) as response:result=json.load(response)
                self.assertEqual(result['recording']['frames'],1234)
                self.assertEqual(result['recording']['instance_id'],'computer-current')
                self.assertTrue(result['recording']['ready'])
            finally:
                for service in (upstream,server):service.shutdown();service.server_close()

    def test_recording_fault_keeps_session_active(self):
        with tempfile.TemporaryDirectory() as root:
            coordinator=Coordinator('unused',root,reserve_bytes=1)
            coordinator.active=True;coordinator.request=MagicMock()
            coordinator.fault('Network interrupted')
            self.assertTrue(coordinator.active)
            coordinator.request.assert_not_called()
            self.assertEqual(len(coordinator.incidents),1)

    def test_next_instance_never_requests_stop(self):
        with tempfile.TemporaryDirectory() as root:
            coordinator=Coordinator('unused',root,reserve_bytes=1)
            coordinator.active=True;coordinator.session='session'
            first={'session_id':'session','instance_id':'first','monotonic_ns':100}
            second={'session_id':'session','instance_id':'second','monotonic_ns':200}
            coordinator._add_instance(first)
            coordinator.request=MagicMock(return_value=second)
            coordinator.next('boundary')
            self.assertEqual([call.args[0] for call in coordinator.request.call_args_list],['/recording/next'])
            self.assertEqual(len(coordinator.instances),2)
            for writer in coordinator.writers.values():writer.close()

    def test_only_explicit_finish_closes_as_user_completed(self):
        with patch('companion.server.Coordinator') as factory:
            gateway=Gateway('unused','unused')
            gateway.finish()
            factory.return_value.close.assert_called_once_with(interrupted=False)

if __name__=='__main__':unittest.main()
