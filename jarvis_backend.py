# ============================================================
# JARVIS BACKEND (Google Colab, libre, T4 GPU)
# Colab: Runtime > Change runtime type > T4 GPU
#
# CELL 1:
#   !pip -q install diffusers transformers accelerate flask flask-cors opencv-python-headless
# CELL 2: i-paste ang buong file na ito at i-run.
# Ipi-print nito ang URL (https://xxxx.trycloudflare.com) -> ilagay sa app.
# ============================================================
import os, json, re, uuid, threading, subprocess, time
import torch
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from transformers import AutoTokenizer, AutoModelForCausalLM
from diffusers import DiffusionPipeline, DPMSolverMultistepScheduler
from diffusers.utils import export_to_video

os.makedirs("videos", exist_ok=True)
MEM_FILE = "jarvis_memory.json"
app = Flask(__name__)
CORS(app)
jobs = {}
gpu_lock = threading.Lock()

# ---------------- UTAK (LLM) ----------------
LLM = "Qwen/Qwen2.5-1.5B-Instruct"
tok = AutoTokenizer.from_pretrained(LLM)
llm = AutoModelForCausalLM.from_pretrained(LLM, torch_dtype=torch.float16, device_map="cuda")

# ---------------- TEXT-TO-VIDEO ----------------
pipe = DiffusionPipeline.from_pretrained(
    "damo-vilab/text-to-video-ms-1.7b", torch_dtype=torch.float16, variant="fp16")
pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)
pipe.enable_model_cpu_offload()
pipe.enable_vae_slicing()

# ---------------- MEMORY ----------------
def load_mem():
    if os.path.exists(MEM_FILE):
        return json.load(open(MEM_FILE))
    return {"facts": [], "history": []}

def save_mem(m):
    json.dump(m, open(MEM_FILE, "w"), ensure_ascii=False)

SYSTEM = """You are JARVIS, the AI brain of the app Jhumong Digital Hub: a witty, loyal, proactive assistant and video studio director.
You also help plan daily content for Facebook Reels and YouTube Shorts.
You have your own personality, opinions and humor. Call the user 'Boss'.
Reply in the same language as the user (Filipino/Taglish if they use it).
Reply ONLY with one JSON object, no other text:
{"reply":"short spoken reply (1-2 sentences)",
 "action":"none|generate|edit",
 "prompt":"rich cinematic ENGLISH video prompt (only if action=generate)",
 "scenes":["scene 1 prompt","scene 2 prompt"],
 "edit":{"op":"trim|speed|text|reverse|gray|upscale","start":0,"end":3,"factor":2.0,"text":"caption"},
 "remember":"new lasting fact about the user, or empty string"}
Use action=generate when the user wants a new video. For a longer video or a story, fill "scenes"
with 2-6 connected English prompts (each scene is ~3 seconds); otherwise leave "scenes" empty. Use action=edit to modify the last video.
Otherwise action=none. Occasionally suggest creative ideas on your own."""

def think(message, last_id):
    mem = load_mem()
    sys = SYSTEM + "\nKnown facts about Boss: " + "; ".join(mem["facts"][-20:])
    if last_id:
        sys += "\nA video already exists, so edits are possible."
    msgs = [{"role": "system", "content": sys}] + mem["history"][-8:] + \
           [{"role": "user", "content": message}]
    text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    inputs = tok(text, return_tensors="pt").to("cuda")
    with gpu_lock:
        out = llm.generate(**inputs, max_new_tokens=300, do_sample=True, temperature=0.7)
    raw = tok.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        data = json.loads(m.group(0))
    except Exception:
        data = {"reply": raw.strip() or "Pasensya na, Boss.", "action": "none"}
    mem["history"] += [{"role": "user", "content": message},
                       {"role": "assistant", "content": data.get("reply", "")}]
    if data.get("remember"):
        mem["facts"].append(data["remember"])
    save_mem(mem)
    return data

# ---------------- VIDEO ----------------
def h264(src, dst):
    subprocess.run(["ffmpeg", "-y", "-i", src, "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", dst], check=True, capture_output=True)

