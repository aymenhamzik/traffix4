"""
Turns decision-log entries into plain sentences in English, French or Arabic, without a
language model. Each reason code has a template per language, filled from the entry's
details with readable names (junctions, streets, "bus 3 of line L1 east", clock times).
Deterministic: it never states anything the log does not contain.
Used by the analyst page, the explainer (Synapse), the copilot and the persona pages.
"""
from datetime import timedelta

from .decision_log import REASON_CODES

LANGS = ("en", "fr", "ar")


def _num(x, lang, digits=0):
    s = f"{x:.{digits}f}"
    return s.replace(".", ",") if lang == "fr" else s


def pct(x, lang="en"):
    return f"{x * 100:.0f}%" if isinstance(x, (int, float)) else "?"


def sec(x, lang="en"):
    if not isinstance(x, (int, float)):
        return {"en": "an unknown time", "fr": "une durée inconnue", "ar": "مدة غير معروفة"}[lang]
    if x < 90:
        return {"en": f"{x:.0f} s", "fr": f"{x:.0f} s", "ar": f"{x:.0f} ثانية"}[lang]
    m = _num(x / 60, lang, 1).rstrip("0").rstrip(".").rstrip(",")
    return {"en": f"{m} min", "fr": f"{m} min", "ar": f"{m} دقيقة"}[lang]


def cap(s):
    return s[:1].upper() + s[1:]


