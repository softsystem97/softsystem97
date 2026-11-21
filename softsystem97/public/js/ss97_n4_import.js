(() => {
  "use strict";
  const form = document.getElementById("n4-csv-form");
  const info = document.getElementById("n4-csv-status");
  if (!form || !info) return;
  const post = async (url, body, json=false) => {
    const headers = {"X-Frappe-CSRF-Token": window.frappe?.csrf_token || ""};
    if (json) headers["Content-Type"]="application/json";
    const resp = await fetch(url, {method:"POST",credentials:"same-origin",headers,body});
    const reply = await resp.json().catch(()=>({}));
    if (!resp.ok || reply.exc) throw Error("Import refusé : fichier ou permissions à vérifier.");
    return reply.message;
  };
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const input = document.getElementById("n4-csv-file");
    const file = input.files?.[0];
    const confirm = document.getElementById("n4-csv-ack");
    if (!file || !confirm.checked || !file.name.toLowerCase().endsWith(".csv")
        || !file.size || file.size > 200000) {
      info.textContent="Sélectionnez le lot CSV et confirmez l'import inactif.";
      return;
    }
    const button = form.querySelector("button[type=submit]");
    button.disabled=true;
    info.textContent="Envoi dans le stockage privé ERPNext…";
    try {
      const body = new FormData();
      body.append("file",file);
      body.append("is_private","1");
      const attachment = await post("/api/method/upload_file",body);
      if (!attachment?.name) throw Error("Fichier privé non enregistré.");
      const result = await post(
        "/api/method/softsystem97.technician_exams.private_import.import_inactive_n4",
        JSON.stringify({file_id:attachment.name,
                        acknowledgement:"IMPORTER_40_INACTIVES"}),true);
      info.textContent=String(result.imported_count)+
        " questions enregistrées. Questions actives : 0. Revue humaine obligatoire.";
      form.reset();
    } catch(error) {info.textContent=error.message;}
    finally {button.disabled=false;}
  });
})();