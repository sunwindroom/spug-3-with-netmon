import zipfile
import os
import sys

def make_zip(src_dir, dst_zip):
    with zipfile.ZipFile(dst_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(src_dir):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, src_dir)
                rel = rel.replace('\\', '/')
                zf.write(full, rel)
    print(f"Created {dst_zip} ({os.path.getsize(dst_zip)//1024}KB)")

base = r'D:\CDCalabar\spug-3-with-netmon'
make_zip(os.path.join(base, 'spug_api'), os.path.join(base, 'spug_api.zip'))
make_zip(os.path.join(base, 'spug_web'), os.path.join(base, 'spug_web.zip'))
make_zip(os.path.join(base, 'docs', 'docker'), os.path.join(base, 'docker.zip'))