import { useTranslation } from 'react-i18next';
import styles from './AvailabilitySwitch.module.css';

interface AvailabilitySwitchProps {
  /** true = in stock (on the menu), false = on the stop list. */
  inStock: boolean;
  /** id of the element that names the item, so the switch reads "Latte, switch, in stock". */
  labelledBy: string;
  onChange: (inStock: boolean) => void;
}

/** "In stock" switch with its state written out next to it (never colour only). */
export function AvailabilitySwitch({ inStock, labelledBy, onChange }: AvailabilitySwitchProps) {
  const { t } = useTranslation();

  return (
    <button
      type="button"
      role="switch"
      aria-checked={inStock}
      aria-labelledby={labelledBy}
      className={`${styles.switch} ${inStock ? styles.on : styles.off}`}
      onClick={() => {
        onChange(!inStock);
      }}
    >
      <span className={styles.label}>{inStock ? t('menu.available') : t('menu.unavailable')}</span>
      <span className={styles.track} aria-hidden="true">
        <span className={styles.knob} />
      </span>
    </button>
  );
}
