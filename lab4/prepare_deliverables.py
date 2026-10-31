"""Build the Lab 4 review documents from executed case evidence.

Use a Python environment with reportlab, Pillow, pypdf and PyMuPDF. This script does not
run collectors, change the database or claim a physical-phone test was performed.
"""
from pathlib import Path
from datetime import datetime
import html
import json
import re
import shutil
import subprocess

from PIL import Image as PILImage
import fitz
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
PDFS = HERE/'output/pdf'
DATE = '26 October 2026'
INK = colors.HexColor('#183247')
PALE = colors.HexColor('#edf2f5')
WIDTH = A4[0]-32*mm
STYLES = getSampleStyleSheet()
STYLES.add(ParagraphStyle(name='BodyTextLab', fontName='Helvetica', fontSize=9.2, leading=13,
                         spaceAfter=7, textColor=INK))
STYLES.add(ParagraphStyle(name='CellLab', fontName='Helvetica', fontSize=7.7, leading=10.3,
                         spaceAfter=0, wordWrap='CJK', textColor=INK))
STYLES.add(ParagraphStyle(name='CellHeadLab', parent=STYLES['CellLab'], fontName='Helvetica-Bold'))
STYLES.add(ParagraphStyle(name='TitleLab', fontName='Helvetica-Bold', fontSize=21, leading=25,
                         spaceAfter=12, textColor=INK))
STYLES.add(ParagraphStyle(name='HeadingLab', fontName='Helvetica-Bold', fontSize=12, leading=16,
                         spaceBefore=8, spaceAfter=8, keepWithNext=True, textColor=INK))


def clean(text):
    return str(text).replace('\u2013','-').replace('\u2014','-').replace('\u2011','-').replace('\u2212','-')


def para(text, style='BodyTextLab'):
    text = html.escape(clean(text)).replace('\n','<br/>')
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    return Paragraph(text, STYLES[style])


def table(headers, rows, weights=None):
    weights = weights or [1]*len(headers)
    widths = [WIDTH*w/sum(weights) for w in weights]
    data = [[para(h, 'CellHeadLab') for h in headers]]
    data += [[para(value, 'CellLab') for value in row] for row in rows]
    result = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
    result.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),PALE), ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
        ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
        ('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#9aadb9')),
        ('LINEBELOW',(0,1),(-1,-1),.25,colors.HexColor('#d8e0e5')),
    ]))
    return result


def page(canvas, document):
    canvas.saveState()
    canvas.setFont('Helvetica',7.5)
    canvas.setFillColor(colors.HexColor('#526978'))
    canvas.drawString(16*mm,A4[1]-12*mm,'ParkChoiceSG | Lab 4 | '+DATE)
    canvas.drawRightString(A4[0]-16*mm,10*mm,str(document.page))
    canvas.restoreState()


def pdf(name, title, story):
    path=PDFS/name
    document=SimpleDocTemplate(str(path),pagesize=A4,rightMargin=16*mm,leftMargin=16*mm,
                              topMargin=21*mm,bottomMargin=17*mm,
                              title=title,author='',creator='')
    document.build(story,onFirstPage=page,onLaterPages=page)


def md_table(headers, rows):
    safe=lambda v:clean(v).replace('|','/').replace('\n',' ')
    return '\n'.join(['| '+' | '.join(map(safe,headers))+' |',
                      '| '+' | '.join('---' for _ in headers)+' |',
                      *['| '+' | '.join(map(safe,row))+' |' for row in rows]])


def flow_diagrams(report):
    folder=HERE/'diagrams';folder.mkdir(exist_ok=True)
    jar=Path.home()/'.cache/parkchoice-tools/plantuml.jar'
    for graph in report['control_flow']:
        name='window-control-flow' if graph['function']=='window_at' else 'tier-control-flow'
        lines=['@startdot','digraph G {',
               'graph [rankdir=TB, nodesep=0.30, ranksep=0.25, dpi=72, bgcolor="white"];',
               'node [shape=circle, fontname="Arial", fontsize=15, width=0.35, height=0.35];',
               'edge [fontname="Arial", fontsize=10, arrowsize=0.7];']
        for a,b in graph['graph_edges']:
            lines.append(f'"{a}" -> "{b}";')
        lines += ['"X" [shape=doublecircle];','}','@enddot']
        source=folder/(name+'.puml');source.write_text('\n'.join(lines)+'\n',encoding='utf-8')
        subprocess.run(['java','-jar',str(jar),'-tsvg',str(source)],check=True,capture_output=True)
        # The bundled Graphviz supports SVG but has no PNG renderer on this host.
        # Rasterize its actual vector output rather than accepting a text error file.
        vector=fitz.open(stream=source.with_suffix('.svg').read_bytes(),filetype='svg')
        vector[0].get_pixmap(matrix=fitz.Matrix(2,2),alpha=False).save(str(source.with_suffix('.png')))
        vector.close()


