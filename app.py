from flask import Flask, Response, request, jsonify
from flask_cors import CORS
import os
import time
import hashlib
import hmac
import random
import json
import base64

app = Flask(__name__)
CORS(app)

# SEGURANÇA: Chave secreta para assinar os tokens (Ninguém descobre isso)
SECRET_KEY = b"SuaChaveSuperSecreta_MudeIsso123"

# --- UTILITÁRIOS DE SEGURANÇA ---
def gerar_assinatura(dados):
    """Cria uma assinatura HMAC para garantir que os dados não foram alterados"""
    msg = json.dumps(dados, sort_keys=True).encode()
    return hmac.new(SECRET_KEY, msg, hashlib.sha256).hexdigest()

def gerar_desafio():
    """Gera um desafio aleatório (Variados)"""
    tipo = random.choice(['math', 'text', 'reverse'])
    
    if tipo == 'math':
        a = random.randint(1, 10)
        b = random.randint(1, 10)
        pergunta = f"Quanto é {a} + {b}?"
        resposta = str(a + b)
    elif tipo == 'reverse':
        cod = "".join(random.choices("ABCDEF123456", k=4))
        pergunta = f"Digite invertido: {cod}"
        resposta = cod[::-1]
    else:
        cod = "".join(random.choices("XYZ789", k=4))
        pergunta = f"Digite o código: {cod}"
        resposta = cod
        
    return pergunta, resposta

# --- ROTAS ---

@app.route('/api.js')
def servir_script():
    """Entrega o Javascript (Frontend)"""
    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    caminho_arquivo = os.path.join(diretorio_atual, 'codigo.txt')
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            js = f.read()
        # Injeta a URL da API dinamicamente no JS
        api_url = request.url_root.rstrip('/')
        js = js.replace('__API_URL__', api_url)
        return Response(js, mimetype='application/javascript')
    except:
        return "Erro ao carregar script", 500

@app.route('/get-challenge', methods=['GET'])
def get_challenge():
    """Cria o desafio e envia criptografado"""
    pergunta, resposta_correta = gerar_desafio()
    timestamp = time.time()
    
    # Payload que será assinado
    dados = {
        "ans": resposta_correta,
        "ts": timestamp,
        "salt": random.randint(1000, 9999)
    }
    
    signature = gerar_assinatura(dados)
    
    # Encodar payload para enviar ao front (mas o front não consegue forjar sem a KEY)
    token = base64.urlsafe_b64encode(json.dumps(dados).encode()).decode()
    
    return jsonify({
        "question": pergunta,
        "token": f"{token}.{signature}" # Token.Assinatura
    })

@app.route('/verify', methods=['POST'])
def verify():
    """Verifica se o humano acertou"""
    data = request.json
    user_answer = data.get('answer', '').strip().lower()
    full_token = data.get('token', '')
    mouse_data = data.get('mouse_trace', []) # Verificação de Bot
    
    # 1. VERIFICAÇÃO DE BOT (Movimento do Mouse)
    # Bots costumam ter 0 movimentos ou movimentos perfeitamente retos.
    if len(mouse_data) < 5:
        return jsonify({"success": False, "error": "Movimento de mouse suspeito (Bot detectado)."})

    try:
        token_b64, signature_recebida = full_token.split('.')
        
        # Decodifica os dados
        dados_json = base64.urlsafe_b64decode(token_b64).decode()
        dados = json.loads(dados_json)
        
        # 2. VERIFICAÇÃO DE INTEGRIDADE (Hacking)
        # Recalcula a assinatura. Se for diferente, o usuário tentou hackear o token.
        assinatura_real = gerar_assinatura(dados)
        if signature_recebida != assinatura_real:
            return jsonify({"success": False, "error": "Token inválido ou adulterado."})
            
        # 3. VERIFICAÇÃO DE TEMPO (Bots são rápidos demais)
        tempo_passado = time.time() - dados['ts']
        if tempo_passado < 1.0: # Menos de 1 segundo
            return jsonify({"success": False, "error": "Respondido muito rápido (Bot)."})
        if tempo_passado > 120: # Mais de 2 minutos
            return jsonify({"success": False, "error": "Tempo expirado."})

        # 4. VERIFICAÇÃO DA RESPOSTA
        if user_answer == dados['ans'].lower():
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Resposta incorreta."})
            
    except Exception as e:
        return jsonify({"success": False, "error": "Erro de validação."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
