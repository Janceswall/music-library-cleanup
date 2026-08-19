#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段4：双层判重（干跑，不移动文件）（参数化版）
用法: python3 dedup.py [输出目录]
  输入 <输出目录>/index_enriched.jsonl（由 enrich.py 产出）
  输出 dup_auto_groups.tsv（自动判重）/ dup_review.jsonl（人工裁决）/ summary.txt

核心安全原则：
  - 歌名/路径含 Live/演唱会/现场/伴奏/演奏/Remix/重制 等版本标记 → 绝不自动判重，转人工裁决。
  - 自动判重仅针对：剔除下载垃圾后缀后名称一致、且无版本标记的文件。
  - 音质评分排序，保留最优。
"""
import json, re, sys, unicodedata
from collections import defaultdict

OUTDIR = sys.argv[1] if len(sys.argv) > 1 else '.'
IN = f"{OUTDIR}/index_enriched.jsonl"
OUT_AUTO = f"{OUTDIR}/dup_auto_groups.tsv"
OUT_REVIEW = f"{OUTDIR}/dup_review.jsonl"
OUT_SUMMARY = f"{OUTDIR}/summary.txt"

def nfkc(s): return unicodedata.normalize('NFKC', s or '')

def junk_clean(t):
    t = nfkc(t).strip()
    t = re.sub(r'\.旺旺[：:].*$', '', t)
    t = re.sub(r'[（(]\s*\d+\s*[)）]$', '', t)
    t = re.sub(r'[【\[（(]?(flac|ape|dsd|sacd|无损|hifi)[】\]）)]?$', '', t, flags=re.I)
    return t.strip(' ._~-~')

VERSION_PAT = re.compile(
    r'(live|演唱会|现场|巡回|演奏会|音乐会|concert|伴奏|纯音乐|演奏|ktv|卡拉|'
    r'remix|混音|重制|remastered|acoustic|demo|翻唱|cover|串烧|串烧版|接歌|'
    r'国语版|粤语版|日语版|英语版|现场版|特别版|完整版|加速版|慢速版)', re.IGNORECASE)

def is_version_variant(title, path):
    return bool(VERSION_PAT.search(title or '') or VERSION_PAT.search(path or ''))

def base_title(t):
    t = junk_clean(t)
    t = re.sub(r'[（(](live|remaster|remix|demo|acoustic|instrumental|karaoke|混音|重制|现场|演唱会|伴奏|演奏|ktv|消音|remastered|翻唱|国语版|粤语版|现场版|特别版)[)）]', '', t, flags=re.I)
    t = re.sub(r'[（(【\[][^（）()】\[\]]{0,12}(live|remaster|remix|现场|演唱会|伴奏|版|演奏|混音)[)）】\]]$', '', t)
    return t.strip(' ._~-~')

def clean_artist(a):
    a = nfkc(a).strip()
    a = re.sub(r'^[（(]\s*\d{2,4}\s*[)）]\s*', '', a)
    a = re.sub(r'^(\d{4})[.\s]+', '', a)
    return a.strip()

def norm(s):
    s = nfkc(s).lower()
    s = re.sub(r'[\s\u3000\u00a0]+', '', s)
    s = re.sub(r'[^\w\u4e00-\u9fff]', '', s, flags=re.UNICODE)
    return s

def quality_score(r):
    codec = (r.get('codec') or '').lower()
    sr = int(r.get('sample_rate') or 0)
    bits = int(r.get('bits') or 0)
    br = int(r.get('bit_rate') or 0)
    base = {
        'dsd_msbf':100,'dsd_lsbf':100,'dsf':100,'dff':100,
        'flac':80, 'alac':75, 'ape':72, 'wav':62, 'pcm_s16le':60,
        'pcm_f32le':62,'pcm_s24le':66,'dts':70,
        'mp3':30,'aac':34,'m4a':34,'ogg':26,'wma':26,
    }
    sc = base.get(codec, 20)
    if codec == 'flac' or codec == 'alac' or codec.startswith('pcm'):
        if bits >= 24: sc += 8
        elif bits >= 20: sc += 5
        elif bits >= 16: sc += 3
    if sr >= 176000: sc += 5
    elif sr >= 96000: sc += 4
    elif sr >= 88200: sc += 3
    elif sr >= 48000: sc += 2
    if codec in ('mp3','aac','m4a','ogg','wma'):
        sc += min(br/1000/100, 3)
    return sc

def in_trash(p):
    return '.trash' in p or '.quarantine' in p

def main():
    recs = []
    for line in open(IN, encoding='utf-8'):
        r = json.loads(line)
        r['unresolved'] = not (r.get('artist_f') and r.get('title_f'))
        r['variant'] = is_version_variant(r.get('title_f',''), r.get('path',''))
        recs.append(r)

    groups = defaultdict(list)
    for r in recs:
        if r['unresolved'] or r['variant']:
            continue
        a = clean_artist(r['artist_f'])
        t = junk_clean(r['title_f'])
        groups[norm(a) + '|' + norm(t)].append(r)

    auto_keep = auto_dup = 0
    auto_dup_bytes = 0
    with open(OUT_AUTO, 'w', encoding='utf-8') as fauto:
        fauto.write('group_key\tkeep_path\tkeep_score\tdup_path\tdup_score\tdup_size\n')
        for key, arr in groups.items():
            if len(arr) < 2:
                auto_keep += 1
                continue
            arr.sort(key=lambda r: (quality_score(r), -in_trash(r['path']), r['size']), reverse=True)
            keep = arr[0]
            auto_keep += 1
            for d in arr[1:]:
                auto_dup += 1
                auto_dup_bytes += d['size']
                fauto.write(f"{key}\t{keep['path']}\t{quality_score(keep)}\t{d['path']}\t{quality_score(d)}\t{d['size']}\n")

    review_groups = defaultdict(list)
    for r in recs:
        if r['unresolved']:
            continue
        a = clean_artist(r['artist_f'])
        bt = base_title(r['title_f'])
        if not norm(bt):
            continue
        review_groups[(norm(a), norm(bt))].append(r)

    review_entries = []
    for key, arr in review_groups.items():
        if len(arr) < 2:
            continue
        titles_norm = {norm(junk_clean(r['title_f'])) for r in arr}
        if not any(r['variant'] for r in arr) and len(titles_norm) == 1:
            continue
        review_entries.append({
            'artist': arr[0]['artist_f'],
            'base_title': base_title(arr[0]['title_f']),
            'variants': [{
                'path': r['path'], 'title': r['title_f'], 'variant': r['variant'],
                'codec': r.get('codec',''), 'sample_rate': r.get('sample_rate',''),
                'bits': r.get('bits',''), 'size': r.get('size'), 'score': quality_score(r),
            } for r in sorted(arr, key=lambda x: -quality_score(x))],
        })
    with open(OUT_REVIEW, 'w', encoding='utf-8') as frv:
        for e in review_entries:
            frv.write(json.dumps(e, ensure_ascii=False) + '\n')

    unresolved = [r for r in recs if r['unresolved']]
    ur_bytes = sum(r['size'] for r in unresolved)
    nvariants = sum(1 for r in recs if r['variant'])

    with open(OUT_SUMMARY, 'w', encoding='utf-8') as fs:
        fs.write(f"总音频:{len(recs)}\n")
        fs.write(f"身份不明:{len(unresolved)}个,{ur_bytes/1024/1024/1024:.1f}GB\n")
        fs.write(f"版本标记文件:{nvariants}个\n")
        fs.write(f"自动判重:保留{auto_keep}首,待清理{auto_dup}首,可腾{auto_dup_bytes/1024/1024/1024:.1f}GB\n")
        fs.write(f"人工裁决组:{len(review_entries)}组\n")

    print(f"总音频: {len(recs)}")
    print(f"身份不明: {len(unresolved)}个, {ur_bytes/1024/1024/1024:.1f}GB")
    print(f"版本标记文件: {nvariants}个")
    print(f"自动判重: 保留{auto_keep}首, 待清理{auto_dup}首, 可腾{auto_dup_bytes/1024/1024/1024:.1f}GB")
    print(f"人工裁决组: {len(review_entries)}组")

if __name__ == '__main__':
    main()
