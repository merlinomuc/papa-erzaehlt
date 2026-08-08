import {
  API,
  ROMAN_PROFILE_ID,
  SUPABASE_URL,
  SUPABASE_KEY
} from "./config.js";

const supabaseClient = window.supabase.createClient(
  SUPABASE_URL,
  SUPABASE_KEY,
  {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true
    }
  }
);

let currentProfileId = null;
let currentRole = null;
let currentMode = null;
let currentHistoryId = null;
let currentAnswerId = null;

let currentFollowUpQuestion = "";
let currentPrivacySignal = false;
let currentPrivacyReason = "";

let currentTimelineYear = null;
let currentTimelineLabel = "";
let currentTimelineConfidence = "unknown";

let archiveItems = [];
let openedMemoryId = null;

let mediaRecorder = null;
let mediaStream = null;
let audioChunks = [];
let recordingMimeType = "";
let recordingExtension = "webm";

let audioContext = null;
let analyser = null;
let analyserData = null;
let meterAnimationId = null;

let timerInterval = null;
let recordingStartedAt = null;

const startupView = document.getElementById("startupView");
const loginView = document.getElementById("loginView");
const appView = document.getElementById("appView");

const homeScreen = document.getElementById("homeScreen");
const storyScreen = document.getElementById("storyScreen");
const processingScreen = document.getElementById("processingScreen");
const reviewScreen = document.getElementById("reviewScreen");
const savedScreen = document.getElementById("savedScreen");
const memoriesScreen = document.getElementById("memoriesScreen");
const timelineScreen = document.getElementById("timelineScreen");

const screens = [
  homeScreen,
  storyScreen,
  processingScreen,
  reviewScreen,
  savedScreen,
  memoriesScreen,
  timelineScreen
];

const emailInput = document.getElementById("email");
const passwordInput = document.getElementById("password");
const loginButton = document.getElementById("loginButton");
const loginMessage = document.getElementById("loginMessage");
const logoutButton = document.getElementById("logoutButton");

const homeNavTell = document.getElementById("homeNavTell");
const homeNavMemories = document.getElementById("homeNavMemories");
const homeNavTimeline = document.getElementById("homeNavTimeline");

const questionModeButton = document.getElementById("questionModeButton");
const freeModeButton = document.getElementById("freeModeButton");
const homeMicButton = document.getElementById("homeMicButton");

const storyBackButton = document.getElementById("storyBackButton");
const memoriesBackButton = document.getElementById("memoriesBackButton");
const timelineBackButton = document.getElementById("timelineBackButton");
const backToHomeButton = document.getElementById("backToHomeButton");

const storyHeading = document.getElementById("storyHeading");
const questionContent = document.getElementById("questionContent");
const freeContent = document.getElementById("freeContent");
const questionElement = document.getElementById("question");

const recordButton = document.getElementById("recordButton");
const micText = document.getElementById("micText");
const recordingFeedback = document.getElementById("recordingFeedback");
const recordingTime = document.getElementById("recordingTime");
const audioMeter = document.getElementById("audioMeter");
const statusElement = document.getElementById("status");

const newQuestionButton = document.getElementById("newQuestionButton");

const processingText = document.getElementById("processingText");

const transcriptElement = document.getElementById("transcript");
const summaryElement = document.getElementById("summary");
const confirmButton = document.getElementById("confirmButton");
const retryButton = document.getElementById("retryButton");
const discardButton = document.getElementById("discardButton");

const savedMessage = document.getElementById("savedMessage");
const privacyContainer = document.getElementById("privacyContainer");

const followUpBox = document.getElementById("followUpBox");
const followUpQuestionElement = document.getElementById("followUpQuestion");
const followUpButton = document.getElementById("followUpButton");
const skipFollowUpButton = document.getElementById("skipFollowUpButton");
const newMemoryButton = document.getElementById("newMemoryButton");

const archiveSearch = document.getElementById("archiveSearch");
const archiveList = document.getElementById("archiveList");

const timelineList = document.getElementById("timelineList");
const unknownTimeline = document.getElementById("unknownTimeline");

