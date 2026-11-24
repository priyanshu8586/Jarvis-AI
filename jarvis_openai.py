"""
JARVIS - OpenAI version (Flask web UI), ready for public hosting

Install:  pip install flask requests
Run:      python jarvis_openai.py

Keys are read from environment variables (safer for public use):
    OPENAI_API_KEY   -> your OpenAI key
    NGROK_AUTHTOKEN  -> (optional) to get a public URL via ngrok
If env vars are not set, paste the key in API_KEY below (only for local testing!).
"""

import os
import json
import time
import uuid
import datetime
import xml.etree.ElementTree as ET
import requests
from collections import defaultdict
from flask import Flask, request, jsonify, render_template_string

API_KEY = os.getenv("OPENAI_API_KEY", "PASTE_YOUR_OPENAI_KEY_HERE")
MODEL = os.getenv("MODEL", "gpt-4o-mini")
BASE_URL = os.getenv("BASE_URL", "https://api.openai.com/v1")  # OpenRouter: https://openrouter.ai/api/v1
SYSTEM = ("You are JARVIS, a smart, witty and loyal AI assistant. "
          "Reply in the same language the user uses (Hindi/Hinglish/English). Be concise.")

RATE_LIMIT = 15      # max messages per minute per user (protects your API credit)
MAX_HISTORY = 20     # messages remembered per user

app = Flask(__name__)
sessions = defaultdict(list)   # session_id -> chat history
hits = defaultdict(list)       # ip -> timestamps


