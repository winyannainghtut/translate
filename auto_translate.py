import os, re, time, subprocess, sys
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

START=1629
END=1700
REPO='/root/translate'
UA={'user-agent':'Mozilla/5.0'}

NO_TRANSLATE=[
    'Spirit Qi','True Qi','Nascent Soul','Golden Core','Foundation Establishment','Deity Transformation',
    'Divine Sense','Spiritual Sense','Dantian','Meridians','Formation','Array','Talisman','Incantation','Spells',
    'Daoist','Sect Master','Fellow Daoist','Sect','Dao','Qi'
]
# sort longer first to avoid partial overlap
NO_TRANSLATE=sorted(NO_TRANSLATE,key=len,reverse=True)

translator = GoogleTranslator(source='en', target='my')

def run(cmd, check=True):
    p=subprocess.run(cmd, cwd=REPO, shell=True, text=True, capture_output=True)
    if check and p.returncode!=0:
        raise RuntimeError(f'cmd failed: {cmd}\n{p.stdout}\n{p.stderr}')
    return p

def fetch_chapter(n):
    # NovelFire seems shifted by +1
    url=f'https://novelfire.net/book/a-record-of-a-mortals-journey-to-immortality/chapter-{n+1}'
    r=requests.get(url,headers=UA,timeout=30)
    if r.status_code!=200:
        raise RuntimeError(f'fetch failed {n} status {r.status_code}')
    soup=BeautifulSoup(r.text,'lxml')
    title_tag=soup.title.get_text(' ',strip=True) if soup.title else f'Chapter {n}'
    m=re.search(r'Chapter\s+(\d+)\s*:\s*(.*?)\s*-\s*Novel Fire', title_tag)
    src_num=int(m.group(1)) if m else None
    src_title=m.group(2).strip() if m else f'Chapter {n}'
    if src_num is not None and src_num!=n:
        raise RuntimeError(f'chapter mismatch wanted {n} got {src_num} from {url}')
    content=soup.select_one('#content')
    if not content:
        raise RuntimeError(f'no #content for {n}')
    paras=[x.strip() for x in content.get_text('\n').split('\n') if x.strip()]
    # drop site boilerplate if present
    bad_prefixes=('Previous Chapter','Next Chapter','Comments')
    paras=[p for p in paras if not p.startswith(bad_prefixes)]
    return src_title, paras, url

def protect_terms(text):
    mapping={}
    for i,t in enumerate(NO_TRANSLATE):
        key=f'[[NT{i}]]'
        text=text.replace(t,key)
        mapping[key]=t
    return text,mapping

def restore_terms(text,mapping):
    for k,v in mapping.items():
        text=text.replace(k,v)
    return text

def trans_text(text):
    # keep manageable chunks
    text,mapping=protect_terms(text)
    parts=[]
    cur=''
    for para in text.split('\n'):
        if len(cur)+len(para)+1>2800:
            parts.append(cur)
            cur=para
        else:
            cur = para if not cur else cur+'\n'+para
    if cur:
        parts.append(cur)

    out=[]
    for part in parts:
        for attempt in range(5):
            try:
                tr=translator.translate(part)
                out.append(tr)
                break
            except Exception as e:
                if attempt==4:
                    raise
                time.sleep(2*(attempt+1))
    joined='\n\n'.join(out)
    joined=restore_terms(joined,mapping)
    return joined

def clean_mm(text):
    text=text.replace('၊။','။').replace('..','။')
    return text

def main():
    first_commit=None
    last_commit=None
    alt_sources=[]

    # ensure git clean except instruction or script
    run('git checkout main')

    for n in range(START,END+1):
        out_path=os.path.join(REPO,f'{n}.md')
        if os.path.exists(out_path):
            print(f'{n} exists, skipping')
            continue
        print(f'Processing {n}...')
        title,paras,url=fetch_chapter(n)
        en='\n'.join(paras)
        my=trans_text(en)
        my=clean_mm(my)
        doc=f'# {n} — {title}\n\n{my}\n'
        with open(out_path,'w',encoding='utf-8') as f:
            f.write(doc)

        run(f'git add {n}.md')
        run(f"git commit -m 'Add Burmese translation chapter {n}'")
        run('git push origin main')
        h=run('git rev-parse --short HEAD').stdout.strip()
        if not first_commit:
            first_commit=h
        last_commit=h
        print(f'{n} committed {h}')
        time.sleep(1)

    print('DONE')
    print('FIRST',first_commit)
    print('LAST',last_commit)
    if alt_sources:
        print('ALT',','.join(map(str,alt_sources)))

if __name__=='__main__':
    main()
