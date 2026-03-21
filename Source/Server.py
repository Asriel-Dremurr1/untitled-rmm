# server.py - ИСПРАВЛЕННАЯ И СОВМЕСТИМАЯ ВЕРСИЯ
from flask import Flask, request, jsonify, send_from_directory
import os, json, time, threading, hmac, hashlib, secrets
from datetime import datetime, timedelta, timezone, UTC
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import socket
import logging
import sys
import base64

app = Flask(__name__)
UPLOAD_DIR = "files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- Конфигурация файлов хранения ---
USERS_FILE = "users.json"
TASKS_FILE = "tasks.json"
AGENTS_FILE = "agents.json"
PENDING_APPROVALS_FILE = "pending_approvals.json"
CONFIG_FILE = "config.json"

LOG_AUDIT = "audit.log"
LOG_HTTP = "http.log"
LOG_TECH = "tech.log"

# ensure directories/files exist
for f in (USERS_FILE, TASKS_FILE, AGENTS_FILE, PENDING_APPROVALS_FILE, CONFIG_FILE):
    if not os.path.exists(f):
        with open(f, "w", encoding="utf-8") as _f:
            if f == TASKS_FILE:
                json.dump([], _f, indent=2, ensure_ascii=False)
            else:
                json.dump({}, _f, indent=2, ensure_ascii=False)

LOCK = threading.RLock()

def check_agent_online_status():
    """Проверяет, какие агенты онлайн/оффлайн на основе last_seen"""
    current_time = datetime.now(UTC)
    
    for agent_id, agent_data in agents.items():
        last_seen_str = agent_data.get("last_seen")
        if last_seen_str:
            try:
                if last_seen_str.endswith('Z'):
                    dt_str = last_seen_str[:-1]
                    last_seen = datetime.fromisoformat(dt_str).replace(tzinfo=UTC)
                else:
                    last_seen = datetime.fromisoformat(last_seen_str)
                
                time_diff = (current_time - last_seen).total_seconds()
                
                if time_diff > 120:
                    agent_data["status"] = "OFFLINE"
                else:
                    agent_data["status"] = "ONLINE"
            except Exception as e:
                print(f"Ошибка парсинга времени у агента {agent_id}: {e}")
                agent_data["status"] = "UNKNOWN"
        else:
            agent_data["status"] = "UNKNOWN"
    
    save_json(AGENTS_FILE, agents)

def status_checker_daemon():
    """Фоновая задача для проверки онлайн статуса агентов"""
    while True:
        time.sleep(120)
        try:
            check_agent_online_status()
        except Exception as e:
            print(f"Status checker error: {e}")

threading.Thread(target=status_checker_daemon, daemon=True).start()

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    with LOCK:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"save_json error for {path}: {e}")

def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {
            "server_secret": "mysecret123",
            "server_description": "NODE-2026: ГЛАВНЫЙ УЗЕЛ УПРАВЛЕНИЯ",
            "port": 5000
        }

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("save_config error:", e)

# load persistent structures
users = load_json(USERS_FILE, {})
tasks = load_json(TASKS_FILE, [])
agents = load_json(AGENTS_FILE, {})
pending_approvals = load_json(PENDING_APPROVALS_FILE, {})
config = load_config()

SERVER_PORT = config.get("port", 5000)

# --- Privileges list ---
PRIVS = [
    "approve_agent",
    "run_cmd",
    "manage_users",
    "push_file",
    "pull_file",
    "view_info",
    "view_logs",
    "shutdown_server",
    "cancel_tasks"
]

# --- Logging helpers ---
def append_log(logfile, entry):
    e = {"ts": datetime.now(UTC).isoformat().replace("+00:00", "Z")}
    e.update(entry)
    try:
        with open(logfile, "a", encoding="utf-8") as f:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    except Exception as ex:
        print("log error", ex)

def audit(username, action, detail=None, ip=None):
    append_log(LOG_AUDIT, {"user": username, "action": action, "detail": detail or {}, "ip": ip})

def tech_log(entry):
    append_log(LOG_TECH, entry)

# --- User helpers ---
def save_users():
    save_json(USERS_FILE, users)

def get_user(username):
    return users.get(username)

def create_user(username, password_plain, privs, cmd_blacklist=None):
    if username in users:
        return False, "user exists"
    
    if len(password_plain) < 8:
        return False, "Пароль должен быть не менее 8 символов"
    
    if not any(c.isupper() for c in password_plain):
        return False, "Пароль должен содержать хотя бы одну заглавную букву"
    
    if not any(c.islower() for c in password_plain):
        return False, "Пароль должен содержать хотя бы одну строчную букву"
    
    if not any(c.isdigit() for c in password_plain):
        return False, "Пароль должен содержать хотя бы одну цифру"
    
    hashpwd = generate_password_hash(password_plain)
    users[username] = {
        "password_hash": hashpwd,
        "privileges": privs,
        "cmd_blacklist": cmd_blacklist or [],
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z")
    }
    save_users()
    return True, ""

