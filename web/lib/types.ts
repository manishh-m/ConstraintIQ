export interface Zone {
  id: string
  name: string
  demand: number | null
  trend_per_day: number
}

export interface Hub {
  id: string
  name: string
  load: number
  capacity: number
  utilization: number
  zones: Zone[]
}

export interface BindingConstraint {
  resource_id: string
  utilization: number
}

export interface SummaryData {
  last_date: string
  hubs: Hub[]
  binding_constraint: BindingConstraint
  historical_migration_count: number
  forecast_horizon_days: number
}

export interface DemandRecord {
  date: string
  zone_id: string
  hub_id: string
  demand: number
}

export interface ForecastRecord {
  date: string
  zone_id: string
  hub_id: string
  forecast_demand: number
}

export interface ZoneMeta {
  id: string
  name: string
  hub: string
  base_demand: number
  trend_per_day: number
  weekly_seasonality: number
}

export interface DemandData {
  history: DemandRecord[]
  forecasts: ForecastRecord[]
  zones: ZoneMeta[]
}

export interface MigrationEvent {
  day: string
  from_resource: string
  to_resource: string
  projected_utilization: number
}

export interface UtilizationRecord {
  date: string
  resource_id: string
  load: number
  capacity: number
  utilization: number
}

export interface MigrationData {
  historical_events: MigrationEvent[]
  forecast_events: MigrationEvent[]
  utilization_history: UtilizationRecord[]
  projected_utilization: UtilizationRecord[]
  summary: string
}
