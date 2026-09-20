import type { ChannelTheme } from '../theme'

export type Reply = { id: string; label: string }

/**
 * Quick-reply chips. A skip chip, when offered, sits last and is styled apart
 * from the answers so declining never looks like the reluctant option.
 */
export function QuickReplies({
  theme,
  replies,
  onPick,
  onSkip,
  skipLabel = 'Skip',
}: {
  theme: ChannelTheme
  replies: Reply[]
  onPick: (id: string) => void
  onSkip?: () => void
  skipLabel?: string
}) {
  return (
    <div className="flex flex-wrap justify-end gap-2">
      {replies.map((reply) => (
        <button
          key={reply.id}
          type="button"
          onClick={() => onPick(reply.id)}
          className="rounded-full border px-3.5 py-2 text-[14px] font-semibold transition active:scale-[0.97]"
          style={{
            borderColor: theme.outgoingBg,
            color: theme.outgoingBg === '#D9FDD3' ? '#0F7A5A' : theme.outgoingBg,
            background: '#FFFFFF',
          }}
        >
          {reply.label}
        </button>
      ))}
      {onSkip && (
        <button
          type="button"
          onClick={onSkip}
          className="rounded-full border border-transparent px-3.5 py-2 text-[14px] font-semibold text-cc-grey underline decoration-cc-grey/40 underline-offset-2"
        >
          {skipLabel}
        </button>
      )}
    </div>
  )
}
