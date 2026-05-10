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
MY_URL = "https://pncp-telegram-bot.onrender.com/" # VERIFIQUE SE É ESTA MESMA
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
        print("⛽ [Auto-Ping] Bot se auto-alimentou para não dormir.")
    except Exception as e:
        print(f"⚠️ [Auto-Ping] Erro ao tentar se manter vivo: {e}")

async def verificar_pncp(context: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID_MONITORAMENTO, VALOR_MAXIMO, enviados, ultima_limpeza
    
    # Limpa a memória todo dia à meia-noite
    hoje_dt = datetime.now()
    if hoje_dt.day != ultima_limpeza:
        enviados.clear()
        ultima_limpeza = hoje_dt.day
        print("🧹 [Memória] Lista de enviados limpa para o novo dia.")

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

# Comandos do Telegram
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

def iniciar_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

if __name__ == "__main__":
    if TOKEN:
        threading.Thread(target=iniciar_flask, daemon=True).start()
        application = ApplicationBuilder().token(TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("valor", valor_cmd))
        
        if application.job_queue:
            # Busca licitações a cada 5 min
            application.job_queue.run_repeating(verificar_pncp, interval=300, first=10)
            # Auto-ping a cada 12 min (para intercalar com o UptimeRobot)
            application.job_queue.run_repeating(auto_ping, interval=720, first=30)
        
        application.run_polling(drop_pending_updates=True)
