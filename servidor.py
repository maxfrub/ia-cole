from flask import Flask, request, send_from_directory, jsonify
import requests
import json
import os
import time

app = Flask(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
PROFE_PASSWORD = "20252026"

# Estado global
modo_clase_global = False
clientes = {}  # token -> {nombre, modo_clase, ultimo_ping}

def limpiar_inactivos():
    ahora = time.time()
    muertos = [k for k, v in clientes.items() if ahora - v['ultimo_ping'] > 30]
    for k in muertos:
        del clientes[k]

@app.route('/')
def index():
    return send_from_directory('.', 'chat.html')

@app.route('/profe')
def profe():
    return send_from_directory('.', 'profe.html')

@app.route('/chat', methods=['POST'])
def chat():
    datos = request.json
    model = datos.get("model", "llama-3.1-8b-instant")
    messages = datos.get("messages", [])
    try:
        res = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "stream": False},
            timeout=30
        )
        data = res.json()
        if "error" in data:
            return jsonify({"error": data["error"]}), 500
        respuesta = data["choices"][0]["message"]["content"]
        return jsonify({"message": {"content": respuesta}})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/verificar-profe', methods=['POST'])
def verificar_profe():
    datos = request.json
    if datos.get("password") == PROFE_PASSWORD:
        return jsonify({"ok": True})
    return jsonify({"ok": False}), 401

# Alumno hace ping cada 5 segundos para mantenerse visible
@app.route('/ping', methods=['POST'])
def ping():
    datos = request.json
    token = datos.get("token")
    nombre = datos.get("nombre", "Alumno")
    if token:
        if token not in clientes:
            clientes[token] = {"nombre": nombre, "modo_clase": modo_clase_global}
        clientes[token]['ultimo_ping'] = time.time()
        clientes[token]['nombre'] = nombre
        modo_actual = clientes[token].get('modo_clase', modo_clase_global)
        return jsonify({"modo_clase": modo_actual})
    return jsonify({"error": "sin token"}), 400

# Profe obtiene lista de alumnos
@app.route('/alumnos', methods=['GET'])
def get_alumnos():
    limpiar_inactivos()
    lista = [{"id": k, "nombre": v["nombre"], "modo_clase": v["modo_clase"]} for k, v in clientes.items()]
    return jsonify({"alumnos": lista, "modo_clase_global": modo_clase_global})

# Profe cambia modo a todos
@app.route('/set-modo-global', methods=['POST'])
def set_modo_global():
    global modo_clase_global
    datos = request.json
    if datos.get("password") != PROFE_PASSWORD:
        return jsonify({"error": "no autorizado"}), 401
    modo_clase_global = datos.get("activo", False)
    for k in clientes:
        clientes[k]['modo_clase'] = modo_clase_global
    return jsonify({"ok": True})

# Profe cambia modo a un alumno
@app.route('/set-modo-alumno', methods=['POST'])
def set_modo_alumno():
    datos = request.json
    if datos.get("password") != PROFE_PASSWORD:
        return jsonify({"error": "no autorizado"}), 401
    alumno_id = datos.get("alumno_id")
    activo = datos.get("activo", False)
    if alumno_id in clientes:
        clientes[alumno_id]['modo_clase'] = activo
    return jsonify({"ok": True})

# Alumno quita modo clase con contraseña
@app.route('/quitar-modo-clase', methods=['POST'])
def quitar_modo_clase():
    datos = request.json
    if datos.get("password") != PROFE_PASSWORD:
        return jsonify({"ok": False}), 401
    token = datos.get("token")
    if token in clientes:
        clientes[token]['modo_clase'] = False
    return jsonify({"ok": True})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 3000))
    print(f"Servidor corriendo en http://localhost:{port}")
    print(f"Panel profe en http://localhost:{port}/profe")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)