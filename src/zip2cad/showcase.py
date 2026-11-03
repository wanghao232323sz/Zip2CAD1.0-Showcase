"""Fresh pretrained-head inference for the prepared library scene; never trains."""
import argparse,html,json,shutil,time,webbrowser
from pathlib import Path
import numpy as np
from .release_io import read,save,sha

def asset(case,item):
    path=(case/item['path']).resolve()
    if not path.is_relative_to(case):raise ValueError('Case asset escapes bundle')
    if not path.is_file() or sha(path)!=item['sha256']:raise ValueError('Case asset missing or changed: '+item['path'])
    return path

def export_obj(components,path):
    lines=['# Fresh Zip2CAD pretrained geometry-head inference; CAD metres'];offset=1
    for row in components:
        lines.append('o '+row['component_id'])
        lines.extend('v '+' '.join(map(str,v)) for v in row['vertices_world_CAD_m'])
        lines.extend('f '+' '.join(str(int(i)+offset) for i in f) for f in row['triangles'])
        offset+=len(row['vertices_world_CAD_m'])
    path.write_text('\n'.join(lines)+'\n',encoding='utf8')

def figure(prediction,corners,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    from matplotlib.ticker import MaxNLocator
    fig=plt.figure(figsize=(14,6));ax=fig.add_subplot(121,projection='3d');top=fig.add_subplot(122);all_points=[]
    for row,color in zip(prediction['components'],['#586f7c','#cf963e','#6ba58c']):
        vertices=np.asarray(row['vertices_world_CAD_m']);all_points.append(vertices)
        ax.add_collection3d(Poly3DCollection(vertices[np.asarray(row['triangles'])],facecolors=color,edgecolors='#253744',linewidths=.25,alpha=.85))
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
        triangles=vertices[np.asarray(row['triangles'])][np.asarray(row['top_triangle_mask'],dtype=bool)]
        footprint=unary_union([Polygon(tri[:,:2]) for tri in triangles])
        polygons=list(footprint.geoms) if footprint.geom_type=='MultiPolygon' else [footprint]
        for i,polygon in enumerate(polygons):
            boundary=np.asarray(polygon.exterior.coords)
            top.fill(boundary[:,0],boundary[:,1],color=color,alpha=.45,label=row['component_id'].replace('NEURAL_','') if i==0 else None)
    p=np.asarray(corners['predictions_world_m']);all_points.append(p);ax.scatter(*p.T,c='#c94646',s=30)
    top.scatter(p[:,0],p[:,1],c='#c94646',s=35,zorder=5)
    for label,point in zip(corners['landmark_ids'],p):top.annotate(label,point[:2],xytext=(7,7),textcoords='offset points',color='#8b1e1e',weight='bold')
    p=np.vstack(all_points);ax.auto_scale_xyz(*p.T);ax.set_box_aspect(np.maximum(np.ptp(p,axis=0),1))
    ax.set(xlabel='CAD X / m',ylabel='CAD Y / m',zlabel='CAD Z / m',title='Live geometry prediction')
    for axis in [ax.xaxis,ax.yaxis,ax.zaxis]:axis.set_major_locator(MaxNLocator(3))
    ax.tick_params(labelsize=8);top.set_aspect('equal');top.set(xlabel='CAD X / m',ylabel='CAD Y / m',title='Top view and predicted landmarks A-F')
    top.legend(loc='lower left',fontsize=8);top.grid(alpha=.2)
    fig.tight_layout();fig.savefig(path,dpi=150);plt.close(fig)

def run(case,output,models,skp_mode='auto',open_report=False):
    from .release_neural import joint_inference,corner_inference
    case=Path(case).resolve();out=Path(output).resolve();models=Path(models).resolve()
    if out.exists() or case.is_relative_to(out) or models.is_relative_to(out):raise ValueError('Use a fresh output directory separate from inputs/models')
    print('[1/5] Check scene inputs and pretrained weights',flush=True)
    manifest=read(case/'manifest.json')
    if manifest['schema']!='zip2cad_showcase_case_v1':raise ValueError('Unsupported showcase case')
    files={key:asset(case,item) for key,item in manifest['files'].items()}
    model_manifest=read(models/'manifest.json')['models'];weights={}
    for key in ['geometry','corners']:
        path=models/Path(model_manifest[key]['file']).name
        if sha(path)!=model_manifest[key]['sha256']:raise ValueError('Pretrained weight hash differs: '+key)
        weights[key]=path
    out.mkdir(parents=True);started=time.perf_counter();status=dict(status='running',training_executed=False)
    try:
        print('[2/5] Run pretrained room/duct and landmark heads (eval / inference_mode)',flush=True)
        tick=time.perf_counter();prediction=joint_inference(files['joint_grid'].parent,weights['geometry'])
        if prediction.get('smoke_only'):raise ValueError('A smoke-only checkpoint is not a showcase model')
        save(out/'joint_prediction.json',prediction)
        corners=corner_inference(files['corner_points'],weights['corners'],out/'corner_prediction.json',files['corner_contract'])
        inference_seconds=time.perf_counter()-tick
        print('[3/5] Export and visualize the fresh local predictions',flush=True)
        export_obj(prediction['components'],out/'predicted_geometry.obj');figure(prediction,corners,out/'live_prediction.png')
        native=dict(status='not_requested',file=None)
        if skp_mode!='off':
            from .sketchup_sdk import discover_sdk
            try:sdk=discover_sdk()
            except Exception:
                if skp_mode=='required':raise
                native=dict(status='sdk_unavailable',file=None)
            else:
                from .native_skp import write_native
                plan=dict(schema='zip2cad_native_completion_plan_v2',source_model=str(files['original_cad']),
                    source_model_sha256=sha(files['original_cad']),components=prediction['components'],textures_allowed=False,
                    hide_existing_pid_paths=[],view_scope_pid_path=[130901,130899])
                save(out/'live_native_plan.json',plan);receipt=write_native(out/'live_native_plan.json',out/'live_native',sdk)
                shutil.copyfile(receipt['updated_model'],out/'live_predicted_library.skp')
                native=dict(status='fresh_prediction_saved_reloaded_verified',file='live_predicted_library.skp')
        print('[4/5] Copy the prepared full-campus showcase deliverable',flush=True)
        final=out/'campus_final_showcase.skp';shutil.copyfile(files['final_cad'],final)
        if sha(final)!=manifest['files']['final_cad']['sha256']:raise ValueError('Final deliverable copy differs')
        print('[5/5] Write results, provenance and presentation page',flush=True)
        result=dict(status='complete',scene='library',training_executed=False,weights_updated=False,
            input_mode='cached_ZipMap_observations_and_frozen_features',ZipMap_reconstructed_live=False,
            Sonata_features_recomputed_live=False,neural_heads_executed_live=['geometry','corners'],
            inference_seconds=inference_seconds,elapsed_seconds=time.perf_counter()-started,
            components=len(prediction['components']),landmarks=len(corners['landmark_ids']),
            checkpoint_sha256={k:sha(v) for k,v in weights.items()},native_prediction=native,
            final_model=dict(file=final.name,sha256=sha(final),role='precomputed_full_campus_showcase_deliverable',generated_by_this_inference=False),
            case_manifest_sha256=sha(case/'manifest.json'),independent_accuracy_validation=False)
        for key,path in weights.items():
            if sha(path)!=model_manifest[key]['sha256']:raise ValueError('Weights changed during inference')
        save(out/'run_report.json',result)
        room=prediction['physical_parameters']['room'];rows=''.join('<tr><td>'+html.escape(str(k))+'</td><td>'+html.escape(str(v))+'</td></tr>' for k,v in room.items())
        native_link='<a href="live_predicted_library.skp">现场预测的图书馆 SKP</a> · ' if native['file'] else ''
        page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Zip2CAD · 图书馆现场推理</title>
<style>body{font:16px/1.75 system-ui,"Microsoft YaHei",sans-serif;max-width:1080px;margin:40px auto;padding:0 24px;color:#20383e;background:#f7f8f5}h1{font-size:34px}section{background:white;padding:24px;margin:20px 0;border:1px solid #dce3de}img{width:100%}a{color:#146556}td{padding:8px 18px;border-bottom:1px solid #ddd}small{color:#53685f}</style>
<p>Zip2CAD / 毕业项目演示</p><h1>图书馆：从观测到可编辑几何</h1>
<p>预处理观测 → 加载训练后模型 → 现场前向推理 → 预测几何与关键点 → 完整校园成品展示</p>
<section><h2>本次现场预测</h2><p>生成 1 间房体、2 条风管及 ABCDEF 六个关键点。无训练、无权重更新。</p><p>任务头推理用时：TIME 秒。</p>
<img src="live_prediction.png" alt="本次现场模型预测"><p>NATIVE<a href="predicted_geometry.obj">现场预测 OBJ</a> · <a href="joint_prediction.json">房体/风管参数</a> · <a href="corner_prediction.json">六角点坐标</a></p><table>ROWS</table></section>
<section><h2>完整校园成品</h2><p><a href="campus_final_showcase.skp">打开完整校园展示 SKP</a></p>
<p>此文件为提前完成并保存的项目成品，现场按哈希校验后复制。完整校园及其细节不是本次两个任务头即时生成的结果。</p></section>
<section><h2>演示范围与可追溯性</h2><p>ZipMap 观测、冻结特征与坐标契约提前准备；现场重新计算几何头和六角点头。当前模型为单图书馆开发案例，未在独立建筑上验证。</p>
<p><a href="run_report.json">查看本次推理日志、输入契约哈希与模型哈希</a></p></section></html>'''
        page=page.replace('TIME',f'{inference_seconds:.3f}').replace('NATIVE',native_link).replace('ROWS',rows)
        (out/'index.html').write_text(page,encoding='utf8');status=result
        if open_report:webbrowser.open((out/'index.html').as_uri())
        return out
    except Exception as error:
        status.update(status='failed',error=str(error));raise
    finally:save(out/'run_status.json',status)

def main(argv=None):
    from datetime import datetime
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case',type=Path,default=Path('artifacts/showcase/library'))
    p.add_argument('--models',type=Path,default=Path('models/pretrained'))
    p.add_argument('--output',type=Path)
    p.add_argument('--skp',choices=['auto','required','off'],default='auto')
    p.add_argument('--open',action='store_true')
    p.add_argument('--verbose',action='store_true',help='Print actual input, checkpoint, source, forward-layer and SKP diagnostics')
    p.add_argument('--presentation-seconds',type=float,default=0,help='Minimum CLI presentation duration; explicit holds are separately recorded')
    p.add_argument('--step-by-step',action='store_true',help='Require Enter before each of the five real pipeline stages')
    p.add_argument('--folder-menu',action='store_true',help='After success, accept 0 + Enter to open this output folder')
    a=p.parse_args(argv);out=a.output or Path('outputs')/('showcase_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    if a.step_by_step and (a.presentation_seconds or a.open):p.error('--step-by-step cannot be combined with --presentation-seconds or --open')
    try:
        if a.verbose or a.presentation_seconds or a.step_by_step:
            from .showcase_console import run_presented
            result=run_presented(a.case,out,a.models,a.skp,a.presentation_seconds,a.step_by_step)
        else:result=run(a.case,out,a.models,a.skp,a.open)
        print(result)
        if a.folder_menu:
            from .showcase_console import output_folder_menu
            output_folder_menu(result)
    except (EOFError,KeyboardInterrupt):
        print('\nRun stopped: no next-step confirmation received. Restart in an interactive terminal.',flush=True);return 1
    except RuntimeError as error:
        from .showcase_console import StageCancelled
        if isinstance(error,StageCancelled):print('Run cancelled. Remaining steps were not executed.',flush=True);return 1
        raise

if __name__=='__main__':main()