# ------------------------------------------------------------------ templates
# Placeholders are filled from Narrator._values(); {J} junction, {V} vehicle, etc.
T = {
    "MAX_PRESSURE_SWITCH": {
        "en": "{J} switched the green to the busier direction (pressure {pold} → {pnew}).",
        "fr": "{J} a donné le vert à la direction la plus chargée (pression {pold} → {pnew}).",
        "ar": "حوّل {J} الضوء الأخضر إلى الاتجاه الأكثر ازدحامًا (الضغط من {pold} إلى {pnew})."},
    "CORRIDOR_PLATOON": {
        "en": "{J} switched the green to let a group of cars arriving from the neighbouring junction through (corridor coordination).",
        "fr": "{J} a donné le vert pour laisser passer un peloton venant du carrefour voisin (coordination de corridor).",
        "ar": "حوّل {J} الضوء الأخضر لتمرير مجموعة سيارات قادمة من التقاطع المجاور (تنسيق الممر)."},
    "PREDICTIVE_SWITCH": {
        "en": "{J} switched early: its 60-second forecast predicted less waiting ({ps} vs {pk} vehicle-seconds).",
        "fr": "{J} a changé de phase en avance : sa prévision sur 60 s annonçait moins d'attente ({ps} contre {pk} véhicule-secondes).",
        "ar": "غيّر {J} الطور مبكرًا: توقّعه لمدة 60 ثانية أظهر انتظارًا أقل ({ps} مقابل {pk} مركبة-ثانية)."},
    "RL_POLICY_SWITCH": {
        "en": "{J} switched the green on the learned policy's advice{guard}.",
        "fr": "{J} a changé le vert sur conseil de la politique apprise{guard}.",
        "ar": "حوّل {J} الضوء الأخضر بناءً على السياسة المتعلَّمة{guard}."},
    "ACTUATED_GAP_OUT": {
        "en": "{J}, in backup mode, ended a green after no more cars arrived ({green} of green).",
        "fr": "{J}, en mode secours, a terminé un vert faute de nouveaux véhicules ({green} de vert).",
        "ar": "أنهى {J} في وضع الطوارئ ضوءًا أخضر بعد توقف وصول السيارات ({green} من الأخضر)."},
    "ACTUATED_MAX_OUT": {
        "en": "{J}, in backup mode, ended a green that reached its maximum length.",
        "fr": "{J}, en mode secours, a terminé un vert arrivé à sa durée maximale.",
        "ar": "أنهى {J} في وضع الطوارئ ضوءًا أخضر بلغ مدته القصوى."},
    "FIXED_CYCLE": {
        "en": "{J}, on its fixed backup plan, moved to the next phase.",
        "fr": "{J}, en plan fixe de secours, est passé à la phase suivante.",
        "ar": "انتقل {J} إلى الطور التالي وفق خطته الثابتة الاحتياطية."},
    "MODE_MAX_PRESSURE": {
        "en": "{J} is back to normal smart control: all its sensors are working.",
        "fr": "{J} revient au contrôle intelligent normal : tous ses capteurs fonctionnent.",
        "ar": "عاد {J} إلى التحكم الذكي العادي: جميع كواشفه تعمل."},
    "MODE_ACTUATED": {
        "en": "{J} switched to a backup mode because sensors on its exit roads stopped working.",
        "fr": "{J} est passé en mode secours car les capteurs de ses sorties ne fonctionnent plus.",
        "ar": "انتقل {J} إلى وضع احتياطي لأن كواشف طرق الخروج توقفت عن العمل."},
    "MODE_FIXED": {
        "en": "{J} switched to its fixed backup plan because sensors on its approaches stopped working.",
        "fr": "{J} est passé en plan fixe de secours car les capteurs de ses entrées ne fonctionnent plus.",
        "ar": "انتقل {J} إلى خطته الثابتة الاحتياطية لأن كواشف المداخل توقفت عن العمل."},
    "EMERGENCY_REQUEST": {
        "en": "{Vc} asked {J} for a green light, arriving in about {eta}.",
        "fr": "{Vc} a demandé le vert à {J}, arrivée dans environ {eta}.",
        "ar": "طلبت {V} الضوء الأخضر من {J}، والوصول خلال حوالي {eta}."},
    "EMERGENCY_PREPARE": {
        "en": "The supermaster warned {J} that {V} will arrive in about {eta}.",
        "fr": "Le superviseur a prévenu {J} que {V} arrivera dans environ {eta}.",
        "ar": "نبّه المشرف العام {J} بأن {V} ستصل خلال حوالي {eta}."},
    "EMERGENCY_GRANTED_SWITCH": {
        "en": "{J} turned the light green for {V}; the road ahead had room.",
        "fr": "{J} a mis le feu au vert pour {V} ; la route en aval était libre.",
        "ar": "أعطى {J} الضوء الأخضر لـ {V}؛ وكان الطريق أمامها متاحًا."},
    "EMERGENCY_GRANTED_HOLD": {
        "en": "{J} kept the light green for {V}, which was already on a green approach.",
        "fr": "{J} a maintenu le vert pour {V}, déjà sur une approche au vert.",
        "ar": "أبقى {J} الضوء أخضر لـ {V} التي كانت أصلًا في اتجاه أخضر."},
    "EMERGENCY_DENIED_EXIT_FULL": {
        "en": "{J} could not give {V} a green: the road ahead ({exit}) was {occ} full, so a green would only have pushed it into the queue.",
        "fr": "{J} n'a pas pu donner le vert à {V} : la route en aval ({exit}) était pleine à {occ}, un vert l'aurait seulement poussée dans la file.",
        "ar": "لم يستطع {J} منح الضوء الأخضر لـ {V}: الطريق أمامها ({exit}) ممتلئ بنسبة {occ}، فكان الأخضر سيدفعها إلى الطابور فقط."},
    "EMERGENCY_DENIED_OTHER_EMERGENCY": {
        "en": "{J} served {served} first, so {V} had to wait.",
        "fr": "{J} a servi {served} en premier, {V} a donc dû attendre.",
        "ar": "خدم {J} {served} أولًا، فاضطرت {V} إلى الانتظار."},
    "RECOVERY_STARTED": {
        "en": "{Vc} passed {J}; normal control resumed ({qnow} cars waiting, {qbefore} before the emergency).",
        "fr": "{Vc} a passé {J} ; le contrôle normal a repris ({qnow} voitures en attente, {qbefore} avant l'urgence).",
        "ar": "عبرت {V} {J}؛ واستُؤنف التحكم العادي ({qnow} سيارة تنتظر، مقابل {qbefore} قبل الطوارئ)."},
    "RECOVERED": {
        "en": "Traffic at {J} was back to normal {rec} after the emergency vehicle passed.",
        "fr": "La circulation à {J} est revenue à la normale {rec} après le passage du véhicule d'urgence.",
        "ar": "عادت الحركة عند {J} إلى طبيعتها بعد {rec} من مرور مركبة الطوارئ."},
    "RECOVERY_INCOMPLETE": {
        "en": "Traffic at {J} had not recovered within 10 minutes of the emergency.",
        "fr": "La circulation à {J} ne s'était pas rétablie 10 minutes après l'urgence.",
        "ar": "لم تتعافَ الحركة عند {J} خلال 10 دقائق من حالة الطوارئ."},
    "TRANSIT_REQUEST_LATE_BUS": {
        "en": "{Vc} was running late ({gap} since the previous bus, scheduled every {head}), so bus priority was requested at {J}.",
        "fr": "{Vc} était en retard ({gap} depuis le bus précédent, prévu toutes les {head}) : priorité bus demandée à {J}.",
        "ar": "كانت {V} متأخرة ({gap} منذ الحافلة السابقة، والموعد كل {head})، فطُلبت أولوية الحافلات عند {J}."},
    "BUS_NOT_LATE": {
        "en": "{Vc} reached {J} on time ({gap} after the previous bus, scheduled every {head}), so no priority was needed.",
        "fr": "{Vc} est arrivé à {J} à l'heure ({gap} après le bus précédent, prévu toutes les {head}) : pas de priorité nécessaire.",
        "ar": "وصلت {V} إلى {J} في موعدها ({gap} بعد الحافلة السابقة، والموعد كل {head})، فلم تكن هناك حاجة للأولوية."},
    "BUS_NO_REFERENCE": {
        "en": "{Vc} reached {J}, but no earlier bus of its line had passed yet, so its delay could not be judged: no priority requested.",
        "fr": "{Vc} est arrivé à {J}, mais aucun bus précédent de sa ligne n'était passé : retard impossible à évaluer, pas de priorité demandée.",
        "ar": "وصلت {V} إلى {J}، لكن لم تمرّ حافلة سابقة على خطها بعد، فتعذّر تقييم تأخرها: لم تُطلب أولوية."},
    "TRANSIT_GRANTED_EXTEND": {
        "en": "{J} held its green a little longer for late {V}.",
        "fr": "{J} a prolongé son vert pour {V}, en retard.",
        "ar": "مدّد {J} الضوء الأخضر قليلًا لـ {V} المتأخرة."},
    "TRANSIT_GRANTED_SWITCH": {
        "en": "{J} switched the green for late {V}.",
        "fr": "{J} a donné le vert à {V}, en retard.",
        "ar": "حوّل {J} الضوء الأخضر لـ {V} المتأخرة."},
    "TRANSIT_DENIED_EMERGENCY": {
        "en": "{J} could not help late {V}: an emergency vehicle had priority.",
        "fr": "{J} n'a pas pu aider {V}, en retard : un véhicule d'urgence était prioritaire.",
        "ar": "لم يستطع {J} مساعدة {V} المتأخرة: كانت الأولوية لمركبة طوارئ."},
    "TRANSIT_DENIED_EXIT_FULL": {
        "en": "{J} could not help late {V}: the road ahead was full.",
        "fr": "{J} n'a pas pu aider {V}, en retard : la route en aval était pleine.",
        "ar": "لم يستطع {J} مساعدة {V} المتأخرة: الطريق أمامها ممتلئ."},
    "TRANSIT_DENIED_MIN_GREEN": {
        "en": "{J} could not switch for late {V} yet: the current green had only just started.",
        "fr": "{J} ne pouvait pas encore changer pour {V} : le vert actuel venait de commencer.",
        "ar": "لم يستطع {J} التحويل لـ {V} المتأخرة بعد: الضوء الأخضر الحالي بدأ للتو."},
    "PED_SERVICE_REQUEST": {
        "en": "{people} pedestrian(s) had waited {wait} at {crossing}, so a walk signal was requested.",
        "fr": "{people} piéton(s) attendaient depuis {wait} à {crossing} : un feu piéton a été demandé.",
        "ar": "انتظر {people} من المشاة {wait} عند {crossing}، فطُلبت إشارة عبور."},
    "PED_SERVICE_GRANTED": {
        "en": "{J} gave a walk signal at {crossing}{waited}.",
        "fr": "{J} a donné le feu piéton à {crossing}{waited}.",
        "ar": "أعطى {J} إشارة العبور عند {crossing}{waited}."},
    "PED_SERVICE_DEFERRED": {
        "en": "{J} postponed a walk signal at {crossing}: the current green had only just started or an emergency had priority.",
        "fr": "{J} a reporté un feu piéton à {crossing} : le vert venait de commencer ou une urgence était prioritaire.",
        "ar": "أجّل {J} إشارة العبور عند {crossing}: الأخضر الحالي بدأ للتو أو كانت الأولوية لحالة طوارئ."},
    "CLEARANCE_EXTENDED": {
        "en": "{J} delayed the next green because someone was still on {crossings}.",
        "fr": "{J} a retardé le vert suivant car quelqu'un était encore sur {crossings}.",
        "ar": "أخّر {J} الضوء الأخضر التالي لأن شخصًا ما كان لا يزال على {crossings}."},
    "CLEARANCE_CAP_REACHED": {
        "en": "{J} reached its 30-second limit for waiting on a crossing; someone may still have been crossing.",
        "fr": "{J} a atteint sa limite de 30 s d'attente sur un passage ; quelqu'un traversait peut-être encore.",
        "ar": "بلغ {J} حدّ الانتظار البالغ 30 ثانية على ممر العبور؛ ربما كان أحدهم لا يزال يعبر."},
    "DATA_STALE": {
        "en": "A detector on {lane} stopped sending data (last update {age} ago); it is marked unreliable.",
        "fr": "Un détecteur sur {lane} n'envoie plus de données (dernière mise à jour il y a {age}) ; il est marqué non fiable.",
        "ar": "توقف كاشف على {lane} عن إرسال البيانات (آخر تحديث قبل {age})؛ وصُنّف غير موثوق."},
    "DATA_FRESH": {
        "en": "The detector on {lane} is sending data again.",
        "fr": "Le détecteur sur {lane} envoie de nouveau des données.",
        "ar": "عاد الكاشف على {lane} إلى إرسال البيانات."},
    "INCIDENT_SUSPECTED": {
        "en": "A vehicle appears stuck on {lane}, blocking a lane ({conf} confidence). The cause is not known.",
        "fr": "Un véhicule semble bloqué sur {lane}, obstruant une voie (confiance {conf}). La cause est inconnue.",
        "ar": "يبدو أن مركبة عالقة على {lane} وتسد مسارًا (درجة الثقة {conf}). السبب غير معروف."},
    "INCIDENT_CLEARED": {
        "en": "{Lc} is no longer blocked.",
        "fr": "{Lc} n'est plus bloquée.",
        "ar": "لم يعد {lane} مغلقًا."},
    "CONGESTION_DETECTED": {
        "en": "Heavy traffic on {edge}: {stopped} vehicles stopped.",
        "fr": "Circulation dense sur {edge} : {stopped} véhicules à l'arrêt.",
        "ar": "ازدحام شديد على {edge}: {stopped} مركبة متوقفة."},
    "CONGESTION_CLEARED": {
        "en": "Traffic on {edge} is flowing again.",
        "fr": "La circulation sur {edge} est de nouveau fluide.",
        "ar": "عادت الحركة إلى الانسياب على {edge}."},
    "REROUTE_ADVISORY": {
        "en": "Drivers heading through {edge} would save about {saving} with a detour. Advice only; nobody was rerouted.",
        "fr": "Les conducteurs passant par {edge} gagneraient environ {saving} avec un détour. Simple conseil ; personne n'a été dévié.",
        "ar": "يمكن للسائقين المارين عبر {edge} توفير نحو {saving} بطريق بديل. نصيحة فقط؛ لم يُحوَّل أحد."},
    "REROUTE_NOT_WORTH": {
        "en": "No detour around {edge} would save meaningful time.",
        "fr": "Aucun détour autour de {edge} ne ferait gagner un temps significatif.",
        "ar": "لا يوجد طريق بديل حول {edge} يوفّر وقتًا يُذكر."},
    "WEATHER_RAIN": {
        "en": "Rain reported ({intensity} intensity): every junction lengthened its yellow and crossing times; traffic expected about {slow} slower.",
        "fr": "Pluie signalée (intensité {intensity}) : chaque carrefour a allongé le jaune et les temps de traversée ; circulation environ {slow} plus lente.",
        "ar": "أُبلغ عن أمطار (شدة {intensity}): مدّد كل تقاطع زمن الأصفر والعبور؛ ويُتوقع أن تكون الحركة أبطأ بنحو {slow}."},
    "WEATHER_CLEAR": {
        "en": "The rain stopped; normal signal timings restored.",
        "fr": "La pluie s'est arrêtée ; durées normales des feux rétablies.",
        "ar": "توقف المطر؛ وأُعيدت توقيتات الإشارات العادية."},
    "WEATHER_FLOOD": {
        "en": "Flood alert: {edge} is impassable; detours will avoid it.",
        "fr": "Alerte inondation : {edge} est impraticable ; les détours l'éviteront.",
        "ar": "تنبيه فيضان: {edge} غير صالح للمرور؛ وستتجنبه الطرق البديلة."},
    "CORRIDOR_DIRECTION": {
        "en": "Main traffic direction is now {direction}; corridor coordination follows it.",
        "fr": "La direction principale du trafic est maintenant {direction} ; la coordination de corridor la suit.",
        "ar": "الاتجاه الرئيسي للحركة الآن {direction}؛ ويتبعه تنسيق الممر."},
    "OPERATOR_APPROVED": {
        "en": "The operator approved the copilot suggestion: \"{suggestion}\" (recorded, not applied automatically).",
        "fr": "L'opérateur a approuvé la suggestion du copilote : « {suggestion} » (enregistrée, non appliquée automatiquement).",
        "ar": "وافق المشغّل على اقتراح المساعد: «{suggestion}» (سُجّل ولم يُطبّق تلقائيًا)."},
    "OPERATOR_DISMISSED": {
        "en": "The operator dismissed the copilot suggestion: \"{suggestion}\".",
        "fr": "L'opérateur a ignoré la suggestion du copilote : « {suggestion} ».",
        "ar": "تجاهل المشغّل اقتراح المساعد: «{suggestion}»."},
    "FORECAST_UPDATE": {
        "en": "Forecast for {ffor}: traffic at {level} of the usual peak, {share} heading into the centre.",
        "fr": "Prévision pour {ffor} : trafic à {level} du pic habituel, {share} vers le centre.",
        "ar": "توقعات {ffor}: الحركة عند {level} من الذروة المعتادة، و{share} منها باتجاه الوسط."},
}

