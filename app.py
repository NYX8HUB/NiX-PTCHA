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
import math
import platform

app = Flask(__name__)
CORS(app)

SECRET_KEY = b"SuaChaveSuperSecreta_MudeIsso123"

# --- FRONTEND (CSS Ajustado para imagem Gigante) ---
JS_TEMPLATE = """
(function() {
    const API_BASE = "__API_URL__";

    const style = document.createElement('style');
    style.innerHTML = `
        .my-captcha { 
            background: #fff; border: 1px solid #d1d5db; border-radius: 8px; 
            width: 320px; padding: 12px; display: flex; align-items: center; 
            font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; 
            user-select: none; position: relative;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .my-captcha:hover { border-color: #6b7280; }
        
        .my-captcha-check {
            width: 28px; height: 28px; border: 2px solid #c1c1c1; border-radius: 5px;
            cursor: pointer; background: #fff; margin-right: 15px; flex-shrink: 0;
            transition: all 0.2s;
        }
        .my-captcha-check.checked { 
            background: #10b981; border-color: #10b981;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='white' width='22px' height='22px'%3E%3Cpath d='M0 0h24v24H0z' fill='none'/%3E%3Cpath d='M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z'/%3E%3C/svg%3E");
            background-position: center; background-repeat: no-repeat;
        }
        
        .captcha-modal {
            position: absolute; top: 50%; left: 50%; transform: translate(-50%, -20px);
            background: white; 
            width: 450px; /* Aumentado para caber a imagem nova */
            max-width: 90vw;
            border-radius: 12px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.2), 0 0 0 1px rgba(0,0,0,0.05);
            z-index: 10000; display: none; overflow: hidden;
            font-family: 'Segoe UI', Roboto, sans-serif;
        }
        
        .modal-header {
            background: #4f46e5; color: white; padding: 14px;
            font-size: 15px; font-weight: 600; text-align: center;
        }
        
        .modal-body { padding: 20px; text-align: center; }
        
        .captcha-img {
            display: block; margin: 0 auto 15px auto; 
            border-radius: 8px; border: 1px solid #e5e7eb;
            width: 100%; height: auto; 
            box-shadow: inset 0 0 10px rgba(0,0,0,0.05);
        }
        
        .captcha-input { 
            width: 100%; padding: 12px; margin-bottom: 15px; 
            box-sizing: border-box; border: 1px solid #d1d5db; 
            border-radius: 8px; font-size: 18px; outline: none;
            text-align: center; letter-spacing: 3px; font-weight: bold;
            text-transform: uppercase;
        }
        .captcha-input:focus { border-color: #4f46e5; box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.2); }
        
        .captcha-btn { 
            background: #4f46e5; color: white; border: none; padding: 12px 0; 
            cursor: pointer; border-radius: 8px; font-weight: 700; width: 100%;
            font-size: 15px; transition: background 0.2s;
        }
        .captcha-btn:hover { background: #4338ca; }
        
        .loader { border: 3px solid #f3f3f3; border-top: 3px solid #4f46e5; border-radius: 50%; width: 24px; height: 24px; animation: spin 1s linear infinite; margin: 0 auto; display: none;}
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        
        #c-msg { font-size: 13px; margin-top: 10px; display: block; min-height: 18px; color: #dc2626; font-weight: 500;}
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
                        <span style="font-size: 15px; font-weight: 600; color: #1f2937;">Não sou um robô</span>
                        <span style="font-size: 11px; color: #6b7280;">Protected by AuthShield</span>
                    </div>
                    
                    <div class="captcha-modal" id="c-modal">
                        <div class="modal-header">Verificação de Segurança</div>
                        <div class="modal-body">
                            <div class="loader" id="c-loader"></div>
                            <img id="c-img" class="captcha-img" alt="" style="display:none;" />
                            <p id="c-instrucao" style="font-size:14px; margin:0 0 10px 0; color:#374151; font-weight:500;">...</p>
                            
                            <input type="text" id="c-input" class="captcha-input" placeholder="RESPOSTA" autocomplete="off">
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
                    
                    if(data.type === 'math') {
                        instrucao.innerText = "Resolva o cálculo:";
                        inputField.placeholder = "Resultado";
                    } else {
                        instrucao.innerText = "Digite os caracteres da imagem:";
                        inputField.placeholder = "TEXTO";
                    }
                    
                    currentToken = data.token;
                    inputField.value = "";
                    inputField.focus();
                } catch(e) { msg.innerText = "Erro ao conectar."; }
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
                        hiddenInput.value = "TOKEN_VERIFICADO_OK"; 
                    } else {
                        msg.innerText = "Incorreto. Tente novamente.";
                        inputBtn.innerText = "VERIFICAR";
                        inputField.value = "";
                        inputField.focus();
                        checkbox.click(); // Recarrega novo desafio
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

# --- BACKEND (LÓGICA DO CAPTCHA) ---

def gerar_assinatura(dados):
    msg = json.dumps(dados, sort_keys=True).encode()
    return hmac.new(SECRET_KEY, msg, hashlib.sha256).hexdigest()

def get_best_font(size):
    """
    Tenta carregar fonte e avisa no terminal qual foi carregada.
    """
    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    
    # LISTA DE FONTES PARA TENTAR (Prioridade)
    fontes_para_tentar = [
        # 1. Arquivo na mesma pasta (Ideal)
        os.path.join(diretorio_atual, 'font.ttf'), 
        
        # 2. Windows (Caminhos comuns)
        "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\segoeui.ttf",
        "C:\\Windows\\Fonts\\calibri.ttf",
        
        # 3. Linux (Caminhos comuns)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/TTF/Arial.ttf"
    ]

    for fonte_path in fontes_para_tentar:
        try:
            # Tenta carregar
            loaded_font = ImageFont.truetype(fonte_path, size)
            return loaded_font
        except OSError:
            # Se falhar (arquivo não existe), tenta o próximo
            continue
            
    # SE CHEGOU AQUI, DEU RUIM
    print("---------------------------------------------------")
    print("AVISO: NENHUMA FONTE ENCONTRADA. USANDO PADRÃO.")
    print("O TEXTO FICARÁ PEQUENO. COPIE UM ARQUIVO .TTF PARA A PASTA.")
    print("---------------------------------------------------")
    return ImageFont.load_default()

def aplicar_distorcao_onda(imagem):
    width, height = imagem.size
    nova_imagem = Image.new("RGBA", (width, height), (0,0,0,0))
    
    amplitude = random.randint(5, 9) 
    frequencia = random.uniform(0.03, 0.05)
    
    for x in range(width):
        offset_y = int(amplitude * math.sin(2 * math.pi * frequencia * x))
        coluna = imagem.crop((x, 0, x + 1, height))
        dest_y = max(0, offset_y)
        nova_imagem.paste(coluna, (x, dest_y))
        
    return nova_imagem

def criar_imagem_distorcida(texto):
    # 1. Tamanho da imagem (Largo e Alto)
    width, height = 520, 180 
    
    background = Image.new('RGB', (width, height), color=(245, 245, 245))
    draw_bg = ImageDraw.Draw(background)
    
    # Ruído de fundo
    for _ in range(40):
        x1, y1 = random.randint(0, width), random.randint(0, height)
        x2, y2 = random.randint(0, width), random.randint(0, height)
        cor = (random.randint(180, 220), random.randint(180, 220), random.randint(180, 220))
        draw_bg.line([(x1, y1), (x2, y2)], fill=cor, width=3)
    
    txt_layer = Image.new('RGBA', (width, height), (255, 255, 255, 0))
    
    # --- AQUI É O TAMANHO DA FONTE (110) ---
    font = get_best_font(110)

    # Cálculo para centralizar
    estimativa_largura = len(texto) * 75
    start_x = (width - estimativa_largura) / 2
    curr_x = start_x if start_x > 0 else 10
    
    for char in texto:
        char_img = Image.new('RGBA', (150, 150), (0,0,0,0))
        char_draw = ImageDraw.Draw(char_img)
        
        cor = (random.randint(0, 80), random.randint(0, 80), random.randint(0, 120))
        
        # Desenha a letra
        char_draw.text((35, 10), char, font=font, fill=cor)
        
        # Rotaciona
        rotacao = random.randint(-20, 20)
        char_rot = char_img.rotate(rotacao, expand=1, resample=Image.BICUBIC)
        
        offset_y = random.randint(10, 40)
        
        txt_layer.paste(char_rot, (int(curr_x), offset_y), char_rot)
        curr_x += 75 
        
    txt_layer_distorted = aplicar_distorcao_onda(txt_layer)
    final_img = Image.alpha_composite(background.convert('RGBA'), txt_layer_distorted)
    
    # Ruído frontal
    draw_final = ImageDraw.Draw(final_img)
    for _ in range(500):
        xy = (random.randint(0, width), random.randint(0, height))
        draw_final.point(xy, fill=(100, 100, 100))
        
    buffer = io.BytesIO()
    final_img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

# --- ROTAS ---

@app.route('/api.js')
def servir_script():
    api_url = request.url_root.rstrip('/')
    js_final = JS_TEMPLATE.replace('__API_URL__', api_url)
    return Response(js_final, mimetype='application/javascript')

@app.route('/get-challenge', methods=['GET'])
def get_challenge():
    tipos = ['num', 'char', 'mix', 'math']
    escolha = random.choice(tipos)
    
    texto_img = ""
    resposta = ""
    
    if escolha == 'math':
        op = random.choice(['+', '-', '*'])
        if op == '+':
            a, b = random.randint(1, 15), random.randint(1, 15)
            texto_img = f"{a} + {b}"
            resposta = str(a + b)
        elif op == '-':
            a, b = random.randint(5, 20), random.randint(1, 10)
            if a < b: a, b = b, a 
            texto_img = f"{a} - {b}"
            resposta = str(a - b)
        elif op == '*':
            a, b = random.randint(2, 9), random.randint(2, 5)
            texto_img = f"{a} x {b}"
            resposta = str(a * b)
    else:
        if escolha == 'num': pool = "23456789"
        elif escolha == 'char': pool = "ACEFHJKLMNPRTXY"
        else: pool = "ACEFHKMNP234579"
        texto_img = "".join(random.choices(pool, k=5))
        resposta = texto_img

    imagem_b64 = criar_imagem_distorcida(texto_img)
    
    dados = { "ans": resposta, "ts": time.time(), "salt": random.randint(1, 9999) }
    token = f"{base64.urlsafe_b64encode(json.dumps(dados).encode()).decode()}.{gerar_assinatura(dados)}"
    
    return jsonify({ "image": imagem_b64, "token": token, "type": escolha })

@app.route('/verify', methods=['POST'])
def verify():
    data = request.json
    try:
        user_ans = data.get('answer', '').strip().upper()
        user_ans = user_ans.replace(" ", "")
        
        token_b64, sig = data.get('token', '').split('.')
        dados = json.loads(base64.urlsafe_b64decode(token_b64).decode())
        
        if gerar_assinatura(dados) != sig: return jsonify({"success": False})
        
        if time.time() - dados['ts'] > 300: return jsonify({"success": False})
        
        if user_ans == dados['ans'].upper(): return jsonify({"success": True})
        
        return jsonify({"success": False})
    except:
        return jsonify({"success": False})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