def is_command_allowed(username, command):
    user = get_user(username)
    if not user:
        return False
    
    blacklist = user.get("cmd_blacklist", [])
    if not blacklist:
        return True
    
    cmd_lower = command.lower()
    
    for forbidden in blacklist:
        forbidden_lower = forbidden.strip().lower()
        if forbidden_lower and forbidden_lower in cmd_lower:
            return False
    
    return True

# On first run: ensure Admin exists
if "Admin" not in users:
    users["Admin"] = {
        "password_hash": "",
        "privileges": PRIVS,
        "cmd_blacklist": [],
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z")
    }
    save_users()

# --- Authentication helpers ---
def verify_basic_auth():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Basic '):
        return None
    
    try:
        auth_b64 = auth_header[6:]
        auth_str = base64.b64decode(auth_b64).decode('utf-8')
        username, password = auth_str.split(':', 1)
        
        user = get_user(username)
        if user and user.get('password_hash') and check_password_hash(user['password_hash'], password):
            return username
    except Exception as e:
        print(f"Auth error: {e}")
    
    return None

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        username = verify_basic_auth()
        if not username:
            return jsonify({"error": "Authentication required"}), 401
        request.username = username
        return f(*args, **kwargs)
    return decorated

def require_priv(priv):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            username = verify_basic_auth()
            if not username:
                return jsonify({"error": "Authentication required"}), 401
            
            user = get_user(username)
            if not user:
                return jsonify({"error": "User not found"}), 403
            
            if priv not in user.get("privileges", []):
                return jsonify({"error": "Insufficient privileges"}), 403
            
            request.username = username
            return f(*args, **kwargs)
        return decorated
    return decorator

# --- Utility functions ---
def now_iso():
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")

def parse_iso(s):
    try:
        return datetime.fromisoformat(s)
    except:
        return None

def sha256_hex(s: str):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def persist_all():
    with LOCK:
        try:
            save_json(TASKS_FILE, tasks)
            save_json(AGENTS_FILE, agents)
            save_json(PENDING_APPROVALS_FILE, pending_approvals)
        except Exception as e:
            print(f"Save error: {e}")

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        s.connect(('10.254.254.254', 1))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = "127.0.0.1"
    finally:
        s.close()
    return local_ip

def discovery_responder():
    UDP_PORT = 37020
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', UDP_PORT))
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            if data in (b"CLIENT_QUERY_2026", b"DISCOVER"):
                ip = get_local_ip()
                server_url = f"https://{ip}:{SERVER_PORT}"
                server_auth = sha256_hex(config.get("server_secret", "") or "")
                response = json.dumps({"url": server_url, "server_auth": server_auth})
                sock.sendto(response.encode(), addr)
        except Exception as e:
            pass

threading.Thread(target=discovery_responder, daemon=True).start()

def is_agent_blocked(agent_id):
    p = pending_approvals.get(agent_id)
    return p and p.get("status") == "BLOCKED"

def is_agent_approved(agent_id):
    a = agents.get(agent_id)
    return a and a.get("approved") is True

def extract_agent_id_from_request(req):
    if req.is_json:
        j = req.get_json(silent=True) or {}
        if "agent_id" in j: return j.get("agent_id")
        if "agent" in j: return j.get("agent")
    a = req.args.get("agent") or req.args.get("agent_id")
    if a: return a
    return req.headers.get("X-Agent-Id")

def verify_agent_request(req):
    try:
        agent_id = extract_agent_id_from_request(req)
        
        if not agent_id:
            return False
        
        if is_agent_blocked(agent_id):
            return False
        
        provided_token = None
        
        if req.is_json:
            json_data = req.get_json(silent=True) or {}
            provided_token = json_data.get("agent_auth")
        
        if not provided_token:
            provided_token = req.args.get("auth")
        
        if not provided_token:
            provided_token = req.headers.get("X-Agent-Auth")
        
        agent_data = agents.get(agent_id)
        
        if not agent_data and not any(a.get("auth") for a in agents.values()):
            return True
        
        if not agent_data:
            return False
        
        stored_token = agent_data.get("auth")
        
        if stored_token and not provided_token:
            return False
        
        if stored_token and provided_token:
            return hmac.compare_digest(stored_token, provided_token)
        
        if not stored_token:
            return True
        
        return False
        
    except Exception as e:
        print(f"[ERROR] verify_agent_request error: {e}")
        return False

def lease_watchdog():
    while True:
        time.sleep(5)
        changed = False
        with LOCK:
            now = datetime.now()
            for t in tasks:
                lease = t.get("lease", {})
                for aid, until_iso in list(lease.items()):
                    if not until_iso:
                        continue
                    try:
                        until_dt = parse_iso(until_iso)
                        if until_dt and until_dt < now:
                            prev_state = t["status"].get(aid)
                            if prev_state in ("RUNNING", "DOWNLOADING", "STARTING_TRANSFER"):
                                t["status"][aid] = "PENDING"
                                t["logs"].setdefault(aid,[]).append(f"{now_iso()}: lease expired -> requeue (was {prev_state})")
                                t.setdefault("lease", {})[aid] = None
                                changed = True
                    except Exception:
                        pass
            if changed:
                persist_all()

