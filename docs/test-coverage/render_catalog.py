"""Render per-file Markdown and the area index from the reviewed JSON snapshot.

Edit semantic review fields in inventory.json after reading changed sources;
this renderer does not infer coverage, update hashes, or execute tests.
Run: python docs/test-coverage/render_catalog.py
"""
import html
import json
import pathlib

OUT = pathlib.Path(__file__).resolve().parent
data = json.loads((OUT / "inventory.json").read_text(encoding="utf-8"))
files = data["files"]
SHA = data["base_commit"]

def escape(value):
    return html.escape(value, quote=False).replace("[", "\\[").replace("]", "\\]")

labels={'passed':'bestanden','failed':'fehlgeschlagen','error':'Setup-/Lauffehler','skipped':'übersprungen','not_run':'nicht ausgeführt'}
def status(f):return ', '.join(f"{n} {labels[k]}" for k,n in f['execution'].items())
def slug(f):return pathlib.Path(f['path']).name.replace('.','-').replace('_','-')
def link(path,label=None):return f'[{label or path}](../../{path})'
for suite,title in [('backend','Reguläre Python-Suite'),('frontend','JavaScript-Suite'),('e2e','Separat gestartete E2E-Suite')]:
 group=[f for f in files if f['suite']==suite]
 lines=[f'# {title}: Abdeckung pro Testdatei','',f'Stand: **{data["review_date"]}**, Quellstand `{SHA}`. [Methodik und Gesamtbefund](../test-coverage-map.md).','',f'**{len(group)} Dateien · {sum(f["definition_count"] for f in group)} statische Testdefinitionen · {sum(f["runner_case_count"] for f in group)} Runner-Fälle.**','', '„Geprüftes Verhalten“ beschreibt die vorhandenen Assertions. Der Laufstatus steht separat: bei Fehlern ist der beschriebene Vertrag nicht als bestanden belegt. Prüfaufträge sind offene Fragen für den Folgeaudit, keine pauschal festgestellten Lücken der gesamten Suite.','', 'Die Codeverweise sind direkte Imports oder wörtliche Pfade, keine gemessene Ausführungsabdeckung. Indirekte Abhängigkeiten über Fixtures/Helpers und dynamisch zusammengesetzte Pfade können fehlen. Das [JSON-Inventar](inventory.json) enthält jede Definition mit Zeilen, Assertion-Fundstellen und jeden expandierten Runner-Fall.','', '| Datei | Definitionen | Runner-Fälle | Primärlauf |','|---|---:|---:|---|']
 for f in group:lines.append(f'| [{pathlib.Path(f["path"]).name}](#{slug(f)}) | {f["definition_count"]} | {f["runner_case_count"]} | {status(f)} |')
 for f in group:
  lines+=['',f'<a id="{slug(f)}"></a>','',f'## {pathlib.Path(f["path"]).name}','',f'**Quelle:** {link(f["path"])} · **Bereiche:** '+', '.join(f['areas'])+'.','',f'**Ebene:** {f["level"].rstrip(chr(46))}.', '',f'**Lauf:** {status(f)}.']
  for c in f['cases']:
   if c['status'] in {'failed','error'}:
    lines+=['',f'- `{c["id"].split("::")[-1]}`: {escape(c.get("message",c["status"]).splitlines()[0][:280].rstrip())}'+(' Im isolierten Wiederholungslauf bestanden; Ursache der Abweichung noch offen.' if c.get('isolated_recheck')=='passed' else '')]
  lines+=['',f'**Geprüftes Verhalten:** {f["covers"]}','',f'**Grenzen und Doubles:** {f["limits"]}','',f'**Prüfauftrag für den Folgeaudit:** {f["questions"]}']
  if f['source_references']:lines+=['','**Direkte Codeverweise:** '+', '.join(link(p) for p in f['source_references'])+'.']
  if f['test_helper_references']:lines+=['','**Direkte Testhelfer:** '+', '.join(link(p) for p in f['test_helper_references'])+'.']
  lines+=['','<details>',f'<summary>{f["definition_count"]} Testdefinitionen und ihre Quellstellen</summary>','']
  for t in f['definitions']:lines.append(f'- [{escape(t["name"])}](../../{f["path"]}#L{t["line"]}) (Zeile {t["line"]})')
  lines+=['','</details>']
 (OUT/(suite+'.md')).write_text('\n'.join(lines)+'\n')
areas=sorted({a for f in files for a in f['areas']})
lines=['# Einstieg nach Produktbereich','','[Methodik und Gesamtbefund](../test-coverage-map.md) · [Maschinenlesbares Inventar](inventory.json)','','Mehrfachzuordnungen sind beabsichtigt. Diese Liste geht vom Testbestand aus. Sie beweist nicht, dass alle Produktmodule oder Anforderungen einen Test besitzen; dafür ist der umgekehrte Abgleich mit Produktionscode nötig.','','| Bereich | Reguläre Python-Dateien | JavaScript-Dateien | E2E-Dateien |','|---|---|---|---|']
for a in areas:
 cells=[]
 for s in ['backend','frontend','e2e']:
  cells.append('<br>'.join(f'[{pathlib.Path(f["path"]).name}]({s}.md#{slug(f)})' for f in files if a in f['areas'] and f['suite']==s) or '—')
 lines.append('| '+a+' | '+' | '.join(cells)+' |')
(OUT/'areas.md').write_text('\n'.join(lines)+'\n')
print("Rendered backend.md, frontend.md, e2e.md and areas.md from inventory.json")
