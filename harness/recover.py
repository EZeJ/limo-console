"""Salvage complete CRC-valid records from a local interrupted MCAP. Preserve input."""
import argparse
from collections import Counter
from pathlib import Path
from mcap.stream_reader import StreamReader
from mcap.records import Schema,Channel,Message
from mcap.writer import Writer,CompressionType
from companion.archive import atomic_json


def recover(source,destination):
    source,destination=Path(source),Path(destination)
    if source.resolve()==destination.resolve() or destination.exists():raise ValueError('Choose a new output file; originals are never overwritten')
    schemas={};channels={};counts=Counter();tail_error=None
    with source.open('rb') as input,destination.open('xb') as output:
        writer=Writer(output,compression=CompressionType.ZSTD,enable_crcs=True,enable_data_crcs=True)
        writer.start(profile='ros2',library='Limo Console recovery')
        try:
            for record in StreamReader(input,validate_crcs=True,record_size_limit=128*1024**2).records:
                if isinstance(record,Schema):schemas[record.id]=writer.register_schema(record.name,record.encoding,record.data)
                elif isinstance(record,Channel):channels[record.id]=writer.register_channel(record.topic,record.message_encoding,schemas.get(record.schema_id,0),record.metadata)
                elif isinstance(record,Message):
                    writer.add_message(channels[record.channel_id],record.log_time,record.data,record.publish_time,record.sequence)
                    counts[str(record.channel_id)]+=1
        except Exception as exc:tail_error=type(exc).__name__+': '+str(exc)
        writer.finish()
    report={'source':str(source),'output':str(destination),'recovered_records':sum(counts.values()),
            'tail_error':tail_error,'original_preserved':True,'complete_recording':False}
    atomic_json(destination.with_suffix('.recovery.json'),report)
    return report

def main():
    import json
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('source');parser.add_argument('output');args=parser.parse_args()
    print(json.dumps(recover(args.source,args.output),indent=2))
if __name__=='__main__':main()
