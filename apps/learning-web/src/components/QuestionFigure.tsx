/**
 * Renders the figure a family-C question is about (D-279).
 *
 * Deterministic SVG computed from the same structured spec the backend gate verified —
 * there is no image to fetch, nothing to store, and the same spec always draws the same
 * picture. That is the whole reason figures are data here rather than generated images:
 * every other part of an item is checked, and an image would have been the one part nobody
 * could check.
 *
 * Everything is drawn in a 0–100 viewBox and scaled by CSS, so the figure is crisp at any
 * size and readable on a phone without a second breakpoint.
 */

export type ClockFigure = { kind: 'clock'; hour: number; minute: number }
export type BarChartFigure = {
  kind: 'bar_chart'
  title: string
  axis_label: string
  categories: string[]
  values: number[]
}
export type ShapeFigure = {
  kind: 'shape'
  shape: 'triangle' | 'rectangle' | 'parallelogram' | 'trapezoid' | 'circle'
  side_lengths: number[]
  angle_degrees: number[]
  unit: string
}
export type CoordinateGridFigure = {
  kind: 'coordinate_grid'
  x_range: [number, number]
  y_range: [number, number]
  points: [number, number][]
  point_labels: string[]
  segments: [number, number][]
}
export type FigureSpec =
  | ClockFigure
  | BarChartFigure
  | ShapeFigure
  | CoordinateGridFigure

const STROKE = 'currentColor'

function Clock({ hour, minute }: ClockFigure) {
  // Both hands from the same clock arithmetic the spec states, so the drawing cannot
  // disagree with the numbers the gate checked. The hour hand advances *within* the hour,
  // which is what makes "the hour hand has moved past 3" readable at 3:45 — drawing it on
  // the 3 would make the question harder than it is meant to be.
  const minuteAngle = (minute / 60) * 360
  const hourAngle = ((hour % 12) / 12) * 360 + (minute / 60) * 30
  const hand = (angle: number, length: number, width: number) => {
    const radians = ((angle - 90) * Math.PI) / 180
    return (
      <line
        x1={50}
        y1={50}
        x2={50 + length * Math.cos(radians)}
        y2={50 + length * Math.sin(radians)}
        stroke={STROKE}
        strokeWidth={width}
        strokeLinecap="round"
      />
    )
  }
  return (
    <svg viewBox="0 0 100 100" role="img" aria-label={`A clock showing ${hour}:${String(minute).padStart(2, '0')}`}>
      <circle cx={50} cy={50} r={46} fill="none" stroke={STROKE} strokeWidth={2} />
      {Array.from({ length: 12 }, (_, i) => {
        const radians = ((i * 30 - 90) * Math.PI) / 180
        return (
          <text
            key={i}
            x={50 + 38 * Math.cos(radians)}
            y={50 + 38 * Math.sin(radians)}
            textAnchor="middle"
            dominantBaseline="central"
            fontSize={9}
            fill={STROKE}
          >
            {i === 0 ? 12 : i}
          </text>
        )
      })}
      {Array.from({ length: 60 }, (_, i) => {
        const radians = ((i * 6 - 90) * Math.PI) / 180
        const inner = i % 5 === 0 ? 44 : 45.5
        return (
          <line
            key={i}
            x1={50 + inner * Math.cos(radians)}
            y1={50 + inner * Math.sin(radians)}
            x2={50 + 46 * Math.cos(radians)}
            y2={50 + 46 * Math.sin(radians)}
            stroke={STROKE}
            strokeWidth={i % 5 === 0 ? 1.2 : 0.5}
          />
        )
      })}
      {hand(hourAngle, 22, 3.2)}
      {hand(minuteAngle, 32, 2)}
      <circle cx={50} cy={50} r={2} fill={STROKE} />
    </svg>
  )
}

function BarChart({ title, axis_label, categories, values }: BarChartFigure) {
  const max = Math.max(...values, 1)
  const width = 100
  const height = 70
  const slot = width / categories.length
  const barWidth = slot * 0.6
  return (
    <figure className="question-figure__chart">
      {title ? <figcaption>{title}</figcaption> : null}
      <svg viewBox="0 0 100 88" role="img" aria-label={`Bar chart: ${categories
        .map((c, i) => `${c} ${values[i]}`)
        .join(', ')}`}>
        <line x1={0} y1={height} x2={width} y2={height} stroke={STROKE} strokeWidth={1} />
        {values.map((value, i) => {
          const barHeight = (value / max) * (height - 8)
          const x = i * slot + (slot - barWidth) / 2
          return (
            <g key={categories[i]}>
              <rect
                x={x}
                y={height - barHeight}
                width={barWidth}
                height={barHeight}
                fill="currentColor"
                opacity={0.75}
              />
              <text
                x={x + barWidth / 2}
                y={height - barHeight - 2}
                textAnchor="middle"
                fontSize={6}
                fill={STROKE}
              >
                {value}
              </text>
              <text
                x={x + barWidth / 2}
                y={height + 8}
                textAnchor="middle"
                fontSize={6}
                fill={STROKE}
              >
                {categories[i]}
              </text>
            </g>
          )
        })}
        {axis_label ? (
          <text x={0} y={86} fontSize={5} fill={STROKE}>
            {axis_label}
          </text>
        ) : null}
      </svg>
    </figure>
  )
}

