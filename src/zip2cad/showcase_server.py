"""Loopback-only web workbench for live inference; no browser-supplied code executes."""
import argparse,inspect,json,mimetypes,os,re,secrets,shutil,subprocess,sys,threading,time,uuid,webbrowser,zipfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from .release_io import read,save,sha
from .showcase import asset

ROOT=Path(__file__).resolve().parents[2]
KINDS={'case':{'.zip'},'original':{'.skp'},'final':{'.skp'},'video':{'.mp4','.avi','.mov'}}
ARTIFACTS={'final':'campus_final_showcase.skp','prediction':'live_predicted_library.skp','report':'run_report.json','geometry':'predicted_geometry.obj','image':'live_prediction.png','joint':'joint_prediction.json','corners':'corner_prediction.json'}

def unpack_case(archive,destination):
    with zipfile.ZipFile(archive) as z:
        if len(z.infolist())>40 or sum(i.file_size for i in z.infolist())>512*1024**2:raise ValueError('Case archive exceeds limits')
        for info in z.infolist():
            target=(destination/info.filename.replace('\\','/')).resolve()
            if not target.is_relative_to(destination.resolve()) or (info.external_attr>>16)&0o170000==0o120000:raise ValueError('Unsafe archive path')
        z.extractall(destination)
    matches=list(destination.rglob('manifest.json'))
    matches=[p for p in matches if read(p).get('schema')=='zip2cad_showcase_case_v1']
    if len(matches)!=1:raise ValueError('Upload the prepared library demo ZIP containing one scene manifest')
    case=matches[0].parent
    for row in read(matches[0])['files'].values():asset(case,row)
    return case

