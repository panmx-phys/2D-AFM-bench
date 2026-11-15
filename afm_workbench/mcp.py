"""MCP stdio adapter. Scientific requests use the exact desktop service."""
from __future__ import annotations
import json
import sys

from . import MAX_REQUEST_BYTES


def _object(properties, required=()):
    return {'type': 'object', 'properties': properties, 'required': list(required), 'additionalProperties': False}


_ID = {'type':'string','description':'Stable image or session ID returned by the catalog.'}
_POINT = {'type':'array','items':{'type':'number','minimum':0,'maximum':1},'minItems':2,'maxItems':2}
_ROI = _object({k:{'type':'number','minimum':0,'maximum':1} for k in ('x0','y0','x1','y1')}, ('x0','y0','x1','y1'))
_MASK = {'type':'array','items':{'type':'array','items':{'type':'number','enum':[0,1]}},
         'description':'Full-resolution binary mask in stored-array coordinates.'}
_MASKING = {'type':'string','enum':['include','exclude','ignore']}
_USE_MASK = {'type':'boolean','description':'Snapshot the current saved image mask for this operation; masking defaults to its saved include/exclude/ignore preference.'}
_DISPLAY = _object({'palette': {'type':'string','enum':['amber','gray','viridis']},
    'mode': {'type':'string','enum':['full','percentile','manual']},
    'clip_percent': {'type':'number','minimum':0,'maximum':10},
    'minimum': {'type':['number','null']}, 'maximum': {'type':['number','null']}})
_OPS = {'type':'array','maxItems':100,'items':_object({
    'type':{'type':'string','enum':['plane','polynomial','align_rows','align_columns','align_scan','terrace_plane','auto_2d','auto_characterize','three_point','zero_mean','zero_min','zero_max']},
    'method':{'type':'string','enum':['gwyddion','legacy','median','mean','median_difference','modus','matching','polynomial','trimmed_mean','trimmed_difference','facet_tilt'],
              'description':'Set gwyddion for plane or zero references; choose an explicit alignment method (median is the Gwyddion default). Omission replays legacy plane/alignment/zero_mean semantics.'},
    'axis':{'type':'string','enum':['auto','rows','columns'],'description':'For align_scan, auto_2d or auto_characterize; auto uses instrument metadata.'},
    'degree':{'type':'integer','minimum':0,'maximum':11,'description':'Line polynomial degree 0..5 (default 1), or total surface degree 0..11 (default 3).'},
    'degree_x':{'type':'integer','minimum':0,'maximum':11},
    'degree_y':{'type':'integer','minimum':0,'maximum':11},
    'mode':{'type':'string','enum':['independent','total'],'description':'Surface polynomial only; default independent, degree_x=degree_y=3.'},
    'trim_fraction':{'type':'number','minimum':0,'maximum':.5,'description':'Fraction removed from each tail; trimmed alignment methods only; default .05.'},
    'line_correction':{'type':'boolean','description':'auto_2d or auto_characterize; default true. False retains scan-line background.'},
    'points':{'type':'array','items':_POINT,'minItems':3,'maxItems':3,'description':'three_point only: three points on the same reference plane.'},
    'radius':{'type':'integer','minimum':0,'maximum':32,'description':'three_point patch half-width in pixels; default 2.'},
    'roi':_ROI,'reference':_ROI,'mask':_MASK,'masking':_MASKING,'use_saved_mask':_USE_MASK},('type',))}
