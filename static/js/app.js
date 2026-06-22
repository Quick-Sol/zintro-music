/* Zintro — shared client JS
   - live clock
   - hover-card on .song elements
   - inertia smooth scroll
   - chart helpers (heatmap, ring, rhythm, waveform)
   - mood chip click → /api/predict-next
*/

/* ───── clock ───── */
(function(){
  const el = document.getElementById('clock');
  if (!el) return;
  function tick(){
    const d = new Date();
    el.textContent = [d.getHours(),d.getMinutes(),d.getSeconds()]
      .map(n=>String(n).padStart(2,'0')).join(':');
  }
  setInterval(tick,1000); tick();
})();

/* ───── hover card ───── */
const hover = document.createElement('div');
hover.id = 'hoverCard';
document.body.appendChild(hover);

function escapeHtml(str){
  return String(str ?? '').replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
}

let cardH = 180; // cached height; avoids forced layout reflow on every mousemove

function showCard(el, ev){
  const a   = escapeHtml(el.dataset.artist || '\u2014');
  const g   = escapeHtml(el.dataset.genre  || '\u2014');
  const y   = escapeHtml(el.dataset.year   || '\u2014');
  const bpm = escapeHtml(el.dataset.bpm    || '\u2014');
  const key = escapeHtml(el.dataset.key    || '\u2014');
  const mood= escapeHtml(el.dataset.mood   || '');
  const title = escapeHtml(el.textContent.trim().replace(/\s+/g,' '));
  const energy = Math.max(0.2, Math.min(1, (parseInt(el.dataset.bpm)||100)/180));
  const bars = Array.from({length:18},()=>{
    const h = 20 + Math.round(Math.random()*80*energy);
    return `<i style="height:${h}%"></i>`;
  }).join('');
  hover.innerHTML = `
    <div class="hc-art">
      <div class="hc-cover"></div>
      <div>
        <div class="hc-title">${title}</div>
        <div class="hc-artist">by <b style="color:var(--bone)">${a}</b></div>
      </div>
    </div>
    <div class="hc-meta">
      <div><div class="k">Genre</div><div class="v" style="font-size:11px">${g}</div></div>
      <div><div class="k">Year</div><div class="v">${y}</div></div>
      <div><div class="k">Tempo</div><div class="v">${bpm} <span style="font-size:9px;color:var(--muted)">BPM</span></div></div>
      <div><div class="k">Key</div><div class="v">${key}</div></div>
    </div>
    <div class="hc-mood">
      <span class="pill">${(mood||g).split(' \u00b7 ')[0]}</span>
      <div class="hc-bars">${bars}</div>
    </div>`;
  hover.classList.add('on');
  cardH = hover.offsetHeight || 180; // single layout read, done once per show, not per mousemove
  positionCard(ev);
}

let posQueued = false;
let lastEv = null;
function positionCard(ev){
  lastEv = ev;
  if (posQueued) return;
  posQueued = true;
  requestAnimationFrame(()=>{
    posQueued = false;
    const w = 260, h = cardH;
    let x = lastEv.clientX + 16, y = lastEv.clientY + 18;
    if (x + w + 14 > innerWidth) x = lastEv.clientX - w - 16;
    if (y + h + 14 > innerHeight) y = lastEv.clientY - h - 18;
    hover.style.left = x + 'px'; hover.style.top = y + 'px';
  });
}
function hideCard(){ hover.classList.remove('on'); }
function bindSongs(scope=document){
  scope.querySelectorAll('.song').forEach(el=>{
    if (el.__bound) return;
    el.__bound = true;
    el.addEventListener('mouseenter', e=>showCard(el,e));
    el.addEventListener('mousemove',  e=>{ if (hover.classList.contains('on')) positionCard(e); }, {passive:true});
    el.addEventListener('mouseleave', hideCard);
  });
}

/* ───── smooth scroll ───── */
(function(){
  if (matchMedia('(pointer:coarse)').matches) return;
  let target = scrollY, current = target, raf = null, animating = false;
  function loop(){
    current += (target - current) * 0.2;
    if (Math.abs(target - current) < 0.5){
      current = target;
      scrollTo(0, Math.round(current));
      raf = null; animating = false;
      return;
    }
    scrollTo(0, Math.round(current));
    raf = requestAnimationFrame(loop);
  }
  addEventListener('wheel', e=>{
    if (e.ctrlKey) return;
    e.preventDefault();
    target += e.deltaY;
    target = Math.max(0, Math.min(target, document.body.scrollHeight - innerHeight));
    animating = true;
    if (!raf) raf = requestAnimationFrame(loop);
  }, {passive:false});
  addEventListener('resize', ()=>{ target = scrollY; current = target; });
  // keep target in sync if the page scrolls via keyboard/scrollbar/touch instead of wheel
  addEventListener('scroll', ()=>{
    if (!animating) { target = scrollY; current = scrollY; }
  }, {passive:true});
})();

