#!/usr/bin/env python3
"""Generate numerical fixtures by executing selected Gwyddion 2.71 C functions.

Usage: python scripts/check_gwyddion.py /path/to/gwyddion-2.71 output.json

Requires a C compiler and NumPy. Supply the unmodified official source release;
this script neither downloads nor bundles Gwyddion. Extracted GPL source and the
compiled library exist only in a temporary directory. The small object/API shim
does not emulate the application: the calculation functions themselves come
unchanged from the supplied source. Only finite synthetic arrays, binary masks,
and nearest/linear profiles are supported by this reference harness.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

import numpy as np


FUNCTIONS = {
    "libgwyddion/gwymath-rank.c": [
        "order_3", "kth_rank_simple", "gwy_math_kth_rank", "gwy_math_median",
        "kth_ranks_brute", "kth_ranks_small", "kth_ranks_recurse", "kth_ranks_fastpath",
        "bisect_lower_guint", "gwy_math_kth_ranks", "gwy_math_trimmed_mean",
    ],
    "libgwyddion/gwymath.c": ["gwy_math_choleski_decompose", "gwy_math_choleski_solve"],
    "libprocess/dataline.c": ["gwy_data_line_get_line_coeffs", "gwy_data_line_line_level"],
    "libprocess/correct.c": [
        "gwy_data_field_subtract_row_shifts", "trimmed_mean_or_median",
        "zero_level_row_shifts", "slope_level_row_shifts",
        "gwy_data_field_find_row_shifts_trimmed_mean",
        "gwy_data_field_find_row_shifts_trimmed_diff", "gwy_data_field_row_level_poly",
    ],
    "modules/process/linematch.c": [
        "linematch_do_modus", "linematch_do_match", "row_fit_facet_tilt",
        "untilt_row", "linematch_do_facet_tilt",
    ],
    "libprocess/stats.c": ["gwy_data_field_get_stats"],
    "libprocess/level.c": ["gwy_data_field_fit_plane", "gwy_data_field_area_fit_plane_mask", "gwy_data_field_plane_level"],
    "libprocess/datafield.c": [
        "gwy_data_field_get_dval", "gwy_data_field_get_dval_real", "gwy_data_field_get_profile_mask",
    ],
}


def extract(source: str, name: str) -> str:
    """Extract one definition without editing its contents."""
    pattern = rf"(?m)^(?:static (?:inline )?)?[\w*]+\s*\n{re.escape(name)}\([^;]*?\)\s*\{{"
    match = re.search(pattern, source)
    if not match:
        raise ValueError(f"Cannot locate upstream function {name}")
    # Braces inside comments and strings must not change the nesting level.
    tokens = re.compile(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\{|\}', re.S)
    depth = 1
    for token in tokens.finditer(source, match.end()):
        if token.group() == "{":
            depth += 1
        elif token.group() == "}":
            depth -= 1
            if depth == 0:
                return source[match.start():token.end()]
    raise ValueError(f"Unterminated upstream function {name}")


# Original adapter code, not a replacement for the extracted algorithms.
SHIM = r'''
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <float.h>
#include <assert.h>
typedef double gdouble;
typedef int gint;
typedef unsigned guint;
typedef size_t gsize;
typedef int gboolean;
typedef int GwyMaskingType;
typedef int GwyInterpolationType;
typedef struct { int xres,yres; double xreal,yreal,xoff,yoff; double *data; int cached; double cache; } GwyDataField;
typedef struct { int res; double real,off; double *data; } GwyDataLine;
typedef struct { double x,y; } GwyXY;
#define TRUE 1
#define FALSE 0
#define GWY_MASK_IGNORE 0
#define GWY_MASK_INCLUDE 1
#define GWY_MASK_EXCLUDE 2
#define GWY_INTERPOLATION_NONE 0
#define GWY_INTERPOLATION_ROUND 1
#define GWY_INTERPOLATION_LINEAR 2
#define G_MAXDOUBLE DBL_MAX
#define G_UNLIKELY(x) (x)
#define MAX(a,b) ((a)>(b)?(a):(b))
#define MIN(a,b) ((a)<(b)?(a):(b))
#define CLAMP(x,a,b) MAX((a),MIN((x),(b)))
#define GWY_ROUND(x) ((int)floor((x)+0.5))
#define g_return_if_fail(x) assert(x)
#define g_return_val_if_fail(x,v) assert(x)
#define g_assert_not_reached() abort()
#define GWY_IS_DATA_FIELD(x) ((x)!=NULL)
#define GWY_IS_DATA_LINE(x) ((x)!=NULL)
#define g_new(t,n) ((t*)malloc(sizeof(t)*(n)))
#define g_new0(t,n) ((t*)calloc((n),sizeof(t)))
#define g_newa(t,n) ((t*)alloca(sizeof(t)*(n)))
#define g_free free
#define gwy_assign(d,s,n) memcpy((d),(s),(n)*sizeof(*(d)))
#define gwy_clear(d,n) memset((d),0,(n)*sizeof(*(d)))
#define GWY_FREE(x) do {free(x); (x)=NULL;} while(0)
#define GWY_SWAP(t,a,b) do {t tmp=(a);(a)=(b);(b)=tmp;} while(0)
#define GWY_ORDER(t,a,b) do {if ((a)>(b)) GWY_SWAP(t,a,b);} while(0)
#define DSWAP(a,b) GWY_SWAP(gdouble,a,b)
#define ISWAP(a,b) GWY_SWAP(guint,a,b)
#define SLi(a,i,j) a[(i)*((i)+1)/2+(j)]
#define gwy_debug(...) ((void)0)
#define gwy_omp_chunk_start(n) 0
#define gwy_omp_chunk_end(n) (n)
#define CTEST(f,n) 1
#define CVAL(f,n) ((f)->cache)
#define CBIT(n) 0
static int cmp_double(const void *a,const void *b){double x=*(const double*)a,y=*(const double*)b; return (x>y)-(x<y);}
static int cmp_uint(const void *a,const void *b){unsigned x=*(const unsigned*)a,y=*(const unsigned*)b;return (x>y)-(x<y);}
static void gwy_math_sort(size_t n,double *a){qsort(a,n,sizeof(double),cmp_double);}
static void gwy_guint_sort(size_t n,unsigned *a){qsort(a,n,sizeof(unsigned),cmp_uint);}
static GwyDataLine *gwy_data_line_new(int n,double real,int clear){GwyDataLine *l=calloc(1,sizeof(*l));l->res=n;l->real=real;l->data=calloc(n,sizeof(double));return l;}
static void g_object_unref(GwyDataLine *l){free(l->data);free(l);}
static void gwy_data_line_resample(GwyDataLine*l,int n,int interp){if(l->res!=n){l->data=realloc(l->data,n*sizeof(double));l->res=n;}}
static double *gwy_data_line_get_data(GwyDataLine*l){return l->data;}
static void gwy_data_line_set_val(GwyDataLine*l,int i,double v){l->data[i]=v;}
static void gwy_data_line_clear(GwyDataLine*l){memset(l->data,0,l->res*sizeof(double));}
static double gwy_data_line_get_avg(GwyDataLine*l){double s=0;for(int i=0;i<l->res;i++)s+=l->data[i];return s/l->res;}
static void gwy_data_line_add(GwyDataLine*l,double v){for(int i=0;i<l->res;i++)l->data[i]+=v;}
static int gwy_data_field_get_xres(GwyDataField*f){return f->xres;}
static int gwy_data_field_get_yres(GwyDataField*f){return f->yres;}
static double gwy_data_field_get_dx(GwyDataField*f){return f->xreal/f->xres;}
static double gwy_data_field_rtoj(GwyDataField*f,double x){return x*f->xres/f->xreal;}
static double gwy_data_field_rtoi(GwyDataField*f,double y){return y*f->yres/f->yreal;}
static double *gwy_data_field_get_data(GwyDataField*f){return f->data;}
static const double *gwy_data_field_get_data_const(GwyDataField*f){return f->data;}
static double gwy_data_field_get_avg(GwyDataField*f){double s=0;for(int i=0;i<f->xres*f->yres;i++)s+=f->data[i];return s/(f->xres*f->yres);}
static int _gwy_data_field_check_mask(GwyDataField*f,GwyDataField**m,int*mode){if(!*m||*mode==GWY_MASK_IGNORE){*m=NULL;*mode=GWY_MASK_IGNORE;}return 1;}
static int _gwy_data_field_check_area(GwyDataField*f,int col,int row,int w,int h,int empty){return col>=0&&row>=0&&col+w<=f->xres&&row+h<=f->yres;}
static void gwy_data_field_copy_units_to_data_line(GwyDataField*f,GwyDataLine*l){}
static void gwy_data_field_invalidate(GwyDataField*f){}
static double gwy_data_field_area_get_median_mask(GwyDataField*f,GwyDataField*m,int mode,int x,int y,int w,int h){double *b=malloc(w*h*sizeof(double));int n=0;for(int i=0;i<w*h;i++)if(!m||mode==GWY_MASK_IGNORE||(mode==GWY_MASK_INCLUDE?m->data[i]>0:m->data[i]<1))b[n++]=f->data[i];assert(n);gwy_math_sort(n,b);double med=b[n/2];free(b);return med;}
static double gwy_interpolation_get_dval_of_equidists(double x,double*a,int interp){abort();}
'''

WRAPPERS = r'''
void reference_align(double *data,double *mask,int rows,int cols,int method,int degree,double trim,double pixel_size,double *offsets){
    GwyDataField f={.xres=cols,.yres=rows,.xreal=pixel_size*cols,.yreal=rows,.data=data};
    GwyDataField m=f;m.data=mask;
    GwyDataLine out={.res=rows,.real=rows,.data=offsets};
    int mode=mask?GWY_MASK_INCLUDE:GWY_MASK_IGNORE;
    GwyDataLine *s=NULL;
    if(method==0||method==1||method==5)s=gwy_data_field_find_row_shifts_trimmed_mean(&f,mask?&m:NULL,mode,method==0?0.0:method==1?0.5:trim,0);
    else if(method==2||method==6)s=gwy_data_field_find_row_shifts_trimmed_diff(&f,mask?&m:NULL,mode,method==2?0.5:trim,0);
    else if(method==3)linematch_do_modus(&f,mask?&m:NULL,&out,mode);
    else if(method==4)linematch_do_match(&f,mask?&m:NULL,&out,mode);
    else if(method==7)linematch_do_facet_tilt(&f,mask?&m:NULL,&out,mode);
    else if(method==8)gwy_data_field_row_level_poly(&f,mask?&m:NULL,mode,degree,&out);
    if(s){gwy_data_field_subtract_row_shifts(&f,s);memcpy(offsets,s->data,rows*sizeof(double));g_object_unref(s);}
}
void reference_stats(double *data,int rows,int cols,double*out){
    GwyDataField f={.xres=cols,.yres=rows,.xreal=cols,.yreal=rows,.data=data};
    gwy_data_field_get_stats(&f,out,out+1,out+2,out+3,out+4);
}
void reference_plane(double *data,double *mask,int rows,int cols,double*out){
    GwyDataField f={.xres=cols,.yres=rows,.xreal=cols,.yreal=rows,.data=data};
    GwyDataField m=f;m.data=mask;double a,bx,by;
    if(mask)gwy_data_field_area_fit_plane_mask(&f,&m,GWY_MASK_INCLUDE,0,0,cols,rows,&a,&bx,&by);
    else gwy_data_field_fit_plane(&f,&a,&bx,&by);
    out[0]=a;out[1]=bx;out[2]=by;
    /* Exact pivot supplied by modules/process/level.c, not the fitted intercept. */
    gwy_data_field_plane_level(&f,-0.5*(bx*cols+by*rows),bx,by);
}
int reference_profile(double*data,int rows,int cols,double width,double height,double x0,double y0,double x1,double y1,int res,int thickness,int interp,double*out){
    GwyDataField f={.xres=cols,.yres=rows,.xreal=width,.yreal=height,.data=data};int n=0;
    GwyXY *xy=gwy_data_field_get_profile_mask(&f,&n,NULL,GWY_MASK_IGNORE,x0,y0,x1,y1,res,thickness,interp);
    for(int i=0;i<n;i++){out[2*i]=xy[i].x;out[2*i+1]=xy[i].y;}free(xy);return n;
}
'''


def build(source: Path, directory: Path):
    config = (source / "configure.ac").read_text()
    if "m4_define([gwy_version_major],[2])" not in config or "m4_define([gwy_version_minor],[71])" not in config:
        raise ValueError("This harness is pinned to the official Gwyddion 2.71 source.")
    functions, hashes = [], {}
    for filename, names in FUNCTIONS.items():
        content = (source / filename).read_text()
        hashes[filename] = hashlib.sha256(content.encode()).hexdigest()
        functions.extend(extract(content, name) for name in names)
    prototypes = "\n".join(f[:f.index("{")].strip() + ";" for f in functions)
    cfile = directory / "upstream-reference.c"
    cfile.write_text(SHIM + prototypes + "\n\n".join(functions) + WRAPPERS)
    output = directory / "upstream-reference.so"
    subprocess.run(["cc", "-std=c99", "-O2", "-shared", "-fPIC", str(cfile), "-lm", "-o", str(output)], check=True)
    library = ctypes.CDLL(str(output))
    pointer = np.ctypeslib.ndpointer(dtype=np.float64, flags="C_CONTIGUOUS")
    library.reference_align.argtypes = [pointer, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                       ctypes.c_int, ctypes.c_double, ctypes.c_double, pointer]
    library.reference_stats.argtypes = [pointer, ctypes.c_int, ctypes.c_int, pointer]
    library.gwy_math_median.argtypes = [ctypes.c_size_t, pointer]
    library.gwy_math_median.restype = ctypes.c_double
    library.reference_plane.argtypes = [pointer, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, pointer]
    library.reference_profile.argtypes = [pointer, ctypes.c_int, ctypes.c_int] + [ctypes.c_double]*6 + [ctypes.c_int]*3 + [pointer]
    library.reference_profile.restype = ctypes.c_int
    return library, hashes


def fixtures(library, hashes):
    y, x = np.mgrid[:5, :12]
    data = .4*x + .07*x*x + np.array([3, -2, 4, 1, -3])[:, None] + .2*y*x + .3*np.sin(x+2*y)
    data[1, 8] += 7
    data[3, 2] -= 9
    entries = []
    for method, code in [("mean",0),("median",1),("median_difference",2),("modus",3),
                         ("matching",4),("trimmed_mean",5),("trimmed_difference",6),
                         ("facet_tilt",7),("polynomial",8)]:
        output = data.copy()
        shifts = np.zeros(data.shape[0])
        library.reference_align(output, None, *data.shape, code, 2, .2, 1., shifts)
        entries.append({"method":method,"degree":2,"trim_fraction":.2,"pixel_size":1.,
                        "input":data.tolist(),"output":output.tolist(),"offsets":shifts.tolist()})
    masked=[]
    mask=np.ones(data.shape,dtype=float)
    mask[:,[3,7]]=0
    for method,code in [("mean",0),("median",1),("modus",3),("matching",4),("trimmed_mean",5),("polynomial",8)]:
        output=data.copy()
        shifts=np.zeros(data.shape[0])
        library.reference_align(output,mask.ctypes.data,*data.shape,code,2,.2,1.,shifts)
        masked.append({"method":method,"degree":2,"trim_fraction":.2,"pixel_size":1.,
                       "input":data.tolist(),"mask":mask.astype(bool).tolist(),"output":output.tolist()})
    # Run in metres, then return values to nanometres as the Workbench API does.
    si_output=data.copy()*1e-9
    si_shifts=np.zeros(data.shape[0])
    library.reference_align(si_output,None,*data.shape,4,2,.2,1e-9,si_shifts)
    matching_si={"method":"matching","value_scale":1e-9,"input":data.tolist(),"output":(si_output/1e-9).tolist()}
    planes=[]
    for included in (None,mask):
        output=data.copy()
        coeff=np.zeros(3)
        library.reference_plane(output,None if included is None else included.ctypes.data,*data.shape,coeff)
        planes.append({"input":data.tolist(),"mask":None if included is None else included.astype(bool).tolist(),
                       "coefficients_pixel_coordinates":coeff.tolist(),"output":output.tolist()})
    statdata = np.array([[0.,1.,1.],[4.,9.,10.]])
    stats = np.zeros(5)
    library.reference_stats(statdata,*statdata.shape,stats)
    stat_output=dict(zip(("mean","sa","sq","skewness","excess_kurtosis"),stats.tolist()))
    stat_output["median"]=library.gwy_math_median(statdata.size,statdata.copy())
    profiledata = (np.arange(20,dtype=float).reshape(4,5)**2 % 29).copy()
    profiles=[]
    for thickness in (1,3):
        for interp in (1,2):
            output = np.zeros((7,2))
            n=library.reference_profile(profiledata,4,5,10.,3.,1.,.3,9.,2.7,7,thickness,interp,output)
            profiles.append({"input":profiledata.tolist(),"width_um":10.,"height_um":3.,
                             "start":[.1,.1],"end":[.9,.9],"samples":7,"width":thickness,
                             "interpolation":"nearest" if interp==1 else "linear",
                             "distance_um":output[:n,0].tolist(),"values":output[:n,1].tolist()})
    return {"reference":"Gwyddion 2.71 selected unmodified C functions; standalone adapter, not full application",
            "source_archive_sha256":"2df721befccbe4d5ee2ba564b32e69341f8ce1de637e2045838a09a2d46b5dba",
            "source_file_sha256":hashes,"alignment":entries,"alignment_masked":masked,"matching_si":matching_si,
            "planes":planes,
            "statistics":{"input":statdata.tolist(),"output":stat_output},
            "profiles":profiles}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source",type=Path)
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="afm-gwyddion-reference-") as tmp:
        library,hashes=build(args.source,Path(tmp))
        result=fixtures(library,hashes)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(f"Wrote {args.output}: nine alignment methods, six masked cases, SI Matching, two planes, moments/median and four profiles.")


if __name__=="__main__":
    main()
