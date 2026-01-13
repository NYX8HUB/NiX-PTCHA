from flask import Flask, Response, request, jsonify
from flask_cors import CORS
from PIL import Image, ImageDraw, ImageFont
import io
import time
import hashlib
import hmac
import random
import json
import base64
import os

app = Flask(__name__)
CORS(app)

SECRET_KEY = b"SuaCha32r532rfte4gvve5t3veSupafsq321rftIsso123"

# --- FRONTEND (JS) ---
JS_TEMPLATE = """
(function() {
    console.log("[Captcha] Iniciando modo Imagem...");
    const API_BASE = "__API_URL__";

    const style = document.createElement('style');
    style.innerHTML = `
        .my-captcha { 
            background: #f9f9f9; border: 1px solid #d3d3d3; border-radius: 4px; 
            width: 300px; padding: 10px; display: flex; align-items: center; 
            font-family: Roboto, Arial, sans-serif; user-select: none; position: relative;
        }
        .my-captcha-check {
            width: 24px; height: 24px; border: 2px solid #c1c1c1; border-radius: 2px;
            cursor: pointer; background: #fff; margin-right: 12px; transition: all 0.2s;
        }
        .my-captcha-check.checked { 
            background: #009688; border-color: #009688;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='white' width='18px' height='18px'%3E%3Cpath d='M0 0h24v24H0z' fill='none'/%3E%3Cpath d='M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z'/%3E%3C/svg%3E");
            background-position: center; background-repeat: no-repeat;
        }
        /* Estilo do Modal com Imagem */
        .captcha-modal {
            position: absolute; top: 110%; left: 0; background: white; 
            border: 1px solid #ccc; padding: 15px; box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            z-index: 9999; display: none; width: 280px; border-radius: 5px; text-align: center;
        }
        .captcha-img {
            display: block; margin: 0 auto 10px auto; border: 1px solid #eee;
            width: 100%; height: auto; border-radius: 3px;
        }
        .captcha-modal input { width: 100%; padding: 8px; margin-bottom: 10px; box-sizing: border-box; border: 1px solid #ddd; border-radius: 3px;}
        .captcha-modal button { 
            background: #4285f4; color: white; border: none; padding: 8px 16px; 
            cursor: pointer; border-radius: 3px; font-weight: bold; width: 100%;
        }
        #c-msg { font-size: 12px; margin-top: 8px; display: block; color: #666;}
    `;
    document.head.appendChild(style);

    let mouseTrace = [];
    document.addEventListener('mousemove', (e) => {
        if(mouseTrace.length < 50) mouseTrace.push([e.clientX, e.clientY]);
    });

    function initCaptcha() {
        const containers = document.querySelectorAll('.g-recaptcha');
        if (containers.length === 0) return;

        containers.forEach(box => {
            if(box.innerHTML.trim() !== "") return;

            // HTML AGORA TEM UMA TAG IMG
            box.innerHTML = `
                <div class="my-captcha">
                    <div class="my-captcha-check" id="c-box"></div>
                    <span style="font-size: 14px; color: #555;">Não sou um robô</span>
                    
                    <div class="captcha-modal" id="c-modal">
                        <p style="font-size:13px; margin-bottom:5px;">Digite os caracteres da imagem:</p>
                        
                        <img id="c-img" class="captcha-img" alt="Carregando..." />
                        
                        <input type="text" id="c-input" placeholder="Resposta" autocomplete="off">
                        <button id="c-btn">VERIFICAR</button>
                        <span id="c-msg"></span>
                    </div>
                </div>
                <input type="hidden" name="g-recaptcha-response" id="c-token">
            `;

            const checkbox = box.querySelector('#c-box');
            const modal = box.querySelector('#c-modal');
            const imgEl = box.querySelector('#c-img');
            const inputBtn = box.querySelector('#c-btn');
            const inputField = box.querySelector('#c-input');
            const msg = box.querySelector('#c-msg');
            const hiddenInput = box.querySelector('#c-token');
            let currentToken = "";

            checkbox.addEventListener('click', async () => {
                if (checkbox.classList.contains('checked')) return;
                
                modal.style.display = 'block';
                msg.innerText = "Gerando imagem...";
                imgEl.src = ""; // Limpa anterior
                
                try {
                    const req = await fetch(`${API_BASE}/get-challenge`);
                    const data = await req.json();
                    
                    // Define a imagem via Base64 recebido do Python
                    imgEl.src = "data:image/png;base64," + data.image;
                    
                    currentToken = data.token;
                    msg.innerText = "";
                    inputField.value = "";
                    inputField.focus();
                } catch(e) {
                    msg.innerText = "Erro ao carregar imagem.";
                }
            });

            inputBtn.addEventListener('click', async (e) => {
                e.preventDefault();
                msg.innerText = "Validando...";
                
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
                        hiddenInput.value = "TOKEN_VALIDO_IMAGEM"; 
                    } else {
                        msg.innerText = "Errou! Tente novamente.";
                        msg.style.color = "red";
                        inputField.value = "";
                        
                        // Opcional: Recarregar imagem se errar
                        checkbox.click(); 
                    }
                } catch (e) { msg.innerText = "Erro ao validar."; }
            });
        });
    }

    if (document.readyState === "complete" || document.readyState === "interactive") {
        setTimeout(initCaptcha, 10);
    } else {
        document.addEventListener("DOMContentLoaded", initCaptcha);
    }
})();
"""

