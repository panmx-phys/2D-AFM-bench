#!/usr/bin/env python3
"""Build Gwyddion's real scientific libraries and the Workbench C ABI adapter.

No GTK, Python extension ABI, OpenMP or fake Gwyddion objects are used.
See native/README.md. All downloads are explicit, pinned and checksum-checked.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    'gwyddion': {'version': '2.71', 'filename': 'gwyddion-2.71.tar.xz',
                 'url': 'https://downloads.sourceforge.net/project/gwyddion/gwyddion/2.71/gwyddion-2.71.tar.xz',
                 'sha256': '2df721befccbe4d5ee2ba564b32e69341f8ce1de637e2045838a09a2d46b5dba', 'license': 'GPL-2.0-or-later'},
    'fftw': {'version': '3.3.10', 'filename': 'fftw-3.3.10.tar.gz',
             'url': 'https://www.fftw.org/fftw-3.3.10.tar.gz',
             'sha256': '56c932549852cddcfafdab3820b0200c7742675be92179e59e6215b340e26467', 'license': 'GPL-2.0-or-later'},
}


def run(command, **kwargs):
    return subprocess.run([str(x) for x in command], check=True, **kwargs)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def acquire(name, cache, allow_download):
    spec = SOURCES[name]
    archive = cache / spec['filename']
    if not archive.exists():
        if not allow_download:
            raise RuntimeError(f"Missing {archive}. Supply the pinned archive or pass --download.")
        print(f"Downloading {name} {spec['version']}", flush=True)
        with urllib.request.urlopen(spec['url'], timeout=120) as response, archive.open('wb') as stream:
            shutil.copyfileobj(response, stream)
    if digest(archive) != spec['sha256']:
        raise RuntimeError(f"SHA-256 mismatch: {archive}")
    destination = cache / f"{name}-{spec['version']}"
    if not destination.exists():
        with tarfile.open(archive) as tar:
            tar.extractall(cache, filter='data')
    return destination, archive


def extract_function(source, name):
    pattern = rf'(?m)^(?:static (?:inline )?)?[\w*]+\s*\n{re.escape(name)}\([^;]*?\)\s*\{{'
    match = re.search(pattern, source)
    if not match:
        raise RuntimeError(f"Missing pinned upstream function {name}")
    depth = 1
    for token in re.finditer(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\{|\}', source[match.end():], re.S):
        if token.group() == '{': depth += 1
        if token.group() == '}': depth -= 1
        if depth == 0:
            return source[match.start():match.end()+token.end()]
    raise RuntimeError(f"Unterminated function {name}")


def source_files(source, library):
    makefile = (source / library / 'Makefile.am').read_text()
    variable = 'libgwyddion2_la_SOURCES' if library == 'libgwyddion' else 'libgwyprocess2_la_SOURCES'
    match = re.search(rf'{variable}\s*=\s*(.*?)(?:\n\n|\Z)', makefile, re.S)
    if not match:
        raise RuntimeError('Unrecognized upstream source list')
    return [source / library / name for name in re.findall(r'[a-zA-Z0-9_-]+\.c', match.group(1))]


def library_file(prefix, base):
    paths = [prefix/'lib'/f'lib{base}.dylib', prefix/'lib'/f'lib{base}.so', prefix/'lib'/f'lib{base}.dll.a']
    for path in paths:
        if path.exists(): return path
    candidates = sorted((prefix/'lib').glob(f'lib{base}*.dylib')) + sorted((prefix/'lib').glob(f'lib{base}.so.*'))
    if candidates: return candidates[0]
    raise RuntimeError(f"Cannot find {base} library under {prefix}")


def dependency_flags(args):
    if args.glib_prefix:
        prefix = args.glib_prefix.resolve()
        config = (args.glib_config_dir or prefix/'lib/glib-2.0/include').resolve()
        if not (config/'glibconfig.h').exists():
            raise RuntimeError(f"Missing generated GLib header: {config/'glibconfig.h'}")
        flags = [f'-I{prefix / "include/glib-2.0"}', f'-I{config}']
        libs = [str(library_file(prefix, name)) for name in ('gobject-2.0', 'gthread-2.0', 'glib-2.0')]
        roots = [prefix/'lib']
    else:
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', 'gobject-2.0', 'gthread-2.0'], text=True))
        libs = shlex.split(subprocess.check_output(['pkg-config', '--libs', 'gobject-2.0', 'gthread-2.0'], text=True))
        roots = [Path(token[2:]) for token in libs if token.startswith('-L')]
    if args.fftw_prefix:
        prefix = args.fftw_prefix.resolve()
        flags += [f'-I{prefix/"include"}']
        libs += [str(library_file(prefix, 'fftw3'))]
        roots += [prefix/'lib']
    else:
        flags += shlex.split(subprocess.check_output(['pkg-config', '--cflags', 'fftw3'], text=True))
        ff = shlex.split(subprocess.check_output(['pkg-config', '--libs', 'fftw3'], text=True))
        libs += ff
        roots += [Path(token[2:]) for token in ff if token.startswith('-L')]
    return flags, libs, roots


def write_configuration(generated, cc, system):
    config = ['/* Workbench library-only feature configuration; generated by build_gwyddion.py. */',
              '#define PACKAGE "gwyddion"', '#define PACKAGE_VERSION "2.71"', '#define VERSION "2.71"',
              '#define PACKAGE_URL "https://gwyddion.net/"', '#define GETTEXT_PACKAGE "gwyddion"',
              '#define STDC_HEADERS 1', '#define HAVE_STDBOOL_H 1', '#define HAVE_UNISTD_H 1']
    if system == 'Darwin': config.append('#define _DARWIN_C_SOURCE 1')
    gwy = ['#ifndef __GWY_CONFIG_H__', '#define __GWY_CONFIG_H__',
           '#define GWY_SHARED_LIBRARY_EXTENSION "' + ('dylib' if system == 'Darwin' else 'dll' if system == 'Windows' else 'so') + '"']
    # Test actual compiler/library support; unavailable functions retain upstream fallbacks.
    funcs = ('cbrt', 'hypot', 'asinh', 'acosh', 'atanh', 'erf', 'erfc', 'exp2', 'log2', 'lgamma', 'tgamma',
             'j0', 'j1', 'y0', 'y1', 'log1p', 'expm1', 'isinf', 'isnan')
    for name in funcs:
        invocation = f'{name}(1.0, 2.0)' if name == 'hypot' else f'{name}(1.0)'
        probe = f'#include <math.h>\nint main(void){{volatile double x={invocation};return x==123;}}\n'
        test = subprocess.run([cc, '-std=gnu99', '-Werror=implicit-function-declaration', '-x', 'c', '-', '-lm', '-o', str(generated/'probe')],
                              input=probe, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if test.returncode == 0:
            config.append(f'#define HAVE_{name.upper()} 1')
            gwy.append(f'#define GWY_HAVE_{name.upper()} 1')
    gwy.append('#endif')
    (generated/'config.h').write_text('\n'.join(config)+'\n')
    (generated/'gwyconfig.h').write_text('\n'.join(gwy)+'\n')


def bundle_macos(output, search_roots):
    """Copy only non-system dynamic dependencies; relocate every reference locally."""
    queue = list(output.glob('*.dylib'))
    seen = set()
    while queue:
        library = queue.pop(0)
        if library.name in seen: continue
        seen.add(library.name)
        dependencies = subprocess.check_output(['otool', '-L', str(library)], text=True).splitlines()[1:]
        for line in dependencies:
            reference = line.strip().split(' (', 1)[0]
            if reference.startswith(('/usr/lib/', '/System/Library/')): continue
            name = Path(reference).name
            if name == library.name: continue
            target = output/name
            if not target.exists():
                candidates = ([Path(reference)] if reference.startswith('/') else []) + [root/name for root in search_roots]
                original = next((p for p in candidates if p.exists()), None)
                if original is None:
                    raise RuntimeError(f"Unresolved dependency {reference} in {library}")
                shutil.copy2(original.resolve(), target)
                target.chmod(target.stat().st_mode | 0o200)
                queue.append(target)
            run(['install_name_tool', '-change', reference, f'@loader_path/{name}', library], stdout=subprocess.DEVNULL)
        run(['install_name_tool', '-id', f'@loader_path/{library.name}', library], stdout=subprocess.DEVNULL)
    # Relocation invalidates signatures. Ad-hoc signing is for local loading only.
    for library in output.glob('*.dylib'):
        run(['codesign', '--force', '--sign', '-', library], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, help='Existing pristine Gwyddion 2.71 source tree')
    parser.add_argument('--build-dir', type=Path, default=ROOT/'.test-artifacts/native')
    parser.add_argument('--output', type=Path, default=ROOT/'afm_workbench/_native')
    parser.add_argument('--source-bundle', type=Path, help='Corresponding-source directory (default OUTPUT/sources)')
    parser.add_argument('--dependency-manifest', type=Path, help='Exact dependency package/source records; see native/README.md')
    parser.add_argument('--dependency-cache', type=Path, default=ROOT/'.test-artifacts/native/dependency-packages')
    parser.add_argument('--zstd', default='zstd', help='Decompressor for conda package metadata, only with --dependency-manifest')
    parser.add_argument('--glib-prefix', type=Path)
    parser.add_argument('--glib-config-dir', type=Path)
    parser.add_argument('--fftw-prefix', type=Path)
    parser.add_argument('--build-fftw', action='store_true', help='Build pinned FFTW into build directory')
    parser.add_argument('--download', action='store_true', help='Download missing checksum-pinned source archives')
    parser.add_argument('--libraries-only', action='store_true', help='Build libraries before the C adapter is available')
    parser.add_argument('--jobs', type=int, default=min(8, os.cpu_count() or 2))
    parser.add_argument('--cc', default=os.environ.get('CC', 'cc'))
    args = parser.parse_args()
    system = platform.system()
    if system not in {'Darwin', 'Linux', 'Windows'}:
        raise RuntimeError('Use a POSIX or MinGW-w64 C compiler.')
    build, output = args.build_dir.resolve(), args.output.resolve()
    cache, generated, objects = build/'sources', build/'generated', build/'objects'
    for directory in (build, output, cache, generated, objects): directory.mkdir(parents=True, exist_ok=True)
    archives = {}
    if args.source:
        source = args.source.resolve()
        archive = cache/SOURCES['gwyddion']['filename']
        if archive.exists() and digest(archive)==SOURCES['gwyddion']['sha256']: archives['gwyddion']=archive
    else:
        source, archives['gwyddion'] = acquire('gwyddion',cache,args.download)
    config_text = (source/'configure.ac').read_text()
    if 'm4_define([gwy_version_minor],[71])' not in config_text or 'm4_define([gwy_version_major],[2])' not in config_text:
        raise RuntimeError('Only Gwyddion 2.71 is supported by this adapter.')
    if args.build_fftw:
        fftw, archives['fftw'] = acquire('fftw',cache,args.download)
        args.fftw_prefix=build/'fftw'
        if not (args.fftw_prefix/'include/fftw3.h').exists():
            with (build/'fftw-build.log').open('w') as log:
                run([fftw/'configure',f'--prefix={args.fftw_prefix}','--enable-shared','--disable-static','--disable-fortran','--disable-doc'],cwd=fftw,stdout=log,stderr=subprocess.STDOUT)
                run(['make',f'-j{args.jobs}'],cwd=fftw,stdout=log,stderr=subprocess.STDOUT)
                run(['make','install'],cwd=fftw,stdout=log,stderr=subprocess.STDOUT)
    depflags, deplibs, roots = dependency_flags(args)
    write_configuration(generated,args.cc,system)
    linematch=(source/'modules/process/linematch.c').read_text()
    names=('zero_level_row_shifts','linematch_do_modus','linematch_do_match','row_fit_facet_tilt','untilt_row','linematch_do_facet_tilt')
    funcs=[extract_function(linematch,name) for name in names]
    prototypes='\n'.join(f[:f.index('{')].strip()+';' for f in funcs)
    (generated/'gwyddion_linematch.inc').write_text(linematch[:linematch.index('*/')+2]+'\n#include <libgwyddion/gwyomp.h>\n'+prototypes+'\n'+'\n\n'.join(funcs)+'\n')
    cflags=['-std=gnu99','-O2','-fPIC','-Wno-deprecated-declarations','-Wno-incompatible-pointer-types-discards-qualifiers',f'-I{generated}',f'-I{source}',*depflags]
    suffix = '.dylib' if system=='Darwin' else '.dll' if system=='Windows' else '.so'
    header_key=hashlib.sha256(''.join(digest(p) for folder in ('libgwyddion','libprocess') for p in sorted((source/folder).glob('*.h'))).encode()).hexdigest()
    compiler_version=subprocess.check_output([args.cc,'--version'],text=True).splitlines()[0]
    def compile_file(path):
        dest=objects/(path.parent.name+'_'+path.stem+'.o')
        # Header/source changes invalidate the small compile cache through a command+content hash.
        key=hashlib.sha256((' '.join(cflags)+digest(path)+header_key+compiler_version+platform.machine()+digest(generated/'config.h')+digest(generated/'gwyconfig.h')).encode()).hexdigest()
        stamp=dest.with_suffix('.sha256')
        if not dest.exists() or not stamp.exists() or stamp.read_text()!=key:
            completed=subprocess.run([args.cc,*cflags,'-c',str(path),'-o',str(dest)],capture_output=True,text=True)
            if completed.returncode:
                raise RuntimeError(f"Compile failed: {path}\n{completed.stderr}")
            stamp.write_text(key)
        return dest
    def link(name, inputs, libraries):
        dest=output/(name+suffix)
        flags=['-dynamiclib','-Wl,-install_name,@rpath/'+dest.name,'-Wl,-rpath,@loader_path'] if system=='Darwin' else ['-shared','-Wl,-soname,'+dest.name,'-Wl,-rpath,$ORIGIN'] if system=='Linux' else ['-shared','-Wl,--export-all-symbols']
        run([args.cc,*flags,*inputs,*libraries,'-lm',*(['-framework','CoreFoundation'] if system=='Darwin' else []),'-o',dest])
        return dest
    built=[]
    for library,name in [('libgwyddion','libgwyddion2'),('libprocess','libgwyprocess2')]:
        files=source_files(source,library)
        print(f'Compiling {name}: {len(files)} upstream C files',flush=True)
        with ThreadPoolExecutor(max_workers=max(1,args.jobs)) as pool:
            compiled=list(pool.map(compile_file,files))
        built.append(link(name,compiled,[*built,*deplibs]))
    if not args.libraries_only:
        adapter=ROOT/'native/afm_gwyddion.c'
        if not adapter.exists(): raise RuntimeError('Missing native/afm_gwyddion.c; use --libraries-only to prepare dependencies.')
        obj=objects/'afm_gwyddion.o'
        run([args.cc,*cflags,f'-I{ROOT/"native"}','-c',adapter,'-o',obj])
        link('libafm_gwyddion' if system!='Windows' else 'afm_gwyddion',[obj],[*built,*deplibs])
    if system=='Darwin': bundle_macos(output,[output,*roots])
    elif system=='Linux' and args.fftw_prefix:
        # Keep the FFTW SONAME aliases beside the native bridge when FFTW was built locally.
        for path in (args.fftw_prefix.resolve()/'lib').glob('libfftw3.so*'):
            shutil.copy2(path.resolve(),output/path.name)
    licenses=output/'licenses'; licenses.mkdir(exist_ok=True)
    shutil.copy2(source/'COPYING',licenses/'Gwyddion-COPYING')
    if args.fftw_prefix:
        candidates=[build/'sources/fftw-3.3.10/COPYING',build/'deps/fftw-3.3.10/COPYING']
        for path in candidates:
            if path.exists(): shutil.copy2(path,licenses/'FFTW-COPYING');break
    corresponding=(args.source_bundle or output/'sources').resolve(); corresponding.mkdir(parents=True,exist_ok=True)
    for name,spec in SOURCES.items():
        existing=cache/spec['filename']
        if existing.exists() and digest(existing)==spec['sha256']:
            archives[name]=existing
    for name,archive in archives.items(): shutil.copy2(archive,corresponding/archive.name)
    if args.dependency_manifest:
        from collect_native_sources import collect
        collect(args.dependency_manifest.resolve(),args.dependency_cache.resolve(),corresponding,licenses,args.zstd,args.download)
    manifest={'schema':'afm-workbench.native-build.v1','gwyddion':'2.71','adapter_abi':1,'platform':system,'machine':platform.machine(),
              'compiler':compiler_version,
              'upstream_sources':SOURCES,'openmp':False,'gtk_runtime':False,'libraries_only':args.libraries_only,
              'configuration':{'config.h':(generated/'config.h').read_text(),'gwyconfig.h':(generated/'gwyconfig.h').read_text()},
              'upstream_file_sha256':{str(p.relative_to(source)):digest(p) for folder in ('libgwyddion','libprocess') for p in source_files(source,folder)},
              'linematch_sha256':hashlib.sha256(linematch.encode()).hexdigest(),
              'binary_sha256':{p.name:digest(p) for p in output.glob('*'+suffix)}}
    (output/'build-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    shutil.copy2(output/'build-manifest.json',corresponding/'native-build-manifest.json')
    adapter_sources=corresponding/'workbench-native'; adapter_sources.mkdir(exist_ok=True)
    for path in (ROOT/'native/afm_gwyddion.c',ROOT/'native/afm_gwyddion.h',Path(__file__),ROOT/'scripts/collect_native_sources.py'):
        if path.exists():shutil.copy2(path,adapter_sources/path.name)
    if (ROOT/'LICENSE').exists():shutil.copy2(ROOT/'LICENSE',adapter_sources/'LICENSE')
    print(f'Built native scientific libraries in {output}',flush=True)


if __name__=='__main__':
    main()
