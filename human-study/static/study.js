"use strict";
(()=>{
  const $=id=>document.getElementById(id),player=$('player');
  let inviteInfo=null,session=null,caseIndex=0,rows=[],current=null,phase='A',activeSlot='A',answerStarted=null,readingLocked=false,lastMediaTime=null,sending=false;
  function error(message){$('error').textContent=message;$('error').hidden=!message;}
  async function request(path,body){
    const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const data=await r.json();if(!r.ok)throw Error(data.error||'Request did not complete.');return data;
  }
  const blankTelemetry=()=>({ended:false,watched_seconds:0,plays:0,error:false});
  function stop(){player.pause();lastMediaTime=null;}
  function useClip(slot){
    stop();activeSlot=slot;player.src=session.cases[caseIndex].videos[slot];player.muted=true;player.load();
    $('clip-label').textContent='Version '+slot+' · 12 seconds · silent · manual playback';
    $('playback-status').textContent='Press Play when ready. You can pause or skip.';$('play').disabled=false;
  }
  function showCase(){
    if(caseIndex>=session.cases.length){stop();current=null;$('trial').hidden=true;$('finish').hidden=false;$('answer-count').textContent=rows.length+' lessons recorded, including '+rows.filter(r=>r.outcome==='skipped').length+' skips.';return;}
    const c=session.cases[caseIndex];current={id:c.id,outcome:'completed',answer:null,answer_ms:null,preference:null,distraction_A:null,distraction_B:null,lost_information:null,skip_reason:null,telemetry:{A:blankTelemetry(),B:blankTelemetry()}};
    phase='A';readingLocked=false;answerStarted=null;$('trial').hidden=false;$('progress').textContent='Lesson '+(caseIndex+1)+' of '+session.cases.length;
    $('trial-title').textContent=c.label;$('task').textContent='Reading task: '+c.question;
    $('reading-form').hidden=true;$('preference-form').hidden=true;$('replay-a').hidden=true;$('replay-b').hidden=true;
    $('reading-form').reset();$('preference-form').reset();$('reading-options').replaceChildren();
    const legend=document.createElement('legend');legend.textContent=c.question;$('reading-options').append(legend);
    for(const option of c.options){const label=document.createElement('label');label.className='check';const input=document.createElement('input');input.type='radio';input.name='reading';input.value=option.id;input.required=true;label.append(input,document.createTextNode(option.text));$('reading-options').append(label);}
    $('credit').textContent=c.credit;$('source-link').href=c.source_page;$('license-link').href=c.license_url;
    useClip('A');$('trial-title').focus?.();
  }
  async function checkInvite(){
    error('');inviteInfo=null;$('start').disabled=true;
    try{
      const code=$('invite').value.trim();const info=await request('/api/invitation',{invite:code});inviteInfo=info;
      $('qa-banner').hidden=!info.is_qa;$('consent').checked=false;
      $('consent-label').textContent=info.is_qa?'I am running software quality assurance. This is not a human participation record and must be excluded from human results.':'I am 18 or older, am volunteering, have not completed this study before, and agree to the anonymous response use described above.';
      $('invite-status').textContent=info.collection_open?'Invitation ready. Complete the choices below.':'Human collection is not open or has closed. No response has been saved.';
      $('protocol-id').textContent='Frozen protocol SHA-256: '+info.protocol_sha256;$('start').disabled=!info.collection_open;
      try{sessionStorage.setItem('lesson-study-invite',code);}catch(_){}
    }catch(e){error(e.message);}
  }
  $('check-invite').addEventListener('click',checkInvite);
  $('invite').addEventListener('input',()=>{inviteInfo=null;$('start').disabled=true;});
  $('join-form').addEventListener('submit',async event=>{
    event.preventDefault();if(!inviteInfo||sending)return;sending=true;$('start').disabled=true;error('');
    try{session=await request('/api/start',{invite:$('invite').value.trim(),consent:$('consent').checked,role:$('role').value,experience:$('experience').value,device:$('device').value});$('intro').hidden=true;$('qa-banner').hidden=!session.is_qa;showCase();}
    catch(e){error(e.message);$('start').disabled=false;}finally{sending=false;}
  });
  $('play').addEventListener('click',async()=>{
    if(!current)return;error('');current.telemetry[activeSlot].plays++;lastMediaTime=null;
    try{await player.play();$('playback-status').textContent='Playing '+activeSlot+'.';}catch(e){current.telemetry[activeSlot].error=true;error('Playback could not start. Retry Play or record a playback-error skip.');}
  });
  $('pause').addEventListener('click',()=>{stop();$('playback-status').textContent='Paused. Resume with Play, or skip.';});
  player.addEventListener('timeupdate',()=>{
    if(!current)return;const now=player.currentTime;
    if(!player.paused&&lastMediaTime!==null){const delta=now-lastMediaTime;if(delta>0&&delta<1.2)current.telemetry[activeSlot].watched_seconds=Math.min(600,current.telemetry[activeSlot].watched_seconds+delta);}
    lastMediaTime=now;
  });
  player.addEventListener('ended',()=>{
    if(!current)return;const t=current.telemetry[activeSlot];t.ended=true;lastMediaTime=null;
    let played=0;for(let i=0;i<player.played.length;i++)played+=player.played.end(i)-player.played.start(i);
    t.watched_seconds=Math.max(t.watched_seconds,played);
    if(t.watched_seconds<10){$('playback-status').textContent='Playback completed, but not enough continuous viewing was reported. Replay this clip or record a skip.';return;}
    if(phase==='A'&&!readingLocked){$('reading-form').hidden=false;answerStarted=performance.now();$('play').disabled=true;$('playback-status').textContent='A finished. Choose what you read before viewing B.';}
    else if(phase==='B'){$('preference-form').hidden=false;$('replay-a').hidden=false;$('replay-b').hidden=false;$('playback-status').textContent='Both versions were viewed. Your answer about A is locked; compare honestly, including no preference or neither.';}
  });
  player.addEventListener('error',()=>{if(current){current.telemetry[activeSlot].error=true;$('playback-status').textContent='This browser could not decode the study video. Record a playback-error skip; this outcome is retained.';}});
  $('reading-form').addEventListener('submit',event=>{
    event.preventDefault();if(readingLocked||!current.telemetry.A.ended)return;
    current.answer=new FormData(event.currentTarget).get('reading');current.answer_ms=Math.round(performance.now()-answerStarted);readingLocked=true;
    $('reading-form').hidden=true;phase='B';$('task').textContent='Watch B, then compare the two presentations. No reading answer feedback is given.';useClip('B');
  });
  $('replay-a').addEventListener('click',()=>useClip('A'));$('replay-b').addEventListener('click',()=>useClip('B'));
  $('preference-form').addEventListener('submit',event=>{
    event.preventDefault();if(!current.telemetry.A.ended||!current.telemetry.B.ended)return;
    current.preference=new FormData(event.currentTarget).get('preference');current.distraction_A=Number($('rating-a').value);current.distraction_B=Number($('rating-b').value);current.lost_information=$('lost').value;
    rows.push(current);caseIndex++;showCase();
  });
  $('skip').addEventListener('click',()=>{if(!current)return;stop();current.outcome='skipped';current.skip_reason=$('skip-reason').value;current.preference=null;current.distraction_A=null;current.distraction_B=null;current.lost_information=null;rows.push(current);caseIndex++;showCase();});
  $('submit-results').addEventListener('click',async()=>{
    if(sending||!session)return;sending=true;error('');$('submit-results').disabled=true;
    try{const result=await request('/api/submit',{session:session.session,cases:rows});$('finish').hidden=true;$('thanks').hidden=false;$('receipt').textContent=(result.is_qa?'QA receipt (excluded from human counts): ':'Anonymous receipt: ')+result.receipt;$('debrief').textContent=result.debrief;}
    catch(e){error(e.message);$('submit-results').disabled=false;}finally{sending=false;}
  });
  $('withdraw').addEventListener('click',async()=>{error('');try{const r=await request('/api/withdraw',{invite:$('invite').value.trim()});$('withdraw-status').textContent=r.message;}catch(e){error(e.message);}});
  try{const code=new URLSearchParams(location.hash.slice(1)).get('invite')||sessionStorage.getItem('lesson-study-invite');if(code){$('invite').value=code;history.replaceState(null,'',location.pathname);checkInvite();}}catch(_){}
})();
