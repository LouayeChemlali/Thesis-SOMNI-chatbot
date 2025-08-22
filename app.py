from flask import Flask, request, jsonify
from flask_cors import CORS
import os, datetime, random, copy

app = Flask(__name__)
CORS(app)

def get_next_log_filename(prefix="chat_log", extension=".txt"):
    # Bepaalt de volgende beschikbare logbestandsnaam
    i = 1
    while True:
        filename = f"{prefix}{i}{extension}"
        if not os.path.exists(filename):
            return filename
        i += 1

LOG_FILE = get_next_log_filename()

def ts():
    # Geeft timestamp (hiermee kan ik eventueel beargumenteren hoe lang een sessie duurt)
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log_header(variant_label: str, strategy: str | None = None):
    # Logt de start van een nieuwe sessie met variant en strategie (alleen bij tweede)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write("\n" + "=" * 64 + "\n")
        f.write(f"[{ts()}] START NIEUWE SESSIE\n")
        f.write(f"[{ts()}] Variant: {variant_label}\n")
        if strategy:
            f.write(f"[{ts()}] Strategie: {strategy}\n")
        f.write("=" * 64 + "\n")


def log_chat(role: str, content: str):
    # Logt een chatbericht van de chatbot of gebruiker
    if isinstance(content, list):
        content = ", ".join(map(str, content))
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts()}] {role}: {content}\n")

def log_end(answers: dict):
    # Logt het einde van de sessie met antwoorden
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts()}] Einde sessie\n")
        f.write(f"[{ts()}] Antwoorden: {answers}\n")

# Categoriserings factoren
QUALITY_CATS = {
    "stress": ["stress", "zorgen", "druk", "pieker"],
    "pijn": ["pijn", "hoofdpijn", "rug", "kramp"],
    "omgeving": ["lawaai", "licht", "temperatuur", "te warm", "te koud", "vocht", "partner", "kind"],
    "apparaat": ["telefoon", "tv", "tablet", "laptop", "scherm"],
}

def categorize(text: str) -> str | None:
    # Categoriseert de tekst
    if not text:
        return None
    t = text.lower()
    for cat, kws in QUALITY_CATS.items():
        if any(k in t for k in kws):
            return cat
    return "overig"

# Scripts 
WAKEUP_STANDARD = [
  {"id":"wu_intro","bot":"We kijken kort terug op de nacht. Klaar om te starten","type":"ack","next":"wu_refreshed"},
  {"id":"wu_refreshed","bot":"Hoe uitgeslapen voel je je, 0 tot 10","type":"likert11","labels":[str(i) for i in range(11)],"save_as":"refreshed","next":"wu_important"},
  {"id":"wu_important","bot":"Was er iets dat je slaapkwaliteit heeft beïnvloed, zo ja wat, overslaan mag","type":"text_optional","save_as":"quality_factor","next":"wu_awake10"},
  {"id":"wu_awake10","bot":"Was je langer dan 10 minuten wakker tijdens de nacht","type":"select","options":["Ja","Nee"],"save_as":"awake_10min","next":"wu_awake_gate"},
  {"id":"wu_awake_gate","bot":"","type":"gate","if":"awake_10min=='Ja'","then":"wu_awake_what","else":"wu_sleep_earlier"},
  {"id":"wu_awake_what","bot":"Wat deed je in die periode, meerdere keuzes mogelijk","type":"multiselect","options":["In bed gebleven","Smart device gebruikt","Naar toilet","Gelezen","Snack genomen","Anders"],"save_as":"awake_activities","next":"wu_sleep_earlier"},
  {"id":"wu_sleep_earlier","bot":"Werd je gisteravond door iets tegengehouden om eerder te gaan slapen","type":"select","options":["Ja","Nee"],"save_as":"prevent_earlier","next":"wu_sleep_earlier_gate"},
  {"id":"wu_sleep_earlier_gate","bot":"","type":"gate","if":"prevent_earlier=='Ja'","then":"wu_sleep_earlier_why","else":"wu_external"},
  {"id":"wu_sleep_earlier_why","bot":"Wat hield je tegen om eerder te slapen","type":"text","save_as":"prevent_reason","next":"wu_external"},
  {"id":"wu_external","bot":"Waren er externe factoren die je slaap belemmerden, meerdere keuzes mogelijk","type":"multiselect","options":["Niets","Comfort","Lawaai","Licht","Temperatuur","Vochtigheid","Partner","Kinderen","Anders"],"save_as":"external_factors","next":"wu_wakeup"},
  {"id":"wu_wakeup","bot":"Hoe werd je wakker","type":"select","options":["Met alarm","Natuurlijk","Anders"],"save_as":"how_woke","next":"wu_blue_light"},
  {"id":"wu_blue_light","bot":"Hoeveel minuten voor bedtijd stopte je met fel schermlicht zoals telefoon of TV","type":"select","options":["<15 minuten","15 tot 30 minuten","30 tot 45 minuten",">45 minuten"],"save_as":"blue_light_cutoff","next":"done"}
]

