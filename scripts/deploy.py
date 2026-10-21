#!/usr/bin/env python3
"""Deploy only committed console files to an existing ROS Docker container."""
import argparse,json,re,subprocess,tempfile
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('target',help='USER@ROBOT_HOST');parser.add_argument('--container',default='limo_control');parser.add_argument('--ssh-control-path');args=parser.parse_args()
    if args.target.startswith('-') or '@' not in args.target:parser.error('Use USER@ROBOT_HOST')
    if not re.fullmatch('[A-Za-z0-9_-]+',args.container):parser.error('Invalid container name')
    options=['-o','ControlPath='+args.ssh_control_path] if args.ssh_control_path else []
    def remote(command,capture=False):
        return subprocess.run(['ssh',*options,args.target,command],check=True,text=True,capture_output=capture)
    root=Path(__file__).resolve().parents[1]
    probe="import json,urllib.request;s=json.load(urllib.request.urlopen('http://127.0.0.1:8765/status'));assert s['mode']=='stopped' and s['output']==[0,0], 'Stop driving first';assert not s.get('recording',{}).get('active'), 'End recording explicitly before deployment';assert not s['mapping']['active'], 'Save and finish mapping before deployment'"
    import shlex
    remote('docker exec '+args.container+' python3 -c '+shlex.quote(probe))
    remote_dir=remote('mktemp -d /tmp/limo-console.XXXXXXXX',True).stdout.strip()
    if not re.fullmatch('/tmp/limo-console.[A-Za-z0-9]+',remote_dir):raise RuntimeError('Unexpected deployment directory')
    with tempfile.TemporaryDirectory() as temporary:
        archive=Path(temporary)/'console.tar'
        subprocess.run(['git','archive','--format=tar','--output',str(archive),'HEAD','robot','scripts/install.sh','requirements-recorder.txt'],cwd=root,check=True)
        subprocess.run(['scp',*options,str(archive),args.target+':'+remote_dir+'/console.tar'],check=True)
    ctr=args.container
    remote('tar -xf '+remote_dir+'/console.tar -C '+remote_dir+' && docker cp '+remote_dir+' '+ctr+':/tmp/')
    remote('docker exec '+ctr+' bash /control/manage.sh shutdown')
    remote('docker exec '+ctr+' bash '+remote_dir+'/scripts/install.sh')
    remote('docker exec '+ctr+' bash /control/manage.sh start')
    remote('docker exec '+ctr+" bash -lc 'source /control/env.sh; for attempt in {1..10}; do python3 /control/doctor.py && exit 0; sleep 2; done; exit 1'")
    print('Deployed committed console source. Recordings remain private and untouched.')
if __name__=='__main__':main()
