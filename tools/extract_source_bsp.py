#!/usr/bin/env python3
"""Simple Source VBSP v20/21 structural face extractor (BSP polygons, non-displacement).
Outputs bsp_faces.json / bsp_faces.npz, matching the shape used by build scripts.
Does not recover prop MDLs, brush collision, displacements' true tessellation, game shaders.
"""
import argparse,struct,json,math
from pathlib import Path
import numpy as np

def extract(inp,out,scale=.0254):
 b=Path(inp).read_bytes()
 if b[:4]!=b'VBSP':raise ValueError('Only Source VBSP supported')
 ver=struct.unpack_from('<i',b,4)[0]
 if ver not in (20,21):raise ValueError(f'Unsupported BSP v{ver}')
 lumps=[struct.unpack_from('<4i',b,8+16*i) for i in range(64)]
 def section(idx):
  off,l,version,fourcc=lumps[idx]
  if off<=0 or l<0 or off+l>len(b):raise ValueError('invalid lump '+str(idx))
  return memoryview(b)[off:off+l]
 V=np.frombuffer(section(3),dtype='<f4').reshape(-1,3)*scale
 E=np.frombuffer(section(12),dtype='<u2').reshape(-1,2)
 SE=np.frombuffer(section(13),dtype='<i4')
 P=np.frombuffer(section(1),dtype=[('n','<f4',(3,)),('d','<f4'),('t','<i4')])['n']
 T=section(6);TD=section(2);ST=np.frombuffer(section(44),dtype='<i4');STR=section(43)
 def mat(texinfo):
  if texinfo<0:return 'tools/toolsskip'
  pos=texinfo*72
  if pos+72>len(T):return 'unknown'
  texdata=struct.unpack_from('<i',T,pos+68)[0]
  if texdata<0 or texdata*32+32>len(TD):return 'unknown'
  nameid=struct.unpack_from('<i',TD,texdata*32+12)[0]
  if nameid<0 or nameid>=len(ST):return 'unknown'
  start=int(ST[nameid]);end=bytes(STR[start:]).find(b'\0')
  return bytes(STR[start:start+(end if end>=0 else 100)]).decode('utf-8','replace')
 face=section(7);size=56 if len(face)%56==0 else 104
 F=[];TR=[];raw=0
 for i in range(len(face)//size):
  o=i*size
  planenum,side,onnode,firstedge,numedges,texinfo,dispinfo=struct.unpack_from('<HBBihhh',face,o)
  if numedges<3 or firstedge<0 or firstedge+numedges>len(SE):continue
  inds=[]
  for idx in SE[firstedge:firstedge+numedges]:
   ed=int(abs(idx));
   if ed>=len(E):continue
   v=int(E[ed,0] if idx>=0 else E[ed,1]);
   if v>=len(V):continue
   inds.append(v)
  if len(inds)<3:continue
  pts=V[inds].astype(np.float32)
  # Coarse structural extractor; compiled BSP face has no material opacity flags in this format.
  vec=np.cross(pts[1]-pts[0],pts[2]-pts[0]);
  n=np.array(P[planenum]) if planenum<len(P) else vec/ max(np.linalg.norm(vec),1e-9)
  if side:n=-n
  tris=[]
  for j in range(1,len(pts)-1):
   tri=np.array([pts[0],pts[j],pts[j+1]])
   if abs(np.linalg.norm(np.cross(tri[1]-tri[0],tri[2]-tri[0])))>1e-5:tris.extend(tri)
  if not tris:continue
  tris=np.array(tris,dtype=np.float32).reshape(-1,3)
  area=sum(float(np.linalg.norm(np.cross(t[1]-t[0],t[2]-t[0]))/2) for t in tris.reshape(-1,3,3))
  m=mat(texinfo)
  if any(z in m.lower() for z in ('tools/toolsnodraw','tools/toolsskybox','tools/toolsskip','tools/toolsclip','tools/toolsplayerclip','tools/toolshint','tools/toolstrigger')):continue
  lo=tris.min(0);hi=tris.max(0);cent=tris.mean(0)
  F.append({'id':i,'mat':m,'lo':lo.astype(float).tolist(),'hi':hi.astype(float).tolist(),'center':cent.astype(float).tolist(),'normal':(n/max(1e-8,np.linalg.norm(n))).astype(float).tolist(),'area':area,'disp':bool(dispinfo>=0),'start':len(TR),'count':len(tris)})
  TR.extend(tris.tolist());raw+=1
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 (out/'bsp_faces.json').write_text(json.dumps(F,ensure_ascii=False,separators=(',',':')))
 np.savez_compressed(out/'bsp_faces.npz',verts=np.array(TR,np.float32).reshape(-1,3))
 (out/'BSP_EXTRACT_WARNINGS.txt').write_text('Non-displacement structural face extraction. Displacement facets approximated by base polygons. No props, collision, material textures, or Vis data. Validate before map building.\n')
 print('BSP',ver,'faces',len(F),'triangle_vertices',len(TR),'source',inp)
 if F:print('FIRST',F[0]['id'],F[0]['mat'],F[0]['center'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input_bsp');p.add_argument('output_directory');p.add_argument('--source-unit-to-meter',type=float,default=.0254)
 a=p.parse_args();extract(a.input_bsp,a.output_directory,a.source_unit_to_meter)
