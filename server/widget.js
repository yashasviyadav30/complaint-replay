/* Complaint Replay widget: one <script> tag on any site.
 *   <script src="https://YOUR-SERVER/widget.js" data-project="crp_..." defer></script>
 * Sends spoken complaints ("Report a problem") and silent ones (rage clicks, JS errors,
 * failed or very slow requests), each with the user's real conditions.
 * Never sends what the user typed into the page's fields: only button/link names.
 * Speaks the user's language (17 built in, right-to-left aware) and later tells them what happened.
 * Users who'd rather talk can speak the complaint: the browser's own speech service writes it into the box
 * (in Chrome that service is Google's), and they check it before sending. Nothing is recorded here.
 */
(() => {
  const script = document.currentScript;
  const PROJECT = (script && script.dataset.project) || "demo";
  const ENDPOINT = new URL("/api/v1/reports", script.src).href;
  const origFetch = window.fetch.bind(window); // the widget's own calls are never watched
  const SLOW_MS = 8000;
  const RAGE_CLICKS = 3, RAGE_WINDOW_MS = 1000, RAGE_RADIUS_PX = 30;
  const STORE_KEY = "crp-reports";
  const breadcrumbs = [];
  const sentSilent = new Set();

  // UI text. Machine-assisted translations: native speakers, please send corrections.
  const T = {
    en: ["Report a problem", "What went wrong?", "Tell us in your own words…", "Send", "Thanks, we're on it", "Close",
         "Your last report", { received: "Received", checking: "We're trying it the way you did", found: "We found the problem", fixing: "A fix is being made", fixed: "Fixed. It will reach you with the next update", not_reproduced: "We couldn't make it happen yet. The team will look", watch: "Watch it working now", speak: "Speak instead" }],
    hi: ["समस्या बताएँ", "क्या गड़बड़ हुई?", "अपने शब्दों में बताइए", "भेजें", "धन्यवाद, हम देख रहे हैं", "बंद करें",
         "आपकी पिछली शिकायत", { received: "मिल गई", checking: "हम इसे आपकी तरह आज़मा रहे हैं", found: "हमें समस्या मिल गई", fixing: "इसे ठीक किया जा रहा है", fixed: "ठीक हो गया। अगले अपडेट में आप तक पहुँचेगा", not_reproduced: "अभी तक दोहरा नहीं पाए। टीम देखेगी", watch: "अब इसे ठीक चलते हुए देखें", speak: "बोलकर बताएँ" }],
    ar: ["الإبلاغ عن مشكلة", "ما الذي حدث؟", "أخبرنا بكلماتك", "إرسال", "شكرًا، نحن نعمل على ذلك", "إغلاق",
         "بلاغك الأخير", { received: "تم الاستلام", checking: "نجرّبها كما فعلت", found: "وجدنا المشكلة", fixing: "يجري إصلاحها", fixed: "تم الإصلاح. سيصلك مع التحديث القادم", not_reproduced: "لم نتمكن من تكرارها بعد. سيتابع الفريق", watch: "شاهده وهو يعمل الآن", speak: "تحدّث بدلًا من الكتابة" }],
    ur: ["مسئلہ بتائیں", "کیا خرابی ہوئی؟", "اپنے الفاظ میں بتائیں", "بھیجیں", "شکریہ، ہم دیکھ رہے ہیں", "بند کریں",
         "آپ کی پچھلی شکایت", { received: "موصول ہو گئی", checking: "ہم اسے آپ کی طرح آزما رہے ہیں", found: "ہمیں مسئلہ مل گیا", fixing: "اسے ٹھیک کیا جا رہا ہے", fixed: "ٹھیک ہو گیا۔ اگلی اپڈیٹ میں آپ تک پہنچے گا", not_reproduced: "ابھی دہرا نہیں سکے۔ ٹیم دیکھے گی", watch: "اب اسے ٹھیک چلتا دیکھیں", speak: "بول کر بتائیں" }],
    bn: ["সমস্যা জানান", "কী সমস্যা হয়েছে?", "নিজের ভাষায় লিখুন", "পাঠান", "ধন্যবাদ, আমরা দেখছি", "বন্ধ করুন",
         "আপনার শেষ অভিযোগ", { received: "পেয়েছি", checking: "আপনার মতো করে চেষ্টা করছি", found: "সমস্যাটি পেয়েছি", fixing: "ঠিক করা হচ্ছে", fixed: "ঠিক হয়েছে। পরের আপডেটে পাবেন", not_reproduced: "এখনও ঘটাতে পারিনি। টিম দেখবে", watch: "এখন এটি ঠিকভাবে চলতে দেখুন", speak: "বলে জানান" }],
    ta: ["சிக்கலைத் தெரிவிக்க", "என்ன தவறு நடந்தது?", "உங்கள் சொற்களில் சொல்லுங்கள்", "அனுப்பு", "நன்றி, கவனிக்கிறோம்", "மூடு",
         "உங்கள் கடைசி புகார்", { received: "பெறப்பட்டது", checking: "நீங்கள் செய்தது போல் முயல்கிறோம்", found: "சிக்கலைக் கண்டோம்", fixing: "சரிசெய்யப்படுகிறது", fixed: "சரிசெய்யப்பட்டது. அடுத்த புதுப்பிப்பில் வரும்", not_reproduced: "இன்னும் மீண்டும் நிகழ்த்த முடியவில்லை. குழு பார்க்கும்", watch: "இப்போது சரியாக வேலை செய்வதைப் பாருங்கள்", speak: "பேசிச் சொல்லுங்கள்" }],
    es: ["Informar de un problema", "¿Qué salió mal?", "Cuéntanoslo con tus palabras", "Enviar", "Gracias, ya lo estamos viendo", "Cerrar",
         "Tu último aviso", { received: "Recibido", checking: "Lo estamos probando como tú", found: "Encontramos el problema", fixing: "Se está preparando el arreglo", fixed: "Arreglado. Te llegará con la próxima actualización", not_reproduced: "Aún no logramos repetirlo. El equipo lo revisará", watch: "Míralo funcionar ahora", speak: "Dilo en voz alta" }],
    pt: ["Relatar um problema", "O que deu errado?", "Conte com suas palavras", "Enviar", "Obrigado, já estamos vendo", "Fechar",
         "Seu último relato", { received: "Recebido", checking: "Estamos testando do seu jeito", found: "Encontramos o problema", fixing: "A correção está sendo feita", fixed: "Corrigido. Chega na próxima atualização", not_reproduced: "Ainda não conseguimos repetir. A equipe vai olhar", watch: "Veja funcionando agora", speak: "Fale em vez de digitar" }],
    fr: ["Signaler un problème", "Qu'est-ce qui n'a pas marché ?", "Dites-le avec vos mots", "Envoyer", "Merci, on s'en occupe", "Fermer",
         "Votre dernier signalement", { received: "Reçu", checking: "Nous essayons comme vous", found: "Nous avons trouvé le problème", fixing: "Un correctif est en cours", fixed: "Corrigé. Il arrivera avec la prochaine mise à jour", not_reproduced: "Pas encore reproduit. L'équipe va regarder", watch: "Voyez-le fonctionner maintenant", speak: "Dites-le à voix haute" }],
    de: ["Problem melden", "Was ist schiefgelaufen?", "Erzähl es in deinen Worten", "Senden", "Danke, wir kümmern uns", "Schließen",
         "Deine letzte Meldung", { received: "Erhalten", checking: "Wir probieren es so wie du", found: "Wir haben das Problem gefunden", fixing: "Eine Korrektur entsteht", fixed: "Behoben. Kommt mit dem nächsten Update", not_reproduced: "Noch nicht nachgestellt. Das Team schaut es sich an", watch: "Sieh es dir jetzt funktionierend an", speak: "Lieber sprechen" }],
    id: ["Laporkan masalah", "Apa yang salah?", "Ceritakan dengan kata-kata Anda", "Kirim", "Terima kasih, sedang kami tangani", "Tutup",
         "Laporan terakhir Anda", { received: "Diterima", checking: "Kami mencobanya seperti Anda", found: "Kami menemukan masalahnya", fixing: "Perbaikan sedang dibuat", fixed: "Sudah diperbaiki. Hadir di pembaruan berikutnya", not_reproduced: "Belum bisa kami ulangi. Tim akan memeriksa", watch: "Lihat sekarang sudah berfungsi", speak: "Ucapkan saja" }],
    sw: ["Ripoti tatizo", "Nini kimeharibika?", "Tuambie kwa maneno yako", "Tuma", "Asante, tunalishughulikia", "Funga",
         "Ripoti yako ya mwisho", { received: "Imepokelewa", checking: "Tunajaribu kama ulivyofanya", found: "Tumepata tatizo", fixing: "Linarekebishwa", fixed: "Limerekebishwa. Litakufikia kwenye sasisho lijalo", not_reproduced: "Bado hatujaweza kulirudia. Timu itaangalia", watch: "Tazama likifanya kazi sasa", speak: "Sema badala ya kuandika" }],
    tr: ["Sorun bildir", "Ne ters gitti?", "Kendi sözlerinle anlat", "Gönder", "Teşekkürler, ilgileniyoruz", "Kapat",
         "Son bildirimin", { received: "Alındı", checking: "Senin gibi deniyoruz", found: "Sorunu bulduk", fixing: "Düzeltme hazırlanıyor", fixed: "Düzeltildi. Sonraki güncellemeyle gelecek", not_reproduced: "Henüz tekrarlayamadık. Ekip bakacak", watch: "Şimdi çalıştığını izle", speak: "Yazmak yerine konuş" }],
    vi: ["Báo lỗi", "Đã có chuyện gì?", "Hãy kể bằng lời của bạn", "Gửi", "Cảm ơn, chúng tôi đang xử lý", "Đóng",
         "Báo cáo gần nhất", { received: "Đã nhận", checking: "Chúng tôi đang thử như bạn đã làm", found: "Đã tìm ra lỗi", fixing: "Đang sửa", fixed: "Đã sửa. Sẽ có trong bản cập nhật tới", not_reproduced: "Chưa tái hiện được. Nhóm sẽ xem xét", watch: "Xem nó hoạt động ngay bây giờ", speak: "Nói thay vì gõ" }],
    ru: ["Сообщить о проблеме", "Что пошло не так?", "Расскажите своими словами", "Отправить", "Спасибо, уже разбираемся", "Закрыть",
         "Ваше последнее сообщение", { received: "Получено", checking: "Пробуем так же, как вы", found: "Мы нашли проблему", fixing: "Готовим исправление", fixed: "Исправлено. Придёт со следующим обновлением", not_reproduced: "Пока не удалось повторить. Команда посмотрит", watch: "Посмотрите, как это работает теперь", speak: "Сказать голосом" }],
    ja: ["問題を報告", "何が起きましたか？", "あなたの言葉で教えてください", "送信", "ありがとうございます。対応中です", "閉じる",
         "前回の報告", { received: "受け付けました", checking: "あなたと同じ操作で確認中", found: "問題が見つかりました", fixing: "修正を作成中", fixed: "修正済み。次の更新で届きます", not_reproduced: "まだ再現できていません。チームが確認します", watch: "直った様子を見る", speak: "話して伝える" }],
    zh: ["报告问题", "出了什么问题？", "用你自己的话告诉我们", "发送", "谢谢，我们正在处理", "关闭",
         "你上次的报告", { received: "已收到", checking: "正在按你的操作重现", found: "我们找到了问题", fixing: "正在修复", fixed: "已修复，将随下次更新发布", not_reproduced: "暂时无法重现，团队会继续查看", watch: "查看修复后的效果", speak: "用语音说" }],
  };
  const RTL = new Set(["ar", "ur", "fa", "he"]);
  const lang = (navigator.language || "en").toLowerCase().split("-")[0];
  const [OPEN, ASK, HINT, SEND, THANKS, CLOSE, LAST, STATUS] = T[lang] || T.en;

  const label = (el) => {
    const target = el.closest("button, a, [role=button], input, select, label") || el;
    const fieldLabel = target.labels && target.labels[0] && target.labels[0].innerText;
    const text = target.getAttribute("aria-label") || fieldLabel || target.innerText || target.placeholder || target.tagName;
    return (text || "").trim().replace(/\s+/g, " ").slice(0, 60);
  };

  const env = () => {
    const c = navigator.connection || {};
    return {
      effective_type: c.effectiveType || null,
      rtt_ms: typeof c.rtt === "number" ? c.rtt : null,
      downlink_mbps: typeof c.downlink === "number" ? c.downlink : null,
      device_memory_gb: navigator.deviceMemory || null,
      cpu_cores: navigator.hardwareConcurrency || null,
      viewport: { width: innerWidth, height: innerHeight },
      pixel_ratio: devicePixelRatio,
      language: navigator.language,
      user_agent: navigator.userAgent.slice(0, 200),
      touch: navigator.maxTouchPoints > 0,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || null,
      color_scheme: matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light",
      reduced_motion: matchMedia("(prefers-reduced-motion: reduce)").matches,
      forced_colors: matchMedia("(forced-colors: active)").matches,
    };
  };

  const remember = (report) => {
    try {
      const saved = JSON.parse(localStorage.getItem(STORE_KEY) || "[]").slice(-4);
      localStorage.setItem(STORE_KEY, JSON.stringify([...saved, report]));
    } catch (e) { /* private mode: the user just won't see the status later */ }
  };
  const lastReport = () => {
    try { return JSON.parse(localStorage.getItem(STORE_KEY) || "[]").pop() || null; } catch (e) { return null; }
  };

  const send = async (kind, text) => {
    const body = JSON.stringify({ project: PROJECT, kind, text: (text || "").slice(0, 1000), page: location.pathname,
                                  env: env(), breadcrumbs: breadcrumbs.slice(-10) });
    try {
      const res = await origFetch(ENDPOINT, { method: "POST", headers: { "Content-Type": "application/json" }, body, keepalive: true });
      const data = res.ok ? await res.json() : null;
      if (data && kind === "spoken") remember({ id: data.id, token: data.token });
    } catch (e) { /* the widget must never break the host page */ }
  };
  const sendSilentOnce = (kind, key, text) => {
    if (sentSilent.has(kind + key)) return;
    sentSilent.add(kind + key);
    send(kind, text);
  };

  // Breadcrumbs + rage clicks
  let clicks = [];
  addEventListener("click", (e) => {
    if (e.target.closest("#cr-widget")) return;
    breadcrumbs.push("clicked " + label(e.target));
    const now = Date.now();
    clicks = clicks.filter((c) => now - c.t < RAGE_WINDOW_MS && Math.hypot(c.x - e.clientX, c.y - e.clientY) < RAGE_RADIUS_PX);
    clicks.push({ t: now, x: e.clientX, y: e.clientY });
    if (clicks.length >= RAGE_CLICKS) {
      sendSilentOnce("rage_click", label(e.target), `Rage-clicked "${label(e.target)}"`);
      clicks = [];
    }
  }, true);

  // JS errors
  addEventListener("error", (e) => sendSilentOnce("js_error", e.message, e.message));
  addEventListener("unhandledrejection", (e) => sendSilentOnce("js_error", String(e.reason), String(e.reason).slice(0, 300)));

  // Failed and slow requests
  window.fetch = async (input, init) => {
    const url = new URL(typeof input === "string" ? input : input.url, location.href);
    const started = performance.now();
    try {
      const res = await origFetch(input, init);
      const ms = performance.now() - started;
      if (res.status >= 500) sendSilentOnce("failed_request", url.pathname, `${url.pathname} returned HTTP ${res.status}`);
      else if (ms > SLOW_MS) sendSilentOnce("slow_request", url.pathname, `${url.pathname} took ${Math.round(ms)} ms`);
      return res;
    } catch (err) {
      sendSilentOnce("failed_request", url.pathname, `${url.pathname} failed after ${Math.round(performance.now() - started)} ms: ${err.name}`);
      throw err;
    }
  };

  // "Report a problem" button and form
  const ui = document.createElement("div");
  ui.id = "cr-widget";
  ui.lang = T[lang] ? lang : "en";
  ui.dir = RTL.has(lang) ? "rtl" : "ltr";
  ui.innerHTML = `
    <style>
      #cr-widget{position:fixed;inset-inline-end:16px;bottom:16px;z-index:2147483647;font:15px/1.45 system-ui,"Noto Sans",sans-serif;color:#1d1b18}
      #cr-widget button{min-height:44px;padding:8px 16px;border-radius:22px;border:0;background:#1d1b18;color:#fff;cursor:pointer;font:inherit}
      #cr-widget button:focus-visible,#cr-widget textarea:focus-visible{outline:3px solid #e8590c;outline-offset:2px}
      #cr-widget form{display:none;width:min(320px,calc(100vw - 32px));background:#fff;border-radius:14px;padding:14px;box-shadow:0 10px 34px rgba(0,0,0,.28)}
      #cr-widget label{display:block;font-weight:600;margin-bottom:6px}
      #cr-widget textarea{width:100%;min-height:90px;box-sizing:border-box;font:inherit;padding:8px;border:1px solid #bbb;border-radius:8px;resize:vertical}
      #cr-widget .row{display:flex;gap:8px;margin-top:10px} #cr-widget .row button{flex:1}
      #cr-widget .ghost{background:#eee;color:#1d1b18}
      #cr-widget .mic{width:100%;margin:4px 0 8px;font-size:13px} #cr-widget .mic[aria-pressed=true]{background:#e8590c;color:#fff}
      #cr-widget .status{margin:0 0 10px;padding:8px 10px;background:#f3f0ea;border-radius:8px;font-size:13px}
      #cr-widget .status a{color:inherit;font-weight:600;text-decoration:underline}
      #cr-widget[data-open] form{display:block} #cr-widget[data-open] > button{display:none}
      @media (prefers-color-scheme: dark){#cr-widget form{background:#211f1c;color:#f4f1ec}#cr-widget textarea{background:#2b2925;color:#f4f1ec;border-color:#555}#cr-widget .ghost{background:#38352f;color:#f4f1ec}#cr-widget .status{background:#2b2925}}
      @media (prefers-reduced-motion: no-preference){#cr-widget form{animation:cr-in .16s ease-out}@keyframes cr-in{from{opacity:0;transform:translateY(6px)}}}
    </style>
    <button type="button" aria-haspopup="dialog" aria-expanded="false"></button>
    <form role="dialog" aria-labelledby="cr-ask">
      <p class="status" role="status" hidden></p>
      <label id="cr-ask" for="cr-text"></label>
      <textarea id="cr-text" maxlength="1000" required></textarea>
      <button type="button" class="ghost mic" aria-pressed="false" hidden></button>
      <div class="row"><button type="submit"></button><button type="button" class="ghost"></button></div>
    </form>`;
  const open = ui.querySelector(":scope > button");
  const form = ui.querySelector("form");
  const text = ui.querySelector("textarea");
  const status = ui.querySelector(".status");
  const [submit, close] = form.querySelectorAll(".row button");
  open.textContent = OPEN;
  ui.querySelector("label").textContent = ASK;
  text.placeholder = HINT;
  submit.textContent = SEND;
  close.textContent = CLOSE;

  const Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
  const mic = ui.querySelector(".mic");
  if (Speech) {
    mic.hidden = false;
    mic.innerHTML = '<span aria-hidden="true">🎤</span> ';
    mic.append(STATUS.speak || T.en[7].speak);
    let rec = null;
    mic.addEventListener("click", () => {
      if (rec) return rec.stop();
      rec = new Speech();
      rec.lang = navigator.language || "en";
      const before = text.value ? text.value.trimEnd() + " " : "";
      rec.onresult = (e) => {
        text.value = (before + Array.from(e.results, (r) => r[0].transcript).join(" ")).slice(0, 1000);
      };
      rec.onend = rec.onerror = () => { rec = null; mic.setAttribute("aria-pressed", "false"); text.focus(); };
      mic.setAttribute("aria-pressed", "true");
      rec.start();
    });
  }

  const showStatus = async () => {
    const last = lastReport();
    if (!last) return;
    try {
      const res = await origFetch(`${ENDPOINT}/${encodeURIComponent(last.id)}?token=${encodeURIComponent(last.token)}`);
      if (!res.ok) return;
      const data = await res.json();
      status.textContent = `${LAST}: ${STATUS[data.status] || STATUS.received}`;
      status.hidden = false;
      if (data.films && data.films.after) { // the twin's replay on the fixed app: their problem, gone
        const watch = document.createElement("a");
        watch.href = new URL(data.films.after, script.src).href;
        watch.target = "_blank"; watch.rel = "noopener";
        watch.textContent = STATUS.watch || T.en[7].watch;
        status.append(" ", watch);
      }
    } catch (e) { /* offline: no status, no harm */ }
  };
  const hide = () => { delete ui.dataset.open; open.setAttribute("aria-expanded", "false"); open.focus(); };
  open.addEventListener("click", () => {
    ui.dataset.open = ""; open.setAttribute("aria-expanded", "true"); text.focus(); showStatus();
  });
  close.addEventListener("click", hide);
  form.addEventListener("keydown", (e) => { if (e.key === "Escape") hide(); });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    await send("spoken", text.value);
    form.reset();
    hide();
    open.textContent = THANKS;
  });
  (document.body ? Promise.resolve() : new Promise((r) => addEventListener("DOMContentLoaded", r)))
    .then(() => document.body.append(ui));
})();
