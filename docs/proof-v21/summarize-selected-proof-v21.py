from pathlib import Path
import hashlib,json
from reportlab.graphics.shapes import Drawing,Rect,String
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics import renderPDF
from reportlab.lib.colors import HexColor
import pypdfium2
W=Path(__file__).resolve().parent;O=W.parent/'outputs/proof-v21';rows=[]
for name,label in [('upload-assistant','French form'),('joomla','Joomla setup'),('gentoo','Gentoo packages')]:
 path=O/'native'/name/'results.json';q=json.loads(path.read_text());assert q['complete']and q['independent_all_360_teaching_rgb_frames_exact']and q['independent_decoded_prepared_audio_exact']and q['independent_boundaries_not_worse']
 activity=q['summary']['stationary_detail']['whole_clip_activity']
 rows.append({'case':name,'label':label,'duration_seconds':12,'source':activity['source'],'edited':activity['edited'],'all_declared_teaching_rgb_frames_exact':True,'prepared_audio_timing_and_boundaries_pass':True,'source_sha256':q['source_sha256'],'result_json_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
source=sum(r['source']for r in rows);edited=sum(r['edited']for r in rows);assert (source,edited)==(37,21)
data={'complete':True,'scope':'Descriptive engineering aggregate of three previously selected original-source native regressions. Whole-excerpt selected-ROI mean RGB changes >=8 codes, including entry/return. Not detection recall, human learning, attention, preference or time saved.','runtime_manifest_sha256':json.loads((W/'proof-v21-build-verified.json').read_text())['source_manifest_sha256'],'cases':rows,'selected_seconds':36,'source_events':source,'edited_events':edited,'fewer_events':source-edited,'relative_event_reduction':(source-edited)/source,'selection_limit':'Chosen development cases; expanded70-window exploratory screens have zero newly useful repairs qualified. Overlapping windows/shared creators are not independent people.'}
(W/'proof-v21-selected-results.json').write_text(json.dumps(data,indent=2)+'\n')
d=Drawing(1200,800);d.add(Rect(0,0,1200,800,fillColor=HexColor('#f7f7ef'),strokeColor=None))
def text(x,y,value,size=20,bold=False,color='#245941'):d.add(String(x,y,value,fontName='Helvetica-Bold'if bold else'Helvetica',fontSize=size,fillColor=HexColor(color)))
text(70,742,'FRAME REVIEW  /  KEEP THE LESSON',27,True)
text(70,670,'37 to 21 measured changes',42,True,'#182b24')
text(70,620,'Three selected real lesson excerpts / 36 seconds total',21,False,'#3f5146')
text(100,552,'Selected-region change events',17,True,'#3f5146')
chart=VerticalBarChart();chart.x=110;chart.y=242;chart.width=995;chart.height=285
chart.data=[tuple(r['source']for r in rows),tuple(r['edited']for r in rows)];chart.categoryAxis.categoryNames=[r['label']for r in rows]
chart.valueAxis.valueMin=0;chart.valueAxis.valueMax=20;chart.valueAxis.valueStep=4
chart.valueAxis.labels.fontSize=15;chart.categoryAxis.labels.fontSize=18
chart.bars[0].fillColor=HexColor('#a4b18c');chart.bars[1].fillColor=HexColor('#245941');chart.bars.strokeColor=None
chart.barLabels.fontSize=18;chart.barLabels.fontName='Helvetica-Bold';chart.barLabelFormat='%d';chart.groupSpacing=30;chart.barSpacing=8
d.add(chart)
for x,color,label in [(650,'#a4b18c','Prepared source'),(878,'#245941','Local encoded edit')]:d.add(Rect(x,550,18,18,fillColor=HexColor(color),strokeColor=None));text(x+27,551,label,16,False,'#3f5146')
text(70,158,'Every declared teaching region stays exact on its prepared timeline.',22,True)
text(70,113,'Prepared audio/timing retained; encoded entry/return checks pass.',19,False,'#3f5146')
text(70,65,'Counts: adjacent ROI-mean RGB steps >=8 codes in each 12-second excerpt, including cut points.',14,False,'#48534a')
text(70,34,'Selected regressions. Expanded 70-window screen: 0 new qualified repairs. Human benefit unmeasured.',14,False,'#48534a')
pdf=O/'selected-real-results.pdf';renderPDF.drawToFile(d,str(pdf))
out=O/'selected-real-results.png';pypdfium2.PdfDocument(str(pdf))[0].render(scale=1).to_pil().save(out)
data['figure_sha256']=hashlib.sha256(out.read_bytes()).hexdigest();(W/'proof-v21-selected-results.json').write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps({'source':source,'edited':edited,'selected_seconds':36,'figure_bytes':out.stat().st_size,'figure_sha256':data['figure_sha256']}))
