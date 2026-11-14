"""Exact generic weighted-conservation and terminal ROBDD checker. Producer not imported."""
import functools,itertools,json,hashlib,copy,sys
from pathlib import Path
from literal import parse,evaluate_gate,need

class BDD:
 def __init__(self,n):self.n=n;self.nodes=[(n,0,0),(n,1,1)];self.unique={};self.cache={}
 def mk(self,v,l,h):
  if l==h:return l
  key=(v,l,h)
  if key not in self.unique:
   need(len(self.nodes)<2000000,'BDD node budget');self.unique[key]=len(self.nodes);self.nodes.append(key)
  return self.unique[key]
 def ite(self,a,b,c):
  if a==0:return c
  if a==1:return b
  if b==c:return b
  if b==1 and c==0:return a
  key=(a,b,c)
  if key in self.cache:return self.cache[key]
  need(len(self.cache)<4000000,'BDD apply budget')
  v=min(self.nodes[x][0] for x in key)
  lo=[self.nodes[x][1] if self.nodes[x][0]==v else x for x in key];hi=[self.nodes[x][2] if self.nodes[x][0]==v else x for x in key]
  z=self.mk(v,self.ite(*lo),self.ite(*hi));self.cache[key]=z;return z
 def negate(self,a):return self.ite(a,0,1)
 def threshold(self,weights,T):
  suffix=[0]*(len(weights)+1)
  for i in range(len(weights)-1,-1,-1):suffix[i]=suffix[i+1]+weights[i]
  @functools.lru_cache(None)
  def rec(i,t):
   if t<=0:return 1
   if t>suffix[i]:return 0
   return self.mk(i,rec(i+1,t),rec(i+1,t-weights[i]))
  return rec(0,T)
 def table(self,pins,vals):
  if all(x==vals[0] for x in vals):return vals[0]
  return self.ite(pins[0],self.table(pins[1:],vals[1::2]),self.table(pins[1:],vals[0::2]))

