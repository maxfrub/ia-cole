from flask import Flask, request, Response, send_from_directory, jsonify
from flask_sock import Sock
import requests
import json
import os

app = Flask(__name__)
sock = Sock(app)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
PROFE_PASSWORD = "20252026"

modo_clase_global = False
clientes = {}  # ws_id -> {ws, nombre, modo_clase}
profe_ws = {}

def broadcast_alumnos():
    muertos = []
    for ws_id, info in clientes.items():
        try:
            info['ws'].send(json.dumps({
                "tipo": "modo_clase",
                "activo": info['modo_clase']
            }))
        except:
            muertos.append(ws_id)
    for ws_id in muertos:
        del clientes[ws_id]

def broadcast_profe():
    lista = [{"id": k, "nombre": v["nombre"], "modo_clase": v["modo_clase"]} for k, v in clientes.items()]
    muertos = []
    for ws_id, ws in profe_ws.items():
        try:
            ws.send(json.dumps({
                "tipo": "alumnos",
                "alumnos": lista,
                "modo_clase_global": modo_clase_global
            }))
        except:
            muertos.append(ws_id)
    for ws_id in muertos:
        del profe_ws[ws_id]

def notificar_alumno(ws_id, activo):
    if ws_id in clientes:
        try:
            clientes[ws_id]['modo_clase'] = activo
            clientes[ws_id]['ws'].send(json.dumps({
                "tipo": "modo_clase",
                "activo": activo
            }))
        except:
            del clientes[ws_id]

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

@sock.route('/ws/alumno')
def ws_alumno(ws):
    global modo_clase_global
    ws_id = str(id(ws))
    clientes[ws_id] = {"ws": ws, "nombre": "Alumno", "modo_clase": modo_clase_global}
    ws.send(json.dumps({"tipo": "modo_clase", "activo": modo_clase_global}))
    broadcast_profe()
    try:
        while True:
            msg = ws.receive()
            if msg is None:
                break
            datos = json.loads(msg)
            if datos.get("tipo") == "nombre":
                clientes[ws_id]["nombre"] = datos["nombre"]
                broadcast_profe()
            elif datos.get("tipo") == "quitar_modo_clase":
                if datos.get("password") == PROFE_PASSWORD:
                    clientes[ws_id]['modo_clase'] = False
                    ws.send(json.dumps({"tipo": "modo_clase", "activo": False}))
                    broadcast_profe()
    except:
        pass
    finally:
        if ws_id in clientes:
            del clientes[ws_id]
        broadcast_profe()

@sock.route('/ws/profe')
def ws_profe(ws):
    global modo_clase_global
    ws_id = str(id(ws))
    profe_ws[ws_id] = ws
    lista = [{"id": k, "nombre": v["nombre"], "modo_clase": v["modo_clase"]} for k, v in clientes.items()]
    ws.send(json.dumps({"tipo": "alumnos", "alumnos": lista, "modo_clase_global": modo_clase_global}))
    try:
        while True:
            msg = ws.receive()
            if msg is None:
                break
            datos = json.loads(msg)
            if datos.get("tipo") == "set_modo_clase_global":
                modo_clase_global = datos.get("activo", False)
                for ws_id_a in list(clientes.keys()):
                    clientes[ws_id_a]['modo_clase'] = modo_clase_global
                    try:
                        clientes[ws_id_a]['ws'].send(json.dumps({"tipo": "modo_clase", "activo": modo_clase_global}))
                    except:
                        del clientes[ws_id_a]
                broadcast_profe()
            elif datos.get("tipo") == "set_modo_clase_alumno":
                alumno_id = datos.get("alumno_id")
                activo = datos.get("activo", False)
                notificar_alumno(alumno_id, activo)
                broadcast_profe()
    except:
        pass
    finally:
        if ws_id in profe_ws:
            del profe_ws[ws_id]

if __name__ == '__main__':
    print("Servidor corriendo en http://localhost:3000")
    print("Panel profe en http://localhost:3000/profe")
    port = int(os.environ.get("PORT", 3000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)