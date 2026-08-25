'use client'

import type { SummaryData } from '@/lib/types'

const DANGER  = '#EF4444'
const WARNING = '#F59E0B'
const OK      = '#10B981'
const PURPLE  = '#7C3AED'

function utilColour(u: number) {
  if (u >= 1.0) return DANGER
  if (u >= 0.8) return WARNING
  return OK
}

function KpiCard({ label, value, colour }: { label: string; value: string; colour: string }) {
  return (
    <div
      className="rounded-lg px-4 py-3 border-l-4"
      style={{ borderColor: colour, background: `${colour}18` }}
    >
      <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">{label}</p>
      <p className="text-2xl font-bold mt-0.5" style={{ color: colour }}>{value}</p>
    </div>
  )
}

function UtilBar({ utilization }: { utilization: number }) {
  const pct = Math.min(utilization * 100, 160)
  const colour = utilColour(utilization)
  return (
    <div className="mt-2">
      <div className="flex justify-between text-xs text-gray-500 mb-1">
        <span>0%</span>
        <span className="font-semibold" style={{ color: colour }}>{(utilization * 100).toFixed(1)}%</span>
        <span>160%</span>
      </div>
      <div className="relative h-3 bg-gray-100 rounded-full overflow-hidden">
        {/* Colour zones */}
        <div className="absolute inset-y-0 left-0 w-[50%] bg-emerald-100" />
        <div className="absolute inset-y-0 left-[50%] w-[12.5%] bg-amber-100" />
        <div className="absolute inset-y-0 left-[62.5%] right-0 bg-red-100" />
        {/* Capacity marker at 100% */}
        <div className="absolute inset-y-0 left-[62.5%] w-px bg-red-500" />
        {/* Utilisation fill */}
        <div
          className="absolute inset-y-0 left-0 rounded-full transition-all"
          style={{ width: `${(pct / 160) * 100}%`, background: colour }}
        />
      </div>
      <p className="text-xs text-gray-400 mt-0.5">Red line = 100% capacity</p>
    </div>
  )
}

export default function NetworkSnapshot({ data }: { data: SummaryData }) {
  const { hubs, binding_constraint, historical_migration_count, last_date } = data

  return (
    <section>
      <h2 className="text-lg font-semibold text-gray-800 mb-1">Network Snapshot</h2>
      <p className="text-sm text-gray-400 mb-4">Last day of history — {last_date}</p>

      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {hubs.map(h => (
          <KpiCard
            key={h.id}
            label={h.name}
            value={`${(h.utilization * 100).toFixed(0)}% utilised`}
            colour={utilColour(h.utilization)}
          />
        ))}
        <KpiCard
          label="Binding Constraint"
          value={binding_constraint.resource_id.replace('HUB_', '').replace('_', ' ') + ' Hub'}
          colour={binding_constraint.utilization >= 1 ? DANGER : WARNING}
        />
        <KpiCard
          label="Historical Migrations"
          value={String(historical_migration_count)}
          colour={PURPLE}
        />
      </div>

      {/* Hub cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {hubs.map(hub => (
          <div key={hub.id} className="bg-white border border-gray-100 rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between mb-1">
              <h3 className="font-semibold text-gray-800">{hub.name}</h3>
              <span
                className="text-sm font-bold px-2 py-0.5 rounded-full"
                style={{ background: `${utilColour(hub.utilization)}20`, color: utilColour(hub.utilization) }}
              >
                {(hub.utilization * 100).toFixed(1)}%
              </span>
            </div>
            <p className="text-xs text-gray-400 mb-3">
              {hub.load.toLocaleString()} / {hub.capacity.toLocaleString()} parcels/day
            </p>
            <UtilBar utilization={hub.utilization} />

            {/* Zone table */}
            <table className="w-full mt-4 text-sm">
              <thead>
                <tr className="text-xs text-gray-400 border-b border-gray-100">
                  <th className="text-left py-1 font-medium">Zone</th>
                  <th className="text-right py-1 font-medium">Demand</th>
                  <th className="text-right py-1 font-medium">Trend/day</th>
                </tr>
              </thead>
              <tbody>
                {hub.zones.map(z => (
                  <tr key={z.id} className="border-b border-gray-50">
                    <td className="py-1.5 text-gray-700">{z.name}</td>
                    <td className="py-1.5 text-right text-gray-600">
                      {z.demand != null ? z.demand.toLocaleString() : '—'}
                    </td>
                    <td className="py-1.5 text-right" style={{ color: z.trend_per_day > 0 ? OK : DANGER }}>
                      {z.trend_per_day >= 0 ? '+' : ''}{z.trend_per_day}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </section>
  )
}
