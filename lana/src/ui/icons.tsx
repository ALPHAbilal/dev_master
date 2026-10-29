// Lana's icons: small, stroked, in the text's color. The panel speaks with them instead of words.

const PATHS = {
  arrow: 'M8 13V3.5M4 7.5l4-4 4 4',
  stop: 'M4.5 4.5h7v7h-7z',
  target: 'M8 2.5v2M8 11.5v2M2.5 8h2M11.5 8h2M8 5a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z',
  frame: 'M3 5V3h2M11 3h2v2M13 11v2h-2M5 13H3v-2',
  highlight: 'M3 12.5h10M5 10l5.5-5.5 1.5 1.5L6.5 11.5H5z',
  clear: 'm4.5 4.5 7 7M11.5 4.5l-7 7',
  check: 'm4 8.5 2.5 2.5L12 5.5',
  cross: 'm5 5 6 6M11 5l-6 6',
  ask: 'M3 3.5h10v7H8l-3 2.5v-2.5H3z',
  'eye-off': 'M2.5 8s2-4 5.5-4 5.5 4 5.5 4-2 4-5.5 4-5.5-4-5.5-4ZM3 13 13 3',
  text: 'M3 4h10M3 8h10M3 12h6',
  code: 'M5.5 4.5 2 8l3.5 3.5M10.5 4.5 14 8l-3.5 3.5',
  image: 'M2 3h12v10H2zM3 11l3.5-3.5 2.5 2.5 2-2 2 2',
  table: 'M2 3h12v10H2zM2 6.5h12M6.5 6.5V13',
  search: 'M7 2.75a4.25 4.25 0 1 0 0 8.5 4.25 4.25 0 0 0 0-8.5ZM10.25 10.25 13.5 13.5',
  open: 'M6 4h6v6M12 4l-7.5 7.5',
  keep: 'M4.5 2.5h7v11L8 10.5l-3.5 3z',
  chevron: 'm6 4 4 4-4 4',
  expand: 'M9.5 2.5h4v4M13.5 2.5 9 7M6.5 13.5h-4v-4M2.5 13.5 7 9',
  panel: 'M2.5 3h11v10h-11zM9.5 3v10',
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 16 }: { name: IconName; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name]} />
    </svg>
  );
}
