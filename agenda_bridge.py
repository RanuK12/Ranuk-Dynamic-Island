"""
Agenda and Task manager bridge for Dynamic Island
Manages today's agenda, meetings, and quick to-dos.
"""
import json
import os
from datetime import datetime
from typing import List, Dict, Any

class AgendaBridge:
    def __init__(self, storage_path: str = None):
        if storage_path is None:
            storage_path = os.path.join(os.path.dirname(__file__), "agenda.json")
        self.storage_path = storage_path
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.storage_path):
            sample = {
                "events": [
                    {"time": "15:00", "title": "Revisión bot Ranukita & Mac jobs", "done": False},
                    {"time": "17:30", "title": "Check de repositorios GitHub", "done": False},
                    {"time": "19:00", "title": "Seguimiento en LinkedIn", "done": False}
                ],
                "quick_notes": "Mini Oficina lista. Isla Dinámica operativa."
            }
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(sample, f, indent=2, ensure_ascii=False)

    def load_data(self) -> Dict[str, Any]:
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"events": [], "quick_notes": ""}

    def save_data(self, data: Dict[str, Any]):
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get_today_summary(self) -> Dict[str, Any]:
        data = self.load_data()
        events = data.get("events", [])
        total = len(events)
        completed = sum(1 for e in events if e.get("done", False))
        
        # Find next event
        now_str = datetime.now().strftime("%H:%M")
        next_event = None
        for ev in events:
            if not ev.get("done") and ev.get("time", "") >= now_str:
                next_event = ev
                break
        if not next_event and events:
            # fallback to first unfinished
            for ev in events:
                if not ev.get("done"):
                    next_event = ev
                    break

        return {
            "total": total,
            "completed": completed,
            "next_event": next_event,
            "events": events,
            "quick_notes": data.get("quick_notes", "")
        }

    def toggle_event(self, index: int):
        data = self.load_data()
        events = data.get("events", [])
        if 0 <= index < len(events):
            events[index]["done"] = not events[index].get("done", False)
            self.save_data(data)
