import type { JSX } from 'react'

import type { Message } from '../conversation/machine'
import { color, type ChannelTheme } from '../theme'

/**
 * One message in the thread, painted in the active channel's style. The
 * conversation content is identical across channels; only the skin differs.
 */
export function Bubble({ message, theme }: { message: Message; theme: ChannelTheme }) {
  const outgoing = message.from === 'worker'
  const bare = message.kind === 'summary'

  return (
    <div className={`cc-rise flex flex-col ${outgoing ? 'items-end' : 'items-start'}`}>
      {message.kind === 'text' && message.sample && <SampleTag />}
      <div
        className={bare ? '' : 'max-w-[78%] px-3.5 py-2'}
        style={
          bare
            ? undefined
            : {
                background: outgoing ? theme.outgoingBg : theme.incomingBg,
                color: outgoing ? theme.outgoingFg : theme.incomingFg,
                borderRadius: theme.radius,
                boxShadow: '0 1px 1px rgba(0,0,0,0.06)',
              }
        }
      >
        {renderBody(message)}
      </div>
    </div>
  )
}

function renderBody(message: Message): JSX.Element {
  switch (message.kind) {
    case 'text':
      return (
        <p className="text-[15px] leading-[1.35] whitespace-pre-wrap">
          {highlightExposure(message.text)}
        </p>
      )
    case 'file':
      return <AttachedFile name={message.name} url={message.url} isImage={message.isImage} />
    case 'summary':
      return <SummaryCard rows={message.rows} />
  }
}

/**
 * Renders the bracketed exposure phrase in Signal Orange.
 *
 * The orange is load-bearing: it marks how bad conditions are and is used
 * nowhere else in the thread. What it marks is a phrase a worker can act on
 * ("hotter than usual"), not a severity code — the colour carries the signal
 * so the sentence does not have to carry a number.
 */
function highlightExposure(text: string) {
  const parts = text.split(/\[([^\]]+)\]/)
  return parts.map((part, i) =>
    i % 2 === 1 ? (
      <strong key={i} style={{ color: color.exposure }} className="font-bold">
        {part}
      </strong>
    ) : (
      <span key={i}>{part}</span>
    ),
  )
}

/**
 * An attached document, shown back as an acknowledgement.
 *
 * The contents are never read, parsed or described. A PDF shows as a named
 * chip; an image shows as a thumbnail — because the worker already knows what
 * they sent, and CrewCare's job is to confirm receipt, not to interpret it.
 */
function AttachedFile({ name, url, isImage }: { name: string; url: string; isImage: boolean }) {
  if (isImage) {
    return (
      <figure className="w-[180px]">
        <img src={url} alt="" className="block w-full rounded-lg border border-black/10" />
        <figcaption className="truncate pt-1 text-[12px] opacity-80">{name}</figcaption>
      </figure>
    )
  }
  return (
    <span className="flex max-w-[210px] items-center gap-2">
      <svg viewBox="0 0 16 18" aria-hidden="true" className="h-5 w-4 shrink-0 fill-none stroke-current stroke-[1.3]">
        <path d="M2 1.5h7L14 6v10.5H2z" />
        <path d="M9 1.5V6h5" />
      </svg>
      <span className="truncate text-[14px] font-semibold">{name}</span>
    </span>
  )
}

function SampleTag() {
  return (
    <span className="mb-1 rounded bg-black/8 px-1.5 py-0.5 text-[10px] font-bold tracking-widest text-cc-grey uppercase">
      sample
    </span>
  )
}

function SummaryCard({ rows }: { rows: { label: string; value: string }[] }) {
  return (
    <div className="w-[300px] overflow-hidden rounded-xl border border-black/10 bg-white">
      <div className="bg-cc-primary px-3.5 py-2.5">
        <p className="text-[14px] font-bold text-white">What you shared</p>
        <p className="text-[12px] text-white/70">Held in this tab only</p>
      </div>
      <dl className="divide-y divide-black/5">
        {rows.map((row) => (
          <div key={row.label} className="px-3.5 py-2">
            <dt className="text-[11px] font-semibold tracking-wide text-cc-grey uppercase">
              {row.label}
            </dt>
            <dd className="text-[14px] font-semibold text-cc-primary">{row.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
