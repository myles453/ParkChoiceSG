"""Fixed diagram layouts with separate connector lanes and readable labels."""
from math import atan2, cos, sin

from reportlab.graphics import renderSVG
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle, Ellipse, Polygon, Path as ShapePath
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase import pdfmetrics

INK='#243B4A'
PALE='#F0F5F7'


class Diagram:
    def __init__(self,width=1200,height=570):
        self.width,self.height=width,height
        self.d=Drawing(width,height)
        self.d.add(Rect(0,0,width,height,fillColor=white,strokeColor=None))

    def text(self,x,y,text,size=17,bold=False,center=False):
        for i,line in enumerate(text.split('\n')):
            self.d.add(String(x,self.height-y-i*size*1.3,line,fontName='Arial-Bold' if bold else 'Arial',
                              fontSize=size,fillColor=HexColor(INK),textAnchor='middle' if center else 'start'))

    def box(self,x,y,w,h,title,body='',size=17,fill=PALE):
        self.d.add(Rect(x,self.height-y-h,w,h,rx=8,ry=8,fillColor=HexColor(fill),strokeColor=HexColor(INK),strokeWidth=1.6))
        self.text(x+w/2,y+28,title,19,True,True)
        if body:
            self.d.add(Line(x+13,self.height-y-42,x+w-13,self.height-y-42,strokeColor=HexColor('#BDCDD5')))
            self.text(x+15,y+66,body,size)

    def edge(self,points,label='',at=None,dashed=False,arrow=True,size=16):
        path=ShapePath(strokeColor=HexColor(INK),strokeWidth=1.6,fillColor=None)
        if dashed:path.strokeDashArray=[5,4]
        path.moveTo(points[0][0],self.height-points[0][1])
        for x,y in points[1:]:path.lineTo(x,self.height-y)
        self.d.add(path)
        if arrow:
            (a,b),(x,y)=points[-2:];angle=atan2(y-b,x-a)
            corners=[x,self.height-y]
            for sign in [-1,1]:corners.extend([x-10*cos(angle)+sign*4*sin(angle),self.height-(y-10*sin(angle)-sign*4*cos(angle))])
            self.d.add(Polygon(corners,fillColor=HexColor(INK),strokeColor=None))
        if label and at:
            lines=label.split('\n');w=max(pdfmetrics.stringWidth(l,'Arial',size) for l in lines)+12
            self.d.add(Rect(at[0]-w/2,self.height-at[1]-(len(lines)-1)*size*1.3-4,w,len(lines)*size*1.3+3,fillColor=white,strokeColor=None))
            self.text(*at,label,size,center=True)

    def start(self,x,y):self.d.add(Circle(x,self.height-y,7,fillColor=HexColor(INK),strokeColor=None))

    def save(self,folder,name):renderSVG.drawToFile(self.d,str(folder/f'{name}.svg'))


def architecture(folder):
    d=Diagram(1200,550)
    for points,label,at in [
        ([(235,95),(350,95)],'HTTP',(292,78)),
        ([(520,155),(520,225)],'trip request',(585,190)),
        ([(690,95),(910,95)],'place search',(800,78)),
        ([(690,260),(810,260),(810,140),(910,140)],'drive / walk',(810,202)),
        ([(350,285),(235,285)],'read',(293,268)),
        ([(690,305),(910,305)],'prediction HTTP',(800,290)),
        ([(1050,350),(1050,430)],'HDB only',(1100,395)),
        ([(910,480),(235,480)],'provider captures',(580,462)),
        ([(118,430),(118,350)],'ingest',(160,396)),
    ]:d.edge(points,label,at)
    d.box(0,40,235,115,'Flutter app','Anonymous driver search\nSeparate operator sign-in',16)
    d.box(350,40,340,115,'FastAPI :8000','/destinations  /recommend\n/operator/login  /health',17)
    d.box(910,40,280,115,'OneMap APIs','Search and drive/walk routes\nPublic map tiles',16)
    d.box(0,225,235,125,'PostgreSQL','Private parking_data schema\nIdentities, readings, tariffs',15)
    d.box(350,225,340,125,'RecommendationController','Shortlist, quote and predict\nEligibility, score and rank',17)
    d.box(910,225,280,125,'HDB model :8001','Engine + calibrated model\nRecent LiveFeed history',16)
    d.box(0,430,235,105,'Separate collector','Clean and store source data',16)
    d.box(910,430,280,105,'HDB / LTA / URA','Public availability feeds',16)
    d.text(350,390,'Phone: foreground GPS, OneMap tiles, external navigation URL.',16)
    d.text(350,417,'Search does not start database collection or model training.',16)
    d.save(folder,'architecture')


