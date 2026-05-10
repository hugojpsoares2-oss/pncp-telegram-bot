import os
import asyncio
import threading
import requests
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Configurações Iniciais
TOKEN = os.getenv("TOKEN")
app = Flask(__name__)

palavras = ["headset", "webcam", "ssd", "memória ram"]
enviados = set()
CHAT_ID_MONITORAMENTO = None

@app.route("/")
def home():
    return "Bot PNCP online!"

# ==========================================
# LÓGICA DE BUSCA PNCP
# ==========================================
from datetime import datetime

async def verificar_pncp(context: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID_MONITORAMENTO
    
    print("🔍 [PNCP] Iniciando busca de novas oportunidades...")
    
    if not CHAT_ID_MONITORAMENTO:
        print("⚠️ [PNCP] Busca cancelada: CHAT_ID ainda não definido. Dê /start no Telegram.")
        return

    # Pega a data de hoje no formato exigido pela API: AAAAMMDD
    hoje = datetime.now().strftime("%Y%m%d")
    
    # Adicionamos os parâmetros na URL (data inicial e página 1)
    url = f"https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao?dataInicial={hoje}&pagina=1"
    
    try:
        loop = asyncio.get_event_loop()
        resposta = await loop.run_in_executor(None, lambda: requests.get(url, timeout=20))
        
        print(f"📡 [PNCP] Status da API: {resposta.status_code}")

        if resposta.status_code == 200:
            # A API do PNCP retorna os dados dentro de 'data'
            dados = resposta.json().get("data", [])
            print(f"📦 [PNCP] {len(dados)} itens recebidos hoje ({hoje}).")
            
            encontrados_nesta_rodada = 0
            for item in dados:
                id_item = item.get("numeroControlePNCP")
                texto = str(item).lower()
                
                for palavra in palavras:
                    if palavra.lower() in texto and id_item not in enviados:
                        enviados.add(id_item)
                        encontrados_nesta_rodada += 1
                        
                        msg = (f"📢 **Nova Oportunidade!**\n\n"
                               f"🔎 Termo: {palavra}\n"
                               f"🏢 Órgão: {item.get('orgaoEntidade', {}).get('razaoSocial')}\n"
                               f"📄 Objeto: {item.get('objetoCompra', 'Sem descrição')}\n"
                               f"🔗 [Link da Contratação](https://pncp.gov.br/app/editais/{item.get('orgaoEntidade', {}).get('cnpj')}/{item.get('anoContratacao')}/{item.get('sequencialContratacao')})")
                        
                        await context.bot.send_message(chat_id=CHAT_ID_MONITORAMENTO, text=msg, parse_mode="Markdown")
            
            print(f"✅ [PNCP] Busca finalizada. {encontrados_nesta_rodada} novas oportunidades enviadas.")
        else:
            print(f"❌ [PNCP] Erro na API: {resposta.status_code} - {resposta.text}")

    except Exception as e:
        print(f"💥 [PNCP] Erro crítico na busca: {e}")
# ==========================================
# FUNÇÕES DOS COMANDOS (Onde estava o erro)
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID_MONITORAMENTO
    CHAT_ID_MONITORAMENTO = update.effective_chat.id
    await update.message.reply_text("✅ Monitoramento PNCP ativado neste chat!")

async def listar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = "📋 Palavras monitoradas:\n\n" + "\n".join([f"• {p}" for p in palavras])
    await update.message.reply_text(texto)

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /add palavra")
        return
    nova = " ".join(context.args).lower()
    if nova not in palavras:
        palavras.append(nova)
        await update.message.reply_text(f"✅ Adicionada: {nova}")
    else:
        await update.message.reply_text("⚠️ Já existe.")

async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /remove palavra")
        return
    palavra = " ".join(context.args).lower()
    if palavra in palavras:
        palavras.remove(palavra)
        await update.message.reply_text(f"🗑 Removida: {palavra}")
    else:
        await update.message.reply_text("❌ Não encontrada.")

# ==========================================
# INICIALIZAÇÃO
# ==========================================
def iniciar_flask():
    port = int(os.environ.get("PORT", 10000))
    # use_reloader=False é vital aqui para evitar duplicar o bot
    app.run(host="0.0.0.0", port=port, use_reloader=False)

if __name__ == "__main__":
    if not TOKEN:
        print("❌ ERRO: Variável TOKEN não configurada no Render!")
    else:
        # 1. Flask em segundo plano para o UptimeRobot responder 200
        print("🌐 Iniciando servidor Flask para UptimeRobot...")
        t_flask = threading.Thread(target=iniciar_flask, daemon=True)
        t_flask.start()

        # 2. Bot na Thread Principal (Correção do RuntimeError de sinais)
        print("🚀 Iniciando Bot do Telegram na thread principal...")
        
        application = ApplicationBuilder().token(TOKEN).build()
        
        # Registrar os Handlers corretamente
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("listar", listar))
        application.add_handler(CommandHandler("add", add))
        application.add_handler(CommandHandler("remove", remove))
        
        # Configura o monitoramento automático (JobQueue)
        if application.job_queue:
            application.job_queue.run_repeating(verificar_pncp, interval=300, first=10)
        
        print("✅ Tudo pronto! Aguardando comandos no Telegram...")
        application.run_polling()