# Basis script voor tweede variant
WAKEUP_RESEARCH_BASE = [
  {"id":"wu_intro","bot":"Een korte terugblik op de nacht helpt patronen herkennen. Klaar om te starten","type":"ack","next":"wu_refreshed"},
  {"id":"wu_refreshed","bot":"Hoe uitgeslapen voel je je, 0 tot 10, dit geeft een snelle kwaliteitsindicatie","type":"likert11","labels":[str(i) for i in range(11)],"save_as":"refreshed","next":"wu_important"},
  {"id":"wu_important","bot":"Was er iets dat je slaapkwaliteit beïnvloedde, vrije toelichting mag en overslaan kan","type":"text_optional","save_as":"quality_factor","next":"wu_awake10"},
  {"id":"wu_awake10","bot":"Ben je langer dan 10 minuten wakker geweest, dit zegt iets over ononderbroken slapen","type":"select","options":["Ja","Nee"],"save_as":"awake_10min","next":"wu_awake_gate"},
  {"id":"wu_awake_gate","bot":"","type":"gate","if":"awake_10min=='Ja'","then":"wu_awake_what","else":"wu_sleep_earlier"},
  {"id":"wu_awake_what","bot":"Wat deed je in die periode, meerdere keuzes mogelijk, dit geeft context bij onderbrekingen","type":"multiselect","options":["In bed gebleven","Smart device gebruikt","Naar toilet","Gelezen","Snack genomen","Anders"],"save_as":"awake_activities","next":"wu_sleep_earlier"},
  {"id":"wu_sleep_earlier","bot":"Werd je gisteravond door iets tegengehouden om eerder te gaan slapen, timing beïnvloedt vaak de totale slaapduur","type":"select","options":["Ja","Nee"],"save_as":"prevent_earlier","next":"wu_sleep_earlier_gate"},
  {"id":"wu_sleep_earlier_gate","bot":"","type":"gate","if":"prevent_earlier=='Ja'","then":"wu_sleep_earlier_why","else":"wu_external"},
  {"id":"wu_sleep_earlier_why","bot":"Wat hield je tegen om eerder te slapen, een korte zin is genoeg","type":"text","save_as":"prevent_reason","next":"wu_external"},
  {"id":"wu_external","bot":"Waren er externe factoren die je slaap belemmerden, meerdere keuzes mogelijk, dit geeft omgevingscontext","type":"multiselect","options":["Niets","Comfort","Lawaai","Licht","Temperatuur","Vochtigheid","Partner","Kinderen","Anders"],"save_as":"external_factors","next":"wu_wakeup"},
  {"id":"wu_wakeup","bot":"Hoe werd je wakker, dit onderscheidt natuurlijke van gestuurde ontwaking","type":"select","options":["Met alarm","Natuurlijk","Anders"],"save_as":"how_woke","next":"wu_blue_light"},
  {"id":"wu_blue_light","bot":"Wanneer stopte je met fel schermlicht voor bedtijd, dit kan slaapdruk en melatonine beïnvloeden","type":"select","options":["<15 minuten","15 tot 30 minuten","30 tot 45 minuten",">45 minuten"],"save_as":"blue_light_cutoff","next":"done"}
]

