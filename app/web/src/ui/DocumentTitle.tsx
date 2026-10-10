import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router';
import { composeTitle, titleKeyFor } from './pageTitle.ts';
import { useUnseenOrders } from './titleBadge.ts';

/**
 * Keeps the browser tab title in step with the screen and the language:
 * "Queue · BrewQ", "Today · BrewQ", ... and "(2) Queue · BrewQ" while new
 * orders are waiting. Renders nothing. Mounted once, around all routes.
 */
export function DocumentTitle() {
  const { t, i18n } = useTranslation();
  const { pathname } = useLocation();
  const unseen = useUnseenOrders();

  useEffect(() => {
    document.title = composeTitle(t(titleKeyFor(pathname)), t('app.title'), unseen);
  }, [pathname, unseen, t, i18n.language]);

  return null;
}