PAGE = r"""{% raw %}
<!doctype html>
<html lang="hi"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#04070f">
<title>JARVIS</title>
<style>
  :root{--c:#00e5ff;--bg:#04070f;--panel:#0a1226}
  *{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
  html,body{height:100%}
  body{
    background:
      radial-gradient(circle at 50% 28%, #0b2a44 0%, transparent 55%),
      repeating-linear-gradient(0deg, #ffffff06 0 1px, transparent 1px 38px),
      repeating-linear-gradient(90deg, #ffffff06 0 1px, transparent 1px 38px),
      var(--bg);
    color:#dff6ff;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
    height:100vh;height:100dvh;display:flex;flex-direction:column;overflow:hidden;
    padding-top:env(safe-area-inset-top);
  }
  header{display:flex;justify-content:space-between;align-items:center;padding:10px 14px}
  h1{font-family:ui-monospace,Consolas,monospace;font-size:15px;letter-spacing:5px;color:var(--c);text-shadow:0 0 10px var(--c)}
  #st{font-family:ui-monospace,Consolas,monospace;font-size:11px;color:var(--c);letter-spacing:1px}
  .hbtn{background:none;border:1px solid #00e5ff55;color:var(--c);border-radius:10px;padding:4px 9px;font-size:14px}

  /* ---------- HUD / ARC REACTOR ---------- */
  #hud{--c:#00e5ff;flex:0 0 auto;display:flex;flex-direction:column;align-items:center;padding:2px 0 4px}
  #hud.listen{--c:#00ff9c} #hud.think{--c:#ffc400} #hud.speak{--c:#ff4fd8}
  #reactor{width:min(46vw,200px);height:min(46vw,200px);filter:drop-shadow(0 0 14px var(--c));cursor:pointer;transition:filter .3s}
  #reactor *{transition:stroke .4s, fill .4s}
  .r{transform-box:fill-box;transform-origin:center}
  .r1{animation:spin 14s linear infinite}
  .r2{animation:spin 9s linear infinite reverse}
  .r3{animation:spin 20s linear infinite}
  .tri{animation:spin 6s linear infinite reverse}
  #hud.think .r1{animation-duration:2.2s} #hud.think .r2{animation-duration:1.6s} #hud.think .tri{animation-duration:1.2s}
  #hud.listen #core, #hud.speak #core{animation:pulse .9s ease-in-out infinite}
  #hud.idle #core{animation:pulse 3.2s ease-in-out infinite}
  @keyframes spin{to{transform:rotate(360deg)}}
  @keyframes pulse{0%,100%{opacity:.75;transform:scale(1)}50%{opacity:1;transform:scale(1.18)}}
  #core{transform-box:fill-box;transform-origin:center}
  #hint{font-family:ui-monospace,Consolas,monospace;font-size:12px;color:#8fd8ea;text-align:center;padding:2px 18px;min-height:32px}
  #hint b{color:var(--c)}

  /* ---------- CHAT ---------- */
  #chat{flex:1;min-height:0;overflow-y:auto;padding:8px 12px;display:flex;flex-direction:column;gap:8px;
        -webkit-mask-image:linear-gradient(transparent 0,#000 18px);mask-image:linear-gradient(transparent 0,#000 18px)}
  .m{max-width:88%;padding:8px 12px;border-radius:16px;line-height:1.4;white-space:pre-wrap;font-size:14.5px;word-wrap:break-word}
  .u{align-self:flex-end;background:#10305a;border:1px solid #2a63b0;border-bottom-right-radius:4px}
  .a{align-self:flex-start;background:#0b1830cc;border:1px solid #00e5ff55;border-bottom-left-radius:4px;box-shadow:0 0 12px #00e5ff1a}
  .who{font-family:ui-monospace,Consolas,monospace;font-size:9.5px;letter-spacing:1px;color:var(--c);margin-bottom:2px}

  /* ---------- BOTTOM BAR ---------- */
  footer{display:flex;gap:8px;align-items:center;padding:8px 10px calc(8px + env(safe-area-inset-bottom));background:#060c1ccc;border-top:1px solid #00e5ff33}
  input{flex:1;min-width:0;padding:12px 14px;border-radius:22px;border:1px solid #00e5ff33;background:#0a1226;color:#e6f9ff;font-size:16px;outline:none}
  input:focus{border-color:var(--c)}
  .fb{flex:0 0 auto;width:46px;height:46px;border:none;border-radius:50%;font-size:19px;display:flex;align-items:center;justify-content:center}
  #mic{background:#0a1226;color:#fff;border:1px solid #00e5ff66}
  #mic.on{background:#00ff9c;color:#00180e;border-color:#00ff9c;box-shadow:0 0 16px #00ff9c88;animation:pulseb 1.6s infinite}
  @keyframes pulseb{50%{box-shadow:0 0 26px #00ff9ccc}}
  #send{background:var(--c);color:#001018;font-weight:bold}
</style></head>
<body>
<header>
  <h1>J.A.R.V.I.S</h1>
  <span id="st">● ONLINE</span>
  <button class="hbtn" id="tts" onclick="toggleTTS()" title="Awaaz on/off">🔊</button>
</header>

<div id="hud" class="idle">
  <svg id="reactor" viewBox="0 0 200 200" onclick="stopSpeak()">
    <g class="r r3"><circle cx="100" cy="100" r="94" fill="none" stroke="var(--c)" stroke-width="1" stroke-opacity=".55"/>
      <circle cx="100" cy="100" r="88" fill="none" stroke="var(--c)" stroke-width="7" stroke-dasharray="2 9.1" stroke-opacity=".8"/></g>
    <g class="r r1"><circle cx="100" cy="100" r="76" fill="none" stroke="var(--c)" stroke-width="3" stroke-dasharray="70 22 20 22" stroke-linecap="round"/></g>
    <g class="r r2"><circle cx="100" cy="100" r="64" fill="none" stroke="var(--c)" stroke-width="2" stroke-dasharray="4 6" stroke-opacity=".9"/></g>
    <g class="r tri"><polygon points="100,52 141,124 59,124" fill="none" stroke="var(--c)" stroke-width="2.2" stroke-linejoin="round" stroke-opacity=".9"/></g>
    <circle cx="100" cy="100" r="30" fill="none" stroke="var(--c)" stroke-width="3"/>
    <circle id="core" cx="100" cy="100" r="19" fill="var(--c)" fill-opacity=".85"/>
    <circle cx="100" cy="100" r="9" fill="#ffffff" fill-opacity=".9"/>
  </svg>
  <div id="hint">Mic ON karo, phir bolo <b>"Jadu"</b> ya <b>"Jarvis"</b></div>
</div>

<div id="chat"></div>

<footer>
  <button class="fb" id="mic" onclick="toggleMic()" title="Hands-free mic">🎙</button>
  <input id="q" placeholder="Type karo ya bolo 'Jadu'..." autocomplete="off" onkeydown="if(event.key==='Enter')send()">
  <button class="fb" id="send" onclick="send()">➤</button>
</footer>

<script>
const chat=document.getElementById('chat'), q=document.getElementById('q'), st=document.getElementById('st'),
      hud=document.getElementById('hud'), hint=document.getElementById('hint'), micBtn=document.getElementById('mic'),
      ttsBtn=document.getElementById('tts');

// ---- wake words (yahan se badal sakte ho) ----
const WAKE=['jadu','jadoo','jaadu','jaadoo','jadu','जादू','जादु','jarvis','जार्विस','जारविस','जर्विस'];
const IDLE_HINT='Mic ON karo, phir bolo <b>"Jadu"</b> ya <b>"Jarvis"</b>';
const AWAKE_MS=10000;

let sid=localStorage.getItem('sid');
if(!sid){sid=(crypto.randomUUID?crypto.randomUUID():String(Math.random()).slice(2));localStorage.setItem('sid',sid);}

let micOn=false, speaking=false, busy=false, awakeUntil=0, rec=null, wakeLock=null, ttsOn=true, hindiVoice=null;
const SR=window.SpeechRecognition||window.webkitSpeechRecognition;

function setState(s,text){
  hud.className=s;
  const names={idle:'● ONLINE',listen:'● LISTENING',think:'● THINKING...',speak:'● SPEAKING'};
  st.textContent=names[s]||'● ONLINE';
  hint.innerHTML=text||(micOn?'Sun raha hoon... bolo <b>"Jadu"</b>':IDLE_HINT);
}
function add(who,t){
  const d=document.createElement('div');d.className='m '+(who==='You'?'u':'a');
  const w=document.createElement('div');w.className='who';w.textContent=who.toUpperCase();
  d.append(w,t);chat.append(d);chat.scrollTop=chat.scrollHeight;
}
add('JARVIS','Namaste! Main JARVIS hoon. Mic ON karke "Jadu" bolo, ya type karo.');

// ---------- TEXT TO SPEECH ----------
function pickVoice(){
  const v=(speechSynthesis.getVoices()||[]);
  hindiVoice=v.find(x=>x.lang&&x.lang.toLowerCase().startsWith('hi'))||null;
}
if('speechSynthesis' in window){pickVoice();speechSynthesis.onvoiceschanged=pickVoice;}
function toggleTTS(){ttsOn=!ttsOn;ttsBtn.textContent=ttsOn?'🔊':'🔇';if(!ttsOn)stopSpeak();}
function stopSpeak(){ if('speechSynthesis' in window){speechSynthesis.cancel();} endSpeak(); }
function endSpeak(){
  if(!speaking)return; speaking=false;
  awakeUntil=Date.now()+AWAKE_MS;           // reply ke baad bina "Jadu" bole bhi follow-up le sakta hai
  setState('idle'); if(micOn) startRec();
}
function speak(text){
  if(!ttsOn||!('speechSynthesis' in window)){ if(micOn)startRec(); return; }
  const clean=text.replace(/[*#`_>~]/g,'').replace(/\s+/g,' ').trim();
  if(!clean){return;}
  speechSynthesis.cancel();
  const u=new SpeechSynthesisUtterance(clean);
  u.lang='hi-IN'; if(hindiVoice)u.voice=hindiVoice; u.rate=1.02;
  u.onend=endSpeak; u.onerror=endSpeak;
  speaking=true; setState('speak','JARVIS bol raha hai... (rokne ke liye reactor dabao)');
  try{rec&&rec.stop();}catch(e){}           // apni hi awaaz sunne se bachne ke liye
  speechSynthesis.speak(u);
}

// ---------- SEND ----------
async function send(textFromVoice){
  const t=(typeof textFromVoice==='string'?textFromVoice:q.value).trim();
  if(!t||busy)return; q.value=''; add('You',t);
  busy=true; setState('think','Soch raha hoon...');
  try{
    const r=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({msg:t,sid:sid})});
    const j=await r.json(); add('JARVIS',j.reply); busy=false; speak(j.reply);
  }catch(e){ add('JARVIS','Error: '+e); busy=false; setState('idle'); }
  if(!speaking && !busy){ setState('idle'); }
}

// ---------- HANDS-FREE MIC (wake word) ----------
function findWake(text){
  const low=text.toLowerCase();
  for(const w of WAKE){const i=low.indexOf(w); if(i>=0) return {i:i,len:w.length};}
  return null;
}
function handleFinal(text){
  text=text.trim(); if(!text||busy||speaking)return;
  const w=findWake(text);
  if(w){
    const cmd=text.slice(w.i+w.len).replace(/^[\s,.:!?-]+/,'').trim();
    if(cmd.length>1){ send(cmd); }
    else{ awakeUntil=Date.now()+AWAKE_MS; setState('listen','Ji, boliye... <b>sun raha hoon</b>'); beep(); }
  }else if(Date.now()<awakeUntil){
    send(text);                              // wake-word ke baad ka agla sentence
  }
}
function beep(){
  try{const a=new (window.AudioContext||window.webkitAudioContext)();const o=a.createOscillator(),g=a.createGain();
    o.frequency.value=880;g.gain.value=.06;o.connect(g);g.connect(a.destination);o.start();setTimeout(()=>{o.stop();a.close();},120);}catch(e){}
}
function startRec(){
  if(!SR||!micOn||speaking||busy)return;
  if(rec){try{rec.onend=null;rec.abort();}catch(e){}}
  rec=new SR(); rec.lang='hi-IN'; rec.continuous=true; rec.interimResults=true;
  rec.onresult=e=>{
    for(let i=e.resultIndex;i<e.results.length;i++){
      const res=e.results[i], txt=res[0].transcript;
      if(res.isFinal){ handleFinal(txt); }
      else if(!busy&&!speaking){ hint.textContent='🎙 '+txt; }
    }
  };
  rec.onerror=e=>{
    if(e.error==='not-allowed'||e.error==='service-not-allowed'){
      micOn=false;micBtn.classList.remove('on');setState('idle','Mic ki permission do (Chrome → site settings → Microphone → Allow)');
    }
  };
  rec.onend=()=>{ if(micOn&&!speaking&&!busy) setTimeout(startRec,250); };   // band ho to khud restart
  try{rec.start();}catch(e){}
  if(!speaking&&!busy) setState(Date.now()<awakeUntil?'listen':'idle');
}
async function keepAwake(){
  try{ if('wakeLock' in navigator){wakeLock=await navigator.wakeLock.request('screen');} }catch(e){}
}
document.addEventListener('visibilitychange',()=>{ if(document.visibilityState==='visible'&&micOn){keepAwake();startRec();} });

async function toggleMic(){
  if(!SR){alert('Is browser mein voice support nahi hai. Android par Chrome use karein.');return;}
  if(micOn){
    micOn=false; micBtn.classList.remove('on'); try{rec&&(rec.onend=null,rec.abort());}catch(e){}
    try{wakeLock&&wakeLock.release();}catch(e){}
    setState('idle'); return;
  }
  try{ const s=await navigator.mediaDevices.getUserMedia({audio:true}); s.getTracks().forEach(t=>t.stop()); }
  catch(e){ setState('idle','Mic permission nahi mili. Allow karke dobara dabao.'); return; }
  micOn=true; micBtn.classList.add('on'); keepAwake(); startRec();
  setState('idle','Sun raha hoon... bolo <b>"Jadu"</b>');
}
</script></body></html>
{% endraw %}"""