def recommendation(folder):
    d=Diagram(1250,680)
    for points,label,at in [
        ([(190,225),(190,330)],'POST /recommend',(190,280)),
        ([(340,390),(390,390),(390,150),(435,150)],'dispatch',(390,285)),
        ([(805,150),(900,150)],'input',(850,132)),
        ([(560,225),(560,330)],'1 router',(600,285)),
        ([(805,190),(850,190),(850,430),(900,430)],'1 predictor',(850,320)),
        ([(480,225),(415,225),(415,600),(400,600)],'calls',(415,508)),
        ([(805,215),(825,215),(825,600),(900,600)],'calls',(825,520)),
    ]:d.edge(points,label,at,dashed=True,size=16)
    d.box(40,65,300,160,'ParkingApi','<<Flutter HTTP adapter>>\nrecommend(...): Future<Map>\ndestinations(query): Future<List>',15)
    d.box(40,330,300,120,'app module','<<FastAPI functions>>\nrecommendations(body): dict',16)
    d.box(435,65,370,160,'RecommendationController','router: RoutingProvider\npredictor: AvailabilityPredictor\nrecommend(TripRequest): dict',17)
    d.box(900,65,330,190,'TripRequest','origin, destination: Coordinate\nduration_minutes: int\ncandidate_limit: int = 3\nradius_meters: int = 1500\nranking_mode, payment_method: str',15)
    d.box(435,330,370,120,'RoutingProvider','<<Protocol>>\nroute(start, end, mode): RouteEstimate',16)
    d.box(900,380,330,120,'AvailabilityPredictor','<<Protocol>>\npredict(PredictionRequest): Prediction',15)
    d.box(40,550,360,110,'recommendation helpers','shortlist(...): list; quote_arrivals(...): dict\ncurrent_fallback(...): list',15)
    d.box(900,550,330,110,'scoring module','score_candidate(...): dict\nrank_candidates(...): list',16)
    d.save(folder,'class-recommendation')


def driver_input(folder):
    d=Diagram(1200,570)
    d.box(25,205,305,140,'Search input','entry / anonymous form\ndo / origin, destination, stay, mode\nFind [invalid] / inline correction',16)
    d.box(430,50,330,135,'Place selection sheet','entry / OneMap matches\ndo / choose a place or cancel',17)
    d.box(430,355,330,150,'Foreground location','do / permission, service and fix\nBound request to 30 seconds\nReport failure; retain manual choice',16)
    d.box(880,205,295,140,'Return to Search','entry / selected input or error\nGPS fix stores time and accuracy\nOld fix > 2 min requires refresh',16)
    d.start(75,155);d.edge([(75,155),(75,205)],'Open app',(138,180))
    d.edge([(330,240),(365,240),(365,115),(430,115)],'Search place',(350,90))
    d.edge([(330,310),(365,310),(365,420),(430,420)],'Use location',(355,460))
    d.edge([(760,115),(1025,115),(1025,205)],'Select valid match / Cancel',(970,95))
    d.edge([(760,420),(1025,420),(1025,345)],'[fix] store origin / [failure] show error',(968,460))
    d.edge([(175,345),(175,540),(690,540)],'Find [valid inputs] / POST recommendation',(440,525))
    d.text(720,546,'Continue to results dialog',17,True)
    d.save(folder,'dialog-driver-input')


