from flask import Flask, Response
from flask_cors import CORS
import os

app = Flask(__name__)
# Habilita CORS para permitir que qualquer site (ou arquivo local) use sua API
CORS(app)

@app.route('/api.js')
def servir_script():
    try:
        # Lê o conteúdo do seu arquivo de texto
        with open('codigo.txt', 'r', encoding='utf-8') as f:
            conteudo_js = f.read()

        # O TRUQUE: Retorna o texto avisando o navegador que é Javascript
        return Response(conteudo_js, mimetype='application/javascript')
        
    except FileNotFoundError:
        return "Erro: arquivo codigo.txt não encontrado", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
