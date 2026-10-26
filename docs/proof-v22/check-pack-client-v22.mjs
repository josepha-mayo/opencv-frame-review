// Pure Node contract checks against the exact shipped client helper, not browser UI evidence.
import fs from 'node:fs';import crypto from 'node:crypto';
const base=new URL('.',import.meta.url),read=p=>fs.readFileSync(new URL(p,base));
const source=fs.readFileSync(process.argv[2]||new URL('opencv-creator/studio/static/app.js',base)).toString();
const begin=source.indexOf('  async function packDigest('),end=source.indexOf('  async function prepareCheckedPack()',begin);if(begin<0||end<0)throw Error('Helper boundaries missing');
const verify=new Function('crypto','PACK_LIMIT',source.slice(begin,end)+'\nreturn verifyRescuePack;')(crypto.webcrypto,112*1024*1024+128*1024);
const bytes=new Uint8Array(fs.readFileSync(process.argv[3]||new URL('../outputs/proof-v22/gentoo-AWS-Rescue-Pack.zip',base))),view=new DataView(bytes.buffer);let p=0,manifest;
while(view.getUint32(p,true)===0x04034b50){const n=view.getUint16(p+26,true),x=view.getUint16(p+28,true),len=view.getUint32(p+18,true),name=new TextDecoder().decode(bytes.slice(p+30,p+30+n)),start=p+30+n+x;if(name==='manifest.json')manifest=JSON.parse(new TextDecoder().decode(bytes.slice(start,start+len)));p=start+len;}
const expected={id:manifest.binding.job_id,input_sha256:manifest.binding.input_sha256,recipe_sha256:manifest.binding.recipe_sha256},tests=[];
const valid=await verify(bytes,expected);if(valid.files!==44)throw Error('Unexpected valid member count');tests.push('Real Gentoo API pack: all 44 hashes pass');
async function refuse(name,data=bytes,binding=expected){let rejected=false;try{await verify(data,binding);}catch{rejected=true;}if(!rejected)throw Error('Incorrect acceptance: '+name);tests.push(name+' refused');}
for(const key of ['id','input_sha256','recipe_sha256'])await refuse('wrong '+key,bytes,{...expected,[key]:'wrong'});
await refuse('truncated transfer',bytes.slice(0,-1));
let bad=bytes.slice();bad[30+view.getUint16(26,true)+view.getUint16(28,true)]^=1;await refuse('modified file payload',bad);
bad=bytes.slice();bad[6]=1;await refuse('encrypted local entry',bad);
bad=bytes.slice();bad[8]=8;await refuse('unsupported compressed entry',bad);
bad=bytes.slice();bad[30]=47;await refuse('unsafe absolute path',bad);
bad=bytes.slice();new DataView(bad.buffer).setUint16(bad.length-12,65,true);await refuse('too many members',bad);
await refuse('too short archive',new Uint8Array(21));
const receipt={complete:true,scope:'Pure Node tests of exact shipped ZIP verification helper; not browser download, stream cancellation, disk-save or human evidence.',tests,checks:tests.length,client_sha256:crypto.createHash('sha256').update(source).digest('hex'),valid_pack:valid};
fs.writeFileSync(process.argv[4]||new URL('proof-v22-client-pack-contract.json',base),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify({complete:true,checks:tests.length,valid_files:valid.files}));
