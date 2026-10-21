/* Computer-backed recording is independent of the control polling loop. */
let recordingView = null,
  nextBusy = false,
  profileLoaded = false,
  recordingErrorUntil = 0;
const readableBytes = (value) =>
  Number(value || 0) >= 1024 ** 3
    ? (value / 1024 ** 3).toFixed(2) + " GB"
    : (value / 1024 ** 2).toFixed(1) + " MB";
window.renderRecording = (r, demo = false) => {
  if (r?.saved_directory) window.localRecordingAvailable = true;
  recordingView = r || {};
  $("#recordingState").textContent = t(
    demo
      ? "Preview only"
      : r?.finishing
        ? "Finishing recording…"
      : r?.ready
        ? "Recording"
        : r?.initializing
          ? "Preparing recording…"
          : r?.error
            ? "Recording error"
            : r?.active ? "Preparing recording…" : "Not recording",
  );
  $("#recordingState").classList.toggle("error", !demo && !!r?.error);
  $("#instanceLabel").textContent = r?.instance_id || "—";
  $("#recordingMetrics").textContent = r
    ? t("{0} frames · {1} archived", [
        r.frames || 0,
        readableBytes(r.archived_bytes),
      ])
    : "";
  $("#recordingPath").textContent =
    r?.saved_directory ||
    t("Connect using scripts/connect.sh to save on this computer");
  $("#startRecording").disabled = demo || !r?.saved_directory || r?.active || r?.initializing || r?.finishing;
  $("#finishRecording").disabled = demo || !r?.active || r?.finishing;
  $("#nextInstance").disabled = nextBusy || !r?.active || r?.finishing || demo;
  $("#retryRecording").disabled = !r?.active || !r?.error;
  $("#openRecordingFolder").disabled = !r?.saved_directory;
  if (performance.now() > recordingErrorUntil)
    $("#recordingError").textContent = t(r?.error || "");
  $("#archiveProgress").textContent = r?.saved_directory
    ? t(
        "{0} chunks verified · {1} free on computer · Robot copies are deleted only after verification",
        [r.archived_chunks || 0, readableBytes(r.free_bytes)],
      )
    : "";
  if (!profileLoaded && r?.profile) {
    $("#recordingFormat").value = r.profile.format;
    $("#recordingFps").value = r.profile.fps;
    $("#recordingResolution").value = r.profile.width + "x" + r.profile.height;
    profileLoaded = true;
  }
};
function recordingFailure(error) {
  $("#recordingError").textContent = t(error.message || String(error));
  recordingErrorUntil = performance.now() + 8000;
}
window.nextRecordingInstance = async () => {
  if (nextBusy || !recordingView?.active) return;
  nextBusy = true;
  try {
    await api("/local/recording/next", {
      request_id: crypto.randomUUID().replaceAll("-", ""),
      name: $("#instanceName").value.trim(),
    });
    $("#instanceName").value = "";
    refreshInstances();
  } catch (error) {
    recordingFailure(error);
  } finally {
    nextBusy = false;
    tick();
  }
};
$("#nextInstance").onclick = window.nextRecordingInstance;
$("#startRecording").onclick = () => api("/local/recording/start", {}).catch(recordingFailure);
$("#openRecordingFolder").onclick = () =>
  api("/local/recording/open-folder", {}).catch(recordingFailure);
$("#retryRecording").onclick = () => {
  api("/local/recording/retry", {}).catch(recordingFailure);
};
$("#finishRecording").onclick = () => {
  api("/local/recording/finish", {}).catch(recordingFailure);
};
$("#applyRecordingProfile").onclick = async () => {
  const [width, height] = $("#recordingResolution")
    .value.split("x")
    .map(Number);
  try {
    await api("/local/recording/profile", {
      width,
      height,
      fps: Number($("#recordingFps").value),
      format: $("#recordingFormat").value,
    });
    $("#recordingError").textContent = t(
      "Profile queued. Stop driving, then start the next instance.",
    );
    recordingErrorUntil = performance.now() + 8000;
  } catch (error) {
    recordingFailure(error);
  }
};
async function refreshInstances() {
  if (!recordingView?.saved_directory) return;
  try {
    const result = await api("/local/instances");
    $("#instanceList").replaceChildren(
      ...result.instances
        .slice(-8)
        .reverse()
        .map((item) => {
          const element = document.createElement("li");
          element.textContent =
            item.instance_id +
            (item.name ? " · " + item.name : "") +
            " · " +
            t(item.status);
          return element;
        }),
    );
  } catch (_) {}
}
async function loadCameraProfiles() {
  try {
    const camera = await api("/capture/status"),
      selected = $("#recordingResolution").value;
    $("#recordingResolution").replaceChildren(
      ...camera.resolutions.map(([width, height]) => {
        const option = document.createElement("option");
        option.value = width + "x" + height;
        option.textContent = width + " × " + height;
        return option;
      }),
    );
    $("#recordingResolution").value = selected;
  } catch (_) {}
}
setInterval(refreshInstances, 3000);
loadCameraProfiles();
window.addEventListener("languagechange", () => {
  if (recordingView) window.renderRecording(recordingView, !!state?.demo);
  refreshInstances();
});
// Driving responses must never replace the richer computer recording state.
async function refreshRecordingState() {
  try {
    const r = await api('/local/recording/status');
    window.renderRecording(r);
  } catch (_) { /* The regular connection status handles unavailable companions. */ }
}
refreshRecordingState();
setInterval(refreshRecordingState, 500);
