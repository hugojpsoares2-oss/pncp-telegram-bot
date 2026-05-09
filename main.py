import os
import time
import threading
import requests

from flask import Flask
from telegram import Bot

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TOKEN)

app = Flask(__name__)

palavras = [
    "headset",
    "webcam",
    "ssd",
    "memória ram"
]

enviados = set()


@app.route("/")
def home():
    return "Bot PNCP online!"


def buscar_pncp():

    url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"

    resposta = requests.get(url, timeout=30)

    if resposta.status_code != 200:
        return

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

                bot.send_message(
                    chat_id=CHAT_ID,
                    text=mensagem
                )


def loop_bot():

    while True:

        try:
            buscar_pncp()

        except Exception as e:
            print(f"Erro: {e}")

        time.sleep(300)


thread = threading.Thread(target=loop_bot)
thread.start()


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
