"""Stationary acceptance probe. Never arms or sends a movement command."""
import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import time
from .client import LimoHarness
from companion.archive import atomic_json

def diagnose(client,seconds):
    samples=[];start=time.monotonic()
    while time.monotonic()-start<seconds:
        state=client.observe()
        if state['mode']!='stopped' or state['output']!=[0,0]:
            client.stop()
            raise ValueError('Stationary probe interrupted by a driving client')
        nav=client.request('/navigation')
        samples.append({'time':time.time(),'odometry':state['odometry'],'pose':nav['pose'],
                        'mapping':state['mapping'],'recording':state['recording'].get('ready'),
                        'battery_voltage':state['chassis'].get('battery_voltage')})
        time.sleep(.5)
    odom=[s['odometry'] for s in samples]
    displacement=max((math.hypot(p['x']-odom[0]['x'],p['y']-odom[0]['y']) for p in odom),default=None)
    poses=[s['pose'] for s in samples if s['pose']]
    drift=max((math.hypot(p[0]-poses[0][0],p[1]-poses[0][1]) for p in poses),default=None)
    yaw=max((abs(math.atan2(math.sin(p[2]-poses[0][2]),math.cos(p[2]-poses[0][2]))) for p in poses),default=None)
    pipeline=bool(poses) and all(s['mapping']['active'] for s in samples)
    return {'duration_s':time.monotonic()-start,'stationary_only':True,'odometry_displacement_m':displacement,
            'map_pose_drift_m':drift,'map_pose_yaw_drift_rad':yaw,'pipeline_healthy':pipeline,
            'stationary_pass':pipeline and displacement<.02 and drift<.05 and yaw<math.radians(2),
            'route_accuracy':'not tested','exploration':'not tested','samples':samples}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--url',default='http://127.0.0.1:18765');parser.add_argument('--seconds',type=float,default=60);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not 1<=args.seconds<=3600:parser.error('Use 1–3600 seconds')
    result=diagnose(LimoHarness(args.url),args.seconds);atomic_json(args.output,result)
    print(json.dumps({key:value for key,value in result.items() if key!='samples'},indent=2))

if __name__=='__main__':main()
