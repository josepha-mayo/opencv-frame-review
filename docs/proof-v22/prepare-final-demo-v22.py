"""Precise timing around Joseph's supplied continuous voice; measured visuals only."""
from pathlib import Path
import hashlib,json,math,textwrap
from PIL import Image,ImageDraw,ImageFont
W=Path(__file__).resolve().parent;O=W.parent/'outputs/final-demo-v22';O.mkdir(exist_ok=True)
FONT=Path('C:/Windows/Fonts/arial.ttf');BOLD=Path('C:/Windows/Fonts/arialbd.ttf')
INK='#193b30';GREEN='#245941';MUTED='#566b60';CREAM='#f4f5ef';LIME='#d7ed9a';LINE='#ccd7ca'
def font(n,b=False):return ImageFont.truetype(str(BOLD if b else FONT),n)
def base(kicker,title,footer):
 im=Image.new('RGB',(1920,1080),CREAM);d=ImageDraw.Draw(im);d.rounded_rectangle((72,55,116,100),radius=8,fill=GREEN)
 for x in(83,92,101):d.rectangle((x,66,x+4,88),fill=LIME)
 d.text((135,58),'FRAME REVIEW',font=font(27,True),fill=GREEN);d.text((72,131),kicker.upper(),font=font(25,True),fill=MUTED);d.text((72,186),title,font=font(62,True),fill=INK,spacing=13);d.line((72,1009,1848,1009),fill=LINE,width=2);d.text((72,1032),footer,font=font(22),fill=MUTED);return im,d
def save(im,name):im.save(O/(name+'.png'))
im,d=base('OpenCV AI Competition 2026 • powered by AWS','Calm the blink.\nKeep the explanation.','Joseph Ayanda  •  Creator voice  •  Built with AI assistance')
d.text((76,407),'A precise repair for a creator\nwith only a finished recording.',font=font(39),fill=MUTED,spacing=17);d.rounded_rectangle((76,590,740,765),radius=18,fill=GREEN);d.text((108,620),'KEEP THE LESSON',font=font(47,True),fill=CREAM);d.text((108,690),'Original recoverable. Review required.',font=font(27),fill=LIME)
d.rounded_rectangle((880,338,1820,870),radius=18,fill='white',outline=LINE,width=2);d.text((914,360),'ACTUAL AWS APP',font=font(24,True),fill=GREEN)
save(im,'01-title')
im,d=base('01 / the reading pause','The lesson is moving.\nOnly one detail needs a hold.','Actual Gentoo prepared source playback outside the static review UI  •  Vitaly Zdanevich / CC0 as listed')
d.rounded_rectangle((600,330,1840,1010),radius=16,fill='white',outline=LINE,width=2);d.text((74,470),'Commands\nChanging progress\nBlinking caret',font=font(40,True),fill=GREEN,spacing=24);d.text((74,770),'No defect added.',font=font(31),fill=MUTED)
save(im,'02-problem')
im,d=base('02 / creator control','Choose the moment.\nInspect before generating.','Actual AWS/Brave screenshots  •  Condensed workflow  •  No automatic approval')
d.rounded_rectangle((800,320,1840,990),radius=16,fill='white',outline=LINE,width=2)
for i,t in enumerate(['1:02 → 62 seconds','Read the full range','Inspect both states','Name teaching areas','Check plan + consent']):d.text((78,414+i*92),t,font=font(36,i==0),fill=GREEN if i==0 else INK)
save(im,'03-workflow')
im,d=base('03 / encoded preservation','What matters is what stays.','Exact checks reference prepared media  •  Presentation footage is re-encoded  •  Creator review remains required')
for x,n,label in [(76,'360','prepared frames'),(688,'0','teaching RGB error'),(1300,'3','cut-point checks')]:
 d.rounded_rectangle((x,330,x+545,590),radius=18,fill='white',outline=LINE,width=2);d.text((x+30,355),n,font=font(92,True),fill=GREEN);d.text((x+30,495),label,font=font(31),fill=INK)
