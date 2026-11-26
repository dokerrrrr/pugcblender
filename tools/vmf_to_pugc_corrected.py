#!/usr/bin/env python3
"""VMF -> PUBG UGC (.pugc) geometry reconstructor with teacher-reference analysis.

Requires: Python 3, numpy, OpenSSL. The input .pugc reference is optional and used
ONLY to learn statistical information; original geometry is generated from VMF.

Examples:
 python vmf_to_pugc_learned.py build de_overpass_d.vmf.txt overpass_independent.pugc --teacher "overpassbydoker (1).pugc" --limit 3000
 python vmf_to_pugc_learned.py analyze "overpassbydoker (1).pugc" teacher_report.json
 python vmf_to_pugc_learned.py extract "overpassbydoker (1).pugc" geometry_only.pugc --limit 3000

Caveats: Cuboid proxies are not a 1:1 replacement for brush wedges, displacements,
or original CS prop meshes. Cube mesh true bounds need confirmation in PUBG.
"""
import argparse,collections,itertools,json,math,pathlib,re,time
import numpy as np

from pugc_codec import CONTAINER_VERSION, PugcError, encode_raw, read_lab_game

P=re.compile(r'\(([-+\d.eE]+) ([-+\d.eE]+) ([-+\d.eE]+)\)')
TECH=('tools/','effects/','dev/','editor/')

def decode_pugc(path):
 return read_lab_game(path, allow_unwrapped=False)

def encode_pugc(data, ver=CONTAINER_VERSION):
 if ver != CONTAINER_VERSION:
  raise PugcError(f"VMF writer supports PUGC container version {CONTAINER_VERSION}")
 return encode_raw(data)

def props(j):return [x for x in j.get('objects',[]) if int(x.get('deviceIndex',-1))==-1]

def teacher_analysis(path):
 j,_=decode_pugc(path);a=props(j)
 sc=np.array([[float(o['spawnTransform']['scale3D'][k]) for k in 'xyz'] for o in a]);t=np.array([[float(o['spawnTransform']['translation'][k]) for k in 'xyz'] for o in a]);r=np.array([[float(o['spawnTransform']['rotation'][k]) for k in 'xyzw'] for o in a]);ids=collections.Counter(str(o['objectId']) for o in a)
 d={'source_file':str(path),'object_total':len(j.get('objects',[])),'props':len(a),'devices_excluded':len(j.get('objects',[]))-len(a),'distinct_prop_ids':len(ids),'common_prop_ids':ids.most_common(35),'position_cm_min':t.min(axis=0).tolist(),'position_cm_max':t.max(axis=0).tolist(),'scale_5_25_50_75_95pct':np.percentile(sc,[5,25,50,75,95],axis=0).round(3).tolist(),'negative_scale_instances':int(np.count_nonzero((sc<0).any(axis=1))),'yaw_only_quaternion_fraction':float(np.mean(np.linalg.norm(r[:,:2],axis=1)<0.001)),'note':'Training statistics; these do not identify true mesh dimensions or correspondence between VMF brushes and UGC props.'}
 return d

def parse_vmf(path):
 solids=[];stack=[];last=None;cur=None;side=None
 for line in open(path,encoding='utf-8',errors='replace'):
  s=line.strip()
  if s=='{':
   stack.append(last)
   if last=='solid':cur={'sides':[]}
   elif last=='side':side={}
   last=None
  elif s=='}':
   x=stack.pop()
   if x=='side' and side is not None and cur is not None:cur['sides'].append(side);side=None
   elif x=='solid' and cur is not None:solids.append(cur);cur=None
  elif s in ('solid','side','entity','world','editor','connections','dispinfo','normals','distances','offsets','offset_normals','alphas','triangle_tags','allowed_verts','group','hidden','cameras','cordon','visgroups'):
   last=s
  elif s.startswith('"') and side is not None:
   m=re.match(r'"([^"]+)"\s+"(.*)"',s)
   if m:side[m.group(1)]=m.group(2)
 return solids

