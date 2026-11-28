import { getConfig } from "./config.js";
import { Database } from "./db.js";
import { TelegramClient } from "./telegram.js";
import { BotContext } from "./context.js";
import { handleUpdate } from "./router.js";
import { runScheduled } from "./cron.js";
export { QuizRoom } from "./quiz_room.js";

function makeCtx(env) {
  const cfg = getConfig(env);
  const db = new Database(env.DB);
  const tg = new TelegramClient(cfg.TELEGRAM_TOKEN);
  return new BotContext(env, cfg, db, tg);
}

export default {
  async fetch(request, env, execCtx) {
    const url = new URL(request.url);
    const ctx = makeCtx(env);

    if (request.method === "GET" && (url.pathname === "/" || url.pathname === "/health")) {
      return Response.json({
        ok: true,
        service: "aitilshunosbot",
        version: ctx.cfg.BOT_VERSION,
        runtime: "cloudflare-workers",
      });
    }

    if (request.method === "GET" && url.pathname === "/set-webhook") {
      if (env.WEBHOOK_SECRET && url.searchParams.get("secret") !== env.WEBHOOK_SECRET) {
        return new Response("Forbidden", { status: 403 });
      }
      const target = `${url.origin}/webhook`;
      const params = {
        url: target,
        allowed_updates: ["message", "callback_query", "poll_answer"],
        drop_pending_updates: false,
      };
      if (env.WEBHOOK_SECRET) params.secret_token = env.WEBHOOK_SECRET;
      const res = await ctx.tg.call("setWebhook", params);
      return Response.json({ ok: true, webhook: target, telegram: res });
    }

    if (request.method === "POST" && url.pathname === "/webhook") {
      if (env.WEBHOOK_SECRET) {
        const hdr = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
        if (hdr !== env.WEBHOOK_SECRET) {
          return new Response("Unauthorized", { status: 401 });
        }
      }
      const update = await request.json().catch(() => null);
      if (update) {
        execCtx.waitUntil(
          handleUpdate(ctx, update).catch(err => console.error("Update error:", err))
        );
      }
      return new Response("OK");
    }

    return new Response("Not found", { status: 404 });
  },

  async scheduled(event, env, execCtx) {
    const ctx = makeCtx(env);
    execCtx.waitUntil(
      runScheduled(ctx, event.cron).catch(err => console.error("Cron error:", err))
    );
  },
};