# =====================  REAL-TIME TOOLS  =====================
# JARVIS ye tools khud call karta hai jab live data chahiye (free APIs, extra key nahi chahiye).
# Optional: environment variable ONLINE=1 (sirf OpenRouter) -> poora web search bhi on ho jata hai.
ONLINE = os.getenv("ONLINE", "0") == "1"
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
UA = {"User-Agent": "Mozilla/5.0 (JARVIS assistant)"}
TOOL_HINT = (" You have live tools: use get_weather for weather, get_news for news/headlines, "
             "get_time for current date/time, wiki_lookup for facts about people/places/topics. "
             "Always use a tool when the question needs current or real-time information, "
             "and summarise the result briefly in the user's language.")

WMO = {0: "clear sky", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "fog",
       51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 61: "light rain", 63: "rain",
       65: "heavy rain", 71: "light snow", 73: "snow", 75: "heavy snow", 80: "rain showers",
       81: "rain showers", 82: "violent showers", 95: "thunderstorm", 96: "thunderstorm with hail",
       99: "thunderstorm with hail"}


def tool_time():
    return datetime.datetime.now(IST).strftime("%A, %d %B %Y, %I:%M %p IST")


def tool_weather(city):
    g = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                     params={"name": city, "count": 1}, headers=UA, timeout=15).json()
    if not g.get("results"):
        return f"'{city}' naam ki jagah nahi mili."
    p = g["results"][0]
    w = requests.get("https://api.open-meteo.com/v1/forecast", headers=UA, timeout=15, params={
        "latitude": p["latitude"], "longitude": p["longitude"], "timezone": "auto", "forecast_days": 3,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
    }).json()
    c, d = w["current"], w["daily"]
    days = [{"date": d["time"][i], "max_c": d["temperature_2m_max"][i], "min_c": d["temperature_2m_min"][i],
             "rain_chance_pct": d["precipitation_probability_max"][i]} for i in range(len(d["time"]))]
    return json.dumps({
        "place": f"{p['name']}, {p.get('admin1', '')}, {p.get('country', '')}",
        "now": {"temp_c": c["temperature_2m"], "feels_like_c": c["apparent_temperature"],
                "humidity_pct": c["relative_humidity_2m"], "wind_kmh": c["wind_speed_10m"],
                "condition": WMO.get(c["weather_code"], "unknown")},
        "forecast": days}, ensure_ascii=False)


