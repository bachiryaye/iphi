import { walkthrough } from "./walkthrough";
import { reference } from "./reference";
import { lookup } from "./lookup";

export type HelpTopic =
  | "start"
  | "states"
  | "scenarios"
  | "metrics"
  | "incidents"
  | "diagnosis"
  | "recovery"
  | "reports"
  | "glossary"
  | "troubleshooting"
  | "tour"
  | "rules"
  | "clock"
  | "audit"
  | "standards"
  | "presentation";
export interface HelpSection {
  id: HelpTopic;
  title: string;
  body: string;
  action?: string;
  result: string;
  to?: string;
  view?: string;
  steps?: readonly { instruction: string; result: string }[];
  entries?: readonly { term: string; definition: string }[];
  resources?: readonly { href: string; label: string }[];
}

const order: readonly HelpTopic[] = [
  "start",
  "tour",
  "states",
  "scenarios",
  "metrics",
  "rules",
  "incidents",
  "diagnosis",
  "clock",
  "recovery",
  "reports",
  "glossary",
  "troubleshooting",
  "audit",
  "standards",
  "presentation",
];

function buildSections(language: "en" | "fr"): readonly HelpSection[] {
  const all = [...walkthrough[language], ...lookup[language], ...reference[language]];
  return order.map((id) => {
    const section = all.find((entry) => entry.id === id);
    if (!section) throw new Error(`Missing help topic: ${id}`);
    return section;
  });
}

export const sections = { en: buildSections("en"), fr: buildSections("fr") };
