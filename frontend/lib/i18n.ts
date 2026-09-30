import { cookies } from "next/headers";

export type Lang = "en" | "hi";

// Interface labels only. Archive text is shown as NCPOR published it; Hindi versions of
// generated content exist only where a reviewer approved a Hindi draft.
const dict = {
  en: {
    site: "NCPOR Polar Knowledge Index",
    tagline: "India's polar expedition archive, searchable and cited to the page",
    skip: "Skip to main content",
    nav_search: "Search",
    nav_ask: "Ask a question",
    nav_expeditions: "Expeditions",
    nav_coverage: "Coverage",
    nav_learn: "Lessons & stories",
    nav_accuracy: "Accuracy",
    nav_staff: "Staff",
    search_label: "Search the archive",
    search_button: "Search",
    search_placeholder: "e.g. Dakshin Gangotri glacier movement",
    ask_label: "Your question",
    ask_button: "Ask",
    view_page: "View original page",
    open_record: "Open record on DSpace",
    source: "Source",
    page: "Page",
    printed_page: "printed p.",
    ocr: "OCR text",
    text_layer: "Text from the PDF",
    refused: "No NCPOR source found for this.",
    reviewed_by: "Reviewed and approved by",
    passages_only: "No reviewed answer yet. These are the archive passages that match your question.",
    not_ai: "These passages are the reports' own words, not AI text.",
    unknown: "unknown",
    footer:
      "Student prototype for Smart India Hackathon (SIH26063). Not an official NCPOR website. Every record links to where it was harvested from.",
  },
  hi: {
    site: "एनसीपीओआर ध्रुवीय ज्ञान सूचकांक",
    tagline: "भारत के ध्रुवीय अभियानों का संग्रह — खोजने योग्य, हर बात पृष्ठ के संदर्भ सहित",
    skip: "मुख्य सामग्री पर जाएँ",
    nav_search: "खोजें",
    nav_ask: "प्रश्न पूछें",
    nav_expeditions: "अभियान",
    nav_coverage: "कवरेज",
    nav_learn: "पाठ और कहानियाँ",
    nav_accuracy: "सटीकता",
    nav_staff: "कर्मचारी",
    search_label: "संग्रह में खोजें",
    search_button: "खोजें",
    search_placeholder: "उदा. दक्षिण गंगोत्री हिमनद की गति",
    ask_label: "आपका प्रश्न",
    ask_button: "पूछें",
    view_page: "मूल पृष्ठ देखें",
    open_record: "DSpace पर रिकॉर्ड खोलें",
    source: "स्रोत",
    page: "पृष्ठ",
    printed_page: "मुद्रित पृ.",
    ocr: "OCR पाठ",
    text_layer: "PDF से पाठ",
    refused: "इसके लिए एनसीपीओआर का कोई स्रोत नहीं मिला।",
    reviewed_by: "समीक्षा और अनुमोदन:",
    passages_only: "अभी कोई समीक्षित उत्तर नहीं है। ये संग्रह के वे अंश हैं जो आपके प्रश्न से मेल खाते हैं।",
    not_ai: "ये अंश रिपोर्टों के अपने शब्द हैं, एआई द्वारा लिखे नहीं।",
    unknown: "अज्ञात",
    footer:
      "स्मार्ट इंडिया हैकाथॉन (SIH26063) के लिए छात्र प्रोटोटाइप। यह एनसीपीओआर की आधिकारिक वेबसाइट नहीं है। हर रिकॉर्ड अपने मूल स्रोत से जुड़ा है।",
  },
} as const;

export type Dict = { [K in keyof (typeof dict)["en"]]: string };

export async function getLang(): Promise<Lang> {
  const value = (await cookies()).get("lang")?.value;
  return value === "hi" ? "hi" : "en";
}

export async function getDict(): Promise<{ lang: Lang; t: Dict }> {
  const lang = await getLang();
  return { lang, t: dict[lang] };
}
