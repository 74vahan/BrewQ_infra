import styles from './Wordmark.module.css';

interface WordmarkProps {
  size?: 'md' | 'xl';
  /** 'chrome': on the fixed dark header strip; 'page': on the themed page background. */
  tone?: 'page' | 'chrome';
}

/** The brand name is a logo, not copy: it is intentionally not translated. */
export function Wordmark({ size = 'md', tone = 'page' }: WordmarkProps) {
  const classes = [styles.wordmark, size === 'xl' ? styles.xl : styles.md, tone === 'chrome' ? styles.onChrome : '']
    .filter(Boolean)
    .join(' ');
  return (
    <span translate="no" className={classes}>
      Brew<span className={styles.q}>Q</span>
    </span>
  );
}
