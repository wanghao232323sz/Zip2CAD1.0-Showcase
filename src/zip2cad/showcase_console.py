"""Detailed, paced CLI presentation of real inference, with explicit presentation holds."""
import contextlib,inspect,io,json,sys,time,os,re
from pathlib import Path
import numpy as np
from .release_io import read,save,sha

class StageCancelled(RuntimeError):pass

def output_folder_menu(output,input_fn=None,opener=None):
    """Use normal line input so both digit 0 and letter O work in CMD/Terminal."""
    output=Path(output).resolve()
    if not output.is_dir():raise FileNotFoundError(output)
    input_fn=input_fn or input;opener=opener or os.startfile
    while True:
        value=input_fn('\n[0] Open output folder  [Q] Exit (type a choice, then press Enter): ').strip().upper()
        if value in ['0','O']:
            opener(str(output));return True
        if value=='Q':return False
        print('Type 0 and press Enter to open the output folder, or type Q to exit.',flush=True)

class Console:
    def __init__(self,stream,seconds,step_by_step=False):
        self.stream=stream;self.seconds=seconds;self.started=time.perf_counter();self.hold_seconds=0.;self.lines=[];self.pending='';self.readout_enabled=False
        self.step_by_step=step_by_step;self.manual_wait_seconds=0.;self.confirmed_stages=[];self.on_stage=None
    def confirm_stage(self,number):
        if number>1:self.emit(f'Step {number-1}/5 completed.')
        titles=['Input and checkpoint validation','Neural forward inference','Geometry and native SKP export','Full-campus deliverable preparation','Output records and verification']
        self.emit(f'Step {number}/5: {titles[number-1]}. Press Enter to run, or type Q then Enter to cancel.')
        begin=time.perf_counter()
        try:
            while True:
                value=input().strip().upper()
                if value=='Q':raise StageCancelled('Remaining steps cancelled by user')
                if value=='':break
                self.emit('Press Enter to run the next step, or type Q then Enter to cancel.')
        finally:self.manual_wait_seconds+=time.perf_counter()-begin
        self.confirmed_stages.append(number);self.emit(f'CONTROL | Step {number}/5 confirmed')
    def emit(self,message):
        line=f'[{time.perf_counter()-self.started:06.2f}s] {message}'
        self.lines.append(line);self.stream.write(line+'\n');self.stream.flush()
        if self.readout_enabled and self.seconds:
            begin=time.perf_counter();time.sleep(.05);self.hold_seconds+=time.perf_counter()-begin
    def hold_until(self,elapsed,label):
        remaining=self.started+elapsed-time.perf_counter()
        if remaining<=.05:return
        self.emit(f'PRESENTATION HOLD | {label} | about {remaining:.1f}s; not model computation')
        while True:
            remaining=self.started+elapsed-time.perf_counter()
            if remaining<=0:break
            duration=min(2.,remaining);begin=time.perf_counter();time.sleep(duration);self.hold_seconds+=time.perf_counter()-begin
            self.emit(f'PRESENTATION HOLD | {max(0.,self.started+elapsed-time.perf_counter()):.1f}s remaining')
    def write(self,text):
        self.pending+=text
        while '\n' in self.pending:
            line,self.pending=self.pending.split('\n',1)
            match=re.match(r'^\[([1-5])/5\]',line)
            if match and self.step_by_step:self.confirm_stage(int(match[1]))
            if match and self.on_stage:self.on_stage(int(match[1]))
            if line.startswith('[2/5]'):self.hold_until(self.seconds*.2,'input contract explanation')
            elif line.startswith('[3/5]'):self.hold_until(self.seconds*.45,'neural prediction explanation')
            elif line.startswith('[4/5]'):self.hold_until(self.seconds*.78,'native geometry inspection')
            elif line.startswith('[5/5]'):self.hold_until(self.seconds*.90,'delivery provenance explanation')
            if line:self.emit(line)
        return len(text)
    def flush(self):self.stream.flush()