def exact_vertices(sides):
 """Intersect all combinations of 3 INWARD VMF side planes.
 Avoid using the three source points as vertices: they only define infinite planes.
 """
 N=[];d=[];materials=[]
 for s in sides:
  p=np.asarray(P.findall(s.get('plane','')),dtype=float)
  if p.shape!=(3,3):continue
  n=np.cross(p[1]-p[0],p[2]-p[0]);l=np.linalg.norm(n)
  if l<1e-8:continue
  n/=l;N.append(n);d.append(float(n@p[0]));materials.append(s.get('material','').lower())
 if len(N)<4:return None,None,None
 N=np.asarray(N);d=np.asarray(d);vertices=[]
 for comb in itertools.combinations(range(len(N)),3):
  A=N[list(comb)]
  if abs(np.linalg.det(A))<1e-7:continue
  x=np.linalg.solve(A,d[list(comb)])
  if np.all(N@x>=d-0.08):
   if not any(np.linalg.norm(x-y)<0.04 for y in vertices):vertices.append(x)
 if len(vertices)<4:return None,None,None
 return np.asarray(vertices),N,materials

def axis_fit(vertices,normals,materials):
 # In-plane rotation from genuine faces, not diagonals drawn between plane anchors.
 angled=[]
 for n,mat in zip(normals,materials):
  if abs(n[2])<0.02 and not mat.startswith(TECH):
   yaw=(math.atan2(-n[0],n[1])+math.pi/4)%(math.pi/2)-math.pi/4
   angled.append((round(yaw,4),1.0))
 if angled:
  votes=collections.Counter()
  for ang,w in angled:votes[ang]+=w
  yaw=votes.most_common(1)[0][0]
 else:yaw=0.0
 c=math.cos(yaw);s=math.sin(yaw)
 rot=np.array([[c,-s,0],[s,c,0],[0,0,1]])
 local=vertices@rot;lo=local.min(axis=0);hi=local.max(axis=0)
 ctr=((lo+hi)*0.5)@rot.T;dims=hi-lo
 # Relative fraction of oriented-bounding-box volume that actual convex brush occupies.
 return ctr,dims,yaw

def convex_volume(verts):
 try:
  from scipy.spatial import ConvexHull
  return float(ConvexHull(verts).volume)
 except Exception:return 0

def extract_boxes(solids):
 boxes=[];failed=0;technical=0
 for i,sol in enumerate(solids):
  sides=sol['sides'];valid=[s for s in sides if not s.get('material','').lower().startswith(TECH)]
  if not valid:technical+=1;continue
  v,n,m=exact_vertices(sides)
  if v is None:failed+=1;continue
  ctr,d,yaw=axis_fit(v,n,m)
  if np.min(d)<0.03:continue
  face_visible_count=len(valid)
  # Weighted score: broad surfaces + height + visible face count.
  dims=np.sort(d);area=dims[-1]*dims[-2]
  vol=convex_volume(v); boxvol=np.prod(d)
  fill=(vol/boxvol) if boxvol else 0
  score=(area**.67)*(1+.04*min(face_visible_count,8))*(0.55+0.45*min(1,fill))
  common=collections.Counter(s.get('material','') for s in valid).most_common(1)[0][0]
  boxes.append({'index':i,'center':ctr,'dims':d,'yaw':yaw,'score':float(score),'fill':float(fill),'material':common,'volume':vol})
 return boxes,failed,technical

def merge_axis_boxes(boxes):
 # Merge exact-axis neighboring boxes with identical perpendicular cross-sections.
 for axis in (0,1,2):
  groups=collections.defaultdict(list)
  for b in boxes:
   if abs(b['yaw'])>0.001:continue
   c,d=b['center'],b['dims']
   k=(b['material'],)+tuple(round(float(x),1) for j in range(3) if j!=axis for x in (c[j],d[j]))
   groups[k].append(b)
  gone=set();add=[]
  for g in groups.values():
   if len(g)<2:continue
   g.sort(key=lambda b:b['center'][axis]-b['dims'][axis]/2)
   chain=[g[0]]
   def finish(chain):
    if len(chain)<=1:return
    l=min(x['center'][axis]-x['dims'][axis]/2 for x in chain)
    h=max(x['center'][axis]+x['dims'][axis]/2 for x in chain)
    b=dict(chain[0]);b['center']=b['center'].copy();b['dims']=b['dims'].copy();b['center'][axis]=(l+h)/2;b['dims'][axis]=h-l;b['score']=sum(x['score'] for x in chain)*0.85;b['index']=[x['index'] for x in chain]
    add.append(b);gone.update(id(x) for x in chain)
   for b in g[1:]:
    prior_right=max(x['center'][axis]+x['dims'][axis]/2 for x in chain)
    left=b['center'][axis]-b['dims'][axis]/2
    if left<=prior_right+.3:chain.append(b)
    else:finish(chain);chain=[b]
   finish(chain)
  boxes=[b for b in boxes if id(b) not in gone]+add
 return boxes

