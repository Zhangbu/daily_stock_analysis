/**
 * Normalize query string for search/matching.
 * Removes leading/trailing spaces, converts to lowercase, removes internal spaces.
 */
export function normalizeQuery(query: string): string {
  return query
    .normalize('NFKC')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '');
}
