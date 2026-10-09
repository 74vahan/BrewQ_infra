import { useState } from 'react';
import { CategoryIcon } from './CategoryIcon.tsx';
import styles from './MenuThumb.module.css';

interface MenuThumbProps {
  imageUrl: string | null;
  category: string;
  /** Dimmed while the item is out of stock. */
  muted: boolean;
}

/**
 * Item picture: the relative `image_url` from the API (same origin, so the
 * strict CSP holds), or a category glyph when there is none or it fails to load.
 * Decorative: the name next to it already says what the item is.
 */
export function MenuThumb({ imageUrl, category, muted }: MenuThumbProps) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const showImage = imageUrl !== null && imageUrl !== failedUrl;

  return (
    <span className={`${styles.thumb} ${muted ? styles.muted : ''}`}>
      {showImage ? (
        <img
          className={styles.image}
          src={imageUrl}
          alt=""
          width="56"
          height="56"
          loading="lazy"
          decoding="async"
          onError={() => {
            setFailedUrl(imageUrl);
          }}
        />
      ) : (
        <CategoryIcon category={category} />
      )}
    </span>
  );
}
