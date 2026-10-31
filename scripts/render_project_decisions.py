"""Render the Markdown decision record as a self-contained, offline HTML reader.

Run from the repository root: python scripts/render_project_decisions.py
Install the document-only build dependency with: python -m pip install Markdown==3.7
"""
from pathlib import Path
import hashlib
import html
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
try:
    import markdown
except ImportError:
    sys.exit('Install the document dependency first: python -m pip install Markdown==3.7')


CSS = r'''
:root {
  color-scheme: light;
  --paper:#fff; --surface:#fff; --ink:#000; --muted:#000;
  --line:#000; --green:#000; --green-soft:#fff; --header:#fff;
  --code:#fff; --amber:#000; --amber-soft:#fff;
  --mark:#fff; --mark-ink:#000; --active-mark:#000;
  --rail:282px; --shadow:none;
}
* {box-sizing:border-box}
html {scroll-behavior:smooth; scroll-padding-top:108px}
body {margin:0; background:var(--paper); color:var(--ink); font:16px/1.8 "Segoe UI",Arial,sans-serif}
button,input {font:inherit}
button,a,input {-webkit-tap-highlight-color:transparent}
a {color:var(--green); text-decoration-thickness:1px; text-underline-offset:3px}
a:hover {text-decoration-thickness:2px}
button {cursor:pointer}
button:focus-visible,a:focus-visible,input:focus-visible,summary:focus-visible,.table-scroll:focus-visible {
  outline:3px solid var(--green); outline-offset:4px;
}
[hidden] {display:none!important}
.skip-link {position:fixed;top:-70px;left:16px;z-index:100;background:var(--surface);padding:8px 18px}
.skip-link:focus {top:12px}
.sidebar {position:fixed;inset:0 auto 0 0;width:var(--rail);background:var(--surface);
  border-right:1px solid var(--line);display:flex;flex-direction:column;z-index:50}
.brand {padding:28px 23px 20px;border-bottom:1px solid var(--line)}
.brand-line {display:flex;align-items:center;gap:12px;text-decoration:none;color:var(--ink)}
.brand-mark {width:36px;height:36px;display:grid;place-items:center;background:var(--green);
  color:var(--surface);border-radius:10px;font-size:22px;font-weight:700;line-height:1}
.brand-name {font-size:17px;font-weight:700;letter-spacing:-.35px}
.brand-subtitle {margin:10px 0 0;font-size:12px;line-height:1.6;color:var(--muted)}
.contents-title {display:flex;align-items:center;justify-content:space-between;padding:17px 23px 4px;
  font-size:11px;font-weight:700;letter-spacing:1.4px;text-transform:uppercase;color:var(--muted)}
.nav-scroll {overflow:auto;overscroll-behavior:contain;padding:0 12px 24px;scrollbar-width:thin}
.nav-group {margin:18px 10px 7px;font-size:10px;font-weight:700;letter-spacing:1px;
  text-transform:uppercase;color:var(--muted)}
.chapter-nav {list-style:none;margin:0;padding:0}
.chapter-nav a {display:flex;gap:10px;padding:9px 11px;border-radius:7px;text-decoration:none;
  color:var(--muted);font-size:12px;line-height:1.55;border:1px solid transparent}
.chapter-nav a:hover {color:var(--ink);background:var(--paper)}
.chapter-nav a[aria-current="location"] {color:var(--green);background:var(--green-soft);
  border-color:var(--line);font-weight:600}
.chapter-number {flex:0 0 18px;font-variant-numeric:tabular-nums;opacity:.75}
.sidebar-footer {margin-top:auto;padding:13px 23px;border-top:1px solid var(--line);
  font-size:11px;color:var(--muted);line-height:1.7}
.sidebar-footer a {display:inline-block;margin-top:4px}
.reader-shell {margin-left:var(--rail)}
.toolbar {position:sticky;top:0;z-index:20;background:var(--header);backdrop-filter:blur(12px);
  border-bottom:1px solid var(--line)}
.toolbar-inner {max-width:1040px;margin:auto;padding:14px 42px;display:flex;gap:12px;align-items:center}
.find-field {flex:1;min-width:100px;position:relative}
.find-field input {width:100%;height:42px;border:1px solid var(--line);border-radius:8px;
  background:var(--surface);color:var(--ink);padding:0 42px 0 14px;font-size:13px}
.find-field input::placeholder {color:var(--muted);opacity:1}
.clear-search {position:absolute;right:5px;top:5px;width:32px;height:32px;border:0;background:transparent;
  color:var(--muted);font-size:20px;border-radius:5px}
.reader-controls {display:flex;align-items:center;gap:5px;flex-shrink:0}
.match-count {font-size:11px;color:var(--muted);min-width:64px;text-align:center;font-variant-numeric:tabular-nums}
.tool-button {height:36px;min-width:36px;padding:0 10px;border:1px solid var(--line);border-radius:7px;
  background:var(--surface);color:var(--ink);font-size:12px;line-height:1;white-space:nowrap}
.tool-button:hover:not(:disabled) {background:var(--green-soft);color:var(--green)}
.tool-button:disabled {opacity:.35;cursor:default}
.mobile-menu,.close-menu {display:none}
.progress-track {height:2px;background:transparent}
.progress-fill {height:100%;width:0;background:var(--green);transition:width .08s linear}
.reading-position {max-width:1040px;padding:0 42px 8px;margin:auto;font-size:10px;line-height:1.3;
  color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.document {max-width:1040px;margin:auto;padding:55px 60px 95px;min-width:0}
.eyebrow {font-size:10px;letter-spacing:1.8px;font-weight:700;color:var(--green);margin-bottom:14px}
h1 {font-size:clamp(30px,3.2vw,44px);line-height:1.16;letter-spacing:-1.35px;font-weight:650;
  margin:0 0 20px;max-width:800px;text-wrap:balance}
.context-date {font-size:12px;color:var(--muted);margin:0 0 20px}
.intro-lead {font-size:17px;line-height:1.8;margin-bottom:23px}
.product-summary {border-left:3px solid var(--green);padding:2px 0 2px 22px;margin:24px 0 27px;
  color:var(--ink);font-size:16px}
.product-summary p {margin:0}
.quick-links {display:flex;flex-wrap:wrap;gap:8px;margin:24px 0}
.quick-links a {padding:6px 12px;border:1px solid var(--line);border-radius:6px;font-size:12px;
  text-decoration:none;background:var(--surface)}
.quick-links a:hover {border-color:var(--green);background:var(--green-soft)}
.reading-guide {margin:26px 0 18px;padding:15px 18px;border:1px solid var(--line);border-radius:9px;background:var(--surface)}
.reading-guide summary {cursor:pointer;font-size:13px;font-weight:600;color:var(--green)}
.reading-guide[open] summary {margin-bottom:16px}
.reading-guide .guide-content {font-size:14px;line-height:1.8;color:var(--muted)}
.chapter {margin-top:60px;padding-top:38px;border-top:1px solid var(--line);scroll-margin-top:110px}
h2 {font-size:27px;line-height:1.35;font-weight:650;letter-spacing:-.6px;margin:0 0 28px;text-wrap:balance}
h3 {font-size:19px;line-height:1.5;font-weight:650;letter-spacing:-.15px;margin:36px 0 15px;scroll-margin-top:110px}
.decision-id {display:inline-block;font-size:11px;letter-spacing:.3px;font-weight:650;color:var(--green);
  background:var(--green-soft);border:1px solid var(--line);border-radius:5px;padding:2px 7px;
  vertical-align:2px;white-space:nowrap;margin-right:5px}
p {margin:0 0 18px;overflow-wrap:break-word}
strong {font-weight:650}
ul,ol {padding-left:24px;margin:15px 0 23px}
li {padding-left:4px;margin:9px 0}
li p {margin:0}
.status-line {font-size:14px;color:var(--muted);line-height:1.8}
.status-line>strong:first-child {display:inline;padding:2px 5px 3px;border-radius:4px;
  background:var(--green-soft);color:var(--green);font-size:12px;margin-right:3px}
.status-line.policy>strong:first-child {color:var(--amber);background:var(--amber-soft)}
.status-line.planned>strong:first-child {color:var(--muted);background:var(--code)}
blockquote {margin:25px 0;padding:14px 22px;border-left:3px solid var(--green);background:var(--green-soft);
  color:var(--green);font-size:17px;line-height:1.75}
blockquote p:last-child {margin-bottom:0}
code {background:var(--code);padding:2px 5px;border-radius:4px;font: .86em/1.5 Consolas,"Courier New",monospace}
pre {overflow:auto;background:var(--code);border:1px solid var(--line);border-radius:9px;padding:24px;
  font:13px/1.85 Consolas,"Courier New",monospace;margin:25px 0;tab-size:4;white-space:pre}
pre code {padding:0;background:transparent;font:inherit;color:var(--ink)}
.table-scroll {max-width:100%;overflow-x:auto;margin:26px 0 30px;border:1px solid var(--line);
  border-radius:8px;background:var(--surface);scrollbar-width:thin}
table {border-collapse:collapse;width:100%;min-width:520px;font-size:13px;line-height:1.7}
th {text-align:left;background:var(--green-soft);color:var(--green);font-size:11px;font-weight:650;padding:13px 15px}
td {padding:14px 15px;border-top:1px solid var(--line);vertical-align:top;overflow-wrap:anywhere}
th:first-child,td:first-child {padding-left:18px}
tbody tr:hover {background:var(--paper)}
td code {font-size:11px;overflow-wrap:anywhere}
.weights-table th:not(:first-child),.weights-table td:not(:first-child) {text-align:center;font-variant-numeric:tabular-nums}
.weights-table .weight-primary {font-weight:700;color:var(--green);background:var(--green-soft)}
td strong {color:var(--green)}
mark {background:var(--mark);color:var(--mark-ink);text-decoration:underline;text-decoration-thickness:2px;border-radius:2px;padding:0;scroll-margin-top:125px}
mark.current-match {background:var(--active-mark);color:#fff;outline:2px solid var(--amber);outline-offset:1px}
.document-footer {margin-top:65px;padding-top:25px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}
.to-top {position:fixed;bottom:20px;right:23px;padding:6px 13px;font-size:11px;background:var(--surface);
  border:1px solid var(--line);border-radius:20px;text-decoration:none;box-shadow:var(--shadow);z-index:15}
.backdrop {display:none}
.sr-only {position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
@media(min-width:1600px) {.document {padding-top:65px} body {font-size:17px}}
@media(max-width:1220px) { :root {--rail:250px} .document {padding:40px 35px 80px}.toolbar-inner {padding-inline:30px}.reading-position {padding-inline:30px}h1{font-size:36px}}
@media(max-width:980px) {
  :root {--rail:282px}
  .sidebar {transform:translateX(-100%);transition:transform .2s ease;width:min(310px,88vw)}
  .sidebar.open {transform:translateX(0)}
  .reader-shell {margin-left:0}
  .mobile-menu,.close-menu {display:inline-block}
  .mobile-menu {font-weight:600}
  .close-menu {height:32px;min-width:32px}
  .backdrop:not([hidden]) {display:block;position:fixed;inset:0;background:rgba(0,0,0,.35);border:0;z-index:40}
  .document {max-width:850px;padding:40px 36px 80px}
  .toolbar-inner,.reading-position {max-width:850px;padding-inline:25px}
}
@media(max-width:600px) {
  body {font-size:15px;line-height:1.85}
  .document {padding:30px 21px 75px}
  .toolbar-inner {padding:11px 16px 7px;display:block}
  .find-field {width:100%;margin-bottom:9px}
  .find-field input {height:42px;font-size:16px}
  .reader-controls {justify-content:space-between;gap:5px}
  .tool-button {min-width:42px;height:39px;font-size:12px;padding-inline:10px}
  .mobile-menu {padding-inline:12px}
  .match-count {flex:1;min-width:45px;font-size:10px}
  .print-button {display:none}
  .reading-position {padding:0 17px 8px;font-size:9px}
  h1 {font-size:31px;letter-spacing:-.9px}
  h2 {font-size:24px;line-height:1.4}
  h3 {font-size:18px;margin-top:30px}
  .chapter {margin-top:42px;padding-top:30px;scroll-margin-top:147px}
  html {scroll-padding-top:145px}
  h3,mark {scroll-margin-top:147px}
  .intro-lead,.product-summary {font-size:15px}
  .product-summary {padding-left:17px}
  .quick-links a {font-size:11px;padding:6px 9px}
  .reading-guide {padding:12px 14px}
  .reading-guide .guide-content {font-size:13px}
  pre {padding:18px;font-size:12px}
  th,td {padding:11px 12px}
  .to-top {right:14px;bottom:13px}
}
@media(prefers-reduced-motion:reduce) {html {scroll-behavior:auto}*,*::before,*::after {transition:none!important}}
@media print {
  :root {color-scheme:light}
  body {background:#fff;font-size:10pt;line-height:1.55}
  .sidebar,.toolbar,.quick-links,.to-top,.backdrop,.skip-link {display:none!important}
  .reader-shell {margin:0}.document {max-width:none;padding:0}
  h1 {font-size:24pt}h2 {font-size:17pt}h3 {font-size:12pt}
  .chapter {margin-top:25px;padding-top:18px}
  h2,h3 {break-after:avoid}p,li {orphans:3;widows:3}
  .table-scroll {overflow:visible;border-radius:0}table {min-width:0;font-size:8pt}
  th,td {padding:7px}tr {break-inside:avoid}thead {display:table-header-group}
  pre {white-space:pre-wrap;font-size:8pt;padding:12px}
  mark,mark.current-match {background:transparent;color:inherit;outline:none}
  .document-footer {margin-top:25px}
  @page {margin:17mm}
}
'''


