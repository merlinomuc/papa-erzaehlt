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
let currentIdentityCandidateId = null;
let currentIdentityQuestion = false;
let currentPrivacySignal = false;
let currentPrivacyReason = "";

let currentTimelineYear = null;
let currentTimelineLabel = "";
let currentTimelineConfidence = "unknown";

let archiveItems = [];
let openedMemoryId = null;
let currentMemoir = null;
let currentAudioObjectUrl = null;

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

let supplementRecorder = null;
let supplementStream = null;
let supplementChunks = [];
let supplementMimeType = "";
let supplementExtension = "webm";

let reviewCorrectionRecorder = null;
let reviewCorrectionStream = null;
let reviewCorrectionChunks = [];
let reviewCorrectionMimeType = "";
let reviewCorrectionExtension = "webm";
let reviewCorrectionProposedText = "";
let reviewCorrectionInstructionText = "";
let reviewCorrectionAudioContext = null;
let reviewCorrectionAnalyser = null;
let reviewCorrectionAnalyserData = null;
let reviewCorrectionMeterAnimationId = null;
let reviewCorrectionTimerInterval = null;
let reviewCorrectionRecordingStartedAt = null;
let currentAnalysisRunning = false;

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
const settingsScreen = document.getElementById("settingsScreen");

const screens = [
  homeScreen,
  storyScreen,
  processingScreen,
  reviewScreen,
  savedScreen,
  memoriesScreen,
  timelineScreen,
  settingsScreen
];

const emailInput = document.getElementById("email");
const passwordInput = document.getElementById("password");
const loginButton = document.getElementById("loginButton");
const loginMessage = document.getElementById("loginMessage");
const logoutButton = document.getElementById("logoutButton");
const settingsButton = document.getElementById("settingsButton");
const settingsBackButton = document.getElementById("settingsBackButton");
const memoirStats = document.getElementById("memoirStats");
const generateCompleteMemoirButton = document.getElementById("generateCompleteMemoirButton");
const generateShareMemoirButton = document.getElementById("generateShareMemoirButton");
const memoirStatus = document.getElementById("memoirStatus");
const memoirWorking = document.getElementById("memoirWorking");
const memoirWorkingTitle = document.getElementById("memoirWorkingTitle");
const memoirWorkingDetail = document.getElementById("memoirWorkingDetail");
const memoirWorkingElapsed = document.getElementById("memoirWorkingElapsed");
const memoirPreview = document.getElementById("memoirPreview");
const memoirPreviewTitle = document.getElementById("memoirPreviewTitle");
const memoirPreviewMeta = document.getElementById("memoirPreviewMeta");
const memoirPreviewIntro = document.getElementById("memoirPreviewIntro");
const memoirChapterList = document.getElementById("memoirChapterList");
const memoirPreviewEpilogue = document.getElementById("memoirPreviewEpilogue");
const memoirPdfButton = document.getElementById("memoirPdfButton");
const memoirDocxButton = document.getElementById("memoirDocxButton");
const archiveBackupButton = document.getElementById("archiveBackupButton");
const archiveBackupStatus = document.getElementById("archiveBackupStatus");

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

const speakCorrectionButton = document.getElementById("speakCorrectionButton");
const editReviewTranscriptButton = document.getElementById("editReviewTranscriptButton");
const reviewCorrectionStatus = document.getElementById("reviewCorrectionStatus");
const reviewCorrectionFeedback = document.getElementById("reviewCorrectionFeedback");
const reviewCorrectionTime = document.getElementById("reviewCorrectionTime");
const reviewCorrectionAudioMeter = document.getElementById("reviewCorrectionAudioMeter");
const reviewCorrectionPreview = document.getElementById("reviewCorrectionPreview");
const reviewCorrectionInstruction = document.getElementById("reviewCorrectionInstruction");
const reviewCorrectionChanges = document.getElementById("reviewCorrectionChanges");
const reviewCorrectionExplanation = document.getElementById("reviewCorrectionExplanation");
const reviewCorrectionFullText = document.getElementById("reviewCorrectionFullText");
const applyReviewCorrectionButton = document.getElementById("applyReviewCorrectionButton");
const repeatReviewCorrectionButton = document.getElementById("repeatReviewCorrectionButton");
const cancelReviewCorrectionButton = document.getElementById("cancelReviewCorrectionButton");
const reviewTranscriptEditPanel = document.getElementById("reviewTranscriptEditPanel");
const reviewTranscriptTextarea = document.getElementById("reviewTranscriptTextarea");
const saveReviewTranscriptButton = document.getElementById("saveReviewTranscriptButton");
const cancelReviewTranscriptButton = document.getElementById("cancelReviewTranscriptButton");

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

let memoryToolsContainer = null;
let editTranscriptButton = null;
let transcriptEditPanel = null;
let transcriptEditTextarea = null;
let saveTranscriptButton = null;
let cancelTranscriptEditButton = null;
let supplementPanel = null;
let supplementTextarea = null;
let saveSupplementButton = null;
let recordSupplementButton = null;
let supplementStatus = null;

