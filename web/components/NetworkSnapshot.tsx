'use client'

import type { Hub, SummaryData } from '@/lib/types'

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

function ConstraintBadge({ is_hard, is_soft }: { is_hard: boolean; is_soft: boolean }) {
  if (is_hard) return (
    <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-red-100 text-red-700 border border-red-200">
      HARD
    </span>
  )
  if (is_soft) return (
    <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 border border-amber-200">
      SOFT
    </span>
  )
  return (
    <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-600 border border-emerald-200">
      OK
    </span>
  )
}

function CapacityBar({ hub }: { hub: Hub }) {
  const { load, base_capacity, surge_available, max_surge_capacity, is_hard, is_soft } = hub
  const scale = base_capacity + max_surge_capacity

  const pct = (v: number) => `${Math.min((v / scale) * 100, 100).toFixed(2)}%`

  const loadColour = is_hard ? DANGER : is_soft ? WARNING : OK

  return (
    <div className="mt-3">
      {/* Legend */}
      <div className="flex gap-4 text-xs text-gray-400 mb-1.5">
        <span className="flex items-center gap-1">
          <span className="inline-block w-2.5 h-2.5 rounded-sm bg-blue-200 border border-blue-300" />
          Base ({(base_capacity / 1000).toFixed(0)}k)
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-2.5 h-2.5 rounded-sm bg-amber-200 border border-amber-300" />
          Surge ({(max_surge_capacity / 1000).toFixed(0)}k max)
        </span>
      </div>

      {/* Stacked track */}
      <div className="relative h-4 rounded-full overflow-hidden bg-gray-100">
        {/* Base zone */}
        <div className="absolute inset-y-0 left-0 bg-blue-100" style={{ width: pct(base_capacity) }} />
        {/* Surge available zone */}
        <div
          className="absolute inset-y-0 bg-amber-100"
          style={{ left: pct(base_capacity), width: pct(surge_available) }}
        />
        {/* Load fill */}
        <div
          className="absolute inset-y-0 left-0 opacity-80 transition-all duration-300"
          style={{ width: pct(load), background: loadColour }}
        />
        {/* Base / surge divider */}
        <div
          className="absolute inset-y-0 w-px bg-blue-400 z-10"
          style={{ left: pct(base_capacity) }}
        />
      </div>

      {/* Foot labels */}
      <div className="flex justify-between text-xs text-gray-400 mt-0.5">
        <span style={{ color: loadColour }} className="font-medium">
          {load.toLocaleString()} load
        </span>
        <span className="text-gray-400">
          {base_capacity.toLocaleString()} base · {(base_capacity + max_surge_capacity).toLocaleString()} max
        </span>
      </div>
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
          colour={binding_constraint.is_hard ? DANGER : binding_constraint.is_soft ? WARNING : OK}
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
            {/* Card header */}
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-gray-800">{hub.name}</h3>
                <ConstraintBadge is_hard={hub.is_hard} is_soft={hub.is_soft} />
              </div>
              <span
                className="text-sm font-bold px-2 py-0.5 rounded-full"
                style={{ background: `${utilColour(hub.utilization)}20`, color: utilColour(hub.utilization) }}
              >
                {(hub.utilization * 100).toFixed(1)}%
              </span>
            </div>

            {/* Surge cost index */}
            <p className="text-xs text-gray-400 mb-0.5">
              Surge cost index:{' '}
              <span
                className="font-semibold"
                style={{ color: hub.surge_cost_multiplier >= 2.5 ? DANGER : hub.surge_cost_multiplier >= 1.5 ? WARNING : OK }}
              >
                {hub.surge_cost_multiplier.toFixed(2)}×
              </span>
              {' '}(worst-case notice)
            </p>

            {/* Stacked capacity bar */}
            <CapacityBar hub={hub} />

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
