"""
Template answers WITHOUT a language model: explain the rule behind a topic ("why"), then
summarise what actually happened in this run, with counts and citations.

Example: "Why did the late buses get priority?"
  -> Buses only get priority when they are late (gap over 6 min on a 4-min schedule) ...
  -> So far: no late bus has needed priority. 7 buses could not be judged yet ... [#91] ...
"""
import re
from collections import Counter, OrderedDict

TOPICS = OrderedDict([
    ("emergency", (r"ambulance|emergency|police|fire", ("EMERGENCY", "RECOVER"))),
    ("bus", (r"\bbus|buses|transit|late|line\b|headway", ("TRANSIT", "BUS_"))),
    ("pedestrian", (r"pedestrian|walk|crossing|piéton|مشا", ("PED_", "CLEARANCE"))),
    ("incident", (r"incident|accident|blocked|crash|congestion|jam|traffic", ("INCIDENT", "CONGESTION", "REROUTE"))),
    ("weather", (r"rain|weather|flood|pluie|مطر", ("WEATHER",))),
    ("sensor", (r"sensor|detector|stale|backup|fallback|data", ("DATA_", "MODE_"))),
    ("signals", (r"switch|phase|green|pressure|corridor|light", ("MAX_PRESSURE", "CORRIDOR", "PREDICTIVE", "RL_",
                                                                   "ACTUATED", "FIXED"))),
])