MANUAL_CHECKS = [
    ('AND-01','Install the supplied arm64 debug APK on the actual demo phone.','Launches anonymous Search.','Pending on device'),
    ('AND-02','Use USB reverse port 8000; issue a real search.','Phone reaches the laptop backend.','Pending on device'),
    ('AND-03','Grant foreground location; then test denial/manual origin.','Fresh fix or recoverable manual-input path.','Pending on device'),
    ('AND-04','Search a rehearsed 15-90-minute arrival scenario.','Real routed prices and eligible arrival probabilities, or an honest unavailable state.','Pending on device'),
    ('AND-05','Re-search with each ranking mode.','Mode sent; old results cleared; policy shown consistently.','Pending on device'),
    ('AND-06','Open map, launch navigation and return to the app.','Attributed tiles/markers and correct carpark handoff; no crash.','Pending on device'),
    ('AND-07','Run a short trip and inspect current-only fallback.','Fallback is separately labelled; no fabricated forecast.','Pending on device'),
    ('AND-08','Rotate, open keyboard, background/foreground, switch tabs repeatedly.','No crash/overflow; transient resets understood.','Pending on device'),
    ('AND-09','Disconnect/reconnect USB and rerun reverse; retry a request.','Recoverable service error and successful retry.','Pending on device'),
    ('AND-10','If showing Admin, test wrong/right configured operator credentials.','Credential check works; console data/actions identified as prototypes.','Pending on device'),
]


DEMO = [
    ('00:00-01:00','Problem and users','Explain that the driver arrives later than the latest reading. Introduce anonymous driver search and the separate operator area.','Driver presenter'),
    ('01:00-02:00','Android input','Show the actual device and one foreground GPS fix if available. For a repeatable forecast scenario, manually select NTU as the origin and Jurong East MRT as destination.','Driver presenter'),
    ('02:00-05:00','Real recommendation','Select a stay duration and Best overall. Explain driving ETA to each carpark, forecast probability of at least one lot, current source timestamp, supported total-stay cost and walking route. Read actual values; do not quote fixed expected counts.','Driver presenter'),
    ('05:00-06:00','Preference trade-off','Re-search using Prioritise cheaper and Prioritise closer. Explain that weights change while eligibility rules do not. A different winner is not guaranteed with every live shortlist.','Driver presenter'),
    ('06:00-07:00','Map and navigation','Show OneMap attribution and start/destination/carpark markers. Open external navigation for one carpark, then return. No physical driving is needed.','Driver presenter'),
    ('07:00-08:30','Short-trip fallback','Use a rehearsed short route such as Novena to City Hall. Explain the disabled sub-15-minute forecasting cohort and the separate current-reading list if fresh usable evidence exists.','Driver presenter'),
    ('08:30-09:30','Recovery and scope','Show a rehearsed recoverable input/provider error. If time permits, show theme persistence or tracker UI, clearly labelling non-durable/prototype behavior. Do not present mock operator data as live monitoring.','Driver presenter'),
    ('09:30-11:30','Traceability','Trace UC-01 through RecommendationController, pricing helpers, model adapter and the CTL/REQ tests. Show one overnight tariff flow graph and its actual expected/observed table.','Technical presenter'),
    ('11:30-13:00','Engineering evidence','Summarize automated tests, independent basis paths, unsupported-price handling and prediction/current separation. Distinguish interface/regression checks from model accuracy and on-phone evidence.','Technical presenter'),
    ('13:00-14:30','Architecture and extension','Explain Flutter -> API -> DB/OneMap/model; collection is separate. Mention canonical IDs, observation/knowledge time, prospective forecast auditing and private server credentials.','Technical presenter'),
    ('14:30-15:00','Close','State implemented search benefits and remaining scope. Leave the app on a useful result screen. Keep the pre-recorded video available for network failure.','Driver presenter'),
]


