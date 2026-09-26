"""Render reviewed audit data. Does not infer coverage or refresh evidence."""
from pathlib import Path
import argparse
import json
import os
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

def read(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))

def code(value):
    value = str(value).replace('\n', ' ')
    delimiter = '`' * (max((len(m.group()) for m in re.finditer(r'`+', value)), default=0) + 1)
    return delimiter + ' ' + value + ' ' + delimiter

def link(path, line=None, label=None):
    label = (label or path).replace('|', '&#124;')
    if not (ROOT / path).exists():
        return code(label) + ' (vorgeschlagen)'
    href = os.path.relpath(ROOT / path, HERE).replace(os.sep, '/')
    return f'[{label}]({href}' + (f'#L{line}' if line else '') + ')'

def ids(values, page):
    return ', '.join(f'[{v}]({page}#{v.lower()})' for v in values) or '—'

def heading(item):
    return f'\n<a id="{item["id"].lower()}"></a>\n\n## {item["id"]} · {item["title"]}\n'

def render():
    data = read('audit.json')
    sources = read('sources.json')
    routes = read('routes.json')
    coverage = read('python-coverage.json')
    searches = read('search-evidence.json')
    pages = {}
    rows = ['# Produktverhalten und Testbelege\n',
      '[Einstieg](README.md) · [Dateikatalog](../backend.md) · [Lücken](gaps.md)\n',
      '77 gruppierte Verhaltensverträge, alle 216 Testdateien verknüpft. '
      'Ein Abschnitt bündelt mehrere Teilverträge; die 83 ausgewählten Testdefinitionen sind konkrete **Teilbelege**. '
      'Sie beweisen nicht jede Klausel des Abschnitts. Der vollständige Testdateikatalog bleibt maßgeblich für die übrigen Assertions. '
      'Zuordnung, Testzahl und Zeilenausführung sind keine fachliche Coveragequote.\n',
      '| Vertrag | Verhalten | Quellen | Testdateien | Befunde |\n|---|---|---:|---:|---|']
    for c in data['contracts']:
        rows.append(f'| [{c["id"]}](#{c["id"].lower()}) | {c["title"]} | {len(c["source_paths"])} | {len(c["test_files"])} | {ids(c["gap_ids"],"gaps.md")} |')
    for c in data['contracts']:
        rows += [heading(c), c['expectation'] + '\n',
          '**Anforderungsbasis:** ' + link(c['basis']['path']) + ' · ' + code(c['basis']['kind']) + '. '
          'Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; '
          '[abweichende Oracles](decisions.md) beachten.\n',
          '**Bewertung:** ' + ('Teilweise belegt.' if c['test_files'] else 'Kein eigener Verhaltensbeleg in der Suite gefunden.') + ' ' + c['evidence_note'] + '\n',
          '**Testgrenze:** ' + c['boundary'] + '\n',
          '**Befunde:** ' + ids(c['gap_ids'],'gaps.md') + '. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.\n',
          '<details><summary>Produktdateien und zugeordnete Testdateien</summary>\n',
          '**Produktdateien:**\n', '\n'.join('- ' + link(p) for p in c['source_paths']) + '\n',
          '**Testdateien:**\n', '\n'.join('- ' + link(p) for p in c['test_files']) or 'Keine.', '\n</details>\n',
          '**Konkrete Teilbelege:**\n']
        for e in c['representative_evidence']:
            rows += ['- ' + link(e['path'],e['line'],e['name']) + f' — {e["level"]}. '
              + 'Historischer **Datei**status: ' + ', '.join(f'{k}={v}' for k,v in e['file_execution'].items()) + '.']
            rows += ['  - ' + link(e['path'],a['line'],f'Zeile {a["line"]}') + ': ' + code(a['excerpt']) for a in e['assertions']]
        if not c['representative_evidence']:
            rows += ['Kein repräsentativer Verhaltenstest vorhanden.']
    pages['matrix.md'] = '\n'.join(rows) + '\n'

    rows = ['# Verifizierte Befunde und ergänzende Tests\n',
      '[Einstieg](README.md) · [Arbeitspakete](work-packages.md) · [Suchbelege](search-evidence.json)\n',
      '36 Befunde. „Verifiziert“ bezeichnet den geprüften Code-/Testabgleich. '
      'Nur G-018/G-019 sind hier direkt beobachtete Verhaltensfehler; '
      'G-007/G-020 zusätzlich durch überlebende gezielte Mutationen belegte Assertionslücken. '
      'Die übrigen Kategorien unterscheiden fehlende Fälle/Integration, defekte Tests, Ausführungsnachweis und CI.\n',
      'P1/P2/P3 ordnen die Umsetzung nach möglichen Folgen und Voraussetzungen; sie sind keine Incident-Schweregrade. '
      'Suchtreffer allein beweisen weder Vorhandensein noch Abwesenheit eines Tests. '
      'Die Schlussfolgerung verbindet Suche, Testkörper, Mockgrenzen und gegebenenfalls Branchlauf/Probe. '
      'Suggested paths sind Vorschläge, vorhandene passende Dateien bevorzugen.\n',
      '| ID | Priorität / Art | Befund | Paket |\n|---|---|---|---|']
    for g in data['gaps']:
        rows += [f'| [{g["id"]}](#{g["id"].lower()}) | {g["priority"]} / {code(g["kind"])} | {g["title"]} | {ids(g["work_package_ids"],"work-packages.md")} |']
    for g in data['gaps']:
        search=searches[g['id']]
        rows += [heading(g), f'**{g["priority"]} · {g["kind"]}** · Verträge: {ids(g["contract_ids"],"matrix.md")} · Paket: {ids(g["work_package_ids"],"work-packages.md")}\n',
          '**Produktbeleg:** ' + '; '.join(link(r['path'],r['line']) + ' — ' + code(r['needle']) for r in g['production']) + '\n',
          '**Vorhandene relevante Prüfungen:**\n']
        for e in g['existing_evidence']:
            rows += ['- ' + link(e['path'],e['line'],e['name']) + ' — ' + e['level'] + '. Assertionstellen: '
              + ', '.join(link(e['path'],n,str(n)) for n in e['assertion_lines']) + '.']
        if not g['existing_evidence']: rows += ['Kein direkter repräsentativer Testbeleg für diese Grenze; Suchtreffer und verwandte Verträge sind separat berücksichtigt.']
        rows += ['\n**Suiteweite Gegenprüfung:** ' + g['verification'] + '\n',
          f'**Suchspur:** {search["scanned_files"]} versionierte Test-/Hilfsdateien durchsucht, {len(search["hits"])} passende Zeilen. '
          'Regexe: ' + ', '.join(code(p) for p in search['regexes']) + '. Vollständige Treffer mit Pfad/Zeile in ' + '[search-evidence.json](search-evidence.json)' + f' unter {code(g["id"])}.\n',
          '| Szenario | Erwartung |\n|---|---|',
          '| Given | ' + g['scenario']['given'].replace('|','&#124;') + ' |',
          '| When | ' + g['scenario']['when'].replace('|','&#124;') + ' |',
          '| Then | ' + g['scenario']['then'].replace('|','&#124;') + ' |\n',
          '**Zielstellen:** ' + ', '.join(link(p) for p in g['suggested_test_paths']) + '\n',
          '**Wiederverwenden:** ' + ', '.join(link(p) for p in g['reuse_helpers']) + '\n',
          '**Validierung nach Implementierung:** ' + code(g['validation_command']) + '\n',
          '**Gezielte Negativkontrolle:** ' + g['negative_control'] + '\n']
    pages['gaps.md']='\n'.join(rows)+'\n'

    rows=['# Codex-Arbeitspakete\n','[Einstieg](README.md) · [Befunde](gaps.md) · [Nutzerreisen](journeys.md) · [Oracles](decisions.md)\n',
      'Alle **30 Pakete sind geplant**, keines in diesem Dokumentationsauftrag implementiert. '
      'Die IDs sind stabil; sie geben keine zwingende lineare Reihenfolge vor. '
      'Abhängigkeiten sind fachliche/technische Voraussetzungen. Vorarbeit ist früher möglich. '
      'WP-01 bis WP-04 klären den Ausgangsstand; WP-05 macht die allgemeine CI verbindlich. '
      'WP-06 bis WP-14 sowie WP-20 schützen besonders folgenreiche Grenzen. '
      'WP-29 folgt auf tragfähige Adapter-/Persistenztests. Die restlichen Pakete bleiben im Gesamtumfang.\n',
      '## Gemeinsamer Auftrag und Abnahme\n',
      'Ein Paket anhand seiner ID auswählen. Zuerst `check_product_audit.py` und den bisherigen Inventarcheck ausführen. '
      'Bei Drift betroffene Code-/Testkörper erneut lesen; Hashes nicht blind aktualisieren. '
      'Produktvertrag, Given/When/Then und vorhandene Testhelfer lesen. Den kleinsten geeigneten Test ergänzen, der das reale Verhalten an der benannten Grenze ausführt. '
      'Nur äußere Abhängigkeiten ersetzen; den zu prüfenden Guard/Adapter nicht mocken. '
      'Bei beobachtetem Produktfehler zuerst roten Regressionstest festhalten und dann begründet korrigieren.\n',
      'Jedes Paket verlangt die verknüpften Then-Bedingungen, mindestens eine fachliche Negativkontrolle '
      '(temporäre Mutation nur lokal/in isoliertem Prozess), passende fokussierte Regressionen und erforderliche Repo-Gates. '
      'Ein Statuscode/Mockaufruf ersetzt keinen benötigten DB-/UI-Endzustand. Konkurrenz mit Barrieren/Fakeuhr steuern; keine Sleeps als Erfolgsbedingung. '
      'Unabhängige Owner-/Run-/Versionskontrollwerte verwenden. Testdoubles an realer SDK-/HTTP-Form ausrichten.\n',
      'Bei neuen Tests die Runner-Discovery kontrollieren. Nach Änderungen unter `static/` Build und öffentliche Cachebuster nach AGENTS.md pflegen; '
      'bei Änderungen von Architektur/Flows `docs/codebase-map.md` im selben Auftrag aktualisieren. '
      'Keine echten Provider-/Produktdatenzugriffe in Regressionen. Fehlende Umgebung als offen dokumentieren, nicht als Erfolg umetikettieren.\n',
      'Abschluss pro Paket in `audit.json`: Status `completed`, Implementierungscommit und konkrete Validierungsevidenz '
      '(Befehle, Umgebung, Pass/Fail/Skip, Negativkontrolle, Restgrenze). Bei Teilabschluss `in_progress` oder `blocked` mit Grund. '
      'Originale Audit-/Laufhistorie erhalten; fachliche Matrix, neuer Testkatalog und aktuelle Nachweise bewusst fortschreiben.\n',
      '| Paket | Ziel | Priorität | Vorher | Befunde | Status |\n|---|---|---|---|---|---|']
    for w in data['work_packages']:
        rows += [f'| [{w["id"]}](#{w["id"].lower()}) | {w["title"]} | {w["priority"]} | {ids(w["dependencies"],"work-packages.md")} | {ids(w["gap_ids"],"gaps.md")} | {w["status"]} |']
    for w in data['work_packages']:
        rows += [heading(w), '**Ziel:** '+w['focus']+'\n', '**Befunde:** '+ids(w['gap_ids'],'gaps.md')+' · **Vorher:** '+ids(w['dependencies'],'work-packages.md')+'\n',
          '**Vorgehen:** '+w['approach']+'\n', '**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** '+w['acceptance']+'\n',
          '**Produktstellen:** '+', '.join(link(p) for p in w['source_paths'])+'\n',
          '**Test-/Dokumentziele:** '+', '.join(link(p) for p in w['target_test_paths'])+'\n',
          '**Vorhandene Hilfen:** '+', '.join(link(p) for p in w['reuse_helpers'])+'\n',
          '**Befehle/Prüfauftrag nach Implementierung:**\n', '\n'.join('- '+code(x) for x in w['validation_commands'])+'\n',
          '**Zu beachten:** '+ids(w['decision_ids'],'decisions.md')+'\n']
    pages['work-packages.md']='\n'.join(rows)+'\n'

    rows=['# Inventar der Produkt- und Betriebsdateien\n','[Einstieg und Scope](README.md) · [Maschinenlesbar mit Hashes und Python-Symbolen](sources.json)\n',
      '269 Dateien, 128.351 physische Quellzeilen. Jede Datei ist mindestens einem Verhaltensbereich zugeordnet. '
      'Das ist ein Vollständigkeitscheck der Auswahl, kein Beweis für jede Funktion/Stylesheetregel. '
      'Direkte Testreferenzen sind ausschließlich Suchkandidaten aus dem vorherigen Testinventar. '
      'Null direkte Referenzen können trotzdem indirekte Tests bedeuten. Alle positiven Testbelege stehen in der Matrix/dem Dateikatalog.\n',
      'Pythonspalte: ausgeführte Statements/Statements und ausgeführte Branches/Branches des regulären Branchlaufs; '
      'bei null Branches „—“, bei nicht instrumentierter Datei „nicht gemessen“. '
      'Vorhandene ausgeführte Statements können Moduldefinitionen/Imports sein.\n',
      '| Datei | Zeilen | Verträge | Direkte Testreferenzen | Python-Ausführung |\n|---|---:|---|---:|---|']
    for s in sources:
        f=coverage['files'].get(s['path']); measure='nicht gemessen'
        if f:
            a=f['summary'];measure=f'{a["covered_lines"]}/{a["num_statements"]} Statements; '+(f'{a["covered_branches"]}/{a["num_branches"]} Branches' if a['num_branches'] else '— Branches')
        rows.append(f'| {link(s["path"])} | {s["lines"]} | {ids(s["contract_ids"],"matrix.md")} | {len(s["direct_test_candidates"])} | {measure} |')
    pages['sources.md']='\n'.join(rows)+'\n'

    rows=['# Runtime-Routeninventar\n','[Einstieg](README.md) · [Rohdaten](routes.json)\n',
      'Aus `main.app.routes` im Unit-Test-Modus erfasst: **158 App-Routeneinträge und 4 Frameworkrouten**. '
      'Methoden werden pro registriertem Eintrag gebündelt; GET/HEAD ist deshalb ein Eintrag. '
      'Die neun dynamischen `/ask_*`-Routen wurden zur Laufzeit aufgelöst. '
      'Das `/static`-Mount ist keine App-Endpointdefinition und wird über Assets/Build im Dateiinventar behandelt. '
      'Vertragszuordnungen beschreiben Handlerzuständigkeit, nicht einen bestandenen HTTP-Test. '
      'Pfadtext in einem Browsertest kann eine Route ersetzen statt sie auszuführen.\n',
      '| ID | Methoden | Pfad | Handler | Vertrag |\n|---|---|---|---|---|']
    for r in routes:
        handler='Framework' if r['source']=='framework' else link(r['source'],r['line'],r['handler'])
        rows += [f'| {r["id"]} | {", ".join(r["methods"])} | {code(r["path"])} | {handler} | {ids(r["contract_ids"],"matrix.md")} |']
    pages['routes.md']='\n'.join(rows)+'\n'
    return {name: content.rstrip() + '\n' for name, content in pages.items()}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='Compare without writing')
    args=parser.parse_args()
    problems=[]
    for name, text in render().items():
        path=HERE/name
        if args.check:
            if not path.exists() or path.read_text(encoding='utf-8')!=text: problems.append(name)
        else: path.write_text(text,encoding='utf-8')
    if problems:
        print('Generated pages differ: '+', '.join(problems))
        return 1
    print('OK: 5 reviewed-data pages '+('match' if args.check else 'rendered'))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