def tool_news(query=""):
    if query:
        url = "https://news.google.com/rss/search"
        params = {"q": query, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"}
    else:
        url = "https://news.google.com/rss"
        params = {"hl": "en-IN", "gl": "IN", "ceid": "IN:en"}
    root = ET.fromstring(requests.get(url, params=params, headers=UA, timeout=15).content)
    items = []
    for it in root.iter("item"):
        items.append({"title": it.findtext("title"), "published": it.findtext("pubDate"),
                      "source": it.findtext("source")})
        if len(items) >= 6:
            break
    return json.dumps(items, ensure_ascii=False) if items else "Koi news nahi mili."


def tool_wiki(topic):
    s = requests.get("https://en.wikipedia.org/w/api.php", headers=UA, timeout=15, params={
        "action": "query", "list": "search", "srsearch": topic, "format": "json", "srlimit": 1}).json()
    hit = s.get("query", {}).get("search", [])
    if not hit:
        return "Wikipedia par kuch nahi mila."
    t = hit[0]["title"]
    r = requests.get("https://en.wikipedia.org/api/rest_v1/page/summary/" + requests.utils.quote(t, safe=""),
                     headers=UA, timeout=15).json()
    return json.dumps({"title": t, "summary": r.get("extract", "")[:1500]}, ensure_ascii=False)


TOOL_FUNCS = {
    "get_time": lambda **a: tool_time(),
    "get_weather": lambda **a: tool_weather(a["city"]),
    "get_news": lambda **a: tool_news(a.get("query", "")),
    "wiki_lookup": lambda **a: tool_wiki(a["topic"]),
}

TOOLS = [
    {"type": "function", "function": {
        "name": "get_time", "description": "Current date and time in India (IST).",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_weather", "description": "Live weather and 3-day forecast for a city.",
        "parameters": {"type": "object", "properties": {
            "city": {"type": "string", "description": "City name, e.g. Patna"}}, "required": ["city"]}}},
    {"type": "function", "function": {
        "name": "get_news", "description": "Latest news headlines. Empty query = top India headlines.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Topic to search, e.g. cricket, ISRO, stock market"}}}}},
    {"type": "function", "function": {
        "name": "wiki_lookup", "description": "Factual summary about a person, place or topic from Wikipedia.",
        "parameters": {"type": "object", "properties": {
            "topic": {"type": "string"}}, "required": ["topic"]}}},
]


