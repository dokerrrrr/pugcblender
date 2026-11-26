"""Rasterize Blender geometry into real sampled top/bottom surfaces for panel reconstruction.
Example: python rasterize_geometry.py --mesh geometry.npz --out surface.npz --hull-material 0
"""
from __future__ import annotations
import argparse,numpy as np,numba
from numba import njit
@njit(cache=True)
def raster(verts,faces,mats,xlo,ylo,step,nx,ny,hullmat):
    tall=np.full((ny,nx),-10000.,np.float32);ball=np.full((ny,nx),10000.,np.float32)
    th=np.full((ny,nx),-10000.,np.float32);bh=np.full((ny,nx),10000.,np.float32)
    for f in range(len(faces)):
        a=verts[faces[f,0]];b=verts[faces[f,1]];c=verts[faces[f,2]]
        xa,ya,za=a[0],a[1],a[2];xb,yb,zb=b[0],b[1],b[2];xc,yc,zc=c[0],c[1],c[2]
        den=(xb-xa)*(yc-ya)-(xc-xa)*(yb-ya)
        if abs(den)<.001:continue
        i0=max(0,int(np.floor((min(xa,xb,xc)-xlo)/step)));i1=min(nx-1,int(np.floor((max(xa,xb,xc)-xlo)/step)))
        j0=max(0,int(np.floor((min(ya,yb,yc)-ylo)/step)));j1=min(ny-1,int(np.floor((max(ya,yb,yc)-ylo)/step)))
        for j in range(j0,j1+1):
            yy=ylo+(j+.5)*step
            for i in range(i0,i1+1):
                xx=xlo+(i+.5)*step
                b1=((xx-xa)*(yc-ya)-(xc-xa)*(yy-ya))/den
                b2=((xb-xa)*(yy-ya)-(xx-xa)*(yb-ya))/den
                b0=1-b1-b2
                if min(b0,b1,b2)<-0.00001:continue
                z=za*b0+zb*b1+zc*b2
                if z>tall[j,i]:tall[j,i]=z
                if z<ball[j,i]:ball[j,i]=z
                if mats[f]==hullmat:
                    if z>th[j,i]:th[j,i]=z
                    if z<bh[j,i]:bh[j,i]=z
    return tall,ball,th,bh

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mesh',required=True);ap.add_argument('--out',required=True)
    ap.add_argument('--step',type=float,default=4);ap.add_argument('--hull-material',type=int,default=0)
    a=ap.parse_args();g=np.load(a.mesh);verts=g['verts'];tri=g['triangles'];mi=g['materials']
    xlo=np.floor(verts[:,0].min()/a.step-2)*a.step;ylo=np.floor(verts[:,1].min()/a.step-2)*a.step
    nx=int(np.ceil((verts[:,0].max()-xlo)/a.step))+3;ny=int(np.ceil((verts[:,1].max()-ylo)/a.step))+3
    t,b,th,bh=raster(verts,tri,mi,xlo,ylo,a.step,nx,ny,a.hull_material)
    np.savez_compressed(a.out,top_all=t,bottom_all=b,top_hull=th,bottom_hull=bh,xlo=xlo,ylo=ylo,step=a.step)
    print('RASTER SAVED',a.out,'shape',t.shape,'shell pixels',np.sum(th>-999))
if __name__=='__main__':main()
