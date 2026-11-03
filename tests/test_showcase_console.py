import io,unittest
from unittest.mock import patch
from zip2cad.showcase_console import Console,run_presented,output_folder_menu,StageCancelled

class ConsolePresentationTests(unittest.TestCase):
    def test_holds_are_explicit_and_do_not_delay_already_slow_computation(self):
        now=[0.];waits=[]
        def sleep(seconds):waits.append(seconds);now[0]+=seconds
        with patch('zip2cad.showcase_console.time.perf_counter',side_effect=lambda:now[0]),patch('zip2cad.showcase_console.time.sleep',side_effect=sleep):
            output=io.StringIO();console=Console(output,60);console.write('[2/5] Real inference\n')
            self.assertAlmostEqual(sum(waits),12);self.assertAlmostEqual(console.hold_seconds,12)
            self.assertIn('not model computation',output.getvalue())
            now[0]=80;console.hold_until(60,'finished');self.assertAlmostEqual(sum(waits),12)

    def test_zero_target_preserves_full_logs_without_sleep(self):
        output=io.StringIO();console=Console(output,0)
        with patch('zip2cad.showcase_console.time.sleep',side_effect=AssertionError('Unexpected wait')):
            console.write('[3/5] Export');console.write(' actual geometry\nnext diagnostic\n')
        self.assertIn('Export actual geometry',output.getvalue());self.assertIn('next diagnostic',output.getvalue())
        self.assertEqual(len(console.lines),2)

    def test_invalid_presentation_duration_rejected_before_running(self):
        for value in [-1,301]:
            with self.assertRaises(ValueError):run_presented('unused','unused','unused',seconds=value)

    def test_every_stage_requires_enter_and_manual_mode_never_sleeps(self):
        output=io.StringIO();console=Console(output,0,step_by_step=True)
        with patch('builtins.input',side_effect=['']*5) as keyboard,patch('zip2cad.showcase_console.time.sleep',side_effect=AssertionError('Manual mode must not sleep')):
            for number in range(1,6):console.write(f'[{number}/5] Actual stage\n')
        self.assertEqual(keyboard.call_count,5);self.assertEqual(console.confirmed_stages,[1,2,3,4,5])
        self.assertNotIn('PRESENTATION HOLD',output.getvalue())
        self.assertTrue(output.getvalue().isascii())

    def test_cancellation_and_closed_input_do_not_advance(self):
        for action,error in [(lambda:'Q',StageCancelled),(lambda:(_ for _ in ()).throw(EOFError()),EOFError)]:
            console=Console(io.StringIO(),0,step_by_step=True)
            with patch('builtins.input',side_effect=action),self.assertRaises(error):console.write('[2/5] Must not start\n')
            self.assertEqual(console.confirmed_stages,[])

    def test_digit_zero_opens_exact_result_folder_and_q_does_not(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            for key in ['0','O','o']:
                with patch('builtins.input',return_value=key),patch('zip2cad.showcase_console.os.startfile',create=True) as opener:
                    self.assertTrue(output_folder_menu(tmp));opener.assert_called_once_with(str(Path(tmp).resolve()))
            with patch('builtins.input',return_value='q'),patch('zip2cad.showcase_console.os.startfile',create=True) as opener:
                self.assertFalse(output_folder_menu(tmp));opener.assert_not_called()

    def test_menu_prompts_and_invalid_choice_are_english(self):
        import tempfile,contextlib
        prompts=[];choices=iter(['invalid','Q']);output=io.StringIO()
        def keyboard(prompt):prompts.append(prompt);return next(choices)
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(output):
            self.assertFalse(output_folder_menu(tmp,input_fn=keyboard,opener=lambda path:None))
        self.assertTrue(''.join(prompts).isascii());self.assertTrue(output.getvalue().isascii())

if __name__=='__main__':unittest.main()
