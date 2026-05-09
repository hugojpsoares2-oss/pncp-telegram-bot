import requests
import time
from telegram import Bot

TOKEN = "8725171682:AAHwAZC05Axrpm5leyC4btpn6ELJ2i7x_aI"
CHAT_ID = "SEU_CHAT_ID"

bot = Bot(token=TOKEN)

palavras = [
    "headset",
    "webcam",
    "ssd",
    "memória ram"
]

enviados = set()

def buscar_pncp():
    url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"

    resposta = requests.get(url)

    if resposta.status_code == 200:
        dados = resposta.json().get("data", [])

        for item in dados:
            texto = str(item).lower()

            for palavra in palavras:
                if palavra in texto:

                    id_item = item.get("numeroControlePNCP")

                    if id_item not in enviados:
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

while True:
    try:
        buscar_pncp()

    except Exception as e:
        print(e)

    time.sleep(300)