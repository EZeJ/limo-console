import csv
import hashlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
import av
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from companion.video import VideoWriter

class VideoTests(unittest.TestCase):
    def encode(self,mode):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        path=Path(temp.name);writer=VideoWriter(path,{'width':64,'height':48,'fps':10,'format':mode})
        arrays=[]
        for i in range(12):
            rgb=np.random.default_rng(i).integers(0,256,(48,64,3),dtype=np.uint8);arrays.append(rgb)
            out=io.BytesIO();Image.fromarray(rgb).save(out,format='PNG')
            writer.write({'sequence':i,'monotonic_ns':10**12+i*100_000_000+(40_000_000 if i%2==0 else -30_000_000),'source_stamp_ns':i,'receive_wall_ns':i,'rgb_sha256':hashlib.sha256(rgb.tobytes()).hexdigest()},out.getvalue())
        writer.close()
        return path,arrays
    def test_ffv1_is_pixel_lossless_and_timestamped(self):
        path,original=self.encode('ffv1')
        with av.open(str(path/'camera.mkv')) as video:
            decoded=[frame.to_ndarray(format='rgb24') for frame in video.decode(video=0)]
        self.assertEqual(len(decoded),len(original))
        for a,b in zip(original,decoded):self.assertTrue(np.array_equal(a,b))
        with (path/'frames.csv').open() as file:rows=list(csv.DictReader(file))
        self.assertEqual(len(rows),12)
        self.assertEqual(int(rows[-1]['pts_us']),1030000)
    def test_h264_is_playable(self):
        path,original=self.encode('h264')
        with av.open(str(path/'camera.mp4')) as video:self.assertEqual(len(list(video.decode(video=0))),12)
    def test_png_sequence_is_pixel_lossless(self):
        path,original=self.encode('png')
        for filename,source in zip(sorted((path/'frames').glob('*.png')),original):self.assertTrue(np.array_equal(np.asarray(Image.open(filename)),source))
    def test_lossless_rejects_changed_pixels(self):
        with tempfile.TemporaryDirectory() as temp:
            writer=VideoWriter(temp,{'width':64,'height':48,'fps':10,'format':'png'})
            out=io.BytesIO();Image.new('RGB',(64,48)).save(out,format='PNG')
            with self.assertRaises(ValueError):writer.write({'rgb_sha256':'wrong'},out.getvalue())
            writer.close()

if __name__=='__main__':unittest.main()