DIRECTIONS = {"inbound": {"en": "inbound", "fr": "vers le centre", "ar": "باتجاه الوسط"},
              "outbound": {"en": "outbound", "fr": "sortant du centre", "ar": "خارج الوسط"},
              "balanced": {"en": "balanced", "fr": "équilibrée", "ar": "متوازن"}}


class Narrator:
    def __init__(self, junction_names=None, edge_names=None, start=None):
        self.j = junction_names or {}
        self.edges = edge_names or {}
        self.start = start

    # ---------------------------------------------------------------- names
    def clock(self, t):
        return (self.start + timedelta(seconds=t)).strftime("%H:%M:%S") if self.start else f"t={t:.0f} s"

    def junction(self, tls, lang="en"):
        if not tls:
            return {"en": "a junction", "fr": "un carrefour", "ar": "تقاطع"}[lang]
        name = self.j.get(tls)
        return f"{tls} ({name})" if name and name != tls else str(tls)

    def vehicle(self, v, lang="en"):
        v = str(v or "")
        if v.startswith("bus_"):
            line, _, n = v[4:].rpartition("_")
            line = line.replace("_", " ")
            return {"en": f"bus {n} of line {line}", "fr": f"le bus {n} de la ligne {line}",
                    "ar": f"الحافلة {n} من الخط {line}"}[lang]
        names = {"ambulance": {"en": "ambulance", "fr": "l'ambulance", "ar": "سيارة الإسعاف"},
                 "police": {"en": "police car", "fr": "la voiture de police", "ar": "سيارة الشرطة"},
                 "fire": {"en": "fire truck", "fr": "le camion de pompiers", "ar": "شاحنة الإطفاء"}}
        for prefix, nm in names.items():
            if v.startswith(prefix) and v[len(prefix):].isdigit():
                return f"{nm[lang]} {v[len(prefix):]}"
        return v or {"en": "a vehicle", "fr": "un véhicule", "ar": "مركبة"}[lang]

    def edge(self, e, lang="en"):
        e = str(e or "")
        name = self.edges.get(e)
        parts = e.split("_")
        if len(parts) != 2:
            direction = ""
        elif lang == "ar":                      # words, not arrows: arrows flip in right-to-left text
            direction = f" (من {parts[0]} إلى {parts[1]})"
        else:
            direction = f" ({parts[0]} → {parts[1]})"
        return f"{name}{direction}" if name else e

    def lane(self, l, lang="en"):
        l = str(l or "")
        edge, _, idx = l.rpartition("_")
        if not edge:
            return l
        return {"en": f"lane {idx} of {self.edge(edge, lang)}", "fr": f"la voie {idx} de {self.edge(edge, lang)}",
                "ar": f"المسار {idx} من {self.edge(edge, lang)}"}[lang]

    def crossing(self, c, lang="en"):
        c = str(c or "").lstrip(":")
        tls, _, n = c.partition("_c")
        if not n:
            return c
        return {"en": f"crossing {n} at {self.junction(tls, lang)}", "fr": f"le passage {n} à {self.junction(tls, lang)}",
                "ar": f"ممر المشاة {n} عند {self.junction(tls, lang)}"}[lang]

    # ---------------------------------------------------------------- sentences
    def _values(self, e, lang):
        d = e.get("details", {})
        V = self.vehicle(d.get("vehicle"), lang)
        lane = self.lane(d.get("lane"), lang)
        num = lambda k: d.get(k) if isinstance(d.get(k), (int, float)) else 0
        guard = {"en": " (starvation guard: someone had waited too long)", "fr": " (garde-fou : quelqu'un attendait depuis trop longtemps)",
                 "ar": " (حماية من التجويع: شخص ما انتظر طويلًا)"}[lang] if d.get("method") == "starvation guard" else ""
        waited = ({"en": f" after {sec(d.get('waited_s'), lang)} of waiting", "fr": f" après {sec(d.get('waited_s'), lang)} d'attente",
                   "ar": f" بعد انتظار {sec(d.get('waited_s'), lang)}"}[lang] if d.get("waited_s") else "")
        direction = d.get("direction", "?")
        return {
            "J": self.junction(e.get("tls"), lang), "V": V, "Vc": cap(V), "lane": lane, "Lc": cap(lane),
            "pold": f"{num('pressure_old'):.0f}", "pnew": f"{num('pressure_new'):.0f}",
            "ps": d.get("predicted_wait_switch", 0), "pk": d.get("predicted_wait_keep", 0), "guard": guard,
            "green": sec(d.get("green_s"), lang), "eta": sec(d.get("eta_s"), lang),
            "exit": self.lane(d.get("exit_lane"), lang), "occ": pct(d.get("exit_occupancy"), lang),
            "served": self.vehicle(d.get("served"), lang), "qnow": d.get("queue_now", "?"),
            "qbefore": d.get("queue_before", "?"), "rec": sec(d.get("recovery_s"), lang),
            "gap": sec(d.get("gap_s"), lang), "head": sec(d.get("scheduled_headway_s", 240), lang),
            "people": d.get("people_waiting", "?"), "wait": sec(d.get("longest_wait_s"), lang),
            "crossing": self.crossing(d.get("crossing"), lang), "waited": waited,
            "crossings": ", ".join(self.crossing(c, lang) for c in d.get("crossings", [])) or
                         {"en": "a crossing", "fr": "un passage piéton", "ar": "ممر عبور"}[lang],
            "age": sec(d.get("last_update_s_ago"), lang), "conf": pct(d.get("confidence"), lang),
            "edge": self.edge(d.get("edge"), lang), "stopped": d.get("stopped_vehicles", "?"),
            "saving": sec(d.get("projected_saving_s"), lang), "intensity": pct(d.get("intensity"), lang),
            "slow": pct(1 - d.get("expected_speed_factor", 1), lang),
            "direction": DIRECTIONS.get(direction, {}).get(lang, direction),
            "suggestion": d.get("suggestion", ""), "ffor": str(d.get("forecast_for", ""))[11:16] or "—",
            "level": pct(d.get("level"), lang), "share": pct(d.get("inbound_share"), lang),
        }

    def sentence(self, e, lang="en"):
        lang = lang if lang in LANGS else "en"
        tpl = T.get(e["reason"], {}).get(lang)
        if not tpl:
            return REASON_CODES.get(e["reason"], e["reason"])
        try:
            return tpl.format(**self._values(e, lang))
        except Exception:                        # never fail on an odd entry
            return REASON_CODES.get(e["reason"], e["reason"])

    def describe(self, e, lang="en"):
        return f"{self.clock(e['t'])} · {self.sentence(e, lang)}"

    def enrich(self, entries):
        """Each entry with its sentence in every language (texts) and the English one (text)."""
        out = []
        for e in entries:
            texts = {l: self.sentence(e, l) for l in LANGS}
            out.append({**e, "text": texts["en"], "texts": texts, "clock": self.clock(e["t"])})
        return out