# Namen chatbot
VARIANT_LABELS = {
    "standard": "eerste variant",
    "research": "tweede variant"
}

# Beschikbare strategieën voor de tweede variant
STRATEGIES = ["empathisch", "motiverend", "informatief", "social proof", "enjoyment"]

# Prescripts voor de strategieën
STRATEGY_PHRASES = {
    "empathisch": {
        "wu_refreshed": " Dat klinkt als waardevolle informatie, of het nu een goede of minder goede nacht was.",
        "wu_important": " Ik begrijp dat sommige nachten door van alles beïnvloed kunnen worden, fijn dat je dit wilt delen.",
        "wu_awake10": " Het is normaal dat nachten soms onderbroken zijn, en het is goed dat je dit aangeeft.",
        "wu_awake_what": " Wat je ook hebt gedaan in die tijd, het helpt om het hier vast te leggen.",
        "wu_sleep_earlier": " Soms houden kleine dingen ons wakker, goed dat je hier even bij stilstaat.",
        "wu_external": " Omgevingsfactoren kunnen echt verschil maken, fijn dat je ze benoemt.",
        "wu_wakeup": " Het moment van wakker worden kan veel zeggen over hoe je de dag start.",
        "wu_blue_light": " Ik weet dat het niet altijd makkelijk is om schermen eerder uit te zetten, maar het kan helpen."
    },
    "motiverend": {
        "wu_refreshed": " Elke keer dat je dit invult, werk je actief aan je slaapgewoonten.",
        "wu_important": " Door dit nu te benoemen, zet je alweer een stap naar meer grip op je nachten.",
        "wu_awake10": " Deze informatie helpt om kleine verbeterpunten te vinden voor je rust.",
        "wu_awake_what": " Alles wat je invult brengt ons dichter bij een beter slaapritme.",
        "wu_sleep_earlier": " Door te zien wat je wakker houdt, kunnen we makkelijker oplossingen vinden.",
        "wu_external": " Elke factor die je aangeeft helpt om je slaapomgeving te verbeteren.",
        "wu_wakeup": " Dit inzicht kan je helpen om je ochtenden energieker te beginnen.",
        "wu_blue_light": " Zelfs kleine veranderingen, zoals schermen iets eerder uit, kunnen grote winst geven."
    },
    "informatief": {
        "wu_refreshed": " Deze score geeft snel inzicht in je ervaren slaapkwaliteit, een belangrijke graadmeter in slaaptherapie.",
        "wu_important": " Door oorzaken te noteren, wordt duidelijk welke factoren je slaap beïnvloeden.",
        "wu_awake10": " Langer dan tien minuten wakker liggen kan je diepe NREM-slaap onderbreken.",
        "wu_awake_what": " Activiteiten tijdens nachtelijk wakker liggen geven aanwijzingen voor slaappatronen.",
        "wu_sleep_earlier": " Bedtijd beïnvloedt vaak je totale slaapduur en slaapdruk.",
        "wu_external": " Licht, geluid of temperatuur kunnen je slaapkwaliteit direct verlagen.",
        "wu_wakeup": " Hoe je wakker wordt kan invloed hebben op je alertheid en stemming overdag.",
        "wu_blue_light": " Fel schermlicht voor het slapengaan kan de aanmaak van melatonine vertragen."
    },
    "social proof": {
        "wu_refreshed": " Veel mensen vinden het nuttig om hun slaap op deze manier dagelijks te scoren.",
        "wu_important": " Anderen merken dat het bijhouden van oorzaken helpt om sneller patronen te herkennen.",
        "wu_awake10": " Het komt vaak voor dat mensen soms langer wakker liggen in de nacht.",
        "wu_awake_what": " De meeste deelnemers kiezen hier meerdere opties tegelijk.",
        "wu_sleep_earlier": " Veel mensen merken dat eerder naar bed gaan hun nachtrust verbetert.",
        "wu_external": " Geluid, licht en temperatuur worden vaak genoemd als belangrijke factoren.",
        "wu_wakeup": " Zonder alarm wakker worden voelt voor veel mensen natuurlijker en rustiger.",
        "wu_blue_light": " Veel deelnemers zeggen dat eerder stoppen met schermen hun inslapen versnelt."
    },
    "enjoyment": {
        "wu_refreshed": " Snel even scoren en je bent klaar voor de dag.",
        "wu_important": " Een korte notitie is genoeg om dit compleet te maken.",
        "wu_awake10": " Even invullen en we gaan weer door.",
        "wu_awake_what": " Klik gewoon alles aan wat klopt voor vannacht.",
        "wu_sleep_earlier": " We houden het simpel en haalbaar vandaag.",
        "wu_external": " Zo houden we een duidelijk en overzichtelijk beeld.",
        "wu_wakeup": " Handig om te weten voor je ochtendroutine.",
        "wu_blue_light": " Een vast ritueel zonder schermen kan je dag mooi afsluiten."
    }
}

