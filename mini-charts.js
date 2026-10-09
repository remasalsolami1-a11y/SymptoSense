/* SymptoSense lightweight dashboard charts.
 * Implements the tiny subset of Chart.js API used by dashboard.py so the
 * privileged dashboard does not execute third-party CDN JavaScript.
 */
(function(global){
  'use strict';
  const TAU=Math.PI*2;
  function n(v){const x=Number(v);return Number.isFinite(x)?x:0;}
  function colorAt(value,i){
    if(Array.isArray(value)) return value[i%value.length]||'#1565c0';
    return value||'#1565c0';
  }
  function prepare(canvas){
    const rect=canvas.getBoundingClientRect();
    const dpr=Math.max(1,Math.min(global.devicePixelRatio||1,2));
    const w=Math.max(240,Math.round(rect.width||canvas.clientWidth||600));
    const h=Math.max(160,Math.round(rect.height||canvas.clientHeight||250));
    canvas.width=Math.round(w*dpr); canvas.height=Math.round(h*dpr);
    const ctx=canvas.getContext('2d'); ctx.setTransform(dpr,0,0,dpr,0,0); ctx.clearRect(0,0,w,h);
    return {ctx,w,h};
  }
  function text(ctx,s,x,y,align){ctx.save();ctx.fillStyle='#566a7d';ctx.font='11px system-ui,sans-serif';ctx.textAlign=align||'center';ctx.textBaseline='middle';ctx.fillText(String(s??''),x,y);ctx.restore();}
  function empty(ctx,w,h){text(ctx,'—',w/2,h/2);}
  function drawLine(canvas,cfg){
    const {ctx,w,h}=prepare(canvas), labels=cfg.data?.labels||[], ds=(cfg.data?.datasets||[])[0]||{}, vals=(ds.data||[]).map(n);
    if(!vals.length){empty(ctx,w,h);return;}
    const p={l:38,r:14,t:16,b:34}, iw=Math.max(1,w-p.l-p.r), ih=Math.max(1,h-p.t-p.b), max=Math.max(1,...vals), min=Math.min(0,...vals), span=Math.max(1,max-min);
    ctx.strokeStyle='#dceafa';ctx.lineWidth=1;for(let i=0;i<=4;i++){const y=p.t+ih*i/4;ctx.beginPath();ctx.moveTo(p.l,y);ctx.lineTo(w-p.r,y);ctx.stroke();text(ctx,Math.round(max-(span*i/4)),p.l-6,y,'right');}
    const x=i=>p.l+(vals.length===1?iw/2:iw*i/(vals.length-1)), y=v=>p.t+ih-(v-min)/span*ih;
    if(ds.fill){ctx.beginPath();ctx.moveTo(x(0),p.t+ih);vals.forEach((v,i)=>ctx.lineTo(x(i),y(v)));ctx.lineTo(x(vals.length-1),p.t+ih);ctx.closePath();ctx.fillStyle=ds.backgroundColor||'rgba(25,118,210,.10)';ctx.fill();}
    ctx.beginPath();vals.forEach((v,i)=>i?ctx.lineTo(x(i),y(v)):ctx.moveTo(x(i),y(v)));ctx.strokeStyle=ds.borderColor||'#1565c0';ctx.lineWidth=2;ctx.stroke();
    ctx.fillStyle=ds.borderColor||'#1565c0';vals.forEach((v,i)=>{ctx.beginPath();ctx.arc(x(i),y(v),2.5,0,TAU);ctx.fill();});
    const step=Math.max(1,Math.ceil(labels.length/6));labels.forEach((lab,i)=>{if(i%step===0||i===labels.length-1)text(ctx,String(lab).slice(0,12),x(i),h-13);});
  }
  function drawBar(canvas,cfg){
    const {ctx,w,h}=prepare(canvas), labels=cfg.data?.labels||[], ds=(cfg.data?.datasets||[])[0]||{}, vals=(ds.data||[]).map(n);
    if(!vals.length){empty(ctx,w,h);return;}
    const p={l:36,r:12,t:16,b:44}, iw=w-p.l-p.r, ih=h-p.t-p.b, max=Math.max(1,...vals), slot=iw/vals.length, bw=Math.max(4,slot*.64);
    ctx.strokeStyle='#dceafa';for(let i=0;i<=4;i++){const y=p.t+ih*i/4;ctx.beginPath();ctx.moveTo(p.l,y);ctx.lineTo(w-p.r,y);ctx.stroke();text(ctx,Math.round(max*(1-i/4)),p.l-6,y,'right');}
    vals.forEach((v,i)=>{const bh=ih*(v/max),x=p.l+i*slot+(slot-bw)/2,y=p.t+ih-bh;ctx.fillStyle=colorAt(ds.backgroundColor,i);ctx.fillRect(x,y,bw,bh);text(ctx,String(labels[i]??'').slice(0,10),x+bw/2,h-17);});
  }
  function drawDoughnut(canvas,cfg){
    const {ctx,w,h}=prepare(canvas), labels=cfg.data?.labels||[], ds=(cfg.data?.datasets||[])[0]||{}, vals=(ds.data||[]).map(v=>Math.max(0,n(v))), total=vals.reduce((a,b)=>a+b,0);
    if(!total){empty(ctx,w,h);return;}
    const cx=w*.38,cy=h/2,r=Math.max(35,Math.min(w*.25,h*.34)),inner=r*.56;let a=-Math.PI/2;
    vals.forEach((v,i)=>{const b=a+TAU*(v/total);ctx.beginPath();ctx.moveTo(cx,cy);ctx.arc(cx,cy,r,a,b);ctx.closePath();ctx.fillStyle=colorAt(ds.backgroundColor,i);ctx.fill();a=b;});ctx.globalCompositeOperation='destination-out';ctx.beginPath();ctx.arc(cx,cy,inner,0,TAU);ctx.fill();ctx.globalCompositeOperation='source-over';
    const lx=Math.min(w-130,cx+r+24), start=Math.max(18,cy-(labels.length*18)/2);labels.slice(0,8).forEach((lab,i)=>{const y=start+i*18;ctx.fillStyle=colorAt(ds.backgroundColor,i);ctx.fillRect(lx,y-5,10,10);text(ctx,String(lab).slice(0,18),lx+16,y,'left');});
  }
  class MiniChart{
    constructor(canvas,config){if(!canvas||!canvas.getContext)throw new Error('canvas_required');this.canvas=canvas;this.config=config||{};this._resize=()=>this.draw();if(global.ResizeObserver){this._observer=new ResizeObserver(this._resize);this._observer.observe(canvas.parentElement||canvas);}else{global.addEventListener('resize',this._resize);}this.draw();}
    draw(){const type=this.config.type||'bar';if(type==='line')drawLine(this.canvas,this.config);else if(type==='doughnut')drawDoughnut(this.canvas,this.config);else drawBar(this.canvas,this.config);}
    destroy(){if(this._observer)this._observer.disconnect();else global.removeEventListener('resize',this._resize);const c=this.canvas.getContext('2d');if(c)c.clearRect(0,0,this.canvas.width,this.canvas.height);}
  }
  global.Chart=MiniChart;
})(window);
