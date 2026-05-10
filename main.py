import os
import asyncio
import threading
import requests
from flask import Flask
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Configurações Iniciais
TOKEN = os.getenv("TOKEN")
MY_URL = "https://pncp-telegram-bot.onrender.com/"
app = Flask(__name__)

# Variáveis globais
palavras = ["headset", "webcam", "ssd", "memória ram"]
VALOR_MAXIMO = 5000.00
enviados = set()
CHAT_ID_MONITORAMENTO = None
ultima_limpeza = datetime.now().day

@app.route("/")
def home():
    return "BOT PNCP VIVO", 200

# Função para o bot se auto-pingar e evitar sono do Render
async def auto_ping(context: ContextTypes.DEFAULT_TYPE):
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: requests.get(MY_URL, timeout=10))
        print("⛽ [Auto-Ping] Bot se auto-alimentou.")
    except Exception as e:
        print(f"⚠️ [Auto-Ping] Erro: {e}")

async def verificar_pncp(context: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID_MONITORAMENTO, VALOR_MAXIMO, enviados, ultima_limpeza
    
    hoje_dt = datetime.now()
    if hoje_dt.day != ultima_limpeza:
        enviados.clear()
        ultima_limpeza = hoje_dt.day
        print("🧹 [Memória] Lista limpa para o novo dia.")

    if not CHAT_ID_MONITORAMENTO:
        return

    hoje = hoje_dt.strftime("%Y%m%d")
    url = (f"https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao?"
           f"dataInicial={hoje}&dataFinal={hoje}&codigoModalidade=8&pagina=1")

    try:
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, lambda: requests.get(url, timeout=20))
        
        if res.status_code == 200:
            dados = res.json().get("data", [])
            for item in dados:
                id_item = item.get("numeroControlePNCP")
                valor = item.get("valorEstimado", 0) or item.get("valorTotal", 0)
                
                if valor <= VALOR_MAXIMO and id_item not in enviados:
                    texto_licitacao = str(item).lower()
                    for p in palavras:
                        if p.lower() in texto_licitacao:
                            enviados.add(id_item)
                            link = f"https://pncp.gov.br/app/editais/{item.get('orgaoEntidade', {}).get('cnpj')}/{item.get('anoContratacao')}/{item.get('sequencialContratacao')}"
                            msg = (f"💰 *DISPENSA ATÉ R$ {VALOR_MAXIMO}*\n\n"
                                   f"🔎 *Termo:* {p.upper()}\n"
                                   f"💵 *Valor:* R$ {valor:,.2f}\n"
                                   f"🏢 *Órgão:* {item.get('orgaoEntidade', {}).get('razaoSocial')}\n"
                                   f"🔗 [Link do Edital]({link})")
                            await context.bot.send_message(CHAT_ID_MONITORAMENTO, msg, parse_mode="Markdown")
    except Exception as e:
        print(f"💥 [Erro PNCP]: {e}")

# ==========================================
# COMANDOS DO TELEGRAM (Recriados)
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID_MONITORAMENTO
    CHAT_ID_MONITORAMENTO = update.effective_chat.id
    await update.message.reply_text("✅ Radar de Dispensas Ativado!")

async def valor_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global VALOR_MAXIMO
    if context.args:
        try:
            VALOR_MAXIMO = float(context.args[0].replace(",", "."))
            await update.message.reply_text(f"✅ Novo limite: R$ {VALOR_MAXIMO:,.2f}")
        except: await update.message.reply_text("Use: /valor 5000")
    else:
        await update.message.reply_text(f"Valor atual: R$ {VALOR_MAXIMO}")

async def listar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = f"📋 *Configurações:*\n💰 Valor Máx: R$ {VALOR_MAXIMO}\n\n*Palavras:*\n" + "\n".join([f"• {p}" for p in palavras])
    await update.message.reply_text(texto, parse_mode="Markdown")

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nova = " ".join(context.args).lower()
    if nova:
        if nova not in palavras:
            palavras.append(nova)
            await update.message.reply_text(f"✅ Adicionada: {nova}")
        else:
            await update.message.reply_text("⚠️ Já está na lista.")
    else:
        await update.message.reply_text("Use: /add termo")

async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = " ".join(context.args).lower()
    if p in palavras:
        palavras.remove(p)
        await update.message.reply_text(f"🗑 Removida: {p}")
    else:
        await update.message.reply_text("❌ Não encontrada.")

def iniciar_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

if __name__ == "__main__":
    if TOKEN:
        threading.Thread(target=iniciar_flask, daemon=True).start()
        application = ApplicationBuilder().token(TOKEN).build()
        
        # REGISTRO OBRIGATÓRIO DOS COMANDOS
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("valor", valor_cmd))
        application.add_handler(CommandHandler("listar", listar))
        application.add_handler(CommandHandler("add", add))
        application.add_handler(CommandHandler("remove", remove))
        
        if application.job_queue:
            application.job_queue.run_repeating(verificar_pncp, interval=300, first=10)
            application.job_queue.run_repeating(auto_ping, interval=720, first=30)
        
        print("✅ Bot Rodando com todos os comandos!")
        application.run_polling(drop_pending_updates=True)
