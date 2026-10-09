/* Runtime regression checks for the symptom-text microphone; no real audio or network. */
const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const path = require('path');
const source = fs.readFileSync(path.join(__dirname, '../views/chat_view.py'), 'utf8');
const code = source.slice(source.indexOf('    let symptomMicRec = null;'), source.indexOf('    function startSpeechRecognition()'));
const tick = () => new Promise(resolve => setImmediate(resolve));
function fixture(extra = {}) {
  const messages = [], files = [];
  const button = {classList: {add(){}, remove(){}}, setAttribute(){}};
  const textarea = {value:'', isConnected:true, dispatchEvent(){}};
  const context = {LANG:'en', add:text=>messages.push(text), window:{addEventListener(){}}, navigator:{},
    Blob, Event, FormData:class {append(...args){files.push(args)}},
    recordedFileName:m=>m.includes('mp4')?'symptosense-voice.m4a':'symptosense-voice.webm',
    prefersRecordedAudioFallback:()=>false, ...extra};
  vm.createContext(context); vm.runInContext(code, context);
  return {context,button,textarea,messages,files};
}
(async()=>{
  let f=fixture(); f.context.toggleSymptomTextMic(f.button,f.textarea);
  assert.equal(f.messages.length,1, 'unsupported microphones show feedback');
  f=fixture({navigator:{mediaDevices:{getUserMedia:()=>Promise.reject(new Error('denied'))}},MediaRecorder:class{}});
  f.context.toggleSymptomTextMic(f.button,f.textarea);await tick();assert.equal(f.messages.length,1);
  let resolvePermission, stopped=0;
  f=fixture({navigator:{mediaDevices:{getUserMedia:()=>new Promise(r=>resolvePermission=r)}},MediaRecorder:class{constructor(){throw Error('cancelled capture must not start')}}});
  f.context.toggleSymptomTextMic(f.button,f.textarea);f.context.toggleSymptomTextMic(f.button,f.textarea);
  resolvePermission({getTracks:()=>[{stop(){stopped++}}]});await tick();assert.equal(stopped,1);assert.equal(f.messages.length,0);
  for (const ok of [true,false]) {
    let stopCount=0;
    class Recorder {constructor(){this.mimeType='audio/mp4'} start(){} stop(){this.ondataavailable({data:new Blob(['fake'],{type:'audio/mp4'})});this.onstop()}}
    f=fixture({navigator:{mediaDevices:{getUserMedia:async()=>({getTracks:()=>[{stop(){stopCount++}}]})}},MediaRecorder:Recorder,
      fetch:async()=>({ok,json:async()=>({ok,text:ok?'spoken text':''})})});
    f.context.toggleSymptomTextMic(f.button,f.textarea);await tick();f.context.toggleSymptomTextMic(f.button,f.textarea);await tick();
    assert.equal(f.files.find(x=>x[0]==='audio')[2],'symptosense-voice.m4a');
    assert.equal(f.textarea.value,ok?'spoken text':'');assert.equal(f.messages.length,ok?0:1);assert.ok(stopCount>0);
  }
  let speech;
  f=fixture({window:{addEventListener(){},SpeechRecognition:class{constructor(){speech=this}start(){this.onstart()}stop(){this.onend()}}}});
  f.context.toggleSymptomTextMic(f.button,f.textarea);speech.onresult({resultIndex:0,results:[[{transcript:'headache'}]]});speech.onend();
  assert.equal(f.textarea.value,'headache');
  console.log('SYMPTOM MICROPHONE: 6 regression scenarios passed');
})().catch(e=>{console.error(e);process.exitCode=1});
