(() => {
"use strict";
const $=key=>document.getElementById("cyberos-v3-"+key);
if(!$("status")) return;
const url="/api/method/softsystem97.cyberos.advisory_api.";
async function call(name,payload){
 const opt={credentials:"same-origin"};
 if(payload){opt.method="POST";opt.headers={"Content-Type":"application/json",
 "X-Frappe-CSRF-Token":window.frappe?.csrf_token||""};opt.body=JSON.stringify(payload);}
 const res=await fetch(url+name,opt);const body=await res.json().catch(()=>({}));
 if(!res.ok||body.exc)throw Error("Fonction indisponible ou accès refusé.");
 return body.message;
}
call("get_my_advisory").then(data=>{
 const root=$("controls");root.replaceChildren();
 if(!data.available){$("status").textContent="Aucun diagnostic autorisé trouvé.";return;}
 $("status").textContent="Synthèse de "+data.organization+" — réponses déclaratives.";
 data.controls.forEach(x=>{const li=document.createElement("li");
 li.textContent=x.function+" : "+x.label+" — "+x.answer+" (non vérifié)";
 root.append(li);});
}).catch(()=>$("status").textContent="Espace de direction indisponible avant activation Frappe.");
$("finance-form").addEventListener("submit",async e=>{
 e.preventDefault();const button=$("finance-form").querySelector("button[type=submit]");
 button.disabled=true;
 try{const data=await call("estimate_disruption",{
 hours:$("hours").value,hourly_impact_eur:$("hourly").value,
 recovery_cost_eur:$("recovery").value});
 $("result").textContent="Coût hypothétique : "+data.total_eur+" EUR. "+data.warning;
 }catch(err){$("result").textContent=err.message;}finally{button.disabled=false;}
});
})();