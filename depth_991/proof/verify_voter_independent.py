#!/usr/bin/env python3
"""Independent no-import literal BLIF weighted conservation proof audit."""
import json,sys,itertools,hashlib,copy
from pathlib import Path

def need(ok,why):
 if not ok: raise ValueError(why)
def parse(raw):
 lines=raw.decode('ascii').replace('\\\n',' ').splitlines();I=[];O=[];G={};cur=None;ended=False
 for line in lines:
  a=line.split()
  if not a or a[0].startswith('#'):continue
  need(not ended,'content after end')
  if a[0]=='.end':ended=True;cur=None
  elif a[0]=='.model':need(len(a)==2,'model');cur=None
  elif a[0]=='.inputs':I+=a[1:];cur=None
  elif a[0]=='.outputs':O+=a[1:];cur=None
  elif a[0]=='.names':
   need(len(a)>=2 and a[-1] not in G,'driver');G[a[-1]]=[a[1:-1],[]];cur=a[-1]
  elif a[0].startswith('.'):raise ValueError('unsupported directive')
  else:
   need(cur is not None,'row outside cover');G[cur][1].append(a)
 need(ended and len(set(I))==len(I) and len(O)==1,'interface/end')
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

def audit(raw,m):
 I,O,G=parse(raw);N=len(I);out=O[0]
 need(N==1001 and set(I)=={'A[%d]'%i for i in range(N)},'original primary interface')
 need(m['N']==N and m['T']==501 and m['K']==9 and m['C']==11,'threshold model')
 need(m.get('output')==out,'output binding')
 need((1<<9)-501==11 and N+11<1024,'offset theorem assumptions')
 state={};order=[];depth={s:0 for s in I}
 def visit(s):
  if s in I:return
  need(s in G,'undriven output');need(state.get(s)!=1,'cycle')
  if state.get(s)==2:return
  state[s]=1
  for p in G[s][0]:visit(p)
  state[s]=2;order.append(s);depth[s]=max((depth[p] for p in G[s][0]),default=0)+(len(G[s][0])>=2)
 visit(out);need(all(len(G[s][0])<=6 for s in order),'paid fanin')
 F=dict.fromkeys(I,0);ever=set(I);cons=[];drop=[];used=set();cases=0
 for ix,g in enumerate(m['groups']):
  inputs=g['inputs'];outputs=g['outputs'];real=[(s,w) for s,w in inputs if s!='__ONE__'];const=[w for s,w in inputs if s=='__ONE__']
  need(1<=len(real)<=6 and len({s for s,w in real})==len(real),'input group')
  need(all(type(w) is int and w>=0 for s,w in inputs+outputs),'weight type')
  need(len({s for s,w in outputs})==len(outputs),'duplicate group output')
  need(all(F.get(s)==w for s,w in real),'frontier membership')
  need(all(s not in ever and s in G and G[s][0]==[p for p,w in real] for s,w in outputs),'output drivers/order')
  dw=g.get('dropped_sum_weight');need(dw is None or (type(dw) is int and 0<=dw<9 and dw not in drop),'drop uniqueness')
  if dw is not None:drop.append(dw)
  cons+=const
  for bits in itertools.product((0,1),repeat=len(real)):
   v=sum(b*(1<<w) for b,(s,w) in zip(bits,real))+sum(1<<w for w in const)
   if v>N+11:continue
   got=sum(evaluate_gate(G[s],bits)*(1<<w) for s,w in outputs)
   need(v-got in ([0] if dw is None else [0,1<<dw]),'weighted identity group '+str(ix))
   cases+=1
  for s,w in real:del F[s]
  for s,w in outputs:F[s]=w;ever.add(s);used.add(s)
 need(len(cons)==len(set(cons)) and all(0<=w<9 for w in cons) and sum(1<<w for w in cons)==11,'constant budget')
 need(all(w>=9 for w in F.values()),'unpaid low frontier')
 need(sorted(F.items())==sorted(map(tuple,m['frontier'])),'frontier binding')
 need(sum(1<<w for w in drop)<=511,'error below threshold quantum')
 # All reachable nongroup nodes must be a complete terminal DAG over F only.
 terminal=[];seen=set()
 def tail(s):
  if s in F or s in seen:return
  need(s in G and s not in used,'hidden source bypass');seen.add(s)
  for p in G[s][0]:tail(p)
  terminal.append(s)
 tail(out)
 need(set(order)<=used|set(terminal),'unaccounted reachable node')
 compare=0
 for bits in itertools.product((0,1),repeat=len(F)):
  val=dict(zip(F,bits));z=sum(val[s]*(1<<w) for s,w in F.items())
  if z>N+11:continue
  for s in terminal:val[s]=evaluate_gate(G[s],[val[p] for p in G[s][0]])
  need(val[out]==int(z>=512),'terminal compare');compare+=1
 return {'PASS':True,'N':N,'T':501,'paid_lut6':sum(len(G[s][0])>=2 for s in order),'depth':depth[out],'groups':len(m['groups']),'group_cases':cases,'compare_cases':compare,'drop_weights':drop,'constant_weights':cons,'netlist_sha256':hashlib.sha256(raw).hexdigest(),'metadata_sha256':hashlib.sha256(json.dumps(m,sort_keys=True).encode()).hexdigest()}

def main():
 raw=Path(sys.argv[1]).read_bytes();m=json.loads(Path(sys.argv[2]).read_text());r=audit(raw,m)
 controls=[]
 for name,change in [('wrong_threshold',lambda z:z.update(T=500)),('wrong_constant',lambda z:z.update(C=10)),('duplicate_output',lambda z:z['groups'][0]['outputs'].append(z['groups'][0]['outputs'][0])),('wrong_weight',lambda z:z['groups'][0]['outputs'][0].__setitem__(1,2)),('missing_group',lambda z:z['groups'].pop(0))]:
  z=copy.deepcopy(m);change(z)
  try:audit(raw,z)
  except ValueError:controls.append(name)
  else:raise ValueError('accepted hostile '+name)
 # A literal cover corruption, not metadata-only tampering.
 I,O,G=parse(raw);target=m['groups'][0]['outputs'][0][0];needle='.names '+' '.join(G[target][0]+[target]);st=raw.decode();start=st.index(needle)+len(needle);end=st.index('\n.names',start);bad=(st[:start]+'\n'+st[end:]).encode()
 try:audit(bad,m)
 except ValueError:controls.append('literal_cover_removed')
 else:raise ValueError('accepted literal corruption')
 r['hostile_controls_rejected']=controls;print(json.dumps(r,sort_keys=True,indent=2))
if __name__=='__main__':main()
