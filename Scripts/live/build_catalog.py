#!/usr/bin/env python3
"""Build the bundled CN/HK/TW catalogue from the three official iptv-org APIs."""
import argparse, datetime, json, pathlib, re, urllib.request
from urllib.parse import urlparse

def build(channels, streams, logos):
    lines, marks = {}, {}
    for s in streams:
        u = urlparse(s['url'])
        if u.scheme not in ('http', 'https') or pathlib.PurePosixPath(u.path).suffix.lower() not in ('.m3u8', '.mp4', '.mov', '.m4v'):
            continue
        lines.setdefault(s.get('channel'), {})[s['url']] = dict(url=s['url'], quality=s.get('quality'), userAgent=s.get('user_agent'), referrer=s.get('referrer'))
    for l in logos:
        if l.get('in_use') and str(l.get('format')).upper() in ('PNG', 'JPEG', 'JPG', 'WEBP'):
            marks.setdefault(l['channel'], l['url'])
    result = []
    for c in channels:
        if c['country'] not in ('CN', 'HK', 'TW') or c.get('is_nsfw') or c.get('closed') or not lines.get(c['id']):
            continue
        name = next((n for n in c.get('alt_names', []) if re.search('[一-鿿]', n)), c['name'])
        group = '港台' if c['country'] in ('HK', 'TW') else '央视' if c['id'].upper().startswith('CCTV') else '卫视' if any(x in name for x in ('卫视','衛視')) else '地方频道'
        result.append(dict(id=c['id'], name=name, country=c['country'], logo=marks.get(c['id']), category=group,
            isSports='sports' in c.get('categories', []) or any(x in name for x in ('体育','體育','足球','篮球','籃球')),
            streams=sorted(lines[c['id']].values(), key=lambda s:(not s['url'].startswith('https://'), s['url']))))
    if not result: raise ValueError('No playable CN/HK/TW channels; refusing to replace catalogue')
    return dict(generatedAt=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), channels=sorted(result,key=lambda c:c['name']))

if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('--input',type=pathlib.Path); p.add_argument('--output',type=pathlib.Path,required=True); a=p.parse_args()
    def read(name):
        if a.input: return json.loads((a.input / (name+'.json')).read_text())
        with urllib.request.urlopen('https://iptv-org.github.io/api/'+name+'.json',timeout=45) as r: return json.load(r)
    result=build(*(read(n) for n in ('channels','streams','logos')))
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(f"Built {len(result['channels'])} channels")
