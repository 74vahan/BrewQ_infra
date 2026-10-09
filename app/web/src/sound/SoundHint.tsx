import { useTranslation } from 'react-i18next';
import { useSoundEnabled } from '../ui/useSoundEnabled.ts';
import { playChime, unlockAudio } from './chime.ts';
import styles from './SoundHint.module.css';
import { useAudioReady } from './useAudioReady.ts';

/**
 * Shown only when the barista wants sound but the browser still blocks it
 * (typically right after a page reload, before the first tap). One tap fixes it
 * and plays the chime as proof.
 */
export function SoundHint() {
  const { t } = useTranslation();
  const [enabled] = useSoundEnabled();
  const ready = useAudioReady();

  if (!enabled || ready) return null;
  return (
    <div className={styles.hint} role="status">
      <p className={styles.text}>{t('sound.blocked')}</p>
      <button
        type="button"
        className={styles.button}
        onClick={() => {
          unlockAudio();
          void playChime();
        }}
      >
        {t('sound.enable')}
      </button>
    </div>
  );
}
