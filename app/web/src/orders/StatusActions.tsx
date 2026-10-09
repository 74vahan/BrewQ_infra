import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { BaristaOrder } from '../api/types.ts';
import { actionKey } from '../i18n/keys.ts';
import { ConfirmDialog } from '../ui/ConfirmDialog.tsx';
import styles from './StatusActions.module.css';
import { actionsFor } from './transitions.ts';
import { useChangeStatus } from './useChangeStatus.ts';

/**
 * Buttons of an order card. They come only from `allowed_transitions`
 * (see transitions.ts): forward buttons are primary, cancellation is a
 * secondary button that asks for confirmation first. There is no "back".
 */
export function StatusActions({ order }: { order: BaristaOrder }) {
  const { t } = useTranslation();
  const change = useChangeStatus();
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const { forward, canCancel } = actionsFor(order);
  const busy = change.isPending;

  if (forward.length === 0 && !canCancel) return null;

  const label = (to: string): string => t(actionKey(to) ?? 'status.unknown');
  const describe = (to: string): string => t('order.actionFor', { action: label(to), code: order.code });

  return (
    <div className={styles.actions}>
      {forward.map((to) => (
        <button
          key={to}
          type="button"
          className={styles.primary}
          disabled={busy}
          aria-busy={busy}
          aria-label={describe(to)}
          onClick={() => {
            change.mutate({ orderId: order.id, to });
          }}
        >
          {label(to)}
        </button>
      ))}

      {canCancel && (
        <button
          type="button"
          className={styles.cancel}
          disabled={busy}
          aria-label={describe('CANCELLED')}
          onClick={() => {
            setConfirmingCancel(true);
          }}
        >
          {label('CANCELLED')}
        </button>
      )}

      {confirmingCancel && (
        <ConfirmDialog
          title={t('cancel.title', { code: order.code })}
          body={t('cancel.body')}
          confirmLabel={t('cancel.confirm')}
          dismissLabel={t('cancel.keep')}
          pending={busy}
          onDismiss={() => {
            setConfirmingCancel(false);
          }}
          onConfirm={() => {
            change.mutate(
              { orderId: order.id, to: 'CANCELLED' },
              {
                onSettled: () => {
                  setConfirmingCancel(false);
                },
              },
            );
          }}
        />
      )}
    </div>
  );
}
