"""Offline inspection and export. No ROS runtime, network or motion interface."""
import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path
from mcap.reader import make_reader
from mcap_ros2.decoder import DecoderFactory
from companion.archive import sha256_file, atomic_json


def messages(folder):
    chunks=[]
    for receipt in (Path(folder)/'sensors').glob('*.manifest.json'):
        info=json.loads(receipt.read_text());path=receipt.with_suffix('').with_suffix('.mcap')
        if not path.is_file() or path.stat().st_size!=info['bytes'] or sha256_file(path)!=info['sha256']:
            raise ValueError('Archive checksum mismatch: '+path.name)
        chunks.append((info.get('first_sequence') or 0,path))
    for _,path in sorted(chunks):
        with path.open('rb') as stream:
            yield from make_reader(stream,validate_crcs=True,decoder_factories=[DecoderFactory()]).iter_decoded_messages(log_time_order=False)


def inspect(folder,export=False):
    folder=Path(folder);counts=Counter();first=last=None;missing=[];duplicates=0
    previous_odom=None;writers={};files=[]
    latest_transform=None;map_snapshot=None;map_transform=None
    def row(name,columns,values):
        if not export:return
        if name not in writers:
            handle=(folder/(name+'.csv')).open('w',newline='');files.append(handle)
            writers[name]=csv.writer(handle);writers[name].writerow(columns)
        writers[name].writerow(values)
    try:
        for schema,channel,message,value in messages(folder):
            # Latched context is not a received sample, but its transform still aligns the map.
            if channel.topic in ('/tf','/tf_static'):
                for transform in value.transforms:
                    if transform.header.frame_id=='map' and transform.child_frame_id=='odom':
                        q=transform.transform.rotation;p=transform.transform.translation
                        latest_transform=[p.x,p.y,math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))]
            # Sequence zero is replay context (latched TF/calibration), not a received sample.
            if not message.sequence:continue
            seq=message.sequence
            if first is None:first=seq
            if last is not None:
                if seq<=last:duplicates+=1
                elif seq>last+1:missing.append([last+1,seq-1])
            last=seq;counts[channel.topic]+=1
            stamp=message.log_time
            if channel.topic=='/map' and value.header.frame_id=='map':
                map_snapshot=value;map_transform=latest_transform
            if channel.topic=='/odom':
                source=value.header.stamp.sec*10**9+value.header.stamp.nanosec
                p,q=value.pose.pose.position,value.pose.pose.orientation
                v,w=value.twist.twist.linear.x,value.twist.twist.angular.z
                acceleration=angular_acceleration=''
                if previous_odom and source>previous_odom[0]:
                    dt=(source-previous_odom[0])/1e9
                    if dt<1:acceleration=(v-previous_odom[1])/dt;angular_acceleration=(w-previous_odom[2])/dt
                previous_odom=(source,v,w)
                yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
                row('odometry',['receive_wall_ns','source_ros_stamp_ns','sequence','x_m','y_m','yaw_rad','linear_m_s','angular_rad_s','derived_acceleration_m_s2','derived_angular_acceleration_rad_s2'],[stamp,source,seq,p.x,p.y,yaw,v,w,acceleration,angular_acceleration])
            elif channel.topic=='/imu':
                source=value.header.stamp.sec*10**9+value.header.stamp.nanosec
                a,g=value.linear_acceleration,value.angular_velocity
                row('imu',['receive_wall_ns','source_ros_stamp_ns','sequence','ax_m_s2','ay_m_s2','az_m_s2','gx_rad_s','gy_rad_s','gz_rad_s'],[stamp,source,seq,a.x,a.y,a.z,g.x,g.y,g.z])
            elif channel.topic=='/console/control_tick':
                tick=json.loads(value.data)
                row('controls',['receive_wall_ns','monotonic_ns','sequence','mode','requested_v_m_s','requested_w_rad_s','output_v_m_s','output_w_rad_s','reason'],[stamp,tick['monotonic_ns'],seq,tick['mode'],*tick['requested'],*tick['output'],tick['reason']])
            elif channel.topic=='/console/events':
                row('events',['receive_wall_ns','sequence','event_json'],[stamp,seq,value.data])
            elif channel.topic=='/limo_status':
                row('chassis',['receive_wall_ns','sequence','battery_voltage','vehicle_state','control_mode','error_code','motion_mode'],[stamp,seq,*[getattr(value,key) for key in ('battery_voltage','vehicle_state','control_mode','error_code','motion_mode')]])
    finally:
        for file in files:file.close()
    report={'topics':dict(counts),'first_sequence':first,'last_sequence':last,'missing_sequence_ranges':missing,'duplicate_sequences':duplicates,'complete_received_stream':not missing and duplicates==0,'motion_output_available':counts['/console/control_tick']>0,
            'unavailable_measurements':['physical steering angle','wheel encoder counts'],
            'notes':['Sequence checks apply to received samples; DDS losses before receipt are not proven absent.','IMU acceleration includes gravity and bias; odometry acceleration is a finite difference.']}
    manifest=folder/'manifest.json'
    if manifest.exists():
        info=json.loads(manifest.read_text());sensor=info.get('sensors',{})
        if sensor.get('end_sequence') is not None:
            expected=sensor['end_sequence']-info['sequence']
            report.update(expected_received_samples=expected,observed_received_samples=sum(counts.values()))
            report['complete_received_stream'] &= expected==sum(counts.values())
    if export:atomic_json(folder/'validation.json',report)
    if export and map_snapshot is not None:
        from PIL import Image
        grid=map_snapshot;origin=grid.info.origin;q=origin.orientation
        pixels=bytes(225 if v<0 else 250 if v<=25 else 145 if v<65 else 42 for v in grid.data)
        Image.frombytes('L',(grid.info.width,grid.info.height),pixels).transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(folder/'map.png')
        metadata={'frame_id':'map','width':grid.info.width,'height':grid.info.height,'resolution':grid.info.resolution,
                  'origin':[origin.position.x,origin.position.y,math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))],
                  'source_stamp_ns':grid.header.stamp.sec*10**9+grid.header.stamp.nanosec,
                  'odom_to_map':map_transform,'alignment_available':map_transform is not None,
                  'trajectory_method':'Odometry projected through the transform accompanying the final recorded map; not an optimized SLAM trajectory.'}
        atomic_json(folder/'map.json',metadata)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('instance',type=Path);parser.add_argument('--export',action='store_true')
    args=parser.parse_args();print(json.dumps(inspect(args.instance,args.export),indent=2))

if __name__=='__main__':main()