def select_spatial(boxes,limit):
 if len(boxes)<=limit:return boxes
 arr=np.array([b['center'] for b in boxes]);mn=arr.min(0)
 # VMF units: 384 approximately one placement neighborhood
 tiles=collections.defaultdict(list)
 for b in boxes:
  c=b['center'];tile=(int((c[0]-mn[0])/384),int((c[1]-mn[1])/384))
  tiles[tile].append(b)
 for g in tiles.values():g.sort(key=lambda b:b['score'],reverse=True)
 # Fair allocation: keep each populated region first, then choose best remaining.
 allocated=[];seen=set();first=max(1,int(limit*.50))
 for depth in range(max(len(x) for x in tiles.values())):
  for key,g in sorted(tiles.items(),key=lambda kv:-len(kv[1])):
   if depth<len(g):
    b=g[depth];allocated.append(b);seen.add(id(b))
    if len(allocated)>=first:break
  if len(allocated)>=first:break
 rest=sorted((b for b in boxes if id(b) not in seen),key=lambda b:b['score'],reverse=True)
 return (allocated+rest)[:limit]

def write_geometry(boxes,path,sourcepath,cube_cm,reference=None,flip_x=True):
 # Source coordinates are right-handed; PUBG/Unreal are left-handed.
 # A single reflected horizontal axis is essential. Teacher-map alignment
 # favours X reflection for this Overpass conversion.
 a=np.array([b['center'] for b in boxes]);factor=np.array([-1.0 if flip_x else 1.0,1.0,1.0]);
 if reference:
  j,_=decode_pugc(reference);t=np.array([[float(o['spawnTransform']['translation'][k]) for k in 'xyz'] for o in props(j)])
  # Align world centers by robust medians, without modifying teacher objects.
  offset=np.median(t,axis=0)-np.median(a*factor*2.54,axis=0)
 else:
  offset=-np.median(a*factor*2.54,axis=0)

 objects=[]
 for b in boxes:
  pos=b['center']*factor*2.54+offset;sc=np.maximum(.01,np.round(b['dims']*2.54/cube_cm,2));yaw=(-b['yaw'] if flip_x else b['yaw']);z=math.sin(yaw/2);w=math.cos(yaw/2)
  objects.append({'objectId':16200,'deviceIndex':-1,'userDeviceName':'','spawnTransform':{'translation':dict(zip('xyz',[round(float(v),2) for v in pos])),'rotation':{'x':0.,'y':0.,'z':round(z,7),'w':round(w,7)},'scale3D':dict(zip('xyz',[float(v) for v in sc]))}})
 now=int(time.time());data={'name':'VMF_Overpass_Geometry','dataVersion':3,'buildVersion':'2608.1.1','creatorData':{'name':'VMF Geometry','description':'Independent VMF brush reconstruction using true plane intersections; cuboid proxies; not 1:1','versionMajor':1,'versionMinor':0,'ownerAccountId':'','ownerNickName':''},'objects':objects,'roundRuleData':{'roundGameCount':1,'timeLimit':300},'characterRuleData':{'characterHP':100},'gameRuleData':{},'userSelectableData':{},'editFileData':{'createAccountId':'','createTime':now,'lastModifierAccountId':'','lastModifiedTime':now,'editPlayers':[],'lastHostPlayerData':None}}
 pathlib.Path(path).write_bytes(encode_pugc(data))
 back,v=decode_pugc(path)
 assert len(back['objects'])==len(objects) and all(o['deviceIndex']==-1 for o in back['objects'])
 assert all(all(round(float(x),2)==x and x>=.01 for x in o['spawnTransform']['scale3D'].values()) for o in objects)
 return {'pugc_path':str(path),'file_bytes':pathlib.Path(path).stat().st_size,'object_count':len(objects),'object_id':16200,'assumed_cube_mesh_size_cm':cube_cm,'coordinate_reflection_x':flip_x,'teacher_anchored':bool(reference),'world_offset_cm':offset.round(5).tolist(),'roundtrip_validation':True}