def driver_results(folder):
    d=Diagram(1200,600)
    d.box(40,70,420,140,'Result cards','entry / ranked forecasts OR labelled current list\ndo / inspect cost, routes, evidence and exclusions\nChange input/mode / return to Search',16)
    d.box(820,70,350,120,'Unavailable / error','entry / no usable comparison\ndo / explain reason and permit retry',16)
    d.box(40,330,420,135,'OneMap marker view','entry / snapshot inputs and returned candidates\ndo / select carpark and external navigation\nNo automatic parking-session creation',16)
    d.box(820,310,350,120,'External navigation','entry / OS opens Google Maps URL\ndo / navigate in external app',16)
    d.box(820,490,350,95,'Navigation error','entry / show failure; map remains open',16)
    d.d.add(Polygon([610,d.height-20,625,d.height-35,610,d.height-50,595,d.height-35],
                    fillColor=white,strokeColor=HexColor(INK),strokeWidth=1.6))
    d.edge([(595,35),(570,35),(570,45),(250,45),(250,70)],'[ranked or fallback list]',(400,30))
    d.edge([(625,35),(995,35),(995,70)],'[no usable list]',(950,20))
    d.edge([(160,210),(160,330)],'View map',(160,275))
    d.edge([(365,330),(365,210)],'Back',(365,275))
    d.edge([(460,370),(820,370)],'Navigate [valid URL; OS accepts]',(640,350))
    d.edge([(460,430),(600,430),(600,535),(820,535)],'[invalid / launch fails]',(676,515))
    d.edge([(995,430),(995,460),(470,460)],'Return to app',(710,445))
    d.edge([(820,565),(350,565),(350,465)],'Dismiss / retry',(570,551))
    d.save(folder,'dialog-driver-results')


def local_dialog(folder):
    d=Diagram(1200,580)
    d.box(80,50,430,145,'Preferences','do / theme, saved labels, local controls\nAppearance persists via SharedPreferences\nOther values remain screen-local',17)
    d.box(730,50,430,145,'Tracker','entry / sample history and active stay if present\ndo / elapsed time and linear cost\nInternal session manager is process-local',17)
    d.box(15,345,245,120,'Add location','Save [nonblank fields]\n/ local list entry',17)
    d.box(350,345,245,120,'Erase confirmation','Confirm / reset vehicle\nand walking controls',17)
    d.box(660,345,245,120,'End confirmation','Confirm / clear session;\nadd screen-local entry',17)
    d.box(950,345,245,120,'Extend modal','Apply / feedback only\nNo reminder scheduled',17)
    d.edge([(170,195),(170,265),(120,265),(120,345)],'Add',(120,245))
    d.edge([(260,400),(290,400),(290,195)],'Save / Cancel',(290,300))
    d.edge([(420,195),(420,345)],'Erase',(420,270))
    d.edge([(500,345),(500,195)],'Confirm / Cancel',(530,230))
    d.edge([(790,195),(790,345)],'End [active]',(790,270))
    d.edge([(870,345),(870,195)],'Confirm / Cancel',(885,230))
    d.edge([(1040,195),(1040,345)],'Extend [active]',(1040,270))
    d.edge([(1150,345),(1150,195)],'Apply / Cancel',(1135,230))
    d.text(600,535,'Bottom navigation opens each screen; leaving/recreating it can discard local sample edits.',17,center=True)
    d.save(folder,'dialog-local')


