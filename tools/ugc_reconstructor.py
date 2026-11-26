#!/usr/bin/env python3
"""BSP -> PUBG PC UGC (.pugc) *experimental* geometry-first reconstructor.

This is a REAL surface-matching generator, not a memorized copy of the reference PUGC.
Trains a material/orientation->UGC mesh selection model from reference PUGC and
BSP; at build time reads *only* a BSP + the trained model + real mesh library.
Results are diagnostic approximations, NOT verified exact replicas.

Usage:
  python ugc_reconstructor.py train --bsp map.bsp --reference teacher.pugc --meshes bp-mesh.zip --model trained_model.json --report train.json
  python ugc_reconstructor.py build --bsp map.bsp --meshes bp-mesh.zip --model trained_model.json --output out.pugc --limit 3000 --report build.json
  python ugc_reconstructor.py audit --bsp map.bsp --meshes bp-mesh.zip --reference teacher.pugc --generated out.pugc --report audit.json

Requirements: numpy, scipy, OpenSSL, pugc editor mesh .bin.gz ZIP.
The game may reject saves with missing account identity / unknown patch metadata.
"""
from __future__ import annotations
import argparse, collections, dataclasses, hashlib, json, math, pathlib, random, re, struct, sys, time
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation as Rotation
from mesh_library import MeshLibrary
from source_bsp import parse_bsp
from pugc_codec import encode_raw, read_game, read_lab_game

# Classify Source face by its actual BSP material path; not an invented texture.
TAGS={
 'concrete':('concrete','cement','cinder','plaster','drainage','sewer','stucco','milwall','trainstation_template'),
 'stone':('stone','brick','tile','rock','marble','pavement','wall_house','infflr'),
 'wood':('wood','plywood','plank','board','timber','beam'),
 'metal':('metal','steel','iron','truss','chainlink','fence','wire','grate','portwall'),
 'glass':('glass','window','translucent'),
 'ground':('grass','dirt','mud','sand','soil','earth','terrain','foliage','blend_','blacktop'),
 'road':('asphalt','road','sidewalk','street','blacktop','concrete_floor'),
 'water':('water','river','pool'),
 'roof':('roof','shingle','slate'),
}

def texture_tag(material):
    s=str(material).lower().replace('\\','/')
    # Give path prefixes more authority than name fragments.
    pref=s.split('/')[0]
    if pref in ('concrete','stone','metal','wood','glass','water'):return pref
    for tag,terms in TAGS.items():
        if any(term in s for term in terms):return tag
    return 'misc'

def axis_tag(normal):
    az=abs(float(normal[2]));return 'horizontal' if az>.83 else ('vertical' if az<.23 else 'slope')

def serial(x):return json.dumps(x,separators=(',',':'),ensure_ascii=False)