def auto_save_daemon():
    while True:
        time.sleep(30)
        try:
            persist_all()
        except Exception as e:
            print("autosave error:", e)

threading.Thread(target=lease_watchdog, daemon=True).start()
threading.Thread(target=auto_save_daemon, daemon=True).start()

# --- Flask endpoints ---
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500

# --- Public endpoints (no auth required) ---
@app.route("/")
def index():
    return "<h1>RMM Server Active</h1><p>Use /server_info for details</p>"

@app.route("/server_info")
def server_info():
    server_auth = sha256_hex(config.get("server_secret", "") or "")
    return jsonify({
        "server_auth": server_auth, 
        "require_tls": config.get("require_tls", False),
        "description": config.get("server_description", "Control Node"),
        "port": SERVER_PORT,
        "agents_count": len(agents),
        "tasks_count": len(tasks)
    })

# ИСПРАВЛЕНИЕ: Добавлен маршрут /api/auth/verify для панели управления
@app.route("/api/auth/verify")
def api_auth_verify():
    username = verify_basic_auth()
    if username:
        user = get_user(username)
        return jsonify({
            "authenticated": True,
            "username": username,
            "privileges": user.get("privileges", []) if user else []
        }), 200
    return jsonify({"authenticated": False}), 401

# ИСПРАВЛЕНИЕ: Добавлены оба маршрута /register и /register_agent для совместимости
@app.route("/register", methods=["POST"])
@app.route("/register_agent", methods=["POST"])
def register_agent():
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id")
    name = data.get("name", agent_id)
    agent_auth = data.get("agent_auth")
    ip = request.remote_addr
    
    if not agent_id:
        return jsonify(ok=False, error="no agent_id"), 400
    
    with LOCK:
        agents.setdefault(agent_id, {})
        
        if name and name != agent_id:
            agents[agent_id]["name"] = name
        
        if "name" not in agents[agent_id]:
            agents[agent_id]["name"] = agent_id
        
        agents[agent_id]["last_seen"] = now_iso()
        agents[agent_id]["ip"] = ip
        agents[agent_id]["status"] = "ONLINE"
        
        if agent_auth and not agents[agent_id].get("auth"):
            agents[agent_id]["auth"] = agent_auth
        
        # Первый агент автоматически апрувится
        if not any(a.get("approved") for a in agents.values()):
            agents[agent_id]["approved"] = True
            agents[agent_id]["first_seen"] = now_iso()
            agents[agent_id]["approved_at"] = now_iso()
            save_json(AGENTS_FILE, agents)
            tech_log({"event": "first_agent_auto_approved", "agent": agent_id})
            return jsonify(ok=True, pending=False, status="approved"), 200
        
        if not agents[agent_id].get("approved"):
            pending_approvals.setdefault(agent_id, {
                "agent_id": agent_id,
                "name": agents[agent_id]["name"],
                "first_seen": agents[agent_id].get("first_seen", now_iso()),
                "ip": ip,
                "status": "AWAIT_ADMIN"
            })
            save_json(PENDING_APPROVALS_FILE, pending_approvals)
        
        save_json(AGENTS_FILE, agents)
        tech_log({"event": "agent_register", "agent": agent_id, "ip": ip, "name": agents[agent_id]["name"]})
    
    return jsonify(ok=True, pending=not agents[agent_id].get("approved", False))

@app.route("/ping", methods=["POST"])
@app.route("/heartbeat", methods=["POST"])
def heartbeat():
    data = request.get_json(silent=True) or {}
    agent = data.get("agent_id") or data.get("agent")
    provided = data.get("agent_auth")
    
    if not agent:
        return "Missing agent id", 400
    
    if is_agent_blocked(agent):
        return "Access Denied", 403
    
    a = agents.get(agent)
    if a and a.get("auth"):
        if not provided or not hmac.compare_digest(provided, a.get("auth")):
            return "Forbidden", 403
    
    with LOCK:
        agents.setdefault(agent, {})
        agents[agent]["last_seen"] = now_iso()
        agents[agent]["ip"] = request.remote_addr
        agents[agent]["status"] = "ONLINE"
        save_json(AGENTS_FILE, agents)
    
    tech_log({"event":"heartbeat", "agent": agent, "ip": request.remote_addr})
    return jsonify({"status": "ok"}), 200

