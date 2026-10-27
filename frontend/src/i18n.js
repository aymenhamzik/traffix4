// Language of the Synapse content (alerts, answers, copilot). UI labels stay in English.
import { createContext, useContext } from "react";

export const LANGS = [
  { id: "en", label: "EN" }, { id: "fr", label: "FR" }, { id: "ar", label: "عربي" },
];
export const LangContext = createContext({ lang: "en", setLang: () => {} });
export const useLang = () => useContext(LangContext);
export const dirOf = (lang) => (lang === "ar" ? "rtl" : "ltr");

// The best text for a notification in a language: Claude's persona rewrite, else built-in translation.
export const noteText = (n, lang) => n.texts_llm?.[lang] || n.texts?.[lang] || n.text;

export const T = {
  copilot: { en: "Operator copilot", fr: "Copilote opérateur", ar: "مساعد المشغّل" },
  suggestions: { en: "Suggested actions", fr: "Actions suggérées", ar: "إجراءات مقترحة" },
  approve: { en: "Approve", fr: "Approuver", ar: "موافقة" },
  dismiss: { en: "Dismiss", fr: "Ignorer", ar: "تجاهل" },
  report: { en: "Draft incident report", fr: "Rédiger un rapport", ar: "صياغة تقرير" },
  approved: { en: "approved · recorded, not applied", fr: "approuvé · enregistré, non appliqué", ar: "تمت الموافقة · سُجّل ولم يُطبّق" },
  dismissed: { en: "dismissed", fr: "ignoré", ar: "تم التجاهل" },
  refresh: { en: "Refresh", fr: "Actualiser", ar: "تحديث" },
  analystTitle: { en: "Why did the system do that?", fr: "Pourquoi le système a-t-il fait cela ?", ar: "لماذا قام النظام بذلك؟" },
  analystSub: { en: "Tahani · every decision has a reason code. Synapse explains with citations or abstains.",
                fr: "Tahani · chaque décision a un code de raison. Synapse explique avec des citations ou s'abstient.",
                ar: "تهاني · لكل قرار رمز سبب. يشرح Synapse مع ذكر المصادر أو يمتنع." },
  askSynapse: { en: "Ask Synapse", fr: "Demander à Synapse", ar: "اسأل Synapse" },
  ask: { en: "Ask", fr: "Demander", ar: "اسأل" },
  log: { en: "Decision log", fr: "Journal des décisions", ar: "سجل القرارات" },
  filter: { en: "Filter: ambulance, B3, bus, crossing, rain...", fr: "Filtrer : ambulance, B3, bus, passage, pluie...",
            ar: "تصفية: إسعاف، B3، حافلة، ممر، مطر..." },
  models: { en: "Trained models", fr: "Modèles entraînés", ar: "النماذج المدرّبة" },
  citations: { en: "citations", fr: "citations", ar: "مصادر" },
  abstained: { en: "abstained", fr: "abstention", ar: "امتناع" },
  typeFirst: { en: "Type a question first", fr: "Tapez d'abord une question", ar: "اكتب سؤالًا أولًا" },
};

// Example questions for the analyst page, by scenario type and language
export const EXAMPLES = {
  emergency: {
    en: ["Why did ambulance 0 get green?", "What happened with fire truck 0?", "Was any emergency vehicle refused?"],
    fr: ["Pourquoi l'ambulance 0 a-t-elle eu le vert ?", "Que s'est-il passé avec le camion de pompiers 0 ?",
         "Un véhicule d'urgence a-t-il été refusé ?"],
    ar: ["لماذا حصلت سيارة الإسعاف 0 على الضوء الأخضر؟", "ماذا حدث لشاحنة الإطفاء 0؟", "هل رُفضت أي مركبة طوارئ؟"],
  },
  general: {
    en: ["Why did the late buses get priority?", "What happened with the incident?", "Why was the walk signal delayed at B2?",
         "What did the rain change?"],
    fr: ["Pourquoi les bus en retard ont-ils eu la priorité ?", "Que s'est-il passé avec l'incident ?",
         "Pourquoi le feu piéton a-t-il été retardé à B2 ?", "Qu'est-ce que la pluie a changé ?"],
    ar: ["لماذا حصلت الحافلات المتأخرة على الأولوية؟", "ماذا حدث في الحادث؟", "لماذا تأخرت إشارة المشاة عند B2؟",
         "ماذا غيّر المطر؟"],
  },
};
export const t = (key, lang) => T[key]?.[lang] || T[key]?.en || key;
