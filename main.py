import os
import asyncio
import threading
import requests
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("TOKEN")
app = Flask(__name__)

palavras = ["headset", "webcam", "ssd", "memória ram"]
enviados = set()
CHAT_ID_MONITORAMENTO = None # Será preenchido quando você der /start

@app.route("/")
def home():
    return "Bot PNCP online!"

# ==========================================
# LÓGICA DE BUSCA (ASSÍNCRONA)
# ==========================================
async def verificar_pncp(context: ContextTypes.DEFAULT_TYPE):
    """Função que será executada repetidamente pelo JobQueue"""
    global CHAT_ID_MONITORAMENTO
    if not CHAT_ID_MONITORAMENTO:
        return

    url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
    try:
        # Usando loop.run_in_executor para não travar o bot com requests síncrono
        loop = asyncio.get_event_loop()
        resposta = await loop.run_in_executor(None, lambda: requests.get(url, timeout=20))
        
        if resposta.status_code == 200:
            dados = resposta.json().get("data", [])
            for item in dados:
                texto = str(item).lower()
                for palavra in palavras:
                    id_item = item.get("numeroControlePNCP")
                    if palavra.lower() in texto and id_item not in enviados:
                        enviados.add(id_item)
                        
                        msg = f"📢 **Nova Oportunidade!**\n\n🔎 Termo: {palavra}\n🏢 Órgão: {item.get('orgaoEntidade', {}).get('razaoSocial')}\n📄 Objeto: {item.get('objetoCompra')}"
                        
                        await context.bot.send_message(chat_id=CHAT_ID_MONITORAMENTO, text=msg)
    except Exception as e:
        print(f"Erro na busca: {e}")

# ==========================================
# COMANDOS
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID_MONITORAMENTO
    CHAT_ID_MONITORAMENTO = update.effective_chat.id
    await update.message.reply_text("✅ Monitoramento PNCP ativado neste chat!")

# ==========================================
# INICIALIZAÇÃO DO BOT
# ==========================================
def run_telegram_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # O segredo está aqui: JobQueue gerencia o tempo para você
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    
    # Configura a busca automática para rodar a cada 300 segundos (5 minutos)
    job_queue = application.job_queue
    job_queue.run_repeating(verificar_pncp, interval=300, first=10)
    
    print("Bot e Monitoramento iniciados...")
    application.run_polling(close_loop=False)

if __name__ == "__main__":
    if TOKEN:
        t = threading.Thread(target=run_telegram_bot, daemon=True)
        t.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