# ИСПРАВЛЕНИЕ: get_task теперь поддерживает и GET и POST для совместимости
@app.route("/get_task", methods=["GET", "POST"])
def get_task():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        agent = data.get("agent_id") or data.get("agent")
    else:
        agent = request.args.get("agent", "")
    
    ip = request.remote_addr

    if not verify_agent_request(request):
        return jsonify({"error": "unauthorized"}), 401

    if is_agent_blocked(agent):
        return jsonify({"error": "blocked"}), 403

    # Обновляем last_seen
    if agent in agents:
        with LOCK:
            agents[agent]["last_seen"] = now_iso()
            agents[agent]["status"] = "ONLINE"
            save_json(AGENTS_FILE, agents)

    if not is_agent_approved(agent):
        with LOCK:
            pending_approvals.setdefault(agent, {
                "agent_id": agent,
                "name": agent,
                "first_seen": now_iso(),
                "ip": ip,
                "status": "AWAIT_ADMIN"
            })
            persist_all()
        return jsonify({"status": "no_task"}), 200

    with LOCK:
        for t in tasks:
            st = t["status"].get(agent)
            should_deliver = False
            
            if st == "PENDING":
                t["status"][agent] = "RUNNING"
                should_deliver = True
            elif st in ["AWAIT_FILE", "DOWNLOAD_NOW"]:
                t["status"][agent] = "DOWNLOAD_NOW"
                should_deliver = True
            elif t.get("task_type") == "UPLOAD_FILE" and st == "AWAIT_UPLOAD":
                should_deliver = True
            elif t.get("task_type") in ["PROCESSES", "FS"]:
                if st == "PENDING" or st == "RUNNING":
                    should_deliver = True

            if should_deliver:
                t_id = str(t.get("id", ""))
                t_cmd = str(t.get("cmd", ""))
                t_url = str(t.get("file_url", "")).strip()
                
                response_data = {
                    "task_id": t_id,
                    "id": t_id,
                    "cmd": t_cmd,
                    "file_url": t_url,
                    "shell": t.get("shell", "cmd"),
                    "save_path": t.get("save_path", ""),
                    "task_type": t.get("task_type", "RUN_CMD"),
                    "target_name": t.get("target_name", ""),
                    "timeout_seconds": t.get("timeout_seconds", 300),
                    "server_auth": sha256_hex(config.get("server_secret", "") or ""),
                    "hmac": ""
                }

                # ИСПРАВЛЕНИЕ: HMAC для многострочных команд
                core_str = f"{t_id}|{t_cmd}|{t_url}"
                key_hex = agents.get(agent, {}).get("auth", "")
                if key_hex:
                    try:
                        key_bytes = bytes.fromhex(key_hex) if key_hex else b''
                        hmac_obj = hmac.new(key_bytes, core_str.encode('utf-8'), hashlib.sha256)
                        response_data["hmac"] = hmac_obj.hexdigest()
                    except Exception as e:
                        print(f"[ERROR] HMAC generation failed: {e}")
                        response_data["hmac"] = ""

                timeout = t.get("timeout_seconds", 300)
                t.setdefault("lease", {})[agent] = (datetime.now(UTC) + timedelta(seconds=timeout)).isoformat()
                
                persist_all()
                return jsonify(response_data)

    return jsonify({"status": "no_task"}), 200

@app.route("/task_info")
def task_info():
    tid = request.args.get("task_id", "")
    agent_id = request.args.get("agent", "")
    
    for t in tasks:
        if t["id"] == tid:
            if agent_id and agent_id in t.get("agent_ids", []):
                return jsonify({
                    "task_id": t["id"],
                    "status": {agent_id: t["status"].get(agent_id)},
                    "cmd": t.get("cmd", "")
                }), 200
            else:
                return jsonify(t), 200
    
    return jsonify({"error": "not found"}), 404

# ИСПРАВЛЕНИЕ: update_status теперь возвращает подтверждение для DONE
@app.route("/update_status", methods=["POST"])
def update_status():
    if not verify_agent_request(request):
        return jsonify(ok=False), 403
    
    data = request.get_json(silent=True) or {}
    tid = data.get("task_id")
    agent = data.get("agent")
    state = data.get("state")

    with LOCK:
        for t in tasks:
            if t["id"] == tid:
                current_status = t["status"].get(agent)
                
                if current_status == "DONE" or current_status == "CANCELLED":
                    return jsonify(status="STOP", action="TERMINATE"), 200

                t["status"][agent] = state
                
                msg = data.get("msg", "")
                t["logs"].setdefault(agent, []).append(f"{now_iso()}: {state} - {msg}")
                
                if "data" in data:
                    t.setdefault("results", {})[agent] = data["data"]
                
                # ИСПРАВЛЕНИЕ: Очищаем lease для DONE и FAILED
                if state in ("DONE", "FAILED"):
                    t.setdefault("lease", {})[agent] = None
                
                persist_all()
                
                # ИСПРАВЛЕНИЕ: Возвращаем подтверждение для DONE
                if state == "DONE":
                    return jsonify(status="CONTINUE", confirmed=True), 200
                
                return jsonify(status="CONTINUE"), 200
                
    return jsonify(status="STOP", error="task_not_found"), 200

@app.route("/telemetry", methods=["POST"])
def telemetry_ingest():
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id")
    
    if not agent_id:
        return jsonify(ok=False), 400

    os.makedirs("telemetry", exist_ok=True)
    
    current_telem = load_json(f"telemetry/{agent_id}.json", {})
    current_telem.update(data)
    
    save_json(f"telemetry/{agent_id}.json", current_telem)
    return jsonify(ok=True)