def build_strategy_scripts():
    # Bouwt de scripts voor elke strategie door de basis te kopiëren en extra zinnen toe te voegen
    scripts = {}
    for strat in STRATEGIES:
        s = copy.deepcopy(WAKEUP_RESEARCH_BASE)
        phrases = STRATEGY_PHRASES.get(strat, {})
        for step in s:
            extra = phrases.get(step["id"])
            if extra:
                base = step['bot'].rstrip()
                # Voeg punt toe als laatste teken geen punt, vraagteken of uitroepteken is
                if base and base[-1] not in ".!?":
                    base += "."
                step["bot"] = f"{base} {extra.strip()}"
        scripts[strat] = s
    return scripts

STRATEGY_SCRIPTS = build_strategy_scripts()


def normalize_variant(value) -> str:
    """
    Normaliseert client-invoer naar 'standard' of 'research'.
    Herkent diverse schrijfwijzen van de tweede variant.
    """
    if value is None:
        return "standard"
    v = str(value).strip().lower()
    research_aliases = {
        "research", "tweede", "tweede variant", "variant 2", "v2",
        "second", "second variant", "2", "two", "research-informed",
        "research informed"
    }
    if v in research_aliases:
        return "research"
    if v in {"true", "yes", "ja"}:
        return "research"
    return "standard"

def resolve_variant_label(client_variant_key: str) -> str:
    return VARIANT_LABELS.get(client_variant_key, "eerste variant")

def pick_or_reuse_strategy(answers: dict) -> str:
    #strategie selectie
    strat = answers.get("_strategy")
    if strat in STRATEGIES:
        return strat
    strat = random.choice(STRATEGIES)
    answers["_strategy"] = strat
    return strat

def step_by_id(script, step_id):
    # Zoekt een stap in het script op basis van ID
    for s in script:
        if s["id"] == step_id:
            return s
    return None

def next_non_gate(script, step_id, answers):
    # Bepaalt de volgende stap na een gegeven stap ID, overslaat gates
    curr = step_by_id(script, step_id)
    if not curr:
        return None, "done"
    nxt_id = curr.get("next", "done")
    while True:
        if nxt_id == "done":
            return None, "done"
        nxt = step_by_id(script, nxt_id)
        if not nxt:
            return None, "done"
        if nxt.get("type") != "gate":
            return nxt, nxt_id
        cond = nxt.get("if", "")
        then_id = nxt.get("then", "done")
        else_id = nxt.get("else", "done")
        try:
            if "==" in cond:
                key, val = cond.split("==")
                ok = answers.get(key.strip()) == val.strip().strip("'").strip('"')
                nxt_id = then_id if ok else else_id
            elif "!=" in cond:
                key, val = cond.split("!=")
                ok = answers.get(key.strip()) != val.strip().strip("'").strip('"')
                nxt_id = then_id if ok else else_id
            else:
                nxt_id = else_id
        except:
            nxt_id = else_id