/* ───── waveform svg ───── */
window.zDrawWave = function(svg){
  const W=600,H=54,N=120,mid=H/2;
  const rng=(s=>()=>{s=(s*9301+49297)%233280;return s/233280})(7);
  let d='';
  for(let i=0;i<N;i++){
    const x=(i/(N-1))*W;
    const env=Math.sin((i/N)*Math.PI)*0.85+0.15;
    const a=(rng()*0.7+0.3)*env*mid*0.95;
    d+=`M${x} ${mid-a} L${x} ${mid+a} `;
  }
  svg.innerHTML=`<path d="${d}" stroke="#56503f" stroke-width="2" stroke-linecap="round"/>
    <clipPath id="prog"><rect width="${W*0.42}" height="${H}"/></clipPath>
    <g clip-path="url(#prog)"><path d="${d}" stroke="#ff5a1f" stroke-width="2" stroke-linecap="round"/></g>`;
};

/* ───── heatmap (7×24) ───── */
window.zDrawHeatmap = function(svg, grid){
  const cols=24,rows=7,gap=2,W=720,H=210;
  const cw=(W-gap*(cols-1))/cols, ch=(H-gap*(rows-1))/rows;
  let max=0; grid.forEach(r=>r.forEach(v=>max=Math.max(max,v)));
  max = max || 1;
  const ramp=t=>{
    const c1=[26,24,19],c2=[255,90,31];
    const r=Math.round(c1[0]+(c2[0]-c1[0])*t),
          g=Math.round(c1[1]+(c2[1]-c1[1])*t),
          b=Math.round(c1[2]+(c2[2]-c1[2])*t);
    return `rgb(${r},${g},${b})`;
  };
  let html='';
  let pr=0,pc=0,pv=0;
  for(let r=0;r<rows;r++) for(let c=0;c<cols;c++){
    const v=grid[r][c]||0, t=v/max;
    const x=c*(cw+gap), y=r*(ch+gap);
    if (v>pv){pv=v;pr=r;pc=c;}
    html+=`<rect x="${x}" y="${y}" width="${cw}" height="${ch}" fill="${t<0.05?'#1a1813':ramp(Math.pow(t,0.85))}"><title>day ${r+1} · ${c}:00 · ${v} plays</title></rect>`;
  }
  html+=`<rect x="${pc*(cw+gap)-1}" y="${pr*(ch+gap)-1}" width="${cw+2}" height="${ch+2}" fill="none" stroke="#f1e9d6" stroke-width="1"/>`;
  svg.innerHTML=html;
  // legend
  const ls=document.getElementById('legendScale');
  if(ls){let lh='';for(let i=0;i<20;i++)lh+=`<i style="background:${ramp(i/19)}"></i>`;ls.innerHTML=lh;}
};

/* ───── donut ring ───── */
window.zDrawRing = function(svg, segments){
  const cx=60,cy=60,r=44,rIn=30;
  const total=segments.reduce((s,m)=>s+m.v,0)||1;
  let acc=0,html='';
  segments.forEach(m=>{
    const a0=(acc/total)*2*Math.PI; acc+=m.v;
    const a1=(acc/total)*2*Math.PI;
    const large=(a1-a0)>Math.PI?1:0;
    const x0=cx+r*Math.cos(a0),y0=cy+r*Math.sin(a0);
    const x1=cx+r*Math.cos(a1),y1=cy+r*Math.sin(a1);
    const xi0=cx+rIn*Math.cos(a1),yi0=cy+rIn*Math.sin(a1);
    const xi1=cx+rIn*Math.cos(a0),yi1=cy+rIn*Math.sin(a0);
    html+=`<path d="M${x0} ${y0} A${r} ${r} 0 ${large} 1 ${x1} ${y1} L${xi0} ${yi0} A${rIn} ${rIn} 0 ${large} 0 ${xi1} ${yi1} Z" fill="${m.hex}" opacity=".92"><title>${m.k} · ${m.v}%</title></path>`;
  });
  svg.innerHTML=html+`<circle cx="${cx}" cy="${cy}" r="${rIn-2}" fill="#15130f"/>`;
};