const memoryDialog = document.getElementById("memoryDialog");
const dialogClose = document.getElementById("dialogClose");
const dialogTitle = document.getElementById("dialogTitle");
const dialogTime = document.getElementById("dialogTime");
const dialogSummary = document.getElementById("dialogSummary");
const dialogTranscript = document.getElementById("dialogTranscript");

const timelineEditor = document.getElementById("timelineEditor");
const timelineYearInput = document.getElementById("timelineYearInput");
const timelineLabelInput = document.getElementById("timelineLabelInput");
const timelineConfidenceInput = document.getElementById("timelineConfidenceInput");
const saveTimelineButton = document.getElementById("saveTimelineButton");

function showScreen(screen) {
  screens.forEach(item => item.classList.remove("active"));
  screen.classList.add("active");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function apiFetch(path, options = {}) {
  const { data, error } = await supabaseClient.auth.getSession();

  if (error || !data.session) {
    await forceLogin();
    throw new Error("Deine Anmeldung ist abgelaufen.");
  }

  const headers = new Headers(options.headers || {});
  headers.set("Authorization", `Bearer ${data.session.access_token}`);

  const response = await fetch(`${API}${path}`, {
    ...options,
    headers
  });

  if (response.status === 401) {
    await forceLogin();
    throw new Error("Bitte erneut anmelden.");
  }

  return response;
}

async function initializeAuth() {
  startupView.style.display = "flex";
  loginView.style.display = "none";
  appView.style.display = "none";

  const { data, error } = await supabaseClient.auth.getSession();

  if (error || !data.session) {
    startupView.style.display = "none";
    showLogin();
    return;
  }

  try {
    await openApp();
    startupView.style.display = "none";
  } catch (error) {
    console.error(error);
    startupView.style.display = "none";
    showLogin();
    loginMessage.textContent = error.message;
  }
}

function showLogin() {
  startupView.style.display = "none";
  loginView.style.display = "flex";
  appView.style.display = "none";
}

async function forceLogin() {
  await supabaseClient.auth.signOut();
  currentProfileId = null;
  currentRole = null;
  showLogin();
}

async function login() {
  const email = emailInput.value.trim();
  const password = passwordInput.value;

  if (!email || !password) {
    loginMessage.textContent = "Bitte E-Mail und Passwort eingeben.";
    return;
  }

  loginButton.disabled = true;
  loginMessage.textContent = "Das Erinnerungsbuch wird geöffnet …";

  try {
    const { error } = await supabaseClient.auth.signInWithPassword({
      email,
      password
    });

    if (error) throw error;

    passwordInput.value = "";
    loginMessage.textContent = "";

    await openApp();
  } catch (error) {
    console.error(error);
    loginMessage.textContent =
      "Anmeldung fehlgeschlagen: " + error.message;
  } finally {
    loginButton.disabled = false;
  }
}

async function openApp() {
  const response = await apiFetch("/me");
  const me = await response.json();

  if (!response.ok) {
    throw new Error(
      me.detail ||
      "Benutzer konnte nicht geladen werden."
    );
  }

  currentRole = me.role;

  if (me.role === "narrator") {
    currentProfileId = me.profile_id;
  } else {
    currentProfileId = ROMAN_PROFILE_ID;
  }

  loginView.style.display = "none";
  appView.style.display = "block";

  if (currentRole === "reader") {
    showMemories();
  } else {
    showHome();
  }
}

async function logout() {
  await supabaseClient.auth.signOut();
  showLogin();
}

function showHome() {
  resetStoryState();
  currentMode = null;
  currentHistoryId = null;

  if (currentRole === "reader") {
    showMemories();
    return;
  }

  showScreen(homeScreen);
}

function resetStoryState() {
  currentAnswerId = null;
  currentFollowUpQuestion = "";
  currentPrivacySignal = false;
  currentPrivacyReason = "";
  currentTimelineYear = null;
  currentTimelineLabel = "";
  currentTimelineConfidence = "unknown";

  privacyContainer.innerHTML = "";
  followUpBox.classList.add("hidden");
  transcriptElement.textContent = "";
  summaryElement.textContent = "";
  statusElement.textContent = "";
}

async function startQuestionMode() {
  resetStoryState();
  currentMode = "question";

  storyHeading.textContent = "Eine Frage an dich";
  questionContent.classList.remove("hidden");
  freeContent.classList.add("hidden");
  newQuestionButton.classList.remove("hidden");

  showScreen(storyScreen);
  await loadQuestion();
}

function startFreeMode() {
  resetStoryState();
  currentMode = "free";
  currentHistoryId = null;

  storyHeading.textContent = "Freie Erinnerung";
  questionContent.classList.add("hidden");
  freeContent.classList.remove("hidden");
  newQuestionButton.classList.add("hidden");

  showScreen(storyScreen);
}

async function loadQuestion() {
  try {
    statusElement.textContent =
      "Ich suche eine Frage für dich aus …";

    const response = await apiFetch(
      `/question/next?profile_id=${currentProfileId}`
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail ||
        "Frage konnte nicht geladen werden."
      );
    }

    currentHistoryId = data.history_id;
    questionElement.textContent = data.question.text;
    statusElement.textContent = "";
  } catch (error) {
    console.error(error);
    statusElement.textContent = error.message;
  }
}