JS = r'''
(() => {
  const article=document.getElementById('record');
  const sidebar=document.getElementById('sidebar');
  const menuButton=document.getElementById('menu-button');
  const closeButton=document.getElementById('close-menu');
  const backdrop=document.getElementById('backdrop');
  const search=document.getElementById('document-search');
  const count=document.getElementById('match-count');
  const previous=document.getElementById('previous-match');
  const next=document.getElementById('next-match');
  const clear=document.getElementById('clear-search');
  const links=Array.from(document.querySelectorAll('.chapter-nav a'));
  const chapters=Array.from(article.querySelectorAll('.chapter'));
  let marks=[],matchIndex=-1,searchTimer,scrollScheduled=false;
  const small=()=>window.innerWidth<=980;
  function setMenu(open,restoreFocus=true) {
    const visible=small()&&open;
    sidebar.classList.toggle('open',visible);
    sidebar.inert=small()&&!visible;
    backdrop.hidden=!visible;
    menuButton.setAttribute('aria-expanded',String(visible));
    document.body.style.overflow=visible?'hidden':'';
    if(visible) closeButton.focus();
    else if(restoreFocus&&small()) menuButton.focus();
  }
  menuButton.addEventListener('click',()=>setMenu(!sidebar.classList.contains('open')));
  closeButton.addEventListener('click',()=>setMenu(false));
  backdrop.addEventListener('click',()=>setMenu(false));
  links.forEach(link=>link.addEventListener('click',()=>setMenu(false,false)));
  function updatePosition() {
    const max=document.documentElement.scrollHeight-innerHeight;
    const progress=max>0?Math.min(100,Math.max(0,scrollY/max*100)):0;
    document.getElementById('progress-fill').style.width=progress+'%';
    let active=null;
    for(const chapter of chapters) {
      if(chapter.getBoundingClientRect().top<(small()?175:135)) active=chapter;
      else break;
    }
    links.forEach(link=>{
      if(active&&link.hash==='#'+active.id) link.setAttribute('aria-current','location');
      else link.removeAttribute('aria-current');
    });
    document.getElementById('reading-position').textContent=active?active.querySelector('h2').textContent:'Overview · 48 decisions across 25 chapters';
    scrollScheduled=false;
  }
  addEventListener('scroll',()=>{
    if(!scrollScheduled){scrollScheduled=true;requestAnimationFrame(updatePosition)}
  },{passive:true});
  addEventListener('resize',()=>{setMenu(false,false);updatePosition()});
  setMenu(false,false);updatePosition();
  function removeMarks() {
    article.querySelectorAll('mark[data-search-match]').forEach(mark=>mark.replaceWith(document.createTextNode(mark.textContent)));
    article.normalize();marks=[];matchIndex=-1;
  }
  function refreshCount() {
    const capped=marks.length===500?'+':'';
    count.textContent=marks.length?(matchIndex+1)+' / '+marks.length+capped:(search.value.trim()?'No matches':'Find in record');
    previous.disabled=next.disabled=marks.length===0;
    clear.hidden=search.value.length===0;
  }
  function showMatch(index,scroll=true) {
    if(!marks.length) return;
    marks.forEach(mark=>mark.classList.remove('current-match'));
    matchIndex=(index+marks.length)%marks.length;
    const selected=marks[matchIndex];selected.classList.add('current-match');
    let parent=selected.parentElement;
    while(parent){if(parent.tagName==='DETAILS')parent.open=true;parent=parent.parentElement}
    if(scroll) selected.scrollIntoView({block:'center',behavior:'auto'});
    refreshCount();
  }
  function findText() {
    removeMarks();
    const query=search.value.trim();
    if(query) {
      const pattern=new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'gi');
      const walker=document.createTreeWalker(article,NodeFilter.SHOW_TEXT,{
        acceptNode:node=>node.parentElement.closest('script,style,button')||!node.textContent.trim()?NodeFilter.FILTER_REJECT:NodeFilter.FILTER_ACCEPT
      });
      const nodes=[];while(walker.nextNode())nodes.push(walker.currentNode);
      for(const node of nodes) {
        if(marks.length>=500)break;
        const text=node.textContent;pattern.lastIndex=0;
        let match,offset=0,found=false;const fragment=document.createDocumentFragment();
        while((match=pattern.exec(text))&&marks.length<500) {
          found=true;fragment.append(document.createTextNode(text.slice(offset,match.index)));
          const mark=document.createElement('mark');mark.dataset.searchMatch='';mark.textContent=match[0];
          fragment.append(mark);marks.push(mark);offset=match.index+match[0].length;
        }
        if(found){fragment.append(document.createTextNode(text.slice(offset)));node.replaceWith(fragment)}
      }
    }
    refreshCount();if(marks.length)showMatch(0);
  }
  search.addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(findText,180)});
  search.addEventListener('keydown',event=>{
    if(event.key==='Enter') {
      event.preventDefault();clearTimeout(searchTimer);
      if(!marks.length)findText();else showMatch(matchIndex+(event.shiftKey?-1:1));
    }
    if(event.key==='Escape'){search.value='';clearTimeout(searchTimer);removeMarks();refreshCount()}
  });
  next.addEventListener('click',()=>showMatch(matchIndex+1));
  previous.addEventListener('click',()=>showMatch(matchIndex-1));
  clear.addEventListener('click',()=>{search.value='';clearTimeout(searchTimer);removeMarks();refreshCount();search.focus()});
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape'&&sidebar.classList.contains('open'))setMenu(false);
    if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k') {event.preventDefault();search.focus();search.select()}
    if(event.key==='Tab'&&small()&&sidebar.classList.contains('open')) {
      const focusable=Array.from(sidebar.querySelectorAll('a,button')).filter(el=>el.getClientRects().length);
      const first=focusable[0],last=focusable[focusable.length-1];
      if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}
      else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}
    }
  });
  document.getElementById('print-button').addEventListener('click',()=>window.print());
  let openDetails=[];
  addEventListener('beforeprint',()=>{openDetails=Array.from(article.querySelectorAll('details')).map(el=>[el,el.open]);openDetails.forEach(([el])=>el.open=true)});
  addEventListener('afterprint',()=>openDetails.forEach(([el,wasOpen])=>el.open=wasOpen));
  refreshCount();
})();
'''


