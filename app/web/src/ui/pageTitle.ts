/** Translation key of the page name for a route path (the name goes into the tab title). */
export function titleKeyFor(pathname: string): string {
  const path = pathname.replace(/\/+$/, '') || '/';
  switch (path) {
    case '/':
      return 'queue.title';
    case '/today':
      return 'today.title';
    case '/menu':
      return 'menu.title';
    case '/login':
      return 'auth.title';
    default:
      return 'notFound.title';
  }
}

/**
 * "Queue · BrewQ", with the number of orders nobody has looked at yet in
 * front: "(2) Queue · BrewQ".
 */
export function composeTitle(pageName: string, appName: string, unseenOrders: number): string {
  const base = `${pageName} · ${appName}`;
  return unseenOrders > 0 ? `(${String(unseenOrders)}) ${base}` : base;
}
