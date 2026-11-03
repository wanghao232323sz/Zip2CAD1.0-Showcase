"""Five independently invoked, checkpointed inference commands. No automatic advance."""
import argparse,contextlib,sys,time,uuid
from datetime import datetime
from pathlib import Path
from .release_io import read,save,sha
from .showcase import asset,export_obj,figure
from .showcase_console import Console,describe_inputs,output_folder_menu

ROOT=Path(__file__).resolve().parents[2]
TITLES=['Input and checkpoint validation','Neural forward inference','Geometry and native SKP export','Full-campus deliverable preparation','Final verification and output records']

def validate_previous(state,step,out):
    if str(step) in state['completed']:raise ValueError(f'Step {step} is already complete. Run the next command, or python step1.py --new-run.')
    for number in range(1,step):
        row=state['completed'].get(str(number))
        if not row:raise ValueError(f'Step {number} is required first. Run: python step{number}.py')
        for name,digest in row['output_hashes'].items():
            path=(out/name).resolve()
            if not path.is_relative_to(out.resolve()) or not path.is_file() or sha(path)!=digest:raise ValueError('Previous output missing or changed: '+name)

def validate_sources(state):
    case=Path(state['case']);models=Path(state['models'])
    if sha(case/'manifest.json')!=state['case_manifest_sha256']:raise ValueError('Scene manifest changed after step 1')
    files={key:asset(case,row) for key,row in read(case/'manifest.json')['files'].items()}
    weights={key:models/(key+'.pt') for key in ['geometry','corners']}
    for key,path in weights.items():
        if sha(path)!=state['weights'][key]:raise ValueError('Model weights changed after step 1: '+key)
    return files,weights