@app.route("/upload_file", methods=["POST"])
def upload_file():
    if not verify_agent_request(request):
        return "Forbidden", 403
    
    agent = request.args.get("agent")
    task_id = request.args.get("task_id")
    
    if not agent or not task_id:
        return "Missing parameters", 400
    
    with LOCK:
        t = next((x for x in tasks if x["id"] == task_id), None)
        if not t:
            return "Task not found", 404
        
        if agent not in t.get("agent_ids", []):
            return "Agent not in task", 403
        
        current_status = t["status"].get(agent)
        if current_status not in ["AWAIT_UPLOAD", "UPLOADING"]:
            return "Invalid task status", 400
        
        t["status"][agent] = "UPLOADING"
        
        data = request.get_data()
        
        fname = t.get("save_path")
        if not fname:
            fname = f"{task_id}_{agent}.bin"
        
        import re
        safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', fname)
        safe_name = safe_name[:100]
        
        outpath = os.path.join(UPLOAD_DIR, safe_name)
        
        try:
            with open(outpath, "wb") as f:
                f.write(data)
            
            t["status"][agent] = "UPLOAD_DONE"
            t["logs"].setdefault(agent, []).append(
                f"{now_iso()}: Файл загружен на сервер как {safe_name} ({len(data)} байт)"
            )
            
            t.setdefault("uploaded_files", {})[agent] = {
                "filename": safe_name,
                "size": len(data),
                "path": outpath,
                "uploaded_at": now_iso()
            }
            
            persist_all()
            return "OK"
        except Exception as e:
            t["status"][agent] = "UPLOAD_FAILED"
            t["logs"].setdefault(agent, []).append(
                f"{now_iso()}: Ошибка загрузки файла: {str(e)}"
            )
            persist_all()
            return str(e), 500

@app.route("/files/<path:name>")
def files(name):
    return send_from_directory("files", name, as_attachment=True)

# --- API endpoints (require user auth) ---
@app.route("/api/state")
@require_auth
def api_state():
    cfg = load_config()
    check_agent_online_status()
    
    return jsonify({
        "server_desc": cfg.get("server_description", "Control Node"),
        "agents": agents,
        "tasks": tasks,
        "pending": pending_approvals
    }), 200

@app.route("/api/config", methods=["GET", "POST"])
@require_auth
def api_config():
    if request.method == "GET":
        return jsonify(config), 200
    
    if request.method == "POST":
        if "shutdown_server" not in get_user(request.username).get("privileges", []):
            return jsonify({"error": "Insufficient privileges"}), 403
        
        data = request.get_json(silent=True) or {}
        
        if "server_secret" in data:
            config["server_secret"] = data["server_secret"]
        
        if "server_description" in data:
            config["server_description"] = data["server_description"]
        
        save_config(config)
        audit(request.username, "config_update", config, request.remote_addr)
        return jsonify({"ok": True}), 200

@app.route("/api/pending", methods=["GET"])
@require_priv("approve_agent")
def api_pending():
    return jsonify(pending_approvals), 200

@app.route("/api/users", methods=["GET"])
@require_priv("manage_users")
def api_users_list():
    out = {}
    for u, v in users.items():
        out[u] = {
            "privileges": v.get("privileges", []),
            "created_at": v.get("created_at", ""),
            "cmd_blacklist": v.get("cmd_blacklist", [])
        }
    return jsonify(out), 200

@app.route("/api/users/create", methods=["POST"])
@require_priv("manage_users")
def api_users_create():
    j = request.get_json(silent=True) or {}
    username = j.get("username", "").strip()
    pwd = j.get("password", "")
    privs = j.get("privileges", [])
    
    if not username or not pwd:
        return jsonify({"error": "missing", "message": "Требуется имя пользователя и пароль"}), 400
    
    if len(username) < 3:
        return jsonify({"error": "invalid", "message": "Имя пользователя должно быть минимум 3 символа"}), 400
    
    success, message = create_user(username, pwd, privs)
    if success:
        audit(request.username, "user_create", {"user": username})
        return jsonify({"ok": True, "message": "Пользователь создан"}), 201
    else:
        return jsonify({"error": "creation_failed", "message": message}), 400

@app.route("/api/users/edit", methods=["POST"])
@require_priv("manage_users")
def api_users_edit():
    j = request.get_json(silent=True) or {}
    username = j.get("username", "")
    
    if username not in users:
        return jsonify({"error": "not_found"}), 404
    
    pwd = j.get("password", "").strip()
    privs = j.get("privileges", users[username].get("privileges", []))
    
    if pwd:
        if len(pwd) < 8:
            return jsonify({"error": "weak_password", "message": "Пароль должен быть минимум 8 символов"}), 400
        
        if not any(c.isupper() for c in pwd):
            return jsonify({"error": "weak_password", "message": "Пароль должен содержать хотя бы одну заглавную букву"}), 400
        
        if not any(c.islower() for c in pwd):
            return jsonify({"error": "weak_password", "message": "Пароль должен содержать хотя бы одну строчную букву"}), 400
        
        if not any(c.isdigit() for c in pwd):
            return jsonify({"error": "weak_password", "message": "Пароль должен содержать хотя бы одну цифру"}), 400
        
        users[username]["password_hash"] = generate_password_hash(pwd)
    
    if username == "Admin":
        users[username]["privileges"] = PRIVS
    else:
        users[username]["privileges"] = privs
    
    save_users()
    audit(request.username, "user_edit", {"target": username})
    return jsonify({"ok": True}), 200

