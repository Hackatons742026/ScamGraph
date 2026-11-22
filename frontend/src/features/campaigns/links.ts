/** Campaign (or network) detail page; falls back to the list when a label has no group id. */
export const campaignHref = (id: string | null | undefined): string =>
  id ? `/campaigns/${encodeURIComponent(id)}` : "/campaigns";

/** Investigation graph focused on one group. */
export const graphFocusHref = (id: string): string => `/graph?campaign=${encodeURIComponent(id)}`;