function selectRecordingFormat() {
  const formats = [
    { mime: "audio/webm;codecs=opus", extension: "webm" },
    { mime: "audio/webm", extension: "webm" },
    { mime: "audio/ogg;codecs=opus", extension: "ogg" },
    { mime: "audio/ogg", extension: "ogg" }
  ];

  for (const format of formats) {
    if (MediaRecorder.isTypeSupported(format.mime)) {
      return format;
    }
  }

  return null;
}

function startAudioMeter(stream) {
  audioContext =
    new (window.AudioContext || window.webkitAudioContext)();

  const source =
    audioContext.createMediaStreamSource(stream);

  analyser = audioContext.createAnalyser();
  analyser.fftSize = 256;
  analyser.smoothingTimeConstant = .82;

  source.connect(analyser);

  analyserData =
    new Uint8Array(analyser.frequencyBinCount);

  drawAudioMeter();
}

function drawAudioMeter() {
  if (!analyser) return;

  analyser.getByteFrequencyData(analyserData);

  const ctx = audioMeter.getContext("2d");
  const width = audioMeter.width;
  const height = audioMeter.height;

  ctx.clearRect(0, 0, width, height);

  const bars = 38;
  const step =
    Math.max(
      1,
      Math.floor(analyserData.length / bars)
    );

  const gap = 7;
  const barWidth =
    (width - gap * (bars - 1)) / bars;

  for (let i = 0; i < bars; i++) {
    const value =
      analyserData[i * step] / 255;

    const shaped =
      Math.pow(value, .75);

    const wave =
      .68 +
      .32 *
      Math.sin(
        Date.now() / 300 +
        i * .52
      );

    const barHeight =
      Math.max(
        5,
        shaped * height * .82 * wave
      );

    const x =
      i * (barWidth + gap);

    const y =
      (height - barHeight) / 2;

    const alpha =
      .24 +
      shaped * .76;

    const gradient =
      ctx.createLinearGradient(
        0,
        y,
        0,
        y + barHeight
      );

    gradient.addColorStop(
      0,
      `rgba(246,212,135,${alpha})`
    );

    gradient.addColorStop(
      .52,
      `rgba(214,160,67,${alpha})`
    );

    gradient.addColorStop(
      1,
      `rgba(135,55,51,${alpha})`
    );

    ctx.fillStyle = gradient;
    ctx.beginPath();

    if (ctx.roundRect) {
      ctx.roundRect(
        x,
        y,
        barWidth,
        barHeight,
        5
      );
    } else {
      ctx.rect(
        x,
        y,
        barWidth,
        barHeight
      );
    }

    ctx.fill();
  }

  meterAnimationId =
    requestAnimationFrame(
      drawAudioMeter
    );
}

async function stopAudioMeter() {
  if (meterAnimationId) {
    cancelAnimationFrame(meterAnimationId);
  }

  meterAnimationId = null;
  analyser = null;

  if (audioContext) {
    try {
      await audioContext.close();
    } catch (_) {}
  }

  audioContext = null;
}

function startTimer() {
  recordingStartedAt = Date.now();
  recordingTime.textContent = "00:00";

  timerInterval = setInterval(() => {
    const seconds =
      Math.floor(
        (Date.now() - recordingStartedAt) / 1000
      );

    const minutes =
      Math.floor(seconds / 60);

    const rest =
      seconds % 60;

    recordingTime.textContent =
      String(minutes).padStart(2, "0") +
      ":" +
      String(rest).padStart(2, "0");
  }, 500);
}

