import { fetchSummary, fetchDemand, fetchMigration } from '@/lib/api'
import NetworkSnapshot from '@/components/NetworkSnapshot'
import DemandChart from '@/components/DemandChart'
import MigrationSection from '@/components/MigrationSection'

export default async function Page() {
  const [summary, demand, migration] = await Promise.all([
    fetchSummary(),
    fetchDemand(),
    fetchMigration(),
  ])

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-12">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-gray-900">📦 ConstraintIQ</h1>
        <p className="mt-1 text-sm text-gray-500">
          Predictive constraint-migration detection · last-mile logistics · proof-of-concept
        </p>
        <div className="mt-3 rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 text-sm text-amber-800">
          <span className="font-semibold">⚠ Synthetic data prototype</span> — not connected to any live
          logistics network. Data is generated from parameterised demand models (trend + weekly
          seasonality + noise).
        </div>
      </div>

      <div className="w-full border-t border-gray-200" />
      <NetworkSnapshot data={summary} />

      <div className="w-full border-t border-gray-200" />
      <DemandChart data={demand} />

      <div className="w-full border-t border-gray-200" />
      <MigrationSection data={migration} />

      <div className="w-full border-t border-gray-200" />
      <footer className="text-xs text-gray-400 text-center pb-4">
        ConstraintIQ · proof-of-concept · synthetic data · Theory of Constraints + Holt-Winters demand forecasting
      </footer>
    </main>
  )
}
