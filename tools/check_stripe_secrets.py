"""Reject Stripe secrets without ever printing matching values."""
from pathlib import Path
import argparse
import re
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staged',action='store_true')
    args=parser.parse_args()
    command=['git','diff','--cached','--name-only','--diff-filter=ACMR','-z'] if args.staged else ['git','ls-files','-z']
    names=subprocess.check_output(command).decode().split('\0')
    pattern=re.compile(rb'(?:[sr]k_(?:live|test)_[A-Za-z0-9]{20,}|whsec_[A-Za-z0-9]{24,})')
    violations=[]
    for name in filter(None,names):
        if args.staged:
            data=subprocess.check_output(['git','show',':'+name])
        else:
            file=Path(name)
            if not file.is_file():continue
            data=file.read_bytes()
        if pattern.search(data):violations.append(name)
    for name in violations:print('Secret Stripe interdit dans :',name)
    return bool(violations)


if __name__=='__main__':
    raise SystemExit(main())