def ack_for_prev(prev_step: dict, user_input) -> str:
    # Geeft een bevestigingstekst voor de vorige stap, afhankelijk van de inhoud
    if not prev_step:
        return ""
    if prev_step.get("save_as") == "refreshed":
        try:
            score = int(str(user_input))
        except:
            return "Dank je, genoteerd."
        if score <= 3:
            return f"Dank je. Je gaf {score} op 10, dat klinkt als een zware nacht."
        if score <= 6:
            return f"Dank je. Je gaf {score} op 10, gemiddeld dus."
        return f"Dank je. Je gaf {score} op 10, dat klinkt redelijk tot goed."
    if prev_step.get("save_as") == "quality_factor":
        if not user_input:
            return "Prima, ik noteer dat er niets toe te lichten is."
        cat = categorize(str(user_input))
        if cat == "stress":
            return "Dank je voor je toelichting, ik noteer stress als factor."
        if cat == "pijn":
            return "Dank je. Ik noteer dat pijn mogelijk een rol speelde."
        if cat == "omgeving":
            return "Helder. Ik noteer een omgevingsfactor."
        if cat == "apparaat":
            return "Dank je. Ik noteer schermgebruik als mogelijke factor."
        return "Dank je voor je toelichting, ik noteer het."
    if prev_step.get("save_as") == "prevent_reason":
        return "Helder, dank je. Ik noteer het kort."
    if prev_step.get("type") in ("select", "multiselect"):
        return "Dank je, genoteerd."
    return "Dank je."

def closing_for_variant(variant_key: str, answers: dict) -> str:
    # Sluitingsbericht afhankelijk van variant
    if variant_key != "research":
        return "Dank je wel, dit rondt de wake-up intake af"
    score = answers.get("refreshed")
    praise = ""
    try:
        s = int(str(score)) if score is not None else None
        if s is not None and s >= 7:
            praise = " Mooi begin van de dag."
        elif s is not None and s <= 3:
            praise = " Knap dat je dit toch even hebt ingevuld."
    except:
        pass
    nudge = " Wil je voor later vandaag één kleine stap kiezen die helpt, bijvoorbeeld schermen 30 min eerder uit of een rustige avondstart."
    return f"Dank je wel, dit rondt de wake-up intake af.{praise}{nudge}"