def run_tool(name, args):
    try:
        return str(TOOL_FUNCS[name](**args))[:3500]
    except Exception as e:
        return f"Tool error: {e}"


def llm_reply(messages):
    """Calls the model; lets it use live tools (up to 4 rounds). Returns the final text."""
    model = MODEL + ":online" if (ONLINE and "openrouter" in BASE_URL and not MODEL.endswith(":online")) else MODEL
    use_tools = True
    for _ in range(5):
        body = {"model": model, "messages": messages}
        if use_tools:
            body["tools"] = TOOLS
        r = requests.post(f"{BASE_URL}/chat/completions",
                          headers={"Authorization": f"Bearer {API_KEY}"}, json=body, timeout=60)
        j = r.json()
        if "choices" not in j and use_tools:      # kuch models tools support nahi karte -> bina tools ke try
            use_tools = False
            continue
        if "choices" not in j:
            raise Exception((j.get("error") or {}).get("message") or "API call failed")
        m = j["choices"][0]["message"]
        calls = m.get("tool_calls")
        if not calls:
            return m["content"]
        messages.append(m)
        for c in calls:
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except Exception:
                args = {}
            messages.append({"role": "tool", "tool_call_id": c["id"],
                             "content": run_tool(c["function"]["name"], args)})
    return "Maaf kijiye, jawab nahi bana paaya. Dobara try karein."


