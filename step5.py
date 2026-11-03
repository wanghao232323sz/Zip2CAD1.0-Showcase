"""Verify all results and show the output folder menu."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'src'))
from zip2cad.showcase_steps import main
if __name__=='__main__':raise SystemExit(main(5))
