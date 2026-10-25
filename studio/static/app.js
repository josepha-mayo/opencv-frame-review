"use strict";

(() => {
  const byId = (id) => document.getElementById(id);
  const ui = {
    form: byId("upload-form"), file: byId("clip-file"), fileInfo: byId("file-info"),
    analyze: byId("analyze-button"), profile: byId("server-profile"), connectionError: byId("connection-error"),
    empty: byId("empty-state"), jobArea: byId("job-area"), jobFile: byId("job-file"),
    statusPill: byId("status-pill"), status: byId("job-status"), error: byId("job-error"), retry: byId("retry-button"),
    candidates: byId("candidate-area"), candidateList: byId("candidate-list"), candidateOptions: byId("candidate-options"),
    image: byId("candidate-overlay"), imageError: byId("overlay-error"), caption: byId("overlay-caption"),
    facts: byId("candidate-facts"), reviewed: byId("review-checkbox"), approve: byId("approve-button"),
    reviewActions: byId("review-actions"), decline: byId("decline-button"), cancel: byId("cancel-button"),
    results: byId("results-panel"), highlights: byId("result-highlights"), raw: byId("raw-report"),
    artifactsArea: byId("artifacts-area"), artifacts: byId("artifact-list"),
    boundaryRows: byId("boundary-review-rows"), boundaryStatus: byId("boundary-review-status"),
    boundaryError: byId("boundary-review-error"), boundaryWarning: byId("boundary-return-warning"),
    boundaryValues: byId("boundary-return-values"), boundaryProvenance: byId("boundary-provenance"),
    boundaryData: byId("boundary-provenance-data"),
    protectX: byId("protect-x"), protectY: byId("protect-y"), protectW: byId("protect-width"), protectH: byId("protect-height"),
    protectPick: byId("protect-pick"), protectCheck: byId("protect-check"), protectClear: byId("protect-clear"),
    protectStatus: byId("protect-status"), protectError: byId("protect-error"), protectRect: byId("protected-rectangle"),
    protectOverlays: byId("protected-overlays"), protectCount: byId("protected-count"), planSummary: byId("plan-summary"),
    serviceScope: byId("service-scope"), serviceBadge: byId("service-badge"), cloudSamples: byId("cloud-samples"), demo: byId("demo-button")
  };
  const recovery = { area: byId("recovery-area"), status: byId("recovery-status"),
    retry: byId("recovery-retry"), dismiss: byId("recovery-dismiss") };
  const RECOVERY_KEY = "frame-review:last-job:v1";
  let recoveryId = null;
  let recovering = false;
  function validJobId(value) { return typeof value === "string" && /^[0-9a-f]{32}$/.test(value); }
  function rememberJob(id) {
    try { window.sessionStorage.setItem(RECOVERY_KEY, id); }
    catch (_) {
      recovery.area.hidden = false;
      recovery.status.textContent = "This browser cannot save the job reference. Keep this tab open until you finish reviewing and downloading.";
    }
  }
  function forgetRecovery() {
    if (recovering) return;
    try { window.sessionStorage.removeItem(RECOVERY_KEY); } catch (_) {}
    recoveryId = null;
    recovery.area.hidden = true;
    updateControls();
  }
  async function restoreJob() {
    if (!recoveryId || recovering) return;
    recovering = true;
    recovery.area.hidden = false;
    recovery.retry.hidden = true;
    recovery.dismiss.hidden = true;
    recovery.status.textContent = "Reopening the previous job from this tab. No upload or review decision is being repeated.";
    updateControls();
    const previousJob = job;
    try {
      const next = await request("/api/jobs/" + recoveryId);
      if (!next || next.id !== recoveryId || typeof next.status !== "string" || !Object.prototype.hasOwnProperty.call(STATUS, next.status)) throw new Error("The server did not return the saved job with a recognized status.");
      job = next;
      stateUncertain = false;
      selectedId = null;
      candidateFingerprint = null;
      ui.reviewed.checked = false;
      protectionPlan = null;
      renderJob();
      schedulePoll();
      recoveryId = null;
      recovery.status.textContent = "Previous job reopened. No decision was repeated. Unsubmitted areas and consent are not saved; check the plan again before generating an edit.";
    } catch (error) {
      stopPolling();
      job = previousJob;
      candidateFingerprint = null;
      selectedId = null;
      protectionPlan = null;
      imageLoaded = false;
      ui.reviewed.checked = false;
      ui.jobArea.hidden = true;
      ui.results.hidden = true;
      ui.empty.hidden = false;
      recovery.status.textContent = "Could not reopen the previous job. " + error.message + " Retry to check its status, or forget this reference to choose another clip. Forgetting does not cancel or delete the server job.";
      recovery.retry.hidden = false;
      recovery.dismiss.hidden = false;
    } finally {
      recovering = false;
      updateControls();
    }
  }
  const exportMode = byId("export-mode"), exportModeNote = byId("export-mode-note");
  const steadyReview = byId("steady-state-review"), steadyAlternate = byId("steady-alternate");
  let alternateLoaded = false;
  const STEADY_NOTE = "Hold the observed brightness state inside the caret box while keeping every original color sample on its timeline. Small color variation inside the caret can remain. Refuses any RGB change outside the actual box, changed teaching areas, timing/audio or worse cut points. Review both states and every cut.";
  const protectLabel = byId("protect-label"), protectList = byId("protected-list"), protectAdd = byId("protect-add");
  let savedRegions = [];
  let editingRegionIndex = null;
  const protectEditCancel = byId("protect-edit-cancel"), protectEditStatus = byId("protect-edit-status");
  const protectPickCancel = byId("protect-pick-cancel");
  let pickDraft = null;
  const MAX_BYTES = 64 * 1024 * 1024;
  const prepareLesson = byId("prepare-lesson"), clipStart = byId("clip-start"), clipDuration = byId("clip-duration");
  const preparationNotice = byId("preparation-notice"), preparationPreview = byId("preparation-preview");
  const realDemo = byId("real-demo-button");
  const realChallenge = byId("real-challenge-button");
  const naturalDemo = byId("natural-demo-button");
  const naturalExample = byId("natural-example");
  const teachingGuide = byId("teaching-guide"), teachingGuideLoad = byId("teaching-guide-load");
  const naturalChoices = {
    joomla: {button:"Try the real Joomla reading pause",description:"VolodyA! V Anarhist, Free Art License as listed. Prepared 12-second installation lesson from a real Ogg/Theora source, with prepared audio and a natural root-prompt caret. No added defect. Load the suggested commands/output and prompt-flank areas, then inspect and check the plan. This prepared example repeats the separately qualified original-upload case."},
    gentoo: {button:"Try the real package-progress lesson",description:"Vitaly Zdanevich, CC0 as listed. Prepared 12-second package tutorial: changing progress beside a naturally blinking caret. Silent source. No added defect. Teaching-area suggestions are available after analysis; review them before checking the plan."},
    terminal: {button:"Try a real terminal blink",description:"Info-farmer, CC0. Prepared 12-second Tamil lesson, with a natural caret and prepared narration. No added defect. Suggested teaching area: [0, 0, 640, 336]."},
    jupyter: {button:"Try a real Jupyter reading pause",description:"Alex The Analyst, CC BY 3.0. Prepared English lesson with a natural caret; no added defect. Suggested code/output area: [52, 96, 552, 45]. Source license and preparation history are linked below."},
    npm: {button:"Try a real command-line pause",description:"Kevin Powell, CC BY 3.0. Prepared English lesson with a natural command-prompt caret; no added defect. Suggested command area: [0, 0, 480, 236]. Source license and preparation history are linked below."}
  };
  function updateNaturalChoice() {
    const example = naturalChoices[naturalExample.value] ? naturalExample.value : "terminal";
    naturalDemo.textContent = naturalChoices[example].button;
    byId("natural-example-description").textContent = naturalChoices[example].description;
    byId("natural-example-download").setAttribute("href","/api/samples/natural-"+example+".mp4");
    byId("natural-example-credit").setAttribute("href","/api/samples/natural-"+example+"-credit.json");
  }
  naturalExample.addEventListener("change",updateNaturalChoice);
  const ACTIVE = new Set(["queued", "analyzing", "exporting"]);
  const TERMINAL = new Set(["complete", "declined", "failed", "cancelled"]);
  const STATUS = {
    queued: ["Queued", "The clip is queued for validation and analysis."],
    analyzing: ["Analyzing", "Validating the clip and identifying candidate regions. No playback is used here."],
    review: ["Review needed", "Inspect the proposed region and interval, then approve a candidate or leave the clip unchanged."],
    exporting: ["Encoding", "Encoding the approved edit and measuring the actual encoded result."],
    complete: ["Processing complete", "Encoding and measurements are complete. Even passing numeric checks still requires creator review."],
    declined: ["Left unchanged", "You chose to leave the clip unchanged. No candidate was approved."],
    failed: ["Stopped", "This job could not be completed. See the details below."],
    cancelled: ["Cancelled", "The job was cancelled."]
  };
  let token = null;
  let job = null;
  let selectedId = null;
  let candidateFingerprint = null;
  let imageLoaded = false;
  let imageVersion = 0;
  let busy = false;
  let stateUncertain = false;
  let pollTimer = null;
  let refreshInFlight = false;
  let requestEpoch = 0;
  let boundaryVersion = 0;
  let protectionPlan = null;
  let picking = false;
  let firstCorner = null;
  let protectionVersion = 0;

  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = String(text);
    if (className) node.className = className;
    return node;
  }

  function showError(node, message) {
    node.textContent = message || "";
    node.hidden = !message;
  }

  function pretty(value) {
    if (value === null || value === undefined) return "Not reported";
    if (typeof value === "number") return Number.isFinite(value) ? String(value) : "Not reported";
    if (typeof value === "boolean") return value ? "Yes" : "No";
    if (typeof value === "string") return value;
    return JSON.stringify(value);
  }

  function readableKey(key) {
    return String(key).replace(/[_-]+/g, " ").replace(/\b\w/, (char) => char.toUpperCase());
  }

  function addFact(list, label, value) {
    const group = element("div");
    group.append(element("dt", label), element("dd", pretty(value)));
    list.append(group);
  }

  // Reject absolute URLs and network-path references before assigning src/href.
  // This interface never fetches media or artifacts from another origin.
  function localURL(value) {
    if (typeof value !== "string" || !value || /[\\\u0000-\u0020]/.test(value)) return null;
    if (value.startsWith("//") || /^[a-z][a-z0-9+.-]*:/i.test(value)) return null;
    try {
      const parsed = new URL(value, window.location.origin + "/");
      return parsed.origin === window.location.origin ? parsed.pathname + parsed.search + parsed.hash : null;
    } catch (_) { return null; }
  }

  async function request(path, options = {}) {
    const method = options.method || "GET";
    const headers = new Headers(options.headers || {});
    headers.set("Accept", "application/json");
    if (method === "POST") {
      if (!token) throw new Error("The local server token is missing. Reload this page before continuing.");
      headers.set("X-App-Token", token);
    }
    let response;
    try {
      response = await fetch(path, { ...options, method, headers, credentials: "same-origin", cache: "no-store", redirect: "error" });
    } catch (_) {
      throw new Error("The local server could not be reached. Check that it is running, then try again.");
    }
    let data;
    try { data = await response.json(); }
    catch (_) { throw new Error("The local server returned an unreadable response."); }
    if (!response.ok) {
      const detail = data && (data.error || data.message || data.detail);
      throw new Error(detail ? pretty(detail) : "The local server could not complete this request (" + response.status + ").");
    }
    return data;
  }

  function currentCandidate() {
    return (job?.candidates || []).find((candidate) => String(candidate.id) === selectedId);
  }

  function updateControls() {
    const locked = recovering || Boolean(recoveryId) || Boolean(job && !TERMINAL.has(job.status));
    recovery.retry.disabled = recovering || !token;
    recovery.dismiss.disabled = recovering;
    ui.file.disabled = busy || !token || locked;
    ui.demo.disabled = busy || !token || locked;
    naturalDemo.disabled = busy || !token || locked;
    naturalExample.disabled = naturalDemo.disabled;
    realDemo.disabled = busy || !token || locked;
    realChallenge.disabled = busy || !token || locked;
    [prepareLesson, clipStart, clipDuration].forEach(node => { node.disabled = busy || locked; });
    const file = ui.file.files[0];
    ui.analyze.disabled = busy || !token || locked || !file || file.size === 0 || file.size > MAX_BYTES;
    ui.analyze.textContent = busy && !job ? "Sending file…" : "Analyze selected file ↗";
    const canReview = job?.status === "review" && !busy && !refreshInFlight && !stateUncertain;
    const steady = currentCandidate()?.action === "steady-detail-v1";
    const imagesReady = imageLoaded && (!steady || alternateLoaded);
    ui.reviewed.disabled = !canReview || !imagesReady || editingRegionIndex !== null || picking;
    ui.approve.disabled = !canReview || !imageLoaded || !ui.reviewed.checked || !imagesReady || !currentCandidate()?.recipe_sha256 || !job?.prediction_sha256 || !protectionPlan || editingRegionIndex !== null || picking;
    [ui.protectX, ui.protectY, ui.protectW, ui.protectH, ui.protectPick, ui.protectCheck, ui.protectClear, exportMode, protectLabel, protectAdd].forEach((node) => { node.disabled = !canReview || !imageLoaded; });
    exportMode.disabled = !canReview || !imageLoaded || steady || picking;
    if (picking) [ui.protectX,ui.protectY,ui.protectW,ui.protectH,protectLabel,ui.protectPick,ui.protectCheck,ui.protectClear,protectAdd].forEach(node=>{node.disabled=true;});
    protectPickCancel.hidden=!picking;
    protectPickCancel.disabled=!canReview || !imageLoaded;
    ui.image.classList.toggle("marking-area",picking);
    exportMode.querySelectorAll("option").forEach(option => { option.disabled = option.value === "steady-detail-v1" && !steady; });
    ui.decline.disabled = !canReview;
    ui.cancel.disabled = busy || refreshInFlight || stateUncertain;
    ui.retry.disabled = busy || refreshInFlight;
    ui.candidateList.querySelectorAll("input").forEach((input) => { input.disabled = !canReview; });
    protectList.querySelectorAll("button").forEach((button) => { button.disabled = !canReview || !imageLoaded || editingRegionIndex !== null || picking; });
    ui.protectCheck.disabled = ui.protectCheck.disabled || editingRegionIndex !== null;
    protectAdd.textContent = editingRegionIndex === null ? "Add area to list" : "Save area changes";
    protectEditCancel.hidden = editingRegionIndex === null;
    protectEditCancel.disabled = !canReview || !imageLoaded || picking;
    protectEditStatus.hidden = editingRegionIndex === null;
    const guide=matchedTeachingGuide();
    teachingGuide.hidden=!guide;
    byId("teaching-guide-focus").textContent=guide?.focus || "";
    teachingGuideLoad.disabled=!canReview || !imagesReady || !guide || picking || savedRegions.length>0 || [ui.protectX,ui.protectY,ui.protectW,ui.protectH,protectLabel].some(field=>String(field.value || "").trim());
  }

  function matchedTeachingGuide() {
    const candidate=currentCandidate();
    return (Array.isArray(job?.teaching_guides) ? job.teaching_guides : []).find(guide=>guide && guide.source_sha256===job?.input_sha256 && guide.candidate_id===candidate?.id && JSON.stringify(guide.candidate_bbox)===JSON.stringify(candidate?.bbox)) || null;
  }
  function loadTeachingGuide() {
    if(teachingGuideLoad.disabled)return;
    const guide=matchedTeachingGuide();
    if(!guide || !Array.isArray(guide.regions) || guide.regions.length<1 || guide.regions.length>4)return;
    savedRegions=guide.regions.map(region=>({label:region.label,xywh:[...region.xywh]}));
    renderProtectedList();invalidateProtection();
    ui.protectStatus.textContent="Example areas loaded. Inspect the highlighted teaching content, edit if needed, then check the plan. Nothing has been approved.";
  }

  function stopPolling() {
    if (pollTimer !== null) window.clearTimeout(pollTimer);
    pollTimer = null;
  }

  function schedulePoll() {
    stopPolling();
    // No polling during human review or after a terminal state. A new GET is
    // scheduled only after the previous GET finishes, never more than once/s.
    if (job && ACTIVE.has(job.status)) pollTimer = window.setTimeout(refreshJob, 1100);
  }

  function renderStages(status) {
    const index = { queued: 0, analyzing: 0, review: 1, exporting: 2, complete: 3 }[status];
    document.querySelectorAll(".job-steps li").forEach((node, position) => {
      node.classList.toggle("current", position === index);
      node.classList.toggle("done", index !== undefined && position < index);
      if (position === index) node.setAttribute("aria-current", "step");
      else node.removeAttribute("aria-current");
    });
  }

  function renderSelectedCandidate() {
    const candidate = currentCandidate();
    imageLoaded = false;
    const version = ++imageVersion;
    alternateLoaded = false;
    steadyReview.hidden = candidate?.action !== "steady-detail-v1";
    steadyAlternate.removeAttribute("src");
    ui.reviewed.checked = false;
    ui.facts.replaceChildren();
    ui.imageError.hidden = true;
    ui.image.removeAttribute("src");
    ui.image.alt = "";
    resetProtection(candidate);
    if (!candidate) { updateControls(); return; }

    if (candidate.action === "steady-detail-v1") {
      addFact(ui.facts,"Action","Steady one observed more contrasting state");
      addFact(ui.facts,"State to keep / alternate frame",[candidate.reference_frame,candidate.alternate_frame]);
      addFact(ui.facts,"Observed state transitions",candidate.state_transitions);
      if (candidate.boundary_alignment) addFact(ui.facts,"Cut points","Source-matched prediction; encoded checks still required");
      addFact(ui.facts,"RGB influence area [x,y,width,height]",candidate.influence_xywh);
      steadyAlternate.onload = () => { if (version !== imageVersion) return; alternateLoaded = true; updateControls(); };
      steadyAlternate.onerror = () => { if (version !== imageVersion) return; alternateLoaded = false; ui.reviewed.checked = false; showError(ui.imageError,"Alternate observed state unavailable. Review both states before generating this edit."); updateControls(); };
      const alternate = localURL(candidate.alternate_url);
      if (alternate) steadyAlternate.src = alternate;
    }

    addFact(ui.facts, "Candidate", candidate.id);
    addFact(ui.facts, "Region [x, y, width, height]", candidate.bbox);
    addFact(ui.facts, "Frame interval (both endpoints included)", candidate.interval_frames);
    addFact(ui.facts, "Time interval (seconds)", candidate.interval_seconds);
    if (candidate.pixels !== undefined) addFact(ui.facts, "Region pixels", candidate.pixels);
    ui.caption.textContent = "Static overlay · Candidate " + String(candidate.id) + " · no playback";
    ui.image.alt = "Static image showing the proposed region for candidate " + String(candidate.id);
    ui.image.onload = () => {
      if (version !== imageVersion) return;
      imageLoaded = true;
      ui.imageError.hidden = true;
      updateControls();
    };
    ui.image.onerror = () => {
      if (version !== imageVersion) return;
      imageLoaded = false;
      ui.imageError.hidden = false;
      ui.reviewed.checked = false;
      updateControls();
    };
    const url = localURL(candidate.overlay_url);
    if (url) ui.image.src = url;
    else ui.imageError.hidden = false;
    updateControls();
  }

  function protectionValues() {
    const fields = [ui.protectX, ui.protectY, ui.protectW, ui.protectH];
    if (fields.every((field) => field.value === "")) {
      if (editingRegionIndex !== null) throw new Error("Complete the area change, or cancel it.");
      return savedRegions.map(r=>({label:r.label,xywh:[...r.xywh]}));
    }
    const values = fields.map((field) => field.value === "" ? NaN : Number(field.value));
    if (!values.every(Number.isSafeInteger) || values[0] < 0 || values[1] < 0 || values[2] <= 0 || values[3] <= 0 ||
        values[0] + values[2] > ui.image.naturalWidth || values[1] + values[3] > ui.image.naturalHeight) {
      throw new Error("Enter one complete rectangle inside the image using integer pixels.");
    }
    const label=protectLabel.value.trim() || "Important area";
    if (editingRegionIndex === null && savedRegions.length>=4) throw new Error("Choose at most four protected areas.");
    if (savedRegions.some((r,index)=>index!==editingRegionIndex && r.label===label)) throw new Error("Use a distinct area name.");
    if (editingRegionIndex !== null) {
      return savedRegions.map((r,index)=>index===editingRegionIndex ? {label,xywh:values} : {label:r.label,xywh:[...r.xywh]});
    }
    return [...savedRegions, {label, xywh: values}];
  }
  function drawProtection() {
    ui.protectRect.hidden = true;
    ui.protectOverlays.replaceChildren();
    try {
      const regions = protectionValues();
      renderProtectionOverlays(regions);
    } catch (_) {
      // Keep already-saved areas visible while the next rectangle is incomplete.
      renderProtectionOverlays(savedRegions);
    }
  }
  function renderProtectionOverlays(regions) {
    if (!(ui.image.naturalWidth > 0 && ui.image.naturalHeight > 0)) return;
    regions.forEach((region, index) => {
      const [x,y,w,h] = region.xywh;
      const box = element("div", null, "protection-box protection-color-" + index);
      // Individual CSSOM properties are permitted by our strict style-src CSP.
      // Parsing an inline style attribute is blocked and collapsed these boxes.
      box.style.left = (100*x/ui.image.naturalWidth) + "%";
      box.style.top = (100*y/ui.image.naturalHeight) + "%";
      box.style.width = (100*w/ui.image.naturalWidth) + "%";
      box.style.height = (100*h/ui.image.naturalHeight) + "%";
      box.append(element("span", (index + 1) + ". " + region.label, "protection-box-label"));
      ui.protectOverlays.append(box);
    });
  }
  function renderProtectedList() {
    protectList.replaceChildren();
    ui.protectCount.textContent = savedRegions.length + " of 4 areas saved";
    savedRegions.forEach((region, index) => {
      const row = element("li", null, "protected-area-row");
      row.append(element("span", (index + 1) + ". " + region.label + " · [" + region.xywh.join(", ") + "]"));
      const remove = element("button", "Remove", "text-button");
      remove.type = "button";
      remove.setAttribute("aria-label", "Remove protected area " + region.label);
      remove.addEventListener("click", () => removeProtectedRegion(index));
      row.append(remove);
      const edit = element("button", "Edit", "text-button");
      edit.type = "button";
      edit.setAttribute("aria-label", "Edit protected area " + region.label);
      edit.addEventListener("click", () => editProtectedRegion(index));
      row.append(edit);
      protectList.append(row);
    });
  }
  function removeProtectedRegion(index) {
    if (busy || refreshInFlight || stateUncertain || picking || !imageLoaded || job?.status !== "review") return;
    if (editingRegionIndex !== null) return;
    if (!Number.isInteger(index) || index < 0 || index >= savedRegions.length) return;
    savedRegions.splice(index, 1);
    renderProtectedList();
    invalidateProtection();
  }
  function editProtectedRegion(index) {
    if (busy || refreshInFlight || stateUncertain || picking || !imageLoaded || job?.status !== "review") return;
    if (!Number.isInteger(index) || index < 0 || index >= savedRegions.length) return;
    if (editingRegionIndex !== null || [ui.protectX,ui.protectY,ui.protectW,ui.protectH,protectLabel].some(field=>String(field.value || "").trim())) {
      showError(ui.protectError,"Finish the current area or clear its input fields before editing another. Your draft has been kept.");
      return;
    }
    editingRegionIndex = index;
    const region = savedRegions[index];
    protectLabel.value = region.label;
    [ui.protectX,ui.protectY,ui.protectW,ui.protectH].forEach((field,i)=>{field.value=String(region.xywh[i]);});
    picking=false;firstCorner=null;
    protectEditStatus.textContent="Editing area "+(index+1)+": "+region.label+". The overlay previews your draft; the saved box stays intact until you save. Save or cancel before checking a new plan.";
    invalidateProtection();
  }
  function cancelProtectedEdit() {
    if (busy || refreshInFlight || stateUncertain || picking || !imageLoaded || job?.status !== "review" || editingRegionIndex === null) return;
    editingRegionIndex=null;
    [ui.protectX,ui.protectY,ui.protectW,ui.protectH].forEach(field=>{field.value="";});
    protectLabel.value="";picking=false;firstCorner=null;
    renderProtectedList();invalidateProtection();
    ui.protectStatus.textContent="Area change cancelled. Saved areas kept; check the plan again before generating.";
  }
  function saveProtectedRegion() {
    if (protectAdd.disabled) return;
    try {
      const regions = protectionValues();
      if (regions.length === savedRegions.length && editingRegionIndex === null) throw new Error("Enter a new rectangle first.");
      savedRegions = regions;
      editingRegionIndex = null;
      renderProtectedList();
      [ui.protectX,ui.protectY,ui.protectW,ui.protectH].forEach(field => { field.value = ""; });
      protectLabel.value = "";
      picking = false; firstCorner = null;
      invalidateProtection();
    } catch (error) { showError(ui.protectError, error.message); }
  }
  function resetProtection(candidate) {
    protectionVersion += 1; picking = false; firstCorner = null;
    pickDraft = null;
    ui.reviewed.checked = false;
    savedRegions=[];editingRegionIndex=null;protectEditStatus.textContent="";protectList.replaceChildren();protectLabel.value="";exportMode.value="periodic-local-retime-v2";exportModeNote.textContent="5× local retiming inside the detected interval only. Requires at least three repeated cycles, mean recurrence error ≤2 and every sample difference ≤32 native codes. Small nonperiodic changes can still pass. Strong entry transitions remain; playback unverified; no safety claim.";
    if (candidate?.action === "steady-detail-v1") { exportMode.value = "steady-detail-v1"; exportModeNote.textContent = STEADY_NOTE; }
    [ui.protectX,ui.protectY,ui.protectW,ui.protectH].forEach((field) => { field.value = ""; });
    protectionPlan = null; // Every retiming mode needs a freshly checked, bound plan.
    ui.protectRect.hidden = true;
    ui.protectOverlays.replaceChildren();
    renderProtectedList();
    ui.protectStatus.textContent = "No important area declared.";
    ui.planSummary.hidden = true;
    ui.planSummary.textContent = "";
    showError(ui.protectError, "");
  }
  function invalidateProtection() {
    protectionVersion += 1; protectionPlan = null; ui.reviewed.checked = false;
    ui.planSummary.hidden = true;
    ui.planSummary.textContent = "";
    ui.protectStatus.textContent = "Area changed. Check it before approving the edit.";
    showError(ui.protectError, ""); drawProtection(); updateControls();
  }
  async function checkProtection() {
    if (ui.protectCheck.disabled || !currentCandidate()) return;
    let regions;
    try { regions = protectionValues(); }
    catch (error) { showError(ui.protectError,error.message); return; }
    if (job.preparation && regions.length === 0) { showError(ui.protectError,"Save at least one teaching area before checking the plan. If this candidate is useful lesson content, leave the clip unchanged."); return; }
    const version = ++protectionVersion, id=job.id, candidateId=currentCandidate().id, prediction=job.prediction_sha256, mode=exportMode.value;
    protectionPlan=null; ui.reviewed.checked=false; busy=true; updateControls();
    ui.planSummary.hidden = true;
    ui.planSummary.textContent = "";
    try {
      const plan=await request("/api/jobs/"+encodeURIComponent(id)+"/plan",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({candidate_id:candidateId,prediction_sha256:prediction,protected_regions:regions,export_mode:exportMode.value})});
      if (version!==protectionVersion || job.id!==id || currentCandidate()?.id!==candidateId) return;
      if (plan.prediction_sha256!==prediction || plan.candidate_id!==candidateId || plan.export_mode!==mode || JSON.stringify(plan.protected_regions)!==JSON.stringify(regions) || !/^[0-9a-f]{64}$/.test(plan.recipe_sha256)) throw new Error("The returned plan does not match the selected edit and areas.");
      const candidate = currentCandidate();
      ui.planSummary.textContent = (mode === "steady-detail-v1" ? "Hold the observed brightness state from frame "+candidate.reference_frame+" steady inside this interval" : mode === "periodic-local-retime-v2" ? "Slow the selected decoration 5×" : mode === "legacy" ? "Hold each 10-frame block in the selected interval" : "Hold the selected decoration across the entire clip") + ". Detected region: [" + candidate.bbox.join(", ") + "]; detected interval: frames " + candidate.interval_frames.join("–") + ". " + (regions.length ? "Check every frame of: " + regions.map(region => region.label).join(", ") + "." : "No important area declared.") + " Generate only after reviewing this plan. The encoded result can still be refused.";
      ui.planSummary.hidden = false;
      protectionPlan=plan;
      ui.protectStatus.textContent=regions.length ? "Checked "+regions.length+" fixed areas. The actual encoded result still has to meet its criteria." : "Edit plan checked. No important area declared.";
      showError(ui.protectError,"");
    } catch (error) {
      protectionPlan=null;
      ui.planSummary.hidden=true;
      ui.planSummary.textContent="";
      showError(ui.protectError,error.message);
    }
    finally { busy=false;updateControls(); }
  }

  function renderCandidates() {
    const candidates = Array.isArray(job.candidates) ? job.candidates : [];
    const fingerprint = JSON.stringify([job.prediction_sha256, candidates]);
    ui.candidates.hidden = job.status !== "review" || candidates.length === 0;
    if (job.status === "review" && candidates.length === 0) {
      ui.status.textContent = "No supported rapid-change or stationary-blink proposal in this excerpt. Notifications, moving cursors and many other distractions remain outside these checks. It does not establish that the lesson is distraction-free. Leave it unchanged and download the lesson decision record.";
    }
    if (fingerprint === candidateFingerprint) return;
    candidateFingerprint = fingerprint;
    selectedId = candidates.length ? String(candidates[0].id) : null;
    ui.candidateList.replaceChildren();
    candidates.forEach((candidate, index) => {
      const label = element("label", null, "candidate-option");
      const input = element("input");
      input.type = "radio";
      input.name = "candidate";
      input.value = String(candidate.id);
      input.checked = index === 0;
      input.addEventListener("change", () => {
        if (!input.checked) return;
        selectedId = input.value;
        renderSelectedCandidate();
      });
      label.append(input, element("span", (candidate.action === "steady-detail-v1" ? "Stationary blink · " : "Rapid change · ") + String(candidate.id)));
      ui.candidateList.append(label);
    });
    renderSelectedCandidate();
  }

  function resultCard(title, values, missing) {
    const card = element("section", null, "result-card");
    card.append(element("h3", title));
    if (values.length) {
      const list = element("dl");
      values.forEach(([label, value]) => addFact(list, label, value));
      card.append(list);
    } else card.append(element("p", missing || "Not reported by the server."));
    return card;
  }

  const BOUNDARY_VERSIONS = [
    ["original", "Original", "Input"],
    ["control", "Control", "Unchanged re-encode"],
    ["edited", "Edited", "Generated edit"]
  ];
  const BOUNDARY_LABELS = ["Before edit", "Edit begins", "Final edited frame", "Original frames resume"];

  function boundaryReviewProblem(review) {
    const record = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
    const hash = (value) => typeof value === "string" && /^[0-9a-f]{64}$/i.test(value);
    const nonnegative = (value) => typeof value === "number" && Number.isFinite(value) && value >= 0;
    if (!record(review) || review.schema !== "encoded-boundaries-v1") return "The boundary-review schema is missing or unsupported.";
    if (![review.input_sha256, review.prediction_sha256, review.recipe_sha256].every(hash) ||
        !record(review.output_hashes) || ![review.output_hashes.control, review.output_hashes.edited].every(hash)) {
      return "Required boundary-review provenance hashes are missing or invalid.";
    }
    if ((job.input_sha256 && job.input_sha256 !== review.input_sha256) ||
        (job.prediction_sha256 && job.prediction_sha256 !== review.prediction_sha256)) {
      return "Boundary-review provenance does not match this job.";
    }
    if (!Array.isArray(review.crop_xywh) || review.crop_xywh.length !== 4 ||
        !review.crop_xywh.every((value) => Number.isSafeInteger(value) && value >= 0) ||
        review.crop_xywh[2] === 0 || review.crop_xywh[3] === 0) return "The shared crop coordinates are missing or invalid.";
    const transition = review.strong_return_transition;
    if (!record(transition) || typeof transition.newly_timed !== "boolean" ||
        !nonnegative(transition.edited_delta) || !nonnegative(transition.control_delta) || transition.criterion !== 0.1) {
      return "The strong-return diagnostic is missing or invalid.";
    }
    if (!Array.isArray(review.rows) || review.rows.length !== 4) return "Exactly four labeled boundary rows are required.";
    for (const [rowIndex, row] of review.rows.entries()) {
      if (!record(row) || typeof row.label !== "string" || !row.label.trim() ||
          row.label !== BOUNDARY_LABELS[rowIndex] ||
          !Number.isSafeInteger(row.frame) || row.frame < 0 || !nonnegative(row.seconds) ||
          typeof row.loop_wrap !== "boolean" || !record(row.images)) return "A boundary row has missing or invalid frame information.";
      for (const [key] of BOUNDARY_VERSIONS) {
        const asset = row.images[key];
        if (!record(asset) || typeof asset.filename !== "string" ||
            !/^[^/\\\u0000-\u001f]+\.png$/i.test(asset.filename) || !hash(asset.sha256) ||
            (asset.decoded_crop_rgb_sha256 !== undefined && !hash(asset.decoded_crop_rgb_sha256))) {
          return "A required static PNG crop or its provenance is missing or invalid.";
        }
        const url = localURL(asset.url);
        if (!url || !/\.png$/i.test(new URL(url, window.location.origin).pathname)) {
          return "A static crop URL is not a local PNG URL. No comparison images were loaded.";
        }
      }
    }
    return null;
  }

  function renderBoundaryReview() {
    const version = ++boundaryVersion;
    const review = job.frame_review;
    ui.boundaryRows.replaceChildren();
    ui.boundaryData.textContent = "";
    ui.boundaryProvenance.hidden = true;
    ui.boundaryProvenance.open = false;
    ui.boundaryWarning.hidden = true;
    ui.boundaryValues.textContent = "";
    showError(ui.boundaryError, "");
    if (job.frame_review_error) {
      ui.boundaryStatus.textContent = "Static boundary comparison unavailable.";
      showError(ui.boundaryError, "The server could not verify this comparison: " + pretty(job.frame_review_error));
      return;
    }
    ui.boundaryWarning.hidden = review?.strong_return_transition?.newly_timed !== true;
    if (review === undefined || review === null) {
      ui.boundaryStatus.textContent = "No static boundary comparison was returned for this job.";
      return;
    }
    const problem = boundaryReviewProblem(review);
    if (problem) {
      ui.boundaryStatus.textContent = "Static boundary comparison unavailable.";
      showError(ui.boundaryError, problem);
      return;
    }
    const transition = review.strong_return_transition;
    ui.boundaryValues.textContent = "Selected-mean delta: control " + String(transition.control_delta) +
      " · edited " + String(transition.edited_delta) + " · criterion " + String(transition.criterion) + ".";
    // Only the declared contract is shown; unrecognized server fields are ignored.
    const provenance = {
      schema: review.schema, input_sha256: review.input_sha256,
      prediction_sha256: review.prediction_sha256, recipe_sha256: review.recipe_sha256,
      output_hashes: { control: review.output_hashes.control, edited: review.output_hashes.edited },
      crop_xywh: review.crop_xywh, rows: [], strong_return_transition: {
        newly_timed: transition.newly_timed, control_delta: transition.control_delta,
        edited_delta: transition.edited_delta, criterion: transition.criterion
      }
    };
    const states = Array(12).fill("loading");
    function updateImageStatus() {
      if (version !== boundaryVersion) return;
      const loaded = states.filter((state) => state === "loaded").length;
      const failed = states.filter((state) => state === "failed").length;
      ui.boundaryStatus.textContent = loaded + " of 12 static PNG crops loaded." +
        (failed ? " Comparison incomplete: " + failed + " could not be displayed." :
          loaded === 12 ? " All four moments are shown below." : " Waiting for the remaining crops.");
      showError(ui.boundaryError, failed ? "One or more static crops could not be displayed. The comparison is incomplete; missing images are not a result." : "");
    }
    updateImageStatus();
    review.rows.forEach((row, rowIndex) => {
      const section = element("section", null, "boundary-row");
      const heading = element("h4", row.label);
      heading.id = "boundary-row-" + rowIndex;
      section.setAttribute("aria-labelledby", heading.id);
      const moment = "Frame " + String(row.frame) + " · " + String(row.seconds) + " s" +
        (row.loop_wrap ? " · loop wrap" : "") + " · crop [" + review.crop_xywh.join(", ") + "]";
      section.append(heading, element("p", moment, "boundary-moment"));
      const images = element("div", null, "boundary-images");
      const rowProvenance = { label: row.label, frame: row.frame, seconds: row.seconds, loop_wrap: row.loop_wrap, images: {} };
      BOUNDARY_VERSIONS.forEach(([key, label, description], columnIndex) => {
        const asset = row.images[key];
        const position = rowIndex * 3 + columnIndex;
        const figure = element("figure", null, "boundary-crop");
        const caption = element("figcaption");
        caption.append(element("strong", label), element("span", description));
        const wrap = element("div", null, "boundary-image-wrap");
        const img = element("img");
        img.alt = label + " static PNG crop · " + row.label + " · " + moment;
        img.width = review.crop_xywh[2];
        img.height = review.crop_xywh[3];
        img.hidden = true;
        const inspect = element("a", "Open full-size PNG in a new tab", "text-button proof-original-link");
        inspect.href = localURL(asset.url);
        inspect.target = "_blank";
        inspect.rel = "noopener noreferrer";
        inspect.hidden = true;
        const status = element("p", "Loading static PNG…", "boundary-image-status");
        function fail(message) {
          if (version !== boundaryVersion) return;
          states[position] = "failed";
          img.hidden = true;
          inspect.hidden = true;
          status.textContent = message;
          status.hidden = false;
          figure.classList.add("boundary-crop-failed");
          updateImageStatus();
        }
        img.onload = () => {
          if (version !== boundaryVersion) return;
          if (img.naturalWidth !== review.crop_xywh[2] || img.naturalHeight !== review.crop_xywh[3]) {
            fail("Static crop dimensions do not match the reported region.");
            return;
          }
          states[position] = "loaded";
          img.hidden = false;
          inspect.hidden = false;
          status.hidden = true;
          figure.classList.remove("boundary-crop-failed");
          updateImageStatus();
        };
        img.onerror = () => fail("Static PNG unavailable. This image has not been displayed.");
        wrap.append(img, status);
        figure.append(caption, wrap, inspect);
        images.append(figure);
        img.src = localURL(asset.url);
        rowProvenance.images[key] = { filename: asset.filename, sha256: asset.sha256, url: localURL(asset.url) };
        if (asset.decoded_crop_rgb_sha256 !== undefined) rowProvenance.images[key].decoded_crop_rgb_sha256 = asset.decoded_crop_rgb_sha256;
      });
      provenance.rows.push(rowProvenance);
      section.append(images);
      ui.boundaryRows.append(section);
    });
    ui.boundaryData.textContent = JSON.stringify(provenance, null, 2);
    ui.boundaryProvenance.hidden = false;
  }

  function renderResults() {
    const summary = job.summary;
    const artifacts = job.artifacts;
    const hasSummary = summary && typeof summary === "object";
    const hasArtifacts = artifacts && typeof artifacts === "object" && Object.keys(artifacts).length > 0;
    const hasFrameReview = (job.frame_review !== undefined && job.frame_review !== null) || Boolean(job.frame_review_error);
    renderBoundaryReview();
    ui.results.hidden = !hasSummary && !hasArtifacts && !hasFrameReview;
    if (ui.results.hidden) return;
    byId("results-title").textContent = hasSummary || hasFrameReview ? "Encoded-result measurements" : "Retained lesson files";
    byId("result-intro").textContent = hasSummary || hasFrameReview ? "These values come from the server’s result report. Read the scope and limitations alongside the measurements." : "No edited export was accepted. Download the retained sources, preparation receipt and lesson decision record.";
    byId("boundary-review").hidden = !hasFrameReview;
    byId("result-report-details").hidden = !hasSummary;
    ui.highlights.replaceChildren();
    ui.artifacts.replaceChildren();
    ui.raw.textContent = hasSummary ? JSON.stringify(summary, null, 2) : "No result report was returned by the server.";

    if (hasSummary) {
      if (summary.export_mode === "steady-detail-v1") {
        const detail = summary.stationary_detail;
        ui.highlights.append(resultCard("Steady reading detail", [["Observed RGB activity before / after",detail ? [detail.activity.source,detail.activity.edited] : null],["Interval frames",detail?.proposal.interval_frames],["Kept source frame",detail?.proposal.reference_frame],["Preservation gate",summary.acceptance?.status]], "Adjacent ROI-mean changes of at least 8 RGB codes inside the interval. This excludes entry/return and does not measure attention or learning."));
        if (detail?.whole_clip_activity) ui.highlights.append(resultCard("Whole excerpt activity · includes cut points",[["Source / edited",[detail.whole_clip_activity.source,detail.whole_clip_activity.edited]]],"Same region and all clip frames, including entry and return. Adjacent ROI-mean changes of at least 8 RGB codes; no measured learning or safety benefit."));
        if (summary.encoded_boundary_checks) ui.highlights.append(resultCard("Encoded cut points",[["Selected and influence RGB",summary.encoded_boundary_checks.passed ? "No worse than source" : "Refused"],["Selected-mean entry / return / loop",summary.checks?.encoded_boundary_selected_mean_not_worse ? "No worse than source" : "Refused"]],"Mean absolute, RMS and maximum decoded RGB changes are checked separately at entry, return and clip loop. Fixed first/last frames preserve the loop. Exact measurements remain in the report."));
      }
      if (summary.export_mode === "periodic-local-retime-v2") {
        ui.highlights.append(resultCard("Local decoration retiming", [["Slowdown", "5×"], ["Observed cycle frames", summary.detection?.period_frames], ["Retimed cycle frames", summary.detection ? summary.detection.period_frames * 5 : null], ["Preservation gate", summary.acceptance?.status]], "The rest of the clip keeps its original timeline. This is slower pulsing, not smooth motion."));
      }
      if (summary.audio_preservation) {
        const a = summary.audio_preservation;
        ui.highlights.append(resultCard(job.preparation ? "Prepared lesson audio" : "Original lesson audio", [["Track", a.present ? "AAC-LC mono / 48 kHz" : "No audio in source"], ["Verification", a.present ? (job.preparation ? "Prepared packet bytes, timestamps, skip metadata and decoded PCM unchanged by this edit" : "Original packet bytes, timestamps, skip metadata and decoded PCM unchanged") : "Silent source retained"]], job.preparation ? "Preparation converted the narration once. This edit copies and checks that prepared audio; it is not packet-identical to the uploaded original." : "Canonical development mux only. No stretching, trimming, resampling or audio encoding. Playback compatibility remains unverified."));
      }
      const trigger = summary.selected_trigger_count;
      const outside = summary.outside_mask_error;
      const boundary = summary.boundary;
      if (summary.export_mode !== "steady-detail-v1") ui.highlights.append(resultCard("Selected trigger count", trigger ? [
        ["Unchanged re-encode control", trigger.control],
        ["Edited encoded result", trigger.edited],
        ["Experimental criterion maximum", trigger.criterion_max]
      ] : []));
      const boundaries = [];
      ["entry", "exit", "loop_seam"].forEach((name) => {
        if (!boundary?.[name]) return;
        boundaries.push([readableKey(name) + " · control delta", boundary[name].control_delta]);
        boundaries.push([readableKey(name) + " · edited delta", boundary[name].edited_delta]);
      });
      ui.highlights.append(resultCard("Boundary measurements", boundaries));
      ui.highlights.append(resultCard("Outside-region preservation", outside ? [
        ["Mean RGB code error", outside.mean_rgb_code_error],
        ["99th-percentile RGB code error", outside.p99_rgb_code_error],
        ["Maximum RGB code error", outside.max_rgb_code_error]
      ] : []));
      const neighbors=summary.outside_selected_box_rgb;
      if (neighbors) ui.highlights.append(resultCard("Pixels beside the caret",[
        ["Scope","Every RGB pixel outside the actual caret box"],
        ["Mean / p99 / maximum RGB error",[neighbors.mean_rgb_code_error,neighbors.p99_rgb_code_error,neighbors.max_rgb_code_error]],
        ["Original color samples",summary.checks?.all_original_chroma_samples_exact ? "All retained on their timeline" : "Check not met"]
      ]));

      const protection = summary.protected_content;
      if (protection?.declared) {
        protection.regions.forEach((region,regionIndex) => {
          const card=resultCard("Important area: "+region.label,[["Fixed rectangle",region.xywh],["Result",region.passed ? "Criteria met; review still required" : "Failed preservation criteria"],["Mean / p99 / maximum RGB error",[region.measurements.mean_rgb_code_error,region.measurements.p99_rgb_code_error,region.measurements.max_rgb_code_error]],["Criteria",region.criteria ? [region.criteria.mean_rgb_code_error,region.criteria.p99_rgb_code_error,region.criteria.max_rgb_code_error] : [0.1,1,3]],["Frames measured",protection.frames]]);
          const motion=summary.teaching_motion?.regions?.[regionIndex];
          if (motion && motion.label===region.label && JSON.stringify(motion.xywh)===JSON.stringify(region.xywh)) {
            card.append(element("h4","Teaching motion kept on its timeline"));
            card.append(element("p","Changing frame pairs inside hold · source / edited: "+pretty([motion.changed_pairs_inside_hold.source,motion.changed_pairs_inside_hold.edited])+" of "+motion.hold_adjacent_pairs+". Ordered RGB sequence: "+(motion.ordered_rgb_sequence_exact ? "exact match" : "different")+".","small"));
            card.append(element("p","Any decoded RGB change is counted, including codec variation. This does not count semantic progress ticks or establish readability.","small muted"));
          }
          const proof=job.teaching_review?.regions?.[regionIndex];
          if (proof && proof.label===region.label && JSON.stringify(proof.xywh)===JSON.stringify(region.xywh)) {
            const details=element("details",null,"teaching-frame-proof");details.append(element("summary","Inspect preserved teaching frames · static PNGs"));
            proof.moments.forEach((moment)=>{
              details.append(element("p",moment.roles.join(" / ")+" · frame "+moment.frame,"small"));
              const pair=element("div",null,"teaching-proof-pair");
              ["source","edited"].forEach((role)=>{
                const asset=moment.images[role],figure=element("figure");
                figure.append(element("figcaption",role==="source" ? "Prepared source" : "Encoded edit"));
                const image=element("img"),status=element("p","Loading static teaching crop…","small muted");
                const inspect=element("a","Open full-size PNG in a new tab","text-button proof-original-link");
                inspect.target="_blank";inspect.rel="noopener noreferrer";inspect.hidden=true;image.hidden=true;
                // Hidden proofs must fetch before their dimension check can reveal them.
                image.alt=region.label+" · "+role+" · frame "+moment.frame;image.loading="eager";
                image.onload=()=>{const valid=image.naturalWidth===asset.width && image.naturalHeight===asset.height;image.hidden=!valid;inspect.hidden=!valid;status.textContent=valid ? "Hash-verified source-bound PNG" : "Teaching crop dimensions differ; image withheld.";};
                image.onerror=()=>{image.hidden=true;inspect.hidden=true;status.textContent="Teaching crop unavailable; it has not been displayed.";};
                figure.append(image,status,inspect);pair.append(figure);
                try { const url=localURL(asset.url);image.src=url;inspect.href=url; } catch(error) { image.hidden=true;inspect.hidden=true;status.textContent="Teaching crop URL refused."; }
              });details.append(pair);
            });card.append(details);
          }
          if (!region.passed) card.classList.add("protected-failed");
          ui.highlights.append(card);
        });
      } else ui.highlights.append(resultCard("Important-area check",[],"No important area declared. No preservation conclusion for text or objects."));
      if (job.teaching_review_error) ui.highlights.append(resultCard("Teaching frame proof unavailable",[],"The source-bound teaching images could not be verified. "+job.teaching_review_error));

      const notes = element("section", null, "result-notes");
      notes.append(element("p", "Numeric checks do not replace creator review, even when every experimental criterion is met.", "result-caveat"));
      if (summary.scope) notes.append(element("p", "Measurement scope: " + pretty(summary.scope), "small muted"));
      if (summary.review_status) notes.append(element("p", "Report status: " + readableKey(summary.review_status), "small"));
      if (summary.checks && typeof summary.checks === "object") {
        const checks = element("ul", null, "check-list");
        Object.entries(summary.checks).forEach(([name, value]) => {
          checks.append(element("li", readableKey(name) + ": " + (value === true ? "criterion met" : value === false ? "criterion not met" : pretty(value))));
        });
        notes.append(checks);
      }
      if (Array.isArray(summary.warnings) && summary.warnings.length) {
        notes.append(element("h3", "Report warnings"));
        const warnings = element("ul", null, "report-warnings");
        summary.warnings.forEach((warning) => warnings.append(element("li", pretty(warning))));
        notes.append(warnings);
      }
      ui.highlights.append(notes);
    }

    const packNote = byId("rescue-pack-note");
    if (packNote) packNote.hidden = !hasArtifacts || !artifacts["Download verified rescue pack"];
    if (hasArtifacts) {
      Object.entries(artifacts).forEach(([label, value]) => {
        const url = localURL(value);
        if (!url) return;
        const item = element("li");
        const link = element("a", readableKey(label));
        link.href = url;
        link.download = "";
        const arrow = element("span", "↓");
        arrow.setAttribute("aria-hidden", "true");
        link.append(arrow);
        item.append(link);
        ui.artifacts.append(item);
      });
    }
    ui.artifactsArea.hidden = ui.artifacts.children.length === 0;
  }

  function renderWorkflow() {
    const area=byId("workflow-area"), next=byId("workflow-next"), data=byId("workflow-data"), link=byId("workflow-download");
    area.hidden=true;data.textContent="";link.removeAttribute("href");
    if (!job) return;
    if (job.workflow_error) {
      area.hidden=false;next.textContent="Workflow snapshot unavailable. Inspect the job status and report before continuing.";link.hidden=true;return;
    }
    const trace=job.workflow;
    if (!trace || trace.schema!=="frame-review-workflow-v1" || trace.job_id!==job.id || trace.status!==job.status || typeof trace.next_action!=="string" || !validJobId(job.id)) return;
    area.hidden=false;next.textContent=trace.next_action;data.textContent=JSON.stringify(trace,null,2);
    link.hidden=false;link.href=localURL("/api/jobs/"+job.id+"/workflow.json");
  }

  function renderJob() {
    if (!job) return;
    renderWorkflow();
    ui.empty.hidden = true;
    ui.jobArea.hidden = false;
    ui.jobFile.textContent = job.input_name || "Selected clip";
    const status = STATUS[job.status] || ["Unknown status", "The server returned an unrecognized job status. Check the local server before continuing."];
    ui.statusPill.textContent = status[0];
    ui.statusPill.dataset.state = job.status;
    ui.status.textContent = status[1];
    if (job.preparing_lesson) ui.status.textContent = "Preparing your selected lesson excerpt, then analyzing it. No edit has been approved.";
    preparationNotice.hidden = !job.preparation && !job.sample_credit;
    if (job.sample_credit) preparationNotice.textContent = "Natural tutorial sample by " + job.sample_credit.author + " (" + job.sample_credit.license + "): " + job.sample_credit.derivation + " Inspect both observed states before deciding whether its caret should stay steady. The full source attribution and preparation history are downloadable.";
    preparationPreview.hidden = !job.preparation;
    byId("preparation-fullsize").hidden = !job.preparation;
    if (job.preparation) {
      preparationNotice.textContent = "Teaching detail check: " + job.preparation.source.width + " × " + job.preparation.source.height + " source → 640 × 360 review. Check the smallest label before editing; resizing can make teaching detail unreadable. Prepared excerpt: " + job.preparation.start_seconds + "–" + (job.preparation.start_seconds + job.preparation.duration_seconds) + " seconds. Picture and audio were converted once. All exact edit checks compare against this prepared clip, not the uploaded original. Keep both sources and the preparation receipt.";
      preparationPreview.src = "/api/jobs/" + encodeURIComponent(job.id) + "/intake/preview";
      byId("preparation-fullsize").href = preparationPreview.src;
    }
    showError(ui.error, job.error ? pretty(job.error) : "");
    ui.retry.hidden = true;
    ui.reviewActions.hidden = job.status !== "review";
    ui.cancel.hidden = !ACTIVE.has(job.status);
    renderStages(job.status);
    renderCandidates();
    renderResults();
    updateControls();
  }

  async function refreshJob() {
    if (!job || refreshInFlight) return;
    stopPolling();
    refreshInFlight = true;
    const epoch = requestEpoch;
    const id = job.id;
    updateControls();
    try {
      const next = await request("/api/jobs/" + encodeURIComponent(id));
      if (epoch !== requestEpoch) return;
      if (!next || String(next.id) !== String(id)) throw new Error("The local server returned a different job. No review decision was sent.");
      job = next;
      stateUncertain = false;
      renderJob();
      schedulePoll();
    } catch (error) {
      if (epoch !== requestEpoch) return;
      stateUncertain = true;
      showError(ui.error, error.message);
      ui.retry.hidden = false;
      ui.status.textContent = "Status updates are paused. Check the connection to continue.";
    } finally {
      refreshInFlight = false;
      updateControls();
    }
  }

  async function decision(action, body) {
    if (!job || busy) return;
    stopPolling();
    busy = true;
    ui.reviewed.checked = false;
    updateControls();
    showError(ui.error, "");
    try {
      await request("/api/jobs/" + encodeURIComponent(job.id) + "/" + action, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
      });
      await refreshJob();
    } catch (error) {
      stateUncertain = true;
      showError(ui.error, error.message + " The decision was not retried. Check the current job status before trying again.");
      ui.retry.hidden = false;
    } finally {
      busy = false;
      updateControls();
    }
  }

  ui.file.addEventListener("change", () => {
    const file = ui.file.files[0];
    showError(ui.connectionError, "");
    if (!file) ui.fileInfo.textContent = "";
    else if (!file.size) ui.fileInfo.textContent = "This file is empty. Choose a supported clip.";
    else if (file.size > MAX_BYTES) ui.fileInfo.textContent = "This file exceeds the 64 MiB lesson limit. Choose a smaller file.";
    else ui.fileInfo.textContent = file.name + " · " + (file.size / 1024 / 1024).toFixed(2) + " MiB";
    updateControls();
  });

  async function startJob(path, options) {
    stopPolling();
    requestEpoch += 1;
    busy = true;
    showError(ui.connectionError, "");
    updateControls();
    try {
      // Header values must be ASCII. encodeURIComponent preserves Unicode names
      // without risking a rejected header or header injection.
      const next = await request(path, {method: "POST", ...options});
      if (!next || !validJobId(next.id)) throw new Error("The server did not return a job identifier. The upload was not retried.");
      job = next;
      recovery.area.hidden = true;
      recovery.retry.hidden = true;
      recovery.dismiss.hidden = true;
      rememberJob(next.id);
      stateUncertain = false;
      candidateFingerprint = null;
      selectedId = null;
      ui.results.hidden = true;
      renderJob();
      await refreshJob();
    } catch (error) {
      showError(ui.connectionError, error.message);
    } finally {
      busy = false;
      updateControls();
    }
  }

  ui.form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (ui.analyze.disabled) return;
    const file = ui.file.files[0];
    if (!file || !file.size || file.size > MAX_BYTES) return;
    if (prepareLesson.checked) {
      const start = Number(clipStart.value), duration = Number(clipDuration.value);
      if (!Number.isFinite(start) || !Number.isFinite(duration) || start < 0 || start > 600 || duration < 1 || duration > 12 || Math.abs(duration * 10 - Math.round(duration * 10)) > .000001) {
        showError(ui.connectionError, "Choose a start from 0 to 600 seconds and a length of 1–12 seconds in 0.1-second steps."); return;
      }
      await startJob("/api/imports", {headers: {"Content-Type":"application/octet-stream", "X-Filename":encodeURIComponent(file.name), "X-Clip-Start":String(start), "X-Clip-Duration":String(duration)}, body:file});
    } else {
      if (file.size > 8 * 1024 * 1024) { showError(ui.connectionError, "Canonical clips are limited to 8 MiB; enable preparation for a real lesson file."); return; }
      await startJob("/api/jobs", {headers: {"Content-Type":"application/octet-stream", "X-Filename":encodeURIComponent(file.name)}, body:file});
    }
  });
  ui.demo.addEventListener("click", async () => {
    if (ui.demo.disabled || ui.cloudSamples.hidden) return;
    await startJob("/api/demo", {headers: {"Content-Type":"application/json"}, body:"{}"});
  });
  naturalDemo.addEventListener("click", async () => {
    if (naturalDemo.disabled) return;
    await startJob("/api/natural-demo", {headers:{"Content-Type":"application/json"},body:JSON.stringify({example:naturalExample.value || "terminal"})});
  });
  realDemo.addEventListener("click", async () => {
    if (realDemo.disabled || ui.cloudSamples.hidden) return;
    await startJob("/api/real-demo", {headers: {"Content-Type":"application/json"}, body:"{}"});
  });
  realChallenge.addEventListener("click", async () => {
    if (realChallenge.disabled || ui.cloudSamples.hidden) return;
    await startJob("/api/real-challenge", {headers: {"Content-Type":"application/json"}, body:"{}"});
  });

  [ui.protectX,ui.protectY,ui.protectW,ui.protectH].forEach((field) => field.addEventListener("input",invalidateProtection));
  protectLabel.addEventListener("input",invalidateProtection);
  exportMode.addEventListener("change",()=>{
    invalidateProtection();
    exportModeNote.textContent=exportMode.value==="periodic-local-retime-v2" ? "5× local retiming inside the detected interval only. Requires at least three repeated cycles, mean recurrence error ≤2 and every sample difference ≤32 native codes. Small nonperiodic changes can still pass. Strong entry transitions remain; playback unverified; no safety claim." : exportMode.value==="legacy" ? "Legacy interval hold: a strong return transition and codec spill are possible." : "Experimental: freeze the selected decoration from frame zero for the ENTIRE clip. Lossless native YUV transport; adjacent RGB pixels can still change. Review all measurements. No safety claim.";
  });
  protectAdd.addEventListener("click",saveProtectedRegion);
  protectEditCancel.addEventListener("click",cancelProtectedEdit);
  teachingGuideLoad.addEventListener("click",loadTeachingGuide);
  ui.protectCheck.addEventListener("click",checkProtection);
  ui.protectClear.addEventListener("click",() => { resetProtection(currentCandidate()); ui.reviewed.checked=false;updateControls(); });
  function startAreaMarking() {
    if (ui.protectPick.disabled) return;
    pickDraft=[ui.protectX,ui.protectY,ui.protectW,ui.protectH].map(field=>field.value);
    picking=true;firstCorner=null;invalidateProtection();
    ui.protectStatus.textContent="Choose the first corner on the static image. Cancel marking or press Escape to keep your previous draft. Pixel fields remain available after marking.";
  }
  function cancelAreaMarking() {
    if (!picking || busy || refreshInFlight || stateUncertain || !imageLoaded || job?.status!=="review") return;
    if (pickDraft) [ui.protectX,ui.protectY,ui.protectW,ui.protectH].forEach((field,i)=>{field.value=pickDraft[i];});
    picking=false;firstCorner=null;pickDraft=null;invalidateProtection();
    ui.protectStatus.textContent="Marking cancelled. Previous draft and saved areas kept. Check the plan again before generating.";
  }
  function markAreaCorner(event) {
    if (!picking || !imageLoaded || busy || refreshInFlight || stateUncertain || job?.status!=="review") return;
    const box=ui.image.getBoundingClientRect();
    if (!(box.width>0 && box.height>0 && ui.image.naturalWidth>0 && ui.image.naturalHeight>0) || !Number.isFinite(event.clientX) || !Number.isFinite(event.clientY) || event.clientX<box.left || event.clientY<box.top || event.clientX>=box.left+box.width || event.clientY>=box.top+box.height) return;
    const point=[Math.floor((event.clientX-box.left)*ui.image.naturalWidth/box.width),Math.floor((event.clientY-box.top)*ui.image.naturalHeight/box.height)];
    if (!firstCorner) { firstCorner=point;ui.protectStatus.textContent="First corner: ("+point.join(", ")+"). Choose the opposite corner, or cancel marking to start again.";return; }
    const values=[Math.min(firstCorner[0],point[0]),Math.min(firstCorner[1],point[1]),Math.abs(firstCorner[0]-point[0])+1,Math.abs(firstCorner[1]-point[1])+1];
    [ui.protectX,ui.protectY,ui.protectW,ui.protectH].forEach((field,i) => { field.value=String(values[i]); });
    picking=false;firstCorner=null;pickDraft=null;invalidateProtection();
    ui.protectStatus.textContent="Rectangle marked: ["+values.join(", ")+"]. Name and save the area, then check the edit plan. Nothing has been approved.";
  }
  ui.protectPick.addEventListener("click",startAreaMarking);
  protectPickCancel.addEventListener("click",cancelAreaMarking);
  ui.image.addEventListener("click",markAreaCorner);
  window.addEventListener("keydown",event=>{if(event.key==="Escape" && picking)cancelAreaMarking();});
  ui.reviewed.addEventListener("change", updateControls);
  ui.approve.addEventListener("click", () => {
    if (ui.approve.disabled) return;
    const candidate = currentCandidate();
    if (!candidate?.recipe_sha256 || !job?.prediction_sha256) return;
    if (!protectionPlan) return;
    decision("approve", { candidate_id: candidate.id, prediction_sha256: job.prediction_sha256, recipe_sha256: protectionPlan.recipe_sha256, protected_regions: protectionPlan.protected_regions, export_mode: protectionPlan.export_mode || "legacy", approve: true });
  });
  ui.decline.addEventListener("click", () => {
    if (!ui.decline.disabled) decision("decline", {});
  });
  ui.cancel.addEventListener("click", () => {
    if (!ui.cancel.disabled) decision("cancel", {});
  });
  ui.retry.addEventListener("click", refreshJob);
  recovery.retry.addEventListener("click", restoreJob);
  recovery.dismiss.addEventListener("click", forgetRecovery);
  window.addEventListener("pagehide", stopPolling);

  async function initialize() {
    try {
      const data = await request("/api/profile");
      if (!data || typeof data.csrf_token !== "string" || !data.csrf_token) {
        throw new Error("The server did not provide a request token. Reload after checking the local server.");
      }
      token = data.csrf_token;
      if (data.transport?.kind === "aws" && typeof data.transport.message === "string") {
        ui.serviceScope.textContent = data.transport.message;
        ui.serviceScope.hidden = false;
        ui.serviceBadge.textContent = "AWS lesson rescue demo";
        ui.cloudSamples.hidden = false;
      }
      try {
        const saved = window.sessionStorage.getItem(RECOVERY_KEY);
        if (validJobId(saved)) recoveryId = saved;
        else if (saved !== null) window.sessionStorage.removeItem(RECOVERY_KEY);
      } catch (_) { /* Storage may be disabled; ordinary local review still works. */ }
      ui.profile.textContent = JSON.stringify({ profiles: data.supported_profiles || [data.profile], limits: data.limits, limitations: data.limitations }, null, 2);
      updateControls();
      await restoreJob();
    } catch (error) {
      ui.profile.textContent = "The server profile is unavailable.";
      showError(ui.connectionError, error.message);
    }
  }

  updateNaturalChoice();
  initialize();
})();
