#!/usr/bin/env python3
"""Prepare compact local sources for the Blender Overpass Geometry Lab.

Uses only local files. Produces source triangles as compressed NPZ, scene placement JSON,
and a filtered UGC mesh zip with real mesh data (no textures invented).
"""
import argparse,json,pathlib,sys,zipfile
import numpy as np
HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from pugc_vmf_lab import build_vmf_geometry, decode_pugc, vmf_solids
from source_bsp import parse_bsp


def source_layers(bsp_path, vmf_path, reference):
    bsp, bsp_stats = b"", {}
    if bsp_path:
        bsp, _, bsp_stats, _ = parse_bsp(bsp_path)
    vmf, vmf_stats = b"", {}
    if vmf_path:
        vmf, _, vmf_stats = build_vmf_geometry(vmf_solids(vmf_path))
    info = {
        "origin": {"bsp": bsp_path.name if bsp_path else "", "vmf": vmf_path.name if vmf_path else "",
                   "pugc": reference.name},
        "bsp": {"stats": bsp_stats},
        "vmf": {"stats": vmf_stats},
    }
    return info, np.frombuffer(bsp, dtype="<f4").reshape(-1, 10), np.frombuffer(vmf, dtype="<f4").reshape(-1, 10)

def read_props(p):
    data=decode_pugc(p)
    out=[]; skipped=0
    for idx,o in enumerate(data.get('objects') or data.get('modObjects') or []):
        if o.get('deviceIndex',-1)!=-1:
            skipped+=1;continue
        tr=o.get('spawnTransform',{})
        t=tr.get('translation',{});q=tr.get('rotation',{});s=tr.get('scale3D',{})
        if any(a not in t or a not in s or a not in q for a in 'xyz') or 'w' not in q:continue
        out.append({'id':int(o['objectId']),'index':idx,'t':t,'q':q,'s':s})
    return {'name':pathlib.Path(p).name,'props':out,'device_count_excluded':skipped}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--bsp', type=pathlib.Path, help='Compiled Source BSP')
    ap.add_argument('--vmf', type=pathlib.Path, help='Source VMF brush geometry')
    ap.add_argument('--html', help='Archived file with embedded BSP/VMF data')
    ap.add_argument('--reference',type=pathlib.Path,required=True,help='Reference .pugc')
    ap.add_argument('--generated',help='Optional generated .pugc')
    ap.add_argument('--mesh-zip',required=True,help='Zip containing bp-mesh/*.bin.gz')
    ap.add_argument('--out',required=True,help='Output directory')
    a=ap.parse_args()
    if bool(a.html) == bool(a.bsp or a.vmf):
        ap.error('provide --bsp and/or --vmf, or --html for archived data')
    if a.html:
        from export_geometry_glb import extract

        info, bsp, vmf = extract(a.html)
    else:
        info, bsp, vmf = source_layers(a.bsp, a.vmf, a.reference)
    out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(out/'overpass_source_surfaces.npz',bsp=bsp,vmf=vmf)
    teacher=read_props(a.reference)
    generated=read_props(a.generated) if a.generated else None
    ids=sorted({o['id'] for o in teacher['props']} | ({o['id'] for o in generated['props']} if generated else set()))
    with zipfile.ZipFile(a.mesh_zip) as zin,zipfile.ZipFile(out/'overpass_ugc_meshes.zip','w',compression=zipfile.ZIP_STORED) as zout:
        missing=[]
        for id in ids:
            for ext in ['bin.gz','json']:
                filename=f'bp-mesh/{id}.{ext}'
                try: data=zin.read(filename)
                except KeyError:missing.append(filename);continue
                zout.writestr(filename,data)
    if missing:raise RuntimeError('Missing UGC meshes: '+', '.join(missing[:25]))
    manifest={'source':info['origin'],'bsp':info['bsp']['stats'],'vmf':info['vmf']['stats'],
              'reference':teacher,'generated':generated,
              'asset_ids':ids,'alignment':{'source_axis_convention':'Source X Y Z (inches) -> (X, Y, Z) meters',
              'source_flip_x':True,'translation_meters_blender_xyz':[325.28,475.59,56.92],
              'notice':'Initial manually inferred alignment, NOT verified exact registration'},
              'limit':3000,'units':'meters'}
    (out/'overpass_lab_inputs.json').write_text(json.dumps(manifest,ensure_ascii=False,separators=(',',':')),encoding='utf8')
    print(json.dumps({'bsp_triangles':len(bsp)//3,'vmf_triangles':len(vmf)//3,
      'reference_props':len(teacher['props']),'generated_props':len(generated['props']) if generated else 0,
      'asset_types':len(ids),'mesh_zip_MB':round((out/'overpass_ugc_meshes.zip').stat().st_size/1e6,2)},indent=2))

if __name__=='__main__':main()
