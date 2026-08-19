#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段5：归类命名计划（干跑，不移动文件）（参数化版）
用法: python3 build_rename_plan.py [输出目录]
  输入 <输出目录>/index_enriched.jsonl，输出 rename_plan.tsv（before→after，action 列）。

只做「无歧义、高价值」的规范化：
  1) 「未知专辑」目录 + 有真实 album 标签 → 归到 歌手/真实专辑/
  2) 文件名最小清理（去垃圾后缀、全角转半角、统一分隔）——【在原始文件名上改，绝不重建，绝不丢 Live/序号/版本标注】
"""
import json, re, os, sys, unicodedata

OUTDIR = sys.argv[1] if len(sys.argv) > 1 else '.'
IN = f"{OUTDIR}/index_enriched.jsonl"
OUT = f"{OUTDIR}/rename_plan.tsv"

def nfkc(s): return unicodedata.normalize('NFKC', s or '')

def strip_tracknum_fname(stem):
    m = re.match(r'^(\d{1,3})\s*[.、．\s\-_]+(.*)$', stem)
    return (m.group(1), m.group(2)) if m else (None, stem)

def normalize_fname(bn):
    """在原始文件名上做最小、可逆的清理，绝不丢失 Live/序号/原唱等信息。"""
    stem, ext = os.path.splitext(bn)
    ext = ext.lower()
    s = nfkc(stem)
    s = re.sub(r'\.旺旺[：:].*$', '', s)                    # 去 .旺旺：xxx
    s = re.sub(r'[（(]\s*(\d+)\s*[)）](?=\s*$)', r'(\1)', s)  # 全角括号数字转半角
    s = re.sub(r'\(\d+\)$', '', s)                          # 去纯数字重复标记 (2)(3)
    s = s.strip(' ._~-')
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'(?<=[^\s])-(?=[^\s])', ' - ', s)            # 无空格连字符加空格
    s = re.sub(r'\s*[∕]\s*', ',', s)                         # 分隔多歌手统一为 ,
    return s + ext

def main():
    recs = [json.loads(l) for l in open(IN, encoding='utf-8')]
    stats = {'album_move':0, 'rename':0, 'keep':0}
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('action\tbefore\tafter\n')
        for r in recs:
            if r.get('unresolved'):
                continue
            p = r['path']
            parts = p.split('/')
            bn = parts[-1]
            stem, ext = os.path.splitext(bn)
            dirparts = parts[:-1]

            # 1) 未知专辑落地
            album_f = nfkc(r.get('album_f') or '').strip()
            album_f = re.sub(r'^[（(]?\d{2,4}[)）]?[.\s\-_]+', '', album_f)
            album_f = re.sub(r'(FLAC|APE|DSD|SACD|无损|CUE)\s*\+?\s*CUE$', '', album_f, flags=re.I).strip(' ._-')
            new_dir = list(dirparts)
            album_moved = False
            has_unk = any(x in ('未知专辑','Unknown','unknown') for x in dirparts)
            if has_unk and album_f and album_f not in ('未知专辑','未知',''):
                new_dir = [album_f if x in ('未知专辑','Unknown','unknown') else x for x in dirparts]
                album_moved = True

            # 2) 文件名最小归一化（整轨保留）
            if re.match(r'^\d{1,3}\s*\.\s*Track\d*', stem, re.I) or stem.lower() in ('cdimage',):
                new_bn = bn
            else:
                new_bn = normalize_fname(bn)

            before = p
            after = '/'.join(new_dir + [new_bn])
            if after != before:
                action = 'album_move' if album_moved else 'rename'
                stats[action] += 1
                f.write(f"{action}\t{before}\t{after}\n")
            else:
                stats['keep'] += 1

    print("干跑结果:")
    print(f"  专辑落地(未知专辑->真实专辑): {stats['album_move']}")
    print(f"  文件名规范化: {stats['rename']}")
    print(f"  保持不变: {stats['keep']}")

if __name__ == '__main__':
    main()
