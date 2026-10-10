import { useId } from 'react';
import { useTranslation } from 'react-i18next';
import type { MenuItem } from '../api/types.ts';
import { sizeKey } from '../i18n/keys.ts';
import { AvailabilitySwitch } from './AvailabilitySwitch.tsx';
import styles from './MenuRow.module.css';
import { MenuThumb } from './MenuThumb.tsx';
import { useSetAvailability } from './useSetAvailability.ts';

/** One menu item: picture, name, offered sizes and the in-stock switch. */
export function MenuRow({ item }: { item: MenuItem }) {
  const { t } = useTranslation();
  const nameId = useId();
  const setAvailability = useSetAvailability();

  return (
    <li className={`${styles.row} ${item.is_available ? '' : styles.stopped}`}>
      <MenuThumb imageUrl={item.image_url} category={item.category} muted={!item.is_available} />

      <div className={styles.text}>
        <p id={nameId} className={styles.name}>
          {item.name}
        </p>
        <ul className={styles.sizes} aria-label={t('menu.sizes')}>
          {item.sizes.map((entry) => (
            <li key={entry.size} className={styles.size}>
              {t(sizeKey(entry.size))}
            </li>
          ))}
        </ul>
      </div>

      <AvailabilitySwitch
        inStock={item.is_available}
        labelledBy={nameId}
        onChange={(inStock) => {
          setAvailability.mutate({ menuItemId: item.id, isAvailable: inStock });
        }}
      />
    </li>
  );
}