def execute(step,root=ROOT,new_run=False,output=None,skp='auto'):
    root=Path(root).resolve();pointer=root/'outputs/current_stepwise_run.json';pointer.parent.mkdir(exist_ok=True)
    if step==1:
        if pointer.exists() and not new_run:
            old=read(pointer)
            if old['status']!='complete':raise ValueError('An unfinished run exists. Continue its next step, or use python step1.py --new-run.')
        case=root/'artifacts/showcase/library';models=root/'models/pretrained'
        manifest=read(case/'manifest.json')
        if manifest['schema']!='zip2cad_showcase_case_v1':raise ValueError('Unsupported scene bundle')
        for row in manifest['files'].values():asset(case,row)
        model_manifest=read(models/'manifest.json')['models'];weights={}
        for key in ['geometry','corners']:
            path=models/(key+'.pt');weights[key]=sha(path)
            if weights[key]!=model_manifest[key]['sha256']:raise ValueError('Model hash differs: '+key)
        out=Path(output).resolve() if output else root/'outputs'/('stepwise_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        if out.exists() or case.is_relative_to(out) or models.is_relative_to(out) or out.is_relative_to(case) or out.is_relative_to(models):raise ValueError('Use a fresh output directory separate from scene/models')
        out.mkdir(parents=True)
        state=dict(schema='zip2cad_stepwise_v1',status='running',case=str(case),models=str(models),output=str(out),
            case_manifest_sha256=sha(case/'manifest.json'),weights=weights,skp=skp,completed={})
        save(pointer,state)
    else:
        if not pointer.is_file():raise ValueError('No active run. Start with: python step1.py')
        state=read(pointer);out=Path(state['output']).resolve();validate_previous(state,step,out)
    console=Console(sys.stdout,0);console.command_steps=True;started=time.perf_counter()
    console.emit(f'STEP {step}/5 | {TITLES[step-1]}')
    try:
        with contextlib.redirect_stdout(console):
            files,weights=validate_sources(state);generated=[]
            if step==1:
                describe_inputs(console,Path(state['case']),Path(state['models']))
                save(out/'01_inputs.json',dict(case_manifest_sha256=state['case_manifest_sha256'],checkpoint_sha256=state['weights'],input_files=read(Path(state['case'])/'manifest.json')['files']))
                generated=['01_inputs.json']
            elif step==2:
                import torch
                from .release_neural import joint_inference,corner_inference
                count=[0]
                def shape(x):
                    if isinstance(x,torch.Tensor):return tuple(x.shape)
                    if isinstance(x,(list,tuple)):return [shape(v) for v in x]
                    return type(x).__name__
                def forward(module,inputs,result):
                    if any(module.children()):return
                    count[0]+=1;console.emit(f'FORWARD {count[0]:03d} | {type(module).__name__} | {shape(inputs)} -> {shape(result)} | inference_mode={torch.is_inference_mode_enabled()}')
                hook=torch.nn.modules.module.register_module_forward_hook(forward);tick=time.perf_counter()
                try:
                    prediction=joint_inference(files['joint_grid'].parent,weights['geometry'])
                    if prediction.get('smoke_only'):raise ValueError('Smoke-only checkpoint cannot be used for delivery')
                    save(out/'joint_prediction.json',prediction)
                    corners=corner_inference(files['corner_points'],weights['corners'],out/'corner_prediction.json',files['corner_contract'])
                finally:hook.remove()
                state['inference_seconds']=time.perf_counter()-tick;state['forward_layers']=count[0]
                for row in prediction['components']:console.emit(f'PREDICTED {row["component_id"]} | vertices={len(row["vertices_world_CAD_m"])} triangles={len(row["triangles"])}')
                for name,p in zip(corners['landmark_ids'],corners['predictions_world_m']):console.emit(f'LANDMARK {name} | CAD_m={p}')
                generated=['joint_prediction.json','corner_prediction.json']
            elif step==3:
                prediction=read(out/'joint_prediction.json');corners=read(out/'corner_prediction.json')
                export_obj(prediction['components'],out/'predicted_geometry.obj');figure(prediction,corners,out/'live_prediction.png')
                generated=['predicted_geometry.obj','live_prediction.png'];native=dict(status='not_requested',file=None)
                if state['skp']!='off':
                    from .sketchup_sdk import discover_sdk
                    try:sdk=discover_sdk()
                    except Exception:
                        if state['skp']=='required':raise
                        native=dict(status='sdk_unavailable',file=None);console.emit('SDK unavailable; OBJ and prediction image exported.')
                    else:
                        import shutil
                        from .native_skp import write_native
                        plan=dict(schema='zip2cad_native_completion_plan_v2',source_model=str(files['original_cad']),source_model_sha256=sha(files['original_cad']),
                            components=prediction['components'],textures_allowed=False,hide_existing_pid_paths=[],view_scope_pid_path=[130901,130899])
                        save(out/'live_native_plan.json',plan)
                        receipt=write_native(out/'live_native_plan.json',out/('native_'+uuid.uuid4().hex[:8]),sdk)
                        shutil.copyfile(receipt['updated_model'],out/'live_predicted_library.skp')
                        receipt_path=Path(receipt['updated_model']).parent/'sdk_native_receipt.json'
                        native=dict(status='fresh_prediction_saved_reloaded_verified',file='live_predicted_library.skp',receipt=receipt_path.relative_to(out).as_posix())
                        generated+=['live_native_plan.json','live_predicted_library.skp',native['receipt']]
                        for row in receipt['component_rows']:console.emit(f'SKP VERIFIED {row["component_id"]} | manifold={row["native_manifold"]} | surface_error={row["maximum_bidirectional_surface_error_m"]:.3e}m')
                state['native_prediction']=native
            elif step==4:
                import shutil
                shutil.copyfile(files['final_cad'],out/'campus_final_showcase.skp')
                if sha(out/'campus_final_showcase.skp')!=sha(files['final_cad']):raise ValueError('Final deliverable copy differs')
                console.emit('Full-campus file copied and SHA-256 verified. This is a prepared deliverable, separate from live predictions.')
                generated=['campus_final_showcase.skp']
            else:
                prediction=read(out/'joint_prediction.json');corners=read(out/'corner_prediction.json')
                result=dict(status='complete',mode='separate_python_commands',training_executed=False,weights_updated=False,
                    steps_completed=[1,2,3,4,5],inference_seconds=state['inference_seconds'],forward_layers_logged=state['forward_layers'],
                    components=len(prediction['components']),landmarks=len(corners['landmark_ids']),checkpoint_sha256=state['weights'],
                    native_prediction=state['native_prediction'],automatic_browser_opened=False,
                    final_model=dict(file='campus_final_showcase.skp',sha256=sha(out/'campus_final_showcase.skp'),generated_by_this_inference=False),
                    input_mode='cached_ZipMap_observations_and_frozen_features',step_timings={k:v['elapsed_seconds'] for k,v in state['completed'].items()})
                save(out/'run_report.json',result)
                (out/'OUTPUT_README.txt').write_text('Prepared full-campus deliverable: campus_final_showcase.skp\nLive predicted library: live_predicted_library.skp (when SDK is available)\nPer-step logs: step1.log through step5.log\nRun report: run_report.json\n',encoding='utf8')
                generated=['run_report.json','OUTPUT_README.txt']
            for name in generated:console.emit(f'ARTIFACT {name} | sha256={sha(out/name)}')
        state['completed'][str(step)]=dict(elapsed_seconds=time.perf_counter()-started,output_hashes={name:sha(out/name) for name in generated})
        state['status']='complete' if step==5 else 'running';state.pop('error',None);save(pointer,state);save(out/'stepwise_run.json',state)
        if step==5:
            (root/'outputs/latest_cli_output.txt').write_text(str(out),encoding='utf8');console.emit('ALL FIVE STEPS COMPLETE');console.emit('OUTPUT FOLDER: '+str(out))
        else:console.emit(f'Step {step}/5 complete. Returned to the terminal. Next command: python step{step+1}.py')
        return out
    except Exception as error:
        state.update(status='failed',error=str(error));save(pointer,state);console.emit('FAILED | '+str(error));raise
    finally:(out/f'step{step}.log').write_text('\n'.join(console.lines)+'\n',encoding='utf8')

def main(step):
    p=argparse.ArgumentParser(description=f'Zip2CAD step {step}: {TITLES[step-1]}')
    if step==1:
        p.add_argument('--new-run',action='store_true');p.add_argument('--output',type=Path);p.add_argument('--skp',choices=['auto','required','off'],default='auto')
    if step==5:p.add_argument('--no-menu',action='store_true')
    a=p.parse_args()
    try:
        out=execute(step,new_run=getattr(a,'new_run',False),output=getattr(a,'output',None),skp=getattr(a,'skp','auto'))
        if step==5 and not a.no_menu:output_folder_menu(out)
        return 0
    except (EOFError,KeyboardInterrupt):print('Command stopped. Completed outputs remain available.',flush=True);return 1
    except Exception as error:print('ERROR | '+str(error),flush=True);return 1
