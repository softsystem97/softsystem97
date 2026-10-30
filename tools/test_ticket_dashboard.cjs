'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(process.argv[2], 'utf8');
class Element {
  constructor(tag='div') {this.tag=tag;this.children=[];this.listeners={};this.attrs={};this.style={};this.disabled=false;this.hidden=false;this._value='';this.textContent='';}
  appendChild(child) {this.children.push(child);return child;}
  replaceChildren() {this.children=[];this.textContent='';this._value='';}
  setAttribute(name,value) {this.attrs[name]=value;}
  addEventListener(name,fn) {this.listeners[name]=fn;}
  get options() {return this.children;}
  get value() {return this._value || (this.tag==='select' && this.children[0] ? this.children[0].value : '');}
  set value(value) {this._value=value;}
}
const tick = () => new Promise(resolve=>setImmediate(resolve));
async function fixture() {
  const elements = new Map();
  function el(id) {if(!elements.has(id))elements.set(id,new Element(id==='ss97-status'?'select':'div'));return elements.get(id);}
  const privateArea = new Element();const notifications=new Element();notifications.appendChild(new Element());
  const calls=[];let mode='ok';let token=0;
  const ticket={name:'SYNTH-1',subject:'<img onerror=evil()>',status:'Open',priority:'High',modified:'v1',description:'plain text',allowed_statuses:['Resolved'],can_add_intervention:true};
  const context={window:{frappe:{csrf_token:'FAKE-CSRF'},crypto:{randomUUID:()=>`fake-id-${++token}`}},URLSearchParams,Map,
    document:{getElementById:el,createElement:t=>new Element(t),querySelectorAll:selector=>selector==='[data-tech-private]'?[privateArea]:selector==='[data-ss97-notifications]'?[notifications]:[...elements.values()].filter(e=>e.attrs['data-scoped-action'])},
    fetch:async(url,options)=>{
      calls.push({url,options});
      const method=url.split('api.')[1].split('?')[0];
      if(mode==='deny')return {status:403,ok:false,json:async()=>{throw Error('HTML error page');}};
      if(options.method==='POST' && mode==='network')throw Error('network unavailable');
      if(options.method==='POST' && mode==='conflict')return {status:409,ok:false,json:async()=>({exc_type:'TimestampMismatchError'})};
      let message;
      if(method==='session_info')message={user:'tech@example.invalid'};
      else if(method==='list_tickets')message={tickets:[{...ticket}],page_size:50};
      else if(method==='get_ticket')message={ticket:{...ticket,...(mode==='restricted'?{allowed_statuses:[],can_add_intervention:false}:{})},history:[{action:'comment',detail:'synthetic report',creation:'today'}]};
      else if(method==='update_status'){ticket.status=JSON.parse(options.body).status;ticket.modified='v2';message={...ticket};}
      else if(method==='add_intervention')message={name:ticket.name,comment:'COMMENT-SYNTH'};
      else throw Error('unexpected endpoint '+method);
      return {ok:true,status:200,json:async()=>({message})};
    }};
  vm.runInNewContext(source,context);
  await tick();await tick();
  return {el,privateArea,notifications,calls,context,setMode:value=>{mode=value;},
    click:id=>el(id).listeners.click(),open:()=>el('ss97-ticket-rows').children[0].children[4].children[0].listeners.click()};
}
(async()=>{
 let count=0;
 let f=await fixture();
 assert(f.calls[0].url.includes('commercial=1'));assert(f.calls[1].url.includes('list_tickets'));
 assert.equal(f.el('ss97-tech-user').textContent,'tech@example.invalid');
 assert.equal(f.el('ss97-ticket-rows').children[0].children[1].textContent,'<img onerror=evil()>');count++;
 await f.open();assert.equal(f.el('ss97-detail').hidden,false);assert(f.el('ss97-detail-status').textContent.includes('High'));
 assert.equal(f.el('ss97-history').children.length,1);count++;
 await f.click('ss97-update');
 let post=f.calls.find(c=>c.options.method==='POST');let body=JSON.parse(post.options.body);
 assert.equal(post.options.headers['X-Frappe-CSRF-Token'],'FAKE-CSRF');assert.equal(body.expected_modified,'v1');assert.equal(body.status,'Resolved');assert(body.request_id);assert.equal(body.name,'SYNTH-1');count++;
 f=await fixture();await f.open();f.el('ss97-report').value='synthetic report';f.setMode('network');
 await f.click('ss97-save-report');await f.click('ss97-save-report');
 let writes=f.calls.filter(c=>c.options.method==='POST');assert.equal(writes.length,2);
 assert.equal(JSON.parse(writes[0].options.body).request_id,JSON.parse(writes[1].options.body).request_id);count++;
 f.setMode('ok');await f.click('ss97-save-report');
 assert(f.el('ss97-operation-result').textContent.includes('enregistré'));count++;
 f=await fixture();await f.open();f.setMode('conflict');await f.click('ss97-update');
 assert.equal(f.el('ss97-detail').hidden,true);assert(f.el('ss97-operation-result').textContent.includes('Conflit'));
 const n=f.calls.length;await f.click('ss97-update');assert.equal(f.calls.length,n);count++;
 f=await fixture();await f.open();delete f.context.window.frappe.csrf_token;
 await f.click('ss97-update');assert.equal(f.calls.filter(c=>c.options.method==='POST').length,0);
 assert(f.el('ss97-operation-result').textContent.includes('CSRF'));count++;
 f=await fixture();await f.open();f.setMode('deny');await f.click('ss97-history-refresh');
 assert.equal(f.el('ss97-ticket-rows').children.length,0);assert.equal(f.el('ss97-history').children.length,0);
 assert.equal(f.el('ss97-tech-user').textContent,'');assert.equal(f.privateArea.style.display,'none');
 assert.equal(f.notifications.children.length,0);count++;
 f=await fixture();f.setMode('restricted');await f.open();
 assert.equal(f.el('ss97-update').disabled,true);assert.equal(f.el('ss97-save-report').disabled,true);
 f.el('ss97-report').value='synthetic report';await f.click('ss97-save-report');
 assert.equal(f.calls.filter(c=>c.options.method==='POST').length,0);count++;
 assert(!source.includes('frappe.client'));assert(!source.includes('innerHTML'));assert(!source.includes('localStorage'));count++;
 console.log(`${count} JavaScript scenarios PASS (fictional server and DOM)`);
})().catch(error=>{console.error(error);process.exitCode=1;});