def describe_inputs(console,case,models):
    console.readout_enabled=True
    console.emit('ZIP2CAD | LIBRARY PRETRAINED INFERENCE | DETAILED EXECUTION')
    if getattr(console,'command_steps',False):console.emit('Mode: separate Python commands | No training or weight updates')
    elif console.step_by_step:console.emit('Mode: five manually confirmed steps | Enter to advance | No training or weight updates')
    elif console.seconds:console.emit('SOURCE READOUT | source/metadata lines are paced for explanation; this is presentation time, not inference time')
    console.emit('Training: OFF | Parameter updates: OFF | Input preprocessing: prepared observations')
    if not console.step_by_step and not getattr(console,'command_steps',False):console.emit(f'Presentation target: {console.seconds:.0f}s minimum; actual computation may take longer.')
    manifest=read(case/'manifest.json')
    for key,row in manifest['files'].items():
        console.emit(f'INPUT {key:18s} | {row["path"]} | {row.get("bytes",0):,} bytes | sha256={row["sha256"]}')
    contract=read(case/manifest['files']['joint_contract']['path'])
    console.emit('CONTRACT frame = '+json.dumps(contract['frame'],ensure_ascii=False,separators=(',',':')))
    with np.load(case/manifest['files']['joint_grid']['path']) as z:
        x=z['features'];console.emit(f'GRID shape={x.shape} dtype={x.dtype} finite={bool(np.isfinite(x).all())}')
        channels=contract.get('feature_channels',[])
        for index,plane in enumerate(x):
            name=channels[index] if index<len(channels) else f'channel_{index:02d}'
            console.emit(f'GRID {index:02d} {name:28s} | min={plane.min():.5f} mean={plane.mean():.5f} max={plane.max():.5f} nonzero={np.count_nonzero(plane):,}')
    with np.load(case/manifest['files']['corner_points']['path']) as z:
        points=z['points_world_m'] if 'points_world_m' in z else z['points_CAD_m']
        refs=z['source_refs'] if 'source_refs' in z else z['frame_refs']
        console.emit(f'LANDMARK INPUT | points={len(points):,} | sampling=4096 | bounds_m={np.array([points.min(0),points.max(0)]).round(4).tolist()}')
        for ref,count in zip(*np.unique(refs,return_counts=True)):console.emit(f'OBSERVATION VIEW ref={int(ref)} | retained_points={int(count):,}')
    import torch
    mm=read(models/'manifest.json')['models']
    for key in ['geometry','corners']:
        path=models/Path(mm[key]['file']).name;state=torch.load(path,map_location='cpu',weights_only=True);weights=state['model']
        console.emit(f'CHECKPOINT {key} | tensors={len(weights)} | parameters={sum(v.numel() for v in weights.values()):,} | sha256={sha(path)}')
        for name,tensor in weights.items():console.emit(f'WEIGHT {key}.{name} | shape={tuple(tensor.shape)} dtype={tensor.dtype}')
    from .release_neural import joint_inference,corner_inference
    for fn in [joint_inference,corner_inference]:
        console.emit('SOURCE | '+fn.__module__+'.'+fn.__name__+' (actual executed source)')
        for index,line in enumerate(inspect.getsource(fn).splitlines(),1):console.emit(f'CODE {index:03d} | {line}')

