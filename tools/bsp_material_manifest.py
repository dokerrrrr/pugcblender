#!/usr/bin/env python3
"""List Source BSP packed VMT/VTF references and missing diffuse texture assets."""
import re,struct,json,csv,zipfile,io,pathlib,collections,argparse

def run(bsp,out):
 b=pathlib.Path(bsp).read_bytes();assert b[:4]==b'VBSP'
 off,length,vers,fourcc=struct.unpack_from('<4i',b,8+16*40)
 z=zipfile.ZipFile(io.BytesIO(b[off:off+length]));paths=z.namelist()
 have={x.lower() for x in paths};rows=[];missing=collections.Counter()
 for path in paths:
  if not path.lower().endswith('.vmt'):continue
  src=z.read(path).decode('utf8','replace')
  tex=re.findall(r'["\']?\$(basetexture|bumpmap|detail|envmapmask|normalmap)["\']?\s+["\']([^"\'\r\n]+)["\']',src,re.I)
  if not tex:
   tex=re.findall(r'\$(basetexture|bumpmap|detail|envmapmask|normalmap)\s+([^\s{}]+)',src,re.I)
  inc=re.search(r'[\"\']?include[\"\']?\s+[\"\']([^\"\'\r\n]+)[\"\']',src,re.I)
  if inc:
   ref=inc.group(1).strip().replace('\\','/').lower();rows.append({'vmt':path,'slot':'include_vmt','referenced_vtf':ref,'packed_in_bsp':ref in have});
   if ref not in have:missing['inherited_vmt']+=1
  for usage,value in tex:
   rel=value.strip().strip('"').replace('\\','/').lower();expect=f'materials/{rel}.vtf'
   ispack=expect in have
   if not ispack:missing[usage.lower()]+=1
   rows.append({'vmt':path,'slot':usage.lower(),'referenced_vtf':expect,'packed_in_bsp':ispack})
 p=pathlib.Path(out);p.write_text(json.dumps({'packed_vmt':sum(x.endswith('.vmt') for x in paths),'packed_vtf':sum(x.endswith('.vtf') for x in paths),'texture_references':rows,'missing_refs_by_slot':dict(missing)},ensure_ascii=False,indent=2))
 with open(p.with_suffix('.csv'),'w',newline='',encoding='utf8') as f:
  w=csv.DictWriter(f,fieldnames=['vmt','slot','referenced_vtf','packed_in_bsp']);w.writeheader();w.writerows(rows)
 print('Wrote',p,'refs',len(rows),'missing',sum(missing.values()))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('bsp');a.add_argument('out');x=a.parse_args();run(x.bsp,x.out)
