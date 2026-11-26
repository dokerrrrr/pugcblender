"""Parse compiled Source BSP surfaces for the laboratory and reconstructor."""
from array import array
import collections
import io
import pathlib
import struct
import sys
import zipfile

import numpy as np

from pugc_vmf_lab import surface_color


TECH=('tools/','effects/','dev/','editor/','tools\\')
HIDE_MATERIALS=('tools/toolsnodraw','tools/toolsskip','tools/toolstrigger','tools/toolsclip','tools/toolsplayerclip','tools/toolsnpcclip','tools/toolsoccluder','tools/toolsareaportal','tools/toolsinvisible','tools/toolsblocklight','tools/toolsblockbullets','tools/toolsblock_los','tools/toolshint')

def parse_bsp(path):
    b=pathlib.Path(path).read_bytes()
    if b[:4]!=b'VBSP':raise ValueError('Not a Source VBSP file')
    version=struct.unpack_from('<i',b,4)[0]
    if version not in (19,20,21):raise ValueError(f'Unverified BSP version {version}; expected 19/20/21')
    def lump(i):
        off,ln,vers,fourcc=struct.unpack_from('<4i',b,8+i*16)
        if off<0 or ln<0 or off+ln>len(b):raise ValueError(f'Invalid lump {i}')
        if fourcc:raise ValueError(f'Lump {i} compressed/unsupported, fourCC={fourcc}')
        return memoryview(b)[off:off+ln]
    verts=np.frombuffer(lump(3),dtype='<f4').reshape(-1,3)
    edges=np.frombuffer(lump(12),dtype='<u2').reshape(-1,2)
    surf=np.frombuffer(lump(13),dtype='<i4')
    texinfo=lump(6);texdata=lump(2)
    names=lump(43).tobytes(); nameidx=np.frombuffer(lump(44),dtype='<i4')
    textable=[]
    for i in range(len(texdata)//32):
        index=struct.unpack_from('<i',texdata,i*32+12)[0]
        if index<0 or index>=len(nameidx):textable.append(f'unknown_tex_{i}');continue
        off=int(nameidx[index]);end=names.find(b'\0',off)
        textable.append(names[off:end].decode('utf8','replace').lower().replace('\\','/'))
    texinfo_ids=[]
    for i in range(len(texinfo)//72):
        val=struct.unpack_from('<i',texinfo,i*72+68)[0]
        texinfo_ids.append(val)
    dispinfos=lump(26);dispverts=np.frombuffer(lump(33),dtype='<f4').reshape(-1,5)
    faces=lump(7)
    # Vertex layout: pos 3, normal 3, material color 3, faceIndex 1.
    buf=array('f');meta=[];stats=collections.Counter();mats=collections.Counter()
    bboxmin=np.array([1e12,1e12,1e12]);bboxmax=-bboxmin.copy()
    for fid in range(len(faces)//56):
        planenum,side,onnode,firstedge,numedges,info,dispid=struct.unpack_from('<HBBihhh',faces,fid*56)
        if numedges<3 or info<0 or info>=len(texinfo_ids):continue
        tx=texinfo_ids[info]
        if tx<0 or tx>=len(textable):continue
        material=textable[tx];ml=material.lower()
        if ml.startswith(HIDE_MATERIALS) or ml.startswith(TECH):stats['technical_faces']+=1;continue
        if firstedge<0 or firstedge+numedges>len(surf):continue
        surfids=surf[firstedge:firstedge+numedges]
        eids=np.abs(surfids)
        if (eids>=len(edges)).any():continue
        corners=edges[eids, (surfids<0).astype(np.intp)]
        if (corners>=len(verts)).any():continue
        facepts=verts[corners].astype(np.float64)
        if not np.isfinite(facepts).all():continue
        # Source face winding usually matches plane orientation; use polygon's own normal.
        normal=np.cross(facepts[1]-facepts[0],facepts[2]-facepts[0]); ln=float(np.linalg.norm(normal))
        if ln<1e-8:continue
        normal/=ln
        trilst=[]
        if dispid>=0:
            if dispid>=len(dispinfos)//176 or len(facepts)!=4:
                stats['bad_disp_faces']+=1;continue
            di=dispid*176
            startpos=np.array(struct.unpack_from('<3f',dispinfos,di),dtype=float)
            vertex_start,tri_start,power=struct.unpack_from('<3i',dispinfos,di+12)
            side_len=(1<<power)+1 if 1<=power<=6 else 0
            if not side_len or vertex_start<0 or vertex_start+side_len*side_len>len(dispverts):
                stats['bad_disp_faces']+=1;continue
            start=int(np.argmin(np.linalg.norm(facepts-startpos,axis=1)))
            # Per Valve displacement convention, first corner is nearest startPosition.
            p00=facepts[start];p10=facepts[(start+1)%4];p11=facepts[(start+2)%4];p01=facepts[(start+3)%4]
            grid=[]
            for y in range(side_len):
                v=y/(side_len-1)
                for x in range(side_len):
                    u=x/(side_len-1)
                    q=(1-u)*(1-v)*p00+u*(1-v)*p10+u*v*p11+(1-u)*v*p01
                    disp=dispverts[vertex_start+y*side_len+x]
                    q=q+disp[:3]*disp[3]
                    grid.append(q)
            for y in range(side_len-1):
                for x in range(side_len-1):
                    a=y*side_len+x;bb=a+1;c=a+side_len;d=c+1
                    trilst.extend(((grid[a],grid[bb],grid[d]),(grid[a],grid[d],grid[c])))
            stats['displacement_faces']+=1
        else:
            # Compiled BSP face edges are convex for the world geometry.
            for k in range(1,len(facepts)-1):trilst.append((facepts[0],facepts[k],facepts[k+1]))
            stats['regular_faces']+=1
        if not trilst:continue
        startv=len(buf)//10;col=surface_color(ml)
        for aa,bb,cc in trilst:
            nn=np.cross(bb-aa,cc-aa); ll=np.linalg.norm(nn)
            if ll<1e-8:continue
            nn/=ll
            for p in (aa,bb,cc):
                # XYZ in Source inches converted to 3D scene (x,y_up,z) in meters.
                buf.extend((float(p[0]*.0254),float(p[2]*.0254),float(p[1]*.0254),
                            float(nn[0]),float(nn[2]),float(nn[1]),*col,float(fid)))
        tri=len(buf)//10-startv
        if tri==0:continue
        mats[ml]+=1
        center=facepts.mean(axis=0)*.0254
        if dispid>=0:
            center=np.mean(np.asarray(grid),axis=0)*.0254
        meta.append({'id':fid,'c':[round(float(center[k]),3) for k in (0,2,1)],
                     'mat':material,'start':startv,'count':tri, 'disp':dispid>=0})
        mn=facepts.min(axis=0)*.0254;mx=facepts.max(axis=0)*.0254
        bboxmin=np.minimum(bboxmin,mn);bboxmax=np.maximum(bboxmax,mx)
    if sys.byteorder!='little':buf.byteswap()
    archive=lump(40).tobytes()
    packed_vmt=packed_vtf=0;tex_types=collections.Counter()
    try:
        pack=zipfile.ZipFile(io.BytesIO(archive))
        ns=pack.namelist();packed_vmt=sum(x.lower().endswith('.vmt') for x in ns)
        vtf=[x for x in ns if x.lower().endswith('.vtf')];packed_vtf=len(vtf)
        tex_types=collections.Counter('cubemap' if '/c-' in x.lower() or '/c' in x.lower().split('/')[-1] else 'other' for x in vtf)
    except Exception:pass
    stats.update({'bsp_version':version,'faces_all':len(faces)//56,'material_names':len(textable),
                  'rendered_faces':len(meta),'triangles':len(buf)//30,'vertices':len(buf)//10,
                  'displacement_records':len(dispinfos)//176,'packed_vmt':packed_vmt,'packed_vtf':packed_vtf})
    return buf.tobytes(),meta,dict(stats),dict(mats.most_common(40))