function showScreen(screen) {
  screens.forEach(item => item.classList.remove("active"));
  screen.classList.add("active");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function getFreshSession() {
  let { data, error } = await supabaseClient.auth.getSession();

  if (error || !data.session) {
    return null;
  }

  const session = data.session;
  const expiresAtMs = Number(session.expires_at || 0) * 1000;
  const expiresSoon = expiresAtMs && expiresAtMs - Date.now() < 120000;

  if (expiresSoon) {
    const refreshed = await supabaseClient.auth.refreshSession();
    if (!refreshed.error && refreshed.data.session) {
      return refreshed.data.session;
    }
  }

  return session;
}

async function apiFetch(path, options = {}) {
  let session = await getFreshSession();

  if (!session) {
    showLogin();
    throw new Error("Deine Anmeldung ist abgelaufen. Bitte erneut anmelden.");
  }

  const doFetch = async activeSession => {
    const headers = new Headers(options.headers || {});
    headers.set("Authorization", `Bearer ${activeSession.access_token}`);

    return fetch(`${API}${path}`, {
      ...options,
      headers
    });
  };

  let response = await doFetch(session);

  // Bei langen KI-Vorgängen kann ein Access-Token inzwischen abgelaufen sein.
  // Deshalb bei 401 zuerst still erneuern und genau einmal wiederholen.
  // Wichtig: Wir melden den Benutzer NICHT sofort ab.
  if (response.status === 401) {
    const refreshed = await supabaseClient.auth.refreshSession();

    if (!refreshed.error && refreshed.data.session) {
      session = refreshed.data.session;
      response = await doFetch(session);
    }
  }

  if (response.status === 401) {
    showLogin();
    throw new Error("Die Anmeldung konnte nicht erneuert werden. Bitte erneut anmelden.");
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
  currentIdentityCandidateId = null;
  currentIdentityQuestion = false;
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
  currentAnalysisRunning = false;
  resetReviewCorrectionUI();
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
  const perfStart = performance.now();
  let uploadStartedAt = null;
  let transcribeStartedAt = null;
  let analyzeStartedAt = null;

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

    uploadStartedAt = performance.now();

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

    console.info(
      `[Roman] Audio-Upload: ${((performance.now() - uploadStartedAt) / 1000).toFixed(1)} s`
    );

    processingText.textContent =
      "Ich schreibe deine Worte auf …";

    transcribeStartedAt = performance.now();

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

    console.info(
      `[Roman] Transkription: ${((performance.now() - transcribeStartedAt) / 1000).toFixed(1)} s`
    );

    transcriptElement.textContent =
      transcribeData.transcript ||
      "(Kein Text erkannt.)";

    /*
     * Ab hier muss Roman nicht mehr auf dem Ladebildschirm warten:
     * Das Transkript ist bereits da und wird sofort gezeigt.
     * Die tiefere Einordnung läuft sichtbar weiter.
     */
    summaryElement.textContent =
      "Die Erinnerung wird noch eingeordnet …";

    confirmButton.disabled = true;
    confirmButton.textContent =
      "Einordnung läuft …";

    retryButton.disabled = true;
    discardButton.disabled = true;

    showScreen(reviewScreen);

    analyzeStartedAt = performance.now();
    currentAnalysisRunning = true;

    const analyzeResponse =
      await apiFetch(
        `/answer/${currentAnswerId}/analyze`,
        {
          method: "POST"
        }
      );

    const analyzeData =
      await analyzeResponse.json();

    currentAnalysisRunning = false;

    if (!analyzeResponse.ok) {
      throw new Error(
        analyzeData.detail ||
        "Erinnerung konnte nicht ausgewertet werden."
      );
    }

    console.info(
      `[Roman] Analyse: ${((performance.now() - analyzeStartedAt) / 1000).toFixed(1)} s`
    );

    summaryElement.textContent =
      analyzeData.memory?.summary ||
      "Keine Zusammenfassung vorhanden.";

    currentFollowUpQuestion =
      analyzeData.follow_up_question ||
      "";

    currentIdentityCandidateId =
      analyzeData.identity_candidates?.[0]?.id ||
      null;

    currentIdentityQuestion =
      Boolean(currentIdentityCandidateId);

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

    confirmButton.disabled = false;
    confirmButton.textContent =
      "So speichern";

    retryButton.disabled = false;
    discardButton.disabled = false;

    console.info(
      `[Roman] Gesamt bis Auswertung: ${((performance.now() - perfStart) / 1000).toFixed(1)} s`
    );
  } catch (error) {
    currentAnalysisRunning = false;
    console.error(error);

    /*
     * Falls das Transkript schon sichtbar ist, bleiben wir dort.
     * So geht die Aufnahme nicht optisch "verloren", nur weil die
     * nachgelagerte KI-Einordnung einmal scheitert.
     */
    if (
      currentAnswerId &&
      transcriptElement.textContent &&
      transcriptElement.textContent !== "(Kein Text erkannt.)"
    ) {
      summaryElement.textContent =
        "Die Einordnung konnte gerade nicht abgeschlossen werden. Die Aufnahme und das Transkript sind bereits gespeichert.";

      confirmButton.disabled = false;
      confirmButton.textContent =
        "So speichern";

      retryButton.disabled = false;
      discardButton.disabled = false;

      showScreen(reviewScreen);
      return;
    }

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

function startReviewCorrectionAudioFeedback(stream) {
  reviewCorrectionAudioContext =
    new (window.AudioContext || window.webkitAudioContext)();

  const source =
    reviewCorrectionAudioContext.createMediaStreamSource(stream);

  reviewCorrectionAnalyser =
    reviewCorrectionAudioContext.createAnalyser();

  reviewCorrectionAnalyser.fftSize = 256;
  reviewCorrectionAnalyser.smoothingTimeConstant = .82;

  source.connect(reviewCorrectionAnalyser);

  reviewCorrectionAnalyserData =
    new Uint8Array(
      reviewCorrectionAnalyser.frequencyBinCount
    );

  reviewCorrectionFeedback.classList.remove("hidden");
  reviewCorrectionTime.textContent = "00:00";
  reviewCorrectionRecordingStartedAt = Date.now();

  reviewCorrectionTimerInterval = setInterval(() => {
    const seconds = Math.floor(
      (Date.now() - reviewCorrectionRecordingStartedAt) / 1000
    );

    const minutes = Math.floor(seconds / 60);
    const rest = seconds % 60;

    reviewCorrectionTime.textContent =
      String(minutes).padStart(2, "0") +
      ":" +
      String(rest).padStart(2, "0");
  }, 500);

  drawReviewCorrectionAudioMeter();
}

function drawReviewCorrectionAudioMeter() {
  if (!reviewCorrectionAnalyser || !reviewCorrectionAudioMeter) return;

  reviewCorrectionAnalyser.getByteFrequencyData(
    reviewCorrectionAnalyserData
  );

  const ctx = reviewCorrectionAudioMeter.getContext("2d");
  const width = reviewCorrectionAudioMeter.width;
  const height = reviewCorrectionAudioMeter.height;

  ctx.clearRect(0, 0, width, height);

  const bars = 32;
  const step = Math.max(
    1,
    Math.floor(reviewCorrectionAnalyserData.length / bars)
  );
  const gap = 5;
  const barWidth =
    (width - gap * (bars - 1)) / bars;

  for (let i = 0; i < bars; i++) {
    const value =
      reviewCorrectionAnalyserData[i * step] / 255;

    const shaped = Math.pow(value, .75);
    const wave =
      .68 +
      .32 * Math.sin(Date.now() / 300 + i * .52);

    const barHeight = Math.max(
      4,
      shaped * height * .82 * wave
    );

    const x = i * (barWidth + gap);
    const y = (height - barHeight) / 2;
    const alpha = .24 + shaped * .76;

    const gradient = ctx.createLinearGradient(
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
        4
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

  reviewCorrectionMeterAnimationId =
    requestAnimationFrame(
      drawReviewCorrectionAudioMeter
    );
}

async function stopReviewCorrectionAudioFeedback() {
  if (reviewCorrectionMeterAnimationId) {
    cancelAnimationFrame(
      reviewCorrectionMeterAnimationId
    );
  }

  reviewCorrectionMeterAnimationId = null;
  reviewCorrectionAnalyser = null;

  if (reviewCorrectionTimerInterval) {
    clearInterval(reviewCorrectionTimerInterval);
  }

  reviewCorrectionTimerInterval = null;
  reviewCorrectionRecordingStartedAt = null;

  if (reviewCorrectionAudioContext) {
    try {
      await reviewCorrectionAudioContext.close();
    } catch (_) {}
  }

  reviewCorrectionAudioContext = null;

  if (reviewCorrectionAudioMeter) {
    const ctx = reviewCorrectionAudioMeter.getContext("2d");
    ctx.clearRect(
      0,
      0,
      reviewCorrectionAudioMeter.width,
      reviewCorrectionAudioMeter.height
    );
  }

  if (reviewCorrectionFeedback) {
    reviewCorrectionFeedback.classList.add("hidden");
  }
}

function resetReviewCorrectionUI() {
  stopReviewCorrectionAudioFeedback();
  reviewCorrectionProposedText = "";
  reviewCorrectionInstructionText = "";

  if (reviewCorrectionPreview) {
    reviewCorrectionPreview.classList.add("hidden");
  }

  if (reviewTranscriptEditPanel) {
    reviewTranscriptEditPanel.classList.add("hidden");
  }

  if (reviewCorrectionStatus) {
    reviewCorrectionStatus.textContent = "";
  }

  if (reviewCorrectionInstruction) {
    reviewCorrectionInstruction.textContent = "";
  }

  if (reviewCorrectionChanges) {
    reviewCorrectionChanges.innerHTML = "";
  }

  if (reviewCorrectionExplanation) {
    reviewCorrectionExplanation.textContent = "";
  }

  if (reviewCorrectionFullText) {
    reviewCorrectionFullText.textContent = "";
  }

  if (speakCorrectionButton) {
    speakCorrectionButton.textContent = "🎤 Korrektur sprechen";
    speakCorrectionButton.classList.remove("recording-inline");
    speakCorrectionButton.disabled = false;
  }
}

async function waitForCurrentAnalysis() {
  if (!currentAnalysisRunning) return;

  reviewCorrectionStatus.textContent =
    "Die laufende Einordnung wird kurz fertiggestellt …";

  while (currentAnalysisRunning) {
    await new Promise(resolve => setTimeout(resolve, 250));
  }
}

async function toggleReviewCorrectionRecording() {
  if (!currentAnswerId) {
    reviewCorrectionStatus.textContent =
      "Es gibt noch keine gespeicherte Aufnahme zum Korrigieren.";
    return;
  }

  if (
    reviewCorrectionRecorder &&
    reviewCorrectionRecorder.state !== "inactive"
  ) {
    reviewCorrectionRecorder.stop();
    return;
  }

  try {
    const format = selectRecordingFormat();

    if (!format) {
      throw new Error(
        "Dieses Gerät unterstützt die Sprachaufnahme leider nicht."
      );
    }

    reviewCorrectionMimeType = format.mime;
    reviewCorrectionExtension = format.extension;
    reviewCorrectionChunks = [];
    reviewCorrectionProposedText = "";
    reviewCorrectionInstructionText = "";

    reviewCorrectionPreview.classList.add("hidden");
    reviewTranscriptEditPanel.classList.add("hidden");

    reviewCorrectionStream =
      await navigator.mediaDevices.getUserMedia({ audio: true });

    reviewCorrectionRecorder = new MediaRecorder(
      reviewCorrectionStream,
      {
        mimeType: reviewCorrectionMimeType,
        audioBitsPerSecond: 128000
      }
    );

    reviewCorrectionRecorder.ondataavailable = event => {
      if (event.data && event.data.size > 0) {
        reviewCorrectionChunks.push(event.data);
      }
    };

    reviewCorrectionRecorder.onstop = uploadReviewCorrectionRecording;
    reviewCorrectionRecorder.start();
    startReviewCorrectionAudioFeedback(reviewCorrectionStream);

    speakCorrectionButton.textContent = "■ Aufnahme beenden";
    speakCorrectionButton.classList.add("recording-inline");
    reviewCorrectionStatus.textContent =
      "Sag zum Beispiel: „Ich meinte nicht er, sondern sie.“";
  } catch (error) {
    console.error(error);
    reviewCorrectionStatus.textContent = error.message;
  }
}

async function uploadReviewCorrectionRecording() {
  await stopReviewCorrectionAudioFeedback();

  if (reviewCorrectionStream) {
    reviewCorrectionStream.getTracks().forEach(track => track.stop());
  }

  speakCorrectionButton.textContent = "🎤 Korrektur sprechen";
  speakCorrectionButton.classList.remove("recording-inline");

  if (!reviewCorrectionChunks.length || !currentAnswerId) {
    reviewCorrectionStatus.textContent =
      "Es wurde keine Korrektur aufgenommen.";
    return;
  }

  const audioBlob = new Blob(
    reviewCorrectionChunks,
    { type: reviewCorrectionMimeType }
  );

  const formData = new FormData();
  formData.append(
    "audio",
    audioBlob,
    `korrektur.${reviewCorrectionExtension}`
  );

  speakCorrectionButton.disabled = true;
  editReviewTranscriptButton.disabled = true;
  reviewCorrectionStatus.textContent =
    "Ich prüfe deine Korrektur …";

  try {
    const response = await apiFetch(
      `/answer/${currentAnswerId}/correction/preview/audio`,
      {
        method: "POST",
        body: formData
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail ||
        "Die gesprochene Korrektur konnte nicht verarbeitet werden."
      );
    }

    reviewCorrectionInstructionText =
      data.instruction_transcript || "";
    reviewCorrectionProposedText =
      data.proposed_text || "";

    reviewCorrectionInstruction.textContent =
      reviewCorrectionInstructionText
        ? `Du hast gesagt: „${reviewCorrectionInstructionText}“`
        : "Gesprochene Korrektur";

    reviewCorrectionChanges.innerHTML = "";

    const changes = Array.isArray(data.changes)
      ? data.changes
      : [];

    if (data.changed && changes.length) {
      changes.forEach(change => {
        const row = document.createElement("div");
        row.className = "correction-change";

        const before = document.createElement("div");
        before.className = "correction-before";
        before.textContent = change.before || "—";

        const arrow = document.createElement("div");
        arrow.className = "correction-arrow";
        arrow.textContent = "→";

        const after = document.createElement("div");
        after.className = "correction-after";
        after.textContent = change.after || "—";

        row.append(before, arrow, after);
        reviewCorrectionChanges.appendChild(row);
      });
    } else if (data.changed) {
      const row = document.createElement("div");
      row.className = "correction-explanation";
      row.textContent =
        "Die gewünschte Änderung wurde im Text erkannt.";
      reviewCorrectionChanges.appendChild(row);
    } else {
      const row = document.createElement("div");
      row.className = "correction-explanation";
      row.textContent =
        "Ich konnte keine eindeutige Änderung erkennen.";
      reviewCorrectionChanges.appendChild(row);
    }

    reviewCorrectionExplanation.textContent =
      data.explanation || "";

    reviewCorrectionFullText.textContent =
      data.proposed_text || transcriptElement.textContent || "";

    applyReviewCorrectionButton.disabled = !data.changed;
    reviewCorrectionPreview.classList.remove("hidden");
    reviewCorrectionStatus.textContent =
      data.changed
        ? "Bitte kurz prüfen und dann übernehmen."
        : "Bitte die Korrektur noch einmal sprechen oder den Text bearbeiten.";
  } catch (error) {
    console.error(error);
    reviewCorrectionStatus.textContent = error.message;
  } finally {
    speakCorrectionButton.disabled = false;
    editReviewTranscriptButton.disabled = false;
  }
}

function openReviewTranscriptEditor() {
  if (!currentAnswerId) return;

  reviewCorrectionPreview.classList.add("hidden");
  reviewTranscriptTextarea.value = transcriptElement.textContent || "";
  reviewTranscriptEditPanel.classList.remove("hidden");
  reviewCorrectionStatus.textContent = "";
  reviewTranscriptTextarea.focus();
}

async function saveCurrentReviewTranscript(
  newText,
  changeNote
) {
  const text = (newText || "").trim();

  if (!currentAnswerId || !text) {
    throw new Error("Der korrigierte Text darf nicht leer sein.");
  }

  await waitForCurrentAnalysis();

  const response = await apiFetch(
    `/answer/${currentAnswerId}/transcript`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        text,
        change_note: changeNote || "Korrektur"
      })
    }
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(
      data.detail ||
      "Die Korrektur konnte nicht gespeichert werden."
    );
  }

  transcriptElement.textContent = text;
  summaryElement.textContent =
    "Die korrigierte Erinnerung wird neu eingeordnet …";

  confirmButton.disabled = true;
  confirmButton.textContent = "Einordnung läuft …";
  retryButton.disabled = true;
  discardButton.disabled = true;

  currentAnalysisRunning = true;

  try {
    const analyzeResponse = await apiFetch(
      `/answer/${currentAnswerId}/analyze`,
      { method: "POST" }
    );

    const analyzeData = await analyzeResponse.json();

    if (!analyzeResponse.ok) {
      throw new Error(
        analyzeData.detail ||
        "Die korrigierte Erinnerung konnte nicht neu eingeordnet werden."
      );
    }

    summaryElement.textContent =
      analyzeData.memory?.summary ||
      "Keine Zusammenfassung vorhanden.";

    currentFollowUpQuestion =
      analyzeData.follow_up_question || "";
    currentIdentityCandidateId =
      analyzeData.identity_candidates?.[0]?.id || null;
    currentIdentityQuestion = Boolean(currentIdentityCandidateId);
    currentPrivacySignal = analyzeData.privacy_signal === true;
    currentPrivacyReason = analyzeData.privacy_reason || "";
    currentTimelineYear = analyzeData.timeline_year;
    currentTimelineLabel = analyzeData.timeline_label || "";
    currentTimelineConfidence =
      analyzeData.timeline_confidence || "unknown";
  } finally {
    currentAnalysisRunning = false;
    confirmButton.disabled = false;
    confirmButton.textContent = "So speichern";
    retryButton.disabled = false;
    discardButton.disabled = false;
  }
}

async function applyReviewCorrection() {
  if (!reviewCorrectionProposedText) return;

  applyReviewCorrectionButton.disabled = true;
  repeatReviewCorrectionButton.disabled = true;
  cancelReviewCorrectionButton.disabled = true;
  reviewCorrectionStatus.textContent =
    "Korrektur wird übernommen …";

  try {
    await saveCurrentReviewTranscript(
      reviewCorrectionProposedText,
      reviewCorrectionInstructionText
        ? `Gesprochene Korrektur: ${reviewCorrectionInstructionText}`
        : "Gesprochene Korrektur"
    );

    reviewCorrectionPreview.classList.add("hidden");
    reviewCorrectionStatus.textContent = "✓ Korrektur übernommen";
    reviewCorrectionProposedText = "";
    reviewCorrectionInstructionText = "";
  } catch (error) {
    console.error(error);
    reviewCorrectionStatus.textContent = error.message;
  } finally {
    applyReviewCorrectionButton.disabled = false;
    repeatReviewCorrectionButton.disabled = false;
    cancelReviewCorrectionButton.disabled = false;
  }
}

async function saveReviewTranscriptEdit() {
  const text = reviewTranscriptTextarea.value.trim();

  if (!text) {
    reviewCorrectionStatus.textContent =
      "Der korrigierte Text darf nicht leer sein.";
    return;
  }

  saveReviewTranscriptButton.disabled = true;
  reviewCorrectionStatus.textContent =
    "Korrektur wird gespeichert …";

  try {
    await saveCurrentReviewTranscript(
      text,
      "Text direkt nach der Transkription korrigiert"
    );

    reviewTranscriptEditPanel.classList.add("hidden");
    reviewCorrectionStatus.textContent = "✓ Korrektur übernommen";
  } catch (error) {
    console.error(error);
    reviewCorrectionStatus.textContent = error.message;
  } finally {
    saveReviewTranscriptButton.disabled = false;
  }
}

function confirmMemory() {
  try {
    if (!currentAnswerId) {
      throw new Error(
        "Die Erinnerung wurde noch nicht vollständig gespeichert."
      );
    }

    privacyContainer.innerHTML = "";
    followUpBox.classList.add("hidden");

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

      if (
        currentIdentityQuestion &&
        currentIdentityCandidateId
      ) {
        followUpButton.textContent =
          "Ja, das ist dieselbe Person";

        skipFollowUpButton.textContent =
          "Nein, jemand anderes";

        followUpButton.onclick =
          () => resolveCurrentIdentity(true);

        skipFollowUpButton.onclick =
          () => resolveCurrentIdentity(false);
      } else {
        followUpButton.textContent =
          "Ja, erzähl weiter";

        skipFollowUpButton.textContent =
          "Lieber etwas Neues";

        followUpButton.onclick =
          activateFollowUp;

        skipFollowUpButton.onclick =
          showHome;
      }

      followUpBox.classList.remove("hidden");
    }

    showScreen(savedScreen);

    window.scrollTo({
      top: 0,
      behavior: "auto"
    });

  } catch (error) {
    console.error(
      "CONFIRM MEMORY ERROR:",
      error
    );

    alert(
      "Die Erinnerung konnte nicht abgeschlossen werden: " +
      error.message
    );
  }
}


async function resolveCurrentIdentity(samePerson) {
  if (!currentIdentityCandidateId) return;

  const candidateId = currentIdentityCandidateId;
  followUpButton.disabled = true;
  skipFollowUpButton.disabled = true;

  try {
    const response = await apiFetch(
      `/person-identity/${candidateId}/resolve`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          same_person: samePerson
        })
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail ||
        "Die Person konnte nicht zugeordnet werden."
      );
    }

    currentIdentityCandidateId = null;
    currentIdentityQuestion = false;
    currentFollowUpQuestion = "";
    followUpBox.classList.add("hidden");

    savedMessage.textContent = samePerson
      ? "Gespeichert · die Erinnerungen zu dieser Person sind jetzt miteinander verbunden."
      : "Gespeichert · diese Person bleibt als eigene Person erhalten.";
  } catch (error) {
    console.error(error);
    savedMessage.textContent = error.message;
  } finally {
    followUpButton.disabled = false;
    skipFollowUpButton.disabled = false;
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


function ensureMemoryToolsUI() {
  if (memoryToolsContainer) return;

  memoryToolsContainer = document.createElement("section");
  memoryToolsContainer.className = "memory-tools";

  memoryToolsContainer.innerHTML = `
    <div class="memory-tools-heading">
      <div class="eyebrow">Erinnerung verfeinern</div>
      <h3>Etwas korrigieren oder ergänzen</h3>
      <p>
        Das Original bleibt immer erhalten. Änderungen werden als neue Version
        oder als Ergänzung gespeichert.
      </p>
    </div>

    <div class="memory-tool-actions">
      <button id="editTranscriptButton" class="outline-button">Text korrigieren</button>
      <button id="openSupplementButton" class="outline-button">Etwas ergänzen</button>
      <button id="playOriginalAudioButton" class="outline-button hidden">Originalaufnahme anhören</button>
      <button id="downloadOriginalAudioButton" class="outline-button hidden">Originalaufnahme speichern</button>
    </div>
    <audio id="originalAudioPlayer" class="original-audio-player hidden" controls preload="none"></audio>

    <div id="transcriptEditPanel" class="memory-tool-panel hidden">
      <label for="transcriptEditTextarea">Korrigierte Fassung</label>
      <textarea id="transcriptEditTextarea" rows="9"></textarea>
      <div class="memory-tool-button-row">
        <button id="saveTranscriptButton" class="gold-button">Korrektur speichern</button>
        <button id="cancelTranscriptEditButton" class="text-button">Abbrechen</button>
      </div>
    </div>

    <div id="supplementPanel" class="memory-tool-panel hidden">
      <label for="supplementTextarea">Was möchtest du präzisieren oder ergänzen?</label>
      <textarea id="supplementTextarea" rows="5" placeholder="Zum Beispiel: Mir ist noch eingefallen, dass …"></textarea>
      <div class="memory-tool-button-row">
        <button id="saveSupplementButton" class="gold-button">Ergänzung speichern</button>
        <button id="recordSupplementButton" class="outline-button">Ergänzung sprechen</button>
      </div>
      <div id="supplementStatus" class="memory-tool-status"></div>
    </div>
  `;

  timelineEditor.parentNode.insertBefore(
    memoryToolsContainer,
    timelineEditor
  );

  editTranscriptButton = document.getElementById("editTranscriptButton");
  const openSupplementButton = document.getElementById("openSupplementButton");
  const playOriginalAudioButton = document.getElementById("playOriginalAudioButton");
  const downloadOriginalAudioButton = document.getElementById("downloadOriginalAudioButton");
  const originalAudioPlayer = document.getElementById("originalAudioPlayer");
  transcriptEditPanel = document.getElementById("transcriptEditPanel");
  transcriptEditTextarea = document.getElementById("transcriptEditTextarea");
  saveTranscriptButton = document.getElementById("saveTranscriptButton");
  cancelTranscriptEditButton = document.getElementById("cancelTranscriptEditButton");
  supplementPanel = document.getElementById("supplementPanel");
  supplementTextarea = document.getElementById("supplementTextarea");
  saveSupplementButton = document.getElementById("saveSupplementButton");
  recordSupplementButton = document.getElementById("recordSupplementButton");
  supplementStatus = document.getElementById("supplementStatus");

  editTranscriptButton.onclick = () => {
    const item = archiveItems.find(row => row.answer_id === openedMemoryId);
    if (!item) return;

    transcriptEditTextarea.value = item.transcript || "";
    transcriptEditPanel.classList.remove("hidden");
    supplementPanel.classList.add("hidden");
    transcriptEditTextarea.focus();
  };

  openSupplementButton.onclick = () => {
    supplementPanel.classList.toggle("hidden");
    transcriptEditPanel.classList.add("hidden");
    supplementStatus.textContent = "";

    if (!supplementPanel.classList.contains("hidden")) {
      supplementTextarea.focus();
    }
  };

  cancelTranscriptEditButton.onclick = () => {
    transcriptEditPanel.classList.add("hidden");
  };

  playOriginalAudioButton.onclick = async () => {
    if (!openedMemoryId) return;
    try {
      playOriginalAudioButton.disabled = true;
      playOriginalAudioButton.textContent = "Aufnahme wird geladen …";
      const response = await apiFetch(`/answer/${openedMemoryId}/audio`);
      if (!response.ok) {
        let message = "Originalaufnahme konnte nicht geladen werden.";
        try {
          const data = await response.json();
          message = data.detail || message;
        } catch (_) {}
        throw new Error(message);
      }
      const blob = await response.blob();
      if (currentAudioObjectUrl) URL.revokeObjectURL(currentAudioObjectUrl);
      currentAudioObjectUrl = URL.createObjectURL(blob);
      originalAudioPlayer.src = currentAudioObjectUrl;
      originalAudioPlayer.classList.remove("hidden");
      await originalAudioPlayer.play().catch(() => {});
    } catch (error) {
      console.error(error);
      alert(error.message);
    } finally {
      playOriginalAudioButton.disabled = false;
      playOriginalAudioButton.textContent = "Originalaufnahme anhören";
    }
  };

  downloadOriginalAudioButton.onclick = async () => {
    if (!openedMemoryId) return;
    try {
      await downloadFromApi(
        `/answer/${openedMemoryId}/audio`,
        `roman-original-${openedMemoryId}.webm`
      );
    } catch (error) {
      console.error(error);
      alert(error.message);
    }
  };

  saveTranscriptButton.onclick = saveTranscriptCorrection;
  saveSupplementButton.onclick = saveSupplementText;
  recordSupplementButton.onclick = toggleSupplementRecording;
}

async function reanalyzeOpenedMemory() {
  if (!openedMemoryId) return;

  const response = await apiFetch(
    `/answer/${openedMemoryId}/analyze`,
    { method: "POST" }
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(
      data.detail ||
      "Die Erinnerung konnte nicht neu ausgewertet werden."
    );
  }

  await loadArchive();
}

async function saveTranscriptCorrection() {
  if (!openedMemoryId) return;

  const text = transcriptEditTextarea.value.trim();

  if (!text) {
    alert("Der korrigierte Text darf nicht leer sein.");
    return;
  }

  saveTranscriptButton.disabled = true;
  saveTranscriptButton.textContent = "Wird gespeichert …";

  try {
    const response = await apiFetch(
      `/answer/${openedMemoryId}/transcript`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          text,
          change_note: "Von Roman oder Familie korrigiert"
        })
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail ||
        "Die Korrektur konnte nicht gespeichert werden."
      );
    }

    saveTranscriptButton.textContent = "Wird neu eingeordnet …";
    await reanalyzeOpenedMemory();

    const updated = archiveItems.find(row => row.answer_id === openedMemoryId);

    if (updated) {
      dialogTranscript.textContent = updated.transcript || "";
      dialogSummary.textContent = getMemorySummary(updated);
    }

    transcriptEditPanel.classList.add("hidden");
    saveTranscriptButton.textContent = "✓ Gespeichert";

    setTimeout(() => {
      saveTranscriptButton.textContent = "Korrektur speichern";
    }, 1600);
  } catch (error) {
    console.error(error);
    alert(error.message);
    saveTranscriptButton.textContent = "Korrektur speichern";
  } finally {
    saveTranscriptButton.disabled = false;
  }
}

