import tempfile,unittest
from pathlib import Path
from zip2cad.showcase_steps import validate_previous,validate_sources
from zip2cad.release_io import save,sha

class SeparateStepTests(unittest.TestCase):
    def test_missing_previous_step_and_duplicate_step_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.assertRaisesRegex(ValueError,'Step 1 is required'):validate_previous(dict(completed={}),2,root)
            with self.assertRaisesRegex(ValueError,'already complete'):validate_previous(dict(completed={'2':dict(output_hashes={})}),2,root)

    def test_changed_previous_output_blocks_next_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);f=root/'prediction.json';f.write_text('original')
            state=dict(completed={'1':dict(output_hashes={'prediction.json':sha(f)})})
            validate_previous(state,2,root);f.write_text('changed')
            with self.assertRaisesRegex(ValueError,'changed'):validate_previous(state,2,root)

    def test_model_change_between_commands_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);models=root/'models';models.mkdir();case=root/'case';case.mkdir()
            save(case/'manifest.json',dict(files={}))
            for name in ['geometry','corners']:(models/(name+'.pt')).write_bytes(b'weights')
            state=dict(case=str(case),models=str(models),case_manifest_sha256=sha(case/'manifest.json'),weights={name:sha(models/(name+'.pt')) for name in ['geometry','corners']})
            validate_sources(state);(models/'geometry.pt').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'weights changed'):validate_sources(state)

if __name__=='__main__':unittest.main()