class State:
    def __init__(self,root=ROOT):
        self.root=Path(root);self.token=secrets.token_urlsafe(32);self.jobs={};self.uploads={};self.lock=threading.RLock();self.active=False
        self.base=self.root/'outputs/web';self.base.mkdir(parents=True,exist_ok=True)
        records=sorted((self.base/'jobs').glob('*/web_run.json'),key=lambda p:p.stat().st_mtime)
        for path in records[-10:]:
            record=read(path)
            if not re.fullmatch('[0-9a-f]{32}',record.get('id','')):continue
            record.update(folder=path.parent,out=path.parent/'result')
            if record['status']=='running':record.update(status='failed',error='Previous local service stopped. Start a new inference.')
            self.jobs[record['id']]=record
    def case(self,selections):
        if selections.get('case'):
            return self.uploads[selections['case']]['case']
        return self.root/'artifacts/showcase/library'
    def source(self,kind,selections,job=None):
        if job and kind=='original':
            case=job['folder']/'case'
            return asset(case,read(case/'manifest.json')['files']['original_cad'])
        if job and kind in ['prediction','final']:
            return job['out']/ARTIFACTS[kind]
        if selections.get(kind):return self.uploads[selections[kind]]['path']
        case=self.case(selections);manifest=read(case/'manifest.json')
        return asset(case,manifest['files'][{'original':'original_cad','final':'final_cad'}[kind]])
    def validate(self,selections):
        if not isinstance(selections,dict):raise ValueError('Invalid file selection')
        for kind,uid in selections.items():
            if kind not in KINDS or uid not in self.uploads or self.uploads[uid]['kind']!=kind:raise ValueError('Unknown uploaded input')
    def prepare(self,selections,folder):
        self.validate(selections);case=self.case(selections);manifest=read(case/'manifest.json');dest=folder/'case';dest.mkdir(parents=True)
        for key,row in manifest['files'].items():
            source=asset(case,row)
            kind={'original_cad':'original','final_cad':'final'}.get(key)
            if kind and selections.get(kind):source=self.uploads[selections[kind]]['path']
            target=(dest/row['path']).resolve()
            if not target.is_relative_to(dest.resolve()):raise ValueError('Unsafe case file path')
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
            manifest['files'][key]=dict(path=row['path'],sha256=sha(target),bytes=target.stat().st_size)
        save(dest/'manifest.json',manifest);return dest
    def worker(self,job,selections,mode):
        try:
            case=self.prepare(selections,job['folder'])
            command=[sys.executable,'-u',str(self.root/'tools/run_showcase.py'),'--case',str(case),'--models',str(self.root/'models/pretrained'),'--output',str(job['out']),'--skp',mode]
            with subprocess.Popen(command,cwd=self.root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace') as process:
                for line in process.stdout:
                    with self.lock:
                        job['logs'].append(line.rstrip());match=re.search(r'\[(\d)/5\]',line)
                        if match:job['step']=int(match[1])
                if process.wait():raise RuntimeError('Inference failed. Inspect the live log and verify scene files / SDK.')
            with self.lock:job.update(status='complete',report=read(job['out']/'run_report.json'))
        except Exception as error:
            with self.lock:job.update(status='failed',error=str(error));job['logs'].append(str(error))
        finally:
            with self.lock:self.active=False
            save(job['folder']/'web_run.json',self.public(job))
    def public(self,job):
        return {k:job[k] for k in ['id','status','step','logs','error','report'] if k in job}

class Handler(BaseHTTPRequestHandler):
    server_version='Zip2CAD-Showcase'
    def log_message(self,*args):pass
    @property
    def state(self):return self.server.state
    def json(self,data,code=200):
        body=json.dumps(data,ensure_ascii=False).encode();self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
    def file(self,path,download=False):
        if not path.is_file():return self.json(dict(error='File not available yet'),404)
        self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(path.name)[0] or 'application/octet-stream');self.send_header('Content-Length',str(path.stat().st_size));self.send_header('X-Content-Type-Options','nosniff')
        if download:self.send_header('Content-Disposition','attachment; filename="'+path.name+'"')
        self.end_headers()
        with path.open('rb') as f:shutil.copyfileobj(f,self.wfile)
    def authorized(self):
        host=self.headers.get('Host','')
        if host not in [f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}']:return False
        origin=self.headers.get('Origin')
        if origin and origin not in ['http://'+host]:return False
        return secrets.compare_digest(self.headers.get('X-Showcase-Token',''),self.state.token)
    def body(self):
        length=int(self.headers.get('Content-Length','0'))
        if not 0<length<65536:raise ValueError('Invalid JSON request size')
        return json.loads(self.rfile.read(length))
    def do_GET(self):
        try:
            route=urlparse(self.path);path=route.path
            if path=='/':return self.file(self.state.root/'web/showcase/index.html')
            if path=='/boot.js':
                body=('window.BOOT='+json.dumps(dict(token=self.state.token))+';').encode();self.send_response(200);self.send_header('Content-Type','text/javascript');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();return self.wfile.write(body)
            if path in ['/app.js','/style.css','/viewer.js']:return self.file(self.state.root/'web/showcase'/path[1:])
            if path.startswith('/download/'):
                _,_,jid,kind=path.split('/')
                if jid not in self.state.jobs or kind not in ARTIFACTS:return self.json(dict(error='Unknown artifact'),404)
                return self.file(self.state.jobs[jid]['out']/ARTIFACTS[kind],download=kind not in ['image'])
            if not self.authorized():return self.json(dict(error='Local session authorization required'),403)
            if path=='/api/config':
                case=self.state.root/'artifacts/showcase/library';m=read(case/'manifest.json') if (case/'manifest.json').exists() else None
                from .sketchup_sdk import discover_sdk
                try:discover_sdk();sdk=True
                except Exception:sdk=False
                latest=self.state.public(next(reversed(self.state.jobs.values()))) if self.state.jobs else None
                return self.json(dict(ready=bool(m),sdk=sdk,files=m['files'] if m else {},models=read(self.state.root/'models/pretrained/manifest.json')['models'],latest_job=latest))
            if path=='/api/code':
                from .release_neural import joint_inference,corner_inference
                return self.json(dict(geometry=inspect.getsource(joint_inference),corners=inspect.getsource(corner_inference)))
            if path.startswith('/api/jobs/'):
                job=self.state.jobs[path.rsplit('/',1)[1]]
                with self.state.lock:return self.json(self.state.public(job))
            return self.json(dict(error='Not found'),404)
        except (KeyError,ValueError,FileNotFoundError) as error:self.json(dict(error=str(error)),400)
        except (BrokenPipeError,ConnectionResetError):pass
    def do_POST(self):
        if not self.authorized():return self.json(dict(error='Local session authorization required'),403)
        try:
            route=urlparse(self.path)
            if route.path=='/api/upload':
                query=parse_qs(route.query);kind=query['kind'][0];name=Path(query['name'][0].replace('\\','/')).name
                if kind not in KINDS or Path(name).suffix.lower() not in KINDS[kind]:raise ValueError('Choose the file type shown by this input slot')
                length=int(self.headers.get('Content-Length','0'));limit=2*1024**3 if kind=='video' else 256*1024**2
                if not 0<length<=limit:raise ValueError('Input file size exceeds this slot limit')
                uid=uuid.uuid4().hex;folder=self.state.base/'uploads'/uid;folder.mkdir(parents=True);target=folder/('input'+Path(name).suffix.lower())
                with target.open('wb') as f:
                    remaining=length
                    while remaining:
                        block=self.rfile.read(min(1024**2,remaining))
                        if not block:raise ValueError('Upload interrupted')
                        f.write(block);remaining-=len(block)
                record=dict(kind=kind,path=target,name=name)
                if kind=='case':record['case']=unpack_case(target,folder/'unpacked')
                self.state.uploads[uid]=record;return self.json(dict(id=uid,name=name,bytes=length))
            data=self.body();selections=data.get('uploads',{});self.state.validate(selections)
            if route.path=='/api/run':
                mode=data.get('skp','auto')
                if mode not in ['auto','required','off']:raise ValueError('Invalid SKP mode')
                with self.state.lock:
                    if self.state.active:return self.json(dict(error='A prediction is already running'),409)
                    jid=uuid.uuid4().hex;folder=self.state.base/'jobs'/jid;folder.mkdir(parents=True)
                    job=dict(id=jid,folder=folder,out=folder/'result',logs=[],status='running',step=0);self.state.jobs[jid]=job;self.state.active=True
                threading.Thread(target=self.state.worker,args=(job,selections,mode),daemon=True).start();return self.json(dict(id=jid),202)
            if route.path=='/api/preview':
                kind=data['kind']
                if kind not in ['original','prediction','final']:raise ValueError('Invalid preview selection')
                job=self.state.jobs.get(data.get('job'))
                if kind=='prediction' and not job:raise ValueError('Run inference first')
                if kind=='prediction' and not (job['out']/'live_predicted_library.skp').exists():
                    p=read(job['out']/'joint_prediction.json');vertices=[];normals=[];colors=[]
                    import numpy as np
                    for row in p['components']:
                        tri=np.array(row['vertices_world_CAD_m'])[np.array(row['triangles'])];n=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-12)
                        vertices.extend(tri.reshape(-1,3).tolist());normals.extend(np.repeat(n,3,axis=0).tolist());colors.extend([list(np.array(row['top_color'])/255)+[1]]*(len(tri)*3))
                    return self.json(dict(positions=vertices,normals=normals,colors=colors,triangles=len(vertices)//3,label='本次现场预测几何（未包含原 CAD）'))
                source=self.state.source(kind,selections,job);cache=self.state.base/'preview_cache';cache.mkdir(exist_ok=True)
                output=cache/(sha(source)+'_'+kind+'.json')
                if not output.exists():
                    cmd=[sys.executable,str(self.state.root/'tools/export_showcase_preview.py'),'--input',str(source),'--output',str(output),'--mode',kind]
                    if kind=='prediction':cmd+=['--receipt',str(job['out']/'live_native/sdk_native_receipt.json')]
                    result=subprocess.run(cmd,cwd=self.state.root,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=180)
                    if result.returncode:raise ValueError('SKP 预览转换失败。请安装官方 SDK，或用 SketchUp 打开查看。'+result.stderr[-300:])
                return self.file(output)
            if route.path=='/api/open':
                kind=data['kind'];job=self.state.jobs.get(data.get('job'))
                if kind not in ['original','prediction','final']:raise ValueError('Invalid native file')
                target=self.state.source(kind,selections,job)
                if not target.is_file():raise ValueError('SKP file has not been generated')
                if os.name!='nt':raise ValueError('Native opening is available on Windows; download the SKP instead')
                os.startfile(str(target));return self.json(dict(status='opened'))
            return self.json(dict(error='Not found'),404)
        except Exception as error:self.json(dict(error=str(error)),400)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',type=int,default=8765);p.add_argument('--open',action='store_true');a=p.parse_args(argv)
    server=ThreadingHTTPServer(('127.0.0.1',a.port),Handler);server.state=State();url=f'http://127.0.0.1:{server.server_port}'
    print('Zip2CAD workbench: '+url,flush=True)
    if a.open:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()
