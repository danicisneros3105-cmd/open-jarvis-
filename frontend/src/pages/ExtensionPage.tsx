import { useCallback, useEffect, useState } from 'react';
import { Loader2, Play, ExternalLink } from 'lucide-react';
import {
  fetchExtensions,
  globeFrameUrl,
  startExtension,
  type ExtensionName,
  type ExtensionsState,
} from '../lib/extensions-api';

const POLL_MS = 3000;

const COPY: Record<ExtensionName, { title: string; hint: string }> = {
  globe: {
    title: 'Globe',
    hint: 'Live 3D globe. Ask in chat: "show me Tokyo in night vision".',
  },
  clacky: {
    title: 'Clacky',
    hint: 'Hands-on agent for your computer and browser. Jarvis delegates tasks here.',
  },
};

// Embeds one bundled extension (OpenClacky or the globe) as a full-page panel.
export function ExtensionPage({ name }: { name: ExtensionName }) {
  const [state, setState] = useState<ExtensionsState | null>(null);
  const [error, setError] = useState('');
  const [starting, setStarting] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setState(await fetchExtensions());
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, POLL_MS);
    return () => window.clearInterval(id);
  }, [refresh]);

  const svc = state?.services.find((s) => s.name === name);
  const copy = COPY[name];

  const handleStart = async () => {
    setStarting(true);
    try {
      await startExtension(name);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setStarting(false);
      refresh();
    }
  };

  const src = svc
    ? name === 'globe'
      ? globeFrameUrl(svc.url, state?.globe_target ?? null)
      : svc.url
    : '';

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <header
        className="flex items-center justify-between gap-3 px-4 py-2 shrink-0 border-b"
        style={{ borderColor: 'var(--color-border)' }}
      >
        <div className="min-w-0">
          <h1 className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
            {copy.title}
            {name === 'globe' && state?.globe_target ? ` · ${state.globe_target.label}` : ''}
          </h1>
          <p className="text-xs truncate" style={{ color: 'var(--color-text-secondary)' }}>
            {copy.hint}
          </p>
        </div>
        {svc?.running && (
          <a
            href={src}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 text-xs"
            style={{ color: 'var(--color-accent)' }}
          >
            <ExternalLink size={14} /> Open in new tab
          </a>
        )}
      </header>

      {svc?.running ? (
        <iframe
          key={src}
          title={copy.title}
          src={src}
          className="flex-1 w-full border-0"
          allow="microphone; clipboard-read; clipboard-write; fullscreen"
        />
      ) : (
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="max-w-md text-center space-y-3">
            {!state && !error && <Loader2 className="mx-auto animate-spin" size={20} />}
            {error && <p style={{ color: 'var(--color-error)' }}>{error}</p>}
            {svc && !svc.available && (
              <p style={{ color: 'var(--color-warning)' }}>{svc.problem}</p>
            )}
            {state && !svc && (
              <p style={{ color: 'var(--color-text-secondary)' }}>
                This extension is disabled in config.toml ([extensions.{name}] enabled = false).
              </p>
            )}
            {svc?.available && (
              <button
                onClick={handleStart}
                disabled={starting}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm"
                style={{ background: 'var(--color-accent)', color: 'white' }}
              >
                {starting ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
                {starting ? 'Starting…' : `Start ${copy.title}`}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
