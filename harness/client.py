"""Bounded capabilities with observed outcomes, for deterministic robot policies."""
from dataclasses import dataclass
import json
import math
import time
from urllib.request import Request, urlopen
import uuid

@dataclass(frozen=True)
class Outcome:
    operation: str
    verified: bool
    evidence: dict

class LimoHarness:
    def __init__(self,url='http://127.0.0.1:18765',*,allow_motion=False):
        self.url=url.rstrip('/');self.allow_motion=allow_motion
    def request(self,path,data=None):
        with urlopen(Request(self.url+path,data=None if data is None else json.dumps(data,allow_nan=False).encode(),headers={'X-Limo-Control':'1','Content-Type':'application/json'}),timeout=8) as response:
            return json.load(response)
    def observe(self):return self.request('/status')
    def stop(self):
        self.request('/stop',{});state=self.observe()
        return Outcome('stop',state['mode']=='stopped' and state['output']==[0,0],state)
    def start_recording(self):
        self.request('/local/recording/start',{})
        return self.wait('recording_started',lambda s:s['recording'].get('ready'),15)
    def end_recording(self):
        self.request('/local/recording/finish',{})
        return self.wait('recording_ended',lambda s:not s['recording'].get('active') and not s['recording'].get('finishing'),30)
    def next_instance(self,name=''):
        before=self.observe();boundary=self.request('/local/recording/next',{'request_id':uuid.uuid4().hex,'name':name})
        state=self.observe()
        valid=(state['recording']['instance_id']==boundary['instance_id'] and
               before['recording']['session_id']==state['recording']['session_id'])
        return Outcome('next_instance',valid,{'before':before,'boundary':boundary,'after':state})
    def start_mapping(self,backend='cartographer'):
        self.request('/mapping/start',{'backend':backend})
        return self.wait('mapping_pipeline_started',lambda s:s['mapping']['active'] and not s['mapping']['busy'],35)
    def wait(self,operation,predicate,seconds):
        deadline=time.monotonic()+seconds;state={}
        while time.monotonic()<deadline:
            state=self.observe()
            if predicate(state):return Outcome(operation,True,state)
            time.sleep(.2)
        return Outcome(operation,False,state)
    def drive_for(self,linear,angular,seconds):
        if not self.allow_motion:raise ValueError('Motion is disabled for this harness')
        if not all(math.isfinite(v) for v in (linear,angular,seconds)) or not 0<seconds<=10:
            raise ValueError('A finite motion duration up to 10 seconds is required')
        state=self.observe()
        if state.get('stationary_mode'):raise ValueError('Stationary maintenance mode; driving is locked')
        evidence=[]
        try:
            self.request('/arm',{'mode':'manual'})
            deadline=time.monotonic()+seconds
            while time.monotonic()<deadline:
                self.request('/drive',{'x':linear,'z':angular})
                state=self.observe();evidence.append(state)
                if state['mode']!='manual':raise ValueError('Motion lease was interrupted')
                time.sleep(.1)
        finally:
            stopped=self.stop()
        # Command acceptance is not proof of achieved physical displacement.
        return Outcome('bounded_drive',stopped.verified,{'samples':evidence,'stopped':stopped.evidence,'physical_distance_verified':False})