WHY = {
    "emergency": {
        "en": "Emergency vehicles outrank every other request; only the safety rules come first. The junction gives green "
              "unless the road ahead is full (a green would only push the vehicle into a queue) or someone is still on the "
              "crossing. Junctions further along the route are warned about 40 s ahead.",
        "fr": "Les véhicules d'urgence passent avant toute autre demande ; seules les règles de sécurité priment. Le carrefour "
              "donne le vert sauf si la route en aval est saturée ou si un piéton traverse encore. Les carrefours suivants "
              "sont prévenus environ 40 s à l'avance.",
        "ar": "مركبات الطوارئ لها الأولوية على كل الطلبات الأخرى، ولا يسبقها إلا قواعد السلامة. يمنح التقاطع الضوء الأخضر "
              "إلا إذا كان الطريق أمامها ممتلئًا أو كان أحد المشاة لا يزال يعبر. وتُنبَّه التقاطعات التالية قبل نحو 40 ثانية."},
    "bus": {
        "en": "Buses only get priority when they are late: when the gap since the previous bus of the same line is more than "
              "1.5 × the 4-minute schedule (6 minutes). An on-time or early bus gets nothing, so buses do not bunch further. "
              "The first bus of a line cannot be judged yet, so it gets no priority either.",
        "fr": "Un bus n'obtient la priorité que s'il est en retard : quand l'écart avec le bus précédent de la même ligne dépasse "
              "1,5 × l'horaire de 4 minutes (6 minutes). Un bus à l'heure ou en avance n'obtient rien. Le premier bus d'une "
              "ligne ne peut pas encore être jugé.",
        "ar": "لا تحصل الحافلة على الأولوية إلا إذا كانت متأخرة: عندما يتجاوز الفارق مع الحافلة السابقة على نفس الخط 1.5 ضعف "
              "الجدول (6 دقائق بدل 4). الحافلة في موعدها أو المبكرة لا تحصل على شيء، ولا يمكن تقييم أول حافلة على الخط بعد."},
    "pedestrian": {
        "en": "Pedestrians are protected by a safety rule: the next green waits until the crossing is empty (up to 30 s). "
              "When people have waited too long, the pedestrian agent asks for a walk signal.",
        "fr": "Les piétons sont protégés par une règle de sécurité : le vert suivant attend que le passage soit vide (jusqu'à "
              "30 s). Quand l'attente est trop longue, l'agent piéton demande un feu piéton.",
        "ar": "يحمي المشاةَ قاعدةُ سلامة: ينتظر الضوء الأخضر التالي حتى يخلو ممر العبور (حتى 30 ثانية). وعندما يطول الانتظار "
              "يطلب وكيل المشاة إشارة عبور."},
    "incident": {
        "en": "The incident agent flags a lane when a vehicle stays stopped away from the queue at the light; it reports a "
              "pattern and a confidence, never a cause. Long queues are reported as congestion, and the rerouting agent "
              "checks whether a detour would save time (advice only).",
        "fr": "L'agent incidents signale une voie quand un véhicule reste arrêté hors de la file au feu ; il donne un motif et "
              "une confiance, jamais une cause. Les longues files sont signalées comme congestion, et l'agent d'itinéraires "
              "vérifie si un détour ferait gagner du temps (conseil seulement).",
        "ar": "يرصد وكيل الحوادث المسار عندما تبقى مركبة متوقفة بعيدًا عن طابور الإشارة، ويذكر نمطًا ودرجة ثقة لا سببًا. "
              "وتُعلَن الطوابير الطويلة كازدحام، ويتحقق وكيل المسارات من جدوى طريق بديل (نصيحة فقط)."},
    "weather": {
        "en": "When rain is reported, every junction lengthens its yellow and crossing times, because vehicles brake longer "
              "and people walk slower. A flooded road is avoided by detours.",
        "fr": "Quand il pleut, chaque carrefour allonge le jaune et le temps de traversée, car les véhicules freinent plus "
              "longtemps et les piétons marchent plus lentement. Une route inondée est contournée.",
        "ar": "عند هطول المطر يمدّد كل تقاطع زمن الأصفر وزمن العبور، لأن المركبات تحتاج مسافة كبح أطول والمشاة أبطأ. "
              "ويتم تجنّب الطريق المغمور بالمياه."},
    "sensor": {
        "en": "Each junction's sensor agent checks that its detectors keep updating. If incoming data goes stale, the junction "
              "falls back to a fixed plan; if only exit data is stale, to actuated control. Stale stays stale until the "
              "detector really updates again.",
        "fr": "L'agent capteurs de chaque carrefour vérifie que ses détecteurs se mettent à jour. Si les données d'entrée sont "
              "périmées, le carrefour passe en plan fixe ; si seules les sorties le sont, en mode actionné.",
        "ar": "يتحقق وكيل الكواشف في كل تقاطع من استمرار تحديث بياناتها. إذا توقفت بيانات المداخل ينتقل التقاطع إلى خطة "
              "ثابتة، وإذا توقفت بيانات المخارج فقط ينتقل إلى التحكم المُفعَّل."},
    "signals": {
        "en": "Normally each junction gives green to the direction with the most queued vehicles, minus those already queued "
              "where they would go (max-pressure), with a bonus for groups of cars arriving from the neighbouring junction.",
        "fr": "Normalement, chaque carrefour donne le vert à la direction la plus chargée, moins les véhicules déjà en file "
              "en aval (max-pressure), avec un bonus pour les pelotons arrivant du carrefour voisin.",
        "ar": "عادةً يمنح كل تقاطع الضوء الأخضر للاتجاه الأكثر ازدحامًا مطروحًا منه الطوابير في الوجهة (الضغط الأقصى)، "
              "مع أفضلية لمجموعات السيارات القادمة من التقاطع المجاور."},
}

HAPPENED = {"en": "What happened in this run so far ({clock}):", "fr": "Ce qui s'est passé jusqu'ici ({clock}) :",
            "ar": "ما حدث حتى الآن ({clock}):"}
