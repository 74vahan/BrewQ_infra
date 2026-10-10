import styles from './ColumnProgress.module.css';

interface ColumnProgressProps {
  /** Zero-based position of the column in the queue (0 = new). */
  position: number;
  total: number;
}

/** Decorative progress strip under a column heading; the heading already says the status in words. */
export function ColumnProgress({ position, total }: ColumnProgressProps) {
  return (
    <div className={styles.track} aria-hidden="true">
      {Array.from({ length: total }, (_, index) => (
        <span key={index} className={`${styles.segment} ${index <= position ? styles.filled : ''}`} />
      ))}
    </div>
  );
}
