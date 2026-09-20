import {
  MATERIAL_ICONS,
  MATERIAL_VIEWBOX,
  type MaterialIconName,
} from './materialIcons'

/**
 * A Material Symbols glyph, inlined.
 *
 * Decorative by default: the nav items these sit beside carry their own
 * visible labels, so announcing the icon too would just read everything
 * twice. Pass a `title` where an icon stands alone.
 */
export function MaterialIcon({
  name,
  size = 20,
  title,
  className,
}: {
  name: MaterialIconName
  size?: number
  title?: string
  className?: string
}) {
  return (
    <svg
      viewBox={MATERIAL_VIEWBOX}
      width={size}
      height={size}
      className={className}
      fill="currentColor"
      role={title ? 'img' : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
    >
      {title && <title>{title}</title>}
      <path d={MATERIAL_ICONS[name]} />
    </svg>
  )
}

export type { MaterialIconName }
