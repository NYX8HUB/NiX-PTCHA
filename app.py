from flask import Flask, Response, request, jsonify
from flask_cors import CORS
import time
import hashlib
import hmac
import random
import json
import base64

app = Flask(__name__)
CORS(app)

# --- SEGURANÇA: CHAVE SECRETA ---
# Na prática, use variáveis de ambiente, mas para este teste pode ficar aqui.
SECRET_KEY = b"Suwsefrtw34rq312drf"

# --- TEMPLATE DO JAVASCRIPT (FRONTEND) ---
# O código está aqui dentro para garantir que o Python sempre o encontre.
JS_TEMPLATE = """
(function() {
    console.log("[Captcha] Script Iniciado!"); // Log para depuração

    // URL da API será injetada pelo Python
    const API_BASE = "__API_URL__";

    // 1. INJETAR CSS
    const style = document.createElement('style');
    style.innerHTML = `
        .my-captcha { 
            background: #f9f9f9; border: 1px solid #d3d3d3; border-radius: 4px; 
            width: 300px; padding: 10px; display: flex; align-items: center; 
            font-family: Roboto, Arial, sans-serif; user-select: none; position: relative;
            box-shadow: 0 1px 1px rgba(0,0,0,0.1);
        }
        .my-captcha-check {
            width: 24px; height: 24px; border: 2px solid #c1c1c1; border-radius: 2px;
            cursor: pointer; background: #fff; margin-right: 12px; transition: all 0.2s;
        }
        .my-captcha-check:hover { border-color: #b2b2b2; }
        .my-captcha-check.checked { 
            background: #009688; border-color: #009688; 
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='white' width='18px' height='18px'%3E%3Cpath d='M0 0h24v24H0z' fill='none'/%3E%3Cpath d='M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z'/%3E%3C/svg%3E");
            background-position: center; background-repeat: no-repeat;
        }
        .captcha-modal {
            position: absolute; top: 110%; left: 0; background: white; 
            border: 1px solid #ccc; padding: 15px; box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            z-index: 9999; display: none; width: 280px; border-radius: 5px;
        }
        .captcha-modal p { margin: 0 0 10px; font-size: 14px; color: #333; }
        .captcha-modal input { width: 100%; padding: 8px; margin-bottom: 10px; box-sizing: border-box; border: 1px solid #ddd; border-radius: 3px;}
        .captcha-modal button { 
            background: #4285f4; color: white; border: none; padding: 8px 16px; 
            cursor: pointer; border-radius: 3px; font-weight: bold; width: 100%;
        }
        .captcha-modal button:hover { background: #357ae8; }
        #c-msg { font-size: 12px; margin-top: 8px; text-align: center; display: block; min-height: 15px;}
    `;
    document.head.appendChild(style);

    // 2. MONITORAMENTO DE MOUSE (Antibot)
    let mouseTrace = [];
    document.addEventListener('mousemove', (e) => {
        if(mouseTrace.length < 50) {
            mouseTrace.push([e.clientX, e.clientY]);
        }
    });

    // 3. FUNÇÃO PRINCIPAL
    function initCaptcha() {
        console.log("[Captcha] Procurando divs .g-recaptcha...");
        const containers = document.querySelectorAll('.g-recaptcha');
        
        if (containers.length === 0) {
            console.warn("[Captcha] Nenhuma div encontrada. Verifique seu HTML.");
            return;
        }

        console.log("[Captcha] Encontrados: " + containers.length);

        containers.forEach(box => {
            if(box.innerHTML.trim() !== "") return; // Já renderizado

            // Desenha o Widget
            box.innerHTML = `
                <div class="my-captcha">
                    <div class="my-captcha-check" id="c-box"></div>
                    <span style="font-size: 14px; color: #555;">Não sou um robô</span>
                    
                    <div class="captcha-modal" id="c-modal">
                        <p id="c-question">Carregando desafio...</p>
                        <input type="text" id="c-input" placeholder="Sua resposta" autocomplete="off">
                        <button id="c-btn">VERIFICAR</button>
                        <span id="c-msg"></span>
                    </div>
                </div>
                <input type="hidden" name="g-recaptcha-response" id="c-token">
            `;

            const checkbox = box.querySelector('#c-box');
            const modal = box.querySelector('#c-modal');
            const questionTxt = box.querySelector('#c-question');
            const inputBtn = box.querySelector('#c-btn');
            const inputField = box.querySelector('#c-input');
            const msg = box.querySelector('#c-msg');
            const hiddenInput = box.querySelector('#c-token');
            
            let currentToken = "";

            // Clique no Checkbox
            checkbox.addEventListener('click', async () => {
                if (checkbox.classList.contains('checked')) return;
                
                modal.style.display = 'block';
                msg.innerText = "Conectando...";
                msg.style.color = "#666";
                
                try {
                    const req = await fetch(`${API_BASE}/get-challenge`);
                    const data = await req.json();
                    
                    questionTxt.innerText = data.question;
                    currentToken = data.token;
                    msg.innerText = "";
                    inputField.value = "";
                    inputField.focus();
                } catch(e) {
                    console.error(e);
                    msg.innerText = "Erro de conexão.";
                    msg.style.color = "red";
                }
            });

            // Clique no Botão Verificar
            inputBtn.addEventListener('click', async (e) => {
                e.preventDefault();
                msg.innerText = "Validando...";
                msg.style.color = "#666";
                
                const payload = {
                    token: currentToken,
                    answer: inputField.value,
                    mouse_trace: mouseTrace
                };

                try {
                    const req = await fetch(`${API_BASE}/verify`, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(payload)
                    });
                    
                    const resp = await req.json();
                    
                    if (resp.success) {
                        modal.style.display = 'none';
                        checkbox.classList.add('checked');
                        // Preenche o input invisível para o formulário funcionar
                        hiddenInput.value = "TOKEN_VALIDO_ASSINADO"; 
                    } else {
                        msg.innerText = resp.error || "Resposta incorreta.";
                        msg.style.color = "red";
                        inputField.value = "";
                        inputField.focus();
                    }
                } catch (e) {
                    msg.innerText = "Erro ao validar.";
                    msg.style.color = "red";
                }
            });
        });
    }

    // 4. INICIALIZAÇÃO SEGURA
    // Garante que roda mesmo se o script carregar depois do HTML
    if (document.readyState === "complete" || document.readyState === "interactive") {
        setTimeout(initCaptcha, 10);
    } else {
        document.addEventListener("DOMContentLoaded", initCaptcha);
    }
})();
"""