/* ───── rhythm (24-hr line chart) ───── */
window.zDrawRhythm = function(svg, vals){
  const W=600,H=220,padL=30,padR=10,padT=14,padB=24;
  const innerW=W-padL-padR, innerH=H-padT-padB;
  const max = Math.max(...vals)*1.1 || 1;
  const px=i=>padL+(i/(vals.length-1))*innerW;
  const py=v=>padT+innerH-(v/max)*innerH;
  let grid='';
  for(let i=0;i<=4;i++){const y=padT+(i/4)*innerH; grid+=`<line x1="${padL}" y1="${y}" x2="${W-padR}" y2="${y}" stroke="#332e25" stroke-dasharray="2 4"/>`;}
  let ticks='';
  for(let i=0;i<vals.length;i+=3) ticks+=`<text x="${px(i)}" y="${H-6}" fill="#7a7160" font-size="9" font-family="JetBrains Mono" text-anchor="middle">${String(i).padStart(2,'0')}</text>`;
  const pts=vals.map((v,i)=>[px(i),py(v)]);
  function smooth(p){
    let d=`M${p[0][0]} ${p[0][1]}`;
    for(let i=0;i<p.length-1;i++){
      const p0=p[i-1]||p[i],p1=p[i],p2=p[i+1],p3=p[i+2]||p2;
      const c1x=p1[0]+(p2[0]-p0[0])/6,c1y=p1[1]+(p2[1]-p0[1])/6;
      const c2x=p2[0]-(p3[0]-p1[0])/6,c2y=p2[1]-(p3[1]-p1[1])/6;
      d+=` C${c1x} ${c1y}, ${c2x} ${c2y}, ${p2[0]} ${p2[1]}`;
    }
    return d;
  }
  const line=smooth(pts);
  const area=line+` L${px(vals.length-1)} ${padT+innerH} L${px(0)} ${padT+innerH} Z`;
  let dots='';
  vals.forEach((v,i)=>{if(i%3===0||v>max*.75) dots+=`<circle cx="${px(i)}" cy="${py(v)}" r="2.5" fill="#0d0c0a" stroke="#ff5a1f" stroke-width="1.4"/>`;});
  const pi=vals.indexOf(Math.max(...vals));
  const annot=`<line x1="${px(pi)}" y1="${py(vals[pi])-6}" x2="${px(pi)}" y2="${padT+4}" stroke="#ff5a1f" stroke-dasharray="2 2"/><text x="${px(pi)-6}" y="${padT-2}" fill="#f1e9d6" font-size="10" font-family="Fraunces" font-style="italic" text-anchor="end">peak · ${String(pi).padStart(2,'0')}:00</text>`;
  svg.innerHTML=`<defs><linearGradient id="ag" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#ff5a1f" stop-opacity=".35"/><stop offset="100%" stop-color="#ff5a1f" stop-opacity="0"/></linearGradient></defs>${grid}<path d="${area}" fill="url(#ag)"/><path d="${line}" fill="none" stroke="#ff5a1f" stroke-width="1.6" stroke-linecap="round"/>${dots}${ticks}${annot}`;
};

/* ───── mood chips → /api/predict-next ───── */
window.zMoodChips = function(){
  document.querySelectorAll('.chip').forEach(el=>{
    el.addEventListener('click', async ()=>{
      document.querySelectorAll('.chip').forEach(c=>c.classList.remove('active'));
      el.classList.add('active');
      const m = el.dataset.mood;
      const lab = document.getElementById('moodTitle');
      if (lab) lab.textContent = m.charAt(0).toUpperCase()+m.slice(1);
      const q = document.getElementById('queue');
      if (!q) return;
      q.classList.add('loading');
      try{
        const res = await fetch('/api/predict-next?mood='+encodeURIComponent(m));
        if (!res.ok) throw new Error('request failed: '+res.status);
        const list = await res.json();
        q.innerHTML = list.map((x,i)=>{
          const artist = escapeHtml((x.a||'').split(' · ')[0]);
          const genre  = escapeHtml(x.g || '\u2014');
          const year   = escapeHtml(x.y || '');
          const bpm    = escapeHtml(x.bpm || '');
          const key    = escapeHtml(x.key || '');
          const title  = escapeHtml(x.t || '');
          const subArtist = escapeHtml(x.a || '');
          const pct    = escapeHtml(x.p ?? '');
          const why    = escapeHtml(x.why || '');
          return `
        <div class="q-item ${x.lead?'lead':''}">
          <div class="rank serif">${String(i+1).padStart(2,'0')}</div>
          <div>
            <div class="title"><span class="song" data-artist="${artist}" data-genre="${genre}" data-year="${year}" data-bpm="${bpm}" data-key="${key}">${title}</span></div>
            <div class="sub">${subArtist}</div>
          </div>
          <div>
            <div class="pct">${pct}%</div>
            <div class="why">${why}</div>
          </div>
        </div>`;
        }).join('');
        bindSongs(q);
      } catch(err){
        console.error('predict-next failed:', err);
        q.innerHTML = `<div class="why" style="padding:14px 0">Couldn't load recommendations right now. Try again in a moment.</div>`;
      } finally {
        q.classList.remove('loading');
      }
    });
  });
};

/* ───── control toggles ───── */
document.querySelectorAll('.ctrls').forEach(g=>{
  g.querySelectorAll('span').forEach(s=>s.addEventListener('click',()=>{
    g.querySelectorAll('span').forEach(x=>x.classList.remove('on'));
    s.classList.add('on');
  }));
});