function stopTimer() {
  if (timerInterval) {
    clearInterval(timerInterval);
  }

  timerInterval = null;
}

async function startRecording() {
  try {
    const format =
      selectRecordingFormat();

    if (!format) {
      throw new Error(
        "Dieses Gerät unterstützt die Sprachaufnahme leider nicht."
      );
    }

    recordingMimeType =
      format.mime;

    recordingExtension =
      format.extension;

    mediaStream =
      await navigator.mediaDevices.getUserMedia({
        audio: true
      });

    mediaRecorder =
      new MediaRecorder(
        mediaStream,
        {
          mimeType:
            recordingMimeType,

          audioBitsPerSecond:
            128000
        }
      );

    audioChunks = [];

    mediaRecorder.ondataavailable =
      event => {
        if (
          event.data &&
          event.data.size > 0
        ) {
          audioChunks.push(event.data);
        }
      };

    mediaRecorder.onstop =
      handleFinishedRecording;

    mediaRecorder.start();

    recordButton.classList.add("recording");
    micText.textContent = "Fertig";

    recordingFeedback.classList.remove("hidden");

    newQuestionButton.classList.add("hidden");
    backToHomeButton.classList.add("hidden");

    statusElement.textContent = "";

    startTimer();
    startAudioMeter(mediaStream);
  } catch (error) {
    console.error(error);
    statusElement.textContent = error.message;
  }
}

async function stopRecording() {
  if (
    !mediaRecorder ||
    mediaRecorder.state === "inactive"
  ) {
    return;
  }

  mediaRecorder.stop();

  if (mediaStream) {
    mediaStream
      .getTracks()
      .forEach(track => track.stop());
  }

  stopTimer();
  await stopAudioMeter();

  recordButton.classList.remove("recording");
  micText.textContent = "Erzählen";

  recordingFeedback.classList.add("hidden");
}

async function createEmptyAnswer() {
  let response;

  if (currentMode === "free") {
    response =
      await apiFetch(
        "/answer/free",
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json"
          },
          body:
            JSON.stringify({
              profile_id:
                currentProfileId
            })
        }
      );
  } else {
    response =
      await apiFetch(
        "/answer",
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json"
          },
          body:
            JSON.stringify({
              history_id:
                currentHistoryId,

              text: ""
            })
        }
      );
  }

  const data =
    await response.json();

  if (!response.ok) {
    throw new Error(
      data.detail ||
      "Erinnerung konnte nicht angelegt werden."
    );
  }

  currentAnswerId =
    data.answer.id;
}

async function handleFinishedRecording() {
  try {
    showScreen(processingScreen);
    processingText.textContent =
      "Die Aufnahme wird sicher verwahrt …";

    if (!audioChunks.length) {
      throw new Error(
        "Es wurde keine Sprache aufgenommen."
      );
    }

    await createEmptyAnswer();

    const actualMimeType =
      mediaRecorder.mimeType ||
      recordingMimeType;

    const audioBlob =
      new Blob(
        audioChunks,
        {
          type:
            actualMimeType
        }
      );

    const formData =
      new FormData();

    formData.append(
      "answer_id",
      currentAnswerId
    );

    formData.append(
      "audio",
      audioBlob,
      `aufnahme.${recordingExtension}`
    );

    const uploadResponse =
      await apiFetch(
        "/audio/upload",
        {
          method: "POST",
          body: formData
        }
      );

    const uploadData =
      await uploadResponse.json();

    if (!uploadResponse.ok) {
      throw new Error(
        uploadData.detail ||
        "Aufnahme konnte nicht gespeichert werden."
      );
    }

    processingText.textContent =
      "Ich schreibe deine Worte auf …";

    const transcribeResponse =
      await apiFetch(
        `/answer/${currentAnswerId}/transcribe`,
        {
          method: "POST"
        }
      );

    const transcribeData =
      await transcribeResponse.json();

    if (!transcribeResponse.ok) {
      throw new Error(
        transcribeData.detail ||
        "Sprache konnte nicht erkannt werden."
      );
    }

    transcriptElement.textContent =
      transcribeData.transcript ||
      "(Kein Text erkannt.)";

    processingText.textContent =
      "Ich ordne die Erinnerung behutsam ein …";

    const analyzeResponse =
      await apiFetch(
        `/answer/${currentAnswerId}/analyze`,
        {
          method: "POST"
        }
      );

    const analyzeData =
      await analyzeResponse.json();

    if (!analyzeResponse.ok) {
      throw new Error(
        analyzeData.detail ||
        "Erinnerung konnte nicht ausgewertet werden."
      );
    }

    summaryElement.textContent =
      analyzeData.memory?.summary ||
      "Keine Zusammenfassung vorhanden.";

    currentFollowUpQuestion =
      analyzeData.follow_up_question ||
      "";

    currentPrivacySignal =
      analyzeData.privacy_signal === true;

    currentPrivacyReason =
      analyzeData.privacy_reason ||
      "";

    currentTimelineYear =
      analyzeData.timeline_year;

    currentTimelineLabel =
      analyzeData.timeline_label ||
      "";

    currentTimelineConfidence =
      analyzeData.timeline_confidence ||
      "unknown";

    showScreen(reviewScreen);
  } catch (error) {
    console.error(error);

    showScreen(storyScreen);

    newQuestionButton.classList.toggle(
      "hidden",
      !(
        currentMode === "question" ||
        currentMode === "followup"
      )
    );

    backToHomeButton.classList.remove("hidden");

    statusElement.textContent =
      "Das hat leider nicht geklappt: " +
      error.message;
  }
}

