import { useEffect, useId, useRef } from 'react';
import type { MouseEvent, SyntheticEvent } from 'react';
import styles from './ConfirmDialog.module.css';

interface ConfirmDialogProps {
  title: string;
  body: string;
  confirmLabel: string;
  /** The safe choice; it gets the initial focus. */
  dismissLabel: string;
  /** While the request runs the dialog cannot be dismissed. */
  pending?: boolean;
  onConfirm: () => void;
  onDismiss: () => void;
}

/**
 * Modal confirmation on the native <dialog>: the browser traps focus, makes
 * the page behind inert and closes on Esc. It is rendered only while open, so
 * it is opened once on mount.
 */
export function ConfirmDialog({
  title,
  body,
  confirmLabel,
  dismissLabel,
  pending = false,
  onConfirm,
  onDismiss,
}: ConfirmDialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const bodyId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
    return () => {
      if (dialog?.open) dialog.close();
    };
  }, []);

  const onCancel = (event: SyntheticEvent<HTMLDialogElement>): void => {
    event.preventDefault(); // React state decides; the parent unmounts the dialog.
    if (!pending) onDismiss();
  };

  const onBackdropClick = (event: MouseEvent<HTMLDialogElement>): void => {
    if (event.target === ref.current && !pending) onDismiss();
  };

  return (
    <dialog
      ref={ref}
      className={styles.dialog}
      aria-labelledby={titleId}
      aria-describedby={bodyId}
      onCancel={onCancel}
      onClick={onBackdropClick}
    >
      <div className={styles.content}>
        <h2 id={titleId} className={styles.title}>
          {title}
        </h2>
        <p id={bodyId} className={styles.body}>
          {body}
        </p>
        <div className={styles.buttons}>
          <button type="button" className={styles.dismiss} autoFocus disabled={pending} onClick={onDismiss}>
            {dismissLabel}
          </button>
          <button type="button" className={styles.confirm} disabled={pending} aria-busy={pending} onClick={onConfirm}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </dialog>
  );
}
