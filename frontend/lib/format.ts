export function fmtMoney(
  value: number,
  opts: { signDisplay?: boolean } = {}
): string {
  const sign = opts.signDisplay && value > 0 ? "+" : "";

  return (
    sign +
    value.toLocaleString("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    })
  );
}

export function fmtMoneyPrecise(value: number): string {
  return value.toLocaleString("en-IN", {
    style: "currency",
    currency: "INR",
  });
}

export function fmtPct(
  value: number,
  opts: { signDisplay?: boolean } = {}
): string {
  const sign = opts.signDisplay && value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}