async function discardCurrentAnswer() {
  if (!currentAnswerId) return;

  const response =
    await apiFetch(
      `/answer/${currentAnswerId}/discard`,
      {
        method: "POST",
        headers: {
          "Content-Type":
            "application/json"
        },
        body:
          JSON.stringify({
            history_id:
              currentHistoryId ||
              null
          })
      }
    );

  const data =
    await response.json();

  if (!response.ok) {
    throw new Error(
      data.detail ||
      "Aufnahme konnte nicht verworfen werden."
    );
  }

  currentAnswerId = null;
}

async function retryRecording() {
  try {
    retryButton.disabled = true;

    await discardCurrentAnswer();

    showScreen(storyScreen);

    backToHomeButton.classList.remove("hidden");

    newQuestionButton.classList.toggle(
      "hidden",
      !(
        currentMode === "question" ||
        currentMode === "followup"
      )
    );

    statusElement.textContent =
      "Kein Problem. Erzähl es einfach noch einmal.";
  } catch (error) {
    console.error(error);
    statusElement.textContent = error.message;
  } finally {
    retryButton.disabled = false;
  }
}

async function discardMemory() {
  try {
    discardButton.disabled = true;
    await discardCurrentAnswer();
    showHome();
  } catch (error) {
    console.error(error);
    statusElement.textContent = error.message;
  } finally {
    discardButton.disabled = false;
  }
}

function confirmMemory() {
  showScreen(savedScreen);

  if (currentTimelineYear) {
    const label =
      currentTimelineLabel ||
      String(currentTimelineYear);

    savedMessage.textContent =
      `Gespeichert · zeitlich eingeordnet: ${label}`;
  } else {
    savedMessage.textContent =
      "Gespeichert · die Zeit kann später ergänzt werden.";
  }

  if (currentPrivacySignal) {
    showPrivacy(currentPrivacyReason);
  }

  if (currentFollowUpQuestion) {
    followUpQuestionElement.textContent =
      currentFollowUpQuestion;

    followUpBox.classList.remove("hidden");
  }
}

function showPrivacy(reason) {
  privacyContainer.innerHTML = "";

  const box =
    document.createElement("div");

  box.className = "privacy-box";

  box.innerHTML = `
    <div class="eyebrow">Vertraulichkeit</div>

    <h3>
      Diese Erinnerung klingt vertraulich
    </h3>

    <p style="
      text-align:center;
      color:var(--cream-soft);
      line-height:1.6;
    ">
      Soll diese Erinnerung ausschließlich
      innerhalb der Familie bleiben?
    </p>

    ${
      reason
        ? `
          <p style="
            text-align:center;
            color:var(--cream-soft);
            font-size:.88rem;
            line-height:1.5;
          ">
            ${escapeHtml(reason)}
          </p>
        `
        : ""
    }

    <div class="button-stack">
      <button id="privacyFamily" class="gold-button">
        Nur für die Familie
      </button>

      <button id="privacyAll" class="outline-button">
        Darf ins Erinnerungsbuch
      </button>
    </div>
  `;

  privacyContainer.appendChild(box);

  document
    .getElementById("privacyFamily")
    .onclick =
      () => setVisibility("family");

  document
    .getElementById("privacyAll")
    .onclick =
      () => setVisibility("all");
}

