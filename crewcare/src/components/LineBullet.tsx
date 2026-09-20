import { LINE_COLOR } from '../data/mockOperations'

/** A route bullet, in the line's official colour. */
export function LineBullet({ line, size = 22 }: { line: string; size?: number }) {
  const color = LINE_COLOR[line] ?? '#7C858C'
  // The yellow lines are the reason this is not always white text: the MTA
  // standard forbids white knock-out type on yellow.
  const dark = color === '#F6BC26'
  return (
    <span
      className="inline-flex shrink-0 items-center justify-center rounded-full font-bold"
      style={{
        width: size,
        height: size,
        background: color,
        color: dark ? '#111111' : '#FFFFFF',
        fontSize: size * 0.55,
      }}
      aria-label={`Line ${line}`}
    >
      {line}
    </span>
  )
}
