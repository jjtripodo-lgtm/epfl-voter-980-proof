#!/usr/bin/env python3
"""Independent no-import literal BLIF weighted conservation proof audit."""
import json,sys,itertools,hashlib,copy
from pathlib import Path

def need(ok,why):
 if not ok: raise ValueError(why)
def parse(raw):
 lines=raw.decode('ascii').replace('\\\n',' ').splitlines();I=[];O=[];G={};cur=None;ended=False;models=0
 for line in lines:
  a=line.split()
  if not a or a[0].startswith('#'):continue
  need(not ended,'content after end')
  if a[0]=='.end':ended=True;cur=None
  elif a[0]=='.model':
   models+=1;need(len(a)==2 and models==1,'model');cur=None
  elif a[0]=='.inputs':I+=a[1:];cur=None
  elif a[0]=='.outputs':O+=a[1:];cur=None
  elif a[0]=='.names':
   need(len(a)>=2 and a[-1] not in G,'driver');G[a[-1]]=[a[1:-1],[]];cur=a[-1]
  elif a[0].startswith('.'):raise ValueError('unsupported directive')
  else:
   need(cur is not None,'row outside cover');G[cur][1].append(a)
 need(models==1 and ended and len(set(I))==len(I) and len(O)==1,'interface/end')
 need(not(set(I)&set(G)),'input driver overlap')
 for out,(pins,rows) in G.items():
  need(len(set(pins))==len(pins),'repeated fanin')
  need(all(p in G or p in I for p in pins),'undefined fanin')
  if pins:
   need(all(len(a)==2 and len(a[0])==len(pins) and set(a[0])<=set('01-') and a[1] in ('0','1') for a in rows),'invalid row')
   need(len(set(a[1] for a in rows))<=1,'mixed polarity')
  else:need(rows in ([],[['0']],[['1']]),'bad constant')
 return I,O,G

def evaluate_gate(g,bits):
 pins,rows=g
 if not pins:return int(rows==[['1']])
 hit=any(all(c=='-' or int(c)==v for c,v in zip(row[0],bits)) for row in rows)
 return int(hit) if not rows or rows[0][1]=='1' else int(not hit)

