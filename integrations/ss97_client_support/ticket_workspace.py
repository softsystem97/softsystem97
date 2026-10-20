# -*- coding: utf-8 -*-
"""Espace ticket production — détail /espace-client/ticket (THEME existant)."""
from __future__ import annotations

import json
from pathlib import Path


def _ticket_pay_link() -> str:
    """Plus de Payment Link global 1 USD / test.

    Le paiement Live utilise uniquement ``Issue.ss97_stripe_checkout_url``
    généré depuis la grille ``ss97-prestation-*`` (montant > 1.01).
    """
    return ""


def ticket_detail_body_and_js() -> tuple[str, str]:
    """Retourne (body_html, script_js) pour page_ticket_detail."""
    pay_link = _ticket_pay_link()
    body = r"""
<style>
.ss97-tk .card > h4{
  color:#f8fafc!important;font-weight:700;font-size:1.08rem;letter-spacing:.01em;
  margin:0 0 12px;padding-bottom:8px;border-bottom:1px solid #475569
}
.ss97-tk .meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-top:12px}
.ss97-tk .meta div{background:#0f172a;border:1px solid #334155;border-radius:10px;padding:10px}
.ss97-tk .meta span{display:block;font-size:.72rem;color:#94a3b8;margin-bottom:4px}
.ss97-tk .meta strong{color:#e2e8f0;font-size:.92rem;word-break:break-word}
.ss97-tk .progbar{display:flex;flex-wrap:wrap;gap:0;margin:8px 0 4px;align-items:stretch}
.ss97-tk .progbar .step{flex:1 1 100px;min-width:90px;text-align:center;padding:10px 5px;border:1px solid #334155;background:#0f172a;color:#94a3b8;font-size:.68rem;line-height:1.35;position:relative}
.ss97-tk .progbar .step.done{background:rgba(34,197,94,.12);border-color:#22c55e;color:#bbf7d0}
.ss97-tk .progbar .step.cur{background:rgba(56,189,248,.15);border-color:#38bdf8;color:#e0f2fe;font-weight:700}
.ss97-tk .msg{color:#cbd5e1}
.ss97-tk #tk-client p,.ss97-tk #tk-tech p,.ss97-tk #tk-pay p,.ss97-tk #tk-interv p,.ss97-tk #tk-report p{color:#e2e8f0}
.ss97-tk .pay-confirmed{display:inline-block;padding:10px 16px;border-radius:10px;border:1px solid #22c55e;background:rgba(34,197,94,.15);color:#bbf7d0;font-weight:700}
.ss97-tk #btn-pay-now{font-size:1.05rem;padding:12px 22px;font-weight:700}
.ss97-tk .msg-row{padding:10px;margin:8px 0;border:1px solid #334155;border-radius:10px;background:#0f172a}
.ss97-tk .msg-row.admin-ch{border-color:#854d0e;background:rgba(161,98,7,.12)}
.ss97-tk .msg-row .who{color:#94a3b8;font-size:.8rem}
.ss97-tk .msg-row .txt{margin-top:6px;color:#e2e8f0;white-space:pre-wrap;word-break:break-word}
.ss97-tk .stars button{background:transparent;border:0;color:#64748b;font-size:1.4rem;cursor:pointer;padding:0 2px}
.ss97-tk .stars button.on{color:#fbbf24}
.ss97-tk .file-list a{color:#7dd3fc;word-break:break-all}
.ss97-tk .tl-item{display:flex;gap:12px;margin:10px 0;align-items:flex-start}
.ss97-tk .tl-dot{width:12px;height:12px;border-radius:50%;margin-top:4px;flex:0 0 auto;background:#334155}
.ss97-tk .tl-dot.on{background:#22c55e}.ss97-tk .tl-dot.cur{background:#38bdf8}
@media(max-width:700px){
  .ss97-tk .progbar .step{flex:1 1 46%}
  .ss97-tk .hide-sm{display:none!important}
}
</style>
<div class="ss97-tk">
  <div class="card" id="tk-head"><p class="msg">Chargement du ticket…</p></div>

  <div class="card" style="margin-top:14px">
    <h4>Progression</h4>
    <div class="progbar" id="tk-prog" aria-label="Progression du ticket"></div>
    <p class="msg" id="tk-prog-hint" style="margin-top:8px"></p>
  </div>

  <div class="grid" style="margin-top:14px">
    <div class="card"><h4>Informations client</h4><div id="tk-client" class="msg">…</div></div>
    <div class="card"><h4>Technicien</h4><div id="tk-tech" class="msg">…</div></div>
  </div>

  <div class="grid" style="margin-top:14px">
    <div class="card">
      <h4>Messages</h4>
      <div class="fgrid" style="margin-bottom:8px">
        <div><label>Canal</label>
          <select id="msg-channel">
            <option value="Client→Technicien">Client ↔ Technicien</option>
            <option value="Client→Administrateur">Client → Administrateur</option>
          </select>
        </div>
      </div>
      <div id="tk-msgs"><p class="msg">Chargement…</p></div>
      <div class="fgrid" style="margin-top:10px">
        <div class="full"><label>Nouveau message</label>
          <textarea id="msg-body" rows="3" placeholder="Écrivez votre message…"></textarea></div>
        <div class="full"><label>Pièces jointes (PDF, images, photos, captures, documents)</label>
          <input id="msg-files" type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.webp,.gif,.doc,.docx,.xls,.xlsx,.mp4,.mov,.txt"></div>
      </div>
      <div class="btns" style="margin-top:8px">
        <button class="btn btn-v" type="button" id="btn-msg">Envoyer</button>
        <button class="btn btn-g" type="button" id="btn-refresh-msg">Actualiser</button>
      </div>
      <p class="msg" id="msg-status"></p>
    </div>

    <div class="card">
      <h4>Intervention</h4>
      <div id="tk-interv" class="msg">…</div>
      <div class="btns" style="margin-top:10px">
        <a class="btn btn-g" id="lnk-remote" href="/espace-client/intervention-distance">Distance</a>
        <a class="btn btn-g" id="lnk-site" href="/espace-client/intervention-site">Sur site</a>
        <a class="btn btn-g" id="lnk-suivi" href="/espace-client/suivi">Suivi</a>
        <a class="btn btn-v" id="lnk-sign" href="/espace-client/signature">Signature</a>
      </div>
    </div>
  </div>

  <div class="grid" style="margin-top:14px">
    <div class="card">
      <h4>Pièces jointes</h4>
      <div id="tk-files" class="file-list msg">…</div>
      <div class="fgrid" style="margin-top:10px">
        <div class="full"><label>Ajouter un document / photo / vidéo</label>
          <input id="att-files" type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.webp,.gif,.doc,.docx,.mp4,.mov"></div>
      </div>
      <div class="btns" style="margin-top:8px">
        <button class="btn btn-v" type="button" id="btn-att">Téléverser</button>
      </div>
      <p class="msg" id="att-status"></p>
    </div>
    <div class="card">
      <h4>Paiement</h4>
      <p class="msg" style="color:#94a3b8;margin:0 0 8px">Paiement sécurisé SoftSystem97</p>
      <div id="tk-pay" class="msg">…</div>
      <div class="btns" style="margin-top:10px" id="tk-pay-actions">
        <button class="btn btn-v" type="button" id="btn-pay-now" style="display:none">Payer maintenant</button>
        <span class="pay-confirmed" id="btn-pay-done" style="display:none">Paiement confirmé</span>
        <button class="btn btn-b" type="button" id="btn-admin-request-pay" style="display:none">Demande de paiement</button>
        <a class="btn btn-g" href="/espace-client/factures">Mes factures</a>
        <a class="btn btn-g" href="/espace-client/paiements">Historique des paiements</a>
      </div>
      <p class="msg" id="tk-pay-status"></p>
    </div>
  </div>

  <div class="card" style="margin-top:14px">
    <h4>Rapport</h4>
    <div id="tk-report" class="msg">…</div>
    <div class="btns" style="margin-top:10px">
      <a class="btn btn-v" id="lnk-rapport" href="/espace-client/rapport">Ouvrir / télécharger le rapport</a>
      <button class="btn btn-g" type="button" id="btn-print-report">Imprimer</button>
    </div>
  </div>

  <div class="card" style="margin-top:14px">
    <h4>Historique</h4>
    <div id="tk-hist"></div>
  </div>

  <div class="card" style="margin-top:14px;display:none" id="tk-rate-card">
    <h4>Évaluation</h4>
    <p class="msg">Notez votre intervention SoftSystem97.</p>
    <div class="fgrid">
      <div><label>Note globale</label><div class="stars" id="rate-global"></div></div>
      <div><label>Ponctualité</label><div class="stars" id="rate-punct"></div></div>
      <div><label>Professionnalisme</label><div class="stars" id="rate-prof"></div></div>
      <div><label>Qualité</label><div class="stars" id="rate-qual"></div></div>
      <div><label>Communication</label><div class="stars" id="rate-comm"></div></div>
      <div class="full"><label>Commentaire</label><textarea id="rate-comment" rows="3" placeholder="Votre avis…"></textarea></div>
    </div>
    <div class="btns" style="margin-top:10px">
      <button class="btn btn-v" type="button" id="btn-rate">Envoyer l évaluation</button>
    </div>
    <p class="msg" id="rate-status"></p>
  </div>

  <div class="btns" style="margin-top:14px">
    <a class="btn btn-g" href="/espace-client/tickets">Retour liste</a>
    <a class="btn btn-g" href="/espace-client/dashboard">Dashboard</a>
    <a class="btn btn-g" href="/espace-client/messages">Messagerie</a>
  </div>
</div>
"""
    js = r"""
<script>
(function(){
  function esc(s){ return String(s||'').replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];}); }
  function stripHtml(s){ return String(s||'').replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim(); }
  function param(n){ try{ return new URL(location.href).searchParams.get(n)||''; }catch(e){ return ''; } }
  function nowMs(){ return Date.now(); }
  function parseDt(s){
    if(!s) return null;
    var raw=String(s).trim();
    if(/[zZ]|[+-]\d{2}:?\d{2}$/.test(raw)){
      var t0=Date.parse(raw); return isNaN(t0)?null:t0;
    }
    var iso=(raw.indexOf('T')>=0?raw:raw.replace(' ','T'));
    /* ERPNext stocke en UTC sans fuseau — forcer Z */
    var t=Date.parse(iso+'Z');
    if(isNaN(t)) t=Date.parse(iso);
    return isNaN(t)?null:t;
  }
  function pad2(n){ return (n<10?'0':'')+n; }
  function fmtParts(dt){
    var t=parseDt(dt);
    if(!t){
      var s=String(dt||'').replace('T',' ').trim();
      if(!s) return {date:'—', time:'—', full:'—'};
      return {date:s.slice(0,10)||'—', time:(s.slice(11,19)||s.slice(11,16)||'—'), full:s.slice(0,19)};
    }
    var d=new Date(t);
    var date=d.getFullYear()+'-'+pad2(d.getMonth()+1)+'-'+pad2(d.getDate());
    var time=pad2(d.getHours())+':'+pad2(d.getMinutes())+':'+pad2(d.getSeconds());
    return {date:date, time:time, full:date+' '+time};
  }
  function fmt(dt){ return fmtParts(dt).full; }
  function fmtDate(dt){ return fmtParts(dt).date; }
  function fmtTime(dt){ return fmtParts(dt).time; }
  function elapsedSince(dt){
    var t=parseDt(dt); if(!t) return '—';
    var diff=Math.max(0, nowMs()-t);
    var sec=Math.floor(diff/1000);
    var d=Math.floor(sec/86400); sec%=86400;
    var h=Math.floor(sec/3600); sec%=3600;
    var m=Math.floor(sec/60); sec%=60;
    if(d>0) return d+' j '+h+' h '+m+' min';
    if(h>0) return h+' h '+m+' min '+sec+' s';
    if(m>0) return m+' min '+sec+' s';
    return sec+' s';
  }
  function etaBeforeIntervention(d){
    var appt=parseDt(d.ss97_appointment_on);
    if(appt){
      var diff=appt-nowMs();
      if(diff<=0) return 'Intervention imminente / échéance atteinte';
      var h=Math.floor(diff/3600000), m=Math.floor((diff%3600000)/60000);
      if(h>48) return Math.floor(h/24)+' j '+(h%24)+' h (RDV '+fmt(d.ss97_appointment_on)+')';
      return h+' h '+m+' min (RDV '+fmt(d.ss97_appointment_on)+')';
    }
    if(d.ss97_planned_duration_min) return 'Durée planifiée : '+d.ss97_planned_duration_min+' min';
    if(d.ss97_sla_deadline) return 'SLA : '+slaLeft(d.ss97_sla_deadline);
    return 'Non renseigné';
  }
  function slaLeft(deadline){
    var t=parseDt(deadline); if(!t) return '—';
    var diff=t-nowMs();
    if(diff<=0) return 'Dépassé';
    var h=Math.floor(diff/3600000), m=Math.floor((diff%3600000)/60000);
    if(h>48) return Math.floor(h/24)+' j '+ (h%24) +' h';
    return h+' h '+m+' min';
  }
  function tsFromLog(log, re){
    var lines=String(log||'').split('\n');
    for(var i=lines.length-1;i>=0;i--){
      var line=lines[i]||'';
      if(re.test(line)){
        var m=line.match(/(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?)/);
        if(m) return m[1];
      }
    }
    return null;
  }
  var name=param('name');
  var followToken=param('token')||'';
  var DOC=null;
  var CLIENT_DETAIL=null;
  var TOKEN_ACCESS=false;
  var RATES={global:0,punct:0,prof:0,qual:0,comm:0};
  var SS97_PAY_LINK=PAY_LINK_PLACEHOLDER;
  var STEPS=[
    'Ticket créé',
    'Ticket validé',
    'Paiement requis',
    'Paiement confirmé',
    'Technicien affecté',
    'Intervention en cours',
    'Rapport terminé',
    'Ticket clôturé'
  ];

  /* Native permission and session errors must remain visible. */
  function roles(){
    try{
      if(window.frappe&&frappe.boot&&frappe.boot.user&&frappe.boot.user.roles) return frappe.boot.user.roles||[];
      if(frappe.user_roles) return frappe.user_roles;
    }catch(e){}
    return [];
  }
  function isStaff(){
    var r=roles().map(String);
    var keys=['System Manager','Administrator','Support Team','SS97 Technician','Technician'];
    for(var i=0;i<keys.length;i++){ if(r.indexOf(keys[i])>=0) return true; }
    return false;
  }
  function isTechOrAdmin(){ return isStaff(); }
  function sessionUser(){ return (window.frappe&&frappe.session&&frappe.session.user)||''; }

  function canAccess(d){
    if(!d||!d.name) return false;
    if(roles().indexOf('System Manager')>=0) return true;
    if(TOKEN_ACCESS && followToken) return true;
    var u=(sessionUser()||'').toLowerCase();
    if(!u||u==='guest') return false;
    var tech=(d.ss97_technician||'').toLowerCase();
    if(roles().indexOf('SS97 Technician')>=0 && tech && u===tech) return true;
    var em=(d.ss97_contact_email||'').toLowerCase();
    var rb=(d.raised_by||'').toLowerCase();
    return u===em || u===rb;
  }

  function stOf(d){ return String(d.ss97_ticket_status||d.status||''); }
  function isReallyPaid(d){
    /* Ne jamais utiliser le seul montant facturé : ce n'est pas un paiement. */
    var paid=String(d.ss97_payment_status||'').toLowerCase();
    var st=stOf(d).toLowerCase();
    /* A reference or the substring 'confirm' is not payment confirmation. */
    if(['a_payer','unpaid','pending','failed','cancelled','refunded','non confirmé','non confirme'].indexOf(paid)>=0) return false;
    if(['paid','payé','paye','confirmed','confirmé','confirme','paiement confirmé','paiement confirme'].indexOf(paid)>=0) return true;
    if(/^(paiement confirmé|paiement confirme|payé|paye)$/.test(st)) return true;
    return false;
  }
  function isValidated(d){
    var st=stOf(d);
    if(/nouveau|en attente de validation/i.test(st) && !Number(d.ss97_invoice_amount||0)) return false;
    if(/validé|valide|ouvert|en attente de paiement|payé|paye|paiement|affect|attribu|accept|intervention|planif|en cours|rapport|résolu|resolu|terminé|termine|clôtur|clotur|ferm|archiv/i.test(st)) return true;
    if(Number(d.ss97_invoice_amount||0)>0) return true;
    if(isReallyPaid(d)) return true;
    return false;
  }
  function isPaymentRequested(d){
    var st=stOf(d);
    if(/paiement requis|en attente de paiement|demande de paiement/i.test(st)) return true;
    if(d.ss97_stripe_checkout_url && !isReallyPaid(d)) return true;
    if(Number(d.ss97_invoice_amount||0)>0 && !isReallyPaid(d)) return true;
    if(isReallyPaid(d)) return true;
    return false;
  }

  function progressIndex(d){
    var st=stOf(d);
    var paid=isReallyPaid(d);
    var idx=0;
    if(isValidated(d) || isPaymentRequested(d) || paid) idx=1;
    if(isPaymentRequested(d) || paid) idx=Math.max(idx,2);
    if(paid) idx=Math.max(idx,3);
    /* Technicien / intervention uniquement APRÈS paiement confirmé */
    if(paid && d.ss97_technician) idx=Math.max(idx,4);
    if(paid && (d.ss97_intervention_started_on || /en cours|intervention|diagnostic|en déplacement|en pause|repris/i.test(st))) idx=Math.max(idx,5);
    if(paid && (d.ss97_intervention_report || d.ss97_resolved_on || /rapport|résolu|resolu/i.test(st))) idx=Math.max(idx,6);
    if(d.ss97_closed_on || /ferm|clôtur|clotur|archiv|termin|closed/i.test(st)) idx=7;
    return idx;
  }

  function renderProgress(d){
    var idx=progressIndex(d);
    document.getElementById('tk-prog').innerHTML=STEPS.map(function(label,i){
      var cls='step'+(i<idx?' done':'')+(i===idx?' cur':'');
      return '<div class="'+cls+'">'+esc(label)+'</div>';
    }).join('');
    document.getElementById('tk-prog-hint').textContent='Étape actuelle : '+STEPS[Math.min(idx, STEPS.length-1)];
  }

  function techDisplayName(d){
    if(!(isReallyPaid(d)&&d.ss97_technician)) return 'Aucun technicien affecté';
    return d._tech_full_name || d.ss97_technician;
  }
  function renderHead(d){
    var ref=d.ss97_public_ref||d.name;
    var clientName=((d.ss97_first_name||'')+' '+(d.ss97_last_name||'')).trim() || d.raised_by || '—';
    var created=fmtParts(d.creation);
    var updated=fmtParts(d.modified);
    document.getElementById('tk-head').innerHTML=
      '<h3 style="margin:0 0 6px">'+esc(ref)+' — '+esc(d.subject||'Sans sujet')+'</h3>'
      +'<p style="color:#94a3b8;margin:0">Référence interne : '+esc(d.name)+'</p>'
      +'<div class="meta">'
      +'<div><span>Statut</span><strong>'+esc(d.ss97_ticket_status||d.status||'—')+'</strong></div>'
      +'<div><span>Priorité</span><strong>'+esc(d.priority||'—')+'</strong></div>'
      +'<div><span>Date de création</span><strong>'+esc(created.date)+'</strong></div>'
      +'<div><span>Heure de création</span><strong>'+esc(created.time)+'</strong></div>'
      +'<div><span>Dernière mise à jour (date)</span><strong>'+esc(updated.date)+'</strong></div>'
      +'<div><span>Dernière mise à jour (heure)</span><strong>'+esc(updated.time)+'</strong></div>'
      +'<div><span>Temps écoulé</span><strong id="tk-elapsed">'+esc(elapsedSince(d.creation))+'</strong></div>'
      +'<div><span>Client</span><strong>'+esc(clientName)+'</strong></div>'
      +'<div><span>Technicien</span><strong id="tk-head-tech">'+esc(techDisplayName(d))+'</strong></div>'
      +'<div><span>Temps estimé avant intervention</span><strong>'+esc(etaBeforeIntervention(d))+'</strong></div>'
      +'<div><span>SLA</span><strong>'+esc(fmt(d.ss97_sla_deadline))+'</strong></div>'
      +'<div><span>Temps restant SLA</span><strong>'+esc(slaLeft(d.ss97_sla_deadline))+'</strong></div>'
      +'<div><span>Catégorie</span><strong>'+esc(d.ss97_category||'—')+'</strong></div>'
      +'</div>'
      +'<div style="margin-top:12px;color:#e2e8f0;line-height:1.55"><strong style="color:#94a3b8">Description</strong><br>'
      +esc(stripHtml(d.description)||'—')+'</div>';
  }

  function renderClient(d){
    var full=((d.ss97_first_name||'')+' '+(d.ss97_last_name||'')).trim()||'—';
    document.getElementById('tk-client').innerHTML=
      '<p><strong style="color:#fff">'+esc(full)+'</strong></p>'
      +'<p>Société : '+esc(d.ss97_client_name||d.customer||d.ss97_company||'—')+'</p>'
      +'<p>Téléphone : '+esc(d.ss97_contact_phone||'—')+'</p>'
      +'<p>E-mail : '+esc(d.ss97_contact_email||d.raised_by||'—')+'</p>'
      +'<p>Adresse : '+esc(d.ss97_intervention_address||'—')+'</p>'
      +'<p>Contrat : '+esc(d.ss97_contract_ref||'—')+'</p>'
      +'<p>Abonnement : <a href="/espace-client/abonnements" style="color:#7dd3fc">Voir</a></p>'
      +'<p id="tk-client-count">Tickets : …</p>';
    // count tickets for same email
    var em=d.ss97_contact_email||d.raised_by;
    if(em&&window.frappe&&frappe.call){
      frappe.call({
        method:'frappe.client.get_count',
        args:{ doctype:'Issue', filters:[['ss97_contact_email','=',em]] },
        callback:function(r){
          var n=r.message; if(typeof n!=='number') n='—';
          var el=document.getElementById('tk-client-count');
          if(el) el.textContent='Tickets : '+n;
        },
        error:function(){
          frappe.call({
            method:'frappe.client.get_list',
            args:{ doctype:'Issue', filters:[['ss97_contact_email','=',em]], fields:['name'], limit_page_length:100 },
            callback:function(r2){
              var el=document.getElementById('tk-client-count');
              if(el) el.textContent='Tickets : '+((r2.message||[]).length);
            }
          });
        }
      });
    }
  }

  function renderTech(d){
    var tech=d.ss97_technician||'';
    var paid=isReallyPaid(d);
    if(!tech || !paid){
      document.getElementById('tk-tech').innerHTML='<p style="color:#e2e8f0">Aucun technicien affecté pour le moment.</p>'
        +(!paid?'<p style="color:#94a3b8;font-size:.85rem">L\'affectation intervient après confirmation du paiement.</p>':'');
      var ht=document.getElementById('tk-head-tech'); if(ht) ht.textContent='Aucun technicien affecté';
      return;
    }
    document.getElementById('tk-tech').innerHTML='<p class="msg">Chargement du profil technicien…</p>';
    frappe.call({
      method:'frappe.client.get',
      args:{ doctype:'User', name:tech },
      callback:function(r){
        var u=r.message||{};
        var full=u.full_name||tech;
        d._tech_full_name=full;
        var ht=document.getElementById('tk-head-tech'); if(ht) ht.textContent=full;
        var photo=u.user_image||'';
        var avail='Affecté';
        if(d.ss97_en_route_on && !d.ss97_intervention_started_on) avail='En déplacement';
        else if(/en pause/i.test(stOf(d))) avail='Intervention en pause';
        else if(/repris/i.test(stOf(d))) avail='Intervention reprise';
        else if(d.ss97_intervention_started_on && !d.ss97_resolved_on) avail='Intervention en cours';
        else if(d.ss97_appointment_on) avail='Intervention planifiée';
        var specialty=u.interest || u.bio || d.ss97_category || '—';
        var img=photo
          ? '<img src="'+esc(photo)+'" alt="" style="width:56px;height:56px;border-radius:50%;object-fit:cover;border:1px solid #334155">'
          : '<div style="width:56px;height:56px;border-radius:50%;background:#1e293b;border:1px solid #334155;display:flex;align-items:center;justify-content:center;color:#94a3b8;font-weight:700">T</div>';
        document.getElementById('tk-tech').innerHTML=
          '<div style="display:flex;gap:12px;align-items:center;margin-bottom:10px">'+img
          +'<div><strong style="color:#fff">'+esc(full)+'</strong>'
          +'<div style="color:#94a3b8;font-size:.8rem">Affecté le '+esc(fmt(d.ss97_assigned_on||d.ss97_accepted_on||d.modified))+'</div></div></div>'
          +'<p>Statut : <strong style="color:#e0f2fe">'+esc(avail)+'</strong></p>'
          +'<p>Date prévue : '+esc(fmt(d.ss97_appointment_on)||'—')+'</p>'
          +'<p>Temps estimé avant intervention : '+esc(etaBeforeIntervention(d))+'</p>'
          +'<p>Spécialité : '+esc(specialty)+'</p>';
      },
      error:function(){
        var ht=document.getElementById('tk-head-tech'); if(ht) ht.textContent=tech;
        document.getElementById('tk-tech').innerHTML=
          '<p><strong style="color:#fff">'+esc(tech)+'</strong></p>'
          +'<p>Statut : Affecté</p>'
          +'<p>Date prévue : '+esc(fmt(d.ss97_appointment_on)||'—')+'</p>'
          +'<p>Temps estimé avant intervention : '+esc(etaBeforeIntervention(d))+'</p>'
          +'<p>Spécialité : '+esc(d.ss97_category||'—')+'</p>';
      }
    });
  }

  function renderInterv(d){
    document.getElementById('tk-interv').innerHTML=
      '<p>RDV : '+esc(fmt(d.ss97_appointment_on))+'</p>'
      +'<p>Adresse : '+esc(d.ss97_intervention_address||'—')+'</p>'
      +'<p>Session remote : '+esc(d.ss97_remote_session_id||'—')+'</p>'
      +'<p>Déplacement : '+esc(fmt(d.ss97_en_route_on))+'</p>'
      +'<p>Début : '+esc(fmt(d.ss97_intervention_started_on))+'</p>'
      +'<p>Résolu / fin : '+esc(fmt(d.ss97_resolved_on||d.ss97_closed_on))+'</p>'
      +'<p>Appareil : '+esc(d.ss97_device_summary||'—')+'</p>';
    ['lnk-remote','lnk-site','lnk-rapport','lnk-sign','lnk-suivi'].forEach(function(id){
      var a=document.getElementById(id); if(!a) return;
      var base=a.getAttribute('href').split('?')[0];
      a.href=base+'?name='+encodeURIComponent(name);
    });
  }

  function renderPay(d){
    var amt=d.ss97_invoice_amount;
    var isPaid=isReallyPaid(d);
    var canPay=!isPaid && isPaymentRequested(d);
    var paidLabel=isPaid?'Paiement confirmé':(isPaymentRequested(d)?'Paiement requis':(String(d.ss97_payment_status||'')||'En attente'));
    var displayAmt=(amt!=null&&amt!==''&&Number(amt)>1.01)? (Number(amt).toFixed(2)+' USD') : (canPay? 'Selon grille SoftSystem97' : '—');
    document.getElementById('tk-pay').innerHTML=
      '<p>Montant à payer : <strong style="color:#fff">'+esc(displayAmt)+'</strong></p>'
      +'<p>Devise : USD (catalogue ERP)</p>'
      +'<p>Statut : <strong style="color:'+(isPaid?'#86efac':'#e0f2fe')+'">'+esc(paidLabel)+'</strong></p>'
      +'<p>Référence : '+esc(d.ss97_payment_ref||'—')+'</p>'
      +'<p>Facture : '+esc(d.ss97_invoice_name||'—')+'</p>'
      +'<p>Reçu : '+esc(d.ss97_receipt_ref||'—')+'</p>';
    var btn=document.getElementById('btn-pay-now');
    var done=document.getElementById('btn-pay-done');
    var adm=document.getElementById('btn-admin-request-pay');
    if(btn){
      if(isPaid){ btn.style.display='none'; }
      else if(canPay){ btn.style.display='inline-flex'; btn.textContent='Payer maintenant'; btn.disabled=false; }
      else { btn.style.display='none'; }
    }
    if(done) done.style.display=isPaid?'inline-block':'none';
    if(adm){
      adm.style.display=(!isPaid && isStaff())?'inline-flex':'none';
    }
  }

  function setPayStatus(ok, text){
    var el=document.getElementById('tk-pay-status');
    if(!el) return;
    el.className=ok?'msg ok':'msg err';
    el.textContent=text||'';
  }

  function buildPayUrl(d){
    var base=(d && d.ss97_stripe_checkout_url) || SS97_PAY_LINK || '';
    if(!base) return '';
    var email=(d && (d.ss97_contact_email||d.raised_by))||'';
    var sep=base.indexOf('?')>=0?'&':'?';
    var url=base+sep+'client_reference_id='+encodeURIComponent(name);
    if(email) url+='&prefilled_email='+encodeURIComponent(email);
    /* retour vers le ticket après paiement Payment Link */
    return url;
  }

  function setMany(fields, done){
    var keys=Object.keys(fields||{}); var i=0;
    function next(){
      if(i>=keys.length){ if(done) done(true); return; }
      var f=keys[i++];
      frappe.call({
        method:'frappe.client.set_value',
        args:{ doctype:'Issue', name:name, fieldname:f, value:fields[f] },
        callback:function(){ next(); },
        error:function(err){ console.error('set', f, err); if(done) done(false); }
      });
    }
    next();
  }

  function adminRequestPayment(){
    if(!name){ setPayStatus(false,'Ticket manquant.'); return; }
    if(!isStaff()){ setPayStatus(false,'Action réservée à l\'administrateur.'); return; }
    if(!DOC){ setPayStatus(false,'Ticket non chargé.'); return; }
    var email=(DOC.ss97_contact_email||DOC.raised_by||'').trim();
    if(!email || email.indexOf('@')<1){ setPayStatus(false,'Adresse e-mail client manquante sur le ticket.'); return; }
    if(isReallyPaid(DOC)){ setPayStatus(false,'Ce ticket est déjà payé.'); return; }
    var btn=document.getElementById('btn-admin-request-pay');
    if(btn){ btn.disabled=true; btn.textContent='Création…'; }
    setPayStatus(true,'Création de la demande de paiement…');
    function finishLocal(okApiMsg){
      var payUrl=buildPayUrl(DOC);
      if(!payUrl && SS97_PAY_LINK){ payUrl=buildPayUrl({}); }
      if(!payUrl){
        if(btn){ btn.disabled=false; btn.textContent='Demande de paiement'; }
        setPayStatus(false,'Lien de paiement indisponible. Relancez le déploiement paiement.');
        return;
      }
      var amt=Number(DOC.ss97_invoice_amount||0);
      if(!(amt>1.01)){
        if(btn){ btn.disabled=false; btn.textContent='Demande de paiement'; }
        setPayStatus(false,'Montant catalogue manquant. Renseignez ss97_invoice_amount depuis la grille ss97-prestation-* avant la demande.');
        return;
      }
      setMany({
        ss97_payment_status:'a_payer',
        ss97_ticket_status:'Paiement requis',
        ss97_stripe_checkout_url:payUrl
      }, function(ok){
        if(btn){ btn.disabled=false; btn.textContent='Demande de paiement'; }
        if(!ok){ setPayStatus(false,'Impossible d\'enregistrer la demande de paiement.'); return; }
        frappe.call({
          method:'frappe.client.insert',
          args:{ doc:{ doctype:'Comment', comment_type:'Info', reference_doctype:'Issue', reference_name:name,
            content:'<p><b>Demande de paiement</b> — '+amt.toFixed(2)+' USD (grille SoftSystem97) — lien client prêt.</p>' } },
          error:function(){}
        });
        setPayStatus(true, okApiMsg||('Demande de paiement créée — '+amt.toFixed(2)+' USD.'));
        loadDoc();
      });
    }
    /* Server Scripts Cloud cassés (get_attr) — parcours fiable = Payment Link + set_value */
    finishLocal(null);
  }

  function clientPayNow(){
    if(!DOC||!name){ setPayStatus(false,'Ticket manquant.'); return; }
    if(isReallyPaid(DOC)){ setPayStatus(false,'Ce ticket est déjà payé.'); return; }
    if(!isPaymentRequested(DOC)){ setPayStatus(false,'Paiement non encore demandé par l\'administrateur.'); return; }
    var btn=document.getElementById('btn-pay-now');
    /* Ne jamais appeler les Server Scripts Cloud (get_attr → Message / Not permitted). */
    var url=buildPayUrl(DOC);
    if(!url && SS97_PAY_LINK) url=buildPayUrl({});
    if(url && url.indexOf('http')===0){
      if(btn){ btn.disabled=true; btn.textContent='Redirection…'; }
      location.href=url;
      return;
    }
    if(btn){ btn.disabled=false; btn.textContent='Payer maintenant'; }
    setPayStatus(false,'Lien de paiement indisponible. Contactez le support SoftSystem97.');
  }

  function maybeConfirmReturn(){
    /* Confirmation UNIQUEMENT via serveur (Stripe). Jamais de set_value local « paid ». */
    var paid=param('paid'); var sid=param('session_id'); var cancelled=param('cancelled');
    var ticketQ=param('ticket');
    if(cancelled==='1'){
      setPayStatus(false,"Le paiement n'a pas été finalisé. Vous pouvez réessayer.");
      return;
    }
    if(paid!=='1' || !sid) return;
    if(ticketQ && name && ticketQ!==name) return;
    setPayStatus(true,'Vérification du paiement auprès du serveur…');
    frappe.call({
      method:'ss97_ticket_confirm_payment',
      args:{ session_id:sid, ticket:name||ticketQ, invoice:param('invoice') },
      callback:function(r){
        var m=(r&&r.message)||{};
        if(m.ok){
          setPayStatus(true,'Paiement confirmé'+(m.receipt?(' — reçu '+m.receipt):''));
          loadDoc();
        } else {
          setPayStatus(false, m.error||"Paiement non confirmé par le serveur. Réessayez ou actualisez dans un instant.");
          loadDoc();
        }
      },
      error:function(err){
        console.error('Confirm paiement', err);
        setPayStatus(false,"Vérification serveur indisponible. Le statut « Paiement confirmé » n'apparaîtra qu'après validation Stripe.");
        loadDoc();
      }
    });
  }

  function renderReport(d){
    var rep=stripHtml(d.ss97_intervention_report||'');
    var box=document.getElementById('tk-report');
    if(!rep){
      box.innerHTML='<p>Rapport non disponible pour le moment.</p>';
      return;
    }
    box.innerHTML=
      '<p><strong style="color:#fff">Travaux / observations</strong></p>'
      +'<div style="color:#e2e8f0;line-height:1.55;white-space:pre-wrap">'+esc(rep.slice(0,2500))+(rep.length>2500?'…':'')+'</div>'
      +'<p style="margin-top:10px">Temps passé : '+esc(d.ss97_actual_duration_min? (d.ss97_actual_duration_min+' min') : '—')+'</p>'
      +'<p>Signature client : '+(d.ss97_client_signature||d.ss97_signed_on?'présente':'en attente')+'</p>'
      +'<p>Photos : '+esc(d.ss97_intervention_photos||'—')+'</p>';
  }

  function renderTimeline(d){
    var paid=isReallyPaid(d);
    var st=stOf(d);
    var log=d.ss97_action_log||'';
    var paidDoneAt=d.ss97_paid_on||tsFromLog(log, /paiement confirm|payé|paye|payment confirm/i)||(d.ss97_payment_ref?d.modified:null);
    var paidReqAt=tsFromLog(log, /paiement requis|en attente de paiement|demande de paiement/i)||(isPaymentRequested(d)?(paidDoneAt||d.modified):null);
    var assignedAt=d.ss97_assigned_on||d.ss97_accepted_on||tsFromLog(log, /technicien affect|affecté|attribué|accepté/i);
    var startedAt=d.ss97_intervention_started_on||tsFromLog(log, /intervention en cours|démarr|debut intervention|début intervention/i);
    var pauseAt=d.ss97_pause_started_on||tsFromLog(log, /en pause|mise en pause|pause/i);
    var resumeAt=tsFromLog(log, /repris|reprise/i)||( /repris/i.test(st) ? d.ss97_ai_intervention_synced_on : null);
    var endedAt=d.ss97_resolved_on||tsFromLog(log, /intervention termin|résolu|resolu|terminé|termine/i);
    var reportAt=tsFromLog(log, /rapport/i)||(d.ss97_intervention_report?(endedAt||d.modified):null);
    var closedAt=d.ss97_closed_on||tsFromLog(log, /clôtur|clotur|ferm|archiv/i);
    var techOn=!!(paid && d.ss97_technician);
    var pauseOn=!!(paid && (pauseAt || /en pause/i.test(st) || d.ss97_ai_intervention_action==='pause'));
    var resumeOn=!!(paid && (resumeAt || /repris/i.test(st) || d.ss97_ai_intervention_action==='resume'));
    var reportOn=!!(paid && (d.ss97_intervention_report || reportAt || /rapport/i.test(st)));
    var closedOn=!!(closedAt || /clôtur|clotur|ferm|archiv|ticket clôtur/i.test(st));
    var items=[
      ['Ticket créé', d.creation, true],
      ['Paiement effectué', paidReqAt||paidDoneAt, !!(isPaymentRequested(d)||paid)],
      ['Paiement validé', paidDoneAt, paid],
      ['Technicien affecté'+(techOn?(' — '+(d._tech_full_name||d.ss97_technician)) : ''), assignedAt, techOn],
      ['Intervention commencée', startedAt, !!(paid && startedAt)],
      ['Intervention en pause', pauseAt, pauseOn],
      ['Intervention reprise', resumeAt||(resumeOn?d.modified:null), resumeOn],
      ['Intervention terminée', endedAt, !!(paid && endedAt)],
      ['Rapport envoyé', reportAt, reportOn],
      ['Ticket clôturé', closedAt, closedOn]
    ];
    var html='<p style="color:#94a3b8;font-size:.85rem;margin:0 0 10px">Chronologie synchronisée (source unique Issue) — date et heure par événement.</p>';
    html+=items.map(function(it){
      var on=!!it[2];
      var p=fmtParts(it[1]);
      var when=on&&it[1] ? (esc(p.date)+' · '+esc(p.time)) : (on?'✓':'En attente');
      return '<div class="tl-item"><div class="tl-dot'+(on?' on':'')+'"></div><div><strong style="color:'+(on?'#fff':'#94a3b8')+'">'
        +esc(it[0])+'</strong><div style="color:#94a3b8;font-size:.8rem">'+when+'</div></div></div>';
    }).join('');
    html+='<p style="margin:10px 0 0;color:#e2e8f0"><b>Statut actuel :</b> '+esc(st||'—')
      +' · <b>Temps écoulé :</b> '+esc(elapsedSince(d.creation))+'</p>';
    var ilog=[];
    try{ ilog=JSON.parse(d.ss97_ai_intervention_log||'[]')||[]; }catch(e){ ilog=[]; }
    if(ilog.length){
      html+='<div style="margin-top:10px"><strong style="color:#e2e8f0">Suivi intervention (temps réel)</strong><ul style="margin:6px 0 0;padding-left:18px;color:#cbd5e1;font-size:.85rem">';
      ilog.slice(-8).forEach(function(e){
        html+='<li>'+esc(fmt(e.at||'')+' · '+(e.action||'')+' → '+(e.status||''))+'</li>';
      });
      html+='</ul></div>';
    }
    var slog=stripHtml(log);
    if(slog){
      html+='<div style="margin-top:12px;padding-top:10px;border-top:1px solid #334155"><strong style="color:#e2e8f0">Journal</strong>'
        +'<pre style="white-space:pre-wrap;color:#cbd5e1;font-size:.8rem;margin:8px 0 0">'+esc(slog.slice(0,3000))+'</pre></div>';
    }
    document.getElementById('tk-hist').innerHTML=html;
  }

  function channelAllowed(content){
    var c=String(content||'');
    if(isTechOrAdmin()) return true;
    // Client: hide internal tech↔admin and private tags
    if(/\[Technicien\s*→\s*Administrateur\]/i.test(c)) return false;
    if(/\[Admin\s*→\s*Technicien\]/i.test(c)) return false;
    if(/\[Interne\]/i.test(c)) return false;
    if(/tech_private|note privée|note privee/i.test(c)) return false;
    return true;
  }

  function renderComments(rows){
    rows=(rows||[]).filter(function(c){ return channelAllowed(c.content); });
    var box=document.getElementById('tk-msgs');
    if(!box) return;
    if(!rows.length){ box.innerHTML='<p class="msg">Aucun message pour le moment.</p>'; return; }
    box.innerHTML=rows.map(function(c){
      var raw=stripHtml(c.content||'');
      var admin=/Administrateur/i.test(raw);
      var who=c.owner||'Client';
      return '<div class="msg-row'+(admin?' admin-ch':'')+'"><div class="who">'+esc(who)+' · '+esc(fmt(c.creation))+'</div>'
        +'<div class="txt">'+esc(raw)+'</div></div>';
    }).join('');
  }

  function fallbackThreadFromDoc(){
    var rows=[];
    if(DOC && DOC.description){
      rows.push({ owner:'Client', creation:DOC.creation, content:DOC.description });
    }
    var ref=(DOC && (DOC.ss97_public_ref||name))||name||'';
    var st=(DOC && (DOC.ss97_ticket_status||DOC.ss97_payment_status))||'Paiement requis';
    rows.push({
      owner:'SS97 CLIENT CHATBOT',
      creation:DOC && DOC.modified,
      content:'[SS97 CLIENT CHATBOT] Ticket '+ref+' reçu. Complétez les infos manquantes (captures). Statut : '+st+'. Aucun paiement confirmé sans validation sécurisée. HUMAN_REVIEW_REQUIRED si doute.'
    });
    return rows;
  }

  function loadComments(){
    if(!name||!(window.frappe&&frappe.call)) return;
    /* Website User : Comment.get_list → Erreur d'autorisation — fil de secours sans appel. */
    if(!isTechOrAdmin() && !(TOKEN_ACCESS && followToken)){
      renderComments(CLIENT_DETAIL ? CLIENT_DETAIL.comments : []);
      return;
    }
    if(TOKEN_ACCESS && followToken){
      frappe.call({
        method:'ss97_ticket_public_detail',
        args:{ token:followToken, name:name },
        callback:function(r){
          var m=r.message||{};
          if(!m.found){ renderComments(fallbackThreadFromDoc()); return; }
          renderComments((m.comments&&m.comments.length)?m.comments:fallbackThreadFromDoc());
        },
        error:function(){ renderComments(fallbackThreadFromDoc()); }
      });
      return;
    }
    frappe.call({
      method:'frappe.client.get_list',
      args:{
        doctype:'Comment',
        filters:[['reference_doctype','=','Issue'],['reference_name','=',name]],
        fields:['name','content','comment_type','creation','owner'],
        order_by:'creation asc',
        limit_page_length:100
      },
      callback:function(r){
        var rows=r.message||[];
        renderComments(rows.length?rows:fallbackThreadFromDoc());
      },
      error:function(){ renderComments(fallbackThreadFromDoc()); }
    });
  }

  function loadFiles(){
    if(!name||!(window.frappe&&frappe.call)) return;
    /* Guest token : pas d'accès File list API (évite Method Not Allowed) */
    if(TOKEN_ACCESS && followToken && sessionUser()==='Guest'){
      var box=document.getElementById('tk-files');
      if(box) box.innerHTML='<p>Pièces jointes visibles après connexion à l’espace client, ou via le message ci-dessus.</p>';
      return;
    }
    /* Website User : File.get_list souvent interdit — upload reste possible. */
    if(!isTechOrAdmin()){
      var box0=document.getElementById('tk-files');
      if(box0) box0.innerHTML='<p>Ajoutez une pièce jointe via « Téléverser ». La liste détaillée peut être limitée selon les permissions.</p>';
      return;
    }
    frappe.call({
      method:'frappe.client.get_list',
      args:{
        doctype:'File',
        filters:[['attached_to_doctype','=','Issue'],['attached_to_name','=',name]],
        fields:['name','file_name','file_url','creation','is_private'],
        order_by:'creation desc',
        limit_page_length:40
      },
      callback:function(r){
        var rows=r.message||[];
        var box=document.getElementById('tk-files');
        if(!rows.length){ box.innerHTML='<p>Aucune pièce jointe pour le moment.</p>'; return; }
        box.innerHTML=rows.map(function(f){
          var url=f.file_url||'#';
          return '<div style="padding:6px 0;border-bottom:1px solid #1e293b"><a href="'+esc(url)+'" target="_blank" rel="noopener">'
            +esc(f.file_name||'fichier')+'</a> <span style="color:#64748b;font-size:.75rem">'+esc(fmt(f.creation))+'</span></div>';
        }).join('');
      },
      error:function(){
        var box=document.getElementById('tk-files');
        if(box) box.innerHTML='<p>Pièces jointes : utilisez « Téléverser » pour ajouter un document à ce ticket.</p>';
      }
    });
  }

  function uploadFiles(fileList, done){
    var files=Array.prototype.slice.call(fileList||[]);
    if(!files.length){ done(true, 0); return; }
    var i=0, ok=0;
    function next(){
      if(i>=files.length){ done(ok>0, ok); return; }
      var file=files[i++];
      var xhr=new XMLHttpRequest();
      var fd=new FormData();
      fd.append('file', file, file.name);
      fd.append('is_private', '1');
      fd.append('folder', 'Home/Attachments');
      fd.append('doctype', 'Issue');
      fd.append('docname', name);
      xhr.open('POST', '/api/method/upload_file');
      if(window.frappe&&frappe.csrf_token) xhr.setRequestHeader('X-Frappe-CSRF-Token', frappe.csrf_token);
      xhr.onload=function(){
        if(xhr.status>=200 && xhr.status<300) ok++;
        next();
      };
      xhr.onerror=function(){ next(); };
      xhr.send(fd);
    }
    next();
  }

  var _msgSending=false;
  function sendMsg(){
    var body=(document.getElementById('msg-body').value||'').trim();
    var ch=document.getElementById('msg-channel').value||'Client→Technicien';
    var st=document.getElementById('msg-status');
    var files=document.getElementById('msg-files').files;
    var btn=document.getElementById('btn-msg');
    if(_msgSending){ return; }
    if(!body && !(files&&files.length)){ st.className='msg err'; st.textContent='Écrivez un message ou ajoutez une pièce jointe.'; return; }
    if(!name){ st.className='msg err'; st.textContent='Ticket manquant.'; return; }
    if(sessionUser()==='Guest' && !(TOKEN_ACCESS && followToken)){ st.className='msg err'; st.textContent='Connexion requise.'; return; }
    if(!isTechOrAdmin() && ch.indexOf('Technicien→Administrateur')===0){
      st.className='msg err'; st.textContent='Canal réservé au personnel.'; return;
    }
    _msgSending=true;
    if(btn){ btn.disabled=true; btn.textContent='Envoi…'; }
    st.className='msg'; st.textContent='Envoi en cours…';
    function unlock(){
      _msgSending=false;
      if(btn){ btn.disabled=false; btn.textContent='Envoyer'; }
    }
    function finish(content){
      if(TOKEN_ACCESS && followToken && sessionUser()==='Guest'){
        var plain=String(content||'').replace(/^\[[^\]]+\]\s*/, '');
        frappe.call({
          method:'ss97_ticket_public_message',
          args:{ token:followToken, name:name, content:plain, channel:ch },
          callback:function(r){
            unlock();
            var m=(r&&r.message)||{};
            if(!m.ok){ st.className='msg err'; st.textContent='Envoi impossible.'; return; }
            st.className='msg ok'; st.textContent='Votre message a été envoyé.';
            document.getElementById('msg-body').value='';
            loadComments(); loadDoc();
          },
          error:function(){ unlock(); st.className='msg err'; st.textContent='Envoi impossible.'; }
        });
        return;
      }
      frappe.call({
        method:isTechOrAdmin() ? 'frappe.client.insert' : 'ss97_client_ticket_api',
        args:isTechOrAdmin() ? { doc:{ doctype:'Comment', comment_type:'Comment', reference_doctype:'Issue', reference_name:name, content:content } } : {action:'comment',name:name,content:content},
        callback:function(){
          unlock();
          st.className='msg ok'; st.textContent='Votre message a été envoyé.';
          if(typeof frappe!=='undefined'&&frappe.call&&name){
            frappe.call({method:'ss97_ai_agent_dialogue_turn',args:{name:name},freeze:false,callback:function(){ loadDoc(); },error:function(){}});
          }
          document.getElementById('msg-body').value='';
          document.getElementById('msg-files').value='';
          loadDoc();
        },
        error:function(){
          unlock();
          st.className='msg err'; st.textContent='Une erreur est survenue. Veuillez réessayer.';
        }
      });
    }
    if(files&&files.length){
      uploadFiles(files, function(success, n){
        var extra=success? ('\nPièces jointes téléversées: '+n) : '\n(Échec téléversement PJ — message texte conservé)';
        finish('['+ch+'] '+body+extra);
      });
    } else {
      finish('['+ch+'] '+body);
    }
  }

  function setupStars(id, key){
    var box=document.getElementById(id); if(!box) return;
    box.innerHTML='';
    for(var i=1;i<=5;i++){
      (function(n){
        var b=document.createElement('button');
        b.type='button'; b.textContent='★'; b.setAttribute('aria-label', n+' étoiles');
        b.onclick=function(){ RATES[key]=n; renderStars(id,key); };
        box.appendChild(b);
      })(i);
    }
    renderStars(id,key);
  }
  function renderStars(id,key){
    var box=document.getElementById(id); if(!box) return;
    var btns=box.querySelectorAll('button');
    for(var i=0;i<btns.length;i++){ btns[i].className=(i<RATES[key]?'on':''); }
  }
  function setupRating(d){
    var closed=!!d.ss97_closed_on || /ferm|clôtur|clotur|ticket clôtur|archiv|termin|closed/i.test(String(d.ss97_ticket_status||d.status||''));
    var card=document.getElementById('tk-rate-card');
    if(!closed){ card.style.display='none'; return; }
    card.style.display='block';
    if(Number(d.ss97_satisfaction||0)>0){
      document.getElementById('rate-status').className='msg ok';
      document.getElementById('rate-status').textContent='Évaluation déjà enregistrée : '+d.ss97_satisfaction+'/5';
    }
    ['rate-global','rate-punct','rate-prof','rate-qual','rate-comm'].forEach(function(id,idx){
      setupStars(id, ['global','punct','prof','qual','comm'][idx]);
    });
  }

  function submitRating(){
    var st=document.getElementById('rate-status');
    if(!RATES.global){ st.className='msg err'; st.textContent='Choisissez une note globale.'; return; }
    var comment=(document.getElementById('rate-comment').value||'').trim();
    var detail='Ponctualité '+RATES.punct+'/5 · Professionnalisme '+RATES.prof+'/5 · Qualité '+RATES.qual+'/5 · Communication '+RATES.comm+'/5';
    st.className='msg'; st.textContent='Enregistrement…';
    frappe.call({
      method:'frappe.client.set_value',
      args:{ doctype:'Issue', name:name, fieldname:'ss97_satisfaction', value:RATES.global },
      callback:function(){
        frappe.call({
          method:'frappe.client.insert',
          args:{ doc:{ doctype:'Comment', comment_type:'Info', reference_doctype:'Issue', reference_name:name,
            content:'[Evaluation] Note '+RATES.global+'/5 — '+detail+(comment?(' — '+comment):'') } },
          callback:function(){
            st.className='msg ok'; st.textContent='Merci — évaluation enregistrée.';
            try{
              frappe.call({
                method:'frappe.client.set_value',
                args:{ doctype:'Issue', name:name, fieldname:'ss97_ai_closure_status', value:'closed' }
              });
            }catch(e){}
            loadComments(); loadDoc();
          },
          error:function(){ st.className='msg ok'; st.textContent='Note enregistrée.'; }
        });
      },
      error:function(){ st.className='msg err'; st.textContent='Impossible d enregistrer la note.'; }
    });
  }

  function clearTicket(message){
    DOC=null;
    CLIENT_DETAIL=null;
    TOKEN_ACCESS=false;
    document.getElementById('tk-head').textContent=message;
    ['tk-client','tk-tech','tk-msgs','tk-interv','tk-files','tk-pay','tk-report','tk-hist'].forEach(function(id){
      var el=document.getElementById(id); if(el) el.innerHTML='';
    });
    var rating=document.getElementById('tk-rate-card'); if(rating) rating.style.display='none';
  }

  function applyTicketDoc(d){
    if(!canAccess(d)){
      clearTicket('Accès refusé — ce ticket ne vous appartient pas.');
      ['tk-client','tk-tech','tk-msgs','tk-interv','tk-files','tk-pay','tk-report','tk-hist'].forEach(function(id){
        var el=document.getElementById(id); if(el) el.innerHTML='';
      });
      return;
    }
    DOC=d;
    renderHead(d); renderProgress(d); renderClient(d); renderTech(d);
    renderInterv(d); renderPay(d); renderReport(d); renderTimeline(d);
    setupRating(d); loadComments(); loadFiles();
  }

  function loadDoc(){
    if(!name){ document.getElementById('tk-head').innerHTML='<p class="msg err">Référence manquante. Ouvrez un ticket depuis Mes tickets.</p>'; return; }
    if(!(window.frappe&&frappe.call)){ document.getElementById('tk-head').innerHTML='<p class="msg err">Session indisponible.</p>'; return; }
    if(sessionUser()==='Guest' && followToken){
      frappe.call({
        method:'ss97_ticket_public_detail',
        args:{ token:followToken, name:name },
        callback:function(r){
          var m=r.message||{};
          if(!m.found || !m.ticket){
            document.getElementById('tk-head').innerHTML='<p class="msg err">Lien sécurisé invalide ou expiré. <a href="/suivre-mon-ticket" style="color:#7dd3fc">Rechercher mon ticket</a></p>';
            return;
          }
          TOKEN_ACCESS=true;
          applyTicketDoc(m.ticket);
        },
        error:function(){
          document.getElementById('tk-head').innerHTML='<p class="msg err">Consultation temporairement indisponible.</p>';
        }
      });
      return;
    }
    if(sessionUser()==='Guest'){
      clearTicket('Connexion requise.');
      document.getElementById('tk-head').innerHTML='<p class="msg err">Connexion requise. <a href="/connexion-client?redirect-to='
        +encodeURIComponent('/espace-client/ticket?name='+name)+'" style="color:#7dd3fc">Se connecter</a></p>';
      return;
    }
    if(!isTechOrAdmin()){
      frappe.call({
        method:'ss97_client_ticket_api',
        args:{action:'get',name:name},
        callback:function(r){
          CLIENT_DETAIL=r.message||null;
          if(!CLIENT_DETAIL || !CLIENT_DETAIL.doc){ clearTicket('Ticket inaccessible.'); return; }
          applyTicketDoc(CLIENT_DETAIL.doc);
        },
        error:function(){ clearTicket('Session expirée ou ticket inaccessible.'); }
      });
      return;
    }
    frappe.call({
      method:'frappe.client.get',
      args:{ doctype:'Issue', name:name },
      callback:function(r){ applyTicketDoc(r.message||{}); },
      error:function(){ clearTicket('Session expirée ou ticket inaccessible.'); }
    });
  }

  document.getElementById('btn-msg').onclick=sendMsg;
  document.getElementById('btn-refresh-msg').onclick=loadComments;
  var _btnPay=document.getElementById('btn-pay-now');
  if(_btnPay) _btnPay.onclick=clientPayNow;
  var _btnAdmPay=document.getElementById('btn-admin-request-pay');
  if(_btnAdmPay) _btnAdmPay.onclick=adminRequestPayment;
  document.getElementById('btn-att').onclick=function(){
    var st=document.getElementById('att-status');
    var files=document.getElementById('att-files').files;
    if(!files||!files.length){ st.className='msg err'; st.textContent='Choisissez un fichier.'; return; }
    st.className='msg'; st.textContent='Téléversement…';
    uploadFiles(files, function(ok,n){
      st.className=ok?'msg ok':'msg err';
      st.textContent=ok? (n+' fichier(s) ajouté(s).') : 'Échec téléversement.';
      document.getElementById('att-files').value='';
      loadFiles();
      if(ok){
        frappe.call({
          method:'frappe.client.insert',
          args:{ doc:{ doctype:'Comment', comment_type:'Info', reference_doctype:'Issue', reference_name:name,
            content:'[Client→Technicien] Pièce(s) jointe(s) ajoutée(s): '+n } },
          callback:loadComments
        });
      }
    });
  };
  document.getElementById('btn-print-report').onclick=function(){ window.print(); };
  document.getElementById('btn-rate').onclick=submitRating;

  function boot(){
    loadDoc();
    maybeConfirmReturn();
  }
  if(window.frappe&&frappe.ready) frappe.ready(boot);
  else setTimeout(boot, 500);
  setInterval(function(){ if(name&&DOC&&window.frappe&&!document.hidden) loadComments(); }, 5000);
  /* Sync automatique Client/Admin/Tech — actualisation contrôlée sans rechargement manuel */
  setInterval(function(){ if(name&&DOC&&window.frappe&&!document.hidden) loadDoc(); }, 5000);
  setInterval(function(){
    if(!DOC) return;
    var el=document.getElementById('tk-elapsed');
    if(el) el.textContent=elapsedSince(DOC.creation);
  }, 1000);
})();
</script>
"""
    js = js.replace("PAY_LINK_PLACEHOLDER", json.dumps(pay_link))
    return body, js