async function setVisibility(visibility) {
  try {
    const response =
      await apiFetch(
        `/answer/${currentAnswerId}/visibility`,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json"
          },
          body:
            JSON.stringify({
              visibility
            })
        }
      );

    const data =
      await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail ||
        "Auswahl konnte nicht gespeichert werden."
      );
    }

    privacyContainer.innerHTML = "";

    if (visibility === "family") {
      savedMessage.textContent =
        "Gespeichert · diese Erinnerung bleibt innerhalb der Familie.";
    } else {
      savedMessage.textContent =
        "Gespeichert · diese Erinnerung darf später auch für Romans Erinnerungsbuch verwendet werden.";
    }
  } catch (error) {
    console.error(error);

    savedMessage.textContent =
      "Die Auswahl konnte leider nicht gespeichert werden.";
  }
}

async function activateFollowUp() {
  try {
    const parentAnswerId =
      currentAnswerId;

    const response =
      await apiFetch(
        "/question/follow-up",
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json"
          },
          body:
            JSON.stringify({
              profile_id:
                currentProfileId,

              parent_answer_id:
                parentAnswerId,

              text:
                currentFollowUpQuestion
            })
        }
      );

    const data =
      await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail ||
        "Nachfrage konnte nicht vorbereitet werden."
      );
    }

    resetStoryState();

    currentMode = "followup";
    currentHistoryId = data.history_id;

    storyHeading.textContent =
      "Noch eine Frage";

    questionContent.classList.remove("hidden");
    freeContent.classList.add("hidden");

    questionElement.textContent =
      data.question.text;

    newQuestionButton.classList.remove("hidden");
    backToHomeButton.classList.remove("hidden");

    showScreen(storyScreen);
  } catch (error) {
    console.error(error);
    savedMessage.textContent = error.message;
  }
}

async function loadArchive() {
  try {
    const response =
      await apiFetch(
        `/archive?profile_id=${currentProfileId}`
      );

    const data =
      await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail ||
        "Erinnerungen konnten nicht geladen werden."
      );
    }

    archiveItems =
      data.items ||
      [];

    renderArchive(archiveItems);

    return archiveItems;
  } catch (error) {
    console.error(error);

    archiveList.innerHTML = `
      <p style="
        text-align:center;
        color:var(--cream-soft)
      ">
        ${escapeHtml(error.message)}
      </p>
    `;

    return [];
  }
}

function getMemoryTitle(item) {
  if (item.question?.text) {
    return item.question.text;
  }

  const summary =
    item.memory?.summary ||
    "";

  if (summary) {
    return summary.length > 78
      ? summary.slice(0, 78) + " …"
      : summary;
  }

  return "Freie Erinnerung";
}

function getMemorySummary(item) {
  return (
    item.memory?.summary ||
    item.transcript ||
    "Erinnerung"
  );
}

function renderArchive(items) {
  archiveList.innerHTML = "";

  if (!items.length) {
    archiveList.innerHTML = `
      <div style="
        text-align:center;
        color:var(--cream-soft);
        padding:32px 0;
        font-style:italic;
      ">
        Noch wartet dieses Kapitel
        auf seine ersten Geschichten.
      </div>
    `;
    return;
  }

  for (const item of items) {
    const card =
      document.createElement("article");

    card.className =
      "memory-card";

    const time =
      item.timeline_label ||
      (
        item.timeline_year
          ? String(item.timeline_year)
          : "Zeit noch unbekannt"
      );

    card.innerHTML = `
      <div class="memory-meta">
        ${
          item.is_free_memory
            ? "Freie Erinnerung"
            : "Erzählte Erinnerung"
        }
      </div>

      <div class="memory-title">
        ${escapeHtml(getMemoryTitle(item))}
      </div>

      <div class="memory-summary">
        ${escapeHtml(getMemorySummary(item))}
      </div>

      <span class="memory-time">
        ${escapeHtml(time)}
      </span>
    `;

    card.onclick =
      () => openMemory(item.answer_id);

    archiveList.appendChild(card);
  }
}

