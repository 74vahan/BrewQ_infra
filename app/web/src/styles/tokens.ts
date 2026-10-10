/**
 * Reads the colour tokens out of tokens.css (dark = the :root block, light =
 * the :root block inside the prefers-color-scheme: light media query). Only
 * for tests: the app itself uses the CSS file directly.
 */
export type TokenSet = Record<string, string>;

function declarations(block: string): TokenSet {
  const tokens: TokenSet = {};
  for (const match of block.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) {
    if (match[1] && match[2]) tokens[match[1]] = match[2].trim();
  }
  return tokens;
}

export function parseThemes(css: string): { dark: TokenSet; light: TokenSet } {
  const withoutComments = css.replace(/\/\*[\s\S]*?\*\//g, '');
  const mediaStart = withoutComments.indexOf('@media (prefers-color-scheme: light)');
  if (mediaStart < 0) throw new Error('tokens.css has no light theme block');
  const dark = declarations(withoutComments.slice(0, mediaStart));
  const light = { ...dark, ...declarations(withoutComments.slice(mediaStart)) };
  return { dark, light };
}
