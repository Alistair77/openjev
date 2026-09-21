const seed = [
  { type: "choice", instructions: "Which team should handle this ticket?", criteria: "billing | Charges, invoices, payment problems, duplicate charges, or refunds.\ntechnical | Bugs, crashes, errors, or product failures.\nother | A request that fits neither billing nor technical." },
  { type: "score", instructions: "How urgent is this support request?", criteria: "Routine request with no immediate impact.\nA problem that should be addressed soon.\nA repeated or high-impact problem requiring priority attention." },
  { type: "noul", instructions: "The customer explicitly requests a refund.", criteria: "" }
];
const questions = document.querySelector("#questions");
const template = document.querySelector("#choice-template");
const count = document.querySelector("#question-count");
const error = document.querySelector("#form-error");

function refreshCount() { count.textContent = `${questions.children.length} decision${questions.children.length === 1 ? "" : "s"}`; }
function addQuestion(data = { type: "choice", instructions: "", criteria: "option_a | Describe this option.\noption_b | Describe this option." }) {
  const node = template.content.firstElementChild.cloneNode(true);
  const type = node.querySelector(".question-type"); const instructions = node.querySelector(".instructions"); const criteria = node.querySelector(".criteria"); const criteriaLabel = node.querySelector(".criteria-label");
  type.value = data.type; instructions.value = data.instructions; criteria.value = data.criteria;
  function sync() { const isNoul = type.value === "noul"; criteriaLabel.hidden = isNoul; if (type.value === "score") criteria.placeholder = "Low level description\nHigh level description"; else if (type.value === "choice") criteria.placeholder = "key | description"; }
  type.addEventListener("change", sync); node.querySelector(".remove-question").addEventListener("click", () => { node.remove(); refreshCount(); }); sync(); questions.append(node); refreshCount();
}
seed.forEach(addQuestion); document.querySelector("#add-question").addEventListener("click", () => addQuestion());
function parseQuestion(node, index) {
  const type = node.querySelector(".question-type").value; const instructions = node.querySelector(".instructions").value.trim(); const raw = node.querySelector(".criteria").value.trim();
  if (!instructions) throw new Error(`Question ${index + 1} needs instructions.`);
  if (type === "noul") return { type, instructions };
  const lines = raw.split("\n").map(line => line.trim()).filter(Boolean); if (lines.length < 2) throw new Error(`Question ${index + 1} needs at least two options or levels.`);
  if (type === "score") return { type, instructions, criteria: lines };
  const criteria = {}; lines.forEach(line => { const [key, ...rest] = line.split("|"); if (!key || !rest.length) throw new Error("Choice options use key | description."); criteria[key.trim()] = rest.join("|").trim(); }); return { type, instructions, criteria };
}
function escapeHtml(value) { return String(value).replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c])); }
function renderAnswer(id, answer) {
  const value = answer.type === "choice" ? answer.choice : answer.type === "score" ? `${answer.score.toFixed(2)} / ${Object.keys(answer.legend).length - 1}` : `${(answer.noul * 100).toFixed(1)}%`;
  const rows = Object.entries(answer.probabilities).sort((a,b) => b[1]-a[1]).map(([key, probability]) => `<div class="probability"><span>${escapeHtml(answer.legend?.[key] || key)}</span><strong>${(probability * 100).toFixed(1)}%</strong><div class="meter"><i style="width:${probability * 100}%"></i></div></div>`).join("");
  return `<article class="answer"><div class="answer-top"><div><div class="answer-id">${escapeHtml(id)} · ${answer.type}</div><div class="answer-value">${escapeHtml(value)}</div></div><span class="answer-status ${answer.abstained ? "abstained" : ""}">${answer.abstained ? "Abstained" : "Actionable"}</span></div><div class="distribution">${rows}</div><p class="answer-meta">Confidence ${(answer.confidence * 100).toFixed(1)}% · Margin ${((answer.margin || 0) * 100).toFixed(1)}%${answer.abstention_reason ? ` · ${escapeHtml(answer.abstention_reason)}` : ""}</p></article>`;
}
document.querySelector("#decision-form").addEventListener("submit", async event => {
  event.preventDefault(); error.textContent = ""; const submit = event.currentTarget.querySelector(".evaluate");
  try {
    const payload = { state: document.querySelector("#state").value.trim(), questions: {}, options: { abstain_below: Number(document.querySelector("#threshold").value), top_k: Number(document.querySelector("#top-k").value), trace: true } };
    if (!payload.state) throw new Error("State cannot be empty."); [...questions.children].forEach((node, index) => payload.questions[`decision_${index + 1}`] = parseQuestion(node, index));
    submit.disabled = true; submit.querySelector("span").textContent = "Evaluating locally";
    const backend = document.querySelector("#backend").value; const response = await fetch("/v1/evaluate", { method:"POST", headers:{"Content-Type":"application/json", "X-OpenJev-Backend": backend}, body:JSON.stringify(payload) });
    const data = await response.json(); if (!response.ok) throw new Error(data.detail?.message || "Evaluation failed.");
    document.querySelector("#result-empty").hidden = true; const list = document.querySelector("#answer-list"); list.hidden = false; list.innerHTML = Object.entries(data.answers).map(([id, answer]) => renderAnswer(id, answer)).join("");
    document.querySelector("#result-title").textContent = `${Object.keys(data.answers).length} decisions evaluated`; document.querySelector("#latency").textContent = `${data.backend} · ${data.latency_ms.toFixed(1)} ms`;
    document.querySelector("#raw-response").hidden = false; document.querySelector("#raw-json").textContent = JSON.stringify(data, null, 2);
  } catch (issue) { error.textContent = issue.message; } finally { submit.disabled = false; submit.querySelector("span").textContent = "Evaluate decision set"; }
});
document.addEventListener("keydown", event => { if ((event.metaKey || event.ctrlKey) && event.key === "Enter") document.querySelector("#decision-form").requestSubmit(); });