@app.route("/api/somni-chat", methods=["POST"])
# Endpoint voor de Somni chatbot
def somni_chat():
    data = request.get_json(force=True)

    # Normaliseer variant
    client_variant_key = normalize_variant(data.get("variant", "standard"))

    state_id = data.get("state_id")
    user_input = data.get("user_input")
    answers = data.get("answers", {}) or {}

    variant_label = resolve_variant_label(client_variant_key)

    # Sessie start
    if state_id is None:
        if client_variant_key == "research":
            strategy = answers.get("_strategy") or pick_or_reuse_strategy(answers)
            script = STRATEGY_SCRIPTS.get(strategy, WAKEUP_RESEARCH_BASE)
            log_header(variant_label, strategy)
        else:
            script = WAKEUP_STANDARD
            log_header(variant_label, strategy=None)

        first = script[0]
        log_chat("SOMNI", first["bot"])
        return jsonify({
            "reply": first["bot"],
            "next_state_id": first["id"],
            "input_type": first.get("type"),
            "options": first.get("options"),
            "labels": first.get("labels"),
            "is_optional": first.get("type") == "text_optional",
            "done": False,
            "answers": answers,
            "_debug": {
                "variant_key": client_variant_key,
                "variant_label": variant_label,
                "strategy": answers.get("_strategy") if client_variant_key == "research" else None
            }
        })

    # Vervolgstap in dezelfde sessie
    if client_variant_key == "research":
        strategy = answers.get("_strategy") or pick_or_reuse_strategy(answers)
        script = STRATEGY_SCRIPTS.get(strategy, WAKEUP_RESEARCH_BASE)
    else:
        script = WAKEUP_STANDARD

    prev = step_by_id(script, state_id)

    # Log user input
    if user_input is None or user_input == "":
        user_display = "(overgeslagen)"
    else:
        user_display = ", ".join(user_input) if isinstance(user_input, list) else str(user_input)
    log_chat("user", user_display)

    # Sla op indien nodig
    if prev and prev.get("save_as"):
        answers[prev["save_as"]] = user_input

    # Bepaal volgende stap
    next_step, next_id = next_non_gate(script, prev.get("id"), answers)

    if next_id == "done" or not next_step:
        closing = closing_for_variant(client_variant_key, answers)
        log_chat("SOMNI", closing)
        log_end(answers)
        return jsonify({
            "reply": closing,
            "next_state_id": "done",
            "input_type": None,
            "options": None,
            "labels": None,
            "is_optional": False,
            "done": True,
            "answers": answers,
            "_debug": {
                "variant_key": client_variant_key,
                "variant_label": variant_label,
                "strategy": answers.get("_strategy") if client_variant_key == "research" else None
            }
        })

    # Log de volgende stap
    ack = ack_for_prev(prev, user_input)
    reply = f"{ack} {next_step['bot']}".strip()
    log_chat("SOMNI", reply)

    return jsonify({
        "reply": reply,
        "next_state_id": next_id,
        "input_type": next_step.get("type"),
        "options": next_step.get("options"),
        "labels": next_step.get("labels"),
        "is_optional": next_step.get("type") == "text_optional",
        "done": False,
        "answers": answers,
        "_debug": {
            "variant_key": client_variant_key,
            "variant_label": variant_label,
            "strategy": answers.get("_strategy") if client_variant_key == "research" else None
        }
    })

@app.route("/api/wakeup-summary", methods=["POST"])
def wakeup_summary():
    # Endpoint voor samenvatting van de wake-up check-in
    data = request.get_json(force=True)
    answers = data.get("answers", {}) or {}

    safe = {k: answers[k] for k in [
        "refreshed","awake_10min","awake_activities","prevent_earlier",
        "external_factors","how_woke","blue_light_cutoff"
    ] if k in answers}

    if "quality_factor" in answers:
        safe["quality_factor_present"] = bool(answers["quality_factor"])
        safe["quality_factor_category"] = categorize(answers["quality_factor"])
    if "prevent_reason" in answers:
        safe["prevent_reason_present"] = bool(answers["prevent_reason"])

    # Variantlabel voor analyses
    variant_key = normalize_variant(data.get("variant", "standard"))
    safe["_variant_label"] = resolve_variant_label(variant_key)
    if "_strategy" in answers:
        safe["_strategy"] = answers["_strategy"]

    # Korte samenvatting
    summary = f"Check-in genoteerd. Uitgeslapen: {safe.get('refreshed','nvt')}/10."
    if safe.get("awake_10min") == "Ja":
        acts = safe.get("awake_activities") or []
        if isinstance(acts, list) and acts:
            summary += f" Wakker >10 min; activiteiten: {', '.join(acts)}."
        else:
            summary += " Wakker >10 min."
    ext = safe.get("external_factors")
    if isinstance(ext, list):
        named = [e for e in ext if e and e.lower() != "niets"]
        if named:
            summary += f" Extern: {', '.join(named)}."
    if safe.get("how_woke"):
        summary += f" Wakker geworden: {safe['how_woke'].lower()}."
    if safe.get("blue_light_cutoff"):
        summary += f" Schermlicht stop: {safe['blue_light_cutoff'].lower()}."

    return jsonify({"summary": summary.strip(), "safe_payload": safe})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, threaded=True, port=port)
