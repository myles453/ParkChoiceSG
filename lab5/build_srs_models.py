"""Build the final use-case/descriptions/diagram PDF and editable diagram exports.

Requires Python with reportlab, svglib and PyMuPDF, plus Java and PlantUML.
This command reads source documentation only; it does not call application APIs.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import subprocess

import pymupdf
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, NextPageTemplate, Flowable,
)
from reportlab.graphics import renderPDF
from svglib.svglib import svg2rlg

from models.use_cases import CASES, REVISION
from models.diagrams import DIAGRAMS, STYLE

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIGURES = HERE/'diagrams'
OUT = HERE/'output/pdf'
MARGIN = 36
INK = colors.HexColor('#183545')
TEAL = colors.HexColor('#087F8C')
PALE = colors.HexColor('#F0F5F7')
LINE = colors.HexColor('#C9D7DE')

for name, filename in [('Arial','arial.ttf'),('Arial-Bold','arialbd.ttf'),('Arial-Italic','ariali.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(Path('C:/Windows/Fonts')/filename)))
pdfmetrics.registerFontFamily('Arial',normal='Arial',bold='Arial-Bold',italic='Arial-Italic')

STYLES = getSampleStyleSheet()
STYLES.add(ParagraphStyle(name='TitleFinal',fontName='Arial-Bold',fontSize=29,leading=34,textColor=INK,spaceAfter=18))
STYLES.add(ParagraphStyle(name='HeadingFinal',fontName='Arial-Bold',fontSize=19,leading=23,textColor=INK,spaceAfter=13))
STYLES.add(ParagraphStyle(name='BodyFinal',fontName='Arial',fontSize=10,leading=14,textColor=INK,spaceAfter=8))
STYLES.add(ParagraphStyle(name='SmallFinal',fontName='Arial',fontSize=8.8,leading=11.5,textColor=INK,spaceAfter=5))
STYLES.add(ParagraphStyle(name='CellFinal',fontName='Arial',fontSize=9,leading=11.7,textColor=INK))
STYLES.add(ParagraphStyle(name='CellLabel',parent=STYLES['CellFinal'],fontName='Arial-Bold'))
STYLES.add(ParagraphStyle(name='CaptionFinal',fontName='Arial',fontSize=9.5,leading=13,textColor=INK,spaceBefore=10,spaceAfter=7))


def p(text, style='BodyFinal'):
    return Paragraph(html.escape(str(text)).replace('\n','<br/>'),STYLES[style])


def table(rows, widths, header=False):
    data=[]
    for index,row in enumerate(rows):
        data.append([p(value,'CellLabel' if (header and index==0) or (not header and j==0) else 'CellFinal')
                     for j,value in enumerate(row)])
    t=Table(data,colWidths=widths,repeatRows=1 if header else 0,hAlign='LEFT')
    commands=[('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),
              ('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),6),
              ('BOTTOMPADDING',(0,0),(-1,-1),6),('GRID',(0,0),(-1,-1),0.4,LINE)]
    if header:
        commands += [('BACKGROUND',(0,0),(-1,0),PALE)]
    else:
        commands += [('BACKGROUND',(0,0),(0,-1),PALE)]
    t.setStyle(TableStyle(commands))
    return t


def page_header(c, doc):
    width,height=c._pagesize
    c.saveState()
    c.setStrokeColor(LINE);c.line(MARGIN,height-29,width-MARGIN,height-29)
    c.setFont('Arial',8);c.setFillColor(INK)
    c.drawString(MARGIN,height-21,'PARKCHOICESG | FINAL USE-CASE AND DESIGN MODELS')
    c.drawRightString(width-MARGIN,20,f'{REVISION}  |  {doc.page}')
    c.restoreState()


class ModelDoc(BaseDocTemplate):
    def afterFlowable(self, flow):
        if isinstance(flow,Paragraph) and flow.style.name in {'HeadingFinal','TitleFinal'}:
            title=flow.getPlainText()
            key=f'section-{len(self.sections)}'
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(title,key,0,False)
            self.sections.append({'title':title,'page':self.page})


class VectorFigure(Flowable):
    def __init__(self,path,width,height):
        Flowable.__init__(self)
        self.drawing=svg2rlg(str(path))
        if self.drawing is None:raise ValueError(f'Cannot load {path.name}')
        factor=min(width/self.drawing.width,height/self.drawing.height)
        self.width=self.drawing.width*factor
        self.height=self.drawing.height*factor
        self.drawing.scale(factor,factor)
        self.hAlign='CENTER'

    def draw(self):
        renderPDF.draw(self.drawing,self.canv,0,0)


def render_diagrams(jar):
    FIGURES.mkdir(parents=True,exist_ok=True)
    sources=[]
    for name,title,paths,body,caption in DIAGRAMS:
        path=FIGURES/f'{name}.puml'
        path.write_text('@startuml\n'+STYLE+body+'\n@enduml\n',encoding='utf-8')
        sources.append(str(path))
    subprocess.run(['java','-jar',str(jar),'-charset','UTF-8','-checkonly',*sources],check=True,capture_output=True)
    subprocess.run(['java','-jar',str(jar),'-charset','UTF-8','-tsvg',*sources],check=True,capture_output=True)
    from layouts import render_manual
    render_manual(FIGURES)
    for name,*_ in DIAGRAMS:
        svg=(FIGURES/f'{name}.svg').read_bytes()
        assert b'Syntax Error' not in svg
        image=pymupdf.open(stream=svg,filetype='svg')
        image[0].get_pixmap(matrix=pymupdf.Matrix(1.5,1.5),alpha=False).save(FIGURES/f'{name}.png')
        image.close()


def numbered(lines):
    return '\n'.join(f'{i}. {line}' for i,line in enumerate(lines,1))


def build_pdf():
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/'ParkChoiceSG-Final-SRS-Models.pdf'
    doc=ModelDoc(str(path),pagesize=A4,leftMargin=MARGIN,rightMargin=MARGIN,
                 topMargin=43,bottomMargin=35,title='ParkChoiceSG Final Use-Case and Design Models',
                 author='ParkChoiceSG',subject='Final implementation models and requirements status')
    doc.sections=[]
    portrait=Frame(MARGIN,35,A4[0]-2*MARGIN,A4[1]-78,id='portrait-frame',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
    wide=landscape(A4)
    diagram=Frame(MARGIN,35,wide[0]-2*MARGIN,wide[1]-78,id='diagram-frame',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id='portrait',frames=portrait,onPage=page_header,pagesize=A4),
                          PageTemplate(id='diagram',frames=diagram,onPage=page_header,pagesize=wide)])
    story=[Spacer(1,80),p('Final Use-Case\nand Design Models','TitleFinal'),
           p('ParkChoiceSG','HeadingFinal'),p('Software Requirements Specification supporting material'),
           p(f'Final implementation baseline | {REVISION}'),Spacer(1,25),
           p('This document supplies the use-case descriptions, class relationships, dialog maps, architecture and request sequences for the final implementation. It is intended for inclusion in the final SRS and design documentation.'),
           p('Implemented, partial/prototype and deferred requirements are identified explicitly. Planned behavior is not presented as a completed capability.'),
           Spacer(1,18),p('Reading order','HeadingFinal'),
           p('1. Scope and requirement inventory\n2. Complete use-case descriptions (UC-01 to UC-19)\n3. Use-case, class, data, architecture, sequence and UI-state diagrams\n4. Scoring, evidence fields and implementation traceability'),PageBreak(),
           p('Final scope and model conventions','HeadingFinal'),
           p('ParkChoiceSG compares nearby carparks using routed driving/walking measurements, source-backed stay prices and the probability of at least one free HDB car lot at arrival. Drivers are anonymous. Operator access is a separate configured-credential check.'),
           p('The working recommendation is implemented in the root backend/, parkchoice_flutter/, data-pipeline/ and ml/ directories. Experimental LTA/URA models are not enabled in application probability ranking. Older lab artifacts remain historical design material.'),
           table([['Label','Meaning'],['Implemented','Connected application or collection behavior with the stated service, source and model limits.'],
                  ['Partial / prototype','A real control/component exists, but effects may be local, sample-based or incomplete.'],
                  ['Deferred','The requirement is retained for traceability; its intended behavior is not implemented.']], [110,413],True),Spacer(1,13),
           p('Diagram conventions'),
           p('UML classes identify actual class names, values and Protocols. Module functions and database records are labelled separately. Solid links represent associations; dotted arrows represent dependencies; interface realization uses a dashed hollow triangle. Multiplicities describe actual ownership/cardinality. Key classes are shown in detail; secondary fields and helper methods may be omitted.'),
           p('Dialog transitions use event [guard] / action where applicable. Sample or screen-local effects are stated on the diagram. Navigation, search and parking-session creation are separate actions.'),
           p('The native source for every diagram is supplied as PlantUML, with SVG and PNG exports. Landscape diagram pages retain legible labels; use-case tables use portrait pages.'),PageBreak(),
           p('Use-case inventory','HeadingFinal'),
           table([['ID','Use case','Final status']]+[[c['id'],c['name'],c['status']] for c in CASES],[45,223,255],True),
           Spacer(1,10),p('UC identifiers are preserved from the earlier requirements. Partial/deferred requirements remain visible rather than being silently removed.'),PageBreak()]
    orientations={}
    for name,*_ in DIAGRAMS:
        drawing=svg2rlg(str(FIGURES/f'{name}.svg'))
        tall_scale=min((A4[0]-2*MARGIN)/drawing.width,(A4[1]-190)/drawing.height)
        wide_scale=min((wide[0]-2*MARGIN)/drawing.width,(wide[1]-190)/drawing.height)
        orientations[name]='portrait' if tall_scale>wide_scale else 'diagram'
    for case_index,case in enumerate(CASES):
        story.append(p(f"{case['id']} - {case['name']}",'HeadingFinal'))
        rows=[('Revision / owner',f'{REVISION}; ParkChoiceSG'),
              ('Status',case['status']),('Goal / actors',case['goal']+'\nActors: '+case['actors']),
              ('Priority / frequency',case['priority']+' / '+case['frequency']),
              ('Trigger', 'The collection operator/scheduler starts a configured capture.' if case['id']=='UC-10' else 'The actor invokes the named action or opens its app control.'),
              ('Preconditions',case['preconditions']),('Main flow',numbered(case['flow'])),
              ('Alternatives / exceptions',numbered(case['alternatives'])),
              ('Postconditions',case['postconditions']),('Special requirements / assumptions',case['limits'])]
        story.append(table(rows,[107,416]))
        if case_index==len(CASES)-1:story.append(NextPageTemplate(orientations[DIAGRAMS[0][0]]))
        story.append(PageBreak())
    for index,(name,title,paths,body,caption) in enumerate(DIAGRAMS):
        size=A4 if orientations[name]=='portrait' else wide
        story += [p(f'Figure {index+1}. {title}','HeadingFinal'),
                  VectorFigure(FIGURES/f'{name}.svg',size[0]-2*MARGIN,size[1]-190),
                  p(caption,'CaptionFinal'),p('Implementation reference: '+paths,'SmallFinal')]
        story.append(NextPageTemplate('portrait' if index==len(DIAGRAMS)-1 else orientations[DIAGRAMS[index+1][0]]))
        story.append(PageBreak())
    story += [p('Recommendation scoring and eligibility','HeadingFinal'),
              p('Eligibility is evaluated before scoring. Valid driving/walking routes, supported current tariffs, coherent identity/capacity evidence and an acceptable forecast are required. Enabled HDB forecasts use short mode at 15-90 minutes, recent source history no older than 15 minutes, consistent confidence/model metadata, and p_free >= 0.90.'),
              table([['Mode','Cost','Walk','Availability','Drive'],['Best overall','40%','30%','20%','10%'],['Prioritise cheaper','65%','15%','15%','5%'],['Prioritise closer','15%','65%','15%','5%']], [175,87,87,87,87],True),Spacer(1,15),
              p('Each nonnegative factor becomes a bounded penalty. Let C be cost in cents, D the stay duration in minutes, W the walking route distance in metres, T the driving duration in seconds, and p the arrival free-lot probability.'),
              table([['Penalty','Implemented formula'],['Cost','C / (C + 400 * D / 60)'],['Walking','W / (W + 500)'],['Driving','T / (T + 900)'],['Forecast availability','1 - p'],['Current-only availability','1 / (1 + current available lots)'],['Final score','100 * (1 - sum(weight * penalty))']], [150,373],True),Spacer(1,12),
              p('Higher scores rank first. Ties use walking then cost in Closer mode, cost then walking in other modes, followed by driving duration and canonical identity. Fixed scales avoid changing pairwise penalties when another candidate appears. Weights/scales are an explicit project policy, not claimed optimal driver preferences.'),
              p('Current-only fallback is a separate list with a visible notice. It requires fresh source-timestamped positive current counts, usable routes/prices and an allowed missing-forecast reason. A known low probability is not promoted into fallback. A failed candidate is not automatically replaced.'),PageBreak(),
              p('Evidence and data dictionary','HeadingFinal'),
              table([['Field / concept','Meaning and constraint'],
                     ['Canonical identity','(agency, carpark_id). Source codes map only using exact reviewed identity or an explicit verified mapping.'],
                     ['latitude / longitude','Finite WGS84 decimal degrees. A single supported point is required for routing. Multiple/ambiguous geometries remain flagged.'],
                     ['lots_available / total_lots','Current counts. HDB capacity is synchronized with its reading; LTA/URA feeds do not provide equivalent total capacity or per-carpark source times.'],
                     ['evidence_at / retrieved_at','Observation/source time and retrieval time have different semantics. A retrieval proxy is labelled as such.'],
                     ['issued_at / arrival_at','Forecast issue time and candidate-specific target arrival. Preserve the service issue time; do not relabel it as request time.'],
                     ['history_cutoff','Latest source history used by the forecast; it must precede issue time and pass the freshness limit.'],
                     ['p_free / confidence','Probability of at least one free lot. High >= 0.99; Medium >= 0.90 and < 0.99; Low < 0.90. It is not a predicted count or reservation guarantee.'],
                     ['amount_cents / range','Full-stay supported estimate, source URL and schedule ID. Compare neighbouring-minute arrivals and score the higher supported quote.'],
                     ['schedule validity / review','Version valid_from/valid_until and review metadata. HDB/commercial review limit: 30 days; URA: 2 days. Changed facility flags and unresolved windows can block a quote.'],
                     ['ranking_exclusions','Machine-readable reasons a candidate did not qualify; unavailable measurements are not replaced with zeros.'],
                     ['Device-local state','Only appearance is durably stored in the current preferences implementation. Sessions, local saved labels and console samples do not form backend driver-profile tables.']], [135,388],True),PageBreak(),
              p('Implementation and test traceability','HeadingFinal'),
              table([['Requirement','Source components','Test evidence'],
                     ['UC-01, UC-02','recommendation.py; comparison.py; pricing.py; scoring.py; CarparkSearchScreen; ParkingApi','backend/validation/test_workflow.py, test_lab4_controller.py, test_ranking_modes.py, test_pricing.py, test_current_fallback.py; Flutter parking_search_test.dart, parking_api_response_test.dart'],
                     ['UC-03, UC-19','CarparkMapScreen; navigation_handoff.dart; device_location.dart','Flutter location_and_navigation_test.dart, map_stability_test.dart, device_location_test.dart'],
                     ['UC-05','OperatorLoginScreen; OperatorSession; app.operator_login; operator_auth.py','test_operator_auth.py; Flutter operator_login_test.dart'],
                     ['UC-10','collect_live.py; collect_periodic.py; puller.py; provider_puller.py; metadata_cleaner.py; export_training.py','test_collect_periodic.py, test_puller.py, test_provider_puller.py, test_metadata_cleaner.py, test_export_training.py, test_refresh_pricing.py'],
                     ['UC-11, UC-12, UC-14-18 partial UI','AppThemeController; PreferencesScreen; ParkingSessionManager; Tracker','Flutter widget_test.dart, frontend_lifecycle_test.dart, frontend_stress_test.dart. UI checks do not establish unimplemented durable storage/notifications.'],
                     ['UC-04, UC-13 and server administration','Deferred or sample-only components','No claim of complete backend acceptance coverage.']], [70,200,253],True),Spacer(1,13),
              p('The submission branch includes executable tests and dated result evidence. Test fixtures verify behavior and failure handling; live source availability, route/provider health, physical-device acceptance and prediction accuracy are separate checks. Model evaluation is retained under ml/reports/; the model is not retrained by building this document.'),
              p('The final SRS should retain the partial/deferred requirement statuses in this document. Do not describe sample console health, feedback-only refresh, incomplete erasure or local session history as working persisted backend features.')]
    doc.build(story)
    with pymupdf.open(path) as check:
        pages=len(check)
        texts=[page.get_text() for page in check]
        assert all(t.strip() for t in texts), 'Unexpected blank page'
        for case in CASES:assert any(case['id']+' - '+case['name'] in t for t in texts)
    manifest={'revision':REVISION,'pdf':path.name,'pages':pages,'use_cases':len(CASES),'diagrams':len(DIAGRAMS),
              'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'sections':doc.sections}
    (HERE/'models/MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    (HERE/'models/USE-CASE-DESCRIPTIONS.json').write_text(json.dumps(CASES,indent=2)+'\n',encoding='utf-8')
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plantuml-jar',type=Path,default=Path.home()/'.cache/parkchoice-tools/plantuml.jar')
    parser.add_argument('--skip-render',action='store_true')
    args=parser.parse_args()
    if not args.skip_render:render_diagrams(args.plantuml_jar)
    print(json.dumps(build_pdf(),indent=2))


if __name__=='__main__':main()
