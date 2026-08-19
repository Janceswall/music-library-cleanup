#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按 {歌曲文件名: 专辑名} 映射执行归位（只移动，不删除）（参数化版）
用法: python3 apply_album_mapping.py <歌手目录路径> <mapping.json>
  <歌手目录路径> 指"直接包含各歌手文件夹"的那一层目录（例如 /volume1/Music，
  或 /volume1/Music/我的收藏 —— 若歌都包在一个总目录里，就传那个总目录）。
  mapping.json 两种格式均支持：
    a) 扁平: {"歌手 - 歌名.ape": "专辑名", ...}（从文件名自动提取歌手）
    b) 嵌套: {"歌手名": {"歌曲文件名": "专辑名", ...}}
专辑名 "待确认"/"单曲" 不移动（保持原位）。日志写 album_assign_log.tsv。
"""
import os, re, sys, json

def usage():
    print("用法: python3 apply_album_mapping.py <歌手目录路径> <mapping.json>")
    sys.exit(1)

if len(sys.argv) < 3:
    usage()

ROOT = sys.argv[1].rstrip('/')
MAPPING_FILE = sys.argv[2]
SCAN = os.path.dirname(os.path.abspath(__file__))

def clean(name):
    name = (name or '').strip()
    name = re.sub(r'[\\/:*?"<>|]', ' ', name)
    name = re.sub(r'\s+', ' ', name)
    name = re.sub(r'^[《「]|[》」]$', '', name)
    return name.strip('. ')

def singer_from_fn(fn):
    stem = os.path.splitext(fn)[0]
    stem = re.sub(r'^\d{1,3}[\s.\-]+', '', stem)
    m = re.match(r'^(.+?)\s*[-－—]\s*(.+)$', stem)
    return m.group(1).strip() if m else None

def find_singer_dir(singer):
    base = ROOT  # ROOT 即歌手目录层
    if os.path.isdir(os.path.join(base, singer)):
        return os.path.join(base, singer)
    for s in os.listdir(base):
        if s.replace(' ', '') == singer.replace(' ', ''):
            return os.path.join(base, s)
    return None

def apply_flat(mapping, log):
    moved = skip = notfound = 0
    for fn, album in mapping.items():
        a = clean(album) if isinstance(album, str) else ''
        if a in ('待确认', '单曲', ''):
            skip += 1
            continue
        singer = singer_from_fn(fn)
        if not singer:
            skip += 1
            continue
        sdir = find_singer_dir(singer)
        if not sdir:
            notfound += 1
            continue
        src = os.path.join(sdir, fn)
        if not os.path.exists(src):
            fnd = None
            for dp, _, fns in os.walk(sdir):
                if fn in fns:
                    fnd = os.path.join(dp, fn)
                    break
            src = fnd
        if not src or not os.path.exists(src):
            skip += 1
            continue
        dst_dir = os.path.join(sdir, a)
        if os.path.abspath(src).startswith(os.path.abspath(dst_dir)):
            skip += 1
            continue
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, fn)
        if os.path.exists(dst):
            b, e = os.path.splitext(fn)
            j = 2
            while os.path.exists(os.path.join(dst_dir, f"{b}_{j}{e}")):
                j += 1
            dst = os.path.join(dst_dir, f"{b}_{j}{e}")
        os.rename(src, dst)
        log.write(f"{os.path.relpath(src, ROOT)}\t{os.path.relpath(dst, ROOT)}\tmoved\n")
        moved += 1
    return moved, skip, notfound

def main():
    mapping = json.load(open(MAPPING_FILE, encoding='utf-8'))
    log = open(os.path.join(SCAN, 'album_assign_log.tsv'), 'a', encoding='utf-8')
    if not log.tell():
        log.write('src\tdst\taction\n')
    moved = skip = notfound = 0
    # 判断嵌套 or 扁平
    first_val = next(iter(mapping.values()), None)
    if isinstance(first_val, dict):
        # 嵌套 {歌手: {文件: 专辑}}
        for singer, songs in mapping.items():
            m, s, n = apply_flat(songs, log)
            moved += m; skip += s; notfound += n
    else:
        m, s, n = apply_flat(mapping, log)
        moved += m; skip += s; notfound += n
    log.close()
    print(f"归位完成: 移动 {moved}, 跳过(待确认/单曲/已就位) {skip}, 未找到歌手目录 {notfound}")

if __name__ == '__main__':
    main()
