export interface ArchiveDocument {
  name: string
  url: string
  bytes: number
  format: string
}

export interface ArchiveEntry {
  id: string
  family: string
  label: string
  variant: string
  year: number
  yearLabel: string
  title: string
  caption: string
  keywords: string[]
  color: string
  author: string
  kind: string
  subject: string
  license: string
  relationship: string
  remarks: string
  sources: string[]
  documents: ArchiveDocument[]
  indexUrl: string
  indexMarkdown: string
  notesMarkdown: string
}

export interface ArchiveCatalog {
  entries: ArchiveEntry[]
  families: string[]
  documentCount: number
}

export type WikiBlock =
  | { kind: 'paragraph'; text: string }
  | { kind: 'code'; title: string; language: string; code: string; notes: string[] }
  | { kind: 'table'; columns: string[]; rows: string[][] }
  | { kind: 'note'; title: string; text: string }

export interface WikiSection { id: string; title: string; blocks: WikiBlock[]; refs: string[] }
export interface WikiReference { key: string; title: string; file?: string; url?: string; locator: string }
export interface WikiFamily {
  name: string; fullName: string; subtitle: string; lead: string; origin: string; people: string
  model: string; setting: string; related: string[]; sections: WikiSection[]; references: WikiReference[]
}
export interface WikiVersion {
  name: string; lead: string; focus: string; boundary: string; features: string[]; sections: WikiSection[]
  implementation?: string
}
export interface RuleModule {
  name: string; path: string; url: string; imports: string[]; syntaxCount: number; effectCount: number
  frontends: string[]; sha256: string; category: string; description: string
}
export interface Implementation {
  name: string; module: string; frontend: string; status: string; summary: string; features: string[]
  limits: string[]; files: { path: string; url: string }[]; examples: { path: string; url: string; code: string }[]
  command: string; modules: string[]
}
export interface WikiCatalog {
  families: Record<string, WikiFamily>; versions: Record<string, WikiVersion>; modules: RuleModule[]
  implementations: Record<string, Implementation>
  report?: { url: string; recordedAt: string; passed: number; total: number; cases: { name: string; passed: boolean }[] }
  editedAt: string
}