@app.route("/api/users/delete", methods=["POST"])
@require_priv("manage_users")
def api_users_delete():
    j = request.get_json(silent=True) or {}
    username = j.get("username", "")
    
    if not username or username == "Admin":
        return jsonify({"error": "forbidden"}), 403
    
    if username in users:
        del users[username]
        save_users()
        audit(request.username, "user_delete", {"user": username})
        return jsonify({"ok": True}), 200
    
    return jsonify({"error": "not_found"}), 404

@app.route("/api/user/<username>/blacklist", methods=["GET", "PUT"])
@require_priv("manage_users")
def manage_blacklist(username):
    if username not in users:
        return jsonify({"error": "user_not_found"}), 404
    
    if username == "Admin" and request.username != "Admin":
        return jsonify({"error": "cannot_modify_admin"}), 403
    
    if request.method == "GET":
        return jsonify({
            "username": username,
            "blacklist": users[username].get("cmd_blacklist", [])
        })
    
    elif request.method == "PUT":
        data = request.get_json(silent=True) or {}
        
        if "commands" not in data or not isinstance(data["commands"], list):
            return jsonify({"error": "invalid_data"}), 400
        
        cleaned_commands = []
        for cmd in data["commands"]:
            if isinstance(cmd, str) and cmd.strip():
                cleaned_commands.append(cmd.strip())
        
        users[username]["cmd_blacklist"] = cleaned_commands
        save_users()
        
        audit(request.username, "blacklist_update", 
              {"target": username, "commands": cleaned_commands}, 
              request.remote_addr)
        
        return jsonify({"success": True, "blacklist": cleaned_commands})

@app.route("/api/privs", methods=["GET"])
@require_auth
def api_privs():
    return jsonify({"privs": PRIVS}), 200

