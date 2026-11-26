"""Read Source VMF brush surfaces and historical PUGC files for the Blender lab."""
from array import array
import collections
import itertools
import re
import sys

import numpy as np

from pugc_codec import read_lab_game


POINT_RE=re.compile(r'\(([-+\d.eE]+) ([-+\d.eE]+) ([-+\d.eE]+)\)')
KV_RE=re.compile(r'^"([^"]+)"\s+"(.*)"$')
VIS_NOT=("tools/","effects/","dev/","editor/")

def decode_pugc(path):
    return read_lab_game(path)[0]

def vmf_solids(path):
    # Track blocks, not substrings. Only "solid" and "side" keys are material.
    solids=[]; stack=[]; pending=None; current=None; side=None; entity_name=None
    for line in open(path,'r',encoding='utf-8',errors='replace'):
        s=line.strip()
        if s=='{':
            tag=pending or ''
            stack.append(tag)
            if tag=='solid':current={'sides':[], 'entity':entity_name, 'id':''}
            if tag=='side':side={}
            if tag=='entity':entity_name='entity'
            pending=None
        elif s=='}':
            tag=stack.pop() if stack else ''
            if tag=='side' and side is not None:
                if current is not None:current['sides'].append(side)
                side=None
            elif tag=='solid' and current is not None:
                solids.append(current);current=None
            elif tag=='entity':entity_name=None
        elif s in {'world','solid','side','entity','editor','connections','dispinfo','normals','distances',
            'offsets','offset_normals','alphas','triangle_tags','allowed_verts','group','hidden',
            'cameras','cordon','visgroups','cordons','keys','navi'}:
            pending=s
        elif s.startswith('"'):
            m=KV_RE.match(s)
            if not m:continue
            key,value=m.groups()
            if stack and stack[-1]=='side' and side is not None:side[key]=value
            elif stack and stack[-1]=='solid' and current is not None and key=='id':current['id']=value
            elif stack and stack[-1]=='entity' and key=='classname':entity_name=value
    return solids

def intersect_brush(sides):
    normals=[];ds=[];mat=[]
    for s in sides:
        v=np.array(POINT_RE.findall(s.get('plane','')),dtype=np.float64)
        if v.shape!=(3,3):continue
        n=np.cross(v[1]-v[0],v[2]-v[0]);l=np.linalg.norm(n)
        if l<1e-7:continue
        n/=l;normals.append(n);ds.append(np.dot(n,v[0]));mat.append(s.get('material','').lower())
    if len(normals)<4 or len(normals)>40:return None
    N=np.array(normals);D=np.array(ds)
    comb=np.array(list(itertools.combinations(range(len(N)),3)))
    A=N[comb];dd=D[comb]
    det=np.linalg.det(A);valid=np.abs(det)>1e-7
    if not valid.any():return None
    xyz=np.linalg.solve(A[valid],dd[valid][...,None])[...,0]
    xyz=xyz[(xyz@N.T>=D-0.13).all(axis=1)]
    if len(xyz)<4:return None
    xyz=np.unique(np.round(xyz,3),axis=0)
    if len(xyz)<4:return None
    return xyz,N,D,mat

def surface_color(mat):
    if 'metal' in mat or 'steel' in mat or 'beam' in mat or 'ibeam' in mat:return (.46,.68,.76)
    if 'wood' in mat or 'plywood' in mat:return (.68,.51,.35)
    if 'brick' in mat or 'roof' in mat:return (.74,.43,.39)
    if 'concrete' in mat or 'cement' in mat:return (.62,.64,.65)
    if 'stone' in mat or 'wall' in mat:return (.65,.60,.56)
    if 'glass' in mat or 'window' in mat:return (.49,.78,.84)
    if 'grass' in mat or 'dirt' in mat:return (.48,.62,.46)
    if 'water' in mat:return (.25,.56,.76)
    return (.68,.63,.55)

def build_vmf_geometry(solids,verbose=True):
    # Interleaved vertex buffer: position xyz, normal xyz, diffuse RGB, brush ordinal.
    floats=array('f');meta=[];counts=collections.Counter();fail=0;excluded=0;disp=0
    for i,sol in enumerate(solids):
        ss=sol['sides']
        visible=[s for s in ss if not s.get('material','').lower().startswith(VIS_NOT)]
        if not visible:excluded+=1;continue
        hit=intersect_brush(ss)
        if hit is None:fail+=1;continue
        verts,N,D,materials=hit
        mn=verts.min(axis=0);mx=verts.max(axis=0);ctr=(mn+mx)*.5
        ntri=0;usedmat=collections.Counter();start=len(floats)//10
        for n,d,mat in zip(N,D,materials):
            if mat.startswith(VIS_NOT):continue
            pts=verts[np.abs(verts@n-d)<0.17]
            if len(pts)<3:continue
            # Angle sort on this actual plane; outward normal opposite VMF half-space direction.
            pts=np.unique(pts,axis=0)
            center=pts.mean(axis=0)
            out=-n
            u=pts[0]-center;length=np.linalg.norm(u)
            if length<1e-7:continue
            u/=length;v=np.cross(out,u)
            theta=np.arctan2((pts-center)@v,(pts-center)@u)
            pts=pts[np.argsort(theta)]
            # Degenerate projections can arise from decompiler numerical noise.
            area=sum(np.linalg.norm(np.cross(pts[j]-pts[0],pts[j+1]-pts[0]))*.5 for j in range(1,len(pts)-1))
            if area<1e-3:continue
            rgb=surface_color(mat);usedmat[mat]+=1;counts[mat]+=1
            for k in range(1,len(pts)-1):
                for p in (pts[0],pts[k],pts[k+1]):
                    # Three.js convention, Y vertical. Source inches -> meters.
                    floats.extend((p[0]*.0254,p[2]*.0254,p[1]*.0254,
                                   out[0],out[2],out[1],*rgb,float(i)))
                ntri+=1
        if ntri:
            meta.append({'id':int(sol['id']) if str(sol['id']).isdigit() else i,'ord':i,
              'center':[round(float(ctr[k]*.0254),3) for k in (0,2,1)],
              'min':[round(float(mn[k]*.0254),3) for k in (0,2,1)],
              'max':[round(float(mx[k]*.0254),3) for k in (0,2,1)],
              'mat':usedmat.most_common(1)[0][0] if usedmat else '',
              'triStart':start,'triCount':ntri})
        if verbose and i and i%1250==0:print(f'  VMF {i}/{len(solids)} brushes, {len(floats)//30} triangles',flush=True)
    if sys.byteorder!='little':floats.byteswap()
    stats={'vmf_solids':len(solids),'visible_brushes':len(meta),'invisible_only':excluded,
      'failed_or_degenerate':fail,'triangles':len(floats)//30,'vertices':len(floats)//10,
      'visible_face_materials':dict(counts.most_common(16)),'displacement_geometry':'not reconstructed'}
    return floats.tobytes(),meta,stats
