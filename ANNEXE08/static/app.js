const fileinput = document.getElementById('fileinput');
const dropzone = document.getElementById('dropzone');
const uploadBtn = document.getElementById('uploadBtn');
const recordsDiv = document.getElementById('records');
const saveBtn = document.getElementById('saveBtn');
const exportBtn = document.getElementById('exportBtn');
const downloadLink = document.getElementById('downloadLink');

let currentRecords = [];

uploadBtn.addEventListener('click', async ()=>{
  const files = fileinput.files;
  if (!files || files.length===0) { alert('Select files first'); return }
  const fd = new FormData();
  for (let i=0;i<files.length;i++) fd.append('files', files[i]);
  uploadBtn.disabled = true; uploadBtn.textContent='Uploading...'
  const res = await fetch('/upload', {method:'POST', body: fd});
  const j = await res.json();
  uploadBtn.disabled=false; uploadBtn.textContent='Upload & Process'
  if (j.status==='ok'){
    // flatten results into currentRecords
    currentRecords = [];
    for (const f of j.results){
      for (const r of f.records){
        const id = r.record_id;
        const cand = r.candidate;
        const spouse = r.spouse || {};
        const rec = {id:id, ...cand, spouse_nom: spouse.nom || ''};
        currentRecords.push(rec);
      }
    }
    renderRecords();
  } else alert('Upload failed')
});

function renderRecords(){
  if (currentRecords.length===0){ recordsDiv.innerHTML='<p>No records yet.</p>'; return }
  let html = '<table><thead><tr>'+
    '<th>Nom</th><th>Prénom</th><th>Date naissance</th><th>Nature</th><th>Lieu</th><th>Nom père</th><th>Nom mère</th><th>Sexe</th><th>Situation</th><th>Spouse</th>'+
    '</tr></thead><tbody>';
  for (let i=0;i<currentRecords.length;i++){
    const r = currentRecords[i];
    html += `<tr data-index="${i}">`+
      `<td><input data-field="nom" value="${r.nom || ''}"></td>`+
      `<td><input data-field="prenom" value="${r.prenom || ''}"></td>`+
      `<td><input data-field="date_naissance" value="${r.date_naissance || ''}"></td>`+
      `<td><input data-field="nature_date" value="${r.nature_date || ''}"></td>`+
      `<td><input data-field="lieu_naissance" value="${r.lieu_naissance || ''}"></td>`+
      `<td><input data-field="nom_pere" value="${r.nom_pere || ''}"></td>`+
      `<td><input data-field="nom_mere" value="${r.nom_mere || ''}"></td>`+
      `<td><input data-field="sexe" value="${r.sexe || ''}"></td>`+
      `<td><input data-field="situation_familiale" value="${r.situation_familiale || ''}"></td>`+
      `<td><input data-field="spouse_nom" value="${r.spouse_nom || ''}"></td>`+
      `</tr>`;
  }
  html += '</tbody></table>';
  recordsDiv.innerHTML = html;
  // attach change listeners
  document.querySelectorAll('#records input').forEach(inp=>{
    inp.addEventListener('input', (e)=>{
      const tr = e.target.closest('tr');
      const idx = Number(tr.getAttribute('data-index'));
      const field = e.target.getAttribute('data-field');
      currentRecords[idx][field] = e.target.value;
    })
  })
}

saveBtn.addEventListener('click', async ()=>{
  const res = await fetch('/save-records', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({records: currentRecords})});
  const j = await res.json();
  if (j.status==='saved') alert('Saved'); else alert('Save error');
});

exportBtn.addEventListener('click', async ()=>{
  const res = await fetch('/export', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({records: currentRecords})});
  const j = await res.json();
  if (j.status==='ok'){
    const filename = j.filename;
    downloadLink.href = `/download/${filename}`;
    downloadLink.style.display='inline-block';
    downloadLink.textContent = 'Download XLSX';
    downloadLink.download = filename;
    alert('Exported: click Download XLSX link')
  } else alert('Export failed')
});
