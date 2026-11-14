// Dependency-free reduced ordered BDD checker. Private engineering source.
// Complement edges; terminals 0 and 1. No producer/metadata dependency.
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <unordered_map>
#include <vector>
using U=uint32_t;
struct Node {U v,l,h;};
struct Key {U v,l,h;bool operator==(const Key&o)const{return v==o.v&&l==o.l&&h==o.h;}};
struct Hash {size_t operator()(const Key&k)const {uint64_t x=k.v*0x9e3779b185ebca87ULL; x^=k.l*0xc2b2ae3d27d4eb4fULL;x^=k.h*0x165667b19e3779f9ULL;return x^(x>>32);}};
struct BDD {
 std::vector<Node> a{{UINT32_MAX,0,0}};
 std::unordered_map<Key,U,Hash> uniq;
 struct Entry {uint64_t key=0;U value=0;};
 std::vector<Entry> cache=std::vector<Entry>(1U<<23);
 size_t slot(uint64_t key)const {key^=key>>33;key*=0xff51afd7ed558ccdULL;key^=key>>33;return key&(cache.size()-1);}
 void clear_cache(){std::fill(cache.begin(),cache.end(),Entry{});}
 U mk(U v,U l,U h){
  if(l==h)return l;
  U sign=l&1; l^=sign;h^=sign;Key k{v,l,h};
  auto it=uniq.find(k);if(it!=uniq.end())return it->second^sign;
  if(a.size()>=60000000)throw std::runtime_error("node limit");
  U id=2*a.size();a.push_back({v,l,h});uniq.emplace(k,id);if(a.size()%1000000==0)std::cerr<<"allocated "<<a.size()<<" nodes\n";return id^sign;
 }
 U land(U x,U y){
  if(!x||!y)return 0;if(x==1)return y;if(y==1||x==y)return x;if(x==(y^1))return 0;
  if(x>y)std::swap(x,y);uint64_t key=(uint64_t(x)<<32)|y;
  size_t at=slot(key);if(cache[at].key==key)return cache[at].value;
  Node nx=a[x>>1],ny=a[y>>1];U v=std::min(nx.v,ny.v);
  U xl=nx.v==v?nx.l^(x&1):x,xh=nx.v==v?nx.h^(x&1):x;
  U yl=ny.v==v?ny.l^(y&1):y,yh=ny.v==v?ny.h^(y&1):y;
  U l=land(xl,yl),h=land(xh,yh),r=mk(v,l,h);
  cache[at]={key,r};return r;
 }
 U lor(U x,U y){return land(x^1,y^1)^1;}
 U ite(U x,U h,U l){if(h==l)return h;if(h==1&&l==0)return x;return lor(land(x,h),land(x^1,l));}
 U truth(const std::vector<U>&p,uint64_t tt,size_t i=0){
  if(i==p.size())return tt&1;
  size_t rem=p.size()-i-1;uint64_t mask=rem==5?0xffffffffULL:((1ULL<<(1ULL<<rem))-1);
  U l=truth(p,tt&mask,i+1),h=truth(p,tt>>(1ULL<<rem),i+1);return ite(p[i],h,l);
 }
 void gc(std::vector<U>&roots){
  std::vector<uint8_t> seen(a.size());std::vector<U> stack;
  for(U r:roots)if(r>1)stack.push_back(r>>1);
  while(!stack.empty()){U u=stack.back();stack.pop_back();if(seen[u])continue;seen[u]=1;for(U p:{a[u].l,a[u].h})if(p>1)stack.push_back(p>>1);}
  std::vector<U> map(a.size());U next=1;
  for(U i=1;i<a.size();++i)if(seen[i])map[i]=next++;
  std::vector<Node> b(next);b[0]={UINT32_MAX,0,0};
  auto cv=[&](U x){return (map[x>>1]<<1)|(x&1);};
  for(U i=1;i<a.size();++i)if(seen[i])b[map[i]]={a[i].v,cv(a[i].l),cv(a[i].h)};
  for(U&r:roots)r=cv(r);
  a.swap(b);uniq.clear();uniq.reserve(a.size()*2);clear_cache();
  for(U i=1;i<a.size();++i)uniq.emplace(Key{a[i].v,a[i].l,a[i].h},i*2);
 }
};
int main(int argc,char**argv){try{
 if(argc!=3)throw std::runtime_error("usage: bdd_replay PLAN threshold");
 std::ifstream f(argv[1]);U n,m,out;f>>n>>m>>out;if(!f||n==0||n>10000||m>1000000||out>=n+m)throw std::runtime_error("bad header");
 std::vector<U> order(n),perm(n);for(U i=0;i<n;++i){f>>order[i];if(order[i]>=n)throw std::runtime_error("bad variable order");perm[order[i]]++;}
 if(std::any_of(perm.begin(),perm.end(),[](U x){return x!=1;}))throw std::runtime_error("nonpermutation");
 struct Gate{std::vector<U>p;uint64_t tt;};std::vector<Gate>gates(m);std::vector<U>refs(n+m);
 for(U i=0;i<m;++i){U k;f>>k;if(k>6)throw std::runtime_error("fanin");for(U j=0;j<k;++j){U p;f>>p;if(p>=n+i)throw std::runtime_error("non-topological");gates[i].p.push_back(p);refs[p]++;}f>>gates[i].tt;}
 if(!f)throw std::runtime_error("truncated plan");std::string trailing;if(f>>trailing)throw std::runtime_error("trailing data");
 refs[out]++;
 BDD b;std::vector<U>val(n+m);for(U i=0;i<n;++i)val[order[i]]=b.mk(i,0,1);
 auto start=std::chrono::steady_clock::now();size_t nextgc=2000000,peak=0;
 for(U i=0;i<m;++i){std::vector<U>p;for(U s:gates[i].p)p.push_back(val[s]);U r=b.truth(p,gates[i].tt);val[n+i]=r;
  for(U s:gates[i].p)if(--refs[s]==0&&s>=n)val[s]=0;
  peak=std::max(peak,b.a.size());if(b.a.size()>nextgc){b.gc(val);nextgc=std::max(size_t(2000000),b.a.size()*2);}
  if(i%1000==0 || i>13500)std::cerr<<"gate "<<i<<"/"<<m<<" nodes "<<b.a.size()<<" seconds "<<std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count()<<"\n";
 }
 int T=std::stoi(argv[2]);if(T<0||T>int(n)+1)throw std::runtime_error("threshold out of range");
 std::vector<U>g(T+1);g[0]=1;
 for(int v=int(n)-1;v>=0;--v){std::vector<U>h(T+1);h[0]=1;for(int k=1;k<=T;++k)h[k]=b.mk(v,g[k],g[k-1]);g.swap(h);}
 bool equal=val[out]==g[T];std::cout<<"{\"equal\":"<<(equal?"true":"false")<<",\"inputs\":"<<n<<",\"gates\":"<<m<<",\"threshold\":"<<T<<",\"nodes\":"<<b.a.size()<<",\"peak_nodes\":"<<peak<<",\"seconds\":"<<std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count()<<"}\n";return equal?0:1;
 }catch(const std::exception&e){std::cerr<<"FAIL "<<e.what()<<"\n";return 2;}}