def make_faces(bsp_path,axis_flip=True, offset=(0,0,0)):
    raw, meta,stat,mats=parse_bsp(bsp_path)
    arr=np.frombuffer(raw,dtype='<f4').reshape(-1,10)
    fids=arr[:,9].astype(np.int32)
    order=np.argsort(fids,kind='stable');idx=fids[order]
    edges=np.r_[0,np.flatnonzero(idx[1:]!=idx[:-1])+1,len(idx)]
    matmap={int(o['id']):o['mat'] for o in meta}
    off=np.asarray(offset,float)
    out=[]
    for i in range(len(edges)-1):
        sub=arr[order[edges[i]:edges[i+1]],:3]
        if len(sub)<3 or len(sub)%3:continue
        # BSP parser stores (Source x, up, y) in meters. Blender/world is (x, y, z).
        v=sub[:,[0,2,1]].astype(np.float64)
        if axis_flip:v[:,0]*=-1
        v+=off
        tri=v.reshape(-1,3,3)
        cross=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);a=np.linalg.norm(cross,axis=1)*.5
        area=float(np.sum(a));
        if not math.isfinite(area) or area<0.001:continue
        j=int(np.argmax(a));n=cross[j]/max(1e-12,2*a[j])
        norm=np.linalg.norm(n)
        if norm<1e-8:continue
        n=n/norm
        center=np.average(tri.mean(axis=1),axis=0,weights=np.maximum(a,1e-12))
        # Stable in-plane basis; vertical faces prioritize the Z axis.
        if abs(n[2])<.82:
            vaxis=np.array([0.,0.,1.]);vaxis-=n*np.dot(vaxis,n);vaxis/=max(1e-10,np.linalg.norm(vaxis))
            uaxis=np.cross(vaxis,n);uaxis/=max(1e-10,np.linalg.norm(uaxis))
        else:
            uaxis=np.array([1.,0.,0.]);uaxis-=n*np.dot(uaxis,n);uaxis/=max(1e-10,np.linalg.norm(uaxis))
            vaxis=np.cross(n,uaxis);vaxis/=max(1e-10,np.linalg.norm(vaxis))
        uv=np.stack((v@uaxis,v@vaxis),axis=1)
        lo=uv.min(axis=0);hi=uv.max(axis=0)
        width,height=(hi-lo).tolist()
        if width<.003 or height<.003:continue
        bbcenter=center+(uaxis*(lo[0]+hi[0])/2+vaxis*(lo[1]+hi[1])/2)-(uaxis*np.dot(center,uaxis)+vaxis*np.dot(center,vaxis))
        # Equivalent to projecting face center on polygon oriented bbox center.
        mat=matmap.get(int(idx[edges[i]]),'')
        face={'id':int(idx[edges[i]]),'pos':bbcenter,'normal':n,'u':uaxis,'v':vaxis,
              'lengths':np.array([width,height]),'area':area,'material':mat,
              'tag':texture_tag(mat),'orientation':axis_tag(n),'fill':min(1.,area/max(width*height,1e-6))}
        out.append(face)
    return out,stat

def meta_model(modelpath):return json.loads(pathlib.Path(modelpath).read_text(encoding='utf8'))

def props(pugc):
    j, _ = read_lab_game(pugc)
    return [o for o in (j.get('objects') or j.get('modObjects') or []) if int(o.get('deviceIndex',-1))==-1]

def actor_center(o,d):
    tr=o['spawnTransform'];t=np.array([tr['translation'][k] for k in 'xyz'],float)/100
    q=np.array([tr['rotation'][k] for k in 'xyzw'],float);q=q/max(1e-9,np.linalg.norm(q))
    s=np.array([tr['scale3D'][k] for k in 'xyz'],float)
    local=np.array(d['center']);return t+Rotation.from_quat(q).apply(local*s)

def face_neighbors(faces,query_pts):
    cloud=np.stack([f['pos'] for f in faces]);tree=cKDTree(cloud)
    # centroid-to-centroid is cheap, but biased against enormous polygons: supplement with
    # nearest BSP triangulated vertices for each teacher placement.
    dd,ii=tree.query(query_pts,k=min(8,len(faces)))
    return np.atleast_2d(dd),np.atleast_2d(ii)

def nearest_faces(actors, descriptors, faces, raw_vertices, axis_flip, offset):
    source=raw_vertices[:,[0,2,1]].astype(np.float32).copy()
    if axis_flip:source[:,0]*=-1
    source+=np.asarray(offset,np.float32)
    tree=cKDTree(source)
    q=[];ids=[];centers=[]
    for o in actors:
        id=int(o['objectId']);d=descriptors.get(str(id))
        if not d:continue
        centers.append(actor_center(o,d));ids.append(id)
    centers=np.array(centers)
    # Anchor to closest actual BSP vertex rather than face centroid (large face centroids are far away).
    distances,vi=tree.query(centers,k=1)
    face_ids=raw_vertices[vi,9].astype(int)
    mapping={f['id']:i for i,f in enumerate(faces)}
    fidx=np.array([mapping.get(int(x),-1) for x in face_ids],int)
    # Some tiny geometry is filtered; use nearest centroid for those.
    bad=np.where(fidx<0)[0]
    if len(bad):
        _,ii=face_neighbors(faces,centers[bad]);fidx[bad]=ii[:,0]
    return ids,centers,distances,fidx

