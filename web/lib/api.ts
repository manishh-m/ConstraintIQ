import type { SummaryData, DemandData, MigrationData } from './types'

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function fetchSummary(): Promise<SummaryData> {
  const res = await fetch(`${BASE}/api/summary`, { cache: 'no-store' })
  if (!res.ok) throw new Error(`/api/summary ${res.status}`)
  return res.json()
}

export async function fetchDemand(): Promise<DemandData> {
  const res = await fetch(`${BASE}/api/demand`, { cache: 'no-store' })
  if (!res.ok) throw new Error(`/api/demand ${res.status}`)
  return res.json()
}

export async function fetchMigration(): Promise<MigrationData> {
  const res = await fetch(`${BASE}/api/migration`, { cache: 'no-store' })
  if (!res.ok) throw new Error(`/api/migration ${res.status}`)
  return res.json()
}