async function saveSupplementText() {
  if (!openedMemoryId) return;

  const transcript = supplementTextarea.value.trim();

  if (!transcript) {
    supplementStatus.textContent = "Bitte erst eine Ergänzung eingeben.";
    return;
  }

  saveSupplementButton.disabled = true;
  supplementStatus.textContent = "Ergänzung wird gespeichert …";

  try {
    const response = await apiFetch(
      `/answer/${openedMemoryId}/supplement`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          transcript,
          supplement_type: "clarification"
        })
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail ||
        "Die Ergänzung konnte nicht gespeichert werden."
      );
    }

    supplementStatus.textContent = "Die Ergänzung wird neu eingeordnet …";
    await reanalyzeOpenedMemory();
    supplementTextarea.value = "";
    supplementStatus.textContent = "✓ Ergänzung gespeichert";

    const updated = archiveItems.find(row => row.answer_id === openedMemoryId);
    if (updated) {
      dialogSummary.textContent = getMemorySummary(updated);
    }
  } catch (error) {
    console.error(error);
    supplementStatus.textContent = error.message;
  } finally {
    saveSupplementButton.disabled = false;
  }
}

async function toggleSupplementRecording() {
  if (!openedMemoryId) return;

  if (supplementRecorder && supplementRecorder.state !== "inactive") {
    supplementRecorder.stop();
    return;
  }

  try {
    const format = selectRecordingFormat();

    if (!format) {
      throw new Error("Dieses Gerät unterstützt die Sprachaufnahme leider nicht.");
    }

    supplementMimeType = format.mime;
    supplementExtension = format.extension;
    supplementChunks = [];

    supplementStream = await navigator.mediaDevices.getUserMedia({ audio: true });

    supplementRecorder = new MediaRecorder(
      supplementStream,
      {
        mimeType: supplementMimeType,
        audioBitsPerSecond: 128000
      }
    );

    supplementRecorder.ondataavailable = event => {
      if (event.data && event.data.size > 0) {
        supplementChunks.push(event.data);
      }
    };

    supplementRecorder.onstop = uploadSupplementRecording;
    supplementRecorder.start();

    recordSupplementButton.textContent = "Aufnahme beenden";
    recordSupplementButton.classList.add("recording-inline");
    supplementStatus.textContent = "Ich höre dir zu …";
  } catch (error) {
    console.error(error);
    supplementStatus.textContent = error.message;
  }
}

