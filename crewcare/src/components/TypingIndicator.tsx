import type { ChannelTheme } from '../theme'

/** Three-dot typing bubble, painted in the incoming style of the channel. */
export function TypingIndicator({ theme }: { theme: ChannelTheme }) {
  return (
    <div className="flex justify-start" aria-label="CrewCare is typing">
      <div
        className="cc-rise flex items-center gap-1 px-3.5 py-3"
        style={{
          background: theme.incomingBg,
          borderRadius: theme.radius,
          boxShadow: '0 1px 1px rgba(0,0,0,0.06)',
        }}
      >
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="block h-1.5 w-1.5 rounded-full"
            style={{
              background: theme.incomingFg,
              animation: `cc-typing 1.2s ${i * 0.16}s infinite ease-in-out`,
            }}
          />
        ))}
      </div>
    </div>
  )
}
