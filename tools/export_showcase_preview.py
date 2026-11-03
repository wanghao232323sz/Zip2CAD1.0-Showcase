"""Extract actual SKP triangles for an offline browser preview. Runs on the SDK main thread."""
import argparse,ctypes as ct,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from zip2cad.release_io import save,read
from zip2cad.sketchup_sdk import SketchUpSDK,Point,Ref

def mesh_payload(meshes,label):
    positions=[];colors=[];normals=[]
    for data in meshes:
        tri=data['vertices_world_m'][data['faces']];owner=data['face_owner_indices']
        if not len(tri):continue
        n=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-12)
        rgba=np.c_[data['face_material_rgb'][owner]/255,np.maximum(data['face_material_opacity'][owner],.18)]
        positions.extend(tri.reshape(-1,3).round(6).tolist());normals.extend(np.repeat(n,3,axis=0).round(5).tolist());colors.extend(np.repeat(rgba,3,axis=0).round(4).tolist())
    if not positions:raise ValueError('Selected SKP contains no visible library geometry')
    return dict(label=label,positions=positions,normals=normals,colors=colors,triangles=len(positions)//3,photographic_textures=False)

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=['original','prediction','final'],required=True);p.add_argument('--receipt',type=Path);a=p.parse_args()
    with SketchUpSDK() as sdk:
        model=sdk.load(a.input)
        try:
            scope=[2041972,2032964,2006195,1905512] if a.mode=='final' else [130901,130899]
            meshes=[sdk.geometry(model,scope=scope,include_appearance=True,visible_only=True)]
            if a.mode=='prediction' and a.receipt:
                meshes.append(sdk.geometry(model,scope=[read(a.receipt)['generated_assembly_pid']],include_appearance=True,visible_only=True))
            if a.mode=='final':
                class Box(ct.Structure):_fields_=[('min',Point),('max',Point)]
                sdk.bind('SUDrawingElementGetBoundingBox',[Ref,ct.POINTER(Box)])
                entities=sdk.ref('SUModelGetEntities',model)
                for kind,plural in [('Group','Groups'),('ComponentInstance','Instances')]:
                    for obj in sdk.list(entities,plural):
                        pid=sdk.pid(kind,obj)
                        if pid==scope[0]:continue
                        b=Box();sdk.call('SUDrawingElementGetBoundingBox',sdk.functions['SUDrawingElementFromEntity'](sdk.entity(kind,obj)),ct.byref(b))
                        lo=np.array([b.min.x,b.min.y,b.min.z])*.0254;hi=np.array([b.max.x,b.max.y,b.max.z])*.0254
                        if np.all(hi>=[4020,-3490,20]) and np.all(lo<=[4100,-3400,40]) and np.max(hi[:2]-lo[:2])<120:
                            meshes.append(sdk.geometry(model,scope=[pid],include_appearance=True,visible_only=True))
        finally:sdk.release(model)
    save(a.output,mesh_payload(meshes,a.mode));print(a.output)

if __name__=='__main__':main()
