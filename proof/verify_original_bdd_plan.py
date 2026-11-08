#!/usr/bin/env python3
"""Independent source-to-plan check; no voter producer or translator import."""
import sys,itertools,json,hashlib
from pathlib import Path
from verify_voter_independent import parse,evaluate_gate,need
def check(source,plan):
 raw=Path(source).read_bytes();praw=Path(plan).read_bytes();I,O,G=parse(raw)
 ls=praw.decode('ascii').splitlines();n,m,o=map(int,ls[0].split());perm=list(map(int,ls[1].split()))
 need(n==len(I)==1001 and sorted(perm)==list(range(n)),'interface/order')
 need(set(I)=={'A[%d]'%i for i in range(1001)},'original inputs')
 todo=[(O[0],False)];done=set(I);visiting=set();order=[]
 while todo:
  s,finish=todo.pop()
  if s in done:continue
  need(s in G,'undriven')
  if finish:done.add(s);visiting.remove(s);order.append(s);continue
  need(s not in visiting,'cycle');visiting.add(s);todo.append((s,True))
  todo.extend((p,False) for p in reversed(G[s][0]) if p not in done)
 need(len(order)==m and len(ls)==m+2,'complete cone')
 ids={s:i for i,s in enumerate(I)};local=0
 for j,s in enumerate(order):
  values=list(map(int,ls[j+2].split()));k=values[0];pins=values[1:-1];tt=values[-1]
  need(k==len(G[s][0])<=6 and len(pins)==k,'fanin')
  need(pins==[ids[p] for p in G[s][0]],'literal wiring')
  need(0<=tt<(1<<(1<<k)),'table width')
  for ix in range(1<<k):
   bits=[(ix>>(k-1-a))&1 for a in range(k)]
   need(((tt>>ix)&1)==evaluate_gate(G[s],bits),'literal truth table')
   local+=1
  ids[s]=n+j
 need(o==ids[O[0]],'output binding')
 return {'status':'PASS','inputs':n,'gates':m,'local_assignments':local,'zero_pin_nodes':sum(not p for p,rs in G.values()),'source_sha256':hashlib.sha256(raw).hexdigest(),'plan_sha256':hashlib.sha256(praw).hexdigest()}
if __name__=='__main__':print(json.dumps(check(*sys.argv[1:]),sort_keys=True,indent=2))