function filterArchive() {
  const term =
    archiveSearch.value
      .trim()
      .toLowerCase();

  if (!term) {
    renderArchive(archiveItems);
    return;
  }

  const filtered =
    archiveItems.filter(item => {
      const haystack =
        [
          getMemoryTitle(item),
          getMemorySummary(item),
          item.transcript,
          item.timeline_label,
          item.timeline_year
        ]
          .join(" ")
          .toLowerCase();

      return haystack.includes(term);
    });

  renderArchive(filtered);
}

async function showMemories() {
  showScreen(memoriesScreen);
  await loadArchive();
}

async function showTimeline() {
  showScreen(timelineScreen);
  await loadArchive();
  renderTimeline();
}

function renderTimeline() {
  timelineList.innerHTML = "";
  unknownTimeline.innerHTML = "";

  const dated =
    archiveItems
      .filter(
        item =>
          item.timeline_year !== null &&
          item.timeline_year !== undefined
      )
      .sort(
        (a, b) =>
          a.timeline_year -
          b.timeline_year
      );

  const unknown =
    archiveItems.filter(
      item =>
        item.timeline_year === null ||
        item.timeline_year === undefined
    );

  if (!dated.length) {
    timelineList.innerHTML = `
      <p style="
        text-align:center;
        color:var(--cream-soft);
        font-style:italic;
      ">
        Noch wurde keine Erinnerung
        zeitlich eingeordnet.
      </p>
    `;
  }

  dated.forEach(
    (item, index) => {
      const row =
        document.createElement("div");

      row.className =
        "timeline-item";

      row.style.animationDelay =
        `${Math.min(index * 70, 650)}ms`;

      row.innerHTML = `
        <div class="timeline-year">
          ${item.timeline_year}
        </div>

        <div class="timeline-dot-wrap">
          <div class="timeline-dot"></div>
        </div>

        <div class="timeline-memory">
          <h3>
            ${escapeHtml(getMemoryTitle(item))}
          </h3>

          <p>
            ${escapeHtml(getMemorySummary(item))}
          </p>

          ${
            item.timeline_label &&
            item.timeline_label !==
              String(item.timeline_year)
              ? `
                <div style="
                  margin-top:8px;
                  color:var(--gold-mid);
                  font-style:italic;
                  font-size:.88rem;
                ">
                  ${escapeHtml(item.timeline_label)}
                </div>
              `
              : ""
          }
        </div>
      `;

      row
        .querySelector(".timeline-memory")
        .onclick =
          () => openMemory(item.answer_id);

      timelineList.appendChild(row);
    }
  );

  if (unknown.length) {
    unknownTimeline.innerHTML = `
      <div class="eyebrow">
        Noch ohne Jahreszahl
      </div>

      <h3 style="
        text-align:center;
        color:#e5c68f;
        font-weight:normal;
      ">
        Zeit noch unbekannt
      </h3>
    `;

    for (const item of unknown) {
      const card =
        document.createElement("article");

      card.className =
        "memory-card";

      card.innerHTML = `
        <div class="memory-title">
          ${escapeHtml(getMemoryTitle(item))}
        </div>

        <div class="memory-summary">
          ${escapeHtml(getMemorySummary(item))}
        </div>

        <span class="memory-time">
          ${
            currentRole !== "reader"
              ? "Zeit hinzufügen"
              : "Zeit unbekannt"
          }
        </span>
      `;

      card.onclick =
        () => openMemory(item.answer_id);

      unknownTimeline.appendChild(card);
    }
  }
}

