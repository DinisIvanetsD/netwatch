export function escapeCsvCell(value: unknown): string {
  const raw = value == null ? "" : String(value);
  // Spreadsheet applications may evaluate cells beginning with these
  // characters as formulas. Prefix suspicious text, including control
  // characters commonly used to hide the real first character.
  const text = /^[\s]*[=+\-@]/.test(raw) ? `'${raw}` : raw;
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

export function toCsv<T extends object>(
  rows: T[],
  columns: Array<{ key: keyof T; label: string }>,
): string {
  const header = columns.map(({ label }) => escapeCsvCell(label)).join(",");
  const body = rows.map((row) =>
    columns.map(({ key }) => escapeCsvCell(row[key])).join(","),
  );
  return [header, ...body].join("\r\n") + "\r\n";
}
