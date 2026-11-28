import { MAX_LEN, splitSource, mdToHtml, stripTags } from "./textfmt.js";

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

export class TelegramClient {
  constructor(token) {
    this.token = token;
    this.base = `https://api.telegram.org/bot${token}`;
  }

  async call(method, payload = {}, retries = 2) {
    for (let attempt = 0; attempt <= retries; attempt++) {
      const resp = await fetch(`${this.base}/${method}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await resp.json().catch(() => ({ ok: false, description: `HTTP ${resp.status}` }));
      if (data.ok) return data.result;
      if (data.error_code === 429 && attempt < retries) {
        const ra = Number(data?.parameters?.retry_after || 2);
        await sleep(Math.min(ra, 15) * 1000);
        continue;
      }
      const err = new Error(data.description || `Telegram API error ${data.error_code}`);
      err.code = data.error_code;
      err.data = data;
      throw err;
    }
  }

  async sendMessage(chatId, text, extra = {}) {
    return this.call("sendMessage", { chat_id: chatId, text: String(text).slice(0, MAX_LEN), ...extra });
  }

  async sendHtml(chatId, htmlText, replyMarkup = null, extra = {}) {
    const base = { disable_web_page_preview: true, ...extra };
    if (replyMarkup) base.reply_markup = replyMarkup;
    try {
      return await this.sendMessage(chatId, htmlText, { parse_mode: "HTML", ...base });
    } catch (e) {
      if (String(e.message || "").toLowerCase().includes("parse entities")) {
        return await this.sendMessage(chatId, stripTags(htmlText), base);
      }
      throw e;
    }
  }

  async sendLong(chatId, mdText, replyMarkup = null, alreadyHtml = false, extra = {}) {
    const chunks = splitSource(mdText);
    if (!chunks.length) return null;
    let last = null;
    for (let i = 0; i < chunks.length; i++) {
      const body = alreadyHtml ? chunks[i] : mdToHtml(chunks[i]);
      const markup = i === chunks.length - 1 ? replyMarkup : null;
      last = await this.sendHtml(chatId, body, markup, extra);
      if (chunks.length > 1) await sleep(250);
    }
    return last;
  }

  async editHtml(chatId, messageId, htmlText, replyMarkup = null) {
    const base = {
      chat_id: chatId,
      message_id: messageId,
      disable_web_page_preview: true,
    };
    if (replyMarkup) base.reply_markup = replyMarkup;
    try {
      return await this.call("editMessageText", { text: String(htmlText).slice(0, MAX_LEN), parse_mode: "HTML", ...base });
    } catch (e) {
      const msg = String(e.message || "").toLowerCase();
      if (msg.includes("not modified")) return null;
      if (msg.includes("parse entities")) {
        return await this.call("editMessageText", { text: stripTags(htmlText).slice(0, MAX_LEN), ...base });
      }
      throw e;
    }
  }

  async editReplyMarkup(chatId, messageId, replyMarkup = null) {
    try {
      return await this.call("editMessageReplyMarkup", {
        chat_id: chatId,
        message_id: messageId,
        reply_markup: replyMarkup || { inline_keyboard: [] },
      });
    } catch {}
  }

  async deleteMessage(chatId, messageId) {
    try {
      await this.call("deleteMessage", { chat_id: chatId, message_id: messageId });
    } catch {}
  }

  async answerCallback(callbackQueryId, text = undefined, showAlert = false) {
    try {
      const payload = { callback_query_id: callbackQueryId, show_alert: Boolean(showAlert) };
      if (text !== undefined && text !== null) payload.text = String(text).slice(0, 200);
      await this.call("answerCallbackQuery", payload);
    } catch {}
  }

  async sendChatAction(chatId, action = "typing") {
    try {
      await this.call("sendChatAction", { chat_id: chatId, action });
    } catch {}
  }

  async sendPoll(chatId, question, options, extra = {}) {
    return this.call("sendPoll", {
      chat_id: chatId,
      question: String(question).slice(0, 300),
      options: options.map(o => ({ text: String(o).slice(0, 100) })),
      ...extra,
    });
  }

  async getChat(chatId) {
    return this.call("getChat", { chat_id: chatId });
  }

  async getChatMember(chatId, userId) {
    return this.call("getChatMember", { chat_id: chatId, user_id: userId });
  }

  async getChatMemberCount(chatId) {
    return this.call("getChatMemberCount", { chat_id: chatId });
  }

  async getMe() {
    return this.call("getMe", {});
  }

  async downloadFile(fileId) {
    const info = await this.call("getFile", { file_id: fileId });
    const url = `https://api.telegram.org/file/bot${this.token}/${info.file_path}`;
    const resp = await fetch(url);
    const buf = await resp.arrayBuffer();
    const bytes = new Uint8Array(buf);
    let bin = "";
    const step = 8192;
    for (let i = 0; i < bytes.length; i += step) {
      bin += String.fromCharCode(...bytes.subarray(i, i + step));
    }
    const base64 = btoa(bin);
    const mime = String(info.file_path || "").toLowerCase().endsWith(".png") ? "image/png" : "image/jpeg";
    return { base64, mime };
  }

  async sendDocumentBytes(chatId, bytes, filename, caption = "") {
    const form = new FormData();
    form.append("chat_id", String(chatId));
    form.append("document", new Blob([bytes], { type: "text/csv;charset=utf-8" }), filename);
    if (caption) form.append("caption", caption);
    const resp = await fetch(`${this.base}/sendDocument`, { method: "POST", body: form });
    return resp.json();
  }

  async sendPhotoSvgOrPng(chatId, svgText, filename, caption = "") {
    const form = new FormData();
    form.append("chat_id", String(chatId));
    form.append("document", new Blob([svgText], { type: "image/svg+xml" }), filename);
    if (caption) form.append("caption", caption);
    const resp = await fetch(`${this.base}/sendDocument`, { method: "POST", body: form });
    return resp.json();
  }
}