VIDEO = [
    ('00:00-00:30','Problem, actual phone and anonymous search.'),
    ('00:30-01:15','Select real origin/destination and duration.'),
    ('01:15-02:30','Show a real forecast recommendation; explain ETA, probability, supported price and walking distance.'),
    ('02:30-03:15','Re-search with a different ranking mode; show actual trade-offs.'),
    ('03:15-04:00','Open map and external navigation; return safely.'),
    ('04:00-04:40','Show short-trip current fallback or an honest unavailable state.'),
    ('04:40-05:00','State the tested scope and close on the result screen.'),
]


def testing(report):
    story=[para('Test Cases and Testing Results','TitleLab'),
           para('Executed evidence for the reconciled local prototype. '+DATE+'.'),
           para('**88 documented cases passed.** The wider backend suite passed 151 unittest methods. '
                'These are different counting units: one method can contain many parameter cases. '
                'The HDB model suite passed 108 tests and Flutter passed 44 tests. Android arm64 debug packaging succeeded. '
                'A physical-device run is still pending.'),
           para('1. Requirement and scope','HeadingLab'),
           table(['Lab 4 requirement','Evidence'],[
               ('3.2.1 - one important control class; equivalence classes and boundary values',
                'RecommendationController.recommend: 16 cases. Validated TripRequest: 18 boundary cases. Supporting scoring: 37 cases.'),
               ('3.2.2 - basis path testing of two complex methods',
                'pricing.window_at and pricing._tier_price. Each graph has V(G)=8 and eight independent feasible paths; one extra full-day condition case is retained.'),
               ('3.2.3 - carefully minimize cases','One fault or boundary is varied at a time. Shared valid inputs avoid unnecessary combinations. Additional full-day case is justified by an actual mutation.'),
               ('3.2.4 - execute and record expected versus actual','Machine-readable rows and source hashes: lab4/evidence/test-results.json. Tables below are regenerated from those rows.'),
           ],[1,2]),
           para('Tests use controlled public-code fixtures. No API/database call is needed to reproduce the offline study. '
                'Passing fixtures do not establish prediction accuracy, universal tariff coverage or crash freedom on every Android device.'),
           PageBreak(),para('2. Black-box partitions and boundaries','HeadingLab'),
           para('The selected control class coordinates the core UC-01 recommendation. It receives routing and prediction '
                'dependencies and returns candidate evidence, exclusions and rankings. The existing recommend(...) function '
                'remains a compatibility entry point. Price calculation, collection and scoring stay in focused helpers.'),
           table(['Input/condition','Partitions or boundaries'],[
               ('Forecast outcome','Valid forecast; invalid identity/history; low probability; unsupported horizon; audit failure.'),
               ('Required evidence','Supported/unsupported price; successful/failed driving or walking route; empty shortlist.'),
               ('Fallback evidence','Fresh source reading; stale reading; retrieval proxy. A known low forecast cannot enter fallback.'),
               ('Probability threshold','0.899999 / 0.900000 / 0.900001; tests eligibility, not probability calibration.'),
               ('Duration, candidates, radius','For each finite integer range, min-1 / min / min+1 / max-1 / max / max+1.'),
               ('Scoring support','Valid lots/probability modes; negative, non-finite, wrong-type or conflicting availability inputs; invalid weights.'),
           ],[1,2]),
           para('Nominal scoring input is 400 cents, 60 minutes, 500 metres, 900 seconds and one available lot. '
                'All penalties equal 0.5, producing score 50. Reference scales and mode weights are policy, not learned driver preferences.'),
           para('Minimization: 16 controller cases distinguish the application outcomes; 18 request points cover the two bounds '
                'of each constrained integer input; 20 equivalence cases and 17 scoring boundary cases provide hand-checkable oracles. '
                'The case sets are deliberately not a Cartesian product.'),
    ]
    md=['# Test cases and testing results\n\n'+DATE+'. Current local review build, not a submission-ready claim.\n',
        '88 documented cases passed; backend regression: 151 unittest methods; model tests: 108; Flutter tests: 44. '
        'Android arm64 debug APK built. Physical-device checks remain pending.\n']
    for title,prefix,weights in [
        ('3. Recommendation control cases','CTL-', [0.6,1.5,2.3,2.0]),
        ('4. Request boundary values','REQ-', [0.6,2.0,1.1,1.1]),
        ('5. Supporting scoring equivalence classes','EC-', [0.6,2.7,1.2,1.2]),
        ('6. Supporting scoring boundary values','BV-', [0.6,2.7,1.2,1.2]),
    ]:
        selected=[r for r in report['rows'] if r['id'].startswith(prefix)]
        rows=[[r['id'],r['inputs'],r['expected'],r['actual']+' | '+('PASS' if r['passed'] else 'FAIL')] for r in selected]
        story += [PageBreak(),para(title,'HeadingLab'),table(['ID','Input / change','Expected','Actual / result'],rows,weights)]
        md += ['\n## '+title+'\n',md_table(['ID','Input / change','Expected','Actual / result'],rows)+'\n']
    for index, graph in enumerate(report['control_flow'],7):
        function=graph['function'];prefix='WA-' if function=='window_at' else 'TP-'
        picture=HERE/'diagrams'/('window-control-flow.png' if prefix=='WA-' else 'tier-control-flow.png')
        w,h=PILImage.open(picture).size;factor=min(195/w,430/h)
        legend = ([('1','Read rule configuration and clocks'),('2','Equal clocks without full_day?'),
                   ('3','Reject empty window'),('4','Next anchor date / exhausted'),('5','Construct dated start and end'),
                   ('6','Closing <= opening?'),('7','Move end into next day'),('8','Minute outside interval?'),
                   ('9','Day category incompatible?'),('10','Weekday filter excludes date?'),
                   ('11','Holiday-eve filter mismatch?'),('12','Return interval'),('13','Return no match'),('X','Shared exit')]
                  if prefix=='WA-' else
                  [('1','Read rule configuration and tiers'),('2','First-entry status required?'),('3','Status unknown?'),
                   ('4','Return unknown'),('5','Repeat entry?'),('6','Read repeat-entry tiers'),('7','Repeat tiers missing?'),
                   ('8','Return unknown'),('9','Initialize amount and remaining'),('10','Next tier / exhausted'),
                   ('11','Used minutes > 0?'),('12','Charge and consume tier minutes'),('13','Minutes remain?'),
                   ('14','Round up remainder charge'),('15','Return exact amount'),('X','Shared exit')])
        legend_table=Table([[para(a,'CellLab'),para(b,'CellLab')] for a,b in legend],
                           colWidths=[24,WIDTH-239],hAlign='LEFT')
        legend_table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),
                                         ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
        diagram_panel=Table([[Image(str(picture),width=w*factor,height=h*factor),legend_table]],
                            colWidths=[210,WIDTH-210])
        diagram_panel.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP')]))
        story += [PageBreak(),para(f'{index}. Basis path study: {function}','HeadingLab'),
                  para(f"N={graph['nodes']}, E={graph['edges']}; V(G)=E-N+2={graph['complexity_edges']}. "
                       'Seven statement-level decisions plus one also gives eight. Boolean operands inside a compound '
                       'condition are not separate nodes in this graph; this is not an MC/DC claim.'),
                  diagram_panel,Spacer(1,8),
                  para('X is the shared virtual exit. Edge direction follows the source; true/false outcomes are specified '
                       'in the path sequences below. Each declared path was checked against an actual line trace.'),
                  para('The eight basis trace vectors have rank eight over GF(2), using edge traversal parity. '
                       'That verifies independence for this selected graph; it does not mean all possible paths were executed.')]
        selected=[r for r in report['rows'] if r['id'].startswith(prefix)]
        pathrows=[[r['id'],r['path'],r['inputs'],r['expected']+' / '+r['actual']] for r in selected]
        story += [PageBreak(),para(function+': executed paths and outputs','HeadingLab'),
                  table(['ID','Path','Input','Expected / actual'],pathrows,[.6,1.8,2.3,1.7])]
        if prefix=='WA-':
            story += [para('WA-C1 is additional condition coverage, not a ninth basis path. Changing closing <= opening '
                           'to closing < opening leaves the eight basis cases passing but fails WA-C1. '
                           'The case checks that equal opening/closing times mean 24 hours only when full_day is explicit.')]
        md += ['\n## '+function+' basis paths\n',
               f"N={graph['nodes']}; E={graph['edges']}; V(G)=8; independent basis rank=8.\n",
               md_table(['ID','Path','Input','Expected / actual'],pathrows)+'\n']
    story += [PageBreak(),para('9. Regression, reproducibility and limits','HeadingLab'),
              table(['Check','Observed result / scope'],[
                  ('Backend regression','151 unittest methods, zero failures/errors/skips. Includes the merged operator tests and ranking modes.'),
                  ('HDB model tests','108 tests passed; selected unit/service suites. Ignored raw-data parity archives were not supplied.'),
                  ('Flutter','44 tests passed; analyzer clean. Includes operator entry, response validation, lifecycle/stress, map and navigation fixtures.'),
                  ('Android build','arm64 debug APK built with API URL http://127.0.0.1:8000. USB reverse is required for this device URL.'),
                  ('Live integration','See evidence/live-check.json. This check observes current providers; it is not a later-outcome accuracy evaluation.'),
                  ('Physical phone','No Android device was connected during this preparation. Do not mark the checklist below passed without execution.'),
              ],[1,2]),
              para('Reproduce the documented study: python lab4/collect_evidence.py using the backend Python environment. '
                   'It evaluates each table row, traces both methods, checks graph complexity/independence and runs backend regression. '
                   'Source SHA-256 hashes and timestamps are stored with the results.'),
              para('Known scope: HDB short-mode forecasts only, 15-90-minute integration horizon, 0.90 ranking threshold; '
                   'selected model evaluation horizons were 15/30/45/60/90. Current fallback is separate. Pricing is conditional '
                   'on fresh supported rules, and shortlisted carparks are not a global optimum. Operator console actions, '
                   'durable sessions and several local-data features remain prototypes.'),
              PageBreak(),para('10. Android acceptance record - pending','HeadingLab'),
              table(['ID','Action','Expected','Actual status'],MANUAL_CHECKS,[.6,2,2,1.0]),
              para('For each completed phone check, record device model, Android version, APK hash, date, observed result '
                   'and tester identity in the team copy. The build and widget tests do not substitute for this record.')]
    md += ['\n## Android acceptance record\n',md_table(['ID','Action','Expected','Actual status'],MANUAL_CHECKS)+'\n',
           '\nReproduce: `python lab4/collect_evidence.py`. Source hashes and exact rows: `evidence/test-results.json`.\n']
    (HERE/'TEST-CASES-AND-RESULTS.md').write_text('\n'.join(md),encoding='utf-8')
    pdf('Testing-Report.pdf','ParkChoiceSG Lab 4 - Test Cases and Results',story)


