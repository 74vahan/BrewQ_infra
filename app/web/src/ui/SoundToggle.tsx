import { useTranslation } from 'react-i18next';
import { playChime, unlockAudio } from '../sound/chime.ts';
import { SoundOffIcon, SoundOnIcon } from './icons.tsx';
import styles from './SoundToggle.module.css';
import { useSoundEnabled } from './useSoundEnabled.ts';

export function SoundToggle() {
  const { t } = useTranslation();
  const [enabled, setEnabled] = useSoundEnabled();
  const state = enabled ? t('sound.on') : t('sound.off');

  return (
    <button
      type="button"
      className={styles.button}
      aria-pressed={enabled}
      aria-label={t('sound.label')}
      title={`${t('sound.label')}: ${state}`}
      onClick={() => {
        setEnabled(!enabled);
        if (!enabled) {
          // Turning sound on is a user gesture: unlock the browser and play the chime as a preview.
          unlockAudio();
          void playChime();
        }
      }}
    >
      {enabled ? <SoundOnIcon /> : <SoundOffIcon />}
      <span className={styles.text}>{state}</span>
    </button>
  );
}
