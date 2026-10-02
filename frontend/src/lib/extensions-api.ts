import { apiFetch } from './api';

// Bundled extensions served next to OpenJarvis (see src/openjarvis/unified).
export type ExtensionName = 'clacky' | 'globe';

export interface ExtensionStatus {
  name: ExtensionName;
  title: string;
  url: string;
  running: boolean;
  available: boolean;
  problem: string;
}

export interface GlobeTarget {
  label: string;
  style: string;
  hash: string;
  updated_at: number;
}

export interface ExtensionsState {
  services: ExtensionStatus[];
  globe_target: GlobeTarget | null;
}

export async function fetchExtensions(): Promise<ExtensionsState> {
  const res = await apiFetch('/v1/extensions');
  if (!res.ok) throw new Error(`Failed to load extensions (${res.status})`);
  return res.json();
}

export async function startExtension(name: ExtensionName): Promise<string> {
  const res = await apiFetch(`/v1/extensions/${name}/start`, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to start ${name} (${res.status})`);
  const body = await res.json();
  return body.outcome as string;
}

// Iframe URL for the globe. The globe reads its camera from the URL hash only
// on load, so a changing query string forces a reload for each new target.
export function globeFrameUrl(base: string, target: GlobeTarget | null): string {
  if (!target) return base;
  return `${base}/?t=${Math.round(target.updated_at * 1000)}#${target.hash}`;
}
