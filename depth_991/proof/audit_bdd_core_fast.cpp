#define main candidate_program_main
#include "bdd_replay_fast.cpp"
#undef main
#include <random>
#include <bitset>
using TT=std::bitset<256>;
bool ev(const BDD& b,U x,U bits){while(x>1){Node p=b.a.at(x/2);x=((bits>>p.v)&1?p.h:p.l)^(x&1);}return x;}
void ensure(bool z){if(!z)throw std::runtime_error("independent audit failure");}
int main(){
 BDD b;std::vector<U> r(16);std::vector<TT> t(16);std::mt19937 rng(170903);
 for(U v=0;v<8;v++){r[v]=b.mk(v,0,1);for(U x=0;x<256;x++)t[v][x]=(x>>v)&1;}
 uint64_t checks=0;size_t collected=0;
 for(U step=0;step<5000;step++){
  U x=rng()%16,y=rng()%16,z=rng()%16,w=8+rng()%8;U op=rng()%4;
  if(op==0){r[w]=b.land(r[x],r[y]);t[w]=t[x]&t[y];}
  if(op==1){r[w]=b.lor(r[x],r[y]);t[w]=t[x]|t[y];}
  if(op==2){r[w]=b.ite(r[x],r[y],r[z]);t[w]=(t[x]&t[y])|((~t[x])&t[z]);}
  if(op==3){r[w]=r[x]^1;t[w]=~t[x];}
  if(step%5==4){size_t old=b.a.size();b.gc(r);collected+=old-b.a.size();}
  for(U j=0;j<16;j++)for(U a=0;a<256;a++){ensure(ev(b,r[j],a)==t[j][a]);checks++;}
  for(U j=1;j<b.a.size();j++){Node n=b.a[j];ensure((n.l&1)==0&&n.l!=n.h);for(U e:{n.l,n.h})if(e>1)ensure(b.a[e/2].v>n.v);ensure(b.uniq.at(Key{n.v,n.l,n.h})==2*j);}
 }
 uint64_t threshold_checks=0;
 for(U n=1;n<=12;n++)for(U threshold=0;threshold<=n+1;threshold++){
  BDD c;std::vector<U> g(threshold+1);g[0]=1;
  for(int v=n-1;v>=0;v--){std::vector<U> h(threshold+1);h[0]=1;for(U k=1;k<=threshold;k++)h[k]=c.mk(v,g[k],g[k-1]);g.swap(h);}
  for(U bits=0;bits<(1U<<n);bits++){ensure(ev(c,g[threshold],bits)==(__builtin_popcount(bits)>=threshold));threshold_checks++;}
 }
 ensure(collected>0);
 std::cout<<"{\"status\":\"PASS\",\"live_root_truth_checks\":"<<checks<<",\"threshold_truth_checks\":"<<threshold_checks<<",\"gc_rounds\":1000,\"collected_nodes\":"<<collected<<"}\n";
}