def run_presented(case,output,models,skp_mode='auto',seconds=60,step_by_step=False):
    if not 0<=seconds<=300:raise ValueError('Presentation seconds must be between 0 and 300')
    if step_by_step and seconds:raise ValueError('Manual steps cannot use a fixed presentation duration')
    from .showcase import run
    console=Console(sys.stdout,seconds,step_by_step);out=Path(output).resolve();case=Path(case).resolve();models=Path(models).resolve();hook=None
    if out.exists():raise FileExistsError('Use a fresh output directory')
    try:
        if step_by_step:
            console.emit('Zip2CAD Library Inference | 5 steps | Confirm each step before execution')
            def on_stage(number):
                if number==1:describe_inputs(console,case,models);console.readout_enabled=False
            console.on_stage=on_stage
        else:describe_inputs(console,case,models);console.readout_enabled=False
        import torch
        counter=[0]
        def shape(value):
            if isinstance(value,torch.Tensor):return tuple(value.shape)
            if isinstance(value,(tuple,list)):return [shape(v) for v in value]
            return type(value).__name__
        def forward(module,inputs,result):
            if any(module.children()):return
            counter[0]+=1
            console.emit(f'FORWARD {counter[0]:03d} | {module.__class__.__name__:18s} | {shape(inputs)} -> {shape(result)} | inference_mode={torch.is_inference_mode_enabled()}')
        hook=torch.nn.modules.module.register_module_forward_hook(forward)
        with contextlib.redirect_stdout(console):run(case,out,models,skp_mode,open_report=False)
        prediction=read(out/'joint_prediction.json');corners=read(out/'corner_prediction.json')
        for part in prediction['components']:
            p=np.asarray(part['vertices_world_CAD_m'])
            console.emit(f'GEOMETRY {part["component_id"]} | vertices={len(p)} triangles={len(part["triangles"])} | bounds_m={np.array([p.min(0),p.max(0)]).round(5).tolist()}')
        for name,p in zip(corners['landmark_ids'],corners['predictions_world_m']):console.emit(f'LANDMARK {name} | CAD metres = '+json.dumps(p))
        receipt=out/'live_native/sdk_native_receipt.json'
        if receipt.is_file():
            data=read(receipt)
            for row in data['component_rows']:
                console.emit(f'SKP ROUNDTRIP {row["component_id"]} | manifold={row["native_manifold"]} volume={row["volume_m3"]:.6f}m3 | surface_error={row["maximum_bidirectional_surface_error_m"]:.3e}m')
            console.emit(f'SOURCE PROTECTION | original_geometry_hierarchy_materials_preserved={data["original_geometry_hierarchy_materials_preserved"]}')
        for path in sorted(out.iterdir()):
            if path.is_file() and path.name not in ['run_report.json','run_status.json']:console.emit(f'ARTIFACT {path.name:32s} | {path.stat().st_size:,} bytes | sha256={sha(path)}')
        console.hold_until(seconds,'inference and export complete; review results before opening SketchUp')
        report=read(out/'run_report.json')
        elapsed=time.perf_counter()-console.started
        if step_by_step:
            report['interaction']=dict(mode='manual_five_steps',confirmed_stages=console.confirmed_stages,
                elapsed_seconds=elapsed,keyboard_wait_seconds=console.manual_wait_seconds,
                work_and_logging_seconds=elapsed-console.manual_wait_seconds,forward_layers_logged=counter[0],automatic_browser_opened=False)
        else:report['presentation']=dict(enabled=True,target_minimum_seconds=seconds,
            elapsed_seconds=elapsed,explicit_hold_seconds=console.hold_seconds,
            work_and_logging_seconds=elapsed-console.hold_seconds,forward_layers_logged=counter[0],automatic_browser_opened=False)
        save(out/'run_report.json',report);save(out/'run_status.json',report)
        for name in ['run_report.json','run_status.json']:
            path=out/name;console.emit(f'ARTIFACT {name:32s} | {path.stat().st_size:,} bytes | sha256={sha(path)}')
        (out/'OUTPUT_README.txt').write_text('Prepared full-campus showcase deliverable: campus_final_showcase.skp\nFreshly predicted library SKP: live_predicted_library.skp (requires SDK)\nFull terminal transcript: console_transcript.log\nRun report: run_report.json (inference and keyboard interaction times recorded separately)\n',encoding='utf8')
        marker=Path(__file__).resolve().parents[2]/'outputs/latest_cli_output.txt';marker.parent.mkdir(exist_ok=True);marker.write_text(str(out),encoding='utf8')
        if step_by_step:console.emit(f'All five steps completed | elapsed={elapsed:.2f}s | neural_inference={report["inference_seconds"]:.3f}s | keyboard_interaction={console.manual_wait_seconds:.2f}s')
        else:console.emit(f'COMPLETE | presentation={elapsed:.2f}s | neural_inference={report["inference_seconds"]:.3f}s | explicit_holds={console.hold_seconds:.2f}s')
        console.emit('SKETCHUP DEMO | campus_final_showcase.skp = prepared full-campus deliverable')
        console.emit('SKETCHUP DEMO | live_predicted_library.skp = fresh neural prediction')
        console.emit('OUTPUT FOLDER: '+str(out));console.emit('FOLDER LINK: '+out.as_uri())
        return out
    except Exception as error:
        console.readout_enabled=False
        console.emit('FAILED | '+str(error));raise
    finally:
        if hook is not None:hook.remove()
        if out.is_dir():(out/'console_transcript.log').write_text('\n'.join(console.lines)+'\n',encoding='utf8')
