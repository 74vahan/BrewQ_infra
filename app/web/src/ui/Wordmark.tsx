import styles from './Wordmark.module.css';

interface WordmarkProps {
  size?: 'md' | 'xl';
}

/** The brand name is a logo, not copy: it is intentionally not translated. */
export function Wordmark({ size = 'md' }: WordmarkProps) {
  return (
    <span translate="no" className={`${styles.wordmark} ${size === 'xl' ? styles.xl : styles.md}`}>
      Brew<span className={styles.q}>Q</span>
    </span>
  );
}
