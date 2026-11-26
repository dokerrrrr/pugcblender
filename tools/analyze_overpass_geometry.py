#!/usr/bin/env python3
"""Numeric OVERPASS real-mesh ↔ BSP/VMF point-cloud comparison. CPU only.

Requires numpy and scipy (not Blender). Uses actual UGC binary triangles and transforms.
Nearest-neighbor distances are *approximate sampled-point distances*, not a proof of
1:1 surface equivalence. Source static props absent from compiled BSP/VMF surfaces.

Examples:
 python analyze_overpass_geometry.py --data-dir .
 python analyze_overpass_geometry.py --data-dir . --samples-per-actor 140 --max-bsp 90000
 python analyze_overpass_geometry.py --data-dir . --dx 5 --dy -3 --dz 0
"""
import argparse,collections,gzip,json,pathlib,struct,zipfile
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

def parse_asset(raw):
    mv=memoryview(raw);offset=0
    def u32():
        nonlocal offset
        v=struct.unpack_from('<I',mv,offset)[0];offset+=4;return v
    assert u32()==0xFFFFFFFE
    meshes=[]
    for _ in range(u32()):
        n=u32()
        xyz=np.frombuffer(mv,dtype='<f4',count=n*3,offset=offset).reshape(-1,3).copy()
        offset+=n*32
        for _ in range(u32()):
            _,_,nn=struct.unpack_from('<III',mv,offset);offset+=12+nn
        meshes.append(xyz)
    instances=[]
    for _ in range(u32()):
        i=u32();M=np.frombuffer(mv,dtype='<f4',count=16,offset=offset).reshape(4,4).T.copy();offset+=64
        instances.append((i,M))
    return meshes,instances

def sample_local_real_mesh(zipfile_obj,id,limit,rng):
    meshes,instances=parse_asset(gzip.decompress(zipfile_obj.read(f'bp-mesh/{id}.bin.gz')))
    total=sum(len(meshes[i]) for i,_ in instances)
    if total==0:return np.zeros((0,3),dtype=np.float32)
    sampled=[]
    C=np.array([[1,0,0],[0,0,1],[0,1,0]],dtype=np.float32)
    for i,im in instances:
        xyz=meshes[i];want=max(2,round(limit*len(xyz)/total));want=min(len(xyz),want)
        chosen=xyz[rng.choice(len(xyz),want,replace=False)]
        # Three Y-up internal matrix, then convert to native UE/Blender Z-up.
        transformed=(chosen@im[:3,:3].T+im[:3,3])@C.T
        sampled.append(transformed.astype(np.float32))
    return np.concatenate(sampled)[:max(limit,len(instances)*2)]

def place_all(actors,samples):
    count=sum(len(samples.get(p['id'],[])) for p in actors)
    pts=np.empty((count,3),np.float32)
    ids=np.empty(count,np.int32)
    k=0
    for ob in actors:
        base=samples.get(ob['id'])
        if base is None or not len(base):continue
        o=ob['s'];s=np.array([o['x'],o['y'],o['z']],dtype=np.float32)
        q=ob['q'];quat=[q['x'],q['y'],q['z'],q['w']]
        rot=Rotation.from_quat(quat).as_matrix().astype(np.float32)
        tr=ob['t'];p=np.array([tr['x'],tr['y'],tr['z']],dtype=np.float32)/100.
        xyz=(base*s)@rot.T+p
        n=len(xyz);pts[k:k+n]=xyz;ids[k:k+n]=ob['id'];k+=n
    return pts[:k],ids[:k]

def stats_distances(a,b,max_points=120000):
    tree=cKDTree(b)
    d=tree.query(a,k=1,workers=-1)[0]
    return {'samples':len(d),'mean_m':float(np.mean(d)),'median_m':float(np.median(d)),
      'p90_m':float(np.percentile(d,90)),'within_0.5m_pct':float(np.mean(d<.5)*100),
      'within_1m_pct':float(np.mean(d<1)*100),'within_2m_pct':float(np.mean(d<2)*100),
      'within_5m_pct':float(np.mean(d<5)*100)},d

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-dir',default='.')
    ap.add_argument('--samples-per-actor',type=int,default=95)
    ap.add_argument('--max-bsp',type=int,default=120000)
    ap.add_argument('--dx',type=float,default=0)
    ap.add_argument('--dy',type=float,default=0)
    ap.add_argument('--dz',type=float,default=0)
    a=ap.parse_args();base=pathlib.Path(a.data_dir)
    j=json.loads((base/'overpass_lab_inputs.json').read_text(encoding='utf8'))
    data=np.load(base/'overpass_source_surfaces.npz')
    src=data['bsp'][:,0:3][:,[0,2,1]].copy().astype(np.float32)
    if j['alignment']['source_flip_x']:src[:,0]*=-1
    src+=np.array(j['alignment']['translation_meters_blender_xyz'],np.float32)+np.array([a.dx,a.dy,a.dz],np.float32)
    rng=np.random.default_rng(10311)
    if len(src)>a.max_bsp:src=src[rng.choice(len(src),a.max_bsp,replace=False)]
    results={'data':'Actual UGC triangle vertices sampled + sampled BSP vertices, transformed in meters',
      'approximation_note':'Nearest sampled vertex distances, not full surface Hausdorff. BSP lacks Source prop models.',
      'axis_transform':'Source = (-x,y,z) + sourceAlignment; PUGC UE xyz and quaternion used directly',
      'source_offset_xyz':(np.array(j['alignment']['translation_meters_blender_xyz'])+[a.dx,a.dy,a.dz]).tolist(),
      'source_total_sampled_vertices':len(src),'objects':{}}
    models={}
    with zipfile.ZipFile(base/'overpass_ugc_meshes.zip') as z:
        for id in j['asset_ids']:
            models[id]=sample_local_real_mesh(z,id,a.samples_per_actor,rng)
    for label in ['reference','generated']:
        ob=j[label]
        if not ob:continue
        pts,ids=place_all(ob['props'],models)
        # One-sided surface consistency (PUGC→BSP): may include props absent in Source BSP.
        p_to_s,dist=stats_distances(pts,src)
        # Coverage measured only in same region where PUGC meshes exist, avoid outer skybox.
        lo=np.percentile(pts,1,axis=0)-15
        hi=np.percentile(pts,99,axis=0)+15
        masked=src[np.all((src>=lo)&(src<=hi),axis=1)]
        s_to_p,_=stats_distances(masked,pts) if len(masked) else ({},None)
        per=[]
        counts=collections.Counter(o['id'] for o in ob['props'])
        for id,n in counts.most_common():
            d=dist[ids==id]
            if len(d):per.append({'UGC_Object_ID':id,'count':n,'samples':len(d),'median_to_BSP_m':float(np.median(d)),'within_2m_pct':float(np.mean(d<2)*100)})
        results['objects'][label]={'objectCount':len(ob['props']),'realUGCtypes':len(counts),'realSamples':len(pts),
            'UGC_to_BSP':p_to_s,'BSP_to_UGC_within_bbox':s_to_p,
            'byUGCtype':per}
        print(label,'ACTORS',len(ob['props']),'samples',len(pts),'UGC → BSP median(m)',round(p_to_s['median_m'],3),
              'BSP → UGC median(m)',round(s_to_p.get('median_m',float('nan')),3))
    target=base/'geometry_distance_report.json'
    target.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
    print('Report',target)

if __name__=='__main__':main()