F = {   # run-summary sentences: {n} counts, {who}/{where} lists, {ids} citations
    "late_asked": {"en": "{n} late bus(es) asked for priority ({who}) {ids}.",
                   "fr": "{n} bus en retard ont demandé la priorité ({who}) {ids}.",
                   "ar": "طلبت {n} حافلة متأخرة الأولوية ({who}) {ids}."},
    "granted": {"en": "Priority was given {n} time(s), at {where} {ids}.",
                "fr": "La priorité a été accordée {n} fois, à {where} {ids}.",
                "ar": "مُنحت الأولوية {n} مرة، عند {where} {ids}."},
    "not_granted": {"en": "None of those requests could be granted yet (an emergency, a full exit or a green that had just started).",
                    "fr": "Aucune de ces demandes n'a encore pu être accordée (urgence, sortie saturée ou vert tout juste commencé).",
                    "ar": "لم يُلبَّ أيٌّ من هذه الطلبات بعد (حالة طوارئ أو طريق خروج ممتلئ أو أخضر بدأ للتو)."},
    "none_late": {"en": "No bus has been late so far, so no bus priority was needed.",
                  "fr": "Aucun bus n'a été en retard jusqu'ici : aucune priorité bus n'a été nécessaire.",
                  "ar": "لم تتأخر أي حافلة حتى الآن، فلم تكن هناك حاجة لأولوية الحافلات."},
    "on_time": {"en": "{n} bus arrival(s) at a junction were on time, so they got no priority {ids}.",
                "fr": "{n} passage(s) de bus à un carrefour étaient à l'heure, sans priorité {ids}.",
                "ar": "{n} وصول حافلة إلى تقاطع كان في الموعد، فلم تُمنح أولوية {ids}."},
    "unknown": {"en": "{n} bus(es) could not be judged yet (first of their line) {ids}.",
                "fr": "{n} bus n'ont pas encore pu être évalués (premiers de leur ligne) {ids}.",
                "ar": "تعذّر تقييم {n} حافلة بعد (الأولى على خطها) {ids}."},
    "refused": {"en": "{n} request(s) were refused (emergency, full exit or minimum green) {ids}.",
                "fr": "{n} demande(s) refusée(s) (urgence, sortie saturée ou vert minimal) {ids}.",
                "ar": "رُفض {n} طلب (طوارئ أو طريق خروج ممتلئ أو أخضر أدنى) {ids}."},
    "no_emergency": {"en": "No emergency vehicle has crossed the network yet in this run.",
                     "fr": "Aucun véhicule d'urgence n'a encore traversé le réseau.",
                     "ar": "لم تعبر أي مركبة طوارئ الشبكة بعد."},
    "em_who": {"en": "Emergency vehicles so far: {who}.", "fr": "Véhicules d'urgence jusqu'ici : {who}.",
               "ar": "مركبات الطوارئ حتى الآن: {who}."},
    "em_warned": {"en": "Junctions were warned ahead of them {n} time(s) {ids}.",
                  "fr": "Les carrefours ont été prévenus à l'avance {n} fois {ids}.",
                  "ar": "نُبّهت التقاطعات مسبقًا {n} مرة {ids}."},
    "em_green": {"en": "They got a green {n} time(s) ({held} time(s) the green was already theirs and was held) {ids}.",
                 "fr": "Ils ont obtenu le vert {n} fois ({held} fois le vert était déjà le leur et a été maintenu) {ids}.",
                 "ar": "حصلت على الأخضر {n} مرة ({held} مرة كان الأخضر لها أصلًا وتم إبقاؤه) {ids}."},
    "em_refused": {"en": "Refused {n} time(s) {ids}.", "fr": "Refusés {n} fois {ids}.", "ar": "رُفضت {n} مرة {ids}."},
    "em_none_refused": {"en": "Refused 0 times: every request was served.", "fr": "Refusés 0 fois : chaque demande a été servie.",
                        "ar": "لم تُرفض أي مرة: خُدم كل طلب."},
    "em_recovered": {"en": "Traffic recovered on average {s} s after they passed {ids}.",
                     "fr": "La circulation s'est rétablie en moyenne {s} s après leur passage {ids}.",
                     "ar": "تعافت الحركة في المتوسط بعد {s} ثانية من مرورها {ids}."},
    "nothing": {"en": "Nothing of this kind has happened yet in this run.", "fr": "Rien de ce type ne s'est encore produit.",
                "ar": "لم يحدث شيء من هذا النوع بعد."},
    "times": {"en": " This happened {n} times in total.", "fr": " C'est arrivé {n} fois au total.",
              "ar": " حدث ذلك {n} مرة إجمالًا."},
}