@app.route("/api/logs", methods=["GET"])
@require_priv("view_logs")
def api_logs():
    which = request.args.get("which", "audit")
    if which == "audit":
        path = LOG_AUDIT
    elif which == "http":
        path = LOG_HTTP
    else:
        path = LOG_TECH
    
    out = []
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()[-500:]
                for l in lines:
                    try:
                        out.append(json.loads(l))
                    except:
                        out.append({"raw": l.strip()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    return jsonify(out)

@app.route("/api/tasks", methods=["GET"])
@require_auth
def api_tasks_list():
    return jsonify(tasks), 200

@app.route("/api/tasks/create", methods=["POST"])
def api_tasks_create():
    username = verify_basic_auth()
    if not username:
        return jsonify({"error": "Authentication required"}), 401
    
    user = get_user(username)
    if not user:
        return jsonify({"error": "User not found"}), 403
    
    # Check if form data (for file upload) or JSON
    if request.content_type and 'multipart/form-data' in request.content_type:
        task_type = request.form.get("task_type", "RUN_CMD")
        cmd = request.form.get("cmd", "").rstrip()  # ИСПРАВЛЕНИЕ: rstrip вместо strip
        shell = request.form.get("shell", "cmd")
        save_path = request.form.get("save_path", "").strip()
        source_path_upload = request.form.get("source_path_upload", "").strip()
        target_name = request.form.get("target_name", "").strip()
        agent_ids = request.form.getlist("agents")
        timeout_seconds = int(request.form.get("timeout", "300") or "300")
        
        # Handle file upload
        file_url = ""
        file_hash = ""
        if "file" in request.files:
            f = request.files["file"]
            if f and f.filename:
                try:
                    content = f.read()
                    file_hash = hashlib.sha256(content).hexdigest()
                    fname = f"task-{int(time.time())}_{os.path.basename(f.filename)}"
                    outdir = "files"
                    os.makedirs(outdir, exist_ok=True)
                    
                    with open(os.path.join(outdir, fname), "wb") as of:
                        of.write(content)
                    
                    file_url = f"{request.host_url.rstrip('/')}/files/{fname}"
                except Exception as e:
                    return jsonify({"error": f"File upload failed: {e}"}), 500
    else:
        data = request.get_json(silent=True) or {}
        task_type = data.get("task_type", "RUN_CMD")
        cmd = data.get("cmd", "").rstrip()  # ИСПРАВЛЕНИЕ: rstrip вместо strip
        shell = data.get("shell", "cmd")
        save_path = data.get("save_path", "").strip()
        source_path_upload = data.get("source_path_upload", "").strip()
        target_name = data.get("target_name", "").strip()
        agent_ids = data.get("agents", [])
        timeout_seconds = int(data.get("timeout", "300") or "300")
        file_url = ""
        file_hash = ""
    
    # Check privileges
    if task_type == "RUN_CMD" and "run_cmd" not in user.get("privileges", []):
        return jsonify({"error": "Insufficient privileges: run_cmd required"}), 403
    
    if task_type == "UPLOAD_FILE" and "pull_file" not in user.get("privileges", []):
        return jsonify({"error": "Insufficient privileges: pull_file required"}), 403
    
    # Check command blacklist
    if task_type == "RUN_CMD" and cmd:
        if not is_command_allowed(username, cmd):
            return jsonify({
                "error": "command_blocked",
                "message": f"Команда содержит запрещенные выражения для пользователя {username}"
            }), 403
    
    # If no agents selected, use all approved agents
    if not agent_ids:
        agent_ids = [aid for aid, a in agents.items() if a.get("approved")]
    
    # Check for existing active tasks
    if task_type != "UPLOAD_FILE":
        with LOCK:
            for existing_task in tasks:
                if existing_task.get("task_type") == task_type:
                    common_agents = set(existing_task.get("agent_ids", [])) & set(agent_ids)
                    if common_agents:
                        for agent in common_agents:
                            status = existing_task["status"].get(agent)
                            if status not in ["DONE", "CANCELLED", "FAILED"]:
                                return jsonify({
                                    "error": "active_task_exists",
                                    "message": f"Уже есть активная задача {existing_task['id']}"
                                }), 400
    
    # For UPLOAD_FILE, use cmd as path on agent
    if task_type == "UPLOAD_FILE":
        cmd = source_path_upload
        save_path = target_name
        status = {a: "AWAIT_UPLOAD" for a in agent_ids}
    elif task_type in ["PROCESSES", "FS"]:
        status = {a: "PENDING" for a in agent_ids}
    else:
        status = {a: ("AWAIT_FILE" if file_url else "PENDING") for a in agent_ids}
    
    task_id = f"task-{int(time.time())}-{secrets.token_hex(4)}"
    
    task_obj = {
        "id": task_id,
        "cmd": cmd,
        "shell": shell,
        "file_url": file_url,
        "file_hash": file_hash,
        "save_path": save_path,
        "agent_ids": agent_ids,
        "status": status,
        "created_at": now_iso(),
        "logs": {a: [] for a in agent_ids},
        "timeout_seconds": timeout_seconds,
        "task_type": task_type,
        "creator": username
    }
    
    # ИСПРАВЛЕНИЕ: Используем LOCK для безопасной записи
    with LOCK:
        tasks.append(task_obj)
        save_json(TASKS_FILE, tasks)
    
    audit(username, "task_create", {"task": task_id, "type": task_type, "agents": agent_ids})
    
    return jsonify({"ok": True, "task_id": task_id}), 201

@app.route("/api/tasks/<task_id>", methods=["GET"])
@require_auth
def api_task_info(task_id):
    for t in tasks:
        if t["id"] == task_id:
            return jsonify(t)
    return jsonify({"error": "not found"}), 404

@app.route("/api/tasks/<task_id>/monitoring", methods=["GET"])
@require_priv("view_info")
def api_task_monitoring(task_id):
    agent_id = request.args.get("agent_id")
    
    for t in tasks:
        if t["id"] == task_id and agent_id in t.get("agent_ids", []):
            if "results" in t and agent_id in t["results"]:
                return jsonify(t["results"][agent_id])
    
    return jsonify({"error": "no data"}), 404

@app.route("/api/tasks/<task_id>/update_path", methods=["POST"])
@require_priv("view_info")
def api_task_update_path(task_id):
    data = request.get_json(silent=True) or {}
    new_path = data.get("new_path")
    agent_id = data.get("agent_id")
    
    if not task_id or not agent_id:
        return jsonify({"ok": False, "error": "missing_params"}), 400
    
    if new_path is None or new_path == "":
        new_path = "ROOT"
    
    with LOCK:
        for task in tasks:
            if task["id"] == task_id and agent_id in task["agent_ids"]:
                task["cmd"] = new_path
                task["last_path_update"] = now_iso()
                
                if task["task_type"] == "FS":
                    task["status"][agent_id] = "PENDING"
                
                save_json(TASKS_FILE, tasks)
                
                tech_log({
                    "event": "monitoring_path_updated",
                    "task_id": task_id,
                    "agent_id": agent_id,
                    "new_path": new_path
                })
                
                return jsonify({"ok": True})
    
    return jsonify({"ok": False, "error": "task_not_found"}), 404

@app.route("/api/tasks/<task_id>/stop", methods=["POST"])
@require_priv("view_info")
def api_task_stop(task_id):
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id")
    
    with LOCK:
        for t in tasks:
            if t["id"] == task_id and agent_id in t["agent_ids"]:
                t["status"][agent_id] = "DONE"
                save_json(TASKS_FILE, tasks)
                return jsonify({"ok": True})
    
    return jsonify({"ok": False, "error": "task_not_found"}), 404

@app.route("/api/tasks/delete", methods=["POST"])
@require_priv("cancel_tasks")
def api_tasks_delete():
    data = request.get_json(silent=True) or {}
    tid = data.get("task_id")
    
    with LOCK:
        initial = len(tasks)
        tasks[:] = [t for t in tasks if t.get("id") != tid]
        if len(tasks) < initial:
            save_json(TASKS_FILE, tasks)
            audit(request.username, "task_delete", {"task": tid})
            return jsonify({"ok": True})
    
    return jsonify({"ok": False, "error": "not_found"}), 404

@app.route("/api/tasks/force_done", methods=["POST"])
@require_priv("cancel_tasks")
def api_tasks_force_done():
    data = request.get_json(silent=True) or {}
    tid = data.get("task_id")
    
    with LOCK:
        for t in tasks:
            if t.get("id") == tid:
                for a in t.get("agent_ids", []):
                    t["status"][a] = "DONE"
                    t.setdefault("lease", {})[a] = None
                save_json(TASKS_FILE, tasks)
                audit(request.username, "task_force_done", {"task": tid})
                return jsonify({"ok": True})
    
    return jsonify({"ok": False, "error": "not_found"}), 404

@app.route("/api/agents", methods=["GET"])
@require_auth
def api_agents_list():
    return jsonify(agents), 200

@app.route("/api/agents/<agent_id>", methods=["GET"])
@require_priv("view_info")
def api_agent_info(agent_id):
    if agent_id not in agents:
        return jsonify({"error": "not found"}), 404
    
    telem_path = f"telemetry/{agent_id}.json"
    telem = load_json(telem_path, None)
    
    return jsonify({"agent": agents[agent_id], "telemetry": telem})

@app.route("/api/agents/delete", methods=["POST"])
@require_priv("approve_agent")
def api_agents_delete():
    data = request.get_json(silent=True) or {}
    aid = data.get("agent_id")
    
    with LOCK:
        if aid in agents:
            del agents[aid]
        
        for t in tasks:
            if aid in t.get("status", {}):
                del t["status"][aid]
            if aid in t.get("agent_ids", []):
                t["agent_ids"].remove(aid)
        
        if aid in pending_approvals:
            del pending_approvals[aid]
        
        persist_all()
        audit(request.username, "agent_delete", {"agent": aid})
    
    return jsonify({"ok": True})

@app.route("/api/agents/rename", methods=["POST"])
@require_priv("approve_agent")
def api_agents_rename():
    data = request.get_json(silent=True) or {}
    aid = data.get("agent_id")
    new_name = data.get("new_name", "").strip()
    
    if not aid:
        return jsonify({"ok": False, "error": "missing"}), 400
    
    with LOCK:
        if aid in agents:
            agents[aid]["name"] = new_name or aid
            save_json(AGENTS_FILE, agents)
            audit(request.username, "agent_rename", {"agent": aid, "new": new_name})
            return jsonify({"ok": True})
    
    return jsonify({"ok": False, "error": "not_found"}), 404

@app.route("/api/agents/approve", methods=["POST"])
@require_priv("approve_agent")
def api_agents_approve():
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id")
    action = data.get("action")
    
    if not agent_id or action not in ("approve", "block"):
        return jsonify({"error": "invalid parameters"}), 400
    
    with LOCK:
        if agent_id in pending_approvals:
            if action == "approve":
                p_data = pending_approvals.pop(agent_id)
                
                if agent_id not in agents:
                    agents[agent_id] = {}
                
                agents[agent_id].update({
                    "name": p_data.get("name") or agent_id,
                    "ip": p_data.get("ip"),
                    "first_seen": p_data.get("first_seen"),
                    "approved": True,
                    "approved_at": now_iso(),
                    "status": "ONLINE"
                })
                audit(request.username, "agent_approved", {"agent": agent_id})
            
            elif action == "block":
                pending_approvals.pop(agent_id)
                agents.setdefault(agent_id, {})["approved"] = False
                agents[agent_id]["status"] = "BLOCKED"
                audit(request.username, "agent_blocked", {"agent": agent_id})
            
            persist_all()
            return jsonify({"ok": True})
    
    return jsonify({"error": "agent not found"}), 404

@app.route("/api/system/shutdown", methods=["POST"])
@require_priv("shutdown_server")
def api_system_shutdown():
    audit(request.username, "server_shutdown", {}, request.remote_addr)
    
    def shutdown_delayed():
        time.sleep(1)
        os._exit(0)
    
    threading.Thread(target=shutdown_delayed, daemon=True).start()
    return jsonify({"ok": True, "message": "Server shutdown initiated"})

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    csp = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';"
    response.headers['Content-Security-Policy'] = csp
    
    return response

threading.Thread(target=status_checker_daemon, daemon=True).start()

if __name__ == "__main__":
    check_agent_online_status()
    port = int(config.get("port", 5000) or 5000)
    cert_file = "myserver.local+1.pem"
    key_file = "myserver.local+1-key.pem"

    if os.path.exists(cert_file) and os.path.exists(key_file):
        print(f"[*] Starting SECURE HTTPS server on port {port}")
        app.run("0.0.0.0", port=port, debug=False, ssl_context=(cert_file, key_file), threaded=True)
    else:
        print("[!] SSL certificates not found! Falling back to HTTP.")
        app.run("0.0.0.0", port=port, debug=False, threaded=True)
