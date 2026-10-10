import { useTranslation } from 'react-i18next';
import { toApiError } from '../api/errors.ts';
import { errorKey } from '../i18n/keys.ts';
import styles from './ErrorMessage.module.css';

interface ErrorMessageProps {
  /** Whatever a query/mutation threw; non-ApiErrors show the generic text. */
  error?: unknown;
  /** Already translated text for a problem that is not an API failure (for example an empty field). */
  message?: string;
  id?: string;
}

/** Translated message for an API failure, chosen by `error.code`, never by the server text. */
export function ErrorMessage({ error, message, id }: ErrorMessageProps) {
  const { t } = useTranslation();
  const text = message ?? t(errorKey(toApiError(error).code));
  return (
    <p className={styles.error} role="alert" {...(id ? { id } : {})}>
      {text}
    </p>
  );
}
