"""
MacBook Pro Bridge for Dynamic Island
Direct integration with:
- Ranuk Hub (http://192.168.1.34:8788)
- Empleados Agentes Slack Feed (~/.ranukita/equipo_canal.jsonl)
- Daily LaunchAgents scheduled crons
- Ranukita core microservices, battery & uptime
"""
import subprocess
import sys
import json
import re
import urllib.request
from datetime import datetime
from typing import Dict, Any, List

AVATAR_ICONS = {
    "bounty-tdd": "⚡",
    "bounty-hunter": "⚡",
    "licitador": "💼",
    "moltbot": "🦞",
    "moltbook_scout": "🦞",
    "auditor_ada": "🔍",
    "asistente_ejecutivo": "📋",
    "cloud_monetizer": "☁️",
    "hunter_ejecutivo": "🎯",
    "api-hunter": "🎯",
    "productor_audiovisual": "🎬",
    "bilibili_creator": "📺",
    "procurement_apis": "🔑",
    "micro_monetizer": "🪙",
    "stripe-auditor": "💳",
    "overseer": "🛡️",
    "antigravity": "🚀",
    "director_general": "👔",
    "emilio": "👑",
    "sistema": "⚙️",
    "default": "🤖"
}

def fix_mojibake(text: str) -> str:
    """Fixes UTF-8 mojibake (e.g. Ã³ -> ó, vÃ¡lida -> válida)."""
    if not text:
        return ""
    if "Ã" in text or "Â" in text or "â" in text:
        try:
            return text.encode("latin1").decode("utf-8")
        except Exception:
            pass
    return text