# --- FUNÇÕES UTILITÁRIAS (BACKEND) ---

def gerar_assinatura(dados):
    """Gera hash HMAC para garantir integridade"""
    msg = json.dumps(dados, sort_keys=True).encode()
    return hmac.new(SECRET_KEY, msg, hashlib.sha256).hexdigest()

def gerar_desafio():
    """Cria um desafio aleatório"""
    tipo = random.choice(['math', 'reverse', 'text'])
    
    if tipo == 'math':
        a = random.randint(1, 9)
        b = random.randint(1, 9)
        pergunta = f"Quanto é {a} + {b}?"
        resposta = str(a + b)
    elif tipo == 'reverse':
        cod = "".join(random.choices("ABCDEF", k=4))
        pergunta = f"Digite invertido: {cod}"
        resposta = cod[::-1]
    else:
        cod = "".join(random.choices("23456789", k=4))
        pergunta = f"Digite o código: {cod}"
        resposta = cod
        
    return pergunta, resposta

# --- ROTAS DA API ---

@app.route('/api.js')
def servir_script():
    """Rota que entrega o arquivo JS modificado dinamicamente"""
    # Descobre a URL do seu site na Vercel automaticamente
    api_url = request.url_root.rstrip('/')
    
    # Substitui o placeholder pela URL real
    js_final = JS_TEMPLATE.replace('__API_URL__', api_url)
    
    # Retorna como Javascript
    return Response(js_final, mimetype='application/javascript')

@app.route('/get-challenge', methods=['GET'])
def get_challenge():
    """Gera o desafio e entrega o token assinado"""
    pergunta, resposta_correta = gerar_desafio()
    
    dados = {
        "ans": resposta_correta,
        "ts": time.time(),
        "salt": random.randint(1000, 9999)
    }
    
    assinatura = gerar_assinatura(dados)
    
    # Cria o token: Base64(Dados) + "." + Assinatura
    token_b64 = base64.urlsafe_b64encode(json.dumps(dados).encode()).decode()
    token_completo = f"{token_b64}.{assinatura}"
    
    return jsonify({
        "question": pergunta,
        "token": token_completo
    })

@app.route('/verify', methods=['POST'])
def verify():
    """Valida a resposta do usuário"""
    data = request.json
    if not data:
        return jsonify({"success": False, "error": "Sem dados"})

    full_token = data.get('token', '')
    user_answer = data.get('answer', '').strip().lower()
    mouse_data = data.get('mouse_trace', [])

    # 1. Checagem de Bot (Mouse)
    if len(mouse_data) < 2: 
        # Aceita pouco movimento se for mobile, mas 0 é suspeito
        return jsonify({"success": False, "error": "Movimento suspeito."})

    try:
        # Separa o token da assinatura
        token_b64, signature_recebida = full_token.split('.')
        
        # Decodifica os dados
        dados_json = base64.urlsafe_b64decode(token_b64).decode()
        dados = json.loads(dados_json)
        
        # 2. Checagem de Integridade (Assinatura)
        assinatura_real = gerar_assinatura(dados)
        if signature_recebida != assinatura_real:
            return jsonify({"success": False, "error": "Token inválido."})
            
        # 3. Checagem de Tempo
        tempo_passado = time.time() - dados['ts']
        if tempo_passado > 120: # Expira em 2 minutos
            return jsonify({"success": False, "error": "Tempo expirado."})

        # 4. Checagem da Resposta
        if user_answer == dados['ans'].lower():
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Resposta incorreta."})
            
    except Exception as e:
        print(f"Erro na validação: {e}")
        return jsonify({"success": False, "error": "Erro de validação."})

# Apenas para rodar localmente. Na Vercel, isso é ignorado.
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