function openMemory(answerId) {
  const item =
    archiveItems.find(
      row =>
        row.answer_id ===
        answerId
    );

  if (!item) return;

  openedMemoryId = answerId;

  dialogTitle.textContent =
    getMemoryTitle(item);

  dialogSummary.textContent =
    getMemorySummary(item);

  dialogTranscript.textContent =
    item.transcript ||
    "";

  if (
    item.timeline_year ||
    item.timeline_label
  ) {
    dialogTime.textContent =
      item.timeline_label ||
      String(item.timeline_year);
  } else {
    dialogTime.textContent =
      "Zeit noch unbekannt";
  }

  timelineYearInput.value =
    item.timeline_year ||
    "";

  timelineLabelInput.value =
    item.timeline_label ||
    "";

  timelineConfidenceInput.value =
    item.timeline_confidence ||
    "unknown";

  timelineEditor.style.display =
    currentRole === "reader"
      ? "none"
      : "block";

  memoryDialog.style.display =
    "block";

  document.body.style.overflow =
    "hidden";
}

function closeMemory() {
  memoryDialog.style.display =
    "none";

  document.body.style.overflow =
    "";

  openedMemoryId = null;
}

async function saveTimeline() {
  if (!openedMemoryId) return;

  const yearText =
    timelineYearInput.value.trim();

  const year =
    yearText
      ? Number(yearText)
      : null;

  if (
    year !== null &&
    (
      !Number.isInteger(year) ||
      year < 1800 ||
      year > 2100
    )
  ) {
    alert(
      "Bitte eine gültige Jahreszahl eingeben."
    );
    return;
  }

  saveTimelineButton.disabled = true;

  try {
    const response =
      await apiFetch(
        `/answer/${openedMemoryId}/timeline`,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json"
          },
          body:
            JSON.stringify({
              timeline_year:
                year,

              timeline_label:
                timelineLabelInput.value
                  .trim() ||
                null,

              timeline_confidence:
                year
                  ? timelineConfidenceInput.value
                  : "unknown"
            })
        }
      );

    const data =
      await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail ||
        "Zeit konnte nicht gespeichert werden."
      );
    }

    await loadArchive();

    const updated =
      archiveItems.find(
        row =>
          row.answer_id ===
          openedMemoryId
      );

    if (updated) {
      dialogTime.textContent =
        updated.timeline_label ||
        updated.timeline_year ||
        "Zeit noch unbekannt";
    }

    renderTimeline();

    saveTimelineButton.textContent =
      "✓ Gespeichert";

    setTimeout(
      () => {
        saveTimelineButton.textContent =
          "Zeit speichern";
      },
      1800
    );
  } catch (error) {
    console.error(error);
    alert(error.message);
  } finally {
    saveTimelineButton.disabled = false;
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

/* Events */
loginButton.onclick = login;

passwordInput.addEventListener(
  "keydown",
  event => {
    if (event.key === "Enter") {
      login();
    }
  }
);

logoutButton.onclick = logout;

homeNavTell.onclick = showHome;
homeNavMemories.onclick = showMemories;
homeNavTimeline.onclick = showTimeline;

questionModeButton.onclick =
  startQuestionMode;

freeModeButton.onclick =
  startFreeMode;

homeMicButton.onclick =
  startFreeMode;

storyBackButton.onclick =
  showHome;

memoriesBackButton.onclick =
  showHome;

timelineBackButton.onclick =
  showHome;

backToHomeButton.onclick =
  showHome;

newQuestionButton.onclick =
  async () => {
    currentMode = "question";
    await loadQuestion();
  };

recordButton.onclick =
  async () => {
    if (
      !mediaRecorder ||
      mediaRecorder.state === "inactive"
    ) {
      await startRecording();
    } else {
      await stopRecording();
    }
  };

confirmButton.onclick =
  confirmMemory;

retryButton.onclick =
  retryRecording;

discardButton.onclick =
  discardMemory;

followUpButton.onclick =
  activateFollowUp;

skipFollowUpButton.onclick =
  showHome;

newMemoryButton.onclick =
  showHome;

archiveSearch.addEventListener(
  "input",
  filterArchive
);

dialogClose.onclick =
  closeMemory;

memoryDialog.addEventListener(
  "click",
  event => {
    if (
      event.target ===
      memoryDialog
    ) {
      closeMemory();
    }
  }
);

document.addEventListener(
  "keydown",
  event => {
    if (
      event.key === "Escape" &&
      memoryDialog.style.display === "block"
    ) {
      closeMemory();
    }
  }
);

saveTimelineButton.onclick =
  saveTimeline;

initializeAuth();