def demo():
    preflight=[
        ('Device','Use the actual Android demo phone. Unlock it, enable USB debugging and confirm adb lists it as device, not unauthorized.'),
        ('Services','Start the model on laptop port 8001 and API on 8000. Inspect model artifact health and run a genuine eligible search; health alone is insufficient.'),
        ('USB','Run adb -s DEVICE_ID reverse tcp:8000 tcp:8000. The APK targets phone loopback port 8000; reconnecting USB may require reverse again.'),
        ('Network','Laptop needs database/OneMap/HDB access. Phone needs internet for OneMap tiles and external navigation. Keep the USB cable connected.'),
        ('Freshness','Rehearse and check metadata, tariff review dates and current source readings. Refresh/review through the normal owner workflow if necessary; do not disable guards for the demo.'),
        ('Scenario','Choose a real current 15-90-minute arrival example and a short-trip example. Live availability and winners may change. Keep a second rehearsed destination.'),
        ('Privacy','Use public sample places in recordings. Keep .env files, passwords and keys off screen; entering operator credentials should be obscured.'),
        ('Backup','Record and review the five-minute screen video before the presentation. The script is prepared; the actual video has not been recorded by this task.'),
    ]
    story=[para('Android Demo Script','TitleLab'),para(DATE+' | 15-minute live sequence and 5-minute video plan.'),
           para('Use the real working search as the main demonstration. Lab 4 permits prioritizing main functionality '
                'when implementation time is limited. Do not present planned features, prototype operator data or widget '
                'fixtures as live backend behavior.'),
           para('1. Preflight','HeadingLab'),table(['Check','Action'],preflight,[1,3]),
           PageBreak(),para('2. Live demo - 15 minutes','HeadingLab'),
           table(['Time','Segment','Actions / explanation','Role'],DEMO,[1,1.1,3.4,1.0]),
           PageBreak(),para('3. Phone commands and recovery','HeadingLab'),
           para('From the repository root, use the setup in backend/README.md. The debug build permits local HTTP; '
                'it is not the production deployment configuration.'),
           para('adb devices -l\nadb -s DEVICE_ID reverse tcp:8000 tcp:8000\n'
                'adb -s DEVICE_ID install -r lab4/submission/ParkChoiceSG-debug-arm64.apk\n'
                'adb -s DEVICE_ID shell am start -n com.example.parkchoicesg_2/.MainActivity'),
           table(['If this happens','Recovery'],[
               ('No device / unauthorized','Unlock the phone, accept debugging, verify the USB data cable, then list devices again.'),
               ('Phone cannot reach API','Confirm backend is running; rerun reverse for the selected device. Do not substitute the laptop LAN address without rebuilding the matching API URL.'),
               ('Location denied or slow','Use manual place selection. Refresh a fix older than two minutes; do not invent a coordinate.'),
               ('No eligible forecast','Explain the actual exclusion. Try the rehearsed alternative; current-only fallback is valid only when the backend permits it.'),
               ('Price unavailable','Explain missing/stale/ambiguous tariff evidence. Do not quote a made-up hourly price or turn missing cost into zero.'),
               ('Provider/network outage','Show recoverable state, then use the reviewed recording clearly identified as pre-recorded evidence.'),
           ],[1,2]),
           para('4. Five-minute recording script','HeadingLab'),table(['Time','What to capture'],VIDEO,[1,3]),
           para('Lab 4 asks for a five-minute video; Lab 5 permits five to seven minutes. A five-minute recording fits both. '
                'This plan does not assert that a video file exists. Capture the actual Android app and check picture, audio '
                'and readable labels before adding the real video/link to the submission index.')]
    pdf('Android-Demo-Script.pdf','ParkChoiceSG Lab 4 - Android Demo Script',story)
    md='# Android demo script\n\n'+DATE+'\n\n## Preflight\n'+md_table(['Check','Action'],preflight)
    md+='\n\n## 15-minute live sequence\n'+md_table(['Time','Segment','Actions','Role'],DEMO)
    md+='\n\n## Five-minute video plan\n'+md_table(['Time','Capture'],VIDEO)
    md+='\n\nActual device acceptance and video recording remain pending. Use the supplied phone checklist; do not infer phone success from a build.\n'
    (HERE/'DEMO-SCRIPT.md').write_text(md,encoding='utf-8')