_TOOLS = [
    ('list_folders','list_folders','List active and archived session folders and source locations.',_object({})),
    ('update_session','update_session','Rename, annotate, archive or restore a session; source files and analysis are preserved.',_object({'id':_ID,'name':{'type':'string'},'notes':{'type':'string'},'archived':{'type':'boolean'}},('id',))),
    ('start_import','start_import','Import or update one folder in the background. Set session_id to reconnect an existing session to a moved folder.',_object({'path':{'type':'string'},'session_id':_ID},('path',))),
    ('import_status','import_status','Inspect progress and errors for the latest folder import.',_object({})),
    ('cancel_import','cancel_import','Stop after the current file; completed images stay saved and a retry skips them.',_object({})),
    ('list_sessions','bootstrap','List all local AFM sessions; one folder is one session.',_object({})),
    ('inspect_session','session','Inspect every image in one AFM session.',_object({'id':_ID},('id',))),
    ('search_scans','search_scans','Search filenames, channels, session names and notes.',_object({'query':{'type':'string'}})),
    ('inspect_scan','scan','Inspect calibration, provenance and numerical statistics. Full arrays are omitted.',_object({'id':_ID,'raw':{'type':'boolean'}},('id',))),
    ('preview_recipe','preview','Preview a recipe without saving. Operations replay from immutable calibrated data.',_object({'id':_ID,'operations':_OPS},('id','operations'))),
    ('run_recipe','process','Save and run a recipe; preserves the source and prior runs.',_object({'id':_ID,'operations':_OPS},('id','operations'))),
    ('measure_profile','profile','Measure a full-resolution profile with Gwyddion sampling and optional transverse averaging.',_object({
        'id':_ID,'start':_POINT,'end':_POINT,'samples':{'type':'integer','minimum':2,'maximum':65536},
        'interpolation':{'type':'string','enum':['linear','nearest']},
        'averaging_width_pixels':{'type':'integer','minimum':1,'maximum':128},
        'sampling':{'type':'string','enum':['gwyddion','legacy']},'mask':_MASK,'masking':_MASKING,'use_saved_mask':_USE_MASK},('id','start','end'))),
    ('measure_area','measure_area','Measure mean-relative area statistics with an optional ROI and include/exclude mask.',_object({'id':_ID,'roi':_ROI,'mask':_MASK,'masking':_MASKING,'use_saved_mask':_USE_MASK},('id',))),
    ('measure_step','step_height','Measure signed mean(B)-mean(A) between two reference regions.',_object({'id':_ID,'region_a':_ROI,'region_b':_ROI,'mask':_MASK,'masking':_MASKING,'use_saved_mask':_USE_MASK},('id','region_a','region_b'))),
    ('edit_mask','edit_mask','Edit the full-resolution image mask. Selection changes never modify source pixels or prior recipe masks.',_object({
        'id':_ID,'action':{'type':'string','enum':['rectangle','brush','threshold','invert','clear','undo','redo']},
        'roi':_ROI,'points':{'type':'array','items':_POINT,'minItems':1,'maxItems':10000},
        'radius':{'type':'number','minimum':.5,'description':'Brush radius in source-array pixels.'},
        'mode':{'type':'string','enum':['add','remove','replace']},'lower':{'type':'number'},'upper':{'type':'number'}},('id','action'))),
    ('update_mask','update_mask','Set mask inclusion and visibility independently. Hiding the overlay does not disable masking.',_object({
        'id':_ID,'masking':_MASKING,'visible':{'type':'boolean'}},('id',))),
    ('set_display','set_display','Persist display-only color-map and range settings for an image.',_object({'id':_ID,'settings':_DISPLAY},('id','settings'))),
    ('display_range','display_range','Compute color limits and a histogram from full-resolution calibrated values without changing data.',_object({
        'id':_ID,'mode':{'type':'string','enum':['full','percentile','roi']},'clip_percent':{'type':'number','minimum':0,'maximum':10},
        'roi':_ROI,'raw':{'type':'boolean'},'operations':_OPS},('id',))),
    ('export_scan','export_scan','Export calibrated CSV or reproducible provenance JSON as text.',_object({'id':_ID,'format':{'type':'string','enum':['csv','json']}},('id',))),
    ('export_session','export_session','Export the complete session provenance manifest as JSON text.',_object({'id':_ID},('id',))),
]


def handle(workbench, request):
    if not isinstance(request, dict) or request.get('jsonrpc') != '2.0':
        return {'jsonrpc':'2.0','id':None,'error':{'code':-32600,'message':'Invalid JSON-RPC request.'}}
    identifier = request.get('id')
    method = request.get('method')
    if identifier is None:
        return None
    response = {'jsonrpc':'2.0','id':identifier}
    params = request.get('params', {})
    if not isinstance(params, dict):
        response['error'] = {'code': -32602, 'message': 'Parameters must be an object.'}
        return response
    if method == 'initialize':
        requested = params.get('protocolVersion')
        version = requested if requested in ('2024-11-05','2025-03-26','2025-06-18') else '2025-06-18'
        response['result'] = {'protocolVersion':version,'capabilities':{'tools':{}},'serverInfo':{'name':'afm-workbench','version':'0.1.0'}}
    elif method == 'ping':
        response['result'] = {}
    elif method == 'tools/list':
        response['result'] = {'tools':[{'name':name,'description':description,'inputSchema':schema} for name,_,description,schema in _TOOLS]}
    elif method == 'tools/call':
        selected = next((t for t in _TOOLS if t[0] == params.get('name')), None)
        if selected is None:
            response['error'] = {'code':-32602,'message':'Unknown tool.'}
        else:
            try:
                result = workbench.dispatch(selected[1], params.get('arguments', {}))
                if isinstance(result, dict):
                    result.pop('data', None)
                response['result'] = {'content':[{'type':'text','text':json.dumps(result, ensure_ascii=False, allow_nan=False)}],'isError':False}
            except (ValueError, TypeError, KeyError, OSError) as exc:
                response['result'] = {'content':[{'type':'text','text':str(exc)}],'isError':True}
            except Exception:
                response['error'] = {'code': -32603, 'message': 'Internal operation error.'}
    else:
        response['error'] = {'code':-32601,'message':'Method not found.'}
    return response


def serve(workbench, input_stream=None, output_stream=None):
    input_stream = input_stream or sys.stdin
    output_stream = output_stream or sys.stdout
    for line in input_stream:
        try:
            if len(line.encode('utf-8')) > MAX_REQUEST_BYTES:
                raise ValueError('Message too large.')
            response = handle(workbench, json.loads(line))
        except (json.JSONDecodeError, ValueError):
            response = {'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':'Invalid JSON.'}}
        if response is not None:
            output_stream.write(json.dumps(response, ensure_ascii=False, allow_nan=False) + '\n')
            output_stream.flush()