def extract_reference(path,output,limit):
 j,v=decode_pugc(path);p=props(j)
 if len(p)>limit:raise ValueError(f'{len(p)} props in reference exceeds limit {limit}; no hidden object deletion is allowed')
 j['objects']=p
 if 'deviceEventList' in j:j['deviceEventList']=[]
 j['dataVersion']=3;j['buildVersion']='2608.1.1'
 j['name']='Overpass_Geometry_Reference_Props'
 pathlib.Path(output).write_bytes(encode_pugc(j))
 j2,_=decode_pugc(output)
 assert j2['objects']==p and len(j2['objects'])<=limit
 return {'objects_kept':len(p),'devices_removed':len(j.get('objects',[]))-len(p),'exact_object_transforms_preserved':True,'roundtrip_validation':True}

def main():
 ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='cmd',required=True)
 p=sub.add_parser('analyze');p.add_argument('reference');p.add_argument('report')
 p=sub.add_parser('extract');p.add_argument('reference');p.add_argument('output');p.add_argument('--limit',type=int,default=3000)
 p=sub.add_parser('build');p.add_argument('vmf');p.add_argument('output');p.add_argument('--teacher');p.add_argument('--limit',type=int,default=3000);p.add_argument('--cube-cm',type=float,default=100);p.add_argument('--report');p.add_argument('--no-flip-x',action='store_true',help='Legacy incorrect orientation (not recommended)')
 a=ap.parse_args()
 if a.cmd=='analyze':info=teacher_analysis(a.reference);pathlib.Path(a.report).write_text(json.dumps(info,indent=2,ensure_ascii=False));print(json.dumps(info,indent=2));return
 if a.cmd=='extract':
  j,_=decode_pugc(a.reference);original_count=len(j.get('objects',[]));p=props(j)
  if len(p)>a.limit:raise ValueError('Reference props exceed cap')
  j['objects']=p;j['deviceEventList']=[];j['dataVersion']=3;j['buildVersion']='2608.1.1';j['name']='Overpass_Reference_GeometryOnly';pathlib.Path(a.output).write_bytes(encode_pugc(j));again,_=decode_pugc(a.output)
  assert again['objects']==p and len(p)<=a.limit
  print(f'Extracted {len(p)} unchanged scene props; removed {original_count-len(p)} devices. Roundtrip OK.');return
 if a.limit<1 or a.limit>3000:ap.error('--limit must be between 1 and 3000')
 if a.cube_cm<=0:ap.error('--cube-cm must be positive')
 t0=time.monotonic();solids=parse_vmf(a.vmf);boxes,failed,technical=extract_boxes(solids);premerge=len(boxes);boxes=merge_axis_boxes(boxes);postmerge=len(boxes);chosen=select_spatial(boxes,a.limit)
 info=write_geometry(chosen,a.output,a.vmf,a.cube_cm,reference=a.teacher,flip_x=not a.no_flip_x)
 info.update({'vmf_solids':len(solids),'nontechnical_valid_brushes':premerge,'technical_only_skipped':technical,'invalid_skipped':failed,'after_merge':postmerge,'brushed_proxy_count_excluded':postmerge-len(chosen),'fraction_proxy_score_retained':sum(x['score'] for x in chosen)/sum(x['score'] for x in boxes),'approx_source_volume_fill_median':float(np.median([b['fill'] for b in chosen])),'seconds':round(time.monotonic()-t0,2),'limitations':['Non-cuboid convex solids approximated as oriented cuboids','Original static prop meshes not recreated','Displacement terrain not reconstructed','Cube true size set by --cube-cm, not independently confirmed']})
 if a.teacher:info['teacher']=teacher_analysis(a.teacher)
 rp=a.report or str(pathlib.Path(a.output).with_suffix('.report.json'))
 pathlib.Path(rp).write_text(json.dumps(info,indent=2,ensure_ascii=False))
 print(json.dumps({k:v for k,v in info.items() if k!='teacher'},indent=2))

if __name__=='__main__':main()
