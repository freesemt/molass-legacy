# coding: utf-8
"""
    DiffUtils.py

    Generating and applying diffs in python
    https://stackoverflow.com/questions/2307472/generating-and-applying-diffs-in-python

"""
import difflib
_no_eol = "\ No newline at end of file"

def make_patch(a,b):
  """
  Get unified string diff between two strings. Trims top two lines.
  Returns empty string if strings are identical.
  """
  diffs = difflib.unified_diff(a.splitlines(True),b.splitlines(True),n=0)
  try: _,_ = next(diffs),next(diffs)
  except StopIteration: pass
  return ''.join([d if d[-1] == '\n' else d+'\n'+_no_eol+'\n' for d in diffs])

import re
_hdr_pat = re.compile("^@@ -(\d+),?(\d+)? \+(\d+),?(\d+)? @@$")

def apply_patch(s,patch,revert=False):
  """
  Apply unified diff patch to string s to recover newer string.
  If revert is True, treat s as the newer string, recover older string.
  """
  s = s.splitlines(True)
  p = patch.splitlines(True)
  t = ''
  i = sl = 0
  (midx,sign) = (1,'+') if not revert else (3,'-')
  while i < len(p) and p[i].startswith(("---","+++")): i += 1 # skip header lines
  while i < len(p):
    m = _hdr_pat.match(p[i])
    if not m: raise Exception("Cannot process diff")
    i += 1
    l = int(m.group(midx))-1 + (m.group(midx+1) == '0')
    t += ''.join(s[sl:l])
    sl = l
    while i < len(p) and p[i][0] != '@':
      if i+1 < len(p) and p[i+1][0] == '\\': line = p[i][:-1]; i += 2
      else: line = p[i]; i += 1
      if len(line) > 0:
        if line[0] == sign or line[0] == ' ': t += line[1:]
        sl += (line[0] != sign)
  t += ''.join(s[sl:])
  return t

def file2string(path):
    with open(path) as fh:
        text = fh.read()
    return text

def string2file(text, path):
    with open(path, "w") as fh:
        fh.write(text)