d.text((80,660),'Teaching sequence exact on its timeline.',font=font(45,True),fill=INK);d.text((80,743),'Entry • return • clip loop\nPrepared audio checked when present. Gentoo source is silent.',font=font(33),fill=MUTED,spacing=20)
save(im,'04-preservation')
im,d=base('04 / inspect and retain','One frame. Same scale.\nEvidence you can keep.','Actual app and offline proof screenshots  •  Static inspection  •  Keep the original before job expiry')
d.rounded_rectangle((750,330,1840,990),radius=16,fill='white',outline=LINE,width=2);d.text((77,440),'100% / 200% detail\nManual source / edit\nOriginal + recipe + report\nEmbedded offline proofs',font=font(34),fill=INK,spacing=33)
save(im,'05-inspect')
im,d=base('05 / controlled counterfactual','Removing the blink is not enough.','Historical V12 diagnostic on one selected French lesson  •  Benoit Rochon / CC BY 3.0 as listed')
for x,label,val in [(73,'Prepared source','Original timeline'),(690,'Local repair','0 teaching frames changed'),(1307,'Whole-frame hold','90 / 97 teaching frames changed')]:
 d.text((x+5,330),label,font=font(34,True),fill=GREEN);d.rounded_rectangle((x,394,x+540,698),radius=8,fill='white',outline=LINE,width=2);d.text((x+5,740),val,font=font(27,True),fill=INK)
d.text((78,860),'Same selected interval and observed reference. Whole-frame hold is a diagnostic, never an app-accepted result.',font=font(27),fill=MUTED)
save(im,'06-counterfactual')
selected=json.loads((W/'proof-v21-selected-results.json').read_text());assert(selected['source_events'],selected['edited_events'])==(37,21)
im,d=base('06 / measured result','37 → 21 selected-region events','Three selected development cases / 36 seconds  •  ROI-mean RGB steps ≥8 codes, including cut points  •  Not human benefit')
top=400;bottom=836;left=230;right=1750
for n in range(0,21,4):
 y=bottom-n/20*(bottom-top);d.line((left,y,right,y),fill=LINE,width=2);d.text((left-62,y-14),str(n),font=font(26),fill=MUTED)
for i,row in enumerate(selected['cases']):
 x=450+i*510
 for delta,val,color in [(-105,row['source'],'#a4b18c'),(35,row['edited'],GREEN)]:
  y=bottom-val/20*(bottom-top);d.rectangle((x+delta,y,x+delta+112,bottom),fill=color);d.text((x+delta+36,y-47),str(val),font=font(34,True),fill=INK)
 d.text((x-120,865),row['label'],font=font(29,True),fill=INK)
d.rectangle((1180,320,1205,345),fill='#a4b18c');d.text((1218,315),'Source',font=font(27),fill=MUTED);d.rectangle((1400,320,1425,345),fill=GREEN);d.text((1438,315),'Local edit',font=font(27),fill=MUTED)
d.text((78,941),'Every declared teaching RGB sequence remains exact.',font=font(34,True),fill=GREEN);save(im,'07-results')
im,d=base('07 / OpenCV 5 + AWS','Perceive. Review. Encode. Verify.','Actual architecture  •  One media worker / 1 vCPU / 2 GiB  •  No application AWS task role')
boxes=[(74,350,'RECORDING','Retain original\nPrepare excerpt'),(670,350,'OPENCV 5','Temporal differences\nConnected components'),(1266,350,'CREATOR','Inspect both states\nTeaching areas + plan'),(1266,640,'FFMPEG + GATES','Observed-state hold\nEncoded preservation'),(670,640,'OWNED ARTIFACTS','Reports + media + PNGs\nVerified rescue pack'),(74,640,'INSPECT / KEEP','Manual static comparison\nOriginal + offline proof')]
for x,y,h,t in boxes:d.rounded_rectangle((x,y,x+560,y+210),radius=15,fill='white',outline=LINE,width=2);d.text((x+25,y+23),h,font=font(29,True),fill=GREEN);d.text((x+25,y+85),t,font=font(29),fill=INK,spacing=12)
for a,b in [((634,455),(670,455)),((1230,455),(1266,455)),((1546,560),(1546,640)),((1266,745),(1230,745)),((670,745),(634,745))]:
 d.line((a,b),fill=GREEN,width=5);x,y=b
 pts=[(x,y),(x-13,y-8),(x-13,y+8)]if b[0]>a[0]else([(x,y),(x+13,y-8),(x+13,y+8)]if b[0]<a[0]else[(x,y),(x-8,y-13),(x+8,y-13)])
 d.polygon(pts,fill=GREEN)
