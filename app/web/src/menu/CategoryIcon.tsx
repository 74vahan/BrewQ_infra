import type { ReactNode } from 'react';

/**
 * Placeholder picture for an item without `image_url` (or whose image failed
 * to load): a simple glyph for the category, so rows keep their rhythm.
 */

const GLYPHS: Record<string, ReactNode> = {
  coffee: (
    <>
      <path d="M5 9h11v5a5 5 0 0 1-5 5H10a5 5 0 0 1-5-5z" />
      <path d="M16 11h1.5a2.5 2.5 0 0 1 0 5H16" />
      <path d="M8 3v2M12 3v2" />
    </>
  ),
  tea: (
    <>
      <path d="M4 10h13v3a6 6 0 0 1-6 6h-1a6 6 0 0 1-6-6z" />
      <path d="M17 11h1a2.5 2.5 0 0 1 0 5h-1" />
      <path d="M9 3c-1 1.5 1 2.5 0 4M13 3c-1 1.5 1 2.5 0 4" />
    </>
  ),
  cake: (
    <>
      <path d="M4 19h16l-1-7H5z" />
      <path d="M7 12V9M12 12V8M17 12V9" />
      <path d="M12 8c-1-1 0-2.5 0-2.5s1 1.5 0 2.5z" />
    </>
  ),
};

/** A plain cup for categories this build does not know. */
const FALLBACK = (
  <>
    <circle cx="12" cy="12" r="8" />
    <path d="M9 12h6" />
  </>
);

export function CategoryIcon({ category, className }: { category: string; className?: string }) {
  return (
    <svg
      className={className}
      width="28"
      height="28"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {GLYPHS[category] ?? FALLBACK}
    </svg>
  );
}