def plain(element):
    return ''.join(element.itertext())


def render():
    source = ROOT/'PROJECT-DECISIONS.md'
    data = source.read_bytes()
    converter = markdown.Markdown(extensions=['tables','fenced_code','toc'],output_format='xhtml')
    fragment = converter.convert(data.decode('utf-8-sig'))
    tree = ET.fromstring('<div>'+fragment+'</div>')
    intro = []
    sections = []
    current = None
    skipping_contents = False
    for element in list(tree):
        if element.tag=='h2':
            skipping_contents = plain(element)=='Contents'
            if skipping_contents:continue
            current = ET.Element('section',{'class':'chapter','id':element.attrib['id']})
            # The chapter owns the anchor so the full heading clears the toolbar.
            element.attrib.pop('id')
            current.append(element);sections.append(current)
        elif skipping_contents:
            continue
        elif current is None:
            intro.append(element)
        else:
            current.append(element)
    assert len(sections)==25
    decisions=0
    for section in sections:
        for heading in section.findall('h3'):
            match=re.match(r'(D\d+)\.\s+(.*)',plain(heading))
            if match:
                heading.text=''
                badge=ET.SubElement(heading,'span',{'class':'decision-id'})
                badge.text=match[1];badge.tail='. '+match[2]
                decisions+=1
        for paragraph in section.findall('p'):
            first=paragraph.find('strong')
            if first is not None and not (paragraph.text or '').strip():
                label=plain(first)
                if any(label.startswith(x) for x in ('Current decision','Working policy','Planned')):
                    category='policy' if label.startswith('Working policy') else 'planned' if label.startswith('Planned') else 'current'
                    paragraph.set('class','status-line '+category)
        for index,table in enumerate(section.findall('table'),1):
            heading=plain(section.find('h2'))
            caption=ET.Element('caption',{'class':'sr-only'})
            caption.text=heading+' - table '+str(index);table.insert(0,caption)
            headers=[plain(th) for th in table.findall('./thead/tr/th')]
            if headers==['Mode','Cost','Walking','Availability','Driving']:
                table.set('class','weights-table')
                for row in table.findall('./tbody/tr'):
                    cells=row.findall('td');weights=[float(plain(cell)) for cell in cells[1:]]
                    cells[1+weights.index(max(weights))].set('class','weight-primary')
            children=list(section);at=children.index(table);section.remove(table)
            wrapper=ET.Element('div',{'class':'table-scroll','role':'region','aria-label':caption.text,'tabindex':'0'})
            wrapper.append(table);section.insert(at,wrapper)
    assert decisions==48
    serialize=lambda el:ET.tostring(el,encoding='unicode',method='html')
    title=plain(intro[0]); intro_html=''
    guide=[]
    for element in intro[1:]:
        text=plain(element)
        if text.startswith('Context record:'):
            element.set('class','context-date');intro_html+=serialize(element)
        elif text.startswith('This document explains'):
            element.set('class','intro-lead');intro_html+=serialize(element)
        elif text.startswith('The product in one paragraph:'):
            intro_html+='<div class="product-summary">'+serialize(element)+'</div>'
        else:guide.append(serialize(element))
    intro_html+='''<nav class="quick-links" aria-label="Quick reading routes">
      <a href="#1-the-product-and-its-purpose">Start here</a>
      <a href="#11-how-we-chose-the-scoring-weights">Weights &amp; trade-offs</a>
      <a href="#13-a-worked-example-of-the-three-modes">Worked example</a>
      <a href="#24-concise-explanations-for-a-presentation">Presentation explanations</a></nav>'''
    intro_html+='<details class="reading-guide"><summary>How to use this record &amp; understand its status labels</summary><div class="guide-content">'+''.join(guide)+'</div></details>'
    groups={1:'The product',4:'Data & prediction',8:'Pricing & preferences',15:'Maps & architecture',19:'Validation & scope',24:'Presentation & sources'}
    navigation=''
    for number,section in enumerate(sections,1):
        if number in groups:
            if number>1:navigation+='</ul>'
            navigation+='<div class="nav-group">'+html.escape(groups[number])+'</div><ul class="chapter-nav">'
        heading=plain(section.find('h2')).split('. ',1)[1]
        navigation+='<li><a href="#'+section.attrib['id']+'"><span class="chapter-number">'+str(number).zfill(2)+'</span><span>'+html.escape(heading)+'</span></a></li>'
    navigation+='</ul>'
    template='''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ | ParkChoiceSG</title><meta name="description" content="A readable guide to 48 ParkChoiceSG project decisions, their rationale, scoring weights and evidence limits.">
<meta name="source-sha256" content="__HASH__"><link rel="icon" href="data:,"><style>__CSS__</style></head>
<body id="top"><a class="skip-link" href="#main">Skip to the decision record</a>
<button id="backdrop" class="backdrop" aria-label="Close contents" hidden></button>
<aside id="sidebar" class="sidebar" aria-label="Document contents">
  <div class="brand"><a class="brand-line" href="#top"><span class="brand-mark" aria-hidden="true">P</span><span class="brand-name">ParkChoiceSG</span></a>
    <p class="brand-subtitle">Project decisions &amp; rationale<br>Context record · 31 October 2026</p></div>
  <div class="contents-title">Contents<button id="close-menu" class="tool-button close-menu" aria-label="Close contents">×</button></div>
  <nav class="nav-scroll" aria-label="Chapters">__NAV__</nav>
  <div class="sidebar-footer">48 decisions · 25 chapters<br>Read offline. Search with Ctrl/Cmd + K.<br><a href="PROJECT-DECISIONS.md">Open the Markdown source</a></div>
</aside>
<div class="reader-shell">
  <header class="toolbar" aria-label="Reading tools"><div class="toolbar-inner">
    <div class="find-field"><label class="sr-only" for="document-search">Find text in the decision record</label>
      <input id="document-search" type="search" placeholder="Find a decision, number or phrase…" autocomplete="off" spellcheck="false">
      <button id="clear-search" class="clear-search" aria-label="Clear search" hidden>×</button></div>
    <div class="reader-controls"><button id="menu-button" class="tool-button mobile-menu" aria-controls="sidebar" aria-expanded="false">Contents</button>
      <span id="match-count" class="match-count" aria-live="polite">Find in record</span>
      <button id="previous-match" class="tool-button" aria-label="Previous match" title="Previous match (Shift + Enter)" disabled>↑</button>
      <button id="next-match" class="tool-button" aria-label="Next match" title="Next match (Enter)" disabled>↓</button>
      <button id="print-button" class="tool-button print-button">Print</button></div></div>
    <div id="reading-position" class="reading-position">Overview · 48 decisions across 25 chapters</div>
    <div class="progress-track" aria-hidden="true"><div id="progress-fill" class="progress-fill"></div></div>
  </header>
  <main id="main" class="document"><article id="record"><div class="eyebrow">PROJECT CONTEXT / DECISION RECORD</div>
    <h1>__TITLE__</h1>__INTRO____BODY__</article>
    <footer class="document-footer">ParkChoiceSG · Project Decisions and Rationale<br>
      Reading edition of <a href="PROJECT-DECISIONS.md">PROJECT-DECISIONS.md</a>. The Markdown file remains the editable source.</footer>
  </main>
</div><a class="to-top" href="#top">Back to top ↑</a>
<noscript><style>.find-field,.reader-controls,.reading-position{display:none}.toolbar-inner{padding:0}</style></noscript>
<script>__JS__</script></body></html>'''
    replacements={'__TITLE__':html.escape(title),'__HASH__':hashlib.sha256(data).hexdigest(),
                  '__CSS__':CSS,'__NAV__':navigation,'__INTRO__':intro_html,
                  '__BODY__':''.join(serialize(section) for section in sections),'__JS__':JS}
    for key,value in replacements.items():template=template.replace(key,value)
    output=source.with_suffix('.html');output.write_text(template,encoding='utf-8',newline='\n')
    print(f'Created {output.name}: {decisions} decisions, {len(sections)} chapters, {output.stat().st_size:,} bytes.')
    print('Content source SHA-256:',hashlib.sha256(data).hexdigest())


if __name__=='__main__':
    render()
