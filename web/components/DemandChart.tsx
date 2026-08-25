'use client'

import { useState, useMemo } from 'react'
import {
  ComposedChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ReferenceLine, ReferenceArea, ResponsiveContainer,
} from 'recharts'
import type { DemandData } from '@/lib/types'

const ZONE_COLOURS: Record<string, string> = {
  Z1: '#3B82F6', Z2: '#60A5FA', Z3: '#1D4ED8', Z4: '#93C5FD',
  Z5: '#F97316', Z6: '#EA580C', Z7: '#FED7AA',
}

function shortDate(iso: string) {
  return iso.slice(5) // MM-DD
}

export default function DemandChart({ data }: { data: DemandData }) {
  const hubs = useMemo(() => {
    const seen = new Set<string>()
    return data.zones.reduce<string[]>((acc, z) => {
      if (!seen.has(z.hub)) { seen.add(z.hub); acc.push(z.hub) }
      return acc
    }, [])
  }, [data.zones])

  const [selectedHub, setSelectedHub] = useState(hubs[0])

  const hubZones = data.zones.filter(z => z.hub === selectedHub)
  const histEnd = data.history.at(-1)?.date ?? ''

  // Build chart series: one row per date, columns per zone (history + forecast combined)
  const chartData = useMemo(() => {
    const byDate = new Map<string, Record<string, number>>()

    for (const r of data.history) {
      if (!hubZones.find(z => z.id === r.zone_id)) continue
      const row = byDate.get(r.date) ?? {}
      row[r.zone_id] = r.demand
      byDate.set(r.date, row)
    }
    for (const r of data.forecasts) {
      if (!hubZones.find(z => z.id === r.zone_id)) continue
      const row = byDate.get(r.date) ?? {}
      row[`${r.zone_id}_fc`] = r.forecast_demand
      byDate.set(r.date, row)
    }

    return Array.from(byDate.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, vals]) => ({ date: shortDate(date), ...vals }))
  }, [data, hubZones])

  return (
    <section>
      <h2 className="text-lg font-semibold text-gray-800 mb-1">Demand &amp; Forecast</h2>
      <p className="text-sm text-gray-400 mb-4">
        Historical demand (solid) + 14-day Holt-Winters forecast (dashed) per zone
      </p>

      {/* Hub selector */}
      <div className="flex gap-2 mb-4">
        {hubs.map(h => (
          <button
            key={h}
            onClick={() => setSelectedHub(h)}
            className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
              selectedHub === h
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {h.replace('HUB_', '').replace('_', ' ')} Hub
          </button>
        ))}
      </div>

      <div className="bg-white border border-gray-100 rounded-xl p-4 shadow-sm">
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
              tickFormatter={v => `${(v / 1000).toFixed(1)}k`}
              label={{ value: 'Parcels/day', angle: -90, position: 'insideLeft', offset: 10, style: { fontSize: 11, fill: '#9CA3AF' } }}
            />
            <Tooltip
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              formatter={(v: any, name: any) => [
                typeof v === 'number' ? v.toLocaleString() : String(v),
                typeof name === 'string' && name.endsWith('_fc')
                  ? `${name.replace('_fc', '')} (forecast)`
                  : String(name),
              ]}
              contentStyle={{ fontSize: 12 }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />

            {/* Forecast shading */}
            <ReferenceArea
              x1={shortDate(histEnd)}
              fill="#F3F4F6"
              opacity={0.6}
              label={{ value: 'Forecast →', position: 'insideTopLeft', fontSize: 11, fill: '#9CA3AF' }}
            />
            <ReferenceLine x={shortDate(histEnd)} stroke="#D1D5DB" strokeDasharray="4 2" />

            {hubZones.map(z => (
              <>
                <Line
                  key={z.id}
                  type="monotone"
                  dataKey={z.id}
                  name={z.name}
                  stroke={ZONE_COLOURS[z.id] ?? '#6B7280'}
                  strokeWidth={1.8}
                  dot={false}
                  legendType="line"
                />
                <Line
                  key={`${z.id}_fc`}
                  type="monotone"
                  dataKey={`${z.id}_fc`}
                  name={`${z.name} (forecast)`}
                  stroke={ZONE_COLOURS[z.id] ?? '#6B7280'}
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
    </section>
  )
}