def reflections():
    paragraphs=[
        ('1. Provenance and materials',
         'These exercises were carried out by the ongoing project coding assistant on 26 October 2026 in a disposable '
         'copy of the project. The assistant had access to the Lab 4 instructions, the codebase and tests. It had previously '
         'seen the implementation in the conversation, so this was not a blind or fresh-session assessment. The exact model '
         'identifier is not asserted. The operational instruction brief is saved in ai-exercises/INSTRUCTIONS.md; it is not '
         'presented as a separately typed student message or an invented chat transcript.'),
        ('2. Exercise 3.3.2 - regenerate the control class',
         'After initial controller tests passed, the entire RecommendationController class was removed from the scratch '
         'module. Its supporting helpers and the frozen controller tests were supplied. Test discovery then failed with '
         'ImportError, confirming that the class was absent. The working implementation was never deleted from the active project.'),
        ('Prompting and iteration',
         'The instruction specified the constructor and recommend(request) API, separate forecast/current rankings, '
         'eligibility rules, audit behavior and a prohibition on changing tests or calling real services. The first generated '
         'replacement preserved the tested business outcomes but the wider suite reported seven errors: scoring_weights '
         'and fallback_scoring_policy response metadata had been omitted. Feedback from these actual failures led to a '
         'second iteration adding the two fields; the unchanged 150-method regression suite then passed.'),
        ('Outcome and reflection',
         'The regeneration met the observable test contract after one feedback iteration. It showed why testing only '
         'the final winner is insufficient: response metadata is also consumed by callers. Frozen tests made that omission '
         'visible. Passing this suite does not establish full behavioral equivalence or show that an agent with no prior '
         'context would succeed. Future exercises could use a fresh context and additional independently designed holdout '
         'cases. The regenerated class remains experiment evidence; the mechanically refactored working implementation was retained.'),
        ('3. Exercise 3.3.3 - refactor and regression-check',
         'The further experiment was a focused refactoring review. The recommendation flow was implemented as a module '
         'function while the design described a recommendation control class. The assistant was instructed to move this '
         'coordination into one small RecommendationController, retain recommend(...) as a compatibility entry point, '
         'and leave collection, tariffs, routes and scoring in their existing helpers. The complete current code and '
         'regression tests were available; no new framework or service process was requested.'),
        ('Outcome and reflection',
         'The controller now owns the existing orchestration and has documented constructor/method contracts. The HTTP '
         'route and older tests still use the compatibility function, which delegates to it. Current regression passed '
         '151 backend methods, including the later request-boundary test. Sixteen controller cases plus eighteen request '
         'boundaries are documented alongside supporting scoring/path cases. Reconciliation also revealed an independent '
         'configuration integration defect: the new operator environment names were missing from the loader whitelist. '
         'That was corrected and covered by a regression test. No tariff, model weights or database schema was changed.'),
        ('Practical assessment',
         'The refactoring improved traceability and made the control-class testing target explicit without adding an '
         'ORM, repository hierarchy or dependency container. The cost was one compatibility wrapper and a class that '
         'still coordinates a sizeable method; further splitting should be driven by concrete maintenance needs. Automated '
         'tests and the Android build are reproducible evidence, while physical-phone acceptance and the team recording '
         'remain separate work. The team should review these technical reflections against its own experience before submission.'),
    ]
    story=[para('Coding-Agent Exercise Reflections','TitleLab'),para(DATE+' | Lab 4 procedures 3.3.2-3.3.4.'),
           para('This report describes executed work and its limitations. Raw input/output is not required by the manual; '
                'the instruction brief, generated class, frozen tests and actual failure/success records are retained for review.')]
    md=['# Coding-agent exercise reflections\n\n'+DATE+'\n']
    for index,(heading,text) in enumerate(paragraphs):
        if heading.startswith('3.'): story.append(PageBreak())
        story += [para(heading,'HeadingLab'),para(text)]
        md += ['\n## '+heading+'\n',text+'\n']
    story += [para('Evidence locations','HeadingLab'),table(['Record','Purpose'],[
        ('evidence/reconstruction-red.json','Entire-class removal and actual ImportError.'),
        ('evidence/reconstruction-iteration-1.json','Actual first generated attempt: seven response-metadata errors.'),
        ('evidence/reconstruction-green.json','Second attempt: unchanged 150-method suite passes.'),
        ('ai-exercises/reconstructed_controller.py','Final generated replacement, kept outside production.'),
        ('ai-exercises/frozen_controller_tests.py','Exact controller-test snapshot supplied during the exercise.'),
        ('evidence/refactor.json; evidence/test-results.json','Refactor scope, hashes and current 151-method / 88-case results.'),
    ],[1,1.5])]
    pdf('Coding-Agent-Reflections.pdf','ParkChoiceSG Lab 4 - Coding-Agent Reflections',story)
    (HERE/'AI-EXERCISES.md').write_text('\n'.join(md),encoding='utf-8')


