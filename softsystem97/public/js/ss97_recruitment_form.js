/* SS97 Job Applicant Web Form: explanatory choices and document safeguards.
 * Server validation remains authoritative. Nothing here certifies identity.
 */
(function () {
  "use strict";
  if (!/^\/ss97-job-apply(?:\/|$)/.test(window.location.pathname)) return;

  var notes = {
    cv_file: "CV : PDF uniquement, 8 Mo maximum. Expérience et parcours professionnel.",
    cover_letter_file: "Lettre de motivation : PDF uniquement, 8 Mo maximum.",
    photo_file: "Photo : JPG ou PNG uniquement, 8 Mo maximum.",
    diploma_file: "Diplôme ou attestation de compétence : PDF, JPG ou PNG, 8 Mo maximum.",
    id_document_file: "Identité : pièce officielle lisible, PDF, JPG ou PNG, 8 Mo maximum. Ne communiquez pas votre pièce dans un message public."
  };

  function addHelp(fieldname, message) {
    var field = document.querySelector('[data-fieldname="' + fieldname + '"]');
    if (!field || field.querySelector('.ss97-field-guidance')) return;
    var help = document.createElement('p');
    help.className = 'ss97-field-guidance';
    help.style.cssText = 'font-size:.85rem;line-height:1.5;color:#45546a;margin:.3rem 0 .6rem';
    help.textContent = message;
    field.appendChild(help);
  }

  function enhance() {
    var select = document.querySelector('select[data-fieldname="technician_type"]');
    if (!select) return false;
    if (!select.options.length) {
      // A cached copy of the old Web Form must remain usable. The Frappe
      // migration also repairs the authoritative Select metadata in the DB.
      [['', 'Choisir votre parcours'], ['N2', 'N2 — Informatique généraliste'],
        ['N3', 'N3 — Assistance bancaire'], ['N4', 'N4 — Cybersécurité']]
        .forEach(function (item) {
          var option = document.createElement('option');
          option.value = item[0];
          option.textContent = item[1];
          select.appendChild(option);
        });
    }
    addHelp('technician_type', 'Choisissez N2 (généraliste), N3 (banque) ou N4 (cybersécurité). La candidature ne donne pas accès aux interventions avant examen et validation humaine.');
    Object.keys(notes).forEach(function (key) { addHelp(key, notes[key]); });
    addHelp('id_document_file', 'Le contrôle de format ne garantit pas l’authenticité de la pièce : un responsable doit la vérifier avant toute habilitation.');
    return true;
  }

  if (!enhance()) {
    var observer = new MutationObserver(function () {
      if (enhance()) observer.disconnect();
    });
    observer.observe(document.documentElement, {childList: true, subtree: true});
    window.addEventListener('load', enhance, {once: true});
  }
})();