def _f(key, lang, **kw):
    return F[key][lang].format(**kw)


def topic_of(question):
    q = question.lower()
    for name, (pattern, _) in TOPICS.items():
        if re.search(pattern, q):
            return name
    return None


def _ids(es, k=3):
    return " ".join(f"[#{e['id']}]" for e in es[-k:])


def _plural(n, word):
    if n == 1:
        return f"{n} {word}"
    return f"{n} {word}es" if word.endswith(("s", "sh", "ch")) else f"{n} {word}s"


def facts(topic, entries, narrator, lang="en"):
    """Sentences summarising the run for a topic, grouped by reason, with citations."""
    prefixes = TOPICS[topic][1]
    es = [e for e in entries if e["reason"].startswith(prefixes)]
    by = OrderedDict()
    for e in es:
        by.setdefault(e["reason"], []).append(e)
    veh = lambda g: sorted({narrator.vehicle(e["details"].get("vehicle"), lang) for e in g if e["details"].get("vehicle")})
    jn = lambda g: sorted({e.get("tls") for e in g if e.get("tls")})
    nveh = lambda g: len({e["details"].get("vehicle") for e in g})
    out = []
    if topic == "bus":
        granted = by.get("TRANSIT_GRANTED_SWITCH", []) + by.get("TRANSIT_GRANTED_EXTEND", [])
        late = by.get("TRANSIT_REQUEST_LATE_BUS", [])
        if late:
            out.append(_f("late_asked", lang, n=nveh(late), who=", ".join(veh(late)[:3]), ids=_ids(late)))
        if granted:
            out.append(_f("granted", lang, n=len(granted), where=", ".join(jn(granted)), ids=_ids(granted)))
        elif late:
            out.append(_f("not_granted", lang))
        else:
            out.append(_f("none_late", lang))
        ok, unknown = by.get("BUS_NOT_LATE", []), by.get("BUS_NO_REFERENCE", [])
        if ok:
            out.append(_f("on_time", lang, n=len(ok), ids=_ids(ok)))
        if unknown:
            out.append(_f("unknown", lang, n=nveh(unknown), ids=_ids(unknown)))
        denied = [e for r, g in by.items() if r.startswith("TRANSIT_DENIED") for e in g]
        if denied:
            out.append(_f("refused", lang, n=len(denied), ids=_ids(denied)))
        return out
    if topic == "emergency":
        req = by.get("EMERGENCY_REQUEST", [])
        g = by.get("EMERGENCY_GRANTED_SWITCH", []) + by.get("EMERGENCY_GRANTED_HOLD", [])
        d = by.get("EMERGENCY_DENIED_EXIT_FULL", []) + by.get("EMERGENCY_DENIED_OTHER_EMERGENCY", [])
        prep = by.get("EMERGENCY_PREPARE", [])
        if not (req or g or prep):
            return [_f("no_emergency", lang)]
        out.append(_f("em_who", lang, who=", ".join(veh(req + g + prep)[:5])))
        if prep:
            out.append(_f("em_warned", lang, n=len(prep), ids=_ids(prep)))
        if g:
            out.append(_f("em_green", lang, n=len(g), held=len(by.get("EMERGENCY_GRANTED_HOLD", [])), ids=_ids(g)))
        out.append(_f("em_refused", lang, n=len(d), ids=_ids(d)) if d else _f("em_none_refused", lang))
        rec = by.get("RECOVERED", [])
        if rec:
            avg = sum(e["details"].get("recovery_s", 0) for e in rec) / len(rec)
            out.append(_f("em_recovered", lang, s=f"{avg:.0f}", ids=_ids(rec)))
        return out
    if not es:
        return [_f("nothing", lang)]
    for reason, g in by.items():
        more = _f("times", lang, n=len(g)) if len(g) > 1 else ""
        out.append(f"{narrator.sentence(g[-1], lang)}{more} {_ids(g)}")
        if len(out) >= 5:
            break
    return out