function Shape({ shape, side_lengths, unit }: ShapeFigure) {
  // Drawn to the proportions the numbers give, so a 3-4-5 triangle looks like one and the
  // picture cannot contradict its own labels.
  const label = (value: number) => `${value}${unit ? ` ${unit}` : ''}`
  const aria = `A ${shape} labelled ${side_lengths.map(label).join(', ')}`

  if (shape === 'circle') {
    const r = 34
    return (
      <svg viewBox="0 0 100 100" role="img" aria-label={aria}>
        <circle cx={50} cy={50} r={r} fill="none" stroke={STROKE} strokeWidth={2} />
        <line x1={50} y1={50} x2={50 + r} y2={50} stroke={STROKE} strokeWidth={1.2} strokeDasharray="3 2" />
        <circle cx={50} cy={50} r={1.5} fill={STROKE} />
        <text x={50 + r / 2} y={46} textAnchor="middle" fontSize={7} fill={STROKE}>
          {label(side_lengths[0])}
        </text>
      </svg>
    )
  }

  const [a = 1, b = 1, c = 1] = side_lengths
  let points: [number, number][]
  if (shape === 'rectangle') {
    const scale = 70 / Math.max(a, b)
    const w = a * scale
    const h = b * scale
    points = [
      [50 - w / 2, 50 - h / 2],
      [50 + w / 2, 50 - h / 2],
      [50 + w / 2, 50 + h / 2],
      [50 - w / 2, 50 + h / 2],
    ]
  } else if (shape === 'parallelogram') {
    const scale = 60 / Math.max(a, b)
    const w = a * scale
    const h = b * scale
    points = [
      [50 - w / 2 + 10, 50 - h / 2],
      [50 + w / 2 + 10, 50 - h / 2],
      [50 + w / 2 - 10, 50 + h / 2],
      [50 - w / 2 - 10, 50 + h / 2],
    ]
  } else if (shape === 'trapezoid') {
    const scale = 60 / Math.max(a, b, c)
    const top = a * scale
    const bottom = b * scale
    const h = c * scale
    points = [
      [50 - top / 2, 50 - h / 2],
      [50 + top / 2, 50 - h / 2],
      [50 + bottom / 2, 50 + h / 2],
      [50 - bottom / 2, 50 + h / 2],
    ]
  } else {
    // Triangle placed from its actual side lengths, so a right triangle looks right.
    const scale = 60 / Math.max(a, b, c)
    const A: [number, number] = [20, 80]
    const B: [number, number] = [20 + a * scale, 80]
    const cosA = (a * a + c * c - b * b) / (2 * a * c || 1)
    const angle = Math.acos(Math.max(-1, Math.min(1, cosA)))
    const C: [number, number] = [
      20 + c * scale * Math.cos(angle),
      80 - c * scale * Math.sin(angle),
    ]
    points = [A, B, C]
  }

  return (
    <svg viewBox="0 0 100 100" role="img" aria-label={aria}>
      <polygon
        points={points.map(([x, y]) => `${x},${y}`).join(' ')}
        fill="currentColor"
        fillOpacity={0.08}
        stroke={STROKE}
        strokeWidth={2}
      />
      {points.map(([x, y], i) => {
        const [nx, ny] = points[(i + 1) % points.length]
        const value = side_lengths[i]
        if (value === undefined) return null
        return (
          <text
            key={i}
            x={(x + nx) / 2}
            y={(y + ny) / 2 - 2}
            textAnchor="middle"
            fontSize={7}
            fill={STROKE}
          >
            {label(value)}
          </text>
        )
      })}
    </svg>
  )
}

function CoordinateGrid({
  x_range,
  y_range,
  points,
  point_labels,
  segments,
}: CoordinateGridFigure) {
  const [x0, x1] = x_range
  const [y0, y1] = y_range
  const sx = (x: number) => ((x - x0) / (x1 - x0)) * 100
  const sy = (y: number) => 100 - ((y - y0) / (y1 - y0)) * 100
  const lines = []
  for (let x = x0; x <= x1; x += 1) lines.push(<line key={`v${x}`} x1={sx(x)} y1={0} x2={sx(x)} y2={100} stroke={STROKE} strokeWidth={0.3} opacity={0.35} />)
  for (let y = y0; y <= y1; y += 1) lines.push(<line key={`h${y}`} x1={0} y1={sy(y)} x2={100} y2={sy(y)} stroke={STROKE} strokeWidth={0.3} opacity={0.35} />)
  return (
    <svg
      viewBox="0 0 100 100"
      role="img"
      aria-label={`Coordinate grid with ${points
        .map((p, i) => `${point_labels[i] ?? ''} at ${p[0]}, ${p[1]}`)
        .join('; ')}`}
    >
      {lines}
      <line x1={0} y1={sy(0)} x2={100} y2={sy(0)} stroke={STROKE} strokeWidth={1.2} />
      <line x1={sx(0)} y1={0} x2={sx(0)} y2={100} stroke={STROKE} strokeWidth={1.2} />
      {segments.map(([i, j], n) => (
        <line
          key={n}
          x1={sx(points[i][0])}
          y1={sy(points[i][1])}
          x2={sx(points[j][0])}
          y2={sy(points[j][1])}
          stroke={STROKE}
          strokeWidth={1.5}
        />
      ))}
      {points.map(([x, y], i) => (
        <g key={i}>
          <circle cx={sx(x)} cy={sy(y)} r={2} fill={STROKE} />
          <text x={sx(x) + 3} y={sy(y) - 3} fontSize={7} fill={STROKE}>
            {point_labels[i] ?? ''}
          </text>
        </g>
      ))}
    </svg>
  )
}

export function QuestionFigure({ figure }: { figure: FigureSpec | null | undefined }) {
  if (!figure) return null
  return (
    <div className="question-figure" data-figure-kind={figure.kind}>
      {figure.kind === 'clock' ? <Clock {...figure} /> : null}
      {figure.kind === 'bar_chart' ? <BarChart {...figure} /> : null}
      {figure.kind === 'shape' ? <Shape {...figure} /> : null}
      {figure.kind === 'coordinate_grid' ? <CoordinateGrid {...figure} /> : null}
    </div>
  )
}
