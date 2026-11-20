(function(){
  'use strict';
  var root=document.documentElement;
  var btn=document.getElementById('langBtn');
  var retry=document.getElementById('retryBtn');
  var status=document.getElementById('netStatus');
  var text=document.getElementById('netText');
  if(!btn||!retry||!status||!text)return;
  var lang='ar';
  try{lang=localStorage.getItem('ss_lang')||((navigator.language||'').toLowerCase().startsWith('ar')?'ar':'en');}catch(e){}
  function sync(){
    var on=navigator.onLine;
    status.classList.toggle('online',on);
    retry.classList.toggle('online',on);
    text.textContent=lang==='ar'?(on?'عاد الاتصال':'بدون اتصال'):(on?'Connection restored':'Offline');
    var ar=retry.querySelector('.only-ar'),en=retry.querySelector('.only-en');
    if(ar)ar.textContent=on?'العودة إلى SymptoSense':'إعادة فحص الاتصال';
    if(en)en.textContent=on?'Return to SymptoSense':'Check connection again';
  }
  function apply(next){
    lang=next==='en'?'en':'ar';
    root.lang=lang;root.dir=lang==='ar'?'rtl':'ltr';
    btn.textContent=lang==='ar'?'EN':'عربي';
    try{localStorage.setItem('ss_lang',lang);}catch(e){}
    sync();
  }
  btn.addEventListener('click',function(){apply(lang==='ar'?'en':'ar');});
  retry.addEventListener('click',function(){if(navigator.onLine){location.href='/home';}else{location.reload();}});
  window.addEventListener('online',sync);window.addEventListener('offline',sync);
  apply(lang);
})();
