(() => {
  document.querySelectorAll('img').forEach(img => { img.loading='lazy'; img.decoding='async'; });
  const root=document.documentElement,toggle=document.getElementById('themeToggle');
  const style=document.createElement('style');
  style.textContent=`.hafez-dark body{background:#080b10;color:#eef1f5}.hafez-dark .cat,.hafez-dark .card,.hafez-dark .filters,.hafez-dark .secondary-btn,.hafez-dark .empty,.hafez-dark .auth form{background:#11151d;color:#eef1f5;border-color:#252b36}.hafez-dark .featured-section,.hafez-dark .cta-section{background:#0d1118}.hafez-dark .section-head p,.hafez-dark .description p,.hafez-dark .results-bar,.hafez-dark .card-meta{color:#929aa8}.hafez-dark .filters input,.hafez-dark .filters select{background:#151a23;color:#fff;border-color:#2a303b}.hafez-dark .pic{background:linear-gradient(135deg,#151922,#0e1218)}.hafez-dark .spec-box{background:#151922;border-color:#2a303b}.hafez-dark .spec-box pre{color:#aab1bd}.hafez-dark .brand-line{border-color:#292f39}.hafez-dark .secondary-btn{border-color:#343b48}.hafez-dark .products-hero p{color:#929aa8}`;
  document.head.appendChild(style);
  if(localStorage.getItem('hafez-theme')==='dark') root.classList.add('hafez-dark');
  const sync=()=>{if(toggle)toggle.textContent=root.classList.contains('hafez-dark')?'☀':'☾';};sync();
  toggle?.addEventListener('click',()=>{root.classList.toggle('hafez-dark');localStorage.setItem('hafez-theme',root.classList.contains('hafez-dark')?'dark':'light');sync();});
  document.querySelectorAll('.card,.cat').forEach(el=>{el.addEventListener('pointermove',e=>{if(innerWidth<900)return;const r=el.getBoundingClientRect(),x=((e.clientX-r.left)/r.width-.5)*2,y=((e.clientY-r.top)/r.height-.5)*2;el.style.transform=`translateY(-7px) rotateX(${y*-1.1}deg) rotateY(${x*1.1}deg)`;});el.addEventListener('pointerleave',()=>el.style.transform='');});
  const header=document.querySelector('.site-header');window.addEventListener('scroll',()=>{if(header)header.style.boxShadow=scrollY>20?'0 14px 45px #00000028':'0 12px 40px #00000012';},{passive:true});
})();
