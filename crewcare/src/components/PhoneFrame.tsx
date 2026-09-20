import { PHONE } from '../theme'

/**
 * 402×874 device shell. The whole worker path renders inside one of these,
 * including the sign-in screen.
 */
export function PhoneFrame({
  children,
  statusBarFg = '#000000',
}: {
  children: React.ReactNode
  statusBarFg?: string
}) {
  return (
    <div
      className="relative shrink-0 rounded-[52px] bg-cc-primary p-[10px] shadow-[0_30px_70px_-20px_rgba(0,26,87,0.45)]"
      style={{ width: PHONE.width + 20, height: PHONE.height + 20 }}
    >
      <div
        className="relative flex flex-col overflow-hidden rounded-[44px] bg-white"
        style={{ width: PHONE.width, height: PHONE.height }}
      >
        <StatusBar fg={statusBarFg} />
        <div className="flex min-h-0 flex-1 flex-col">{children}</div>
      </div>
    </div>
  )
}

function StatusBar({ fg }: { fg: string }) {
  return (
    <div
      className="pointer-events-none absolute inset-x-0 top-0 z-20 flex h-[44px] items-center justify-between px-8 text-[14px] font-semibold"
      style={{ color: fg }}
    >
      <span>9:41</span>
      <div className="absolute left-1/2 top-[8px] h-[26px] w-[110px] -translate-x-1/2 rounded-full bg-black" />
      <span className="flex items-center gap-1.5" aria-hidden="true">
        <svg viewBox="0 0 18 12" className="h-3 w-[18px] fill-current">
          <rect x="0" y="8" width="3" height="4" rx="1" />
          <rect x="5" y="5.5" width="3" height="6.5" rx="1" />
          <rect x="10" y="3" width="3" height="9" rx="1" />
          <rect x="15" y="0.5" width="3" height="11.5" rx="1" />
        </svg>
        <svg viewBox="0 0 16 12" className="h-3 w-4 fill-current">
          <path d="M8 11.2 5.6 8.6a3.5 3.5 0 0 1 4.8 0L8 11.2Zm-4-4.4a7 7 0 0 1 8 0l-1.3 1.4a5.2 5.2 0 0 0-5.4 0L4 6.8Zm-2.2-2.4a10.2 10.2 0 0 1 12.4 0l-1.3 1.4a8.4 8.4 0 0 0-9.8 0L1.8 4.4Z" />
        </svg>
        <svg viewBox="0 0 26 12" className="h-3 w-[26px]">
          <rect x="0.5" y="0.5" width="21" height="11" rx="3.2" fill="none" stroke="currentColor" opacity="0.4" />
          <rect x="2" y="2" width="16" height="8" rx="2" fill="currentColor" />
          <path d="M23.5 4v4a2.2 2.2 0 0 0 0-4Z" fill="currentColor" opacity="0.4" />
        </svg>
      </span>
    </div>
  )
}
