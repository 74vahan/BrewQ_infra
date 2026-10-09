/**
 * "New order" sound, synthesised with the Web Audio API: no audio files, no
 * CDN, nothing to cache or license.
 *
 * Autoplay policy: browsers keep an AudioContext suspended until the user has
 * touched the page. `unlockAudio()` is called from real user gestures (login
 * click, any tap/keypress later) and resumes the context. After a page reload
 * the context is locked again until the first tap, so the UI shows a hint
 * (`useAudioReady`) instead of silently failing to beep.
 */

interface Note {
  /** Hz */
  frequency: number;
  /** Seconds after the chime starts. */
  start: number;
  /** Seconds. */
  duration: number;
}

/** A bright rising two-note "ding-dong", long enough to be heard over a grinder. */
export const CHIME_NOTES: readonly Note[] = [
  { frequency: 880, start: 0, duration: 0.22 },
  { frequency: 1318.51, start: 0.18, duration: 0.55 },
];

const PEAK_GAIN = 0.35;

type ContextConstructor = typeof AudioContext;

let context: AudioContext | null = null;
const listeners = new Set<() => void>();

function contextConstructor(): ContextConstructor | null {
  if (typeof window === 'undefined') return null;
  const legacy = window as unknown as { webkitAudioContext?: ContextConstructor };
  return (typeof AudioContext === 'undefined' ? undefined : AudioContext) ?? legacy.webkitAudioContext ?? null;
}

function notify(): void {
  listeners.forEach((listener) => {
    listener();
  });
}

function ensureContext(): AudioContext | null {
  if (context) return context;
  const Constructor = contextConstructor();
  if (!Constructor) return null;
  try {
    context = new Constructor();
  } catch {
    return null;
  }
  context.addEventListener('statechange', notify);
  return context;
}

/** True once the browser lets the page make sound. */
export function isAudioReady(): boolean {
  return context?.state === 'running';
}

export function subscribeAudio(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Call from a user gesture (click, tap, keydown). Safe to call repeatedly. */
export function unlockAudio(): void {
  const ctx = ensureContext();
  if (ctx && ctx.state !== 'running') {
    ctx.resume().then(notify, () => {
      // Not a user activation after all: stay locked, the hint stays visible.
    });
  }
}

function schedule(ctx: AudioContext): void {
  const base = ctx.currentTime;
  for (const note of CHIME_NOTES) {
    const oscillator = ctx.createOscillator();
    const gain = ctx.createGain();
    const start = base + note.start;
    const end = start + note.duration;
    oscillator.type = 'sine';
    oscillator.frequency.setValueAtTime(note.frequency, start);
    // Fast attack, exponential decay: a struck bell, not a beep.
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(PEAK_GAIN, start + 0.015);
    gain.gain.exponentialRampToValueAtTime(0.0001, end);
    oscillator.connect(gain).connect(ctx.destination);
    oscillator.start(start);
    oscillator.stop(end + 0.05);
  }
}

/** Plays the chime if the browser allows it; resolves to whether it played. */
export async function playChime(): Promise<boolean> {
  const ctx = context;
  if (!ctx) return false;
  if (ctx.state !== 'running') {
    try {
      await ctx.resume();
    } catch {
      return false;
    }
    // resume() resolving does not guarantee 'running' (the browser may still refuse).
    if ((ctx.state as AudioContextState) !== 'running') return false;
  }
  schedule(ctx);
  return true;
}
