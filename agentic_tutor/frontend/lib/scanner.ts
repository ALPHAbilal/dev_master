export interface SourceHighlight {
  /** Inclusive, one-based source line range. Array order is reading order. */
  label: string;
  file: string;
  lo: number;
  hi: number;
  annotation: string;
  excerpt?: string;
}
export interface StationSource {
  /** Primary anchor, retained for older scan responses. */
  file: string;
  lo: number;
  hi: number;
  /** Canonical source ranges; may span multiple files. */
  highlights?: SourceHighlight[];
  contract?: StationContract;
}
export function stationHighlights(station: StationSource): SourceHighlight[] {
  // Nested highlights are supported for the first contract-based scanner preview.
  return station.highlights ?? station.contract?.highlights ?? [{
    file: station.file, lo: station.lo, hi: station.hi,
    label: 'Source', annotation: '',
  }];
}
export interface AxisContract {
  axis: string;
  objective: string;
  probe: string;
  evidence: string;
}
export interface StationContract {
  question: string;
  target: string;
  prerequisites: string[];
  scope: string;
  highlights: SourceHighlight[];
  axes: AxisContract[];
  misconceptions: string[];
}
export interface BatchSettings {
  initial: number;
  next: number;
  remaining: number;
  automatic: boolean;
}
export const defaultBatchSettings: BatchSettings = { initial: 3, next: 3, remaining: 1, automatic: true };
export function parseBatchSettings(value: unknown): BatchSettings {
  const v = (value && typeof value === 'object' ? value : {}) as Partial<BatchSettings>;
  const integer = (n: unknown, fallback: number, max: number, min = 1) => typeof n === 'number' && Number.isFinite(n) ? Math.max(min, Math.min(max, Math.trunc(n))) : fallback;
  return { initial: integer(v.initial, 3, 3), next: integer(v.next, 3, 50), remaining: integer(v.remaining, 1, 50, 0), automatic: typeof v.automatic === 'boolean' ? v.automatic : true };
}
export function batchStorageKey(user: string, codebase: string) {
  return `scanner-batches:${JSON.stringify([user, codebase])}`;
}
