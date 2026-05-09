# untitled-rmm
RMM for Windows 10+ Home for bulk task issuance

# WARNING. it is JUST BETA. much function could dont work

[English](#en)
[Russian](#ru)

---

# EN

---


## 📋 Table of Contents

1. [Introduction](#introduction)
2. [System Architecture](#system-architecture)
3. [System Requirements](#system-requirements)
4. [Installation and Setup](#installation-and-setup)
5. [Agent Management](#agent-management)
6. [Task Management](#task-management)
7. [User Management](#user-management)
8. [Logging System](#logging-system)
9. [Monitoring and Telemetry](#monitoring-and-telemetry)
10. [Uninstallation and Removal](#uninstallation-and-removal)
11. [Security](#security)
12. [Troubleshooting](#troubleshooting)
13. [API Reference](#api-reference)

---

## Introduction

**RMM System** is a comprehensive solution for remote management and monitoring of Windows computers in a corporate network. The system consists of three main components:

- **Server** (`server.py`) — central management server in Python/Flask
- **Agent** (`HomeDomainClient.exe`) — Windows client agent (service)
- **Control Panel** (`controlpanel.exe`) — graphical management interface in PyQt5

### Key Features:

✅ **Remote command execution** (PowerShell/CMD)  
✅ **File transfer** in both directions (push/pull)  
✅ **Real-time monitoring** (processes, disks, network)  
✅ **Agent approval system** (secure connection)  
✅ **Flexible privilege system** for administrators  
✅ **Audit logging** (JSON format)  
✅ **Automatic server discovery** on network  
✅ **HTTPS/SSL support** for secure data transmission  
✅ **Task persistence** (execution after reboot)  

---

## System Architecture

### Overall System Diagram

```
┌─────────────────────┐
│  Control Panel      │  ◄─── Administrator
│  (controlpanel.exe) │
└──────────┬──────────┘
           │ HTTPS/HTTP
           │ (REST API)
           ▼
┌─────────────────────┐
│   RMM Server        │
│   (server.py)       │  ◄─── Flask + JSON files
│   Port: 5000        │
└──────────┬──────────┘
           │ HTTPS/HTTP
           │ (Polling)
           ▼
┌─────────────────────┐
│  Agent (Service)    │  ◄─── Windows machines
│  HomeDomainClient   │       (clients)
│  .exe               │
└─────────────────────┘
```

### System Components

#### 1. **Server (server.py)**

**Technologies:** Python 3.10+, Flask, Threading

**Main Functions:**
- REST API for agent and control panel communication
- User management with privilege system
- Task queue with support for various task types
- New agent approval system
- Agent status monitoring (ONLINE/OFFLINE)
- Telemetry storage
- Full action auditing

**Data Storage (JSON files):**
```
server/
├── users.json              # Users and their privileges
├── agents.json             # Registered agents
├── tasks.json              # Task queue
├── pending_approvals.json  # Agents awaiting approval
├── config.json             # Server configuration
├── audit.log               # Audit log
├── http.log                # HTTP requests log
├── tech.log                # Technical logs
├── files/                  # Uploaded files
└── telemetry/              # Agent telemetry
    ├── <agent_id>.json
    └── ...
```

#### 2. **Agent (HomeDomainClient.exe)**

**Technologies:** C++17, WinAPI, Windows Service, WinHTTP, nlohmann/json

**Main Functions:**
- Server registration with unique hardware ID
- Server polling for tasks (every 60 seconds)
- Command execution (CMD/PowerShell)
- File upload and download
- Telemetry collection (CPU, RAM, disks, processes, network)
- Automatic server discovery on network
- Task persistence (saved in tasks.json)
- Windows Service mode operation

**Installation Structure:**
```
C:\Program Files\RMMAgent\
├── HomeDomainClient.exe    # Main executable
├── agent.conf              # Configuration (agent_auth, server_auth, server URL)
├── agent.log               # Agent log
└── tasks.json              # Local task queue
```

**Secrets stored in registry:**
```
HKLM\SOFTWARE\MYRMM\Secrets\
├── agent_auth     (REG_SZ)   # SHA256 hash for authentication
└── server_auth    (REG_SZ)   # SHA256 hash for server verification
```

#### 3. **Control Panel (controlpanel.exe)**

**Technologies:** Python 3.10+, PyQt5, Requests

**Main Functions:**
- Graphical management interface
- Multi-server management
- Task creation and management
- User management
- Real-time agent monitoring
- Log viewing
- File management

---

## System Requirements

### For Server:

| Component | Minimum | Recommended |
|-----------|---------|---------------|
| OS | Windows 10/11, Linux, macOS | Ubuntu 20.04 LTS / Windows Server 2019+ |
| Python | 3.10+ | 3.11+ |
| RAM | 512 MB | 2 GB |
| Storage | 1 GB | 10 GB (for logs/telemetry) |
| Network | 100 Mbit/s | 1 Gbit/s |
| Ports | 5000 (HTTP) or 443/5000 (HTTPS) | — |

**Python Dependencies:**
```bash
flask>=2.3.0
werkzeug>=2.3.0
requests>=2.31.0
```

### For Agent (Client Machines):

| Component | Minimum |
|-----------|---------|
| OS | **Windows 10** (version 1809+) or **Windows 11** |
| Editorial | Windows Home |
| Architecture | x86 (32-bit) |
| RAM | 256 MB free |
| Storage | 100 MB |
| Privileges | Administrator rights for installation |
| .NET | Not required (native C++) |

**⚠️ IMPORTANT:** Agent works ONLY on Windows 10/11 !

### For Control Panel:

| Component | Requirements |
|-----------|--------------|
| OS | Windows 10/11 |
| Python | 3.10+ |
| Dependencies | PyQt5, requests |

---

## Installation and Setup

### 1. Server Installation

#### Step 1: Install Python Dependencies

```bash
# Create virtual environment (optional)
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Install dependencies
pip install flask werkzeug requests
```

#### Step 2: Generate Secret Keys

Run `hashmade.py` to generate keys:

```bash
python hashmade.py
```

**Output:**
```
Secret key (server): a1b2c3d4e5f6...  (32 bytes in HEX)
SHA256 hash (agent.conf): 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
```

**Save both values!**

#### Step 3: Configure Server

Create/edit `config.json`:

```json
{
  "server_secret": "a1b2c3d4e5f6...",
  "server_description": "NODE-2026: MAIN MANAGEMENT NODE",
  "port": 5000
}
```

- `server_secret` — secret key from hashmade.py (not hash!)
- `port` — server port (default 5000)

#### Step 4: Configure HTTPS (optional but recommended)

SSL certificates are required for HTTPS. Use **mkcert** for local network:

```bash
# Install mkcert
# Windows: scoop install mkcert
# Linux: apt install mkcert / brew install mkcert

# Generate certificates
mkcert myserver.local 192.168.1.100

# Rename files:
# myserver.local+1.pem       → keep as is
# myserver.local+1-key.pem   → keep as is
```

Place files in the folder with `server.py`.

**For production use Let's Encrypt or corporate CA.**

#### Step 5: Create Administrator

On first launch, an **Admin** user is created. The first time Admin logs in, any password will be accepted, and it will be saved forever. (To reset, delete the hash contents in the user data file). Set password via API:

```bash
# Start server
python server.py

# In another terminal, set password for Admin:
curl -X POST http://localhost:5000/api/users/set_password \
  -H "Content-Type: application/json" \
  -d '{"username": "Admin", "password": "YourSecurePassword123!"}'
```

**⚠️ Password requirements:**
- Minimum 8 characters
- At least 1 uppercase letter
- At least 1 lowercase letter
- At least 1 digit

#### Step 6: Start Server

```bash
python server.py
```

**Output:**
```
[*] Starting SECURE HTTPS server on port 5000
 * Running on https://0.0.0.0:5000
```

Server is ready! Now install agents.

---

### 2. Agent Installation

Agent is distributed as a **compiled .exe** file, ready for installation.

#### Prepare Installation Package

Structure:
```
agent_installer/
├── HomeDomainAgenInstaller.exe  # Installer
└── agent/
    ├── HomeDomainClient.exe     # Agent (service)
    └── agent.conf               # Configuration
```

#### Configure `agent.conf`

Create `agent.conf` with the following content:

```ini
server=https://192.168.1.100:5000
agent_auth=9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
server_auth=9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
```

**Parameters:**
- `server` — server address (HTTP/HTTPS)
- `agent_auth` — SHA256 hash from hashmade.py
- `server_auth` — same SHA256 hash (for server verification)

**⚠️ IMPORTANT:**
- Use **HTTPS** in production
- Specify correct server IP/domain
- Hashes must match those in server's `config.json`

#### Install Agent on Client Machine

1. **Copy `agent_installer` folder to target computer**

2. **Run installer as administrator:**

   ```cmd
   # Right-click → "Run as administrator"
   HomeDomainAgenInstaller.exe
   ```

   **Installation process:**
   - Create `C:\Program Files\RMMAgent` folder
   - Copy `HomeDomainClient.exe` and `agent.conf`
   - Copy config to system folders (`System32`, `SysWOW64`)
   - Migrate secrets to registry (`HKLM\SOFTWARE\MYRMM\Secrets`)
   - Install Windows service `RMMService`
   - Configure auto-start
   - Start service

3. **Verify installation:**

   ```cmd
   # Check service status
   sc query RMMService
   
   # Output should contain:
   # STATE: 4 RUNNING
   ```

4. **Check logs:**

   ```cmd
   # View agent log
   type "C:\Program Files\RMMAgent\agent.log"
   ```

   Successful registration:
   ```
   [*] Hardware-bound ID: HW-ABCD1234EFGH5678
   [?] Probing config server: https://192.168.1.100:5000
   [+] DISCOVERED: https://192.168.1.100:5000
   [!] Connected to https://192.168.1.100:5000. Starting main loop.
   [*] Heartbeat OK
   ```

#### Automatic Server Discovery

If `server=AUTO` is specified in `agent.conf` or server is unavailable, agent automatically:

1. **Scans local network** for available servers
2. **Excludes VPN interfaces** (WireGuard, OpenVPN, Hamachi)
3. **Checks /server_info** on each host
4. **Connects to the first server found**

**Timeouts:**
- Network scan: 3000 ms per host
- UDP Discovery: 2000 ms
- Search retry: every 10 seconds

---

### 3. Control Panel Installation

#### Option 1: Run from Source

```bash
# Install dependencies
pip install PyQt5 requests

# Run panel
python controlpanel.py
```

#### Option 2: Compiled .exe

```bash
# Use PyInstaller for compilation
pyinstaller --onefile --windowed --icon=icon.ico controlpanel.py

# Run
dist/controlpanel.exe
```

#### First Launch

1. **Open Control Panel**
2. **Add server:**
   - Click "➕ Add Server"
   - Specify:
     - **Name**: `Main Server`
     - **Host/IP**: `192.168.1.100`
     - **Port**: `5000`
     - **HTTPS**: ✅ (if SSL configured)
     - **Verify SSL**: ❌ (for self-signed certificates)
   - Click "💾 Save"

3. **Connect to server:**
   - Select server from list
   - Click "🔌 Connect"
   - Enter:
     - **Username**: `Admin`
     - **Password**: `YourSecurePassword123!`
   - Click "Login"

4. **Done!** You're in the main control panel.

---

## Agent Management

### Agent Lifecycle

```
┌──────────────┐
│ Install      │
│ Agent        │
└──────┬───────┘
       │
       ▼
┌──────────────────┐
│ First connection │  → Agent sends registration
│ to server        │     with hardware ID
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ PENDING_APPROVAL │  → Agent in approval queue
└──────┬───────────┘
       │
       │ Administrator approves/blocks
       ▼
┌──────────────────┐
│ APPROVED         │  → Agent active, accepts tasks
│ (status: ONLINE) │
└──────┬───────────┘
       │
       │ Agent sends heartbeat every 60 sec
       │
       ├─► last_seen updated
       │
       │ If no heartbeat > 120 sec
       ▼
┌──────────────────┐
│ status: OFFLINE  │
└──────────────────┘
```

### Agent Approval

#### Through Control Panel:

1. **Open "Pending Agents" tab**
2. **Select agent from list** (shows: ID, name, IP, first connection)
3. **Click:**
   - **"✅ Approve"** — agent becomes active
   - **"🚫 Block"** — agent gets blocked

#### Through API:

```bash
curl -X POST https://192.168.1.100:5000/api/agents/approve \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "HW-ABCD1234EFGH5678",
    "action": "approve"
  }'
```

### Agent Status Monitoring

**Statuses:**
- **ONLINE** — last heartbeat < 120 seconds ago
- **OFFLINE** — last heartbeat > 120 seconds ago
- **UNKNOWN** — agent never sent heartbeat
- **BLOCKED** — agent blocked by administrator

**In Control Panel:**
- Green indicator 🟢 — ONLINE
- Red indicator 🔴 — OFFLINE
- Gray indicator ⚪ — UNKNOWN
- Black indicator ⚫ — BLOCKED

**Automatic check:**
Server updates all agent statuses every 120 seconds.

### Rename Agent

```bash
# Through API
curl -X POST https://192.168.1.100:5000/api/agents/rename \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "HW-ABCD1234EFGH5678",
    "new_name": "Office-PC-01"
  }'
```

**Through Control Panel:**
1. Find agent in table
2. Click "✏️ Rename"
3. Enter new name
4. Click OK

### Delete Agent

**⚠️ IMPORTANT:** Deleting agent from server does NOT remove service from client machine!

**Through Control Panel:**
1. Select agent
2. Click "🗑️ Delete"
3. Confirm deletion

**What happens:**
- Agent removed from `agents.json`
- All agent tasks marked inactive
- Agent removed from pending_approvals (if there)
- Entry created in audit.log

**To remove service from client machine:**
See [Uninstallation and Removal](#uninstallation-and-removal).

### View Agent Information

**Through Control Panel:**
1. Click on agent row in table
2. Detailed information window opens:
   - System information (OS, version, architecture)
   - Hardware ID
   - IP address
   - Registration time
   - Last heartbeat
   - Status
   - Telemetry (CPU, RAM, disks, network, processes)

**Through API:**

```bash
curl https://192.168.1.100:5000/api/agents/HW-ABCD1234EFGH5678 \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)"
```

**Response:**
```json
{
  "agent": {
    "name": "Office-PC-01",
    "ip": "192.168.1.50",
    "status": "ONLINE",
    "approved": true,
    "first_seen": "2026-03-20T10:30:00Z",
    "last_seen": "2026-03-20T14:25:30Z"
  },
  "telemetry": {
    "os_info": {
      "name": "Windows 11 Pro",
      "version": "10.0.22631"
    },
    "cpu": {
      "usage_percent": 23.5,
      "cores": 8
    },
    "memory": {
      "total_mb": 16384,
      "used_mb": 8192,
      "percent": 50.0
    },
    "disks": [
      {
        "drive": "C:",
        "total_gb": 476.94,
        "free_gb": 123.45,
        "percent_used": 74.1
      }
    ],
    "network": {
      "interfaces": [
        {
          "name": "Ethernet",
          "ip": "192.168.1.50",
          "mac": "00:11:22:33:44:55"
        }
      ]
    },
    "top_processes": [
      {
        "name": "chrome.exe",
        "pid": 1234,
        "memory_mb": 512,
        "cpu_percent": 5.2
      }
    ]
  }
}
```

---

## Task Management

### Task Types

RMM supports the following task types:

| Type | Description | Parameters |
|------|-------------|------------|
| **RUN_CMD** | Execute command | `cmd`, `shell` (cmd/powershell), `timeout` |
| **PUSH_FILE** | Send file to agent | `file_url`, `save_path` |
| **PULL_FILE** | Receive file from agent | `file_path` |
| **PS** | Process monitoring | — |
| **FS** | File system monitoring | `path` (path to scan) |

### Create Task

#### Through Control Panel:

1. **Click "➕ Create Task"**
2. **Select task type:**
   - **RUN_CMD** — execute command
   - **PUSH_FILE** — send file
   - **PULL_FILE** — receive file
   - **Monitoring** (PS/FS)

3. **Fill in parameters:**

**Example: RUN_CMD**
```
Type: RUN_CMD
Command: ipconfig /all
Shell: cmd
Timeout: 30 seconds
Agents: Office-PC-01, Office-PC-02
```

**Example: PUSH_FILE**
```
Type: PUSH_FILE
File: C:\Users\Admin\Documents\config.xml
Agent path: C:\ProgramData\MyApp\config.xml
Agents: Office-PC-01
```

**Example: PULL_FILE**
```
Type: PULL_FILE
Agent path: C:\Users\User\Documents\report.pdf
Agents: Office-PC-03
```

4. **Click "Create"**

Task is added to queue and will be executed on next agent polling (up to 60 sec).

#### Through API:

**RUN_CMD:**
```bash
curl -X POST https://192.168.1.100:5000/api/tasks \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "RUN_CMD",
    "cmd": "Get-Process | Sort-Object CPU -Descending | Select-Object -First 10",
    "shell": "powershell",
    "timeout_seconds": 60,
    "agent_ids": ["HW-ABCD1234EFGH5678"]
  }'
```

**PUSH_FILE:**
```bash
# First upload file to server
curl -X POST https://192.168.1.100:5000/api/files/upload \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)" \
  -F "file=@/path/to/local/file.exe"

# Then create PUSH_FILE task
curl -X POST https://192.168.1.100:5000/api/tasks \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "PUSH_FILE",
    "file_url": "https://192.168.1.100:5000/files/file.exe",
    "save_path": "C:\\Temp\\file.exe",
    "agent_ids": ["HW-ABCD1234EFGH5678"]
  }'
```

### Task Statuses

**Each agent has its own task status:**

- **PENDING** — task created, waiting for execution
- **RUNNING** — task is being executed by agent
- **DONE** — task completed successfully
- **FAILED** — task failed with error
- **EXPIRED** — task timeout expired

**Lease Mechanism:**
When agent picks up a task, it gets a "lease" for 300 seconds (5 minutes). If agent doesn't return result within this time, lease expires and task can be picked up again.

### Task Monitoring

**Through Control Panel:**

1. **Open "Tasks" tab**
2. **Table shows:**
   - Task ID
   - Type
   - Command/description
   - Status for each agent
   - Creation time

3. **View result:**
   - Click on task row
   - If status DONE — result window opens
   - If status FAILED — error window opens

**Through API:**

```bash
# Get task information
curl https://192.168.1.100:5000/api/tasks/<task_id> \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)"
```

**Response:**
```json
{
  "id": "TASK-20260320-143025-ABCD",
  "task_type": "RUN_CMD",
  "cmd": "ipconfig /all",
  "shell": "cmd",
  "timeout_seconds": 30,
  "agent_ids": ["HW-ABCD1234EFGH5678"],
  "status": {
    "HW-ABCD1234EFGH5678": "DONE"
  },
  "results": {
    "HW-ABCD1234EFGH5678": {
      "stdout": "Windows IP Configuration...",
      "stderr": "",
      "exit_code": 0,
      "finished_at": "2026-03-20T14:31:05Z"
    }
  },
  "created_at": "2026-03-20T14:30:25Z"
}
```

### Real-time Monitoring

For **PS** (processes), **FS** (file system) tasks:

1. **Create monitoring task**
2. **Open monitor:**
   - Click "👁️ Monitor" next to task
   - Window opens with updating data

**Example: Process Monitoring (PS)**
- Real-time process list
- Sort by CPU, memory, name
- Updates every 5-10 seconds

**Example: File System Monitoring (FS)**
- Contents of specified folder
- File sizes
- Modification dates
- Option to change folder ("🔄 Change Path")

### Cancel and Delete Tasks

**Force completion:**

```bash
curl -X POST https://192.168.1.100:5000/api/tasks/force_done \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)" \
  -H "Content-Type: application/json" \
  -d '{"task_id": "TASK-20260320-143025-ABCD"}'
```

**Delete task:**

```bash
curl -X POST https://192.168.1.100:5000/api/tasks/delete \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)" \
  -H "Content-Type: application/json" \
  -d '{"task_id": "TASK-20260320-143025-ABCD"}'
```

**⚠️ IMPORTANT:**
- `force_done` — marks task as DONE, but doesn't delete
- `delete` — completely removes task from system
- Both actions require `cancel_tasks` privilege

### Task Persistence

Agent saves received tasks locally in `tasks.json`. This means:

✅ **Tasks will execute even after agent reboot**  
✅ **If agent was offline, it will execute tasks when reconnected**  
✅ **Retry mechanism** — tasks can be retried on errors

**Deadline Mechanism:**
- Each task has `deadline` = current time + `timeout_seconds`
- If `deadline` has passed, task is not executed (status: EXPIRED)
- Agent checks `deadline` before execution

---

## User Management

### Privilege System

RMM uses a flexible privilege system (ACL). Each user has a set of permissions:

| Privilege | Description |
|-----------|-------------|
| `approve_agent` | Approve new agents, rename, delete |
| `run_cmd` | Execute commands on agents |
| `manage_users` | Create, modify, delete users |
| `push_file` | Send files to agents |
| `pull_file` | Receive files from agents |
| `view_info` | View agent and task information |
| `view_logs` | View logs (audit, http, tech) |
| `shutdown_server` | Shut down server |
| `cancel_tasks` | Cancel and delete tasks |

### Create User

**Through Control Panel:**

1. **Open "Users" tab**
2. **Click "➕ Create User"**
3. **Fill in data:**
   - **Username**: `operator1`
   - **Password**: `SecurePass123!`
   - **Privileges**: select needed (e.g., `view_info`, `run_cmd`)
   - **Command blacklist** (optional): `format`, `del /f`, `rm -rf`

4. **Click "Create"**

**Through API:**

```bash
curl -X POST https://192.168.1.100:5000/api/users \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "operator1",
    "password": "SecurePass123!",
    "privileges": ["view_info", "run_cmd", "pull_file"],
    "cmd_blacklist": ["format", "del /f", "rm -rf"]
  }'
```

### Command Blacklist

For additional security, you can prevent users from executing certain commands.

**How it works:**
- Check occurs when creating RUN_CMD task
- If command contains forbidden word — task is rejected
- Case-insensitive check

**Example:**
```json
{
  "username": "junior_admin",
  "cmd_blacklist": ["format", "del /f /q", "shutdown", "reboot", "rm -rf"]
}
```

User `junior_admin` CANNOT execute:
- `format C:` ❌
- `del /f /q C:\Important\*` ❌
- `shutdown /s /f` ❌

But can:
- `dir C:\` ✅
- `ipconfig` ✅
- `Get-Process` ✅

### Change Password

**Set password:**

```bash
curl -X POST https://192.168.1.100:5000/api/users/set_password \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "operator1",
    "password": "NewSecurePass456!"
  }'
```

**⚠️ IMPORTANT:**
- Only users with `manage_users` privilege can change others' passwords
- Users can change their own password without `manage_users`

### Change Privileges

```bash
curl -X PUT https://192.168.1.100:5000/api/users/operator1 \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "privileges": ["view_info", "run_cmd", "push_file", "pull_file"]
  }'
```

### Delete User

**⚠️ WARNING:** User **Admin** cannot be deleted!

```bash
curl -X DELETE https://192.168.1.100:5000/api/users/operator1 \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)"
```

### View All Users

```bash
curl https://192.168.1.100:5000/api/users \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)"
```

**Response:**
```json
{
  "Admin": {
    "privileges": ["approve_agent", "run_cmd", "manage_users", ...],
    "cmd_blacklist": [],
    "created_at": "2026-03-20T10:00:00Z"
  },
  "operator1": {
    "privileges": ["view_info", "run_cmd"],
    "cmd_blacklist": ["format", "del /f"],
    "created_at": "2026-03-20T14:00:00Z"
  }
}
```

**⚠️ NOTE:** Password hashes are NOT output in API!

---

## Logging System

RMM maintains three types of logs:

### 1. Audit Log (`audit.log`)

**Purpose:** Logging all administrative actions.

**Format:** JSON, one entry per line.

**Content:**
```json
{
  "ts": "2026-03-20T14:30:25Z",
  "user": "Admin",
  "action": "agent_approved",
  "detail": {"agent": "HW-ABCD1234EFGH5678"},
  "ip": "192.168.1.10"
}
```

**Events:**
- `login` — successful login
- `login_failed` — failed login attempt
- `agent_approved` — agent approved
- `agent_blocked` — agent blocked
- `agent_delete` — agent deleted
- `agent_rename` — agent renamed
- `user_create` — user created
- `user_delete` — user deleted
- `user_password_change` — password changed
- `task_create` — task created
- `task_delete` — task deleted
- `task_force_done` — task force completed
- `file_upload` — file uploaded
- `server_shutdown` — server shutdown

### 2. HTTP Log (`http.log`)

**Purpose:** Logging all HTTP requests.

**Format:** JSON.

**Content:**
```json
{
  "ts": "2026-03-20T14:30:25Z",
  "method": "POST",
  "path": "/api/tasks",
  "ip": "192.168.1.10",
  "user": "Admin",
  "status": 200
}
```

### 3. Technical Log (`tech.log`)

**Purpose:** Technical events (errors, exceptions, internal events).

**Format:** JSON.

**Content:**
```json
{
  "ts": "2026-03-20T14:30:25Z",
  "event": "task_leased",
  "task_id": "TASK-20260320-143025-ABCD",
  "agent_id": "HW-ABCD1234EFGH5678"
}
```

**Events:**
- `task_leased` — task taken by agent
- `task_result_saved` — task result saved
- `telemetry_saved` — telemetry saved
- `monitoring_path_updated` — monitoring path updated
- Various errors and exceptions

### View Logs

**Through Control Panel:**

1. **Click "📋 Logs"**
2. **Select log type:**
   - Audit Log
   - HTTP Log
   - Technical Log

**Through API:**

```bash
# Audit Log
curl https://192.168.1.100:5000/api/logs/audit?limit=100 \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)"

# HTTP Log
curl https://192.168.1.100:5000/api/logs/http?limit=100 \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)"

# Technical Log
curl https://192.168.1.100:5000/api/logs/tech?limit=100 \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)"
```

**Parameters:**
- `limit` — number of entries (default 100)
- `offset` — offset (for pagination)
- `filter_user` — filter by user
- `filter_action` — filter by action

### Log Rotation

**⚠️ IMPORTANT:** Logs can grow very quickly!

**Recommendations:**
1. Configure logrotate (Linux) or Task Scheduler (Windows)
2. Archive old logs
3. Delete logs older than N days

**Example logrotate (Linux):**
```
/path/to/rmm/audit.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
}
```

**Example PowerShell (Windows):**
```powershell
# Delete logs older than 30 days
$logPath = "C:\RMM\Server"
Get-ChildItem "$logPath\*.log" | Where-Object {
    $_.LastWriteTime -lt (Get-Date).AddDays(-30)
} | Remove-Item -Force
```

---

## Monitoring and Telemetry

### Telemetry Collection

Agent automatically collects telemetry every **60 seconds** and sends to server with heartbeat.

**Telemetry Data:**

#### 1. OS Information
```json
{
  "os_info": {
    "name": "Windows 11 Pro",
    "version": "10.0.22631",
    "architecture": "x64",
    "build": "22631"
  }
}
```

#### 2. CPU
```json
{
  "cpu": {
    "usage_percent": 23.5,
    "cores": 8,
    "threads": 16
  }
}
```

#### 3. Memory
```json
{
  "memory": {
    "total_mb": 16384,
    "used_mb": 8192,
    "free_mb": 8192,
    "percent": 50.0
  }
}
```

#### 4. Disks
```json
{
  "disks": [
    {
      "drive": "C:",
      "total_gb": 476.94,
      "used_gb": 353.49,
      "free_gb": 123.45,
      "percent_used": 74.1,
      "filesystem": "NTFS"
    },
    {
      "drive": "D:",
      "total_gb": 931.51,
      "used_gb": 500.00,
      "free_gb": 431.51,
      "percent_used": 53.7,
      "filesystem": "NTFS"
    }
  ]
}
```

#### 5. Network
```json
{
  "network": {
    "interfaces": [
      {
        "name": "Ethernet",
        "description": "Realtek PCIe GbE Family Controller",
        "ip": "192.168.1.50",
        "mac": "00:11:22:33:44:55",
        "status": "Up",
        "speed_mbps": 1000
      }
    ]
  }
}
```

#### 6. Processes
```json
{
  "top_processes": [
    {
      "name": "chrome.exe",
      "pid": 1234,
      "memory_mb": 512.5,
      "cpu_percent": 5.2
    },
    {
      "name": "explorer.exe",
      "pid": 5678,
      "memory_mb": 234.1,
      "cpu_percent": 1.3
    }
  ]
}
```

### View Telemetry

**Through Control Panel:**

1. Click on agent in table
2. "Agent Information" window opens
3. Tabs:
   - **General Information** — status, IP, connection time
   - **System** — OS, CPU, RAM
   - **Disks** — disk usage
   - **Network** — network interfaces
   - **Processes** — top processes by CPU/RAM

**Through API:**

```bash
curl https://192.168.1.100:5000/api/agents/HW-ABCD1234EFGH5678 \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)"
```

### Telemetry Storage

Telemetry is stored in files:

```
telemetry/
├── HW-ABCD1234EFGH5678.json
├── HW-EFGH5678IJKL9012.json
└── ...
```

Each file contains the latest agent telemetry. File is overwritten on update.

**⚠️ IMPORTANT:** Historical data is NOT saved. For history storage, integrate with InfluxDB, Prometheus, or other TSDB.

---

## Uninstallation and Removal

### Remove Agent from Client Machine

#### Option 1: Automatic Removal (recommended)

Create RUN_CMD task with uninstall command:

```powershell
# PowerShell command for removal
sc stop RMMService; sc delete RMMService; Remove-Item -Path "C:\Program Files\RMMAgent" -Recurse -Force; Remove-Item -Path "HKLM:\SOFTWARE\MYRMM" -Recurse -Force
```

**Through Control Panel:**
1. Create RUN_CMD task
2. Shell: PowerShell
3. Command: (see above)
4. Agents: select agents to remove
5. Create task

#### Option 2: Manual Removal

**On client machine (as administrator):**

```cmd
:: Stop and delete service
sc stop RMMService
sc delete RMMService

:: Delete files
rmdir /s /q "C:\Program Files\RMMAgent"

:: Delete from System32/SysWOW64
del /q /f C:\Windows\System32\agent.conf
del /q /f C:\Windows\SysWOW64\agent.conf

:: Delete from registry
reg delete "HKLM\SOFTWARE\MYRMM" /f
```
### Remove Server

```bash
# Stop server (Ctrl+C)

# Delete all files
rm -rf /path/to/rmm/server
```

**⚠️ WARNING:**
- All data (users, agents, tasks, logs) will be lost
- Make backup before removal!

**Backup:**
```bash
# Create archive
tar -czf rmm_backup_$(date +%Y%m%d).tar.gz \
  users.json agents.json tasks.json \
  pending_approvals.json config.json \
  audit.log http.log tech.log \
  files/ telemetry/
```

### Remove Control Panel

```bash
# Simply delete .exe file
rm controlpanel.exe

# Or delete source folder
rm -rf /path/to/controlpanel/
```

Server configuration is stored in `servers.json` next to .exe.

---

## Security

### Authentication

RMM uses **two-level authentication:**

#### 1. Agent Authentication
- **Hardware ID** — unique ID based on hardware (motherboard, CPU, BIOS)
- **Agent Auth** — SHA256 hash for agent verification
- **Server Auth** — SHA256 hash for server verification

**Process:**
1. Agent sends registration with `agent_id` (hardware ID) and `agent_auth` (hash)
2. Server validates hash
3. If hash valid — agent added to `pending_approvals`
4. Administrator manually approves agent
5. Agent becomes active

**⚠️ IMPORTANT:**
- `agent_auth` hash must match `server_secret` in server's `config.json`
- Use `hashmade.py` to generate hash
- DO NOT put secret key in config — only hash!

#### 2. Administrator Authentication
- **HTTP Basic Auth** — username and password in Authorization header
- **Bcrypt password hashing** (werkzeug)
- **Password requirements:**
  - Minimum 8 characters
  - Uppercase and lowercase letters
  - Numbers

**Process:**
1. Control panel/API sends header: `Authorization: Basic <base64(username:password)>`
2. Server verifies password hash
3. If valid — access granted
4. Privilege check for each action

### Encryption

#### HTTPS/SSL (recommended for production)

**Certificate generation (local network):**
```bash
# Install mkcert
brew install mkcert  # macOS
scoop install mkcert # Windows
apt install mkcert   # Linux

# Generate CA
mkcert -install

# Generate certificate
mkcert myserver.local 192.168.1.100

# Files:
# myserver.local+1.pem       → certificate
# myserver.local+1-key.pem   → private key
```

Place files in folder with `server.py`. Server automatically uses HTTPS.

**Production (Let's Encrypt):**
```bash
# Install certbot
sudo apt install certbot

# Get certificate
sudo certbot certonly --standalone -d rmm.example.com

# Certificates at:
# /etc/letsencrypt/live/rmm.example.com/fullchain.pem
# /etc/letsencrypt/live/rmm.example.com/privkey.pem

# Rename or create symlinks:
ln -s /etc/letsencrypt/live/rmm.example.com/fullchain.pem myserver.local+1.pem
ln -s /etc/letsencrypt/live/rmm.example.com/privkey.pem myserver.local+1-key.pem
```

**In agent.conf:**
```ini
server=https://rmm.example.com:443
```

**In Control Panel:**
- HTTPS: ✅
- Verify SSL: ✅ (for valid certificates)

### Attack Protection

#### 1. CSRF Protection
Server includes security headers:
```python
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000
Content-Security-Policy: default-src 'self'
```

#### 2. Rate Limiting
**⚠️ NOT implemented in current version!**

For production add:
```python
from flask_limiter import Limiter
limiter = Limiter(app, key_func=lambda: request.remote_addr)

@app.route("/api/login")
@limiter.limit("5 per minute")
def login():
    ...
```

#### 3. IP Whitelisting
Restrict server access to trusted IPs only:

**Through nginx (reverse proxy):**
```nginx
location /api/ {
    allow 192.168.1.0/24;  # Local network
    allow 10.0.0.0/8;      # VPN
    deny all;
    
    proxy_pass http://localhost:5000;
}
```

#### 4. Firewall
Allow access only to server ports:

```bash
# Ubuntu (ufw)
sudo ufw allow from 192.168.1.0/24 to any port 5000
sudo ufw enable

# Windows (PowerShell)
New-NetFirewallRule -DisplayName "RMM Server" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow
```

### Agent Security

#### 1. Running as SYSTEM
Agent runs as a service under **NT AUTHORITY\SYSTEM** — highest privilege level.

**⚠️ RISKS:**
- Agent can execute ANY command
- Agent compromise = full machine control

**RECOMMENDATIONS:**
- Restrict server access (HTTPS, IP whitelist)
- Use agent approval system
- Regularly check logs
- Use command blacklist for users

#### 2. Secrets in Registry
Agent stores `agent_auth` and `server_auth` in registry with ACL:

```
HKLM\SOFTWARE\MYRMM\Secrets
- SYSTEM: Full Control
- Administrators: Read + Delete
- Everyone: Deny All
```

**⚠️ IMPORTANT:**
- ACL mechanism is DISABLED in current version (see `HomeDomainAgenInstaller.cpp`)
- For production, correctly implement `SetRegistryACL`

#### 3. agent.conf File
`agent.conf` contains hash, NOT secret key!

**NOT SECURE:**
```ini
server_secret=a1b2c3d4e5f6...  # ❌ NEVER!
```

**SECURE:**
```ini
server_auth=9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08  # ✅
```

### Security Recommendations

1. **Use HTTPS** — mandatory for production
2. **Strong passwords** — minimum 12 characters, mix of letters/numbers/symbols
3. **Limit privileges** — don't give all users `run_cmd`
4. **Use command blacklist** — prohibit dangerous commands
5. **Regularly check logs** — monitor audit.log
6. **Update system** — apply security patches
7. **Backups** — regular data backups
8. **Network segmentation** — isolate RMM server in separate subnet
9. **VPN** — for external access, use VPN, don't open ports to internet
10. **Monitoring** — integrate with SIEM (Splunk, ELK, Wazuh)

---

## Troubleshooting

### Server Issues

#### 1. Server Won't Start

**Symptoms:**
```
Address already in use
```

**Cause:** Port 5000 is in use by another process.

**Solution:**
```bash
# Find process using port
lsof -i :5000  # Linux/macOS
netstat -ano | findstr :5000  # Windows

# Terminate process or change port in config.json
{
  "port": 5001
}
```

#### 2. SSL Errors

**Symptoms:**
```
ssl.SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]
```

**Cause:** Invalid/self-signed certificate.

**Solution:**
```bash
# In Control Panel: HTTPS ✅, Verify SSL ❌
# Or use valid certificates (Let's Encrypt)
```

#### 3. JSON Errors

**Symptoms:**
```
json.decoder.JSONDecodeError: Expecting value
```

**Cause:** Corrupted JSON files (users.json, agents.json, etc.)

**Solution:**
```bash
# Delete corrupted file (new one will be created)
rm users.json

# Or restore from backup
cp backup/users.json .
```

#### 4. Logs Filled Up

**Symptoms:**
- Server runs slowly
- Disk full

**Solution:**
```bash
# Clear old logs
> audit.log
> http.log
> tech.log

# Configure rotation (see "Log Rotation" section)
```

### Agent Issues

#### 1. Service Won't Start

**Symptoms:**
```
Error 1053: The service did not respond in a timely fashion
Error 193: %1 is not a valid Win32 application
```

**Cause:**
- Error 1053: Agent not responding on startup (maybe server unavailable)
- Error 193: Incorrect path to .exe (spaces in path without quotes)

**Solution:**

```cmd
:: Check service path
sc qc RMMService

:: Should be:
:: BINARY_PATH_NAME: "C:\Program Files\RMMAgent\HomeDomainClient.exe"

:: If no quotes — reinstall service
sc delete RMMService
sc create RMMService binPath= "\"C:\Program Files\RMMAgent\HomeDomainClient.exe\"" start= auto

:: For Error 1053 — check server availability
ping 192.168.1.100
```

#### 2. Agent Not Connecting to Server

**Symptoms:**
```
[-] Server not found. Retrying in 10s...
[!] Connection failed. Resetting server URL.
```

**Cause:**
- Server unavailable
- Wrong URL in agent.conf
- Firewall blocking port

**Solution:**

```bash
# 1. Check server availability
curl https://192.168.1.100:5000/server_info

# 2. Check agent.conf
type "C:\Program Files\RMMAgent\agent.conf"

# 3. Check firewall
# Windows: Control Panel → Windows Firewall → Allow application

# 4. Check agent.log
type "C:\Program Files\RMMAgent\agent.log"
```

#### 3. Agent Stuck in PENDING_APPROVAL

**Symptoms:**
- Agent in "Pending Approval" list
- Agent not receiving tasks

**Cause:**
- Administrator didn't approve agent

**Solution:**
```bash
# Approve agent through Control Panel or API
curl -X POST https://192.168.1.100:5000/api/agents/approve \
  -H "Authorization: Basic <base64(Admin:Password)>" \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "HW-ABCD1234EFGH5678", "action": "approve"}'
```

#### 4. Agent Shows OFFLINE

**Symptoms:**
- In Control Panel agent red 🔴 OFFLINE
- But service is running

**Cause:**
- Agent didn't send heartbeat > 120 seconds
- Possibly network issues

**Solution:**
```cmd
:: Restart service
sc stop RMMService
sc start RMMService

:: Check logs
type "C:\Program Files\RMMAgent\agent.log"

:: Check network
ping 192.168.1.100
```

#### 5. Tasks Not Executing

**Symptoms:**
- Task status PENDING forever
- Agent ONLINE but not picking tasks

**Cause:**
- Agent not approved (`approved: false`)
- Error in agent logic
- Task expired (deadline)

**Solution:**
```bash
# 1. Check agent status
curl https://192.168.1.100:5000/api/agents/HW-ABCD1234EFGH5678 \
  -H "Authorization: Basic <base64>"

# Verify: "approved": true

# 2. Check task deadline
curl https://192.168.1.100:5000/api/tasks/TASK-ID \
  -H "Authorization: Basic <base64>"

# 3. Check agent.log
type "C:\Program Files\RMMAgent\agent.log"
```

### Control Panel Issues

#### 1. Cannot Connect to Server

**Symptoms:**
```
Error: Connection refused
Error: SSL certificate verify failed
```

**Cause:**
- Wrong address/port
- SSL issues
- Firewall

**Solution:**
1. Check server address and port
2. If HTTPS with self-signed certificate: HTTPS ✅, Verify SSL ❌
3. Check server availability through browser: `https://192.168.1.100:5000/server_info`

#### 2. Authentication Error

**Symptoms:**
```
401 Unauthorized
```

**Cause:**
- Wrong username/password
- User doesn't exist

**Solution:**
```bash
# Check user
curl https://192.168.1.100:5000/api/users \
  -H "Authorization: Basic <base64(Admin:DefaultPass)>"

# If password forgotten — reset by directly editing users.json
# Or create new administrator
```

#### 3. Panel Freezes

**Symptoms:**
- Panel unresponsive on connection
- "Attempt 1/10 → ..."

**Cause:**
- Server unavailable
- Slow network

**Solution:**
- Click "Cancel"
- Check server availability
- Reduce number of attempts in code (ConnectWorker.tries)

### General Recommendations

#### Diagnostics

1. **Check logs:**
   - Server: `audit.log`, `tech.log`, `http.log`
   - Agent: `C:\Program Files\RMMAgent\agent.log`

2. **Check network:**
   ```bash
   ping <server_ip>
   telnet <server_ip> 5000
   curl https://<server_ip>:5000/server_info
   ```

3. **Check services:**
   ```cmd
   sc query RMMService
   ```

4. **Check firewall:**
   - Windows: Control Panel → Windows Firewall
   - Linux: `sudo ufw status`

5. **Check certificates:**
   ```bash
   openssl s_client -connect <server_ip>:5000
   ```

#### Recovery After Failure

1. **Backup:**
   ```bash
   # Regular backups
   tar -czf rmm_backup.tar.gz users.json agents.json tasks.json config.json
   ```

2. **Restore:**
   ```bash
   # Stop server
   # Restore files from backup
   tar -xzf rmm_backup.tar.gz
   # Start server
   ```

3. **Cleanup:**
   ```bash
   # If system corrupted — clean everything
   rm users.json agents.json tasks.json pending_approvals.json
   # Start server (new files will be created)
   # Reinstall agents
   ```

---

## API Reference

### Authentication

All API requests require **HTTP Basic Authentication:**

```bash
Authorization: Basic <base64(username:password)>
```

**Example:**
```bash
echo -n 'Admin:Password' | base64
# QWRtaW46UGFzc3dvcmQ=

curl https://192.168.1.100:5000/api/agents \
  -H "Authorization: Basic QWRtaW46UGFzc3dvcmQ="
```

### Endpoints

#### Server Info

**GET /server_info**

Get server information (public endpoint, no authentication).

**Response:**
```json
{
  "name": "NODE-2026: MAIN MANAGEMENT NODE",
  "version": "1.0",
  "time": "2026-03-20T14:30:25Z"
}
```

---

#### Users

**GET /api/users**

Get list of all users.

**Required privileges:** `view_info`

**Response:**
```json
{
  "Admin": {
    "privileges": [...],
    "cmd_blacklist": [],
    "created_at": "2026-03-20T10:00:00Z"
  },
  "operator1": {
    "privileges": ["view_info"],
    "cmd_blacklist": ["format"],
    "created_at": "2026-03-20T14:00:00Z"
  }
}
```

---

**POST /api/users**

Create new user.

**Required privileges:** `manage_users`

**Request:**
```json
{
  "username": "operator1",
  "password": "SecurePass123!",
  "privileges": ["view_info", "run_cmd"],
  "cmd_blacklist": ["format", "del /f"]
}
```

**Response:**
```json
{
  "ok": true
}
```

---

**PUT /api/users/{username}**

Modify user privileges.

**Required privileges:** `manage_users`

**Request:**
```json
{
  "privileges": ["view_info", "run_cmd", "push_file"]
}
```

---

**DELETE /api/users/{username}**

Delete user.

**Required privileges:** `manage_users`

**Response:**
```json
{
  "ok": true
}
```

---

**POST /api/users/set_password**

Set user password.

**Required privileges:** `manage_users` (or for own password)

**Request:**
```json
{
  "username": "operator1",
  "password": "NewPass456!"
}
```

---

#### Agents

**GET /api/agents**

Get list of all agents.

**Required privileges:** Any authenticated user

**Response:**
```json
{
  "HW-ABCD1234EFGH5678": {
    "name": "Office-PC-01",
    "ip": "192.168.1.50",
    "status": "ONLINE",
    "approved": true,
    "first_seen": "2026-03-20T10:30:00Z",
    "last_seen": "2026-03-20T14:25:30Z"
  }
}
```

---

**GET /api/agents/{agent_id}**

Get detailed agent information.

**Required privileges:** `view_info`

**Response:**
```json
{
  "agent": {
    "name": "Office-PC-01",
    ...
  },
  "telemetry": {
    "os_info": {...},
    "cpu": {...},
    "memory": {...},
    ...
  }
}
```

---

**POST /api/agents/approve**

Approve or block agent.

**Required privileges:** `approve_agent`

**Request:**
```json
{
  "agent_id": "HW-ABCD1234EFGH5678",
  "action": "approve"  // or "block"
}
```

---

**POST /api/agents/rename**

Rename agent.

**Required privileges:** `approve_agent`

**Request:**
```json
{
  "agent_id": "HW-ABCD1234EFGH5678",
  "new_name": "Office-PC-01"
}
```

---

**POST /api/agents/delete**

Delete agent.

**Required privileges:** `approve_agent`

**Request:**
```json
{
  "agent_id": "HW-ABCD1234EFGH5678"
}
```

---

#### Tasks

**GET /api/tasks**

Get list of all tasks.

**Required privileges:** `view_info`

**Response:**
```json
[
  {
    "id": "TASK-20260320-143025-ABCD",
    "task_type": "RUN_CMD",
    "cmd": "ipconfig /all",
    "shell": "cmd",
    "timeout_seconds": 30,
    "agent_ids": ["HW-ABCD1234EFGH5678"],
    "status": {
      "HW-ABCD1234EFGH5678": "DONE"
    },
    "created_at": "2026-03-20T14:30:25Z"
  }
]
```

---

**POST /api/tasks**

Create task.

**Required privileges:** Depends on task type

**RUN_CMD:**
```json
{
  "task_type": "RUN_CMD",
  "cmd": "Get-Process",
  "shell": "powershell",
  "timeout_seconds": 60,
  "agent_ids": ["HW-ABCD1234EFGH5678"]
}
```

**PUSH_FILE:**
```json
{
  "task_type": "PUSH_FILE",
  "file_url": "https://192.168.1.100:5000/files/file.exe",
  "save_path": "C:\\Temp\\file.exe",
  "agent_ids": ["HW-ABCD1234EFGH5678"]
}
```

**PULL_FILE:**
```json
{
  "task_type": "PULL_FILE",
  "file_path": "C:\\Users\\User\\report.pdf",
  "agent_ids": ["HW-ABCD1234EFGH5678"]
}
```

---

**GET /api/tasks/{task_id}**

Get task information.

**Required privileges:** `view_info`

---

**POST /api/tasks/delete**

Delete task.

**Required privileges:** `cancel_tasks`

**Request:**
```json
{
  "task_id": "TASK-20260320-143025-ABCD"
}
```

---

**POST /api/tasks/force_done**

Force complete task.

**Required privileges:** `cancel_tasks`

**Request:**
```json
{
  "task_id": "TASK-20260320-143025-ABCD"
}
```

---

#### Files

**POST /api/files/upload**

Upload file to server.

**Required privileges:** `push_file`

**Request:** multipart/form-data

```bash
curl -X POST https://192.168.1.100:5000/api/files/upload \
  -H "Authorization: Basic <base64>" \
  -F "file=@/path/to/file.exe"
```

**Response:**
```json
{
  "ok": true,
  "filename": "file.exe",
  "url": "https://192.168.1.100:5000/files/file.exe"
}
```

---

**GET /files/{filename}**

Download file from server.

**Required privileges:** `pull_file`

---

#### Logs

**GET /api/logs/audit**

Get entries from audit.log.

**Required privileges:** `view_logs`

**Parameters:**
- `limit` — number of entries (default 100)
- `offset` — offset

**Response:**
```json
[
  {
    "ts": "2026-03-20T14:30:25Z",
    "user": "Admin",
    "action": "agent_approved",
    "detail": {"agent": "HW-ABCD1234EFGH5678"},
    "ip": "192.168.1.10"
  }
]
```

---

**GET /api/logs/http**

Get entries from http.log.

---

**GET /api/logs/tech**

Get entries from tech.log.

---

#### System

**POST /api/system/shutdown**

Shutdown server.

**Required privileges:** `shutdown_server`

**Response:**
```json
{
  "ok": true,
  "message": "Server shutdown initiated"
}
```

---

**⚠️ DISCLAIMER:**

This software is provided "as is" without any warranties. Use at your own risk. The author is not liable for any damage caused by the use of this software.

**Security first!** 🔒


---

# RU

---

# 📚 Документация RMM (Remote Monitoring and Management) System

## 📋 Содержание

1. [Введение](#введение)
2. [Архитектура системы](#архитектура-системы)
3. [Системные требования](#системные-требования)
4. [Установка и настройка](#установка-и-настройка)
5. [Управление агентами](#управление-агентами)
6. [Управление задачами](#управление-задачами)
7. [Управление пользователями](#управление-пользователями)
8. [Система логирования](#система-логирования)
9. [Мониторинг и телеметрия](#мониторинг-и-телеметрия)
10. [Удаление и деинсталляция](#удаление-и-деинсталляция)
11. [Безопасность](#безопасность)
12. [Возможные проблемы и решения](#возможные-проблемы-и-решения)
13. [API Reference](#api-reference)

---

## Введение

**RMM System** — это комплексное решение для удаленного управления и мониторинга Windows-компьютеров в корпоративной сети. Система состоит из трех основных компонентов:

- **Server** (`server.py`) — центральный сервер управления на Python/Flask
- **Agent** (`HomeDomainClient.exe`) — клиентский агент для Windows (служба)
- **Control Panel** (`controlpanel.exe`) — графическая панель управления на PyQt5

### Основные возможности:

✅ **Удаленное выполнение команд** (PowerShell/CMD)  
✅ **Передача файлов** в обе стороны (push/pull)  
✅ **Мониторинг в реальном времени** (процессы, диски, сеть)  
✅ **Система одобрения агентов** (безопасное подключение)  
✅ **Гибкая система привилегий** для администраторов  
✅ **Аудит всех действий** (логи в JSON)  
✅ **Автоматическое обнаружение сервера** в сети  
✅ **HTTPS/SSL поддержка** для безопасной передачи данных  
✅ **Персистентность задач** (выполнение после перезагрузки)  

---

## Архитектура системы

### Общая схема работы

```
┌─────────────────────┐
│  Control Panel      │  ◄─── Администратор
│  (controlpanel.exe) │
└──────────┬──────────┘
           │ HTTPS/HTTP
           │ (REST API)
           ▼
┌─────────────────────┐
│   RMM Server        │
│   (server.py)       │  ◄─── Flask + JSON файлы
│   Port: 5000        │
└──────────┬──────────┘
           │ HTTPS/HTTP
           │ (Polling)
           ▼
┌─────────────────────┐
│  Agent (Service)    │  ◄─── Windows машины
│  HomeDomainClient   │       (клиенты)
│  .exe               │
└─────────────────────┘
```

### Компоненты системы

#### 1. **Server (server.py)**

**Технологии:** Python 3.10+, Flask, Threading

**Основные функции:**
- REST API для взаимодействия с агентами и панелью управления
- Управление пользователями с системой привилегий
- Очередь задач с поддержкой различных типов
- Система одобрения новых агентов
- Мониторинг статуса агентов (ONLINE/OFFLINE)
- Хранение телеметрии
- Аудит всех действий

**Хранилище данных (JSON файлы):**
```
server/
├── users.json              # Пользователи и их права
├── agents.json             # Зарегистрированные агенты
├── tasks.json              # Очередь задач
├── pending_approvals.json  # Агенты на одобрении
├── config.json             # Конфигурация сервера
├── audit.log               # Лог аудита
├── http.log                # HTTP запросы
├── tech.log                # Технические логи
├── files/                  # Загруженные файлы
└── telemetry/              # Телеметрия агентов
    ├── <agent_id>.json
    └── ...
```

#### 2. **Agent (HomeDomainClient.exe)**

**Технологии:** C++17, WinAPI, Windows Service, WinHTTP, nlohmann/json

**Основные функции:**
- Регистрация на сервере с уникальным hardware ID
- Polling сервера для получения задач (каждые 60 сек)
- Выполнение команд (CMD/PowerShell)
- Загрузка и скачивание файлов
- Сбор телеметрии (CPU, RAM, диски, процессы, сеть)
- Автоматическое обнаружение сервера в сети
- Персистентность задач (сохранение в tasks.json)
- Работа в режиме Windows Service

**Структура установки:**
```
C:\Program Files\RMMAgent\
├── HomeDomainClient.exe    # Основной исполняемый файл
├── agent.conf              # Конфигурация (agent_auth, server_auth, server URL)
├── agent.log               # Лог агента
└── tasks.json              # Локальная очередь задач
```

**Секреты хранятся в реестре:**
```
HKLM\SOFTWARE\MYRMM\Secrets\
├── agent_auth     (REG_SZ)   # SHA256 хэш для аутентификации
└── server_auth    (REG_SZ)   # SHA256 хэш сервера для проверки
```

#### 3. **Control Panel (controlpanel.exe)**

**Технологии:** Python 3.10+, PyQt5, Requests

**Основные функции:**
- Графический интерфейс для управления
- Мультисерверное управление
- Создание и управление задачами
- Управление пользователями
- Мониторинг агентов в реальном времени
- Просмотр логов
- Управление файлами

---

## Системные требования

### Для сервера:

| Компонент | Минимум | Рекомендуется |
|-----------|---------|---------------|
| ОС | Windows 10/11, Linux, macOS | Ubuntu 20.04 LTS / Windows Server 2019+ |
| Python | 3.10+ | 3.11+ |
| RAM | 512 MB | 2 GB |
| HDD | 1 GB | 10 GB (для логов/телеметрии) |
| Сеть | 100 Mbit/s | 1 Gbit/s |
| Порты | 5000 (HTTP) или 443/5000 (HTTPS) | — |

**Зависимости Python:**
```bash
flask>=2.3.0
werkzeug>=2.3.0
requests>=2.31.0
```

### Для агента (клиентские машины):

| Компонент | Минимум |
|-----------|---------|
| ОС | **Windows 10** (версия 1809+) или **Windows 11** |
| Редакция | Windows Home |
| Архитектура | x86 (32-bit) |
| RAM | 256 MB свободной |
| HDD | 100 MB |
| Права | Права администратора для установки |
| .NET | Не требуется (нативный C++) |

**⚠️ ВАЖНО:** Агент работает ТОЛЬКО на Windows 10/11 (x86)!

### Для панели управления:

| Компонент | Требования |
|-----------|------------|
| ОС | Windows 10/11 |
| Python | 3.10+ |
| Зависимости | PyQt5, requests |

---

## Установка и настройка

### 1. Установка сервера

#### Шаг 1: Установка Python зависимостей

```bash
# Создайте виртуальное окружение (опционально)
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Установите зависимости
pip install flask werkzeug requests
```

#### Шаг 2: Генерация секретных ключей

Запустите `hashmade.py` для генерации ключей:

```bash
python hashmade.py
```

**Вывод:**
```
Secret key (server): a1b2c3d4e5f6...  (32 байта в HEX)
SHA256 hash (agent.conf): 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
```

**Сохраните оба значения!**

#### Шаг 3: Настройка конфигурации сервера

Создайте/отредактируйте `config.json`:

```json
{
  "server_secret": "a1b2c3d4e5f6...",
  "server_description": "NODE-2026: ГЛАВНЫЙ УЗЕЛ УПРАВЛЕНИЯ",
  "port": 5000
}
```

- `server_secret` — секретный ключ из hashmade.py (не хэш!)
- `port` — порт сервера (по умолчанию 5000)

#### Шаг 4: Настройка HTTPS (опционально, но рекомендуется)

Для HTTPS необходимы SSL сертификаты. Используйте **mkcert** для локальной сети:

```bash
# Установка mkcert
# Windows: scoop install mkcert
# Linux: apt install mkcert / brew install mkcert

# Генерация сертификатов
mkcert myserver.local 192.168.1.100

# Переименуйте файлы:
# myserver.local+1.pem       → оставить как есть
# myserver.local+1-key.pem   → оставить как есть
```

Поместите файлы в папку с `server.py`.

**Для production используйте Let's Encrypt или корпоративный CA.**

#### Шаг 5: Создание администратора

При первом запуске создается пользователь **Admin**. Первый вход Admin примет любой пароль и он будет сохранен на всегда. (для сброса в файле данных пользователей удалите содержимое хэша). Установите пароль через API:

```bash
# Запустите сервер
python server.py

# В другом терминале установите пароль для Admin:
curl -X POST http://localhost:5000/api/users/set_password \
  -H "Content-Type: application/json" \
  -d '{"username": "Admin", "password": "YourSecurePassword123!"}'
```

**⚠️ Требования к паролю:**
- Минимум 8 символов
- Хотя бы 1 заглавная буква
- Хотя бы 1 строчная буква
- Хотя бы 1 цифра

#### Шаг 6: Запуск сервера

```bash
python server.py
```

**Вывод:**
```
[*] Starting SECURE HTTPS server on port 5000
 * Running on https://0.0.0.0:5000
```

Сервер готов! Теперь установите агенты.

---

### 2. Установка агента

Агент распространяется как **скомпилированный .exe** файл, готовый к установке.

#### Подготовка установочного пакета

Структура:
```
agent_installer/
├── HomeDomainAgenInstaller.exe  # Инсталлятор
└── agent/
    ├── HomeDomainClient.exe     # Агент (служба)
    └── agent.conf               # Конфигурация
```

#### Настройка `agent.conf`

Создайте файл `agent.conf` со следующим содержимым:

```ini
server=https://192.168.1.100:5000
agent_auth=9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
server_auth=9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
```

**Параметры:**
- `server` — адрес сервера (HTTP/HTTPS)
- `agent_auth` — SHA256 хэш из hashmade.py
- `server_auth` — тот же SHA256 хэш (для проверки сервера)

**⚠️ ВАЖНО:**
- Используйте **HTTPS** в production
- Укажите правильный IP/домен сервера
- Хэши должны совпадать с теми, что в `config.json` сервера

#### Установка агента на клиентскую машину

1. **Скопируйте папку `agent_installer` на целевой компьютер**

2. **Запустите инсталлятор от имени администратора:**

   ```cmd
   # Правый клик → "Запустить от имени администратора"
   HomeDomainAgenInstaller.exe
   ```

   **Процесс установки:**
   - Создание папки `C:\Program Files\RMMAgent`
   - Копирование `HomeDomainClient.exe` и `agent.conf`
   - Копирование конфига в системные папки (`System32`, `SysWOW64`)
   - Миграция секретов в реестр (`HKLM\SOFTWARE\MYRMM\Secrets`)
   - Установка службы Windows `RMMService`
   - Настройка автозапуска
   - Запуск службы

3. **Проверка установки:**

   ```cmd
   # Проверка статуса службы
   sc query RMMService
   
   # Вывод должен содержать:
   # STATE: 4 RUNNING
   ```

4. **Проверка логов:**

   ```cmd
   # Просмотр лога агента
   type "C:\Program Files\RMMAgent\agent.log"
   ```

   Успешная регистрация:
   ```
   [*] Hardware-bound ID: HW-ABCD1234EFGH5678
   [?] Probing config server: https://192.168.1.100:5000
   [+] DISCOVERED: https://192.168.1.100:5000
   [!] Connected to https://192.168.1.100:5000. Starting main loop.
   [*] Heartbeat OK
   ```

#### Автоматическое обнаружение сервера

Если в `agent.conf` указан `server=AUTO` или сервер недоступен, агент автоматически:

1. **Сканирует локальную сеть** на предмет доступных серверов
2. **Исключает VPN интерфейсы** (WireGuard, OpenVPN, Hamachi)
3. **Проверяет /server_info** на каждом хосте
4. **Подключается к первому найденному серверу**

**Таймауты:**
- Сканирование сети: 3000 мс на хост
- UDP Discovery: 2000 мс
- Повтор поиска: каждые 10 секунд

---

### 3. Установка панели управления

#### Вариант 1: Запуск из исходников

```bash
# Установите зависимости
pip install PyQt5 requests

# Запустите панель
python controlpanel.py
```

#### Вариант 2: Скомпилированный .exe

```bash
# Используйте PyInstaller для компиляции
pyinstaller --onefile --windowed --icon=icon.ico controlpanel.py

# Запустите
dist/controlpanel.exe
```

#### Первый запуск

1. **Откройте Control Panel**
2. **Добавьте сервер:**
   - Нажмите "➕ Добавить сервер"
   - Укажите:
     - **Имя**: `Главный сервер`
     - **Хост/IP**: `192.168.1.100`
     - **Порт**: `5000`
     - **HTTPS**: ✅ (если настроили SSL)
     - **Проверять SSL**: ❌ (для самоподписанных сертификатов)
   - Нажмите "💾 Сохранить"

3. **Подключитесь к серверу:**
   - Выберите сервер из списка
   - Нажмите "🔌 Подключиться"
   - Введите:
     - **Username**: `Admin`
     - **Password**: `YourSecurePassword123!`
   - Нажмите "Войти"

4. **Готово!** Вы в главной панели управления.

---

## Управление агентами

### Жизненный цикл агента

```
┌──────────────┐
│ Установка    │
│ агента       │
└──────┬───────┘
       │
       ▼
┌──────────────────┐
│ Первое подключение│  → Агент отправляет регистрацию
│ к серверу         │     с hardware ID
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ PENDING_APPROVAL │  → Агент в очереди на одобрение
└──────┬───────────┘
       │
       │ Администратор одобряет/блокирует
       ▼
┌──────────────────┐
│ APPROVED         │  → Агент активен, принимает задачи
│ (статус: ONLINE) │
└──────┬───────────┘
       │
       │ Агент отправляет heartbeat каждые 60 сек
       │
       ├─► last_seen обновляется
       │
       │ Если нет heartbeat > 120 сек
       ▼
┌──────────────────┐
│ статус: OFFLINE  │
└──────────────────┘
```

### Подтверждение агентов

#### Через Control Panel:

1. **Откройте вкладку "Агенты на одобрение"**
2. **Выберите агент из списка** (показывает: ID, имя, IP, первое подключение)
3. **Нажмите:**
   - **"✅ Одобрить"** — агент активируется
   - **"🚫 Заблокировать"** — агент заблокируется

#### Через API:

```bash
curl -X POST https://192.168.1.100:5000/api/agents/approve \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "HW-ABCD1234EFGH5678",
    "action": "approve"
  }'
```

### Мониторинг статуса агентов

**Статусы:**
- **ONLINE** — последний heartbeat < 120 секунд назад
- **OFFLINE** — последний heartbeat > 120 секунд назад
- **UNKNOWN** — агент никогда не отправлял heartbeat
- **BLOCKED** — агент заблокирован администратором

**В Control Panel:**
- Зеленый индикатор 🟢 — ONLINE
- Красный индикатор 🔴 — OFFLINE
- Серый индикатор ⚪ — UNKNOWN
- Черный индикатор ⚫ — BLOCKED

**Автоматическая проверка:**
Сервер каждые 120 секунд обновляет статусы всех агентов.

### Переименование агента

```bash
# Через API
curl -X POST https://192.168.1.100:5000/api/agents/rename \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "HW-ABCD1234EFGH5678",
    "new_name": "Office-PC-01"
  }'
```

**Через Control Panel:**
1. Найдите агента в таблице
2. Нажмите "✏️ Переименовать"
3. Введите новое имя
4. Нажмите OK

### Удаление агента

**⚠️ ВАЖНО:** Удаление агента с сервера НЕ удаляет службу с клиентской машины!

**Через Control Panel:**
1. Выберите агента
2. Нажмите "🗑️ Удалить"
3. Подтвердите удаление

**Что происходит:**
- Агент удаляется из `agents.json`
- Все задачи агента помечаются как неактивные
- Агент удаляется из pending_approvals (если был там)
- Создается запись в audit.log

**Для удаления службы с клиентской машины:**
См. раздел [Удаление и деинсталляция](#удаление-и-деинсталляция).

### Просмотр информации об агенте

**Через Control Panel:**
1. Нажмите на строку агента в таблице
2. Откроется окно с детальной информацией:
   - Системная информация (ОС, версия, архитектура)
   - Hardware ID
   - IP адрес
   - Время регистрации
   - Последний heartbeat
   - Статус
   - Телеметрия (CPU, RAM, диски, сеть, процессы)

**Через API:**

```bash
curl https://192.168.1.100:5000/api/agents/HW-ABCD1234EFGH5678 \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)"
```

**Ответ:**
```json
{
  "agent": {
    "name": "Office-PC-01",
    "ip": "192.168.1.50",
    "status": "ONLINE",
    "approved": true,
    "first_seen": "2026-03-20T10:30:00Z",
    "last_seen": "2026-03-20T14:25:30Z"
  },
  "telemetry": {
    "os_info": {
      "name": "Windows 11 Pro",
      "version": "10.0.22631"
    },
    "cpu": {
      "usage_percent": 23.5,
      "cores": 8
    },
    "memory": {
      "total_mb": 16384,
      "used_mb": 8192,
      "percent": 50.0
    },
    "disks": [
      {
        "drive": "C:",
        "total_gb": 476.94,
        "free_gb": 123.45,
        "percent_used": 74.1
      }
    ],
    "network": {
      "interfaces": [
        {
          "name": "Ethernet",
          "ip": "192.168.1.50",
          "mac": "00:11:22:33:44:55"
        }
      ]
    },
    "top_processes": [
      {
        "name": "chrome.exe",
        "pid": 1234,
        "memory_mb": 512,
        "cpu_percent": 5.2
      }
    ]
  }
}
```

---

## Управление задачами

### Типы задач

RMM поддерживает следующие типы задач:

| Тип | Описание | Параметры |
|-----|----------|-----------|
| **RUN_CMD** | Выполнение команды | `cmd`, `shell` (cmd/powershell), `timeout` |
| **PUSH_FILE** | Отправка файла на агент | `file_url`, `save_path` |
| **PULL_FILE** | Получение файла с агента | `file_path` |
| **PS** | Мониторинг процессов | — |
| **FS** | Мониторинг файловой системы | `path` (путь для сканирования) |

### Создание задачи

#### Через Control Panel:

1. **Нажмите "➕ Создать задачу"**
2. **Выберите тип задачи:**
   - **RUN_CMD** — выполнить команду
   - **PUSH_FILE** — отправить файл
   - **PULL_FILE** — получить файл
   - **Мониторинг** (PS/FS)

3. **Заполните параметры:**

**Пример: RUN_CMD**
```
Тип: RUN_CMD
Команда: ipconfig /all
Shell: cmd
Таймаут: 30 секунд
Агенты: Office-PC-01, Office-PC-02
```

**Пример: PUSH_FILE**
```
Тип: PUSH_FILE
Файл: C:\Users\Admin\Documents\config.xml
Путь на агенте: C:\ProgramData\MyApp\config.xml
Агенты: Office-PC-01
```

**Пример: PULL_FILE**
```
Тип: PULL_FILE
Путь на агенте: C:\Users\User\Documents\report.pdf
Агенты: Office-PC-03
```

4. **Нажмите "Создать"**

Задача добавляется в очередь и будет выполнена при следующем polling агента (до 60 сек).

#### Через API:

**RUN_CMD:**
```bash
curl -X POST https://192.168.1.100:5000/api/tasks \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "RUN_CMD",
    "cmd": "Get-Process | Sort-Object CPU -Descending | Select-Object -First 10",
    "shell": "powershell",
    "timeout_seconds": 60,
    "agent_ids": ["HW-ABCD1234EFGH5678"]
  }'
```

**PUSH_FILE:**
```bash
# Сначала загрузите файл на сервер
curl -X POST https://192.168.1.100:5000/api/files/upload \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)" \
  -F "file=@/path/to/local/file.exe"

# Затем создайте задачу PUSH_FILE
curl -X POST https://192.168.1.100:5000/api/tasks \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "PUSH_FILE",
    "file_url": "https://192.168.1.100:5000/files/file.exe",
    "save_path": "C:\\Temp\\file.exe",
    "agent_ids": ["HW-ABCD1234EFGH5678"]
  }'
```

### Статусы задач

**Для каждого агента задача имеет свой статус:**

- **PENDING** — задача создана, ожидает выполнения
- **RUNNING** — задача выполняется агентом
- **DONE** — задача выполнена успешно
- **FAILED** — задача завершилась с ошибкой
- **EXPIRED** — истек таймаут задачи

**Lease механизм:**
Когда агент берет задачу, он получает "lease" (аренду) на 300 секунд (5 минут). Если агент не отправит результат за это время, lease истекает и задача может быть взята снова.

### Мониторинг выполнения задач

**Через Control Panel:**

1. **Откройте вкладку "Задачи"**
2. **Таблица показывает:**
   - ID задачи
   - Тип
   - Команда/описание
   - Статус для каждого агента
   - Время создания

3. **Для просмотра результата:**
   - Нажмите на строку задачи
   - Если статус DONE — откроется окно с результатом
   - Если статус FAILED — откроется окно с ошибкой

**Через API:**

```bash
# Получить информацию о задаче
curl https://192.168.1.100:5000/api/tasks/<task_id> \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)"
```

**Ответ:**
```json
{
  "id": "TASK-20260320-143025-ABCD",
  "task_type": "RUN_CMD",
  "cmd": "ipconfig /all",
  "shell": "cmd",
  "timeout_seconds": 30,
  "agent_ids": ["HW-ABCD1234EFGH5678"],
  "status": {
    "HW-ABCD1234EFGH5678": "DONE"
  },
  "results": {
    "HW-ABCD1234EFGH5678": {
      "stdout": "Windows IP Configuration...",
      "stderr": "",
      "exit_code": 0,
      "finished_at": "2026-03-20T14:31:05Z"
    }
  },
  "created_at": "2026-03-20T14:30:25Z"
}
```

### Мониторинг в реальном времени

Для задач типа **PS** (процессы), **FS** (файловая система):

1. **Создайте задачу мониторинга**
2. **Откройте монитор:**
   - Нажмите "👁️ Монитор" рядом с задачей
   - Откроется окно с обновляющимися данными

**Пример: Мониторинг процессов (PS)**
- Список процессов в реальном времени
- Сортировка по CPU, памяти, имени
- Обновление каждые 5-10 секунд

**Пример: Мониторинг файловой системы (FS)**
- Содержимое указанной папки
- Размеры файлов
- Даты изменения
- Возможность смены папки ("🔄 Сменить путь")

### Отмена и удаление задач

**Принудительное завершение:**

```bash
curl -X POST https://192.168.1.100:5000/api/tasks/force_done \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)" \
  -H "Content-Type: application/json" \
  -d '{"task_id": "TASK-20260320-143025-ABCD"}'
```

**Удаление задачи:**

```bash
curl -X POST https://192.168.1.100:5000/api/tasks/delete \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)" \
  -H "Content-Type: application/json" \
  -d '{"task_id": "TASK-20260320-143025-ABCD"}'
```

**⚠️ ВАЖНО:**
- `force_done` — помечает задачу как DONE, но не удаляет
- `delete` — полностью удаляет задачу из системы
- Для обоих действий требуется привилегия `cancel_tasks`

### Персистентность задач

Агент сохраняет полученные задачи в `tasks.json` локально. Это означает:

✅ **Задачи выполнятся даже после перезагрузки агента**  
✅ **Если агент был оффлайн, он выполнит задачи при подключении**  
✅ **Retry механизм** — задачи могут быть повторены при ошибках

**Механизм deadline:**
- Каждая задача имеет `deadline` = текущее время + `timeout_seconds`
- Если `deadline` истек, задача не выполняется (статус: EXPIRED)
- Агент проверяет `deadline` перед выполнением

---

## Управление пользователями

### Система привилегий

RMM использует гибкую систему привилегий (ACL). Каждый пользователь имеет набор разрешений:

| Привилегия | Описание |
|------------|----------|
| `approve_agent` | Одобрение новых агентов, переименование, удаление |
| `run_cmd` | Выполнение команд на агентах |
| `manage_users` | Создание, изменение, удаление пользователей |
| `push_file` | Отправка файлов на агенты |
| `pull_file` | Получение файлов с агентов |
| `view_info` | Просмотр информации об агентах и задачах |
| `view_logs` | Просмотр логов (audit, http, tech) |
| `shutdown_server` | Выключение сервера |
| `cancel_tasks` | Отмена и удаление задач |

### Создание пользователя

**Через Control Panel:**

1. **Откройте вкладку "Пользователи"**
2. **Нажмите "➕ Создать пользователя"**
3. **Заполните данные:**
   - **Логин**: `operator1`
   - **Пароль**: `SecurePass123!`
   - **Привилегии**: выберите нужные (например: `view_info`, `run_cmd`)
   - **Черный список команд** (опционально): `format`, `del /f`, `rm -rf`

4. **Нажмите "Создать"**

**Через API:**

```bash
curl -X POST https://192.168.1.100:5000/api/users \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "operator1",
    "password": "SecurePass123!",
    "privileges": ["view_info", "run_cmd", "pull_file"],
    "cmd_blacklist": ["format", "del /f", "rm -rf"]
  }'
```

### Черный список команд

Для дополнительной безопасности можно запретить пользователям выполнять определенные команды.

**Механизм работы:**
- Проверка происходит при создании задачи RUN_CMD
- Если команда содержит запрещенное слово — задача отклоняется
- Проверка регистронезависимая

**Пример:**
```json
{
  "username": "junior_admin",
  "cmd_blacklist": ["format", "del /f /q", "shutdown", "reboot", "rm -rf"]
}
```

Пользователь `junior_admin` НЕ сможет выполнить:
- `format C:` ❌
- `del /f /q C:\Important\*` ❌
- `shutdown /s /f` ❌

Но сможет:
- `dir C:\` ✅
- `ipconfig` ✅
- `Get-Process` ✅

### Изменение пароля

**Установка пароля:**

```bash
curl -X POST https://192.168.1.100:5000/api/users/set_password \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "operator1",
    "password": "NewSecurePass456!"
  }'
```

**⚠️ ВАЖНО:**
- Только пользователи с привилегией `manage_users` могут менять чужие пароли
- Пользователь может менять свой пароль без `manage_users`

### Изменение привилегий

```bash
curl -X PUT https://192.168.1.100:5000/api/users/operator1 \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "privileges": ["view_info", "run_cmd", "push_file", "pull_file"]
  }'
```

### Удаление пользователя

**⚠️ ВНИМАНИЕ:** Пользователь **Admin** не может быть удален!

```bash
curl -X DELETE https://192.168.1.100:5000/api/users/operator1 \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)"
```

### Просмотр всех пользователей

```bash
curl https://192.168.1.100:5000/api/users \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)"
```

**Ответ:**
```json
{
  "Admin": {
    "privileges": ["approve_agent", "run_cmd", "manage_users", ...],
    "cmd_blacklist": [],
    "created_at": "2026-03-20T10:00:00Z"
  },
  "operator1": {
    "privileges": ["view_info", "run_cmd"],
    "cmd_blacklist": ["format", "del /f"],
    "created_at": "2026-03-20T14:00:00Z"
  }
}
```

**⚠️ ЗАМЕЧАНИЕ:** Хэши паролей не выводятся в API!

---

## Система логирования

RMM ведет три типа логов:

### 1. Audit Log (`audit.log`)

**Назначение:** Логирование всех административных действий.

**Формат:** JSON, одна запись на строку.

**Содержимое:**
```json
{
  "ts": "2026-03-20T14:30:25Z",
  "user": "Admin",
  "action": "agent_approved",
  "detail": {"agent": "HW-ABCD1234EFGH5678"},
  "ip": "192.168.1.10"
}
```

**События:**
- `login` — успешный вход
- `login_failed` — неудачная попытка входа
- `agent_approved` — одобрение агента
- `agent_blocked` — блокировка агента
- `agent_delete` — удаление агента
- `agent_rename` — переименование агента
- `user_create` — создание пользователя
- `user_delete` — удаление пользователя
- `user_password_change` — смена пароля
- `task_create` — создание задачи
- `task_delete` — удаление задачи
- `task_force_done` — принудительное завершение задачи
- `file_upload` — загрузка файла
- `server_shutdown` — выключение сервера

### 2. HTTP Log (`http.log`)

**Назначение:** Логирование всех HTTP запросов.

**Формат:** JSON.

**Содержимое:**
```json
{
  "ts": "2026-03-20T14:30:25Z",
  "method": "POST",
  "path": "/api/tasks",
  "ip": "192.168.1.10",
  "user": "Admin",
  "status": 200
}
```

### 3. Technical Log (`tech.log`)

**Назначение:** Технические события (ошибки, исключения, внутренние события).

**Формат:** JSON.

**Содержимое:**
```json
{
  "ts": "2026-03-20T14:30:25Z",
  "event": "task_leased",
  "task_id": "TASK-20260320-143025-ABCD",
  "agent_id": "HW-ABCD1234EFGH5678"
}
```

**События:**
- `task_leased` — задача взята агентом
- `task_result_saved` — результат задачи сохранен
- `telemetry_saved` — телеметрия сохранена
- `monitoring_path_updated` — путь мониторинга изменен
- Различные ошибки и исключения

### Просмотр логов

**Через Control Panel:**

1. **Нажмите "📋 Логи"**
2. **Выберите тип лога:**
   - Audit Log
   - HTTP Log
   - Technical Log

**Через API:**

```bash
# Audit Log
curl https://192.168.1.100:5000/api/logs/audit?limit=100 \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)"

# HTTP Log
curl https://192.168.1.100:5000/api/logs/http?limit=100 \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)"

# Technical Log
curl https://192.168.1.100:5000/api/logs/tech?limit=100 \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)"
```

**Параметры:**
- `limit` — количество записей (по умолчанию 100)
- `offset` — смещение (для пагинации)
- `filter_user` — фильтр по пользователю
- `filter_action` — фильтр по действию

### Ротация логов

**⚠️ ВАЖНО:** Логи могут расти очень быстро!

**Рекомендации:**
1. Настройте logrotate (Linux) или планировщик задач (Windows)
2. Архивируйте старые логи
3. Удаляйте логи старше N дней

**Пример logrotate (Linux):**
```
/path/to/rmm/audit.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
}
```

**Пример PowerShell (Windows):**
```powershell
# Удалить логи старше 30 дней
$logPath = "C:\RMM\Server"
Get-ChildItem "$logPath\*.log" | Where-Object {
    $_.LastWriteTime -lt (Get-Date).AddDays(-30)
} | Remove-Item -Force
```

---

## Мониторинг и телеметрия

### Сбор телеметрии

Агент автоматически собирает телеметрию каждые **60 секунд** и отправляет на сервер вместе с heartbeat.

**Данные телеметрии:**

#### 1. Информация об ОС
```json
{
  "os_info": {
    "name": "Windows 11 Pro",
    "version": "10.0.22631",
    "architecture": "x64",
    "build": "22631"
  }
}
```

#### 2. CPU
```json
{
  "cpu": {
    "usage_percent": 23.5,
    "cores": 8,
    "threads": 16
  }
}
```

#### 3. Память
```json
{
  "memory": {
    "total_mb": 16384,
    "used_mb": 8192,
    "free_mb": 8192,
    "percent": 50.0
  }
}
```

#### 4. Диски
```json
{
  "disks": [
    {
      "drive": "C:",
      "total_gb": 476.94,
      "used_gb": 353.49,
      "free_gb": 123.45,
      "percent_used": 74.1,
      "filesystem": "NTFS"
    },
    {
      "drive": "D:",
      "total_gb": 931.51,
      "used_gb": 500.00,
      "free_gb": 431.51,
      "percent_used": 53.7,
      "filesystem": "NTFS"
    }
  ]
}
```

#### 5. Сеть
```json
{
  "network": {
    "interfaces": [
      {
        "name": "Ethernet",
        "description": "Realtek PCIe GbE Family Controller",
        "ip": "192.168.1.50",
        "mac": "00:11:22:33:44:55",
        "status": "Up",
        "speed_mbps": 1000
      }
    ]
  }
}
```

#### 6. Процессы
```json
{
  "top_processes": [
    {
      "name": "chrome.exe",
      "pid": 1234,
      "memory_mb": 512.5,
      "cpu_percent": 5.2
    },
    {
      "name": "explorer.exe",
      "pid": 5678,
      "memory_mb": 234.1,
      "cpu_percent": 1.3
    }
  ]
}
```

### Просмотр телеметрии

**Через Control Panel:**

1. Нажмите на агента в таблице
2. Откроется окно "Информация об агенте"
3. Вкладки:
   - **Общая информация** — статус, IP, время подключения
   - **Система** — ОС, CPU, RAM
   - **Диски** — использование дисков
   - **Сеть** — сетевые интерфейсы
   - **Процессы** — топ процессов по CPU/RAM

**Через API:**

```bash
curl https://192.168.1.100:5000/api/agents/HW-ABCD1234EFGH5678 \
  -H "Authorization: Basic $(echo -n 'Admin:Password' | base64)"
```

### Хранение телеметрии

Телеметрия хранится в файлах:

```
telemetry/
├── HW-ABCD1234EFGH5678.json
├── HW-EFGH5678IJKL9012.json
└── ...
```

Каждый файл содержит последнюю телеметрию агента. При обновлении файл перезаписывается.

**⚠️ ВАЖНО:** Исторические данные НЕ сохраняются. Для хранения истории интегрируйте с InfluxDB, Prometheus или другой TSDB.

---

## Удаление и деинсталляция

### Удаление агента с клиентской машины

#### Вариант 1: Автоматическое удаление (рекомендуется)

Создайте задачу RUN_CMD с командой удаления:

```powershell
# PowerShell команда для удаления
sc stop RMMService; sc delete RMMService; Remove-Item -Path "C:\Program Files\RMMAgent" -Recurse -Force; Remove-Item -Path "HKLM:\SOFTWARE\MYRMM" -Recurse -Force
```

**Через Control Panel:**
1. Создайте задачу RUN_CMD
2. Shell: PowerShell
3. Команда: (см. выше)
4. Агенты: выберите агенты для удаления
5. Создайте задачу

#### Вариант 2: Ручное удаление

**На клиентской машине (от имени администратора):**

```cmd
:: Остановка и удаление службы
sc stop RMMService
sc delete RMMService

:: Удаление файлов
rmdir /s /q "C:\Program Files\RMMAgent"

:: Удаление из System32/SysWOW64
del /q /f C:\Windows\System32\agent.conf
del /q /f C:\Windows\SysWOW64\agent.conf

:: Удаление из реестра
reg delete "HKLM\SOFTWARE\MYRMM" /f
```

### Удаление сервера

```bash
# Остановите сервер (Ctrl+C)

# Удалите все файлы
rm -rf /path/to/rmm/server
```

**⚠️ ВНИМАНИЕ:**
- Все данные (пользователи, агенты, задачи, логи) будут потеряны
- Сделайте резервную копию перед удалением!

**Резервная копия:**
```bash
# Создайте архив
tar -czf rmm_backup_$(date +%Y%m%d).tar.gz \
  users.json agents.json tasks.json \
  pending_approvals.json config.json \
  audit.log http.log tech.log \
  files/ telemetry/
```

### Удаление Control Panel

```bash
# Просто удалите .exe файл
rm controlpanel.exe

# Или удалите папку с исходниками
rm -rf /path/to/controlpanel/
```

Конфигурация серверов хранится в `servers.json` рядом с .exe.

---

## Безопасность

### Аутентификация

RMM использует **двухуровневую аутентификацию:**

#### 1. Аутентификация агента
- **Hardware ID** — уникальный ID на основе железа (материнская плата, процессор, BIOS)
- **Agent Auth** — SHA256 хэш для проверки подлинности агента
- **Server Auth** — SHA256 хэш для проверки подлинности сервера

**Процесс:**
1. Агент отправляет регистрацию с `agent_id` (hardware ID) и `agent_auth` (хэш)
2. Сервер проверяет хэш
3. Если хэш валиден — агент добавляется в `pending_approvals`
4. Администратор одобряет агента вручную
5. Агент становится активным

**⚠️ ВАЖНО:**
- Хэш `agent_auth` должен совпадать с `server_secret` в `config.json` сервера
- Используйте `hashmade.py` для генерации хэша
- НЕ передавайте секретный ключ в конфиге — только хэш!

#### 2. Аутентификация администратора
- **HTTP Basic Auth** — логин и пароль в заголовке Authorization
- **Bcrypt хэширование** паролей (werkzeug)
- **Обязательные требования к паролю:**
  - Минимум 8 символов
  - Заглавные и строчные буквы
  - Цифры

**Процесс:**
1. Панель управления/API отправляет заголовок: `Authorization: Basic <base64(username:password)>`
2. Сервер проверяет хэш пароля
3. Если валиден — доступ разрешен
4. Проверка привилегий для каждого действия

### Шифрование

#### HTTPS/SSL (рекомендуется для production)

**Генерация сертификатов (локальная сеть):**
```bash
# Установите mkcert
brew install mkcert  # macOS
scoop install mkcert # Windows
apt install mkcert   # Linux

# Генерация CA
mkcert -install

# Генерация сертификата
mkcert myserver.local 192.168.1.100

# Файлы:
# myserver.local+1.pem       → сертификат
# myserver.local+1-key.pem   → приватный ключ
```

Поместите файлы в папку с `server.py`. Сервер автоматически использует HTTPS.

**Production (Let's Encrypt):**
```bash
# Установите certbot
sudo apt install certbot

# Получите сертификат
sudo certbot certonly --standalone -d rmm.example.com

# Сертификаты в:
# /etc/letsencrypt/live/rmm.example.com/fullchain.pem
# /etc/letsencrypt/live/rmm.example.com/privkey.pem

# Переименуйте или создайте симлинки:
ln -s /etc/letsencrypt/live/rmm.example.com/fullchain.pem myserver.local+1.pem
ln -s /etc/letsencrypt/live/rmm.example.com/privkey.pem myserver.local+1-key.pem
```

**В agent.conf:**
```ini
server=https://rmm.example.com:443
```

**В Control Panel:**
- HTTPS: ✅
- Проверять SSL: ✅ (для валидных сертификатов)

### Защита от атак

#### 1. CSRF Protection
Сервер включает заголовки безопасности:
```python
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000
Content-Security-Policy: default-src 'self'
```

#### 2. Rate Limiting
**⚠️ В текущей версии НЕ реализован!**

Для production добавьте:
```python
from flask_limiter import Limiter
limiter = Limiter(app, key_func=lambda: request.remote_addr)

@app.route("/api/login")
@limiter.limit("5 per minute")
def login():
    ...
```

#### 3. IP Whitelisting
Ограничьте доступ к серверу только с доверенных IP:

**Через nginx (reverse proxy):**
```nginx
location /api/ {
    allow 192.168.1.0/24;  # Локальная сеть
    allow 10.0.0.0/8;      # VPN
    deny all;
    
    proxy_pass http://localhost:5000;
}
```

#### 4. Firewall
Разрешите доступ только к портам сервера:

```bash
# Ubuntu (ufw)
sudo ufw allow from 192.168.1.0/24 to any port 5000
sudo ufw enable

# Windows (PowerShell)
New-NetFirewallRule -DisplayName "RMM Server" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow
```

### Безопасность агента

#### 1. Запуск от SYSTEM
Агент работает как служба от имени **NT AUTHORITY\SYSTEM** — самый высокий уровень прав.

**⚠️ РИСКИ:**
- Агент может выполнить ЛЮБУЮ команду
- Взлом агента = полный контроль над машиной

**РЕКОМЕНДАЦИИ:**
- Ограничивайте доступ к серверу (HTTPS, IP whitelist)
- Используйте систему одобрения агентов
- Регулярно проверяйте логи
- Используйте черный список команд для пользователей

#### 2. Секреты в реестре
Агент хранит `agent_auth` и `server_auth` в реестре с ACL:

```
HKLM\SOFTWARE\MYRMM\Secrets
- SYSTEM: Full Control
- Administrators: Read + Delete
- Everyone: Deny All
```

**⚠️ ВАЖНО:**
- ACL механизм в текущей версии ОТКЛЮЧЕН (см. `HomeDomainAgenInstaller.cpp`)
- Для production реализуйте `SetRegistryACL` корректно

#### 3. Конфиг agent.conf
Файл `agent.conf` содержит хэш, НЕ секретный ключ!

**НЕ БЕЗОПАСНО:**
```ini
server_secret=a1b2c3d4e5f6...  # ❌ НИКОГДА!
```

**БЕЗОПАСНО:**
```ini
server_auth=9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08  # ✅
```

### Рекомендации по безопасности

1. **Используйте HTTPS** — обязательно для production
2. **Сильные пароли** — минимум 12 символов, комбинация букв/цифр/символов
3. **Ограничивайте привилегии** — не давайте всем пользователям `run_cmd`
4. **Используйте черный список команд** — запретите опасные команды
5. **Регулярно проверяйте логи** — мониторинг audit.log
6. **Обновляйте систему** — применяйте патчи безопасности
7. **Резервные копии** — регулярные бэкапы данных
8. **Сегментация сети** — изолируйте RMM сервер в отдельной подсети
9. **VPN** — для доступа извне используйте VPN, не открывайте порты в интернет
10. **Мониторинг** — интегрируйте с SIEM (Splunk, ELK, Wazuh)

---

## Возможные проблемы и решения

### Проблемы с сервером

#### 1. Сервер не запускается

**Симптомы:**
```
Address already in use
```

**Причина:** Порт 5000 занят другим процессом.

**Решение:**
```bash
# Найдите процесс, использующий порт
lsof -i :5000  # Linux/macOS
netstat -ano | findstr :5000  # Windows

# Завершите процесс или измените порт в config.json
{
  "port": 5001
}
```

#### 2. SSL ошибки

**Симптомы:**
```
ssl.SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]
```

**Причина:** Невалидный/самоподписанный сертификат.

**Решение:**
```bash
# В Control Panel: HTTPS ✅, Проверять SSL ❌
# Или используйте валидные сертификаты (Let's Encrypt)
```

#### 3. Ошибки JSON

**Симптомы:**
```
json.decoder.JSONDecodeError: Expecting value
```

**Причина:** Поврежденные JSON файлы (users.json, agents.json и т.д.)

**Решение:**
```bash
# Удалите поврежденный файл (создастся новый)
rm users.json

# Или восстановите из резервной копии
cp backup/users.json .
```

#### 4. Логи переполнены

**Симптомы:**
- Медленная работа сервера
- Диск заполнен

**Решение:**
```bash
# Очистите старые логи
> audit.log
> http.log
> tech.log

# Настройте ротацию (см. раздел "Ротация логов")
```

### Проблемы с агентом

#### 1. Служба не запускается

**Симптомы:**
```
Error 1053: The service did not respond in a timely fashion
Error 193: %1 is not a valid Win32 application
```

**Причина:**
- Error 1053: Агент не отвечает при старте (возможно, недоступен сервер)
- Error 193: Неверный путь к .exe (пробелы в пути без кавычек)

**Решение:**

```cmd
:: Проверьте путь к службе
sc qc RMMService

:: Должно быть:
:: BINARY_PATH_NAME: "C:\Program Files\RMMAgent\HomeDomainClient.exe"

:: Если нет кавычек — переустановите службу
sc delete RMMService
sc create RMMService binPath= "\"C:\Program Files\RMMAgent\HomeDomainClient.exe\"" start= auto

:: Для Error 1053 — проверьте доступность сервера
ping 192.168.1.100
```

#### 2. Агент не подключается к серверу

**Симптомы:**
```
[-] Server not found. Retrying in 10s...
[!] Connection failed. Resetting server URL.
```

**Причина:**
- Сервер недоступен
- Неверный URL в agent.conf
- Firewall блокирует порт

**Решение:**

```bash
# 1. Проверьте доступность сервера
curl https://192.168.1.100:5000/server_info

# 2. Проверьте agent.conf
type "C:\Program Files\RMMAgent\agent.conf"

# 3. Проверьте firewall
# Windows: Панель управления → Брандмауэр Windows → Разрешить приложение

# 4. Проверьте agent.log
type "C:\Program Files\RMMAgent\agent.log"
```

#### 3. Агент в PENDING_APPROVAL навсегда

**Симптомы:**
- Агент в списке "На одобрении"
- Агент не получает задачи

**Причина:**
- Администратор не одобрил агента

**Решение:**
```bash
# Одобрите агента через Control Panel или API
curl -X POST https://192.168.1.100:5000/api/agents/approve \
  -H "Authorization: Basic <base64(Admin:Password)>" \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "HW-ABCD1234EFGH5678", "action": "approve"}'
```

#### 4. Агент показывает OFFLINE

**Симптомы:**
- В Control Panel агент красный 🔴 OFFLINE
- Но служба запущена

**Причина:**
- Агент не отправлял heartbeat > 120 секунд
- Возможно, проблемы с сетью

**Решение:**
```cmd
:: Перезапустите службу
sc stop RMMService
sc start RMMService

:: Проверьте логи
type "C:\Program Files\RMMAgent\agent.log"

:: Проверьте сеть
ping 192.168.1.100
```

#### 5. Задачи не выполняются

**Симптомы:**
- Статус задачи PENDING навсегда
- Агент ONLINE, но не берет задачи

**Причина:**
- Агент не одобрен (`approved: false`)
- Ошибка в логике агента
- Задача истекла (deadline)

**Решение:**
```bash
# 1. Проверьте статус агента
curl https://192.168.1.100:5000/api/agents/HW-ABCD1234EFGH5678 \
  -H "Authorization: Basic <base64>"

# Убедитесь: "approved": true

# 2. Проверьте deadline задачи
curl https://192.168.1.100:5000/api/tasks/TASK-ID \
  -H "Authorization: Basic <base64>"

# 3. Проверьте agent.log
type "C:\Program Files\RMMAgent\agent.log"
```

### Проблемы с Control Panel

#### 1. Не удается подключиться к серверу

**Симптомы:**
```
Ошибка: Connection refused
Ошибка: SSL certificate verify failed
```

**Причина:**
- Неверный адрес/порт
- SSL проблемы
- Firewall

**Решение:**
1. Проверьте адрес и порт сервера
2. Если HTTPS с самоподписанным сертификатом: HTTPS ✅, Проверять SSL ❌
3. Проверьте доступность сервера через браузер: `https://192.168.1.100:5000/server_info`

#### 2. Ошибка авторизации

**Симптомы:**
```
401 Unauthorized
```

**Причина:**
- Неверный логин/пароль
- Пользователь не существует

**Решение:**
```bash
# Проверьте пользователя
curl https://192.168.1.100:5000/api/users \
  -H "Authorization: Basic <base64(Admin:DefaultPass)>"

# Если пароль забыт — сбросьте через прямое редактирование users.json
# Или создайте нового администратора
```

#### 3. Панель зависает

**Симптомы:**
- Панель не отвечает при подключении
- "Попытка 1/10 → ..."

**Причина:**
- Сервер недоступен
- Медленная сеть

**Решение:**
- Нажмите "Отмена"
- Проверьте доступность сервера
- Уменьшите количество попыток в коде (ConnectWorker.tries)

### Общие рекомендации

#### Диагностика

1. **Проверьте логи:**
   - Сервер: `audit.log`, `tech.log`, `http.log`
   - Агент: `C:\Program Files\RMMAgent\agent.log`

2. **Проверьте сеть:**
   ```bash
   ping <server_ip>
   telnet <server_ip> 5000
   curl https://<server_ip>:5000/server_info
   ```

3. **Проверьте службы:**
   ```cmd
   sc query RMMService
   ```

4. **Проверьте firewall:**
   - Windows: Панель управления → Брандмауэр
   - Linux: `sudo ufw status`

5. **Проверьте сертификаты:**
   ```bash
   openssl s_client -connect <server_ip>:5000
   ```

#### Восстановление после сбоя

1. **Резервная копия:**
   ```bash
   # Регулярно делайте бэкапы
   tar -czf rmm_backup.tar.gz users.json agents.json tasks.json config.json
   ```

2. **Восстановление:**
   ```bash
   # Остановите сервер
   # Восстановите файлы из бэкапа
   tar -xzf rmm_backup.tar.gz
   # Запустите сервер
   ```

3. **Очистка:**
   ```bash
   # Если система повреждена — очистите все
   rm users.json agents.json tasks.json pending_approvals.json
   # Запустите сервер (создадутся новые файлы)
   # Переустановите агентов
   ```

---

## 📖 API Reference

### Аутентификация

Все API запросы требуют **HTTP Basic Authentication:**

```bash
Authorization: Basic <base64(username:password)>
```

**Пример:**
```bash
echo -n 'Admin:Password' | base64
# QWRtaW46UGFzc3dvcmQ=

curl https://192.168.1.100:5000/api/agents \
  -H "Authorization: Basic QWRtaW46UGFzc3dvcmQ="
```

### Эндпоинты

#### Server Info

**GET /server_info**

Получить информацию о сервере (публичный эндпоинт, без аутентификации).

**Response:**
```json
{
  "name": "NODE-2026: ГЛАВНЫЙ УЗЕЛ УПРАВЛЕНИЯ",
  "version": "1.0",
  "time": "2026-03-20T14:30:25Z"
}
```

---

#### Users

**GET /api/users**

Получить список всех пользователей.

**Требуемые права:** `view_info`

**Response:**
```json
{
  "Admin": {
    "privileges": [...],
    "cmd_blacklist": [],
    "created_at": "2026-03-20T10:00:00Z"
  },
  "operator1": {
    "privileges": ["view_info"],
    "cmd_blacklist": ["format"],
    "created_at": "2026-03-20T14:00:00Z"
  }
}
```

---

**POST /api/users**

Создать нового пользователя.

**Требуемые права:** `manage_users`

**Request:**
```json
{
  "username": "operator1",
  "password": "SecurePass123!",
  "privileges": ["view_info", "run_cmd"],
  "cmd_blacklist": ["format", "del /f"]
}
```

**Response:**
```json
{
  "ok": true
}
```

---

**PUT /api/users/{username}**

Изменить привилегии пользователя.

**Требуемые права:** `manage_users`

**Request:**
```json
{
  "privileges": ["view_info", "run_cmd", "push_file"]
}
```

---

**DELETE /api/users/{username}**

Удалить пользователя.

**Требуемые права:** `manage_users`

**Response:**
```json
{
  "ok": true
}
```

---

**POST /api/users/set_password**

Установить пароль пользователю.

**Требуемые права:** `manage_users` (или для своего пароля)

**Request:**
```json
{
  "username": "operator1",
  "password": "NewPass456!"
}
```

---

#### Agents

**GET /api/agents**

Получить список всех агентов.

**Требуемые права:** Любой аутентифицированный пользователь

**Response:**
```json
{
  "HW-ABCD1234EFGH5678": {
    "name": "Office-PC-01",
    "ip": "192.168.1.50",
    "status": "ONLINE",
    "approved": true,
    "first_seen": "2026-03-20T10:30:00Z",
    "last_seen": "2026-03-20T14:25:30Z"
  }
}
```

---

**GET /api/agents/{agent_id}**

Получить детальную информацию об агенте.

**Требуемые права:** `view_info`

**Response:**
```json
{
  "agent": {
    "name": "Office-PC-01",
    ...
  },
  "telemetry": {
    "os_info": {...},
    "cpu": {...},
    "memory": {...},
    ...
  }
}
```

---

**POST /api/agents/approve**

Одобрить или заблокировать агента.

**Требуемые права:** `approve_agent`

**Request:**
```json
{
  "agent_id": "HW-ABCD1234EFGH5678",
  "action": "approve"  // или "block"
}
```

---

**POST /api/agents/rename**

Переименовать агента.

**Требуемые права:** `approve_agent`

**Request:**
```json
{
  "agent_id": "HW-ABCD1234EFGH5678",
  "new_name": "Office-PC-01"
}
```

---

**POST /api/agents/delete**

Удалить агента.

**Требуемые права:** `approve_agent`

**Request:**
```json
{
  "agent_id": "HW-ABCD1234EFGH5678"
}
```

---

#### Tasks

**GET /api/tasks**

Получить список всех задач.

**Требуемые права:** `view_info`

**Response:**
```json
[
  {
    "id": "TASK-20260320-143025-ABCD",
    "task_type": "RUN_CMD",
    "cmd": "ipconfig /all",
    "shell": "cmd",
    "timeout_seconds": 30,
    "agent_ids": ["HW-ABCD1234EFGH5678"],
    "status": {
      "HW-ABCD1234EFGH5678": "DONE"
    },
    "created_at": "2026-03-20T14:30:25Z"
  }
]
```

---

**POST /api/tasks**

Создать задачу.

**Требуемые права:** Зависит от типа задачи

**RUN_CMD:**
```json
{
  "task_type": "RUN_CMD",
  "cmd": "Get-Process",
  "shell": "powershell",
  "timeout_seconds": 60,
  "agent_ids": ["HW-ABCD1234EFGH5678"]
}
```

**PUSH_FILE:**
```json
{
  "task_type": "PUSH_FILE",
  "file_url": "https://192.168.1.100:5000/files/file.exe",
  "save_path": "C:\\Temp\\file.exe",
  "agent_ids": ["HW-ABCD1234EFGH5678"]
}
```

**PULL_FILE:**
```json
{
  "task_type": "PULL_FILE",
  "file_path": "C:\\Users\\User\\report.pdf",
  "agent_ids": ["HW-ABCD1234EFGH5678"]
}
```

---

**GET /api/tasks/{task_id}**

Получить информацию о задаче.

**Требуемые права:** `view_info`

---

**POST /api/tasks/delete**

Удалить задачу.

**Требуемые права:** `cancel_tasks`

**Request:**
```json
{
  "task_id": "TASK-20260320-143025-ABCD"
}
```

---

**POST /api/tasks/force_done**

Принудительно завершить задачу.

**Требуемые права:** `cancel_tasks`

**Request:**
```json
{
  "task_id": "TASK-20260320-143025-ABCD"
}
```

---

#### Files

**POST /api/files/upload**

Загрузить файл на сервер.

**Требуемые права:** `push_file`

**Request:** multipart/form-data

```bash
curl -X POST https://192.168.1.100:5000/api/files/upload \
  -H "Authorization: Basic <base64>" \
  -F "file=@/path/to/file.exe"
```

**Response:**
```json
{
  "ok": true,
  "filename": "file.exe",
  "url": "https://192.168.1.100:5000/files/file.exe"
}
```

---

**GET /files/{filename}**

Скачать файл с сервера.

**Требуемые права:** `pull_file`

---

#### Logs

**GET /api/logs/audit**

Получить записи из audit.log.

**Требуемые права:** `view_logs`

**Parameters:**
- `limit` — количество записей (по умолчанию 100)
- `offset` — смещение

**Response:**
```json
[
  {
    "ts": "2026-03-20T14:30:25Z",
    "user": "Admin",
    "action": "agent_approved",
    "detail": {"agent": "HW-ABCD1234EFGH5678"},
    "ip": "192.168.1.10"
  }
]
```

---

**GET /api/logs/http**

Получить записи из http.log.

---

**GET /api/logs/tech**

Получить записи из tech.log.

---

#### System

**POST /api/system/shutdown**

Выключить сервер.

**Требуемые права:** `shutdown_server`

**Response:**
```json
{
  "ok": true,
  "message": "Server shutdown initiated"
}
```

---

**⚠️ DISCLAIMER:**

Данное ПО предоставляется "как есть" без каких-либо гарантий. Используйте на свой риск. Автор не несет ответственности за любой ущерб, причиненный использованием данного ПО.

**Безопасность превыше всего!** 🔒
