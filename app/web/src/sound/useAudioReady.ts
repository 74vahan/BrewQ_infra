import { useEffect, useSyncExternalStore } from 'react';
import { isAudioReady, subscribeAudio, unlockAudio } from './chime.ts';

const GESTURES = ['pointerdown', 'keydown', 'touchend'] as const;

/**
 * Whether the browser currently allows sound. While it does not, the first
 * tap or key press anywhere unlocks it (so the barista never has to find a
 * special button, and the hint in the UI is only a fallback).
 */
export function useAudioReady(): boolean {
  const ready = useSyncExternalStore(subscribeAudio, isAudioReady, () => false);

  useEffect(() => {
    if (ready) return;
    const onGesture = (): void => {
      unlockAudio();
    };
    GESTURES.forEach((type) => {
      window.addEventListener(type, onGesture, { passive: true });
    });
    return () => {
      GESTURES.forEach((type) => {
        window.removeEventListener(type, onGesture);
      });
    };
  }, [ready]);

  return ready;
}