def index_and_traceability():
    coverage=[
        ('UC-01 recommendation','RecommendationController; TripRequest; pricing/model/scoring adapters',
         'CTL-01..16; REQ-01..18; scoring EC/BV; mode tests','Implemented search, with documented cohort limits'),
        ('UC-02 inspect carpark','Search result cards; price/source/forecast payload',
         'Flutter parking_search_test and parking_api_response_test','Implemented result inspection; full planned detail flow remains partial'),
        ('UC-03 navigation; UC-19 map','carpark_map_screen; navigation_handoff; device_location',
         'Flutter map_stability, location_and_navigation, device_location tests; AND-03/06','Automated fixtures passed; physical handoff pending'),
        ('UC-05 operator sign-in','operator_auth; /operator/login; OperatorLoginScreen / OperatorSession',
         'test_operator_auth; operator_login_test','Credential check and UI gate implemented; not a server session/authorization system'),
        ('UC-10 collection','data-pipeline collectors and cleaning/export contracts',
         'Collector, provider, metadata, refresh and export regression modules','Implemented separately; teammate operates collection'),
        ('UC-11 preferences / UC-12 saved places','PreferencesScreen; theme controller',
         'Flutter lifecycle/stress/theme tests','Theme persists; other controls retain prototype scope'),
        ('UC-14..17 parking tracker/history','ParkingSessionManager and tracker UI',
         'Flutter lifecycle/stress tests','In-memory/prototype behavior; not durable session history'),
        ('UC-04/06/07/08/09/13/18 remaining scope','Planned reports, admin operations, favourites and full erasure',
         'Do not infer real backend coverage from prototype UI tests','Not complete; keep visible in the implementation-gap record'),
    ]
    (HERE/'TRACEABILITY.md').write_text('# Requirements to code and tests\n\n'+md_table(
        ['Use case','Implementation','Test evidence','Status'],coverage)+'\n',encoding='utf-8')
    checks=[
        ('Working source and prototype','Prepared','Use backend/, parkchoice_flutter/, data-pipeline/ and ml/. Source ZIP and Android debug APK are local review artifacts.'),
        ('Black-box and basis-path evidence','Prepared','88 recorded cases; 151 backend methods; two verified eight-path graphs.'),
        ('Demo script','Prepared','15-minute Android sequence and five-minute recording script.'),
        ('Coding-agent PDF','Prepared for team review','Executed reconstruction/refactor exercises, with prior-context and iteration details disclosed.'),
        ('On-phone acceptance','Pending','No Android device connected. Complete AND-01..10 and record actual outcomes.'),
        ('Demo video','Pending','Record the real Android app, review it and add the actual video/link.'),
        ('Work-product attribution','Pending','Names omitted as requested. Lab 4 section 3.5.2 requires attribution before final delivery.'),
        ('Team review / GitHub publication','Pending','Check scope, source changes, test evidence and role allocation. This task does not push automatically.'),
        ('Lab 5 final models/SRS','Follow-up','Update final diagrams/SRS against accepted code; retain implementation-gap statements until features exist.'),
    ]
    (HERE/'CHECKLIST.md').write_text('# Lab 4 completion checklist\n\n'+md_table(['Item','Status','Action'],checks)+'\n',encoding='utf-8')
    (HERE/'README.md').write_text('''# Lab 4 review package

Prepared 26 October 2026 from upstream main `790ac78`, reconciled with the newer
local ranking/frontend work. Application code stays in the permanent working
directories; this folder contains submission evidence and review documents.

| File | Purpose |
|---|---|
| [Testing report](output/pdf/Testing-Report.pdf) | Partitions, boundaries, actual results and verified basis-path graphs. |
| [Android demo script](output/pdf/Android-Demo-Script.pdf) | Live sequence, phone setup/recovery and recording plan. |
| [Coding-agent reflections](output/pdf/Coding-Agent-Reflections.pdf) | Two executed experiments, iterations, outcomes and limits. |
| [Source snapshot](submission/ParkChoiceSG-Lab4-Source.zip) | Curated source/model/assets; no private config, captures or generated builds. |
| [Android arm64 debug APK](submission/ParkChoiceSG-debug-arm64.apk) | Phone prototype built for API URL http://127.0.0.1:8000 with USB reverse. |
| [Traceability](TRACEABILITY.md) | Use cases to implementation and actual test coverage. |
| [Completion checklist](CHECKLIST.md) | Remaining phone checks, video, attribution and team review. |

Editable reports are the Markdown files in this folder. Machine-readable rows,
source hashes and experiment records are under `evidence/`; diagram sources and
PNG/SVG exports are under `diagrams/`. `tmp/` is ignored experiment scratch space.

Reproduce offline evidence using the backend Python environment:

```powershell
python lab4/collect_evidence.py
```

Regenerate PDFs with `python lab4/prepare_deliverables.py` in an environment with
reportlab, Pillow, pypdf and PyMuPDF, plus Java and the local PlantUML jar configured in
that script. Use the installed PDF authoring workflow before regeneration.

This is a review package, not a claim that all planned features or device checks
are complete. Operator sign-in checks credentials and gates a prototype console;
admin actions are not authenticated server operations. The actual Android device
acceptance and five-minute video remain pending. Author names are intentionally
omitted for now, as requested. No GitHub push is performed by this generator.
''',encoding='utf-8')


def main():
    PDFS.mkdir(parents=True,exist_ok=True)
    report=json.loads((HERE/'evidence/test-results.json').read_text())
    flow_diagrams(report)
    testing(report);demo();reflections();index_and_traceability()
    print('Created three portrait PDF reports and editable sources under lab4/.')


if __name__=='__main__':
    main()
