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

SECRET_KEY = b"SuaChaveSuperSecreta_MudeIsso123"

# --- FRONTEND (JS + CSS BONITO) ---
JS_TEMPLATE = """
(function() {
    const API_BASE = "__API_URL__";

    const style = document.createElement('style');
    style.innerHTML = `
        /* Estilo do Widget (Botão inicial) */
        .my-captcha { 
            background: #fff; border: 1px solid #d1d5db; border-radius: 6px; 
            width: 300px; padding: 12px; display: flex; align-items: center; 
            font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; 
            user-select: none; position: relative;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
            transition: border-color 0.2s;
        }
        .my-captcha:hover { border-color: #9ca3af; }
        
        .my-captcha-check {
            width: 26px; height: 26px; border: 2px solid #c1c1c1; border-radius: 4px;
            cursor: pointer; background: #fff; margin-right: 14px; transition: all 0.2s;
            position: relative;
        }
        .my-captcha-check:hover { border-color: #a1a1a1; }
        .my-captcha-check.checked { 
            background: #10b981; border-color: #10b981;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='white' width='20px' height='20px'%3E%3Cpath d='M0 0h24v24H0z' fill='none'/%3E%3Cpath d='M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z'/%3E%3C/svg%3E");
            background-position: center; background-repeat: no-repeat;
        }
        
        /* Estilo do Modal (Janela do Desafio) */
        .captcha-modal {
            position: absolute; top: 50%; left: 50%; transform: translate(-50%, -15px);
            background: white; width: 320px;
            border-radius: 12px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.15), 0 0 0 1px rgba(0,0,0,0.05);
            z-index: 10000; display: none; overflow: hidden;
            font-family: 'Segoe UI', Roboto, sans-serif;
        }
        
        .modal-header {
            background: #2563eb; color: white; padding: 12px 15px;
            font-size: 14px; font-weight: 600; text-align: center;
        }
        
        .modal-body { padding: 20px; text-align: center; }
        
        .captcha-img {
            display: block; margin: 0 auto 15px auto; 
            border-radius: 6px; border: 1px solid #e5e7eb;
            width: 100%; max-width: 280px; height: auto;
        }
        
        .captcha-input { 
            width: 100%; padding: 10px; margin-bottom: 12px; 
            box-sizing: border-box; border: 1px solid #d1d5db; 
            border-radius: 6px; font-size: 16px; outline: none;
            text-align: center; letter-spacing: 2px;
            transition: border 0.2s;
        }
        .captcha-input:focus { border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37,99,235,0.1); }
        
        .captcha-btn { 
            background: #2563eb; color: white; border: none; padding: 10px 0; 
            cursor: pointer; border-radius: 6px; font-weight: 600; width: 100%;
            font-size: 14px; transition: background 0.2s;
        }
        .captcha-btn:hover { background: #1d4ed8; }
        
        #c-msg { font-size: 13px; margin-top: 10px; display: block; min-height: 18px; color: #dc2626;}
        
        /* Loading Spinner */
        .loader { border: 3px solid #f3f3f3; border-top: 3px solid #2563eb; border-radius: 50%; width: 20px; height: 20px; animation: spin 1s linear infinite; margin: 0 auto; display: none;}
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
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

            box.innerHTML = `
                <div class="my-captcha">
                    <div class="my-captcha-check" id="c-box"></div>
                    <div style="display:flex; flex-direction:column;">
                        <span style="font-size: 14px; font-weight: 500; color: #374151;">Não sou um robô</span>
                        <span style="font-size: 10px; color: #9ca3af;">Secure Verification</span>
                    </div>
                    
                    <div class="captcha-modal" id="c-modal">
                        <div class="modal-header">Verificação de Segurança</div>
                        <div class="modal-body">
                            <p id="c-instrucao" style="font-size:13px; margin:0 0 10px 0; color:#4b5563;">Resolva o desafio abaixo:</p>
                            
                            <div class="loader" id="c-loader"></div>
                            <img id="c-img" class="captcha-img" alt="" style="display:none;" />
                            
                            <input type="text" id="c-input" class="captcha-input" placeholder="Resposta" autocomplete="off">
                            <button id="c-btn" class="captcha-btn">VERIFICAR</button>
                            <span id="c-msg"></span>
                        </div>
                    </div>
                </div>
                <input type="hidden" name="g-recaptcha-response" id="c-token">
            `;

            const checkbox = box.querySelector('#c-box');
            const modal = box.querySelector('#c-modal');
            const imgEl = box.querySelector('#c-img');
            const loader = box.querySelector('#c-loader');
            const inputBtn = box.querySelector('#c-btn');
            const inputField = box.querySelector('#c-input');
            const msg = box.querySelector('#c-msg');
            const instrucao = box.querySelector('#c-instrucao');
            const hiddenInput = box.querySelector('#c-token');
            let currentToken = "";

            checkbox.addEventListener('click', async () => {
                if (checkbox.classList.contains('checked')) return;
                
                modal.style.display = 'block';
                imgEl.style.display = 'none';
                loader.style.display = 'block';
                msg.innerText = "";
                
                try {
                    const req = await fetch(`${API_BASE}/get-challenge`);
                    const data = await req.json();
                    
                    loader.style.display = 'none';
                    imgEl.style.display = 'block';
                    imgEl.src = "data:image/png;base64," + data.image;
                    
                    // Muda instrução dependendo do tipo
                    if(data.type === 'math') {
                        instrucao.innerText = "Resolva a conta na imagem:";
                        inputField.placeholder = "Resultado (ex: 10)";
                    } else {
                        instrucao.innerText = "Digite os caracteres da imagem:";
                        inputField.placeholder = "Caracteres";
                    }
                    
                    currentToken = data.token;
                    inputField.value = "";
                    inputField.focus();
                } catch(e) {
                    msg.innerText = "Erro ao carregar desafio.";
                }
            });

            inputBtn.addEventListener('click', async (e) => {
                e.preventDefault();
                inputBtn.innerText = "...";
                
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
                        hiddenInput.value = "TOKEN_VALIDO_V2"; 
                    } else {
                        msg.innerText = "Incorreto. Tente novamente.";
                        inputBtn.innerText = "VERIFICAR";
                        inputField.value = "";
                        inputField.focus();
                        // Opcional: recarregar desafio aqui se quiser ser rigoroso
                    }
                } catch (e) { 
                    msg.innerText = "Erro ao validar.";
                    inputBtn.innerText = "VERIFICAR";
                }
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

# --- BACKEND ---

def gerar_assinatura(dados):
    msg = json.dumps(dados, sort_keys=True).encode()
    return hmac.new(SECRET_KEY, msg, hashlib.sha256).hexdigest()

def criar_imagem_bonita(texto):
    """Gera uma imagem maior, mais legível e com fonte personalizada"""
    # Tamanho maior (300x100)
    width, height = 280, 90 
    image = Image.new('RGB', (width, height), color=(245, 247, 250)) # Fundo cinza bem claro
    draw = ImageDraw.Draw(image)
    
    # 1. Adiciona "Ruído" (Linhas e Pontos) para segurança
    for _ in range(20): # Linhas
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        cor = (random.randint(200, 230), random.randint(200, 230), random.randint(200, 230))
        draw.line([(x1, y1), (x2, y2)], fill=cor, width=2)

    for _ in range(150): # Pontos
        xy = (random.randint(0, width), random.randint(0, height))
        draw.point(xy, fill=(180, 180, 180))

    # 2. Carregar Fonte (Tenta carregar font.ttf, senão usa padrão)
    try:
        # Aumentamos o tamanho para 35!
        diretorio_atual = os.path.dirname(os.path.abspath(__file__))
        caminho_fonte = os.path.join(diretorio_atual, 'font.ttf')
        font = ImageFont.truetype(caminho_fonte, 40)
        has_font = True
    except:
        font = ImageFont.load_default()
        has_font = False
        print("AVISO: Arquivo 'font.ttf' não encontrado. Usando fonte padrão pequena.")

    # 3. Desenhar Texto Centralizado e Distorcido
    text_bbox = draw.textbbox((0, 0), texto, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    start_x = (width - text_width) / 2
    start_y = (height - text_height) / 2

    # Se tivermos a fonte bonita, desenhamos letra por letra levemente girada/movida
    if has_font:
        curr_x = (width - (len(texto) * 25)) / 2 # Calculo manual para espaçamento
        for char in texto:
            # Cor escura e variada
            cor_texto = (random.randint(20, 80), random.randint(20, 80), random.randint(20, 100))
            
            # Pequena variação na posição Y
            offset_y = random.randint(-5, 5)
            
            draw.text((curr_x, start_y + offset_y - 10), char, font=font, fill=cor_texto)
            curr_x += random.randint(30, 45) # Espaçamento entre letras
    else:
        # Fonte padrão (fallback)
        draw.text((start_x, start_y), texto, font=font, fill=(0,0,0))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

@app.route('/api.js')
def servir_script():
    api_url = request.url_root.rstrip('/')
    js_final = JS_TEMPLATE.replace('__API_URL__', api_url)
    return Response(js_final, mimetype='application/javascript')

@app.route('/get-challenge', methods=['GET'])
def get_challenge():
    # Sorteia o tipo de desafio
    tipo = random.choice(['num', 'char', 'mix', 'math'])
    
    if tipo == 'num':
        # APENAS NÚMEROS (5 dígitos)
        texto_exibido = "".join(random.choices("23456789", k=5))
        resposta_esperada = texto_exibido
        
    elif tipo == 'char':
        # APENAS LETRAS (5 letras)
        texto_exibido = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ", k=5))
        resposta_esperada = texto_exibido
        
    elif tipo == 'math':
        # DESAFIO MATEMÁTICO VISUAL
        val_a = random.randint(1, 9)
        val_b = random.randint(1, 9)
        texto_exibido = f"{val_a} + {val_b} = ?"
        resposta_esperada = str(val_a + val_b)
        
    else: # 'mix'
        # MISTURADO
        texto_exibido = "".join(random.choices("ABCDEFGH23456789", k=5))
        resposta_esperada = texto_exibido

    # Gera a imagem
    imagem_b64 = criar_imagem_bonita(texto_exibido)
    
    dados = {
        "ans": resposta_esperada,
        "ts": time.time(),
        "salt": random.randint(1000, 9999)
    }
    
    assinatura = gerar_assinatura(dados)
    token_b64 = base64.urlsafe_b64encode(json.dumps(dados).encode()).decode()
    
    return jsonify({
        "image": imagem_b64,
        "token": f"{token_b64}.{assinatura}",
        "type": tipo # Avisa o frontend qual o tipo para mudar a instrução
    })

@app.route('/verify', methods=['POST'])
def verify():
    data = request.json
    if not data: return jsonify({"success": False})

    user_ans = data.get('answer', '').strip().upper() # Ignora maiuscula/minuscula
    full_token = data.get('token', '')

    try:
        token_b64, signature = full_token.split('.')
        dados = json.loads(base64.urlsafe_b64decode(token_b64).decode())
        
        if gerar_assinatura(dados) != signature:
            return jsonify({"success": False, "error": "Token inválido."})
            
        if user_ans == dados['ans'].upper():
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Resposta incorreta."})
    except:
        return jsonify({"success": False, "error": "Erro servidor."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
