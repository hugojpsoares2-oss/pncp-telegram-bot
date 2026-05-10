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
app = Flask(__name__)

# Variáveis globais dinâmicas
palavras = ["headset", "webcam", "ssd", "memória ram"]
VALOR_MAXIMO = 5000.00  # Valor padrão inicial
enviados = set()
CHAT_ID_MONITORAMENTO = None

@app.route("/")
def home():
    return "Bot PNCP Online!", 200

# ==========================================
# LÓGICA DE BUSCA PNCP
# ==========================================
async def verificar_pncp(context: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID_MONITORAMENTO, VALOR_MAXIMO
    
    if not CHAT_ID_MONITORAMENTO:
        print("⚠️ [PNCP] Aguardando /start no Telegram para enviar mensagens.")
        return

    hoje = datetime.now().strftime("%Y%m%d")
    print(f"🔍 [PNCP] Buscando Dispensas (Mod 8) até R$ {VALOR_MAXIMO}...")

    # URL filtrando por data e Modalidade 8 (Dispensa)
    url = (
        f"https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao?"
        f"dataInicial={hoje}&dataFinal={hoje}&codigoModalidade=8&pagina=1"
    )

    try:
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, lambda: requests.get(url, timeout=20))
        
        if res.status_code == 200:
            dados = res.json().get("data", [])
            encontrados = 0
            
            for item in dados:
                id_item = item.get("numeroControlePNCP")
                # Pega o valor (estimado ou total)
                valor = item.get("valorEstimado", 0) or item.get("valorTotal", 0)
                texto_licitacao = str(item).lower()

                # Filtro 1: Valor
                if valor <= VALOR_MAXIMO:
                    # Filtro 2: Palavras-chave
                    for p in palavras:
                        if p.lower() in texto_licitacao and id_item not in enviados:
                            enviados.add(id_item)
                            encontrados += 1
                            
                            link = f"https://pncp.gov.br/app/editais/{item.get('orgaoEntidade', {}).get('cnpj')}/{item.get('anoContratacao')}/{item.get('sequencialContratacao')}"
                            
                            msg = (
                                f"💰 *Dispensa Encontrada (Até R$ {VALOR_MAXIMO})*\n\n"
                                f"🔎 *Termo:* {p.upper()}\n"
                                f"💵 *Valor:* R$ {valor:,.2f}\n"
                                f"🏢 *Órgão:* {item.get('orgaoEntidade', {}).get('razaoSocial')}\n"
                                f"📄 *Objeto:* {item.get('objetoCompra', 'Sem descrição')[:250]}...\n\n"
                                f"🔗 [Ver no PNCP]({link})"
                            )
                            await context.bot.send_message(CHAT_ID_MONITORAMENTO, msg, parse_mode="Markdown")
            
            print(f"✅ [PNCP] Busca concluída. {encontrados} novas oportunidades enviadas.")
        else:
            print(f"❌ [PNCP] Erro na API: {res.status_code}")

    except Exception as e:
        print(f"💥 [PNCP] Erro crítico: {e}")

# ==========================================
# COMANDOS DO TELEGRAM
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID_MONITORAMENTO
    CHAT_ID_MONITORAMENTO = update.effective_chat.id
    await update.message.reply_text("✅ Monitoramento de DISPENSAS ativado!")

async def valor_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global VALOR_MAXIMO
    if not context.args:
        await update.message.reply_text(f"O valor máximo atual é R$ {VALOR_MAXIMO}. Use: /valor 5000")
        return
    try:
        VALOR_MAXIMO = float(context.args[0].replace(",", "."))
        await update.message.reply_text(f"✅ Novo limite de valor definido: R$ {VALOR_MAXIMO:,.2f}")
    except ValueError:
        await update.message.reply_text("❌ Valor inválido. Use apenas números.")

async def listar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = f"📋 *Configurações:* \n💰 Valor Máx: R$ {VALOR_MAXIMO}\n\n*Palavras:*\n" + "\n".join([f"• {p}" for p in palavras])
    await update.message.reply_text(texto, parse_mode="Markdown")

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nova = " ".join(context.args).lower()
    if nova and nova not in palavras:
        palavras.append(nova)
        await update.message.reply_text(f"✅ Adicionada: {nova}")

async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = " ".join(context.args).lower()
    if p in palavras:
        palavras.remove(p)
        await update.message.reply_text(f"🗑 Removida: {p}")

# ==========================================
# INICIALIZAÇÃO
# ==========================================
def iniciar_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

if __name__ == "__main__":
    if TOKEN:
        threading.Thread(target=iniciar_flask, daemon=True).start()
        
        application = ApplicationBuilder().token(TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("valor", valor_cmd))
        application.add_handler(CommandHandler("listar", listar))
        application.add_handler(CommandHandler("add", add))
        application.add_handler(CommandHandler("remove", remove))
        
        if application.job_queue:
            application.job_queue.run_repeating(verificar_pncp, interval=300, first=10)
        
        print("✅ Bot Rodando. Aguardando comandos...")
        application.run_polling(drop_pending_updates=True)