# --- BACKEND COM GERAÇÃO DE IMAGEM ---

def gerar_assinatura(dados):
    msg = json.dumps(dados, sort_keys=True).encode()
    return hmac.new(SECRET_KEY, msg, hashlib.sha256).hexdigest()

def criar_imagem_captcha(texto):
    """Gera uma imagem com ruído e texto usando Pillow"""
    width, height = 200, 70
    # Cria fundo branco
    image = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    
    # Adiciona ruído (linhas aleatórias) para confundir robôs
    for _ in range(15):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        cor = (random.randint(150, 200), random.randint(150, 200), random.randint(150, 200))
        draw.line([(x1, y1), (x2, y2)], fill=cor, width=2)
        
    # Adiciona pontos de sujeira
    for _ in range(100):
        xy = (random.randint(0, width), random.randint(0, height))
        draw.point(xy, fill=(100, 100, 100))

    # Desenha o texto
    # Nota: Na Vercel não temos fontes .ttf instaladas por padrão, 
    # então usaremos a fonte padrão do Pillow que é simples mas funciona.
    # Para melhorar, você pode enviar um arquivo .ttf junto com o projeto.
    try:
        # Tenta aumentar um pouco a fonte padrão se possível
        # ou carrega padrão
        font = ImageFont.load_default() 
    except:
        font = None

    # Desenha o texto centralizado (aproximado)
    # Como a fonte padrão é pequena, vamos desenhar espalhado
    x_pos = 20
    for char in texto:
        # Cor escura aleatória para o texto
        text_color = (random.randint(0, 100), random.randint(0, 100), random.randint(0, 100))
        # Desenha caractere
        draw.text((x_pos, 25), char, font=font, fill=text_color)
        x_pos += 25 # Espaçamento

    # Salva na memória
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    # Converte para base64
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return img_str

@app.route('/api.js')
def servir_script():
    api_url = request.url_root.rstrip('/')
    js_final = JS_TEMPLATE.replace('__API_URL__', api_url)
    return Response(js_final, mimetype='application/javascript')

@app.route('/get-challenge', methods=['GET'])
def get_challenge():
    # 1. Gera código aleatório (Letras e Números)
    codigo = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=5))
    
    # 2. Cria a imagem desse código
    imagem_base64 = criar_imagem_captcha(codigo)
    
    # 3. Prepara o token de segurança
    dados = {
        "ans": codigo,
        "ts": time.time(),
        "salt": random.randint(1000, 9999)
    }
    assinatura = gerar_assinatura(dados)
    token_b64 = base64.urlsafe_b64encode(json.dumps(dados).encode()).decode()
    
    return jsonify({
        "image": imagem_base64, # Enviamos a imagem em vez da pergunta
        "token": f"{token_b64}.{assinatura}"
    })

@app.route('/verify', methods=['POST'])
def verify():
    data = request.json
    if not data: return jsonify({"success": False})

    # Validações padrão (Mouse, Token, etc)
    user_ans = data.get('answer', '').strip().upper() # Transforma em maiúscula
    full_token = data.get('token', '')
    mouse_data = data.get('mouse_trace', [])

    if len(mouse_data) < 2:
        return jsonify({"success": False, "error": "Bot detectado."})

    try:
        token_b64, signature = full_token.split('.')
        dados = json.loads(base64.urlsafe_b64decode(token_b64).decode())
        
        if gerar_assinatura(dados) != signature:
            return jsonify({"success": False, "error": "Token inválido."})
            
        if user_ans == dados['ans']:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Código incorreto."})
            
    except:
        return jsonify({"success": False, "error": "Erro servidor."})

if __name__ == '__main__':
    app.run(debug=True)
