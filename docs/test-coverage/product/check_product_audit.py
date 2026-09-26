"""Validate an audit snapshot; never infer semantic coverage or refresh hashes."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote

from render_product_audit import render

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

def read(name):
    return json.loads((HERE/name).read_text(encoding='utf-8'))

def selected(path):
    included = path.startswith(('app/','benchmark/','scripts/','templates/','static/js/','static/css/','.github/workflows/')) or path in (
      'main.py','static/firebase.js','static/app-ui.js','static/demo.js','static/style.css','dev.ps1',
      'firebase.json','firestore.rules','firestore.indexes.json','package.json','vitest.config.mjs')
    return included and path.endswith(('.py','.js','.mjs','.html','.css','.json','.yml','.ps1','.rules'))

def main():
    problems=[]
    def require(condition,message):
        if not condition: problems.append(message)
    data=read('audit.json'); sources=read('sources.json'); routes=read('routes.json')
    searches=read('search-evidence.json'); cov=read('python-coverage.json'); execution=read('execution.json')
    inv=json.loads((HERE.parent/'inventory.json').read_text(encoding='utf-8'))
    tracked=subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines()
    untracked=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
    all_paths=sorted(set(tracked+untracked))
    source_paths={s['path'] for s in sources}
    require(source_paths=={p for p in all_paths if selected(p)},'Product file selection changed; review inventory')
    require(len(source_paths)==len(sources),'Duplicate source paths')
    contracts={c['id']:c for c in data['contracts']}; gaps={g['id']:g for g in data['gaps']}; packages={w['id']:w for w in data['work_packages']}
    for label,seq,mapping in [('contracts',data['contracts'],contracts),('gaps',data['gaps'],gaps),('packages',data['work_packages'],packages)]:
        require(len(seq)==len(mapping),f'Duplicate {label} IDs')
    testfiles={t['path']:t for t in inv['files']}
    text_cache={}
    def lines(path):
        if path not in text_cache:
            text_cache[path]=(ROOT/path).read_text(encoding='utf-8-sig').splitlines()
        return text_cache[path]
    for s in sources + data['reference_hashes'] + inv['files'] + inv['support_files']:
        path=ROOT/s['path']
        require(path.is_file(),f'Missing {s["path"]}')
        if path.is_file():
            require(hashlib.sha256(path.read_bytes()).hexdigest()==s['sha256'],f'Changed; review required: {s["path"]}')
    for s in sources:
        require(len(lines(s['path']))==s['lines'],f'Line count drift: {s["path"]}')
        require(s['contract_ids']==[c['id'] for c in data['contracts'] if s['path'] in c['source_paths']],f'Bad reverse mapping: {s["path"]}')
        require(bool(s['contract_ids']),f'Unassigned source: {s["path"]}')
        for symbol in s['symbols']:
            require(1<=symbol['line']<=symbol['end_line']<=s['lines'],f'Invalid symbol position: {s["path"]}')
    linked_tests=set()
    for c in contracts.values():
        require(set(c['source_paths'])<=source_paths,f'Unknown source: {c["id"]}')
        require(set(c['test_files'])<=set(testfiles),f'Unknown test: {c["id"]}')
        linked_tests.update(c['test_files'])
        require(c['gap_ids']==[g['id'] for g in data['gaps'] if c['id'] in g['contract_ids']],f'Wrong gap mapping: {c["id"]}')
        require(bool(c['representative_evidence'])==bool(c['test_files']),f'Missing representative evidence: {c["id"]}')
        for e in c['representative_evidence']:
            require(e['path'] in c['test_files'],f'Evidence outside contract tests: {c["id"]}')
            ds=[d for d in testfiles[e['path']]['definitions'] if d['name']==e['name'] and d['line']==e['line']]
            require(len(ds)==1,f'Unknown evidence definition: {e["path"]}:{e["line"]}')
            require(e['file_execution']==testfiles[e['path']]['execution'],f'Wrong historical execution: {c["id"]}')
            for a in e['assertions']:
                require(e['line']<=a['line']<=e['end_line'],f'Assertion outside definition: {c["id"]}')
                snippet='\n'.join(lines(e['path'])[a['line']-1:e['end_line']])
                require(a['excerpt'] in snippet,f'Assertion text drift: {e["path"]}:{a["line"]}')
    require(linked_tests==set(testfiles),'Not every inventoried test file is linked')
    require(set(searches)==set(gaps),'Search evidence gap IDs differ')
    test_search_paths=sorted(p for p in all_paths if p.startswith('tests/') and p.endswith(('.py','.js','.mjs','.json','.md')))
    for g in gaps.values():
        require(set(g['contract_ids'])<=set(contracts),f'Unknown gap contracts: {g["id"]}')
        require(set(g['dependencies'])<=set(gaps),f'Unknown gap dependency: {g["id"]}')
        require(set(g['work_package_ids'])<=set(packages),f'Unknown gap package: {g["id"]}')
        for ref in g['production']:
            require((ROOT/ref['path']).is_file(),f'Missing gap source: {g["id"]}')
            require(1<=ref['line']<=len(lines(ref['path'])),f'Invalid gap position: {g["id"]}')
            require(ref['needle'] in lines(ref['path'])[ref['line']-1],f'Gap source text drift: {g["id"]}')
        for e in g['existing_evidence']:
            defs=[d for d in testfiles[e['path']]['definitions'] if d['name']==e['name'] and d['line']==e['line']]
            require(len(defs)==1,f'Invalid gap evidence: {g["id"]}')
            if defs: require(e['assertion_lines']==[a['line'] for a in defs[0]['assertion_evidence']],f'Assertion locations differ: {g["id"]}')
        for p in g['reuse_helpers']: require((ROOT/p).exists(),f'Missing reuse target: {g["id"]} {p}')
        s=searches[g['id']]
        require(s['scanned_files']==len(test_search_paths),f'Search scope drift: {g["id"]}')
        patterns=[(pattern,re.compile(pattern,re.I)) for pattern in s['regexes']]
        actual=[]
        for p in test_search_paths:
            for n,line in enumerate(lines(p),1):
                terms=[pattern for pattern,compiled in patterns if compiled.search(line)]
                if terms: actual.append(dict(path=p,line=n,terms=terms,text=line.strip()[:400]))
        require(actual==s['hits'],f'Search hits drift: {g["id"]}')
    route_keys=set()
    for r in routes:
        key=(tuple(r['methods']),r['path']);require(key not in route_keys,f'Duplicate route: {key}');route_keys.add(key)
        if r['source']!='framework':
            require(r['source'] in source_paths,f'Unknown route source: {r["id"]}')
            require(1<=r['line']<=len(lines(r['source'])),f'Invalid route line: {r["id"]}')
            require(bool(r['contract_ids']) and set(r['contract_ids'])<=set(contracts),f'Unknown route contract: {r["id"]}')
    decision_ids=set(re.findall(r'<a id="(d-\d+)"', (HERE/'decisions.md').read_text()))
    covered_gaps=Counter()
    for w in packages.values():
        require(set(w['dependencies'])<=set(packages),f'Unknown dependency: {w["id"]}')
        require(set(w['gap_ids'])<=set(gaps),f'Unknown package gap: {w["id"]}')
        require(all(d.lower() in decision_ids for d in w['decision_ids']),f'Unknown decision: {w["id"]}')
        covered_gaps.update(w['gap_ids'])
        for gid in w['gap_ids']: require(w['id'] in gaps[gid]['work_package_ids'],f'Bad package reverse mapping: {gid}')
        require(w['status'] in ('planned','in_progress','blocked','completed'),f'Invalid package status: {w["id"]}')
        if w['status']=='completed': require(bool(w['implementation_commit']) and bool(w['validation_evidence']),f'Completed without evidence: {w["id"]}')
    require(set(covered_gaps)==set(gaps) and all(v==1 for v in covered_gaps.values()),'Each gap must have exactly one owning package')
    def ancestors(key,trail=()):
        if key in trail:
            problems.append('Dependency cycle: '+' -> '.join(trail+(key,)))
            return set()
        deps=set(packages[key]['dependencies'])
        for dep in tuple(deps):
            if dep in packages: deps.update(ancestors(dep,trail+(key,)))
        return deps
    for wid in packages: ancestors(wid)
    for g in gaps.values():
        for dep in g['dependencies']:
            for current in g['work_package_ids']:
                require(set(gaps[dep]['work_package_ids'])<=(ancestors(current)|{current}),f'Unrepresented gap dependency: {g["id"]} -> {dep}')
    expected_counts=dict(source_files=len(sources),source_lines=sum(s['lines'] for s in sources),contracts=len(contracts),
       test_files_linked=len(linked_tests),representative_definitions=sum(len(c['representative_evidence']) for c in contracts.values()),
       application_routes=sum(r['source']!='framework' for r in routes),framework_routes=sum(r['source']=='framework' for r in routes),gaps=len(gaps),work_packages=len(packages))
    require(data['counts']==expected_counts,'Inconsistent overview counts')
    for field in ('covered_lines','num_statements','missing_lines','excluded_lines','num_branches','num_partial_branches','covered_branches','missing_branches'):
        require(sum(f['summary'][field] for f in cov['files'].values())==cov['totals'][field],f'Coverage total mismatch: {field}')
    require(set(cov['files'])<=source_paths,'Coverage source outside inventory')
    require(execution['reviewed_commit']==data['reviewed_commit'],'Execution/review commit mismatch')
    for name,expected in render().items():
        require((HERE/name).read_text(encoding='utf-8')==expected,f'Regenerate {name}')
    for md in HERE.glob('*.md'):
        content=md.read_text(encoding='utf-8')
        content=re.sub(r'```.*?```','',content,flags=re.S)
        content=re.sub(r'(`+).*?\1','',content)
        for href in re.findall(r'\]\(([^)]+)\)',content):
            if re.match(r'\w+://',href): continue
            raw,_,anchor=href.partition('#')
            target=(md.parent/unquote(raw)).resolve() if raw else md
            require(target.exists(),f'Broken link in {md.name}: {href}')
            if anchor and target.is_file():
                if re.fullmatch(r'L\d+',anchor):
                    require(int(anchor[1:])<=len(target.read_text(encoding='utf-8-sig').splitlines()),f'Bad source line link: {href}')
                elif target.suffix=='.md':
                    require(f'id="{anchor}"' in target.read_text(encoding='utf-8'),f'Missing explicit anchor: {md.name} -> {href}')
    if problems:
        print('\n'.join(sorted(set(problems))))
        return 1
    print(f'OK: {len(sources)} sources, {len(contracts)} contracts, {len(linked_tests)} test files, {len(routes)} routes, {len(gaps)} gaps, {len(packages)} packages.')
    print('Hashes, evidence locations, search trails, dependency DAG, local links and generated pages match. Semantic review and live execution are not renewed.')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