class MacBridge:
    def __init__(self, host: str = "192.168.1.34", user: str = "emilioranucoli", hub_url: str = "http://192.168.1.34:8788"):
        self.host = host
        self.user = user
        self.hub_url = hub_url
        self.cached_crons = []
        self.last_crons_fetch = 0

    def execute_remote(self, command: str, timeout: int = 5) -> tuple[int, str]:
        target = f"{self.user}@{self.host}"
        cmd = [
            "ssh",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=2",
            "-o", "StrictHostKeyChecking=accept-new",
            target,
            command
        ]
        try:
            kwargs = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                **kwargs
            )
            return res.returncode, res.stdout.strip()
        except subprocess.TimeoutExpired:
            return -1, "Timeout"
        except Exception as e:
            return -1, str(e)

    def fetch_slack_messages(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Reads latest messages from the agent Slack channel (~/.ranukita/equipo_canal.jsonl)."""
        cmd = f"tail -n {limit} ~/.ranukita/equipo_canal.jsonl 2>/dev/null"
        code, out = self.execute_remote(cmd, timeout=3)
        messages = []
        if code == 0 and out:
            for line in out.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    sender = data.get("de") or data.get("remitente") or "sistema"
                    icon = AVATAR_ICONS.get(sender, AVATAR_ICONS["default"])
                    ts = data.get("ts", "")
                    time_str = ts.split("T")[-1][:5] if "T" in ts else ts[-8:-3]
                    raw_text = data.get("texto", "")
                    clean_text = fix_mojibake(raw_text)
                    messages.append({
                        "sender": sender,
                        "dest": data.get("para") or data.get("destinatario") or "equipo",
                        "text": clean_text,
                        "time": time_str or "--:--",
                        "icon": icon
                    })
                except Exception:
                    pass
        messages.reverse() # newest first
        return messages

    def send_slack_message(self, text: str, sender: str = "emilio") -> bool:
        """Appends a new directive / message to the agents Slack channel."""
        if not text.strip():
            return False
        now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        entry = json.dumps({"ts": now_iso, "de": sender, "para": "equipo", "texto": text.strip()}, ensure_ascii=False)
        # Append remotely
        cmd = f"echo {json.dumps(entry)} >> ~/.ranukita/equipo_canal.jsonl"
        code, _ = self.execute_remote(cmd, timeout=3)
        return code == 0

    def fetch_daily_crons(self) -> List[Dict[str, Any]]:
        """Parses all scheduled launchd crons and calculates remaining/done for today."""
        now = datetime.now()
        now_str = now.strftime("%H:%M")

        # Refresh cron definitions once every 10 mins
        if not self.cached_crons or (now.timestamp() - self.last_crons_fetch > 600):
            python_script = (
                "import plistlib, glob, os, json\n"
                "crons = []\n"
                "for p in sorted(glob.glob(os.path.expanduser('~/Library/LaunchAgents/com.ranuk.*.plist'))):\n"
                "    try:\n"
                "        with open(p, 'rb') as f:\n"
                "            d = plistlib.load(f)\n"
                "        label = d.get('Label', '').replace('com.ranuk.', '')\n"
                "        cal = d.get('StartCalendarInterval')\n"
                "        if cal:\n"
                "            if isinstance(cal, dict): cal = [cal]\n"
                "            for c in cal:\n"
                "                h = c.get('Hour', None)\n"
                "                m = c.get('Minute', 0)\n"
                "                if h is not None:\n"
                "                    crons.append({'time': f'{h:02d}:{m:02d}', 'title': label})\n"
                "    except: pass\n"
                "crons.sort(key=lambda x: x['time'])\n"
                "print(json.dumps(crons))\n"
            )
            target = f"{self.user}@{self.host}"
            cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=2", target, "python3 -"]
            try:
                kwargs = {}
                if sys.platform == "win32":
                    kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                p = subprocess.run(
                    cmd,
                    input=python_script,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    timeout=5,
                    **kwargs
                )
                if p.returncode == 0 and p.stdout.strip():
                    self.cached_crons = json.loads(p.stdout.strip())
                    self.last_crons_fetch = now.timestamp()
            except Exception:
                pass

        # Calculate status
        results = []
        for c in self.cached_crons:
            is_done = c["time"] < now_str
            results.append({
                "time": c["time"],
                "title": c["title"],
                "done": is_done,
                "type": "cron"
            })
        return results

    def fetch_hub_data(self) -> Dict[str, Any]:
        """Queries the Ranuk Hub HTTP API."""
        try:
            req = urllib.request.Request(f"{self.hub_url}/api/empresa", headers={"User-Agent": "Island"})
            with urllib.request.urlopen(req, timeout=1.5) as r:
                if r.status == 200:
                    data = json.loads(r.read())
                    empresa = data.get("empleados", {})
                    estado = data.get("estado_vivo", {})
                    return {
                        "ok": True,
                        "hub_live": True,
                        "empresa": empresa.get("empresa", "Ranuk IT Solutions"),
                        "ceo": empresa.get("ceo", "Emilio Ranucoli"),
                        "empleados_count": len(empresa.get("empleados", {})),
                        "estado": estado
                    }
        except Exception:
            pass
        return {"ok": False, "hub_live": False, "empresa": "Ranuk IT Solutions", "empleados_count": 0}

    def fetch_full_status(self) -> Dict[str, Any]:
        """Gathers full live state: system, microservices, hub, slack, and daily crons."""
        remote_script = (
            "echo '---SERVICES---'; "
            "ps -Ao pid,args | grep -E 'ranukita|rk-' | grep -v grep | head -n 14 || echo 'NOT_FOUND'; "
            "echo '---BATT---'; "
            "pmset -g batt 2>/dev/null | grep -E -o '[0-9]+%' || echo '100%'; "
            "echo '---UPTIME---'; "
            "uptime | awk -F'(up |,[0-9]+ user)' '{print $2}'"
        )
        code, output = self.execute_remote(remote_script, timeout=4)
        if code != 0:
            return {
                "connected": False,
                "bot_running": False,
                "bot_info": "Mac no accesible",
                "battery": "--",
                "uptime": "--",
                "services": [],
                "slack_messages": [],
                "crons": [],
                "hub": {"hub_live": False},
                "error": output or "Conexión fallida"
            }

        # Parse sections
        sections = {}
        curr_key = None
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("---") and line.endswith("---"):
                curr_key = line.replace("---", "")
                sections[curr_key] = []
            elif curr_key:
                sections[curr_key].append(line)

        # Services
        services = []
        for l in sections.get("SERVICES", []):
            if l and l != "NOT_FOUND":
                m = re.search(r'([a-zA-Z0-9_\-]+\.py)', l)
                if m:
                    services.append(m.group(1))

        # Battery & Uptime
        batt_lines = sections.get("BATT", [])
        battery = batt_lines[0] if batt_lines else "100%"
        uptime_lines = sections.get("UPTIME", [])
        uptime = uptime_lines[0].strip() if uptime_lines else "Activo"

        # Hub & Slack & Crons
        hub = self.fetch_hub_data()
        slack = self.fetch_slack_messages(limit=8)
        crons = self.fetch_daily_crons()

        return {
            "connected": True,
            "bot_running": len(services) > 0,
            "bot_info": f"Activo ({len(services)} microservicios)",
            "battery": battery,
            "uptime": uptime,
            "services": services,
            "hub": hub,
            "slack_messages": slack,
            "crons": crons,
            "error": None
        }

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    b = MacBridge()
    st = b.fetch_full_status()
    print("Full status keys:", list(st.keys()))
    print("Services:", len(st.get("services", [])))
    print("Slack messages:", len(st.get("slack_messages", [])))
    print("Crons:", len(st.get("crons", [])))
