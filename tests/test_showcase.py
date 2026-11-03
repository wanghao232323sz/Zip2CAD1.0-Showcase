import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from zip2cad.showcase import run,asset
from zip2cad.release_io import save,sha

class ShowcaseTests(unittest.TestCase):
    def test_asset_rejects_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);case=root/'case';case.mkdir();f=root/'external';f.write_bytes(b'x')
            with self.assertRaisesRegex(ValueError,'escapes'):asset(case,dict(path='../external',sha256=sha(f)))

    def test_asset_rejects_changed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            case=Path(tmp);f=case/'input';f.write_bytes(b'x');digest=sha(f);f.write_bytes(b'y')
            with self.assertRaisesRegex(ValueError,'changed'):asset(case,dict(path='input',sha256=digest))

    def test_live_heads_run_before_final_copy_without_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);case=root/'case';case.mkdir();models=root/'models';models.mkdir();out=root/'run'
            files={}
            for key in ['joint_grid','corner_points','corner_contract','original_cad','final_cad']:
                f=case/key;f.write_bytes(b'prepared input');files[key]=dict(path=f.name,sha256=sha(f))
            save(case/'manifest.json',dict(schema='zip2cad_showcase_case_v1',files=files))
            weights={}
            for key in ['geometry','corners']:
                f=models/(key+'.pt');f.write_bytes(b'weights');weights[key]=dict(file=f.name,sha256=sha(f))
            save(models/'manifest.json',dict(models=weights))
            calls=[]
            def joint(*args):
                self.assertFalse((out/'campus_final_showcase.skp').exists());calls.append('joint')
                return dict(components=[],physical_parameters=dict(room={}))
            def corners(inputs,checkpoint,output,contract):
                self.assertFalse((out/'campus_final_showcase.skp').exists());calls.append('corners')
                result=dict(landmark_ids=list('ABCDEF'),predictions_world_m=np.zeros((6,3)).tolist());save(output,result);return result
            with patch('zip2cad.release_neural.joint_inference',side_effect=joint),patch('zip2cad.release_neural.corner_inference',side_effect=corners),patch('zip2cad.showcase.figure'),patch('zip2cad.release_neural.train_joint',side_effect=AssertionError('Training called')),patch('zip2cad.release_neural.train_corners',side_effect=AssertionError('Training called')):
                run(case,out,models,skp_mode='off')
            self.assertEqual(calls,['joint','corners']);report=json.loads((out/'run_report.json').read_text())
            self.assertFalse(report['training_executed']);self.assertFalse(report['final_model']['generated_by_this_inference'])
            self.assertEqual(sha(out/'campus_final_showcase.skp'),files['final_cad']['sha256'])
            with self.assertRaisesRegex(ValueError,'fresh output'):run(case,out,models,skp_mode='off')

if __name__=='__main__':unittest.main()
