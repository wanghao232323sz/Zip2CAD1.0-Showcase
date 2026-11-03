"""Run from a source checkout without relying on another installed zip2cad."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from zip2cad.showcase import main
if __name__=='__main__':raise SystemExit(main())
