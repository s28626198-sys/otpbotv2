import TelegramBot from "node-telegram-bot-api";

const BOT_TOKEN = process.env.BOT_TOKEN;
const SMSBOWER_API_KEY = process.env.SMSBOWER_API_KEY;
const BASE = process.env.SMSBOWER_BASE_URL || "https://smsbower.page/stubs/handler_api.php";

const bot = new TelegramBot(BOT_TOKEN, { polling: true });

async function api(params) {
  const u = new URL(BASE);
  Object.entries({ api_key: SMSBOWER_API_KEY, ...params }).forEach(([k, v]) => u.searchParams.set(k, String(v)));
  const t = (await fetch(u).then(r => r.text())).trim();
  return t;
}

bot.onText(/^\/buy\s+(\w+)\s+(\d+)$/, async (msg, m) => {
  const chatId = msg.chat.id;
  const service = m[1];
  const country = m[2];

  const r = await api({ action: "getNumber", service, country });
  if (!r.startsWith("ACCESS_NUMBER:")) {
    await bot.sendMessage(chatId, `❌ Failed: ${r}`);
    return;
  }

  const [, activationId, phone] = r.split(":");
  await bot.sendMessage(chatId, `📱 Number: ${phone}\nActivation: ${activationId}`);

  const started = Date.now();
  const timer = setInterval(async () => {
    const st = await api({ action: "getStatus", id: activationId });

    if (st.startsWith("STATUS_OK:")) {
      const code = st.replace("STATUS_OK:", "");
      await bot.sendMessage(chatId, `✅ OTP: ${code}`);
      await api({ action: "setStatus", id: activationId, status: 6 });
      clearInterval(timer);
      return;
    }

    if (Date.now() - started > 120000) {
      await bot.sendMessage(chatId, "⌛ Timeout waiting for SMS");
      clearInterval(timer);
    }
  }, 5000);
});

bot.onText(/^\/balance$/, async (msg) => {
  const r = await api({ action: "getBalance" });
  await bot.sendMessage(msg.chat.id, `💰 ${r}`);
});
