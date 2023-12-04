import argparse
import re
import io
import sys
import pathlib

folder = r"C:\Users\andrew\Saved Games\Pillars of Eternity"
p = pathlib.Path(folder)
for f in p.glob('**/*'):
    print(f)
