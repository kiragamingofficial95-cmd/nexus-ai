"""Safe PC control tools (Windows). All destructive ops need UI confirmation."""
import os, sys, subprocess, platform, shutil, socket, getpass
from pathlib import Path

def pc_info():
    try:
        import psutil  # optional
        has_ps = True
    except Exception:
        has_ps = False
    info = {
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "machine": platform.machine(),
        "processor": platform.processor(),
        "user": getpass.getuser(),
        "hostname": socket.gethostname(),
        "cwd": os.getcwd(),
    }
    if has_ps:
        try:
            import psutil
            info["cpu%"] = psutil.cpu_percent(interval=0.5)
            vm = psutil.virtual_memory()
            info["ram"] = f"{vm.percent}% used ({vm.used//2**30}G/{vm.total//2**30}G)"
            info["disk"] = f"{psutil.disk_usage('/').percent}% used"
        except Exception:
            pass
    return info

def file_list(path="."):
    p = Path(path).expanduser()
    if not p.exists():
        return f"Not found: {p}"
    return "\n".join(f"{'[D]' if (p/x).is_dir() else '[F]'} {x}" for x in sorted(os.listdir(p))[:200])

def file_read(path, max_chars=15000):
    p = Path(path).expanduser()
    try:
        return open(p, encoding="utf-8", errors="ignore").read()[:max_chars]
    except Exception as e:
        return f"Error: {e}"

def file_write(path, content):
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    open(p, "w", encoding="utf-8").write(content)
    return f"Wrote {len(content)} chars to {p}"

BLOCKED = ("format ", "del /f /s /q c:", "rm -rf /", "mkfs", ":(){:|:&};:")

def shell_run(cmd, timeout=30):
    c = cmd.strip()
    low = c.lower()
    for b in BLOCKED:
        if b in low:
            return "BLOCKED: destructive command refused."
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or "") + ("\n[stderr]\n" + r.stderr if r.stderr else "")
        return out[:12000] or f"(exit {r.returncode}, no output)"
    except subprocess.TimeoutExpired:
        return "Timeout."
    except Exception as e:
        return f"Error: {e}"

def app_launch(name):
    try:
        if platform.system() == "Windows":
            os.startfile(name)  # type: ignore
        else:
            subprocess.Popen([name])
        return f"Launched {name}"
    except Exception:
        try:
            subprocess.Popen(name, shell=True)
            return f"Launched {name}"
        except Exception as e:
            return f"Error: {e}"

def screenshot(save="screenshot.png"):
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        img.save(save)
        return f"Saved {os.path.abspath(save)} ({img.size[0]}x{img.size[1]})"
    except Exception as e:
        return f"Screenshot failed: {e}"
