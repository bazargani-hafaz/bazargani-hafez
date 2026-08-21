(() => {
  const root=document.documentElement,toggle=document.getElementById('themeToggle');
  document.querySelectorAll('img').forEach(img=>{img.loading='lazy';img.decoding='async';});
  const style=document.createElement('style');
  style.textContent=`
  :root{--mx:50vw;--my:20vh}
  body:before{background:radial-gradient(500px circle at var(--mx) var(--my),#d7b66f18,transparent 60%),radial-gradient(circle at 85% 5%,#d7b66f12,transparent 25%),radial-gradient(circle at 5% 85%,#6978a812,transparent 28%);transition:background .2s}
  .hafez-dark body{background:#080b10;color:#eef1f5}.hafez-dark .cat,.hafez-dark .card,.hafez-dark .filters,.hafez-dark .secondary-btn,.hafez-dark .empty,.hafez-dark .auth form{background:#11151d;color:#eef1f5;border-color:#252b36}.hafez-dark .featured-section,.hafez-dark .cta-section{background:#0d1118}.hafez-dark .section-head p,.hafez-dark .description p,.hafez-dark .results-bar,.hafez-dark .card-meta{color:#929aa8}.hafez-dark .filters input,.hafez-dark .filters select{background:#151a23;color:#fff;border-color:#2a303b}.hafez-dark .pic{background:linear-gradient(135deg,#151922,#0e1218)}.hafez-dark .spec-box{background:#151922;border-color:#2a303b}.hafez-dark .spec-box pre{color:#aab1bd}.hafez-dark .brand-line{border-color:#292f39}.hafez-dark .secondary-btn{border-color:#343b48}.hafez-dark .products-hero p{color:#929aa8}
  .hafez-progress{position:fixed;top:0;right:0;height:3px;width:0;z-index:9999;background:linear-gradient(90deg,#8b6328,#f3dfa7,#d7b66f);box-shadow:0 0 18px #d7b66f;transition:width .08s linear}
  .hafez-cursor{position:fixed;width:18px;height:18px;border:1px solid #d7b66f99;border-radius:50%;pointer-events:none;z-index:9998;transform:translate(-50%,-50%);mix-blend-mode:difference;transition:width .15s,height .15s,background .15s;display:none}
  .reveal{opacity:0;transform:translateY(24px);transition:opacity .7s ease,transform .7s ease}.reveal.visible{opacity:1;transform:none}
  .magnetic{will-change:transform}.ripple{position:absolute;border-radius:50%;pointer-events:none;background:#fff8;width:8px;height:8px;transform:translate(-50%,-50%) scale(0);animation:hafez-ripple .65s ease-out forwards}@keyframes hafez-ripple{to{transform:translate(-50%,-50%) scale(25);opacity:0}}
  .card,.cat{transform-style:preserve-3d;will-change:transform}.hero-search,.filters{transition:box-shadow .25s,border-color .25s}.hero-search:focus-within,.filters:focus-within{border-color:#d7b66f88;box-shadow:0 25px 90px #0006,0 0 0 4px #d7b66f12}
  .showcase-card{transform-style:preserve-3d}.showcase-symbol{animation:hafez-glow 3s ease-in-out infinite}@keyframes hafez-glow{50%{text-shadow:0 0 75px #d7b66f65;transform:scale(1.04)}}
  .quick-view{backdrop-filter:blur(10px)}.btn,.icon-btn,.secondary-btn{position:relative;overflow:hidden}
  .flash{animation:hafez-in .5s ease both}@keyframes hafez-in{from{opacity:0;transform:translateY(-10px)}to{opacity:1;transform:none}}
  @media(max-width:700px){.hafez-cursor{display:none!important}.reveal{transition-duration:.45s}}
  @media(prefers-reduced-motion:reduce){*,*:before,*:after{scroll-behavior:auto!important;animation-duration:.001ms!important;animation-iteration-count:1!important;transition-duration:.001ms!important}.reveal{opacity:1;transform:none}}
  `;
  document.head.appendChild(style);
  if(localStorage.getItem('hafez-theme')==='dark')root.classList.add('hafez-dark');
  const sync=()=>{if(toggle)toggle.textContent=root.classList.contains('hafez-dark')?'☀':'☾';};sync();
  toggle?.addEventListener('click',()=>{root.classList.toggle('hafez-dark');localStorage.setItem('hafez-theme',root.classList.contains('hafez-dark')?'dark':'light');sync();});
  const progress=document.createElement('div');progress.className='hafez-progress';document.body.appendChild(progress);
  const updateProgress=()=>{const max=document.documentElement.scrollHeight-innerHeight;progress.style.width=(max>0?scrollY/max*100:0)+'%';};
  addEventListener('scroll',updateProgress,{passive:true});updateProgress();
  addEventListener('pointermove',e=>{root.style.setProperty('--mx',e.clientX+'px');root.style.setProperty('--my',e.clientY+'px');},{passive:true});
  if(innerWidth>900){const cursor=document.createElement('div');cursor.className='hafez-cursor';document.body.appendChild(cursor);addEventListener('pointermove',e=>{cursor.style.display='block';cursor.style.left=e.clientX+'px';cursor.style.top=e.clientY+'px';},{passive:true});document.querySelectorAll('a,button,input,select').forEach(el=>{el.addEventListener('mouseenter',()=>{cursor.style.width='34px';cursor.style.height='34px';cursor.style.background='#d7b66f22'});el.addEventListener('mouseleave',()=>{cursor.style.width='18px';cursor.style.height='18px';cursor.style.background='transparent'});});}
  document.querySelectorAll('.card,.cat').forEach(el=>{el.addEventListener('pointermove',e=>{if(innerWidth<900)return;const r=el.getBoundingClientRect(),x=((e.clientX-r.left)/r.width-.5)*2,y=((e.clientY-r.top)/r.height-.5)*2;el.style.transform=`translateY(-7px) rotateX(${y*-1.4}deg) rotateY(${x*1.4}deg)`;});el.addEventListener('pointerleave',()=>el.style.transform='');});
  document.querySelectorAll('.btn,.icon-btn,.secondary-btn').forEach(el=>{el.addEventListener('click',e=>{const r=el.getBoundingClientRect(),s=document.createElement('span');s.className='ripple';s.style.left=(e.clientX-r.left)+'px';s.style.top=(e.clientY-r.top)+'px';el.appendChild(s);setTimeout(()=>s.remove(),700);});});
  document.querySelectorAll('.section,.card,.cat,.cta,.products-hero,.detail-features>div').forEach(el=>el.classList.add('reveal'));
  if('IntersectionObserver' in window){const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('visible');io.unobserve(e.target)}}),{threshold:.08});document.querySelectorAll('.reveal').forEach(el=>io.observe(el));}else document.querySelectorAll('.reveal').forEach(el=>el.classList.add('visible'));
  document.querySelectorAll('.magnetic').forEach(el=>{el.addEventListener('pointermove',e=>{const r=el.getBoundingClientRect();el.style.transform=`translate(${(e.clientX-r.left-r.width/2)*.08}px,${(e.clientY-r.top-r.height/2)*.08}px)`});el.addEventListener('pointerleave',()=>el.style.transform='')});
  document.querySelectorAll('.hero-search input,.filter-search input').forEach(input=>{input.addEventListener('keydown',e=>{if(e.key==='/'&&!e.ctrlKey){e.preventDefault();input.focus()}if(e.key==='Escape')input.blur()});});
  const header=document.querySelector('.site-header');addEventListener('scroll',()=>{if(header)header.style.boxShadow=scrollY>20?'0 14px 45px #00000035':'0 12px 40px #00000012';},{passive:true});
})();
