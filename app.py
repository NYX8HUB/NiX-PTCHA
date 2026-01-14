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

app = Flask(__name__)
CORS(app)

SECRET_KEY = b"SuaChaveSuperSecreta_MudeIsso123"

# --- FRONTEND (NIX-PTCHA) ---
JS_TEMPLATE = """
(function() {
    const API_BASE = "__API_URL__";

    const style = document.createElement('style');
    style.innerHTML = `
        .nix-captcha-box { 
            background: #fff; border: 1px solid #d1d5db; border-radius: 8px; 
            width: 320px; padding: 12px; display: flex; align-items: center; 
            font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; 
            user-select: none; position: relative;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .nix-captcha-box:hover { border-color: #6b7280; }
        
        .nix-check {
            width: 28px; height: 28px; border: 2px solid #c1c1c1; border-radius: 5px;
            cursor: pointer; background: #fff; margin-right: 15px; flex-shrink: 0;
            transition: all 0.2s;
        }
        .nix-check.checked { 
            background: #10b981; border-color: #10b981;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='white' width='22px' height='22px'%3E%3Cpath d='M0 0h24v24H0z' fill='none'/%3E%3Cpath d='M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z'/%3E%3C/svg%3E");
            background-position: center; background-repeat: no-repeat;
        }
        
        .nix-modal {
            position: absolute; top: 50%; left: 50%; transform: translate(-50%, -20px);
            background: white; 
            width: 450px; 
            max-width: 90vw;
            border-radius: 12px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.2), 0 0 0 1px rgba(0,0,0,0.05);
            z-index: 10000; display: none; overflow: hidden;
            font-family: 'Segoe UI', Roboto, sans-serif;
        }
        
        .nix-header {
            background: #4f46e5; color: white; padding: 14px;
            font-size: 15px; font-weight: 600; text-align: center;
        }
        
        .nix-body { padding: 20px; text-align: center; }
        
        .nix-img {
            display: block; margin: 0 auto 15px auto; 
            border-radius: 8px; border: 1px solid #e5e7eb;
            width: 100%; height: auto; 
            box-shadow: inset 0 0 10px rgba(0,0,0,0.05);
        }
        
        .nix-input { 
            width: 100%; padding: 12px; margin-bottom: 15px; 
            box-sizing: border-box; border: 1px solid #d1d5db; 
            border-radius: 8px; font-size: 18px; outline: none;
            text-align: center; letter-spacing: 3px; font-weight: bold;
            text-transform: uppercase;
        }
        .nix-input:focus { border-color: #4f46e5; box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.2); }
        
        .nix-btn { 
            background: #4f46e5; color: white; border: none; padding: 12px 0; 
            cursor: pointer; border-radius: 8px; font-weight: 700; width: 100%;
            font-size: 15px; transition: background 0.2s;
        }
        .nix-btn:hover { background: #4338ca; }
        
        .loader { border: 3px solid #f3f3f3; border-top: 3px solid #4f46e5; border-radius: 50%; width: 24px; height: 24px; animation: spin 1s linear infinite; margin: 0 auto; display: none;}
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        
        #nix-msg { font-size: 13px; margin-top: 10px; display: block; min-height: 18px; color: #dc2626; font-weight: 500;}
    `;
    document.head.appendChild(style);

    let mouseTrace = [];
    document.addEventListener('mousemove', (e) => {
        if(mouseTrace.length < 50) mouseTrace.push([e.clientX, e.clientY]);
    });

    function initCaptcha() {
        const containers = document.querySelectorAll('.nix-ptcha');
        if (containers.length === 0) return;

        containers.forEach(box => {
            if(box.innerHTML.trim() !== "") return;

            box.innerHTML = `
                <div class="nix-captcha-box">
                    <div class="nix-check" id="nix-box"></div>
                    <div style="display:flex; flex-direction:column;">
                        <span style="font-size: 15px; font-weight: 600; color: #1f2937;">Não sou um robô</span>
                        <span style="font-size: 11px; color: #6b7280;">Protected by <strong>NIX-ptcha</strong></span>
                    </div>
                    
                    <div class="nix-modal" id="nix-modal">
                        <div class="nix-header">Verificação de Segurança</div>
                        <div class="nix-body">
                            <div class="loader" id="nix-loader"></div>
                            <img id="nix-img" class="nix-img" alt="" style="display:none;" />
                            
                            <p id="nix-instrucao" style="font-size:15px; margin:0 0 10px 0; color:#111827; font-weight:700;">...</p>
                            
                            <input type="text" id="nix-input" class="nix-input" placeholder="RESPOSTA" autocomplete="off">
                            <button id="nix-btn" class="nix-btn">VERIFICAR</button>
                            <span id="nix-msg"></span>
                        </div>
                    </div>
                </div>
                <input type="hidden" name="nix-ptcha-response" id="nix-token">
            `;

            const checkbox = box.querySelector('#nix-box');
            const modal = box.querySelector('#nix-modal');
            const imgEl = box.querySelector('#nix-img');
            const loader = box.querySelector('#nix-loader');
            const inputBtn = box.querySelector('#nix-btn');
            const inputField = box.querySelector('#nix-input');
            const msg = box.querySelector('#nix-msg');
            const instrucao = box.querySelector('#nix-instrucao');
            const hiddenInput = box.querySelector('#nix-token');
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
                    
                    instrucao.innerText = data.instruction;
                    
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
                        checkbox.click(); 
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

# --- BACKEND (ZOOM DIGITAL) ---

def gerar_assinatura(dados):
    msg = json.dumps(dados, sort_keys=True).encode()
    return hmac.new(SECRET_KEY, msg, hashlib.sha256).hexdigest()

def criar_texto_ampliado(texto):
    """Zoom Digital para não depender de fontes externas"""
    w_small = len(texto) * 10 + 20
    h_small = 20
    img_small = Image.new('RGBA', (w_small, h_small), (0,0,0,0))
    draw_small = ImageDraw.Draw(img_small)
    
    font_padrao = ImageFont.load_default()
    draw_small.text((5, 2), texto, font=font_padrao, fill=(0,0,0,255))
    
    bbox = img_small.getbbox()
    if bbox: img_small = img_small.crop(bbox)
        
    target_height = 90
    aspect_ratio = img_small.width / img_small.height
    target_width = int(target_height * aspect_ratio)
    
    # NEAREST mantém o visual "pixel art" nítido
    img_large = img_small.resize((target_width, target_height), resample=Image.NEAREST)
    return img_large

def aplicar_distorcao_onda(imagem):
    width, height = imagem.size
    nova_imagem = Image.new("RGBA", (width, height), (0,0,0,0))
    amplitude = random.randint(4, 7)
    frequencia = random.uniform(0.04, 0.06)
    for x in range(width):
        offset_y = int(amplitude * math.sin(2 * math.pi * frequencia * x))
        dest_y = max(0, offset_y)
        coluna = imagem.crop((x, 0, x + 1, height))
        nova_imagem.paste(coluna, (x, dest_y))
    return nova_imagem

def criar_imagem_distorcida(texto):
    width, height = 520, 180 
    background = Image.new('RGB', (width, height), color=(245, 245, 250))
    
    texto_img = criar_texto_ampliado(texto)
    txt_layer = Image.new('RGBA', (width, height), (0,0,0,0))
    
    pos_x = (width - texto_img.width) // 2
    pos_y = (height - texto_img.height) // 2
    
    txt_layer.paste(texto_img, (pos_x, pos_y))
    txt_layer = aplicar_distorcao_onda(txt_layer)
    final_img = Image.alpha_composite(background.convert('RGBA'), txt_layer)
    
    draw_final = ImageDraw.Draw(final_img)
    # Ruído de fundo (linhas)
    for _ in range(15):
        draw_final.line([(random.randint(0, width), random.randint(0, height)), 
                         (random.randint(0, width), random.randint(0, height))], 
                        fill=(180,180,180), width=2)
    # Ruído frontal (pontos)
    for _ in range(400):
        draw_final.point((random.randint(0, width), random.randint(0, height)), fill=(100, 100, 100))
        
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
    # TIPOS DE DESAFIO (AGORA INCLUINDO MAIOR/MENOR)
    tipos = ['normal', 'math', 'max_min']
    escolha = random.choice(tipos)
    
    texto_img = ""
    resposta = ""
    instrucao = ""
    
    # 1. MATEMÁTICA
    if escolha == 'math':
        op = random.choice(['+', '-', '*'])
        if op == '+':
            a, b = random.randint(1, 9), random.randint(1, 9)
            texto_img = f"{a} + {b} = ?"
            resposta = str(a + b)
        elif op == '-':
            a, b = random.randint(5, 15), random.randint(1, 5)
            texto_img = f"{a} - {b} = ?"
            resposta = str(a - b)
        elif op == '*':
            a, b = random.randint(2, 6), random.randint(2, 4)
            texto_img = f"{a} x {b} = ?"
            resposta = str(a * b)
        instrucao = "Resolva o cálculo abaixo:"

    # 2. NOVO: MAIOR OU MENOR NÚMERO
    elif escolha == 'max_min':
        # Gera 3 números distintos entre 1 e 50
        nums = random.sample(range(1, 50), 3)
        
        # Decide aleatoriamente se pede o MAIOR ou o MENOR
        if random.random() < 0.5:
            # Pede o Maior
            target = max(nums)
            instrucao = "Digite o MAIOR número:"
        else:
            # Pede o Menor
            target = min(nums)
            instrucao = "Digite o MENOR número:"
        
        # Formata com espaços extras para ficar visível na imagem
        texto_img = f"{nums[0]}   {nums[1]}   {nums[2]}"
        resposta = str(target)

    # 3. TEXTO NORMAL (PADRÃO)
    else:
        texto_img = "".join(random.choices("ACEFHKMNP234579", k=5))
        resposta = texto_img
        instrucao = "Digite os caracteres da imagem:"

    # Gera a imagem
    imagem_b64 = criar_imagem_distorcida(texto_img)
    
    dados = { "ans": resposta, "ts": time.time(), "salt": random.randint(1, 9999) }
    token = f"{base64.urlsafe_b64encode(json.dumps(dados).encode()).decode()}.{gerar_assinatura(dados)}"
    
    return jsonify({ 
        "image": imagem_b64, 
        "token": token, 
        "type": escolha,
        "instruction": instrucao 
    })

@app.route('/verify', methods=['POST'])
def verify():
    data = request.json
    try:
        user_ans = data.get('answer', '').strip().upper()
        # Remove espaços (importante para evitar erro se user digitar " 10 ")
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
