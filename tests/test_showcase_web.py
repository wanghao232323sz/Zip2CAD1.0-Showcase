import io,json,tempfile,threading,unittest,zipfile
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from zip2cad.showcase_server import State,Handler,ThreadingHTTPServer,unpack_case
from zip2cad.release_io import save,sha

class ShowcaseWebTests(unittest.TestCase):
    def test_archive_cannot_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);archive=root/'case.zip'
            with zipfile.ZipFile(archive,'w') as z:z.writestr('../escape.txt','bad')
            with self.assertRaisesRegex(ValueError,'Unsafe archive'):unpack_case(archive,root/'target')
            self.assertFalse((root/'escape.txt').exists())

    def test_packaged_case_resolves_relative_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);archive=root/'case.zip';payload=b'observed input'
            import hashlib
            manifest=dict(schema='zip2cad_showcase_case_v1',files=dict(grid=dict(path='grid.npz',sha256=hashlib.sha256(payload).hexdigest())))
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr('artifacts/showcase/library/manifest.json',json.dumps(manifest));z.writestr('artifacts/showcase/library/grid.npz',payload)
            case=unpack_case(archive,root/'target');self.assertEqual((case/'grid.npz').read_bytes(),payload)

    def test_prepared_overrides_do_not_mutate_builtin_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);case=root/'artifacts/showcase/library';case.mkdir(parents=True)
            original=case/'original.skp';original.write_bytes(b'original')
            save(case/'manifest.json',dict(schema='zip2cad_showcase_case_v1',files=dict(original_cad=dict(path='original.skp',sha256=sha(original)))))
            alternate=root/'selected.skp';alternate.write_bytes(b'new selection');state=State(root)
            state.uploads['selected']=dict(kind='original',path=alternate)
            result=state.prepare(dict(original='selected'),root/'job')
            self.assertEqual((result/'original.skp').read_bytes(),b'new selection');self.assertEqual(original.read_bytes(),b'original')
            self.assertEqual(json.loads((result/'manifest.json').read_text())['files']['original_cad']['sha256'],sha(alternate))

    def test_mutation_requires_session_token_and_same_origin(self):
        with tempfile.TemporaryDirectory() as tmp:
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.state=State(tmp)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();url=f'http://127.0.0.1:{server.server_port}/api/run'
            try:
                for headers in [{},{'X-Showcase-Token':server.state.token,'Origin':'https://other.example'}]:
                    request=Request(url,data=b'{}',headers=headers)
                    with self.assertRaises(HTTPError) as error:urlopen(request)
                    self.assertEqual(error.exception.code,403)
            finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
