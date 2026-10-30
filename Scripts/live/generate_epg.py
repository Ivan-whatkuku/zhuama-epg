#!/usr/bin/env python3
"""Select exact upstream channel IDs, run pinned epg, validate and publish atomically."""
import argparse, copy, datetime as dt, json, pathlib, subprocess, tempfile, xml.etree.ElementTree as ET
UTC = dt.timezone.utc

def xmltv_date(value):
    for fmt in ('%Y%m%d%H%M%S %z','%Y%m%d%H%M %z','%Y%m%d%H%M%S','%Y%m%d%H%M'):
        try:
            d=dt.datetime.strptime(value.strip(),fmt)
            return d.replace(tzinfo=UTC) if d.tzinfo is None else d.astimezone(UTC)
        except ValueError: pass
    raise ValueError('Invalid XMLTV timestamp: '+value)

def select_channels(epg, catalogue, config, output):
    ids={c['id'] for c in catalogue['channels']}; selected={}; xml=ET.Element('channels')
    for filename in config['channelFiles']:
        for channel in ET.parse(epg/'sites'/filename).getroot():
            upstream=channel.get('xmltv_id',''); base=upstream.split('@')[0]
            # Feed suffixes belong to the same official channel, never fuzzy match names.
            if base in ids and base not in selected:
                selected[base]=dict(upstreamID=upstream,site=channel.get('site'),siteID=channel.get('site_id'))
                xml.append(copy.deepcopy(channel))
    if not selected: raise ValueError('No exact channel-ID mappings found')
    ET.ElementTree(xml).write(output,encoding='utf-8',xml_declaration=True)
    return selected

def validate_and_merge(raw, previous, ids, now):
    current=ET.parse(raw).getroot(); result=ET.Element('tv',{'generator-info-name':'ZhuaMa / iptv-org/epg'})
    metadata={}; programmes={}; fresh=set(); starts=[]; ends=[]
    for element in current.findall('channel'):
        key=element.get('id','').split('@')[0]
        if key in ids:
            c=copy.deepcopy(element);c.set('id',key);metadata[key]=c
    def ingest(root, fresh_data):
        for p in root.findall('programme'):
            channel=p.get('channel','').split('@')[0]
            if channel not in ids or (not fresh_data and channel in fresh):continue
            try: start=xmltv_date(p.get('start',''));end=xmltv_date(p.get('stop',''))
            except ValueError: continue
            title=(p.findtext('title') or '').strip()
            if not title or end<=start or end<now-dt.timedelta(days=2) or start>now+dt.timedelta(days=14):continue
            element=copy.deepcopy(p);element.set('channel',channel)
            programmes[(channel,start,title)]=(element,start,end)
            if fresh_data:fresh.add(channel)
    ingest(current,True)
    if not fresh or not any(end>now for _,_,end in programmes.values()): raise ValueError('No fresh, current/future programmes; previous published guide retained')
    if previous and previous.exists():
        old=ET.parse(previous).getroot()
        for element in old.findall('channel'):
            if element.get('id') in ids:metadata.setdefault(element.get('id'),copy.deepcopy(element))
        ingest(old,False)
    for key in sorted({k[0] for k in programmes}):
        result.append(metadata.get(key,ET.Element('channel',{'id':key})))
    for element,start,end in sorted(programmes.values(),key=lambda v:(v[1],v[0].get('channel'))):
        result.append(element);starts.append(start);ends.append(end)
    manifest=dict(generatedAt=now.strftime('%Y-%m-%dT%H:%M:%SZ'),validFrom=min(starts).strftime('%Y-%m-%dT%H:%M:%SZ'),validUntil=max(ends).strftime('%Y-%m-%dT%H:%M:%SZ'),channelCount=len({k[0] for k in programmes}),programmeCount=len(programmes),freshChannelCount=len(fresh))
    return result,manifest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--epg',type=pathlib.Path,required=True);p.add_argument('--catalogue',type=pathlib.Path,default=pathlib.Path('ZhuaMa/LiveChannels.json'));p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--select-only',action='store_true');a=p.parse_args()
    config=json.loads(pathlib.Path(__file__).with_name('epg_sources.json').read_text());catalogue=json.loads(a.catalogue.read_text())
    a.output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        work=pathlib.Path(temp);selection=work/'channels.xml';mapping=select_channels(a.epg,catalogue,config,selection)
        print(f'Mapped {len(mapping)} of {len(catalogue["channels"])} channels by exact ID')
        if a.select_only: print(json.dumps(mapping,ensure_ascii=False));raise SystemExit(0)
        raw=work/'guide.xml'
        subprocess.run(['npm','run','grab','--','--channels='+str(selection.resolve()),'--output='+str(raw.resolve()),'--maxConnections=3','--timeout=15000'],cwd=a.epg,check=True)
        guide,manifest=validate_and_merge(raw,a.output/'guide.xml',set(mapping),dt.datetime.now(UTC))
        manifest['upstreamRevision']=config['revision'];manifest['mappedChannelCount']=len(mapping);manifest['missingChannelIDs']=sorted(set(c['id'] for c in catalogue['channels'])-set(mapping))
        staged=work/'validated.xml';ET.ElementTree(guide).write(staged,encoding='utf-8',xml_declaration=True)
        # Validation is complete before touching published files.
        (a.output/'guide.xml').write_bytes(staged.read_bytes())
        (a.output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        (a.output/'mapping.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(manifest,ensure_ascii=False))
