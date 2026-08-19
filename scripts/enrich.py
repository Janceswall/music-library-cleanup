#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段3：标签补齐（参数化版）
用法: python3 enrich.py <音乐库路径> [输出目录]
对无标签/标签垃圾的音频，从「文件名 + 目录层级」解析 歌手/歌名/专辑。
输入 <输出目录>/index.jsonl，输出 index_enriched.jsonl（含 artist_f/title_f/album_f/src）。
"""
import json, re, unicodedata, os, sys

if len(sys.argv) < 2:
    print("用法: python3 enrich.py <音乐库路径> [输出目录]"); sys.exit(1)

ROOT = sys.argv[1].rstrip('/')
OUTDIR = sys.argv[2] if len(sys.argv) > 2 else '.'
IN = os.path.join(OUTDIR, 'index.jsonl')
OUT = os.path.join(OUTDIR, 'index_enriched.jsonl')

def nfkc(s):
    return unicodedata.normalize('NFKC', s or '')

def clean_str(s):
    return nfkc(s).strip()

JUNK_PATTERNS = [
    r'\.旺旺[：:].*$',          # .旺旺：pciks
    r'[（(]\s*\d+\s*[)）]$',    # (2) (3)
    r'[【\[]无损[】\]]$',
    r'\.\d+$',                   # .2 .3
]
def strip_junk(s):
    for p in JUNK_PATTERNS:
        s = re.sub(p, '', s)
    return s.strip(' ._~-')

VERSION_MARKERS = re.compile(
    r'(live|remaster|remix|demo|acoustic|instrumental|karaoke|混音|重制|现场|演唱会|'
    r'伴奏|演奏|纯音乐|版|Remastered|KTV|伴奏版|消音)', re.IGNORECASE)

def split_artist_title(stem, hint=None):
    """返回 (artist, title, reversed)。hint 为目录推断的歌手名，用于校验易误判分隔符。"""
    for sep in [' - ', '－', ' — ', ' – ']:
        if sep in stem:
            parts = stem.split(sep, 1)
            a, t = parts[0].strip(), parts[1].strip()
            if a and t:
                return a, t, False
    m = re.match(r'^(\d{1,3})\s*[-－—]\s*(.+?)\s*[-－—]\s*(.+)$', stem)
    if m and m.group(2) and m.group(3):
        return m.group(3), m.group(2), True
    m = re.match(r'^(.+?)[（(]([^（）()]{1,30})[)）]$', stem)
    if m:
        return m.group(2), m.group(1), False
    if hint:
        h = nfkc(hint).strip()
        for sep in ['.', '．', '-', '－', '—', '_']:
            idx = stem.find(sep)
            if idx > 0:
                left = nfkc(stem[:idx]).strip()
                right = stem[idx+1:].strip()
                if left and right and left == h:
                    return left, right, False
    return None, stem, False

def strip_tracknum(t):
    return re.sub(r'^\s*\d{1,3}\s*[.、．\s-]+', '', t).strip()

def path_singer_album(relpath):
    """推断歌手/专辑。约定目录结构为 <根>/歌手/专辑/... ，也兼容 .trash 等前缀。"""
    parts = relpath.split('/')
    singer = album = ''
    # 找到"歌手/专辑"层级：取深层目录中非音频文件的倒数两层作为候选
    # 优先识别"未知专辑"等标记
    for i, p in enumerate(parts):
        if p in ('未知专辑', 'Unknown', 'unknown'):
            if i >= 1:
                singer = parts[i-1]
            continue
    if not singer:
        # 取路径倒数第二层作为歌手（若倒数第一层是文件名）
        if len(parts) >= 3:
            singer = parts[-2]
            album = ''
    singer = re.sub(r'\s*(ape|flac|dsd|sacd|无损).*$', '', singer, flags=re.I).strip()
    album = nfkc(album).strip()
    if album in ('未知专辑', 'Unknown', ''):
        album = ''
    return singer, album

WATERMARK = re.compile(
    r'(論壇|论坛|音樂論壇|音乐论坛|捌零|收藏|分享|賴子|赖子|残阳|聚智|'
    r'www\.|http|\.com|\.cn|\.net|bbs|pt80|zyt8|ape520|ape愛好者|ape爱好者|'
    r'下載|下载|壓縮|压缩|精品論壇)', re.IGNORECASE)

def tag_is_garbage(s):
    return bool(WATERMARK.search(s or ''))

def filename_artist_title(relpath):
    bn = os.path.splitext(os.path.basename(relpath))[0]
    bn = strip_junk(bn)
    hint, _ = path_singer_album(relpath)
    a, t, _ = split_artist_title(bn, hint=hint)
    return a, t

def main():
    total = enriched = 0
    with open(IN, encoding='utf-8') as fin, open(OUT, 'w', encoding='utf-8') as fout:
        for line in fin:
            r = json.loads(line)
            total += 1
            artist = clean_str(r.get('artist') or '')
            title = clean_str(r.get('title') or '')
            album = clean_str(r.get('album') or '')
            src = 'tag'
            if artist or title:
                if tag_is_garbage(title) or tag_is_garbage(artist):
                    a2, t2 = filename_artist_title(r['path'])
                    if a2 and t2:
                        artist, title = clean_str(a2), clean_str(t2)
                        src = 'tag-polluted->name'
                    else:
                        if tag_is_garbage(title):
                            title = ''
                        if tag_is_garbage(artist):
                            singer_dir, _ = path_singer_album(r['path'])
                            artist = singer_dir if singer_dir else ''
                        src = 'tag-polluted'
                elif not artist or not title:
                    a2, t2, _ = split_artist_title(os.path.splitext(os.path.basename(r['path']))[0])
                    artist = artist or (a2 or '')
                    title = title or (t2 or '')
                    if a2 or t2:
                        src = 'tag+name'
            else:
                bn = os.path.splitext(os.path.basename(r['path']))[0]
                bn = strip_junk(bn)
                singer_dir, album_dir = path_singer_album(r['path'])
                a, t, _ = split_artist_title(bn, hint=singer_dir)
                if a and t:
                    artist, title = clean_str(a), clean_str(t)
                    src = 'filename'
                else:
                    t = strip_tracknum(bn)
                    title = clean_str(t) if t and 'Track' not in t else ''
                    artist = singer_dir
                    src = 'dir'
                if not album:
                    album = album_dir
                if not artist:
                    artist = singer_dir
            r['artist_f'] = artist
            r['title_f'] = title
            r['album_f'] = album
            r['src'] = src
            r['version_like'] = bool(artist and title and VERSION_MARKERS.search(title))
            fout.write(json.dumps(r, ensure_ascii=False) + '\n')
            enriched += 1
    print(f"DONE total={total} enriched={enriched}")

if __name__ == '__main__':
    main()
