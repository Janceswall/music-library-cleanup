#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段2：全库音频元数据索引（参数化版）
用法: python3 build_index.py <音乐库路径> [输出目录]
  默认输出目录为当前目录。
用 ffprobe 读取每个音频文件的标签与编码信息，输出 index.jsonl + index_errors.jsonl。
"""
import os, sys, json, subprocess, time

def usage():
    print("用法: python3 build_index.py <音乐库路径> [输出目录]")
    sys.exit(1)

if len(sys.argv) < 2:
    usage()

ROOT = sys.argv[1].rstrip('/')
OUTDIR = sys.argv[2] if len(sys.argv) > 2 else '.'
OUT = os.path.join(OUTDIR, 'index.jsonl')
ERR = os.path.join(OUTDIR, 'index_errors.jsonl')

AUDIO_EXT = {'.flac', '.ape', '.mp3', '.wav', '.dsf', '.dff', '.m4a',
             '.aac', '.ogg', '.wma', '.opus', '.alac', '.mka'}

def probe(abspath):
    cmd = ['ffprobe', '-v', 'error', '-show_format', '-show_streams',
           '-of', 'json', abspath]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                       timeout=20)
    if p.returncode != 0:
        return None
    return json.loads(p.stdout.decode('utf-8', 'replace'))

def pick(d, *keys):
    """从 tags dict 按大小写不敏感取第一个存在的值"""
    if not isinstance(d, dict):
        return ''
    low = {kk.lower(): vv for kk, vv in d.items()}
    for k in keys:
        if k.lower() in low:
            return low[k.lower()]
    return ''

def main():
    total = audio = tagless = failed = 0
    t0 = time.time()
    os.makedirs(OUTDIR, exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as fout, \
         open(ERR, 'w', encoding='utf-8') as ferr:
        for dirpath, dirnames, filenames in os.walk(ROOT):
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                if ext not in AUDIO_EXT:
                    continue
                abspath = os.path.join(dirpath, fn)
                relpath = os.path.relpath(abspath, ROOT)
                audio += 1
                try:
                    st = os.stat(abspath)
                    data = probe(abspath)
                except Exception as e:
                    failed += 1
                    ferr.write(json.dumps({'path': relpath, 'error': str(e)},
                                          ensure_ascii=False) + '\n')
                    continue
                rec = {'path': relpath, 'size': st.st_size, 'mtime': st.st_mtime}
                if data is None:
                    rec['probe_error'] = True
                    failed += 1
                else:
                    fmt = data.get('format', {})
                    tags = fmt.get('tags', {}) or {}
                    # 大小写不敏感取 artist/title/album/date
                    rec['artist'] = pick(tags, 'artist', 'album_artist')
                    rec['title'] = pick(tags, 'title')
                    rec['album'] = pick(tags, 'album')
                    rec['date'] = pick(tags, 'date', 'year')
                    rec['duration'] = fmt.get('duration', '')
                    rec['bit_rate'] = fmt.get('bit_rate', '')
                    if not rec['artist'] and not rec['title']:
                        tagless += 1
                    streams = data.get('streams', []) or []
                    astream = next((s for s in streams if s.get('codec_type') == 'audio'), None)
                    if astream:
                        rec['codec'] = astream.get('codec_name', '')
                        rec['sample_rate'] = astream.get('sample_rate', '')
                        rec['bits'] = astream.get('bits_per_raw_sample') or astream.get('bits_per_sample') or ''
                        rec['channels'] = astream.get('channels', '')
                fout.write(json.dumps(rec, ensure_ascii=False) + '\n')
                fout.flush()
                if audio % 500 == 0:
                    print(f"[{time.time()-t0:6.0f}s] 已处理 {audio}, 失败 {failed}, 无标签 {tagless}", flush=True)
    print(f"DONE total_audio={audio} failed={failed} tagless={tagless} elapsed={time.time()-t0:.0f}s", flush=True)

if __name__ == '__main__':
    main()
