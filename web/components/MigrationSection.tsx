'use client'

import { useMemo } from 'react'
import {
  ComposedChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ReferenceLine, ReferenceArea, ResponsiveContainer,
} from 'recharts'
import type { MigrationData } from '@/lib/types'

const HUB_COLOURS: Record<string, string> = {
  HUB_NORTH: '#3B82F6',
  HUB_SOUTH: '#F97316',
}

function shortDate(iso: string) {
  return iso.slice(5) // MM-DD
}

function labelHub(id: string) {
  return id.replace('HUB_', '').replace('_', ' ') + ' Hub'
}

export default function MigrationSection({ data }: { data: MigrationData }) {
  const { historical_events, forecast_events, utilization_history, projected_utilization } = data

  const hubs = useMemo(
    () => [...new Set(utilization_history.map(r => r.resource_id))],
    [utilization_history],
  )

  const histEnd = utilization_history.at(-1)?.date ?? ''

  // Merge history + projected into a single chart series
  const chartData = useMemo(() => {
    const byDate = new Map<string, Record<string, number>>()

    for (const r of utilization_history) {
      const row = byDate.get(r.date) ?? {}
      row[r.resource_id] = parseFloat((r.utilization * 100).toFixed(1))
      byDate.set(r.date, row)
    }
    for (const r of projected_utilization) {
      const row = byDate.get(r.date) ?? {}
      row[`${r.resource_id}_proj`] = parseFloat((r.utilization * 100).toFixed(1))
      byDate.set(r.date, row)
    }

    return Array.from(byDate.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, vals]) => ({ date: shortDate(date), fullDate: date, ...vals }))
  }, [utilization_history, projected_utilization])

  // Find chart points for migration markers
  const migrationXs = historical_events.map(e => shortDate(e.day))

  return (
    <section>
      <h2 className="text-lg font-semibold text-gray-800 mb-1">Constraint Migration</h2>
      <p className="text-sm text-gray-400 mb-4">
        7-day smoothed hub utilisation (history + 14-day projection). Dashed red = 100% capacity.
      </p>

      <div className="bg-white border border-gray-100 rounded-xl p-4 shadow-sm mb-6">
        <ResponsiveContainer width="100%" height={380}>
          <ComposedChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: '#9CA3AF' }}
              interval={13}
            />
            <YAxis
              tick={{ fontSize: 11, fill: '#9CA3AF' }}
              tickFormatter={v => `${v}%`}
              domain={[0, 160]}
              label={{ value: 'Utilisation (%)', angle: -90, position: 'insideLeft', offset: 10, style: { fontSize: 11, fill: '#9CA3AF' } }}
            />
            <Tooltip
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              formatter={(v: any, name: any) => [
                `${v}%`,
                typeof name === 'string' && name.endsWith('_proj')
                  ? `${labelHub(name.replace('_proj', ''))} (projected)`
                  : labelHub(String(name)),
              ]}
              contentStyle={{ fontSize: 12 }}
            />
            <Legend
              formatter={name =>
                name.endsWith('_proj')
                  ? `${labelHub(name.replace('_proj', ''))} (projected)`
                  : labelHub(name)
              }
              wrapperStyle={{ fontSize: 12 }}
            />

            {/* 100% capacity ceiling */}
            <ReferenceLine y={100} stroke="#EF4444" strokeDasharray="4 2" strokeWidth={1.5}
              label={{ value: '100% capacity', position: 'insideBottomRight', fontSize: 10, fill: '#EF4444' }} />

            {/* Forecast region */}
            <ReferenceArea
              x1={shortDate(histEnd)}
              fill="#F3F4F6"
              opacity={0.6}
              label={{ value: 'Forecast →', position: 'insideTopLeft', fontSize: 11, fill: '#9CA3AF' }}
            />
            <ReferenceLine x={shortDate(histEnd)} stroke="#D1D5DB" strokeDasharray="4 2" />

            {/* Historical migration markers */}
            {migrationXs.map((x, i) => (
              <ReferenceLine
                key={i}
                x={x}
                stroke="#7C3AED"
                strokeDasharray="3 2"
                strokeWidth={1}
                label={{ value: `→ ${labelHub(historical_events[i].to_resource)}`, position: 'top', fontSize: 9, fill: '#7C3AED' }}
              />
            ))}

            {hubs.map(hub => (
              <>
                <Line
                  key={hub}
                  type="monotone"
                  dataKey={hub}
                  name={hub}
                  stroke={HUB_COLOURS[hub] ?? '#6B7280'}
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  key={`${hub}_proj`}
                  type="monotone"
                  dataKey={`${hub}_proj`}
                  name={`${hub}_proj`}
                  stroke={HUB_COLOURS[hub] ?? '#6B7280'}
                  strokeWidth={2}
                  strokeDasharray="5 3"
                  dot={false}
                  legendType="none"
                />
              </>
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Event tables */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Historical */}
        <div className="bg-white border border-gray-100 rounded-xl p-5 shadow-sm">
          <h3 className="font-semibold text-gray-800 mb-3">Historical migration events</h3>
          {historical_events.length > 0 ? (
            <>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-gray-400 border-b border-gray-100">
                    <th className="text-left py-1 font-medium">Date</th>
                    <th className="text-left py-1 font-medium">From</th>
                    <th className="text-left py-1 font-medium">To</th>
                    <th className="text-right py-1 font-medium">Util.</th>
                  </tr>
                </thead>
                <tbody>
                  {historical_events.map((e, i) => (
                    <tr key={i} className="border-b border-gray-50">
                      <td className="py-1.5 text-gray-600">{e.day}</td>
                      <td className="py-1.5 text-gray-600">{e.from_resource.replace('HUB_', '')}</td>
                      <td className="py-1.5 font-medium text-blue-700">{e.to_resource.replace('HUB_', '')}</td>
                      <td className="py-1.5 text-right text-gray-600">{(e.projected_utilization * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-xs text-gray-400 mt-3">
                📌 Constraint settled at{' '}
                <span className="font-medium text-gray-600">
                  {labelHub(historical_events.at(-1)!.to_resource)}
                </span>{' '}
                as Zone 3&apos;s demand trend became decisive.
              </p>
            </>
          ) : (
            <p className="text-sm text-gray-400">No migrations detected in history window.</p>
          )}
        </div>

        {/* Forecast */}
        <div className="bg-white border border-gray-100 rounded-xl p-5 shadow-sm">
          <h3 className="font-semibold text-gray-800 mb-3">Forecast migration events</h3>
          {forecast_events.length > 0 ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-gray-400 border-b border-gray-100">
                  <th className="text-left py-1 font-medium">Date</th>
                  <th className="text-left py-1 font-medium">From</th>
                  <th className="text-left py-1 font-medium">To</th>
                  <th className="text-right py-1 font-medium">Proj. util.</th>
                </tr>
              </thead>
              <tbody>
                {forecast_events.map((e, i) => (
                  <tr key={i} className="border-b border-gray-50">
                    <td className="py-1.5 text-gray-600">{e.day}</td>
                    <td className="py-1.5 text-gray-600">{e.from_resource.replace('HUB_', '')}</td>
                    <td className="py-1.5 font-medium text-orange-600">{e.to_resource.replace('HUB_', '')}</td>
                    <td className="py-1.5 text-right text-gray-600">{(e.projected_utilization * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="rounded-lg bg-emerald-50 border border-emerald-100 p-4">
              <p className="text-sm text-emerald-700 font-medium">
                ✓ No constraint migration expected in the next {data.forecast_events.length === 0 ? '14' : ''} days.
              </p>
              <p className="text-xs text-emerald-600 mt-1">
                North Hub remains the binding constraint — utilisation continues to rise.
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