def operator_dialog(folder):
    d=Diagram(1200,540)
    d.box(20,95,300,140,'Operator login','entry / username and password\ndo / validate nonempty fields\nDriver search remains anonymous',16)
    d.box(440,95,300,140,'Signing in','do / POST /operator/login\nDisable repeated submission\nDiscard success after leaving',16)
    d.box(860,95,320,140,'Operator console','entry / in-memory signedIn gate\ndo / sample alerts, health, overrides\nResolve/refresh affects local UI only',15)
    d.box(440,370,300,115,'Login error','entry / invalid or unavailable\ndo / correct input and retry',17)
    d.box(860,370,320,115,'Local override modal','Apply / update sample list\nCancel / no local change',17)
    d.edge([(320,165),(440,165)],'Submit [valid]',(380,145))
    d.edge([(740,165),(860,165)],'[200 + active]',(800,145))
    d.edge([(590,235),(590,370)],'[401 / 422 / 503 / timeout]',(590,310))
    d.edge([(440,430),(170,430),(170,235)],'Retry',(290,410))
    d.edge([(1000,95),(1000,30),(170,30),(170,95)],'Sign out / clear app flag',(590,16))
    d.edge([(950,235),(950,370)],'Add override',(950,290))
    d.edge([(1100,370),(1100,235)],'Apply / Cancel',(1100,320))
    d.text(600,525,'Admin tab opens console if already signed in; otherwise login. No server write authorization is issued.',17,center=True)
    d.save(folder,'dialog-operator')


def partial_use_cases(folder):
    d=Diagram(1200,570)
    def actor(x,y,name):
        d.d.add(Circle(x,d.height-y,11,strokeColor=HexColor(INK),fillColor=None,strokeWidth=2))
        for points in [[(x,y+11),(x,y+52)],[(x-20,y+28),(x+20,y+28)],[(x,y+52),(x-18,y+77)],[(x,y+52),(x+18,y+77)]]:
            d.edge(points,arrow=False)
        d.text(x,y+102,name,16,True,True)
    def uc(x,y,w,title,detail):
        d.d.add(Ellipse(x+w/2,d.height-y,w/2,30,strokeColor=HexColor(INK),fillColor=HexColor('#FFF6DE'),strokeWidth=1.3))
        d.text(x+w/2,y-4,title,17,True,True);d.text(x+w/2,y+17,detail,15,center=True)
    actor(45,225,'Driver');actor(755,225,'Operator')
    driver=[('UC-11 Preferences','Appearance persists; other controls local'),
            ('UC-12 Saved locations','Screen-local labels; recent search deferred'),
            ('UC-14 Start session','Internal manager; complete UI entry deferred'),
            ('UC-15 Extend session','Feedback only; no reminder scheduling'),
            ('UC-16 End session','Clear active stay; screen-local entry'),
            ('UC-17 Session history','Sample/local display; no durable history'),
            ('UC-18 Erase data','Reset two controls; full erasure deferred')]
    for i,(title,detail) in enumerate(driver):
        y=60+i*74;uc(195,y,490,title,detail)
        d.edge([(65,255),(120,255),(120,y),(195,y)],arrow=False)
    operator=[('UC-06 Sample alerts','Local status changes'),('UC-07 Override list','No recommendation effect'),
              ('UC-08 Health display','Sample measurements'),('UC-09 Refresh control','Feedback; no collector starts')]
    for i,(title,detail) in enumerate(operator):
        y=90+i*105;uc(840,y,350,title,detail)
        d.edge([(775,255),(805,255),(805,y),(840,y)],arrow=False)
    d.text(835,505,'UC-05 gate required for console entry.',16)
    d.text(835,535,'No server admin token or persisted writes.',16)
    d.save(folder,'use-cases-partial')


def sequence(folder,name,participants,messages,footnote):
    d=Diagram(1250,590)
    xs=[95,360,625,890,1155]
    for x,label in zip(xs,participants):
        d.box(x-86,5,172,78,label,size=16)
        d.edge([(x,83),(x,550)],dashed=True,arrow=False)
    for y,src,dst,label,returned in messages:
        if src==dst:
            x=xs[src];d.edge([(x,y),(x+35,y),(x+35,y+18),(x,y+18)],label,(x+235,y+4),dashed=returned,size=16)
        else:d.edge([(xs[src],y),(xs[dst],y)],label,((xs[src]+xs[dst])/2,y-9),dashed=returned,size=16)
    d.text(625,578,footnote,16,center=True)
    d.save(folder,name)