def answer(question, entries, narrator, lang="en"):
    """Returns the answer text, or None when the question has no recognisable topic."""
    topic = topic_of(question)
    if topic is None:
        return None
    clock = narrator.clock(entries[-1]["t"]) if entries else ""
    lines = [WHY[topic][lang], "", HAPPENED[lang].format(clock=clock)]
    lines += [f"- {f}" for f in facts(topic, entries, narrator, lang)]
    return "\n".join(lines)


def vehicle_summary(selected, narrator, lang="en"):
    """One-line summary before a single vehicle's timeline."""
    vs = {e["details"].get("vehicle") for e in selected if e["details"].get("vehicle")}
    if len(vs) != 1:
        return None
    name = narrator.vehicle(next(iter(vs)), lang)
    r = Counter(e["reason"] for e in selected)
    if lang != "en":
        g = r["EMERGENCY_GRANTED_SWITCH"] + r["EMERGENCY_GRANTED_HOLD"] + r["TRANSIT_GRANTED_SWITCH"] + r["TRANSIT_GRANTED_EXTEND"]
        dn = r["EMERGENCY_DENIED_EXIT_FULL"] + r["EMERGENCY_DENIED_OTHER_EMERGENCY"] + sum(v for k, v in r.items() if k.startswith("TRANSIT_DENIED"))
        js = ", ".join(sorted({e.get("tls") for e in selected if e.get("tls")}))
        return {"fr": f"{name[:1].upper() + name[1:]} : carrefours {js} ; vert ou priorité accordés {g} fois, refusés {dn} fois. Étape par étape :",
                "ar": f"{name}: التقاطعات {js}؛ مُنح الأخضر أو الأولوية {g} مرة، ورُفض {dn} مرة. خطوة بخطوة:"}[lang]
    if any(k.startswith("EMERGENCY") for k in r):
        junctions = sorted({e.get("tls") for e in selected if e.get("tls")})
        granted = r["EMERGENCY_GRANTED_SWITCH"] + r["EMERGENCY_GRANTED_HOLD"]
        denied = r["EMERGENCY_DENIED_EXIT_FULL"] + r["EMERGENCY_DENIED_OTHER_EMERGENCY"]
        return (f"{name[:1].upper() + name[1:]} passed {len(junctions)} junction(s) ({', '.join(junctions)}). It got a green "
                f"{_plural(granted, 'time')}: {_plural(r['EMERGENCY_GRANTED_SWITCH'], 'switch')} made for it and "
                f"{_plural(r['EMERGENCY_GRANTED_HOLD'], 'green')} already in its direction and held; refused "
                f"{_plural(denied, 'time')}. Junctions ahead were warned {_plural(r['EMERGENCY_PREPARE'], 'time')}. "
                f"Step by step:")
    if any(k.startswith(("TRANSIT", "BUS_")) for k in r):
        return (f"{name[:1].upper() + name[1:]}: late at {_plural(r['TRANSIT_REQUEST_LATE_BUS'], 'junction')}, priority given "
                f"{_plural(r['TRANSIT_GRANTED_SWITCH'] + r['TRANSIT_GRANTED_EXTEND'], 'time')}, on time at "
                f"{_plural(r['BUS_NOT_LATE'], 'junction')}, not yet judgeable at {r['BUS_NO_REFERENCE']}. Step by step:")
    return None