def too_many_requests(ip):
    now = time.time()
    hits[ip] = [t for t in hits[ip] if now - t < 60]
    if len(hits[ip]) >= RATE_LIMIT:
        return True
    hits[ip].append(now)
    return False


@app.route("/")
def home():
    return render_template_string(PAGE)


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json() or {}
    msg = (data.get("msg") or "")[:2000]
    sid = (data.get("sid") or str(uuid.uuid4()))[:64]
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    if not msg:
        return jsonify(reply="Kuch likhiye to sahi 🙂")
    if too_many_requests(ip):
        return jsonify(reply="Thoda ruko! Bahut tez messages bhej rahe ho. 1 minute baad try karo.")

    history = sessions[sid]
    history.append({"role": "user", "content": msg})
    messages = [{"role": "system", "content": SYSTEM + TOOL_HINT}] + history[-MAX_HISTORY:]

    try:
        reply = llm_reply(messages)
        history.append({"role": "assistant", "content": reply})
    except Exception as e:
        history.pop()
        reply = f"Error: {e}"
    return jsonify(reply=reply)


def start_ngrok(port):
    """Optional: creates a public URL when NGROK_AUTHTOKEN is set."""
    token = os.getenv("NGROK_AUTHTOKEN")
    if not token:
        return
    try:
        from pyngrok import ngrok, conf
        conf.get_default().auth_token = token
        tunnel = ngrok.connect(port)
        print("\n PUBLIC URL ->", tunnel.public_url, "\n")
    except Exception as e:
        print("ngrok start nahi hua:", e)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    start_ngrok(port)
    app.run(host="0.0.0.0", port=port)
