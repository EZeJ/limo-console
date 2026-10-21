"""Expand generated ROS field descriptions into self-contained MCAP schemas."""
import re
from importlib import import_module

PRIMITIVES = {'boolean':'bool','octet':'byte','float':'float32','double':'float64',
              'long double':'float64'}
BUILTINS = {'bool','byte','char','float32','float64','int8','uint8','int16','uint16',
            'int32','uint32','int64','uint64','string','wstring'}


def message_definition(typename, loader):
    definitions = {}

    def load(name):
        parts=name.split('/')
        candidates=[name] if len(parts)==3 else [parts[0]+'/msg/'+parts[-1],parts[0]+'/action/'+parts[-1]]
        for candidate in candidates:
            try:return loader(candidate)
            except (AttributeError,ModuleNotFoundError,ValueError):pass
        # Generated action payloads live on Action.Feedback/Goal/Result rather than
        # being exported as stand-alone messages by the action package.
        for suffix in ('Feedback','Goal','Result'):
            if parts[-1].endswith('_'+suffix):
                try:
                    action=getattr(import_module(parts[0]+'.action'),parts[-1][:-len(suffix)-1])
                    return getattr(action,suffix)
                except (ImportError,AttributeError):pass
        raise ValueError('Message type unavailable: '+name)

    def convert(field):
        sequence=re.fullmatch(r'(?:bounded_)?sequence<(.+)>',field)
        if sequence:
            body=sequence[1]
            if ',' in body:
                inner,limit=body.rsplit(',',1)
                return convert(inner.strip())+'[<='+limit.strip()+']'
            return convert(body)+'[]'
        array=re.fullmatch(r'(.+)(\[\d*\])',field)
        if array:return convert(array[1])+array[2]
        field=PRIMITIVES.get(field,field)
        if field.startswith('string<') or field.startswith('wstring<'):
            field=field.replace('<','<=').rstrip('>')
        base=field.split('<=')[0]
        if base in BUILTINS:return field
        parts=field.split('/')
        if len(parts)<2:raise ValueError('Unknown message field: '+field)
        key=parts[0]+'/'+parts[-1]
        visit(key)
        return key

    def visit(name):
        key=name.split('/')[0]+'/'+name.split('/')[-1]
        if key in definitions:return
        definitions[key]=''
        message=load(name)
        lines=[convert(field)+' '+label for label,field in message.get_fields_and_field_types().items()]
        definitions[key]='\n'.join(lines)+'\n'

    visit(typename)
    root=typename.split('/')[0]+'/'+typename.split('/')[-1]
    return definitions[root]+''.join('\n'+'='*80+'\nMSG: '+key+'\n'+text
                                    for key,text in definitions.items() if key!=root)
