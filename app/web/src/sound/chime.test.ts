import { describe, expect, it } from 'vitest';
import { CHIME_NOTES, isAudioReady, playChime, unlockAudio } from './chime.ts';

describe('chime without Web Audio (server, old browser)', () => {
  it('stays silent and never throws', async () => {
    expect(isAudioReady()).toBe(false);
    expect(() => {
      unlockAudio();
    }).not.toThrow();
    expect(await playChime()).toBe(false);
  });

  it('is a short rising two-note figure', () => {
    expect(CHIME_NOTES).toHaveLength(2);
    const [first, second] = CHIME_NOTES;
    expect(second?.frequency).toBeGreaterThan(first?.frequency ?? Infinity);
    const total = CHIME_NOTES.reduce((end, note) => Math.max(end, note.start + note.duration), 0);
    expect(total).toBeLessThan(1.5);
  });
});
