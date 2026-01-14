from flask import Flask, Response, request, jsonify, render_template
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

SECRET_KEY = b"Swga413RQWT43TYe22WQRAFWGQ23"

# --- SISTEMA DE DIFICULDADE DINÂMICA ---
# Armazena histórico: { "IP_DO_CLIENTE": [timestamp1, timestamp2, ...] }
USER_HISTORY = {}

def get_client_ip():
    """Pega o IP real, mesmo estando atrás do proxy da Vercel"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0]
    return request.remote_addr

def get_difficulty_level(ip):
    """
    Calcula o nível de dificuldade baseado no histórico dos últimos 3 minutos.
    Retorna: 0 (Normal), 1 (Difícil), 2 (Extremo)
    """
    now = time.time()
    if ip not in USER_HISTORY:
        return 0
    
    # 1. Filtra: Mantém apenas registros dos últimos 180 segundos (3 min)
    timestamps = [t for t in USER_HISTORY[ip] if now - t < 180]
    USER_HISTORY[ip] = timestamps # Atualiza a lista limpa
    
    count = len(timestamps)
    
    # 2. Define Nível
    if count < 3: return 0      # Normal
    if count < 6: return 1      # Difícil (3 a 5 feitos)
    return 2                    # Extremo (6+ feitos rapidão)

def registrar_sucesso(ip):
    """Chamado quando o usuário ACERTA o captcha"""
    if ip not in USER_HISTORY:
        USER_HISTORY[ip] = []
    USER_HISTORY[ip].append(time.time())

# --- ROTAS ---
@app.route("/")
def sobre():
    return render_template("main.html")

@app.route("/demo")
def demo():
    return render_template("main.html")

# --- FRONTEND (MANTIDO IGUAL) ---
JS_TEMPLATE = """
(function() {
    const API_BASE = "__API_URL__";
    const style = document.createElement('style');
    style.innerHTML = `
        .nix-captcha-box { background: #fff; border: 1px solid #d1d5db; border-radius: 8px; width: 320px; padding: 12px; display: flex; align-items: center; font-family: 'Segoe UI', Roboto, sans-serif; user-select: none; position: relative; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .nix-check { width: 28px; height: 28px; border: 2px solid #c1c1c1; border-radius: 5px; cursor: pointer; background: #fff; margin-right: 15px; flex-shrink: 0; transition: all 0.2s; }
        .nix-check.checked { background: #10b981; border-color: #10b981; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='white' width='22px' height='22px'%3E%3Cpath d='M0 0h24v24H0z' fill='none'/%3E%3Cpath d='M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z'/%3E%3C/svg%3E"); background-position: center; background-repeat: no-repeat; }
        .nix-modal { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -20px); background: white; width: 450px; max-width: 90vw; border-radius: 12px; box-shadow: 0 20px 40px rgba(0,0,0,0.2), 0 0 0 1px rgba(0,0,0,0.05); z-index: 10000; display: none; overflow: hidden; font-family: 'Segoe UI', Roboto, sans-serif; padding-bottom: 20px; }
        .nix-header { background: #4f46e5; color: white; padding: 14px; font-size: 15px; font-weight: 600; text-align: center; position: relative; }
        .nix-close-btn { position: absolute; top: 0; right: 0; padding: 14px 20px; cursor: pointer; font-size: 20px; line-height: 1; color: rgba(255,255,255,0.8); }
        .nix-close-btn:hover { color: #fff; background: rgba(0,0,0,0.1); }
        .nix-body { padding: 20px; text-align: center; }
        .nix-img { display: block; margin: 0 auto 15px auto; border-radius: 8px; border: 1px solid #e5e7eb; width: 100%; height: auto; box-shadow: inset 0 0 10px rgba(0,0,0,0.05); }
        .nix-input { width: 100%; padding: 12px; margin-bottom: 15px; box-sizing: border-box; border: 1px solid #d1d5db; border-radius: 8px; font-size: 18px; outline: none; text-align: center; letter-spacing: 3px; font-weight: bold; text-transform: uppercase; }
        .nix-input:focus { border-color: #4f46e5; box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.2); }
        .nix-btn { background: #4f46e5; color: white; border: none; padding: 12px 0; cursor: pointer; border-radius: 8px; font-weight: 700; width: 100%; font-size: 15px; transition: background 0.2s; }
        .nix-btn:hover { background: #4338ca; }
        .nix-options-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-bottom: 10px; }
        .nix-opt-btn { padding: 15px 5px; border: 1px solid #d1d5db; background: #f9fafb; border-radius: 8px; font-weight: 600; cursor: pointer; color: #374151; font-size: 14px; transition: all 0.2s; }
        .nix-opt-btn:hover { background: #e5e7eb; border-color: #9ca3af; }
        .loader { border: 3px solid #f3f3f3; border-top: 3px solid #4f46e5; border-radius: 50%; width: 24px; height: 24px; animation: spin 1s linear infinite; margin: 0 auto; display: none;}
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        #nix-msg { font-size: 13px; margin-top: 10px; display: block; min-height: 18px; color: #dc2626; font-weight: 500;}
    `;
    document.head.appendChild(style);
    let mouseTrace = [];
    document.addEventListener('mousemove', (e) => { if(mouseTrace.length < 50) mouseTrace.push([e.clientX, e.clientY]); });
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
                        <div class="nix-header">Verificação de Segurança<span class="nix-close-btn" id="nix-close">&times;</span></div>
                        <div class="nix-body">
                            <div class="loader" id="nix-loader"></div>
                            <img id="nix-img" class="nix-img" alt="" style="display:none;" />
                            <p id="nix-instrucao" style="font-size:15px; margin:0 0 10px 0; color:#111827; font-weight:700;">...</p>
                            <div id="nix-text-container">
                                <input type="text" id="nix-input" class="nix-input" placeholder="RESPOSTA" autocomplete="off">
                                <button id="nix-btn" class="nix-btn">VERIFICAR</button>
                            </div>
                            <div id="nix-options-container" class="nix-options-grid" style="display:none;"></div>
                            <span id="nix-msg"></span>
                        </div>
                    </div>
                </div>
                <input type="hidden" name="nix-ptcha-response" id="nix-token">
            `;
            const checkbox = box.querySelector('#nix-box'), modal = box.querySelector('#nix-modal'), closeBtn = box.querySelector('#nix-close'), imgEl = box.querySelector('#nix-img'), loader = box.querySelector('#nix-loader'), textContainer = box.querySelector('#nix-text-container'), optionsContainer = box.querySelector('#nix-options-container'), inputBtn = box.querySelector('#nix-btn'), inputField = box.querySelector('#nix-input'), msg = box.querySelector('#nix-msg'), instrucao = box.querySelector('#nix-instrucao'), hiddenInput = box.querySelector('#nix-token');
            let currentToken = "";
            closeBtn.addEventListener('click', (e) => { e.stopPropagation(); modal.style.display = 'none'; msg.innerText = ""; inputField.value = ""; });
            async function submitAnswer(answer) {
                msg.innerText = "Verificando...";
                try {
                    const req = await fetch(`${API_BASE}/verify`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ token: currentToken, answer: answer, mouse_trace: mouseTrace }) });
                    const resp = await req.json();
                    if (resp.success) { modal.style.display = 'none'; checkbox.classList.add('checked'); hiddenInput.value = resp.verification_token; } 
                    else { msg.innerText = "Incorreto. Tente novamente."; setTimeout(() => { msg.innerText = ""; checkbox.click(); }, 1000); }
                } catch (e) { msg.innerText = "Erro ao validar."; }
            }
            checkbox.addEventListener('click', async () => {
                if (checkbox.classList.contains('checked')) return;
                modal.style.display = 'block'; imgEl.style.display = 'none'; loader.style.display = 'block'; textContainer.style.display = 'none'; optionsContainer.style.display = 'none'; msg.innerText = "";
                try {
                    const req = await fetch(`${API_BASE}/get-challenge`);
                    const data = await req.json();
                    loader.style.display = 'none'; imgEl.style.display = 'block'; imgEl.src = "data:image/png;base64," + data.image; instrucao.innerText = data.instruction; currentToken = data.token;
                    if (data.options && data.options.length > 0) {
                        optionsContainer.innerHTML = ''; optionsContainer.style.display = 'grid';
                        data.options.forEach(opt => { const btn = document.createElement('button'); btn.className = 'nix-opt-btn'; btn.innerText = opt; btn.onclick = (e) => { e.preventDefault(); submitAnswer(opt); }; optionsContainer.appendChild(btn); });
                    } else { textContainer.style.display = 'block'; inputField.value = ""; inputField.focus(); }
                } catch(e) { msg.innerText = "Erro ao conectar."; }
            });
            inputBtn.addEventListener('click', (e) => { e.preventDefault(); submitAnswer(inputField.value); });
        });
    }
    if (document.readyState === "complete" || document.readyState === "interactive") { setTimeout(initCaptcha, 10); } else { document.addEventListener("DOMContentLoaded", initCaptcha); }
})();
"""

# --- FUNÇÕES GRÁFICAS ---

def gerar_assinatura(dados):
    msg = json.dumps(dados, sort_keys=True).encode()
    return hmac.new(SECRET_KEY, msg, hashlib.sha256).hexdigest()

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

def criar_texto_ampliado(texto, cor_texto=(0,0,0,255)):
    w_small = len(texto) * 10 + 20
    h_small = 20
    img_small = Image.new('RGBA', (w_small, h_small), (0,0,0,0))
    draw_small = ImageDraw.Draw(img_small)
    font_padrao = ImageFont.load_default()
    draw_small.text((5, 2), texto, font=font_padrao, fill=cor_texto)
    bbox = img_small.getbbox()
    if bbox: img_small = img_small.crop(bbox)
    
    aspect_ratio = img_small.width / img_small.height
    target_height = 90
    target_width = int(target_height * aspect_ratio)
    
    MAX_WIDTH = 480
    if target_width > MAX_WIDTH:
        target_width = MAX_WIDTH
        target_height = int(target_width / aspect_ratio)
        
    img_large = img_small.resize((target_width, target_height), resample=Image.NEAREST)
    return img_large

def criar_imagem_distorcida(texto, cor_texto=(0,0,0)):
    cor_rgba = (cor_texto[0], cor_texto[1], cor_texto[2], 255)
    width, height = 520, 180 
    background = Image.new('RGB', (width, height), color=(245, 245, 250))
    texto_img = criar_texto_ampliado(texto, cor_rgba)
    txt_layer = Image.new('RGBA', (width, height), (0,0,0,0))
    pos_x = (width - texto_img.width) // 2
    pos_y = (height - texto_img.height) // 2
    txt_layer.paste(texto_img, (pos_x, pos_y))
    txt_layer = aplicar_distorcao_onda(txt_layer)
    final_img = Image.alpha_composite(background.convert('RGBA'), txt_layer)
    draw_final = ImageDraw.Draw(final_img)
    for _ in range(15):
        draw_final.line([(random.randint(0, width), random.randint(0, height)), (random.randint(0, width), random.randint(0, height))], fill=(180,180,180), width=2)
    for _ in range(400):
        draw_final.point((random.randint(0, width), random.randint(0, height)), fill=(100, 100, 100))
    buffer = io.BytesIO()
    final_img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def criar_imagem_cor(cor_rgb):
    width, height = 520, 180
    background = Image.new('RGB', (width, height), color=(245, 245, 250))
    draw = ImageDraw.Draw(background)
    cx, cy = width // 2, height // 2
    r = 70
    draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=cor_rgb)
    for _ in range(500):
        ox = random.randint(cx-r, cx+r)
        oy = random.randint(cy-r, cy+r)
        noise_r = max(0, min(255, cor_rgb[0] + random.randint(-20, 20)))
        noise_g = max(0, min(255, cor_rgb[1] + random.randint(-20, 20)))
        noise_b = max(0, min(255, cor_rgb[2] + random.randint(-20, 20)))
        draw.point((ox, oy), fill=(noise_r, noise_g, noise_b))
    buffer = io.BytesIO()
    background.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def criar_imagem_stroop(texto, cor_tinta_rgb):
    return criar_imagem_distorcida(texto, cor_tinta_rgb)

# --- ROTAS API ---

@app.route('/api.js')
def servir_script():
    api_url = request.url_root.rstrip('/')
    js_final = JS_TEMPLATE.replace('__API_URL__', api_url)
    return Response(js_final, mimetype='application/javascript')

@app.route('/get-challenge', methods=['GET'])
def get_challenge():
    # 1. PEGAR IP E CALCULAR NÍVEL
    client_ip = get_client_ip()
    nivel_dificuldade = get_difficulty_level(client_ip)
    
    # Debug: Mostra no terminal o nível (opcional)
    # print(f"IP: {client_ip} | Nível: {nivel_dificuldade}")

    # Tipos disponíveis (removido 'shapes')
    tipos = ['math_word', 'color_match', 'stroop', 'position', 'intruder', 'normal']
    escolha = random.choice(tipos)
    
    texto_img = ""
    resposta = ""
    instrucao = ""
    options = []
    imagem_b64 = ""
    
    # --- APLICAÇÃO DA DIFICULDADE (SCALING) ---

    # 1. MATEMÁTICA POR EXTENSO
    if escolha == 'math_word':
        nums_map = {1: "UM", 2: "DOIS", 3: "TRES", 4: "QUATRO", 5: "CINCO", 6: "SEIS", 7: "SETE", 8: "OITO", 9: "NOVE", 10: "DEZ"}
        
        if nivel_dificuldade == 0:
            # Fácil: Soma pequena, números 1-5
            val_a, val_b = random.randint(1, 4), random.randint(1, 3)
        elif nivel_dificuldade == 1:
            # Difícil: Soma média, números 1-8
            val_a, val_b = random.randint(3, 8), random.randint(2, 6)
        else:
            # Extremo: Soma grande, números 5-10
            val_a, val_b = random.randint(5, 10), random.randint(5, 10)

        # Garante que os valores estejam no mapa
        val_a = min(val_a, 10)
        val_b = min(val_b, 10)

        if random.random() < 0.5:
            expr_str = f"{nums_map[val_a]} + {val_b}"
        else:
            expr_str = f"{val_a} + {nums_map[val_b]}"
            
        texto_img = f"{expr_str} = ?"
        resposta = str(val_a + val_b)
        instrucao = "Resolva a soma (digite o número):"
        imagem_b64 = criar_imagem_distorcida(texto_img)

    # 2. NORMAL (CARACTERES)
    elif escolha == 'normal':
        # Nível 0: 5 chars
        # Nível 1: 6 chars
        # Nível 2: 8 chars
        comp = 5
        if nivel_dificuldade == 1: comp = 6
        elif nivel_dificuldade == 2: comp = 8
        
        texto_img = "".join(random.choices("ACEFHKMNP234579", k=comp))
        resposta = texto_img
        instrucao = "Digite os caracteres:"
        imagem_b64 = criar_imagem_distorcida(texto_img)
    
    # 3. STROOP (Mantido, difícil por natureza)
    elif escolha == 'stroop':
        cores = {'VERMELHO': (200,0,0), 'AZUL': (0,0,200), 'VERDE': (0,180,0), 'ROXO': (128,0,128)}
        nomes = list(cores.keys())
        texto_exibido = random.choice(nomes)
        cor_tinta_nome = random.choice([n for n in nomes if n != texto_exibido])
        texto_img = texto_exibido
        resposta = cor_tinta_nome
        instrucao = "Qual a COR da tinta do texto?"
        options = nomes
        random.shuffle(options)
        imagem_b64 = criar_imagem_stroop(texto_img, cores[cor_tinta_nome])

    # 4. POSIÇÃO
    elif escolha == 'position':
        # Aumenta a quantidade de caracteres no nível difícil
        qtd = 3
        if nivel_dificuldade >= 1: qtd = 4
        if nivel_dificuldade >= 2: qtd = 5
        
        chars = random.sample("ABCDEFGHMNPRT23456789", qtd)
        texto_img = "   ".join(chars)
        
        # Lógica simples para pegar posições
        idx_alvo = random.randint(0, qtd-1)
        if idx_alvo == 0: instrucao = "Digite o PRIMEIRO caractere:"
        elif idx_alvo == qtd-1: instrucao = "Digite o ÚLTIMO caractere:"
        else: instrucao = f"Digite o {idx_alvo+1}º caractere:" # Ex: 2º, 3º
        
        resposta = chars[idx_alvo]
        imagem_b64 = criar_imagem_distorcida(texto_img)

    # 5. INTRUSO
    elif escolha == 'intruder':
        # Mais números para confundir em níveis altos
        qtd_nums = 3 + nivel_dificuldade # 3, 4 ou 5 números
        nums = random.choices("23456789", k=qtd_nums)
        letra = random.choice("ABCDEFGH")
        itens = nums + [letra]; random.shuffle(itens)
        texto_img = " ".join(itens)
        instrucao = "Digite a LETRA intrusa:"
        resposta = letra
        imagem_b64 = criar_imagem_distorcida(texto_img)

    # 6. COLOR MATCH
    elif escolha == 'color_match':
        cores_dict = {'VERMELHO': (200,40,40), 'VERDE': (40,200,40), 'AZUL': (40,40,200)}
        nomes_cores = list(cores_dict.keys())
        cor_correta = random.choice(nomes_cores)
        opcoes = nomes_cores; resposta = cor_correta; instrucao = "Qual a cor da mancha?"; options = opcoes
        img = Image.new('RGB', (520, 180), (245, 245, 250)); d = ImageDraw.Draw(img)
        d.ellipse([220, 50, 300, 130], fill=cores_dict[cor_correta])
        buf = io.BytesIO(); img.save(buf, format="PNG"); imagem_b64 = base64.b64encode(buf.getvalue()).decode()

    dados = { "ans": resposta, "ts": time.time(), "salt": random.randint(1, 9999) }
    token = f"{base64.urlsafe_b64encode(json.dumps(dados).encode()).decode()}.{gerar_assinatura(dados)}"
    return jsonify({ "image": imagem_b64, "token": token, "type": escolha, "instruction": instrucao, "options": options })

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
        
        if user_ans == dados['ans'].upper():
            # ACERTOU: Registra no histórico para aumentar dificuldade
            client_ip = get_client_ip()
            registrar_sucesso(client_ip)

            payload_sucesso = { "valid": True, "ts_passed": time.time(), "expires_at": time.time() + 300, "nonce": random.randint(100000, 999999) }
            token_final = f"{base64.urlsafe_b64encode(json.dumps(payload_sucesso).encode()).decode()}.{gerar_assinatura(payload_sucesso)}"
            return jsonify({ "success": True, "verification_token": token_final })
        
        return jsonify({"success": False})
    except: return jsonify({"success": False})

@app.route('/validate', methods=['GET', 'POST'])
def validate_token():
    token_recebido = request.args.get('token') if request.method == 'GET' else (request.get_json(silent=True) or {}).get('token', request.form.get('token'))
    if not token_recebido or "." not in token_recebido: return jsonify({"valid": False, "error": "Formato inválido"})
    try:
        token_b64, sig = token_recebido.split('.')
        payload = json.loads(base64.urlsafe_b64decode(token_b64).decode())
        if gerar_assinatura(payload) != sig: return jsonify({"valid": False, "error": "Assinatura inválida"})
        if time.time() > payload.get('expires_at', 0): return jsonify({"valid": False, "error": "Token expirado"})
        if not payload.get('valid'): return jsonify({"valid": False, "error": "Token inválido"})
        return jsonify({"valid": True, "ts": payload.get('ts_passed')})
    except Exception as e: return jsonify({"valid": False, "error": str(e)})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