def request_sequence(folder):
    sequence(folder,'sequence-recommendation',
             ['Flutter /\nParkingApi','FastAPI /\nController','PostgreSQL /\ncomparison','OneMapClient','HdbModelClient /\nservice'],[
        (125,0,1,'POST /recommend',False),
        (165,1,2,'Eligible nearby pool',False),
        (205,2,1,'Canonical IDs + coordinates',True),
        (250,1,3,'Each candidate: drive and walk routes',False),
        (290,3,1,'Distance, duration and route times',True),
        (335,1,2,'Full-stay arrival quotes',False),
        (375,2,1,'Supported range / status',True),
        (420,1,4,'Current evidence and candidate arrival predictions',False),
        (460,4,1,'p_free, confidence, issue/history time or reason',True),
        (495,1,1,'Audit, gate, score and rank',False),
        (550,1,0,'Ranked / fallback / unavailable',True)],
        'Shortlist uses Haversine distance first. DB transactions close before network calls. No automatic replacements.')


def operator_sequence(folder):
    sequence(folder,'sequence-operator',
             ['Operator','Login screen /\nParkingApi','POST\n/operator/login','verify_operator','OperatorSession'],[
        (135,0,1,'Enter credentials',False),
        (190,1,2,'POST username/password',False),
        (245,2,3,'Check configured hash',False),
        (295,3,2,'Valid / invalid / config error',True),
        (350,2,1,'200 / 401 / 422 / 503',True),
        (405,1,4,'[200 and login active] signIn()',False),
        (465,1,0,'[success] open console',True),
        (525,1,0,'[failure] inline error / retry',True)],
        'Empty fields fail locally. Repeated taps send one request. Leaving the screen discards late success.')


def data_model(folder):
    d=Diagram(1250,690)
    d.box(20,20,320,135,'ingestion_runs','PK run_id: uuid\nretrieved_at: timestamptz\nmanifest: jsonb',16)
    d.box(450,20,350,135,'carpark_identities','PK agency + carpark_id\ndisplay_name, address\nCanonical agency-specific identity',16)
    d.box(900,20,330,135,'source_carpark_codes','PK feed + source_agency + code\nFK agency + carpark_id\nmatch_method, verified_at',16)
    d.box(20,300,320,160,'metadata evidence','carpark_metadata_evidence\nPK run_id + source + agency + ID\nFK run_id; FK agency + carpark_id\ncaptured_at, geometry, quality',15)
    d.box(450,300,350,160,'rate_schedules','PK schedule_id\nFK agency + carpark_id\nsource_run_id: optional capture FK\nValidity, review and calculator',16)
    d.box(900,300,330,160,'tariff_source_evidence','PK evidence_id\nFK agency + carpark_id\nCapture key, time, source hash\nPublished facts and review status',16)
    d.box(20,535,320,130,'provider snapshots','provider_availability_snapshots\nPK run + agency + ID + lot_type\nFK run_id; feed, time, count',15)
    d.box(450,535,350,130,'rate_schedule_rules','PK rule_id; FK schedule_id\nDay/time, cents, unit, priority\nReview and calculation rules',16)
    d.edge([(800,85),(900,85)],'1 : 0..*',(850,66),arrow=False)
    d.edge([(625,155),(625,300)],'1 : 0..*',(625,230),arrow=False)
    d.edge([(450,110),(400,110),(400,255),(280,255),(280,300)],'1 : 0..*',(345,238),arrow=False)
    d.edge([(800,115),(850,115),(850,255),(1065,255),(1065,300)],'1 : 0..*',(1000,237),arrow=False)
    d.edge([(145,155),(145,300)],'1 capture : 0..*',(145,225),arrow=False)
    d.edge([(20,90),(3,90),(3,600),(20,600)],'1 : 0..*',(52,498),arrow=False)
    d.edge([(625,460),(625,535)],'1 : 0..*',(625,507),arrow=False)
    d.text(900,550,'HDB direct history is separate:',17,True)
    d.text(900,581,'carparks + availability_observations.\nNormalized views provide comparison\nand training inputs.',16)
    d.save(folder,'data-model')


def render_manual(folder):
    for draw in [architecture,recommendation,driver_input,driver_results,local_dialog,operator_dialog,partial_use_cases,
                 request_sequence,operator_sequence,data_model]:
        draw(folder)