def audit(raw,m,N,T,model):
 need(type(N)is int and type(T)is int and 1<=T<=N,'external case')
 I,O,G=parse(raw);need(len(I)==N and set(I)=={'A[%d]'%i for i in range(N)} and O==['maj'],'exact primary interface')
 need(m.get('N')==N and m.get('T')==T and m.get('output')==O[0],'expected case binding')
 need(model in ('direct','offset'),'proof model')
 if model=='offset':
  K=m.get('K');C=m.get('C');q=m.get('frontier_quantum',K)
  need(type(K)is int and 0<=K<=32 and type(C)is int and C>=0,'offset integers')
  need(type(q)is int and 0<=q<=K,'quantum')
  target=1<<K;need(C==target-T and N+C<(1<<(K+1)),'offset bound')
 else:
  C=0;q=0;target=T
  need('C' not in m or m['C']==0,'direct constant')
 bound=N+C;order=[];state={};depth=dict.fromkeys(I,0)
 def walk(s):
  if s in depth:return
  need(s in G and state.get(s)!=1,'node or cycle');state[s]=1
  for p in G[s][0]:walk(p)
  state[s]=2;order.append(s);depth[s]=max([depth[x] for x in G[s][0]],default=0)+int(len(G[s][0])>=2)
 walk(O[0]);need(all(len(G[x][0])<=6 for x in order),'fanin')
 need(all(len(g[0])<=6 for g in G.values()),'all literal fanins')
 values={s:tuple(evaluate_gate(G[s],[(j>>i)&1 for i in range(len(G[s][0]))]) for j in range(1<<len(G[s][0]))) for s in G}
 F=dict.fromkeys(I,0);ever=set(I);used=set();drops=[];constants=[];cases=0
 for g in m['groups']:
  a=g['inputs'];z=g['outputs'];real=[(s,w) for s,w in a if s!='__ONE__'];const=[w for s,w in a if s=='__ONE__']
  need(1<=len(real)<=6 and len({s for s,w in real})==len(real),'real group')
  need(all(type(w)is int and 0<=w<=32 for s,w in a+z),'weights')
  need(len({s for s,w in z})==len(z),'duplicate output')
  need(all(F.get(s)==w for s,w in real),'frontier consumed')
  need(all(s not in ever and s in G and G[s][0]==[p for p,w in real] for s,w in z),'group literal drivers')
  dw=g.get('dropped_sum_weight');need(dw is None or(type(dw)is int and 0<=dw<q and dw not in drops),'drop discipline')
  if dw is not None:drops.append(dw)
  constants+=const
  for j in range(1<<len(real)):
   v=sum(((j>>i)&1)<<w for i,(s,w) in enumerate(real))+sum(1<<w for w in const)
   if v>bound:continue
   got=sum(values[s][j]<<w for s,w in z)
   need(v-got in ([0] if dw is None else [0,1<<dw]),'local weighted identity');cases+=1
  for s,w in real:del F[s]
  for s,w in z:F[s]=w;ever.add(s);used.add(s)
 need(sum(1<<w for w in constants)==C,'total constant')
 need(all(w>=q for w in F.values()) and sum(1<<w for w in drops)<1<<q,'error/quantum bound')
 need(sorted(F.items())==sorted(map(tuple,m['frontier'])),'frontier binding')
 need(target%(1<<q)==0,'target lattice')
 terminal=[];seen=set()
 def tail(s):
  if s in F or s in seen:return
  need(s in G and s not in used,'hidden source bypass');seen.add(s)
  for p in G[s][0]:tail(p)
  terminal.append(s)
 tail(O[0]);need(set(order)<=used|set(terminal),'reachable accounting')
 ids=sorted(F,key=lambda s:(-F[s],s));weights=[1<<F[s] for s in ids];bdd=BDD(len(ids));roots={s:bdd.mk(i,0,1) for i,s in enumerate(ids)}
 for s in terminal:roots[s]=bdd.table([roots[p] for p in G[s][0]],values[s])
 expected=bdd.threshold(weights,target);care=bdd.negate(bdd.threshold(weights,bound+1));diff=bdd.ite(roots[O[0]],bdd.negate(expected),expected)
 need(bdd.ite(care,diff,0)==0,'terminal exact BDD comparison')
 return {'PASS':True,'N':N,'T':T,'model':model,'C':C,'Q':1<<q,'groups':len(m['groups']),'local_assignments':cases,'frontier_bits':len(F),'terminal_nodes':len(terminal),'terminal_proof':'exact ROBDD on all assignments with weighted sum <= N+C','bdd_nodes':len(bdd.nodes),'paid_lut6':sum(len(G[s][0])>=2 for s in order),'depth':depth[O[0]],'netlist_sha256':hashlib.sha256(raw).hexdigest(),'metadata_sha256':hashlib.sha256(json.dumps(m,sort_keys=True).encode()).hexdigest()}

def main():
 raw=Path(sys.argv[1]).read_bytes();m=json.loads(Path(sys.argv[2]).read_text());N,T=map(int,sys.argv[3:5]);model=sys.argv[5];r=audit(raw,m,N,T,model);controls=[]
 for name,change in [('wrong_expected_threshold',lambda z:z.update(T=T+1)),('wrong_expected_N',lambda z:z.update(N=N+1)),('wrong_output',lambda z:z.update(output='other')),('duplicate_group_output',lambda z:z['groups'][0]['outputs'].append(z['groups'][0]['outputs'][0])),('missing_group',lambda z:z['groups'].pop(0))]:
  z=copy.deepcopy(m);change(z)
  try:audit(raw,z,N,T,model)
  except ValueError:controls.append(name)
  else:raise ValueError('accepted hostile '+name)
 I,O,G=parse(raw);target=m['groups'][0]['outputs'][0][0];text=raw.decode();needle='.names '+' '.join(G[target][0]+[target]);start=text.index(needle)+len(needle);end=text.index('\n.names',start);bad=(text[:start]+'\n'+text[end:]).encode()
 try:audit(bad,m,N,T,model)
 except ValueError:controls.append('literal_first_group_cover_removed')
 else:raise ValueError('accepted literal mutation')
 r['hostile_controls_rejected']=controls;print(json.dumps(r,sort_keys=True,indent=2))
if __name__=='__main__':main()