d.text((80,902),'AWS ECS hosts the media workflow; ECR pins the image.',font=font(32,True),fill=GREEN);d.text((80,948),'CodeBuild: 14 Linux stages + real-source regressions.',font=font(30),fill=MUTED);save(im,'08-architecture')
im,d=base('08 / failures remain visible','A shorter retry can correctly\nleave the lesson unchanged.','Actual SMW Docker original / Otautz / CC BY-SA 4.0 as listed  •  Recovery of review is not a repair')
d.rounded_rectangle((830,375,1840,990),radius=16,fill='white',outline=LINE,width=2);d.text((79,477),'12 seconds: region limit\nKeep the source links\nExplicit 4-second retry\nNo proposal → unchanged',font=font(34),fill=INK,spacing=31);save(im,'09-recovery')
im,d=base('09 / evidence boundaries','Keep the negative results.', 'Exploratory windows overlap and share creators  •  No held-out recall or population efficacy claim')
for x,n,label in [(76,'70','exploratory windows'),(688,'0','new qualified repairs'),(1300,'0','valid human responses')]:d.rounded_rectangle((x,350,x+545,620),radius=18,fill='white',outline=LINE,width=2);d.text((x+30,385),n,font=font(96,True),fill=GREEN);d.text((x+30,535),label,font=font(29),fill=INK)
d.text((80,704),'Short prepared excerpts. Human benefit unproven.',font=font(43,True),fill=INK);d.text((80,787),'Browser transfer verification and file-save completion are separate checks.\nOne invitation start is not a completed person or a benefit result.',font=font(31),fill=MUTED,spacing=21);save(im,'10-limits')
im,d=base('Frame Review / Keep the Lesson','A precise repair.\nAn explanation preserved.','Joseph Ayanda  •  OpenCV AI Competition 2026  •  Creator narration, no synthetic voice')
d.text((80,436),'For a creator with only the recording.',font=font(43),fill=MUTED);d.rounded_rectangle((80,560,1820,900),radius=20,fill=GREEN);d.text((120,609),'TRY THE LIVE APP',font=font(34,True),fill=LIME);d.text((120,675),'Source • report • cases • retained failures',font=font(43,True),fill=CREAM);d.text((120,768),'github.com/josepha-mayo/opencv-frame-review',font=font(35),fill=CREAM);save(im,'11-close')
chapters=[('title',0,6.0),('problem',6,35.3),('real-source',35.3,47.9),('timestamp',47.9,61.8),('states',61.8,74.8),('plan',74.8,81.5),('preservation',81.5,107),('inspect',107,120.6),('offline',120.6,125.3),('counterfactual',125.3,140.7),('results',140.7,160),('architecture',160,179),('cloud-proof',179,185.9),('recovery',185.9,201.1),('negative-screen',201.1,209.0),('limits',209,225.3),('close',225.3,244.1)]
(O/'timeline.json').write_text(json.dumps({'source_audio_seconds':242.1,'final_seconds':244.1,'audio_speed':1.0,'chapters':[{'scene':s,'start':round(a*30)/30,'end':round(b*30)/30}for s,a,b in chapters]},indent=2)+'\n')
print('Prepared 11 evidence-based visual cards and 17 scenes around the 242.1-second creator recording.')
