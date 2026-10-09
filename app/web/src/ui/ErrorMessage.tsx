import { useTranslation } from 'react-i18next';
import { toApiError } from '../api/errors.ts';
import { errorKey } from '../i18n/keys.ts';
import styles from './ErrorMessage.module.css';

interface ErrorMessageProps {
  /** Whatever a query/mutation threw; non-ApiErrors show the generic text. */
  error: unknown;
  id?: string;
}

/** Translated message for an API failure, chosen by `error.code`, never by the server text. */
export function ErrorMessage({ error, id }: ErrorMessageProps) {
  const { t } = useTranslation();
  const { code } = toApiError(error);
  return (
    <p className={styles.error} role="alert" {...(id ? { id } : {})}>
      {t(errorKey(code))}
    </p>
  );
}
