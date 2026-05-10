import os
import time
import threading
import requests

from flask import Flask

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)

TOKEN = os.getenv("TOKEN")

app = Flask(__name__)

# Palavras monitoradas
palavras = [
    "headset",
    "webcam",
    "ssd",
    "memória ram"
]

# Evita mensagens repetidas
enviados = set()


@app.route("/")
def home():
    return "Bot PNCP online!"


# =========================
# FUNÇÃO DE BUSCA PNCP
# =========================

async def buscar_pncp_manual(chat_id, app_telegram):

    url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"

    try:

        resposta = requests.get(url, timeout=30)

        print("Status PNCP:", resposta.status_code)

        if resposta.status_code != 200:

            await app_telegram.bot.send_message(
                chat_id=chat_id,
                text="❌ Erro ao consultar PNCP."
            )

            return

        dados = resposta.json().get("data", [])

        encontrados = 0

        for item in dados:

            texto = str(item).lower()

            for palavra in palavras:

                if palavra.lower() in texto:

                    id_item = item.get("numeroControlePNCP")

                    if not id_item:
                        continue

                    if id_item in enviados:
                        continue

                    enviados.add(id_item)

                    encontrados += 1

                    mensagem = f"""
📢 Nova oportunidade encontrada!

🔎 Palavra: {palavra}

📄 Objeto:
{item.get('objetoCompra', 'Sem descrição')}

🏢 Órgão:
{item.get('orgaoEntidade', {}).get('razaoSocial', 'Não informado')}
"""

                    await app_telegram.bot.send_message(
                        chat_id=chat_id,
                        text=mensagem
                    )

        if encontrados == 0:

            await app_telegram.bot.send_message(
                chat_id=chat_id,
                text="🔍 Nenhuma nova oportunidade encontrada."
            )

    except Exception as e:

        print(e)

        await app_telegram.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Erro: {e}"
        )


# =========================
# LOOP AUTOMÁTICO
# =========================

def loop_busca(app_telegram, chat_id):

    while True:

        try:

            requests.get("https://pncp.gov.br")

            url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"

            resposta = requests.get(url, timeout=30)

            if resposta.status_code == 200:

                dados = resposta.json().get("data", [])

                for item in dados:

                    texto = str(item).lower()

                    for palavra in palavras:

                        if palavra.lower() in texto:

                            id_item = item.get("numeroControlePNCP")

                            if not id_item:
                                continue

                            if id_item in enviados:
                                continue

                            enviados.add(id_item)

                            mensagem = f"""
📢 Nova oportunidade encontrada!

🔎 Palavra: {palavra}

📄 Objeto:
{item.get('objetoCompra', 'Sem descrição')}

🏢 Órgão:
{item.get('orgaoEntidade', {}).get('razaoSocial', 'Não informado')}
"""

                            app_telegram.bot.send_message(
                                chat_id=chat_id,
                                text=mensagem
                            )

        except Exception as e:

            print(f"Erro loop: {e}")

        time.sleep(300)


# =========================
# COMANDOS TELEGRAM
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    mensagem = """
✅ Bot PNCP iniciado!

Comandos disponíveis:

/listar
/add palavra
/remove palavra
/buscar
"""

    await update.message.reply_text(mensagem)


async def listar(update: Update, context: ContextTypes.DEFAULT_TYPE):

    texto = "📋 Palavras monitoradas:\n\n"

    for p in palavras:
        texto += f"• {p}\n"

    await update.message.reply_text(texto)


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:

        await update.message.reply_text(
            "Use:\n/add headset"
        )

        return

    nova = " ".join(context.args).lower()

    if nova in palavras:

        await update.message.reply_text(
            "⚠️ Palavra já existe."
        )

        return

    palavras.append(nova)

    await update.message.reply_text(
        f"✅ Palavra adicionada: {nova}"
    )


async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:

        await update.message.reply_text(
            "Use:\n/remove headset"
        )

        return

    palavra = " ".join(context.args).lower()

    if palavra not in palavras:

        await update.message.reply_text(
            "❌ Palavra não encontrada."
        )

        return

    palavras.remove(palavra)

    await update.message.reply_text(
        f"🗑 Palavra removida: {palavra}"
    )


async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🔍 Buscando oportunidades..."
    )

    await buscar_pncp_manual(
        update.effective_chat.id,
        context.application
    )


import asyncio

# ... (seus handlers e funções permanecem iguais)

# =========================
# INICIAR BOT
# =========================

def rodar_bot_thread():
    # Cria um novo loop de eventos para esta thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Configura a aplicação
    telegram_app = ApplicationBuilder().token(TOKEN).build()

    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("listar", listar))
    telegram_app.add_handler(CommandHandler("add", add))
    telegram_app.add_handler(CommandHandler("remove", remove))
    telegram_app.add_handler(CommandHandler("buscar", buscar))

    print("Bot do Telegram iniciado...")
    
    # Roda o bot dentro do loop da thread
    telegram_app.run_polling(close_loop=False)

if __name__ == "__main__":
    # Inicia o Telegram em background
    t = threading.Thread(target=rodar_bot_thread, daemon=True)
    t.start()

    # Inicia o Flask (Bloqueante, mantém o script vivo)
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
