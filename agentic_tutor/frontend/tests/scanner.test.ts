import test from 'node:test';
import assert from 'node:assert/strict';
import { batchStorageKey, parseBatchSettings, stationHighlights } from '../lib/scanner';

test('batch preferences isolate both the user and codebase, including delimiter characters', () => {
  const keys = [batchStorageKey('a', 'b:c'), batchStorageKey('a:b', 'c'), batchStorageKey('other', 'b:c'), batchStorageKey('a', 'other')];
  assert.equal(new Set(keys).size, keys.length);
});

test('restored preferences constrain invalid counts and retain the zero-remaining trigger', () => {
  assert.deepEqual(parseBatchSettings({ initial: 99, next: -1, remaining: 0, automatic: false }), { initial: 3, next: 1, remaining: 0, automatic: false });
  assert.deepEqual(parseBatchSettings({ initial: NaN, next: '5', remaining: Infinity }), { initial: 3, next: 3, remaining: 1, automatic: true });
});

test('station sources preserve ordered cross-file ranges and support legacy anchors', () => {
  const anchor = { file: 'main.py', lo: 1, hi: 10 };
  const highlights = [
    { file: 'main.py', lo: 2, hi: 4, label: 'Call', annotation: 'Invocation' },
    { file: 'helper.py', lo: 20, hi: 25, label: 'Implementation', annotation: 'Definition' },
    { file: 'main.py', lo: 8, hi: 9, label: 'Use result', annotation: 'Consumer' },
  ];
  assert.deepEqual(stationHighlights({ ...anchor, highlights }), highlights);
  assert.deepEqual(stationHighlights(anchor), [{ ...anchor, label: 'Source', annotation: '' }]);
  assert.deepEqual(stationHighlights({ ...anchor, highlights: [] }), []);
});
