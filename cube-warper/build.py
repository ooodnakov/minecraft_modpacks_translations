"""Build bilingual FTB Quests text from the preserved Cube Warper 1.11 originals."""
from pathlib import Path
import json,re
ROOT=Path(__file__).resolve().parent
WORK=ROOT/'source'
TRANSLATIONS=WORK/'translations'
CHAPTERS=ROOT/'overrides/config/ftbquests/quests/chapters'
BACKUP=WORK/'originals'
STRING=re.compile(r'"(?:\\.|[^"\\])*"')
def entries(source):
    description=False
    offset=0
    for line in source.splitlines(keepends=True):
        field=re.match(r'\s*(title|subtitle|description):',line)
        if field or description:
            for m in STRING.finditer(line):
                text=json.loads(m.group())
                if text and not re.fullmatch(r'\{image:.*\}',text):
                    yield offset+m.start(),offset+m.end(),text
        if field and field[1]=='description':
            description=not line.rstrip().endswith(']')
        elif description and line.strip()==']':
            description=False
        offset+=len(line)
def read(path):
    return path.read_bytes().decode('utf-8')
def inventory():
    if not BACKUP.is_dir():
        raise FileNotFoundError(f'Missing canonical originals: {BACKUP}')
    originals=sorted(BACKUP.glob('chapter_*.snbt'))
    if not originals:
        raise FileNotFoundError(f'No original chapter files in {BACKUP}')
    result={}
    for saved in originals:
        result[saved.stem]=[text for _,_,text in entries(read(saved))]
    (WORK/'source.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result
def build():
    source=inventory()
    en,ru={},{}
    localized={}
    for chapter,texts in source.items():
        translated=json.loads((TRANSLATIONS/f'{chapter}.ru.json').read_text())
        assert len(translated)==len(texts),(chapter,len(translated),len(texts))
        original=read(BACKUP/f'{chapter}.snbt')
        changes=list(entries(original))
        output=original
        for i,(start,end,english) in reversed(list(enumerate(changes))):
            russian=translated[i]
            assert isinstance(russian,str) and russian.strip(),(chapter,i)
            assert re.findall(r'&[0-9a-fk-or]|§[0-9a-fk-or]',english)==re.findall(r'&[0-9a-fk-or]|§[0-9a-fk-or]',russian),(chapter,i,'formatting')
            assert re.findall(r'\{[^{}]*\}',english)==re.findall(r'\{[^{}]*\}',russian),(chapter,i,'embedded markup')
            key=f'cube_warper.quest.{chapter}.{i:03}'
            en[key]=english
            ru[key]=russian
            output=output[:start]+json.dumps('{'+key+'}')+output[end:]
        # Resolve every key to prove the non-text content is byte-for-byte unchanged.
        resolved=re.sub(r'"\{(cube_warper\.quest\.[^{}]+)\}"',lambda m:json.dumps(en[m[1]],ensure_ascii=False),output)
        normalized=original
        for start,end,text in reversed(changes):
            normalized=normalized[:start]+json.dumps(text,ensure_ascii=False)+normalized[end:]
        assert resolved==normalized,chapter
        localized[chapter]=output
    items=json.loads((WORK/'quest-items.ru.json').read_text())
    assert not (ru.keys() & items.keys()),'duplicate item and quest language keys'
    ru.update(items)
    lang=ROOT/'overrides/kubejs/assets/cube_warper/lang'
    lang.mkdir(parents=True,exist_ok=True)
    for locale,values in [('en_us',en),('ru_ru',ru)]:
        p=lang/f'{locale}.json'
        p.write_text(json.dumps(values,ensure_ascii=False,indent=2)+'\n')
    CHAPTERS.mkdir(parents=True,exist_ok=True)
    for chapter,output in localized.items():
        (CHAPTERS/f'{chapter}.snbt').write_bytes(output.encode('utf-8'))
    print(f'Built {len(en)} quest text entries and {len(items)} item names in {len(localized)} chapters; original quest structure verified.')
if __name__=='__main__':
    import sys
    if '--inventory' in sys.argv:
        for chapter,texts in inventory().items():
            print(chapter,len(texts))
    else:
        build()