def run_generate(jid, scenes):
    try:
        scenes = scenes[:6]
        parts = []
        for n, prompt in enumerate(scenes):
            jobs[jid] = {"status": "working", "progress": f"{n + 1}/{len(scenes)}"}
            with gpu_lock:
                frames = pipe(prompt, num_inference_steps=25, num_frames=24).frames[0]
            raw = f"videos/{jid}_{n}_raw.mp4"
            export_to_video(frames, raw, fps=8)
            part = f"videos/{jid}_{n}.mp4"
            h264(raw, part)
            parts.append(part)
        if len(parts) == 1:
            os.replace(parts[0], f"videos/{jid}.mp4")
        else:
            lst = f"videos/{jid}_list.txt"
            with open(lst, "w") as f:
                for p in parts:
                    f.write(f"file '{os.path.abspath(p)}'\n")
            subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                            "-c", "copy", f"videos/{jid}.mp4"], check=True, capture_output=True)
        jobs[jid] = {"status": "done"}
    except Exception as e:
        jobs[jid] = {"status": "error", "error": str(e)}

def run_edit(jid, src_id, e):
    try:
        src, dst = f"videos/{src_id}.mp4", f"videos/{jid}.mp4"
        op = e.get("op")
        cmd = ["ffmpeg", "-y", "-i", src]
        if op == "trim":
            cmd = ["ffmpeg", "-y", "-ss", str(e.get("start", 0)), "-to", str(e.get("end", 3)), "-i", src]
        elif op == "speed":
            cmd += ["-vf", f"setpts=PTS/{float(e.get('factor', 2.0))}"]
        elif op == "text":
            t = re.sub(r"[^\w \-!?.,]", "", str(e.get("text", "")))
            cmd += ["-vf", "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
                           f"text='{t}':fontcolor=white:fontsize=28:box=1:boxcolor=black@0.5:"
                           "x=(w-text_w)/2:y=h-th-30"]
        elif op == "reverse":
            cmd += ["-vf", "reverse"]
        elif op == "gray":
            cmd += ["-vf", "hue=s=0"]
        elif op == "upscale":
            cmd += ["-vf", "scale=iw*2:ih*2:flags=lanczos"]
        else:
            raise ValueError("Hindi ko kilala ang edit na iyan")
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", dst]
        subprocess.run(cmd, check=True, capture_output=True)
        jobs[jid] = {"status": "done"}
    except Exception as ex:
        jobs[jid] = {"status": "error", "error": str(ex)}

# ---------------- API ----------------
@app.post("/chat")
def chat():
    d = request.json
    return jsonify(think(d["message"], d.get("last_id")))

@app.post("/generate")
def generate():
    jid = uuid.uuid4().hex[:10]
    jobs[jid] = {"status": "working"}
    d = request.json
    scenes = d.get("scenes") or [d["prompt"]]
    threading.Thread(target=run_generate, args=(jid, scenes)).start()
    return jsonify({"id": jid})

@app.post("/edit")
def edit():
    d = request.json
    if not d.get("id"):
        return jsonify({"error": "Wala pang video na ie-edit, Boss."})
    jid = uuid.uuid4().hex[:10]
    jobs[jid] = {"status": "working"}
    threading.Thread(target=run_edit, args=(jid, d["id"], d["edit"])).start()
    return jsonify({"id": jid})

@app.get("/status/<jid>")
def status(jid):
    return jsonify(jobs.get(jid, {"status": "error", "error": "unknown id"}))

@app.get("/video/<jid>")
def video(jid):
    return send_file(f"videos/{jid}.mp4", mimetype="video/mp4")

# ---------------- LIBRENG TUNNEL (walang account) ----------------
threading.Thread(target=lambda: app.run(port=5000), daemon=True).start()
subprocess.run("wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/"
               "cloudflared-linux-amd64 -O cloudflared && chmod +x cloudflared", shell=True)
p = subprocess.Popen(["./cloudflared", "tunnel", "--url", "http://localhost:5000"],
                     stderr=subprocess.PIPE, text=True)
for line in p.stderr:
    m = re.search(r"https://[a-z0-9\-]+\.trycloudflare\.com", line)
    if m:
        print("\n>>> ILAGAY ITO SA APP:", m.group(0), "\n")
        break
while True:
    time.sleep(60)
