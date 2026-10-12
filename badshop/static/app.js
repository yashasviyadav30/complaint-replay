const $ = (id) => document.getElementById(id);
const CFG = window.BADSHOP_CONFIG;
const state = { phone: "", products: [], cart: new Map(), coupon: null };

document.documentElement.lang = LANG;
document.querySelectorAll("[data-i18n]").forEach((el) => {
  el.textContent = t(el.dataset.i18n);
});

const rupees = (n) => "₹" + n.toLocaleString("en-IN");
const cartItems = () => [...state.cart].map(([id, qty]) => ({ id, qty }));

async function postJson(url, body, timeoutMs = 15000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: ctrl.signal,
    });
    const data = await res.json().catch(() => ({}));
    return { ok: res.ok, data };
  } finally {
    clearTimeout(timer);
  }
}

function showLoginError(msg) {
  $("login-error").textContent = msg;
}

$("send-otp").addEventListener("click", async () => {
  showLoginError("");
  const phone = $("phone").value.trim();
  if (!/^[6-9]\d{9}$/.test(phone)) return showLoginError(t("invalidPhone"));
  state.phone = phone;
  $("send-otp").disabled = true;
  $("login-status").textContent = t("sending");
  try {
    const { ok } = await postJson("/api/otp/send", { phone }, CFG.OTP_TIMEOUT_MS);
    if (!ok) throw new Error("otp send failed");
    $("login-status").textContent = t("otpSent");
    $("otp-step").hidden = false;
    $("otp").focus();
  } catch {
    $("login-status").textContent = "";
    showLoginError(t("otpFailed"));
  } finally {
    $("send-otp").disabled = false;
  }
});

$("verify-otp").addEventListener("click", async () => {
  showLoginError("");
  const { ok } = await postJson("/api/otp/verify", { phone: state.phone, otp: $("otp").value.trim() });
  if (!ok) return showLoginError(t("invalidOtp"));
  $("login").hidden = true;
  $("shop").hidden = false;
  $("cart-btn").hidden = false;
  loadProducts();
});

async function loadProducts() {
  const res = await fetch("/api/products");
  state.products = await res.json();
  $("products").replaceChildren(...state.products.map(productRow));
}

function productRow(p) {
  const name = LANG === "hi" ? p.name_hi : p.name;
  const li = document.createElement("li");
  const label = document.createElement("span");
  label.textContent = `${name} — ${rupees(p.price)}`;
  const add = document.createElement("button");
  add.textContent = t("add");
  add.setAttribute("aria-label", `${t("add")} ${name}`);
  add.addEventListener("click", () => addToCart(p.id));
  li.append(label, add);
  return li;
}

function addToCart(id) {
  state.cart.set(id, (state.cart.get(id) || 0) + 1);
  const count = [...state.cart.values()].reduce((a, b) => a + b, 0);
  $("cart-count").textContent = count;
  if (!$("cart").hidden) renderCart();
}

function renderCart() {
  $("cart-items").replaceChildren(
    ...cartItems().map(({ id, qty }) => {
      const p = state.products.find((x) => x.id === id);
      const li = document.createElement("li");
      li.textContent = `${LANG === "hi" ? p.name_hi : p.name} × ${qty}`;
      return li;
    }),
  );
  refreshQuote();
}

async function refreshQuote() {
  const { ok, data } = await postJson("/api/cart/quote", { items: cartItems(), coupon: state.coupon });
  if (ok) $("total").textContent = rupees(data.total);
}

$("cart-btn").addEventListener("click", () => {
  $("cart").hidden = false;
  renderCart();
  $("cart").scrollIntoView();
});

$("apply-coupon").addEventListener("click", () => {
  state.coupon = $("coupon").value.trim() || null;
  refreshQuote();
});

$("pay").addEventListener("click", async () => {
  $("cart-error").textContent = "";
  if (!state.cart.size) return ($("cart-error").textContent = t("emptyCart"));
  const { ok, data } = await postJson("/api/checkout", { items: cartItems(), coupon: state.coupon });
  if (!ok) return ($("cart-error").textContent = t("otpFailed"));
  $("shop").hidden = true;
  $("cart").hidden = true;
  $("done").hidden = false;
  $("charged").textContent = rupees(data.charged);
});
