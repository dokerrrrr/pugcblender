#!/usr/bin/env python3
"""Recover BSP/VMF surface layers from an archived Overpass HTML file as Blender GLB.

Source surfaces are transformed to the aligned PUBG world. The export includes
per-material diagnostic vertex colors.
"""
import argparse,base64,gzip,json,pathlib,re
import numpy as np

def extract(html):
 s=pathlib.Path(html).read_text(encoding='utf8')
 def unpack(key):
  m=re.search(r'<script id="'+key+r'" type="text/plain">(.*?)</script>',s,re.S)
  if not m:raise ValueError('Missing embedded layer '+key)
  return gzip.decompress(base64.b64decode(m.group(1)))
 return json.loads(unpack('sceneB64')),np.frombuffer(unpack('bspB64'),dtype='<f4').reshape(-1,10),np.frombuffer(unpack('vmfB64'),dtype='<f4').reshape(-1,10)

def mesh(tri,offset,flip_x=True):
 import trimesh

 v=tri[:,0:3].copy();v[:,0]*=(-1 if flip_x else 1);v+=np.array(offset,dtype=np.float32)
 col=np.clip(tri[:,6:9]*255,0,255).astype(np.uint8)
 rgba=np.column_stack([col,np.full(len(col),255,dtype=np.uint8)])
 m=trimesh.Trimesh(vertices=v,faces=np.arange(len(v)).reshape(-1,3),vertex_colors=rgba,process=False,validate=False)
 return m

def main():
 import trimesh

 p=argparse.ArgumentParser(description=__doc__);p.add_argument('html');p.add_argument('--out-dir',default='.')
 p.add_argument('--offset',nargs=3,type=float,default=[325.28,56.92,475.59]);p.add_argument('--no-flip',action='store_true');args=p.parse_args()
 scene,bsp,vmf=extract(args.html);out=pathlib.Path(args.out_dir);out.mkdir(parents=True,exist_ok=True)
 for name,arr in [('overpass_bsp_aligned.glb',bsp),('overpass_vmf_aligned.glb',vmf)]:
  if not len(arr):continue
  path=out/name
  m=mesh(arr,args.offset,flip_x=not args.no_flip)
  m.export(path);back=trimesh.load(path,force='mesh');print(path,'triangles',len(back.faces),'bounds',back.bounds.round(3).tolist())
if __name__=='__main__':main()
