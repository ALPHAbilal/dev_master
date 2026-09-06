export function editKey(
  value: string,
  start: number,
  end: number,
  key: string,
  shift: boolean,
): { value: string; start: number; end: number } | null {
  const indent = "    ";
  if (key === "Enter") {
    const line = value.lastIndexOf("\n", start - 1) + 1,
      leading = value.slice(line, start).match(/^[ \t]*/)?.[0] || "";
    const insertion =
      "\n" +
      leading +
      (value.slice(0, start).trimEnd().endsWith(":") ? indent : "");
    return {
      value: value.slice(0, start) + insertion + value.slice(end),
      start: start + insertion.length,
      end: start + insertion.length,
    };
  }
  if (key !== "Tab") return null;
  if (start === end && !shift)
    return {
      value: value.slice(0, start) + indent + value.slice(end),
      start: start + 4,
      end: start + 4,
    };
  const first = value.lastIndexOf("\n", start - 1) + 1,
    starts = [first];
  for (let i = first; i < end; i++)
    if (value[i] === "\n" && i + 1 < end) starts.push(i + 1);
  let result = value,
    before = 0,
    removed = 0;
  for (const at of starts.toReversed()) {
    if (shift) {
      const count =
        result[at] === "\t" ? 1 : result.slice(at).match(/^ {0,4}/)![0].length;
      result = result.slice(0, at) + result.slice(at + count);
      if (at < start) before += Math.min(count, start - at);
      removed += count;
    } else result = result.slice(0, at) + indent + result.slice(at);
  }
  return {
    value: result,
    start: shift ? Math.max(first, start - before) : start + 4,
    end: shift ? Math.max(first, end - removed) : end + starts.length * 4,
  };
}