def model_for_training(bsp,ref,zip_path,report_path,model_path):
    t0=time.perf_counter(); sha=hashlib.sha256(pathlib.Path(bsp).read_bytes()).hexdigest()
    raw,_,_,_=parse_bsp(bsp);src=np.frombuffer(raw,dtype='<f4').reshape(-1,10)
    # Precalibrated Overpass transform is only the starting point; verify candidate flips by distances.
    # Input old Geometry Lab assumption: flip Source X, offset on Blender xyz (m).
    teacher=props(ref)
    lib=MeshLibrary(zip_path)
    ids=sorted(set(int(o['objectId']) for o in teacher));desc={str(i):lib.load(i)[0] for i in ids}
    source_bbox=np.stack((src[:,[0,2,1]].min(0),src[:,[0,2,1]].max(0)))
    teacher_centers=np.array([actor_center(o,desc[str(o['objectId'])]) for o in teacher])
    # Candidate alignment can be adjusted via affine median, plus search small offsets. Keep flip
    # fixed for the known Overpass reference and test orientation itself independently below.
    probes=[]
    for flip in (True,False):
        bs=src[:,[0,2,1]].copy()
        if flip:bs[:,0]*=-1
        center=np.percentile(bs,[10,50,90],axis=0)[1]
        guess=np.median(teacher_centers,axis=0)-center
        if flip:approx=np.array([325.28,475.59,56.92])
        else:approx=guess
        tree=cKDTree(bs[::3])
        for delta in [np.array([0,0,0]),np.array([2,0,0]),np.array([-2,0,0]),np.array([0,2,0]),np.array([0,-2,0])]:
            shift=approx+delta
            dist,_=tree.query(teacher_centers-shift)
            # 50% trimmed average avoids most prop geometry not in BSP and background terrain.
            score=float(np.mean(np.minimum(dist,12)))
            probes.append((score,flip,shift.tolist()))
    probes.sort(key=lambda x:x[0]);best=probes[0]
    # Limit huge coordinate excursions; on another reference fit offset via coarse search later.
    flip=bool(best[1]);offset=np.array(best[2])
    faces,stats=make_faces(bsp,flip,offset)
    src_world=src.copy();face_ids=np.array([int(x['id']) for x in faces])
    aids,centers,dists,fi=nearest_faces(teacher,desc,faces,src_world,flip,offset)
    labels=[];examples=[];idx=0
    for o in teacher:
        id=int(o['objectId']);d=desc.get(str(id))
        if d is None:continue
        f=faces[int(fi[idx])];dist=float(dists[idx]);pos=centers[idx]
        examples.append({'id':id,'face_id':f['id'],'tag':f['tag'],'orientation':f['orientation'],
                         'dist_m':dist,'actor_center_m':pos.tolist(),
                         'source_face_area_m2':f['area']})
        idx+=1
    # Spatial holdout by region: 4x4 chessboard cells, ~20% held-out for reproducible validation.
    XY=np.array([e['actor_center_m'][:2] for e in examples]);x0=np.percentile(XY,5,axis=0)
    tile=np.floor((XY-x0)/18).astype(int)
    holdout=((tile[:,0]+2*tile[:,1])%5==0)
    if np.mean(holdout)<.07 or np.mean(holdout)>.5:
        rng=np.random.default_rng(27);holdout=rng.random(len(examples))<.2
    def counts_for(ix):
        c=collections.defaultdict(collections.Counter)
        for k in ix:
            e=examples[k]
            if e['dist_m']>12:continue # unrelated BSP asset in absent Source props
            key=e['tag']+'|'+e['orientation'];c[key][e['id']]+=math.exp(-max(0.,e['dist_m']-1.5)/9)
        return {k:dict(v) for k,v in c.items()}
    valid_train=np.flatnonzero(~holdout);valid_test=np.flatnonzero(holdout)
    ctrain=counts_for(valid_train);freq=collections.Counter(e['id'] for e in examples if e['dist_m']<12)
    def score_id(f,dct,freqs):
        tags=f['tag']+'|'+f['orientation'];counts=dct.get(tags,{})
        global_prior=freqs
        # Material-conditioned probability with global smoothing.
        options=set(counts)|set(global_prior)
        if not options:return -1
        return max(options,key=lambda i: float(counts.get(i,0))+0.015*float(global_prior.get(i,0)))
    predicted=[score_id(examples[k],ctrain,freq) for k in valid_test]
    actual=[examples[k]['id'] for k in valid_test]
    match=sum(a==p for a,p in zip(actual,predicted));baseline=freq.most_common(1)[0][0]
    # Learn which axis of each real UGC model is normally used as a surface normal.
    orientation_priors=collections.defaultdict(collections.Counter)
    for o in teacher:
        sid=str(o['objectId']);d=desc[sid]
        tr=o['spawnTransform'];q=np.array([tr['rotation'][k] for k in 'xyzw'],float)
        q=q/max(1e-10,np.linalg.norm(q))
        sc=np.abs(np.array([tr['scale3D'][k] for k in 'xyz'],float))
        # The thickest real meshes cannot be classified as flat walls with this heuristic.
        local_normal=int(np.argmin(np.array(d['dimensions'])*np.maximum(sc,.01)))
        vec=Rotation.from_quat(q).apply(np.eye(3)[local_normal])
        orientation_priors[sid][axis_tag(vec)]+=1
    # Learn which Source surface categories the teacher actually chose to represent,
    # measured against REAL reference mesh vertices (not just actor pivots).
    teacher_cloud=[]
    for o in teacher:
        d,verts=lib.load(o['objectId'],cap_vertices=3000)
        sub=verts[::max(1,len(verts)//12)][:12]
        tr=o['spawnTransform'];p=np.array([tr['translation'][k] for k in 'xyz'],float)/100
        q=np.array([tr['rotation'][k] for k in 'xyzw'],float);q/=max(1e-9,np.linalg.norm(q))
        sc=np.array([tr['scale3D'][k] for k in 'xyz'],float)
        teacher_cloud.append(Rotation.from_quat(q).apply(sub*sc)+p)
    importance=collections.defaultdict(list)
    if teacher_cloud:
        targettree=cKDTree(np.concatenate(teacher_cloud))
        dst,_=targettree.query(np.array([f['pos'] for f in faces]),k=1)
        for f,dist in zip(faces,dst):
            importance[f['tag']+'|'+f['orientation']].append(math.exp(-min(15.,float(dist))/3.))
    source_importance={k:round(float(np.mean(v)),5) for k,v in importance.items() if len(v)>12}
    # Save compact learned style+geometry library. NO actor positions from teacher stored.
    m={'version':1,'model_type':'BSP_surface_to_real_UGC_material_and_form',
       'reference_bsp_sha256':sha,
       'coordinate_handedness':{'source_reflect_x':flip,'blender_source_offset_m':offset.tolist(),
                                 'note':'Calibrated on reference; on other maps only shape/material priors transfer'},
       'descriptors':desc,'learned_surface_priors':counts_for(range(len(examples))),
       'id_frequency':dict(collections.Counter(aids)),
       'id_orientation_priors':{k:dict(v) for k,v in orientation_priors.items()},
       'source_surface_interest':source_importance,
       'material_categories':{k:list(v) for k,v in TAGS.items()},
       'reference_count':len(examples),'user_limit':3000}
    pathlib.Path(model_path).write_text(json.dumps(m,indent=1,ensure_ascii=False),encoding='utf8')
    report={'bsp_sha256':sha,'reference_props':len(teacher),'UGC_types':len(ids),'mesh_binary_types_loaded':len(desc),
            'source_bsp_faces':len(faces),'bsp_triangles':stats.get('triangles'),
            'selected_flip':flip,'selected_offset_m':offset.tolist(),
            'alignment_probes_top3':probes[:3],
            'reference_to_nearest_BSP_vertex_m':{'p50':float(np.percentile(dists,50)),'p90':float(np.percentile(dists,90)),
            'gt_5m_pct':float(np.mean(dists>5)*100)},
            'spatial_holdout':{'train':len(valid_train),'test':len(valid_test),'exact_object_id_accuracy_pct':100*match/max(1,len(valid_test)),
             'global_majority_baseline_accuracy_pct':100*sum(a==baseline for a in actual)/max(1,len(actual)),
             'warning':'This tests material/orientation classification only, NOT the placement quality on a new map'},
            'texture_note':'BSP material names and UGC material paths are available, not a source->PUBG texture replacement mechanism',
            'runtime_s':round(time.perf_counter()-t0,2)}
    pathlib.Path(report_path).write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf8')
    return report

def prioritize_faces(faces,limit,model=None):
    # Exclude sub-centimeter detail and severely sparse irregular shapes; prioritize surface area.
    candidates=[f for f in faces if f['area']>.035 and f['fill']>.25]
    if len(candidates)<=limit:return candidates
    # Fairly spread budget over 16m XY cells, instead of consuming every prop on the giant ground.
    cells=collections.defaultdict(list)
    pos=np.array([f['pos'] for f in candidates]);origin=np.percentile(pos,1,axis=0)
    for f in candidates:
        key=(int(math.floor((f['pos'][0]-origin[0])/18)),int(math.floor((f['pos'][1]-origin[1])/18)))
        # Cap extreme ground faces and long slender trim faces. Size still matters.
        l=f['lengths'];ratio=min(l)/max(l)
        role_boost=1.45 if f['orientation']=='vertical' else 1
        f['score']=(min(f['area'],110)**.59)*(max(.12,ratio)**.25)*role_boost
        if model:
            learned_interest=model.get('source_surface_interest',{}).get(f['tag']+'|'+f['orientation'],.4)
            f['score']*=.55+1.2*learned_interest
        cells[key].append(f)
    for v in cells.values():v.sort(key=lambda x:x['score'],reverse=True)
    # Every occupied cell gets proportional quota by total visible area, with square-root damping.
    keys=list(cells);budgets={k:max(1, math.sqrt(sum(min(100,f['area']) for f in cells[k]))) for k in keys}
    total=sum(budgets.values());quota={k:max(1,int(limit*budgets[k]/total)) for k in keys}
    selected=[];remaining=[]
    for k,g in cells.items():
        n=min(quota[k],len(g));selected.extend(g[:n]);remaining.extend(g[n:])
    if len(selected)>limit:selected.sort(key=lambda x:x['score'],reverse=True);selected=selected[:limit]
    elif len(selected)<limit:selected+=sorted(remaining,key=lambda x:x['score'],reverse=True)[:limit-len(selected)]
    return selected[:limit]

def select_ugc(face,model,usage):
    tag=face['tag'];orient=face['orientation'];cat=tag+'|'+orient
    rawcounts=model['learned_surface_priors'].get(cat,{})
    freq=model['id_frequency'];options=[]
    for sid,desc in model['descriptors'].items():
        d=np.asarray(desc['dimensions'],float)
        if np.min(d)<.002:continue
        thin=np.min(d)/np.max(d)
        name=' '.join(desc['materials']).lower()
        # Use visual/texture material affinities, not synthetic material recoloring.
        tex_aff=0
        if tag=='concrete' and any(x in name for x in ('concrete','cement','cinder','wall','stone','sidewalk')):tex_aff+=2
        elif tag=='wood' and ('wood' in name or 'plywood' in name):tex_aff+=2
        elif tag=='metal' and any(x in name for x in ('metal','steel','iron','fence')):tex_aff+=2
        elif tag=='ground' and any(x in name for x in ('grass','land','ground','dirt','road')):tex_aff+=2
        elif tag=='road' and any(x in name for x in ('road','floor','sidewalk','concrete')):tex_aff+=2
        elif tag=='stone' and any(x in name for x in ('stone','wall','brick','cement')):tex_aff+=2
        elif tag=='glass' and 'glass' in name:tex_aff+=2
        elif tag=='roof' and ('roof' in name or 'floor' in name):tex_aff+=2
        elif tag=='water' and 'water' in name:tex_aff+=2
        source_u,source_v=face['lengths'];a=max(source_u,source_v);b=min(source_u,source_v)
        long=np.sort(d)[1:];plane_aspect=float(long[1]/max(1e-4,long[0]))
        target_aspect=a/max(b,1e-4)
        aspect_error=abs(math.log(max(1e-6,plane_aspect)/max(1e-6,target_aspect)))
        # Favor thin, planar surfaces. Cubical models are still allowed for wide floors and beams.
        shape=1.6 if thin<.19 else (1 if thin<.46 else -0.6)
        # Avoid enormous complex prefabs for simple BSP faces.
        weight=math.log1p(float(rawcounts.get(sid,0))*3+.05*float(freq.get(sid,0)))
        orient_counts=model.get('id_orientation_priors',{}).get(sid,{})
        orient_total=sum(orient_counts.values())
        orient_aff=(orient_counts.get(orient,0)+1)/(orient_total+3) if orient_total else 1/3
        score=2.7*tex_aff+shape+.7*weight-1.0*aspect_error-.000065*float(desc['mesh_vertices'])
        score+=1.4*math.log(max(.05,orient_aff)*3)
        score-=.55*math.log1p(usage.get(sid,0)) # don't emit 3000 identical objects
        # Encourage structured elements used often in reference.
        options.append((score,sid))
    if not options:raise RuntimeError('No UGC candidates')
    return int(max(options)[1])

def make_placement(face,id,desc,min_scale=.09):
    d=np.asarray(desc['dimensions'],float);local_center=np.asarray(desc['center'],float)
    n=face['normal'];u=face['u'];v=face['v'];target=np.asarray(face['lengths'],float)
    thin_axis=int(np.argmin(d))
    tangents=[k for k in range(3) if k!=thin_axis]
    # Match longer local axis with longer target dimension to reduce texture stretch.
    if (d[tangents[0]]>d[tangents[1]]) != (target[0]>target[1]):tangents=tangents[::-1]
    axes=np.zeros((3,3))
    axes[:,tangents[0]]=u;axes[:,tangents[1]]=v;axes[:,thin_axis]=n
    if np.linalg.det(axes)<0:axes[:,thin_axis]*=-1
    # If the large facade has modest detail depth, keep some original thickness.
    thickness=.18 if face['orientation']=='vertical' else .11
    # Water, giant ground/floor areas can be thinner.
    if face['tag'] in ('ground','road','water'):thickness=.07
    scale=np.ones(3);scale[tangents[0]]=target[0]/d[tangents[0]];scale[tangents[1]]=target[1]/d[tangents[1]]
    scale[thin_axis]=thickness/d[thin_axis]
    scale=np.maximum(np.round(scale,2),min_scale) # No artificial upper bound; round then enforce reference minimum
    q=Rotation.from_matrix(axes).as_quat()
    pos=face['pos'] - axes@(local_center*scale)
    # Face is the middle of the matched thickness, not the origin of the UGC mesh.
    if not np.isfinite(pos).all() or not np.isfinite(q).all():raise ValueError('Non-finite transform')
    return {'objectId':id,'deviceIndex':-1,'userDeviceName':'',
            'spawnTransform':{'translation':{k:round(float(x*100),2) for k,x in zip('xyz',pos)},
            'rotation':{k:round(float(x),8) for k,x in zip('xyzw',q)},
            'scale3D':{k:float(x) for k,x in zip('xyz',scale)}}}

def build(bsp,meshzip,modelfile,out,limit,report,min_scale=.09,template_pugc=None):
    t0=time.perf_counter();m=meta_model(modelfile)
    src_hash=hashlib.sha256(pathlib.Path(bsp).read_bytes()).hexdigest()
    known=src_hash==m['reference_bsp_sha256']
    origin=m['coordinate_handedness']['blender_source_offset_m'] if known else [0,0,0]
    faces,stats=make_faces(bsp, m['coordinate_handedness']['source_reflect_x'], origin)
    if not known:
        # Center new BSP in a positive UE-safe workspace; same trained style priors transfer.
        mn=np.min([f['pos'] for f in faces],axis=0);mx=np.max([f['pos'] for f in faces],axis=0)
        center=(mn+mx)/2
        target=np.array([500.,500.,60.]);shift=target-center
        for f in faces:f['pos']=f['pos']+shift
    else:shift=np.zeros(3)
    chosen=prioritize_faces(faces,limit,m)
    usage=collections.Counter();outobjs=[]
    for f in chosen:
        id=select_ugc(f,m,usage)
        outobjs.append(make_placement(f,id,m['descriptors'][str(id)],min_scale));usage[str(id)]+=1
    # Optional genuine game-created save supplies creator/account metadata.
    # All scene objects and device link arrays are replaced, not imported from the template.
    # Validate all chosen game assets against the supplied *real* mesh archive.
    library=MeshLibrary(meshzip)
    missing_meshes=sorted(set(o['objectId'] for o in outobjs)-library.ids)
    if missing_meshes:raise ValueError(f'Missing required UGC meshes: {missing_meshes[:15]}')
    library.close()
    now=int(time.time())
    j={'name':'BSP_UGC_Geometry_Experimental','dataVersion':3,'buildVersion':'2608.1.1',
       'creatorData':{'name':'BSP geometry','description':'Automated textured-asset approximation; not 1:1; devices excluded.',
        'versionMajor':1,'versionMinor':0,'ownerAccountId':'','ownerNickName':''},
       'objects':outobjs,'roundRuleData':{'roundGameCount':1,'timeLimit':300},
       'characterRuleData':{'characterHP':100},'gameRuleData':{},'userSelectableData':{},
       'editFileData':{'createAccountId':'','createTime':now,'lastModifierAccountId':'','lastModifiedTime':now,
                       'editPlayers':[],'lastHostPlayerData':None}}
    if template_pugc:
        template, _ = read_lab_game(template_pugc)
        template['objects']=outobjs
        template.pop('modObjects',None)
        for key in ('deviceEventList','deviceConnections','deviceEventLinks'):
            if key in template:template[key]=[]
        template['name']='BSP_UGC_Geometry_Experimental'
        template['dataVersion']=3
        template['buildVersion']='2608.1.1'
        j=template
    pathlib.Path(out).write_bytes(encode_raw(j))
    verify=read_game(out)
    assert len(verify['objects'])==len(outobjs) and len(outobjs)<=limit
    assert all(o.get('deviceIndex')==-1 for o in verify['objects'])
    assert all(min(o['spawnTransform']['scale3D'].values())>=min_scale for o in outobjs)
    assert all(all(round(x,2)==x for x in o['spawnTransform']['scale3D'].values()) for o in outobjs)
    typed=collections.Counter(o['objectId'] for o in outobjs)
    objmat={int(k):' '.join(v['materials']).lower() for k,v in m['descriptors'].items()}
    matched=0
    for f,o in zip(chosen,outobjs):
        tag=f['tag']; name=objmat[o['objectId']]
        if any(w in name for w in TAGS.get(tag,())):matched+=1
    summary={'result':'Experimental BSP-only generation, NOT a 1:1 replica',
       'input_bsp_sha256':src_hash,'reference_bsp_recognized_for_alignment':known,
       'teacher_pugc_opened_during_build':False,'unrelated_template_save_used_for_metadata':bool(template_pugc),
       'source_bsp_faces':len(faces),'source_bsp_triangles':stats.get('triangles'),
       'selected_source_faces':len(chosen),'source_face_area_coverage_pct':round(100*sum(f['area'] for f in chosen)/sum(f['area'] for f in faces),2),
       'output_object_count':len(outobjs),'distinct_ugc_object_ids':len(typed),'ugc_types':typed.most_common(),
       'devices':0,'min_scale':min(min(o['spawnTransform']['scale3D'].values()) for o in outobjs),
       'scale_precision_decimals':2,'specified_min_scale':min_scale,'roundtrip_decode_ok':True,
       'material_semantic_keyword_match_pct':round(100*matched/max(1,len(chosen)),2),
       'missing_source_prop_meshes':True,'source_material_textures_copied':False,
       'warning':'Game import not tested. PUGC static mesh texture is fixed by objectId; cannot directly assign Counter-Strike textures.',
       'runtime_s':round(time.perf_counter()-t0,2)}
    pathlib.Path(report).write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    return summary

def audit(bsp,zip_path,reference,generated,report,limit_samples=45000):
    # Compare real mesh surface sample clouds to visible BSP vertex cloud, same fixed alignment.
    start=time.perf_counter();lib=MeshLibrary(zip_path)
    original=props(reference);synthetic=props(generated)
    arr=np.frombuffer(parse_bsp(bsp)[0],dtype='<f4').reshape(-1,10)
    raw=arr[::max(1,len(arr)//limit_samples),:3][:,[0,2,1]].copy();raw[:,0]*=-1
    raw+=np.array([325.28,475.59,56.92]); bsp_tree=cKDTree(raw)
    results={}; clouds={}
    for name,objects in [('teacher',original),('generated',synthetic)]:
        rng=np.random.default_rng(2026);chunks=[];pruned=0
        for o in objects:
            try:
                d,pts=lib.load(o['objectId'],cap_vertices=2000)
                if len(pts)==0:continue
                tr=o['spawnTransform'];p=np.array([tr['translation'][k] for k in 'xyz'],float)/100
                q=np.array([tr['rotation'][k] for k in 'xyzw'],float);q/=max(1e-9,np.linalg.norm(q))
                sc=np.array([tr['scale3D'][k] for k in 'xyz'],float)
                sub=pts[::max(1,len(pts)//45)][:45]
                world=Rotation.from_quat(q).apply(sub*sc)+p
                chunks.append(world)
            except Exception:pruned+=1
        cloud=np.concatenate(chunks);clouds[name]=cloud
        dd,_=bsp_tree.query(cloud,k=1)
        # Prune scene extremities, but expose full histogram so model failure isn't hidden.
        results[name]={'objects':len(objects),'sampled_real_ugc_mesh_vertices':len(cloud),
          'median_to_nearest_bsp_vertex_m':round(float(np.median(dd)),3),
          'p90_m':round(float(np.percentile(dd,90)),3),
          'within_1m_pct':round(100*float(np.mean(dd<1)),2),
          'within_2m_pct':round(100*float(np.mean(dd<2)),2),'mesh_failures':pruned}
    ttree=cKDTree(clouds['teacher']);gtree=cKDTree(clouds['generated'])
    td,_=gtree.query(clouds['teacher']);gd,_=ttree.query(clouds['generated'])
    results['cross_comparison']={'teacher_to_generated_median_m':round(float(np.median(td)),3),
      'generated_to_teacher_median_m':round(float(np.median(gd)),3),
      'teacher_to_generated_within_1m_pct':round(100*float(np.mean(td<1)),2),
      'generated_to_teacher_within_1m_pct':round(100*float(np.mean(gd<1)),2)}
    results['method']='Nearest sampled VERTEX, not triangle surface or true render/texturing comparison.'
    results['runtime_s']=round(time.perf_counter()-start,2)
    pathlib.Path(report).write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
    return results

def main():
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='command',required=True)
    t=sub.add_parser('train');t.add_argument('--bsp',required=True);t.add_argument('--reference',required=True);t.add_argument('--meshes',required=True);t.add_argument('--model',required=True);t.add_argument('--report',required=True)
    b=sub.add_parser('build');b.add_argument('--bsp',required=True);b.add_argument('--meshes',required=True);b.add_argument('--model',required=True);b.add_argument('--output',required=True);b.add_argument('--limit',type=int,default=3000);b.add_argument('--template-pugc',help='Optional separate fresh game-created PUGC save for account/rule metadata; its objects are discarded');b.add_argument('--min-scale',type=float,default=.09,help='Minimum axis scale, >= 0.09 from the provided reference PUGC; 0.1 for editor compatibility');b.add_argument('--report',required=True)
    a=sub.add_parser('audit');a.add_argument('--bsp',required=True);a.add_argument('--meshes',required=True);a.add_argument('--reference',required=True);a.add_argument('--generated',required=True);a.add_argument('--report',required=True)
    args=ap.parse_args()
    if args.command=='train':r=model_for_training(args.bsp,args.reference,args.meshes,args.report,args.model)
    elif args.command=='build':
        if not 1<=args.limit<=3000:ap.error('1 <= --limit <= 3000')
        if not (math.isfinite(args.min_scale) and args.min_scale>=0.09):ap.error('--min-scale must be >= 0.09 (rounded reference-map minimum)')
        r=build(args.bsp,args.meshes,args.model,args.output,args.limit,args.report,args.min_scale,args.template_pugc)
    else:r=audit(args.bsp,args.meshes,args.reference,args.generated,args.report)
    print(json.dumps(r,ensure_ascii=False,indent=2)[:9000])
if __name__=='__main__':main()