async function uploadSupplementRecording() {
  if (supplementStream) {
    supplementStream.getTracks().forEach(track => track.stop());
  }

  recordSupplementButton.textContent = "Ergänzung sprechen";
  recordSupplementButton.classList.remove("recording-inline");

  if (!supplementChunks.length) {
    supplementStatus.textContent = "Es wurde keine Sprache aufgenommen.";
    return;
  }

  const answerId = openedMemoryId;

  if (!answerId) return;

  try {
    supplementStatus.textContent = "Die Ergänzung wird transkribiert …";
    recordSupplementButton.disabled = true;

    const blob = new Blob(
      supplementChunks,
      {
        type: supplementRecorder?.mimeType || supplementMimeType
      }
    );

    const formData = new FormData();
    formData.append("supplement_type", "clarification");
    formData.append(
      "audio",
      blob,
      `ergaenzung.${supplementExtension}`
    );

    const response = await apiFetch(
      `/answer/${answerId}/supplement/audio`,
      {
        method: "POST",
        body: formData
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail ||
        "Die gesprochene Ergänzung konnte nicht gespeichert werden."
      );
    }

    supplementTextarea.value = data.transcript || "";
    supplementStatus.textContent = "Die Ergänzung wird neu eingeordnet …";
    await reanalyzeOpenedMemory();
    supplementStatus.textContent = "✓ Gesprochene Ergänzung gespeichert";

    const updated = archiveItems.find(row => row.answer_id === answerId);
    if (updated) {
      dialogSummary.textContent = getMemorySummary(updated);
    }
  } catch (error) {
    console.error(error);
    supplementStatus.textContent = error.message;
  } finally {
    recordSupplementButton.disabled = false;
    supplementChunks = [];
    supplementRecorder = null;
    supplementStream = null;
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

  ensureMemoryToolsUI();

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

  memoryToolsContainer.style.display =
    currentRole === "reader"
      ? "none"
      : "block";

  const originalAudioButton = document.getElementById("downloadOriginalAudioButton");
  const playOriginalAudioButton = document.getElementById("playOriginalAudioButton");
  const originalAudioPlayer = document.getElementById("originalAudioPlayer");
  if (originalAudioButton) originalAudioButton.classList.toggle("hidden", !item.has_audio);
  if (playOriginalAudioButton) playOriginalAudioButton.classList.toggle("hidden", !item.has_audio);
  if (originalAudioPlayer) {
    originalAudioPlayer.pause();
    originalAudioPlayer.removeAttribute("src");
    originalAudioPlayer.classList.add("hidden");
  }

  transcriptEditPanel.classList.add("hidden");
  supplementPanel.classList.add("hidden");
  supplementStatus.textContent = "";

  memoryDialog.style.display =
    "block";

  document.body.style.overflow =
    "hidden";
}

function closeMemory() {
  if (supplementRecorder && supplementRecorder.state !== "inactive") {
    supplementRecorder.stop();
  }

  memoryDialog.style.display =
    "none";

  document.body.style.overflow =
    "";

  if (currentAudioObjectUrl) {
    URL.revokeObjectURL(currentAudioObjectUrl);
    currentAudioObjectUrl = null;
  }

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


let memoirWorkingTimer = null;
let memoirWorkingStartedAt = 0;
let memoirWorkingStageIndex = 0;
let memoirWorkingStages = [];

function formatWorkingElapsed(seconds) {
  if (seconds < 10) return "Seit wenigen Sekunden in Arbeit …";
  if (seconds < 60) return `Seit ${seconds} Sekunden in Arbeit …`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `Seit ${minutes} Min. ${String(rest).padStart(2, "0")} Sek. in Arbeit …`;
}

function startMemoirWorking(title, stages) {
  if (memoirWorkingTimer) {
    clearInterval(memoirWorkingTimer);
  }
  memoirWorkingTitle.textContent = title;
  memoirWorkingStages = stages && stages.length ? stages : ["Die Datei wird vorbereitet …"];
  memoirWorkingStageIndex = 0;
  memoirWorkingDetail.textContent = memoirWorkingStages[0];
  memoirWorkingStartedAt = Date.now();
  memoirWorkingElapsed.textContent = "Seit wenigen Sekunden in Arbeit …";
  memoirWorking.classList.remove("hidden");
  memoirWorking.scrollIntoView({ behavior: "smooth", block: "center" });

  memoirWorkingTimer = setInterval(() => {
    const elapsed = Math.max(0, Math.floor((Date.now() - memoirWorkingStartedAt) / 1000));
    memoirWorkingElapsed.textContent = formatWorkingElapsed(elapsed);

    // Diese Texte sind bewusst nur Tätigkeits-Feedback, keine behaupteten Server-Prozentwerte.
    const nextStage = Math.min(
      memoirWorkingStages.length - 1,
      Math.floor(elapsed / 8)
    );
    if (nextStage !== memoirWorkingStageIndex) {
      memoirWorkingStageIndex = nextStage;
      memoirWorkingDetail.textContent = memoirWorkingStages[nextStage];
    }
  }, 1000);
}

function stopMemoirWorking() {
  if (memoirWorkingTimer) {
    clearInterval(memoirWorkingTimer);
    memoirWorkingTimer = null;
  }
  memoirWorking.classList.add("hidden");
}

async function loadMemoirStats() {
  memoirStats.textContent = "Erinnerungen werden gezählt …";
  try {
    const response = await apiFetch(
      `/memoir/stats?profile_id=${currentProfileId}`
    );
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Die Erinnerungen konnten nicht gezählt werden.");
    }
    memoirStats.innerHTML = `
      <strong>${data.total}</strong> Erinnerungen insgesamt<br>
      <span>${data.family_only} nur für die Familie · ${data.shareable} für die Version zum Teilen</span>
    `;
  } catch (error) {
    console.error(error);
    memoirStats.textContent = error.message;
  }
}

async function showSettings() {
  stopMemoirWorking();
  currentMemoir = null;
  memoirPreview.classList.add("hidden");
  memoirStatus.textContent = "";
  archiveBackupStatus.textContent = "";
  showScreen(settingsScreen);
  await loadMemoirStats();
}

function renderMemoirPreview(memoir) {
  memoirPreviewTitle.textContent = memoir.title || "Romans Erinnerungen";
  const familyText = memoir.mode === "complete"
    ? "Familienfassung · enthält auch familieninterne Erinnerungen"
    : "Version zum Teilen · nur freigegebene Erinnerungen";
  memoirPreviewMeta.textContent = `${familyText} · ${memoir.memory_count || 0} Erinnerungen`;
  memoirPreviewIntro.textContent = memoir.introduction || "";
  memoirChapterList.innerHTML = "";

  for (const chapter of memoir.chapters || []) {
    const card = document.createElement("article");
    card.className = "memoir-chapter";
    const text = String(chapter.text || "").trim();
    const excerpt = text.length > 330 ? text.slice(0, 330) + " …" : text;
    card.innerHTML = `
      <div class="memoir-chapter-title">${escapeHtml(chapter.title || "Kapitel")}</div>
      ${chapter.period ? `<div class="memoir-chapter-period">${escapeHtml(chapter.period)}</div>` : ""}
      <div class="memoir-chapter-excerpt">${escapeHtml(excerpt)}</div>
    `;
    memoirChapterList.appendChild(card);
  }

  memoirPreviewEpilogue.textContent = memoir.epilogue || "";
  memoirPreview.classList.remove("hidden");
  memoirPreview.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function generateMemoir(mode) {
  const complete = mode === "complete";
  const button = complete ? generateCompleteMemoirButton : generateShareMemoirButton;
  const otherButton = complete ? generateShareMemoirButton : generateCompleteMemoirButton;
  button.disabled = true;
  otherButton.disabled = true;
  memoirPdfButton.disabled = true;
  memoirDocxButton.disabled = true;
  memoirPreview.classList.add("hidden");
  currentMemoir = null;
  memoirStatus.textContent = "";

  startMemoirWorking(
    complete
      ? "Ich schreibe die komplette Familienfassung …"
      : "Ich schreibe die Version zum Teilen …",
    [
      "Erinnerungen werden gesammelt und geprüft …",
      "Zeiten, Orte und Zusammenhänge werden geordnet …",
      "Eine sinnvolle Kapitelstruktur wird aufgebaut …",
      "Die Kapitel werden aus Romans Erinnerungen geschrieben …",
      "Wiederholungen werden geglättet und Übergänge geprüft …",
      "Das Buch wird für die Vorschau fertiggestellt …"
    ]
  );

  try {
    const response = await apiFetch("/memoir/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id: currentProfileId, mode })
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Das Buch konnte nicht erstellt werden.");
    }
    currentMemoir = data;
    stopMemoirWorking();
    memoirStatus.textContent = "✓ Buchvorschau ist fertig.";
    renderMemoirPreview(data);
  } catch (error) {
    console.error(error);
    stopMemoirWorking();
    memoirStatus.textContent = `Fehler: ${error.message}`;
  } finally {
    button.disabled = false;
    otherButton.disabled = false;
    memoirPdfButton.disabled = false;
    memoirDocxButton.disabled = false;
  }
}

function filenameFromDisposition(response, fallback) {
  const value = response.headers.get("Content-Disposition") || "";
  const match = value.match(/filename="?([^";]+)"?/i);
  return match ? match[1] : fallback;
}

async function saveBlobResponse(response, fallbackFilename) {
  if (!response.ok) {
    let message = "Download fehlgeschlagen.";
    try {
      const data = await response.json();
      message = data.detail || message;
    } catch (_) {}
    throw new Error(message);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filenameFromDisposition(response, fallbackFilename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}

async function downloadFromApi(path, fallbackFilename, options = {}) {
  const response = await apiFetch(path, options);
  await saveBlobResponse(response, fallbackFilename);
}

async function exportMemoir(format) {
  if (!currentMemoir) {
    memoirStatus.textContent = "Bitte zuerst eine Buchvorschau erstellen.";
    return;
  }
  const button = format === "pdf" ? memoirPdfButton : memoirDocxButton;
  memoirPdfButton.disabled = true;
  memoirDocxButton.disabled = true;
  memoirStatus.textContent = "";

  startMemoirWorking(
    format === "pdf" ? "Ich setze die PDF-Datei …" : "Ich erstelle die Word-Datei …",
    format === "pdf"
      ? ["Buchseiten werden gesetzt …", "Kapitel und Seitenumbrüche werden geprüft …", "Die druckbare PDF-Datei wird fertiggestellt …"]
      : ["Kapitel werden in das Word-Dokument übertragen …", "Überschriften und Absätze werden formatiert …", "Die bearbeitbare Word-Datei wird fertiggestellt …"]
  );

  try {
    const response = await apiFetch(`/memoir/export/${format}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id: currentProfileId, memoir: currentMemoir })
    });
    await saveBlobResponse(
      response,
      format === "pdf" ? "romans-erinnerungen.pdf" : "romans-erinnerungen.docx"
    );
    stopMemoirWorking();
    memoirStatus.textContent = "✓ Datei wurde erstellt und der Download gestartet.";
  } catch (error) {
    console.error(error);
    stopMemoirWorking();
    memoirStatus.textContent = `Fehler: ${error.message}`;
  } finally {
    memoirPdfButton.disabled = false;
    memoirDocxButton.disabled = false;
  }
}

async function backupArchive() {
  archiveBackupButton.disabled = true;
  const oldText = archiveBackupButton.textContent;
  archiveBackupButton.textContent = "Sicherung wird erstellt …";
  archiveBackupStatus.textContent = "Originalaufnahmen werden mit eingepackt. Das kann etwas dauern …";
  try {
    await downloadFromApi(
      `/export/archive?profile_id=${currentProfileId}`,
      "romans-archiv.zip"
    );
    archiveBackupStatus.textContent = "✓ Archiv-Sicherung ist fertig.";
  } catch (error) {
    console.error(error);
    archiveBackupStatus.textContent = error.message;
  } finally {
    archiveBackupButton.disabled = false;
    archiveBackupButton.textContent = oldText;
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
settingsButton.onclick = showSettings;
settingsBackButton.onclick = showHome;
generateCompleteMemoirButton.onclick = () => generateMemoir("complete");
generateShareMemoirButton.onclick = () => generateMemoir("share");
memoirPdfButton.onclick = () => exportMemoir("pdf");
memoirDocxButton.onclick = () => exportMemoir("docx");
archiveBackupButton.onclick = backupArchive;

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

speakCorrectionButton.onclick = toggleReviewCorrectionRecording;
editReviewTranscriptButton.onclick = openReviewTranscriptEditor;
applyReviewCorrectionButton.onclick = applyReviewCorrection;
repeatReviewCorrectionButton.onclick = async () => {
  reviewCorrectionPreview.classList.add("hidden");
  await toggleReviewCorrectionRecording();
};
cancelReviewCorrectionButton.onclick = () => {
  reviewCorrectionPreview.classList.add("hidden");
  reviewCorrectionStatus.textContent = "";
};
saveReviewTranscriptButton.onclick = saveReviewTranscriptEdit;
cancelReviewTranscriptButton.onclick = () => {
  reviewTranscriptEditPanel.classList.add("hidden");
  reviewCorrectionStatus.textContent = "";
};

confirmButton.addEventListener(
  "click",
  event => {
    event.preventDefault();
    confirmMemory();
  }
);

retryButton.onclick =
  retryRecording;

discardButton.onclick =
  discardMemory;

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

// ---------------------------------------------------------
// PWA / INSTALLIERBARE APP
// ---------------------------------------------------------
if ("serviceWorker" in navigator) {
  window.addEventListener("load", async () => {
    try {
      const registration = await navigator.serviceWorker.register("/sw.js");
      console.log("PWA Service Worker aktiv:", registration.scope);
    } catch (error) {
      console.error("PWA Service Worker konnte nicht registriert werden:", error);
    }
  });
}

window.addEventListener("appinstalled", () => {
  console.log("Romans Erinnerungen wurde als App installiert.");
});
